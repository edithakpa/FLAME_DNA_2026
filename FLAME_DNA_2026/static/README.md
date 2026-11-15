# FLAME DNA — web app (Vercel-ready)

Static front-end (HTML/CSS/JS, no framework) + one Python serverless function (`api/chat.py`, standard library only).

## Deploy on Vercel
1. Push the project to GitHub.
2. On vercel.com → **Add New Project** → import the repo.
3. **Root Directory = `web`**, Framework preset = **Other**, no build command, no output directory.
4. *(Optional, smarter AI assistant)* Settings → Environment Variables:
   - `GROQ_API_KEY` = your free Groq key (model `llama-3.3-70b-versatile`), **or**
   - `LLM_API_KEY` + `LLM_BASE_URL` (+ `LLM_MODEL`) for any OpenAI-compatible API.
   Without a key the assistant runs on its local engine (data queries, live status, knowledge base, NASA paper retrieval).
5. Deploy.

## Run locally
```
cd web
python -m http.server 8000      # then open http://localhost:8000
```
(Opening `index.html` directly with file:// does not work: browsers block the JSON data files.)

## Regenerate the data (from the project root)
```
pip install -r tools/requirements-build.txt
python tools/build_web_data.py --src "C:/Users/USER/Desktop/saffire" --out web/data
python tools/export_catalog.py --db data/research_catalog/nasa_catalog.db --out web/data
```
`web/data/knowledge.json` (investigations, habitats, knowledge base) is hand-curated.

## Sections
Overview · Real-Time Monitoring (simulated sensors, fire replayed from SAFFIRE-I S1, multi-criteria alerts) ·
NASA Research Catalog (publications + reference sites) · Data Explorer (NASA files channel by channel + investigation ranking) ·
Scientific Comparison (common parameters only, similar-sample finder) · Mission Fire Safety (habitats, what-if, Earth benefits) · AI Assistant.
