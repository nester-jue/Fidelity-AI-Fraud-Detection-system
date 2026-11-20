import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..services.db import get_db, SessionLocal
from ..models.sqlalchemy_models import (
    Claim, ClaimDocument, FraudAssessment, Notification, User, RoleEnum, Policy, Customer, Investigation
)
from ..dependencies import get_current_active_user, require_roles, log_audit_trail
from ..integrations.mock_services import PolicyService, CustomerService, ClaimsService
from ..ocr.ocr_service import process_document
from ..ml.fraud_engine import fraud_engine
from ..core.config import settings

router = APIRouter(prefix="/claims", tags=["Claims Management"])

def save_uploaded_file(upload: UploadFile, claim_id: str) -> str:
    os.makedirs(settings.DOCUMENTS_DIR, exist_ok=True)
    safe_name = upload.filename.replace(" ", "_") if upload.filename else "doc.bin"
    unique_filename = f"{claim_id}_{uuid.uuid4().hex[:6]}_{safe_name}"
    file_path = os.path.join(settings.DOCUMENTS_DIR, unique_filename)
    with open(file_path, "wb") as buffer:
        buffer.write(upload.file.read())
    return file_path

def run_ai_claim_analysis(claim_id: int):
    """Background task: Performs OCR document analysis, extracts features, and runs FraudDetectionEngine."""
    db = SessionLocal()
    try:
        claim = db.query(Claim).filter(Claim.id == claim_id).first()
        if not claim:
            return

        # 1. Collect and process documents via OCR
        ocr_findings = []
        known_hashes = [
            doc.file_path for doc in db.query(ClaimDocument).filter(ClaimDocument.claim_id != claim.id).all()
        ]
        
        for doc in claim.documents:
            res = process_document(
                file_path=doc.file_path,
                expected_claim_data={
                    "incident_date": claim.incident_date.isoformat(),
                    "claim_amount": claim.amount,
                },
                known_hashes=known_hashes,
            )
            ocr_findings.append(res)

        # 2. Historical claims for this customer/policy
        historical_claims_objs = (
            db.query(Claim)
            .filter((Claim.customer_id == claim.customer_id) & (Claim.id != claim.id))
            .all()
        )
        history_list = [
            {
                "claim_id": h.claim_id,
                "amount": h.amount,
                "incident_date": h.incident_date.isoformat() if h.incident_date else "",
                "policy_number": h.policy.policy_number if h.policy else "",
            }
            for h in historical_claims_objs
        ]

        # 3. Policy & Customer records
        policy_dict = {
            "policy_number": claim.policy.policy_number if claim.policy else "UNKNOWN",
            "policy_type": claim.policy.policy_type if claim.policy else "Life",
            "effective_date": claim.policy.effective_date.isoformat() if claim.policy else "2023-01-01",
            "coverage_amount": getattr(claim.policy, "coverage_amount", 50000.0) or 50000.0,
        }
        cust_dict = {
            "customer_id": claim.customer.customer_id if claim.customer else "UNKNOWN",
            "national_id": claim.customer.national_id if claim.customer else "",
        }

        # 4. Evaluate Fraud Risk
        assessment_res = fraud_engine.evaluate_claim(
            claim_data={
                "claim_id": claim.claim_id,
                "policy_number": policy_dict["policy_number"],
                "amount": claim.amount,
                "incident_date": claim.incident_date.isoformat(),
                "submission_date": claim.submission_date.isoformat(),
                "claim_type": claim.claim_type,
            },
            policy_data=policy_dict,
            customer_data=cust_dict,
            historical_claims=history_list,
            ocr_results=ocr_findings,
        )

        # 5. Persist or Update FraudAssessment
        assessment = db.query(FraudAssessment).filter(FraudAssessment.claim_id == claim.id).first()
        if not assessment:
            assessment = FraudAssessment(
                claim_id=claim.id,
                risk_score=assessment_res["risk_score"],
                risk_category=assessment_res["risk_category"],
                indicators=assessment_res["indicators"],
                explanation=assessment_res["explanation"],
                model_version=assessment_res["model_version"],
                assessed_at=datetime.now(timezone.utc),
            )
            db.add(assessment)
        else:
            assessment.risk_score = assessment_res["risk_score"]
            assessment.risk_category = assessment_res["risk_category"]
            assessment.indicators = assessment_res["indicators"]
            assessment.explanation = assessment_res["explanation"]
            assessment.model_version = assessment_res["model_version"]
            assessment.assessed_at = datetime.now(timezone.utc)

        # 6. Flag claim & notify if High or Critical risk
        if assessment_res["risk_category"] in ["High", "Critical"]:
            if claim.status in ["submitted", "in_review"]:
                claim.status = "flagged"

            # Create an investigation alert record if none exists
            existing_inv = db.query(Investigation).filter(Investigation.claim_id == claim.id).first()
            if not existing_inv:
                inv = Investigation(
                    claim_id=claim.id,
                    investigator_id=1,  # Default system investigator
                    status="open",
                    notes=f"Auto-generated priority investigation: {assessment_res['explanation']}",
                    opened_at=datetime.now(timezone.utc),
                )
                db.add(inv)

            # Alert notification for investigators
            notif = Notification(
                recipient_id=1,
                message=f"URGENT FRAUD ALERT: Claim {claim.claim_id} flagged as {assessment_res['risk_category']} Risk (Score: {assessment_res['risk_score']}/100).",
                read=False,
            )
            db.add(notif)

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error in background AI claim analysis for claim {claim_id}: {e}")
    finally:
        db.close()

