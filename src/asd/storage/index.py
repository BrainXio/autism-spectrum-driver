"""TF-IDF index management and search for the knowledge base.

Migrated and simplified from OCD kb/relevance.py. Pure Python — no external
dependencies beyond stdlib. Builds a JSON-cached search index from flat markdown
files under USER/kb/.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

# ── Stop words ─────────────────────────────────────────────────────────────────

_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "about",
        "after",
        "all",
        "also",
        "am",
        "an",
        "and",
        "any",
        "are",
        "as",
        "at",
        "back",
        "be",
        "because",
        "been",
        "being",
        "but",
        "by",
        "can",
        "come",
        "could",
        "day",
        "did",
        "do",
        "does",
        "doing",
        "even",
        "first",
        "for",
        "from",
        "get",
        "give",
        "go",
        "good",
        "had",
        "has",
        "have",
        "having",
        "he",
        "her",
        "him",
        "his",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "just",
        "know",
        "like",
        "look",
        "make",
        "me",
        "most",
        "my",
        "new",
        "no",
        "not",
        "now",
        "of",
        "on",
        "one",
        "only",
        "or",
        "other",
        "our",
        "out",
        "over",
        "people",
        "say",
        "see",
        "she",
        "so",
        "some",
        "take",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "think",
        "this",
        "time",
        "to",
        "two",
        "up",
        "us",
        "use",
        "want",
        "was",
        "way",
        "we",
        "well",
        "were",
        "what",
        "when",
        "which",
        "who",
        "will",
        "with",
        "work",
        "would",
        "year",
        "you",
        "your",
    },
)

_MIN_SCORE = 0.1
_SEARCHABLE_SUBDIRS = ("concepts", "connections", "mechanisms", "outcomes", "references")


# ── Tokenization ───────────────────────────────────────────────────────────────


def tokenize(text: str) -> list[str]:
    """Extract lowercase word tokens from text, filtering stop words."""
    words = re.findall(r"\b[a-z]{2,}\b", text.lower())
    return [w for w in words if w not in _STOP_WORDS]


# ── TF-IDF ─────────────────────────────────────────────────────────────────────


def _term_freq(tokens: list[str]) -> dict[str, float]:
    """Compute normalized term frequency for a token list."""
    if not tokens:
        return {}
    counts: dict[str, int] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    total = len(tokens)
    return {t: c / total for t, c in counts.items()}


def _idf(all_docs: list[dict[str, float]]) -> dict[str, float]:
    """Compute inverse document frequency across all document term-frequency dicts."""
    n = len(all_docs)
    if n == 0:
        return {}
    doc_freq: dict[str, int] = {}
    for doc in all_docs:
        for term in doc:
            doc_freq[term] = doc_freq.get(term, 0) + 1
    return {t: math.log(n / df) for t, df in doc_freq.items()}


def _tfidf_vector(tf: dict[str, float], idf: dict[str, float]) -> dict[str, float]:
    """Compute TF-IDF vector by multiplying term freq by inverse doc freq."""
    return {t: tf[t] * idf.get(t, 0.0) for t in tf}


def _cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """Compute cosine similarity between two sparse vectors represented as dicts."""
    common = set(vec_a) & set(vec_b)
    if not common:
        return 0.0
    dot = sum(vec_a[t] * vec_b[t] for t in common)
    mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
    mag_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ── Frontmatter ────────────────────────────────────────────────────────────────


def _parse_frontmatter(content: str) -> dict[str, Any]:
    """Extract YAML frontmatter fields from markdown content."""
    if not content.startswith("---"):
        return {}
    end = content.find("---", 3)
    if end == -1:
        return {}
    fm = content[3:end]
    result: dict[str, Any] = {}
    for line in fm.strip().splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if val.startswith("[") and val.endswith("]"):
            items = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",")]
            result[key] = [i for i in items if i]
        else:
            result[key] = val
    return result


def _extract_wikilinks(text: str) -> list[str]:
    """Extract [[wikilink]] targets from text."""
    return re.findall(r"\[\[([^\]]+)\]\]", text)


def _file_hash(path: Path) -> str:
    """SHA-256 hex digest of file content (first 16 chars)."""
    try:
        content = path.read_text(encoding="utf-8")
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    except OSError:
        return ""


# ── Index building ─────────────────────────────────────────────────────────────


def _scan_kb_files(kb_dir: Path) -> list[Path]:
    """Scan knowledge base directory for markdown article files."""
    if not kb_dir.is_dir():
        return []
    files: list[Path] = []
    for subdir_name in _SEARCHABLE_SUBDIRS:
        subdir = kb_dir / subdir_name
        if subdir.is_dir():
            files.extend(sorted(subdir.glob("*.md")))
    return files


def build_index(kb_dir: Path) -> dict[str, Any]:
    """Scan all KB articles and build a search index with TF-IDF metadata.

    Returns a JSON-serializable dict with:
        version, built_at, article_count, articles, idf
    """
    articles: list[dict[str, Any]] = []
    all_tfs: list[dict[str, float]] = []

    for article_path in _scan_kb_files(kb_dir):
        rel = str(article_path.relative_to(kb_dir))
        try:
            content = article_path.read_text(encoding="utf-8")
        except OSError:
            continue

        fm = _parse_frontmatter(content)
        title = fm.get("title", article_path.stem)
        tags: list[str] = fm.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        aliases: list[str] = fm.get("aliases", [])
        if isinstance(aliases, str):
            aliases = [aliases]
        sources: list[str] = fm.get("sources", [])
        if isinstance(sources, str):
            sources = [sources]

        searchable = " ".join(
            [str(title)] + tags + aliases + sources + [content],
        )
        tokens = tokenize(searchable)
        tf = _term_freq(tokens)

        src_version = fm.get("source_version", "1")
        try:
            src_version_int = int(str(src_version))
        except (ValueError, TypeError):
            src_version_int = 1

        articles.append(
            {
                "path": rel,
                "title": str(title),
                "summary": fm.get("summary", ""),
                "tags": tags,
                "aliases": aliases,
                "updated": str(fm.get("updated", "")),
                "source_version": src_version_int,
                "ingest_date": str(fm.get("ingest_date", "")),
                "tf": tf,
                "hash": _file_hash(article_path),
            },
        )
        all_tfs.append(tf)

    idf = _idf(all_tfs)
    for entry in articles:
        entry["tfidf"] = _tfidf_vector(entry["tf"], idf)

    return {
        "version": 1,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "article_count": len(articles),
        "idf": idf,
        "articles": [
            {
                "path": a["path"],
                "title": a["title"],
                "summary": a["summary"],
                "tags": a["tags"],
                "aliases": a["aliases"],
                "updated": a["updated"],
                "source_version": a["source_version"],
                "ingest_date": a["ingest_date"],
                "tfidf": a["tfidf"],
                "hash": a["hash"],
            }
            for a in articles
        ],
    }


# ── Search ─────────────────────────────────────────────────────────────────────


def search(
    query: str,
    index: dict[str, Any],
    top_k: int = 5,
    min_version: int | None = None,
    max_version: int | None = None,
) -> list[dict[str, Any]]:
    """Score articles against a query and return the top_k most relevant.

    Args:
        query: Search query string.
        index: Pre-built search index from build_index().
        top_k: Maximum number of results.
        min_version: Optional minimum source_version filter.
        max_version: Optional maximum source_version filter.

    Returns list of dicts with: path, title, summary, score.
    Falls back to most-recently-updated articles when no article scores
    above _MIN_SCORE.
    """
    if not query or not index.get("articles"):
        return _fallback_recent(index, top_k)

    query_tokens = tokenize(query)
    if not query_tokens:
        return _fallback_recent(index, top_k)

    query_tf = _term_freq(query_tokens)
    query_idf = index.get("idf", {})
    query_tfidf = _tfidf_vector(query_tf, query_idf)

    scored = []
    for article in index["articles"]:
        # Apply version range filter
        article_version = article.get("source_version", 1)
        if min_version is not None and article_version < min_version:
            continue
        if max_version is not None and article_version > max_version:
            continue

        article_tfidf = article.get("tfidf", {})
        if not article_tfidf:
            continue
        score = _cosine_similarity(query_tfidf, article_tfidf)
        scored.append(
            {
                "path": article["path"],
                "title": article["title"],
                "summary": article.get("summary", ""),
                "score": score,
                "source_version": article_version,
            },
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:top_k]

    if not top or top[0]["score"] < _MIN_SCORE:
        return _fallback_recent(index, top_k)

    return top


def _fallback_recent(index: dict[str, Any], top_k: int) -> list[dict[str, Any]]:
    """Return the most recently updated articles as a fallback."""
    articles = index.get("articles", [])
    sorted_articles = sorted(articles, key=lambda a: a.get("updated", ""), reverse=True)
    return [
        {
            "path": a["path"],
            "title": a["title"],
            "summary": a.get("summary", ""),
            "score": 0.0,
        }
        for a in sorted_articles[:top_k]
    ]


# ── Index persistence ──────────────────────────────────────────────────────────


def load_index(cache_path: Path) -> dict[str, Any] | None:
    """Load a cached index from disk, or None if not found / corrupted."""
    if not cache_path.exists():
        return None
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_index(index: dict[str, Any], cache_path: Path) -> Path:
    """Write the index JSON to disk."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    return cache_path


