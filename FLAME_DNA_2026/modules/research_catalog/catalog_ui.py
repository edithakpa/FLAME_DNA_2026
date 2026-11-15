
"""
FLAME DNA - NASA Research Catalog
Scientific library interface.
"""

import streamlit as st

from modules.research_catalog.sync_ui import render_sync_ui
from modules.research_catalog.online_search import (
    search_nasa_online,
    import_nasa_results,
)
from modules.research_catalog.experiments.experiment_ui import (
    render_experiments_ui,
)
from modules.research_catalog.search_engine import (
    search_publications,
    get_catalog_statistics,
)



def render_catalog():

    # ==========================================
    # RESEARCH CATALOG NAVIGATION
    # ==========================================

    catalog_section = st.radio(
        "Research Catalog Section",
        [
            "Scientific Library & NASA Search",
            "NASA Experiments & Datasets",
            "Sources & Synchronization",
        ],
        horizontal=True,
        key="research_catalog_section",
    )

    if catalog_section == "NASA Experiments & Datasets":
        render_experiments_ui()
        return

    if catalog_section == "Sources & Synchronization":
        render_sync_ui()
        return

    st.title("NASA Research Catalog")

    st.caption(
        "Explore NASA scientific publications, "
        "research reports and technical knowledge."
    )

    # ==========================================
    # LIBRARY STATISTICS
    # ==========================================

    stats = get_catalog_statistics()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Indexed Publications",
            stats["total_publications"],
        )

    with col2:
        st.metric(
            "Years Represented",
            stats["years_covered"],
        )

    with col3:
        st.metric(
            "Connected Sources",
            stats["sources"],
        )

    st.caption(
        "Statistics reflect locally indexed records, "
        "not the entire NASA archive."
    )

    # ==========================================
    # NASA ONLINE SEARCH
    # ==========================================

    st.subheader("NASA Online Search")

    st.caption(
        "Search the official NASA NTRS archive "
        "and import publications into FLAME DNA."
    )

    online_query = st.text_input(
        "Search NASA Archives",
        value="microgravity combustion",
        key="nasa_online_query",
    )

    page_size = st.selectbox(
        "Results per page",
        options=[5, 10, 20, 50],
        index=1,
        key="nasa_online_page_size",
    )

    if "nasa_online_page" not in st.session_state:
        st.session_state.nasa_online_page = 1

    if "nasa_online_results" not in st.session_state:
        st.session_state.nasa_online_results = None

    if st.button(
        "Search NASA",
        key="search_nasa_online_button",
    ):
        st.session_state.nasa_online_page = 1
        st.session_state.nasa_online_results = None

    def load_online_results():
        try:
            return search_nasa_online(
                query=online_query,
                page=st.session_state.nasa_online_page,
                page_size=page_size,
            )
        except Exception as error:
            st.error(f"NASA search failed: {error}")
            return None

    if online_query.strip():

        if st.session_state.nasa_online_results is None:
            with st.spinner("Searching NASA archives..."):
                st.session_state.nasa_online_results = (
                    load_online_results()
                )

        online_results = (
            st.session_state.nasa_online_results
        )

        if online_results:

            records = online_results["records"]

            st.write(
                f"**Page {online_results['page']} — "
                f"{len(records)} publications**"
            )

            for record in records:

                title = record.get(
                    "title",
                    "Untitled NASA Publication",
                )

                nasa_id = (
                    record.get("id")
                    or record.get("nasaId")
                )

                with st.expander(title):

                    st.write(
                        "**NASA ID:**",
                        nasa_id or "Not available",
                    )

                    st.write(
                        "**Abstract:**",
                        record.get("abstract")
                        or "No abstract available.",
                    )

                    if nasa_id:
                        st.link_button(
                            "View on NASA NTRS",
                            f"https://ntrs.nasa.gov/citations/{nasa_id}",
                        )

            if records:

                if st.button(
                    "Import This Page to Library",
                    key="import_nasa_page",
                ):
                    result = import_nasa_results(records)

                    st.success(
                        f"{result['new_publications']} new "
                        f"publications imported. "
                        f"Library total: {result['total_local']}"
                    )

            previous_col, next_col = st.columns(2)

            with previous_col:
                if st.button(
                    "Previous Page",
                    disabled=(
                        st.session_state.nasa_online_page <= 1
                    ),
                    key="nasa_previous_page",
                ):
                    st.session_state.nasa_online_page -= 1
                    st.session_state.nasa_online_results = None
                    st.rerun()

            with next_col:
                if st.button(
                    "Next Page",
                    disabled=len(records) < page_size,
                    key="nasa_next_page",
                ):
                    st.session_state.nasa_online_page += 1
                    st.session_state.nasa_online_results = None
                    st.rerun()

        else:
            st.info("No NASA online results available.")

    st.divider()

    # ==========================================
    # SCIENTIFIC SEARCH
    # ==========================================

    st.subheader("Scientific Library")

    keyword = st.text_input(
        "Search NASA publications",
        placeholder=(
            "Search by title, keywords or abstract..."
        ),
        key="catalog_keyword",
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        author = st.text_input(
            "Author",
            key="catalog_author",
        )

    with col2:
        year = st.text_input(
            "Publication Year",
            placeholder="e.g. 2024",
            key="catalog_year",
        )

    with col3:
        document_type = st.text_input(
            "Document Type",
            key="catalog_document_type",
        )

    results = search_publications(
        keyword=keyword,
        author=author,
        year=year,
        document_type=document_type,
        limit=500,
    )

    st.markdown(
        f"**{len(results)} publications found**"
    )

    # ==========================================
    # SEARCH RESULTS
    # ==========================================

    if not results:
        st.info(
            "No publications match your search."
        )
        return

    for publication in results:

        title = publication["title"]

        with st.expander(title):

            st.write(
                "**NASA ID:**",
                publication["nasa_id"],
            )

            st.write(
                "**Authors:**",
                publication["authors"] or "Not specified",
            )

            st.write(
                "**Publication Date:**",
                publication["publication_date"]
                or "Not specified",
            )

            st.write(
                "**Document Type:**",
                publication["document_type"]
                or "Not specified",
            )

            st.write("**Abstract:**")

            st.write(
                publication["abstract"]
                or "No abstract available."
            )

            if publication["source_url"]:
                st.link_button(
                    "View NASA Publication",
                    publication["source_url"],
                )
