
from pathlib import Path
import re

import pandas as pd
import plotly.express as px
import streamlit as st


# =====================================================
# FLAME DNA — SCIENTIFIC WORKSPACE
# FLAMENOVA TECH
# =====================================================

ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = (
    ROOT
    / "data"
    / "research_catalog"
    / "experiments"
    / "saffire_1"
)

TELEMETRY_FILE = DATA_DIR / "saffire_s2_telemetry_clean.csv"
SAMPLES_FILE = DATA_DIR / "experimental_table.csv"

ORANGE = "#F36B08"
GOLD = "#D9A441"
DARK = "#101010"


# =====================================================
# DATA LOADING
# =====================================================

@st.cache_data(show_spinner="Loading SAFFIRE-I telemetry...")
def load_telemetry():
    if not TELEMETRY_FILE.exists():
        return pd.DataFrame()

    return pd.read_csv(
        TELEMETRY_FILE,
        low_memory=False,
    )


@st.cache_data(show_spinner=False)
def load_samples():
    if not SAMPLES_FILE.exists():
        return pd.DataFrame()

    return pd.read_csv(SAMPLES_FILE)


def numeric_columns(df):
    return df.select_dtypes(
        include="number"
    ).columns.tolist()


def find_time_column(df):
    candidates = [
        column
        for column in df.columns
        if re.search(
            r"time|elapsed|seconds",
            str(column),
            re.IGNORECASE,
        )
    ]

    return candidates[0] if candidates else None


def apply_chart_style(fig):
    fig.update_layout(
        paper_bgcolor=DARK,
        plot_bgcolor="#181818",
        font=dict(
            color="#F5F5F5"
        ),
        colorway=[
            ORANGE,
            GOLD,
            "#21B6C7",
            "#B57EDC",
        ],
        hovermode="x unified",
        margin=dict(
            l=20,
            r=20,
            t=45,
            b=35,
        ),
    )

    fig.update_xaxes(
        gridcolor="#333333"
    )

    fig.update_yaxes(
        gridcolor="#333333"
    )

    return fig


def require_telemetry():
    df = load_telemetry()

    if df.empty:
        st.warning(
            "SAFFIRE-I S2 telemetry is unavailable. "
            "Check the dataset folder."
        )
        return None

    return df


def download_csv(df, filename, key):
    st.download_button(
        label="Download CSV",
        data=df.to_csv(
            index=False
        ).encode("utf-8-sig"),
        file_name=filename,
        mime="text/csv",
        key=key,
    )


# =====================================================
# MODULE 1 — DATA EXPLORER
# =====================================================

def render_data_explorer():

    st.subheader("Data Explorer")

    st.caption(
        "Explore SAFFIRE-I experimental datasets "
        "and recorded sensor telemetry."
    )

    dataset_choice = st.radio(
        "Select Dataset",
        [
            "SAFFIRE-I S2 Telemetry",
            "SAFFIRE-I Experimental Table",
        ],
        horizontal=True,
        key="data_explorer_dataset",
    )

    if dataset_choice == "SAFFIRE-I S2 Telemetry":
        df = require_telemetry()
    else:
        df = load_samples()

    if df is None or df.empty:
        st.warning(
            "No data available for this dataset."
        )
        return

    # Dataset indicators
    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Total Records",
        f"{len(df):,}",
    )

    c2.metric(
        "Variables",
        len(df.columns),
    )

    c3.metric(
        "Missing Values",
        f"{int(df.isna().sum().sum()):,}",
    )

    # Time filtering
    time_col = find_time_column(df)

    filtered_df = df.copy()

    if time_col:
        time_values = pd.to_numeric(
            df[time_col],
            errors="coerce",
        )

        if time_values.notna().any():

            min_time = float(time_values.min())
            max_time = float(time_values.max())

            if min_time < max_time:

                selected_range = st.slider(
                    "Select Time Range",
                    min_value=min_time,
                    max_value=max_time,
                    value=(min_time, max_time),
                    key="explorer_time_range",
                )

                filtered_df = df.loc[
                    time_values.between(
                        selected_range[0],
                        selected_range[1],
                    )
                ].copy()

    st.markdown("### Dataset Preview")

    st.dataframe(
        filtered_df.head(1000),
        width="stretch",
        hide_index=True,
    )

    download_csv(
        filtered_df,
        "flame_dna_explorer.csv",
        "explorer_download",
    )

    # Interactive visualization
    st.markdown("### Interactive Visualization")

    numeric = numeric_columns(filtered_df)

    if not numeric:
        st.info(
            "No numeric variables available."
        )
        return

    default_columns = [
        col for col in numeric
        if col != time_col
    ][:2]

    selected_variables = st.multiselect(
        "Select Variables",
        numeric,
        default=default_columns,
        key="explorer_selected_variables",
    )

    if not selected_variables:
        st.info(
            "Select at least one variable."
        )
        return

    plot_df = filtered_df.copy()

    if time_col:
        x_axis = time_col
    else:
        plot_df["_row_index"] = range(
            len(plot_df)
        )
        x_axis = "_row_index"

    y_axis = [
        col
        for col in selected_variables
        if col != x_axis
    ]

    if not y_axis:
        st.info(
            "Select a sensor variable to visualize."
        )
        return

    # Reduce chart rendering cost
    if len(plot_df) > 3000:
        step = max(
            1,
            len(plot_df) // 3000,
        )

        plot_df = plot_df.iloc[::step]

    fig = px.line(
        plot_df,
        x=x_axis,
        y=y_axis,
        title="SAFFIRE-I Sensor Trends",
    )

    st.plotly_chart(
        apply_chart_style(fig),
        width="stretch",
    )

    st.caption(
        "Sensor variables may use different units. "
        "Do not compare their magnitudes directly "
        "without checking the measurement units."
    )


