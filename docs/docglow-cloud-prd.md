# Docglow Cloud — Product Requirements Document

**Version:** 1.1
**Date:** March 26, 2026
**Author:** Josh (founder) + Claude (co-architect)
**Status:** Planning
**Companion doc:** `docglow-cloud-build-plan.md` (phased task list for Claude Code)

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Repo strategy | Separate `docglow-cloud` repo | Keep OSS clean; cloud users shouldn't download cloud-specific code |
| Code sharing | npm packages from OSS repo | Publish `@docglow/site-renderer`, `@docglow/health-scoring`, `@docglow/shared-types` |
| Hosting | Vercel (dashboard) + Cloudflare Workers (doc sites) | Both from day one; Cloudflare needed for wildcard subdomains |
| First upload method | `docglow push` CLI command | CLI already exists; fastest path to working upload flow |
| MVP scope | Phase 0–4 (scaffold → auth → upload → teams → billing) | Ship a chargeable product ASAP |

---

## 1. Executive Summary

Docglow Cloud is the hosted commercial tier of Docglow, an open-source CLI tool that generates modern documentation sites for dbt™ projects. The cloud product extends the OSS CLI with features that require a persistent service: hosted documentation sites published from CI/CD, AI-powered chat and documentation generation, a Slack bot for project Q&A, and historical health dashboards.

The core business thesis: 60,000+ teams use dbt Core without access to dbt Cloud's AI features, and the default `dbt docs serve` experience is widely considered inadequate. Docglow Cloud gives these teams a modern documentation and discovery layer at a fraction of what dbt Cloud costs, with unlimited models and unlimited viewers.

**Revenue model:** Workspace-based subscription ($49–$149/month) with usage-based pricing for AI queries and enrichments.

**Primary differentiator vs. Tributary Docs (Datacoves):** Unlimited models, unlimited viewers, Slack-native distribution, and a free open-source tier that serves as an organic acquisition funnel.

---

## 2. Target Users

### 2.1 Buyer Persona

Data engineering or analytics engineering leads at companies running dbt Core. Typically a Director or Senior Manager who controls tooling decisions for their team. They're frustrated that dbt Cloud's per-seat pricing makes AI features inaccessible to their broader org, or they're on dbt Core by choice and want best-in-class documentation without buying a full platform.

### 2.2 End Users

- **Analytics engineers** — publish docs from CI, review health scores, edit descriptions
- **Data analysts** — search the docs site, ask AI questions about models, use the Slack bot
- **Product managers / stakeholders** — browse the docs site to understand what data is available, ask the Slack bot plain-language questions
- **Data engineers** — review lineage, check test coverage, monitor health trends

### 2.3 Value Propositions by Tester Archetype

Two validated beta contacts represent the primary adoption paths:

**Path A (formerly dbt Cloud, limited licenses):** "We had dbt Cloud but could only afford 5 seats. 90% of the people who needed docs access couldn't get it." → Docglow Cloud's unlimited viewers solve this directly.

**Path B (dbt Core, strong engineering, limited dbt expertise):** "Our engineers are great at Python and infrastructure, but dbt is new to them. They need a way to understand the project without reading every SQL file." → AI chat + Slack bot make the project discoverable.

---

## 3. Infrastructure Architecture

### 3.1 Stack Recommendation

The architecture uses a **Supabase + Vercel** primary stack with **Cloudflare Workers** for edge doc-site serving. This combination optimizes for build speed at 2–5 hours/week while keeping infrastructure costs near zero at early scale.

| Layer | Service | Rationale |
|---|---|---|
| **Auth** | Supabase Auth | Magic links + Google OAuth out of the box. No auth code to write. |
| **Database** | Supabase Postgres | Full SQL, row-level security for multi-tenancy, pgvector for embeddings. |
| **Object storage** | Supabase Storage | Artifact uploads from CI. Signed URLs for private access. |
| **Vector search** | Supabase pgvector | Embeddings for RAG stored alongside relational data. No separate vector DB. |
| **Dashboard + API** | Vercel (Next.js) | React frontend (shared with OSS) + API routes. Josh has Vercel experience. |
| **Doc site serving** | Cloudflare Workers + R2 | Edge-speed static serving with wildcard subdomain routing. |
| **Background jobs** | Supabase Edge Functions + pg_cron | Artifact processing, embedding generation, health score computation. |
| **Billing** | Stripe Checkout + Billing | Subscription management, usage metering, webhooks. |
| **Transactional email** | Resend | Magic link emails, publish notifications, billing alerts. |
| **AI** | Anthropic Claude API | RAG-based chat, documentation generation, enrichments. |
| **Slack integration** | Slack API (Bot) | Slash commands + app mentions → same RAG pipeline as web chat. |

