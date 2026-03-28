# Docglow Cloud — Build Plan

**Companion to:** `docglow-cloud-prd.md`
**Version:** 1.1 (updated March 26, 2026)
**Structure:** Each phase is a self-contained unit of work with clear inputs, outputs, and acceptance criteria. Phases are designed for handoff to Claude Code sub-agents.

### Architecture Decisions (locked in)

- **Separate repo:** `docglow-cloud` — cloud-specific code stays out of the OSS repo
- **Code sharing:** npm packages (`@docglow/shared-types`, `@docglow/site-renderer`, `@docglow/health-scoring`)
- **Hosting:** Vercel (dashboard) + Cloudflare Workers (doc sites) from day one
- **MVP scope:** Phase 0–4 (scaffold → auth → publish → doc sites → billing)
- **First upload method:** `docglow push` CLI command

---

## Phase 0: Project Scaffolding + Local Dev Environment

**Goal:** Set up the separate cloud repo, local development stack, npm package scaffolding, and CI/CD so that all subsequent phases have infrastructure to build and deploy against.

**Estimated effort:** 10–14 hours (this is the foundation — spending time here saves time everywhere else)

### Task 0.1: Repo + Monorepo Setup

Create a new `docglow-cloud` repo (separate from the OSS `docglow` repo).

```
docglow-cloud/
├── apps/
│   ├── web/                    # Next.js dashboard (Vercel)
│   │   ├── src/
│   │   │   ├── app/            # App Router pages
│   │   │   ├── components/     # React components
│   │   │   ├── lib/            # Supabase client, utils
│   │   │   └── styles/
│   │   ├── next.config.js
│   │   ├── package.json
│   │   └── tsconfig.json
│   └── worker/                 # Cloudflare Worker (doc site serving)
│       ├── src/
│       │   └── index.ts
│       ├── wrangler.toml
│       └── package.json
├── packages/
│   └── shared/                 # Cloud-specific shared types, constants
│       ├── src/
│       │   ├── types.ts        # Re-exports @docglow/shared-types + cloud-only types
│       │   └── constants.ts
│       └── package.json
├── supabase/
│   ├── migrations/             # SQL migration files
│   ├── functions/              # Edge Functions
│   │   ├── process-artifacts/
│   │   └── compute-health/
│   ├── seed.sql                # Local dev seed data
│   └── config.toml
├── .github/
│   └── workflows/
│       ├── ci.yml              # Lint, type-check, test on every PR
│       └── deploy.yml          # Deploy to Vercel + Cloudflare on merge to main
├── scripts/
│   └── dev-setup.sh            # One-command local bootstrap
├── turbo.json                  # Turborepo config
├── package.json
├── .env.example                # Template for all required env vars
└── README.md
```

**Actions:**
1. Create `docglow-cloud` repo on GitHub
2. Initialize the monorepo with Turborepo + pnpm workspaces
3. Create the Next.js app in `apps/web/` with App Router, TypeScript, Tailwind CSS
4. Create the Cloudflare Worker project in `apps/worker/` with Wrangler
5. Create the cloud-specific shared package in `packages/shared/`
6. Install `@docglow/shared-types` from npm (publish from OSS repo first — see Task 0.5)
7. Initialize the Supabase project directory with `supabase init`

**Acceptance criteria:**
- `pnpm install` succeeds from root
- `pnpm dev` starts Next.js + Wrangler + Supabase concurrently (via Turbo)
- `pnpm build` succeeds for all apps/packages
- `pnpm lint` and `pnpm typecheck` pass

### Task 0.2: Local Development Stack

Set up all services to run locally without any cloud accounts.

**Local services:**

| Service | Local Tool | Command |
|---------|-----------|---------|
| Supabase (Auth, DB, Storage) | Docker via `supabase start` | Postgres on `localhost:54322`, Auth on `localhost:54321` |
| Next.js dashboard | `next dev` | `localhost:3000` |
| Cloudflare Worker | `wrangler dev --local` | `localhost:8787` (Miniflare; R2 emulated on local filesystem) |
| Stripe webhooks | `stripe listen --forward-to localhost:3000/api/v1/webhooks/stripe` | Forwards test events to local API |
| Email (Resend) | Console logger mock | In dev mode, emails log to terminal instead of sending |

