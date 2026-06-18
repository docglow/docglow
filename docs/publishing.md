# Publishing to Docglow Cloud

**Push your dbt documentation to a hosted, shareable site with a single command.**

`docglow publish` uploads your dbt artifacts to [Docglow Cloud](cloud.md), which renders the documentation site, scores its health, and hosts it at a shareable URL. There's no static site to build first and no infrastructure to manage — you run `dbt build`, then `docglow publish`.

!!! note "Docglow Cloud is in early access"
    Publishing requires a Docglow Cloud account. We're onboarding early access users now — [join the waitlist](https://docglow.com/#cloud){ .md-button .md-button--primary } to get a token.

## Prerequisites

Before you can publish, you'll need:

1. **A Docglow Cloud account and API token.** Get your token at [app.docglow.com/settings/tokens](https://app.docglow.com/settings/tokens).
2. **The `cloud` extra installed**, which pulls in the HTTP client used for uploads:
   ```bash
   pip install "docglow[cloud]"
   ```
3. **dbt artifacts.** Publishing uploads the JSON artifacts dbt writes to your `target/` directory. Run a build first:
   ```bash
   dbt build   # or: dbt docs generate
   ```

!!! tip "You do *not* need to run `docglow generate` first"
    Unlike local site generation, `publish` uploads your raw dbt artifacts (`manifest.json`, `catalog.json`, and friends) — the Cloud renders the site server-side. Just make sure `target/` is fresh from a recent `dbt build`.

## Authenticate

Save your API token once with `docglow login`:

```bash
docglow login --token YOUR_TOKEN
```

Your token is stored in `~/.docglow/config.json` (created with `0600` permissions) and reused on every subsequent command.

To sign out and remove the stored credentials:

```bash
docglow logout
```

!!! note "Interactive browser login is coming"
    For now, pass your token explicitly with `--token`. Browser-based login isn't available yet.

## Publish your docs

From your dbt project root, after a `dbt build`:

```bash
docglow publish
```

What happens:

1. Docglow finds the dbt artifacts in `target/` (`manifest.json`, `catalog.json`, and optionally `run_results.json`, `sources.json`, `profiles.json`).
2. It packs them into a compressed archive and uploads it to Docglow Cloud.
3. The Cloud renders your documentation site and scores its health.
4. The CLI waits for processing to finish, then prints your site URL and health score:

```
Published successfully!
Site: https://your-workspace.docglow.com
Health score: 87
```

The upload is associated with your token's workspace and project automatically — you don't pass a workspace or project name on the command line.

## Check your site and workspace

`docglow status` shows your workspace, plan tier, latest health score, and live site URL:

```bash
docglow status
```

```
Workspace:    Acme Data
Slug:         acme-data
Tier:         pro
Health:       87
Site:         https://acme-data.docglow.com
```

## Publishing from CI/CD

Publishing is designed to drop into a CI pipeline so your hosted docs stay in sync with `main`. Authenticate non-interactively with the `DOCGLOW_TOKEN` environment variable (no `docglow login` step needed) and pass `--no-wait` so the job returns as soon as the upload completes instead of polling for the render to finish.

```yaml
# .github/workflows/publish-docs.yml
name: Publish docs
on:
  push:
    branches: [main]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install "docglow[cloud]"
      - run: dbt build        # produces target/ artifacts
      - run: docglow publish --no-wait
        env:
          DOCGLOW_TOKEN: ${{ secrets.DOCGLOW_TOKEN }}
```

Store your API token as a repository secret named `DOCGLOW_TOKEN`. For deploying the open-source static site instead of using Cloud, see the [CI/CD Deployment guide](ci-cd-guide.md).

## Options

```bash
docglow publish [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--token` | `DOCGLOW_TOKEN` env var | API token. Falls back to `~/.docglow/config.json`. |
| `--project-dir` | `.` | Path to the dbt project root |
| `--target-dir` | `<project-dir>/target` | Directory containing the dbt artifacts to upload |
| `--api-url` | `https://app.docglow.com` | Override the API base URL. Falls back to `DOCGLOW_API_URL` env var, then `~/.docglow/config.json`. |
| `--no-wait` | off | Upload and exit without waiting for the site to finish rendering |
| `--verbose` | off | Enable debug logging |

When you wait for processing (the default), the CLI polls for up to 5 minutes before timing out. Use `--no-wait` in automation where you don't need the final URL echoed back.

### Targeting a non-production environment

To publish to staging instead of production:

```bash
docglow publish --api-url https://app-staging.docglow.com
# or
DOCGLOW_API_URL=https://app-staging.docglow.com docglow publish
```

## Troubleshooting

| Message | Cause and fix |
|---------|---------------|
| `Cloud features require httpx. Install with: pip install docglow[cloud]` | The `cloud` extra isn't installed. Run `pip install "docglow[cloud]"`. |
| `No API token found. Set DOCGLOW_TOKEN env var or run docglow login.` | You're not authenticated. Run `docglow login --token YOUR_TOKEN` or set `DOCGLOW_TOKEN`. |
| `Target directory not found ... Run 'dbt build' first to generate artifacts.` | There's no `target/` directory. Run `dbt build` from your project root, or point `--target-dir` at the right path. |
| `No dbt artifacts found ... Expected at least manifest.json and catalog.json.` | The target directory exists but has no artifacts. Re-run `dbt build` / `dbt docs generate`. |
| `Publish failed: ...` | The Cloud rejected the upload or failed to render. Re-run with `--verbose` for details, and check `docglow status` for your workspace state. |
| `Publish timed out after 300s` | The render took longer than the 5-minute wait window. The publish may still complete — check `docglow status`, or re-run with `--no-wait`. |

## Related

- [Docglow Cloud](cloud.md) — what's included, pricing, and the early access waitlist
- [CLI Reference](reference/cli.md) — full command and option listing
- [CI/CD Deployment](ci-cd-guide.md) — deploying the open-source static site