### 3.2 Why This Stack (vs. Alternatives)

**Why not all-Cloudflare (the original architecture)?**
The original `docglow-cloud-architecture.md` spec was all Cloudflare: Workers, R2, D1, Queues. This is the cheapest option at scale, but it means building auth (magic links, OAuth, session management, revocation) from scratch on Workers — easily 20+ hours of work. D1 is SQLite under the hood, which lacks pgvector for embeddings and row-level security for multi-tenancy. At 2–5 hours/week, the time cost of building auth and managing tenant isolation manually pushes the launch date out by months.

Cloudflare is still the best choice for the one thing it does better than anyone: serving static doc sites at the edge with wildcard subdomain routing. So it stays in the stack for that specific purpose.

**Why not all-Vercel?**
Vercel can host the frontend and API, but wildcard subdomains (`{workspace}.docglow.com`) require Vercel Enterprise. Path-based routing (`app.docglow.com/w/acme`) works on Vercel Pro ($20/mo) but feels less premium and is harder to share externally. Using Cloudflare Workers for doc site routing solves this cleanly.

**Why not Firebase?**
Firebase Auth and Firestore would work, but Firestore's NoSQL model is a poor fit for the relational queries this product needs (workspace → projects → models → columns → descriptions with joins against health scores and publish history). Postgres is the right database for this data model.

**Migration path:** If Docglow scales beyond what Supabase handles comfortably, the Postgres schema ports directly to AWS RDS/Aurora, Supabase Auth can be replaced with Auth0 or WorkOS, and Supabase Storage maps to S3. Nothing in this architecture creates vendor lock-in.

### 3.3 npm Package Strategy (OSS → Cloud Code Sharing)

The cloud repo (`docglow-cloud`) consumes shared logic from the OSS repo (`docglow`) via npm packages. This keeps the OSS repo free of cloud-specific code while avoiding duplication.

| Package | Source | Contents | Consumer |
|---------|--------|----------|----------|
| `@docglow/site-renderer` | OSS repo | React SPA build, `docglow-data.json` schema, static site generator | Cloud: artifact processing (Phase 2), Cloudflare Worker (Phase 3) |
| `@docglow/health-scoring` | OSS repo | Health score computation logic (docs, tests, naming, complexity) | Cloud: `compute-health` Edge Function (Phase 2) |
| `@docglow/shared-types` | OSS repo | TypeScript types for dbt artifacts, manifest/catalog schemas | Cloud: all packages and apps |

**Publishing workflow:**
1. OSS repo publishes packages to npm (scoped under `@docglow/`)
2. Cloud repo installs them as normal dependencies
3. OSS releases trigger a Renovate/Dependabot PR in the cloud repo
4. Breaking changes in OSS packages are caught by cloud CI before merge

**When to extract:** Start with `@docglow/shared-types` in Phase 0 (needed immediately). Extract `@docglow/site-renderer` and `@docglow/health-scoring` during Phase 2 when the cloud pipeline needs them.

### 3.4 High-Level System Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                        User's CI/CD Pipeline                         │
│                                                                      │
│   $ dbt build                                                        │
│   $ dbt docs generate                                                │
│   $ docglow publish --token $DOCGLOW_TOKEN                           │
└──────────────────┬───────────────────────────────────────────────────┘
                   │
                   │  POST /api/v1/publish (multipart: artifacts.tar.gz)
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     Vercel (Next.js)                                  │
│                                                                      │
│   Dashboard UI          API Routes                                   │
│   ─────────────         ───────────────────                          │
│   /login                /api/v1/publish     ──┐                      │
│   /dashboard            /api/v1/chat           │                     │
│   /settings             /api/v1/health         │                     │
│   /billing              /api/v1/webhooks       │                     │
│                         /api/v1/slack          │                     │
└─────────────────────────┬──────────────────────┘                     │
                          │                                             │
                          ▼                                             │