**Dev bootstrap script (`scripts/dev-setup.sh`):**
```bash
#!/bin/bash
set -e
pnpm install
supabase start                    # Pull Docker images, start local Supabase
supabase db reset                 # Run migrations + seed data
cp .env.example apps/web/.env.local  # Pre-fill with local Supabase URLs
echo "✓ Ready. Run 'pnpm dev' to start all services."
```

**Turbo `dev` pipeline runs concurrently:**
- `apps/web`: `next dev`
- `apps/worker`: `wrangler dev --local`
- (Supabase is expected to already be running via `supabase start`)

**Acceptance criteria:**
- `./scripts/dev-setup.sh && pnpm dev` brings up the full stack from a fresh clone
- Auth magic links work locally (Supabase Inbucket email viewer at `localhost:54324`)
- Worker responds at `localhost:8787` and can read from local R2 emulation
- Stripe CLI forwards `checkout.session.completed` events to local webhook handler
- No cloud accounts required for any of the above

### Task 0.3: Supabase Schema + Seed Data

**Migration file:** `supabase/migrations/001_initial_schema.sql`
- Full schema from PRD Section 4.1
- RLS policies for each table
- Indexes from PRD Section 4.2
- `CREATE EXTENSION IF NOT EXISTS vector;`

**Seed file:** `supabase/seed.sql`
- Test user (`test@docglow.com`)
- Test workspace (`acme-analytics`, slug: `acme-analytics`)
- Test project with jaffle_shop metadata
- Pre-computed health scores (2 publishes with different scores for trend testing)
- A handful of embeddings (enough to test vector search)
- API token for local testing: `dg_live_test_localdev_xxxxxxxxxxxxxxxx`

**Acceptance criteria:**
- `supabase db reset` runs migrations + seed without errors
- Local Supabase running with all tables created
- RLS policies prevent cross-workspace data access (test with a second workspace in seed)
- Seed data provides enough content for all dashboard views

### Task 0.4: Environment Configuration

**`.env.example`** (single source of truth, documented):
```bash
# === Supabase (local defaults pre-filled) ===
NEXT_PUBLIC_SUPABASE_URL=http://localhost:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=<from supabase start output>
SUPABASE_SERVICE_ROLE_KEY=<from supabase start output>

# === Cloudflare (only needed for deployed environments) ===
CLOUDFLARE_ACCOUNT_ID=
CLOUDFLARE_API_TOKEN=
R2_BUCKET_NAME=docglow-sites

# === Stripe (use test mode keys) ===
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...  # From `stripe listen` output
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...

# === Anthropic (real key, use Haiku for cheap local dev) ===
ANTHROPIC_API_KEY=sk-ant-...

# === Resend (optional — dev mode logs to console) ===
RESEND_API_KEY=

# === App URLs ===
NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_DOCS_DOMAIN=localhost:8787
```

**`apps/worker/wrangler.toml`:**
```toml
name = "docglow-sites"
main = "src/index.ts"
compatibility_date = "2024-01-01"

[vars]
SUPABASE_URL = "http://localhost:54321"

[[r2_buckets]]
binding = "SITES_BUCKET"
bucket_name = "docglow-sites"

[dev]
port = 8787
local_protocol = "http"
```

**Acceptance criteria:**
- `.env.example` documents every env var with comments
- `apps/web/.env.local` (gitignored) works with local Supabase out of the box after `dev-setup.sh`
- No secrets committed to the repo

### Task 0.5: OSS npm Package Extraction

In the **OSS `docglow` repo**, extract shared code into publishable packages.

**Phase 0 deliverable (minimum):** `@docglow/shared-types`
- TypeScript types for dbt manifest, catalog, run_results schemas
- Shared constants (plan tiers, health score thresholds)
- Publish to npm under the `@docglow` scope

**Phase 2 deliverables (when needed):**
- `@docglow/site-renderer` — React SPA build + static site generator
- `@docglow/health-scoring` — Health score computation logic

**Publishing approach:**
- Use `tsup` for building, `changesets` for versioning
- Publish from a GitHub Action on tagged release in the OSS repo
- Cloud repo pins to specific versions (no `^` ranges)