def is_index_stale(index: dict[str, Any] | None, kb_dir: Path) -> bool:
    """Check if the index needs rebuilding (missing, hashes differ, count changed)."""
    if index is None:
        return True
    indexed_hashes = {a["path"]: a["hash"] for a in index.get("articles", [])}
    for article_path in _scan_kb_files(kb_dir):
        rel = str(article_path.relative_to(kb_dir))
        if rel not in indexed_hashes or indexed_hashes[rel] != _file_hash(article_path):
            return True
    indexed_paths = set(indexed_hashes.keys())
    current_paths = {str(p.relative_to(kb_dir)) for p in _scan_kb_files(kb_dir)}
    return indexed_paths != current_paths


# ── Article loading ────────────────────────────────────────────────────────────


def load_article_content(
    scored: list[dict[str, Any]],
    kb_dir: Path,
    max_chars: int = 8000,
) -> str:
    """Load the full text of scored articles for context injection.

    Truncates to max_chars if needed.
    """
    parts: list[str] = []
    total = 0

    for entry in scored:
        path = kb_dir / entry["path"]
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue

        header = f"## {entry['path'].replace('.md', '')}"
        if entry.get("score", 0) > 0:
            header += f" (relevance: {entry['score']:.2f})"

        article_text = f"{header}\n\n{content}"
        if total + len(article_text) > max_chars:
            remaining = max_chars - total
            if remaining > 200:
                article_text = article_text[:remaining] + "\n\n...(truncated)"
                parts.append(article_text)
            break
        parts.append(article_text)
        total += len(article_text)

    return "\n\n---\n\n".join(parts)