# =====================================================
# MODULE 2 — SCIENTIFIC ANALYSIS & COMPARISON
# =====================================================

def render_scientific_analysis():

    st.subheader(
        "Scientific Analysis & Comparison"
    )

    st.caption(
        "Statistical exploration of available "
        "SAFFIRE-I S2 telemetry measurements."
    )

    df = require_telemetry()

    if df is None:
        return

    time_col = find_time_column(df)

    sensors = [
        col
        for col in numeric_columns(df)
        if col != time_col
    ]

    if not sensors:
        st.warning(
            "No numeric sensor variables found."
        )
        return

    selected_sensors = st.multiselect(
        "Select Sensors",
        sensors,
        default=sensors[:3],
        key="scientific_sensors",
    )

    if not selected_sensors:
        st.info(
            "Select at least one sensor."
        )
        return

    # Descriptive statistics
    st.markdown(
        "### Descriptive Statistics"
    )

    statistics = (
        df[selected_sensors]
        .describe()
        .T
        .reset_index()
    )

    statistics = statistics.rename(
        columns={
            "index": "Sensor"
        }
    )

    st.dataframe(
        statistics.round(4),
        width="stretch",
        hide_index=True,
    )

    download_csv(
        statistics,
        "flame_dna_statistics.csv",
        "statistics_download",
    )

    # Temporal comparison
    st.markdown(
        "### Time-Series Comparison"
    )

    if time_col:

        plot_df = df[
            [time_col] + selected_sensors
        ].copy()

        plot_df[time_col] = pd.to_numeric(
            plot_df[time_col],
            errors="coerce",
        )

        plot_df = plot_df.dropna(
            subset=[time_col]
        )

        if len(plot_df) > 3000:
            step = max(
                1,
                len(plot_df) // 3000,
            )

            plot_df = plot_df.iloc[::step]

        fig = px.line(
            plot_df,
            x=time_col,
            y=selected_sensors,
            title="Sensor Comparison Over Time",
        )

        st.plotly_chart(
            apply_chart_style(fig),
            width="stretch",
        )

    else:
        st.info(
            "No time column identified."
        )

    # Correlation analysis
    st.markdown(
        "### Correlation Analysis"
    )

    if len(selected_sensors) >= 2:

        correlation = df[
            selected_sensors
        ].corr()

        fig = px.imshow(
            correlation,
            zmin=-1,
            zmax=1,
            color_continuous_scale="RdBu_r",
            title="Pearson Correlation Matrix",
        )

        st.plotly_chart(
            apply_chart_style(fig),
            width="stretch",
        )

        st.caption(
            "Correlation indicates statistical "
            "association, not causation."
        )

    else:
        st.info(
            "Select at least two sensors "
            "to calculate correlations."
        )

    # Experiment availability
    st.markdown(
        "### Experiment Comparison Availability"
    )

    availability = pd.DataFrame(
        [
            {
                "Experiment": "SAFFIRE-I",
                "Status": "S2 telemetry available",
            },
            {
                "Experiment": "SAFFIRE-II",
                "Status": "Telemetry not integrated",
            },
            {
                "Experiment": "SAFFIRE-III",
                "Status": "Telemetry not integrated",
            },
        ]
    )

    st.dataframe(
        availability,
        width="stretch",
        hide_index=True,
    )


# =====================================================
# MODULE 3 — SPACE MISSION FIRE SAFETY
# =====================================================

