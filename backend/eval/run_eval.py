"""Evaluation harness CLI.

Runs the current RAG pipeline (the compiled corrective-RAG graph) over a golden
dataset, scores each answer, prints a metrics table, and persists the run to the
eval_runs table.

Usage (from backend/):
    ./.venv/bin/python eval/run_eval.py                  # full dataset
    ./.venv/bin/python eval/run_eval.py --limit 3        # quick smoke run
    ./.venv/bin/python eval/run_eval.py --dataset eval/golden.jsonl --k 3

It is self-contained: on each run it ensures an "eval-harness" tenant exists and
that the fixture docs (eval/fixtures/*.md) are ingested into it (idempotent), so
it works out of the box once Postgres + Qdrant are up.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

# Make `app` importable when run as `python eval/run_eval.py` from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.database.models import (  # noqa: E402
    Document,
    DocumentStatus,
    EvalRun,
    SourceType,
    Tenant,
)
from app.database.session import sync_session  # noqa: E402
from app.graphs.graph import get_query_graph  # noqa: E402
from app.services.ingestion_service import _index_document  # noqa: E402

from eval.metrics import Scores, get_evaluator  # noqa: E402

EVAL_TENANT = "eval-harness"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


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


def load_dataset(path: Path) -> list[dict]:
    with path.open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


def run_pipeline(graph, question: str, tenant_id: uuid.UUID, k: int) -> tuple[str, list, list]:
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


def print_table(rows: list[tuple[dict, Scores]], agg: Scores) -> None:
    print(f"\n{'#':>2}  {'question':<44}  faith  relev  precis  recall")
    print("-" * 82)
    for i, (row, s) in enumerate(rows, start=1):
        q = row["question"][:42]
        print(
            f"{i:>2}  {q:<44}  {s.faithfulness:>5.2f}  {s.answer_relevancy:>5.2f}  "
            f"{s.context_precision:>6.2f}  {s.context_recall:>6.2f}"
        )
    print("-" * 82)
    print(
        f"    {'AGGREGATE (mean)':<44}  {agg.faithfulness:>5.2f}  {agg.answer_relevancy:>5.2f}  "
        f"{agg.context_precision:>6.2f}  {agg.context_recall:>6.2f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the RAG eval harness.")
    parser.add_argument("--dataset", default=str(Path(__file__).resolve().parent / "golden.jsonl"))
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N questions.")
    parser.add_argument("--k", type=int, default=3, help="Top-k passed to the LLM.")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    print(f"Ensuring eval corpus ({EVAL_TENANT})...")
    tenant_id = ensure_corpus()

    dataset = load_dataset(dataset_path)
    if args.limit:
        dataset = dataset[: args.limit]
    print(f"Running {len(dataset)} question(s) through the pipeline...\n")

    evaluator = get_evaluator()
    graph = get_query_graph()
    results: list[tuple[dict, Scores]] = []

    for i, row in enumerate(dataset, start=1):
        answer, contexts, sources = run_pipeline(graph, row["question"], tenant_id, args.k)
        scores = evaluator.evaluate(
            question=row["question"],
            answer=answer,
            contexts=contexts,
            retrieved_sources=sources,
            ideal_sources=row["ideal_sources"],
            ground_truth=row["ground_truth"],
        )
        results.append((row, scores))
        print(f"  [{i}/{len(dataset)}] scored: {row['question'][:50]}")

    agg = Scores(
        faithfulness=_mean([s.faithfulness for _, s in results]),
        answer_relevancy=_mean([s.answer_relevancy for _, s in results]),
        context_precision=_mean([s.context_precision for _, s in results]),
        context_recall=_mean([s.context_recall for _, s in results]),
    )
    print_table(results, agg)

    # Persist the run.
    with sync_session() as db:
        run = EvalRun(
            dataset=dataset_path.name,
            num_questions=len(results),
            llm_model=evaluator.model_name,
            faithfulness=agg.faithfulness,
            answer_relevancy=agg.answer_relevancy,
            context_precision=agg.context_precision,
            context_recall=agg.context_recall,
            details=[
                {
                    "question": row["question"],
                    "faithfulness": s.faithfulness,
                    "answer_relevancy": s.answer_relevancy,
                    "context_precision": s.context_precision,
                    "context_recall": s.context_recall,
                }
                for row, s in results
            ],
        )
        db.add(run)
        db.commit()
        print(f"\nPersisted eval_run {run.id}")


if __name__ == "__main__":
    main()
