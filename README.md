# behave-asd

**Autism Spectrum Driver** — systematizing memory layer for the BrainXio stack.

ASD turns raw, messy, contradictory inputs into clean, versioned, interconnected,
queryable knowledge artifacts that serve as the Single Source of Truth.

## Installation

```bash
uv sync
uv pip install -e ".[dev]"
```

## Usage

ASD exposes an MCP server (`asd-mcp`) with these tools:

| Tool | Description |
|------|-------------|
| `asd_ingest` | Raw markdown -> processed artifacts |
| `asd_compile` | Full knowledge base compilation |
| `asd_query` | Semantic/structured lookup |
| `asd_validate` | Consistency and standards checks |
| `asd_status` | KB health report |

```bash
uv run asd-mcp
```

## Configuration

Set `ASD_PROJECT_ROOT` to specify the project root (defaults to CWD).
Set `ASD_KB_DIR` to override the knowledge base directory (defaults to `USER/kb/`).

## Development

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```
