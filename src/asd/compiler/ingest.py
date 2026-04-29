"""Knowledge ingestion pipeline — raw markdown into cleaned KB artifacts.

Migrated from OCD kb/ingest.py. Scans USER/kb/ subdirectories for markdown
articles, parses frontmatter, computes quality scores, and writes cleaned
copies. Uses mtime-first change detection for fast incremental runs.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

# ── Subdirectory structure ─────────────────────────────────────────────────────

_KB_SUBDIRS = ("concepts", "connections", "mechanisms", "outcomes", "references")

# ── Result type ─────────────────────────────────────────────────────────────────


@dataclass
class IngestResult:
    """Summary of an ingestion run."""

    scanned: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    deleted: int = 0
    errors: int = 0
    details: list[dict[str, str]] = field(default_factory=list)


# ── Frontmatter parsing ────────────────────────────────────────────────────────


def _split_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Split markdown content into (frontmatter_dict, body_text).

    Returns ({}, content) if no frontmatter delimiters found.
    """
    if not content.startswith("---"):
        return {}, content
    end = content.find("---", 3)
    if end == -1:
        return {}, content
    fm_text = content[3:end].strip()
    body = content[end + 3 :].strip()

    result: dict[str, str] = {}
    for line in fm_text.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        result[key.strip()] = val.strip().strip('"').strip("'")
    return result, body


def _parse_list_field(value: str | None) -> list[str]:
    """Parse a YAML list field like '[tag1, tag2]' into a Python list."""
    if not value:
        return []
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [v.strip().strip('"').strip("'") for v in value.split(",") if v.strip()]


# ── Scoring ─────────────────────────────────────────────────────────────────────


def _score_article(frontmatter: dict[str, str], body: str) -> float:
    """Compute a quality score (0.0-1.0) for a raw article.

    Criteria (each worth 0.2):
    - Has a title in frontmatter
    - Has tags
    - Has sources
    - Word count >= 100
    - Contains wikilinks
    """
    score = 0.0
    if frontmatter.get("title"):
        score += 0.2
    tags = _parse_list_field(frontmatter.get("tags"))
    if tags:
        score += 0.2
    sources = _parse_list_field(frontmatter.get("sources"))
    if sources:
        score += 0.2
    if len(body.split()) >= 100:
        score += 0.2
    if re.findall(r"\[\[([^\]]+)\]\]", body):
        score += 0.2
    return round(score, 1)


# ── Hashing ────────────────────────────────────────────────────────────────────


def _file_hash(content: str) -> str:
    """SHA-256 hash of content (first 16 hex chars)."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# ── File scanning ──────────────────────────────────────────────────────────────


def _scan_kb_files(knowledge_dir: Path) -> list[Path]:
    """Scan knowledge directory for markdown article files."""
    if not knowledge_dir.is_dir():
        return []
    files: list[Path] = []
    for subdir_name in _KB_SUBDIRS:
        subdir = knowledge_dir / subdir_name
        if subdir.is_dir():
            files.extend(sorted(subdir.glob("*.md")))
    return files


# ── Timestamp helpers ──────────────────────────────────────────────────────────


def _now_iso() -> str:
    """Current UTC time in ISO 8601 format."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def _today_iso() -> str:
    """Current UTC date in ISO 8601 format."""
    return datetime.now(UTC).strftime("%Y-%m-%d")


# ── Core ingestion ─────────────────────────────────────────────────────────────


