# docglow Cloud: Hosted Tier Architecture

## Technical Architecture Document

**Version:** 0.1.0
**Date:** March 2026
**Status:** Planning
**Depends on:** docglow OSS PRD v0.1.0 (docglow-prd.md)

**Naming:** See the naming conventions table in the OSS PRD. Brand name is "docglow" (stylized) or "d++" (shorthand). All code identifiers, packages, domains, and CLI commands use `docglow`. The hosted product is "docglow Cloud" at `docglow.dev`.

**Trademark Notice:** dbt™, dbt Core™, and dbt Cloud™ are trademarks of dbt Labs, Inc. docglow is not affiliated with or endorsed by dbt Labs.

---

## 1. Product Overview

**docglow Cloud** is a hosted service that eliminates the infrastructure burden of publishing, sharing, and maintaining dbt documentation. Teams run `docglow publish` from their CI/CD pipeline, and their documentation site is live at `https://{workspace}.docglow.dev` within seconds — always current, always accessible, with features that only a persistent backend can provide.

### 1.1 Why Hosted? (The pitch to the user)

The open-source `docglow generate` produces a static HTML file. That's great for local use, but teams hit the same wall every time they try to share it:

- **Hosting is a headache.** Setting up S3 + CloudFront + IAP, or maintaining a GCP App Engine deploy, or running a dedicated EC2 instance just for docs — none of this is worth anyone's time, but somebody always gets stuck with the ticket.
- **Docs go stale.** The static file is a snapshot. If nobody re-generates and re-deploys after each dbt build, the docs drift from reality within days.
- **No memory.** A static file has no concept of "yesterday." You can't see whether documentation coverage improved or regressed, whether a source that's stale now was fine last week, or whether the model someone added last sprint has been documented yet.
- **Access control is DIY.** Sharing a static HTML file means either "everyone can see it" or "set up OAuth yourself."

docglow Cloud solves all of this with a single CLI command added to your existing dbt pipeline.

### 1.2 Free vs. Paid Feature Matrix

| Feature | OSS (Free) | Cloud Starter ($49/mo) | Cloud Team ($99/mo) | Cloud Business ($149/mo) |
|---|---|---|---|---|
| Static site generation | ✅ | ✅ | ✅ | ✅ |
| Column profiling | ✅ (BYOK warehouse) | ✅ | ✅ | ✅ |
| Health scoring | ✅ (CLI only) | ✅ | ✅ | ✅ |
| Full-text search | ✅ | ✅ | ✅ | ✅ |
| Lineage DAG | ✅ | ✅ | ✅ | ✅ |
| AI chat | ✅ (BYOK API key) | ✅ (managed, 100 msgs/mo) | ✅ (managed, 500 msgs/mo) | ✅ (managed, unlimited) |
| **Hosted URL** | ❌ | ✅ (1 project) | ✅ (3 projects) | ✅ (10 projects) |
| **Auto-publish from CI/CD** | ❌ | ✅ | ✅ | ✅ |
| **Access controls** | ❌ | ✅ (email allowlist) | ✅ (SSO/Google Workspace) | ✅ (SAML SSO) |
| **Historical health tracking** | ❌ | ✅ (30 days) | ✅ (90 days) | ✅ (1 year) |
| **Change notifications** | ❌ | ❌ | ✅ (Slack/email) | ✅ (Slack/email) |
| **Custom domain** | ❌ | ❌ | ✅ | ✅ |
| **Description editing via UI** | ❌ | ❌ | ✅ (creates PR) | ✅ (creates PR) |
| **Team members** | n/a | 5 viewers | 15 viewers | 50 viewers |
| **Audit log** | ❌ | ❌ | ❌ | ✅ |

---

## 2. Architecture Overview

### 2.1 High-Level System Diagram

