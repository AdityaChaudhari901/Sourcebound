# AI KnowledgeOps Platform — Full Research & Concept Guide

> The goal of this document is not "how to build it" — it's **why every piece exists, what it solves, what the alternatives are, and the tradeoffs**. If you internalize this, you can explain the project from first principles to any interviewer and survive the follow-up "why?" three levels deep. That depth is the entire point.

---

## Part 0 — How to read this

Interviews don't test whether you *used* LangGraph. They test whether you *understood the problem well enough to choose* LangGraph over the alternative. So every section here follows the same shape:

**What it is → What problem it solves → Alternatives → Why we chose this → Pros/Cons → What an interviewer will probe.**

Read it once for the narrative. Read it again and quiz yourself on the "alternatives" and "cons" columns — that's where weak candidates fold.

---

## Part 1 — The problem space (start every interview here)

### The real-world problem

Knowledge inside a company is **scattered, stale, and unsearchable in a useful way**. It lives in PDFs, GitHub READMEs and code, Confluence/Notion pages, API docs, and old chat threads. When an engineer needs an answer, they either ping a senior (interrupting them), dig through a dozen sources, or — worst case — act on documentation that's six months out of date.

Three concrete failure modes:
1. **Discovery fails** — keyword search returns 200 documents, none obviously right.
2. **Trust fails** — even when you find an answer, you can't tell if it's current or correct.
3. **Context fails** — the answer is spread across three sources and nobody stitches it together.

### The use cases (have 2–3 ready to name)

- **Engineering onboarding**: a new hire asks "how do I set up the payments service locally?" and gets a stitched, *cited* answer instead of a three-hour Slack archaeology session.
- **Internal support / DevEx**: a platform team fields the same "how do I rotate a secret?" question 40 times a month; the assistant answers it with links to the source of truth.
- **Reducing senior-engineer interruptions**: the most expensive people stop being human search engines.
- **Stale-doc detection**: surfacing documentation that contradicts newer sources or hasn't been touched in a year.

### Why a normal chatbot / ChatGPT doesn't solve it

An LLM on its own has three fatal gaps for this:
1. **It doesn't know your private data** — your internal docs were never in its training set.
2. **Its knowledge is frozen and stale** — training has a cutoff; your runbook changed yesterday.
3. **It can't cite** — for an internal tool, an answer you can't trace to a source is worse than no answer, because people will act on it.

This is the exact gap **RAG (Retrieval-Augmented Generation)** was invented to close. Which brings us to the core technique.

---

## Part 2 — RAG: the core idea and why it beats the alternatives

### What RAG is, in one sentence

Instead of expecting the LLM to *know* the answer, you **retrieve the relevant pieces of your own data at query time and put them into the prompt**, so the model answers *from* that grounded context rather than from memory.

Flow: `user question → find relevant chunks of your docs → inject them into the prompt → LLM answers using them → cite the sources.`

### Why not the alternatives? (This is a top-3 interview question.)

| Approach | How it works | When it's right | Why it's wrong *here* |
|---|---|---|---|
| **Plain prompting** | Just ask the LLM | General knowledge | Doesn't know private/fresh data; hallucinates specifics; can't cite |
| **Long-context stuffing** | Dump *all* docs into the prompt | Tiny corpora (a few docs) | Cost scales with tokens; latency; context limits; "lost in the middle" degradation; doesn't scale to thousands of docs |
| **Fine-tuning** | Retrain the model on your data | Teaching *style/format/behavior* | Bad at injecting *facts* reliably; bakes knowledge in statically (instantly stale); can't cite; expensive to update on every doc change |
| **RAG** | Retrieve relevant chunks at query time | Large, changing, private knowledge that needs citations | — (this is the right tool) |

**The key mental model to say out loud:** *Fine-tuning changes how the model behaves; RAG changes what the model knows at the moment of asking.* For a knowledge base that changes daily and must be citable, you want RAG, not fine-tuning. (In production, mature systems sometimes combine both — fine-tune for style, RAG for facts — but for this project RAG is the backbone.)

### RAG's honest weaknesses (name these before the interviewer does)

