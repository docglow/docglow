# CI/CD Deployment Guide

This guide walks through deploying your Docglow documentation site in CI/CD, using documentation health as a quality gate, and integrating with common hosting targets.

## Quick Start — GitHub Pages

The fastest path: copy the example workflow, enable Pages, and push.

1. **Enable GitHub Pages** — go to your repo's **Settings > Pages** and set the source to **GitHub Actions**.
2. **Copy the workflow** — save [`docs/examples/docglow-pages.yml`](examples/docglow-pages.yml) to `.github/workflows/docglow-pages.yml` in your repository.
3. **Push to main** — the workflow runs automatically on every push.

Your site will be live at `https://<org>.github.io/<repo>/` within a few minutes.

> **Tip:** The example workflow includes a health check step that fails the build if documentation quality drops below a threshold. Set the `DOCGLOW_FAIL_UNDER` repository variable (Settings > Variables > Actions) to adjust the threshold — it defaults to 70.

## GitHub Actions — GitHub Pages (Full Walkthrough)

Below is a step-by-step explanation of each piece. See [`docs/examples/docglow-pages.yml`](examples/docglow-pages.yml) for the complete, copy-paste-ready file.

### Trigger

```yaml
on:
  push:
    branches: [main]
  workflow_dispatch:
```

The workflow runs on every push to `main` and can be triggered manually from the Actions tab.

### Permissions

```yaml
permissions:
  contents: read
  pages: write
  id-token: write
```

GitHub Pages deployment requires `pages: write` and `id-token: write` for the OIDC token used by the deploy action.

### Concurrency

```yaml
concurrency:
  group: pages
  cancel-in-progress: true
```

Ensures only one deployment runs at a time. If you push twice in quick succession, the first deployment is cancelled.

### Steps

1. **Checkout** — `actions/checkout@v4`
2. **Set up Python** — `actions/setup-python@v5` (Python 3.12 recommended)
3. **Install Docglow** — `pip install docglow`
4. **Health check** — `docglow health --project-dir . --fail-under 70` (optional but recommended)
5. **Generate site** — `docglow generate --project-dir . --output-dir site --static`
6. **Configure Pages** — `actions/configure-pages@v4`
7. **Upload artifact** — `actions/upload-pages-artifact@v3`
8. **Deploy** — `actions/deploy-pages@v4`

### dbt Artifacts

Docglow reads from your dbt project's `target/` directory. You have two options:

- **Commit artifacts** — check `target/manifest.json` and `target/catalog.json` into the repository. Simple, but increases repo size.
- **Generate in CI** — add a step before Docglow that runs `dbt compile` (or `dbt run`). This requires your dbt dependencies and warehouse credentials to be available in CI.

## GitHub Actions — S3 Deployment

For teams hosting on S3 with static website hosting:

```yaml
name: Deploy Docs to S3

on:
  push:
    branches: [main]
  workflow_dispatch:

env:
  S3_BUCKET: my-dbt-docs-bucket

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install docglow
        run: pip install docglow

      - name: Check documentation health
        run: docglow health --project-dir . --fail-under 70

      - name: Generate documentation site
        run: docglow generate --project-dir . --output-dir site

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Deploy to S3
        run: aws s3 sync site/ s3://${{ env.S3_BUCKET }}/ --delete
```

**Prerequisites:**

