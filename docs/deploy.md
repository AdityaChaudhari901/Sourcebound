# Deploy a live demo (free-tier)

Goal: a **shareable public URL** where anyone can click "View live demo" and get
cited answers — at **zero cost** if you stay in the free tiers.

> **I (the assistant) cannot and will not create accounts, enter API keys, or enter
> payment for you.** This guide marks every spot where *you* must do that with 🔐
> (secret) or 💳 (a card/payment decision). Everything else (repo config) is already
> done.

---

## Architecture (all free tiers)

| Piece | Service | Free? |
|---|---|---|
| Frontend (Next.js) | **Vercel** (Hobby) | ✅ no card |
| API (FastAPI) | **Render** (Docker web service) | ✅ no card* |
| Postgres | **Neon** | ✅ no card, persistent |
| Vector store | **Qdrant Cloud** (1 GB cluster) | ✅ no card |
| Redis (rate-limit) | **Upstash** | ✅ no card |
| LLM | **Google AI Studio** Gemini API | ✅ free tier, rate-limited |
| Embeddings | **local BGE** (runs in the API container) | ✅ no API, no cost |

**Why this combo:** the demo is **read-only** and the **Celery worker is not needed**
(the demo corpus is seeded by the API itself), and **local BGE embeddings** mean
**no per-query embedding cost**. The only external paid surface is the LLM — kept on
Gemini's **free tier**.

> \* Free tiers and limits change — **verify each provider's current terms before you
> rely on "free."** Where a provider asks for a card to *verify identity* (some do),
> that's noted; you won't be charged on the free tier unless you explicitly enable
> billing.

---

## 💳 COST FLAGS — read before you click anything

1. **Keep billing OFF on the Gemini API key.** Google AI Studio's free tier is
   rate-limited (a few requests/min, daily cap). If you never enable billing on that
   key, you **cannot be charged** — requests just fail when you hit the limit. The
   app's rate limiter + read-only demo guard further cap abuse.
2. **Do NOT use Vertex AI for the public demo.** Vertex (`gemini-embedding-001`,
   `gemini-3.5-flash`) bills GCP credits **per call** — a public URL on Vertex can run
   up real charges. The demo config below uses the **free Gemini API + local BGE**
   instead.
3. **Render free web service**: 512 MB RAM, **sleeps after ~15 min idle** (first
   request after sleep takes ~30–60 s — fine for a demo). No card for the free plan.
4. **Render free Postgres expires after 90 days** — that's why this guide uses
   **Neon** (free, persistent) for Postgres instead.
5. **Vercel Hobby is free for non-commercial use.** A portfolio demo qualifies;
   a commercial product does not.
6. Nothing in this guide requires a paid plan. If any provider blocks the free path
   behind a card, **stop and tell me** — there's almost always a no-card alternative.

---

## Step 1 — Provision the datastores (you create these accounts)

For each, sign up, create the resource, and copy the connection string somewhere safe.

### Neon (Postgres) 🔐
1. neon.tech → sign up → **Create project**.
2. Copy the **connection string**. It looks like
   `postgresql://USER:PASSWORD@HOST/neondb?sslmode=require&channel_binding=require`.
3. Sourcebound needs the **async** driver — change **only the scheme**
   `postgresql://` → `postgresql+asyncpg://` and keep everything else (you can leave
   the `?sslmode=require&channel_binding=require` on the end). The app strips those
   libpq-only params and turns on SSL for you. Save the result as your
   **`DATABASE_URL`**, e.g.
   `postgresql+asyncpg://USER:PASSWORD@HOST/neondb?sslmode=require&channel_binding=require`.
   (Neon's default endpoint or the `-pooler` one both work — the app disables the
   prepared-statement cache so the pooler is happy.)

### Qdrant Cloud (vectors) 🔐
1. cloud.qdrant.io → sign up → **Create a free cluster** (1 GB).
2. Copy the cluster **URL** (`https://xxxx.qdrant.io:6333`) and create an **API key**.
3. Save as **`QDRANT_URL`** and **`SOURCEBOUND_QDRANT_API_KEY`**.

### Upstash (Redis, for rate limiting) 🔐
1. upstash.com → sign up → **Create database** (Redis, pick a nearby region).
2. Copy the **`redis://` (or `rediss://`) connection URL**. Save as **`REDIS_URL`**.

