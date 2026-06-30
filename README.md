# Sourcebound

[**▶ Live demo**](https://sourcebound.vercel.app) &nbsp;·&nbsp; one click, no sign-up — ask a question, get a cited, grounded answer.

> Hosted on free tiers, so the API may take ~30–50s to wake on the first request.

**Ask questions against your internal docs and code, and get answers with citations
back to the source — every claim traceable, or it doesn't ship.**

Sourcebound is a citation-grounded KnowledgeOps RAG platform. You connect your
internal documents; you ask a question; you get a streamed answer where **every
claim links to the chunk it came from**. The engine grades its own retrieval,
rewrites the query when retrieval is weak, falls back to web search when its own
corpus comes up short, and verifies the answer is grounded before returning it.

> The non-negotiable invariant: **an uncited claim is a bug, not a feature.**

---

## The problem

Plain RAG (`retrieve → stuff into prompt → generate`) has one fatal failure mode:
when retrieval returns irrelevant context, it generates anyway — fluently, and
ungrounded. For an internal knowledge base that's worse than useless: a confident,
plausible, *wrong* answer with no way to check it. The hard part isn't calling an
LLM; it's making the system **notice when it doesn't know**, recover when it can,
and prove where every sentence came from when it does answer.

Sourcebound solves this with a **corrective (agentic) RAG** engine: a state machine
that self-grades, self-corrects with bounded retries, degrades gracefully, and
attaches provenance end-to-end (chunk → service → API → UI).

---

## What's inside

- **Corrective-RAG query engine** — grade → rewrite-loop → web fallback → generate →
  verify-grounding, as a LangGraph state machine (not an opaque chain).
- **Hybrid retrieval + rerank** — dense (BGE) + sparse (BM25) fused with weighted
  RRF, then a cross-encoder reranker for a precise top-`k`.
- **Citations as a first-class output** — answers carry `source_uri`, `chunk_id`,
  and a snippet for each citation; web-sourced facts are flagged as external.
- **Streaming UI** — Next.js (App Router, JS/JSX) streaming tokens over SSE, with a
  grounding score and "self-corrected / used-web" indicators.
- **Async ingestion** — upload returns immediately; a Celery worker parses, chunks,
  embeds (dense + sparse), and indexes off the request path.
- **Multi-tenant by construction** — `tenant_id` is a required retrieval argument and
  a Qdrant payload filter; no code path can read another tenant's data.
- **Provider-agnostic models** — swap Vertex / Gemini / Groq / Ollama / OpenAI by
  config; open BGE embeddings run locally for free.
- **Built-in evaluation** — a golden-dataset harness with an LLM-as-judge, gated in
  CI on a configurable faithfulness threshold.
- **Observability** — per-node Langfuse traces (cost + latency), structured JSON
  logs with correlation ids, a consistent error envelope.

---

## Architecture

One backend image runs as both the API and the Celery worker, in front of Postgres
(facts), Qdrant (vectors), and Redis (broker), with swappable model providers.

```mermaid
flowchart TB
    browser["Browser — Next.js UI (SSE streaming)"]

    subgraph app["Backend (one image, two roles)"]
        api["FastAPI API — /api/v1, async, SSE"]
        worker["Celery worker — parse · chunk · embed · index"]
    end

    subgraph data["Infrastructure"]
        pg[("PostgreSQL<br/>tenants, docs, jobs,<br/>conversations, eval_runs")]
        qd[("Qdrant<br/>dense + sparse vectors,<br/>per-tenant filter")]
        redis[("Redis<br/>Celery broker + cache")]
    end

    subgraph prov["Swappable providers (config-selected)"]
        llm["LLM — Vertex / Gemini / Groq / Ollama / OpenAI"]
        emb["Embeddings — BGE dense + BM25 sparse"]
        web["Web search — Tavily (optional)"]
    end

    lf["Langfuse — per-node traces"]

    browser -->|REST + SSE| api
    api -->|enqueue| redis --> worker
    api --> pg & qd & llm & emb
    worker --> pg & qd & emb
    api -.->|fallback| web
    api -.->|traces| lf
```

Deeper diagrams (ingestion vs. ask sequence flows, retrieval internals, tenancy)
are in [`docs/architecture.md`](docs/architecture.md).

---

## The corrective-RAG graph

The query engine loops and branches — that's why it's a graph, not a chain. The
only cycle (`retrieve → grade → rewrite → retrieve`) is bounded by a retry cap, so
it always terminates.

```mermaid
flowchart TD
    START([START]) --> retrieve
    retrieve["retrieve<br/>hybrid → rerank top-k"] --> grade["grade_documents<br/>LLM keeps relevant chunks"]
    grade -->|relevant| generate["generate<br/>cited answer (streamed)"]
    grade -->|"not relevant,<br/>retries < cap"| rewrite["rewrite_query<br/>reformulate, retries++"]
    grade -->|"at cap, web on"| websearch["web_search<br/>external fallback"]
    grade -->|"at cap, no web"| generate
    rewrite --> retrieve
    websearch --> generate
    generate --> verify["verify_grounding<br/>rate 0–1 vs context"]
    verify --> END([END])
```

| Node | Role |
|---|---|
| `retrieve` | Hybrid (dense+sparse) recall → cross-encoder rerank to top-`k` |
| `grade_documents` | One batched LLM call keeps only relevant chunks (**fail-open** on parse error) |
| `rewrite_query` | Intent-preserving reformulation; increments the retry guard |
| `web_search` | Last-resort public-web fallback; results cited as external URLs |
| `generate` | Grounded, cited answer, streamed token-by-token |
| `verify_grounding` | LLM rates how grounded the answer is (0–1), surfaced to the UI |

---

## Results: naive vs. corrective

Measured by the eval harness (`backend/eval/`) over a **30-question golden dataset
across 12 documents** (`eval/golden.jsonl`) — deliberately seeded with distractors
(three different "90-day" facts, three Slack channels, three error-rate thresholds,
a payments-vs-billing service split) so retrieval has to discriminate. Reproduce with:

```bash
cd backend && python eval/run_eval.py --compare naive corrective
```

**Two findings, both stated straight.**

**(1) Upgrading the models lifted the whole system.** Moving dense retrieval from
local BGE-small (384-dim) to `gemini-embedding-001` (3072-dim), with
`bge-reranker-base` and `gemini-3.5-flash`, raised precision and faithfulness for
*every* configuration — the distractor chunks that used to leak into the context
mostly stopped:

| Config | faithfulness | answer_relevancy | context_precision | context_recall |
|---|---|---|---|---|
| Baseline — naive, BGE-small | 0.93 | 0.94 | 0.77 | 0.97 |
| **Upgraded — naive** (gemini-embedding) | 0.94 | 0.91 | 0.82 | 0.95 |
| **Upgraded — corrective** (full stack) | 0.94 | 0.89 | **0.83** | 0.95 |

**(2) Corrective ≈ naive — the engine is insurance, not a leaderboard number.**
On the upgraded stack, comparing the two configs head-to-head over all 30 questions
gave **0 clear wins and 0 clear losses** for corrective; the aggregate deltas are
within noise (corrective is fractionally behind). That is an honest result, and the
reason is structural: on a clean corpus that a strong LLM can answer from strong
dense retrieval (per-question precision is now mostly 1.00), the extra machinery —
hybrid's sparse arm, the rewrite loop — has no headroom to add and occasionally adds
a little noise.

The **per-category** breakdown (`--compare` reports this now) shows where the small
differences actually live — corrective's cross-encoder rerank sharpens *factual*
precision, its graceful-degradation path lifts *unanswerable* faithfulness, and
hybrid's sparse arm costs a little *distractor* precision:

| Category | n | faithfulness (naive → corrective) | precision (naive → corrective) |
|---|---|---|---|
| factual | 16 | 0.93 → 0.93 | 0.88 → **0.94** |
| distractor | 11 | 0.95 → 0.95 | 0.91 → 0.86 |
| multi-hop | 1 | 1.00 → 1.00 | 0.50 → 0.50 |
| unanswerable | 2 | 0.85 → **0.90** | 0.00 → 0.00 |

(`unanswerable` precision is 0 by construction — there are no ideal sources to hit;
faithfulness is what matters there, and corrective edges ahead by refusing/grounding
rather than guessing. `multi-hop` is a single question — directional, not significant.)

The corrective pipeline still earns its place, just not on these means: it's the
**robustness layer** for the cases this clean benchmark under-stresses — the rewrite
loop and **web fallback** keep an answer grounded when first-pass retrieval is weak
or the corpus simply doesn't contain the answer (both unanswerable questions were
handled by web fallback rather than hallucinated), and the **verify-grounding** node
is what lets the system *prove* an answer is sourced. The right way to make those
show up in numbers is a harder, retrieval-stressing golden set — the clear next step.