@router.post("/submit", summary="Submit a new insurance claim with documents and auto-score fraud risk")
async def submit_claim(
    background_tasks: BackgroundTasks,
    policy_number: str = Form(..., description="Active policy reference number"),
    claim_type: str = Form(..., description="e.g. Death Benefit, Funeral Cash Plan, Accident"),
    claim_amount: float = Form(..., description="Claim payout amount requested"),
    incident_date: str = Form(..., description="Date of death or incident (YYYY-MM-DD)"),
    description: Optional[str] = Form("", description="Claim narrative or circumstances"),
    beneficiary_name: Optional[str] = Form(None, description="Designated beneficiary"),
    documents: List[UploadFile] = File([], description="Supporting files (Death cert, medical report, ID)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        incident_dt = datetime.fromisoformat(incident_date.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident_date format. Use YYYY-MM-DD.")

    # 1. Lookup or create Policy & Customer
    policy = db.query(Policy).filter(Policy.policy_number == policy_number).first()
    if not policy:
        # Query Policy Mock Service
        mock_p = PolicyService().get_policy(policy_number)
        # Check customer
        cust = db.query(Customer).filter(Customer.customer_id == mock_p["customer_id"]).first()
        if not cust:
            mock_c = CustomerService().get_customer(mock_p["customer_id"])
            cust = Customer(
                customer_id=mock_c["customer_id"],
                name=mock_c["name"],
                national_id=mock_c["national_id"],
                date_of_birth=datetime.fromisoformat(mock_c["date_of_birth"]),
            )
            db.add(cust)
            db.commit()
            db.refresh(cust)

        policy = Policy(
            policy_number=policy_number,
            policy_type=claim_type,
            customer_id=cust.id,
            effective_date=datetime.fromisoformat(mock_p["effective_date"]),
            expiry_date=datetime.fromisoformat(mock_p["expiry_date"]),
        )
        db.add(policy)
        db.commit()
        db.refresh(policy)

    # 2. Create Claim record
    claim_ref = f"CLM-2026-{uuid.uuid4().hex[:6].upper()}"
    new_claim = Claim(
        claim_id=claim_ref,
        policy_id=policy.id,
        customer_id=policy.customer_id,
        claim_type=claim_type,
        amount=claim_amount,
        incident_date=incident_dt,
        submission_date=datetime.now(timezone.utc),
        description=description,
        status="submitted",
    )
    db.add(new_claim)
    db.commit()
    db.refresh(new_claim)

    # 3. Store uploaded documents
    stored_docs = []
    for upload in documents:
        if upload.filename:
            f_path = save_uploaded_file(upload, new_claim.claim_id)
            c_doc = ClaimDocument(
                claim_id=new_claim.id,
                filename=upload.filename,
                file_path=f_path,
                mime_type=upload.content_type or "application/octet-stream",
            )
            db.add(c_doc)
            stored_docs.append(upload.filename)
    db.commit()

    # 4. Trigger asynchronous background AI fraud analysis
    background_tasks.add_task(run_ai_claim_analysis, new_claim.id)

    log_audit_trail(
        db, current_user, action="CLAIM_SUBMITTED", target=f"Claim:{new_claim.claim_id}",
        detail={"amount": claim_amount, "policy": policy_number, "docs": stored_docs}
    )

    return {
        "message": "Claim successfully submitted. AI fraud detection analysis initiated.",
        "claim_id": new_claim.claim_id,
        "policy_number": policy_number,
        "amount": claim_amount,
        "status": new_claim.status,
        "documents_uploaded": stored_docs,
    }

@router.get("/", summary="List claims with search, status and risk category filters")
async def list_claims(
    status: Optional[str] = Query(None, description="Filter by status (submitted, flagged, in_review, approved, rejected)"),
    risk_category: Optional[str] = Query(None, description="Filter by AI risk (Low, Medium, High, Critical)"),
    search: Optional[str] = Query(None, description="Search by Claim ID, Policy Number, or Customer Name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = db.query(Claim).order_by(desc(Claim.submission_date))

    if status:
        query = query.filter(Claim.status == status.lower())
    if risk_category:
        query = query.join(FraudAssessment).filter(FraudAssessment.risk_category == risk_category.capitalize())
    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.join(Policy).join(Customer).filter(
            (Claim.claim_id.ilike(search_fmt)) |
            (Policy.policy_number.ilike(search_fmt)) |
            (Customer.name.ilike(search_fmt)) |
            (Customer.national_id.ilike(search_fmt))
        )

    claims = query.offset(skip).limit(limit).all()

    results = []
    for c in claims:
        assessment = c.assessment
        results.append({
            "id": c.id,
            "claim_id": c.claim_id,
            "policy_number": c.policy.policy_number if c.policy else "",
            "policy_type": c.policy.policy_type if c.policy else "",
            "customer_name": c.customer.name if c.customer else "",
            "customer_id": c.customer.customer_id if c.customer else "",
            "national_id": c.customer.national_id if c.customer else "",
            "claim_type": c.claim_type,
            "amount": c.amount,
            "incident_date": c.incident_date.isoformat() if c.incident_date else "",
            "submission_date": c.submission_date.isoformat() if c.submission_date else "",
            "status": c.status,
            "documents_count": len(c.documents),
            "risk_score": assessment.risk_score if assessment else None,
            "risk_category": assessment.risk_category if assessment else "Pending AI Analysis",
            "indicators": assessment.indicators if assessment else [],
        })
    return results

@router.get("/{claim_id}", summary="Get detailed claim profile and AI analysis")
async def get_claim_details(
    claim_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    claim = db.query(Claim).filter((Claim.claim_id == claim_id) | (Claim.id == claim_id)).first()
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found.")

    assessment = claim.assessment
    investigation = db.query(Investigation).filter(Investigation.claim_id == claim.id).first()

    return {
        "id": claim.id,
        "claim_id": claim.claim_id,
        "claim_type": claim.claim_type,
        "amount": claim.amount,
        "incident_date": claim.incident_date.isoformat() if claim.incident_date else None,
        "submission_date": claim.submission_date.isoformat() if claim.submission_date else None,
        "description": claim.description,
        "status": claim.status,
        "policy": {
            "policy_number": claim.policy.policy_number if claim.policy else None,
            "policy_type": claim.policy.policy_type if claim.policy else None,
            "effective_date": claim.policy.effective_date.isoformat() if claim.policy else None,
            "expiry_date": claim.policy.expiry_date.isoformat() if claim.policy else None,
        },
        "customer": {
            "customer_id": claim.customer.customer_id if claim.customer else None,
            "name": claim.customer.name if claim.customer else None,
            "national_id": claim.customer.national_id if claim.customer else None,
            "date_of_birth": claim.customer.date_of_birth.isoformat() if claim.customer and claim.customer.date_of_birth else None,
        },
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "mime_type": doc.mime_type,
                "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            }
            for doc in claim.documents
        ],
        "assessment": {
            "risk_score": assessment.risk_score if assessment else None,
            "risk_category": assessment.risk_category if assessment else "Pending",
            "indicators": assessment.indicators if assessment else [],
            "explanation": assessment.explanation if assessment else "Analysis in progress.",
            "model_version": assessment.model_version if assessment else None,
            "assessed_at": assessment.assessed_at.isoformat() if assessment else None,
        } if assessment else None,
        "investigation": {
            "id": investigation.id,
            "status": investigation.status,
            "notes": investigation.notes,
            "opened_at": investigation.opened_at.isoformat() if investigation.opened_at else None,
            "closed_at": investigation.closed_at.isoformat() if investigation.closed_at else None,
        } if investigation else None,
    }

@router.put("/{claim_id}", summary="Update claim status (e.g. approve, reject, refer)")
async def update_claim_status(
    claim_id: str,
    status: str = Form(..., description="New status: approved, rejected, in_review, flagged"),
    reason: Optional[str] = Form("", description="Officer reason or justification"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([RoleEnum.CLAIMS_OFFICER, RoleEnum.CLAIMS_MANAGER, RoleEnum.SYSTEM_ADMIN])),
):
    claim = db.query(Claim).filter((Claim.claim_id == claim_id) | (Claim.id == claim_id)).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found.")

    old_status = claim.status
    claim.status = status.lower()
    db.commit()

    log_audit_trail(
        db, current_user, action="CLAIM_STATUS_UPDATED", target=f"Claim:{claim.claim_id}",
        detail={"old_status": old_status, "new_status": claim.status, "reason": reason}
    )

    return {
        "message": f"Claim {claim.claim_id} status updated to '{claim.status}'.",
        "claim_id": claim.claim_id,
        "status": claim.status,
    }

@router.post("/{claim_id}/score", summary="Manually trigger or recalculate AI fraud risk score")
async def rescore_claim(
    claim_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    claim = db.query(Claim).filter((Claim.claim_id == claim_id) | (Claim.id == claim_id)).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found.")

    # Execute synchronous re-analysis
    run_ai_claim_analysis(claim.id)
    db.refresh(claim)

    log_audit_trail(db, current_user, action="CLAIM_RESCORED", target=f"Claim:{claim.claim_id}")

    return {
        "message": f"AI Fraud score recalculated for {claim.claim_id}.",
        "claim_id": claim.claim_id,
        "risk_score": claim.assessment.risk_score if claim.assessment else None,
        "risk_category": claim.assessment.risk_category if claim.assessment else None,
    }

@router.get("/fnol/list", summary="List First Notice of Loss (FNOL) preliminary intake notifications")
async def list_fnol_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Returns recent First Notice of Loss notifications before full claim adjudication."""
    claims = db.query(Claim).order_by(desc(Claim.created_at)).limit(10).all()
    fnol_list = []
    channels = ["Branch Walk-In", "Digital Portal", "Broker Advisory", "Contact Centre"]
    
    for idx, c in enumerate(claims):
        fnol_list.append({
            "fnol_reference": f"FNOL-2026-00{c.id:02d}",
            "claim_id": c.claim_id,
            "policy_number": c.policy.policy_number if c.policy else "POL-LIF-801294",
            "claimant_name": c.customer.name if c.customer else "Simbarashe Mpofu",
            "event_type": c.claim_type,
            "incident_date": c.incident_date.strftime("%Y-%m-%d") if c.incident_date else "2026-05-10",
            "notification_date": c.submission_date.strftime("%Y-%m-%d %H:%M") if c.submission_date else "2026-05-12 09:30",
            "reporting_channel": channels[idx % len(channels)],
            "estimated_amount": c.amount,
            "initial_triage": "Fast-Track" if (c.assessment and c.assessment.risk_category == "Low") else ("SIU Review Priority" if (c.assessment and c.assessment.risk_category in ["High", "Critical"]) else "Standard Intake"),
            "status": "Claim Created" if c.status in ["approved", "in_review", "flagged"] else "Pending Documentation",
        })

    return {
        "total_fnol": len(fnol_list),
        "fnol_intakes": fnol_list,
    }

@router.post("/fnol", summary="Register a First Notice of Loss (FNOL) notification")
async def submit_fnol(
    policy_number: str = Form(..., description="Active policy reference"),
    claimant_name: str = Form(..., description="Reporting individual / claimant name"),
    event_type: str = Form(..., description="Nature of loss event"),
    incident_date: str = Form(..., description="Date event occurred"),
    estimated_amount: float = Form(..., description="Preliminary estimated loss amount"),
    reporting_channel: str = Form("Branch Walk-In", description="Channel notice received"),
    initial_notes: Optional[str] = Form("", description="Initial facts and notification summary"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Registers First Notice of Loss, validates policy existence, and prepares claim routing."""
    fnol_ref = f"FNOL-2026-{uuid.uuid4().hex[:5].upper()}"
    
    # Check policy
    policy = db.query(Policy).filter(Policy.policy_number == policy_number).first()
    policy_valid = bool(policy)
    
    # Determine initial triage queue
    triage_queue = "Standard Verification"
    if estimated_amount > 50000:
        triage_queue = "High-Value Claims Review"
    elif not policy_valid:
        triage_queue = "Underwriting Exception Desk"

    log_audit_trail(
        db, current_user, action="FNOL_REGISTERED", target=f"FNOL:{fnol_ref}",
        detail={"policy": policy_number, "claimant": claimant_name, "amount": estimated_amount, "queue": triage_queue}
    )

    return {
        "message": "First Notice of Loss (FNOL) successfully logged and assigned to triage queue.",
        "fnol_reference": fnol_ref,
        "policy_number": policy_number,
        "policy_status": "Active & Validated" if policy_valid else "Pending Underwriting Lookup",
        "triage_queue": triage_queue,
        "notification_timestamp": datetime.now(timezone.utc).isoformat(),
        "next_steps": "Submit formal death certificate or medical proof in Claims Management to trigger automated OCR and AI risk score.",
    }

