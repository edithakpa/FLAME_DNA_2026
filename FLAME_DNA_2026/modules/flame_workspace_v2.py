"""FLAME DNA - Data Explorer, Scientific Analysis, Fire Safety context and Overview.

Every displayed measurement comes from a real local source file. Synthetic sensor
simulation is NOT loaded here. Missing S1 or Saffire-II telemetry is disclosed.
"""
from __future__ import annotations

from pathlib import Path
import math
import re
import sqlite3

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data" / "research_catalog" / "experiments"
S1_DIR = DATA_ROOT / "saffire_1"
SOURCE_URL = "https://psi.nasa.gov/physci/repo/data/investigations/PSI-98"
ORANGE, GOLD, AMBER = "#F36B08", "#D9A441", "#A96B35"
COLORS = [ORANGE, GOLD, "#A96B35", "#FFB16E", "#6BA9DE", "#B495D6"]

DATASETS = {
    "SAFFIRE-I S1 Telemetry": {
        "candidates": [
            S1_DIR / "saffire_s1_telemetry_clean.csv",
            S1_DIR / "saffire_s1_telemetry.csv",
            S1_DIR / "saffire_s1_sensor_data.csv",
        ],
        "pattern": "*Sample*1*Sensor*Data*.xlsx",
        "directory": S1_DIR,
        "type": "telemetry",
    },
    "SAFFIRE-I S2 Telemetry": {
        "candidates": [
            S1_DIR / "saffire_s2_telemetry_clean.csv",
            S1_DIR / "saffire_s2_telemetry.csv",
        ],
        "directory": S1_DIR,
        "type": "telemetry",
    },
    "SAFFIRE-II Telemetry": {
        "candidates": [
            DATA_ROOT / "saffire_2" / "saffire_ii_telemetry_clean.csv",
            DATA_ROOT / "saffire_2" / "saffire_ii_telemetry.csv",
            DATA_ROOT / "saffire_2" / "saffire_2_telemetry_clean.csv",
        ],
        "directory": DATA_ROOT / "saffire_2",
        "type": "telemetry",
    },
    "SAFFIRE-I Experimental Table": {
        "candidates": [S1_DIR / "experimental_table.csv"],
        "directory": S1_DIR,
        "type": "experimental",
    },
}


def _is_index_column(name):
    val = str(name).strip().casefold()
    return bool(re.fullmatch(r"(?:index|unnamed:\s*\d+|level_0|row[_ ]?index)", val))


def measurement_columns(df):
    """Only numeric sensor measurements, excluding index / row counters."""
    names = []
    for name in df.columns:
        if _is_index_column(name):
            continue
        if pd.api.types.is_numeric_dtype(df[name]) or \
                pd.to_numeric(df[name], errors="coerce").notna().sum() >= max(2, int(len(df) * 0.2)):
            names.append(name)
    return names


def time_column(df):
    for name in df.columns:
        if _is_index_column(name):
            continue
        if re.search(r"elapsed\s*time|mission\s*time|time\s*\(s\)|time\s*\[s\]|time\s*sec|seconds", str(name), re.I):
            if pd.to_numeric(df[name], errors="coerce").notna().sum() >= 2:
                return name
    for name in df.columns:
        if not _is_index_column(name) and re.fullmatch(r"time", str(name), flags=re.I):
            if pd.to_numeric(df[name], errors="coerce").notna().sum() >= 2:
                return name
    return None


def available_path(name):
    item = DATASETS[name]
    for file in item["candidates"]:
        if file.is_file():
            return file
    if "pattern" in item:
        directory = item["directory"]
        if directory.is_dir():
            files = sorted(directory.glob(item["pattern"]))
            return files[0] if files else None
    return None


@st.cache_data(show_spinner=False)
def _read_csv(path, mtime):
    try:
        df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="latin-1", low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df.dropna(how="all").copy()