┌──────────────────────────────────────────────────────────────────────┐
│                        Supabase                                      │
│                                                                      │
│   Auth              Postgres (+ pgvector)     Storage                │
│   ──────            ─────────────────────     ───────                │
│   Magic links       workspaces                /artifacts/            │
│   Google OAuth      projects                    {workspace}/         │
│   Session mgmt      models + columns            {version}/          │
│                     embeddings (vector)                               │
│                     health_scores              /sites/               │
│                     publish_history              {workspace}/        │
│                     subscriptions                site files          │
│                     api_tokens                                       │
│                     slack_installations                               │
│                                                                      │
│   Edge Functions                                                     │
│   ──────────────                                                     │
│   process-artifacts   (unpack, parse, embed, generate site)          │
│   compute-health      (score calculation on publish)                 │
│   generate-embeddings (model/column text → vectors)                  │
└──────────────────────────────────────────────────────────────────────┘
                          │
                          │  (site files synced after processing)
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    Cloudflare                                         │
│                                                                      │
│   Workers (edge routing)              R2 (object store)              │
│   ──────────────────────              ─────────────────              │
│   {workspace}.docglow.com  ────────►  /sites/{workspace}/           │
│   - Resolve workspace                   index.html                   │
│   - Check auth (call Supabase)          docglow-data.json            │
│   - Serve from R2                       assets/                      │
│   - Handle 404s                                                      │
└──────────────────────────────────────────────────────────────────────┘

External Services:
─────────────────
  Stripe          → Subscription billing, usage metering
  Anthropic API   → Claude for RAG chat + doc generation
  Resend          → Transactional email (magic links, alerts)
  Slack API       → Bot integration (slash commands, app mentions)
```

### 3.4 Domain Structure

| Domain | Purpose |
|---|---|
| `docglow.com` | Marketing site + login |
| `app.docglow.com` | Dashboard (Vercel) |
| `{workspace}.docglow.com` | Customer doc sites (Cloudflare Workers → R2) |
| `api.docglow.com` | API endpoints (Vercel, proxied) |

---

## 4. Data Model

### 4.1 Core Tables (Supabase Postgres)

```sql
-- Workspace: the top-level tenant
CREATE TABLE workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT UNIQUE NOT NULL,           -- URL-safe, used in subdomain
    name TEXT NOT NULL,
    owner_id UUID REFERENCES auth.users(id),
    plan TEXT DEFAULT 'free',            -- free | starter | team | business
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    access_mode TEXT DEFAULT 'private',  -- public | private
    allowed_email_domain TEXT,           -- e.g., '@acme.com' for domain-wide access
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Project: a dbt project within a workspace (most workspaces have 1)
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    slug TEXT NOT NULL,
    name TEXT NOT NULL,
    dbt_version TEXT,
    last_published_at TIMESTAMPTZ,
    artifact_path TEXT,                  -- path in Supabase Storage
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(workspace_id, slug)
);

-- Workspace members: who can access the dashboard and manage settings
CREATE TABLE workspace_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id),
    role TEXT DEFAULT 'viewer',          -- owner | admin | viewer
    invited_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(workspace_id, user_id)
);

-- API tokens: for CI/CD publish
CREATE TABLE api_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,                  -- e.g., "GitHub Actions - production"
    token_hash TEXT NOT NULL,            -- bcrypt hash of the token
    token_prefix TEXT NOT NULL,          -- first 8 chars for identification
    last_used_at TIMESTAMPTZ,
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Publish history: every artifact upload
CREATE TABLE publish_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    artifact_path TEXT NOT NULL,         -- Supabase Storage path
    site_path TEXT,                      -- R2 path after processing
    model_count INTEGER,
    source_count INTEGER,
    status TEXT DEFAULT 'processing',    -- processing | complete | failed
    error_message TEXT,
    published_by TEXT,                   -- token name or user email
    published_at TIMESTAMPTZ DEFAULT now(),
    processed_at TIMESTAMPTZ
);

-- Health scores: one row per publish, stores the computed scores
CREATE TABLE health_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    publish_id UUID REFERENCES publish_history(id) ON DELETE CASCADE,
    overall_score NUMERIC(5,2),
    documentation_score NUMERIC(5,2),
    test_coverage_score NUMERIC(5,2),
    naming_score NUMERIC(5,2),
    complexity_score NUMERIC(5,2),
    details JSONB,                       -- per-model breakdown
    computed_at TIMESTAMPTZ DEFAULT now()
);

