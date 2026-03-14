# docglow

Next-generation documentation site generator for [dbt Core](https://github.com/dbt-labs/dbt-core) projects.

## Why Docglow?

Over **60,000 teams** use dbt Core without access to dbt Cloud's documentation features. The built-in `dbt docs serve` generates a dated, hard-to-navigate static site that doesn't scale.

Docglow replaces it with a **modern, interactive single-page application** — and it works with any dbt Core project out of the box.

- **No dbt Cloud required** — generate and serve docs locally or deploy anywhere
- **Unlimited models, unlimited viewers** — no seat caps, no model limits (unlike hosted alternatives like Tributary Docs)
- **Zero configuration** — just point it at a dbt project with compiled artifacts and go
- **Interactive lineage explorer** — drag, filter, and trace upstream/downstream dependencies visually
- **Project health scoring** — get a coverage report for descriptions, tests, and documentation completeness

<!-- TODO: Add screenshot or GIF of lineage explorer here -->
<!-- Place image assets in docs/images/ -->

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
