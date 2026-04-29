"""Tests for ASD storage artifacts — Pydantic models."""

from asd.storage.artifacts import (
    IngestResult,
    KBArticle,
    KbStatus,
    QueryResult,
    ValidationIssue,
)


class TestKBArticle:
    """KBArticle model validation."""

    def test_minimal_article(self) -> None:
        article = KBArticle(
            path="concepts/test.md",
            title="Test Article",
            article_type="concept",
            created="2026-04-29",
            updated="2026-04-29",
            body="Some markdown body content here.",
        )
        assert article.title == "Test Article"
        assert article.article_type == "concept"
        assert article.aliases == []
        assert article.tags == []
        assert article.sources == []

    def test_full_article(self) -> None:
        article = KBArticle(
            path="mechanisms/build-pattern.md",
            title="Build Pattern",
            article_type="mechanism",
            aliases=["build-system", "ci-pattern"],
            tags=["ci", "infrastructure"],
            sources=["daily/2026-04-29.md"],
            created="2026-04-29",
            updated="2026-04-29",
            body="## Key Points\n\n- Point one\n- Point two\n\n## Details\n\nFull details here.",
            hash="abc123def456",
        )
        assert len(article.aliases) == 2
        assert len(article.tags) == 2
        assert len(article.sources) == 1
        assert article.hash == "abc123def456"

    def test_all_article_types(self) -> None:
        for atype in ("concept", "mechanism", "outcome", "reference", "connection"):
            article = KBArticle(
                path=f"{atype}s/test.md",
                title="Test",
                article_type=atype,
                created="2026-04-29",
                updated="2026-04-29",
                body="Body content.",
            )
            assert article.article_type == atype


class TestIngestResult:
    """IngestResult model."""

    def test_defaults(self) -> None:
        result = IngestResult()
        assert result.scanned == 0
        assert result.inserted == 0
        assert result.errors == 0

    def test_counts(self) -> None:
        result = IngestResult(
            scanned=10,
            inserted=3,
            updated=2,
            skipped=4,
            deleted=1,
            errors=0,
        )
        assert result.scanned == 10
        assert result.inserted == 3


class TestKbStatus:
    """KbStatus model."""

    def test_defaults(self) -> None:
        status = KbStatus()
        assert status.synced is False
        assert status.last_ingest is None

    def test_synced(self) -> None:
        status = KbStatus(
            article_count=5,
            disk_count=5,
            synced=True,
            last_ingest="2026-04-29T12:00:00Z",
        )
        assert status.synced is True
        assert status.last_ingest == "2026-04-29T12:00:00Z"


class TestQueryResult:
    """QueryResult model."""

    def test_basic(self) -> None:
        result = QueryResult(
            path="concepts/test.md",
            title="Test Concept",
            summary="A test concept",
            score=0.85,
        )
        assert result.score == 0.85
        assert result.path == "concepts/test.md"


class TestValidationIssue:
    """ValidationIssue model."""

    def test_error_issue(self) -> None:
        issue = ValidationIssue(
            severity="error",
            check="broken_link",
            file="concepts/test.md",
            detail="Broken link: [[missing]]",
        )
        assert issue.severity == "error"
        assert issue.auto_fixable is False

    def test_suggestion_auto_fixable(self) -> None:
        issue = ValidationIssue(
            severity="suggestion",
            check="missing_backlink",
            file="concepts/a.md",
            detail="A links to B but not vice versa",
            auto_fixable=True,
        )
        assert issue.severity == "suggestion"
        assert issue.auto_fixable is True
