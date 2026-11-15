"""FLAME DNA - 5-publication pagination for the NASA research catalogue.

Works on Streamlit Community Cloud. Uses the project's nasa_catalog.db for its
Scientific Library and the official NASA NTRS API for online results.
No API key required. Does not silently fabricate publications.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path
import sqlite3
from urllib.parse import urlparse
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "research_catalog" / "nasa_catalog.db"
PAGE_SIZE = 5
NTRS = "https://ntrs.nasa.gov/api/citations/search"


def _safe_url(url):
    value = str(url or "").strip()
    parsed = urlparse(value)
    return value if parsed.scheme in ("http", "https") and parsed.netloc else None


def _read_library():
    if not DB.is_file():
        raise FileNotFoundError(f"Local NASA catalog not found: {DB}")
    # URI read-only mode prevents SQLite from creating an empty database.
    with sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(r) for r in connection.execute(
            "SELECT nasa_id, title, authors, publication_date, abstract, document_type, source_url "
            "FROM publications ORDER BY publication_date DESC, title ASC"
        ).fetchall()]


def _page_nav(prefix, current, total, total_count):
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if st.button("◀ Previous", disabled=current <= 1, key=f"{prefix}_prev"):
            st.session_state[f"{prefix}_page"] = current - 1
            st.rerun()
    with c2:
        st.markdown(
            f"<p style='text-align:center'>Page {current} of {total} "
            f"· {total_count:,} publication(s) · {PAGE_SIZE} per page</p>",
            unsafe_allow_html=True,
        )
    with c3:
        if st.button("Next ▶", disabled=current >= total, key=f"{prefix}_next"):
            st.session_state[f"{prefix}_page"] = current + 1
            st.rerun()


def render_scientific_library():
    st.subheader("Scientific Library")
    try:
        records = _read_library()
    except (FileNotFoundError, sqlite3.Error) as exc:
        st.error(str(exc))
        return

    # One form: pressing Enter and clicking Search do the same thing.
    with st.form("v2_library_search_form", clear_on_submit=False,
                 enter_to_submit=True, border=False):
        search = st.text_input("Search saved NASA publications", key="v2_library_search")
        submitted = st.form_submit_button("Search", type="primary")

    # Keep the last submitted query during pagination and other reruns.
    if submitted:
        value = search.casefold().strip()
        if value != st.session_state.get("v2_lib_last_query", ""):
            st.session_state["v2_library_page"] = 1
        st.session_state["v2_lib_last_query"] = value
        st.session_state["v2_library_query"] = value

    value = st.session_state.get("v2_library_query", "")

    filtered = [r for r in records if any(
        value in str(r.get(field) or "").casefold()
        for field in ("title", "authors", "abstract", "nasa_id")
    )] if value else records

    total = max(1, math.ceil(len(filtered) / PAGE_SIZE))
    current = max(1, min(total, st.session_state.get("v2_library_page", 1)))
    st.session_state["v2_library_page"] = current
    st.metric("Saved NASA Publications", len(records))
    st.caption(f"Showing {len(filtered):,} matching publication(s).")
    page_records = filtered[(current - 1) * PAGE_SIZE:current * PAGE_SIZE]

    if not page_records:
        st.info("No publications match this search.")
    for pos, rec in enumerate(page_records, start=(current - 1) * PAGE_SIZE + 1):
        title = rec.get("title") or "Untitled publication"
        with st.expander(f"{pos}. {title}"):
            st.write("**NASA ID:**", rec.get("nasa_id") or "Not recorded")
            st.write("**Authors:**", rec.get("authors") or "Not recorded")
            st.write("**Publication date:**", rec.get("publication_date") or "Not recorded")
            st.write("**Document type:**", rec.get("document_type") or "Not recorded")
            st.write("**Abstract:**", rec.get("abstract") or "No abstract available.")
            if url := _safe_url(rec.get("source_url")):
                st.link_button("Open NASA Source", url)
    _page_nav("v2_library", current, total, len(filtered))


@st.cache_data(ttl=1200, show_spinner=False)
def _ntrs_search(query: str, page: int):
    # NASA NTRS provides server-side pagination via the page.from and page.size keys.
    params = {"q": query, "page.size": PAGE_SIZE, "page.from": (page - 1) * PAGE_SIZE}
    response = requests.get(NTRS, params=params, timeout=25,
                            headers={"User-Agent": "FLAME-DNA-Research-Dashboard/1.0"})
    response.raise_for_status()
    obj = response.json()
    if not isinstance(obj, dict):
        raise ValueError("NASA API returned an unexpected response.")
    results = obj.get("results") or []
    if not isinstance(results, list):
        raise ValueError("NASA API results format is unsupported.")
    stats = obj.get("stats") or {}
    total = stats.get("total") if isinstance(stats, dict) else None
    try:
        total = max(0, int(total)) if total is not None else None
    except (ValueError, TypeError):
        total = None
    return results, total


def render_online_search():
    st.subheader("NASA Online Search (NTRS)")
    st.caption("Live search of NASA's Technical Reports Server. Five results per page. Internet required.")
    with st.form("v2_ntrs_search_form", clear_on_submit=False, enter_to_submit=True, border=False):
        typed = st.text_input("NASA research keywords", value="microgravity fire saffire", key="v2_ntrs_input")
        submitted = st.form_submit_button("Search NASA", type="primary")
    if submitted:
        st.session_state["v2_ntrs_query"] = typed.strip()
        st.session_state["v2_ntrs_page"] = 1
    query = st.session_state.get("v2_ntrs_query", "")
    if not query:
        st.info("Enter keywords and click Search NASA to load online publications.")
        return
    page = max(1, st.session_state.get("v2_ntrs_page", 1))
    try:
        with st.spinner("Searching NASA NTRS..."):
            rows, total = _ntrs_search(query, page)
    except (requests.RequestException, ValueError) as exc:
        st.warning(f"NASA online search is temporarily unavailable: {exc}")
        st.info("The saved Scientific Library remains available without Internet access.")
        return

    total_pages = max(1, math.ceil(total / PAGE_SIZE)) if total is not None else None
    if not rows:
        st.info("No NASA publications found on this page.")
    for pos, rec in enumerate(rows, start=(page - 1) * PAGE_SIZE + 1):
        title = rec.get("title") or "Untitled NASA record"
        with st.expander(f"{pos}. {title}"):
            st.write("**NASA ID:**", rec.get("id") or "Not recorded")
            st.write("**Publication date:**", rec.get("publicationDate") or rec.get("publicationYear") or "Not recorded")
            st.write("**Abstract:**", rec.get("abstract") or "Not available in search result.")
            if rec.get("id"):
                st.link_button("Open NASA Citation", f"https://ntrs.nasa.gov/citations/{rec['id']}")
    # If total isn't returned, pagination remains possible as long as a full page was returned.
    if total_pages is not None:
        _page_nav("v2_ntrs", page, total_pages, total)
    else:
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if st.button("◀ Previous", key="v2_ntrs_prev", disabled=page <= 1):
                st.session_state["v2_ntrs_page"] = page - 1
                st.rerun()
        with c2:
            st.markdown(f"Page {page} · up to {PAGE_SIZE} results per page")
        with c3:
            if st.button("Next ▶", key="v2_ntrs_next", disabled=len(rows) < PAGE_SIZE):
                st.session_state["v2_ntrs_page"] = page + 1
                st.rerun()


def render_catalog_v2():
    st.title("NASA Research Catalog")
    lib, online, experimental, sources = st.tabs([
        "Scientific Library", "NASA Online Search", "NASA Experiments & Datasets", "Sources & Synchronization"
    ])
    with lib:
        render_scientific_library()
    with online:
        render_online_search()
    with experimental:
        try:
            from modules.research_catalog.experiments.experiment_ui import render_experiments_ui
            render_experiments_ui()
        except ImportError as exc:
            st.warning(f"Existing experiments UI not available: {exc}")
            st.link_button("Open NASA SAFFIRE-I investigation", "https://psi.nasa.gov/physci/repo/data/investigations/PSI-98")
    with sources:
        st.markdown("### Scientific data provenance")
        st.write("**NASA SAFFIRE-I investigation:** PSI-98 · DOI 10.60555/0t15-1z43")
        st.link_button("NASA PSI-98 Official Data", "https://psi.nasa.gov/physci/repo/data/investigations/PSI-98")
        st.link_button("NASA Technical Reports Server", "https://ntrs.nasa.gov/")
        st.caption("Online search does not automatically alter your local SQLite library.")
        st.markdown("#### Original Catalog Management Tools")
        st.caption("The previous import and synchronization interface remains available here if installed. "
                   "Its original pagination settings are unchanged; use the tabs above for 5-per-page browsing.")
        if st.button("Show / Hide Original Management Tools", key="v2_legacy_toggle"):
            st.session_state["v2_legacy_open"] = not st.session_state.get("v2_legacy_open", False)
        if st.session_state.get("v2_legacy_open", False):
            try:
                from modules.research_catalog.catalog_ui import render_catalog
                render_catalog()
            except ImportError as exc:
                st.warning(f"Original catalog tools are not installed: {exc}")
