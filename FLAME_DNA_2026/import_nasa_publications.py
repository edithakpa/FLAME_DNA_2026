
"""
FLAME DNA - NASA Research Library
Import NASA NTRS publications into SQLite.
"""

from modules.research_catalog.ntrs_client import (
    search_publications,
    NTRSError,
)

from modules.research_catalog.catalog_store import (
    save_publications,
    count_publications,
    get_publications,
)


SEARCH_TOPICS = [
    "microgravity combustion",
    "spacecraft fire safety",
    "NASA space science",
]


def extract_records(response):
    """Extract publication records from NTRS response."""

    if not isinstance(response, dict):
        raise ValueError("Unexpected NASA API response.")

    records = response.get("results")

    if records is None:
        raise ValueError(
            "NASA response does not contain a results field."
        )

    if not isinstance(records, list):
        raise ValueError(
            "NASA results must be a list."
        )

    return records


def main():
    print("=" * 55)
    print("FLAME DNA - NASA RESEARCH LIBRARY")
    print("=" * 55)

    for topic in SEARCH_TOPICS:
        print(f"\nSearching NASA: {topic}")

        try:
            response = search_publications(
                topic,
                limit=10,
            )

            records = extract_records(response)

            saved = save_publications(records)

            print(f"Records received: {len(records)}")
            print(f"Records processed: {saved}")

        except (NTRSError, ValueError) as error:
            print(f"Import error: {error}")

    print("\n" + "=" * 55)
    print("LOCAL NASA RESEARCH DATABASE")
    print("=" * 55)

    total = count_publications()

    print(f"Total unique publications: {total}")

    print("\nRecent stored publications:")

    for publication in get_publications(limit=5):
        print(f"- {publication['title']}")


if __name__ == "__main__":
    main()