def ingest(
    *,
    kb_dir: Path,
    force_all: bool = False,
    dry_run: bool = False,
) -> IngestResult:
    """Ingest raw markdown articles into cleaned KB artifacts.

    Scans the knowledge directory, parses frontmatter, computes scores,
    and reports the state of all files. In dry-run mode, only reports
    without making changes. Writes a state file for change tracking.

    Uses mtime-first, hash-confirmed change detection for fast incremental runs.
    Detects orphaned files (deleted from disk) and reports them.
    """
    result = IngestResult()
    state_file = kb_dir / ".ingest_state.json"

    wiki_files = _scan_kb_files(kb_dir)
    result.scanned = len(wiki_files)

    # Load previous state for change detection
    prev_state: dict[str, dict[str, Any]] = {}
    if state_file.exists():
        try:
            raw = json.loads(state_file.read_text(encoding="utf-8"))
            prev_state = raw.get("files", {})
        except (json.JSONDecodeError, OSError):
            pass

    if dry_run:
        for f in wiki_files:
            content = f.read_text(encoding="utf-8")
            frontmatter, body = _split_frontmatter(content)
            score = _score_article(frontmatter, body)
            rel = str(f.relative_to(kb_dir))
            result.details.append(
                {"path": rel, "action": "would_ingest", "score": str(score)},
            )
        return result

    disk_paths: set[str] = set()
    current_state: dict[str, dict[str, Any]] = {}

    for f in wiki_files:
        rel_path = str(f.relative_to(kb_dir))
        disk_paths.add(rel_path)
        try:
            file_mtime = os.path.getmtime(f)

            # Fast path: mtime matches — skip
            if not force_all and rel_path in prev_state:
                prev = prev_state[rel_path]
                if prev.get("mtime") == file_mtime:
                    result.skipped += 1
                    current_state[rel_path] = prev
                    result.details.append(
                        {"path": rel_path, "action": "skip", "reason": "mtime_match"},
                    )
                    continue

            # Slow path: read and hash
            content = f.read_text(encoding="utf-8")
            content_hash = _file_hash(content)
            frontmatter, body = _split_frontmatter(content)

            # Check if content actually changed
            if not force_all and rel_path in prev_state:
                prev = prev_state[rel_path]
                if prev.get("hash") == content_hash:
                    # Mtime changed but content didn't
                    current_state[rel_path] = {**prev, "mtime": file_mtime}
                    result.skipped += 1
                    result.details.append(
                        {"path": rel_path, "action": "skip", "reason": "same_hash"},
                    )
                    continue

            title = frontmatter.get("title", f.stem)
            score = _score_article(frontmatter, body)
            is_new = rel_path not in prev_state

            current_state[rel_path] = {
                "title": title,
                "hash": content_hash,
                "mtime": file_mtime,
                "score": score,
                "ingested_at": _now_iso(),
            }

            action = "insert" if is_new else "update"
            if action == "insert":
                result.inserted += 1
            else:
                result.updated += 1
            result.details.append(
                {"path": rel_path, "action": action, "score": str(score)},
            )

        except Exception as e:
            result.errors += 1
            result.details.append(
                {"path": rel_path, "action": "error", "reason": str(e)},
            )

    # Detect orphaned files
    prev_paths = set(prev_state.keys())
    orphaned = prev_paths - disk_paths
    for orphan_path in orphaned:
        result.deleted += 1
        result.details.append(
            {"path": orphan_path, "action": "delete", "reason": "file_removed"},
        )

    # Persist state
    if not dry_run:
        kb_dir.mkdir(parents=True, exist_ok=True)
        state_data = {
            "updated_at": _now_iso(),
            "files": current_state,
        }
        state_file.write_text(json.dumps(state_data, indent=2), encoding="utf-8")

    return result


# ── KB status ──────────────────────────────────────────────────────────────────


def ingest_status(*, kb_dir: Path) -> dict[str, Any]:
    """Compare filesystem with the ingest state and report sync status.

    Returns a dict with:
        db_count: number of tracked articles
        disk_count: number of article files on disk
        new: list of paths on disk but not tracked
        stale: list of paths tracked but with different mtime
        orphaned: list of paths tracked but not on disk
        last_ingest: ISO timestamp of last ingestion, or None
        synced: True if tracked == disk and no new/stale/orphaned
    """
    state_file = kb_dir / ".ingest_state.json"
    wiki_files = _scan_kb_files(kb_dir)

    disk_paths: dict[str, float] = {}
    for f in wiki_files:
        rel = str(f.relative_to(kb_dir))
        with contextlib.suppress(OSError):
            disk_paths[rel] = os.path.getmtime(f)

    status: dict[str, Any] = {
        "db_count": 0,
        "disk_count": len(disk_paths),
        "new": [],
        "stale": [],
        "orphaned": [],
        "last_ingest": None,
        "synced": False,
    }

    if not state_file.exists():
        status["new"] = sorted(disk_paths)
        status["synced"] = len(disk_paths) == 0
        return status

    try:
        state_data = json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        status["new"] = sorted(disk_paths)
        return status

    prev_files: dict[str, dict[str, Any]] = state_data.get("files", {})
    status["db_count"] = len(prev_files)
    status["last_ingest"] = state_data.get("updated_at")

    new_paths = set(disk_paths) - set(prev_files)
    status["new"] = sorted(new_paths)

    orphaned_paths = set(prev_files) - set(disk_paths)
    status["orphaned"] = sorted(orphaned_paths)

    for path in sorted(set(disk_paths) & set(prev_files)):
        if disk_paths[path] != prev_files[path].get("mtime"):
            status["stale"].append(path)

    status["synced"] = not status["new"] and not status["stale"] and not status["orphaned"]
    return status