```
                                    ┌─────────────────────────┐
                                    │    User's CI/CD          │
                                    │    (GitHub Actions,      │
                                    │     Airflow, etc.)       │
                                    │                          │
                                    │  $ dbt build             │
                                    │  $ docglow publish \   │
                                    │      --token $TOKEN      │
                                    └───────────┬─────────────┘
                                                │
                                    POST /api/v1/publish
                                    (multipart: artifacts.tar.gz)
                                                │
                                                ▼
┌───────────────────────────────────────────────────────────────────────┐
│                        Cloudflare                                     │
│                                                                       │
│   ┌─────────────┐    ┌──────────────────┐    ┌────────────────────┐  │
│   │  DNS/CDN    │    │  Workers (API)    │    │  R2 (Object Store) │  │
│   │             │    │                   │    │                    │  │
│   │ *.docglow.dev │───▶│  /api/v1/publish  │───▶│  /artifacts/       │  │
│   │             │    │  /api/v1/auth     │    │    {workspace}/    │  │
│   │             │    │  /api/v1/billing  │    │    {version}/      │  │
│   │             │    │  /api/v1/chat     │    │                    │  │
│   │             │    │                   │    │  /sites/           │  │
│   │             │    │  (Hono framework) │    │    {workspace}/    │  │
│   │             │    │                   │    │    index.html      │  │
│   │             │    └──────────────────┘    │    docglow-data.json  │  │
│   │             │              │              └────────────────────┘  │
│   │             │              │                                      │
│   │             │              ▼                                      │
│   │             │    ┌──────────────────┐    ┌────────────────────┐  │
│   │             │    │  Workers Queue    │    │  D1 (SQLite DB)    │  │
│   │             │    │                   │    │                    │  │
│   │             │    │  - Site regen     │    │  - workspaces      │  │
│   │             │    │  - Profile diff   │    │  - projects        │  │
│   │             │    │  - Notifications  │    │  - publish_history │  │
│   │             │    │  - Health track   │    │  - health_scores   │  │
│   │             │    │                   │    │  - users           │  │
│   │             │    └──────────────────┘    │  - api_tokens      │  │
│   │             │                            │  - subscriptions    │  │
│   │             │                            └────────────────────┘  │
│   └─────────────┘                                                    │
│                                                                       │
│   Site Serving:                                                       │
│   {workspace}.docglow.dev → R2 /sites/{workspace}/index.html           │
│   (Cloudflare Worker routes to R2, checks auth if private)           │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
                    │
                    │ (External services)
                    ▼
    ┌───────────────────────────────────┐
    │  Stripe (billing)                 │
    │  Anthropic API (managed AI chat)  │
    │  Resend (transactional email)     │
    │  GitHub API (PR creation for      │
    │    description edits)             │
    └───────────────────────────────────┘
```

### 2.2 Why Cloudflare Stack?

This architecture is deliberately built on Cloudflare's platform for three reasons that matter for a side-project with limited hours:

**Near-zero ops burden.** Workers, R2, D1, and Queues are all serverless. No EC2 instances to patch, no Kubernetes clusters to manage, no Aurora scaling to worry about. You deploy with `wrangler deploy` and forget about infrastructure.

**Extremely cheap at low scale.** The free tier includes 100K Worker requests/day, 10GB R2 storage, 5M D1 rows read/day, and 100K Queue messages/month. A realistic early-stage workload (50-100 teams publishing daily) costs under $20/month in platform fees. You don't hit meaningful costs until you have hundreds of paying customers — at which point revenue more than covers it.

**Built-in global CDN and custom domains.** Every workspace gets a `{name}.docglow.dev` subdomain via Cloudflare's DNS. Custom domains are a DNS CNAME pointing to Cloudflare. TLS is automatic. No CloudFront distributions or certificate managers to configure.

If you later outgrow this or want to migrate to AWS (your comfort zone), the Worker API layer ports cleanly to Lambda@Edge or API Gateway + Lambda, R2 maps to S3, and D1 maps to Aurora Serverless or DynamoDB.

---

## 3. Core Services

### 3.1 Publish Service

The most critical flow. This is what runs in the customer's CI/CD pipeline.

**Client-side (added to the docglow CLI):**

```bash
$ docglow publish --token $DOCGLOW_TOKEN

# What this does:
# 1. Reads artifacts from target/ directory (manifest, catalog, run_results, sources)
# 2. Optionally reads profiles.json if profiling was run locally
# 3. Compresses into a single artifacts.tar.gz
# 4. POST to https://api.docglow.dev/v1/publish with Bearer token auth
# 5. Receives a 202 Accepted with a publish_id
# 6. Polls /v1/publish/{publish_id}/status until complete (or --no-wait to skip)
# 7. Prints the live URL on success
```

