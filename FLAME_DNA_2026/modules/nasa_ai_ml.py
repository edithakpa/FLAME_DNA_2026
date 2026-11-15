"""FLAME DNA — scientific assistant using local NLP and machine learning.

No external AI service, key, Ollama, or additional model download required.
Retrieval: TF-IDF + Latent Semantic Analysis (TruncatedSVD).
Answer: extractive passages from NASA abstracts with traceable references.
"""

from pathlib import Path
import re
import sqlite3
import unicodedata
from urllib.parse import urlparse

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "research_catalog" / "nasa_catalog.db"

# Limited bilingual normalization. These terms are equivalents, not inferred findings.
TERMS = {
    "microgravity": ("microgravity", "microgravite", "micropesanteur", "weightlessness"),
    "flame": ("flame", "flames", "flamme", "flammes"),
    "fire": ("fire", "fires", "feu", "feux", "incendie", "incendies"),
    "combustion": ("combustion", "burning"),
    "oxygen": ("oxygen", "oxygene"),
    "temperature": ("temperature", "temperatures"),
    "spacecraft": ("spacecraft", "vaisseau", "vaisseaux"),
    "safety": ("safety", "securite"),
    "ignition": ("ignition", "allumage", "igniter"),
    "propagation": ("propagation", "spreading", "spread"),
    "experiment": ("experiment", "experiments", "experience", "experiences"),
    "material": ("material", "materials", "materiau", "materiaux"),
    "smoke": ("smoke", "fumee"),
}
REPLACEMENTS = [
    (re.compile(r"\b(?:" + "|".join(map(re.escape, vals)) + r")\b"), canonical)
    for canonical, vals in TERMS.items()
]


def normalized_text(value):
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\bsaffire\s*[-–]?\s*(?:i|1)\b", "saffire1", text)
    text = re.sub(r"\bsaffire\s*[-–]?\s*(?:ii|2)\b", "saffire2", text)
    text = re.sub(r"\bsaffire\s*[-–]?\s*(?:iii|3)\b", "saffire3", text)
    for pattern, replacement in REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text


def read_catalog(path=DB_PATH):
    if not path.is_file():
        raise FileNotFoundError(f"NASA database not found: {path}")
    # Read-only SQLite connection; nothing will be created or altered.
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute("""
            SELECT nasa_id, title, authors, publication_date, abstract, source_url
            FROM publications
            WHERE title IS NOT NULL
        """)]
    finally:
        connection.close()


def build_index(path=DB_PATH):
    publications = read_catalog(path)
    if not publications:
        raise ValueError("The NASA catalog contains no publications with a title.")

    documents = [normalized_text(
        " ".join([p.get("title") or ""] * 3 + [p.get("abstract") or ""])
    ) for p in publications]

    word_model = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
    char_model = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), max_features=16000)
    words = word_model.fit_transform(documents)
    chars = char_model.fit_transform(documents)

    lsa = None
    semantic_documents = None
    dimensions = min(24, words.shape[0] - 1, words.shape[1] - 1)
    if dimensions >= 2:
        lsa = TruncatedSVD(n_components=dimensions, random_state=42)
        semantic_documents = normalize(lsa.fit_transform(words))

    return {
        "publications": publications,
        "word_model": word_model,
        "word_matrix": words,
        "char_model": char_model,
        "char_matrix": chars,
        "lsa": lsa,
        "semantic_matrix": semantic_documents,
    }


def find_references(question, index, limit=5):
    text = normalized_text(question)
    q_words = index["word_model"].transform([text])
    q_chars = index["char_model"].transform([text])

    word_scores = cosine_similarity(q_words, index["word_matrix"]).ravel()
    char_scores = cosine_similarity(q_chars, index["char_matrix"]).ravel()
    scores = 0.65 * word_scores + 0.25 * char_scores

    if index["lsa"] is not None and q_words.nnz:
        q_sem = normalize(index["lsa"].transform(q_words))
        sem_scores = cosine_similarity(q_sem, index["semantic_matrix"]).ravel()
        scores += 0.10 * np.maximum(sem_scores, 0)

    # A lexical match is required; SVD alone must not manufacture evidence.
    matched = [i for i in np.argsort(-scores)
               if scores[i] >= 0.055 and (word_scores[i] > 0.01 or char_scores[i] > 0.04)]
    return [(index["publications"][i], float(scores[i])) for i in matched[:limit]]


