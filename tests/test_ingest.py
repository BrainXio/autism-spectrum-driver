"""Tests for compiler/ingest.py — frontmatter parsing, scoring, file scanning."""

import tempfile
from pathlib import Path

from asd.compiler.ingest import (
    _parse_list_field,
    _scan_kb_files,
    _score_article,
    _split_frontmatter,
    ingest,
    ingest_status,
)


class TestFrontmatterParsing:
    """Frontmatter extraction from markdown."""

    def test_basic_frontmatter(self) -> None:
        content = """---
title: "Test Article"
tags: [concept, test]
sources: [daily/source.md]
---

## Body content here."""
        fm, body = _split_frontmatter(content)
        assert fm["title"] == "Test Article"
        assert "Body content here" in body

    def test_no_frontmatter(self) -> None:
        content = "# Just a heading\n\nSome content."
        fm, body = _split_frontmatter(content)
        assert fm == {}
        assert body == content

    def test_malformed_frontmatter_closing(self) -> None:
        content = "---\ntitle: Test\nNo closing delimiter"
        fm, body = _split_frontmatter(content)
        assert fm == {}
        assert body == content

    def test_frontmatter_with_list_fields(self) -> None:
        content = """---
title: "Article"
aliases: [alt-name, other-name]
tags: [tag1, tag2]
sources: [src1, src2]
---

Body here."""
        fm, body = _split_frontmatter(content)
        assert fm["title"] == "Article"


class TestListFieldParsing:
    """YAML list field parsing."""

    def test_bracket_list(self) -> None:
        result = _parse_list_field("[tag1, tag2, tag3]")
        assert result == ["tag1", "tag2", "tag3"]

    def test_empty(self) -> None:
        assert _parse_list_field(None) == []
        assert _parse_list_field("") == []

    def test_single_item(self) -> None:
        result = _parse_list_field("[only-item]")
        assert result == ["only-item"]


class TestScoring:
    """Article quality scoring."""

    def test_high_quality_article(self) -> None:
        fm = {
            "title": "Test",
            "tags": "[a, b]",
            "sources": "[src1]",
        }
        long_body = "word " * 101 + " [[link1]]"
        score = _score_article(fm, long_body)
        assert score == 1.0

    def test_minimal_article(self) -> None:
        fm: dict[str, str] = {}
        score = _score_article(fm, "short")
        assert score == 0.0

    def test_partial_scores(self) -> None:
        fm = {"title": "Has Title"}
        score = _score_article(fm, "short body")
        assert score == 0.2


class TestFileScanning:
    """KB directory scanning."""

    def test_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_dir = Path(tmp) / "empty"
            kb_dir.mkdir()
            files = _scan_kb_files(kb_dir)
            assert files == []

    def test_scans_subdirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_dir = Path(tmp)
            concepts = kb_dir / "concepts"
            concepts.mkdir(parents=True)
            (concepts / "article1.md").write_text("content")
            (concepts / "article2.md").write_text("content")

            connections = kb_dir / "connections"
            connections.mkdir(parents=True)
            (connections / "link1.md").write_text("content")

            files = _scan_kb_files(kb_dir)
            assert len(files) == 3

    def test_missing_directory(self) -> None:
        files = _scan_kb_files(Path("/nonexistent/path"))
        assert files == []


class TestIngest:
    """Full ingestion pipeline."""

    def test_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_dir = Path(tmp)
            concepts = kb_dir / "concepts"
            concepts.mkdir(parents=True)
            article = concepts / "test.md"
            article.write_text(
                '---\ntitle: "Test"\ntags: [a]\n---\n\nBody content here.\n',
            )

            result = ingest(kb_dir=kb_dir, dry_run=True)
            assert result.scanned == 1
            assert len(result.details) == 1
            assert result.details[0]["action"] == "would_ingest"

    def test_incremental_ingest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_dir = Path(tmp)
            concepts = kb_dir / "concepts"
            concepts.mkdir(parents=True)
            article = concepts / "test.md"
            article.write_text(
                '---\ntitle: "Test"\ntags: [a, b]\nsources: [daily/log.md]\n---\n\n'
                + "word " * 100
                + " [[link1]] [[link2]]\n",
            )

            result = ingest(kb_dir=kb_dir)
            assert result.scanned == 1
            assert result.inserted == 1

            # Second run should skip
            result2 = ingest(kb_dir=kb_dir)
            assert result2.skipped == 1

    def test_force_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_dir = Path(tmp)
            concepts = kb_dir / "concepts"
            concepts.mkdir(parents=True)
            article = concepts / "test.md"
            article.write_text(
                '---\ntitle: "Test"\n---\n\n' + "word " * 60 + "\n",
            )

            result = ingest(kb_dir=kb_dir)
            assert result.inserted == 1

            # force_all should re-process
            result2 = ingest(kb_dir=kb_dir, force_all=True)
            assert result2.updated == 1

    def test_orphan_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_dir = Path(tmp)
            concepts = kb_dir / "concepts"
            concepts.mkdir(parents=True)
            article = concepts / "test.md"
            article.write_text("---\ntitle: Test\n---\n\n" + "word " * 60 + "\n")

            ingest(kb_dir=kb_dir)
            article.unlink()

            result = ingest(kb_dir=kb_dir)
            assert result.deleted == 1


class TestIngestStatus:
    """KB status reporting."""

    def test_no_state_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_dir = Path(tmp)
            concepts = kb_dir / "concepts"
            concepts.mkdir(parents=True)
            (concepts / "article.md").write_text(
                "---\ntitle: A\n---\n\n" + "word " * 60 + "\n",
            )

            status = ingest_status(kb_dir=kb_dir)
            assert status["disk_count"] == 1
            assert len(status["new"]) == 1

    def test_after_ingest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_dir = Path(tmp)
            concepts = kb_dir / "concepts"
            concepts.mkdir(parents=True)
            (concepts / "article.md").write_text(
                "---\ntitle: A\n---\n\n" + "word " * 60 + "\n",
            )

            ingest(kb_dir=kb_dir)
            status = ingest_status(kb_dir=kb_dir)
            assert status["synced"] is True
            assert status["last_ingest"] is not None
