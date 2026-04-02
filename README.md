<p align="center">
  <img src="https://raw.githubusercontent.com/docglow/docglow/main/.github/assets/docglow-logo.png" alt="Docglow" width="160" />
</p>

<h1 align="center">docglow</h1>

<p align="center">
  Next-generation documentation site generator for <a href="https://github.com/dbt-labs/dbt-core">dbt™ Core</a> projects.
</p>

<p align="center">
  <a href="https://docglow.github.io/docglow/"><strong>Live Demo</strong></a> · <a href="https://docglow.com">Website</a> · <a href="https://pypi.org/project/docglow/">PyPI</a> · <a href="CHANGELOG.md">Changelog</a>
</p>

<p align="center">
  <a href="https://pypi.org/project/docglow/"><img src="https://img.shields.io/pypi/v/docglow" alt="PyPI version"></a>
  <a href="https://pypi.org/project/docglow/"><img src="https://img.shields.io/pypi/dm/docglow" alt="PyPI downloads"></a>
  <a href="https://github.com/docglow/docglow"><img src="https://img.shields.io/github/stars/docglow/docglow?style=social" alt="GitHub stars"></a>
  <a href="https://github.com/docglow/docglow/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/docglow/docglow/ci.yml?label=CI" alt="CI status"></a>
  <a href="https://github.com/docglow/docglow/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/docglow" alt="License"></a>
</p>

## Why Docglow?

Thousands of teams use dbt Core without access to dbt Cloud's documentation features. The built-in `dbt docs generate && dbt docs serve` generates a useful, but somewhat dated static site, with limited functionality that doesn't scale well.

Docglow replaces it with a **modern, interactive single-page application** — and it works with any dbt Core project out of the box.

- **No dbt Cloud required** — generate and serve docs locally or deploy anywhere
- **Unlimited models, unlimited viewers** — no seat caps, no model limits
- **Zero configuration** — just point it at a dbt project with compiled artifacts and go
- **Interactive lineage explorer** — drag, filter, and trace upstream/downstream dependencies visually
- **Project health scoring** — get a coverage report for descriptions, tests, and documentation completeness

Switching from `dbt docs serve`? See the [migration guide](docs/migrating-from-dbt-docs.md) for a side-by-side comparison and step-by-step instructions.

**Interactive lineage explorer** — layer-grouped DAG with upstream/downstream filtering, depth control, and folder grouping

![Lineage explorer with layer bands](https://raw.githubusercontent.com/docglow/docglow/main/.github/assets/lineage-view.png)

**Column-level lineage** — expand nodes to trace individual columns across models with transformation labels (direct, derived, aggregated)

![Column-level lineage tracing](https://raw.githubusercontent.com/docglow/docglow/main/.github/assets/column-lineage-view.png)

**Column table with lineage** — view types, descriptions, tests, and upstream/downstream dependencies for every column. Click a lineage badge to jump directly to that column in the linked model.

![Column table with upstream and downstream lineage](https://raw.githubusercontent.com/docglow/docglow/main/.github/assets/columns-view.png)

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
- **Project health score** — coverage metrics for descriptions, tests, and documentation completeness ([details](docs/health-scoring.md))
- **Full-text search** — instant search across all models, sources, and columns
- **Single static site** — no backend required, deploy anywhere (S3, GitHub Pages, Netlify, etc.)
- **AI chat (BYOK)** — ask natural language questions about your project using your own Anthropic API key
- **Dark mode** — auto, light, and dark themes (follows system preference by default)

## CLI Commands

| Command | Description |
|---------|-------------|
| `docglow generate` | Generate the documentation site from dbt artifacts |
| `docglow serve` | Serve the generated site locally |
| `docglow health` | Show project health score and coverage metrics |
| `docglow mcp-server` | Start MCP server for AI editor integration |
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

## AI Chat (Bring Your Own Key)

Docglow includes a built-in AI chat panel powered by Claude. Ask natural language questions about your dbt project and get answers grounded in your actual metadata — models, columns, lineage, tests, and health scores.

**Enable it:**

```bash
# Option 1: Pass your key as a flag (for local use only)
docglow generate --ai --ai-key sk-ant-...

# Option 2: Set the environment variable
export ANTHROPIC_API_KEY=sk-ant-...
docglow generate --ai

# Option 3: Enable in docglow.yml
# ai:
#   enabled: true
```

Open the chat panel with `Ctrl+J` (or click the chat icon in the header), enter your Anthropic API key, and start asking questions.

**Example questions:**

| Question | What it does |
|----------|-------------|
| *What models depend on the orders source?* | Traces the lineage graph to find all downstream consumers |
| *Which columns might contain PII?* | Scans column names and descriptions for personally identifiable information |
| *What would break if I changed stg_customers?* | Lists all downstream models that depend on `stg_customers` |
| *Show me all models related to revenue* | Searches model names, descriptions, and tags for revenue-related content |
| *Which models have the most failing tests?* | Cross-references test results with model metadata |
| *What's the overall health of this project?* | Summarizes the health score breakdown across all six dimensions |
| *Explain what dim_employee does* | Describes the model using its SQL, columns, upstream dependencies, and description |
| *What's the difference between stg_orders and fct_orders?* | Compares two models side-by-side using their metadata |

**How it works:** When you generate with `--ai`, Docglow builds a compact project context (model names, descriptions, columns, lineage, test status, health scores) and embeds it in the site. The chat panel sends this context as a system prompt to the Anthropic API along with your question. Responses stream back in real-time with clickable model references.

**Security note:** The `--ai` flag embeds your API key in the generated site files. This is safe for local use (`docglow serve`) but **do not deploy AI-enabled sites publicly**. For hosted docs with secure AI features, use [Docglow Cloud](https://docglow.com) (coming soon).

**Limits:** 20 requests per session (clear chat to reset). Uses Claude Sonnet 4 with streaming.

## AI Editor Integration (MCP)

Docglow includes a [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes your dbt project to AI editors like Claude Code, Cursor, and Copilot.

Add to your editor's MCP config (e.g. `~/.claude.json`):

```json
{
  "mcpServers": {
    "docglow": {
      "command": "docglow",
      "args": ["mcp-server", "--project-dir", "/path/to/dbt/project"]
    }
  }
}
```

The server provides 9 tools: model/source lookup, lineage traversal, health scores, undocumented/untested discovery, cross-model column search, and full-text search. No API keys or network access required — it runs locally over stdio.

## CI/CD Deployment

Use Docglow as a CI quality gate with the `--fail-under` flag:

```yaml
# .github/workflows/docs.yml
- name: Check documentation health
  run: docglow health --project-dir . --fail-under 75

- name: Generate and deploy docs
  run: docglow generate --project-dir . --output-dir ./site
```

For large projects, add `--slim` to strip SQL source from the output and reduce payload size by 40–60%.

See the **[CI/CD Deployment Guide](docs/ci-cd-guide.md)** for complete walkthroughs covering GitHub Pages, S3, GitLab CI, health score thresholds, and enterprise private Pages.

Ready-to-copy workflow files: [GitHub Pages](docs/examples/docglow-pages.yml) (recommended), [S3](docs/ci-examples/github-actions-s3.yml), and [PR health check](docs/ci-examples/github-actions-health-check.yml).

### Pre-commit

Add Docglow's health check to your existing pre-commit workflow:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/docglow/docglow
    rev: v0.5.1
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

---

*dbt is a trademark of dbt Labs, Inc. Docglow is not affiliated with or endorsed by dbt Labs.*