-- Model metadata: parsed from manifest, used for search and AI
CREATE TABLE models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    unique_id TEXT NOT NULL,             -- e.g., model.jaffle_shop.stg_orders
    name TEXT NOT NULL,
    resource_type TEXT NOT NULL,         -- model | source | seed | snapshot
    schema_name TEXT,
    description TEXT,
    raw_sql TEXT,
    compiled_sql TEXT,
    columns JSONB,                       -- array of {name, description, data_type, tests}
    depends_on JSONB,                    -- upstream node unique_ids
    tags TEXT[],
    meta JSONB,
    package_name TEXT,                   -- for filtering out dbt packages
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(project_id, unique_id)
);

-- Embeddings: vector representations of model/column metadata for RAG
CREATE TABLE embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    model_id UUID REFERENCES models(id) ON DELETE CASCADE,
    content_type TEXT NOT NULL,          -- model_description | column_description | sql
    content_text TEXT NOT NULL,          -- the text that was embedded
    embedding vector(1536),             -- OpenAI ada-002 or similar dimension
    created_at TIMESTAMPTZ DEFAULT now()
);

-- AI query log: for usage-based billing
CREATE TABLE ai_query_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id),
    source TEXT NOT NULL,                -- web_chat | slack_bot | api
    query_text TEXT NOT NULL,
    response_text TEXT,
    tokens_used INTEGER,
    model_used TEXT,                     -- claude-sonnet-4-20250514, etc.
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Slack installations: per-workspace Slack app installs
CREATE TABLE slack_installations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    slack_team_id TEXT NOT NULL,
    slack_team_name TEXT,
    bot_token TEXT NOT NULL,             -- encrypted at rest
    bot_user_id TEXT NOT NULL,
    installing_user_id UUID REFERENCES auth.users(id),
    default_project_id UUID REFERENCES projects(id),
    installed_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(workspace_id, slack_team_id)
);

-- Row-level security policies
ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspace_members ENABLE ROW LEVEL SECURITY;
-- ... (policies defined per table based on workspace membership)
```

### 4.2 Indexes

```sql
-- Vector similarity search
CREATE INDEX ON embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Common query patterns
CREATE INDEX idx_models_project ON models(project_id);
CREATE INDEX idx_health_scores_project ON health_scores(project_id, computed_at DESC);
CREATE INDEX idx_publish_history_project ON publish_history(project_id, published_at DESC);
CREATE INDEX idx_ai_query_log_workspace ON ai_query_log(workspace_id, created_at DESC);
CREATE INDEX idx_api_tokens_hash ON api_tokens(token_hash);
```

---

## 5. Core Features

### 5.1 Publish from CI/CD

The bridge between the open-source CLI and the hosted service. A single CI step uploads dbt artifacts and triggers site generation.

**CLI command:**
```bash
$ docglow publish --token $DOCGLOW_TOKEN
```

**Flow:**
1. CLI reads `target/manifest.json`, `target/catalog.json`, and optionally `target/run_results.json`
2. Compresses into `artifacts.tar.gz`
3. `POST /api/v1/publish` with Bearer token auth (multipart upload)
4. API validates token → resolves workspace + project → uploads to Supabase Storage
5. Returns `202 Accepted` with a `publish_id`
6. Supabase Edge Function triggers asynchronously:
   a. Unpack and parse artifacts
   b. Upsert model metadata into `models` table (filtering out package nodes)
   c. Generate embeddings for model/column descriptions and SQL
   d. Compute health scores
   e. Generate static site files (same renderer as OSS CLI)
   f. Upload site files to Cloudflare R2
   g. Update `publish_history` status to `complete`
7. CLI polls `/api/v1/publish/{id}/status` until complete (with timeout)

**GitHub Actions example:**
```yaml
- name: Publish to Docglow
  run: |
    pip install docglow
    docglow publish --token ${{ secrets.DOCGLOW_TOKEN }}
