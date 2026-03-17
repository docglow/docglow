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

## Try It in 60 Seconds

```bash
pip install docglow
git clone https://github.com/docglow/docglow.git
cd docglow
docglow generate --project-dir examples/jaffle-shop --output-dir ./demo-site
docglow serve --dir ./demo-site
```

This uses the bundled [jaffle_shop](https://github.com/dbt-labs/jaffle-shop) example project with pre-built dbt artifacts.

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
- **Dark mode** — auto, light, and dark themes (follows system preference by default)

## CLI Commands

| Command | Description |
|---------|-------------|
| `docglow generate` | Generate the documentation site from dbt artifacts |
| `docglow serve` | Serve the generated site locally |
| `docglow health` | Show project health score and coverage metrics |
| `docglow init` | Generate a starter `docglow.yml` configuration file |
| `docglow profile` | Run column-level profiling (requires `docglow[profiling]`) |

## Single-File Mode

Generate a completely self-contained HTML file — no server needed:

```bash
docglow generate --project-dir /path/to/dbt --static
# Open target/docglow/index.html directly in your browser
```

The entire site (data, styles, JavaScript) is embedded in one file. Perfect for sharing via email, Slack, or committing to a repository.

## Configuration

Add a `docglow.yml` to your dbt project root for optional customization (layer definitions, display settings, etc.). Docglow works out of the box without any configuration — just point it at a dbt project with compiled artifacts in `target/`.

Generate a starter config with all options documented:

```bash
docglow init
```

### Theme

Docglow supports three themes: `auto` (follows system preference), `light`, and `dark`.

```bash
docglow generate --theme dark
```

Or in `docglow.yml`:

```yaml
theme: dark  # auto | light | dark
```

## CI/CD

Use Docglow as a CI quality gate with the `--fail-under` flag:

```yaml
# .github/workflows/docs.yml
- name: Check documentation health
  run: docglow health --project-dir . --fail-under 75

- name: Generate and deploy docs
  run: docglow generate --project-dir . --output-dir ./site
```

Ready-to-copy workflow files for [GitHub Pages](docs/ci-examples/github-actions-pages.yml), [S3](docs/ci-examples/github-actions-s3.yml), and [health checks](docs/ci-examples/github-actions-health-check.yml) are available in `docs/ci-examples/`.

### Pre-commit

Add Docglow's health check to your existing pre-commit workflow:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/docglow/docglow
    rev: v0.3.0
    hooks:
      - id: docglow-health
        args: ['--fail-under', '75']
```

## Requirements

- Python 3.10+
- A dbt project with `target/manifest.json` (run `dbt compile` or `dbt run` first)
- See [Compatibility](docs/compatibility.md) for supported dbt versions and adapters

## License

MIT
