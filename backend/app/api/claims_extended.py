import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, status
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from ..services.db import get_db, SessionLocal
from ..services import tenant as tenant_service
from ..models.sqlalchemy_models import Claim, ClaimDocument, FraudAssessment, Notification, User, RoleEnum, Policy, Customer
from ..dependencies import require_role, get_current_active_user
from ..integrations.mock_services import PolicyService, CustomerService, ClaimsService
from ..ocr.ocr_service import process_document
from ..ml.inference import assess_claim_fraud

router = APIRouter(prefix="/claims", tags=["Claims"])

# Helper to store uploaded files safely
def save_uploaded_file(upload: UploadFile, claim_id: str) -> str:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "documents"))
    os.makedirs(base_dir, exist_ok=True)
    filename = f"{claim_id}_{uuid.uuid4().hex}_{upload.filename}"  # ensure uniqueness
    file_path = os.path.join(base_dir, filename)
    with open(file_path, "wb") as buffer:
        buffer.write(upload.file.read())
    return file_path

async def background_process_claim(claim_id: int, organisation_id: int | None = None):
    with tenant_service.bound_tenant(organisation_id):
        await _background_process_claim(claim_id)


async def _background_process_claim(claim_id: int):
    # Create a fresh DB session for the background task
    db = SessionLocal()
    # Load claim with related objects
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        db.close()
        return
    # 1️⃣ OCR on each document
    ocr_results = []
    for doc in claim.documents:
        result = process_document(doc.file_path)
        ocr_results.append(result)
    # 2️⃣ Gather features (very simplified for demo)
    policy_info = PolicyService().get_policy(claim.policy.policy_number)
    customer_info = CustomerService().get_customer(claim.customer.customer_id)
    previous_claims = ClaimsService().list_previous_claims(claim.policy.policy_number)
    features = {
        "amount": claim.amount,
        "policy_type": policy_info.get("policy_type"),
        "customer_history_len": len(previous_claims),
        "ocr_flags": [r.get("flags", []) for r in ocr_results],
    }
    # 3️⃣ Fraud assessment (placeholder model)
    assessment = assess_claim_fraud(features)
    # 4️⃣ Persist FraudAssessment
    fraud = FraudAssessment(
        claim_id=claim.id,
        risk_score=assessment["risk_score"],
        risk_category=assessment["risk_category"],
        indicators=assessment["indicators"],
        explanation=assessment["explanation"],
        model_version=assessment["model_version"],
    )
    db.add(fraud)
    # 5️⃣ Update claim status if high/critical
    if assessment["risk_category"] in ["High", "Critical"]:
        claim.status = "flagged"
        # 6️⃣ Create notification for investigators (placeholder recipient_id=1)
        notification = Notification(
            recipient_id=1,
            message=f"Claim {claim.claim_id} flagged as {assessment['risk_category']} (score {assessment['risk_score']})",
        )
        db.add(notification)
    db.commit()
    db.close()


@router.post("/submit", summary="Submit a new insurance claim with supporting documents")
async def submit_claim(
    background_tasks: BackgroundTasks,
    policy_number: str = Form(...),
    claim_type: str = Form(...),
    claim_date: str = Form(...),
    claim_amount: float = Form(...),
    beneficiary_name: Optional[str] = Form(None),
    documents: List[UploadFile] = File([]),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleEnum.CLAIMS_OFFICER)),
):
    # Basic validation (could be expanded)
    try:
        incident_dt = datetime.fromisoformat(claim_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident date format")
    # Resolve the policy from the system of record; never fabricate one.
    policy_obj = db.query(Policy).filter(Policy.policy_number == policy_number.strip()).first()
    if not policy_obj or not policy_obj.customer:
        raise HTTPException(status_code=404, detail="Policy and policyholder must exist before a claim is submitted.")
    customer_obj = policy_obj.customer
    # Create Claim record with proper foreign keys
    claim = Claim(
        claim_id=f"CLM{uuid.uuid4().hex[:10].upper()}",
        policy_id=policy_obj.id,
        customer_id=customer_obj.id,
        claim_type=claim_type,
        amount=claim_amount,
        incident_date=incident_dt,
        description="Submitted via API",
        status="submitted",
    )
    # Store documents
    for upload in documents:
        file_path = save_uploaded_file(upload, claim.claim_id)
        doc = ClaimDocument(
            filename=upload.filename,
            file_path=file_path,
            mime_type=upload.content_type or "application/octet-stream",
        )
        claim.documents.append(doc)
    db.add(claim)
    db.commit()
    db.refresh(claim)
    # Kick off background processing
    background_tasks.add_task(background_process_claim, claim.id, current_user.organisation_id)
    return {"message": "Claim submitted", "claim_id": claim.claim_id}

@router.get("/", summary="List all claims (admin/manager view)")
async def list_claims(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleEnum.CLAIMS_MANAGER)),
    skip: int = 0,
    limit: int = 100,
):
    claims = db.query(Claim).offset(skip).limit(limit).all()
    return [{
        "claim_id": c.claim_id,
        "policy_number": c.policy.policy_number if c.policy else None,
        "customer_id": c.customer.customer_id if c.customer else None,
        "claim_type": c.claim_type,
        "amount": c.amount,
        "status": c.status,
        "submitted": c.submission_date,
    } for c in claims]

@router.get("/{claim_id}", summary="Get details for a single claim")
async def get_claim(
    claim_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    claim = db.query(Claim).filter(Claim.claim_id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return {
        "claim_id": claim.claim_id,
        "policy_number": claim.policy.policy_number if claim.policy else None,
        "customer_id": claim.customer.customer_id if claim.customer else None,
        "claim_type": claim.claim_type,
        "amount": claim.amount,
        "incident_date": claim.incident_date,
        "submission_date": claim.submission_date,
        "status": claim.status,
        "documents": [d.filename for d in claim.documents],
        "assessment": {
            "risk_score": claim.assessment.risk_score if claim.assessment else None,
            "risk_category": claim.assessment.risk_category if claim.assessment else None,
            "indicators": claim.assessment.indicators if claim.assessment else None,
            "explanation": claim.assessment.explanation if claim.assessment else None,
        } if claim.assessment else None,
    }

@router.put("/{claim_id}", summary="Update a claim (claims officer)")
async def update_claim(
    claim_id: str,
    status: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleEnum.CLAIMS_OFFICER)),
):
    claim = db.query(Claim).filter(Claim.claim_id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if status:
        claim.status = status
    db.commit()
    db.refresh(claim)
    return {"msg": "Claim updated", "claim_id": claim.claim_id, "status": claim.status}
