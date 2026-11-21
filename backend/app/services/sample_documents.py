"""Genuine sample claim-form documents — ingestion service (NEXA phases 6-8).

Ingests the genuine, publicly-available claim forms from
``data/sample_claim_documents`` (organized by category) into the OCR
pipeline: one ``OCRDocument`` row per PDF, system-wide (``claim_id=None``,
``is_sample_document=True``) so Claims Officers, Fraud Investigators,
Compliance Officers, Management and System Admins can browse them on the
existing OCR dashboards.

OCR: text extraction with the existing ``DocumentVerificationModule`` +
``pdf_text_extractor`` (pdftotext-based, pure-Python fallback). Structured
field extraction is generic (label + regex based) so it works across the
real forms and new forms; see ``extract_claim_fields``.

Idempotent: documents whose file paths already exist in the store are
skipped. Re-runs report extracted/failed counts.
"""

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.sqlalchemy_models import OCRDocument, RoleEnum, User
from ..ocr.pdf_text_extractor import extract_pdf_text
from ..ocr.ocr_service import document_verifier
from ..services.db import SessionLocal

logger = logging.getLogger("sample_documents")

SAMPLE_DOC_DIR = Path(settings.SAMPLE_CLAIM_DOCUMENTS_DIR)
REGISTER_FILE = Path(SAMPLE_DOC_DIR / "DOCUMENT_REGISTER.md")

CATEGORIES = ["life_insurance", "medical_insurance", "funeral_claims", "hospitalisation", "accident_disability"]

# Category keywords, checked in order against the (lowercased) document text.
CATEGORY_KEYWORDS: List[Tuple[str, List[str]]] = [
    ("funeral_claims", ["funeral", "burial", "cremation", "undertaker", "memorial", "funeral benefit",
                        "funding death", "final expense"]),
    ("life_insurance", ["death benefit", "certificate of death", "proof of death", "policyholder statement",
                        "statement of claimant", "declaration of claimant", "life assurance claim",
                        "death claim form", "declaration of death", "death certificate", "death benefit claim"]),
    ("medical_insurance", ["reimbursement", "medical aid", "doctor consultation", "consultation fee",
                           "medical claim form", "hospital admission", "physician fee", "medical expense claim",
                           "pre/post hospitalization", "medical treatment claim", "patient statement",
                           "medical advice", "medical consultation"]),
    ("hospitalisation", ["discharge summary", "hospital discharge", "method of admission", "discharging consultant",
                         "date of admission", "patient details", "g.p. details", "clinical narrative",
                         "discharge documentation", "nhs/ hosp no."]),
    ("accident_disability", ["personal accident", "disablement claim", "temporary total disablement",
                             "permanent total disablement", "accident claim form", "disability claim",
                             "injury assessment", "permanent partial", "total permanent"]),
]

# Filename category hints, checked FIRST: the intake filenames carry the
# category (e.g. "funeral_claims_uwrf_funeral_claim_form.pdf",
# "life_insurance_pearlnylife_death_claim_form.pdf"). Text extraction can be
# ambiguous — some death claim forms mention funerals in attachment rules.
FILENAME_CATEGORY_HINTS: List[Tuple[str, List[str]]] = [
    ("funeral_claims", ["funeral", "burial", "cremation"]),
    ("life_insurance", ["death", "declaration", "statement"]),
    ("medical_insurance", ["medical", "doctor", "physician", "consultation", "reimbursement"]),
    ("hospitalisation", ["discharge", "admission", "hospital"]),
    ("accident_disability", ["accident", "disability", "personal"]),
]


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def categorize_sample_document(filename: str, text: str) -> str:
    lower = filename.lower()
    for category, hints in FILENAME_CATEGORY_HINTS:
        if any(h in lower for h in hints):
            return category
    t = text.lower()
    for category, keywords in CATEGORY_KEYWORDS:
        if any(k in t for k in keywords):
            return category
    return "other"


# ---------------------------------------------------------------------------
# Structured field extraction (label + regex patterns over OCR text)
# ---------------------------------------------------------------------------

def _label_value(text: str, labels: List[str], max_len: int = 150) -> Optional[str]:
    """Returns the value of the first occurrence of any ``label`` in ``text``."""
    t = text.replace("\r", " ")
    for label in labels:
        # Direct label match anywhere: "Label: value" or "Label value"
        m = re.search(rf"{re.escape(label)}\s*[:\-]?\s+([^\n]{{1,{max_len}}})", t, re.IGNORECASE)
        if m:
            value = m.group(1).strip().rstrip(" .;:")
            if value:
                return value[:max_len]
    return None


