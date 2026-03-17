# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/docglow/docglow/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/docglow/docglow/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/docglow/docglow/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/docglow/docglow/releases/tag/v0.1.0
