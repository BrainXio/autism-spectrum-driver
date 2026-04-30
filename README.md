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

## What This Is

An MCP-native knowledge compilation server that turns raw markdown inputs (daily logs, notes,
references) into structured, indexed, validated knowledge artifacts. It works with Claude Code,
Another Intelligence, or any agent with MCP support. Think of it as a librarian that never misfiles
a book and always knows what's on every shelf.

## Core Architecture

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
---
```

Articles are organized by type into subdirectories under `USER/kb/`: `concepts/`, `mechanisms/`,
`outcomes/`, `references/`, `connections/`.

### MCP Server

The sole interface is `asd-mcp`, a FastMCP stdio server registered via `.mcp.json`.

| Tool           | Purpose                                  | ASD Parallel                               |
| -------------- | ---------------------------------------- | ------------------------------------------ |
| `asd_set_mode` | Switch active operational mode           | Switching contexts deliberately            |
| `asd_get_mode` | Return current mode                      | Knowing your frame of mind                 |
| `asd_ingest`   | Raw markdown → processed artifacts       | Taking in information systematically       |
| `asd_compile`  | Daily logs → structured articles         | Building understanding from raw experience |
| `asd_query`    | TF-IDF semantic search                   | Retrieving the exact fact you need         |
| `asd_validate` | Structural consistency checks (6 checks) | Checking your work for errors              |
| `asd_status`   | KB health report                         | Self-monitoring: how is the system doing?  |

## Installation

```bash
git clone git@github.com:BrainXio/ASD.git
cd asd
uv pip install -e .
```

## Usage

### Ingest raw markdown files

```
asd_ingest(source="USER/kb")
```

### Compile daily logs into structured articles

```
asd_compile(file="2026-04-29.md")
```

### Search the knowledge base

```
asd_query(question="What do we know about MCP servers?", top_k=5)
```

### Run validation checks

```
asd_validate()
```

## KB Storage Location

The knowledge base lives under the project root's `USER/kb/` directory. Configure via environment
variables for cross-repo access.

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

## Design Philosophy

**Structure over speed.** Every artifact follows a schema. Every relationship is explicit. A KB
that's fast to write but impossible to query isn't a KB — it's a junk drawer.

**Explicit over implicit.** Frontmatter is mandatory. Types are enforced. Aliases are declared. The
KB doesn't guess what you meant — it tells you when you're ambiguous.

**Graceful degradation.** If the KB directory is empty, tools report empty results, not errors. If
an index is stale, it rebuilds. Missing data never crashes the server.
