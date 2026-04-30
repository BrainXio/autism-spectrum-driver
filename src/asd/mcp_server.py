"""ASD MCP Server — FastMCP stdio server for the systematizing memory layer.

Exposes 10 MCP tools:
    asd_set_mode, asd_get_mode, asd_ingest, asd_compile,
    asd_query, asd_validate, asd_status,
    asd_scan_prototypes, asd_get_shortlist, asd_get_rules

Usage:
    uv run asd-mcp
    python -m asd.mcp_server
"""

from __future__ import annotations

import os
from pathlib import Path

from fastmcp import FastMCP

from asd.rules import get_rules
from asd.tools.developer import (
    handle_compile,
    handle_get_mode,
    handle_get_shortlist,
    handle_ingest,
    handle_query,
    handle_scan_prototypes,
    handle_set_mode,
    handle_status,
    handle_validate,
)

mcp = FastMCP("asd-mcp")


def _get_project_root() -> str:
    """Resolve project root from env var or CWD."""
    env_root = os.environ.get("ASD_PROJECT_ROOT")
    if env_root:
        return env_root
    return str(Path.cwd())


# ── Mode tools ─────────────────────────────────────────────────────────────────


@mcp.tool
def asd_set_mode(mode: str) -> dict:
    """Switch the active mode. Valid modes: developer, research, review, ops, personal.

    Each mode has different quality thresholds and validation rules.
    - developer: Standard gates for active development
    - research: Lenient gates for exploratory research
    - review: Strict gates for formal review
    - ops: Focused on operational content
    - personal: Permissive gates for personal notes

    Args:
        mode: The mode to activate.
    """
    return handle_set_mode(mode)


@mcp.tool
def asd_get_mode() -> dict:
    """Return the currently active mode."""
    return handle_get_mode()


# ── Ingestion ──────────────────────────────────────────────────────────────────


@mcp.tool
def asd_ingest(source: str = "USER/kb", force_all: bool = False, dry_run: bool = False) -> dict:
    """Ingest raw markdown files into cleaned, tracked KB artifacts.

    Scans USER/kb/ subdirectories for markdown articles, parses frontmatter,
    computes quality scores, and tracks state for change detection. Uses
    mtime-first, hash-confirmed change detection for fast incremental runs.

    Args:
        source: Source directory relative to project root (default: 'USER/kb').
        force_all: Re-ingest all files regardless of change detection.
        dry_run: Report what would be ingested without making changes.
    """
    project_root = _get_project_root()
    return handle_ingest(project_root, source=source, force_all=force_all, dry_run=dry_run)


# ── Compilation ────────────────────────────────────────────────────────────────


@mcp.tool
def asd_compile(all_logs: bool = False, file: str | None = None, dry_run: bool = False) -> dict:
    """Compile daily conversation logs into structured knowledge articles.

    Reads daily logs from USER/logs/daily/ and produces markdown articles
    under USER/kb/ with proper YAML frontmatter, cross-references, and
    index entries.

    Args:
        all_logs: Force recompile all logs regardless of state.
        file: Compile a specific log file by name (e.g. '2026-04-29.md').
        dry_run: Report what would be compiled without writing files.
    """
    project_root = _get_project_root()
    return handle_compile(project_root, all_logs=all_logs, file=file, dry_run=dry_run)


# ── Query ──────────────────────────────────────────────────────────────────────


@mcp.tool
def asd_query(
    question: str,
    top_k: int = 5,
    min_version: int | None = None,
    max_version: int | None = None,
) -> dict:
    """Search the knowledge base using TF-IDF relevance scoring.

    Builds or loads a cached search index from USER/kb/ and scores all
    articles against the query using cosine similarity over TF-IDF vectors.

    Args:
        question: Natural language search query.
        top_k: Maximum number of results to return (default: 5).
        min_version: Optional minimum source_version filter.
        max_version: Optional maximum source_version filter.
    """
    project_root = _get_project_root()
    return handle_query(
        project_root,
        question=question,
        top_k=top_k,
        min_version=min_version,
        max_version=max_version,
    )


# ── Validation ─────────────────────────────────────────────────────────────────


@mcp.tool
def asd_validate() -> dict:
    """Run all structural validation checks on the knowledge base.

    Checks: broken links, orphan pages, orphan sources, stale articles,
    missing backlinks, and sparse articles. Returns issue counts and
    a health status.
    """
    project_root = _get_project_root()
    return handle_validate(project_root)


# ── Status ─────────────────────────────────────────────────────────────────────


@mcp.tool
def asd_status() -> dict:
    """Report on current KB health.

    Returns article counts, sync state, new/stale/orphaned counts,
    last ingest/compile timestamps, and lint issue count.
    """
    project_root = _get_project_root()
    return handle_status(project_root)


# ── Entry point ────────────────────────────────────────────────────────────────


# ── Rules ──────────────────────────────────────────────────────────────────────


@mcp.tool
def asd_get_rules() -> dict:
    """Return structured KB rules for the ASD knowledge base.

    Returns a JSON object describing the KB schema, ingestion pipeline,
    artifact format, mode definitions with quality thresholds, validation
    checks, environment variables, and tool listing. Agents can call this
    at startup to learn how the knowledge base works.
    """
    return get_rules()


# ── Prototype scanner ──────────────────────────────────────────────────────────


@mcp.tool
def asd_scan_prototypes(
    scan_dir: str | None = None,
    output_file: str | None = None,
) -> dict:
    """Scan a directory for prototype projects and produce an ingestion shortlist.

    Walks scan_dir (defaults to the parent of the project root) looking for
    project directories. For each candidate, extracts domain, maturity,
    tech_stack, last_modified, topic_overlap, and suggested priority.
    Saves results to a shortlist JSON file.

    Args:
        scan_dir: Directory to scan for prototypes (default: project_root parent).
        output_file: Path for shortlist JSON (default: USER/shortlist.json).
    """
    project_root = _get_project_root()
    return handle_scan_prototypes(project_root, scan_dir=scan_dir, output_file=output_file)


@mcp.tool
def asd_get_shortlist(
    shortlist_path: str | None = None,
) -> dict:
    """Load a previously generated prototype shortlist.

    Returns the full shortlist with domain, maturity, priority, and rationale
    for each prototype. Use this to review which prototypes Cerebro should
    suggest for ingestion next.

    Args:
        shortlist_path: Path to the shortlist JSON (default: USER/shortlist.json).
    """
    project_root = _get_project_root()
    return handle_get_shortlist(project_root, shortlist_path=shortlist_path)


# ── Entry point ────────────────────────────────────────────────────────────────


def main() -> None:
    """Entry point for asd-mcp console script."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
