# ASD — Autism Spectrum Driver

> **Autism Spectrum Driver** (ASD) is the systematizing memory layer for the BrainXio stack.
>
> It ingests raw, messy, contradictory inputs and produces clean, versioned, interconnected,
> queryable knowledge artifacts — a single source of truth that grows more useful with every entry.

## The ASD Parallel

Autism isn't a deficit — it's a different operating system. The autistic brain excels at pattern
recognition, systematic organization, and building richly interconnected semantic networks. It sees
the structure beneath the noise.

Most knowledge bases drift into entropy. Notes get dumped into flat folders. Cross-references rot.
Search becomes "hope the filename is descriptive enough." The more entries you add, the less useful
the whole thing becomes.

ASD externalizes the cognitive superpowers that make systematizing minds invaluable:

- **Pattern recognition**: ASD finds connections between articles that a keyword search would miss,
  building a web of cross-references automatically.
- **Hyper-systematizing**: Every artifact follows strict structure — YAML frontmatter, typed
  categories, validated consistency. No loose notes, no drift.
- **Semantic precision**: Disambiguation via aliases, tags, and typed relationships. A "mechanism"
  is never confused with an "outcome."
- **Routine adherence**: Ingest, compile, validate, query. The same pipeline every time. Structure
  over speed, always.

## Superpowers

ASD converts raw, ephemeral notes into a persistent, queryable knowledge base:

- **Structured artifacts**: Every article has YAML frontmatter with typed categories (concept,
  mechanism, outcome, reference, connection), aliases, tags, and source tracking
- **TF-IDF semantic search**: Find articles by meaning, not just keywords — with version-filtered
  queries
- **Cross-reference network**: Automatic connection discovery between related articles
- **Quality gates**: Per-mode thresholds that accept, warn, or reject based on completeness and
  consistency
- **Prototype scanning**: Survey project directories and produce ingestion shortlists with priority
  scoring

## Quick Start

```bash
# Clone and install
git clone git@github.com:BrainXio/autism-spectrum-driver.git
cd asd
uv pip install -e .

# Ingest raw markdown files
asd_ingest(source="USER/kb")

# Compile daily logs into structured articles
asd_compile(file="2026-04-29.md")

# Search the knowledge base
asd_query(question="What do we know about MCP servers?", top_k=5)

# Run validation checks
asd_validate()
```

## Architecture

### KB Artifact Format

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

Articles are organized by type into subdirectories under `USER/kb/`: `concepts/`, `mechanisms/`,
`outcomes/`, `references/`, `connections/`.

### Pipeline

```
Raw Markdown (daily logs, notes) → Ingestion → Structured KB Artifacts → TF-IDF Index → Semantic Query
                                         ↓
                                  Quality Gates (per-mode thresholds)
                                         ↓
                                  Validation (6 checks: links, orphans, backlinks, etc.)
```

### Design Philosophy

- **Structure over speed.** Every artifact follows a schema. Every relationship is explicit.
- **Explicit over implicit.** Frontmatter is mandatory. Types are enforced. Aliases are declared.
- **Graceful degradation.** Empty KB directory reports empty results, not errors. Stale indexes
  rebuild.

## MCP Integration

The sole interface is `asd-mcp`, a FastMCP stdio server registered via `.mcp.json`.

| Tool                  | Purpose                                   | ASD Parallel                               |
| --------------------- | ----------------------------------------- | ------------------------------------------ |
| `asd_set_mode`        | Switch active operational mode            | Switching contexts deliberately            |
| `asd_get_mode`        | Return current mode and thresholds        | Knowing your frame of mind                 |
| `asd_ingest`          | Raw markdown → processed artifacts        | Taking in information systematically       |
| `asd_compile`         | Daily logs → structured articles          | Building understanding from raw experience |
| `asd_query`           | TF-IDF semantic search (version-filtered) | Retrieving the exact fact you need         |
| `asd_validate`        | Structural consistency checks (6 checks)  | Checking your work for errors              |
| `asd_status`          | KB health report                          | Self-monitoring: how is the system doing?  |
| `asd_scan_prototypes` | Scan for projects to ingest next          | Surveying the landscape before organizing  |
| `asd_get_shortlist`   | Load prototype ingestion shortlist        | Reviewing the catalog before filing        |
| `asd_get_rules`       | Return structured KB rules and schema     | Self-documentation: here is how I work     |

### Cross-Repo Integration

ASD is consumed as an MCP server by:

- **Another-Intelligence**: Calls `asd_query` for semantic memory during PPAC decisions; calls
  `asd_compile` for daily knowledge consolidation
- **ADHD**: Posts KB status updates to the bus for cross-agent awareness

## Persistent Memory & RPE

ASD *is* the persistent memory layer. Knowledge compiled by ASD:

- **Survives across sessions**: Once compiled, articles persist until explicitly invalidated
- **Is versioned**: `source_version` field tracks knowledge freshness; queries can filter by minimum
  version
- **Drives better decisions**: Other agents query ASD to make informed choices based on accumulated
  knowledge
- **Supports RPE indirectly**: Decision outcomes can be compiled into the KB as `outcome`-type
  articles, closing the learning loop

## Development & Contribution

```bash
# Setup
uv sync
uv pip install -e ".[dev]"

# Tests (150+ passing)
uv run pytest -q
uv run pytest --cov=src/ --cov-report=term-missing

# Lint & format
uv run ruff check .
uv run ruff format --check .
```

**Contribution guidelines**: See `CONTRIBUTING.md` for branch naming, conventional commits, PR
workflow, and code style. All development must happen in worktrees.

### Environment Variables

| Variable           | Purpose                                     |
| ------------------ | ------------------------------------------- |
| `ASD_PROJECT_ROOT` | Absolute path to the project root           |
| `ASD_KB_DIR`       | Override KB directory (default: `USER/kb/`) |

### Cross-Repo Knowledge Access

Set `ASD_PROJECT_ROOT` to point at another repo's KB for shared knowledge access:

```bash
ASD_PROJECT_ROOT=/path/to/shared/project uv run asd-mcp
```

## Related Repos & Roadmap

### Ecosystem

| Package                  | Directory                                 | Role                                     | Type         |
| ------------------------ | ----------------------------------------- | ---------------------------------------- | ------------ |
| **ADHD**                 | `attention-deficit-hyperactivity-driver/` | Coordination nervous system              | MCP Server   |
| **Another-Intelligence** | `another-intelligence/`                   | Cognitive core — PPAC loop               | Agent / Host |
| **OCD**                  | `obsessive-compulsive-driver/`            | Discipline & enforcement — quality gates | MCP Server   |

### Roadmap

- [x] KB ingestion, compilation, validation pipeline
- [x] TF-IDF semantic search with version filtering
- [x] Quality gates with per-mode thresholds (developer/research/review/personal)
- [x] Prototype scanning and ingestion shortlisting
- [ ] Cross-repo KB sharing and synchronization
- [ ] Automated backlink discovery on compile

## License

Apache-2.0. See `LICENSE`.
