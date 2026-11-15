"""FLAME DNA — exporte nasa_catalog.db (publications NTRS) en JSON pour le front web.

Usage : python tools/export_catalog.py --db data/research_catalog/nasa_catalog.db --out web/data
Ajoute un score de pertinence « sécurité incendie » transparent (mots-clés pondérés).
"""
import argparse
import json
import re
import sqlite3
from pathlib import Path

WEIGHTS = {
    r"spacecraft fire|fire safety": 5, r"saffire": 5, r"flame spread|flame propagation": 4,
    r"flammab": 4, r"extinguish|suppress": 4, r"smoke|detect": 3, r"ignition": 3,
    r"solid fuel|solids|material": 2, r"microgravity|low.gravity|reduced gravity": 2,
    r"combustion": 2, r"oxygen": 1, r"crew|habitat|exploration|iss|space station": 2,
    r"smolder": 3, r"droplet": 1, r"soot": 1,
}
TOPICS = [
    ("Spacecraft fire safety", r"spacecraft fire|fire safety|saffire|electrical fire"),
    ("Flame spread & solids", r"flame spread|solid|material|bass|thermoplastic|smolder|graphite|metal"),
    ("Droplets & sprays", r"droplet|spray|emulsion|aerosol|dust"),
    ("Gaseous flames", r"acme|gaseous|premixed|laminar|soot|cool flame"),
    ("Diagnostics", r"diagnostic|measurement|laser|fluorescence|sensing"),
    ("Programs & workshops", r"program|workshop|conference|plan"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", default="web/data")
    a = ap.parse_args()
    con = sqlite3.connect(a.db)
    con.row_factory = sqlite3.Row
    pubs = []
    for row in con.execute("select * from publications"):
        text = f"{row['title']} {row['abstract'] or ''}".lower()
        score = sum(w * min(3, len(re.findall(p, text))) for p, w in WEIGHTS.items())
        topic = next((t for t, p in TOPICS if re.search(p, text)), "Other")
        authors = row["authors"] or ""
        try:
            authors = ", ".join(json.loads(authors)) if authors.startswith("[") else authors
        except Exception:  # noqa: BLE001
            pass
        pubs.append({
            "id": row["nasa_id"], "title": row["title"].strip(), "authors": authors[:200],
            "year": (row["publication_date"] or "")[:4], "type": (row["document_type"] or "").replace("_", " ").title(),
            "abstract": (row["abstract"] or "").strip(), "url": row["source_url"], "source": row["source"],
            "topic": topic, "relevance": score,
        })
    mx = max(p["relevance"] for p in pubs) or 1
    for p in pubs:
        p["relevance"] = round(100 * p["relevance"] / mx)
    pubs.sort(key=lambda p: -p["relevance"])
    Path(a.out).mkdir(parents=True, exist_ok=True)
    Path(a.out, "publications.json").write_text(json.dumps(pubs, ensure_ascii=False, indent=1))
    print(len(pubs), "publications")


if __name__ == "__main__":
    main()
