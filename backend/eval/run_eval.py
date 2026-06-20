"""Evaluation harness CLI.

Runs the current RAG pipeline (the compiled corrective-RAG graph) over a golden
dataset, scores each answer, prints a metrics table, and persists the run to the
eval_runs table.

Modes:
    # single run (optionally gate CI on faithfulness)
    ./.venv/bin/python eval/run_eval.py
    ./.venv/bin/python eval/run_eval.py --min-faithfulness 0.8
    ./.venv/bin/python eval/run_eval.py --limit 3

    # compare two configs, print a side-by-side delta table (for the README)
    ./.venv/bin/python eval/run_eval.py --compare dense hybrid_rerank
    ./.venv/bin/python eval/run_eval.py --compare naive corrective

Presets toggle retrieval/pipeline settings, so you can isolate the effect of each
stage. Self-contained: ensures an "eval-harness" tenant with the fixture docs
ingested (idempotent), so it works out of the box once Postgres + Qdrant are up.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

# Make `app` importable when run as `python eval/run_eval.py` from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.database.models import (  # noqa: E402
    Document,
    DocumentStatus,
    EvalRun,
    SourceType,
    Tenant,
)
from app.database.session import sync_session  # noqa: E402
from app.graphs.graph import get_query_graph  # noqa: E402
from app.rag.reranking import get_reranker  # noqa: E402
from app.services.ingestion_service import _index_document  # noqa: E402

from eval.metrics import Scores, get_evaluator  # noqa: E402

EVAL_TENANT = "eval-harness"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Config presets toggle the dimensions that settings control, so a comparison
# isolates the effect of a stage (retrieval style, rerank, corrective loop).
CONFIG_PRESETS: dict[str, dict] = {
    "dense": {"retriever_mode": "dense", "rerank_enabled": False, "max_query_retries": 0},
    "hybrid": {"retriever_mode": "hybrid", "rerank_enabled": False, "max_query_retries": 0},
    "hybrid_rerank": {"retriever_mode": "hybrid", "rerank_enabled": True, "max_query_retries": 0},
    "naive": {"retriever_mode": "dense", "rerank_enabled": False, "max_query_retries": 0},
    "corrective": {"retriever_mode": "hybrid", "rerank_enabled": True, "max_query_retries": 2},
}


@contextmanager
def use_preset(name: str):
    """Temporarily apply a config preset (mutate settings + reset the cached
    retriever/reranker so they pick up the change), then restore."""
    overrides = CONFIG_PRESETS[name]
    original = {k: getattr(settings, k) for k in overrides}
    try:
        for key, value in overrides.items():
            setattr(settings, key, value)
        get_reranker.cache_clear()  # cached on rerank_enabled; retriever reads settings live
        yield
    finally:
        for key, value in original.items():
            setattr(settings, key, value)
        get_reranker.cache_clear()


def ensure_corpus() -> uuid.UUID:
    """Ensure the eval tenant exists and the fixtures are ingested (idempotent)."""
    with sync_session() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.name == EVAL_TENANT))
        if tenant is None:
            tenant = Tenant(name=EVAL_TENANT)
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
        tenant_id = tenant.id

    for path in sorted(FIXTURES.glob("*.md")):
        source_uri = path.name
        with sync_session() as db:
            exists = db.scalar(
                select(Document).where(
                    Document.tenant_id == tenant_id, Document.uri == source_uri
                )
            )
            if exists is not None:
                continue
            doc = Document(
                tenant_id=tenant_id,
                source_type=SourceType.MARKDOWN,
                uri=source_uri,
                title=path.stem,
                status=DocumentStatus.PENDING,
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            doc_id = doc.id

        _index_document(
            doc_id,
            tenant_id=tenant_id,
            filename=path.name,
            content=path.read_bytes(),
            content_type="text/markdown",
            source_uri=source_uri,
        )
        with sync_session() as db:
            doc = db.get(Document, doc_id)
            doc.status = DocumentStatus.READY
            db.commit()
        print(f"  ingested fixture: {source_uri}")

    return tenant_id


def load_dataset(path: Path, limit: int | None) -> list[dict]:
    with path.open() as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    return rows[:limit] if limit else rows


def _run_pipeline(graph, question: str, tenant_id: uuid.UUID, k: int) -> tuple[str, list, list]:
    final = graph.invoke(
        {
            "question": question,
            "documents": [],
            "documents_relevant": False,
            "generation": "",
            "retries": 0,
        },
        config={"configurable": {"k": k, "tenant_id": str(tenant_id), "history": None}},
    )
    docs = final["documents"]
    return final["generation"], [d.text for d in docs], [d.source_uri for d in docs]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def run_dataset(
    dataset: list[dict], tenant_id: uuid.UUID, k: int
) -> tuple[list[tuple[dict, Scores]], Scores]:
    evaluator = get_evaluator()
    graph = get_query_graph()
    results: list[tuple[dict, Scores]] = []
    for i, row in enumerate(dataset, start=1):
        answer, contexts, sources = _run_pipeline(graph, row["question"], tenant_id, k)
        scores = evaluator.evaluate(
            question=row["question"],
            answer=answer,
            contexts=contexts,
            retrieved_sources=sources,
            ideal_sources=row["ideal_sources"],
            ground_truth=row["ground_truth"],
        )
        results.append((row, scores))
        print(f"    [{i}/{len(dataset)}] {row['question'][:48]}")
    agg = Scores(
        faithfulness=_mean([s.faithfulness for _, s in results]),
        answer_relevancy=_mean([s.answer_relevancy for _, s in results]),
        context_precision=_mean([s.context_precision for _, s in results]),
        context_recall=_mean([s.context_recall for _, s in results]),
    )
    return results, agg


def persist_run(dataset_name: str, results: list[tuple[dict, Scores]], agg: Scores) -> uuid.UUID:
    with sync_session() as db:
        run = EvalRun(
            dataset=dataset_name,
            num_questions=len(results),
            llm_model=get_evaluator().model_name,
            faithfulness=agg.faithfulness,
            answer_relevancy=agg.answer_relevancy,
            context_precision=agg.context_precision,
            context_recall=agg.context_recall,
            details=[
                {"question": row["question"], **vars(s)} for row, s in results
            ],
        )
        db.add(run)
        db.commit()
        return run.id


def print_table(results: list[tuple[dict, Scores]], agg: Scores) -> None:
    print(f"\n{'#':>2}  {'question':<44}  faith  relev  precis  recall")
    print("-" * 82)
    for i, (row, s) in enumerate(results, start=1):
        print(
            f"{i:>2}  {row['question'][:42]:<44}  {s.faithfulness:>5.2f}  "
            f"{s.answer_relevancy:>5.2f}  {s.context_precision:>6.2f}  {s.context_recall:>6.2f}"
        )
    print("-" * 82)
    print(
        f"    {'AGGREGATE (mean)':<44}  {agg.faithfulness:>5.2f}  {agg.answer_relevancy:>5.2f}  "
        f"{agg.context_precision:>6.2f}  {agg.context_recall:>6.2f}"
    )


def print_delta(a_name: str, b_name: str, a: Scores, b: Scores) -> None:
    print(f"\nCONFIG COMPARISON: {a_name}  vs  {b_name}\n")
    print(f"{'metric':<20}{a_name:>12}{b_name:>14}{'delta':>10}")
    print("-" * 56)
    for metric in ("faithfulness", "answer_relevancy", "context_precision", "context_recall"):
        av, bv = getattr(a, metric), getattr(b, metric)
        delta = bv - av
        print(f"{metric:<20}{av:>12.2f}{bv:>14.2f}{delta:>+10.2f}")
    print("-" * 56)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the RAG eval harness.")
    parser.add_argument("--dataset", default=str(Path(__file__).resolve().parent / "golden.jsonl"))
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N questions.")
    parser.add_argument("--k", type=int, default=3, help="Top-k passed to the LLM.")
    parser.add_argument(
        "--compare", nargs=2, metavar=("A", "B"),
        help=f"Compare two presets: {', '.join(CONFIG_PRESETS)}",
    )
    parser.add_argument(
        "--min-faithfulness", type=float, default=None,
        help="Exit non-zero if aggregate faithfulness is below this (CI gate).",
    )
    args = parser.parse_args()

    print(f"Ensuring eval corpus ({EVAL_TENANT})...")
    tenant_id = ensure_corpus()
    dataset = load_dataset(Path(args.dataset), args.limit)
    dataset_name = Path(args.dataset).name

    if args.compare:
        a_name, b_name = args.compare
        for name in (a_name, b_name):
            if name not in CONFIG_PRESETS:
                parser.error(f"unknown preset {name!r}; choose from {list(CONFIG_PRESETS)}")
        print(f"\n[{a_name}] running {len(dataset)} question(s)...")
        with use_preset(a_name):
            results_a, agg_a = run_dataset(dataset, tenant_id, args.k)
            persist_run(f"{dataset_name} [{a_name}]", results_a, agg_a)
        print(f"\n[{b_name}] running {len(dataset)} question(s)...")
        with use_preset(b_name):
            results_b, agg_b = run_dataset(dataset, tenant_id, args.k)
            persist_run(f"{dataset_name} [{b_name}]", results_b, agg_b)
        print_delta(a_name, b_name, agg_a, agg_b)
        return 0

    print(f"Running {len(dataset)} question(s) through the pipeline...\n")
    results, agg = run_dataset(dataset, tenant_id, args.k)
    print_table(results, agg)
    run_id = persist_run(dataset_name, results, agg)
    print(f"\nPersisted eval_run {run_id}")

    if args.min_faithfulness is not None and agg.faithfulness < args.min_faithfulness:
        print(
            f"\nFAIL: faithfulness {agg.faithfulness:.2f} < threshold {args.min_faithfulness:.2f}"
        )
        return 1
    if args.min_faithfulness is not None:
        print(f"\nPASS: faithfulness {agg.faithfulness:.2f} >= {args.min_faithfulness:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
