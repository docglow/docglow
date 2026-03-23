# Contributing to Docglow

Thanks for your interest in contributing to docglow! This guide covers everything you need to get set up and start contributing.

## Local Dev Setup

### Prerequisites

- **Python 3.10+**
- **Node 18+** and npm
- A dbt project with compiled artifacts (or use the included `examples/jaffle-shop`)

### Python Environment

```bash
# Clone the repo
git clone https://github.com/docglow/docglow.git
cd docglow

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with all dev extras
pip install -e ".[dev,column-lineage,profiling,ai,cloud]"

# Install pre-commit hooks
pre-commit install
```

### Frontend

```bash
cd frontend
npm install
npm run build    # Production build (output to frontend/dist/)
npm run dev      # Vite dev server with hot reload
cd ..
```

### Verify Everything Works

```bash
# Run tests
pytest

# Lint + type check
ruff check src/
mypy src/

# Generate a site from the example project
docglow generate --project-dir examples/jaffle-shop
docglow serve
```

## Project Architecture

### Data Pipeline

```
dbt project (target/)
    |
    v
[Artifact Loading] artifacts/loader.py
    Reads manifest.json, catalog.json, run_results.json, sources.json
    Returns: LoadedArtifacts dataclass
    |
    v
[Data Transformation] generator/data.py
    Transforms raw artifacts into the unified DocglowData payload:
    - Models, sources, seeds, snapshots, exposures, metrics
    - Health scores (analyzer/)
    - Column-level lineage (lineage/)
    - Column profiling (profiler/)
    - Search index
    - AI context
    Returns: dict suitable for JSON serialization
    |
    v
[Bundling] generator/bundle.py
    Copies frontend assets + writes docglow-data.json
    OR embeds everything into a single index.html (--static mode)
    |
    v
[Frontend] frontend/src/
    React SPA loads docglow-data.json into a Zustand store
    Renders models, lineage graphs, health scores, search
```

### Key Source Directories

```
src/docglow/
  artifacts/      Pydantic models for dbt manifest, catalog, run_results
  analyzer/       Health scoring: coverage, naming, complexity, orphans
  generator/      Site generation pipeline: data transformation + bundling
  lineage/        Column-level lineage: sqlglot parsing, macro expansion, caching
  profiler/       Column profiling: duckdb/postgres/snowflake stats
  server/         Dev server + file watcher for auto-rebuild
  cloud/          docglow.dev publishing client
  mcp/            MCP server for AI editor integration
  ai/             AI chat context building
  cli.py          Click CLI entry point (all commands)
  config.py       docglow.yml schema and loading

frontend/src/
  components/     React components (lineage graph, column table, health, etc.)
  pages/          Page containers (ModelPage, LineagePage, HealthPage)
  stores/         Zustand state management
  utils/          Graph layout, search, column lineage tracing
  types/          TypeScript interfaces matching the backend JSON schema
```

## Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=term-missing

# Specific test file
pytest tests/test_health.py

# Only unit tests
pytest -m unit

# Only lineage tests
pytest tests/lineage/

# Frontend E2E tests (requires built frontend + running server)
cd frontend && npm run test:e2e
```

Test fixtures live in `tests/fixtures/` and contain Jaffle Shop dbt artifacts. The `conftest.py` provides path fixtures for these.

## Building the Frontend

```bash
cd frontend

# Development with hot reload
npm run dev

# Production build
npm run build

# Type check only
npx tsc --noEmit

# Lint
npm run lint
```

After building, the output in `frontend/dist/` is picked up automatically by the Python bundler during `docglow generate` in development mode. For installed packages, assets are stored in `src/docglow/static/`.

## Code Style

### Python

- **Formatter/linter**: ruff (auto-runs via pre-commit hooks)
- **Type checking**: mypy with `strict = true`
- **Line length**: 100 characters
- **Python target**: 3.10+
- **Frozen dataclasses** for all data containers
- **Type annotations** on all function signatures

```bash
ruff check src/          # Lint
ruff format src/         # Format
mypy src/                # Type check
```

### TypeScript

- React + TypeScript with strict mode
- Tailwind CSS for styling
- Zustand for state management
- No `console.log` in production code

### Pre-commit Hooks

The repo has pre-commit hooks that run automatically on `git commit`:
- `ruff` — lint with auto-fix
- `ruff-format` — auto-format

Install them with `pre-commit install` after cloning.

## How to Add a New CLI Command

All CLI commands follow the same pattern in `src/docglow/cli.py`:

```python
@cli.command()
@click.option("--project-dir", type=click.Path(exists=True, path_type=Path), default=".")
@click.option("--verbose", is_flag=True)
def my_command(project_dir: Path, verbose: bool) -> None:
    """Short description shown in --help."""
    _setup_logging(verbose)

    # Lazy-import heavy dependencies to keep CLI startup fast
    from docglow.artifacts.loader import load_artifacts

    try:
        artifacts = load_artifacts(project_dir)
        # ... command logic
    except ArtifactLoadError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(1) from e
```

Key conventions:
- Use `click.Path(path_type=Path)` for path arguments
- Lazy-import modules inside the function body (keeps `docglow --help` fast)
- Use `console.print()` (Rich) for user-facing output
- Use `logger.info/warning` for verbose diagnostic output
- Handle errors with clear messages and `SystemExit(1)`

## How to Add an MCP Tool

MCP tools are defined in `src/docglow/mcp/tools.py`. Each tool is a pure function that queries the in-memory docglow data:

```python
def _my_tool(data: dict[str, Any], params: dict[str, Any]) -> Any:
    """Tool implementation — receives the full docglow data payload and params."""
    name = params.get("name", "")
    # ... query data and return results
    return {"result": "..."}

# Register in the TOOLS list at the bottom of the file:
ToolDefinition(
    name="my_tool",
    description="What this tool does",
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "..."},
        },
    },
    handler=_my_tool,
),
```

## PR Guidelines

- Use [conventional commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`
- Link related issues in the PR description
- Ensure `pytest`, `ruff check`, and `mypy` pass before submitting
- Add tests for new functionality
- Keep PRs focused — one feature or fix per PR

## Questions?

Open an issue at [github.com/docglow/docglow/issues](https://github.com/docglow/docglow/issues) or start a discussion.
