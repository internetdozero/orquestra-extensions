"""On-demand Cloudflare documentation lookup.

Instead of loading large reference manuals into the model context, tools query
this module, which scores a compact bundled corpus plus optional local
markdown directories (``CLOUDFLARE_MCP_DOCS_DIRS``) and returns only the most
relevant snippets and code samples.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any, Iterable

MAX_EXTERNAL_BYTES = 8_000_000  # bound the scan so huge doc trees stay cheap
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "in",
    "is", "it", "of", "on", "or", "the", "to", "what", "when", "with", "do",
    "does", "i", "my", "our", "use", "using",
}

# Small synonym table expands a query so keyword search behaves semi-semantically.
SYNONYMS: dict[str, tuple[str, ...]] = {
    "sql": ("d1", "query", "database"),
    "query": ("sql", "d1"),
    "database": ("d1", "sqlite"),
    "storage": ("r2", "kv"),
    "bucket": ("r2", "object"),
    "objects": ("r2", "bucket"),
    "blob": ("r2", "bucket"),
    "cache": ("kv", "cache"),
    "keyvalue": ("kv", "namespace"),
    "cron": ("cron-trigger", "scheduled", "trigger"),
    "schedule": ("cron-trigger", "scheduled"),
    "script": ("worker", "durable-object"),
    "deploy": ("deploy", "wrangler", "publish"),
    "publish": ("wrangler", "deploy"),
    "route": ("routes", "pattern", "zone"),
    "record": ("dns-record", "dns"),
    "cname": ("dns-record", "cname"),
    "ip": ("a-record", "a", "dns"),
    "reverse-proxy": ("proxy", "orange-cloud", "dns-record"),
    "https": ("tls", "ssl", "certificate"),
    "certificate": ("tls", "ssl"),
    "env": ("secrets", "variables", "wrangler"),
    "secret": ("secrets", "variables", "environment"),
    "config": ("wrangler", "configuration"),
    "error": ("tail", "logs", "observability"),
    "log": ("tail", "observability", "wrangler tail"),
    "limit": ("limits", "quota", "plan"),
    "vectorize": ("embeddings", "vector"),
    "ai": ("workers-ai", "inference", "model"),
}


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t and t not in STOPWORDS]


def _query_terms(query: str) -> list[str]:
    terms: list[str] = []
    for token in _tokenize(query):
        terms.append(token)
        terms.extend(SYNONYMS.get(token, ()))
    seen: set[str] = set()
    ordered: list[str] = []
    for term in terms:
        if term not in seen:
            seen.add(term)
            ordered.append(term)
    return ordered


def score_entry(query_terms: Iterable[str], entry: dict[str, Any]) -> float:
    """Score one corpus entry against expanded query terms."""
    terms = list(query_terms)
    if not terms:
        return 0.0
    title = set(_tokenize(str(entry.get("title", "")) or ""))
    tags = set(_tokenize(" ".join(map(str, entry.get("tags", [])))))
    product = set(_tokenize(str(entry.get("product", ""))))
    snippet = set(_tokenize(f"{entry.get('snippet', '')} {entry.get('summary', '')}"))
    code = set(_tokenize(str(entry.get("code", ""))))
    score = 0.0
    for term in terms:
        if term in title:
            score += 5.0
        if term in tags:
            score += 4.0
        if term in product:
            score += 3.0
        if term in snippet:
            score += 1.5
        if term in code:
            score += 1.0
    phrase = " ".join(terms[: max(2, len(terms)) ])
    if phrase and phrase in str(entry.get("title", "")).lower():
        score += 3.0
    return score


@lru_cache(maxsize=4)
def load_corpus(extra_dirs: tuple[str, ...] = ()) -> tuple[dict[str, Any], ...]:
    """Load the bundled index plus markdown files from ``extra_dirs``."""
    with resources.files("cloudflare_mcp").joinpath("data", "docs_index.json").open(
        "r", encoding="utf-8"
    ) as handle:
        bundled = json.load(handle)
    entries: list[dict[str, Any]] = list(bundled)
    entries.extend(_load_external(extra_dirs))
    return tuple(entries)


def _load_external(extra_dirs: Iterable[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    budget = MAX_EXTERNAL_BYTES
    for directory in extra_dirs:
        base = Path(directory).expanduser()
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            if budget <= 0:
                break
            try:
                stat = path.stat()
                if stat.st_size > budget:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            budget -= len(text)
            entries.append(_md_entry(path, text))
    return entries


def _md_entry(path: Path, text: str) -> dict[str, Any]:
    lines = [line for line in text.splitlines()]
    title = next((line.lstrip("# ").strip() for line in lines if line.startswith("# ")),
                 path.stem.replace("-", " "))
    body = "\n".join(lines[:120])
    return {
        "id": f"local:{path}",
        "title": title,
        "product": "cloudflare",
        "tags": [part.lower() for part in re.split(r"[^a-z0-9]+", path.stem.lower()) if part],
        "snippet": body[:400].strip(),
        "summary": title,
        "code": body[:1200],
        "url": f"file://{path}",
    }


def search(query: str, *, limit: int = 5, extra_dirs: tuple[str, ...] = ()) -> dict[str, Any]:
    """Return the top matches for ``query`` (empty result set is explicit)."""
    cleaned = (query or "").strip()
    if not cleaned:
        return {"query": query, "matches": [], "count": 0,
                "hint": "Provide a keyword query, e.g. 'd1 migrations' or 'kv ttl'."}
    terms = _query_terms(cleaned)
    corpus = load_corpus(tuple(extra_dirs))
    scored = [
        (score_entry(terms, entry), entry)
        for entry in corpus
    ]
    scored = [item for item in scored if item[0] > 0]
    scored.sort(key=lambda item: (-item[0], str(item[1].get("title", ""))))
    top = scored[: max(1, min(limit, 20))]
    return {
        "query": cleaned,
        "terms": terms[:12],
        "count": len(top),
        "matches": [
            {
                "score": round(score, 2),
                "title": entry.get("title"),
                "product": entry.get("product"),
                "tags": entry.get("tags", []),
                "snippet": (entry.get("snippet") or entry.get("summary") or "")[:400],
                "code": (entry.get("code") or "")[:1500],
                "url": entry.get("url"),
            }
            for score, entry in top
        ],
        "hint": "Targeted snippets only; ask again with tighter keywords for more precision.",
    }