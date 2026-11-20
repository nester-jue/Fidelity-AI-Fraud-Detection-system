"""
OCR Document Intelligence API
Handles document uploads, OCR processing, extraction results, and manual verification.
"""
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from ..services.db import get_db
from ..models.sqlalchemy_models import (
    OCRDocument, OCRCorrection, Claim, Investigation, User, RoleEnum, AuditLog
)
from ..dependencies import get_current_active_user, require_roles, log_audit_trail
from ..ocr.ocr_service import process_document
from ..core.config import settings

router = APIRouter(prefix="/ocr", tags=["OCR Document Intelligence"])

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/tiff",
    "image/webp",
    "text/plain",
}
MAX_FILE_SIZE_MB = settings.MAX_DOCUMENT_SIZE_MB


def _claims_visible_to_user(db: Session, user: User):
    """Returns claim IDs visible to the current user under departmental rules."""
    q = db.query(Claim.id)
    if user.role == RoleEnum.CLAIMS_OFFICER:
        q = q.filter(
            (Claim.assigned_officer_id == user.id) | (Claim.assigned_officer_id.is_(None))
        )
    elif user.role == RoleEnum.COMPLIANCE_OFFICER:
        flagged_ids = db.query(Claim.id).filter(Claim.status == "flagged").all()
        inv_claim_ids = db.query(Investigation.claim_id).all()
        q = q.filter(Claim.id.in_([c[0] for c in (flagged_ids + inv_claim_ids)]))
    elif user.role == RoleEnum.FRAUD_INVESTIGATOR:
        inv_claim_ids = db.query(Investigation.claim_id).all()
        q = q.filter(Claim.id.in_([c[0] for c in inv_claim_ids]))
    return [c[0] for c in q.all()]


class FieldCorrectionRequest(BaseModel):
    field_name: str
    corrected_value: str
    correction_note: Optional[str] = None


def _serialize_document(doc: OCRDocument) -> Dict[str, Any]:
    return {
        "id": doc.id,
        "claim_id": doc.claim.claim_id if doc.claim else None,
        "claim_db_id": doc.claim_id,
        "uploaded_by": doc.uploaded_by.full_name or doc.uploaded_by.username if doc.uploaded_by else "Unknown",
        "filename": doc.filename,
        "document_type": doc.document_type,
        "mime_type": doc.mime_type,
        "file_size_bytes": doc.file_size_bytes,
        "processing_status": doc.processing_status,
        "ocr_engine": doc.ocr_engine,
        "confidence_score": doc.confidence_score,
        "raw_text_snippet": (doc.raw_text or "")[:300] + ("..." if doc.raw_text and len(doc.raw_text) > 300 else ""),
        "extracted_fields": doc.extracted_fields,
        "extracted_dates": doc.extracted_dates,
        "extracted_amounts": doc.extracted_amounts,
        "extracted_national_ids": doc.extracted_national_ids,
        "has_date_mismatch": doc.has_date_mismatch,
        "missing_fields": doc.missing_fields or [],
        "flags": doc.flags or [],
        "is_manually_verified": doc.is_manually_verified,
        "verified_by": doc.verified_by.full_name or doc.verified_by.username if doc.verified_by else None,
        "verified_at": doc.verified_at.isoformat() if doc.verified_at else None,
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
        "corrections": [
            {
                "field": c.field_name,
                "original": c.original_value,
                "corrected": c.corrected_value,
                "note": c.correction_note,
                "corrected_by": c.corrected_by.full_name or c.corrected_by.username if c.corrected_by else None,
                "corrected_at": c.corrected_at.isoformat() if c.corrected_at else None,
            }
            for c in (doc.corrections or [])
        ],
    }


