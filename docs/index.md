# Docglow

**Next-generation documentation site generator for dbt Core projects.**

[Live Demo](https://demo.docglow.com){ .md-button .md-button--primary }
[GitHub](https://github.com/docglow/docglow){ .md-button }
[PyPI](https://pypi.org/project/docglow/){ .md-button }

---

Thousands of teams use dbt Core without access to dbt Cloud's documentation features. The built-in `dbt docs serve` generates a useful but dated static site with limited functionality that doesn't scale well.

Docglow replaces it with a **modern, interactive single-page application** — and it works with any dbt Core project out of the box.

!!! tip "Docglow Cloud (coming soon)"
    Hosted docs, AI-powered Q&A, Slack bot, and project health dashboards.
    Unlimited models, unlimited viewers.
    **[Join the waitlist →](https://docglow.com/#cloud)**

## Key Features

- **Interactive lineage explorer** — drag, filter, and trace upstream/downstream dependencies with configurable depth and layer visualization
- **Column-level lineage** — trace individual columns across models with transformation labels (direct, derived, aggregated)
- **Project health scoring** — coverage metrics for documentation, tests, naming conventions, complexity, and more
- **AI chat (BYOK)** — ask natural language questions about your project using your own Anthropic API key
- **Full-text search** — instant search across all models, sources, and columns
- **MCP server** — expose your dbt project to AI editors like Claude Code, Cursor, and Copilot
- **Single static site** — no backend required, deploy anywhere (S3, GitHub Pages, Netlify)
- **Dark mode** — auto, light, and dark themes

## Quick Install

```bash
pip install docglow
```

## Screenshots

**Lineage explorer** — layer-grouped DAG with upstream/downstream filtering

![Lineage explorer](https://raw.githubusercontent.com/docglow/docglow/main/.github/assets/lineage-view.png)

**Column-level lineage** — trace individual columns with transformation labels

![Column lineage](https://raw.githubusercontent.com/docglow/docglow/main/.github/assets/column-lineage-view.png)

**Column table** — types, descriptions, tests, and upstream/downstream dependencies

![Column table](https://raw.githubusercontent.com/docglow/docglow/main/.github/assets/columns-view.png)