def _first_match(text: str, patterns: List[str], max_len: int = 150) -> Optional[str]:
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if m:
            value = m.group(1).strip().rstrip(" .;:")
            if value:
                return value[:max_len]
    return None


def _extract_policy_number(text: str) -> Optional[str]:
    value = _label_value(text, ["policy number", "policy no", "policy ref", "policy",
                                "plan number", "contract number", "policy number/ref"])
    if value:
        return value
    return _first_match(text, [
        r"\b(POL[A-Z0-9]{2,20})\b",
        r"\b([A-Z]{2,6}\d{5,10}(?:-[A-Z0-9]+)?[^\n]{0,10})\b",
    ])


def _extract_claim_number(text: str) -> Optional[str]:
    value = _label_value(text, ["claim number", "claim no", "claim reference", "claim id"])
    if value:
        return value
    return _first_match(text, [r"\b(CLM[-\d]{2,20})\b", r"\b(C[A-Z]{2,4}[A-Z0-9-]{2,20})\b"])


def _extract_claimant_name(text: str) -> Optional[str]:
    for label in ("name of policyholder", "name of insured", "name of claimant", "name of member",
                  "name of principal", "full names and surname", "full name of", "surname",
                  "policyholder name", "name of dependant", "contact name"):
        value = _label_value(text, [label])
        if value:
            return value
    return _first_match(text, [
        r"^\s*Name\s*[:\-]?\s*([A-Z][A-Za-z]+(?:\s+[A-Za-z.]+){0,3})",
        r"\b(Dr\s+[A-Z][A-Za-z]+\s+[A-Z][A-Za-z]+)",
    ])


def _extract_amount(text: str, max_len: int = 30) -> Optional[float]:
    value = _label_value(text, ["claim amount", "claimed amount", "claim value", "amount claimed",
                                "total amount", "sum claimed", "benefit amount", "payment amount"], max_len=max_len)
    if value:
        m = re.search(r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)", value.replace(",", ""))
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass
    return None


def _extract_dates_generic(text: str) -> List[str]:
    # Reuse the verifier's extraction helper (YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY).
    return document_verifier._extract_dates(text)


def extract_claim_fields(text: str) -> Dict[str, Any]:
    """Extracts structured claim-form fields from OCR text (generic, real-form friendly)."""
    fields: Dict[str, Any] = {}
    fields["claimant_name"] = _extract_claimant_name(text)
    fields["policy_number"] = _extract_policy_number(text)
    fields["claim_number"] = _extract_claim_number(text)
    fields["national_id"] = document_verifier._extract_national_ids(text)
    fields["date_of_birth"] = _label_value(text, ["date of birth", "dob", "birth date"]) or _first_match(text, [
        r"\b\d{2}/\d{2}/\d{4}\b(?!.*?\b(?:accident|death|incident|discharge)\b)",
        r"\b\d{2}-\d{2}-\d{4}\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b(?:born|birth)\s*\w*\s*[:\-]?\s*(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})\b",
    ])
    fields["incident_date"] = _label_value(text, ["date of death", "date of incident", "date of accident",
                                                  "date of loss", "incident date", "date of event",
                                                  "date ofmedical treatment", "date of medical treatment",
                                                  "date of treatment", "date of hospitalisation",
                                                  "date of hospitalization", "date of medical event"])
    fields["claimed_amount"] = _extract_amount(text)
    fields["medical_practitioner"] = _label_value(text, ["dr.", "doctor", "physician", "medical practitioner",
                                                          "consultant", "surgeon"])
    fields["hospital_name"] = _label_value(text, ["hospital", "health care provider", "medical aid provider",
                                                  "medical institution", "health facility"])
    fields["diagnosis"] = _label_value(text, ["diagnosis", "diagnosis at discharge", "reason for admission",
                                              "medical condition", "complaint", "injury description"])
    fields["beneficiary_name"] = _label_value(text, ["beneficiary", "payee name", "payee"])
    fields["dates_observed"] = _extract_dates_generic(text)
    fields["signature_declarations"] = [
        ln.strip() for ln in text.split("\n")
        if re.search(r"\b(signed|signature|declaration|certify|confirmed)\b", ln, re.IGNORECASE)
    ][:8]
    fields["supporting_documents"] = [
        ln.strip() for ln in text.split("\n")
        if re.search(r"\b(attach|enclose|supporting doc|certificate|statement)\b", ln, re.IGNORECASE)
    ][:8]
    return {k: v for k, v in fields.items() if v not in (None, "", [])}


