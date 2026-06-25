"""Unit tests for recursive character chunking (app/rag/chunking.py)."""

from __future__ import annotations

from app.rag.chunking import chunk_blocks
from app.rag.parsing import ParsedBlock


def test_short_block_yields_single_chunk():
    chunks = chunk_blocks([ParsedBlock(text="Rotate the secret.", heading_path="Setup")])
    assert len(chunks) == 1
    assert chunks[0].text == "Rotate the secret."
    assert chunks[0].heading_path == "Setup"
    assert chunks[0].position == 0


def test_whitespace_only_block_yields_nothing():
    assert chunk_blocks([ParsedBlock(text="   \n\n  ", heading_path=None)]) == []


def test_positions_are_global_across_blocks():
    blocks = [
        ParsedBlock(text="First block.", heading_path="A"),
        ParsedBlock(text="Second block.", heading_path="B"),
    ]
    chunks = chunk_blocks(blocks)
    assert [c.position for c in chunks] == [0, 1]
    # Each chunk keeps its own block's heading — a chunk never spans two headings.
    assert chunks[0].heading_path == "A"
    assert chunks[1].heading_path == "B"


def test_long_block_splits_into_multiple_ordered_chunks():
    text = " ".join(f"word{i}" for i in range(200))  # well over the chunk size
    chunks = chunk_blocks([ParsedBlock(text=text, heading_path="Doc")], chunk_size=60, chunk_overlap=10)
    assert len(chunks) > 1
    # positions are contiguous 0..n-1 and every chunk is non-empty
    assert [c.position for c in chunks] == list(range(len(chunks)))
    assert all(c.text.strip() for c in chunks)
    assert all(c.heading_path == "Doc" for c in chunks)


def test_smaller_chunk_size_produces_more_chunks():
    # Note: chunk_blocks coerces a 0 overlap to the settings default (`0 or default`),
    # so use small non-zero overlaps here.
    text = " ".join(f"token{i}" for i in range(200))
    block = [ParsedBlock(text=text, heading_path=None)]
    coarse = chunk_blocks(block, chunk_size=300, chunk_overlap=10)
    fine = chunk_blocks(block, chunk_size=50, chunk_overlap=10)
    assert len(fine) > len(coarse)


def test_more_overlap_duplicates_more_content():
    text = " ".join(f"w{i}" for i in range(150))
    small = chunk_blocks([ParsedBlock(text=text, heading_path=None)], chunk_size=80, chunk_overlap=5)
    large = chunk_blocks([ParsedBlock(text=text, heading_path=None)], chunk_size=80, chunk_overlap=40)
    # Larger overlap repeats more boundary content, so total characters grow.
    assert sum(len(c.text) for c in large) > sum(len(c.text) for c in small)