- **Retrieval is the bottleneck.** "Garbage in, garbage out" — if you retrieve the wrong chunks, even a perfect LLM gives a wrong answer. *Most of the engineering effort goes into retrieval quality, not generation.*
- **More system complexity** — you now run a vector DB, an embedding pipeline, ingestion, etc.
- **Latency** — retrieval adds a step before generation.
- **Naive RAG fails silently** — it'll confidently answer from irrelevant context. (This is exactly what the corrective-RAG graph in Part 6 fixes, and it's your differentiator.)

---

## Part 3 — The RAG pipeline, stage by stage

This is the heart of the project. Each stage has real techniques and real tradeoffs. Know them cold.

```
INGESTION (offline):  load → chunk → embed → index
QUERY (online):       embed query → retrieve → rerank → generate (with citations) → verify
```

### 3.1 Loading / parsing

Turn heterogeneous sources (PDF, Markdown, HTML, code, Notion export) into clean text + metadata. The non-obvious part is **metadata** — you capture `source`, `path`, `heading hierarchy`, `last_modified`. This metadata is what later powers citations, multi-tenant filtering, and staleness detection. *Parsing quality (especially PDFs with tables/columns) is a common silent failure point* — worth mentioning as a real-world gotcha.

### 3.2 Chunking — the most underrated decision

You can't embed a whole document as one vector (it'd be too diluted) or feed a whole doc per query (too big). So you split documents into **chunks**. How you chunk dominates retrieval quality.

| Strategy | How | Pro | Con |
|---|---|---|---|
| **Fixed-size** | Every N tokens | Dead simple | Cuts mid-sentence; ignores structure |
| **Recursive** | Split on separators (paragraphs → sentences) | Respects structure; good default | Still naive about meaning |
| **Semantic** | Split where embedding similarity drops (topic shift) | Coherent chunks | More compute; needs tuning |
| **Code-aware** | Split on functions/classes (language-aware/AST) | Keeps code units intact | Language-specific |

**The core tradeoff to articulate — chunk size:**
- **Too small** → loses surrounding context, fragments meaning, you retrieve a sentence that needs its paragraph.
- **Too large** → the chunk covers multiple topics, so its single embedding is a blurry average → *poor retrieval precision*; also wastes the LLM's context budget.
- **Overlap** between chunks preserves context across boundaries, at the cost of some duplication.

Interviewer probe: *"What chunk size did you use and why?"* The correct answer is never a number — it's *"I tuned it against my eval set; for prose ~500–800 tokens with overlap worked best, code I split by function."* You justify it with **measurement**, which is why the eval harness (Part 9) matters.

### 3.3 Embeddings — turning text into meaning-vectors

An **embedding** is a fixed-length vector (e.g., 384 / 768 / 1536 numbers) that represents the *meaning* of a piece of text. Texts with similar meaning land close together in vector space. This is what lets you search by *meaning* instead of keywords.

How it's used here: a **bi-encoder** encodes each chunk independently at ingestion time (so you can precompute and store them), and encodes the query at search time, then you compare by cosine similarity / dot product.

**Tradeoffs:**
- **Dimensionality**: more dimensions = more expressive but more storage and compute. (bge-small=384, bge-base=768, OpenAI text-embedding-3-small=1536.)
- **Open vs proprietary models**: open (BGE, E5, GTE) = free, self-hostable, data stays private; proprietary (OpenAI) = sometimes higher quality and zero ops, but costs money and your data leaves your infra. *For an internal knowledge tool, "data stays private" is a real argument for open embeddings — say that.*
- **Bi-encoder is fast but lossy** — compressing a whole chunk into one vector loses nuance. That lossiness is *why we add reranking* (3.5).

### 3.4 Vector storage & retrieval

Embeddings live in a **vector database**, which is optimized for one thing: *given a query vector, find the nearest vectors fast, even across millions of them.*

**Why not brute force?** Comparing the query against every vector is O(N) — fine for 10k chunks, dead at 10M. So vector DBs use **ANN (Approximate Nearest Neighbor)** indexes — most commonly **HNSW** (a navigable graph). The tradeoff is **recall vs speed vs memory**: ANN trades a tiny bit of accuracy for massive speed. (Interviewer probe: *"What's HNSW?"* → a graph-based ANN index that finds approximate nearest neighbors quickly; you trade exactness for speed/scale.)

**Dense vs sparse vs hybrid retrieval — a guaranteed interview topic:**