```

**Artifact processing considerations:**
- Filter out nodes where `package_name != project_name` (exclude dbt_utils, dbt_expectations, etc.)
- Parse `depends_on` to build the DAG for the lineage graph
- Extract column-level metadata from catalog.json
- Handle missing catalog.json gracefully (docs without column types)

**Artifact size limits and retention:**

| Constraint | Limit | Rationale |
|-----------|-------|-----------|
| Max upload size | 100 MB | Covers large dbt projects (1,000+ models); `manifest.json` + `catalog.json` rarely exceeds 50 MB even compressed |
| Artifact retention | 90 days (Starter), 1 year (Team/Business) | Matches health history retention per tier |
| Max publishes/day | 50 (all tiers) | Prevents runaway CI loops; typical teams publish 1–5x/day |
| Free tier storage | 500 MB total | Sufficient for ~10 publishes of a 50-model project |

Artifacts past the retention window are deleted by a scheduled `pg_cron` job. The latest version's artifacts are always retained regardless of age.

### 5.1.1 Publish Failure Notifications

When a publish fails (artifact processing error, size limit exceeded, plan limit hit), the user needs to know. Silent failures in CI are unacceptable.

**Notification channels:**
1. **CLI output:** The `docglow push` command polls for status and prints the error directly in the CI log
2. **Dashboard:** Failed publishes appear in the publish history with a red status badge and error message
3. **Email (optional):** Workspace owners can opt in to publish failure emails via workspace settings (sent via Resend)
4. **Webhook (future):** POST to a user-configured URL on publish success/failure — useful for Slack/PagerDuty integration. Not in MVP scope but the `publish_history` status field supports it.

### 5.2 Hosted Documentation Site

Each workspace gets a hosted version of the Docglow documentation site, served at `{workspace}.docglow.com`.

**The key insight:** The OSS CLI already generates a React frontend that reads from a `docglow-data.json` file. The hosted version serves the same frontend, but the JSON is generated from the Postgres metadata store instead of from local files. The frontend code is shared. This means OSS users are beta-testing the commercial frontend daily.

**Site serving (Cloudflare Worker):**
```
Request: https://acme.docglow.com
  │
  Worker:
  ├── Parse subdomain → workspace = "acme"
  ├── Look up workspace in cache (Workers KV) or Supabase
  ├── If access_mode = "public" → serve from R2 directly
  ├── If access_mode = "private":
  │   ├── Check session cookie (JWT signed by Supabase)
  │   ├── If no session → redirect to app.docglow.com/login?redirect=acme
  │   ├── If session valid → verify email domain or membership
  │   ├── If authorized → serve from R2
  │   └── If not authorized → 403 page
  └── If workspace not found → 404 page
```

**Features beyond OSS:**
- AI chat panel (calls `/api/v1/chat` with session auth)
- "Published X hours ago" indicator with link to publish history
- Health score badge in the header
- Private access with email domain or individual allowlist

### 5.3 AI Chat

AI-powered Q&A about the dbt project. Users ask natural language questions and get answers grounded in their project's actual metadata.

**RAG pipeline:**
1. User submits question via web chat or Slack
2. Generate embedding for the question using the same model used during indexing
3. Vector similarity search against `embeddings` table (cosine distance, top 10 results)
4. Construct prompt with retrieved context:
   - Model names, descriptions, column details
   - Relevant SQL snippets
   - Upstream/downstream dependencies
   - Test coverage information
5. Call Anthropic Claude API with the context-stuffed prompt
6. Stream response back to the user
7. Log the query in `ai_query_log` for usage billing

**System prompt template:**
```
You are a data documentation assistant for a dbt project called "{project_name}".
You answer questions about data models, their relationships, column definitions,
and how data flows through the pipeline.

Here is the relevant context from the project:

{retrieved_context}

Answer the user's question based on this context. If the context doesn't contain
enough information to answer confidently, say so. Always reference specific model
names and column names when relevant.
```

**Embedding model options:**
- OpenAI `text-embedding-3-small` (1536 dimensions, $0.02/1M tokens) — most widely used
- Anthropic's embedding via Voyager — check availability and pricing
- For MVP, OpenAI embeddings + Claude for generation is a pragmatic split

**Usage metering:**
- Count each AI query as one billable unit
- Log `tokens_used` from the Claude API response for cost tracking
- Stripe usage records updated daily via a scheduled function

### 5.4 Slack Bot

The primary adoption mechanism. Based on firsthand observation, an AI Analyst Slack integration reached 100 users in one week at Josh's current company. The Slack bot is how Docglow spreads beyond the data team.

**Slack app configuration:**
- Bot token scopes: `chat:write`, `app_mentions:read`, `commands`
- Slash command: `/docglow [question]`
- App mention: `@Docglow what does stg_orders contain?`
- Event subscription: `app_mention` events

**Flow:**
1. User types `/docglow what columns are in dim_customers?` in any Slack channel
2. Slack sends the event to `/api/v1/slack/events`
3. API verifies the Slack request signature
4. Looks up `slack_installations` to find the workspace and default project
5. Runs the same RAG pipeline as web chat (embed → search → prompt → generate)
6. Posts the response back to the Slack channel
7. Includes a "View in Docglow" link to the relevant model page

**Response format in Slack:**
```
📊 *dim_customers*
> A dimension table containing one row per customer, enriched with
> lifetime order metrics.

