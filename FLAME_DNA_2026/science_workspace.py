
from pathlib import Path
import io
import re

import pandas as pd
import plotly.express as px
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "research_catalog" / "experiments" / "saffire_1"
TELEMETRY = DATA_DIR / "saffire_s2_telemetry_clean.csv"
SAMPLES = DATA_DIR / "experimental_table.csv"

ORANGE = "#F36B08"
GOLD = "#D9A441"
DARK = "#101010"


@st.cache_data(show_spinner="Loading SAFFIRE-I telemetry...")
def load_telemetry():
    if not TELEMETRY.exists():
        return pd.DataFrame()
    return pd.read_csv(TELEMETRY, low_memory=False)


@st.cache_data
def load_samples():
    if not SAMPLES.exists():
        return pd.DataFrame()
    return pd.read_csv(SAMPLES)


def numeric_columns(df):
    return df.select_dtypes(include="number").columns.tolist()


def time_column(df):
    candidates = [
        c for c in df.columns
        if re.search(r"time|elapsed|seconds", str(c), re.I)
    ]
    return candidates[0] if candidates else None


def style_figure(fig):
    fig.update_layout(
        paper_bgcolor=DARK,
        plot_bgcolor="#181818",
        font=dict(color="#F5F5F5"),
        colorway=[ORANGE, GOLD, "#21B6C7", "#B57EDC"],
        hovermode="x unified",
        legend=dict(orientation="h", y=-0.3),
        margin=dict(l=20, r=20, t=45, b=35),
    )
    fig.update_xaxes(gridcolor="#333333")
    fig.update_yaxes(gridcolor="#333333")
    return fig


def telemetry_required():
    df = load_telemetry()
    if df.empty:
        st.warning(
            "SAFFIRE-I S2 telemetry is unavailable. "
            "Check the data/research_catalog/experiments/saffire_1 folder."
        )
        return None
    return df


def csv_download(df, filename, key):
    st.download_button(
        "Download CSV",
        df.to_csv(index=False).encode("utf-8-sig"),
        file_name=filename,
        mime="text/csv",
        key=key,
    )


# =====================================================
# 1. DATA EXPLORER
# =====================================================

