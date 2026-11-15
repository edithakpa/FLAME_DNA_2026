"""FLAME DNA | NASA PSI-98 SAFFIRE-I experimental sample comparison.

The NASA sample table is NOT time-series telemetry. No simulated data are used.
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "research_catalog" / "experiments" / "saffire_1"
CANDIDATES = [
    SOURCE_DIR / "experimental_table.csv",
    SOURCE_DIR / "PSI-98_Experimental table_SAFFIRE-1.csv",
]
ORANGE, GOLD = "#F36B08", "#D9A441"


def find_source():
    return next((path for path in CANDIDATES if path.is_file()), None)


@st.cache_data(show_spinner=False)
def read_experiment_table(path, mtime_ns):
    """Load without changing original NASA text values or units."""
    try:
        df = pd.read_csv(path, dtype="string", encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv(path, dtype="string", encoding="cp1252")
    df.columns = [str(col).strip() for col in df.columns]
    return df.dropna(how="all").copy()


def separate_records(df):
    """S1/S2 are actual samples; F1C1/F2C1 are pre-test records."""
    if "Sample Number" not in df.columns:
        raise ValueError("The NASA CSV has no 'Sample Number' column.")
    sample = df["Sample Number"].fillna("").str.strip()
    mask = sample.str.fullmatch(r"(?i)S\d+", na=False)
    return df.loc[mask].copy(), df.loc[~mask].copy()


def numeric_parameters(df):
    """Only unambiguous numeric columns; oxygen range strings stay as text."""
    excluded = {"Sample Number", "Index"}
    parameters = {}
    for name in df.columns:
        if name in excluded or str(name).lower().startswith("unnamed:"):
            continue
        values = pd.to_numeric(df[name], errors="coerce")
        if values.notna().all() and len(values) > 0:
            parameters[name] = values
    return parameters


def format_s(value, unit="s"):
    try:
        return f"{float(value):g} {unit}"
    except (ValueError, TypeError):
        return "Not available"


def render_saffire_experimental_analysis():
    st.subheader("SAFFIRE-I — Experimental Table")
    st.caption("NASA PSI-98 sample conditions. These data are not sensor telemetry.")

    source = find_source()
    if source is None:
        st.error("SAFFIRE-I experimental table not found. Place experimental_table.csv in data/research_catalog/experiments/saffire_1/.")
        return
    try:
        original = read_experiment_table(str(source), source.stat().st_mtime_ns)
        samples, pretests = separate_records(original)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        st.error(f"Unable to load the NASA experiment table: {exc}")
        return
    if samples.empty:
        st.warning("No experimental samples were identified in the CSV.")
        return

    st.caption(f"Local source: {source.relative_to(ROOT)} · {len(original)} records · {len(samples)} experimental samples")
    col1, col2, col3 = st.columns(3)
    col1.metric("Experimental Samples", len(samples))
    for col, name in [(col2, "S1"), (col3, "S2")]:
        subset = samples.loc[samples["Sample Number"].str.strip().eq(name)]
        burn = subset["Burn Time (s)"].iloc[0] if not subset.empty and "Burn Time (s)" in subset else None
        col.metric(f"{name} Burn Time", format_s(burn))

    names = samples["Sample Number"].str.strip().tolist()
    selected = st.multiselect("Samples to Compare", names, default=names, key="psi98_sample_choice")
    filtered = samples.loc[samples["Sample Number"].str.strip().isin(selected)].copy()
    if filtered.empty:
        st.info("Select one or more samples to display their experimental conditions.")
        return

    st.markdown("### Experimental Conditions")
    st.dataframe(filtered.fillna(""), hide_index=True, width="stretch")
    st.download_button("Download Selected Samples (CSV)", data=filtered.to_csv(index=False).encode("utf-8-sig"),
                       file_name="nasa_psi98_selected_samples.csv", mime="text/csv", key="psi98_sample_download")

    st.markdown("### Burn Time Comparison")
    if "Burn Time (s)" in filtered.columns:
        plot = filtered[["Sample Number", "Burn Time (s)"]].copy()
        plot["Burn Time (s)"] = pd.to_numeric(plot["Burn Time (s)"], errors="coerce")
        plot = plot.dropna(subset=["Burn Time (s)"])
        if not plot.empty:
            fig = go.Figure(go.Bar(x=plot["Sample Number"], y=plot["Burn Time (s)"],
                                   marker_color=[ORANGE if n == "S1" else GOLD for n in plot["Sample Number"]],
                                   text=plot["Burn Time (s)"], textposition="outside"))
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#171717",
                              xaxis_title="Sample", yaxis_title="Recorded burn time (s)",
                              font=dict(color="#F5F5F5"), showlegend=False)
            st.plotly_chart(fig, width="stretch", key="psi98_burn_chart")

    st.markdown("### Experimental Parameter Comparison")
    params = numeric_parameters(filtered)
    if params:
        parameter = st.selectbox("Parameter", list(params), key="psi98_parameter")
        numeric = params[parameter]
        fig = go.Figure(go.Bar(x=filtered["Sample Number"], y=numeric,
                               marker_color=[ORANGE if n == "S1" else GOLD for n in filtered["Sample Number"]]))
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#171717",
                          xaxis_title="Sample", yaxis_title=parameter, font=dict(color="#F5F5F5"))
        st.plotly_chart(fig, width="stretch", key="psi98_parameter_chart")
    st.caption("Percent O2 is displayed as reported (a range for S1 and an approximate value for S2); it is not converted into an exact sensor measurement.")

    if not pretests.empty:
        with st.expander(f"Other records ({len(pretests)} pre-test entries)"):
            st.dataframe(pretests.fillna(""), hide_index=True, width="stretch")

    st.info("Scientific interpretation: S1 and S2 have different airflow orientations (Concurrent and Opposed). Their reported burn times are not direct evidence of a causal relationship, a flame speed, or a validated fire-risk threshold. Separate NASA S1 telemetry is required for temporal sensor curves.")
