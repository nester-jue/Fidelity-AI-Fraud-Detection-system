"""Claim Timeline Intelligence API (Phase 6).

Reconstructs the chronological history of a claim from real database
records and returns anomalies/missing steps for human review.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..dependencies import get_current_active_user
from ..services import claim_timeline
from ..services.db import get_db

router = APIRouter(prefix="/timeline", tags=["Claim Timeline Intelligence"])


@router.get("/{claim_id}", summary="Reconstructed claim timeline with anomalies and missing steps")
async def get_claim_timeline(
    claim_id: str,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    from ..models.sqlalchemy_models import Claim
    claim = db.query(Claim).filter(Claim.claim_id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found.")
    data = claim_timeline.build_claim_timeline(db, claim.id)
    data["claim_id_ref"] = claim.claim_id
    data["notes"] = claim_timeline.get_claim_notes_summary(db, claim.id)
    return data


@router.get("/all", summary="Timelines for multiple claims")
async def get_all_timelines(
    claim_ids: str = Query("", description="Comma-separated claim IDs"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_active_user),
) -> Dict[str, Any]:
    from ..models.sqlalchemy_models import Claim
    wanted = [c.strip() for c in claim_ids.split(",") if c.strip()]
    timelines = []
    for ref in wanted[:limit]:
        claim = db.query(Claim).filter(Claim.claim_id == ref).first()
        if claim:
            timelines.append(claim_timeline.build_claim_timeline(db, claim.id))
    return {"count": len(timelines), "timelines": timelines}
