#!/usr/bin/env python3
"""
Retrieval seam -- optionally pull reference context (e.g. from your
vectorization engine) and prepend it to the prompt before each call.

Configured per folder via config.txt:

    RETRIEVER=none            # none | folder | command | http
    RETRIEVER_PATH=           # 'folder' : a folder of reference files to read
    RETRIEVER_CMD=            # 'command': a local script; {query} is substituted,
                              #            otherwise the query is sent on stdin.
                              #            Its stdout becomes the context.
    RETRIEVER_URL=            # 'http'   : POST {"query","top_k"} -> text/JSON
    RETRIEVER_TOPK=8
    RETRIEVER_MAX_CHARS=12000 # hard cap on how much context to inject

The 'command' backend is how you wire in a local vector search: point
RETRIEVER_CMD at your script and it gets the job's query, returns the
relevant chunks. The 'folder' backend just stuffs a folder's text (good
when the "series" is really a folder of documents).
"""

import os
import json
import subprocess
import urllib.request

CONTEXT_HEADER = (
    "\n\n--- REFERENCE CONTEXT (retrieved from your knowledge base) ---\n"
    "Use the material below to help answer. If it is not relevant, ignore it.\n\n"
)


def _truncate(text: str, max_chars: int) -> str:
    if max_chars and len(text) > max_chars:
        return text[:max_chars] + "\n...[reference context truncated]..."
    return text


def _from_folder(path, query, top_k, max_chars):
    import pathlib
    base = pathlib.Path(path)
    if not base.exists():
        return ""
    files = [p for p in sorted(base.rglob("*")) if p.is_file() and p.name != ".gitkeep"]
    # Light relevance: rank files by how many query words appear in them.
    terms = [w.lower() for w in query.split() if len(w) > 3][:40]
    scored = []
    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        low = text.lower()
        score = sum(low.count(t) for t in terms) if terms else 1
        scored.append((score, p, text))
    scored.sort(key=lambda x: x[0], reverse=True)
    chunks, used = [], 0
    for score, p, text in scored[: top_k or len(scored)]:
        snippet = f"[{p.name}]\n{text}\n"
        chunks.append(snippet)
        used += len(snippet)
        if max_chars and used >= max_chars:
            break
    return _truncate("\n".join(chunks), max_chars)


def _from_command(cmd, query, max_chars, cwd):
    if "{query}" in cmd:
        run = cmd.replace("{query}", query.replace('"', '\\"'))
        stdin = None
    else:
        run = cmd
        stdin = query
    try:
        proc = subprocess.run(
            run, shell=True, cwd=cwd, input=stdin,
            capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        return "\n[retriever command timed out]\n"
    out = proc.stdout or ""
    if proc.returncode != 0 and not out:
        return f"\n[retriever command failed: {proc.stderr.strip()[:200]}]\n"
    return _truncate(out, max_chars)


def _from_http(url, query, top_k, max_chars):
    payload = json.dumps({"query": query, "top_k": top_k}).encode("utf-8")
    req = urllib.request.Request(url, data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as e:                       # noqa: BLE001
        return f"\n[retriever http error: {e}]\n"
    # Accept either plain text or JSON ({"chunks":[...]} / {"context":"..."} / list)
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            if "context" in data:
                raw = str(data["context"])
            elif "chunks" in data:
                raw = "\n".join(str(c) for c in data["chunks"])
            elif "results" in data:
                raw = "\n".join(str(c) for c in data["results"])
        elif isinstance(data, list):
            raw = "\n".join(str(c) for c in data)
    except (ValueError, TypeError):
        pass
    return _truncate(raw, max_chars)


def retrieve(cfg: dict, query: str, folder) -> str:
    """Return context text to prepend (or '' when retrieval is off/empty)."""
    kind = (cfg.get("RETRIEVER", "none") or "none").strip().lower()
    if kind in ("", "none", "off"):
        return ""
    top_k = int(cfg.get("RETRIEVER_TOPK", "8") or "0")
    max_chars = int(cfg.get("RETRIEVER_MAX_CHARS", "12000") or "0")

    body = ""
    if kind == "folder":
        body = _from_folder(cfg.get("RETRIEVER_PATH", ""), query, top_k, max_chars)
    elif kind == "command":
        cmd = cfg.get("RETRIEVER_CMD", "")
        if cmd:
            body = _from_command(cmd, query, max_chars, cwd=str(folder))
    elif kind == "http":
        url = cfg.get("RETRIEVER_URL", "")
        if url:
            body = _from_http(url, query, top_k, max_chars)
    else:
        body = f"\n[unknown RETRIEVER '{kind}']\n"

    body = (body or "").strip()
    return CONTEXT_HEADER + body if body else ""