**Acceptance criteria:**
- `@docglow/shared-types` published to npm and installable in the cloud repo
- Types are used in both `apps/web` and `apps/worker`
- TypeScript strict mode passes with the shared types

### Task 0.6: CI/CD Pipeline

**`.github/workflows/ci.yml`** (runs on every PR):
```yaml
jobs:
  lint-and-typecheck:
    - pnpm install
    - pnpm lint
    - pnpm typecheck
  test:
    - pnpm test
  supabase-migration-check:
    - supabase start
    - supabase db reset  # Verify migrations apply cleanly
```

**`.github/workflows/deploy.yml`** (runs on merge to `main`):
```yaml
jobs:
  deploy-web:
    # Vercel auto-deploys from GitHub — this job is a placeholder
    # for any post-deploy smoke tests
  deploy-worker:
    - wrangler deploy
```

**Acceptance criteria:**
- PRs cannot merge with lint/type/test failures
- Supabase migrations are verified on every PR
- Merge to `main` triggers deployment to Vercel + Cloudflare

---

## Phase 1: Auth + Workspace Creation

**Goal:** Users can sign up, create a workspace, and see an empty dashboard. This is the foundation everything else builds on.

### Task 1.1: Login Page

**File:** `apps/web/src/app/login/page.tsx`

Build a login page with:
- Email input + "Send magic link" button
- "Sign in with Google" button
- Supabase Auth client handles both flows
- On successful auth → redirect to `/dashboard`
- If user has no workspace → redirect to `/onboarding`

**Supabase client setup:**
```typescript
// apps/web/src/lib/supabase/client.ts
import { createBrowserClient } from '@supabase/ssr'

export const createClient = () =>
  createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  )
```

**Server-side client for API routes:**
```typescript
// apps/web/src/lib/supabase/server.ts
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export const createClient = () => {
  const cookieStore = cookies()
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { cookies: { /* cookie handlers */ } }
  )
}
```

**Acceptance criteria:**
- Magic link login works end-to-end (send email → click → logged in)
- Google OAuth login works end-to-end
- Unauthenticated users are redirected to `/login`
- Session persists across page refreshes

### Task 1.2: Onboarding Flow

**File:** `apps/web/src/app/onboarding/page.tsx`

After first login, user creates their workspace:
1. Enter workspace name (e.g., "Acme Analytics")
2. Auto-generate slug from name (e.g., "acme-analytics")
3. Allow editing the slug (validate: lowercase, alphanumeric + hyphens, unique)
4. "Create workspace" → insert into `workspaces` table + `workspace_members` (role: owner)
5. Redirect to `/dashboard`

**Validation:**
- Slug must be 3-40 characters, lowercase alphanumeric + hyphens
- Slug must be unique (check against `workspaces` table)
- Reserved slugs: `www`, `app`, `api`, `admin`, `login`, `docs`, `help`, `support`, `status`

**Acceptance criteria:**
- Workspace created with correct owner
- Slug uniqueness enforced
- Reserved slugs rejected
- Owner added to `workspace_members` with `owner` role

### Task 1.3: Dashboard Shell

**File:** `apps/web/src/app/dashboard/page.tsx`

Build the dashboard layout:
- Sidebar: workspace name, navigation (Overview, Health, Settings)
- Main content area: "No project yet — publish your first dbt project" empty state
- User dropdown in header: email, sign out
- Responsive layout (sidebar collapses on mobile)

**Acceptance criteria:**
- Dashboard loads for authenticated users
- Shows workspace name and user email
- Empty state is clear and actionable
- Sign out works

---

## Phase 2: Publish Pipeline

**Goal:** `docglow publish` uploads artifacts from CI, triggers processing, and stores parsed metadata. No site serving yet — just the data pipeline.

### Task 2.1: API Token Management

**Files:**
- `apps/web/src/app/dashboard/settings/tokens/page.tsx` (UI)
- `apps/web/src/app/api/v1/tokens/route.ts` (API)

**UI:**
- "Create token" button → modal with name input and project selector
- Show token ONCE after creation in a copyable text box
- Token list showing: name, prefix (`dg_live_aBcD...`), created by, last used, delete button

