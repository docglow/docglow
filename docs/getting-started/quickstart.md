# Quick Start

## Try It in 60 Seconds

```bash
pip install docglow
git clone https://github.com/docglow/docglow.git
cd docglow
docglow generate --project-dir examples/jaffle-shop --output-dir ./demo-site
docglow serve --dir ./demo-site
```

This uses the bundled [jaffle_shop](https://github.com/dbt-labs/jaffle-shop) example project with pre-built dbt artifacts.

## With Your Own Project

```bash
# 1. Generate the site from your dbt project
docglow generate --project-dir /path/to/dbt/project

# 2. Serve locally
docglow serve
```

Docglow reads `target/manifest.json` and `target/catalog.json` from your dbt project. Make sure you've run `dbt compile` (or `dbt run` / `dbt build`) first.

## Single-File Mode

Generate a completely self-contained HTML file — no server needed:

```bash
docglow generate --project-dir /path/to/dbt --static
# Open target/docglow/index.html directly in your browser
```

The entire site (data, styles, JavaScript) is embedded in one file. Perfect for sharing via email, Slack, or committing to a repository.

## What's Next?

- [Configuration](../configuration.md) — customize themes, health weights, and lineage layers
- [Column-Level Lineage](../column-lineage.md) — trace column dependencies across models
- [Health Scoring](../health-scoring.md) — understand your project's documentation quality
- [CI/CD Deployment](../ci-cd-guide.md) — deploy docs automatically from your pipeline