**Server-side Worker flow:**

```
POST /api/v1/publish
  ├── Authenticate token → look up workspace + project
  ├── Validate payload size (max 50MB compressed)
  ├── Upload artifacts.tar.gz to R2: /artifacts/{workspace}/{project}/{timestamp}.tar.gz
  ├── Record publish event in D1: publish_history table
  ├── Enqueue site regeneration job to Workers Queue
  └── Return 202 { publish_id, status: "processing" }

Workers Queue Consumer (async):
  ├── Download artifacts from R2
  ├── Decompress and parse artifacts (same logic as OSS docglow)
  ├── Run health scoring
  ├── Compute health delta from previous publish
  ├── Generate docglow-data.json
  ├── Bundle with pre-built React SPA → index.html
  ├── Upload generated site to R2: /sites/{workspace}/{project}/
  │   ├── index.html
  │   └── docglow-data.json
  ├── Update D1: health_scores table (for historical tracking)
  ├── Update D1: publish_history (status: "complete")
  ├── If health regressed → trigger notification (Slack/email via Queue)
  └── Purge CDN cache for {workspace}.docglow.dev
```

**Key implementation detail:** The site regeneration logic is the *exact same Python code* as the OSS `docglow generate` command, compiled to run in a Worker via a lightweight Python runtime (Pyodide) or extracted into a TypeScript port of the core data transformation logic. The simpler approach for Phase 1: run the Python processing in a small always-on container (Fly.io $5/month nano VM) that the Worker triggers via HTTP, and have the Worker handle only routing, auth, and R2 storage.

### 3.2 Site Serving

**Public workspaces:** `{workspace}.docglow.dev` routes directly to R2 static files. Cloudflare Worker intercepts the request, resolves the workspace from the subdomain, and serves `/sites/{workspace}/{project}/index.html` from R2. This is pure CDN-speed serving.

**Private workspaces (most paid plans):** The Worker intercepts the request and checks for a valid session cookie. If no cookie, redirect to the auth flow. If valid cookie, check that the user's email is in the workspace's access list (stored in D1), then serve the site.

**Routing logic:**

```
Request: https://acme.docglow.dev
  │
  Worker:
  ├── Parse subdomain → workspace = "acme"
  ├── Look up workspace in D1 → get project, access_mode
  ├── If access_mode = "public" → serve from R2
  ├── If access_mode = "private":
  │   ├── Check session cookie
  │   ├── If no session → redirect to auth.docglow.dev/login?workspace=acme
  │   ├── If session valid → check email in allowed_viewers
  │   ├── If allowed → serve from R2
  │   └── If not allowed → 403 page
  └── If workspace not found → 404 page

Request: https://acme.docglow.dev/api/v1/chat
  │
  Worker:
  ├── Authenticate session (same as above)
  ├── Rate-limit check against subscription tier
  ├── Forward prompt + project context to Anthropic API
  └── Stream response back to client
```

**Multi-project workspaces:** For Team and Business tiers, the URL structure is `{workspace}.docglow.dev/{project-slug}`. The Worker routes based on the path.

### 3.3 Authentication Service

Keep auth simple. No building a full auth system from scratch.

**Phase 1 (Starter tier): Magic link email auth**
- User enters email on login page
- Worker generates a one-time token, stores in D1, sends email via Resend
- User clicks link → Worker validates token → sets session cookie (signed JWT with 7-day expiry)
- Workspace admin configures allowed email addresses or email domain (e.g., `@acme.com`)

**Phase 2 (Team tier): Google OAuth**
- Standard OAuth 2.0 flow via Google
- Workspace admin configures allowed Google Workspace domain
- Worker validates that authenticated email belongs to the allowed domain

**Phase 3 (Business tier): SAML SSO**
- Integrate with a SAML identity provider via a service like WorkOS ($0.50/user/month)
- Only needed when you have enterprise customers; don't build until needed

**Session management:**
- JWT stored in httpOnly cookie on `.docglow.dev` domain
- JWT payload: `{ user_id, email, workspace_id, expires_at }`
- Workers KV for session revocation list (fast lookup)

