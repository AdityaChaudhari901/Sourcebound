"""Evaluation metrics behind an Evaluator interface.

Four metrics, split by which half of the pipeline they diagnose:

  RETRIEVAL  | context_precision  - of the retrieved chunks, how many are relevant
             | context_recall     - of the sources that SHOULD be found, how many were
  GENERATION | faithfulness       - is the answer grounded in the retrieved context
             | answer_relevancy   - does the answer actually address the question

Retrieval metrics are computed deterministically from the golden ``ideal_sources``
(no LLM, no judge bias). Generation metrics use an LLM-as-judge (our configured
provider) because "grounded" and "on-topic" need semantic judgement.

The default LLMJudgeEvaluator is one implementation of the Evaluator protocol; a
RAGAS-backed evaluator could be dropped in behind the same interface.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.rag.providers.llm import get_llm_provider


@dataclass(frozen=True)
class Scores:
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float


@runtime_checkable
class Evaluator(Protocol):
    def evaluate(
        self,
        *,
        question: str,
        answer: str,
        contexts: list[str],
        retrieved_sources: list[str],
        ideal_sources: list[str],
        ground_truth: str,
    ) -> Scores: ...


def _source_precision_recall(retrieved: list[str], ideal: list[str]) -> tuple[float, float]:
    ideal_set = {s.lower() for s in ideal}
    retrieved_set = {s.lower() for s in retrieved}
    if not retrieved_set:
        return 0.0, (0.0 if ideal_set else 1.0)
    hits = retrieved_set & ideal_set
    precision = len(hits) / len(retrieved_set)
    recall = len(hits) / len(ideal_set) if ideal_set else 1.0
    return precision, recall


_FAITHFULNESS_SYSTEM = (
    "You are a strict grader. Given CONTEXT and an ANSWER, rate how fully the answer "
    "is supported by the context. 1.0 = every claim is directly supported; 0.0 = the "
    "answer makes claims not found in the context (hallucination). "
    "Reply with ONLY a number between 0 and 1."
)

_RELEVANCY_SYSTEM = (
    "You are a strict grader. Given a QUESTION and an ANSWER, rate how directly the "
    "answer addresses the question. 1.0 = fully on-topic and responsive; 0.0 = "
    "evasive, off-topic, or a non-answer. Reply with ONLY a number between 0 and 1."
)


def _parse_score(raw: str) -> float:
    match = re.search(r"\d*\.?\d+", raw)
    if not match:
        return 0.0
    return max(0.0, min(1.0, float(match.group(0))))


class LLMJudgeEvaluator:
    """LLM-as-judge for generation metrics; source-overlap for retrieval metrics."""

    def __init__(self) -> None:
        self._llm = get_llm_provider()

    @property
    def model_name(self) -> str:
        return self._llm.model_name

    def _judge(self, system: str, user: str) -> float:
        return _parse_score(self._llm.complete(system=system, user=user))

    def evaluate(
        self,
        *,
        question: str,
        answer: str,
        contexts: list[str],
        retrieved_sources: list[str],
        ideal_sources: list[str],
        ground_truth: str,
    ) -> Scores:
        precision, recall = _source_precision_recall(retrieved_sources, ideal_sources)

        context_block = "\n\n".join(contexts) if contexts else "(no context retrieved)"
        faithfulness = self._judge(
            _FAITHFULNESS_SYSTEM,
            f"CONTEXT:\n{context_block}\n\nANSWER:\n{answer}\n\nScore (0-1):",
        )
        relevancy = self._judge(
            _RELEVANCY_SYSTEM,
            f"QUESTION:\n{question}\n\nANSWER:\n{answer}\n\nScore (0-1):",
        )
        return Scores(
            faithfulness=faithfulness,
            answer_relevancy=relevancy,
            context_precision=precision,
            context_recall=recall,
        )


def get_evaluator() -> Evaluator:
    return LLMJudgeEvaluator()
