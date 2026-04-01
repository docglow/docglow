# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.5.0] - 2026-03-31

### Added
- **Tag-based model filtering** — filter sidebar and lineage by model tags (DOC-83)
- **Column-name search** — search for column names across all models in the project (DOC-84)
- **`--slim` flag** — strip raw and compiled SQL from output to reduce file size (DOC-75)
- **Expanded SQL dialect support** — Athena, SQL Server, Oracle, Fabric, Starburst (DOC-74)
- **"Switching from dbt docs serve" migration guide** — feature comparison, step-by-step migration, CI examples (DOC-69)
- **CI/CD deployment guide** — comprehensive workflow examples for GitHub Pages, S3, and health checks (DOC-82)
- **Health scoring documentation** — explains all six dimensions, default weights, grade thresholds, and `docglow.yml` customization (DOC-65)
- **GitHub issue templates** — bug report and feature request templates (DOC-80)
- **dbt version test fixtures** — per-version fixtures for dbt 1.8 and 1.9 (DOC-81)
- **PyPI, stars, CI, and license badges** in README (DOC-61)
- **Live demo link and docglow.com homepage** in README and repo metadata (DOC-58, DOC-59)

### Fixed
- **Freshness score inflation** — no longer gives 100% when no sources are monitored; weight is redistributed to other dimensions (DOC-64)
- **Column lineage transformation types** — reclassified as passthrough, rename, aggregated, derived, unknown (DOC-76)
- Mypy type errors in freshness score refactor

### Improved
- **CLI extraction** — `cli.py` reduced from 774 to 60 lines; commands split into `src/docglow/commands/` (DOC-66)
- **Data transform split** — `generator/data.py` reduced from 766 to 295 lines; transform logic in `generator/transforms/` (DOC-67)
- **Generation pipeline** — `build_docglow_data` now executes 11 discrete, named stages via `generator/pipeline.py` (DOC-68)
- **Stale version references** audited and fixed (DOC-70)
- CHANGELOG linked from README (DOC-62)

## [0.4.1] - 2026-03-26

### Fixed
- Resolved mypy errors in freshness score refactor
- Badge rendering and freshness scoring bug fixes
- MCP hardening, cache location, and macro expansion fixes
- Pre-commit hook rev and init guard fixes

### Added
- Demo link, homepage URL, and changelog link in README hero
- Health scoring documentation
- Column insights — infer roles, semantic types, and descriptions
- `@docglow/shared-types` shared TypeScript package for frontend

### Improved
- Split `data.py` into focused modules for maintainability
- Consumed shared types in frontend, removed private docs

## [0.4.0] - 2026-03-24

### Added
- **MCP server** — `docglow mcp-server` command exposes dbt project data to AI editors (Claude Code, Cursor, Copilot) via Model Context Protocol. 9 tools: `list_models`, `get_model`, `get_source`, `get_lineage`, `get_health`, `find_undocumented`, `find_untested`, `search`, `get_column_info`. Stdio JSON-RPC 2.0, no external dependencies.
- **Incremental column lineage** — `--column-lineage-select fct_orders` analyzes only a model and its upstream/downstream subgraph. Supports `+name`/`name+` direction syntax and `--column-lineage-depth` for hop limits.
- **Lineage caching** — `.docglow-column-lineage-cache.json` keyed by SQL hash. Results accumulate across incremental runs.
- **Macro expander** — 12 common dbt macros (`surrogate_key`, `star`, `date_trunc`, `safe_cast`, type helpers, etc.) produce SQL approximations instead of NULL placeholders.
- **CTE column resolution** — models with `SELECT * FROM <cte>` and no catalog data now resolve columns from CTE definitions (fixes Dynamic Tables and uncompiled models).
- **Column backfill** — models with lineage but no catalog/manifest columns get synthetic column entries so the frontend can display them.
- **Unified lineage column** — single "Lineage" column in the column table with `←` upstream / `→` downstream directional arrows, replacing separate columns.
- **Click-through column navigation** — click a lineage badge to jump directly to that column in the target model with smooth scroll and highlight flash.
- **Column search in lineage graph** — search input in toolbar with dropdown results that highlight the full upstream+downstream path.
- **Edge transformation labels** — color-coded `direct`/`derived`/`aggregated` labels on column-level lineage graph edges.
- **Failure report** — `.docglow-column-lineage-failures.log` with per-model error details and common cause hints.
- **CONTRIBUTING.md** — local dev setup, architecture overview, testing, code style, how to add CLI commands and MCP tools.
- **Downstream column indicators** — ColumnTable shows which models consume each column.
- **README screenshots** — lineage explorer, column lineage, and columns table views with descriptive captions.