### 3.4 Billing Service

**Use Stripe Checkout and Stripe Billing. Do not build custom billing.**

**Flow:**

```
1. User signs up at docglow.dev → creates workspace (free tier, no card needed)
2. User wants paid features → clicks "Upgrade" → redirected to Stripe Checkout
3. Stripe Checkout collects payment → redirects back to docglow.dev/settings
4. Stripe webhook fires → Worker receives event → updates D1 subscription table
5. Feature flags in D1 now reflect the paid tier
6. On each API request, Worker checks subscription tier for rate limits / feature access
```

**Stripe configuration:**

```
Products:
  - Starter: $49/month (price_starter_monthly)
    - 1 project, 5 viewers, 100 AI messages/month, 30-day history
  - Team: $99/month (price_team_monthly)
    - 3 projects, 15 viewers, 500 AI messages/month, 90-day history
  - Business: $149/month (price_business_monthly)
    - 10 projects, 50 viewers, unlimited AI messages, 1-year history

Billing events to handle:
  - checkout.session.completed → activate subscription
  - invoice.paid → extend subscription
  - invoice.payment_failed → grace period (7 days), then downgrade
  - customer.subscription.deleted → downgrade to free tier
```

**Metering for AI chat:**
- Track AI message count per workspace per billing period in D1
- Worker checks count before proxying to Anthropic API
- If over limit → return 429 with upgrade prompt

### 3.5 Notification Service

Triggered by the publish pipeline when notable changes are detected.

**Change detection logic (runs during site regeneration):**

```python
# Compare current publish to previous publish
changes = {
    "new_models": [],          # Models in current but not in previous
    "removed_models": [],      # Models in previous but not in current
    "new_undocumented": [],    # Models added without descriptions
    "health_delta": 0,         # Change in overall health score
    "newly_failing_tests": [], # Tests that were passing, now failing
    "freshness_alerts": [],    # Sources that breached SLA since last publish
    "coverage_delta": {
        "doc_coverage": +0.03, # Documentation coverage change
        "test_coverage": -0.01 # Test coverage change
    }
}
```

**Notification channels:**

- **Slack** (Team and Business tiers): Incoming webhook configured by workspace admin. Posts a summary card with health score, notable changes, and a link to the docs site.
- **Email** (all paid tiers): Weekly digest email summarizing health trends and outstanding documentation debt. Uses Resend for delivery.

**Example Slack notification:**

```
📊 docglow | acme-analytics updated
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Health Score: 74 → 72 (▼ 2)

⚠️  3 new models added without documentation:
    • stg_hubspot_contacts
    • int_customer_enrichment
    • fct_campaign_attribution

🔴  2 tests now failing:
    • unique_fct_orders_order_id
    • not_null_dim_customers_email

📈  Doc coverage: 66% → 64%
📈  Test coverage: 76% → 75%

View docs → https://acme.docglow.dev
```

### 3.6 AI Chat Proxy

The hosted tier proxies AI chat requests through the backend instead of calling Anthropic directly from the browser. This provides three benefits: users don't need their own API key, you can enforce rate limits per subscription tier, and you can inject richer context (like historical health data) into the prompt.

**Flow:**

```
Browser → POST /api/v1/chat { message, conversation_history }
  │
  Worker:
  ├── Authenticate session
  ├── Check AI message quota (D1 lookup)
  ├── Load docglow-data.json from R2 for this workspace/project
  ├── Build context payload (compact model registry from docglow-data.json)
  ├── Call Anthropic API (streaming):
  │   model: claude-sonnet-4-20250514
  │   system: [project context + system prompt]
  │   messages: [conversation_history + new message]
  ├── Stream response tokens back to browser via SSE
  ├── Increment AI message counter in D1
  └── Log token usage for cost tracking
```

**Cost management:**
- Use claude-sonnet-4-20250514 (not Opus) to keep costs reasonable
- Limit context to compact model registry (not full SQL)
- Average cost per message: ~$0.01-0.03
- At 500 messages/month (Team tier): $5-15/month in API costs
- Well within margin at $99/month price point

---

## 4. Database Schema (Cloudflare D1)

D1 is SQLite-based, so keep the schema simple and denormalized where it helps performance.

