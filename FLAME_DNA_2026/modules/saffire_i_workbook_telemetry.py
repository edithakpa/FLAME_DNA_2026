"""FLAME DNA: data review for the uploaded, processed SAFFIRE-I workbook.

The local source is a user-uploaded processed workbook, not independently
verified NASA S1 telemetry. Sample1/2 igniter channels are NOT labeled as
independent SAFFIRE-I S1/S2 telemetry data. Original measurements are preserved.
"""
from __future__ import annotations

from pathlib import Path
import json
import math
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "research_catalog" / "experiments" / "saffire_1"
SOURCES = {
    "SAFFIRE-I Instrument Channels": DIR / "saffire_i_workbook_telemetry.csv",
    "Cygnus Vehicle Channels": DIR / "saffire_i_workbook_cygnus.csv",
}
PROVENANCE = DIR / "saffire_i_workbook_provenance.json"
TIME = "Elapsed Since First Record (s)"
COLORS = ("#F36B08", "#D9A441", "#A96B35", "#74B6DA", "#C5A0E6", "#FF8C64")
EXCLUDE = re.compile(r"^(?:index|unnamed:\s*\d+|level_0|row[_ ]?index)$", re.I)
CONTEXT_URL = "https://psi.nasa.gov/physci/repo/data/investigations/PSI-98"


