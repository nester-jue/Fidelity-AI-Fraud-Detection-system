"""Digital Evidence Management (Phase 9).

Structured evidence tracking for investigations:

- SHA-256 hashing of artifacts at registration time (integrity fingerprint).
- Integrity re-verification against the stored hash.
- Evidence registers linked to claims and/or investigations.
- Append-only investigation actions are written to the AuditLog trail.

Integrity guarantees: original artifacts are preserved (file_path kept).
Evidence records are exposed through the Evidence API with permissions.
"""

import hashlib
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..models.sqlalchemy_models import AuditLog, EvidenceRecord, Investigation, User
from ..dependencies import log_audit_trail

EVIDENCE_TYPES = ["DOCUMENT", "PHOTOGRAPH", "DIGITAL_ARTIFACT", "NOTE", "AUDIO", "OTHER"]
STATUS_OPTIONS = ["collected", "pending_review", "under_review", "verified", "rejected"]


def compute_sha256(file_path: Optional[str]) -> Optional[str]:
    """Computes the SHA-256 hex digest of a file; returns None if unreadable."""
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


def verify_evidence_integrity(db: Session, evidence: EvidenceRecord) -> Dict[str, Any]:
    """Re-computes the artifact hash and compares with the recorded SHA-256."""
    expected = evidence.sha256_hash
    actual = compute_sha256(evidence.file_path) if evidence.file_path else None
    ok = bool(expected and actual and expected == actual)
    return {
        "evidence_id": evidence.id,
        "integrity_ok": ok,
        "expected_sha256": expected,
        "actual_sha256": actual,
        "file_path_exists": bool(evidence.file_path and os.path.isfile(evidence.file_path)),
    }