| Retrieval type | Matches on | Strength | Weakness |
|---|---|---|---|
| **Dense (vector)** | Meaning/semantics | Handles synonyms & paraphrase ("how do I sign in" finds "authentication flow") | Misses exact rare terms, IDs, error codes, function names |
| **Sparse (BM25/keyword)** | Exact terms | Nails rare jargon, codes, exact tokens | No semantic understanding; misses paraphrases |
| **Hybrid** | Both, fused | Best recall — covers both failure modes | Runs two retrievers; needs a fusion step (e.g., Reciprocal Rank Fusion) |

**Why we use hybrid:** an internal tech KB is full of *both* natural-language questions *and* exact identifiers (service names, env vars, error codes). Dense alone misses the exact tokens; sparse alone misses the paraphrases. Hybrid + RRF gets both. This is a strong, specific answer that shows you understand *your data*.

### 3.5 Reranking — the cheap quality multiplier

Bi-encoder retrieval is fast but coarse, so the top-20 it returns are roughly relevant but poorly ordered. A **cross-encoder reranker** takes the query and each candidate chunk *together* and scores true relevance much more accurately.

**Why two stages?** A cross-encoder is far more accurate but far more expensive (it can't be precomputed — it must run per query-doc pair), so you *can't* run it over the whole corpus. The standard pattern:

```
retrieve top-20 cheaply (bi-encoder)  →  rerank to top-5 accurately (cross-encoder)  →  feed top-5 to the LLM
```

You get cross-encoder accuracy at bi-encoder scale. This single addition usually produces the biggest measurable quality jump in a RAG system — and you'll *prove* it with a before/after eval table (Part 9). Great interview moment.

### 3.6 Generation with citations

Finally the LLM answers, but with two hard constraints baked into the prompt:
1. **"Answer only from the provided context; if it's not there, say so."** This is your primary anti-hallucination guardrail.
2. **"Cite the source for each claim."** Every claim maps back to a chunk + its source metadata.

For an internal tool, **citations are non-negotiable** — they're what make the answer trustworthy and auditable. An uncited answer is a liability.

---

## Part 4 — Why naive RAG isn't enough (and what fixes it)

Everything in Part 3 is "naive RAG": `retrieve → stuff → generate`. It works in a demo and breaks in reality. Know its failure modes precisely:

1. **Bad retrieval, used anyway** — if the retriever returns irrelevant chunks, naive RAG *still answers from them*, confidently and wrongly.
2. **Hallucination** — the model pads gaps with plausible-sounding fabrication.
3. **Query phrasing mismatch** — the user's wording doesn't match how the docs are written, so retrieval whiffs.
4. **No "I don't know"** — naive RAG always answers, even when it shouldn't.

These failures are *silent* — the system looks confident while being wrong. Fixing them is the **engineering depth** that elevates this project, and it's done with **corrective / agentic RAG**, implemented as a LangGraph workflow.

### The family of advanced RAG (name-drop these to show range)

| Variant | Core idea |
|---|---|
| **Naive RAG** | retrieve → generate |
| **Corrective RAG (CRAG)** | grade the retrieved docs; if weak, correct course (rewrite query / web fallback) |
| **Self-RAG** | the model decides *when* to retrieve and critiques its own output |
| **Agentic RAG** | an agent/graph orchestrates retrieve/rewrite/verify/loop with explicit control flow |

Our project is **agentic/corrective RAG** built on LangGraph. The graph:

```
retrieve → grade_documents → (relevant?) 
   ├─ yes → generate
   └─ no  → rewrite_query → re-retrieve   (or web_search fallback)
generate → verify_grounding → (grounded & cited?)
   ├─ yes → return answer
   └─ no  → regenerate / re-retrieve   (capped at N loops, then degrade gracefully)
```

**What this buys you:** robustness to retrieval failure, dramatically reduced hallucination, honest "low confidence" degradation, and grounded+cited answers. **The cost (say it honestly):** more LLM calls → more latency and more money. You cap retries and you trace cost per node so it doesn't run away. That cost/quality tradeoff *is* the senior-level conversation.

---

## Part 5 — LangChain: what, why, and its honest criticism

### What it is
A framework of **composable building blocks** for LLM apps: document loaders, text splitters, embedding wrappers, vector-store adapters, retrievers, prompt templates, output parsers, and LCEL (a syntax for chaining steps), plus a huge library of integrations.

### Why use it
- You don't reinvent the glue — loaders for 100+ sources, splitters, retriever combinators (e.g., ensemble for hybrid) come for free.
- Async/streaming/batching are built into its primitives.
- It's the lingua franca — interviewers expect familiarity.

### The honest criticism (a senior engineer says this unprompted)
LangChain gets real flak: **heavy abstractions that can be leaky**, **historically frequent breaking changes**, and a tendency to **hide what's actually happening**, which hurts debugging and learning. Many production teams use it *selectively* or drop into the raw provider SDK for hot paths.

### Our stance (this is the mature answer)
> "I use LangChain at the **component layer** — loaders, splitters, retrievers, rerankers — where it genuinely saves time. I deliberately **don't** bury core logic in deep opaque chains; the orchestration lives in LangGraph where I control the flow explicitly, and I keep the LLM client behind my own interface so I'm not locked in."

That answer signals you can use a tool *and* see its limits — exactly the judgment interviewers screen for.

---

## Part 6 — LangGraph: why a graph beats a chain

### The problem with chains
LangChain "chains" are essentially **linear / DAG** pipelines: A → B → C. They can't naturally express:
- **Loops** ("retrieve → grade → if weak, go back and re-retrieve"),
- **Conditional branching** ("if grounded, return; else regenerate"),
- **Persistent state** across steps,
- **Retries / human-in-the-loop**.

Agentic RAG needs *all* of these. Forcing it into a chain becomes spaghetti.

### What LangGraph is
A library for building LLM workflows as an explicit **state machine / graph**:
- **Nodes** = steps (functions): `retrieve`, `grade_documents`, `generate`, `verify`.
- **Edges** = transitions; **conditional edges** = routing decisions.
- **State** = a shared object passed and updated across nodes (the question, retrieved docs, grades, generation, retry count).
- It supports **cycles**, **checkpointing/persistence**, **streaming**, and **human-in-the-loop**.

### Why we use it (the crisp interview line)
> "A chain is a straight line; my query engine needs to make decisions and loop — grade its own retrieval, rewrite the query, re-retrieve, and verify grounding before answering. That's a state machine, and LangGraph lets me express it as an explicit, debuggable graph instead of tangled conditionals."

### Pros / Cons
- **Pros:** explicit, inspectable control flow (you can literally draw the graph); real state management; supports the cyclic, conditional logic agentic RAG requires; debuggable.
- **Cons:** more boilerplate than a one-line chain; learning curve; **overkill for genuinely linear flows** — don't use it where a chain suffices (knowing when *not* to use it is itself a senior signal).

---

## Part 7 — Vector database: why Qdrant (and when you wouldn't bother)

### Why a dedicated vector DB at all
You need fast ANN search with **metadata filtering** (for multi-tenancy: "search only tenant X's docs"), persistence, and an API. A flat library doesn't give you that out of the box.

### The comparison (have opinions ready)

| Option | Type | Strengths | Weaknesses / when not |
|---|---|---|---|
| **Qdrant** | OSS DB (Rust) | Fast, excellent payload filtering, hybrid support, self-host or free cloud, easy Docker | Another service to run |
| **pgvector** | Postgres extension | One database for everything; simplest ops; great for small/medium | Less optimized at very large scale; fewer vector-native features |
| **Pinecone** | Managed SaaS | Zero ops, scales effortlessly | Proprietary, paid, data leaves your infra |
| **Weaviate** | OSS DB | Feature-rich, modules, hybrid | Heavier; more concepts |
| **Milvus** | OSS DB | Massive scale | Heavier ops burden |
| **Chroma** | OSS / embedded | Great for prototyping | Less production-hardened |
| **FAISS** | Library | Blazing ANN | No persistence/filtering/API — you build all that |

### Why Qdrant for this project
Free and self-hostable (no budget needed), **strong payload filtering** (which directly enables your multi-tenant isolation), hybrid support, and it's production-credible — using it signals you understand purpose-built vector infra.

### The honest nuance that impresses
> "At my project's scale, `pgvector` would actually be enough and would simplify ops to a single database. I chose Qdrant deliberately to demonstrate purpose-built vector infrastructure and metadata-filtered multi-tenancy — but I can articulate exactly when I'd downgrade to pgvector or upgrade to a managed service."

Showing you'd *not* over-engineer at small scale is a stronger signal than reflexively reaching for the heaviest tool.

---

## Part 8 — FastAPI: why it's the right backend for AI

### Why FastAPI specifically
- **Async-native (ASGI).** AI backends are overwhelmingly **I/O-bound** — waiting on the vector DB, the LLM API, Postgres. Async lets one worker handle many concurrent requests while they wait, instead of blocking. This is the single biggest reason.
- **Pydantic validation + typing** — request/response schemas are validated and self-documenting.
- **Auto OpenAPI/Swagger docs** — free interactive API docs (great for demos).
- **Streaming (SSE)** — stream LLM tokens to the client as they generate, so the user sees output immediately instead of staring at a spinner.

### Versus the alternatives
- **Flask**: sync-first (WSGI); fine for simple apps, but not built for high-concurrency I/O without extra work.
- **Django**: batteries-included (ORM, admin) but heavier and more opinionated; overkill for an API-first AI microservice.
- **FastAPI's con**: *not* batteries-included — no built-in ORM/admin, you assemble more yourself (you add SQLAlchemy, Alembic, etc.). For a focused AI API, that's a feature, not a bug.

### The CPU-bound caveat (a great detail to drop)
Async helps I/O-bound work, **not** CPU-bound work. Embedding generation is CPU/GPU-heavy and would block the event loop — so you push ingestion (parse/chunk/embed) to a **background worker (Celery)** rather than doing it inside the request. Knowing *where async helps and where it doesn't* is a senior distinction.

---

## Part 9 — Evaluation: your single biggest differentiator

### Why it matters
RAG **fails silently**. Without measurement you're flying blind — you can't tell if a change helped, and you can't *prove* quality to anyone. The line to say: *"If you can't measure it, you can't improve it — or trust it."* Most fresher projects skip this entirely, which is exactly why having it makes you stand out.

### The four metrics (know what each catches)

| Metric | Question it answers | Catches |
|---|---|---|
| **Faithfulness** | Is the answer grounded in the retrieved context? | **Hallucination** |
| **Answer relevancy** | Does the answer actually address the question? | Off-topic / evasive answers |
| **Context precision** | Are the retrieved chunks relevant (signal vs noise)? | **Bad retrieval** (too much junk) |
| **Context recall** | Did retrieval fetch *all* the needed info? | **Missing retrieval** (gaps) |

Notice precision/recall isolate **retrieval** quality while faithfulness/relevancy isolate **generation** quality — so when a number drops, you know *which half* of the pipeline to fix. Say that; it shows systems thinking.

### How
- A **golden set**: ~50 question→ideal-answer pairs over your corpus.
- **RAGAS** (or a hand-rolled **LLM-as-judge**) computes the metrics.
- **LLM-as-judge tradeoff:** scalable and cheap vs. human eval, but has biases (position, verbosity, self-preference) and needs calibration — *acknowledge this; don't pretend it's ground truth.*
- **The killer move:** wire it into **CI** so a pull request *fails the build* if faithfulness drops below threshold. You've turned "AI quality" into a regression test. Almost no fresher does this — lead your interview with it.

---

## Part 10 — Observability: Langfuse and why you trace LLM apps

LLM apps are **non-deterministic, multi-step, and cost money per call**. When an answer is wrong, you need to see *exactly* what happened: which chunks were retrieved, what the prompt was, how many tokens, how long, how much it cost — per step.

**Langfuse** (open-source LLM observability) gives you traces and spans across the whole graph, plus token/cost/latency tracking and prompt management. Why it matters: it's how you **debug** (why did this answer go wrong?), **optimize cost** (which node is burning tokens?), and **optimize latency** (where's the time going?). For an agentic graph with multiple LLM calls, this isn't optional — without it you're guessing.

