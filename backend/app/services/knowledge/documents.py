"""Parsing helpers for knowledge documents.

Phase 5 supports text documents (.txt/.md). PDF/DOCX parsing — the Phase 6
feature for ingesting Fidelity manuals, policies and procedures — is a stub
below; add `pypdf`/`python-docx` and implement here when that phase starts.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("knowledge_documents")


def parse_document(path: Path, text: Optional[str] = None) -> str:
    """Returns the text content of a knowledge document.

    Phase 5 supports text formats (.txt, .md, .csv, .tsv, .rst). PDF/DOCX
    parsing arrives in Phase 6 — the stubs below raise ``NotImplementedError``
    unless the optional libraries are installed.

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
            from pypdf import PdfReader  # Phase 6: pip install pypdf
        except ImportError:
            raise NotImplementedError(
                f"PDF parsing needs pypdf installed (Phase 6); "
                f"document: {path}"
            )
        return "\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)
    if lower.endswith(".docx"):
        try:
            from docx import Document  # Phase 6: pip install python-docx
        except ImportError:
            raise NotImplementedError(
                f"DOCX parsing needs python-docx installed (Phase 6); "
                f"document: {path}"
            )
        doc = Document(str(path))
        return "\n".join(paragraph.text for paragraph in doc.paragraphs)
    raise NotImplementedError(
        f"Unsupported document type: {path} (supported: .txt/.md/.csv/.tsv/.rst; PDF/DOCX in Phase 6)."
    )