def register_evidence(
    db: Session,
    *,
    collected_by_id: int,
    title: str,
    evidence_type: str,
    claim_id: Optional[int] = None,
    investigation_id: Optional[int] = None,
    document_id: Optional[int] = None,
    file_path: Optional[str] = None,
    notes: Optional[str] = None,
    status: str = "collected",
    linked_claim_id_snapshot: Optional[str] = None,
) -> EvidenceRecord:
    """Creates an EvidenceRecord with a fresh SHA-256 fingerprint and audit trail entry."""
    evidence_type = (evidence_type or "OTHER").upper()
    if evidence_type not in EVIDENCE_TYPES:
        evidence_type = "OTHER"
    record = EvidenceRecord(
        investigation_id=investigation_id,
        claim_id=claim_id,
        document_id=document_id,
        evidence_type=evidence_type,
        title=title,
        file_path=file_path,
        sha256_hash=compute_sha256(file_path) if file_path else None,
        status=status,
        collected_by_id=collected_by_id,
        notes=notes,
        linked_claim_id_snapshot=linked_claim_id_snapshot,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # Append-only audit entry: "EVIDENCE_REGISTERED"
    db.add(AuditLog(
        user_id=collected_by_id,
        action="EVIDENCE_REGISTERED",
        target=f"Evidence:{record.id}",
        detail={
            "investigation_id": investigation_id,
            "claim_id": claim_id,
            "evidence_type": evidence_type,
            "title": title,
            "file_path": file_path,
            "sha256": record.sha256_hash,
        },
        timestamp=datetime.now(timezone.utc),
    ))
    db.commit()
    return record


def update_evidence_status(db: Session, evidence_id: int, new_status: str,
                           user_id: int, notes: Optional[str] = None) -> Optional[EvidenceRecord]:
    """Moves evidence between review statuses (audited)."""
    if new_status not in STATUS_OPTIONS:
        return None
    evidence = db.query(EvidenceRecord).filter(EvidenceRecord.id == evidence_id).first()
    if not evidence:
        return None
    old_status = evidence.status
    evidence.status = new_status
    if new_status == "verified" and not evidence.integrity_verified:
        ver = verify_evidence_integrity(db, evidence)
        evidence.integrity_verified = bool(ver["integrity_ok"])
        evidence.integrity_verified_at = datetime.now(timezone.utc)
    db.commit()
    db.add(AuditLog(
        user_id=user_id,
        action="EVIDENCE_STATUS_UPDATED",
        target=f"Evidence:{evidence_id}",
        detail={"old_status": old_status, "new_status": new_status, "notes": notes},
        timestamp=datetime.now(timezone.utc),
    ))
    db.commit()
    return evidence


def verify_all_integrity(db: Session, investigation_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Verifies integrity of every evidence record (optionally scoped to an investigation)."""
    q = db.query(EvidenceRecord).filter(EvidenceRecord.sha256_hash.isnot(None))
    if investigation_id is not None:
        q = q.filter(EvidenceRecord.investigation_id == investigation_id)
    results = []
    for e in q.all():
        ver = verify_evidence_integrity(db, e)
        if ver["integrity_ok"]:
            e.integrity_verified = True
            e.integrity_verified_at = datetime.now(timezone.utc)
        results.append(ver)
    db.commit()
    return results


def list_evidence(
    db: Session,
    claim_id: Optional[int] = None,
    investigation_id: Optional[int] = None,
    status: Optional[str] = None,
    evidence_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    q = db.query(EvidenceRecord)
    if claim_id is not None:
        q = q.filter(EvidenceRecord.claim_id == claim_id)
    if investigation_id is not None:
        q = q.filter(EvidenceRecord.investigation_id == investigation_id)
    if status:
        q = q.filter(EvidenceRecord.status == status)
    if evidence_type:
        q = q.filter(EvidenceRecord.evidence_type == evidence_type.upper())
    records = q.order_by(EvidenceRecord.collected_at.desc()).offset(skip).limit(limit).all()
    out = []
    for e in records:
        out.append({
            "id": e.id,
            "investigation_id": e.investigation_id,
            "claim_id": e.claim_id,
            "document_id": e.document_id,
            "evidence_type": e.evidence_type,
            "title": e.title,
            "file_path": e.file_path,
            "file_exists": bool(e.file_path and os.path.isfile(e.file_path)),
            "sha256_hash": e.sha256_hash,
            "status": e.status,
            "integrity_verified": e.integrity_verified,
            "integrity_verified_at": e.integrity_verified_at.isoformat() if e.integrity_verified_at else None,
            "collected_at": e.collected_at.isoformat() if e.collected_at else None,
            "collected_by": e.collected_by.full_name if e.collected_by else "Unknown",
            "notes": e.notes,
            "linked_claim_id_snapshot": e.linked_claim_id_snapshot,
        })
    return out


def get_investigation_evidence_report(db: Session, investigation_id: int) -> Dict[str, Any]:
    """Compact evidence report + status summary for an investigation."""
    evidence = list_evidence(db, investigation_id=investigation_id, limit=100)
    audit_events = (
        db.query(AuditLog)
        .filter(AuditLog.target.like(f"Evidence:%"), AuditLog.action.in_(["EVIDENCE_REGISTERED", "EVIDENCE_STATUS_UPDATED"]))
        .order_by(desc(AuditLog.timestamp)).limit(50).all()
    )
    return {
        "investigation_id": investigation_id,
        "total_evidence": len(evidence),
        "statuses": {s: sum(1 for e in evidence if e["status"] == s) for s in STATUS_OPTIONS},
        "integrity_verified_count": sum(1 for e in evidence if e["integrity_verified"]),
        "evidence_items": evidence,
        "recent_actions": [
            {
                "action": a.action,
                "target": a.target,
                "by": (a.user.full_name if a.user else "Unknown"),
                "at": a.timestamp.isoformat() if a.timestamp else None,
                "detail": a.detail,
            }
            for a in audit_events
        ],
    }


def log_evidence_action(db: Session, user: User, action: str, target: str, detail: Optional[Dict[str, Any]] = None):
    """Appends an append-only action entry for sensitive evidence changes."""
    db.add(AuditLog(user_id=user.id, action=action, target=target,
                    detail=detail or {}, timestamp=datetime.now(timezone.utc)))
    db.commit()