### Google AI Studio (Gemini LLM) 🔐 💳
1. aistudio.google.com → **Get API key** → create a key.
2. **Leave billing disabled** on the associated project (free tier, no charges — see
   cost flag #1). Save as **`GOOGLE_API_KEY`**.

---

## Step 2 — Deploy the API on Render (you click; secrets are yours)

The repo is already deploy-ready: the Dockerfile honors `$PORT`, the worker isn't
required, and embeddings default to local BGE.

> **Shortcut:** the repo ships a `render.yaml` Blueprint. Render → **New →
> Blueprint** → pick this repo and it pre-creates the service with all the settings
> below; you just fill the secret values and add the `gcp-sa.json` secret file. The
> manual steps below are the alternative.

1. render.com → sign up → **New → Web Service** → connect your GitHub repo
   `AdityaChaudhari901/Sourcebound`.
2. Settings:
   - **Root Directory:** `backend`
   - **Runtime:** Docker (it finds `backend/Dockerfile`)
   - **Instance type:** Free
   - **Region:** Virginia (US East) — matches Neon + Qdrant
   - **Health Check Path:** `/health`
   - **Docker Command** (override the default): `sh start.sh` — it runs migrations
     then uvicorn at **startup**, because Render's free tier has **no separate
     pre-deploy step** (`alembic upgrade head` is idempotent, safe every start).
3. **Environment variables** 🔐 (Render dashboard → Environment). Paste the values you
   saved above plus these. **Generate `JWT_SECRET` yourself** with
   `openssl rand -hex 32` — never reuse a default:

   ```
   SOURCEBOUND_ENVIRONMENT=production
   JWT_SECRET=<paste output of: openssl rand -hex 32>
   DATABASE_URL=<your Neon async URL>
   QDRANT_URL=<your Qdrant Cloud URL>
   SOURCEBOUND_QDRANT_API_KEY=<your Qdrant API key>
   REDIS_URL=<your Upstash URL>
   LLM_PROVIDER=gemini
   LLM_MODEL=gemini-2.0-flash
   GOOGLE_API_KEY=<your AI Studio key>
   SOURCEBOUND_EMBEDDING_PROVIDER=fastembed
   SOURCEBOUND_RERANKER_MODEL=Xenova/ms-marco-MiniLM-L-6-v2
   SOURCEBOUND_CORS_ORIGINS=https://REPLACE-WITH-YOUR-VERCEL-URL.vercel.app
   ```
   - Use the **lightweight MiniLM reranker** (above) — the production `bge-reranker-base`
     is ~1 GB and won't fit Render's 512 MB free instance. If the service still OOMs,
     set `SOURCEBOUND_RERANK_ENABLED=false` (the corrective grade + rewrite + generate
     still work without rerank).
   - Leave `SOURCEBOUND_CORS_ORIGINS` as a placeholder for now; you'll set the real
     Vercel URL in Step 5.
4. **Create Web Service.** First build ~5–8 min. When live, note the URL, e.g.
   `https://sourcebound-api.onrender.com`. Verify:
   - `https://<api>/health` → `{"status":"ok",...}`
   - `https://<api>/docs` → Swagger UI

---

### Variant — use Google Cloud credits via Vertex (stronger models)

If you have GCP credits and want the better stack (`gemini-3.5-flash` +
`gemini-embedding-001`, see [ADR-0008](decisions.md)), use Vertex instead of the
free Gemini API + local BGE. Usage is billed to your **credits** (a demo spends a
tiny fraction) — but credits are real spend, so heed the flags below.

**GCP setup (you do this):**
1. GCP Console → **IAM & Admin → Service Accounts** → create one → grant role
   **Vertex AI User** (`roles/aiplatform.user`). 🔐
2. Create a **JSON key** and download it.
3. Render → your service → **Environment → Secret Files** → add the JSON as
   `gcp-sa.json` (Render mounts it at `/etc/secrets/gcp-sa.json`).

**Env vars — replace the `gemini`/BGE ones from Step 2 with:**
```
LLM_PROVIDER=vertex
LLM_MODEL=gemini-3.5-flash
VERTEX_PROJECT_ID=<your GCP project id>
VERTEX_REGION=global
SOURCEBOUND_EMBEDDING_PROVIDER=vertex
GOOGLE_APPLICATION_CREDENTIALS=/etc/secrets/gcp-sa.json
```
Drop `GOOGLE_API_KEY`. Keep the lightweight reranker for 512 MB (Vertex embeddings
run via API, so there's no big local embedding model — only the reranker is local).
No code change is needed: the app authenticates to Vertex through
`GOOGLE_APPLICATION_CREDENTIALS` automatically.

**💳 Cost flags (credits are still real money):**
- **Check credit expiry** (GCP console → *View expiry details*). After credits expire
  or run out, usage bills your card (pay-as-you-go).
- **Set a GCP budget alert** at a low threshold so a hammered public demo can't
  silently drain credits.
- **Keep rate limiting ON** for this path (use Upstash) — it's your guardrail against
  credit burn under abuse.

---

## Step 3 — Seed the public demo corpus

The demo is self-seeding: the first call to `POST /auth/demo` provisions the shared
read-only workspace and ingests the 6 sample docs (embedded locally with BGE). Warm
it once after deploy so the first real visitor doesn't wait:

```bash
curl -X POST https://<your-api>/api/v1/auth/demo
```
(That returns a token and triggers seeding — takes a few seconds on first call.)
The demo is **read-only**: ingest/reingest return `403`, so visitors can't pollute it.

---

## Step 4 — Deploy the frontend on Vercel (you click)

1. vercel.com → sign up → **Add New → Project** → import the same GitHub repo.
2. Settings:
   - **Root Directory:** `frontend`
   - Framework preset: **Next.js** (auto-detected)
3. **Environment Variable** 🔐 (Project Settings → Environment Variables):
   ```
   NEXT_PUBLIC_API_URL = https://<your-render-api>/api/v1
   ```
   (`NEXT_PUBLIC_*` is baked at build time — if you change it later, redeploy.)
4. **Deploy.** You'll get a URL like `https://sourcebound.vercel.app`.

---

## Step 5 — Connect CORS (the one wiring step)

The browser (Vercel HTTPS) calls the API cross-origin, so the API must allow the
Vercel origin:

1. Render dashboard → your API → Environment → set
   `SOURCEBOUND_CORS_ORIGINS=https://sourcebound.vercel.app` (your real Vercel URL).
2. Save → Render redeploys automatically.

---

## Step 6 — Your shareable URL ✅

Open `https://sourcebound.vercel.app`, click **"View live demo"** → it should drop
straight into the read-only demo workspace and answer questions with citations.
Share that Vercel URL.

Quick smoke test:
```bash
curl -s https://<api>/health
curl -s -X POST https://<api>/api/v1/auth/demo   # returns a token
```

---

## Alternative — single VM (one box, reuses docker-compose)

If you'd rather run everything on one small VM (e.g., a free Oracle Cloud Always-Free
ARM instance — 💳 card for identity verification, no charge — or a ~$5/mo Hetzner/DO
box — 💳 paid):

1. Install Docker + Docker Compose on the VM.
2. Clone the repo, create `backend/.env` with the same vars as Step 2 (but you can use
   the in-compose Postgres/Qdrant/Redis instead of the cloud ones — they're already in
   `docker-compose.yml`).
3. `docker compose up -d postgres qdrant redis migrate api`  (no `worker`, no
   `frontend` — frontend stays on Vercel).
4. **HTTPS is required** (Vercel is HTTPS; a browser won't call an `http://` API).
   Easiest free options:
   - **Cloudflare Tunnel** — `cloudflared tunnel --url http://localhost:8000` gives a
     free `https://*.trycloudflare.com` URL instantly (ephemeral), or a stable URL
     with a named tunnel + a domain.
   - **Caddy** reverse proxy + a free domain (e.g., DuckDNS) for auto Let's Encrypt TLS.
5. Point Vercel's `NEXT_PUBLIC_API_URL` at that HTTPS URL + `/api/v1`, and set the
   API's `SOURCEBOUND_CORS_ORIGINS` to the Vercel URL.

---

## Production hardening (when you go beyond a demo)

See [`docs/production.md`](production.md): real secrets manager, the
read-only-demo + rate-limit are already in place, budget alerts, backups, and the
Vertex-vs-Gemini / privacy trade-off ([ADR-0008](decisions.md)).