```sql
-- Workspace is the top-level organizational unit (one per paying customer)
CREATE TABLE workspaces (
    id TEXT PRIMARY KEY,                    -- ulid
    slug TEXT UNIQUE NOT NULL,              -- URL-safe name, used in subdomain
    name TEXT NOT NULL,                     -- Display name
    owner_email TEXT NOT NULL,
    access_mode TEXT DEFAULT 'private',     -- 'public' or 'private'
    allowed_emails TEXT,                    -- JSON array of allowed viewer emails
    allowed_domain TEXT,                    -- e.g., 'acme.com' (all emails from this domain allowed)
    stripe_customer_id TEXT,
    subscription_tier TEXT DEFAULT 'free',  -- 'free', 'starter', 'team', 'business'
    subscription_status TEXT DEFAULT 'active', -- 'active', 'past_due', 'canceled'
    settings TEXT,                          -- JSON blob for misc settings
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Projects within a workspace (1 for Starter, 3 for Team, 10 for Business)
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    slug TEXT NOT NULL,                     -- URL path segment
    name TEXT NOT NULL,
    dbt_project_name TEXT,                  -- From manifest.json metadata
    latest_publish_id TEXT,
    latest_health_score INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(workspace_id, slug)
);

-- API tokens for CI/CD authentication
CREATE TABLE api_tokens (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    project_id TEXT REFERENCES projects(id), -- null = workspace-wide token
    token_hash TEXT UNIQUE NOT NULL,         -- SHA-256 hash of the actual token
    name TEXT NOT NULL,                      -- User-given name, e.g., "GitHub Actions"
    last_used_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Publish history (each time docglow publish runs)
CREATE TABLE publishes (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    status TEXT DEFAULT 'processing',        -- 'processing', 'complete', 'failed'
    artifact_path TEXT,                      -- R2 path to artifacts.tar.gz
    site_path TEXT,                          -- R2 path to generated site
    health_score INTEGER,
    health_report TEXT,                      -- JSON blob of full HealthReport
    change_summary TEXT,                     -- JSON blob of detected changes
    dbt_version TEXT,
    model_count INTEGER,
    source_count INTEGER,
    error_message TEXT,                      -- If status = 'failed'
    duration_ms INTEGER,                     -- Time to process
    triggered_by TEXT,                       -- 'cli', 'api', 'webhook'
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);

-- Historical health scores (one row per publish, queryable for trends)
CREATE TABLE health_history (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    publish_id TEXT NOT NULL REFERENCES publishes(id),
    overall_score INTEGER,
    doc_model_coverage REAL,
    doc_column_coverage REAL,
    test_model_coverage REAL,
    test_column_coverage REAL,
    freshness_passing_rate REAL,
    model_count INTEGER,
    source_count INTEGER,
    recorded_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_health_history_project ON health_history(project_id, recorded_at);

-- Users (viewers who access the docs site)
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    avatar_url TEXT,
    auth_provider TEXT,                     -- 'magic_link', 'google', 'saml'
    last_login_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Workspace membership
CREATE TABLE workspace_members (
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    user_id TEXT NOT NULL REFERENCES users(id),
    role TEXT DEFAULT 'viewer',             -- 'owner', 'admin', 'viewer'
    invited_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (workspace_id, user_id)
);

-- AI chat usage tracking
CREATE TABLE ai_usage (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    user_id TEXT NOT NULL REFERENCES users(id),
    project_id TEXT NOT NULL REFERENCES projects(id),
    message_count INTEGER DEFAULT 1,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd REAL,
    billing_period TEXT,                    -- '2026-03' format
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_ai_usage_billing ON ai_usage(workspace_id, billing_period);

-- Notification configuration
CREATE TABLE notification_configs (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    channel TEXT NOT NULL,                  -- 'slack', 'email'
    config TEXT NOT NULL,                   -- JSON: { webhook_url } for Slack, { recipients: [] } for email
    events TEXT NOT NULL,                   -- JSON array: ['health_regression', 'new_undocumented', 'test_failure']
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);
```

---

## 5. R2 (Object Storage) Structure

