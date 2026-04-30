"""Self-describing rules for the ASD knowledge compilation layer.

Exposes KB schema, ingestion rules, artifact format, mode semantics,
and environment variable reference so agents can discover ASD capabilities
at runtime via asd_get_rules.
"""

from __future__ import annotations


def get_rules() -> dict[str, object]:
    """Return structured rules for the ASD knowledge base.

    Versioned and matching the current KB schema. MCP clients can
    call asd_get_rules at startup to learn the KB protocol.
    """
    return {
        "package": "asd",
        "version": "0.1.0",
        "description": "Systematizing memory — knowledge compilation layer",
        "kb_schema": {
            "artifact_format": {
                "description": "Every article is a .md file with YAML frontmatter under USER/kb/",
                "subdirs": [
                    "concepts",
                    "connections",
                    "mechanisms",
                    "outcomes",
                    "references",
                ],
                "frontmatter_fields": {
                    "required": ["title"],
                    "recommended": ["type", "tags", "sources", "created", "updated"],
                    "versioning": ["source_version", "ingest_date", "historical_context"],
                },
                "article_types": [
                    "concept",
                    "mechanism",
                    "outcome",
                    "reference",
                    "connection",
                ],
                "example": (
                    "---\n"
                    'title: "Article Title"\n'
                    "type: concept\n"
                    "aliases: []\n"
                    "tags: [tag1, tag2]\n"
                    'sources: ["daily/2026-04-30.md"]\n'
                    "created: 2026-04-30\n"
                    "updated: 2026-04-30\n"
                    "source_version: 1\n"
                    "ingest_date: 2026-04-30\n"
                    'historical_context: "Compiled from daily log"\n'
                    "---"
                ),
            },
            "ingestion": {
                "description": "Raw markdown → cleaned KB artifacts with quality gating",
                "detection": "mtime-first, hash-confirmed change detection",
                "state_file": ".ingest_state.json",
                "quality_gating": {
                    "description": "Articles are scored and checked against mode-specific thresholds",
                    "score_criteria": [
                        "title in frontmatter (+0.2)",
                        "tags present (+0.2)",
                        "sources present (+0.2)",
                        "word count >= 100 (+0.2)",
                        "contains wikilinks (+0.2)",
                    ],
                    "rejection_reasons": [
                        "word count below mode's min_words_reject",
                        "missing required frontmatter fields",
                        "quality score at or below reject_quality_score",
                    ],
                },
                "compilation": {
                    "description": "Daily logs → structured KB articles",
                    "input": "USER/logs/daily/*.md",
                    "output": "USER/kb/{subdir}/{slug}.md",
                    "section_min_words": 50,
                    "state_file": ".compile_state.json",
                },
            },
            "search": {
                "engine": "TF-IDF",
                "caching": ".index_cache.json",
                "version_filtering": "min_version / max_version params on asd_query",
                "fallback": "Most-recently-updated articles when no match above threshold",
            },
            "validation": {
                "description": "6 deterministic structural checks, no LLM dependency",
                "checks": [
                    {
                        "name": "broken_links",
                        "severity": "error",
                        "description": "[[wikilinks]] to non-existent articles",
                    },
                    {
                        "name": "orphan_pages",
                        "severity": "warning",
                        "description": "Articles with zero inbound links",
                    },
                    {
                        "name": "orphan_sources",
                        "severity": "warning",
                        "description": "Daily logs not referenced by any article",
                    },
                    {
                        "name": "stale_articles",
                        "severity": "warning",
                        "description": "Source logs changed since last compilation",
                    },
                    {
                        "name": "missing_backlinks",
                        "severity": "suggestion",
                        "description": "Asymmetric links (A→B but B↛A)",
                    },
                    {
                        "name": "sparse_articles",
                        "severity": "suggestion",
                        "description": "Articles below minimum word count",
                    },
                ],
            },
        },
        "modes": [
            {
                "name": "developer",
                "description": "Standard thresholds for active development",
                "min_words": 50,
                "min_words_reject": 10,
                "min_frontmatter_fields": 2,
                "required_frontmatter": ["title"],
                "min_quality_score": 0.2,
                "reject_quality_score": 0.0,
            },
            {
                "name": "research",
                "description": "Lenient gates for exploratory research notes",
                "min_words": 30,
                "min_words_reject": 5,
                "min_frontmatter_fields": 1,
                "required_frontmatter": ["title"],
                "min_quality_score": 0.1,
                "reject_quality_score": 0.0,
            },
            {
                "name": "review",
                "description": "Strict gates for formal review before publication",
                "min_words": 100,
                "min_words_reject": 20,
                "min_frontmatter_fields": 4,
                "required_frontmatter": ["title", "type", "tags"],
                "min_quality_score": 0.4,
                "reject_quality_score": 0.1,
            },
            {
                "name": "ops",
                "description": "Focused on operational content",
                "min_words": 30,
                "min_words_reject": 5,
                "min_frontmatter_fields": 2,
                "required_frontmatter": ["title"],
                "min_quality_score": 0.2,
                "reject_quality_score": 0.0,
            },
            {
                "name": "personal",
                "description": "Permissive gates for personal journal entries",
                "min_words": 10,
                "min_words_reject": 1,
                "min_frontmatter_fields": 1,
                "required_frontmatter": ["title"],
                "min_quality_score": 0.0,
                "reject_quality_score": 0.0,
            },
        ],
        "env_vars": [
            {
                "name": "ASD_PROJECT_ROOT",
                "purpose": "Project root directory",
                "default": "Current working directory",
            },
            {
                "name": "ASD_KB_DIR",
                "purpose": "Knowledge base directory path",
                "default": "USER/kb/ relative to project root",
            },
        ],
        "tools": [
            {"tool": "asd_set_mode", "purpose": "Switch active mode"},
            {
                "tool": "asd_get_mode",
                "purpose": "Get current mode, thresholds, and available modes",
            },
            {"tool": "asd_ingest", "purpose": "Ingest markdown files into cleaned KB artifacts"},
            {"tool": "asd_compile", "purpose": "Compile daily logs into structured articles"},
            {
                "tool": "asd_query",
                "purpose": "Search KB via TF-IDF with optional version filtering",
            },
            {"tool": "asd_validate", "purpose": "Run all 6 structural validation checks"},
            {"tool": "asd_status", "purpose": "KB health report with sync and lint counts"},
            {
                "tool": "asd_scan_prototypes",
                "purpose": "Scan directories for prototype projects and produce shortlist",
            },
            {
                "tool": "asd_get_shortlist",
                "purpose": "Load previously generated prototype ingestion shortlist",
            },
            {"tool": "asd_get_rules", "purpose": "Return these KB rules"},
        ],
        "cross_references": {
            "adhd": {
                "package": "adhd",
                "role": "Coordination bus",
                "get_rules_tool": "adhd_get_rules",
                "tools_for_asd": [
                    "adhd_signin",
                    "adhd_start_heartbeat",
                    "adhd_send",
                    "adhd_post",
                ],
            },
            "ocd": {
                "package": "ocd",
                "role": "Quality enforcement",
                "get_rules_tool": "ocd_get_rules",
                "tools_for_asd": [
                    "ocd_check",
                    "ocd_lint_work",
                    "ocd_run_formatters",
                ],
            },
        },
    }
