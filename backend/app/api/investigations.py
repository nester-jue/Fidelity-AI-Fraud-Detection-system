from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..services.db import get_db
from ..models.sqlalchemy_models import Investigation, Claim, User, RoleEnum
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

    db.commit()
    db.refresh(inv)

    log_audit_trail(
        db, current_user, action="INVESTIGATION_UPDATED", target=f"Investigation:{inv.id}",
        detail={"status": inv.status, "claim_id": inv.claim.claim_id if inv.claim else None}
    )

    return {
        "message": f"Investigation #{inv.id} updated successfully.",
        "status": inv.status,
        "notes": inv.notes,
        "closed_at": inv.closed_at.isoformat() if inv.closed_at else None,
    }