@st.cache_data(show_spinner=False)
def _read_workbook(path, mtime):
    """Use only a worksheet with an identifiable time axis, never invented telemetry."""
    book = pd.ExcelFile(path)
    candidates = []
    for sheet in book.sheet_names:
        for header in (0, 1, 2, 3, 4, 5):
            try:
                df = pd.read_excel(book, sheet_name=sheet, header=header)
            except Exception:
                continue
            df.columns = [str(c).strip() for c in df.columns]
            df = df.dropna(how="all")
            tc = time_column(df)
            if tc and len(measurement_columns(df)) >= 3:
                candidates.append((len(df), len(measurement_columns(df)), sheet, df))
                break
    if not candidates:
        raise ValueError("No worksheet with an identifiable time column and numeric sensors was found. "
                         "Check the NASA file and its sensor definitions before conversion.")
    candidates.sort(reverse=True, key=lambda tup: (tup[0], tup[1]))
    _, _, sheet, data = candidates[0]
    return data, sheet


def load_dataset(name):
    path = available_path(name)
    if path is None:
        return None, None, None
    mtime = path.stat().st_mtime_ns
    if path.suffix.lower() in (".xlsx", ".xls"):
        df, sheet = _read_workbook(str(path), mtime)
    else:
        df, sheet = _read_csv(str(path), mtime), None
    # Remove any pre-existing index column from the analysis data.
    df = df.loc[:, [c for c in df.columns if not _is_index_column(c)]].copy()
    return df.reset_index(drop=True), path, sheet


def preview_with_index(df, limit=300):
    view = df.head(limit).reset_index(drop=True).copy()
    # Explicit first column 'Index' is for preview only, NEVER for statistics/charts.
    view.insert(0, "Index", range(1, len(view) + 1))
    return view


def _chart_style(fig):
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#171717", font=dict(color="#EDE8E2"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=30, r=20, t=62, b=45),
        hovermode="x unified",
        xaxis=dict(showgrid=True, gridcolor="#39312C", zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="#39312C", zeroline=False),
    )
    return fig


def sensor_trend_chart(df, selected, heading="Sensor Trends", max_points=2500):
    """Return a Plotly line chart akin to Real-Time Monitoring live trends."""
    tc = time_column(df)
    if not tc:
        return None
    x = pd.to_numeric(df[tc], errors="coerce")
    if x.notna().sum() < 2:
        return None
    # Evenly downsample large real telemetry sets for fast Streamlit Cloud rendering.
    step = max(1, math.ceil(len(df) / max_points))
    idx = x.notna() & x.apply(lambda y: math.isfinite(y) if pd.notna(y) else False)
    valid = df.loc[idx].iloc[::step].copy()
    fig = go.Figure()
    for pos, name in enumerate(selected):
        if name == tc or _is_index_column(name) or name not in df.columns:
            continue
        y = pd.to_numeric(valid[name], errors="coerce")
        if y.notna().sum() < 2:
            continue
        fig.add_trace(go.Scatter(
            x=pd.to_numeric(valid[tc], errors="coerce"), y=y,
            mode="lines", name=str(name), line=dict(color=COLORS[pos % len(COLORS)], width=2),
            connectgaps=False,
        ))
    if not fig.data:
        return None
    fig.update_layout(title=heading, xaxis_title=tc,
                      yaxis_title="Recorded value (see original sensor units)")
    return _chart_style(fig)


def _numeric_frame(df):
    out = pd.DataFrame(index=df.index)
    for name in measurement_columns(df):
        if not _is_index_column(name):
            out[name] = pd.to_numeric(df[name], errors="coerce")
    return out


def _select_dataset(key, default="SAFFIRE-I S2 Telemetry"):
    names = list(DATASETS)
    return st.selectbox("Choose NASA dataset", names, index=names.index(default), key=key)


