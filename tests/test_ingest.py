"""Tests for compiler/ingest.py — frontmatter parsing, scoring, file scanning."""

import tempfile
from pathlib import Path

from asd.compiler.ingest import (
    _parse_list_field,
    _quality_gate,
    _scan_kb_files,
    _score_article,
    _split_frontmatter,
    ingest,
    ingest_status,
)
from asd.tools.developer import get_mode_thresholds


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


class TestQualityGate:
    """Quality gate function — article acceptance and warnings."""

    def test_accepts_good_article(self) -> None:
        fm = {"title": "Test", "type": "concept", "tags": "[a, b]", "sources": "[s1]"}
        body = "word " * 100 + " [[link1]] [[link2]]"
        accepted, warnings = _quality_gate(fm, body)
        assert accepted is True
        assert warnings == []

    def test_rejects_empty_body(self) -> None:
        fm = {"title": "Test"}
        accepted, warnings = _quality_gate(fm, "hi")
        assert accepted is False
        assert "word count" in warnings[0]

    def test_rejects_missing_title(self) -> None:
        fm: dict[str, str] = {}
        body = "word " * 100
        accepted, warnings = _quality_gate(fm, body)
        assert accepted is False
        assert "missing required frontmatter" in warnings[0]

    def test_warns_low_word_count(self) -> None:
        fm = {"title": "Test"}
        # 15 words: above reject (10) but below min (50)
        body = "word " * 15
        accepted, warnings = _quality_gate(fm, body)
        assert accepted is True
        assert any("word count" in w for w in warnings)

    def test_warns_low_frontmatter_fields(self) -> None:
        fm = {"title": "Only Title"}
        body = "word " * 60
        accepted, warnings = _quality_gate(fm, body)
        assert accepted is True
        assert any("frontmatter fields" in w for w in warnings)

    def test_warns_low_quality_score(self) -> None:
        fm = {"title": "Test"}
        body = "just a short body"
        accepted, warnings = _quality_gate(fm, body)
        # Short body = low score, should warn
        assert any("quality score" in w or "word count" in w for w in warnings)

    def test_rejects_zero_score_under_reject_threshold(self) -> None:
        fm = {"title": "Test"}
        # Enough words to pass word count gate but quality score of 0.2 hits reject threshold
        body = "word " * 20
        thresholds = {
            "min_words": 50,
            "min_words_reject": 5,
            "min_frontmatter_fields": 2,
            "required_frontmatter": ["title"],
            "min_quality_score": 0.4,
            "reject_quality_score": 0.2,
        }
        accepted, warnings = _quality_gate(fm, body, thresholds)
        # quality score = 0.2 (title only), reject_quality_score = 0.2, so score <= 0.2 → rejected
        assert accepted is False
        assert "quality score" in warnings[0]

    def test_custom_thresholds_allow_permissive(self) -> None:
        fm: dict[str, str] = {}
        body = "just a few words"
        thresholds = {
            "min_words": 50,
            "min_words_reject": 1,
            "min_frontmatter_fields": 0,
            "required_frontmatter": [],
            "min_quality_score": 0.0,
            "reject_quality_score": -1.0,  # below zero so nothing is rejected
        }
        accepted, _ = _quality_gate(fm, body, thresholds)
        assert accepted is True

    def test_custom_thresholds_reject_strictly(self) -> None:
        fm = {"title": "Only Title"}
        body = "only thirty words here " * 2
        thresholds = {
            "min_words": 100,
            "min_words_reject": 50,
            "min_frontmatter_fields": 4,
            "required_frontmatter": ["title", "type", "tags"],
            "min_quality_score": 0.4,
            "reject_quality_score": 0.1,
        }
        accepted, _ = _quality_gate(fm, body, thresholds)
        assert accepted is False

    def test_rejects_missing_required_fields_custom(self) -> None:
        fm = {"title": "Test"}
        body = "word " * 80
        thresholds = {
            "min_words": 50,
            "min_words_reject": 10,
            "min_frontmatter_fields": 2,
            "required_frontmatter": ["title", "type", "tags"],
            "min_quality_score": 0.2,
            "reject_quality_score": 0.0,
        }
        accepted, warnings = _quality_gate(fm, body, thresholds)
        assert accepted is False
        assert "missing required frontmatter" in warnings[0]