---

## Part 11 — The supporting cast (one line of "why" each)

- **PostgreSQL** — relational, ACID metadata store: tenants, users, documents, ingestion jobs, conversations, eval runs. Vectors live in Qdrant; *facts and relationships* live in Postgres.
- **Redis** — in-memory store used three ways: **cache** (embeddings/retrieval results), **rate limiting**, and **Celery's message broker**.
- **Celery** — distributed task queue for **async ingestion**. Parsing/chunking/embedding a large doc is slow; you must not block the HTTP request, so you enqueue a job and a worker processes it. The user gets an immediate "job accepted, here's the status endpoint."
- **Docker / Compose** — reproducible multi-service environment; one command brings up api + worker + qdrant + postgres + redis + langfuse. *Reproducibility* is the production signal.

---

## Part 12 — The big tradeoff cheat-sheet (memorize this)

| Decision | We chose | Over | Because |
|---|---|---|---|
| Knowledge injection | RAG | Fine-tuning | Changing, private, citable knowledge |
| Small corpora alt. | RAG | Long-context stuffing | Scales; cheaper per query; no "lost in middle" |
| Retrieval | Hybrid (dense+sparse) | Dense only | KB has both prose *and* exact identifiers |
| Quality boost | Cross-encoder rerank | Bi-encoder only | Big precision gain at acceptable cost |
| Robustness | Corrective/agentic RAG | Naive RAG | Naive RAG fails silently on bad retrieval |
| Orchestration | LangGraph | LangChain chains | Need cycles, branching, state |
| LangChain scope | Components only | Deep chains | Keep flow explicit & debuggable |
| Vector store | Qdrant | pgvector / Pinecone | Free, self-host, filtering for multi-tenancy (pgvector fine at small scale) |
| Backend | FastAPI | Flask/Django | Async I/O, validation, streaming, auto-docs |
| Heavy work | Celery worker | In-request | Embedding is CPU-bound; don't block the event loop |
| Trust | Eval harness + CI gate | Nothing | RAG fails silently; measure and gate regressions |
| Debugging | Langfuse tracing | Print logs | Multi-step, non-deterministic, costed calls |

