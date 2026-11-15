
"""
FLAME DNA - NASA Research Catalog
Local SQLite storage for NASA publications.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]

DATABASE_PATH = (
    BASE_DIR / "data" / "research_catalog" / "nasa_catalog.db"
)


def get_connection():
    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection


def initialize_database():
    """Create the local NASA publication database."""

    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS publications (
                nasa_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                authors TEXT,
                publication_date TEXT,
                abstract TEXT,
                document_type TEXT,
                source TEXT NOT NULL,
                source_url TEXT,
                metadata_json TEXT,
                updated_at TEXT NOT NULL
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_publications_title
            ON publications(title)
        """)


def normalize_publication(record):
    """Convert a NASA NTRS record into a local format."""

    nasa_id = record.get("id") or record.get("nasaId")

    if not nasa_id:
        return None

    authors = record.get("authorAffiliations", [])

    if not authors:
        authors = record.get("authors", [])

    author_names = []

    for author in authors:
        if isinstance(author, dict):
            name = (
                author.get("meta", {}).get("author", {}).get("name")
                if isinstance(author.get("meta"), dict)
                else None
            )

            name = name or author.get("name")

            if name:
                author_names.append(str(name))

        elif isinstance(author, str):
            author_names.append(author)

    return {
        "nasa_id": str(nasa_id),
        "title": record.get("title") or "Untitled",
        "authors": ", ".join(author_names),
        "publication_date": (
            record.get("publicationDate")
            or record.get("created")
            or ""
        ),
        "abstract": record.get("abstract") or "",
        "document_type": (
            record.get("subjectCategory")
            or record.get("stiType")
            or ""
        ),
        "source": "NASA NTRS",
        "source_url": (
            f"https://ntrs.nasa.gov/citations/{nasa_id}"
        ),
        "metadata_json": json.dumps(
            record,
            ensure_ascii=False,
            default=str
        ),
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat()
    }


def save_publications(records):
    """Insert or update NASA publications."""

    initialize_database()

    saved = 0

    with get_connection() as connection:

        for record in records:
            publication = normalize_publication(record)

            if publication is None:
                continue

            connection.execute("""
                INSERT INTO publications (
                    nasa_id,
                    title,
                    authors,
                    publication_date,
                    abstract,
                    document_type,
                    source,
                    source_url,
                    metadata_json,
                    updated_at
                )
                VALUES (
                    :nasa_id,
                    :title,
                    :authors,
                    :publication_date,
                    :abstract,
                    :document_type,
                    :source,
                    :source_url,
                    :metadata_json,
                    :updated_at
                )
                ON CONFLICT(nasa_id)
                DO UPDATE SET
                    title = excluded.title,
                    authors = excluded.authors,
                    publication_date = excluded.publication_date,
                    abstract = excluded.abstract,
                    document_type = excluded.document_type,
                    source_url = excluded.source_url,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
            """, publication)

            saved += 1

    return saved


def get_publications(limit=100):
    """Read stored publications."""

    initialize_database()

    with get_connection() as connection:
        rows = connection.execute("""
            SELECT
                nasa_id,
                title,
                authors,
                publication_date,
                abstract,
                document_type,
                source,
                source_url
            FROM publications
            ORDER BY publication_date DESC
            LIMIT ?
        """, (limit,)).fetchall()

    return [dict(row) for row in rows]


def count_publications():
    """Count locally stored NASA publications."""

    initialize_database()

    with get_connection() as connection:
        result = connection.execute(
            "SELECT COUNT(*) FROM publications"
        ).fetchone()

    return result[0]