class TestModeThresholds:
    """Per-mode quality threshold configuration."""

    def test_developer_mode_thresholds(self) -> None:
        t = get_mode_thresholds()
        assert t["min_words"] == 50
        assert t["required_frontmatter"] == ["title"]
        assert t["reject_quality_score"] == 0.0

    def test_research_mode_is_lenient(self) -> None:
        from asd.tools.developer import handle_set_mode

        handle_set_mode("research")
        t = get_mode_thresholds()
        assert t["min_words"] == 30
        assert t["reject_quality_score"] == 0.0

        # Restore default
        handle_set_mode("developer")

    def test_review_mode_is_strict(self) -> None:
        from asd.tools.developer import handle_set_mode

        handle_set_mode("review")
        t = get_mode_thresholds()
        assert t["min_words"] == 100
        assert t["reject_quality_score"] == 0.1
        assert t["required_frontmatter"] == ["title", "type", "tags"]

        handle_set_mode("developer")

    def test_personal_mode_is_permissive(self) -> None:
        from asd.tools.developer import handle_set_mode

        handle_set_mode("personal")
        t = get_mode_thresholds()
        assert t["min_words"] == 10
        assert t["min_words_reject"] == 1
        assert t["reject_quality_score"] == 0.0

        handle_set_mode("developer")

    def test_ops_mode_thresholds(self) -> None:
        from asd.tools.developer import handle_set_mode

        handle_set_mode("ops")
        t = get_mode_thresholds()
        assert t["min_words"] == 30
        assert t["min_frontmatter_fields"] == 2
        assert t["reject_quality_score"] == 0.0

        handle_set_mode("developer")

    def test_mode_persists_to_disk(self) -> None:
        from asd.tools.developer import _MODE_STATE_FILE, _load_mode, handle_set_mode

        handle_set_mode("review")
        # Verify state file was written
        assert Path(_MODE_STATE_FILE).exists()
        saved = _load_mode()
        assert saved == "review"

        handle_set_mode("developer")


class TestQualityGateIngest:
    """Quality gate integration with full ingest pipeline."""

    def test_rejected_articles_not_in_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_dir = Path(tmp)
            concepts = kb_dir / "concepts"
            concepts.mkdir(parents=True)
            (concepts / "good.md").write_text(
                "---\ntitle: Good\n---\n\n" + "word " * 60 + "\n",
            )
            (concepts / "bad.md").write_text("too short")  # no frontmatter, too few words

            result = ingest(kb_dir=kb_dir)
            assert result.inserted == 1
            assert result.rejected == 1
            assert any("bad.md" in str(d.get("path", "")) for d in result.details)

    def test_quality_warnings_in_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_dir = Path(tmp)
            concepts = kb_dir / "concepts"
            concepts.mkdir(parents=True)
            (concepts / "borderline.md").write_text(
                "---\ntitle: Borderline\n---\n\nonly twenty words " * 2 + "\n",
            )

            result = ingest(kb_dir=kb_dir)
            assert result.inserted == 1
            assert result.warned == 1


class TestVersioningIngest:
    """Version tracking during ingestion."""

    def test_source_version_in_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_dir = Path(tmp)
            concepts = kb_dir / "concepts"
            concepts.mkdir(parents=True)
            (concepts / "article.md").write_text(
                "---\ntitle: A\n---\n\n" + "word " * 60 + "\n",
            )

            result = ingest(kb_dir=kb_dir)
            assert result.inserted == 1
            detail = result.details[0]
            assert detail["source_version"] == 1

    def test_version_increments_on_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            kb_dir = Path(tmp)
            concepts = kb_dir / "concepts"
            concepts.mkdir(parents=True)
            article = concepts / "article.md"
            article.write_text("---\ntitle: A\n---\n\n" + "word " * 60 + "\n")

            first = ingest(kb_dir=kb_dir)
            assert first.details[0]["source_version"] == 1

            article.write_text("---\ntitle: A\ntags: [updated]\n---\n\n" + "word " * 60 + "\n")
            # force_all bypasses mtime-based skip on fast filesystems
            second = ingest(kb_dir=kb_dir, force_all=True)
            assert second.updated == 1
            assert second.details[0]["source_version"] == 2