def _missing(name):
    st.warning(f"{name} is not yet available as verified local telemetry.")
    st.write("The official SAFFIRE-I PSI-98 investigation identifies S1 and S2. "
             "An experimental sample record is NOT a sensor time series.")
    if name == "SAFFIRE-I S1 Telemetry":
        raw = S1_DIR / "experimental_table.csv"
        if raw.exists():
            exp = _read_csv(str(raw), raw.stat().st_mtime_ns)
            sample = next((c for c in exp.columns if c.casefold() == "sample number"), None)
            if sample:
                s1 = exp.loc[exp[sample].astype(str).str.strip().str.upper().eq("S1")]
                if not s1.empty:
                    st.markdown("#### S1 experimental record (not telemetry)")
                    st.dataframe(preview_with_index(s1), hide_index=True, width="stretch")
    st.link_button("Find original NASA SAFFIRE-I data (PSI-98)", SOURCE_URL)
    st.code("data/research_catalog/experiments/saffire_1/saffire_s1_telemetry_clean.csv")
    st.caption("Place an authenticated S1 sensor CSV at the path above to activate its charts. "
               "Alternatively, place the original S1 sensor workbook in the same folder.")


def render_explorer_v2():
    st.subheader("NASA Data Explorer")
    selected = _select_dataset("v2_explorer_choice")
    try:
        df, path, sheet = load_dataset(selected)
    except Exception as exc:
        st.error(f"Dataset could not be loaded: {exc}")
        return
    if df is None:
        _missing(selected)
        return
    st.caption(f"Local source: {path.relative_to(ROOT)}" + (f" · Worksheet: {sheet}" if sheet else ""))
    a, b, c = st.columns(3)
    a.metric("Rows", f"{len(df):,}")
    b.metric("Original variables", len(df.columns))
    c.metric("Numeric variables", len(measurement_columns(df)))
    st.markdown("### Dataset Preview")
    st.caption("Index is a preview row number only; it is never used as a sensor variable.")
    st.dataframe(preview_with_index(df), width="stretch", hide_index=True)
    st.download_button("Download Loaded Dataset (CSV)", df.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"{selected.lower().replace(' ', '_')}.csv", mime="text/csv", key="v2_explorer_download")
    st.markdown("### Interactive Visualization")
    num = _numeric_frame(df)
    if DATASETS[selected]["type"] == "experimental":
        _experimental_bars(df, key="v2_explorer_experimental")
        return
    tc = time_column(df)
    options = [c for c in num if c != tc and not _is_index_column(c)]
    if not options:
        st.info("No numeric sensor variables are available for charting.")
        return
    sensor = st.selectbox("Sensor variable", options, key="v2_explorer_variable_single")
    if sensor:
        fig = sensor_trend_chart(df, [sensor], f"{selected} — {sensor} Sensor Trend")
        if fig is None:
            st.warning("This dataset has no identifiable numeric time column. A temporal curve cannot be validated.")
        else:
            st.plotly_chart(fig, width="stretch", key="v2_explorer_chart")
            st.caption("Line curves show recorded NASA data, not live spacecraft monitoring.")


def _experimental_bars(df, key):
    sample_col = next((c for c in df if c.casefold() == "sample number"), None)
    numbers = [n for n in measurement_columns(df) if n != sample_col]
    if not numbers:
        st.info("No unambiguous numeric values for plotting; original entries are shown in the table.")
        return
    variable = st.selectbox("Experimental variable", numbers, key=f"{key}_var")
    y = pd.to_numeric(df[variable], errors="coerce")
    x = df[sample_col] if sample_col else pd.Series(range(1, len(df) + 1))
    fig = go.Figure([go.Bar(x=x, y=y, marker_color=ORANGE, name=variable)])
    fig.update_layout(title=f"Experimental Comparison — {variable}", xaxis_title="Sample", yaxis_title=variable)
    st.plotly_chart(_chart_style(fig), width="stretch", key=f"{key}_plot")
    st.caption("The experiment table records test conditions; it is not a time series.")