@router.get("/overview", summary="Get OCR processing statistics and overview")
async def get_ocr_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    total = db.query(OCRDocument).count()
    completed = db.query(OCRDocument).filter(OCRDocument.processing_status == "completed").count()
    pending = db.query(OCRDocument).filter(OCRDocument.processing_status == "pending").count()
    failed = db.query(OCRDocument).filter(OCRDocument.processing_status == "failed").count()
    manual_review = db.query(OCRDocument).filter(
        OCRDocument.processing_status == "completed",
        OCRDocument.is_manually_verified == False,
        OCRDocument.flags != None,
    ).count()

    # Average confidence score for completed docs
    avg_conf_result = db.query(func.avg(OCRDocument.confidence_score)).filter(
        OCRDocument.processing_status == "completed",
        OCRDocument.confidence_score > 0,
    ).scalar()
    avg_confidence = round(float(avg_conf_result or 0), 1)

    # By document type
    type_breakdown = db.query(
        OCRDocument.document_type, func.count(OCRDocument.id)
    ).group_by(OCRDocument.document_type).all()

    return {
        "total_documents": total,
        "documents_completed": completed,
        "documents_pending": pending,
        "documents_failed": failed,
        "documents_requiring_manual_review": manual_review,
        "average_extraction_confidence": avg_confidence,
        "document_type_breakdown": [
            {"type": t[0] or "Unknown", "count": t[1]} for t in type_breakdown
        ],
    }


