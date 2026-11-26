"""Parsing helpers for knowledge documents.

Supported formats: plain text/markdown/CSV/TSV/RST, PDF (``pypdf``) and
DOCX (``python-docx``). Missing optional libraries produce a clear runtime
error naming the dependency instead of a silent stub.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("knowledge_documents")


def parse_document(path: Path, text: Optional[str] = None) -> str:
    """Return the text content of a knowledge document.

    Args:
        path: file path (may not exist for in-memory text uploads).
        text: in-memory content, takes precedence when provided.
    """
    if text is not None:
        return text
    lower = str(path).lower()
    if lower.endswith((".txt", ".md", ".markdown", ".csv", ".tsv", ".rst")):
        return Path(path).read_text(encoding="utf-8", errors="replace")
    if lower.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF ingestion requires 'pypdf' in backend/requirements.txt") from exc
        reader = PdfReader(str(path))
        pages = [(page.extract_text() or "") for page in reader.pages]
        content = "\n".join(pages).strip()
        if not content:
            raise ValueError(f"PDF contains no extractable text (it may be a scan): {path}")
        return content
    if lower.endswith(".docx"):
        try:
            from docx import Document
        except ImportError as exc:
            raise RuntimeError("DOCX ingestion requires 'python-docx' in backend/requirements.txt") from exc
        doc = Document(str(path))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        content = "\n".join(part for part in parts if part.strip()).strip()
        if not content:
            raise ValueError(f"DOCX contains no extractable text: {path}")
        return content
    raise ValueError(
        f"Unsupported document type: {path} (supported: .txt/.md/.csv/.tsv/.rst/.pdf/.docx)."
    )
