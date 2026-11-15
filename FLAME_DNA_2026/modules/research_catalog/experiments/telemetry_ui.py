
"""FLAME DNA - SAFFIRE-I S2 telemetry analysis (descriptive)."""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


BASE_DIR = Path(__file__).resolve().parents[3]

TELEMETRY_FILE = (
    BASE_DIR
    / "data"
    / "research_catalog"
    / "experiments"
    / "saffire_1"
    / "saffire_s2_telemetry_clean.csv"
)

SENSOR_GROUPS = {
    "Plume Temperatures": [
        f"Plume Temp {i} (TC{i})"
        for i in range(1, 7)
    ],
    "Sample Temperatures": [
        f"Sample Temp {i} (TC{i + 6})"
        for i in range(1, 7)
    ],
    "Atmospheric Measurements": [
        "O2",
        "CO2",
        "Humidity",
        "Ambient Pressure",
    ],
    "Airflow Measurements": [
        "Average Fan Speed",
        "Anemometer 1",
        "Anemometer 2",
    ],
    "Radiometers": [
        f"Radiometer {i}"
        for i in range(1, 5)
    ],
    "Ignition Measurements": [
        "Igniter Current",
        "Igniter Voltage",
        "Igniter Power Enable",
        "Igniter Voltage Set Point",
    ],
}


@st.cache_data(show_spinner=False)
def load_telemetry():
    return pd.read_csv(TELEMETRY_FILE)


def detect_igniter_intervals(
    df,
    time_column="Elapsed Time (s)",
):
    if "Igniter Power Enable" not in df.columns:
        return []

    active = pd.to_numeric(
        df["Igniter Power Enable"],
        errors="coerce",
    ).fillna(0).gt(0)

    starts = df.loc[
        active & ~active.shift(fill_value=False),
        time_column,
    ].tolist()

    ends = df.loc[
        active & ~active.shift(-1, fill_value=False),
        time_column,
    ].tolist()

    return list(zip(starts, ends))


