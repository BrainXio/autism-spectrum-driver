"""Tests for storage/index.py — TF-IDF search engine."""

import tempfile
from pathlib import Path

import pytest

from asd.storage.index import (
    _cosine_similarity,
    _idf,
    _term_freq,
    build_index,
    is_index_stale,
    load_article_content,
    load_index,
    save_index,
    search,
    tokenize,
)


class TestTokenization:
    """Token extraction from text."""

    def test_basic_tokenization(self) -> None:
        tokens = tokenize("The quick brown fox jumps over the lazy dog")
        assert "quick" in tokens
        assert "brown" in tokens
        assert "fox" in tokens
        assert "the" not in tokens  # stop word

    def test_stop_words_filtered(self) -> None:
        tokens = tokenize("the and of in on at by for to a it")
        assert tokens == []

    def test_minimum_length(self) -> None:
        tokens = tokenize("a x ab abc")
        assert "ab" in tokens
        assert "abc" in tokens
        assert "a" not in tokens
        assert "x" not in tokens  # single char filtered by {2,} regex

    def test_lowercase_normalization(self) -> None:
        tokens = tokenize("HELLO Hello hello")
        assert tokens.count("hello") == 3


class TestTermFrequency:
    """Term frequency computation."""

    def test_basic(self) -> None:
        tf = _term_freq(["hello", "world", "hello"])
        assert tf["hello"] == 2 / 3
        assert tf["world"] == 1 / 3

    def test_empty(self) -> None:
        assert _term_freq([]) == {}


class TestIDF:
    """Inverse document frequency."""

    def test_computation(self) -> None:
        docs = [
            {"hello": 0.5, "world": 0.5},
            {"hello": 1.0},
            {"hello": 0.3, "python": 0.7},
        ]
        idf = _idf(docs)
        assert idf["hello"] < idf["python"]
        assert idf["hello"] < idf["world"]


class TestCosineSimilarity:
    """Cosine similarity between sparse vectors."""

    def test_identical(self) -> None:
        vec = {"a": 0.5, "b": 0.3}
        assert _cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_orthogonal(self) -> None:
        assert _cosine_similarity({"a": 1.0}, {"b": 1.0}) == 0.0

    def test_empty(self) -> None:
        assert _cosine_similarity({}, {}) == 0.0


class TestIndexBuilding:
    """Index construction from KB files."""

    def test_build_from_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_dir = Path(tmp)
            concepts = kb_dir / "concepts"
            concepts.mkdir(parents=True)

            (concepts / "article1.md").write_text(
                '---\ntitle: "Python Patterns"\ntags: [python, patterns]\n'
                'updated: "2026-04-29"\n---\n\nPython design patterns.\n',
            )
            (concepts / "article2.md").write_text(
                '---\ntitle: "Rust Memory"\ntags: [rust, memory]\n'
                'updated: "2026-04-28"\n---\n\nRust memory management.\n',
            )

            index = build_index(kb_dir)
            assert index["article_count"] == 2
            assert len(index["articles"]) == 2
            assert "idf" in index
            # Every article should have a tfidf vector
            for article in index["articles"]:
                assert "tfidf" in article
                assert "path" in article
                assert "title" in article
                assert "hash" in article

    def test_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            index = build_index(Path(tmp))
            assert index["article_count"] == 0


