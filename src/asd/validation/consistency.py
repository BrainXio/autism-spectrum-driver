"""Structural validation for the knowledge base.

Migrated from OCD kb/lint.py. Runs 6 deterministic checks on flat markdown
files: broken links, orphan pages, orphan sources, stale articles, missing
backlinks, and sparse articles. No LLM dependency.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

# ── Constants ──────────────────────────────────────────────────────────────────

_KB_SUBDIRS = ("concepts", "connections", "mechanisms", "outcomes", "references")
_MIN_WORD_COUNT = 50

# ── Result types ───────────────────────────────────────────────────────────────


@dataclass
class ValidationIssue:
    """A single structural or semantic issue found during validation."""

    severity: str  # "error", "warning", "suggestion"
    check: str
    file: str
    detail: str
    auto_fixable: bool = False


@dataclass
class ValidationReport:
    """Aggregated validation results."""

    issues: list[ValidationIssue] = field(default_factory=list)
    errors: int = 0
    warnings: int = 0
    suggestions: int = 0
    checked_at: str = ""

    @property
    def is_healthy(self) -> bool:
        return self.errors == 0


# ── Helpers ────────────────────────────────────────────────────────────────────


def _extract_wikilinks(text: str) -> list[str]:
    """Extract [[wikilink]] targets from text."""
    return re.findall(r"\[\[([^\]]+)\]\]", text)


def _scan_kb_files(kb_dir: Path) -> list[Path]:
    """Scan knowledge directory for markdown article files."""
    if not kb_dir.is_dir():
        return []
    files: list[Path] = []
    for subdir_name in _KB_SUBDIRS:
        subdir = kb_dir / subdir_name
        if subdir.is_dir():
            files.extend(sorted(subdir.glob("*.md")))
    return files


def _article_exists(kb_dir: Path, link: str) -> bool:
    """Check if an article referenced by [[wikilink]] exists.

    Handles links with and without subdirectory prefix.
    """
    if "/" in link:
        target = kb_dir / f"{link}.md"
        return target.exists()

    # Bare link — check all subdirs
    for subdir in _KB_SUBDIRS:
        target = kb_dir / subdir / f"{link}.md"
        if target.exists():
            return True
    return False


def _article_file(kb_dir: Path, link: str) -> Path | None:
    """Resolve a [[wikilink]] to an actual file path.

    Handles links with and without subdirectory prefix.
    """
    if "/" in link:
        target = kb_dir / f"{link}.md"
        return target if target.exists() else None

    for subdir in _KB_SUBDIRS:
        target = kb_dir / subdir / f"{link}.md"
        if target.exists():
            return target
    return None


def _file_hash(path: Path) -> str:
    """SHA-256 hash of file content (first 16 hex chars)."""
    try:
        content = path.read_text(encoding="utf-8")
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    except OSError:
        return ""


def _now_iso() -> str:
    """Current UTC time in ISO 8601 format."""
    return datetime.now(UTC).isoformat(timespec="seconds")


# ── Check 1: Broken links ─────────────────────────────────────────────────────


def check_broken_links(kb_dir: Path) -> list[ValidationIssue]:
    """Check for [[wikilinks]] that point to non-existent articles."""
    issues: list[ValidationIssue] = []
    for article in _scan_kb_files(kb_dir):
        content = article.read_text(encoding="utf-8")
        rel = str(article.relative_to(kb_dir))
        for link in _extract_wikilinks(content):
            if link.startswith("daily/"):
                continue
            if not _article_exists(kb_dir, link):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        check="broken_link",
                        file=rel,
                        detail=f"Broken link: [[{link}]] — target does not exist",
                    ),
                )
    return issues


# ── Check 2: Orphan pages ────────────────────────────────────────────────────


def check_orphan_pages(kb_dir: Path) -> list[ValidationIssue]:
    """Check for articles with zero inbound links."""
    issues: list[ValidationIssue] = []

    # Build inbound link count for each article
    inbound: dict[str, int] = {}
    for article in _scan_kb_files(kb_dir):
        content = article.read_text(encoding="utf-8")
        for link in _extract_wikilinks(content):
            if link.startswith("daily/"):
                continue
            inbound[link] = inbound.get(link, 0) + 1

    for article in _scan_kb_files(kb_dir):
        rel = str(article.relative_to(kb_dir))
        link_target = rel.replace(".md", "").replace("\\", "/")
        if inbound.get(link_target, 0) == 0:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    check="orphan_page",
                    file=rel,
                    detail=f"Orphan page: no other articles link to [[{link_target}]]",
                ),
            )
    return issues


# ── Check 3: Orphan sources ──────────────────────────────────────────────────


def check_orphan_sources(kb_dir: Path, logs_dir: Path) -> list[ValidationIssue]:
    """Check for daily log files that haven't been compiled yet.

    A daily log is an "orphan source" if it exists on disk but has no
    corresponding article entries referencing it in the sources frontmatter.
    """
    issues: list[ValidationIssue] = []
    if not logs_dir.is_dir():
        return issues

    # Collect all sources referenced in KB articles
    referenced_sources: set[str] = set()
    for article in _scan_kb_files(kb_dir):
        try:
            content = article.read_text(encoding="utf-8")
        except OSError:
            continue
        # Look for sources in frontmatter
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                fm = content[3:end]
                for line in fm.splitlines():
                    if line.strip().startswith("sources:"):
                        val = line.split(":", 1)[1].strip()
                        refs = re.findall(r"daily/([^\]]+)\]", val)
                        referenced_sources.update(refs)

    for log_path in sorted(logs_dir.glob("*.md")):
        if log_path.name not in referenced_sources:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    check="orphan_source",
                    file=f"daily/{log_path.name}",
                    detail=f"Uncompiled daily log: {log_path.name} has no KB references",
                ),
            )
    return issues


# ── Check 4: Stale articles ───────────────────────────────────────────────────


def check_stale_articles(
    kb_dir: Path,
    logs_dir: Path,
    compile_state: dict[str, Any] | None = None,
) -> list[ValidationIssue]:
    """Check if source daily logs have changed since their last compilation.

    Compares current file hashes against the compile state stored in
    .compile_state.json.
    """
    issues: list[ValidationIssue] = []
    if not logs_dir.is_dir():
        return issues

    if compile_state is None:
        state_file = kb_dir / ".compile_state.json"
        if state_file.exists():
            try:
                compile_state = json.loads(state_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                compile_state = {}
        else:
            compile_state = {}

    compiled = compile_state.get("compiled", {})
    for log_path in sorted(logs_dir.glob("*.md")):
        log_name = log_path.name
        if log_name in compiled:
            stored_hash = compiled[log_name].get("hash", "")
            current_hash = _file_hash(log_path)
            if stored_hash and stored_hash != current_hash:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        check="stale_article",
                        file=f"daily/{log_name}",
                        detail=f"Stale: {log_name} has changed since last compilation",
                    ),
                )
    return issues


# ── Check 5: Missing backlinks ────────────────────────────────────────────────


def check_missing_backlinks(kb_dir: Path) -> list[ValidationIssue]:
    """Check for asymmetric links: A links to B but B doesn't link to A."""
    issues: list[ValidationIssue] = []
    for article in _scan_kb_files(kb_dir):
        content = article.read_text(encoding="utf-8")
        rel = str(article.relative_to(kb_dir))
        source_link = rel.replace(".md", "").replace("\\", "/")

        for link in _extract_wikilinks(content):
            if link.startswith("daily/"):
                continue
            if ".." in link or link.startswith("/"):
                continue
            target_path = _article_file(kb_dir, link)
            if target_path is not None:
                target_content = target_path.read_text(encoding="utf-8")
                if f"[[{source_link}]]" not in target_content:
                    issues.append(
                        ValidationIssue(
                            severity="suggestion",
                            check="missing_backlink",
                            file=rel,
                            detail=(f"[[{source_link}]] links to [[{link}]] but not vice versa"),
                            auto_fixable=True,
                        ),
                    )
    return issues


