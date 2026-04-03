# Installation

## Basic Install

```bash
pip install docglow
```

This installs the core package with all you need to generate and serve documentation sites.

## Optional Extras

Docglow has optional dependencies for advanced features:

```bash
# Column-level lineage (parses SQL with sqlglot)
pip install "docglow[column-lineage]"

# Column profiling (connects to your database)
pip install "docglow[profiling]"

# Cloud publishing (push docs to Docglow Cloud)
pip install "docglow[cloud]"

# Everything
pip install "docglow[column-lineage,profiling,cloud]"
```

## Requirements

- **Python 3.10+**
- A dbt project with compiled artifacts in `target/` (run `dbt compile` or `dbt run` first)
- See [Compatibility](../compatibility.md) for supported dbt versions and adapters

## Verify Installation

```bash
docglow --version
```
