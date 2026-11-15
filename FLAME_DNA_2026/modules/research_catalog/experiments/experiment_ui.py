
"""FLAME DNA - NASA Experiments & Datasets Interface."""

import streamlit as st

from modules.research_catalog.experiments.telemetry_ui import (
    render_telemetry_ui,
)

from modules.research_catalog.experiments.experiment_store import (
    get_experiments,
    get_datasets,
)


def render_experiments_ui():

    st.subheader(
        "NASA Experiments & Datasets"
    )

    st.caption(
        "Explore NASA experiments, scientific objectives, "
        "datasets and research sources."
    )

    experiments = get_experiments()

    if not experiments:
        st.info(
            "No NASA experiments registered yet."
        )
        return

    all_datasets = get_datasets()

    col1, col2 = st.columns(2)

    col1.metric(
        "Registered Experiments",
        len(experiments),
    )

    col2.metric(
        "Registered Datasets",
        len(all_datasets),
    )

    st.divider()

    experiment_options = {
        f"{exp['experiment_id']} - {exp['name']}": exp
        for exp in experiments
    }

    selected_name = st.selectbox(
        "Select NASA Experiment",
        options=list(experiment_options),
        key="selected_nasa_experiment",
    )

    experiment = experiment_options[selected_name]

    st.markdown(
        f"### {experiment['name']}"
    )

    st.write(
        "**Experiment ID:**",
        experiment["experiment_id"],
    )

    st.write(
        "**NASA Program:**",
        experiment["program"] or "Not specified",
    )

    st.write(
        "**Mission:**",
        experiment["mission"] or "Not specified",
    )

    st.markdown(
        "#### Scientific Objective"
    )

    st.write(
        experiment["objective"]
        or "No objective available."
    )

    st.markdown(
        "#### Experiment Description"
    )

    st.write(
        experiment["description"]
        or "No description available."
    )

    st.markdown(
        "#### Scientific Source"
    )

    st.write(
        experiment["source_name"]
        or "Not specified"
    )

    if experiment["source_url"]:
        st.link_button(
            "View NASA Source",
            experiment["source_url"],
        )

    st.divider()

    st.markdown(
        "#### Experimental Datasets"
    )

    datasets = get_datasets(
        experiment["experiment_id"]
    )

    if not datasets:
        st.info(
            "No experimental datasets registered "
            "for this experiment yet."
        )
    else:
        for dataset in datasets:

            with st.expander(
                dataset["dataset_name"]
            ):

                st.write(
                    "**Dataset ID:**",
                    dataset["dataset_id"],
                )

                st.write(
                    "**File Format:**",
                    dataset["file_format"]
                    or "Not specified",
                )

                st.write(
                    "**Description:**",
                    dataset["description"]
                    or "Not available",
                )

                st.write(
                    "**Local Path:**",
                    dataset["local_path"]
                    or "Not downloaded",
                )

                if dataset["source_url"]:
                    st.link_button(
                        "View Dataset Source",
                        dataset["source_url"],
                    )

    # SAFFIRE-I scientific visualization
    if experiment["experiment_id"] == "SAFFIRE-I":

        st.divider()

        st.markdown("#### SAFFIRE-I — Sensor Telemetry Analysis")
        with st.container(border=True):
            render_telemetry_ui()
