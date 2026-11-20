from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..services.db import get_db
from ..models.sqlalchemy_models import FraudAssessment, Claim, User, RoleEnum
from ..dependencies import get_current_active_user, require_roles

router = APIRouter(prefix="/fraud", tags=["Fraud Risk Intelligence"])

@router.get("/assessments", summary="List all fraud risk assessments")
async def list_fraud_assessments(
    risk_category: Optional[str] = Query(None, description="Low, Medium, High, Critical"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = db.query(FraudAssessment).order_by(desc(FraudAssessment.assessed_at))
    if risk_category:
        query = query.filter(FraudAssessment.risk_category == risk_category.capitalize())
    
    records = query.offset(skip).limit(limit).all()
    results = []
    for a in records:
        claim = a.claim
        results.append({
            "id": a.id,
            "claim_id": claim.claim_id if claim else None,
            "claim_type": claim.claim_type if claim else None,
            "amount": claim.amount if claim else None,
            "policy_number": claim.policy.policy_number if claim and claim.policy else None,
            "customer_name": claim.customer.name if claim and claim.customer else None,
            "risk_score": a.risk_score,
            "risk_category": a.risk_category,
            "indicators": a.indicators,
            "explanation": a.explanation,
            "model_version": a.model_version,
            "assessed_at": a.assessed_at.isoformat() if a.assessed_at else None,
        })
    return results

@router.get("/assessments/{claim_id}", summary="Get fraud risk assessment for a specific claim")
async def get_claim_fraud_assessment(
    claim_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    claim = db.query(Claim).filter((Claim.claim_id == claim_id) | (Claim.id == claim_id)).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found.")
    
    assessment = claim.assessment
    if not assessment:
        raise HTTPException(status_code=404, detail="No fraud assessment has been calculated for this claim yet.")

    return {
        "claim_id": claim.claim_id,
        "policy_number": claim.policy.policy_number if claim.policy else None,
        "customer_name": claim.customer.name if claim.customer else None,
        "amount": claim.amount,
        "risk_score": assessment.risk_score,
        "risk_category": assessment.risk_category,
        "indicators": assessment.indicators,
        "explanation": assessment.explanation,
        "model_version": assessment.model_version,
        "assessed_at": assessment.assessed_at.isoformat() if assessment.assessed_at else None,
    }

@router.get("/high-risk", summary="Get priority queue of High and Critical risk claims")
async def get_high_risk_claims(
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    assessments = (
        db.query(FraudAssessment)
        .filter(FraudAssessment.risk_category.in_(["High", "Critical"]))
        .order_by(desc(FraudAssessment.risk_score))
        .limit(limit)
        .all()
    )

    results = []
    for a in assessments:
        claim = a.claim
        results.append({
            "claim_id": claim.claim_id if claim else None,
            "policy_number": claim.policy.policy_number if claim and claim.policy else None,
            "customer_name": claim.customer.name if claim and claim.customer else None,
            "claim_type": claim.claim_type if claim else None,
            "amount": claim.amount if claim else None,
            "status": claim.status if claim else None,
            "risk_score": a.risk_score,
            "risk_category": a.risk_category,
            "indicators": a.indicators,
            "explanation": a.explanation,
            "assessed_at": a.assessed_at.isoformat() if a.assessed_at else None,
        })
    return results