```
docglow-r2-bucket/
├── artifacts/
│   └── {workspace_slug}/
│       └── {project_slug}/
│           ├── 2026-03-06T14:30:00Z.tar.gz    # Raw artifacts from each publish
│           ├── 2026-03-05T14:30:00Z.tar.gz
│           └── ...                              # Retain last 30/90/365 based on tier
│
├── sites/
│   └── {workspace_slug}/
│       └── {project_slug}/
│           ├── index.html                       # Current live site
│           ├── docglow-data.json                  # Current data payload
│           └── previous/                        # Previous version (for rollback)
│               ├── index.html
│               └── docglow-data.json
│
└── static/
    ├── app.js                                   # Pre-built React SPA (shared across all sites)
    ├── app.css
    └── favicon.svg
```

**Storage optimization:** Instead of bundling the React SPA into each site's `index.html`, serve the SPA assets from a shared `/static/` path and have each site's `index.html` just reference the shared SPA + its own `docglow-data.json`. This means a site update only writes the data file (~1-5MB), not the full SPA bundle.

**Retention policy:**
- Starter: keep last 30 days of artifacts and health history
- Team: 90 days
- Business: 1 year
- Automated cleanup via a daily cron Worker

---

## 6. API Specification

### 6.1 Publish API (used by CLI)

```
POST /api/v1/publish
Authorization: Bearer {api_token}
Content-Type: multipart/form-data

Body:
  artifacts: (file) artifacts.tar.gz containing:
    - manifest.json
    - catalog.json
    - run_results.json (optional)
    - sources.json (optional)
    - profiles.json (optional, from local profiling)

Response: 202 Accepted
{
  "publish_id": "01HXYZ...",
  "status": "processing",
  "status_url": "/api/v1/publish/01HXYZ.../status"
}
```

```
GET /api/v1/publish/{publish_id}/status
Authorization: Bearer {api_token}

Response: 200 OK
{
  "publish_id": "01HXYZ...",
  "status": "complete",           // or "processing" or "failed"
  "site_url": "https://acme.docglow.dev",
  "health_score": 72,
  "health_delta": -2,
  "duration_ms": 4200,
  "changes": {
    "new_models": ["stg_hubspot_contacts"],
    "newly_failing_tests": ["unique_fct_orders_order_id"],
    "doc_coverage_delta": -0.02
  }
}
```

### 6.2 AI Chat API (used by frontend)

```
POST /api/v1/chat
Cookie: docglow_session={jwt}

Body:
{
  "project_id": "proj_abc123",
  "message": "What models depend on the Stripe source?",
  "conversation_history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}

Response: 200 OK (Server-Sent Events stream)
data: {"type": "token", "content": "The"}
data: {"type": "token", "content": " following"}
data: {"type": "token", "content": " models"}
...
data: {"type": "done", "usage": {"input_tokens": 1200, "output_tokens": 340}}
```

### 6.3 Health History API (used by frontend dashboard)

```
GET /api/v1/projects/{project_id}/health/history?days=30
Cookie: docglow_session={jwt}

Response: 200 OK
{
  "project_id": "proj_abc123",
  "data_points": [
    {
      "date": "2026-03-06",
      "overall_score": 72,
      "doc_model_coverage": 0.66,
      "doc_column_coverage": 0.35,
      "test_model_coverage": 0.76,
      "model_count": 68
    },
    {
      "date": "2026-03-05",
      "overall_score": 74,
      ...
    }
  ]
}
```

### 6.4 Workspace Management API (used by settings UI)

```
# Create workspace (signup)
POST /api/v1/workspaces
{ "name": "Acme Analytics", "slug": "acme", "owner_email": "josh@acme.com" }

# Update workspace settings
PATCH /api/v1/workspaces/{workspace_id}
{ "access_mode": "private", "allowed_domain": "acme.com" }

# Create API token
POST /api/v1/workspaces/{workspace_id}/tokens
{ "name": "GitHub Actions", "project_id": "proj_abc123" }
→ { "token": "dtm_live_abc123xyz...", "id": "tok_..." }
  (token shown once, only hash stored)

# List publish history
GET /api/v1/projects/{project_id}/publishes?limit=20

# Manage viewers
POST /api/v1/workspaces/{workspace_id}/members
{ "email": "analyst@acme.com", "role": "viewer" }
```

---

