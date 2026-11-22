"""NEXA Forensic Analysis — Document-Level Checks (Phase 8).

Operates on ``OCRDocument`` records (system claim documents and ingested
sample claim forms):

- ``find_duplicate_document_groups`` — documents sharing SHA-256 fingerprints.
- ``analyze_claim_documents`` — per-claim cross-document consistency:
  conflicting claimant names, policy numbers and dates; missing fields
  aggregated across a claim's documents.
- ``find_suspicious_flags`` — heuristic flags for human review.
- ``generate_forensic_analysis`` — full analysis dict for dashboards.

Important honesty note: inconsistencies, duplicates and suspicious flags are
findings for human review — they are NOT proof of fraud.
"""

import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.sqlalchemy_models import OCRDocument

try:
    from PIL import Image
except ImportError:  # Pillow optional; forensics degrade gracefully
    Image = None


def find_duplicate_document_groups(db: Session) -> List[Dict[str, Any]]:
    """Groups of system documents sharing SHA-256 fingerprints (sample docs excluded)."""
    docs = (
        db.query(OCRDocument)
        .filter(or_(OCRDocument.is_sample_document.is_(None), OCRDocument.is_sample_document == False))  # noqa: E712
        .all()
    )
    by_hash: Dict[str, List[OCRDocument]] = defaultdict(list)
    for d in docs:
        if d.document_hash_sha256:
            by_hash[d.document_hash_sha256].append(d)
    return [
        {
            "hash": g[0].document_hash_sha256,
            "documents": [
                {
                    "id": d.id,
                    "filename": d.filename,
                    "claim_id": d.claim.claim_id if d.claim else None,
                    "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
                }
                for d in g
            ],
        }
        for g in by_hash.values()
        if len(g) > 1
    ]


