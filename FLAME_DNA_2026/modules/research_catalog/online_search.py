
"""
FLAME DNA - NASA Online Research Search

Search NASA NTRS and import publications
into the local research library.
"""

from modules.research_catalog.ntrs_client import (
    search_publications as nasa_search,
)

from modules.research_catalog.catalog_store import (
    save_publications,
    count_publications,
)


def search_nasa_online(query, page=1, page_size=10):
    """
    Search the NASA NTRS archive.

    Returns publication records and pagination metadata.
    """

    query = str(query).strip()

    if not query:
        raise ValueError("Enter a search keyword.")

    page = int(page)
    page_size = int(page_size)

    if page < 1:
        raise ValueError("Page must be at least 1.")

    if not 1 <= page_size <= 100:
        raise ValueError("Page size must be between 1 and 100.")

    offset = (page - 1) * page_size

    response = nasa_search(
        query=query,
        limit=page_size,
        offset=offset,
    )

    records = response.get("results", [])

    if not isinstance(records, list):
        raise ValueError("Unexpected NASA results format.")

    return {
        "query": query,
        "page": page,
        "page_size": page_size,
        "records": records,
        "received": len(records),
        "total": response.get("stats", {}).get("total"),
    }


def import_nasa_results(records):
    """
    Save NASA records into the local SQLite database.
    """

    if not isinstance(records, list):
        raise ValueError("Expected a list of NASA records.")

    before = count_publications()

    processed = save_publications(records)

    after = count_publications()

    return {
        "processed": processed,
        "new_publications": after - before,
        "total_local": after,
    }