def render_data_explorer():
    st.subheader("Data Explorer")
    st.caption(
        "Explore recorded SAFFIRE-I S2 telemetry. "
        "These are experimental records, not live sensor readings."
    )

    source = st.radio(
        "Dataset",
        ["SAFFIRE-I S2 Telemetry", "SAFFIRE-I Experimental Table"],
        horizontal=True,
        key="explorer_source",
    )

    df = (
        telemetry_required()
        if source == "SAFFIRE-I S2 Telemetry"
        else load_samples()
    )
    if df is None or df.empty:
        st.warning("No records available for this dataset.")
        return

    a, b, c = st.columns(3)
    a.metric("Records", f"{len(df):,}")
    b.metric("Variables", len(df.columns))
    c.metric("Missing cells", f"{int(df.isna().sum().sum()):,}")

    t = time_column(df)
    filtered = df

    if t:
        time_values = pd.to_numeric(df[t], errors="coerce")
        if time_values.notna().any():
            lo = float(time_values.min())
            hi = float(time_values.max())
            if lo < hi:
                bounds = st.slider(
                    f"Time range — {t}",
                    min_value=lo,
                    max_value=hi,
                    value=(lo, hi),
                    key="explorer_time",
                )
                filtered = df.loc[
                    time_values.between(bounds[0], bounds[1])
                ].copy()

    st.markdown("### Data preview")
    st.dataframe(filtered.head(1000), width="stretch")
    csv_download(filtered, "flame_dna_explorer.csv", "explorer_csv")

    nums = numeric_columns(filtered)
    if not nums:
        st.info("No numeric variables available for plotting.")
        return

    default = [c for c in nums if c != t][:2]
    selected = st.multiselect(
        "Variables to visualize",
        nums,
        default=default,
        key="explorer_variables",
    )

    if not selected:
        st.info("Select at least one numeric variable.")
        return

    if t and t in filtered.columns:
        x = t
    else:
        filtered = filtered.copy()
        filtered["_row_index"] = range(len(filtered))
        x = "_row_index"

    plot_df = filtered[[x] + [c for c in selected if c != x]]
    if len(plot_df) > 3000:
        plot_df = plot_df.iloc[::max(1, len(plot_df) // 3000)]

    y = [c for c in selected if c != x]
    if y:
        fig = px.line(plot_df, x=x, y=y, title="Sensor trends")
        st.plotly_chart(style_figure(fig), width="stretch")
        st.caption(
            "Variables may have different units. "
            "Compare magnitudes only when units are compatible."
        )


# =====================================================
# 2. SCIENTIFIC ANALYSIS & COMPARISON
# =====================================================

def render_scientific_analysis():
    st.subheader("Scientific Analysis & Comparison")
    st.caption(
        "Descriptive analysis of available SAFFIRE-I S2 measurements. "
        "No SAFFIRE-II or SAFFIRE-III telemetry is integrated yet."
    )

    df = telemetry_required()
    if df is None:
        return

    nums = numeric_columns(df)
    t = time_column(df)
    sensors = [c for c in nums if c != t]

    if not sensors:
        st.warning("No numeric sensor columns detected.")
        return

    selected = st.multiselect(
        "Select sensors",
        sensors,
        default=sensors[:3],
        key="analysis_sensors",
    )
    if not selected:
        return

    stats = df[selected].describe().T.reset_index()
    stats = stats.rename(columns={"index": "Sensor"})

    st.markdown("### Descriptive statistics")
    st.dataframe(stats.round(4), width="stretch")
    csv_download(stats, "flame_dna_statistics.csv", "analysis_stats_csv")

    st.markdown("### Time-series comparison")
    if t and t in df:
        view = df[[t] + selected].copy()
        view[t] = pd.to_numeric(view[t], errors="coerce")
        view = view.dropna(subset=[t])
        if len(view) > 3000:
            view = view.iloc[::max(1, len(view) // 3000)]
        fig = px.line(view, x=t, y=selected)
        st.plotly_chart(style_figure(fig), width="stretch")
    else:
        st.info("A time variable was not identified automatically.")

    st.markdown("### Correlation analysis")
    if len(selected) >= 2:
        corr = df[selected].corr()
        fig = px.imshow(
            corr,
            zmin=-1,
            zmax=1,
            color_continuous_scale="RdBu_r",
            title="Pearson correlation matrix",
        )
        st.plotly_chart(style_figure(fig), width="stretch")
        st.caption(
            "Correlation describes statistical association; "
            "it does not establish causation."
        )
    else:
        st.info("Select at least two sensors for correlation analysis.")

    st.markdown("### Experiment availability")
    st.dataframe(
        pd.DataFrame([
            {"Experiment": "SAFFIRE-I", "Telemetry": "S2 available"},
            {"Experiment": "SAFFIRE-II", "Telemetry": "Not integrated"},
            {"Experiment": "SAFFIRE-III", "Telemetry": "Not integrated"},
        ]),
        hide_index=True,
        width="stretch",
    )


# =====================================================
# 3. SPACE MISSION FIRE SAFETY
# =====================================================

def render_fire_safety():
    st.subheader("Space Mission Fire Safety")
    st.caption(
        "Scientific interpretation workspace — "
        "not an operational spacecraft safety certification."
    )

    st.markdown("### Research context")
    st.write(
        "The SAFFIRE program investigates fire behavior and "
        "material flammability in spacecraft-relevant conditions. "
        "FLAME DNA helps inspect available experimental measurements "
        "and communicate observations with appropriate limitations."
    )

    st.markdown("### SAFFIRE-I S2: Available observations")
    df = telemetry_required()
    if df is None:
        return

    t = time_column(df)
    a, b, c = st.columns(3)
    a.metric("Telemetry records", f"{len(df):,}")
    b.metric("Recorded variables", len(df.columns))
    c.metric("Time variable", t or "Not identified")

    if "Igniter Power Enable" in df.columns and t:
        signal = pd.to_numeric(
            df["Igniter Power Enable"], errors="coerce"
        ).fillna(0)
        time = pd.to_numeric(df[t], errors="coerce")
        active = time[signal > 0]
        if not active.empty:
            st.info(
                f"Igniter-enable signal recorded from "
                f"{active.min():.3f} s to {active.max():.3f} s."
            )
            st.caption(
                "An electrical ignition signal does not, by itself, "
                "confirm that a flame formed or propagated."
            )

    st.markdown("### Interpretation framework")
    st.write(
        "**Observation:** Identify measured temperature, airflow, "
        "atmospheric and ignition signals."
    )
    st.write(
        "**Analysis:** Examine temporal changes and relationships "
        "between sensors."
    )
    st.write(
        "**Limitation:** Verify sensor units, calibration, "
        "experimental configuration and source documentation "
        "before making physical conclusions."
    )
    st.write(
        "**Safety relevance:** Use the findings to formulate "
        "research questions about fire detection, material behavior "
        "and risk monitoring in spacecraft."
    )

    st.warning(
        "This dashboard cannot establish material flammability "
        "limits, predict spacecraft fires, or recommend operational "
        "safety thresholds without validated models and complete "
        "experimental documentation."
    )


# =====================================================
# 4. AI ASSISTANT — DOCUMENTARY FOUNDATION
# =====================================================

KNOWLEDGE = [
    {
        "topic": "SAFFIRE program",
        "keywords": ["saffire", "programme", "program", "experiment"],
        "answer": (
            "SAFFIRE studies fire behavior and material flammability "
            "under spacecraft-relevant conditions. Its experimental "
            "results must be interpreted with the original documentation."
        ),
        "source": "SAFFIRE research context; verify NASA source documents",
    },
    {
        "topic": "SAFFIRE-I S2 telemetry",
        "keywords": ["telemetry", "sensor", "capteur", "temperature", "donnée"],
        "answer": (
            "FLAME DNA contains a processed SAFFIRE-I S2 telemetry file. "
            "Use Data Explorer and Scientific Analysis to inspect "
            "recorded variables and trends."
        ),
        "source": str(TELEMETRY.relative_to(ROOT)),
    },
    {
        "topic": "Ignition signal",
        "keywords": ["ignition", "igniter", "allumage", "flamme", "flame"],
        "answer": (
            "The Igniter Power Enable channel indicates an electrical "
            "activation command. It is not standalone proof of flame "
            "formation, growth or extinction."
        ),
        "source": str(TELEMETRY.relative_to(ROOT)),
    },
    {
        "topic": "Data limitations",
        "keywords": ["limite", "limit", "fiabilité", "quality", "unit", "unité"],
        "answer": (
            "Measurements require verification of units, calibration, "
            "sensor definitions and experimental conditions. "
            "SAFFIRE-II and III telemetry are not yet integrated."
        ),
        "source": "Local dataset inventory and current integration status",
    },
]


def render_ai_assistant():
    st.subheader("AI Assistant")
    st.caption(
        "Documentary question-answering prototype. "
        "This version uses a curated local knowledge base; "
        "it does not call a generative AI model or search NASA online."
    )

    question = st.text_input(
        "Ask a question about SAFFIRE or FLAME DNA",
        placeholder="Example: What does the igniter signal mean?",
        key="science_assistant_question",
    )

    if not question.strip():
        st.info(
            "Try asking about SAFFIRE, telemetry, "
            "ignition signals or data limitations."
        )
        return

    q = question.casefold()
    matched = [
        item for item in KNOWLEDGE
        if any(word.casefold() in q for word in item["keywords"])
    ]

    if not matched:
        st.warning(
            "No reliable answer found in the local knowledge base. "
            "Please consult the NASA Research Catalog."
        )
        return

    for item in matched[:3]:
        st.markdown(f"### {item['topic']}")
        st.write(item["answer"])
        st.caption(f"Reference / provenance: {item['source']}")

    st.caption(
        "The displayed references identify the supporting context; "
        "they are not automatically verified NASA publication citations."
    )
