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


def build_user_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    return (
        f"Context:\n{build_context_block(chunks)}\n\n"
        f"Question: {question}\n\n"
        "Answer (grounded in the context, with [n] citations):"
    )
