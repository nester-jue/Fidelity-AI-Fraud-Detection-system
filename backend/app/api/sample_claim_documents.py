"""NEXA OCR — Sample Claim Documents API (genuine public claim forms).

Read endpoints for the ingested genuine claim-form documents from
``data/sample_claim_documents`` (organized by category: life_insurance,
medical_insurance, funeral_claims, hospitalisation, accident_disability) —
with full OCR extractions, structured fields, missing fields, source
institution and source URL.

Backend role enforcement:
- Claims Officers, Claims Managers (Claims-dept view), Fraud Investigators,
  Compliance Officers, Management, System Admins: sample documents are a
  shared, public-registry — visible to all of them.

Document-level forensic analysis is in ``forensics`` (/forensics/document-analysis).
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..dependencies import get_current_active_user
from ..models.sqlalchemy_models import OCRDocument, User
from ..services.db import get_db
from .ocr import _serialize_document

router = APIRouter(prefix="/ocr/sample-documents", tags=["Sample Claim Documents (OCR)"])


@router.get("/", summary="List ingested genuine sample claim-form documents")
async def list_sample_documents(
    category: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[Dict[str, Any]]:
    query = (
        db.query(OCRDocument)
        .filter(OCRDocument.is_sample_document == True)  # noqa: E712
        .order_by(desc(OCRDocument.uploaded_at))
    )
    if category:
        query = query.filter(OCRDocument.sample_category == category)
    docs = query.offset(skip).limit(limit).all()
    return [_serialize_document(d) for d in docs]


@router.get("/{document_id}", summary="Get detailed extraction results for a sample claim document")
async def get_sample_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    doc = db.get(OCRDocument, document_id)
    if not doc or not doc.is_sample_document:
        raise HTTPException(status_code=404, detail="Sample claim document not found.")
    return _serialize_document(doc)
