"""Compile daily conversation logs into structured knowledge articles.

Refactored from OCD kb/compile.py. Deterministic pipeline — no LLM dependency.
Reads daily logs from USER/logs/daily/ and produces markdown articles under
USER/kb/ with proper YAML frontmatter and cross-references.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

# ── Constants ──────────────────────────────────────────────────────────────────

_KB_SUBDIRS = ("concepts", "connections", "mechanisms", "outcomes", "references")
_DEFAULT_INDEX_HEADER = (
    "# Knowledge Base Index\n\n"
    "| Article | Summary | Compiled From | Updated |\n"
    "|---------|---------|---------------|---------|\n"
)


# ── Result type ─────────────────────────────────────────────────────────────────


@dataclass
class CompileResult:
    """Summary of a compilation run."""

    files_processed: int = 0
    articles_created: int = 0
    articles_updated: int = 0
    articles_skipped: int = 0
    errors: int = 0
    details: list[dict[str, Any]] = field(default_factory=list)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    """Current UTC time in ISO 8601 format."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def _today_iso() -> str:
    """Current date in ISO 8601 format."""
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _file_hash(path: Path) -> str:
    """SHA-256 hash of file content (first 16 hex chars)."""
    try:
        content = path.read_text(encoding="utf-8")
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    except OSError:
        return ""


def _slugify(text: str) -> str:
    """Convert a title string into a URL-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug.strip("-")


def _extract_wikilinks(text: str) -> list[str]:
    """Extract [[wikilink]] targets from markdown text."""
    return re.findall(r"\[\[([^\]]+)\]\]", text)


# ── Frontmatter ────────────────────────────────────────────────────────────────


def _split_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Split markdown content into (frontmatter_dict, body_text)."""
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


def _build_frontmatter(article: dict[str, Any]) -> str:
    """Build YAML frontmatter string from article fields."""
    lines = [
        "---",
        f'title: "{article["title"]}"',
        f"type: {article.get('article_type', 'concept')}",
    ]
    aliases = article.get("aliases", [])
    if aliases:
        alias_str = ", ".join(aliases)
        lines.append(f"aliases: [{alias_str}]")
    tags = article.get("tags", [])
    if tags:
        tag_str = ", ".join(tags)
        lines.append(f"tags: [{tag_str}]")
    sources = article.get("sources", [])
    if sources:
        source_str = ", ".join(sources)
        lines.append(f"sources: [{source_str}]")
    lines.append(f"created: {article.get('created', _today_iso())}")
    lines.append(f"updated: {article.get('updated', _today_iso())}")
    lines.append("---")
    return "\n".join(lines)


# ── Log extraction ─────────────────────────────────────────────────────────────


def _extract_sections(content: str) -> list[dict[str, str]]:
    """Extract ##-level sections from a daily log.

    Each section becomes a candidate article. Returns list of
    {heading, body} dicts.
    """
    sections: list[dict[str, str]] = []
    current_heading: str | None = None
    current_body: list[str] = []

    for line in content.splitlines():
        if line.startswith("## "):
            if current_heading is not None:
                sections.append(
                    {"heading": current_heading, "body": "\n".join(current_body).strip()},
                )
            current_heading = line[3:].strip()
            current_body = []
        elif current_heading is not None:
            current_body.append(line)

    if current_heading is not None:
        sections.append(
            {"heading": current_heading, "body": "\n".join(current_body).strip()},
        )

    return sections


def _classify_section(heading: str) -> tuple[str, str]:
    """Classify a section heading into (article_type, subdir).

    Returns ("concept", "concepts") as default.
    Special headings like "Connections" or "Mechanisms" get different types.
    """
    heading_lower = heading.lower()

    if "connection" in heading_lower or "link" in heading_lower:
        return ("connection", "connections")
    if "mechanism" in heading_lower or "pattern" in heading_lower:
        return ("mechanism", "mechanisms")
    if "outcome" in heading_lower or "result" in heading_lower or "validation" in heading_lower:
        return ("outcome", "outcomes")
    if "reference" in heading_lower or "resource" in heading_lower:
        return ("reference", "references")
    return ("concept", "concepts")


def _extract_key_points(body: str) -> str:
    """Extract bullet points from body text as key points."""
    points = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            points.append(stripped)
    return "\n".join(points[:5]) if points else ""


# ── Index management ───────────────────────────────────────────────────────────


def _read_index(index_path: Path) -> dict[str, dict[str, str]]:
    """Parse the KB index table into {slug: {summary, compiled_from, updated}}."""
    entries: dict[str, dict[str, str]] = {}
    if not index_path.exists():
        return entries

    content = index_path.read_text(encoding="utf-8")
    for line in content.splitlines():
        if not line.startswith("| [["):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 5:
            continue
        link = parts[1]
        slug = link.replace("[[", "").replace("]]", "")
        entries[slug] = {
            "summary": parts[2],
            "compiled_from": parts[3],
            "updated": parts[4],
        }
    return entries


