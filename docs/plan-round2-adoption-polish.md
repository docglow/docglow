# Plan: Round 2 — Adoption & Polish Tasks

Pre-implementation plan for 11 tasks focused on reducing friction for new users, enabling CI/CD workflows, and adding polish for community launch.

## Decisions Resolved

| # | Question | Answer |
|---|----------|--------|
| 1 | jaffle_shop artifacts source | Use existing repo at `dev/jaffle-shop/` — copy `target/` artifacts |
| 2 | Example directory structure | `examples/jaffle-shop/target/` (mimics dbt project layout) |
| 3 | Favicon asset | Brand logo provided — stacked orange diamond layers on dark navy circle. Small icon variant (no text) for favicon, full logo with "docglow" text available. |
| 4 | dbt version compatibility | Only tested with latest version. Document that and create issue for broader testing. |
| 5 | `generate --fail-under` | Only compute health when `--fail-under` flag is provided |

---

## Wave 1 — Core Infrastructure (parallel)

### Task 1: Live Demo Site with jaffle_shop
- **Complexity**: Medium
- **Source**: Copy artifacts from `dev/jaffle-shop/target/` (manifest.json, catalog.json, run_results.json)
- **Files to create**:
  - `examples/jaffle-shop/target/manifest.json`
  - `examples/jaffle-shop/target/catalog.json`
  - `examples/jaffle-shop/target/run_results.json`
  - `.github/workflows/demo-site.yml` — generate site + deploy to GitHub Pages
- **Files to modify**:
  - `README.md` — add Live Demo badge at top
- **Tests**: None (workflow is the integration test)

### Task 2: `--fail-under` and Exit Codes
- **Complexity**: Low-Medium
- **Files to modify**:
  - `src/docglow/cli.py` — add `--fail-under` option to `health` and `generate` commands
- **Files to create**:
  - `tests/test_cli_fail_under.py`
- **Implementation**:
  - `health --fail-under 80` → exit 1 if score < 80, exit 0 otherwise
  - `generate --fail-under 80` → generate site, then compute health score, exit 1 if below
  - Only compute health on `generate` when `--fail-under` is provided
  - Extract `_compute_health_score()` helper to avoid duplication
- **Tests**: TDD — fail-under triggers exit code 1, passes exit code 0, no flag = no check

### Task 5: Fix Missing Favicon
- **Complexity**: Low
- **Brand assets**: Stacked orange diamond layers icon (small variant without text for favicon)
- **Files to create**:
  - `frontend/public/favicon.svg` — SVG recreation of the small icon variant
- **Files to modify**:
  - `frontend/index.html` — replace `/vite.svg` reference with `/favicon.svg`
  - Rebuild frontend (`npm run build` in `frontend/`)
  - Copy built assets to `src/docglow/static/`
- **Tests**: None (visual asset)

---

## Wave 2 — Documentation & CLI Polish (parallel, after Wave 1)

### Task 7: Quickstart Tutorial in README (depends on Task 1)
- **Complexity**: Low
- **Files to modify**: `README.md`
- **Content**: "Try It in 60 Seconds" section using `examples/jaffle-shop`
- **Tests**: None

### Task 3: GitHub Actions Workflow Examples (partially depends on Task 2)
- **Complexity**: Low
- **Files to create**:
  - `docs/ci-examples/github-actions-s3.yml`
  - `docs/ci-examples/github-actions-pages.yml`
  - `docs/ci-examples/github-actions-health-check.yml` (references `--fail-under`)
- **Files to modify**: `README.md` — add CI/CD section
- **Tests**: None

### Task 4: `docglow init` Command
- **Complexity**: Low-Medium
- **Files to modify**: `src/docglow/cli.py` — add `init` command
- **Files to create**: `tests/test_cli_init.py`
- **Implementation**:
  - Generate commented `docglow.yml` with all config options documented
  - Refuse to overwrite existing file (unless `--force`)
  - Template mirrors `DocglowConfig` structure from `src/docglow/config.py`
- **Tests**: TDD — creates file, refuses overwrite, force overwrites, valid YAML output

### Task 8: Document `--static` Single-File Mode
- **Complexity**: Low
- **Files to modify**: `README.md`
- **Content**: Dedicated section explaining single-file mode use cases (email, Slack, Confluence, no-server)
- **Tests**: None

### Task 9: Document Theme Support
- **Complexity**: Low
- **Files to modify**: `README.md`
- **Content**: Theme info in features list, CLI flag and config examples
- **Tests**: None

---

## Wave 3 — Compatibility Docs & Future Issues (parallel, anytime)

### Task 6: dbt Version Compatibility Documentation
- **Complexity**: Low
- **Files to create**: `docs/compatibility.md`
- **Files to modify**: `README.md` — add compatibility note in Requirements
- **Content**: Only latest dbt version tested; adapter-agnostic (reads standard artifacts); create GitHub issue for broader version testing
- **Tests**: None

### Task 10: Seed `docglow diff` GitHub Issue
- **Complexity**: Low
- **Action**: Create GitHub issue with spec for comparing health scores between runs
- **Tests**: None

### Task 11: Seed Docker Image GitHub Issue
- **Complexity**: Low
- **Action**: Create GitHub issue with Dockerfile sketch
- **Tests**: None

---

## Execution Summary

```
Wave 1 (parallel):
  ├── Task 1: Demo site (copy artifacts from dev/jaffle-shop, CI workflow, README badge)
  ├── Task 2: --fail-under flag (cli.py + tests)
  └── Task 5: Favicon fix (SVG + frontend rebuild)

Wave 2 (parallel, after Wave 1):
  ├── Task 7: Quickstart tutorial (README, needs Task 1)
  ├── Task 3: CI workflow examples (docs, needs Task 2 for health-check)
  ├── Task 4: docglow init command (cli.py + tests)
  ├── Task 8: Document --static mode (README)
  └── Task 9: Document theme support (README)

Wave 3 (parallel, anytime):
  ├── Task 6: Compatibility docs
  ├── Task 10: docglow diff issue (GitHub)
  └── Task 11: Docker image issue (GitHub)
```

## Linear Issues

Create Linear issues (DOC-12 through DOC-22) for each task before implementation, then move to In Progress as work begins.

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| jaffle_shop artifacts may be large (manifest ~350KB+) | Medium | Minify JSON when copying |
| GitHub Pages deployment requires repo settings config | Low | Document in workflow comments |
| Frontend rebuild needed for favicon (requires Node.js) | Low | Already part of dev workflow |
| Only tested with latest dbt — compatibility claims must be conservative | Medium | Document honestly, create issue for broader testing |
