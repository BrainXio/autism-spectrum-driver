"""MCP tool handler implementations for developer mode.

Each handler is a pure function that takes typed arguments and returns
a JSON-serializable result. The MCP server wraps these as tool endpoints.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from asd.compiler.compile import compile_logs
from asd.compiler.ingest import ingest, ingest_status
from asd.scanner import load_shortlist, save_shortlist, scan_prototypes
from asd.storage.index import build_index, is_index_stale, load_index, save_index, search
from asd.validation.consistency import validate

# ── Mode state ─────────────────────────────────────────────────────────────────

_current_mode: str = "developer"

# Mode-specific quality threshold presets
_MODE_DEFAULTS: dict[str, dict[str, Any]] = {
    "developer": {
        "min_words": 50,
        "min_words_reject": 10,
        "min_frontmatter_fields": 2,
        "required_frontmatter": ["title"],
        "min_quality_score": 0.2,
        "reject_quality_score": 0.0,
        "check_broken_links": True,
        "max_broken_links": 5,
    },
    "research": {
        "min_words": 30,
        "min_words_reject": 5,
        "min_frontmatter_fields": 1,
        "required_frontmatter": ["title"],
        "min_quality_score": 0.1,
        "reject_quality_score": 0.0,
        "check_broken_links": False,
        "max_broken_links": 10,
    },
    "review": {
        "min_words": 100,
        "min_words_reject": 20,
        "min_frontmatter_fields": 4,
        "required_frontmatter": ["title", "type", "tags"],
        "min_quality_score": 0.4,
        "reject_quality_score": 0.1,
        "check_broken_links": True,
        "max_broken_links": 2,
    },
    "ops": {
        "min_words": 30,
        "min_words_reject": 5,
        "min_frontmatter_fields": 2,
        "required_frontmatter": ["title"],
        "min_quality_score": 0.2,
        "reject_quality_score": 0.0,
        "check_broken_links": True,
        "max_broken_links": 5,
    },
    "personal": {
        "min_words": 10,
        "min_words_reject": 1,
        "min_frontmatter_fields": 1,
        "required_frontmatter": ["title"],
        "min_quality_score": 0.0,
        "reject_quality_score": 0.0,
        "check_broken_links": False,
        "max_broken_links": 999,
    },
}

# Mode descriptions for documentation
_MODE_DESCRIPTIONS: dict[str, str] = {
    "developer": "Standard thresholds for active development — balanced quality gates",
    "research": "Lenient gates for exploratory research notes and early prototypes",
    "review": "Strict gates for articles undergoing formal review before publication",
    "ops": "Focused on operational content — runbooks, incident reports, deployment notes",
    "personal": "Permissive gates for personal journal entries and private notes",
}


def _resolve_kb_dir(project_root: Path) -> Path:
    """Resolve the knowledge base directory within a project.

    Uses ASD_KB_DIR env var if set, otherwise defaults to USER/kb/.
    """
    import os

    env_kb = os.environ.get("ASD_KB_DIR")
    if env_kb:
        return Path(env_kb)
    return project_root / "USER" / "kb"


def _resolve_logs_dir(project_root: Path) -> Path:
    """Resolve the daily logs directory within a project."""
    return project_root / "USER" / "logs" / "daily"


def get_mode_thresholds() -> dict[str, Any]:
    """Return the quality thresholds for the currently active mode."""
    return dict(_MODE_DEFAULTS.get(_current_mode, _MODE_DEFAULTS["developer"]))


# ── Mode handlers ──────────────────────────────────────────────────────────────


def handle_set_mode(mode: str) -> dict[str, Any]:
    """Switch the active mode."""
    global _current_mode
    valid_modes = set(_MODE_DEFAULTS.keys())
    if mode not in valid_modes:
        return {
            "ok": False,
            "error": f"Invalid mode: '{mode}'. Valid modes: {sorted(valid_modes)}",
        }
    prev = _current_mode
    _current_mode = mode
    return {
        "ok": True,
        "previous": prev,
        "current": mode,
        "description": _MODE_DESCRIPTIONS.get(mode, ""),
        "thresholds": _MODE_DEFAULTS[mode],
    }


def handle_get_mode() -> dict[str, Any]:
    """Return the currently active mode."""
    return {
        "mode": _current_mode,
        "description": _MODE_DESCRIPTIONS.get(_current_mode, ""),
        "thresholds": get_mode_thresholds(),
        "available_modes": sorted(_MODE_DEFAULTS.keys()),
    }


# ── Ingestion ──────────────────────────────────────────────────────────────────


def handle_ingest(
    project_root: str,
    source: str = "USER/kb",
    force_all: bool = False,
    dry_run: bool = False,
    quality_thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ingest raw markdown files into cleaned KB artifacts.

    Args:
        project_root: Root directory of the project (usually CWD).
        source: Source directory relative to project root containing .md files.
        force_all: Re-ingest all files regardless of change detection.
        dry_run: Report what would be done without making changes.
        quality_thresholds: Optional dict of quality gate thresholds.
    """
    root = Path(project_root)
    kb_dir = _resolve_kb_dir(root)

    if not kb_dir.exists():
        return {
            "ok": False,
            "error": f"Knowledge base directory not found: {kb_dir}",
        }

    # Apply mode-specific defaults when no custom thresholds provided
    thresholds = quality_thresholds if quality_thresholds is not None else get_mode_thresholds()

    result = ingest(
        kb_dir=kb_dir,
        force_all=force_all,
        dry_run=dry_run,
        quality_thresholds=thresholds,
    )

    return {
        "ok": True,
        "scanned": result.scanned,
        "inserted": result.inserted,
        "updated": result.updated,
        "skipped": result.skipped,
        "deleted": result.deleted,
        "errors": result.errors,
        "rejected": result.rejected,
        "warned": result.warned,
        "details": result.details,
    }