*Key columns:*
• `customer_id` — Primary key, unique customer identifier
• `first_order_date` — Date of the customer's first order
• `lifetime_value` — Total revenue attributed to this customer

*Upstream models:* stg_customers → stg_orders → stg_payments
*Test coverage:* 4 tests (unique, not_null on customer_id; accepted_values on status)

🔗 <https://acme.docglow.com/models/dim_customers|View in Docglow>
```

**Installation flow:**
1. Workspace admin clicks "Add to Slack" in the Docglow dashboard settings
2. Standard Slack OAuth flow → receive bot token
3. Store installation in `slack_installations` table
4. Admin selects which project the bot should answer about (if multi-project workspace)

### 5.5 Health Dashboard with History

Extends the OSS CLI's health scoring with historical tracking, trend visualization, and team-level insights.

**Dashboard views:**
- **Current health score** with breakdown by category (documentation, tests, naming, complexity)
- **Health trend chart** — line chart showing overall and per-category scores over time (one data point per publish)
- **Worst offenders** — models with the lowest individual scores, sorted by impact
- **Category deep-dives** — click into "documentation coverage" to see every undocumented model/column
- **Diff view** — "what changed since last publish?" showing models added, removed, or modified

**Health score computation** runs as part of the publish processing pipeline. The same scoring logic from the OSS CLI is reused server-side, with results stored in the `health_scores` table.

**API endpoints:**
- `GET /api/v1/projects/{id}/health/current` — latest scores
- `GET /api/v1/projects/{id}/health/history?since=30d` — historical data
- `GET /api/v1/projects/{id}/health/details` — per-model breakdown

---

## 6. Authentication & Authorization

### 6.1 Auth Flows

**Magic link (all tiers):**
- User enters email at `app.docglow.com/login`
- Supabase Auth sends a magic link via Resend
- User clicks link → Supabase creates session → redirect to dashboard
- For doc site access: session cookie is set on `.docglow.com` domain

**Google OAuth (all tiers):**
- "Sign in with Google" button on login page
- Standard OAuth 2.0 via Supabase Auth
- Workspace admin can restrict access to a specific Google Workspace domain

**Future: SAML SSO (Business tier):**
- Integrate via WorkOS ($0.50/user/month) when enterprise customers require it
- Don't build until needed

### 6.2 Authorization Model

```
Workspace Owner  → full control (billing, settings, members, tokens)
Workspace Admin  → manage members, tokens, projects; no billing access
Workspace Viewer → view docs site, use AI chat, use Slack bot

Doc Site Access:
  - Public workspace  → anyone with the URL
  - Private workspace → authenticated users whose email matches:
    - The workspace's allowed_email_domain, OR
    - An explicit entry in workspace_members