def render_telemetry_ui():

    st.markdown(
        "### SAFFIRE-I — Sensor Telemetry Analysis"
    )

    st.caption(
        "SAFFIRE-I Sample 2: processed local telemetry. "
        "Sensor units and original NASA provenance require "
        "verification. Electrical activation is not proof "
        "of flame ignition."
    )

    if not TELEMETRY_FILE.is_file():
        st.warning(
            f"Telemetry file not found: {TELEMETRY_FILE}"
        )
        return

    try:
        df = load_telemetry()
    except (
        OSError,
        ValueError,
        pd.errors.ParserError,
    ) as exc:
        st.error(f"Unable to load telemetry: {exc}")
        return

    time_column = "Elapsed Time (s)"

    if time_column not in df.columns:
        st.error(
            "Elapsed Time (s) column not found."
        )
        return

    times = pd.to_numeric(
        df[time_column],
        errors="coerce",
    )

    valid = times.notna()

    df = df.loc[valid].copy()
    df[time_column] = times.loc[valid]

    if df.empty:
        st.warning(
            "No valid time measurements found."
        )
        return

    intervals = detect_igniter_intervals(
        df,
        time_column,
    )

    duration = float(
        df[time_column].max()
        - df[time_column].min()
    )

    a, b, c, d = st.columns(4)

    a.metric(
        "Measurements",
        f"{len(df):,}",
    )

    b.metric(
        "Columns",
        len(df.columns),
    )

    c.metric(
        "Recorded duration",
        f"{duration / 60:.2f} min",
    )

    d.metric(
        "Igniter activations",
        len(intervals),
    )

    st.divider()

    group = st.selectbox(
        "Select Sensor Group",
        list(SENSOR_GROUPS),
        key="telemetry_sensor_group",
    )

    sensors = [
        sensor
        for sensor in SENSOR_GROUPS[group]
        if sensor in df.columns
    ]

    selected = st.multiselect(
        "Select Sensors",
        sensors,
        default=sensors[:2],
        key="telemetry_selected_sensors",
    )

    if not selected:
        st.info("Select at least one sensor.")
        return

    lo = float(df[time_column].min())
    hi = float(df[time_column].max())

    if lo == hi:
        st.warning(
            "Only one recorded timestamp; "
            "time-range selection unavailable."
        )
        return

    start, end = st.slider(
        "Time Range (seconds)",
        min_value=lo,
        max_value=hi,
        value=(lo, hi),
        key="telemetry_time_range",
    )

    filtered = df.loc[
        df[time_column].between(
            start,
            end,
        )
    ]

    if filtered.empty:
        st.warning(
            "No measurements in this interval."
        )
        return

    fig = go.Figure()

    for sensor in selected:
        fig.add_trace(
            go.Scatter(
                x=filtered[time_column],
                y=pd.to_numeric(
                    filtered[sensor],
                    errors="coerce",
                ),
                mode="lines",
                name=sensor,
            )
        )

    # Automatic ignition command detection
    for i, (begin, finish) in enumerate(intervals):

        if finish < start or begin > end:
            continue

        fig.add_vrect(
            x0=begin,
            x1=finish,
            fillcolor="#F97316",
            opacity=0.20,
            line_width=0,
            annotation_text=(
                "Igniter enabled"
                if i == 0
                else None
            ),
            annotation_position="top left",
        )

    fig.update_layout(
        title=f"SAFFIRE-I S2 — {group}",
        xaxis_title="Elapsed Time (s)",
        yaxis_title=(
            "Recorded sensor value "
            "(units unverified)"
        ),
        hovermode="x unified",
        height=480,
        margin=dict(
            l=30,
            r=20,
            t=60,
            b=30,
        ),
    )

    st.plotly_chart(
        fig,
        width="stretch",
        key="saffire_telemetry_chart",
    )

    st.markdown(
        "#### Sensor statistics — selected time range"
    )

    stats = (
        filtered[selected]
        .apply(
            pd.to_numeric,
            errors="coerce",
        )
        .describe()
        .T
    )

    st.dataframe(
        stats,
        width="stretch",
    )

    st.download_button(
        "Download selected measurements (CSV)",
        data=filtered[
            [time_column] + selected
        ].to_csv(index=False).encode("utf-8"),
        file_name=(
            "saffire_i_s2_selected_measurements.csv"
        ),
        mime="text/csv",
        key="saffire_i_s2_download",
    )

    # Scientific temperature comparison
    st.markdown(
        "#### Igniter activation and temperature response"
    )

    if not intervals:
        st.info(
            "No igniter activation detected in this file."
        )
        return

    st.caption(
        "Exploratory comparison: 20 seconds before "
        "each activation, and 20 seconds after its "
        "last active sample. These windows are not "
        "official NASA experimental phases."
    )

    temp_sensors = [
        sensor
        for sensor in (
            SENSOR_GROUPS["Plume Temperatures"]
            + SENSOR_GROUPS["Sample Temperatures"]
        )
        if sensor in df.columns
    ]

    records = []

    for idx, (begin, finish) in enumerate(
        intervals,
        1,
    ):

        before = df.loc[
            df[time_column].between(
                begin - 20,
                begin,
                inclusive="left",
            )
        ]

        after = df.loc[
            df[time_column].between(
                finish,
                finish + 20,
                inclusive="right",
            )
        ]

        for sensor in temp_sensors:

            before_mean = (
                pd.to_numeric(
                    before[sensor],
                    errors="coerce",
                ).mean()
                if not before.empty
                else float("nan")
            )

            after_mean = (
                pd.to_numeric(
                    after[sensor],
                    errors="coerce",
                ).mean()
                if not after.empty
                else float("nan")
            )

            records.append({
                "Activation": idx,
                "Sensor": sensor,
                "Start (s)": round(
                    float(begin),
                    3,
                ),
                "End (s)": round(
                    float(finish),
                    3,
                ),
                "Before mean": before_mean,
                "After mean": after_mean,
                "Difference": (
                    after_mean - before_mean
                ),
            })

    result = pd.DataFrame.from_records(
        records
    )

    st.dataframe(
        result.round(3),
        width="stretch",
        hide_index=True,
    )

    st.download_button(
        "Download temperature comparison (CSV)",
        data=result.to_csv(
            index=False
        ).encode("utf-8"),
        file_name=(
            "saffire_i_s2_temperature_comparison.csv"
        ),
        mime="text/csv",
        key="saffire_i_s2_comparison_download",
    )

    st.caption(
        "Observed differences are descriptive "
        "and do not establish causality, flame "
        "formation, spread, or fire risk. "
        "Units and sensor positions must be verified."
    )