def render_fire_safety():

    st.subheader(
        "Space Mission Fire Safety"
    )

    st.caption(
        "Research-based interpretation of "
        "spacecraft fire safety experiments."
    )

    st.markdown(
        "### Scientific Context"
    )

    st.write(
        "The SAFFIRE experiments investigate "
        "fire behavior and material flammability "
        "under spacecraft-relevant conditions."
    )

    st.write(
        "FLAME DNA supports the exploration "
        "of experimental observations and "
        "their potential relevance to "
        "space mission fire safety."
    )

    st.markdown(
        "### SAFFIRE-I S2 Observations"
    )

    df = require_telemetry()

    if df is None:
        return

    time_col = find_time_column(df)

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Telemetry Records",
        f"{len(df):,}",
    )

    c2.metric(
        "Recorded Variables",
        len(df.columns),
    )

    c3.metric(
        "Time Variable",
        time_col or "Unknown",
    )

    # Igniter activation
    if (
        "Igniter Power Enable" in df.columns
        and time_col
    ):

        ignition_signal = pd.to_numeric(
            df["Igniter Power Enable"],
            errors="coerce",
        ).fillna(0)

        time_values = pd.to_numeric(
            df[time_col],
            errors="coerce",
        )

        active_times = time_values[
            ignition_signal > 0
        ]

        if not active_times.empty:

            start_time = float(
                active_times.min()
            )

            end_time = float(
                active_times.max()
            )

            st.info(
                "Igniter-enable signal detected "
                f"from {start_time:.3f} s "
                f"to {end_time:.3f} s."
            )

            st.caption(
                "The electrical activation signal "
                "does not independently confirm "
                "flame formation."
            )

    st.markdown(
        "### Scientific Interpretation"
    )

    st.write(
        "**Observation:** Examine temperature, "
        "airflow, atmosphere and ignition signals."
    )

    st.write(
        "**Analysis:** Compare sensor responses "
        "before, during and after ignition."
    )

    st.write(
        "**Limitations:** Verify sensor units, "
        "calibration and experimental conditions."
    )

    st.write(
        "**Safety Relevance:** Investigate "
        "possible implications for fire detection "
        "and material behavior in spacecraft."
    )

    st.warning(
        "FLAME DNA is a research prototype. "
        "Its current analyses do not establish "
        "validated fire-risk thresholds or "
        "operational spacecraft safety predictions."
    )


# =====================================================
# MODULE 4 — AI ASSISTANT
# =====================================================

KNOWLEDGE_BASE = [
    {
        "topic": "SAFFIRE Program",
        "keywords": [
            "saffire",
            "program",
            "programme",
            "experiment",
            "expérience",
        ],
        "answer": (
            "The SAFFIRE research program studies "
            "fire behavior and material flammability "
            "under spacecraft-relevant conditions."
        ),
        "source": (
            "SAFFIRE research context; "
            "consult original NASA documentation."
        ),
    },
    {
        "topic": "SAFFIRE-I S2 Telemetry",
        "keywords": [
            "telemetry",
            "sensor",
            "capteur",
            "temperature",
            "température",
            "données",
            "data",
        ],
        "answer": (
            "FLAME DNA contains processed "
            "SAFFIRE-I S2 telemetry. "
            "Use Data Explorer to inspect measurements "
            "and Scientific Analysis to compare trends."
        ),
        "source": str(
            TELEMETRY_FILE.relative_to(ROOT)
        ),
    },
    {
        "topic": "Ignition Signal",
        "keywords": [
            "ignition",
            "igniter",
            "allumage",
            "flamme",
            "flame",
        ],
        "answer": (
            "The Igniter Power Enable channel "
            "records electrical activation. "
            "This signal alone does not prove "
            "that a flame formed or propagated."
        ),
        "source": str(
            TELEMETRY_FILE.relative_to(ROOT)
        ),
    },
    {
        "topic": "Data Limitations",
        "keywords": [
            "limite",
            "limit",
            "quality",
            "fiabilité",
            "unit",
            "unité",
        ],
        "answer": (
            "Scientific interpretation requires "
            "verified sensor definitions, units, "
            "calibration and experimental conditions. "
            "SAFFIRE-II and III telemetry are "
            "not yet integrated."
        ),
        "source": (
            "Local dataset inventory "
            "and integration status."
        ),
    },
]


def render_ai_assistant():

    st.subheader("AI Assistant")

    st.caption(
        "Local documentary assistant prototype. "
        "This version uses a curated knowledge base "
        "and does not call an external generative AI."
    )

    question = st.text_input(
        "Ask a Question",
        placeholder=(
            "Example: What does the "
            "igniter signal mean?"
        ),
        key="ai_assistant_question",
    )

    if not question.strip():

        st.info(
            "Ask about SAFFIRE experiments, "
            "telemetry, ignition or data limitations."
        )

        return

    query = question.casefold()

    matching_entries = [
        item
        for item in KNOWLEDGE_BASE
        if any(
            keyword.casefold() in query
            for keyword in item["keywords"]
        )
    ]

    if not matching_entries:

        st.warning(
            "No reliable answer found "
            "in the local knowledge base. "
            "Please consult NASA Research Catalog."
        )

        return

    for entry in matching_entries[:3]:

        st.markdown(
            f"### {entry['topic']}"
        )

        st.write(
            entry["answer"]
        )

        st.caption(
            f"Reference: {entry['source']}"
        )

    st.caption(
        "References indicate local supporting "
        "context and are not automatically "
        "verified NASA publication citations."
    )