- Create an S3 bucket with [static website hosting](https://docs.aws.amazon.com/AmazonS3/latest/userguide/WebsiteHosting.html) enabled.
- Add `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` as repository secrets (Settings > Secrets > Actions).
- Optionally front the bucket with CloudFront for HTTPS and caching.

> **Note:** Unlike GitHub Pages, S3 doesn't require `--static` mode. You can deploy the multi-file output for faster incremental updates.

## Health Score as a CI Quality Gate

The `--fail-under` flag on both `docglow health` and `docglow generate` exits with code 1 when the project health score drops below the given threshold. This makes it easy to enforce documentation standards in CI.

### As a PR check

Add a health check that runs on pull requests so documentation regressions are caught before merge:

```yaml
name: Documentation Health Check

on:
  pull_request:
    branches: [main]

jobs:
  health-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install docglow
        run: pip install docglow

      - name: Check documentation health
        run: docglow health --project-dir . --fail-under 75
```

To make this a **required status check**, go to your repo's **Settings > Branches > Branch protection rules** and add `health-check` as a required check for the `main` branch.

### Choosing a threshold

| Threshold | When to use |
|-----------|-------------|
| **50–60** | Getting started — enforces basic descriptions exist |
| **70–75** | Recommended default — good coverage without being too strict |
| **80–90** | Mature projects with strong documentation culture |
| **90+**   | Aspirational — may require every column to be documented |

Start lower and ratchet up over time as your team builds documentation habits.

## The `--slim` Flag for Large Projects

For projects with hundreds of models, the generated site payload can be large — SQL source code is the biggest contributor. The `--slim` flag strips `raw_sql` and `compiled_sql` from the output:

```bash
docglow generate --project-dir . --output-dir site --slim
```

This can reduce output size by 40–60% for SQL-heavy projects. The trade-off is that users won't see SQL source in the documentation site. Use `--slim` in CI when:

- Your project has 200+ models and deploy times are a concern.
- You're deploying to GitHub Pages (which has a [1 GB size limit](https://docs.github.com/en/pages/getting-started-with-github-pages/about-github-pages#usage-limits)).
- SQL source isn't needed in the published docs (e.g., internal viewers already use dbt Cloud or an IDE).

You can also set `slim: true` in `docglow.yml` to make it the default for all commands.

## Enterprise GitHub with Private Pages

GitHub Enterprise Cloud and GitHub Enterprise Server support [private GitHub Pages](https://docs.github.com/en/enterprise-cloud@latest/pages/getting-started-with-github-pages/changing-the-visibility-of-your-github-pages-site) — the site is only accessible to members of the organization.

To use private Pages:

1. Go to **Settings > Pages > Visibility** and select **Private**.
2. Use the same workflow above — no changes needed.
3. Only authenticated organization members can view the site.

> **Note:** Private Pages is only available on GitHub Enterprise Cloud and GitHub Enterprise Server. On GitHub.com (free/pro/team plans), Pages sites are always public. If you need private hosting on a non-Enterprise plan, consider S3 with CloudFront and IAM-based access control, or [Docglow Cloud](https://docglow.com) which includes built-in access management.

## GitLab CI

The same approach works in GitLab CI. Here's an equivalent `.gitlab-ci.yml`:

```yaml
pages:
  image: python:3.12
  stage: deploy
  script:
    - pip install docglow
    - docglow health --project-dir . --fail-under 70
    - docglow generate --project-dir . --output-dir public --static
  artifacts:
    paths:
      - public
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

Key differences from GitHub Actions:

- GitLab Pages expects the output directory to be named `public`.
- The `pages` job name is special in GitLab — it automatically triggers a Pages deployment.
- The `rules` block replaces GitHub's `on.push.branches` trigger.
- Use GitLab CI/CD variables (Settings > CI/CD > Variables) for secrets instead of GitHub's repository secrets.

## Ready-to-Copy Workflow Files

| File | Description |
|------|-------------|
| [`docs/examples/docglow-pages.yml`](examples/docglow-pages.yml) | Complete GitHub Pages deployment with health gate |
| [`docs/ci-examples/github-actions-pages.yml`](ci-examples/github-actions-pages.yml) | Minimal GitHub Pages deployment |
| [`docs/ci-examples/github-actions-s3.yml`](ci-examples/github-actions-s3.yml) | S3 deployment with health check |
| [`docs/ci-examples/github-actions-health-check.yml`](ci-examples/github-actions-health-check.yml) | PR health check (quality gate only) |
