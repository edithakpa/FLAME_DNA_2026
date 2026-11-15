"""FLAME DNA — fonction serverless Vercel (Python, bibliothèque standard uniquement).

GET  /api/chat  → {"llm": true|false, "model": "..."}  (le front sait si un LLM est branché)
POST /api/chat  → {"answer": "...", "model": "..."}

Le front calcule lui-même le contexte (données SAFFIRE, base de connaissances,
extraits de publications NASA) et l'envoie ici ; le LLM ne fait que rédiger une
réponse ANCRÉE dans ce contexte. Sans clé API, le front garde sa réponse locale.

Variables d'environnement (Vercel → Settings → Environment Variables) :
  GROQ_API_KEY                 → utilise Groq (gratuit) : modèle llama-3.3-70b-versatile
  ou LLM_API_KEY + LLM_BASE_URL (+ LLM_MODEL) → n'importe quelle API compatible OpenAI
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler

SYSTEM = (
    "You are FLAME DNA Copilot, a fire-safety science assistant for crewed space habitats "
    "(spacecraft, space stations, lunar/Mars bases, pressurized rovers), built on NASA microgravity "
    "combustion data (SAFFIRE I-III, PSI) and NASA NTRS publications. "
    "Answer ONLY from the CONTEXT provided (data metrics, knowledge base, publication excerpts, live monitoring state). "
    "If the context is insufficient, say so and suggest where to look (Data Explorer, NASA Catalog, PSI, NTRS). "
    "Never invent numbers. Quote figures with their units and sample IDs. "
    "Reply in the user's language (French if the question is in French). "
    "Use short Markdown: a direct answer first, then 2-5 bullet points, optionally a small table. "
    "Remind that simulated monitoring is not a certified fire-detection system when giving safety advice."
)


def _provider():
    if os.environ.get("GROQ_API_KEY"):
        return ("https://api.groq.com/openai/v1/chat/completions", os.environ["GROQ_API_KEY"],
                os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile"))
    if os.environ.get("LLM_API_KEY") and os.environ.get("LLM_BASE_URL"):
        base = os.environ["LLM_BASE_URL"].rstrip("/")
        return (f"{base}/chat/completions", os.environ["LLM_API_KEY"], os.environ.get("LLM_MODEL", "gpt-4o-mini"))
    return None


class handler(BaseHTTPRequestHandler):  # noqa: N801 (nom imposé par Vercel)
    def _send(self, code: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        p = _provider()
        self._send(200, {"llm": bool(p), "model": p[2] if p else None})

    def do_POST(self):  # noqa: N802
        p = _provider()
        if not p:
            return self._send(503, {"error": "no LLM configured"})
        try:
            length = min(int(self.headers.get("Content-Length", 0)), 200_000)
            req = json.loads(self.rfile.read(length) or b"{}")
            question = str(req.get("question", ""))[:2000]
            context = str(req.get("context", ""))[:24_000]
            history = req.get("history", [])[-6:]
        except Exception:  # noqa: BLE001
            return self._send(400, {"error": "bad request"})

        messages = [{"role": "system", "content": SYSTEM}]
        for h in history:
            if h.get("role") in ("user", "assistant") and h.get("content"):
                messages.append({"role": h["role"], "content": str(h["content"])[:2000]})
        messages.append({"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION: {question}"})

        url, key, model = p
        data = json.dumps({"model": model, "messages": messages, "temperature": 0.2, "max_tokens": 700}).encode()
        r = urllib.request.Request(url, data=data, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(r, timeout=25) as resp:
                out = json.loads(resp.read())
            answer = out["choices"][0]["message"]["content"]
            return self._send(200, {"answer": answer, "model": model})
        except urllib.error.HTTPError as e:
            return self._send(502, {"error": f"LLM HTTP {e.code}"})
        except Exception as e:  # noqa: BLE001
            return self._send(502, {"error": type(e).__name__})
