# Architecture Decision Records

Short, dated records of the decisions that shaped Sourcebound and the trade-offs
behind them. Each ADR is **Context → Decision → Consequences (incl. what we gave
up)**. The full "why" behind the platform lives in
[`knowledgeops_research.md`](./knowledgeops_research.md).

Status legend: ✅ Accepted · 🔄 Superseded · ⛔ Rejected

---

## ADR-0001 — Corrective (agentic) RAG instead of a linear RAG chain

**Status:** ✅ Accepted

### Context
The core invariant of the product is: *every answer must be traceable to a source;
an uncited claim is a bug.* A naive `retrieve → stuff → generate` chain violates
this whenever retrieval is weak: it has no way to notice that the retrieved context
is irrelevant, so it generates anyway — confidently, and ungrounded. That is
exactly the failure mode we cannot ship.

### Decision
Build the query engine as a **self-correcting state machine** (LangGraph
`StateGraph`) that grades its own retrieval and acts on the grade:

1. `retrieve` → `grade_documents` (LLM keeps only relevant chunks).
2. If nothing relevant and under the retry cap → `rewrite_query` and loop back to
   `retrieve`.
3. If still nothing at the cap → `web_search` (if configured) or graceful
   degradation on best-available docs.
4. `generate` a cited answer, then `verify_grounding` rates it 0–1 before return.

The loop is bounded by `settings.max_query_retries`, which guarantees termination.

### Consequences
- **Gain:** the pipeline can recover from bad retrieval (rewrite), escape its own
  corpus when needed (web fallback), and self-report confidence (grounding score) —
  all surfaced to the UI. Honest caveat from the eval: on a 30-question / 12-doc set
  with distractors (see the README table), corrective does **not** beat naive on
  aggregate metrics — a strong LLM over high-recall retrieval leaves little headroom,
  and hybrid trades some precision when the reranker is weak. Corrective's measured
  wins are the *robustness* cases the means dilute: it **refused an unanswerable
  question that naive hallucinated** (faithfulness 0.00 → 1.00) and did better on
  multi-hop. The engine is groundedness insurance, not a leaderboard number.
- **Cost:** more LLM calls per query (grade + optional rewrite + verify on top of
  generate), so higher latency and token cost. We accept this: a fast wrong answer
  is worthless when citations are the product. The extra calls use small/cheap
  prompts (index lists, single scores), and the corrective branches only fire when
  retrieval is actually weak.
- It's a *graph*, not a chain — which is why LangGraph (state + branches + loops)
  is the right tool over LangChain's opaque chains.

---

## ADR-0002 — Qdrant as the vector store

**Status:** ✅ Accepted

### Context
We need a vector store that supports (a) **strong metadata filtering** for
multi-tenant isolation, (b) **hybrid** dense + sparse retrieval, (c) **self-hosting
at zero cost** so data stays private and the project runs with no budget, and (d) a
clean async-friendly client.

### Decision
Use **Qdrant**, with named vectors per point: one dense vector (BGE) and one sparse
vector (BM25). Tenant isolation is a payload filter applied on every query
(`tenant_filter`), and `tenant_id` is a required argument on the retriever — there
is no unfiltered retrieval path.

### Alternatives considered
- **pgvector** — appealing (one fewer service, already running Postgres), but its
  payload filtering and native hybrid/sparse story are weaker, and mixing the
  vector workload into the metadata DB couples two very different scaling profiles.
- **Pinecone / hosted vector DBs** — managed and capable, but paid and off-box;
  fails the "zero budget, data stays private" constraint.
- **Weaviate / Milvus** — capable but heavier to self-host for this scope.

### Consequences
- **Gain:** first-class payload filtering (clean multi-tenancy), native dense+sparse
  in one store, free self-hosting, good dashboard for debugging.
- **Cost:** one more stateful service to run and back up (vs folding vectors into
  Postgres). We accept the operational cost for the isolation and hybrid-retrieval
  guarantees. See ADR-0004 for why we keep facts in Postgres and vectors in Qdrant.

---

## ADR-0003 — Hybrid retrieval (dense + sparse) with a cross-encoder reranker

**Status:** ✅ Accepted

### Context
The corpus is an internal tech knowledge base: prose questions ("how do I rotate a
key") *and* exact identifiers (service names, env vars, error codes, function
names). Dense embeddings are great at meaning but blur exact tokens; lexical search
nails exact tokens but misses paraphrase. Neither alone gives good recall on this
mix. And high recall isn't enough — what lands in the LLM's top-`k` must also be
**precise**, or grading and generation pay for the noise.

### Decision
Two stages:

1. **Hybrid recall** — run dense (BGE cosine) and sparse (BM25) retrieval, then fuse
   the ranked lists with **weighted Reciprocal Rank Fusion**
   (`score = Σ weight / (rrf_k + rank)`). Weights, `rrf_k`, and prefetch depth are
   configurable.