# ---------------------------------------------------------------------------
# Register (institution + source link for each downloaded document)
# ---------------------------------------------------------------------------

def parse_source_info(path: Path) -> Tuple[Optional[str], Optional[str]]:
    """Reads DOCUMENT_REGISTER.md for institution + URL of a downloaded file.

    Register rows are Markdown table rows:
    ``| # | File | Category | Source Institution | Source URL | Size |`` —
    after stripping the outer pipes, filename is column 2, institution 3, URL 4.
    """
    if not REGISTER_FILE.exists():
        return None, None
    try:
        for line in REGISTER_FILE.read_text(encoding="utf-8").splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 3:
                continue
            # Skip header row and the table separator row.
            if cells[1].lower() == "file" or all(set(c) <= {"-", ":"} for c in cells[1:]):
                continue
            if cells[1] == path.name:
                institution = cells[3] if len(cells) > 3 else None
                url = cells[4] if len(cells) > 4 else None
                return (institution or None, url or None)
    except Exception:
        pass
    return None, None


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def iter_sample_pdf_files(docs_dir: Optional[Path] = None) -> List[Path]:
    directory = Path(docs_dir or SAMPLE_DOC_DIR)
    if not directory.is_dir():
        return []
    return sorted(directory.rglob("*.pdf"))


def _admin_user_id(db: Session) -> int:
    user = db.query(User).filter(User.role == RoleEnum.SYSTEM_ADMIN).first()
    return user.id if user else db.query(User).first().id


def ingest_sample_documents(db: Optional[Session] = None) -> Dict[str, Any]:
    """Ingests genuine sample claim forms into the OCR pipeline. Idempotent."""
    session = db or SessionLocal()
    try:
        ingested: List[str] = []
        skipped: List[str] = []
        errors: List[str] = []
        for path in iter_sample_pdf_files():
            if session.query(OCRDocument).filter(OCRDocument.file_path == str(path)).first():
                skipped.append(path.name)
                continue
            try:
                text = extract_pdf_text(str(path))
                category = categorize_sample_document(path.name, text)
                ocr_result = document_verifier.process_document(str(path))
                raw_text = text or ocr_result.get("raw_text_snippet", "")
                extracted_fields = extract_claim_fields(raw_text)
                missing_fields = list(ocr_result.get("missing_fields") or [])
                if extracted_fields.get("claimant_name") is None and "Claimant Name" not in missing_fields:
                    missing_fields.append("Claimant Name")
                if extracted_fields.get("policy_number") is None and "Policy Number" not in missing_fields:
                    missing_fields.append("Policy Number")
                institution, url = parse_source_info(path)
                doc = OCRDocument(
                    claim_id=None,
                    uploaded_by_id=_admin_user_id(session),
                    filename=path.name,
                    file_path=str(path),
                    mime_type="application/pdf",
                    document_type=ocr_result.get("document_type"),
                    file_size_bytes=path.stat().st_size if path.exists() else 0,
                    document_hash_sha256=ocr_result.get("document_hash_sha256") or "",
                    ocr_engine="PDF-Text-Extraction (pdftotext) + DocumentVerificationModule",
                    raw_text=(raw_text or "")[:50000],
                    confidence_score=0.85 if text else 0.35,
                    extracted_fields=extracted_fields,
                    extracted_dates=list(ocr_result.get("extracted_dates") or []),
                    extracted_amounts=list(ocr_result.get("extracted_amounts") or []),
                    extracted_national_ids=list(ocr_result.get("extracted_national_ids") or []),
                    processing_status="completed" if text.strip() else "failed",
                    has_date_mismatch=bool(ocr_result.get("date_mismatch")),
                    missing_fields=missing_fields,
                    flags=list(ocr_result.get("flags") or []),
                    is_sample_document=True,
                    sample_category=category,
                    source_institution=institution,
                    source_url=url,
                    uploaded_at=datetime.now(timezone.utc),
                )
                session.add(doc)
                ingested.append(f"{path.name} [{category}]")
            except Exception as exc:
                errors.append(f"{path.name}: {exc}")
                logger.exception("sample_documents: failed to ingest %s", path.name)
        session.commit()
        return {"ingested": ingested, "skipped": skipped, "errors": errors}
    finally:
        if db is None:
            session.close()
