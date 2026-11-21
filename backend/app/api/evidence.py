"""Digital Evidence API (Phase 9).

Registers, lists, verifies and reports evidence records. All records get
SHA-256 fingerprints; integrity is re-verifiable on demand.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..dependencies import get_current_active_user
from ..services import evidence as evidence_service
from ..services.db import get_db

router = APIRouter(prefix="/evidence", tags=["Digital Evidence & Audit Trail"])


class EvidenceRegisterRequest(BaseModel):
    title: str
    evidence_type: Optional[str] = "DOCUMENT"
    claim_id: Optional[int] = None
    investigation_id: Optional[int] = None
    document_id: Optional[int] = None
    file_path: Optional[str] = None
    notes: Optional[str] = None
    linked_claim_id_snapshot: Optional[str] = None
    status: str = "collected"


class EvidenceStatusUpdateRequest(BaseModel):
    status: str
    notes: Optional[str] = None


@router.post("/", summary="Register digital evidence (SHA-256 fingerprint + audit entry)")
async def register_evidence(
    request: EvidenceRegisterRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    if not request.title:
        raise HTTPException(status_code=400, detail="title is required.")
    rec = evidence_service.register_evidence(
        db,
        collected_by_id=current_user.id,
        title=request.title,
        evidence_type=request.evidence_type,
        claim_id=request.claim_id,
        investigation_id=request.investigation_id,
        document_id=request.document_id,
        file_path=request.file_path,
        notes=request.notes,
        status=request.status,
        linked_claim_id_snapshot=request.linked_claim_id_snapshot,
    )
    return {
        "message": f"Evidence '{rec.title}' registered.",
        "evidence": {
            "id": rec.id,
            "title": rec.title,
            "evidence_type": rec.evidence_type,
            "claim_id": rec.claim_id,
            "investigation_id": rec.investigation_id,
            "document_id": rec.document_id,
            "file_path": rec.file_path,
            "sha256_hash": rec.sha256_hash,
            "status": rec.status,
            "integrity_verified": rec.integrity_verified,
            "collected_at": rec.collected_at.isoformat() if rec.collected_at else None,
        },
    }


@router.get("/", summary="List evidence records (filters by claim, investigation, status, type)")
async def list_evidence(
    claim_id: Optional[int] = Query(None),
    investigation_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    evidence_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    return evidence_service.list_evidence(
        db, claim_id=claim_id, investigation_id=investigation_id,
        status=status, evidence_type=evidence_type, skip=skip, limit=limit,
    )


@router.get("/types", summary="Supported evidence types and statuses")
async def evidence_types():
    return {
        "evidence_types": evidence_service.EVIDENCE_TYPES,
        "statuses": evidence_service.STATUS_OPTIONS,
    }


@router.get("/{evidence_id}", summary="Get evidence record detail")
async def get_evidence_detail(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    from ..models.sqlalchemy_models import EvidenceRecord
    e = db.query(EvidenceRecord).filter(EvidenceRecord.id == evidence_id).first()
    if not e:
        raise HTTPException(status_code=404, detail=f"Evidence {evidence_id} not found.")
    return {
        "id": e.id,
        "investigation_id": e.investigation_id,
        "claim_id": e.claim_id,
        "document_id": e.document_id,
        "evidence_type": e.evidence_type,
        "title": e.title,
        "file_path": e.file_path,
        "sha256_hash": e.sha256_hash,
        "status": e.status,
        "integrity_verified": e.integrity_verified,
        "integrity_verified_at": e.integrity_verified_at.isoformat() if e.integrity_verified_at else None,
        "collected_at": e.collected_at.isoformat() if e.collected_at else None,
        "collected_by": e.collected_by.full_name if e.collected_by else "Unknown",
        "notes": e.notes,
        "linked_claim_id_snapshot": e.linked_claim_id_snapshot,
        "integrity": evidence_service.verify_evidence_integrity(db, e),
    }


@router.put("/{evidence_id}/status", summary="Update evidence status (audited)")
async def update_evidence_status(
    evidence_id: int,
    request: EvidenceStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    e = evidence_service.update_evidence_status(db, evidence_id, request.status,
                                                current_user.id, request.notes)
    if not e:
        raise HTTPException(status_code=404, detail="Evidence not found or invalid status.")
    return {
        "message": f"Evidence {evidence_id} status updated to '{e.status}'.",
        "evidence": {
            "id": e.id, "status": e.status,
            "integrity_verified": e.integrity_verified,
        },
    }


@router.get("/{evidence_id}/verify", summary="Re-verify artifact integrity against stored SHA-256")
async def verify_evidence(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    from ..models.sqlalchemy_models import EvidenceRecord
    e = db.query(EvidenceRecord).filter(EvidenceRecord.id == evidence_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Evidence not found.")
    if e.integrity_verified is False or not e.integrity_verified:
        e.integrity_verified = evidence_service.verify_evidence_integrity(db, e)["integrity_ok"]
        from datetime import datetime, timezone
        e.integrity_verified_at = datetime.now(timezone.utc)
        db.commit()
    return {
        "evidence_id": e.id,
        "integrity": evidence_service.verify_evidence_integrity(db, e),
    }


@router.get("/integrity/all", summary="Verify integrity of all evidence records")
async def verify_all(
    investigation_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    results = evidence_service.verify_all_integrity(db, investigation_id)
    return {
        "checked": len(results),
        "all_verified": all(r["integrity_ok"] for r in results),
        "failures": [r for r in results if not r["integrity_ok"]],
    }


@router.get("/report/{investigation_id}", summary="Evidence report for an investigation (audit trail)")
async def get_evidence_report(
    investigation_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    return evidence_service.get_investigation_evidence_report(db, investigation_id)