*`gemini-3.5-flash` as both generator and judge, 2026-06-29; dense embeddings
`gemini-embedding-001`; reranker `bge-reranker-base`. Aggregate means over 30
questions. The hosted stack is opt-in via config — `SOURCEBOUND_EMBEDDING_PROVIDER`
defaults to local BGE so the project still runs free and offline (see
[`docs/decisions.md` ADR-0008](docs/decisions.md)).*

> Retrieval metrics (`context_precision` / `context_recall`) are computed
> deterministically from the golden `ideal_sources`; generation metrics
> (`faithfulness` / `answer_relevancy`) use an LLM-as-judge. See
> [`docs/architecture.md §7`](docs/architecture.md) for the methodology.

---

## Run it locally — one command

```bash
# Prereq: create backend/.env (see backend/.env.example) — set JWT_SECRET and one
# LLM provider (e.g. LLM_PROVIDER=groq + GROQ_API_KEY).
docker compose up --build -d
```

Brings up **api + worker + frontend + postgres + qdrant + redis + langfuse** (a
one-shot Alembic `migrate` job runs first). Then:

- Frontend → http://localhost:3000
- API + docs → http://localhost:8000/docs
- Langfuse → http://localhost:3001

Stop / reset: `docker compose down` (keeps data) · `docker compose down -v` (wipes
volumes). Full env-var reference and local (non-Docker) dev setup are in
[`CLAUDE.md §8`](CLAUDE.md).

