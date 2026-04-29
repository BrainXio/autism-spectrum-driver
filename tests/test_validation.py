"""Tests for validation/consistency.py — structural KB checks."""

import tempfile
from pathlib import Path

from asd.validation.consistency import (
    ValidationIssue,
    ValidationReport,
    check_broken_links,
    check_missing_backlinks,
    check_orphan_pages,
    check_orphan_sources,
    check_sparse_articles,
    check_stale_articles,
    validate,
)


def _make_kb_with_articles(articles: list[tuple[str, str, str]]) -> Path:
    """Create a temp KB directory with articles.

    Each tuple: (subdir, filename, content).
    """
    tmp = tempfile.mkdtemp()
    kb_dir = Path(tmp)
    for subdir, filename, content in articles:
        d = kb_dir / subdir
        d.mkdir(parents=True, exist_ok=True)
        (d / filename).write_text(content)
    return kb_dir


class TestBrokenLinks:
    """Check 1: wikilinks to non-existent files."""

    def test_no_broken_links(self) -> None:
        kb_dir = _make_kb_with_articles(
            [
                ("concepts", "a.md", "---\ntitle: A\n---\n\nSee [[concepts/b]].\n"),
                ("concepts", "b.md", "---\ntitle: B\n---\n\nReferenced by A.\n"),
            ],
        )
        issues = check_broken_links(kb_dir)
        assert len(issues) == 0

    def test_broken_link_detected(self) -> None:
        kb_dir = _make_kb_with_articles(
            [("concepts", "a.md", "---\ntitle: A\n---\n\nSee [[concepts/missing]].\n")],
        )
        issues = check_broken_links(kb_dir)
        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert issues[0].check == "broken_link"

    def test_daily_links_ignored(self) -> None:
        kb_dir = _make_kb_with_articles(
            [("concepts", "a.md", "---\ntitle: A\n---\n\nSee [[daily/log.md]].\n")],
        )
        issues = check_broken_links(kb_dir)
        assert len(issues) == 0


class TestOrphanPages:
    """Check 2: articles with zero inbound links."""

    def test_orphan_detected(self) -> None:
        kb_dir = _make_kb_with_articles(
            [("concepts", "lonely.md", "---\ntitle: Lonely\n---\n\nNo one links here.\n")],
        )
        issues = check_orphan_pages(kb_dir)
        assert len(issues) == 1
        assert issues[0].severity == "warning"

    def test_linked_page_not_orphan(self) -> None:
        kb_dir = _make_kb_with_articles(
            [
                ("concepts", "a.md", "---\ntitle: A\n---\n\nLinks to [[concepts/b]].\n"),
                ("concepts", "b.md", "---\ntitle: B\n---\n\nLinked from A.\n"),
            ],
        )
        issues = check_orphan_pages(kb_dir)
        # B has an inbound link from A; A has zero
        assert len(issues) == 1
        assert "a" in issues[0].file.lower()


class TestSparseArticles:
    """Check 6: articles below minimum word count."""

    def test_sparse_detected(self) -> None:
        kb_dir = _make_kb_with_articles(
            [("concepts", "tiny.md", "---\ntitle: Tiny\n---\n\ntoo short.\n")],
        )
        issues = check_sparse_articles(kb_dir)
        assert len(issues) == 1
        assert issues[0].severity == "suggestion"

    def test_normal_article_passes(self) -> None:
        body = "word " * 100  # 100 words
        kb_dir = _make_kb_with_articles(
            [("concepts", "long.md", f"---\ntitle: Long\n---\n\n{body}\n")],
        )
        issues = check_sparse_articles(kb_dir)
        assert len(issues) == 0


class TestMissingBacklinks:
    """Check 5: asymmetric links."""

    def test_asymmetric_link(self) -> None:
        kb_dir = _make_kb_with_articles(
            [
                ("concepts", "a.md", "---\ntitle: A\n---\n\n[[concepts/b]]\n"),
                ("concepts", "b.md", "---\ntitle: B\n---\n\nNo link back.\n"),
            ],
        )
        issues = check_missing_backlinks(kb_dir)
        assert len(issues) == 1
        assert issues[0].auto_fixable is True


class TestOrphanSources:
    """Check 3: uncompiled daily logs."""

    def test_orphan_source(self) -> None:
        with tempfile.TemporaryDirectory() as logs_tmp:
            logs_dir = Path(logs_tmp)
            (logs_dir / "2026-04-29.md").write_text("Log content")

            kb_dir = _make_kb_with_articles(
                [("concepts", "a.md", "---\ntitle: A\n---\n\nBody.\n")],
            )
            issues = check_orphan_sources(kb_dir, logs_dir)
            assert len(issues) >= 1  # Should report the uncompiled log


class TestStaleArticles:
    """Check 4: source logs changed since compilation."""

    def test_stale_detected(self) -> None:
        with tempfile.TemporaryDirectory() as logs_tmp:
            logs_dir = Path(logs_tmp)
            log = logs_dir / "2026-04-29.md"
            log.write_text("Original content")

            # Create compile state referencing old hash
            compile_state = {
                "compiled": {
                    "2026-04-29.md": {
                        "hash": "0000000000000000",
                        "compiled_at": "2026-04-29T00:00:00",
                    },
                },
            }

            kb_dir = _make_kb_with_articles(
                [("concepts", "a.md", "---\ntitle: A\n---\n\nBody.\n")],
            )
            issues = check_stale_articles(kb_dir, logs_dir, compile_state)
            assert len(issues) == 1
            assert issues[0].check == "stale_article"


class TestFullValidation:
    """End-to-end validation run."""

    def test_validate_healthy_kb(self) -> None:
        kb_dir = _make_kb_with_articles(
            [
                ("concepts", "a.md", "---\ntitle: A\n---\n\n" + "word " * 60 + "\n"),
                ("concepts", "b.md", "---\ntitle: B\n---\n\n" + "word " * 60 + "\n"),
            ],
        )
        report = validate(kb_dir=kb_dir)
        assert isinstance(report, ValidationReport)
        assert report.checked_at != ""

    def test_validation_report_healthy(self) -> None:
        report = ValidationReport(issues=[], errors=0, warnings=0, suggestions=0)
        assert report.is_healthy is True

    def test_validation_report_unhealthy(self) -> None:
        issue = ValidationIssue(
            severity="error",
            check="broken_link",
            file="test.md",
            detail="Broken",
        )
        report = ValidationReport(issues=[issue], errors=1, warnings=0, suggestions=0)
        assert report.is_healthy is False