# ── Check 6: Sparse articles ──────────────────────────────────────────────────


def check_sparse_articles(kb_dir: Path) -> list[ValidationIssue]:
    """Check for articles below the minimum recommended word count."""
    issues: list[ValidationIssue] = []
    for article in _scan_kb_files(kb_dir):
        try:
            body = article.read_text(encoding="utf-8")
        except OSError:
            continue
        word_count = len(body.split())
        if word_count < _MIN_WORD_COUNT:
            rel = str(article.relative_to(kb_dir))
            issues.append(
                ValidationIssue(
                    severity="suggestion",
                    check="sparse_article",
                    file=rel,
                    detail=(
                        f"Sparse article: {word_count} words "
                        f"(minimum recommended: {_MIN_WORD_COUNT})"
                    ),
                ),
            )
    return issues


# ── Full validation run ───────────────────────────────────────────────────────


def validate(
    *,
    kb_dir: Path,
    logs_dir: Path | None = None,
) -> ValidationReport:
    """Run all structural validation checks on the knowledge base.

    Args:
        kb_dir: Knowledge base directory (USER/kb/).
        logs_dir: Daily logs directory for source checks (optional).

    Returns:
        ValidationReport with all issues, counts, and health status.
    """
    all_issues: list[ValidationIssue] = []

    # Load compile state for stale check
    compile_state: dict[str, Any] | None = None
    state_file = kb_dir / ".compile_state.json"
    if state_file.exists():
        with contextlib.suppress(json.JSONDecodeError, OSError):
            compile_state = json.loads(state_file.read_text(encoding="utf-8"))

    logs = logs_dir or (kb_dir.parent / "logs" / "daily")

    # Run all 6 checks
    for _name, check_fn in [
        ("broken_links", lambda: check_broken_links(kb_dir)),
        ("orphan_pages", lambda: check_orphan_pages(kb_dir)),
        ("orphan_sources", lambda: check_orphan_sources(kb_dir, logs)),
        ("stale_articles", lambda: check_stale_articles(kb_dir, logs, compile_state)),
        ("missing_backlinks", lambda: check_missing_backlinks(kb_dir)),
        ("sparse_articles", lambda: check_sparse_articles(kb_dir)),
    ]:
        with contextlib.suppress(Exception):
            all_issues.extend(check_fn())

    # Aggregate counts
    errors = sum(1 for i in all_issues if i.severity == "error")
    warnings = sum(1 for i in all_issues if i.severity == "warning")
    suggestions = sum(1 for i in all_issues if i.severity == "suggestion")

    return ValidationReport(
        issues=all_issues,
        errors=errors,
        warnings=warnings,
        suggestions=suggestions,
        checked_at=_now_iso(),
    )