### Fixed
- `generate --fail-under` no longer reloads artifacts twice (returns health score from `generate_site()`)
- Snowflake variant access syntax (`obj:key::type`) no longer causes `OptimizeError` in column lineage
- Case-insensitive column matching for Snowflake uppercase column references in downstream lineage
- Postgres/Snowflake profiler connection params — accept DSN string directly
- CTE counting heuristic — require WITH keyword, avoid false matches on `CAST(x AS type)`
- Pre-commit hook threshold aligned to 75 (matches README)

### Improved
- React Flow controls visibility in dark mode (background + icon fill)
- Minimap viewport contrast (increased mask opacity, added border)
- Layer band labels readable — separated background opacity from label opacity
- Center-on-model button aligned with zoom controls
- dbt™ trademark attribution in README
- Replaced hardcoded `claude-sonnet-4-20250514` with `claude-sonnet-4` alias
- Removed unused `jinja2` from core dependencies
- Removed dead `try/except` for pyyaml import
- Column lineage capabilities and limitations documented in `docs/compatibility.md`

## [0.3.0] - 2026-03-16

### Added
- **Column-level lineage** — parse compiled SQL via sqlglot to trace column dependencies. Expandable DagNodes in the lineage graph with per-column click tracing and dashed amber edges. (`--column-lineage` flag, `pip install docglow[column-lineage]`)
- **`docglow init`** — generate a starter `docglow.yml` with all options documented
- **`docglow health --fail-under`** — CI quality gate, exit code 1 if score below threshold
- **`docglow health --format markdown`** — GitHub-flavored markdown output for PR comments
- **Package filtering** — dbt package models excluded from lineage by default (`--include-packages` to override)
- **Live demo site** — GitHub Pages deployment from jaffle_shop example project
- **Pre-commit hook** — `.pre-commit-hooks.yaml` for zero-friction CI integration
- **CI workflow examples** — ready-to-copy GitHub Actions for Pages, S3, and health checks
- **Graceful degradation** — `catalog.json` is now optional (warns, continues without column types)
- **Ref/source resolver** — `scripts/resolve_refs.py` for column lineage without compiled SQL

### Improved
- Actionable error message when `manifest.json` is missing
- API key security warning when `--ai` embeds key in generated site
- Custom favicon (stacked diamond layers brand icon)
- README: "Why Docglow?", "Try It in 60 Seconds", single-file mode, themes, CI/CD section
- dbt version compatibility documentation
- `SELECT * EXCLUDE(...)` support in column lineage parser (Snowflake)
- Thread-safe column trace timeouts (ThreadPoolExecutor instead of SIGALRM)
- Optimized DagNode Zustand selectors to prevent O(N) re-renders

### Fixed
- Static site `<script>` injection order (data before app JS)
- `re.sub` corrupting JSON newline escapes in static mode
- Preserved `type="module"` on inlined scripts for deferred execution
- CI lint errors and Click 8.1 compatibility

### Performance
- Column lineage: schema-first-then-fallback for better `SELECT *` expansion
- Skip models with unresolvable Jinja in column lineage analysis
- Package node filtering reduces lineage graph size for real projects

## [0.2.0] - 2026-03-12

### Changed
- Version is now dynamically sourced from `src/docglow/__init__.py` (single source of truth)

### Added
- CI workflow: lint, type check, and test matrix (Python 3.10–3.13)
- Publish workflow: automatic PyPI release via Trusted Publishers on GitHub Release

## [0.1.0] - 2026-03-12

### Added
- Initial release on PyPI
- dbt documentation site generator with React frontend
- Interactive lineage explorer (React Flow) with drag, zoom, fullscreen, and direction toggle
- Model detail panel with column docs, tests, and profiling stats
- Histogram visualizations for profiled columns
- Resizable sidebar with search and layer filtering
- Collapsible dependency sections and node detail panel
- Layer bands and draggable nodes in lineage view
- Bring Your Own Key (BYOK) support for AI-powered descriptions
- `--watch` mode for live regeneration during development
- Profiling integration with DuckDB
- CLI entry point (`docglow`)

### Performance
- Debounced hover and capped highlight depth in lineage explorer
- Suppressed hover highlights during node drag to prevent flicker
- Shared SVG markers to reduce DOM overhead

[Unreleased]: https://github.com/docglow/docglow/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/docglow/docglow/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/docglow/docglow/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/docglow/docglow/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/docglow/docglow/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/docglow/docglow/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/docglow/docglow/releases/tag/v0.1.0
