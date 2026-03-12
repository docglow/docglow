# docglow

Next-generation documentation site generator for [dbt Core](https://github.com/dbt-labs/dbt-core) projects.

Docglow replaces the default `dbt docs serve` workflow with a modern, interactive single-page application featuring lineage exploration, documentation serving, and project health scoring.

## Install

```bash
pip install docglow
```

## Quick Start

```bash
# Generate the site from your dbt project
docglow generate --project-dir /path/to/dbt/project --output-dir ./site

# Serve locally
docglow serve --dir ./site
```

## Features

- **Interactive lineage explorer** — drag, filter, and explore upstream/downstream dependencies with configurable depth and layer visualization
- **Column-level documentation** — searchable column tables with descriptions, types, and test status
- **Project health score** — coverage metrics for descriptions, tests, and documentation completeness
- **Full-text search** — instant search across all models, sources, and columns
- **Single static site** — no backend required, deploy anywhere (S3, GitHub Pages, Netlify, etc.)

## CLI Commands

| Command | Description |
|---------|-------------|
| `docglow generate` | Generate the documentation site from dbt artifacts |
| `docglow serve` | Serve the generated site locally |
| `docglow health` | Show project health score and coverage metrics |
| `docglow profile` | Run column-level profiling (requires `docglow[profiling]`) |

## Configuration

Add a `docglow.yml` to your dbt project root for optional customization (layer definitions, display settings, etc.). Docglow works out of the box without any configuration — just point it at a dbt project with compiled artifacts in `target/`.

## Requirements

- Python 3.10+
- A dbt project with `target/manifest.json` (run `dbt compile` or `dbt run` first)

## License

MIT