def _update_index(
    index_path: Path,
    article_slug: str,
    title: str,
    source_file: str,
) -> None:
    """Add or update an entry in the KB index table."""
    index_path.parent.mkdir(parents=True, exist_ok=True)

    entries = _read_index(index_path)
    today = _today_iso()

    if article_slug in entries:
        entries[article_slug]["updated"] = today
    else:
        entries[article_slug] = {
            "summary": title,
            "compiled_from": source_file,
            "updated": today,
        }

    lines = [_DEFAULT_INDEX_HEADER.rstrip()]
    for slug in sorted(entries):
        entry = entries[slug]
        lines.append(
            f"| [[{slug}]] | {entry['summary']} | {entry['compiled_from']} | {entry['updated']} |",
        )

    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── Core compilation ───────────────────────────────────────────────────────────


def _compile_log_sections(
    log_content: str,
    log_name: str,
    kb_dir: Path,
) -> tuple[int, int, list[dict[str, Any]]]:
    """Extract sections from a daily log and produce KB articles.

    Returns (created, updated, details).
    """
    sections = _extract_sections(log_content)
    created = 0
    updated = 0
    details: list[dict[str, Any]] = []
    today = _today_iso()

    for section in sections:
        heading = section["heading"]
        body = section["body"]

        if len(body.split()) < 50:
            continue  # Skip sections that are too short

        article_type, subdir = _classify_section(heading)
        slug = _slugify(heading)
        article_path = kb_dir / subdir / f"{slug}.md"
        article_path.parent.mkdir(parents=True, exist_ok=True)

        # Determine tags from content analysis
        tags = [article_type]
        _extract_wikilinks(body)

        article_data: dict[str, Any] = {
            "title": heading,
            "article_type": article_type,
            "aliases": [],
            "tags": tags,
            "sources": [f"daily/{log_name}"],
            "created": today,
            "updated": today,
            "body": f"## Key Points\n\n{_extract_key_points(body)}\n\n## Details\n\n{body}",
            "slug": slug,
        }

        fm = _build_frontmatter(article_data)
        full_content = f"{fm}\n\n{article_data['body']}\n"

        if article_path.exists():
            article_path.read_text(encoding="utf-8")
            if _file_hash(article_path) == hashlib.sha256(full_content.encode()).hexdigest()[:16]:
                details.append({"slug": slug, "action": "skip", "title": heading})
                continue
            updated += 1
            details.append({"slug": slug, "action": "update", "title": heading})
        else:
            created += 1
            details.append({"slug": slug, "action": "create", "title": heading})

        article_path.write_text(full_content, encoding="utf-8")

        # Update index
        index_path = kb_dir / "index.md"
        _update_index(index_path, f"{subdir}/{slug}", heading, f"daily/{log_name}")

    return created, updated, details


# ── Public API ─────────────────────────────────────────────────────────────────


def compile_logs(
    *,
    logs_dir: Path,
    kb_dir: Path,
    all_logs: bool = False,
    file: str | None = None,
    dry_run: bool = False,
) -> CompileResult:
    """Compile daily conversation logs into structured knowledge articles.

    Args:
        logs_dir: Directory containing daily log files.
        kb_dir: Output directory for knowledge base articles.
        all_logs: Force recompile all logs regardless of state.
        file: Compile a specific log file (name only, e.g. '2026-04-29.md').
        dry_run: Report what would be compiled without writing files.

    Returns:
        CompileResult with counts and details.
    """
    import json as _json

    result = CompileResult()
    state_file = kb_dir / ".compile_state.json"

    # Load previous state
    prev_compiled: dict[str, dict[str, Any]] = {}
    if state_file.exists():
        try:
            state_data = _json.loads(state_file.read_text(encoding="utf-8"))
            prev_compiled = state_data.get("compiled", {})
        except (_json.JSONDecodeError, OSError):
            pass

    # Determine files to process
    if file:
        target = logs_dir / file
        if not target.exists():
            result.errors += 1
            result.details.append({"error": f"File not found: {file}"})
            return result
        to_compile = [target]
    else:
        all_log_files = sorted(logs_dir.glob("*.md")) if logs_dir.is_dir() else []
        if all_logs:
            to_compile = all_log_files
        else:
            to_compile = []
            for log_path in all_log_files:
                log_name = log_path.name
                prev = prev_compiled.get(log_name, {})
                if not prev or prev.get("hash") != _file_hash(log_path):
                    to_compile.append(log_path)

    result.files_processed = len(to_compile)

    if not to_compile:
        result.details.append({"message": "No files to compile — all logs are up to date."})
        return result

    if dry_run:
        for log_path in to_compile:
            result.details.append(
                {"file": log_path.name, "action": "would_compile"},
            )
        return result

    # Compile each log
    new_compiled: dict[str, dict[str, Any]] = dict(prev_compiled)
    for log_path in to_compile:
        log_name = log_path.name
        try:
            content = log_path.read_text(encoding="utf-8")
            created, updated, section_details = _compile_log_sections(
                content,
                log_name,
                kb_dir,
            )
            result.articles_created += created
            result.articles_updated += updated
            result.articles_skipped += len(
                [d for d in section_details if d.get("action") == "skip"],
            )
            result.details.append(
                {
                    "file": log_name,
                    "created": created,
                    "updated": updated,
                    "sections": section_details,
                },
            )
            new_compiled[log_name] = {
                "hash": _file_hash(log_path),
                "compiled_at": _now_iso(),
            }
        except Exception as e:
            result.errors += 1
            result.details.append({"file": log_name, "error": str(e)})

    # Persist state
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        _json.dumps(
            {"updated_at": _now_iso(), "compiled": new_compiled},
            indent=2,
        ),
        encoding="utf-8",
    )

    return result
