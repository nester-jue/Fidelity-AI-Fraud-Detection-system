"""Historical Claim Behaviour Analysis API (Phase 5).

Returns customer history analysis, current-claim vs history comparisons and
real record evidence for investigators.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..dependencies import get_current_active_user
from ..services import historical_behavior
from ..services.db import get_db

router = APIRouter(prefix="/historical", tags=["Historical Claim Behaviour Intelligence"])


@router.get("/claim/{claim_id}", summary="Full comparison of a claim against policyholder history and similar claims")
async def analyze_claim_vs_history(
    claim_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    from ..models.sqlalchemy_models import Claim
    claim = db.query(Claim).filter(Claim.claim_id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found.")
    return historical_behavior.analyze_claim_vs_history(db, claim.id)


@router.get("/customer/{customer_id}", summary="Customer claim-history analysis (anomalies, stats)")
async def analyze_customer_history(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    return historical_behavior.analyze_customer_history(db, customer_id)


@router.get("/customer/{customer_id}/stats", summary="Compact claim stats for a customer")
async def customer_claim_stats(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    return {
        "customer_id": customer_id,
        "stats": historical_behavior.compute_customer_claim_stats(db, customer_id),
    }


@router.get("/claim/{claim_id}/similar", summary="Similar historical claims for a claim")
async def get_similar_claims(
    claim_id: str,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    from ..models.sqlalchemy_models import Claim
    claim = db.query(Claim).filter(Claim.claim_id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found.")
    return {
        "claim_id": claim.claim_id,
        "similar_claims": historical_behavior.find_similar_historical_claims(db, claim, limit=limit),
    }