---

## Part 13 — How to explain this in an interview (layered)

Have three depths ready and read the room.

### 30-second elevator
> "It's a production-grade internal knowledge assistant. You connect your docs and code; you ask a question; it answers **with citations**. The interesting part is the query engine — it's a self-correcting workflow that checks whether its own retrieval is relevant, fixes its query if not, and verifies the answer is grounded before showing it. And I measure answer quality with an eval harness that gates regressions in CI, so I can *prove* it works."

### 2-minute overview
Walk the pipeline: *"Documents get ingested asynchronously — parsed, chunked, embedded, and indexed in a vector DB with metadata. At query time I do hybrid retrieval — dense for meaning, sparse for exact terms — then rerank with a cross-encoder to get the best few chunks. Then a LangGraph workflow takes over: it grades the retrieved docs, and if they're weak it rewrites the query and re-retrieves; it generates a cited answer and verifies the answer is actually grounded before returning it, looping if not. Everything's traced in Langfuse for cost and latency, and I have a 50-question eval set scoring faithfulness and retrieval precision/recall, run in CI as a quality gate."*

### Deep-dive (when they say "tell me about the hard part")
Go into the corrective-RAG graph (Part 6) and the eval methodology (Part 9) — those are your two deepest, most defensible areas. Draw the graph. Show the before/after eval table.

