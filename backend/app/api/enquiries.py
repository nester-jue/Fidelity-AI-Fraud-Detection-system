"""Public product enquiry capture.

Recorded as a genuine database record with a reference. No email is claimed
to have been dispatched, and no licence or payment is created.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..services.db import get_db
from ..models.sqlalchemy_models import Enquiry

router = APIRouter(prefix="/enquiries", tags=["Public Enquiries"])


class EnquiryRequest(BaseModel):
    organisation: str = Field(..., min_length=2, max_length=200)
    email: str = Field(..., min_length=5, max_length=200)
    interests: str = Field("", max_length=4000)


@router.post("/", summary="Record a product demonstration enquiry")
async def create_enquiry(payload: EnquiryRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="A valid work email address is required.")
    reference = f"ENQ-{datetime.now(timezone.utc).year}-{uuid.uuid4().hex[:8].upper()}"
    enquiry = Enquiry(
        reference=reference,
        organisation=payload.organisation.strip(),
        email=email,
        interests=payload.interests.strip(),
        status="received",
    )
    db.add(enquiry)
    db.commit()
    db.refresh(enquiry)
    return {
        "reference": reference,
        "status": enquiry.status,
        "message": "Enquiry recorded. A product specialist will respond through the agreed contact channel.",
    }