---

## Tech decisions & trade-offs

Short version (full ADRs with alternatives in [`docs/decisions.md`](docs/decisions.md)):

- **Corrective RAG over a linear chain** — a plain chain can't notice bad retrieval,
  so it hallucinates. The graph self-grades and self-corrects. *Trade-off:* more LLM
  calls per query (grade + optional rewrite + verify), accepted because a fast
  ungrounded answer is worthless when citations are the product.
- **Qdrant for vectors** — strong payload filtering (clean multi-tenancy), native
  dense+sparse, free self-hosting. *Trade-off:* one more stateful service vs folding
  vectors into Postgres with pgvector, accepted for the isolation + hybrid guarantees.
- **Hybrid retrieval + cross-encoder rerank** — an internal KB mixes prose and exact
  identifiers; dense alone blurs tokens, sparse alone misses paraphrase. RRF fusion
  gets both, the reranker makes the top-`k` precise. *Trade-off:* more moving parts
  and rerank latency; the reranker is swappable/downsizable via config.
- **Postgres for facts, Qdrant for vectors** — ACID system-of-record separate from
  ANN search; provenance is duplicated into the vector payload so citations travel
  with the chunk.
- **Provider-agnostic LLM/embeddings** — no vendor lock-in; run fully local for free
  or point at a hosted tier with a config change.
- **LLM-as-judge eval gated in CI** — answer-quality regressions fail the build;
  threshold is a repo variable. *Trade-off:* the judge has variance and token cost,
  mitigated with strict numeric prompts behind a swappable `Evaluator` interface.

---

## Project layout

```
backend/   FastAPI app, RAG graph, providers, Celery worker, eval harness, tests
frontend/  Next.js (App Router, JS/JSX) streaming UI
docs/      architecture.md · decisions.md · knowledgeops_research.md
docker-compose.yml   full stack in one command
```

The build contract and conventions for all work live in [`CLAUDE.md`](CLAUDE.md).
