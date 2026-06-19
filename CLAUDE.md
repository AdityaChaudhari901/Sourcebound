# Sourcebound — Project Guide for All Future Work

> This file is the contract for how Sourcebound is built. Read it before writing
> any code. When a decision here conflicts with a default behavior, this file wins.

---

## 1. What Sourcebound Is

**Sourcebound is a citation-grounded KnowledgeOps RAG platform.** You connect your
internal docs and code; you ask a question; you get an answer **with citations back
to the source**. The non-negotiable invariant of this project:

> **Every answer must be traceable to a source. An uncited claim is a bug, not a feature.**

The interesting engineering is the **query engine**: a self-correcting (corrective /
agentic) RAG workflow that grades its own retrieval, rewrites the query when retrieval
is weak, generates a cited answer, and verifies the answer is grounded before returning
it — capped retries, graceful low-confidence degradation. See `docs/knowledgeops_research.md`
for the full "why" behind every component.

---

## 2. Golden Rules (apply to every change)

1. **Citations are the product.** Any path that produces an answer must carry source
   metadata end-to-end (chunk → service → API → UI). Never drop provenance.
2. **Build one slice at a time. Do not build ahead.** No speculative endpoints,
   tables, or components for features not in the current slice.
3. **Async for all I/O.** Every DB call, vector call, LLM call, and HTTP call is `async`.
   CPU-bound work (embedding, parsing) goes to a Celery worker, never the request path.
4. **Routers thin, services thick.** Routers only validate, call a service, and shape
   the response. All business logic lives in `services/` (and `rag/`).
5. **Pydantic at every boundary.** Every request and response is a typed Pydantic schema.
6. **Provider-agnostic LLM/embeddings.** All model access goes through the swappable
   provider interface — never import an SDK directly in a service.
7. **No TypeScript on the frontend.** Plain JavaScript/JSX only.
8. **Secrets only via env.** Never hardcode keys; read from `.env` / settings.

---

## 3. Backend Stack (one line of "why" each)

| Component | Choice | Why |
|---|---|---|
| Language | **Python 3.11+** | Modern async, typing, and the LLM/RAG ecosystem live here. |
| Web framework | **FastAPI (async/ASGI)** | AI backends are I/O-bound; async serves many concurrent waits, plus Pydantic validation, auto OpenAPI, and SSE streaming. |
| RAG components | **LangChain (components only)** | Use loaders, splitters, retrievers, and the reranker — *not* deep opaque chains; keeps glue free without hiding control flow. |
| Orchestration | **LangGraph** | The query engine loops, branches, and holds state — that is a state machine, not a chain. |
| Vector store | **Qdrant** | Free, self-hostable, strong payload filtering for multi-tenant isolation and hybrid retrieval. |
| Metadata store | **PostgreSQL** | ACID store for tenants, users, documents, ingestion jobs, conversations, eval runs — facts live here, vectors live in Qdrant. |
| Cache / broker | **Redis** | Caching, rate limiting, and Celery's message broker in one in-memory store. |
| Task queue | **Celery** | Ingestion (parse/chunk/embed) is slow and CPU-bound — enqueue a job, return immediately, process in a worker. |
| Observability | **Langfuse** | Multi-step, non-deterministic, per-call-costed pipeline needs per-node traces for debugging, cost, and latency. |
| LLM + embeddings | **Swappable provider interface** | Avoid lock-in and cost; default to a **free LLM** (Groq / Gemini free tier or local **Ollama**) and **open embeddings (BGE)** so data stays private and the project runs with zero budget. |

**Provider interface rule:** define one `LLMProvider` and one `EmbeddingProvider`
protocol/interface. Services depend on the interface; the concrete provider is chosen
by config/env. Swapping Groq → Gemini → Ollama is a config change, never a code change
in a service.

---

## 4. Frontend Stack (one line of "why" each)

| Component | Choice | Why |
|---|---|---|
| Framework | **Next.js (App Router)** | File-based routing, server components for shell, first-class data fetching. |
| Language | **JavaScript / JSX (NO TypeScript)** | Per project mandate — functional components and hooks only. |
| Styling | **Tailwind CSS** | Utility-first, fast iteration, consistent design tokens. |
| Components | **shadcn/ui (configured for JS)** | Accessible, unstyled-by-default primitives we own in-repo — generated as `.jsx`. |
| Server state | **TanStack Query** | Caching, retries, and request lifecycle for API data without hand-rolled state. |
| Streaming | **SSE (Server-Sent Events)** | Stream answer tokens as they generate so the user sees output immediately, not a spinner. |
| Dashboard | **Bento-grid layout** | Dense, scannable overview of documents, ingestion jobs, and recent queries. |

---

## 5. Backend Conventions

- **Async everywhere** for I/O (`async def`, async SQLAlchemy, async clients).
- **Routers thin, services thick.** Routers in `api/v1/routes/`, logic in `services/`
  and `rag/`. A router function should be readable in a few lines.
- **Pydantic schemas for all I/O**, kept in `schemas/`. Never return raw ORM objects.
- **API versioned under `/api/v1`.** All routes mount beneath the version prefix.
- **Consistent error envelope.** Every error response has the same shape:
  ```json
  { "error": { "code": "string_code", "message": "human readable", "details": {} } }
  ```
  Raise typed app exceptions; a central exception handler renders the envelope.
- **Structured logging** (JSON), one logger config in `core/logging.py`; include a
  request/correlation id. No bare `print`.
