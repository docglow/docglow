# CLI Reference

## Commands

### `docglow generate`

Generate the documentation site from dbt artifacts.

```bash
docglow generate [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--project-dir` | `.` | Path to the dbt project root |
| `--target-dir` | `target/` | Path to the dbt target directory |
| `--output-dir` | `target/docglow/` | Where to write the generated site |
| `--static` | off | Bundle everything into a single `index.html` |
| `--theme` | `auto` | Theme: `auto`, `light`, or `dark` |
| `--title` | project name | Custom site title |
| `--select` | all | Only include models matching this pattern |
| `--exclude` | none | Exclude models matching this pattern |
| `--slim` | off | Omit raw/compiled SQL from output (reduces file size 40-60%) |
| `--ai` | off | Enable AI chat panel |
| `--ai-key` | env var | Anthropic API key (or set `ANTHROPIC_API_KEY`) |
| `--skip-column-lineage` | off | Skip column-level lineage analysis |
| `--column-lineage-select` | all | Only analyze column lineage for this model |
| `--column-lineage-depth` | unlimited | Max hops from the selected model |
| `--include-packages` | off | Include dbt package models in lineage |
| `--profile` | off | Enable column profiling |
| `--profile-adapter` | none | Database adapter (`duckdb`, `postgres`, `snowflake`) |
| `--profile-connection` | none | Connection string or DB path |
| `--profile-sample-size` | 10000 | Max rows to sample per model |
| `--profile-no-cache` | off | Skip profile caching |
| `--fail-under` | none | Exit code 1 if health score below threshold (0-100) |
| `--verbose` | off | Enable debug logging |

### `docglow serve`

Serve the generated site locally.

```bash
docglow serve [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--dir` | `target/docglow/` | Directory to serve |
| `--port` | `8081` | Port number |
| `--host` | `127.0.0.1` | Host address |
| `--open/--no-open` | open | Auto-open browser |
| `--watch` | off | Watch for artifact changes and auto-rebuild |
| `--project-dir` | `.` | dbt project root (for `--watch` mode) |

### `docglow health`

Show project health score and coverage metrics.

```bash
docglow health [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--project-dir` | `.` | Path to the dbt project root |
| `--target-dir` | `target/` | Path to the dbt target directory |
| `--format` | `table` | Output format: `table`, `json`, or `markdown` |
| `--select` | all | Only include matching models |
| `--fail-under` | none | Exit code 1 if score below threshold |

### `docglow mcp-server`

Start an MCP server for AI editor integration.

```bash
docglow mcp-server [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--project-dir` | `.` | Path to the dbt project root |
| `--target-dir` | `target/` | Path to the dbt target directory |

### `docglow init`

Generate a starter `docglow.yml` configuration file.

```bash
docglow init [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--project-dir` | `.` | Where to create `docglow.yml` |
| `--force` | off | Overwrite existing `docglow.yml` |

### `docglow profile`

Run column-level profiling only (without generating a site).

```bash
docglow profile [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--project-dir` | `.` | Path to the dbt project root |
| `--target-dir` | `target/` | Path to the dbt target directory |
| `--adapter` | required | Database adapter (`duckdb`, `postgres`, `snowflake`) |
| `--connection` | required | Connection string or path |
| `--sample-size` | 10000 | Max rows to sample per model |
| `--no-cache` | off | Skip profile caching |
| `--output` | `target/docglow/` | Output directory for `profiles.json` |
| `--verbose` | off | Enable debug logging |

### `docglow publish`

Publish documentation to Docglow Cloud.

```bash
docglow publish [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--token` | `DOCGLOW_TOKEN` env var | API token |
| `--project-dir` | `.` | Path to the dbt project root |
| `--target-dir` | `target/` | Path to the dbt target directory |
| `--no-wait` | off | Don't wait for processing to complete |
| `--verbose` | off | Enable debug logging |

### `docglow login`

Authenticate with Docglow Cloud.

```bash
docglow login [--token YOUR_TOKEN]
```

### `docglow logout`

Remove stored Docglow Cloud credentials.

```bash
docglow logout
```
