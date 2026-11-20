from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..services.db import get_db
from ..models.sqlalchemy_models import Investigation, InvestigationNote, OCRDocument, Claim, User, RoleEnum
from ..dependencies import get_current_active_user, require_roles, log_audit_trail

router = APIRouter(prefix="/investigations", tags=["Investigation Case Management"])

class InvestigationCreate(BaseModel):
    claim_id: str = Field(..., description="Target claim reference ID or DB ID")
    notes: Optional[str] = Field(None, description="Initial investigation notes or hypothesis")
    assigned_to_username: Optional[str] = Field(None, description="Assigned fraud investigator username")

class InvestigationUpdate(BaseModel):
    status: Optional[str] = Field(None, description="open, in_review, escalated, confirmed_fraud, cleared")
    notes: Optional[str] = Field(None, description="Updated findings, evidence log, or conclusions")
    reassign_to_username: Optional[str] = None
    evidence_documents: Optional[List[int]] = Field(None, description="OCRDocument IDs to attach as evidence")
    outcome: Optional[str] = Field(None, description="confirmed_fraud or cleared")

@router.get("/", summary="List all investigation cases")
async def list_investigations(
    status: Optional[str] = Query(None, description="Filter: open, in_review, escalated, confirmed_fraud, cleared"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = db.query(Investigation).order_by(desc(Investigation.opened_at))
    if status:
        query = query.filter(Investigation.status == status.lower())

    cases = query.offset(skip).limit(limit).all()
    results = []
    for inv in cases:
        claim = inv.claim
        assessment = claim.assessment if claim else None
        results.append({
            "id": inv.id,
            "claim_id": claim.claim_id if claim else None,
            "claim_type": claim.claim_type if claim else None,
            "claim_amount": claim.amount if claim else None,
            "policy_number": claim.policy.policy_number if claim and claim.policy else None,
            "customer_name": claim.customer.name if claim and claim.customer else None,
            "risk_score": assessment.risk_score if assessment else None,
            "risk_category": assessment.risk_category if assessment else None,
            "investigator": inv.investigator.full_name or inv.investigator.username if inv.investigator else "Unassigned",
            "status": inv.status,
            "notes": inv.notes,
            "opened_at": inv.opened_at.isoformat() if inv.opened_at else None,
            "closed_at": inv.closed_at.isoformat() if inv.closed_at else None,
        })
    return results

@router.post("/", summary="Open a new investigation case for a suspicious claim")
async def create_investigation(
    case_in: InvestigationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([RoleEnum.FRAUD_INVESTIGATOR, RoleEnum.CLAIMS_MANAGER, RoleEnum.SYSTEM_ADMIN])),
):
    claim = db.query(Claim).filter((Claim.claim_id == case_in.claim_id) | (Claim.id == case_in.claim_id)).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Target claim not found.")

    existing = db.query(Investigation).filter(Investigation.claim_id == claim.id).first()
    if existing:
        return {"message": "Investigation case already exists for this claim.", "investigation_id": existing.id}

    investigator = current_user
    if case_in.assigned_to_username:
        assigned = db.query(User).filter(User.username == case_in.assigned_to_username).first()
        if assigned:
            investigator = assigned

    new_inv = Investigation(
        claim_id=claim.id,
        investigator_id=investigator.id,
        status="open",
        notes=case_in.notes or "Manual investigation case opened.",
        opened_at=datetime.now(timezone.utc),
    )
    db.add(new_inv)
    claim.status = "under_investigation"
    db.commit()
    db.refresh(new_inv)

    log_audit_trail(db, current_user, action="INVESTIGATION_OPENED", target=f"Investigation:{new_inv.id}", detail={"claim_id": claim.claim_id})

    return {
        "message": "Investigation case successfully opened.",
        "investigation_id": new_inv.id,
        "claim_id": claim.claim_id,
        "status": new_inv.status,
    }

@router.put("/{investigation_id}", summary="Update investigation status, notes, or findings")
async def update_investigation(
    investigation_id: int,
    update_data: InvestigationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([RoleEnum.FRAUD_INVESTIGATOR, RoleEnum.CLAIMS_MANAGER, RoleEnum.COMPLIANCE_OFFICER, RoleEnum.SYSTEM_ADMIN])),
):
    inv = db.query(Investigation).filter(Investigation.id == investigation_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation case not found.")

    if update_data.status:
        inv.status = update_data.status.lower()
        if inv.status in ["confirmed_fraud", "cleared"]:
            inv.closed_at = datetime.now(timezone.utc)
            if inv.claim:
                inv.claim.status = "rejected" if inv.status == "confirmed_fraud" else "cleared"

    if update_data.notes:
        inv.notes = f"{inv.notes or ''}\n[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}] {update_data.notes}"

    if update_data.reassign_to_username:
        reassign_user = db.query(User).filter(User.username == update_data.reassign_to_username).first()
        if reassign_user:
            inv.investigator_id = reassign_user.id

    if update_data.evidence_documents is not None:
        # Attach/detach OCR evidence documents (verify they exist and are linked to the claim)
        docs = db.query(OCRDocument).filter(OCRDocument.id.in_(update_data.evidence_documents)).all()
        inv.evidence_documents = [d.id for d in docs]

    if update_data.outcome:
        if update_data.outcome.lower() not in ("confirmed_fraud", "cleared"):
            raise HTTPException(status_code=400, detail="Outcome must be one of: confirmed_fraud, cleared")
        inv.outcome = update_data.outcome.lower()
        inv.status = inv.outcome
        inv.closed_at = datetime.now(timezone.utc)
        if inv.claim:
            inv.claim.status = "rejected" if inv.outcome == "confirmed_fraud" else "cleared"

    db.commit()
    db.refresh(inv)

    log_audit_trail(
        db, current_user, action="INVESTIGATION_UPDATED", target=f"Investigation:{inv.id}",
        detail={"status": inv.status, "claim_id": inv.claim.claim_id if inv.claim else None}
    )

    # Investigation outcome details (linked to Claim)
    ocr_evidence = []
    if inv.evidence_documents:
        ocr_evidence = [
            {
                "document_id": d.id,
                "filename": d.filename,
                "document_type": d.document_type,
                "processing_status": d.processing_status,
                "confidence_score": d.confidence_score,
                "flags": d.flags or [],
                "has_date_mismatch": d.has_date_mismatch,
                "extracted_fields": d.extracted_fields,
            }
            for d in db.query(OCRDocument).filter(OCRDocument.id.in_(inv.evidence_documents)).all()
        ]
    related_claims = []
    if inv.claim:
        related_claims = [
            {
                "claim_id": inv.claim.claim_id,
                "claim_type": inv.claim.claim_type,
                "amount": inv.claim.amount,
                "status": inv.claim.status,
            }
        ]

    return {
        "message": f"Investigation #{inv.id} updated successfully.",
        "status": inv.status,
        "outcome": inv.outcome,
        "notes": inv.notes,
        "closed_at": inv.closed_at.isoformat() if inv.closed_at else None,
        "ocr_evidence": ocr_evidence,
        "related_claims": related_claims,
    }


@router.get("/{investigation_id}", summary="Get investigation case detail")
async def get_investigation(
    investigation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    inv = db.query(Investigation).filter(Investigation.id == investigation_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation case not found.")

    notes = (
        db.query(InvestigationNote)
        .filter(InvestigationNote.investigation_id == inv.id)
        .order_by(desc(InvestigationNote.created_at))
        .limit(50)
        .all()
    )
    note_list = [
        {
            "id": n.id,
            "note": n.note,
            "created_by": n.user.full_name or n.user.username if n.user else "Unknown",
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in reversed(notes)
    ]
    return {
        "id": inv.id,
        "claim_id": inv.claim.claim_id if inv.claim else None,
        "investigator": inv.investigator.full_name or inv.investigator.username if inv.investigator else "Unassigned",
        "status": inv.status,
        "outcome": inv.outcome,
        "notes": inv.notes,
        "opened_at": inv.opened_at.isoformat() if inv.opened_at else None,
        "closed_at": inv.closed_at.isoformat() if inv.closed_at else None,
        "evidence_documents": inv.evidence_documents or [],
        "timeline": note_list,
    }


@router.post("/{investigation_id}/notes", summary="Add a timestamped note to an investigation")
async def add_investigation_note(
    investigation_id: int,
    data: dict = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([RoleEnum.FRAUD_INVESTIGATOR, RoleEnum.COMPLIANCE_OFFICER, RoleEnum.SYSTEM_ADMIN])),
):
    inv = db.query(Investigation).filter(Investigation.id == investigation_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation case not found.")
    note_text = ((data or {}).get("note") or "").strip()
    if not note_text:
        raise HTTPException(status_code=400, detail="Note text is required.")
    new_note = InvestigationNote(
        investigation_id=inv.id,
        user_id=current_user.id,
        note=note_text,
        created_at=datetime.now(timezone.utc),
    )
    db.add(new_note)
    db.commit()
    db.refresh(new_note)
    log_audit_trail(db, current_user, action="INVESTIGATION_NOTE_ADDED", target=f"Investigation:{inv.id}", detail={"note_id": new_note.id})
    return {
        "message": "Investigation note recorded.",
        "id": new_note.id,
        "note": new_note.note,
        "created_by": current_user.full_name or current_user.username,
        "created_at": new_note.created_at.isoformat() if new_note.created_at else None,
    }