@router.post("/upload", summary="Upload a document for OCR processing")
async def upload_document_for_ocr(
    file: UploadFile = File(..., description="Document file (PDF, PNG, JPG)"),
    claim_reference: Optional[str] = Form(None, description="Associated claim ID (optional)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles([
            RoleEnum.CLAIMS_OFFICER, RoleEnum.CLAIMS_MANAGER, RoleEnum.FRAUD_INVESTIGATOR,
            RoleEnum.COMPLIANCE_OFFICER, RoleEnum.SYSTEM_ADMIN,
        ])
    ),
):
    """Uploads a document, runs OCR extraction, and stores structured results in the database."""

    # Validate file type
    content_type = file.content_type or ""
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    allowed_exts = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".webp", ".txt"}

    if content_type not in ALLOWED_MIME_TYPES and file_ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type. Allowed: PDF, PNG, JPG, TIFF, TXT. Got: {content_type or file_ext}",
        )

    # Read and validate file size
    file_bytes = await file.read()
    file_size = len(file_bytes)
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size {file_size // (1024*1024)}MB exceeds the {MAX_FILE_SIZE_MB}MB limit.",
        )

    # Departmental restriction: Claims Officers may only upload documents for
    # claims in their queue (assigned to them or unassigned).
    if claim_reference:
        ref_claim = db.query(Claim).filter(
            (Claim.claim_id == claim_reference) | (Claim.id == claim_reference)
        ).first()
        if ref_claim and current_user.role == RoleEnum.CLAIMS_OFFICER and ref_claim.assigned_officer_id not in (None, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorised to upload documents for this claim.",
            )

    # Save file to disk (sanitized — strip any directory components)
    safe_name = os.path.basename((file.filename or "document").replace(" ", "_"))
    if not safe_name or safe_name in (".", ".."):
        safe_name = "document"
    os.makedirs(settings.DOCUMENTS_DIR, exist_ok=True)
    unique_filename = f"OCR_{uuid.uuid4().hex[:8]}_{safe_name}"
    file_path = os.path.join(settings.DOCUMENTS_DIR, unique_filename)
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    # Resolve claim if provided
    claim_db = None
    expected_claim_data = {}
    known_hashes = []
    if claim_reference:
        claim_db = db.query(Claim).filter(
            (Claim.claim_id == claim_reference) | (Claim.id == claim_reference)
        ).first()
        if claim_db:
            expected_claim_data = {
                "incident_date": claim_db.incident_date.isoformat() if claim_db.incident_date else "",
                "claim_amount": claim_db.amount,
            }
            # Collect existing document hashes for duplicate detection
            from ..models.sqlalchemy_models import ClaimDocument
            other_docs = db.query(ClaimDocument).filter(ClaimDocument.claim_id != claim_db.id).all()
            known_hashes = [d.file_path for d in other_docs]

    # Create initial OCRDocument record
    ocr_doc = OCRDocument(
        claim_id=claim_db.id if claim_db else None,
        uploaded_by_id=current_user.id,
        filename=safe_name,
        file_path=file_path,
        mime_type=content_type or "application/octet-stream",
        file_size_bytes=file_size,
        processing_status="processing",
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(ocr_doc)
    db.commit()
    db.refresh(ocr_doc)

    # Run OCR processing
    try:
        ocr_result = process_document(
            file_path=file_path,
            expected_claim_data=expected_claim_data,
            known_hashes=known_hashes,
        )

        # Build structured extracted fields
        extracted_fields = {}
        raw_text = ocr_result.get("raw_text_snippet") or ""
        
        # Extract full text if available via re-processing
        from ..ocr.ocr_service import document_verifier
        full_ocr = document_verifier.provider.extract_text(file_path)
        raw_text_full = full_ocr.get("text", "")

        if ocr_result.get("extracted_dates"):
            extracted_fields["dates"] = ocr_result["extracted_dates"]
        if ocr_result.get("extracted_amounts"):
            extracted_fields["amounts"] = ocr_result["extracted_amounts"]
        if ocr_result.get("extracted_national_ids"):
            extracted_fields["national_ids"] = ocr_result["extracted_national_ids"]

        # Update OCR document record
        ocr_doc.document_type = ocr_result.get("document_type", "Supporting Document")
        ocr_doc.document_hash_sha256 = ocr_result.get("document_hash_sha256", "")
        ocr_doc.ocr_engine = full_ocr.get("engine", "Tesseract-OCR")
        ocr_doc.raw_text = raw_text_full
        ocr_doc.confidence_score = ocr_result.get("confidence", full_ocr.get("confidence", 0.0))
        ocr_doc.extracted_fields = extracted_fields
        ocr_doc.extracted_dates = ocr_result.get("extracted_dates", [])
        ocr_doc.extracted_amounts = ocr_result.get("extracted_amounts", [])
        ocr_doc.extracted_national_ids = ocr_result.get("extracted_national_ids", [])
        ocr_doc.has_date_mismatch = ocr_result.get("date_mismatch", False)
        ocr_doc.missing_fields = ocr_result.get("missing_fields", [])
        ocr_doc.flags = ocr_result.get("flags", [])
        ocr_doc.processing_status = "completed"
        ocr_doc.processed_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(ocr_doc)

    except Exception as e:
        ocr_doc.processing_status = "failed"
        ocr_doc.flags = [f"processing_error: {str(e)}"]
        db.commit()

    log_audit_trail(
        db, current_user, action="OCR_DOCUMENT_UPLOADED",
        target=f"OCRDocument:{ocr_doc.id}",
        detail={"filename": safe_name, "claim": claim_reference, "status": ocr_doc.processing_status}
    )

    return {
        "message": "Document uploaded and OCR processing complete.",
        "document_id": ocr_doc.id,
        "filename": ocr_doc.filename,
        "processing_status": ocr_doc.processing_status,
        "document_type": ocr_doc.document_type,
        "confidence_score": ocr_doc.confidence_score,
        "flags": ocr_doc.flags or [],
        "extracted_dates": ocr_doc.extracted_dates or [],
        "extracted_amounts": ocr_doc.extracted_amounts or [],
        "extracted_national_ids": ocr_doc.extracted_national_ids or [],
        "has_date_mismatch": ocr_doc.has_date_mismatch,
        "missing_fields": ocr_doc.missing_fields or [],
    }


@router.get("/documents", summary="List OCR processed documents")
async def list_ocr_documents(
    claim_reference: Optional[str] = Query(None, description="Filter by claim ID"),
    processing_status: Optional[str] = Query(None, description="pending, processing, completed, failed"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = db.query(OCRDocument).order_by(desc(OCRDocument.uploaded_at))

    if claim_reference:
        claim_db = db.query(Claim).filter(
            (Claim.claim_id == claim_reference) | (Claim.id == claim_reference)
        ).first()
        if claim_db:
            query = query.filter(OCRDocument.claim_id == claim_db.id)

    if processing_status:
        query = query.filter(OCRDocument.processing_status == processing_status.lower())

    # Departmental data-access restrictions
    visible_claim_ids = _claims_visible_to_user(db, current_user)
    if current_user.role == RoleEnum.CLAIMS_OFFICER:
        query = query.filter(
            (OCRDocument.claim_id.is_(None)) | (OCRDocument.claim_id.in_(visible_claim_ids))
        )
    elif current_user.role == RoleEnum.COMPLIANCE_OFFICER:
        query = query.filter(OCRDocument.claim_id.in_(visible_claim_ids))
    elif current_user.role == RoleEnum.FRAUD_INVESTIGATOR:
        query = query.filter(OCRDocument.claim_id.in_(visible_claim_ids))

    docs = query.offset(skip).limit(limit).all()
    return [_serialize_document(d) for d in docs]


@router.get("/documents/{document_id}", summary="Get detailed OCR extraction results for a document")
async def get_ocr_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    doc = db.query(OCRDocument).filter(OCRDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="OCR document record not found.")

    # Departmental data-access restrictions
    visible_claim_ids = _claims_visible_to_user(db, current_user)
    if current_user.role in (RoleEnum.CLAIMS_OFFICER, RoleEnum.COMPLIANCE_OFFICER, RoleEnum.FRAUD_INVESTIGATOR):
        if doc.claim_id is not None and doc.claim_id not in visible_claim_ids:
            raise HTTPException(status_code=403, detail="Not authorised to view this document.")

    return _serialize_document(doc)


@router.post("/documents/{document_id}/correct", summary="Apply manual correction to an OCR-extracted field")
async def correct_ocr_field(
    document_id: int,
    correction: FieldCorrectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Allows authorised employees to correct extracted fields. Original values are preserved in audit trail."""
    doc = db.query(OCRDocument).filter(OCRDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="OCR document record not found.")

    visible_claim_ids = _claims_visible_to_user(db, current_user)
    if doc.claim_id is not None and doc.claim_id not in visible_claim_ids:
        raise HTTPException(status_code=403, detail="Not authorised to correct this document.")

    # Get original value from extracted_fields
    original_value = None
    if doc.extracted_fields and correction.field_name in doc.extracted_fields:
        original_value = str(doc.extracted_fields[correction.field_name])

    # Create correction record (audit trail)
    new_correction = OCRCorrection(
        document_id=doc.id,
        corrected_by_id=current_user.id,
        field_name=correction.field_name,
        original_value=original_value,
        corrected_value=correction.corrected_value,
        correction_note=correction.correction_note,
        corrected_at=datetime.now(timezone.utc),
    )
    db.add(new_correction)

    # Update extracted_fields in-place (store corrected value)
    fields = dict(doc.extracted_fields or {})
    fields[correction.field_name] = correction.corrected_value
    doc.extracted_fields = fields
    doc.is_manually_verified = True
    doc.verified_by_id = current_user.id
    doc.verified_at = datetime.now(timezone.utc)

    db.commit()

    log_audit_trail(
        db, current_user, action="OCR_FIELD_CORRECTED",
        target=f"OCRDocument:{doc.id}",
        detail={"field": correction.field_name, "original": original_value, "corrected": correction.corrected_value}
    )

    return {
        "message": f"Field '{correction.field_name}' corrected and audit trail recorded.",
        "document_id": doc.id,
        "field_name": correction.field_name,
        "corrected_value": correction.corrected_value,
    }


@router.post("/documents/{document_id}/verify", summary="Mark an OCR document as manually verified")
async def mark_document_verified(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    doc = db.query(OCRDocument).filter(OCRDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="OCR document record not found.")

    visible_claim_ids = _claims_visible_to_user(db, current_user)
    if doc.claim_id is not None and doc.claim_id not in visible_claim_ids:
        raise HTTPException(status_code=403, detail="Not authorised to verify this document.")

    doc.is_manually_verified = True
    doc.verified_by_id = current_user.id
    doc.verified_at = datetime.now(timezone.utc)
    db.commit()

    log_audit_trail(
        db, current_user, action="OCR_DOCUMENT_VERIFIED",
        target=f"OCRDocument:{doc.id}",
        detail={"filename": doc.filename}
    )

    return {"message": "Document marked as manually verified.", "document_id": doc.id}
