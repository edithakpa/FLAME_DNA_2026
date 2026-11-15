
"""
FLAME DNA - NASA Synchronization Interface
"""

import streamlit as st

from modules.research_catalog.sync_manager import (
    synchronize_nasa,
    read_sync_history,
    DEFAULT_TOPICS,
)


def render_sync_ui():

    st.subheader("Sources & Synchronization")

    st.caption(
        "Synchronize NASA NTRS publications "
        "with the local FLAME DNA research library."
    )

    st.markdown("#### NASA Research Topics")

    topics = st.multiselect(
        "Select research topics",
        options=DEFAULT_TOPICS,
        default=DEFAULT_TOPICS[:2],
        key="sync_topics",
    )

    col1, col2 = st.columns(2)

    with col1:
        page_size = st.selectbox(
            "Results per page",
            [5, 10, 20, 50],
            index=1,
            key="sync_page_size",
        )

    with col2:
        pages = st.number_input(
            "Pages per topic",
            min_value=1,
            max_value=10,
            value=1,
            key="sync_pages",
        )

    if st.button(
        "Synchronize NASA Research",
        key="sync_nasa_button",
        disabled=not topics,
    ):

        with st.spinner("Synchronizing NASA archives..."):

            try:
                result = synchronize_nasa(
                    topics=topics,
                    page_size=page_size,
                    pages_per_topic=int(pages),
                )

                st.session_state["last_sync_result"] = result

            except Exception as error:
                st.error(f"Synchronization failed: {error}")

    result = st.session_state.get("last_sync_result")

    if result:

        st.markdown("#### Latest Synchronization")

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Records Received",
            result["received"],
        )

        c2.metric(
            "New Publications",
            result["new_publications"],
        )

        c3.metric(
            "Library Total",
            result["total_local"],
        )

        if result["status"] == "completed":
            st.success("Synchronization completed.")
        else:
            st.warning(
                "Synchronization partially completed."
            )
            if result["errors"]:
                st.json(result["errors"])

    st.divider()

    st.markdown("#### Synchronization History")

    try:
        history = read_sync_history()
    except Exception as error:
        st.error(f"Unable to read history: {error}")
        return

    if history:

        for entry in reversed(history[-10:]):

            with st.expander(
                f"{entry['started_at']} — "
                f"{entry['status']}"
            ):

                st.write(
                    "**Source:**",
                    entry["source"],
                )

                st.write(
                    "**Publications received:**",
                    entry["received"],
                )

                st.write(
                    "**New publications:**",
                    entry["new_publications"],
                )

                st.write(
                    "**Local library total:**",
                    entry["total_local"],
                )

                st.write(
                    "**Research topics:**"
                )

                st.json(entry["topics"])

                if entry.get("errors"):
                    st.write("**Errors:**")
                    st.json(entry["errors"])

    else:
        st.info("No synchronization history available.")