@st.cache_data(show_spinner=False)
def _read_source(path: str, mtime: int):
    df = pd.read_csv(path, low_memory=False, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    if TIME not in df.columns:
        raise ValueError(f"Time column missing: {TIME}")
    df[TIME] = pd.to_numeric(df[TIME], errors="coerce")
    df = df.loc[df[TIME].notna()].copy()
    return df.sort_values(TIME, kind="stable").reset_index(drop=True)


def _measurement_columns(df):
    result = []
    for col in df.columns:
        if EXCLUDE.fullmatch(col) or col == TIME:
            continue
        # Timestamps and timing metadata are x-axis/context, not sensors.
        if re.search(r"timestamp|relative time|delta timestamp|^rel-to-cygnus|^cygnus-saffire", col, re.I):
            continue
        num = pd.to_numeric(df[col], errors="coerce")
        if num.notna().sum() >= 5 and num.nunique(dropna=True) >= 2:
            result.append(col)
    return result


def _line_plot(df, selected, title):
    stride = max(1, math.ceil(len(df) / 2500))
    plot_df = df.iloc[::stride]
    fig = go.Figure()
    for idx, col in enumerate(selected):
        y = pd.to_numeric(plot_df[col], errors="coerce")
        if y.notna().sum() < 2:
            continue
        fig.add_trace(go.Scatter(
            x=plot_df[TIME], y=y, mode="lines", name=col,
            line={"color": COLORS[idx % len(COLORS)], "width": 2},
            connectgaps=False,
        ))
    fig.update_layout(
        title=title, template="plotly_dark", hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#151515",
        font={"color": "#F0ECE6"},
        legend={"orientation": "h", "y": 1.1, "x": 0},
        xaxis={"title": TIME, "gridcolor": "#35312C"},
        yaxis={"title": "Recorded sensor value (source units)", "gridcolor": "#35312C"},
        margin={"l": 30, "r": 20, "t": 70, "b": 45},
    )
    return fig


def _load_selected(name):
    path = SOURCES[name]
    if not path.is_file():
        st.warning(f"Missing data file: {path.relative_to(ROOT)}")
        return None
    try:
        return _read_source(str(path), path.stat().st_mtime_ns)
    except Exception as exc:
        st.error(f"Unable to read workbook export: {exc}")
        return None


def render_workbook_panel(key="workbook"):
    st.markdown("### SAFFIRE-I Processed Workbook — Sensor Records")
    st.caption("Historical experimental recordings. This panel is not live monitoring or a certified fire detector.")
    st.warning(
        "Source classification pending: the uploaded workbook has Sample 1/2 igniter channels, "
        "but it does not independently establish separate official S1 and S2 sensor telemetry datasets. "
        "Do not interpret negative/placeholder-like values without sensor calibration metadata."
    )
    name = st.selectbox("Recorded source", list(SOURCES), key=f"{key}_source")
    df = _load_selected(name)
    if df is None or df.empty:
        return
    sensor_names = _measurement_columns(df)
    c1, c2, c3 = st.columns(3)
    c1.metric("Valid time records", f"{len(df):,}")
    c2.metric("Variable channels", len(sensor_names))
    c3.metric("Recorded span", f"{df[TIME].max() - df[TIME].min():,.1f} s")

    st.markdown("#### Dataset Preview")
    preview = df.head(150).copy()
    preview.insert(0, "Index", range(1, len(preview) + 1))
    st.dataframe(preview, hide_index=True, width="stretch")
    st.download_button(
        "Download source records (CSV)", df.to_csv(index=False).encode("utf-8-sig"),
        file_name=SOURCES[name].name, mime="text/csv", key=f"{key}_download",
    )

    st.markdown("#### Interactive Sensor Trends")
    preferred = [v for v in (
        "Sample1IgniterV", "Sample2IgniterV", "Radiometer1Value", "Anemometer1",
        "PCM Air Temp (degC)", "PCM Press (psi)",
    ) if v in sensor_names]
    if not sensor_names:
        st.info("No numeric sensor channels available for plotting.")
        return
    selected = st.selectbox(
        "Sensor channel", sensor_names,
        index=sensor_names.index(preferred[0]) if preferred else 0,
        key=f"{key}_single_variable",
    )
    if selected:
        st.plotly_chart(_line_plot(df, [selected], f"{name} — {selected} Sensor Trend"),
                        width="stretch", key=f"{key}_trends")
        st.caption("Individual source channels can use different units. Compare curve shapes only when instrument units are verified.")
        st.markdown("#### Descriptive Statistics")
        stats = df[[selected]].apply(pd.to_numeric, errors="coerce").describe().T
        stats.index.name = "Sensor"
        st.dataframe(stats.reset_index().round(4), width="stretch", hide_index=True)
        corr_sensors = [c for c in sensor_names if c != selected][:5]
        if corr_sensors:
            st.markdown("#### Correlation Analysis")
            st.caption("Correlation uses multiple independent channels; it does not change the single sensor trend selection.")
            corr_names = [selected] + corr_sensors
            corr = df[corr_names].apply(pd.to_numeric, errors="coerce").corr()
            fig = go.Figure(data=go.Heatmap(
                z=corr.values, x=corr_names, y=corr_names,
                zmin=-1, zmax=1, colorscale="RdBu", reversescale=True,
                hovertemplate="%{y} / %{x}: %{z:.3f}<extra></extra>",
            ))
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                              plot_bgcolor="#151515", font={"color": "#F0ECE6"},
                              margin={"l": 35, "r": 20, "t": 30, "b": 40})
            st.plotly_chart(fig, width="stretch", key=f"{key}_correlation")

    with st.expander("Dataset provenance and limitations"):
        if PROVENANCE.is_file():
            try:
                metadata = json.loads(PROVENANCE.read_text(encoding="utf-8"))
                st.json(metadata)
            except (OSError, json.JSONDecodeError) as exc:
                st.warning(f"Unable to load provenance metadata: {exc}")
        st.link_button("Official NASA PSI-98 investigation (context)", CONTEXT_URL)
        st.caption("This NASA link identifies the investigation; it does not authenticate the uploaded processed workbook.")


def render_workbook_status():
    """Overview additions, without changing original KPIs."""
    st.markdown("#### SAFFIRE-I Workbook Integration Status")
    ready = [name for name, path in SOURCES.items() if path.is_file()]
    st.caption(f"Historical processed-workbook datasets installed: {len(ready)} of {len(SOURCES)}.")
    if ready:
        st.info("SAFFIRE-I processed workbook channels available for exploration. Dedicated NASA S1 telemetry source confirmation remains pending.")
    else:
        st.warning("Processed workbook sensor exports have not been installed.")


def render_workbook_context():
    st.markdown("#### SAFFIRE-I Instrument and Vehicle Data")
    st.write(
        "The processed workbook includes SAFFIRE instrument channels (radiometers, airflow and "
        "sample igniter circuits) alongside Cygnus spacecraft environmental channels. "
        "These are historical recordings, not live spacecraft sensors. "
        "The SAFFIRE-I Experimental Table separately documents test configurations for S1 and S2."
    )
    st.caption("Source: uploaded processed workbook; independent NASA provenance and calibration not confirmed.")
