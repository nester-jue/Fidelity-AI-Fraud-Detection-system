"""Lightweight PDF text extraction for claim-form documents.

Extracts text from PDF content streams: uncompressed streams are read
directly, FlateDecode streams are decompressed with zlib. Text in ``Tj`` and
``TJ`` operators is unescaped and joined in document order. This works for
genuinely-formatted insurance claim forms (text-based PDFs) without external
PDF libraries; images/scans are best-effort only.
"""

import re
import shutil
import subprocess
import zlib
from typing import List, Optional

_STREAM_RE = re.compile(rb"stream\r?\n(.*?)endstream", re.DOTALL)
_STRING_RE = re.compile(r"\((?:\\.|[^\\)])*\)", re.DOTALL)

_ESCAPES = {
    "n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f",
    "(": "(", ")": ")", "\\": "\\",
}


def _unescape_pdf_string(s: str) -> str:
    out: List[str] = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt in _ESCAPES:
                out.append(_ESCAPES[nxt])
                i += 2
            elif nxt.isdigit():
                j = i + 1
                octal = ""
                while j < len(s) and len(octal) < 3 and s[j].isdigit():
                    octal += s[j]
                    j += 1
                try:
                    out.append(chr(int(octal, 8) & 0xFF))
                except ValueError:
                    pass
                i = j
            elif nxt in "\r\n":
                i += 2
                if nxt == "\r" and i < len(s) and s[i] == "\n":
                    i += 1
            else:
                out.append(nxt)
                i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _extract_strings_from_stream(stream_bytes: bytes) -> str:
    parts: List[str] = []
    s = stream_bytes.decode("latin-1", errors="ignore")
    for m in _STRING_RE.finditer(s):
        text = _unescape_pdf_string(m.group(0)[1:-1])
        if text.strip():
            parts.append(text)
    return " ".join(parts).strip()


def _extract_with_pdftotext(file_path: str) -> Optional[str]:
    """Uses the ``pdftotext`` binary (poppler) when available; best-effort."""
    cmd = shutil.which("pdftotext")
    if not cmd:
        return None
    try:
        result = subprocess.run(
            [cmd, "-layout", file_path, "-"],
            capture_output=True, timeout=60, check=False,
        )
        if result.returncode != 0:
            return None
        text = result.stdout.decode("utf-8", errors="replace").strip()
        return text if text else None
    except Exception:
        return None


def extract_pdf_text(file_path: str) -> str:
    """Best-effort text extraction from a PDF file.

    Tries ``pdftotext`` first (handles CID fonts, XFA, and compressed
    encodings well), then falls back to the pure-Python content-stream
    extractor. Returns an empty string on failure — callers record the
    extraction error and flag the document.
    """
    text = _extract_with_pdftotext(file_path)
    if text:
        return text
    try:
        with open(file_path, "rb") as f:
            data = f.read()
    except Exception:
        return ""
    chunks: List[str] = []
    for m in _STREAM_RE.finditer(data):
        raw = m.group(1)
        try:
            try:
                content = zlib.decompress(raw)
            except Exception:
                content = raw
        except Exception:
            continue
        text = _extract_strings_from_stream(content)
        if text:
            chunks.append(text)
    return "\n\n".join(chunks).strip()