**API:**
- `POST /api/v1/tokens` — generate token, store bcrypt hash, return raw token
- `DELETE /api/v1/tokens/{id}` — delete token
- `GET /api/v1/tokens` — list tokens (without hashes)

**Token format:** `dg_live_` + 32 random alphanumeric characters

**Acceptance criteria:**
- Tokens can be created, listed, and deleted
- Raw token shown only once at creation
- Token works for authentication on the publish endpoint (Task 2.2)
- Deleting a token immediately invalidates it

### Task 2.2: Publish Endpoint

**File:** `apps/web/src/app/api/v1/publish/route.ts`

**Request:**
```
POST /api/v1/publish
Authorization: Bearer dg_live_aBcDeFgH...
Content-Type: multipart/form-data

Body: artifacts.tar.gz
```

**Handler logic:**
1. Extract token from Authorization header
2. Hash the token → look up in `api_tokens` table
3. If not found → 401
4. Resolve workspace and project from the token
5. Check workspace plan allows publishing (model count check on free tier)
6. Upload `artifacts.tar.gz` to Supabase Storage: `artifacts/{workspace_id}/{version}/`
7. Insert row into `publish_history` (status: `processing`)
8. Trigger artifact processing (Supabase Edge Function or background job)
9. Return `202 Accepted` with `{ publish_id, status_url }`

**Status polling endpoint:**
```
GET /api/v1/publish/{publish_id}/status
→ { status: "processing" | "complete" | "failed", error_message?: string }
```

**Acceptance criteria:**
- Publish endpoint accepts artifact uploads with valid token
- Invalid tokens return 401
- Artifacts stored in Supabase Storage with correct path
- Publish history row created
- Status endpoint returns current processing status

### Task 2.3: CLI `publish` Command

**File:** Add to the existing `docglow` Python CLI (in the OSS repo)

```python
# src/docglow/commands/publish.py

@click.command()
@click.option('--token', envvar='DOCGLOW_TOKEN', required=True)
@click.option('--target', default='target', help='Path to dbt target directory')
@click.option('--api-url', default='https://api.docglow.com', envvar='DOCGLOW_API_URL')
def publish(token, target, api_url):
    """Publish dbt artifacts to Docglow Cloud."""
    # 1. Validate target/ directory has required files
    # 2. Create artifacts.tar.gz (manifest.json, catalog.json, run_results.json)
    # 3. POST to {api_url}/api/v1/publish
    # 4. Poll status until complete or timeout (60s)
    # 5. Print result with link to docs site
```

**Acceptance criteria:**
- `docglow publish --token $TOKEN` works against the deployed API
- Clear error messages for: missing target dir, invalid token, upload failure
- Shows progress and final URL on success
- Works in GitHub Actions, GitLab CI, and local terminal

### Task 2.4: Artifact Processing

**File:** `supabase/functions/process-artifacts/index.ts`

This is the most complex task. When triggered by a publish event:

1. Download `artifacts.tar.gz` from Supabase Storage
2. Unpack and parse:
   - `manifest.json` → extract nodes (models, sources, seeds, snapshots)
   - `catalog.json` → extract column types and stats
   - `run_results.json` → extract test results and timing (if present)
3. Filter out package nodes: skip any node where `package_name != project_name`
4. Upsert into `models` table:
   - For each node: name, description, SQL, columns, depends_on, tags, meta
   - DELETE models that existed in the previous publish but not in this one
5. Generate embeddings:
   - For each model: embed `"{name}: {description}. Columns: {column_names_and_descriptions}"`
   - For models with SQL: embed a truncated version of the compiled SQL
   - Use OpenAI `text-embedding-3-small` API
   - Upsert into `embeddings` table
6. Compute health scores:
   - Reuse the scoring logic from the OSS CLI
   - Insert into `health_scores` table
7. Generate static site files:
   - Build the `docglow-data.json` from the parsed metadata
   - Copy the OSS frontend build files
   - Upload everything to Cloudflare R2 at `/sites/{workspace_slug}/`
8. Update `publish_history` status to `complete`