def _experimental_analysis():
    from modules.saffire_experimental_analysis import render_saffire_experimental_analysis
    render_saffire_experimental_analysis()


def _telemetry_analysis(name, key):
    st.markdown(f"### {name}")
    try:
        df, path, sheet = load_dataset(name)
    except Exception as exc:
        st.error(f"Unable to load {name}: {exc}")
        return
    if df is None:
        _missing(name)
        return
    st.caption("Source: " + str(path.relative_to(ROOT)) + (f" · Worksheet: {sheet}" if sheet else ""))
    nums = _numeric_frame(df)
    if nums.empty:
        st.warning("No numeric data available for statistical analysis.")
        return
    a, b, c = st.columns(3)
    a.metric("Measurements", f"{len(df):,}")
    b.metric("Sensor variables", len(nums.columns))
    c.metric("Time variable", time_column(df) or "Unavailable")
    st.markdown("#### Descriptive Statistics")
    # Explicitly remove the Index row, even if source CSV carried one.
    desc = nums.describe().T
    desc = desc.loc[[name for name in desc.index if not _is_index_column(name)]]
    st.dataframe(desc.round(4), width="stretch")
    st.download_button("Download Statistics (CSV)", desc.to_csv().encode("utf-8-sig"),
                       file_name=f"{key}_descriptive_statistics.csv", mime="text/csv", key=f"{key}_statistics_dl")
    st.markdown("#### Time-Series Comparison")
    tc = time_column(df)
    candidates = [n for n in nums if n != tc and not _is_index_column(n)]
    selected = st.selectbox("Sensor variable", candidates, key=f"{key}_single_sensor") if candidates else None
    if selected:
        figure = sensor_trend_chart(df, [selected], f"{name} — {selected} Sensor Trend")
        if figure is None:
            st.warning("The source does not contain an identifiable time coordinate for valid temporal curves.")
        else:
            st.plotly_chart(figure, width="stretch", key=f"{key}_timeseries")
    st.markdown("#### Correlation Analysis")
    corr_columns = [x for x in candidates if nums[x].nunique(dropna=True) > 1]
    if len(corr_columns) < 2:
        st.info("At least two variable numeric sensors are needed for correlation.")
        return
    corr = nums[corr_columns].corr(numeric_only=True, min_periods=3)
    if corr.empty or corr.isna().all().all():
        st.info("Correlation is unavailable for the selected data.")
        return
    fig = go.Figure(go.Heatmap(
        z=corr.values, x=corr.columns.tolist(), y=corr.index.tolist(),
        colorscale=[[0, "#173349"], [0.5, "#171717"], [1, ORANGE]],
        zmin=-1, zmax=1, colorbar=dict(title="r"),
    ))
    fig.update_layout(title="Sensor Correlation")
    st.plotly_chart(_chart_style(fig), width="stretch", key=f"{key}_corr")
    st.caption("Correlation does not establish causation. Sensor units and calibration must be confirmed.")


def _comparison_status():
    st.markdown("### Comparison Availability")
    s1 = available_path("SAFFIRE-I S1 Telemetry") is not None
    s2 = available_path("SAFFIRE-I S2 Telemetry") is not None
    ii = available_path("SAFFIRE-II Telemetry") is not None
    st.dataframe(pd.DataFrame([
        {"Experiment": "SAFFIRE-I", "Telemetry status": f"S1: {'Available' if s1 else 'Not integrated'} · S2: {'Available' if s2 else 'Not integrated'}"},
        {"Experiment": "SAFFIRE-II", "Telemetry status": "Available" if ii else "Not integrated"},
    ]), hide_index=True, width="stretch")
    st.caption("Availability is based on local files, not on an assumption about NASA data releases.")


