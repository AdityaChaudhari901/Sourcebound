"""Grounded RAG prompt construction and the anti-hallucination contract.

The whole point of Sourcebound is trustworthy, citable answers, so the prompt is
strict: answer ONLY from the numbered context, cite every claim, and when the
context doesn't cover the question, emit a fixed insufficiency sentence instead
of guessing. ``INSUFFICIENT_ANSWER`` is matched downstream to drop citations.
"""

from __future__ import annotations

from app.rag.retrievers import RetrievedChunk

INSUFFICIENT_ANSWER = (
    "I don't have enough information in the provided sources to answer that."
)

SYSTEM_PROMPT = (
    "You are Sourcebound, a citation-grounded assistant for internal knowledge.\n"
    "Follow these rules without exception:\n"
    "1. Answer ONLY using the numbered context below. Do not use outside or prior "
    "knowledge.\n"
    "2. Cite the sources you use inline with bracketed numbers like [1] or [2], "
    "matching the context items, for every claim you make.\n"
    f"3. If the context does not contain enough information to answer, reply with "
    f"exactly this sentence and nothing else: \"{INSUFFICIENT_ANSWER}\"\n"
    "4. Do not speculate, infer beyond the text, or fabricate citations.\n"
    "5. Be concise and direct."
)


def build_context_block(chunks: list[RetrievedChunk]) -> str:
    blocks = []
    for index, chunk in enumerate(chunks, start=1):
        location = chunk.source_uri
        if chunk.heading_path:
            location += f" — {chunk.heading_path}"
        blocks.append(f"[{index}] (source: {location})\n{chunk.text}")
    return "\n\n".join(blocks)


def build_history_block(history: list[dict] | None) -> str:
    """Compact prior-turns block (already bounded by the caller)."""
    if not history:
        return ""
    lines = [f"{turn['role']}: {turn['content']}" for turn in history]
    return "Conversation so far (for context only — still answer ONLY from the sources):\n" + (
        "\n".join(lines) + "\n\n"
    )


def build_user_prompt(
    question: str, chunks: list[RetrievedChunk], history: list[dict] | None = None
) -> str:
    return (
        f"{build_history_block(history)}"
        f"Context:\n{build_context_block(chunks)}\n\n"
        f"Question: {question}\n\n"
        "Answer (grounded in the context, with [n] citations):"
    )


# --- Relevance grader (LLM-as-grader for corrective RAG) ---------------------------
#
# Calibration is baked into the rubric: the grader is a coarse noise filter, not a
# judge of whether a doc *fully answers* the question. It is biased toward RECALL
# (keep a doc that is even partially related) because the grounded answer prompt
# above is the real backstop against using off-topic context — dropping a doc that
# holds the answer is the costlier error. The output is a hard JSON list of indices
# (binary keep/drop), which is less wobbly than a fuzzy 0-1 score.

GRADER_SYSTEM = (
    "You are a relevance grader for a retrieval system. You are given a question and "
    "a numbered list of retrieved documents.\n"
    "A document is RELEVANT if it contains facts, keywords, identifiers, or context "
    "that help answer the question — even partially. It does NOT need to fully answer "
    "the question on its own.\n"
    "Be inclusive: when genuinely unsure about a document, keep it. Only drop "
    "documents that are clearly about a different topic.\n"
    "Output ONLY a JSON array of the relevant document numbers, e.g. [1, 3]. "
    "If none are relevant, output []. No prose, no explanation."
)


def build_grader_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    items = "\n\n".join(f"[{i}] {chunk.text}" for i, chunk in enumerate(chunks, start=1))
    return (
        f"Question: {question}\n\n"
        f"Documents:\n{items}\n\n"
        "JSON array of the relevant document numbers:"
    )


# --- Query rewriter (corrective RAG: reformulate for better retrieval) -------------

REWRITE_SYSTEM = (
    "You reformulate a user's question into a single improved search query for an "
    "internal technical knowledge base. Preserve the original intent exactly. Make it "
    "more retrievable: clearer keywords, likely exact identifiers (service names, env "
    "vars, error codes) and synonyms that would appear in the docs. "
    "Output ONLY the reformulated query — no quotes, no preamble."
)


def build_rewrite_prompt(question: str) -> str:
    return f"Original question: {question}\n\nReformulated search query:"


# --- Grounding verifier (the verify node's confidence signal) ----------------------

VERIFY_SYSTEM = (
    "You are a strict grounding verifier. Given CONTEXT and an ANSWER, rate from 0 to 1 "
    "how fully the answer is supported by the context: 1.0 = every claim is directly "
    "supported; 0.0 = the answer makes claims not found in the context. "
    "Reply with ONLY a number between 0 and 1."
)


def build_verify_prompt(answer: str, chunks: list[RetrievedChunk]) -> str:
    return (
        f"CONTEXT:\n{build_context_block(chunks)}\n\n"
        f"ANSWER:\n{answer}\n\nGrounding score (0-1):"
    )