- **Secrets via env / `.env`**, loaded through Pydantic `Settings` in `core/config.py`.
  Runtime variables use the `SOURCEBOUND_` prefix to avoid collisions with
  generic shell variables.
  Commit only `.env.example`.
- **Naming:** modules and functions `snake_case`; classes `PascalCase`; Pydantic
  schemas suffixed by role (`DocumentCreate`, `DocumentRead`, `QueryRequest`,
  `AnswerResponse`); services named `<domain>_service.py` exposing a `<Domain>Service`
  class or async functions; LangGraph nodes are verbs (`retrieve`, `grade_documents`,
  `rewrite_query`, `generate`, `verify_grounding`).

---

## 6. Frontend Conventions

- **Functional components + hooks only.** No class components, no TypeScript.
- **File extensions:** `.jsx` for components/pages, `.js` for plain logic/helpers.
- **Server state via TanStack Query**; local UI state via `useState`/`useReducer`.
  Do not fetch in components ad hoc — go through the API client + query hooks.
- **One API client** (`lib/api-client.js`) pointed at the backend `/api/v1`; base URL
  from `NEXT_PUBLIC_API_BASE_URL`.
- **Streaming answers via SSE** through a dedicated helper (`lib/sse.js`).
- **Naming:** components `PascalCase` files and exports (`AnswerCard.jsx`); hooks
  `useThing.js`; route folders lowercase (`app/ask/page.jsx`); Tailwind for styling,
  no ad-hoc CSS files unless unavoidable.

---

## 7. Intended Folder Layout

> Folders are created slice by slice — this is the target shape, not a mandate to
> scaffold everything now.

### `backend/`
```
backend/
  app/
    main.py                  # app factory: middleware, error handlers, mounts /api/v1
    core/
      config.py              # Pydantic Settings (env, .env)
      logging.py             # structured (JSON) logging setup
      errors.py              # app exceptions + error-envelope handlers
    api/
      v1/
        router.py            # aggregates all v1 route modules
        routes/
          health.py
          documents.py       # ingestion endpoints (thin)
          query.py           # ask + SSE streaming endpoints (thin)
    schemas/                 # Pydantic request/response models
    services/                # business logic (thick): ingestion_service.py, query_service.py
    rag/
      providers/             # LLMProvider / EmbeddingProvider interfaces + impls (groq, gemini, ollama, bge)
      loaders/               # LangChain loaders + splitters wiring
      retrieval/             # hybrid retriever (dense+sparse) + cross-encoder reranker
      graph/                 # LangGraph corrective-RAG: state.py, nodes.py, graph.py
    db/
      session.py             # async SQLAlchemy engine/session
      models.py              # ORM models (tenants, documents, jobs, conversations, eval_runs)
      migrations/            # Alembic
    workers/
      celery_app.py          # Celery app + Redis broker config
      tasks.py               # async ingestion tasks (parse/chunk/embed/index)
    integrations/
      qdrant.py              # Qdrant client + collection helpers
      redis.py               # Redis client / cache helpers
      langfuse.py            # tracing setup
  tests/
  pyproject.toml             # deps + tooling (or requirements.txt)
  alembic.ini
  .env.example
  Dockerfile
```

### `frontend/`
```
frontend/
  app/
    layout.jsx               # root layout + providers
    page.jsx                 # bento-grid dashboard
    ask/page.jsx             # ask + streamed cited answer
    documents/page.jsx       # documents + ingestion status
  components/
    ui/                      # shadcn/ui primitives (generated as .jsx)
    ...                      # feature components (AnswerCard.jsx, CitationList.jsx, ...)
  hooks/                     # useAsk.js, useDocuments.js, ...
  lib/
    api-client.js            # fetch wrapper to backend /api/v1
    query-client.js          # TanStack Query client
    sse.js                   # SSE streaming helper
  providers/                 # QueryClientProvider, etc.
  jsconfig.json              # path aliases (JS, not TS)
  components.json            # shadcn config (JS mode)
  tailwind.config.js
  postcss.config.js
  package.json
  .env.local.example
```

### Repo root
```
docker-compose.yml           # api + worker + qdrant + postgres + redis + langfuse
CLAUDE.md                    # this file
docs/                        # research + design notes
backend/  frontend/
```

---

## 8. How to Run Everything

> Exact scripts land with the slices that introduce them. This is the intended shape.

### Infrastructure (one command brings up the services)
```bash
docker compose up -d        # qdrant + postgres + redis + langfuse (+ api/worker when containerized)
```

### Backend (local dev)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .                       # or: pip install -r requirements.txt
cp .env.example .env                   # then fill in secrets
alembic upgrade head                   # apply DB migrations
uvicorn app.main:app --reload          # API at http://localhost:8000, docs at /docs
celery -A app.workers.celery_app worker --loglevel=info   # ingestion worker (separate shell)
```

### Frontend (local dev)
```bash
cd frontend
npm install
cp .env.local.example .env.local       # set NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
npm run dev                            # app at http://localhost:3000
```

### Conventions for new commands
When a slice adds a runnable command, document it here in the same shape and keep the
"one command for infra, one per app" structure intact.

---

## 9. Definition of Done (per slice)

- Stays inside the described slice — no build-ahead.
- Async I/O; routers thin, services thick; Pydantic at boundaries; `/api/v1` prefix.
- Errors use the standard envelope; logs are structured; secrets come from env.
- Frontend is JS/JSX, functional components, server state via TanStack Query.
- Citations preserved wherever an answer is produced.
- A short note on key decisions + exact run/verify steps accompanies the change.