### Anticipated probes — and the one-line spine of each answer
- *"Why RAG not fine-tuning?"* → Fine-tuning changes behavior; RAG changes knowledge. KB changes daily and must be citable.
- *"How do you stop hallucination?"* → Grounded prompting + citation requirement + a verification node + honest low-confidence degradation.
- *"Why hybrid retrieval?"* → Dense misses exact identifiers; sparse misses paraphrases; my KB has both.
- *"Why rerank?"* → Bi-encoder is fast but coarse; cross-encoder is accurate but expensive — so retrieve cheap, rerank the top-k. Two-stage.
- *"Why LangGraph?"* → My flow has loops and branches and state — that's a state machine, not a chain.
- *"How do you know it's good?"* → Eval harness, four metrics, golden set, **CI gate**. (Lead with this.)
- *"How would you scale it?"* → Partition ingestion by tenant, scale Celery workers, batch embeddings, per-tenant collections, cache hot queries.
- *"What's still weak?"* → Be honest: small eval set, single region, no human-in-the-loop review yet. Self-awareness scores.

---

## Part 14 — What to read/learn next (in priority order)

1. **The original RAG idea** + why retrieval-augmentation beats parametric memory — so you can talk about it historically.
2. **Corrective RAG (CRAG) and Self-RAG** — the papers/concepts behind your graph; even a blog-level understanding lets you name-drop and compare.
3. **HNSW** at a conceptual level — enough to explain ANN vs exact search.
4. **RAGAS metrics** — what each one measures and its limitations.
5. **LangGraph state/nodes/conditional-edges** — hands-on, since this is your centerpiece.

Then start the 30-day build. The understanding you've just loaded is what makes the build *defensible* — which was always the point.
