"""Recursive character chunking with overlap.

Splits each parsed block independently so a chunk never spans two headings, and
assigns a document-global ``position`` so chunks stay ordered for retrieval and
re-assembly. Size/overlap are configurable (see settings) and should be tuned
against an eval set.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings
from app.rag.parsing import ParsedBlock


@dataclass(frozen=True)
class TextChunk:
    text: str
    heading_path: str | None
    position: int


def chunk_blocks(
    blocks: list[ParsedBlock],
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[TextChunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or settings.chunk_size,
        chunk_overlap=chunk_overlap or settings.chunk_overlap,
        # Prefer paragraph, then line, then word, then character boundaries.
        separators=["\n\n", "\n", " ", ""],
    )

    chunks: list[TextChunk] = []
    position = 0
    for block in blocks:
        for piece in splitter.split_text(block.text):
            piece = piece.strip()
            if not piece:
                continue
            chunks.append(
                TextChunk(text=piece, heading_path=block.heading_path, position=position)
            )
            position += 1
    return chunks