# ── Compilation ────────────────────────────────────────────────────────────────


def handle_compile(
    project_root: str,
    all_logs: bool = False,
    file: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Compile daily conversation logs into structured knowledge articles.

    Args:
        project_root: Root directory of the project (usually CWD).
        all_logs: Force recompile all logs.
        file: Compile a specific log file by name.
        dry_run: Report what would be compiled without compiling.
    """
    root = Path(project_root)
    logs_dir = _resolve_logs_dir(root)
    kb_dir = _resolve_kb_dir(root)

    if not logs_dir.exists():
        return {
            "ok": False,
            "error": f"Logs directory not found: {logs_dir}",
        }

    result = compile_logs(
        logs_dir=logs_dir,
        kb_dir=kb_dir,
        all_logs=all_logs,
        file=file,
        dry_run=dry_run,
    )

    return {
        "ok": True,
        "files_processed": result.files_processed,
        "articles_created": result.articles_created,
        "articles_updated": result.articles_updated,
        "articles_skipped": result.articles_skipped,
        "errors": result.errors,
        "details": result.details,
    }


# ── Query ──────────────────────────────────────────────────────────────────────


def handle_query(
    project_root: str,
    question: str,
    top_k: int = 5,
    min_version: int | None = None,
    max_version: int | None = None,
) -> dict[str, Any]:
    """Search the knowledge base using TF-IDF relevance scoring.

    Args:
        project_root: Root directory of the project (usually CWD).
        question: Search query describing what to find.
        top_k: Maximum number of results to return.
        min_version: Optional minimum source_version filter.
        max_version: Optional maximum source_version filter.
    """
    root = Path(project_root)
    kb_dir = _resolve_kb_dir(root)
    cache_path = kb_dir / ".index_cache.json"

    if not kb_dir.exists():
        return {"ok": False, "error": f"Knowledge base directory not found: {kb_dir}"}

    # Load or rebuild index
    index = load_index(cache_path)
    if index is None or is_index_stale(index, kb_dir):
        index = build_index(kb_dir)
        save_index(index, cache_path)

    results = search(question, index, top_k=top_k, min_version=min_version, max_version=max_version)

    return {
        "ok": True,
        "question": question,
        "results": results,
        "index_updated": index.get("built_at", ""),
    }


# ── Validation ─────────────────────────────────────────────────────────────────


def handle_validate(project_root: str) -> dict[str, Any]:
    """Run all structural validation checks on the knowledge base.

    Args:
        project_root: Root directory of the project (usually CWD).
    """
    root = Path(project_root)
    kb_dir = _resolve_kb_dir(root)
    logs_dir = _resolve_logs_dir(root)

    if not kb_dir.exists():
        return {"ok": False, "error": f"Knowledge base directory not found: {kb_dir}"}

    report = validate(kb_dir=kb_dir, logs_dir=logs_dir)

    return {
        "ok": True,
        "is_healthy": report.is_healthy,
        "errors": report.errors,
        "warnings": report.warnings,
        "suggestions": report.suggestions,
        "checked_at": report.checked_at,
        "issues": [
            {
                "severity": i.severity,
                "check": i.check,
                "file": i.file,
                "detail": i.detail,
                "auto_fixable": i.auto_fixable,
            }
            for i in report.issues
        ],
    }


# ── Status ─────────────────────────────────────────────────────────────────────


def handle_status(project_root: str) -> dict[str, Any]:
    """Report on current KB health: article counts, sync state, timestamps.

    Args:
        project_root: Root directory of the project (usually CWD).
    """
    root = Path(project_root)
    kb_dir = _resolve_kb_dir(root)

    if not kb_dir.exists():
        return {
            "ok": True,
            "article_count": 0,
            "disk_count": 0,
            "new_count": 0,
            "stale_count": 0,
            "orphaned_count": 0,
            "last_ingest": None,
            "last_compile": None,
            "synced": False,
            "lint_issues": 0,
        }

    # Get ingest status
    ing_status = ingest_status(kb_dir=kb_dir)

    # Get compile state
    compile_state_file = kb_dir / ".compile_state.json"
    last_compile = None
    if compile_state_file.exists():
        try:
            cs = json.loads(compile_state_file.read_text(encoding="utf-8"))
            last_compile = cs.get("updated_at")
        except (json.JSONDecodeError, OSError):
            pass

    # Run a quick validation for lint count
    lint_count = 0
    try:
        report = validate(kb_dir=kb_dir)
        lint_count = report.errors + report.warnings + report.suggestions
    except Exception:
        pass

    return {
        "ok": True,
        "article_count": ing_status.get("db_count", 0),
        "disk_count": ing_status.get("disk_count", 0),
        "new_count": len(ing_status.get("new", [])),
        "stale_count": len(ing_status.get("stale", [])),
        "orphaned_count": len(ing_status.get("orphaned", [])),
        "last_ingest": ing_status.get("last_ingest"),
        "last_compile": last_compile,
        "synced": ing_status.get("synced", False),
        "lint_issues": lint_count,
    }


# ── Prototype scanner ──────────────────────────────────────────────────────────


def _collect_kb_topics(kb_dir: Path) -> list[str]:
    """Collect all tags and titles from existing KB articles as topic strings."""
    topics: list[str] = []
    from asd.compiler.ingest import _KB_SUBDIRS as kb_subdirs

    for subdir_name in kb_subdirs:
        subdir = kb_dir / subdir_name
        if not subdir.is_dir():
            continue
        for article_path in sorted(subdir.glob("*.md")):
            try:
                content = article_path.read_text(encoding="utf-8")
            except OSError:
                continue
            if content.startswith("---"):
                end = content.find("---", 3)
                if end != -1:
                    fm_text = content[3:end]
                    for line in fm_text.splitlines():
                        line = line.strip()
                        if line.startswith("title:"):
                            topics.append(line.split(":", 1)[1].strip().strip('"'))
                        elif line.startswith("tags:"):
                            val = line.split(":", 1)[1].strip()
                            if val.startswith("[") and val.endswith("]"):
                                items = [
                                    v.strip().strip('"').strip("'") for v in val[1:-1].split(",")
                                ]
                                topics.extend(i for i in items if i)
    return list(set(topics))


def handle_scan_prototypes(
    project_root: str,
    scan_dir: str | None = None,
    output_file: str | None = None,
) -> dict[str, Any]:
    """Scan a directory for prototype projects and produce a shortlist.

    Args:
        project_root: Root directory of the project (usually CWD).
        scan_dir: Directory to scan (defaults to project_root parent).
        output_file: Path to write shortlist JSON (defaults to USER/shortlist.json).
    """
    root = Path(project_root)
    kb_dir = _resolve_kb_dir(root)

    target = Path(scan_dir) if scan_dir else root.parent
    out = Path(output_file) if output_file else root / "USER" / "shortlist.json"

    existing_topics = _collect_kb_topics(kb_dir)
    result = scan_prototypes(root_dir=target, existing_kb_topics=existing_topics)
    save_shortlist(result, out)

    return {
        "ok": True,
        "scanned_at": result.scanned_at,
        "root_directory": result.root_directory,
        "prototypes_found": result.prototypes_found,
        "shortlist_path": str(out),
        "prototypes": result.prototypes,
    }


def handle_get_shortlist(
    project_root: str,
    shortlist_path: str | None = None,
) -> dict[str, Any]:
    """Load a previously generated prototype shortlist.

    Args:
        project_root: Root directory of the project (usually CWD).
        shortlist_path: Path to the shortlist JSON file.
    """
    root = Path(project_root)
    path = Path(shortlist_path) if shortlist_path else root / "USER" / "shortlist.json"

    result = load_shortlist(path)
    if result is None:
        return {"ok": False, "error": f"No shortlist found at {path}"}

    return {
        "ok": True,
        "scanned_at": result.scanned_at,
        "root_directory": result.root_directory,
        "prototypes_found": result.prototypes_found,
        "prototypes": result.prototypes,
    }