## 7. CLI Additions (docglow publish)

Add these commands to the OSS CLI package. The commands themselves are free and open source; they just require a docglow.dev account to function.

```python
# src/docglow/cloud/
#   __init__.py
#   publish.py      # Publish command implementation
#   auth.py         # Token management
#   config.py       # Cloud configuration

# New CLI commands:

@cli.command()
@click.option("--token", envvar="DOCGLOW_TOKEN", help="API token")
@click.option("--project-dir", default=".", help="dbt project directory")
@click.option("--target-dir", default="target", help="dbt target directory")
@click.option("--no-wait", is_flag=True, help="Don't wait for processing to complete")
def publish(token, project_dir, target_dir, no_wait):
    """Publish documentation to docglow.dev"""
    pass

@cli.command()
@click.option("--token", envvar="DOCGLOW_TOKEN")
def status(token):
    """Check publish status and site health"""
    pass

@cli.command()
def login():
    """Authenticate with docglow.dev (opens browser)"""
    pass

@cli.command()
def setup():
    """Interactive setup wizard for docglow.dev integration"""
    pass
```

**Example CI/CD integration (GitHub Actions):**

```yaml
# .github/workflows/dbt-docs.yml
name: Publish dbt Docs

on:
  push:
    branches: [main]

jobs:
  publish-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dbt and docglow
        run: |
          pip install dbt-core dbt-snowflake docglow

      - name: Run dbt build
        run: dbt build
        env:
          DBT_PROFILES_DIR: .

      - name: Publish docs
        run: docglow publish
        env:
          DOCGLOW_TOKEN: ${{ secrets.DOCGLOW_TOKEN }}
```

---

## 8. Frontend Additions for Hosted Mode

The React SPA needs to detect whether it's running in local/static mode or hosted mode, and conditionally render additional features.

**Detection mechanism:** The `docglow-data.json` payload includes a `metadata.hosted` field:

```typescript
interface DocglowMetadata {
  // ... existing fields from OSS PRD ...
  hosted: boolean;
  workspace_slug: string | null;
  project_slug: string | null;
  api_base_url: string | null;     // e.g., "https://acme.docglow.dev/api/v1"
  features: {
    ai_chat: boolean;               // true if managed AI is available
    health_history: boolean;        // true if historical data is available
    notifications: boolean;
    description_editing: boolean;
    max_viewers: number;
  };
}
```

**Hosted-only UI additions:**

1. **Health History Chart** on the Health Dashboard page: line chart showing health score over time (fetched from `/api/v1/projects/{id}/health/history`)
2. **Settings Panel** (gear icon in header): workspace settings, viewer management, notification config, API token management, billing (links to Stripe Customer Portal)
3. **Managed AI Chat**: same UI as BYOK chat, but calls the hosted API endpoint instead of Anthropic directly. No API key input needed.
4. **"Published X hours ago" indicator** in footer, with link to publish history.
5. **Description Edit Button**: pencil icon next to model/column descriptions. Clicking opens an edit modal. Saving creates a PR on the connected GitHub repo with the updated schema.yml. (Team+ tier only.)

---

## 9. Infrastructure Cost Estimate

### At 0 paying customers (development/launch):

| Service | Monthly Cost |
|---|---|
| Cloudflare Workers (free tier) | $0 |
| Cloudflare R2 (free tier: 10GB) | $0 |
| Cloudflare D1 (free tier: 5M reads/day) | $0 |
| docglow.dev domain | ~$1 |
| Fly.io nano VM (Python processing) | $5 |
| Resend (free tier: 3K emails/month) | $0 |
| Stripe | $0 (no transactions) |
| **Total** | **~$6/month** |

### At 50 paying customers (~$4K MRR):

| Service | Monthly Cost |
|---|---|
| Cloudflare Workers Paid ($5/month + usage) | ~$10 |
| Cloudflare R2 (~50GB storage + bandwidth) | ~$5 |
| Cloudflare D1 (~1M rows) | ~$5 |
| Fly.io (scaled up for processing) | $15 |
| Anthropic API (managed AI chat) | ~$100 |
| Resend (paid tier) | $20 |
| Stripe fees (2.9% + $0.30) | ~$130 |
| **Total** | **~$285/month** |
| **Margin** | **~93%** |