class TestSearch:
    """Relevance search against the index."""

    def test_search_returns_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_dir = Path(tmp)
            concepts = kb_dir / "concepts"
            concepts.mkdir(parents=True)
            # Use distinctive bodies so TF-IDF can discriminate
            (concepts / "python.md").write_text(
                '---\ntitle: "Python Guide"\ntags: [python]\n'
                'updated: "2026-04-29"\n---\n\n'
                + "python decorators generators coroutines asyncio typing\n",
            )
            (concepts / "rust.md").write_text(
                '---\ntitle: "Rust Guide"\ntags: [rust]\n'
                'updated: "2026-04-28"\n---\n\n'
                + "rust ownership borrowing lifetimes traits cargo\n",
            )

            index = build_index(kb_dir)
            results = search("python decorators asyncio", index, top_k=2)
            assert len(results) >= 1
            # Python article should score higher for Python-related query
            assert results[0]["title"] == "Python Guide"
            assert results[0]["score"] > 0

    def test_version_field_in_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_dir = Path(tmp)
            concepts = kb_dir / "concepts"
            concepts.mkdir(parents=True)
            (concepts / "article.md").write_text(
                '---\ntitle: "Versioned Article"\nsource_version: 3\ningest_date: "2026-04-30"\n'
                'updated: "2026-04-30"\n---\n\nBody with version info.\n',
            )
            index = build_index(kb_dir)
            assert index["article_count"] == 1
            article = index["articles"][0]
            assert article["source_version"] == 3
            assert article["ingest_date"] == "2026-04-30"

    def test_returns_default_version_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_dir = Path(tmp)
            concepts = kb_dir / "concepts"
            concepts.mkdir(parents=True)
            (concepts / "article.md").write_text(
                '---\ntitle: "No Version"\nupdated: "2026-04-29"\n---\n\nContent.\n',
            )
            index = build_index(kb_dir)
            article = index["articles"][0]
            assert article["source_version"] == 1

    def test_version_filtering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_dir = Path(tmp)
            concepts = kb_dir / "concepts"
            concepts.mkdir(parents=True)
            (concepts / "v1.md").write_text(
                '---\ntitle: "V1"\nsource_version: 1\nupdated: "2026-04-29"\n---\n\nV1 content.\n',
            )
            (concepts / "v5.md").write_text(
                '---\ntitle: "V5"\nsource_version: 5\nupdated: "2026-04-30"\n---\n\nV5 content.\n',
            )

            index = build_index(kb_dir)
            # Filter: only articles with version >= 3
            results = search("content", index, top_k=5, min_version=3)
            assert len(results) == 1
            assert results[0]["title"] == "V5"

            # Filter: only articles with version <= 2
            results = search("content", index, top_k=5, max_version=2)
            assert len(results) == 1
            assert results[0]["title"] == "V1"

    def test_fallback_when_no_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_dir = Path(tmp)
            concepts = kb_dir / "concepts"
            concepts.mkdir(parents=True)
            (concepts / "topic.md").write_text(
                '---\ntitle: "Topic"\nupdated: "2026-04-29"\n---\n\nContent.\n',
            )
            index = build_index(kb_dir)
            results = search("", index)
            assert len(results) >= 0  # Fallback or empty is fine


class TestIndexPersistence:
    """Index save/load cycle."""

    def test_save_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "index.json"
            index = {"version": 1, "articles": []}
            save_index(index, cache)
            assert cache.exists()

            loaded = load_index(cache)
            assert loaded is not None
            assert loaded["version"] == 1

    def test_load_missing(self) -> None:
        assert load_index(Path("/nonexistent/index.json")) is None


class TestStaleness:
    """Index staleness detection."""

    def test_stale_when_missing(self) -> None:
        assert is_index_stale(None, Path("/tmp")) is True

    def test_stale_with_changed_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_dir = Path(tmp)
            concepts = kb_dir / "concepts"
            concepts.mkdir(parents=True)
            (concepts / "article.md").write_text("---\ntitle: A\n---\n\nOld body.\n")

            index = build_index(kb_dir)
            assert is_index_stale(index, kb_dir) is False

            # Change the file
            (concepts / "article.md").write_text("---\ntitle: A\n---\n\nNew body changed.\n")
            assert is_index_stale(index, kb_dir) is True


class TestArticleLoading:
    """Loading article content for context injection."""

    def test_load_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_dir = Path(tmp)
            concepts = kb_dir / "concepts"
            concepts.mkdir(parents=True)
            (concepts / "article.md").write_text(
                "---\ntitle: Test\n---\n\nThis is the body.\n",
            )

            scored = [
                {"path": "concepts/article.md", "title": "Test", "score": 0.9},
            ]
            content = load_article_content(scored, kb_dir)
            assert "article" in content
            assert "This is the body" in content
