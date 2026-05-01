# Contributing to ASD

## Branch Naming

Use conventional prefix and a short kebab-case description:

| Prefix      | When to use                               |
| ----------- | ----------------------------------------- |
| `feat/`     | New feature or enhancement                |
| `fix/`      | Bug fix                                   |
| `docs/`     | Documentation changes only                |
| `chore/`    | Maintenance, tooling, CI, dependencies    |
| `refactor/` | Code restructuring without feature change |
| `test/`     | Test additions or improvements            |

Examples: `feat/backlink-discovery`, `fix/ingest-empty-dir`, `docs/kb-schema-reference`.

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>
```

Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `style`.

Scopes: `ingest`, `compile`, `query`, `validate`, `kb`, `mcp`, `quality`, `docs`.

Examples:

- `feat(ingest): add mtime-fast-path for incremental ingestion`
- `fix(query): handle empty index gracefully`
- `docs(kb): add cross-reference discovery section`

Keep descriptions concise and imperative.

## PR Workflow

1. Create a feature branch from `main`

2. Implement with tests (150+ baseline, maintain or improve)

3. Run the local CI gate before pushing:

   ```bash
   uv run ruff check .
   uv run ruff format --check .
   uv run pytest -q
   uv run mdformat --check README.md docs/
   ```

4. Push and open a PR against `main`

5. Post the PR URL to the ADHD bus for review

6. Do not self-merge — wait for a supporter review

## Code Style

- Type hints on all public functions and classes
- Line length: 100 characters
- Use Pydantic for configuration and data models
- Tests use `pytest` (not `unittest`)
- Imports sorted via `ruff` (enforced in CI)
- No attribution of any kind in commits, PRs, comments, or docs

## KB Schema Conventions

- Frontmatter is mandatory for all KB articles — never create an article without it
- Types must be one of: `concept`, `mechanism`, `outcome`, `reference`, `connection`
- Always declare `sources` that track where the content originated
- Update `updated` date when modifying existing articles
- Run `asd_validate` before pushing changes to the KB

## Getting Help

Post questions to the ADHD bus with `type: question` and `topic: asd`. For schema or validation
questions, check `docs/architecture.md` first.
