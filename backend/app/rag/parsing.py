"""Parse uploaded files into text blocks carrying a heading path.

PDF and Markdown to start. Each block keeps a ``heading_path`` so citations can
point at *where* in the document an answer came from:
- PDF  -> one block per page, heading_path = "page N".
- Markdown -> split on headings (via LangChain's MarkdownHeaderTextSplitter),
  heading_path = the joined header hierarchy (e.g. "Setup / Local").
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from app.database.models import SourceType


@dataclass(frozen=True)
class ParsedBlock:
    text: str
    heading_path: str | None


class UnsupportedFileType(Exception):
    """Raised when a file is neither PDF nor Markdown."""


def detect_source_type(filename: str | None, content_type: str | None) -> SourceType:
    name = (filename or "").lower()
    ctype = (content_type or "").lower()
    if name.endswith(".pdf") or "application/pdf" in ctype:
        return SourceType.PDF
    if name.endswith((".md", ".markdown")) or "markdown" in ctype:
        return SourceType.MARKDOWN
    raise UnsupportedFileType(
        f"Unsupported file type (filename={filename!r}, content_type={content_type!r}); "
        "only PDF and Markdown are supported."
    )


def _parse_pdf(content: bytes) -> list[ParsedBlock]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    blocks: list[ParsedBlock] = []
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            blocks.append(ParsedBlock(text=text, heading_path=f"page {index}"))
    return blocks


def _parse_markdown(content: bytes) -> list[ParsedBlock]:
    from langchain_text_splitters import MarkdownHeaderTextSplitter

    text = content.decode("utf-8", errors="replace")
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
        strip_headers=False,
    )
    sections = splitter.split_text(text)
    blocks: list[ParsedBlock] = []
    for section in sections:
        body = section.page_content.strip()
        if not body:
            continue
        headers = [section.metadata[k] for k in ("h1", "h2", "h3") if section.metadata.get(k)]
        heading_path = " / ".join(headers) if headers else None
        blocks.append(ParsedBlock(text=body, heading_path=heading_path))
    # Fallback: a markdown file with no headings is still one block.
    if not blocks and text.strip():
        blocks.append(ParsedBlock(text=text.strip(), heading_path=None))
    return blocks


def parse(
    *, filename: str | None, content: bytes, content_type: str | None
) -> tuple[SourceType, list[ParsedBlock]]:
    """Return (source_type, blocks). Raises UnsupportedFileType for other types."""
    source_type = detect_source_type(filename, content_type)
    if source_type is SourceType.PDF:
        return source_type, _parse_pdf(content)
    return source_type, _parse_markdown(content)
