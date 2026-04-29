# behave-asd Architecture

## System Role

ASD is the **systematizing memory layer** of the BrainXio stack. It ingests raw
information (daily logs, notes, references) and produces clean, versioned,
interconnected knowledge artifacts.

## Package Boundaries

- **Only interface**: `asd-mcp` (FastMCP stdio server)
- **Zero hard dependencies** on OCD, ADHD, or any other package
- **MCP-only** — no CLI, no standalone scripts
- **Storage**: Flat markdown files under `USER/kb/` with YAML frontmatter

## Module Map

```
src/asd/
├── mcp_server.py        FastMCP server with 7 tool endpoints
├── compiler/
│   ├── ingest.py        Raw input → cleaned artifacts
│   └── compile.py       Daily logs → structured articles
├── storage/
│   ├── artifacts.py     Pydantic data models
│   └── index.py         TF-IDF search engine
├── validation/
│   └── consistency.py   Structural KB checks (6 checks)
└── tools/
    └── developer.py     Tool handler implementations
```

## Data Flow

```
Raw Input (daily logs, notes)
        │
        ▼
    asd_compile ──► USER/kb/{concepts,connections,mechanisms,outcomes,references}/
        │
        ▼
    asd_ingest  ──► .ingest_state.json (change tracking)
        │
        ▼
    asd_query   ──► .index_cache.json (TF-IDF index)
        │
        ▼
    asd_validate ──► lint report (6 structural checks)
```

## KB Artifact Format

Every article is a `.md` file with YAML frontmatter:

```yaml
---
title: "Article Title"
type: concept | mechanism | outcome | reference | connection
aliases: []
tags: []
sources: ["daily/YYYY-MM-DD.md"]
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

## Key Design Decisions

1. **Flat files over SQLite** — git-friendly, zero schema management
2. **No LLM dependency** — deterministic pipelines; the MCP host handles LLM use
3. **TF-IDF over vector search** (MVP) — pure Python, no extras needed
4. **State files** — JSON files track ingest/compile state for incremental runs
