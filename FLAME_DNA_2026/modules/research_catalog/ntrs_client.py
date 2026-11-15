
"""
FLAME DNA - NASA NTRS Connector
Official NASA Technical Reports Server API.
"""

import requests


BASE_URL = "https://ntrs.nasa.gov/api"
TIMEOUT = 30


class NTRSError(Exception):
    """Raised when the NASA NTRS API request fails."""


def search_publications(query, limit=10, offset=0):
    """
    Search public NASA scientific and technical records.

    Returns the original API response for later processing.
    """
    query = query.strip()

    if not query:
        raise ValueError("Search query cannot be empty.")

    if not 1 <= limit <= 100:
        raise ValueError("Limit must be between 1 and 100.")

    if offset < 0:
        raise ValueError("Offset cannot be negative.")

    endpoint = f"{BASE_URL}/citations/search"

    params = {
        "q": query,
        "page.size": limit,
        "page.from": offset,
    }

    try:
        response = requests.get(
            endpoint,
            params=params,
            timeout=TIMEOUT,
            headers={
                "Accept": "application/json",
                "User-Agent": "FLAME-DNA-Research-Catalog/1.0",
            },
        )
        response.raise_for_status()
        return response.json()

    except requests.RequestException as error:
        raise NTRSError(
            f"NASA NTRS search failed: {error}"
        ) from error

    except ValueError as error:
        raise NTRSError(
            "NASA NTRS returned an invalid JSON response."
        ) from error


def get_publication(citation_id):
    """Retrieve a NASA publication using its citation ID."""
    citation_id = str(citation_id).strip()

    if not citation_id:
        raise ValueError("Citation ID cannot be empty.")

    endpoint = f"{BASE_URL}/citations/{citation_id}"

    try:
        response = requests.get(
            endpoint,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    except requests.RequestException as error:
        raise NTRSError(
            f"Unable to retrieve NASA citation: {error}"
        ) from error


def get_downloads(citation_id):
    """Retrieve available download information."""
    citation_id = str(citation_id).strip()

    if not citation_id:
        raise ValueError("Citation ID cannot be empty.")

    endpoint = f"{BASE_URL}/citations/{citation_id}/downloads"

    try:
        response = requests.get(
            endpoint,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    except requests.RequestException as error:
        raise NTRSError(
            f"Unable to retrieve download links: {error}"
        ) from error
