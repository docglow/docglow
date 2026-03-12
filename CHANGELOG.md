# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/docglow/docglow/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/docglow/docglow/releases/tag/v0.1.0