def analyze_claim_documents(
    db: Session,
    claim_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Cross-document consistency issues for claims (all claims, or one)."""
    issues: List[Dict[str, Any]] = []
    q = db.query(OCRDocument).filter(OCRDocument.claim_id.isnot(None))
    if claim_id is not None:
        q = q.filter(OCRDocument.claim_id == claim_id)
    docs = q.all()

    by_claim: Dict[int, List[OCRDocument]] = defaultdict(list)
    for d in docs:
        by_claim[d.claim_id].append(d)

    for cid, claim_docs in sorted(by_claim.items()):
        # Conflicting claimant names (different names on different documents).
        claimants = {d.extracted_fields.get("claimant_name") for d in claim_docs
                     if d.extracted_fields and d.extracted_fields.get("claimant_name")}
        if len(claimants) > 1:
            issues.append({
                "claim_id": cid,
                "type": "conflicting_claimant_names",
                "details": f"Documents on this claim show different claimant names: {sorted(claimants)}",
                "severity": "potential_inconsistency",
            })
        # Conflicting policy numbers.
        policies = {d.extracted_fields.get("policy_number") for d in claim_docs
                    if d.extracted_fields and d.extracted_fields.get("policy_number")}
        if len(policies) > 1:
            issues.append({
                "claim_id": cid,
                "type": "conflicting_policy_numbers",
                "details": f"Documents show different policy numbers: {sorted(str(p) for p in policies)}",
                "severity": "potential_inconsistency",
            })
        # Conflicting dates (use each doc's primary extracted date).
        doc_dates = {(d.extracted_dates or [None])[0] for d in claim_docs if d.extracted_dates}
        if len(doc_dates) > 1:
            issues.append({
                "claim_id": cid,
                "type": "conflicting_dates",
                "details": f"Documents show different date sets: {sorted(str(x) for x in doc_dates)}",
                "severity": "potential_inconsistency",
            })
        # Missing fields aggregated across a claim's documents.
        missing: Dict[str, int] = {}
        for d in claim_docs:
            for field in d.missing_fields or []:
                missing[field] = missing.get(field, 0) + 1
        if missing:
            issues.append({
                "claim_id": cid,
                "type": "missing_fields_across_docs",
                "details": "; ".join(f"{k} ({v} doc(s))" for k, v in sorted(missing.items())),
                "severity": "information_gap",
            })
    return issues


def find_suspicious_flags(db: Session) -> List[Dict[str, Any]]:
    """Heuristic flags on documents for human review."""
    flags: List[Dict[str, Any]] = []
    for d in db.query(OCRDocument).all():
        if (d.processing_status == "failed" and (d.raw_text or "").strip()) or \
           (d.flags and not d.is_manually_verified):
            flags.append({
                "document_id": d.id,
                "filename": d.filename,
                "type": "flagged_for_review",
                "details": list(d.flags or []),
                "severity": "needs_review",
            })
        if d.has_date_mismatch:
            flags.append({
                "document_id": d.id,
                "filename": d.filename,
                "type": "date_mismatch",
                "severity": "potential_inconsistency",
            })
    return flags


def generate_forensic_analysis(db: Session) -> Dict[str, Any]:
    """Full forensic analysis of documents: duplicates, cross-doc issues, suspicious flags."""
    duplicates = find_duplicate_document_groups(db)
    consistency = analyze_claim_documents(db)
    suspicious = find_suspicious_flags(db)
    return {
        "duplicate_groups": duplicates,
        "claim_consistency_issues": consistency,
        "suspicious_flags": suspicious,
        "image_forensics": [analyze_image_forensics(d.file_path) for d in db.query(OCRDocument).all()
                            if d.file_path and d.mime_type.startswith("image/")][:50],
        "pdf_signature_checks": [analyze_pdf_signature(d.file_path) for d in db.query(OCRDocument).all()
                                 if d.file_path and d.mime_type == "application/pdf"][:50],
        "reused_document_groups": detect_reused_documents(db),
        "summary": {
            "duplicate_groups": len(duplicates),
            "claim_consistency_issues": len(consistency),
            "suspicious_flags": len(suspicious),
            "reused_document_groups": None,  # filled below
        },
    }


# ---------------------------------------------------------------------------
# Image forensics (Phase 4)
# ---------------------------------------------------------------------------

def analyze_image_forensics(file_path: Optional[str]) -> Dict[str, Any]:
    """Technical image integrity forensics: format, dimensions, DPI, entropy,
    metadata presence. Reports technical anomalies; fraud linkage needs humans."""
    findings: Dict[str, Any] = {
        "file_path": file_path,
        "mime_type": None, "format": None, "width": None, "height": None,
        "dpi": None, "file_size_bytes": None, "has_exif": False,
        "entropy": None, "suspicious": False, "notes": [],
        "verified_with": "Pillow",
    }
    if not file_path or not os.path.isfile(file_path):
        findings["notes"].append("File missing or unreadable.")
        return findings
    try:
        with Image.open(file_path) as im:
            findings["format"] = im.format
            findings["width"], findings["height"] = im.size
            try:
                dpi = im.info.get("dpi")
                findings["dpi"] = [int(d) for d in dpi] if dpi and isinstance(dpi[0], float) else list(dpi) if dpi else None
            except Exception:
                findings["dpi"] = None
            exif = getattr(im, "getexif", None)
            if exif:
                try:
                    has_data = len(im.getexif()) > 0
                except Exception:
                    has_data = False
                findings["has_exif"] = bool(has_data)
            if im.format == "PNG":
                findings["notes"].append("PNG format supports metadata chunks (e.g., tEXt, eXIf); verify provenance.")
        findings["file_size_bytes"] = os.path.getsize(file_path)
        with open(file_path, "rb") as f:
            data = f.read()
        if data[:8] != b"\x89PNG\r\n\x1a\n" and data[:4] == b"%PDF":
            findings["format"] = "PDF"
        # Extremely suspicious: 0-byte file
        if findings["file_size_bytes"] == 0:
            findings["suspicious"] = True
            findings["notes"].append("Empty file: size 0 bytes.")
        # File size / dimension sanity ratio (declared compression)
        if findings["width"] and findings["file_size_bytes"]:
            ratio = findings["file_size_bytes"] / float(max(1, findings["width"] * findings["height"]))
            if ratio > 100 and findings["format"] in ("JPEG", "PNG"):
                findings["suspicious"] = True
                findings["notes"].append("Suspiciously high file-size-to-pixel ratio; image may be padded/watermarked (needs review, not proof of fraud).")
        # Entropy quick check (flat images often suspicious)
        if findings["format"] in ("JPEG", "PNG") and findings["file_size_bytes"] > 1000 and Image is not None:
            try:
                with Image.open(file_path) as im:
                    import math
                    small = im.convert("L").resize((32, 32))
                    hist = small.histogram()
                    n = sum(hist)
                    if n:
                        findings["entropy"] = round(
                            -sum((c / n) * math.log2(c / n) for c in hist if c), 4
                        )
            except Exception:
                pass
        if findings["has_exif"]:
            findings["notes"].append("EXIF metadata present — may contain camera/device provenance data.")
    except Exception as e:
        findings["notes"].append(f"Forensic read error: {e}")
    return findings


def analyze_pdf_signature(file_path: Optional[str]) -> Dict[str, Any]:
    """Detects PDF digital signatures and file format integrity markers.

    Technical check only: presence of a signature trailer; production use
    requires dedicated PDF signature validation (e.g., signature value
    verification via signing certificates).
    """
    result: Dict[str, Any] = {
        "file_path": file_path,
        "format": None, "is_pdf": False, "has_digital_signature_marker": False,
        "has_signed_data": False, "producer": None, "creator": None,
        "creation_date": None, "modification_date": None, "file_size_bytes": None,
        "trailer_ok": False, "notes": [],
    }
    if not file_path or not os.path.isfile(file_path):
        result["notes"].append("File missing or unreadable.")
        return result
    try:
        with open(file_path, "rb") as f:
            head = f.read(1024)
            f.seek(0)
            data = f.read()
        result["file_size_bytes"] = os.path.getsize(file_path)
        if data[:5] == b"%PDF-":
            result["is_pdf"] = True
            result["format"] = "PDF"
            result["trailer_ok"] = data.rstrip()[-1:] == b"%%EOF" or b"%%EOF" in data[-1024:]
            # Signature/trailer markers (raw bytes, case-insensitive)
            lower = data.lower()
            result["has_digital_signature_marker"] = b"/adobesignature" in lower or b"/adobesignatureev" in lower or b"/siginannot" in lower
            result["has_signed_data"] = b"bytestring" in lower and b"signeddata" in lower
            # Metadata strings (may leak producer info)
            if b"/Producer" in data:
                i = data.find(b"/Producer")
                snippet = data[i:i + 200].decode("latin-1", "ignore")
                m = re.search(r"\((.*?)\)", snippet)
                if m:
                    result["producer"] = m.group(1)[:100]
            if b"/Creator" in data:
                i = data.find(b"/Creator")
                snippet = data[i:i + 200].decode("latin-1", "ignore")
                m = re.search(r"\((.*?)\)", snippet)
                if m:
                    result["creator"] = m.group(1)[:100]
            if b"/CreationDate" in data:
                i = data.find(b"/CreationDate")
                snippet = data[i:i + 100].decode("latin-1", "ignore")
                m = re.search(r"\((.*?)\)", snippet)
                if m:
                    result["creation_date"] = m.group(1)
            if b"/ModDate" in data:
                i = data.find(b"/ModDate")
                snippet = data[i:i + 100].decode("latin-1", "ignore")
                m = re.search(r"\((.*?)\)", snippet)
                if m:
                    result["modification_date"] = m.group(1)
            if not result["trailer_ok"]:
                result["notes"].append("PDF trailer marker %%EOF missing or truncated.")
            if result["has_digital_signature_marker"]:
                result["notes"].append("Digital signature marker present in PDF — verify signature validity through certificate authority validation.")
            elif result["has_signed_data"]:
                result["notes"].append("SignedData structures present; requires dedicated signature-value validation.")
            else:
                result["notes"].append("No PDF digital-signature marker found in trailer; confirm signature position and integrity through signed evidence capture.")
    except Exception as e:
        result["notes"].append(f"Forensic read error: {e}")
    return result


# ---------------------------------------------------------------------------
# Document reuse detection (Phase 4)
# ---------------------------------------------------------------------------

def detect_reused_documents(db: Session, threshold: float = 0.9,
                            min_length: int = 80,
                            max_compare: int = 4000) -> List[Dict[str, Any]]:
    """Detects documents that are near-duplicates by text similarity even
    without identical hashes (e.g., reused medical certificates/receipts).

    Returns groups of documents sharing a similarity ratio above ``threshold``.
    """
    docs = [d for d in db.query(OCRDocument).all()
            if d.raw_text and len(d.raw_text.strip()) >= min_length]
    groups: List[Dict[str, Any]] = []
    # Optimizations over a naive O(n^2) full-text scan:
    #  - length gate: pairs whose max possible ratio
    #    (2*min(la,lb)/(la+lb)) cannot reach the threshold are skipped with an
    #    O(1) check instead of a text compare;
    #  - quick_ratio() prefilter: cheap O(n) upper bound, skips most pairs;
    #  - ratio() runs on the first `max_compare` chars: reuse typically comes
    #    from the same source document, so the prefix is where the match lives.
    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            a, b = docs[i], docs[j]
            if a.document_hash_sha256 and a.document_hash_sha256 == b.document_hash_sha256:
                continue  # handled by exact-hash duplicates
            if a.claim_id and b.claim_id and a.claim_id == b.claim_id:
                continue
            la, lb = len(a.raw_text or ""), len(b.raw_text or "")
            denom = la + lb
            if denom == 0 or 2 * min(la, lb) < threshold * denom:
                continue
            matcher = SequenceMatcher(None, (a.raw_text or "")[:max_compare],
                                      (b.raw_text or "")[:max_compare], autojunk=True)
            if matcher.quick_ratio() < threshold:
                continue
            ratio = matcher.ratio()
            if ratio >= threshold:
                groups.append({
                    "documents": [
                        {"id": a.id, "claim_id": a.claim_id, "filename": a.filename,
                         "hash": (a.document_hash_sha256 or "")[:16], "sha256": a.document_hash_sha256,
                         "document_type": a.document_type},
                        {"id": b.id, "claim_id": b.claim_id, "filename": b.filename,
                         "hash": (b.document_hash_sha256 or "")[:16], "sha256": b.document_hash_sha256,
                         "document_type": b.document_type},
                    ],
                    "similarity_score": round(ratio, 3),
                    "different_claims": bool(a.claim_id != b.claim_id and a.claim_id and b.claim_id),
                    "suspicious": True,
                    "evidence": f"Documents '{a.filename}' and '{b.filename}' share {ratio:.0%} text similarity.",
                })
    return groups


def compare_documents_fields(doc_a: OCRDocument, doc_b: OCRDocument) -> Dict[str, Any]:
    """Compares extracted structured fields between two documents of related claims."""
    def _unique(seq):
        seen, out = set(), []
        for x in seq or []:
            if x not in seen:
                seen.add(x); out.append(str(x))
        return out
    a = {"dates": _unique(doc_a.extracted_dates), "amounts": _unique(doc_a.extracted_amounts),
         "national_ids": _unique(doc_a.extracted_national_ids)}
    b = {"dates": _unique(doc_b.extracted_dates), "amounts": _unique(doc_b.extracted_amounts),
         "national_ids": _unique(doc_b.extracted_national_ids)}
    diffs = []
    for field in ("dates", "amounts", "national_ids"):
        if set(a[field]) != set(b[field]):
            diffs.append({
                "field": field,
                "doc_a_values": a[field],
                "doc_b_values": b[field],
                "difference_type": "content_differs",
                "confidence": 0.8,
                "notes": f"Documents show different {field.replace('_', ' ')}.",
            })
    return {"doc_a_id": doc_a.id, "doc_b_id": doc_b.id, "field_diffs": diffs,
            "comparison_explanation": "; ".join(d["notes"] for d in diffs) or "Documents agree on extracted fields."}


# ---------------------------------------------------------------------------
# Per-document forensic reports (Phase 4 format)
# ---------------------------------------------------------------------------

def generate_forensic_report_for_document(db: Session, doc_id: int) -> Dict[str, Any]:
    """Produces a forensic report per document: suspicious fields, extracted
    vs expected values, explanations, confidence, recommended actions."""
    doc = db.query(OCRDocument).filter(OCRDocument.id == doc_id).first()
    if not doc:
        return {"error": "document_not_found", "document_id": doc_id}

    page_numbers = []
    if doc.mime_type == "application/pdf":
        try:
            import re as _re
            with open(doc.file_path, "rb") as f:
                data = f.read()
            page_numbers = [i + 1 for i in range(len(_re.findall(b"/Type/Page[^s]", data)))] or [1]
        except Exception:
            page_numbers = [1]
    else:
        page_numbers = [1]

    image_forensic = analyze_image_forensics(doc.file_path) if doc.mime_type.startswith("image/") else None
    pdf_signature = analyze_pdf_signature(doc.file_path) if doc.mime_type == "application/pdf" else None

    # Build per-page forensic findings where possible.
    findings = []
    def _add(page: int, field: str, extracted, expected, explanation: str, confidence: float, action: str):
        findings.append({
            "page_number": page,
            "suspicious_field": field,
            "extracted_value": extracted,
            "expected_or_conflicting_value": expected,
            "explanation": explanation,
            "confidence_level": confidence,
            "recommended_investigation_action": action,
            "severity": "potential_fraud_indicator" if confidence >= 0.7 else "requires_review",
        })

    for d in [doc]:
        page = page_numbers[0] if page_numbers else 1
        # Hash reuse finding
        if doc.document_hash_sha256:
            dup_groups = find_duplicate_document_groups(db)
            for group in dup_groups:
                if group["hash"] == doc.document_hash_sha256 and any(x["id"] == doc.id for x in group["documents"]):
                    others = [x["filename"] for x in group["documents"] if x["id"] != doc.id]
                    _add(page, "document_hash", doc.document_hash_sha256[:16] + "…",
                         f"Identical SHA-256 fingerprint matches: {', '.join(others[:5])}",
                         "The document is byte-identical to another document in another claim. This is a technical anomaly; it may indicate document reuse or substitution, and cannot alone prove fraud.",
                         0.95, "Verify the second document against its claim; flag for forensic review.")
        # Missing fields finding
        for field in (doc.missing_fields or []):
            _add(page, field, None, "not_extracted",
                 "Mandatory field missing from extracted document content.",
                 0.6, "Request original document; verify extraction.")
        # Date mismatch finding
        if doc.has_date_mismatch and doc.extracted_dates and doc.claim:
            _add(page, "date", doc.extracted_dates[0], doc.claim.incident_date.date().isoformat() if doc.claim.incident_date else None,
                 "Extracted document date conflicts with the claim incident date. This may be an OCR error or a factual inconsistency.",
                 0.75, "Verify with claimant whether the date is correct; request official date certification.")
        # Extracted national ID finding (background check window)
        if doc.extracted_national_ids:
            nids = doc.extracted_national_ids
            _add(page, "national_id", nids,
                 doc.claim.customer.national_id if doc.claim and doc.claim.customer else None,
                 "National ID extracted from document. Verify against customer registry; format validation is best-effort (no external registry lookup).",
                 0.7, "Cross-check with KYC records; request photo ID if unverified.")
        # Image tampering
        if image_forensic and (image_forensic.get("suspicious") or image_forensic.get("has_exif")):
            _add(page, "image_metadata", image_forensic.get("format"),
                 image_forensic.get("dpi"),
                 " ".join(image_forensic.get("notes", [])),
                 "Technical anomaly detected during image forensics; not proof of manipulation.",
                 0.6 if image_forensic.get("suspicious") else 0.4,
                 "Compare with other submissions by the same claimant; request re-upload with higher-quality original.")
        if pdf_signature and not pdf_signature.get("has_digital_signature_marker") and pdf_signature.get("is_pdf"):
            _add(page, "signature", "none_found", pdf_signature.get("has_digital_signature_marker"),
                 "No PDF digital-signature marker detected in the trailer. Original documents are typically signed; a missing signature warrants review, though absence of a marker is not evidence of fraud.",
                 0.55, "Request the officially signed original document and its certificate of registration.")

    findings.sort(key=lambda f: -f["confidence_level"])
    if not findings:
        findings.append({
            "page_number": page_numbers[0] if page_numbers else 1,
            "suspicious_field": None,
            "extracted_value": None,
            "expected_or_conflicting_value": None,
            "explanation": "No forensic anomalies detected in this document.",
            "confidence_level": 1.0,
            "recommended_investigation_action": "No immediate action required; document verified structurally.",
            "severity": "clean",
        })

    return {
        "document_id": doc.id,
        "document_name": doc.filename,
        "document_type": doc.document_type,
        "claim_id": doc.claim_id,
        "mime_type": doc.mime_type,
        "pages": page_numbers,
        "page_count": len(page_numbers),
        "forensic_findings": findings,
        "image_forensics": image_forensic,
        "pdf_signature_check": pdf_signature,
        "integrity_sha256": doc.document_hash_sha256,
        "integrity_hash_verified": (
            doc.document_hash_sha256 == compute_sha256_of(doc.file_path)
            if doc.file_path else None
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "honesty_note": (
            "Forensic findings distinguish technical anomalies from potential fraud indicators. "
            "No finding establishes confirmed fraud; all high-confidence findings require human review."
        ),
    }


def compute_sha256_of(file_path: Optional[str]) -> Optional[str]:
    """Re-computes the SHA-256 of a file artifact (used for integrity re-verification)."""
    import hashlib
    if not file_path or not os.path.isfile(file_path):
        return None
    hasher = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return None


def generate_forensic_analysis(db: Session) -> Dict[str, Any]:
    """Full forensic analysis of documents: duplicates, cross-doc issues, suspicious flags."""
    duplicates = find_duplicate_document_groups(db)
    consistency = analyze_claim_documents(db)
    suspicious = find_suspicious_flags(db)
    reused = detect_reused_documents(db)
    return {
        "duplicate_groups": duplicates,
        "claim_consistency_issues": consistency,
        "suspicious_flags": suspicious,
        "reused_document_groups": reused,
        "image_forensics": [analyze_image_forensics(d.file_path) for d in db.query(OCRDocument).all()
                            if d.file_path and d.mime_type.startswith("image/")][:50],
        "pdf_signature_checks": [analyze_pdf_signature(d.file_path) for d in db.query(OCRDocument).all()
                                 if d.file_path and d.mime_type == "application/pdf"][:50],
        "summary": {
            "duplicate_groups": len(duplicates),
            "claim_consistency_issues": len(consistency),
            "suspicious_flags": len(suspicious),
            "reused_document_groups": len(reused),
        },
    }
