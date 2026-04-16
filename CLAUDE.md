# CLAUDE.md — Docglow

## Project

Docglow is a next-generation documentation site generator for dbt Core projects. It replaces `dbt docs serve` with a modern React SPA featuring interactive lineage, column-level lineage, health scoring, AI chat, and full-text search.

- **OSS CLI** — `pip install docglow` — generates static sites from dbt artifacts
- **Cloud tier** (coming soon) — hosted docs, AI Q&A, Slack bot at docglow.com
- **License** — MIT

## Tech Stack

**Python backend** (CLI + site generation):
- Python 3.10+ with type annotations on all functions
- Click for CLI, Pydantic-style frozen dataclasses for config
- SQLGlot for SQL parsing and column lineage
- Rich for terminal output
- Formatting: ruff + ruff-format. Linting: ruff. Types: mypy

**React frontend** (the generated SPA):
- React 19, TypeScript, Vite, Tailwind CSS v4
- Zustand for state management
- MiniSearch for full-text search (two-tier: resources + columns)
- React Flow (@xyflow/react) for lineage visualization
- Recharts for health score charts
- Playwright for E2E tests, Vitest for unit tests

**Shared types**: `packages/shared-types/` — published to npm as `@docglow/shared-types`

## Build & Test

```bash
# Python
pip install -e ".[dev,column-lineage]"
pytest                          # run all tests (524+)
pytest --cov=docglow            # with coverage
ruff check src/ tests/          # lint
ruff format src/ tests/         # format
mypy src/docglow                # type check

# Frontend
cd frontend
npm ci
npm run build                   # tsc -b && vite build
npm run sync-static             # copy dist/ → ../src/docglow/static/ (needed before local docglow generate)
npm run build:sync              # build + sync-static in one step
npm run test                    # vitest
npm run test:e2e                # playwright

# Generate a site (quick test)
docglow generate --project-dir examples/jaffle-shop --static
```

## Project Structure

```
src/docglow/
├── cli.py                  # CLI entry point
├── config.py               # docglow.yml schema (frozen dataclasses)
├── commands/               # Click commands (generate, serve, publish, etc.)
├── artifacts/              # dbt manifest/catalog/run_results loader
├── generator/
│   ├── pipeline.py         # PipelineContext + ordered stages
│   ├── data.py             # Build DocglowData payload
│   ├── bundle.py           # HTML bundling (static + separate modes)
│   ├── search_index.py     # MiniSearch index builder
│   └── transforms/         # Per-node-type transformers
├── lineage/
│   ├── analyzer.py         # Column lineage orchestrator (parallel ProcessPoolExecutor)
│   ├── column_parser.py    # SQLGlot-based column tracing
│   ├── table_resolver.py   # Map SQL table refs → dbt unique_ids
│   └── macro_expander.py   # Jinja macro → SQL expansion
├── analyzer/               # Health scoring
├── profiler/               # Column profiling (DuckDB/Postgres/Snowflake)
├── insights/               # Column description inference
├── cloud/                  # Cloud API client (publish, auth)
├── ai/                     # AI chat context builder
├── mcp/                    # MCP server for AI editors
└── static/                 # Pre-built frontend assets (copied during install)

frontend/src/
├── App.tsx                 # Root component, data loading
├── stores/                 # Zustand stores (project, search, settings)
├── components/             # React components (layout, search, lineage, health)
├── pages/                  # Route pages (model detail, lineage, health, search)
├── types/                  # TypeScript types + shared-types augmentation
└── utils/                  # Helpers
```

## Git & Branching

- **Identity**: Use `cplax14@gmail.com` for commits (not josh@casechrono.com)
- **Always cut a feature branch** before making any code changes — never commit directly to main
- **Branch naming**: `cplax14/doc-{issue}-short-description` (matches Linear's suggested branch name)
- **Commit style**: Conventional commits — `feat:`, `fix:`, `perf:`, `refactor:`, `chore:`, `docs:`, `test:`
- **Wait for CI to pass** before merging PRs
- **Never auto-push** — only push when explicitly asked

## CI/CD

- **CI** (`ci.yml`): ruff lint, ruff format, mypy, pytest across Python 3.10-3.13
- **Demo site** (`demo-site.yml`): builds frontend, generates site from jaffle-shop, deploys to Cloudflare Pages (demo.docglow.com)
- **Docs** (`docs.yml`): MkDocs Material → GitHub Pages (docs.docglow.com)
- **PyPI** (`publish.yml`): triggered by version tags

## Issue Tracking

- **Linear** — project "Docglow", team ID `0489f9e3-e966-4210-a253-2e4e61dbab9b`, prefix `DOC-`
- **GitHub Issues** — for public bug reports and feature requests
- When replying to GitHub issues, **draft the reply for the user to post** — never auto-post comments

## Deployment

- **demo.docglow.com** — Cloudflare Pages (static site generated from jaffle-shop example)
- **docs.docglow.com** — GitHub Pages (MkDocs Material)
- **docglow.com** — Vercel (static landing page, separate `www` repo)
- **PostHog analytics** on demo site via `--head-script` flag and `POSTHOG_API_KEY` secret

## Versioning & Releases

- Version lives in `src/docglow/__init__.py` (`__version__ = "X.Y.Z"`)
- Update `CHANGELOG.md` with every release
- Tag format: `v0.6.1`
- Version bumps and changelog updates should come through PRs, not direct to main
- Create GitHub release after tagging: `gh release create vX.Y.Z`

## Key Patterns

- **Frozen dataclasses** for config and result types (immutability)
- **Pipeline stages** — site generation runs through `PipelineContext` with ordered named stages
- **ProcessPoolExecutor** for column lineage parallelism (bypasses GIL for CPU-bound SQLGlot work)
- **Two-tier search** — MiniSearch resource index searched first, column index only when results are sparse
- **`--head-script`** flag injects arbitrary HTML into `<head>` (analytics, etc.)
- **Cache files** — column lineage cache (`.docglow-column-lineage-cache.json`) keyed by SQL hash + docglow version

## Testing

- Python: pytest with fixtures in `tests/fixtures/` (jaffle-shop dbt artifacts)
- Frontend: Vitest for unit tests, Playwright for E2E
- Always run `pytest` after Python changes, `tsc --noEmit` after frontend changes
- Benchmark scripts in `scripts/` for performance-sensitive code (column lineage, search)