### At 200 paying customers (~$16K MRR):

| Service | Monthly Cost |
|---|---|
| Cloudflare Workers | ~$25 |
| Cloudflare R2 (~200GB) | ~$20 |
| Cloudflare D1 | ~$10 |
| Fly.io (multiple VMs) | $50 |
| Anthropic API | ~$400 |
| Resend | $40 |
| Stripe fees | ~$500 |
| **Total** | **~$1,045/month** |
| **Margin** | **~93%** |

---

## 10. Implementation Phases

### Phase 1: Hosted MVP (Weeks 13-16, after OSS MVP is stable)

Focus: Get the core publish → host → view loop working.

- [ ] Cloudflare Worker project setup (Hono framework)
- [ ] Publish API endpoint (upload artifacts to R2)
- [ ] Site generation Worker (reuse OSS logic, output to R2)
- [ ] Site serving Worker (subdomain routing → R2)
- [ ] D1 schema migration and workspace/project tables
- [ ] API token generation and authentication
- [ ] `docglow publish` CLI command
- [ ] Stripe Checkout integration (single "Starter" tier)
- [ ] Magic link email auth for viewers
- [ ] Simple settings page (manage viewers, view publish history)
- [ ] Landing page at docglow.dev with signup flow

### Phase 2: Intelligence Features (Weeks 17-20)

- [ ] Health history storage and trend API
- [ ] Health history chart in frontend
- [ ] Managed AI chat proxy with rate limiting
- [ ] Slack notification integration
- [ ] Change detection between publishes
- [ ] Team tier with Google OAuth

### Phase 3: Growth Features (Weeks 21-24)

- [ ] Custom domain support
- [ ] Description editing → GitHub PR flow
- [ ] Weekly email digest
- [ ] Business tier with SAML (via WorkOS)
- [ ] Audit logging
- [ ] Workspace admin dashboard

---

## 11. Security Considerations

- **API tokens** are hashed (SHA-256) before storage. Raw token shown once at creation.
- **Session JWTs** are signed with a secret rotated monthly, stored in Workers Secrets.
- **Artifact data** is isolated per workspace. R2 paths are namespaced. Workers verify workspace ownership on every request.
- **AI chat** prompts never include raw warehouse data — only metadata from manifest/catalog. No actual row-level data leaves the customer's warehouse.
- **No warehouse credentials** are ever sent to docglow.dev. Profiling runs locally in the customer's environment.
- **SOC 2 / compliance:** Not needed initially, but the Cloudflare stack is SOC 2 Type II compliant, which simplifies future certification if enterprise customers require it.
- **Data retention:** Customers can delete their workspace at any time, which triggers deletion of all artifacts, generated sites, and metadata from R2 and D1.

---

## 12. Go-to-Market Sequence

1. **Months 1-3:** Build and launch OSS docglow. Focus entirely on adoption, GitHub stars, and community presence. No hosted tier yet.
2. **Month 4:** Begin building hosted tier while OSS gains traction.
3. **Month 5:** Soft launch hosted tier to 10-20 beta users from the OSS community. Free during beta.
4. **Month 6:** Public launch of hosted tier with Starter plan only ($49/month). Announce on dbt Slack, Reddit, LinkedIn.
5. **Month 7-8:** Add Team tier based on beta feedback. Add Slack notifications.
6. **Month 9-12:** Add Business tier if demand warrants. Focus on retention and expansion.

**Conversion funnel:**
```
OSS users (pip installs)
  → docglow.dev signups (free workspace, limited to public access)
    → Starter conversions (need private access or managed AI)
      → Team upgrades (need more projects, viewers, or notifications)
        → Business upgrades (need SSO, custom domain, long history)
```

The key insight: the OSS tool is the distribution engine. Every team that runs `docglow generate` locally is a potential hosted customer. The publish command is the bridge — making it trivially easy to go from "I use this locally" to "my whole team uses this on docglow.dev."

---

*This architecture document should be read alongside the OSS PRD (docglow-prd.md). The hosted tier is designed to be built on top of the OSS core, sharing the same data transformation and site generation logic. Every feature in the hosted tier exists because a persistent backend enables capabilities that a static file cannot provide.*