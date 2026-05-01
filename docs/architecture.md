# ASD Architecture

## System Role

ASD is the **systematizing memory layer** of the BrainXio stack. It ingests raw information (daily
logs, notes, references) and produces clean, versioned, interconnected knowledge artifacts.

## Package Boundaries

- **Only interface**: `asd-mcp` (FastMCP stdio server)
- **Zero hard dependencies** on OCD, ADHD, or any other package
- **MCP-only** — no CLI, no standalone scripts
- **Storage**: Flat markdown files under `USER/kb/` with YAML frontmatter

## Module Map

```
src/asd/
├── mcp_server.py        FastMCP server with 10 tool endpoints
├── scanner.py           Prototype project scanner and shortlist generator
├── compiler/
│   ├── ingest.py        Raw input → cleaned artifacts (with quality gates)
│   └── compile.py       Daily logs → structured articles
├── storage/
│   ├── artifacts.py     Pydantic data models
│   └── index.py         TF-IDF search engine
├── validation/
│   └── consistency.py   Structural KB checks (6 checks)
└── tools/
    └── developer.py     Tool handler implementations (5 modes)
```

## Data Flow

```
Raw Input (daily logs, notes, prototypes)
        │
        ▼
    asd_scan_prototypes ──► USER/shortlist.json (ingestion planning)
        │
        ▼
    asd_compile ──► USER/kb/{concepts,connections,mechanisms,outcomes,references}/
        │
        ▼
    asd_ingest  ──► .ingest_state.json (change tracking + versioning + quality)
        │
        ▼
    asd_query   ──► .index_cache.json (TF-IDF index, version-filterable)
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
source_version: 1
ingest_date: YYYY-MM-DD
historical_context: "Compiled from daily log YYYY-MM-DD.md"
---
```

## Modes

Five modes with distinct quality thresholds:

| Mode      | Min Words | Min Score | Required FM       | Link Check |
| --------- | --------- | --------- | ----------------- | ---------- |
| developer | 50        | 0.2       | title             | yes        |
| research  | 30        | 0.1       | title             | no         |
| review    | 100       | 0.4       | title, type, tags | yes        |
| ops       | 30        | 0.2       | title             | yes        |
| personal  | 10        | 0.0       | title             | no         |

## MCP Tools (10)

| Tool                | Description                           |
| ------------------- | ------------------------------------- |
| asd_set_mode        | Switch active mode                    |
| asd_get_mode        | Get current mode and thresholds       |
| asd_ingest          | Ingest markdown with quality gates    |
| asd_compile         | Compile daily logs into articles      |
| asd_query           | TF-IDF search with version filtering  |
| asd_validate        | Run 6 structural checks               |
| asd_status          | KB health report                      |
| asd_scan_prototypes | Scan for prototype projects           |
| asd_get_shortlist   | Load prototype ingestion shortlist    |
| asd_get_rules       | Return structured KB rules and schema |

## Bus Etiquette

Agents communicating on the ADHD bus must follow these rules:

- **No duplicate questions**: Check recent bus messages before posting a question. If the answer
  already exists, use it instead of re-asking.
- **Single recipient**: Address questions to one specific agent, not `all`. Duplicate questions to
  multiple supporters create noise and waste context.
- **Read before write**: Always `adhd_read(limit=30)` before posting. The answer may already be
  sitting in the last 20-30 messages.

## Key Design Decisions

1. **Flat files over SQLite** — git-friendly, zero schema management
2. **No LLM dependency** — deterministic pipelines; the MCP host handles LLM use
3. **TF-IDF over vector search** (MVP) — pure Python, no extras needed
4. **State files** — JSON files track ingest/compile state for incremental runs
