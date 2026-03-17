# Community Launch Templates

## dbt Slack `#show-and-tell`

> Introducing docglow -- a better `dbt docs serve` for dbt Core teams
>
> We built an open-source replacement for the default dbt docs site. It generates a modern, interactive documentation site from your existing dbt artifacts -- no dbt Cloud required.
>
> Live demo: https://docglow.github.io/docglow/
> Install: `pip install docglow`
> Repo: https://github.com/docglow/docglow
>
> What it does differently:
> - Interactive lineage explorer (drag, filter, zoom)
> - Column-level lineage tracing via sqlglot
> - Project health scoring (docs coverage, test coverage, naming, complexity)
> - Full-text search across models, sources, and columns
> - Single-file mode for sharing via email/Slack
> - CI quality gate: `docglow health --fail-under 80`
>
> Works with any dbt Core project. Point it at your target/ directory and go.
>
> Looking for early feedback -- especially from teams with 200+ models. What's missing?

## r/dataengineering

**Title:** I built an open-source replacement for dbt docs that includes health scoring and an interactive lineage explorer

**Body:**

> Like most dbt Core teams, we were stuck with `dbt docs serve` -- the default documentation site that hasn't changed much in years. Static, hard to navigate, no search, no health metrics.
>
> So we built docglow: an open-source tool that generates a modern documentation site from your existing dbt artifacts. No dbt Cloud required, no configuration needed.
>
> **Live demo:** https://docglow.github.io/docglow/
>
> **What it does:**
> - Interactive lineage explorer with drag, filter, and zoom
> - Column-level lineage -- click a column to trace its upstream/downstream flow
> - Project health scoring -- coverage metrics for docs, tests, naming, complexity
> - Full-text search across models, sources, and columns
> - Single-file mode -- generate one HTML file you can share via email or Slack
> - CI integration -- `docglow health --fail-under 80` as a PR quality gate
>
> **Install:** `pip install docglow`
>
> It works with any dbt Core project (tested with dbt 1.11, adapter-agnostic). Just point it at your `target/` directory.
>
> Looking for feedback from teams running real projects -- especially those with 200+ models. What would make this useful for your workflow?
>
> Repo: https://github.com/docglow/docglow

## Posting Guidelines

- Post Tuesday-Thursday, 9am-12pm EST for peak engagement
- Lead with the demo link -- people click links, not walls of text
- Don't mention commercial tier -- focus on open-source credibility
- Ask for specific feedback ("teams with 200+ models") to drive engagement
- Be transparent about the project being early-stage