**Important considerations:**
- Supabase Edge Functions have a 150-second timeout. For large projects (1,000+ models), this may not be enough. Consider splitting into multiple function calls: parse → embed → generate site.
- Embedding generation is the slowest step. Batch embed requests (OpenAI supports up to 2,048 inputs per request).
- If the function fails, update `publish_history` status to `failed` with the error message.

**Acceptance criteria:**
- jaffle_shop project processes successfully end-to-end
- Models table contains all expected nodes (no package nodes)
- Embeddings generated for all models
- Health scores computed and stored
- Site files uploaded to R2
- Status updated to `complete`
- Failed processing sets status to `failed` with error message

---

## Phase 3: Doc Site Serving

**Goal:** `{workspace}.docglow.com` serves the customer's documentation site with authentication.

### Task 3.1: Cloudflare Worker for Site Routing

**File:** `apps/worker/src/index.ts`

```typescript
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const hostname = url.hostname;

    // Extract workspace slug from subdomain
    // e.g., "acme.docglow.com" → "acme"
    const parts = hostname.split('.');
    if (parts.length < 3) return new Response('Not found', { status: 404 });
    const workspaceSlug = parts[0];

    // Skip known subdomains
    if (['app', 'api', 'www'].includes(workspaceSlug)) {
      return new Response('Not found', { status: 404 });
    }

    // Look up workspace (cache in Workers KV for performance)
    const workspace = await getWorkspace(workspaceSlug, env);
    if (!workspace) return new Response('Workspace not found', { status: 404 });

    // Auth check for private workspaces
    if (workspace.access_mode === 'private') {
      const session = await validateSession(request, env);
      if (!session) {
        return Response.redirect(
          `https://app.docglow.com/login?redirect=${workspaceSlug}`
        );
      }
      if (!isAuthorized(session, workspace)) {
        return new Response('Forbidden', { status: 403 });
      }
    }

    // Serve from R2
    const path = url.pathname === '/' ? '/index.html' : url.pathname;
    const object = await env.SITES_BUCKET.get(`sites/${workspaceSlug}${path}`);
    if (!object) {
      // SPA fallback: serve index.html for client-side routing
      const fallback = await env.SITES_BUCKET.get(`sites/${workspaceSlug}/index.html`);
      if (!fallback) return new Response('Not found', { status: 404 });
      return new Response(fallback.body, {
        headers: { 'Content-Type': 'text/html' },
      });
    }

    return new Response(object.body, {
      headers: {
        'Content-Type': getContentType(path),
        'Cache-Control': 'public, max-age=3600',
      },
    });
  },
};
```

**DNS setup:**
- Wildcard DNS record: `*.docglow.com` → Cloudflare Worker route
- Worker route: `*.docglow.com/*` → `docglow-sites` worker

**Acceptance criteria:**
- `acme.docglow.com` serves the correct site from R2
- Public workspaces accessible without auth
- Private workspaces redirect to login
- SPA client-side routing works (all paths serve index.html)
- Unknown workspaces return 404
- `app.docglow.com` and `api.docglow.com` are not intercepted

### Task 3.2: Session Sharing Between Vercel and Cloudflare

The Cloudflare Worker needs to validate Supabase session cookies. Since the cookie is set on `.docglow.com`, it's available to both `app.docglow.com` (Vercel) and `{workspace}.docglow.com` (Cloudflare Worker).

**Approach:**
- Supabase sets the session cookie on the `.docglow.com` domain
- The Cloudflare Worker reads the cookie and validates the JWT using Supabase's JWT secret
- No need to call Supabase on every request — JWT validation is local
- Cache workspace metadata in Workers KV (TTL: 5 minutes) to avoid Supabase lookups on every request

**Acceptance criteria:**
- Login at `app.docglow.com` → cookie set on `.docglow.com`
- Navigate to `acme.docglow.com` → Worker reads the cookie → site served
- Expired/invalid JWT → redirect to login
- Workspace access rules enforced (email domain matching)

---

## Phase 4: AI Chat

**Goal:** Users can ask natural language questions about their dbt project from the hosted docs site.

### Task 4.1: Chat API Endpoint

**File:** `apps/web/src/app/api/v1/chat/route.ts`

```typescript
// POST /api/v1/chat
// Body: { project_id: string, message: string }
// Response: Streamed text (SSE)

export async function POST(request: Request) {
  // 1. Authenticate (session cookie)
  // 2. Validate workspace has AI queries remaining (plan check)
  // 3. Embed the user's question
  // 4. Vector similarity search in embeddings table (top 10)
  // 5. Fetch full model metadata for matched results
  // 6. Construct prompt with context
  // 7. Call Anthropic Claude API (streaming)
  // 8. Stream response back to client
  // 9. Log query in ai_query_log
  // 10. Update usage meter for billing
}
```

**Context construction:**
```typescript
function buildContext(matches: ModelMatch[]): string {
  return matches.map(m => `
Model: ${m.name} (${m.resource_type})
Description: ${m.description || 'No description'}
Schema: ${m.schema_name}
Columns: ${m.columns.map(c => `${c.name} (${c.data_type}): ${c.description || 'no description'}`).join(', ')}
Upstream: ${m.depends_on.join(', ')}
Tags: ${m.tags.join(', ')}
  `).join('\n---\n');
}
```

**Acceptance criteria:**
- Chat endpoint returns streamed responses
- Responses are grounded in actual project metadata
- Plan limits enforced (error message when AI queries exhausted)
- Queries logged for billing
- Handles edge cases: empty project, no embeddings, no relevant matches

### Task 4.2: Chat UI Component

**File:** `apps/web/src/components/chat/ChatPanel.tsx`

Add a chat panel to the hosted docs site (slide-out from the right side or bottom bar):
- Text input with send button
- Streaming message display (tokens appear as they arrive)
- Message history within the session
- "X of Y AI queries used this month" indicator
- Model name links in responses that navigate to the model page

**Acceptance criteria:**
- Chat panel opens/closes smoothly
- Messages stream in real-time
- Previous messages in session are preserved
- Usage counter updates after each query
- Model names in responses are clickable links

---

## Phase 5: Slack Bot

**Goal:** Teams can ask questions about their dbt project directly in Slack.

### Task 5.1: Slack App Configuration

1. Create a Slack app at api.slack.com
2. Configure bot token scopes: `chat:write`, `app_mentions:read`, `commands`
3. Add slash command: `/docglow`
4. Add event subscription for `app_mention`
5. Set request URL to `https://api.docglow.com/api/v1/slack/events`
6. Enable OAuth distribution (for multi-workspace installation)

### Task 5.2: Slack OAuth Installation Flow

**Files:**
- `apps/web/src/app/dashboard/settings/slack/page.tsx` (UI)
- `apps/web/src/app/api/v1/slack/oauth/route.ts` (OAuth callback)

**Flow:**
1. Dashboard settings page shows "Add to Slack" button (Slack's official button markup)
2. Button links to Slack's OAuth authorization URL with state parameter (workspace_id)
3. User authorizes → Slack redirects to callback URL
4. Callback exchanges code for bot token
5. Store installation in `slack_installations` table
6. Redirect to dashboard settings with success message

**Acceptance criteria:**
- "Add to Slack" button initiates OAuth flow
- Bot token stored securely after authorization
- Installation visible in dashboard settings
- "Remove from Slack" button revokes token and deletes installation

### Task 5.3: Slack Event Handler

**File:** `apps/web/src/app/api/v1/slack/events/route.ts`

**Handler logic:**
1. Verify Slack request signature (HMAC-SHA256)
2. Handle URL verification challenge (Slack sends this during app setup)
3. For `app_mention` events and slash commands:
   a. Extract the question text
   b. Look up `slack_installations` by `slack_team_id` → get workspace and project
   c. Run the same RAG pipeline as the web chat (embed → search → prompt → generate)
   d. Format response for Slack (markdown with bold, bullet points, links)
   e. Post response using `chat.postMessage` API
4. Log the query in `ai_query_log` (source: `slack_bot`)

**Slack response formatting:**
- Use Slack's Block Kit for rich formatting
- Include model name as bold header
- Column list as bullet points
- Upstream/downstream as inline text
- "View in Docglow" link at the bottom

**Acceptance criteria:**
- `/docglow what is dim_customers?` returns a formatted response
- `@Docglow what columns are in stg_orders?` works via app mention
- Responses include "View in Docglow" links
- Request signature verification prevents spoofed requests
- Queries are logged for billing
- Graceful error handling for: uninstalled workspace, no project, AI query limit reached

---

## Phase 6: Health Dashboard

**Goal:** Dashboard shows historical health scores with trend visualization.

### Task 6.1: Health Overview Page

**File:** `apps/web/src/app/dashboard/health/page.tsx`

**Components:**
- Current overall health score (large number with color coding: green >80, yellow >60, red ≤60)
- Category breakdown: documentation, test coverage, naming, complexity (each as a gauge or bar)
- Health trend chart: line chart showing overall score over the last N publishes (Recharts)
- "Last published X hours ago" with link to publish history

**API endpoint:** `GET /api/v1/projects/{id}/health/current`

**Acceptance criteria:**
- Current scores displayed accurately
- Scores match the OSS CLI output for the same project
- Color coding is clear and accessible

### Task 6.2: Health History Chart

**File:** `apps/web/src/components/health/HealthTrendChart.tsx`

- Line chart with one data point per publish event
- Toggle lines for each category (overall, docs, tests, naming, complexity)
- X-axis: publish date/time
- Y-axis: score (0-100)
- Hover tooltips showing exact values
- Time range selector: 7 days, 30 days, 90 days, 1 year (based on plan tier)

**API endpoint:** `GET /api/v1/projects/{id}/health/history?since=30d`

**Acceptance criteria:**
- Chart renders with real publish data
- Category toggles work
- Time range selector respects plan limits (Starter: 30 days, Team: 90 days, Business: 1 year)
- Chart handles edge cases: only 1 data point, no data

### Task 6.3: Worst Offenders List

**File:** `apps/web/src/components/health/WorstOffenders.tsx`

- Table of models sorted by health score (ascending)
- Columns: model name, overall score, docs coverage, test coverage, naming, complexity
- Click model name → navigate to model detail page in the docs site
- Filterable by category ("show me undocumented models only")

**API endpoint:** `GET /api/v1/projects/{id}/health/details`

**Acceptance criteria:**
- Models sorted by score, worst first
- Clicking navigates to model page
- Category filter works
- Pagination for projects with many models

---

## Phase 7: Billing Integration

**Goal:** Stripe handles subscription lifecycle and usage-based billing for AI queries.

### Task 7.1: Stripe Setup

1. Create Stripe products and prices:
   - Starter: $49/month
   - Team: $99/month
   - Business: $149/month
   - AI query overage: metered price (per unit)
2. Configure Stripe Customer Portal for self-service management
3. Set up Stripe webhook endpoint

### Task 7.2: Upgrade Flow

**Files:**
- `apps/web/src/app/dashboard/settings/billing/page.tsx` (UI)
- `apps/web/src/app/api/v1/billing/checkout/route.ts` (create checkout session)
- `apps/web/src/app/api/v1/webhooks/stripe/route.ts` (webhook handler)

**Flow:**
1. User clicks "Upgrade" → sees plan comparison
2. Selects a plan → API creates a Stripe Checkout Session
3. User completes payment on Stripe → redirected back to dashboard
4. Stripe webhook fires `checkout.session.completed`
5. Webhook handler updates `workspaces.plan` and creates subscription record
6. Dashboard reflects new plan immediately

**Webhook events to handle:**
- `checkout.session.completed` → activate plan
- `invoice.paid` → confirm renewal
- `invoice.payment_failed` → send warning email, grace period
- `customer.subscription.deleted` → downgrade to free tier
- `customer.subscription.updated` → plan change

**Acceptance criteria:**
- Upgrade flow works end-to-end with Stripe test mode
- Plan changes reflected immediately in dashboard
- Failed payments trigger warning email
- Subscription cancellation downgrades to free tier
- Stripe Customer Portal accessible from billing settings

### Task 7.3: Usage Metering

**File:** `apps/web/src/lib/billing/usage.ts`

```typescript
// Called after each AI query
async function recordAIUsage(workspaceId: string) {
  // 1. Increment monthly query count in ai_query_log
  // 2. Check if over plan limit
  // 3. If over limit, create Stripe usage record for overage billing
}

// Scheduled function: runs daily
async function syncUsageToStripe() {
  // 1. Query ai_query_log for each workspace
  // 2. Calculate overage (queries above plan limit)
  // 3. Report to Stripe via Usage Records API
}
```

**Acceptance criteria:**
- AI queries counted accurately
- Overage charges appear on Stripe invoice
- Usage displayed in dashboard billing page
- Plan limits enforced (error message when queries exhausted on free tier)

---

## Phase 8: Polish & Launch Prep

### Task 8.1: Marketing Site

**File:** Update `docglow.com` landing page

- Hero section: "Modern documentation for dbt Core teams"
- Feature sections: Hosted docs, AI chat, Slack bot, Health dashboard
- Pricing table
- "Get started free" CTA → sign up flow
- Demo link to the jaffle_shop site
- Footer with dbt Labs trademark attribution

### Task 8.2: Onboarding Email Sequence (Resend)

- Welcome email after signup
- "Publish your first project" guide email (Day 1)
- "Add your team" email (Day 3)
- "Try the Slack bot" email (Day 7, Team+ plans only)

### Task 8.3: Error Handling & Edge Cases

Audit all API endpoints for:
- Rate limiting (use Vercel's built-in or Upstash Redis)
- Input validation (zod schemas for all request bodies)
- Graceful error responses (consistent JSON error format)
- Logging (structured logs for debugging)

### Task 8.4: Monitoring

- Vercel Analytics for dashboard performance
- Supabase dashboard for DB metrics
- Stripe dashboard for revenue
- Simple uptime monitoring (e.g., BetterStack free tier) for `app.docglow.com` and a sample doc site

---

## Build Order Summary

| Phase | Dependency | Estimated Hours | Estimated Weeks (at 2–5 hrs/wk) |
|---|---|---|---|
| Phase 0: Scaffolding + Local Dev | None | 10–14 hrs | 3–4 weeks |
| Phase 1: Auth + Workspace | Phase 0 | 6–10 hrs | 2–3 weeks |
| Phase 2: Publish Pipeline | Phase 1 | 12–18 hrs | 4–6 weeks |
| Phase 3: Doc Site Serving | Phase 2 | 6–10 hrs | 2–3 weeks |
| Phase 4: AI Chat | Phase 2 (needs embeddings) | 8–12 hrs | 2–4 weeks |
| Phase 5: Slack Bot | Phase 4 (reuses RAG pipeline) | 6–10 hrs | 2–3 weeks |
| Phase 6: Health Dashboard | Phase 2 (needs health scores) | 6–8 hrs | 2–3 weeks |
| Phase 7: Billing | Phase 1 | 8–12 hrs | 2–4 weeks |
| Phase 8: Polish | All above | 6–10 hrs | 2–3 weeks |
| **Total** | | **68–104 hrs** | **~20–30 weeks** |

**Critical path:** Phase 0 → Phase 1 → Phase 2 → Phase 3. Once Phase 2 is complete, Phases 4, 5, 6, and 7 can be built in parallel (they all depend on the data from the publish pipeline but don't depend on each other).

**Realistic timeline note:** At 2–5 hrs/week, Phases 0–4 (the MVP target) total 42–64 hours, which is 10–16 weeks — not 4. If you want to hit a 4-week MVP, you'd need to ramp to ~12–15 hrs/week for that month.

**Recommended sequence for 2–5 hours/week:**
1. Phase 0 (scaffolding + local dev — ~3-4 weeks, **invest here to save time later**)
2. Phase 1 (auth + workspaces — ~2–3 weeks)
3. Phase 2 (publish pipeline — ~4–6 weeks, most complex phase)
4. Phase 3 (site serving — ~2–3 weeks)
5. Phase 7 (billing — ~2–4 weeks, unblocks revenue) ← **First billable milestone**
6. Phase 4 (AI chat — ~2–4 weeks)
7. Phase 6 (health dashboard — ~2–3 weeks)
8. Phase 5 (Slack bot — ~2–3 weeks)
9. Phase 8 (polish — ongoing)

This order gets you to "publishable, browsable docs you can charge for" fastest (Phases 0–3 + 7), then layers on AI and Slack as differentiators.
