
"""
FLAME DNA - NASA Research Library
Local scientific publication search engine.
"""

from modules.research_catalog.catalog_store import (
    get_connection,
    initialize_database,
)


def search_publications(
    keyword="",
    author="",
    year="",
    document_type="",
    limit=100,
):
    """Search locally indexed NASA publications."""

    initialize_database()

    conditions = []
    parameters = []

    if keyword:
        conditions.append(
            "(title LIKE ? OR abstract LIKE ?)"
        )
        pattern = f"%{keyword.strip()}%"
        parameters.extend([pattern, pattern])

    if author:
        conditions.append("authors LIKE ?")
        parameters.append(f"%{author.strip()}%")

    if year:
        conditions.append(
            "substr(publication_date, 1, 4) = ?"
        )
        parameters.append(str(year).strip())

    if document_type:
        conditions.append("document_type LIKE ?")
        parameters.append(f"%{document_type.strip()}%")

    query = """
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
    """

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY publication_date DESC LIMIT ?"

    parameters.append(max(1, min(int(limit), 500)))

    with get_connection() as connection:
        rows = connection.execute(
            query,
            parameters,
        ).fetchall()

    return [dict(row) for row in rows]


def get_catalog_statistics():
    """Return statistics for locally indexed records."""

    initialize_database()

    with get_connection() as connection:
        total = connection.execute(
            "SELECT COUNT(*) FROM publications"
        ).fetchone()[0]

        years = connection.execute("""
            SELECT COUNT(DISTINCT substr(publication_date, 1, 4))
            FROM publications
            WHERE publication_date IS NOT NULL
              AND publication_date != ''
        """).fetchone()[0]

        sources = connection.execute("""
            SELECT COUNT(DISTINCT source)
            FROM publications
        """).fetchone()[0]

    return {
        "total_publications": total,
        "years_covered": years,
        "sources": sources,
    }
