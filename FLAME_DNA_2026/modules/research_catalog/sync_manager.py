
"""
FLAME DNA - NASA Research Synchronization Manager

Synchronize NASA NTRS publications with the
local SQLite scientific research catalog.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from modules.research_catalog.ntrs_client import (
    search_publications as nasa_search,
)

from modules.research_catalog.catalog_store import (
    save_publications,
    count_publications,
)


BASE_DIR = Path(__file__).resolve().parents[2]

SYNC_LOG = (
    BASE_DIR
    / "data"
    / "research_catalog"
    / "metadata"
    / "sync_history.json"
)


DEFAULT_TOPICS = [
    "microgravity combustion",
    "spacecraft fire safety",
    "SAFFIRE fire experiment",
    "Advanced Combustion via Microgravity Experiments",
    "NASA space science",
]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def read_sync_history():
    """Read previous synchronization records."""

    if not SYNC_LOG.exists():
        return []

    with open(SYNC_LOG, "r", encoding="utf-8") as file:
        return json.load(file)


def save_sync_history(history):
    """Save synchronization history."""

    SYNC_LOG.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(SYNC_LOG, "w", encoding="utf-8") as file:
        json.dump(
            history,
            file,
            indent=2,
            ensure_ascii=False,
        )


def synchronize_nasa(
    topics=None,
    page_size=20,
    pages_per_topic=2,
):
    """
    Synchronize NASA publications by research topic.

    This is a bounded synchronization, not a
    complete mirror of the NASA archive.
    """

    if topics is None:
        topics = DEFAULT_TOPICS

    if not topics:
        raise ValueError("At least one topic is required.")

    if not 1 <= page_size <= 100:
        raise ValueError("Invalid page size.")

    if not 1 <= pages_per_topic <= 20:
        raise ValueError("Invalid number of pages.")

    started_at = utc_now()

    before = count_publications()

    total_received = 0
    total_processed = 0
    errors = []
    topic_results = []

    for topic in topics:

        topic_received = 0

        for page in range(pages_per_topic):

            try:
                response = nasa_search(
                    query=topic,
                    limit=page_size,
                    offset=page * page_size,
                )

                records = response.get("results", [])

                if not records:
                    break

                total_received += len(records)
                topic_received += len(records)

                processed = save_publications(records)

                total_processed += processed

                if len(records) < page_size:
                    break

            except Exception as error:
                errors.append({
                    "topic": topic,
                    "page": page + 1,
                    "error": str(error),
                })
                break

        topic_results.append({
            "topic": topic,
            "received": topic_received,
        })

    after = count_publications()

    result = {
        "started_at": started_at,
        "finished_at": utc_now(),
        "source": "NASA NTRS",
        "topics": topic_results,
        "received": total_received,
        "processed": total_processed,
        "new_publications": after - before,
        "total_local": after,
        "status": (
            "completed"
            if not errors
            else "partial"
        ),
        "errors": errors,
    }

    history = read_sync_history()
    history.append(result)
    save_sync_history(history)

    return result
