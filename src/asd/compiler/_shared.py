"""Shared utility functions used across the ASD compiler, storage, and validation modules.

These were previously duplicated across compile.py, ingest.py, index.py,
scanner.py, and consistency.py. Consolidating them here eliminates ~200 lines
of duplicate code.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────────────────────

_KB_SUBDIRS = ("concepts", "connections", "mechanisms", "outcomes", "references")

# ── Timestamp helpers ──────────────────────────────────────────────────────────


def _now_iso() -> str:
    """Current UTC time in ISO 8601 format."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def _today_iso() -> str:
    """Current date in ISO 8601 format."""
    return datetime.now(UTC).strftime("%Y-%m-%d")


# ── File operations ────────────────────────────────────────────────────────────


def _file_hash(path: Path) -> str:
    """SHA-256 hash of file content (first 16 hex chars)."""
    try:
        content = path.read_text(encoding="utf-8")
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    except OSError:
        return ""


def _file_hash_str(content: str) -> str:
    """SHA-256 hash of a string (first 16 hex chars)."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _scan_kb_files(kb_dir: Path) -> list[Path]:
    """Scan knowledge base directory for markdown article files."""
    if not kb_dir.is_dir():
        return []
    files: list[Path] = []
    for subdir_name in _KB_SUBDIRS:
        subdir = kb_dir / subdir_name
        if subdir.is_dir():
            files.extend(sorted(subdir.glob("*.md")))
    return files


# ── Parsing helpers ────────────────────────────────────────────────────────────


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


def _extract_wikilinks(text: str) -> list[str]:
    """Extract [[wikilink]] targets from markdown text."""
    return re.findall(r"\[\[([^\]]+)\]\]", text)