```

**Unlimited viewers:** The pricing model promises unlimited viewers. This means no seat tracking for doc site access. The `workspace_members` table is for dashboard/admin access only. Doc site access is controlled by email domain matching — if your company email ends in `@acme.com` and the workspace allows `@acme.com`, you're in.

### 6.3 API Token Auth

For CI/CD publish endpoints, authentication uses project-scoped API tokens.

- Tokens are generated in the dashboard: `dg_live_aBcDeFgH...` (prefix for identification)
- Only the bcrypt hash is stored; the raw token is shown once at creation
- Tokens are scoped to a specific project within a workspace
- Token auth is only valid for `/api/v1/publish` — dashboard and chat require session auth

---

## 7. Pricing & Billing

### 7.1 Tier Structure

| | Free | Starter ($49/mo) | Team ($99/mo) | Business ($149/mo) |
|---|---|---|---|---|
| Projects | 1 | 1 | 3 | 10 |
| Models | 50 | Unlimited | Unlimited | Unlimited |
| Viewers | Unlimited | Unlimited | Unlimited | Unlimited |
| Doc site | Public only | Public or private | Private + custom domain | Private + custom domain |
| AI queries/mo | 0 | 100 | 500 | 2,000 |
| Additional AI queries | — | $0.10 each | $0.08 each | $0.05 each |
| Slack bot | No | No | Yes | Yes |
| Health dashboard | Current only | Current + 30 days | Current + 90 days | Current + 1 year |
| AI doc generation | No | No | Yes | Yes |
| SSO/SAML | No | No | No | Yes |
| Support | Community | Email | Email (priority) | Email + Slack |

### 7.2 Billing Implementation

- **Stripe Checkout** for initial subscription
- **Stripe Billing** for recurring charges
- **Stripe Usage Records** for AI query overages (metered billing, reported daily)
- **Stripe Customer Portal** for self-service plan changes, payment method updates, invoice history
- **Stripe Webhooks** → `/api/v1/webhooks/stripe` → update `workspaces.plan` and `subscriptions` in Postgres

### 7.3 Free Tier Rationale

The free tier exists to convert OSS users into cloud users. The friction-free path: install the CLI, generate docs, like it, want to share it with the team → sign up for free → hit the 50-model limit or want private access → upgrade to Starter.

---

## 8. AI Documentation Generation (Team+ Tier)

Beyond answering questions, the AI can generate documentation for undocumented models and columns.

**Flow:**
1. User clicks "Generate descriptions" on a model page (or bulk-select on the health dashboard)
2. API sends model SQL, column names, upstream/downstream context to Claude
3. Claude generates business-friendly descriptions for the model and each column
4. Descriptions are shown in a review modal — user can edit before accepting
5. On accept, a PR is created on the connected GitHub repo updating the relevant `schema.yml`

**GitHub integration:**
- Workspace admin connects their GitHub repo in settings (OAuth app, not personal token)
- When descriptions are accepted, Docglow creates a branch and PR with the updated YAML
- This keeps the source of truth in version control, not in Docglow's database

**Billing:** Each model enrichment counts as 1 AI query for usage metering purposes.

---

## 9. Infrastructure Cost Estimates

### At 0 paying customers (development):

| Service | Monthly Cost |
|---|---|
| Supabase (free tier: 500MB DB, 1GB storage, 50K MAU auth) | $0 |
| Vercel (Hobby: personal projects) | $0 |
| Cloudflare Workers (free tier: 100K req/day) | $0 |
| Cloudflare R2 (free tier: 10GB storage) | $0 |
| docglow.com domain | ~$12/year |
| Resend (free tier: 3K emails/month) | $0 |
| **Total** | **~$1/month** |

### At 20 paying customers (~$1.5K MRR):

| Service | Monthly Cost |
|---|---|
| Supabase Pro ($25/mo: 8GB DB, 100GB storage) | $25 |
| Vercel Pro ($20/mo) | $20 |
| Cloudflare Workers Paid ($5/mo + usage) | ~$7 |
| Cloudflare R2 (~20GB) | ~$3 |
| Anthropic API (AI chat + enrichments) | ~$50 |
| Resend (paid tier) | $20 |
| Stripe fees (2.9% + $0.30) | ~$50 |
| **Total** | **~$175/month** |
| **Margin** | **~88%** |

### At 100 paying customers (~$8K MRR):

| Service | Monthly Cost |
|---|---|
| Supabase Pro (scaled) | $75 |
| Vercel Pro | $20 |
| Cloudflare Workers | ~$15 |
| Cloudflare R2 (~100GB) | ~$10 |
| Anthropic API | ~$200 |
| Resend | $40 |
| Stripe fees | ~$250 |
| **Total** | **~$610/month** |
| **Margin** | **~92%** |

---

## 10. Security Considerations

### 10.1 Data Isolation

- **Row-level security (RLS)** on all Supabase tables ensures users can only access data belonging to their workspace
- **Storage buckets** are organized by workspace ID with Supabase Storage policies
- **R2 paths** are namespaced by workspace slug; the Cloudflare Worker enforces access
- **API tokens** are scoped to a specific project — a token for Project A cannot publish to Project B

### 10.2 Secrets Management

- Slack bot tokens: encrypted at rest in Postgres (Supabase encryption)
- API tokens: only bcrypt hashes stored; raw tokens shown once at creation
- Stripe keys: stored as Vercel environment variables, never in code
- Anthropic API key: stored as Vercel environment variable

### 10.3 Compliance

- No PII beyond email addresses and names (from OAuth)
- dbt metadata (model names, SQL, descriptions) is the customer's IP — treat it accordingly
- Data deletion on workspace cancellation: 30-day grace period, then full deletion
- Privacy Policy and ToS generated via Termly/TermsFeed, customized for Docglow's data flows

---

## 11. Local Development Environment

All services must be runnable locally without cloud accounts. This is critical for a 2–5 hr/week development cadence — zero time should be spent debugging cloud config when you could be writing features.

### 11.1 Local Stack

| Service | Local Tool | Setup |
|---------|-----------|-------|
| Supabase (Auth, DB, Storage) | `supabase start` (Docker) | `supabase/config.toml` in cloud repo; runs Postgres, Auth, Storage, Edge Functions locally |
| Vercel (Next.js) | `next dev` | Standard Next.js dev server on `localhost:3000` |
| Cloudflare Worker | `wrangler dev` | Miniflare local runtime; R2 emulated with local filesystem |
| Stripe | `stripe listen --forward-to localhost:3000/api/v1/webhooks/stripe` | Stripe CLI forwards test webhooks to local API |
| Resend | Mock/console logger | In dev mode, emails print to console instead of sending |
| Anthropic API | Real API with test key | No local substitute needed; use a low-cost model (Haiku) for dev |

### 11.2 Dev Bootstrap

A single command should bring up the full local stack:

```bash
# In the cloud repo root
pnpm dev:setup    # Install deps, pull Supabase Docker images, seed DB
pnpm dev          # Starts: next dev + wrangler dev + supabase start (via Turbo)
```

### 11.3 Seed Data

A `supabase/seed.sql` file creates:
- A test workspace (`acme-analytics`) with owner user
- A test project with a jaffle_shop publish
- Pre-computed health scores and a few embeddings
- An API token for local testing (`dg_live_test_localdev...`)

This ensures the dashboard has data to render immediately after `pnpm dev`.

---

## 12. Open Questions

1. **Embedding model choice:** OpenAI `text-embedding-3-small` is the pragmatic default, but using Anthropic for both embeddings and generation would simplify the vendor relationship. Check if Anthropic offers a production embedding API at competitive pricing.

2. **Supabase Edge Functions vs. Vercel serverless for artifact processing:** Edge Functions run on Deno and have a 150-second timeout. Large dbt projects (1,000+ models) may need longer processing. Alternative: trigger a Vercel serverless function (which has a 5-minute timeout on Pro) for heavy processing, or use Supabase's `pg_net` to call an external endpoint.

3. **Real-time updates after publish:** Should the dashboard auto-update when a new publish completes? Supabase Realtime (Postgres changes → WebSocket) makes this easy but adds complexity. Polling is simpler for MVP.

4. **Multi-project workspaces:** The data model supports them, but the MVP could ship with single-project workspaces only and add multi-project later for the Team tier.

5. **Custom domains for doc sites:** Requires Cloudflare for SaaS, which is $2/month per custom domain. Worth supporting at the Business tier but not at launch.

---

## 13. Success Metrics

| Metric | Target (6 months post-launch) |
|---|---|
| Paying workspaces | 20+ |
| MRR | $2,000+ |
| Publish events/week (across all customers) | 100+ |
| AI queries/week | 500+ |
| Slack bot installations | 10+ |
| OSS → Cloud conversion rate | 5%+ |
| Churn rate (monthly) | <5% |

---

## 14. Non-Goals (for MVP)

- Column-level lineage (dbt Docs also lacks it — parity is fine for now)
- SAML/SSO (build when an enterprise customer needs it)
- Custom domains for doc sites (Business tier, post-MVP)
- Mobile app
- Self-hosted cloud option
- Workspace-to-workspace sharing
- Audit logging (add when enterprise customers need SOC 2)

---

*This PRD is the planning document. See `docglow-cloud-build-plan.md` for the phased implementation plan optimized for Claude Code handoff.*