def pick_excerpts(question, abstract, index, max_sentences=2):
    sentences = re.split(r"(?<=[.!?])\s+", str(abstract or "").strip())
    sentences = [s.strip() for s in sentences if len(s.strip()) > 35]
    if not sentences:
        return []
    q = index["word_model"].transform([normalized_text(question)])
    matrix = index["word_model"].transform([normalized_text(s) for s in sentences])
    scores = cosine_similarity(q, matrix).ravel()
    chosen = [int(i) for i in np.argsort(-scores)[:max_sentences]
              if scores[i] > 0.005]
    # Preserve the order of sentences within the document.
    return [sentences[i] for i in sorted(chosen)]


def valid_source_url(url):
    try:
        parsed = urlparse(str(url or "").strip())
        return parsed.geturl() if parsed.scheme in {"http", "https"} and parsed.netloc else None
    except ValueError:
        return None


def render_nasa_ai():
    import streamlit as st

    st.subheader("FLAME DNA — NASA AI Research Assistant")
    st.caption("Integrated NLP & machine learning · No API key · NASA-sourced answers")

    try:
        stamp = DB_PATH.stat().st_mtime_ns
        # Cached model shared safely across reruns; refreshed when the database changes.
        @st.cache_resource(show_spinner=False)
        def cached_model(database_stamp):
            return build_index(DB_PATH)
        index = cached_model(stamp)
    except (OSError, ValueError, sqlite3.Error) as exc:
        st.error(f"NASA Research Catalog unavailable: {exc}")
        return

    col1, col2 = st.columns(2)
    col1.metric("NASA Publications", len(index["publications"]))
    col2.metric("AI Technology", "TF-IDF + LSA")

    with st.form("flame_nlp_search_form", clear_on_submit=False, enter_to_submit=True, border=False):
        question = st.text_input(
            "Ask a scientific question",
            placeholder="What do NASA publications say about flames in microgravity?",
            key="flame_nlp_question",
        )
        submitted = st.form_submit_button("Analyze NASA Research", type="primary")
    if not submitted:
        return
    if not question.strip():
        st.warning("Please enter a question / Saisissez une question.")
        return

    results = find_references(question, index)
    if not results:
        st.warning("No sufficiently relevant text was found in the indexed NASA abstracts. ")
        st.caption("Try adding scientific terms in English, e.g. SAFFIRE, flame, ignition or microgravity.")
        return

    st.markdown("### Evidence-based scientific answer")
    st.caption("Extractive answer: the sentences below come directly from NASA abstracts. They are not generated findings.")
    facts_found = False
    for number, (publication, score) in enumerate(results[:3], start=1):
        excerpts = pick_excerpts(question, publication.get("abstract"), index)
        if not excerpts:
            continue
        facts_found = True
        st.markdown(f"**[{number}] {publication.get('title') or 'Untitled'}**")
        for sentence in excerpts:
            st.write(sentence)
    if not facts_found:
        st.info("Relevant publications were found, but their indexed abstracts provide no extractable answer. Open the sources below.")

    st.markdown("### NASA sources & traceability")
    for number, (publication, score) in enumerate(results, start=1):
        with st.expander(f"[{number}] {publication.get('title') or 'Untitled'}"):
            st.write("**NASA ID:**", publication.get("nasa_id") or "Not provided")
            st.write("**Authors:**", publication.get("authors") or "Not provided")
            st.write("**Date:**", publication.get("publication_date") or "Not provided")
            st.write("**Abstract:**", publication.get("abstract") or "Not available")
            url = valid_source_url(publication.get("source_url"))
            if url:
                st.link_button("Open publication", url)

    st.caption("Scientific limitations: text matching and LSA cannot independently verify claims or interpret missing measurements. Only the stored NASA abstracts are searched, not full PDF content.")
