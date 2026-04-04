# Installation

## Basic Install

```bash
pip install docglow
```

This installs the core package with all you need to generate and serve documentation sites.

## What's Included

The base install includes everything you need:

- Documentation site generation
- Interactive lineage explorer
- **Column-level lineage** (via sqlglot)
- Health scoring
- Full-text search
- AI chat panel (BYOK)

## Optional Extras

Some features require additional dependencies:

```bash
# Column profiling (connects to your database)
pip install "docglow[profiling]"

# Cloud publishing (push docs to Docglow Cloud)
pip install "docglow[cloud]"
```

## Requirements

- **Python 3.10+**
- A dbt project with compiled artifacts in `target/` (run `dbt compile` or `dbt run` first)
- See [Compatibility](../compatibility.md) for supported dbt versions and adapters

## Verify Installation

```bash
docglow --version
```
