"""On-demand documentation search over the bundled corpus and local directories."""

from __future__ import annotations

import json

from cloudflare_mcp import docs


def test_bundled_corpus_loads_and_is_tagged():
    corpus = docs.load_corpus()
    assert len(corpus) >= 20
    assert all(entry.get("title") for entry in corpus)
    products = {entry["product"] for entry in corpus}
    assert {"d1", "workers", "kv", "r2", "dns"} <= products


def test_search_returns_ranked_snippets():
    result = docs.search("d1 migrations", limit=3)

    assert result["count"] >= 1
    assert len(result["matches"]) <= 3
    top = result["matches"][0]
    assert top["score"] > 0
    assert "d1" in json.dumps(top).lower()
    assert top["snippet"]


def test_synonyms_expand_the_query():
    result = docs.search("sql")
    assert "d1" in result["terms"]
    assert result["count"] >= 1


def test_blank_query_returns_guidance():
    result = docs.search("   ")
    assert result["count"] == 0
    assert result["matches"] == []
    assert "hint" in result


def test_unknown_query_is_explicitly_empty():
    result = docs.search("zzzz-nonexistent-product-term")
    assert result["count"] == 0
    assert result["matches"] == []


def test_local_markdown_directories_are_indexed(tmp_path):
    reference = tmp_path / "reference"
    reference.mkdir()
    (reference / "queues-guide.md").write_text(
        "# Cloudflare Queues consumer guide\n\n"
        "Use a consumer worker to drain the queue.\n",
        encoding="utf-8",
    )

    result = docs.search("queues consumer", extra_dirs=(str(reference),))
    assert result["count"] >= 1
    assert any("Queues" in (match["title"] or "") for match in result["matches"])


def test_missing_local_directory_is_ignored(tmp_path):
    result = docs.search("d1", extra_dirs=(str(tmp_path / "absent"),))
    assert result["count"] >= 1


def test_search_limit_is_clamped():
    assert len(docs.search("workers", limit=0)["matches"]) <= 1
    assert len(docs.search("workers", limit=500)["matches"]) <= 20
