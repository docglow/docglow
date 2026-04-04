# Migrating from dbt docs serve

This guide walks you through replacing `dbt docs serve` with Docglow. The switch takes about five minutes and requires no changes to your dbt project.

## Feature comparison

| Feature | dbt docs serve | Docglow |
|---------|---------------|---------|
| Model and source documentation | Yes | Yes |
| Column descriptions and types | Yes | Yes |
| Interactive lineage graph | Basic (static DAG) | Drag, zoom, filter, depth control, layer bands |
| Column-level lineage | No | Yes (traces columns across models) |
| Full-text search | Basic | Instant search across models, sources, and columns |
| Project health scoring | No | Yes (coverage metrics for descriptions, tests, docs) |
| CI quality gate | No | `--fail-under` flag for CI pipelines |
| Dark mode | No | Auto, light, and dark themes |
| Single-file export | No | `--static` flag embeds everything in one HTML file |
| AI editor integration (MCP) | No | Claude Code, Cursor, Copilot via MCP server |
| Pre-commit hook | No | Built-in health check hook |
| Column profiling | No | Optional with DuckDB (`docglow[profiling]`) |
| Deployment options | Local only | Static site — deploy to S3, GitHub Pages, Netlify, etc. |
| Requires dbt Cloud | No | No |
| Cost | Free | Free (MIT license) |

## Step-by-step migration

### 1. Install Docglow

```bash
pip install docglow
```

Column-level lineage is included out of the box. For column profiling, install the extra:

```bash
pip install "docglow[profiling]"        # column profiling via DuckDB
```

### 2. Generate the documentation site

You still run `dbt compile` (or `dbt run` / `dbt build`) as before to produce `target/manifest.json` and `target/catalog.json`. Then replace `dbt docs generate && dbt docs serve` with:

```bash
docglow generate --project-dir /path/to/dbt/project --output-dir ./site
docglow serve --dir ./site
```

The `--project-dir` flag should point to your dbt project root (the directory containing `dbt_project.yml`). Docglow reads the `target/` subdirectory automatically.

### 3. Column-level lineage (enabled by default)

Column-level lineage runs automatically. It parses compiled SQL via sqlglot to trace column dependencies across models. Results are cached in `.docglow-column-lineage-cache.json` for fast incremental rebuilds.

To skip column lineage analysis (e.g. for faster iteration), use:

```bash
docglow generate --project-dir . --output-dir ./site --skip-column-lineage
```

Or set `column_lineage: false` in your `docglow.yml`.

### 4. Optional: generate a self-contained file

```bash
docglow generate --project-dir . --output-dir ./site --static
```

The output is a single `index.html` with all data, styles, and JavaScript embedded. Share it via Slack, email, or commit it to your repo.

## CI pipeline changes

### Before (dbt docs)

Most teams using `dbt docs serve` don't have automated doc deployment. If you do, it typically looks like this:

```yaml
# .github/workflows/docs.yml
name: Deploy dbt docs
on:
  push:
    branches: [main]

jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dbt
        run: pip install dbt-core dbt-postgres  # your adapter

      - name: Generate docs
        run: |
          dbt deps
          dbt compile
          dbt docs generate

      # Manual upload of target/ directory to hosting
```

### After (Docglow)

```yaml
# .github/workflows/docs.yml
name: Deploy Docglow site
on:
  push:
    branches: [main]

jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dbt and Docglow
        run: pip install dbt-core dbt-postgres docglow

      - name: Compile dbt project
        run: |
          dbt deps
          dbt compile

      - name: Check documentation health
        run: docglow health --project-dir . --fail-under 75

      - name: Generate Docglow site
        run: docglow generate --project-dir . --output-dir ./site

      - name: Deploy to GitHub Pages
        uses: actions/upload-pages-artifact@v3
        with:
          path: ./site
```

See `docs/ci-examples/` for ready-to-copy workflows for GitHub Pages, S3, and health-check-only pipelines.

### Pre-commit hook

Add a documentation health gate that runs on every commit:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/docglow/docglow
    rev: v0.4.1
    hooks:
      - id: docglow-health
        args: ['--fail-under', '75']
```

## FAQ

**Do I need to change my dbt project at all?**
No. Docglow reads the same `manifest.json` and `catalog.json` that `dbt docs generate` produces. Keep running `dbt compile` or `dbt build` as you normally do.

**Does Docglow replace `dbt docs generate`?**
Not exactly. You still need dbt to compile your project and produce artifacts in `target/`. Docglow replaces the *site generation and serving* step (`dbt docs generate` + `dbt docs serve`).

**Can I use Docglow without `catalog.json`?**
Yes. If `catalog.json` is missing, Docglow warns and continues without column type information. Run `dbt docs generate` (which produces the catalog) if you want full column metadata.

**What dbt versions are supported?**
Docglow supports dbt Core 1.0 through 1.9. See [compatibility.md](compatibility.md) for detailed adapter and version support.

**Can I run both dbt docs and Docglow side by side?**
Yes. Docglow generates its output in a separate directory (`--output-dir`) and doesn't modify your dbt `target/` folder. You can run both and compare.

**Does the generated site need a backend?**
No. The output is a static site (HTML, CSS, JS) with all data embedded. Host it anywhere that serves static files.

**How do I add custom branding or configuration?**
Run `docglow init` to generate a starter `docglow.yml` with all available options documented (layer definitions, themes, display settings).

**What if my project uses packages (e.g., dbt_utils)?**
Package models are excluded from the lineage graph by default to reduce noise. Use `--include-packages` if you want to see them.