def render_analysis_v2():
    st.subheader("Scientific Analysis & Comparison")
    s1, s2, table, ii = st.tabs([
        "SAFFIRE-I S1 Telemetry", "SAFFIRE-I S2 Telemetry",
        "SAFFIRE-I Experimental Table", "SAFFIRE-II Telemetry"
    ])
    with s1:
        _telemetry_analysis("SAFFIRE-I S1 Telemetry", "v2_s1")
    with s2:
        _telemetry_analysis("SAFFIRE-I S2 Telemetry", "v2_s2")
    with table:
        _experimental_analysis()
    with ii:
        _telemetry_analysis("SAFFIRE-II Telemetry", "v2_ii")
    _comparison_status()


def render_mission_context_v2():
    """Append this after the existing Space Mission Fire Safety content."""
    st.markdown("### Additional NASA Scientific Context")
    st.write(
        "According to NASA PSI-98, SAFFIRE-I investigated large-scale flame growth "
        "in microgravity using SIBAL fabric (approximately 75% cotton and 25% fiberglass), "
        "with an approximately 0.94 m × 0.4 m sample and 20 cm/s test airflow. "
        "Its instrumentation included thermocouples, radiometers, gas sensors, "
        "anemometers and cameras. These are investigation details, not a substitute "
        "for individual sensor recordings."
    )
    st.markdown("#### SAFFIRE-I S1 Experimental Conditions")
    path = available_path("SAFFIRE-I Experimental Table")
    if path:
        df, _, _ = load_dataset("SAFFIRE-I Experimental Table")
        col = next((c for c in df if c.casefold() == "sample number"), None)
        s1_rows = df.loc[df[col].astype(str).str.strip().str.upper().eq("S1")] if col else pd.DataFrame()
        if not s1_rows.empty:
            st.dataframe(preview_with_index(s1_rows), hide_index=True, width="stretch")
        else:
            st.info("The local experimental table has no identifiable S1 sample row.")
        st.markdown("#### SAFFIRE-I Experimental Table")
        st.dataframe(preview_with_index(df, limit=100), hide_index=True, width="stretch")
        st.caption("These are experimental conditions, not a record of flame propagation over time.")
    else:
        st.warning("The NASA experimental table is not available locally.")
    st.markdown("#### SAFFIRE-I S1 Telemetry")
    if available_path("SAFFIRE-I S1 Telemetry"):
        st.success("Local S1 sensor telemetry available in the Data Explorer and Scientific Analysis.")
    else:
        st.info("S1 time-series telemetry is not yet integrated. Do not infer it from the experimental sample table.")
    st.link_button("NASA SAFFIRE-I (PSI-98, DOI 10.60555/0t15-1z43)", SOURCE_URL)


def render_overview_update_v2():
    """Call INSIDE the original Overview branch, while retaining its existing content."""
    st.markdown("### Updated NASA Research Coverage")
    s1 = available_path("SAFFIRE-I S1 Telemetry") is not None
    s2 = available_path("SAFFIRE-I S2 Telemetry") is not None
    exp = available_path("SAFFIRE-I Experimental Table") is not None
    ii = available_path("SAFFIRE-II Telemetry") is not None
    a, b, c, d = st.columns(4)
    a.metric("SAFFIRE-I S1 Telemetry", "Available" if s1 else "Pending")
    b.metric("SAFFIRE-I S2 Telemetry", "Available" if s2 else "Pending")
    c.metric("SAFFIRE-I Test Table", "Available" if exp else "Pending")
    d.metric("SAFFIRE-II Telemetry", "Available" if ii else "Pending")
    db = ROOT / "data" / "research_catalog" / "nasa_catalog.db"
    try:
        with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True) as con:
            count = con.execute("SELECT COUNT(*) FROM publications").fetchone()[0]
        st.caption(f"NASA Scientific Library: {count} stored publications · 5 per page · "
                   f"{max(1, math.ceil(count / 5))} page(s).")
    except (sqlite3.Error, OSError):
        st.caption("NASA Scientific Library: catalog unavailable in this deployment.")
    st.caption("NASA experimental measurements and simulated real-time monitoring are separate data sources.")