2. **Cross-encoder rerank** — re-score the fused candidates with a cross-encoder and
   truncate to top-`k`. This is the precision step fusion alone can't provide,
   because a cross-encoder reads the (query, chunk) pair jointly.

### Consequences
- **Gain:** recall of both retrieval styles *and* a precise final top-`k` — measured
  by the `context_precision` / `context_recall` metrics and the `dense` →
  `hybrid_rerank` eval presets.
- **Cost:** more moving parts (two indexes per point, a fusion step, a reranker
  model) and added per-query latency from reranking. The reranker is swappable via
  config (`SOURCEBOUND_RERANKER_MODEL`) so it can be downsized — CI uses a small
  MiniLM cross-encoder to avoid downloading the ~1 GB BGE reranker.
- RRF was chosen over score-normalization fusion because it's rank-based and needs
  no per-query score calibration between two very different scoring scales.

---

## ADR-0004 — Postgres for facts, Qdrant for vectors (split data model)

**Status:** ✅ Accepted

### Context
We have two very different kinds of state: relational facts (tenants, users,
documents, ingestion jobs, conversations, eval runs) that need ACID guarantees, and
high-dimensional vectors that need ANN search.

### Decision
Keep them in separate stores: **PostgreSQL** for facts (the system of record),
**Qdrant** for vectors. Provenance (`source_uri`, `document_id`, `chunk_id`,
`tenant_id`) is duplicated into the Qdrant payload so a retrieved chunk carries its
own citation without a round-trip to Postgres.

### Consequences
- **Gain:** each store does what it's best at; they scale independently; citations
  survive end-to-end because provenance travels with the vector.
- **Cost:** two stores to operate, and provenance is denormalized into the payload
  (must stay consistent at index time). Acceptable — the write path is the worker,
  which owns both writes in one task.

---

## ADR-0005 — Provider-agnostic LLM & embedding interfaces

**Status:** ✅ Accepted

### Context
Model choice changes with cost, privacy, and availability. We must not lock the
codebase to one vendor's SDK, and the project must run with **zero budget** (local
models) yet scale up to a hosted model without touching service code.

### Decision
Define one `LLMProvider` and one `EmbeddingProvider` protocol; services depend only
on the protocol. Concrete providers are selected by config:
- **LLM** — Vertex (Gemini via ADC), or any OpenAI-compatible endpoint (Gemini,
  Groq, Ollama, OpenAI) behind one client. Swapping is a `LLM_PROVIDER` change.
- **Embeddings** — BGE via FastEmbed (open, local, ONNX, no torch; data never leaves
  the box) by default, dense + BM25 sparse.

### Consequences
- **Gain:** no vendor lock-in; run fully local for free or point at a hosted free
  tier; the eval harness can A/B providers behind the same interface.
- **Cost:** lowest-common-denominator API surface (chat-style complete/stream),
  and provider quirks (e.g. Vertex auth via ADC) handled in the provider layer, not
  smeared across services. Worth it for the portability.

---

## ADR-0006 — LLM-as-judge evaluation, gated in CI

**Status:** ✅ Accepted

### Context
"Did this change make answers better or worse?" needs to be answerable
automatically, on every PR — not by eyeballing. But "grounded" and "on-topic" are
semantic properties a regex can't score.

### Decision
A golden-dataset harness scores four metrics per answer: retrieval metrics
(`context_precision`, `context_recall`) computed **deterministically** from
`ideal_sources` (no judge bias), and generation metrics (`faithfulness`,
`answer_relevancy`) scored by the configured LLM as judge. The `faithfulness`
aggregate is a **CI gate** whose threshold is a repo variable
(`FAITHFULNESS_THRESHOLD`, default 0.8).

### Consequences
- **Gain:** answer-quality regressions fail the build; config presets isolate the
  effect of each pipeline stage; runs are persisted to `eval_runs` for history.
- **Cost:** the judge is itself an LLM (some variance and token cost), and the gate
  needs provider credentials in CI (skipped on fork PRs where secrets aren't
  available). We mitigate variance by keeping the judge prompts strict and
  numeric, and the `Evaluator` is an interface so a RAGAS-backed judge could be
  dropped in.

---

## ADR-0007 — One backend image, three roles

**Status:** ✅ Accepted

### Context
The API, the Celery worker, and the one-shot DB-migration job all run the same
Python application code. Building and versioning them separately invites drift.

### Decision
Build a **single** backend image (`backend/Dockerfile`). `docker-compose` runs it
three ways: `uvicorn` (API), `celery … worker` (worker), and `alembic upgrade head`
(migrate, gated before API/worker start). The frontend is a separate multi-stage
Next.js standalone image.

### Consequences
- **Gain:** one artifact to build, scan, and promote; impossible for the worker and
  API to run different code; simpler CI.
- **Cost:** the worker image carries the API's web deps (and vice versa) — a few MB
  of unused packages per role. Negligible against the drift risk it removes.
