"""Prototype scanner — extract metadata from project folders for ingestion planning.

Walks a directory tree, identifies prototype projects, and extracts structured
metadata: domain, maturity, tech_stack, last_modified, topic_overlap. Produces
a shortlist.json for human or Cerebro review.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from asd.compiler._shared import _now_iso

# ── Domain keywords ─────────────────────────────────────────────────────────────

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "ai-ml": [
        "machine learning",
        "deep learning",
        "neural network",
        "transformer",
        "llm",
        "language model",
        "training",
        "inference",
        "ollama",
        "embedding",
        "rag",
        "fine-tuning",
        "prompt engineering",
        "agent",
        "rlhf",
    ],
    "neuroscience": [
        "brain",
        "neuron",
        "synapse",
        "dopamine",
        "prefrontal",
        "basal ganglia",
        "hippocampus",
        "amygdala",
        "cortex",
        "cognitive",
        "reward prediction",
        "action selection",
        "evidence accumulation",
    ],
    "knowledge-management": [
        "knowledge base",
        "wiki",
        "markdown",
        "frontmatter",
        "compilation",
        "ingest",
        "semantic search",
        "tf-idf",
        "indexing",
        "cross-reference",
    ],
    "dev-tools": [
        "mcp",
        "cli",
        "tool",
        "lint",
        "format",
        "ci",
        "test",
        "build",
        "package",
        "deploy",
        "hook",
        "plugin",
        "extension",
    ],
    "data-engineering": [
        "pipeline",
        "etl",
        "streaming",
        "batch",
        "database",
        "storage",
        "cache",
        "queue",
        "message bus",
        "event",
    ],
}

# ── Maturity indicators ────────────────────────────────────────────────────────

_MATURITY_INDICATORS: dict[str, list[str]] = {
    "production": [
        "ci.yml",
        ".github/workflows",
        "docker-compose.yml",
        "Dockerfile",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
    ],
    "beta": ["tests/", "test_", "_test.py", "conftest.py", "pyproject.toml"],
    "alpha": ["README.md", "setup.py", "requirements.txt"],
    "prototype": [".ipynb", "scratch", "prototype", "experiment"],
}

# ── Tech stack indicators ──────────────────────────────────────────────────────


def _detect_tech_stack(root: Path) -> list[str]:
    """Detect technology stack from project files."""
    stack: list[str] = []

    indicators: dict[str, str] = {
        "pyproject.toml": "python",
        "setup.py": "python",
        "requirements.txt": "python",
        "Pipfile": "python",
        "package.json": "javascript",
        "tsconfig.json": "typescript",
        "Cargo.toml": "rust",
        "go.mod": "go",
        "Makefile": "c/c++",
        "CMakeLists.txt": "c/c++",
        "Dockerfile": "docker",
        "docker-compose.yml": "docker",
    }

    for file_name, lang in indicators.items():
        if (root / file_name).exists() and lang not in stack:
            stack.append(lang)

    return sorted(stack) if stack else ["unknown"]


# ── File scanning ──────────────────────────────────────────────────────────────


def _scan_files(root: Path, max_files: int = 200) -> list[Path]:
    """Recursively collect readable text files, capped at max_files."""
    files: list[Path] = []
    text_extensions = {
        ".py",
        ".md",
        ".txt",
        ".yaml",
        ".yml",
        ".toml",
        ".json",
        ".ipynb",
        ".rs",
        ".go",
        ".js",
        ".ts",
        ".html",
        ".css",
        ".cfg",
        ".ini",
        ".sh",
        ".bash",
        ".zsh",
        ".dockerfile",
    }
    for dirpath, _dirnames, filenames in os.walk(root):
        for fname in filenames:
            if len(files) >= max_files:
                return files
            fpath = Path(dirpath) / fname
            if fpath.suffix in text_extensions:
                files.append(fpath)
    return files


def _read_file_safe(path: Path, max_bytes: int = 50_000) -> str:
    """Read a file safely, returning empty string on failure or oversized files."""
    try:
        if path.stat().st_size > max_bytes:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# ── Metadata extraction ────────────────────────────────────────────────────────


def _detect_domain(file_contents: list[str]) -> tuple[str, float]:
    """Detect primary domain from file contents using keyword matching.

    Returns (domain_label, confidence_score).
    """
    combined = " ".join(file_contents).lower()
    scores: dict[str, float] = {}

    for domain, keywords in _DOMAIN_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in combined)
        if hits:
            scores[domain] = hits / len(keywords)

    if not scores:
        return ("unknown", 0.0)

    best = max(scores, key=lambda k: scores[k])
    return (best, round(scores[best], 2))


def _detect_maturity(root: Path) -> str:
    """Detect project maturity level from file indicators."""
    for level, indicators in _MATURITY_INDICATORS.items():
        for indicator in indicators:
            found = (
                (indicator.endswith("/") and list(root.glob(f"**/{indicator}*")))
                or (root / indicator).exists()
                or any(root.glob(f"**/{indicator}"))
            )
            if found:
                return level
    return "unknown"


def _last_modified(root: Path) -> str:
    """Find the most recent modification time across all files."""
    latest = 0.0
    for dirpath, _dirnames, filenames in os.walk(root):
        for fname in filenames:
            try:
                mtime = os.path.getmtime(str(Path(dirpath) / fname))
                if mtime > latest:
                    latest = mtime
            except OSError:
                continue
    if latest:
        dt = datetime.fromtimestamp(latest, tz=UTC)
        return dt.isoformat(timespec="seconds")
    return _now_iso()


def _compute_topic_overlap(root: Path, existing_kb_topics: list[str]) -> float:
    """Estimate topic overlap with existing KB by scanning for topic mentions."""
    combined = ""
    for f in _scan_files(root, max_files=100):
        combined += _read_file_safe(f, max_bytes=10_000) + " "

    if not combined or not existing_kb_topics:
        return 0.0

    combined_lower = combined.lower()
    hits = sum(1 for topic in existing_kb_topics if topic.lower() in combined_lower)
    return round(hits / len(existing_kb_topics), 2)


# ── Project detection ──────────────────────────────────────────────────────────


def _is_project_directory(path: Path) -> bool:
    """Check if a directory looks like a project worth scanning."""
    indicators = [
        "pyproject.toml",
        "setup.py",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "Makefile",
        "README.md",
        "requirements.txt",
    ]
    for indicator in indicators:
        if (path / indicator).exists():
            return True
    # Check for .ipynb files
    if list(path.glob("*.ipynb")):
        return True
    # Check for multiple .py files
    py_files = list(path.glob("*.py"))
    return len(py_files) >= 2


# ── Result types ────────────────────────────────────────────────────────────────


@dataclass
class PrototypeMetadata:
    """Metadata for a single prototype project."""

    name: str
    path: str
    domain: str
    domain_confidence: float
    maturity: str
    tech_stack: list[str]
    last_modified: str
    topic_overlap: float
    file_count: int
    summary: str = ""
    suggested_priority: int = 3
    priority_rationale: str = ""


@dataclass
class ScanResult:
    """Result of a prototype directory scan."""

    scanned_at: str
    root_directory: str
    prototypes_found: int
    prototypes: list[dict[str, Any]] = field(default_factory=list)


# ── Priority scoring ───────────────────────────────────────────────────────────


def _compute_priority(meta: PrototypeMetadata) -> tuple[int, str]:
    """Assign a suggested ingestion priority (1=highest, 5=lowest) with rationale."""
    score = 0
    reasons: list[str] = []

    # High domain confidence is good
    if meta.domain_confidence >= 0.3:
        score += 2
        reasons.append(f"strong domain signal ({meta.domain})")
    elif meta.domain_confidence > 0:
        score += 1
        reasons.append(f"weak domain signal ({meta.domain})")

    # Maturity: prefer more mature (beta/production = more to ingest)
    if meta.maturity in ("production", "beta"):
        score += 2
        reasons.append(f"{meta.maturity}-level maturity")
    elif meta.maturity == "alpha":
        score += 1
        reasons.append("alpha-level maturity")

    # Known tech stack
    if meta.tech_stack and meta.tech_stack != ["unknown"]:
        score += 1
        reasons.append(f"known stack: {', '.join(meta.tech_stack)}")

    # Has topic overlap with KB
    if meta.topic_overlap >= 0.2:
        score += 1
        reasons.append("high topic overlap with existing KB")

    # File count indicates substance
    if meta.file_count >= 20:
        score += 1
        reasons.append("substantial file count")

    # Map score to priority
    if score >= 6:
        priority = 1
    elif score >= 4:
        priority = 2
    elif score >= 2:
        priority = 3
    elif score >= 1:
        priority = 4
    else:
        priority = 5

    rationale = "; ".join(reasons) if reasons else "no strong signals"
    return priority, rationale


# ── Public API ─────────────────────────────────────────────────────────────────


def scan_prototypes(
    *,
    root_dir: Path,
    existing_kb_topics: list[str] | None = None,
    max_prototypes: int = 50,
) -> ScanResult:
    """Scan a directory recursively for prototype projects.

    Args:
        root_dir: Directory to scan for prototypes.
        existing_kb_topics: List of topic strings from existing KB articles
            for computing topic overlap scores.
        max_prototypes: Maximum number of prototypes to process.

    Returns:
        ScanResult with all found prototypes and their metadata.
    """
    topics = existing_kb_topics or []
    result = ScanResult(
        scanned_at=_now_iso(),
        root_directory=str(root_dir),
        prototypes_found=0,
    )

    if not root_dir.is_dir():
        return result

    # Find candidate directories (limit depth to avoid scanning entire filesystem)
    candidates: list[Path] = []
    for entry in sorted(root_dir.iterdir()):
        if entry.is_dir() and not entry.name.startswith(".") and _is_project_directory(entry):
            candidates.append(entry)

    candidates = candidates[:max_prototypes]

    for candidate in candidates:
        try:
            files = _scan_files(candidate)
            contents = [_read_file_safe(f) for f in files]
            contents = [c for c in contents if c]

            domain, confidence = _detect_domain(contents)
            maturity = _detect_maturity(candidate)
            tech_stack = _detect_tech_stack(candidate)
            modified = _last_modified(candidate)
            overlap = _compute_topic_overlap(candidate, topics)

            # Build a short summary from README if present
            summary = ""
            readme_candidates = [
                "README.md",
                "README.txt",
                "README.rst",
                "README",
            ]
            for rc in readme_candidates:
                readme_path = candidate / rc
                if readme_path.exists():
                    summary = _read_file_safe(readme_path, max_bytes=2000)[:500]
                    break

            meta = PrototypeMetadata(
                name=candidate.name,
                path=str(candidate),
                domain=domain,
                domain_confidence=confidence,
                maturity=maturity,
                tech_stack=tech_stack,
                last_modified=modified,
                topic_overlap=overlap,
                file_count=len(files),
                summary=summary.split("\n")[0] if summary else "",
            )

            priority, rationale = _compute_priority(meta)
            meta.suggested_priority = priority
            meta.priority_rationale = rationale

            result.prototypes.append(
                {
                    "name": meta.name,
                    "path": meta.path,
                    "domain": meta.domain,
                    "domain_confidence": meta.domain_confidence,
                    "maturity": meta.maturity,
                    "tech_stack": meta.tech_stack,
                    "last_modified": meta.last_modified,
                    "topic_overlap": meta.topic_overlap,
                    "file_count": meta.file_count,
                    "summary": meta.summary,
                    "suggested_priority": meta.suggested_priority,
                    "priority_rationale": meta.priority_rationale,
                }
            )
        except Exception:
            continue

    # Sort by priority (highest first), then by confidence (descending)
    result.prototypes.sort(
        key=lambda p: (p["suggested_priority"], -p["domain_confidence"]),
    )
    result.prototypes_found = len(result.prototypes)

    return result


def save_shortlist(result: ScanResult, output_path: Path) -> Path:
    """Write scan results as a shortlist JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "scanned_at": result.scanned_at,
        "root_directory": result.root_directory,
        "prototypes_found": result.prototypes_found,
        "prototypes": result.prototypes,
    }
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return output_path


def load_shortlist(input_path: Path) -> ScanResult | None:
    """Load a previously saved shortlist JSON file."""
    if not input_path.exists():
        return None
    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
        return ScanResult(
            scanned_at=data.get("scanned_at", ""),
            root_directory=data.get("root_directory", ""),
            prototypes_found=data.get("prototypes_found", 0),
            prototypes=data.get("prototypes", []),
        )
    except (json.JSONDecodeError, OSError):
        return None
