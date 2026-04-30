"""KB artifact data models — Pydantic schemas for all ASD types."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class KBArticle(BaseModel):
    """A compiled knowledge base article with YAML frontmatter and body."""

    path: str = Field(description="Relative path from USER/kb/")
    title: str
    article_type: Literal["concept", "mechanism", "outcome", "reference", "connection"]
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    created: str = Field(description="ISO date YYYY-MM-DD")
    updated: str = Field(description="ISO date YYYY-MM-DD")
    body: str = Field(description="Full markdown body content")
    hash: str = Field(default="", description="Content hash for change detection")
    source_version: int = Field(default=1, description="Monotonic version, bumped on re-ingest")
    ingest_date: str = Field(default="", description="ISO timestamp of last ingestion")
    historical_context: str = Field(
        default="",
        description="Free-form note about why this version exists (architecture state, etc.)",
    )


class IngestResult(BaseModel):
    """Summary of an ingestion run."""

    scanned: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    deleted: int = 0
    errors: int = 0


class KbStatus(BaseModel):
    """Knowledge base health report."""

    article_count: int = 0
    disk_count: int = 0
    new_count: int = 0
    stale_count: int = 0
    orphaned_count: int = 0
    last_ingest: str | None = Field(default=None, description="ISO timestamp of last ingestion")
    last_compile: str | None = Field(default=None, description="ISO timestamp of last compilation")
    synced: bool = False
    lint_issues: int = 0


class QueryResult(BaseModel):
    """A single query result with relevance score."""

    path: str
    title: str
    summary: str = ""
    score: float = 0.0


class ValidationIssue(BaseModel):
    """A single KB structural or semantic issue found during validation."""

    severity: Literal["error", "warning", "suggestion"]
    check: str = Field(description="Name of the check that found this issue")
    file: str = Field(description="Relative path of the article with the issue")
    detail: str = Field(description="Human-readable description of the issue")
    auto_fixable: bool = False


class QualityThresholds(BaseModel):
    """Configurable quality thresholds for ingestion gating."""

    min_words: int = Field(default=50, description="Minimum word count before warning")
    min_words_reject: int = Field(
        default=10, description="Word count below which ingestion is rejected"
    )
    min_frontmatter_fields: int = Field(
        default=2,
        description="Minimum required frontmatter fields (title + one other)",
    )
    required_frontmatter: list[str] = Field(
        default_factory=lambda: ["title"],
        description="Frontmatter fields that must be present",
    )
    min_quality_score: float = Field(
        default=0.2,
        description="Articles scoring below this are warned",
    )
    reject_quality_score: float = Field(
        default=0.0,
        description="Articles scoring below this are rejected",
    )
    check_broken_links: bool = Field(
        default=True,
        description="Check for broken internal [[wikilinks]]",
    )
    max_broken_links: int = Field(
        default=5,
        description="Articles with more broken links than this are warned",
    )


Mode = Literal["developer", "research", "review", "ops", "personal"]
