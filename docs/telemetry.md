# Telemetry

Docglow can send fully anonymous, opt-in telemetry to help us understand which dbt adapters are in use and roughly how big real-world projects are. Telemetry is **off by default** and will not send a single byte until you explicitly enable it.

This page is the canonical reference for what we collect, why, and how to control it.

## Principles

- **Opt-in only.** Default off. We never quietly turn it on.
- **Anonymous.** No model names, column names, SQL, file paths, project names, credentials, or anything else that could identify you.
- **Transparent.** This page lists the exact payload. The implementation lives in [`src/docglow/telemetry/`](https://github.com/docglow/docglow/tree/main/src/docglow/telemetry).
- **Easy to turn off.** A single env var, a config flag, or `docglow telemetry disable`. All three work.
- **Never breaks your build.** All network and I/O is wrapped to swallow failures. Telemetry can never make `docglow generate` slower than a few milliseconds, hang, or exit non-zero.

## What we collect

When telemetry is enabled, every successful `docglow generate`, `docglow health`, and `docglow serve` startup sends one event with these fields:

```json
{
  "schema_version": 1,
  "instance_id": "5c5a6a39-54bb-4e98-8f3e-5a02e7d7c90e",
  "command": "generate",
  "result": "success",
  "duration_ms": 4218,
  "docglow_version": "0.7.4",
  "python_version": "3.12.2",
  "platform": "linux",
  "adapter_type": "snowflake",
  "project_shape": {
    "models": 142,
    "sources": 31,
    "seeds": 4,
    "tests": 213,
    "macros": 8
  },
  "features_used": ["column_lineage", "static"]
}
```

| Field | Why we want it |
| --- | --- |
| `schema_version` | Lets us evolve the payload without breaking older CLIs. |
| `instance_id` | A random UUID4 generated once per machine when you opt in. Lets us count distinct installs without identifying anyone. |
| `command` | One of `generate`, `health`, `serve`. Tells us which workflows people actually use. |
| `result` | `success` or `error`. Tells us if a feature is broken in the wild. |
| `duration_ms` | Performance signal — is `generate` getting slower as we add features? |
| `docglow_version` | Helps us know how fast users upgrade and whether old versions still need support. |
| `python_version` / `platform` | Tells us when we can drop a Python version or stop testing a platform. |
| `adapter_type` | The single most useful field — tells us which dbt adapters to prioritise (Snowflake vs BigQuery vs DuckDB vs Postgres etc). |
| `project_shape` | Counts only. Lets us understand what "typical" looks like and where to optimise. |
| `features_used` | Boolean flags only (e.g. `column_lineage`, `static`, `slim`). Tells us which features are loved and which are dead. |

## What we never collect

- Model names, column names, source names, macro names
- SQL — neither raw nor compiled
- File paths or directory structure
- Project names, profile names, schema names
- API keys, tokens, or credentials of any kind
- IP addresses, MAC addresses, hostnames, or anything geolocatable
- Manifest contents, catalog contents, or run results contents

If we ever add a field, it ships in a new `schema_version`, gets documented here, and is reviewed in public on GitHub. There is no path for a field to land silently — the payload builder uses an explicit allow-list ([`src/docglow/telemetry/payload.py`](https://github.com/docglow/docglow/blob/main/src/docglow/telemetry/payload.py)) and the snapshot test pins the exact shape.

## How to enable

Three equivalent ways:

```bash
docglow telemetry enable
```

```yaml
# docglow.yml
telemetry:
  enabled: true
```

```bash
export DOCGLOW_TELEMETRY=1
```

The first time you run `docglow generate` on an interactive terminal, you'll see a one-screen prompt asking if you'd like to opt in. The default answer is **no** — pressing enter, running in CI, or running with stdin redirected all keep telemetry off.

## How to disable

Any of these turns telemetry off completely:

```bash
docglow telemetry disable
```

```bash
export DOCGLOW_NO_TELEMETRY=1   # always wins, regardless of other settings
```

```yaml
# docglow.yml
telemetry:
  enabled: false   # the default
```

`DOCGLOW_NO_TELEMETRY=1` is the master kill switch. It overrides `DOCGLOW_TELEMETRY=1`, `telemetry: enabled: true` in `docglow.yml`, and any consent recorded by the prompt.

## Resolution order

When deciding whether to send an event, Docglow checks in this order (first match wins):

1. `DOCGLOW_NO_TELEMETRY=1` → off, no matter what.
2. `DOCGLOW_TELEMETRY=1` (or `=0`) → on (or off).
3. `telemetry.enabled` in `docglow.yml`.
4. Recorded consent from the prompt or `docglow telemetry enable`.
5. Default: off.

To inspect the resolved state on your machine:

```bash
docglow telemetry status
```

That command prints whether telemetry is currently active, your machine-level instance ID, the endpoint, and which env vars are set.

## Where the data goes

Events are sent over HTTPS to the Docglow Cloud API at `api.docglow.dev`. Rows land in a Postgres table managed via Supabase, accessible only to Docglow maintainers. We retain raw events for 365 days; aggregates may be kept longer.

If you want a particular `instance_id`'s data deleted, open an issue on [docglow/docglow](https://github.com/docglow/docglow/issues) with the ID and we'll purge it.
