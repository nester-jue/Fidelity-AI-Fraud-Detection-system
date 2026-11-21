"""
AI Forensic Analysis API
Provides forensic analysis overview, risk assessments, and explainable AI findings.
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from ..services.db import get_db
from ..models.sqlalchemy_models import (
    Claim, FraudAssessment, Investigation, User, RoleEnum, OCRDocument
)
from ..dependencies import get_current_active_user, require_roles
from ..core.config import settings

router = APIRouter(prefix="/forensics", tags=["AI Forensic Analysis"])


@router.get("/risk-thresholds", summary="Get the configurable AI fraud risk classification thresholds")
async def get_risk_thresholds():
    return {
        "thresholds": settings.risk_thresholds,
        "classification": {
            "Low Risk": {"min": 0, "max": settings.RISK_THRESHOLD_LOW_MAX},
            "Medium Risk": {"min": settings.RISK_THRESHOLD_MEDIUM_MIN, "max": settings.RISK_THRESHOLD_MEDIUM_MAX},
            "High Risk": {"min": settings.RISK_THRESHOLD_HIGH_MIN, "max": settings.RISK_THRESHOLD_HIGH_MAX},
            "Critical Risk": {"min": settings.RISK_THRESHOLD_CRITICAL_MIN, "max": 100},
        },
    }


@router.put("/risk-thresholds", summary="Update configurable AI risk classification thresholds (system admin)")
async def update_risk_thresholds(
    updates: dict,
    current_user: User = Depends(require_roles([RoleEnum.SYSTEM_ADMIN])),
):
    """Updates thresholds at runtime. Values validated as integers 0-100 and min<=max."""
    from fastapi import HTTPException

    allowed = {
        "LOW_MAX": "RISK_THRESHOLD_LOW_MAX",
        "LOW_MIN": "RISK_THRESHOLD_LOW_MIN",
        "MEDIUM_MAX": "RISK_THRESHOLD_MEDIUM_MAX",
        "MEDIUM_MIN": "RISK_THRESHOLD_MEDIUM_MIN",
        "HIGH_MAX": "RISK_THRESHOLD_HIGH_MAX",
        "HIGH_MIN": "RISK_THRESHOLD_HIGH_MIN",
        "CRITICAL_MAX": "RISK_THRESHOLD_CRITICAL_MAX",
        "CRITICAL_MIN": "RISK_THRESHOLD_CRITICAL_MIN",
    }
    applied = {}
    for key, val in (updates or {}).items():
        attr = allowed.get(key)
        if attr is None:
            raise HTTPException(status_code=400, detail=f"Unknown threshold key: {key}")
        if not isinstance(val, int) or isinstance(val, bool) or not 0 <= val <= 100:
            raise HTTPException(status_code=400, detail=f"Invalid value for {key}: must be integer 0-100")
        setattr(settings, attr, val)
        applied[key] = val

    # Enforce min < max sanity
    if settings.RISK_THRESHOLD_LOW_MAX >= settings.RISK_THRESHOLD_MEDIUM_MAX:
        raise HTTPException(status_code=400, detail="LOW_MAX must be less than MEDIUM_MAX")
    if settings.RISK_THRESHOLD_MEDIUM_MAX >= settings.RISK_THRESHOLD_HIGH_MAX:
        raise HTTPException(status_code=400, detail="MEDIUM_MAX must be less than HIGH_MAX")
    if settings.RISK_THRESHOLD_HIGH_MAX >= settings.RISK_THRESHOLD_CRITICAL_MAX:
        raise HTTPException(status_code=400, detail="HIGH_MAX must be less than CRITICAL_MAX")

    return {"message": "Risk thresholds updated.", "thresholds": settings.risk_thresholds, "applied": applied}


def _risk_color(category: str) -> str:
    return {
        "Critical": "#EF4444",
        "High": "#F97316",
        "Medium": "#F59E0B",
        "Low": "#10B981",
    }.get(category, "#6B7280")


@router.get("/overview", summary="Get AI forensic analysis overview statistics")
async def get_forensic_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    total_claims = db.query(Claim).count()
    total_analysed = db.query(FraudAssessment).count()
    pending_analysis = total_claims - total_analysed

    low_risk = db.query(FraudAssessment).filter(FraudAssessment.risk_category == "Low").count()
    medium_risk = db.query(FraudAssessment).filter(FraudAssessment.risk_category == "Medium").count()
    high_risk = db.query(FraudAssessment).filter(FraudAssessment.risk_category == "High").count()
    critical_risk = db.query(FraudAssessment).filter(FraudAssessment.risk_category == "Critical").count()

    confirmed_suspicious = db.query(Investigation).filter(
        Investigation.status == "confirmed_fraud"
    ).count()

    completion_rate = round((total_analysed / total_claims * 100), 1) if total_claims > 0 else 0.0

    # Average risk score
    avg_score_result = db.query(func.avg(FraudAssessment.risk_score)).scalar()
    avg_risk_score = round(float(avg_score_result or 0), 1)

    return {
        "total_claims_analysed": total_analysed,
        "total_claims": total_claims,
        "claims_pending_analysis": max(0, pending_analysis),
        "analysis_completion_rate": completion_rate,
        "average_risk_score": avg_risk_score,
        "risk_breakdown": {
            "low_risk": low_risk,
            "medium_risk": medium_risk,
            "high_risk": high_risk,
            "critical_risk": critical_risk,
        },
        "confirmed_suspicious_cases": confirmed_suspicious,
        "risk_thresholds": {
            "low": "0–29",
            "medium": "30–59",
            "high": "60–79",
            "critical": "80–100",
        },
    }


@router.get("/claims", summary="List all claims with AI forensic risk assessments")
async def list_forensic_claims(
    risk_category: Optional[str] = Query(None, description="Low, Medium, High, Critical"),
    min_score: Optional[float] = Query(None, ge=0, le=100),
    max_score: Optional[float] = Query(None, ge=0, le=100),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = db.query(FraudAssessment).order_by(
        desc(FraudAssessment.risk_score)
    )

    if risk_category:
        query = query.filter(FraudAssessment.risk_category == risk_category.capitalize())
    if min_score is not None:
        query = query.filter(FraudAssessment.risk_score >= min_score)
    if max_score is not None:
        query = query.filter(FraudAssessment.risk_score <= max_score)

    assessments = query.offset(skip).limit(limit).all()

    results = []
    for a in assessments:
        claim = a.claim
        if not claim:
            continue
        investigation = db.query(Investigation).filter(Investigation.claim_id == claim.id).first()
        results.append({
            "assessment_id": a.id,
            "claim_id": claim.claim_id,
            "policy_number": claim.policy.policy_number if claim.policy else None,
            "policy_type": claim.policy.policy_type if claim.policy else None,
            "claim_type": claim.claim_type,
            "amount": claim.amount,
            "customer_name": claim.customer.name if claim.customer else None,
            "claim_status": claim.status,
            "risk_score": a.risk_score,
            "risk_category": a.risk_category,
            "risk_color": _risk_color(a.risk_category),
            "analysis_date": a.assessed_at.isoformat() if a.assessed_at else None,
            "model_version": a.model_version,
            "indicator_count": len(a.indicators or []),
            "top_indicators": (a.indicators or [])[:3],
            "has_investigation": investigation is not None,
            "investigation_status": investigation.status if investigation else None,
        })
    return results


@router.get("/claims/{claim_id}", summary="Get detailed AI forensic analysis for a specific claim")
async def get_forensic_claim_detail(
    claim_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    claim = db.query(Claim).filter(
        (Claim.claim_id == claim_id) | (Claim.id == claim_id)
    ).first()
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found.")

    assessment = claim.assessment
    if not assessment:
        return {
            "claim_id": claim.claim_id,
            "status": "pending",
            "message": "This claim has not yet been evaluated by the AI fraud detection engine. Submit the claim for assessment or trigger a manual re-score.",
            "assessment": None,
        }

    investigation = db.query(Investigation).filter(Investigation.claim_id == claim.id).first()

    # OCR documents for this claim
    ocr_docs = db.query(OCRDocument).filter(OCRDocument.claim_id == claim.id).all()
    ocr_summary = [
        {
            "id": doc.id,
            "filename": doc.filename,
            "document_type": doc.document_type,
            "confidence_score": doc.confidence_score,
            "has_date_mismatch": doc.has_date_mismatch,
            "flags": doc.flags or [],
            "missing_fields": doc.missing_fields or [],
            "processing_status": doc.processing_status,
        }
        for doc in ocr_docs
    ]

    # Build detailed forensic findings
    indicators = assessment.indicators or []
    forensic_findings = []
    for ind in indicators:
        severity_map = {
            "CRITICAL": {"level": "Critical", "color": "#EF4444", "bg": "#FEF2F2"},
            "HIGH": {"level": "High", "color": "#F97316", "bg": "#FFF7ED"},
            "MEDIUM": {"level": "Medium", "color": "#F59E0B", "bg": "#FFFBEB"},
            "LOW": {"level": "Low", "color": "#10B981", "bg": "#F0FDF4"},
        }
        sev = severity_map.get(ind.get("severity", "LOW"), severity_map["LOW"])
        forensic_findings.append({
            "code": ind.get("code"),
            "description": ind.get("detail"),
            "severity": sev["level"],
            "severity_color": sev["color"],
            "severity_bg": sev["bg"],
            "weight": ind.get("weight", 0),
        })

    return {
        "claim_id": claim.claim_id,
        "status": "assessed",
        "claim_info": {
            "claim_type": claim.claim_type,
            "amount": claim.amount,
            "incident_date": claim.incident_date.isoformat() if claim.incident_date else None,
            "submission_date": claim.submission_date.isoformat() if claim.submission_date else None,
            "claim_status": claim.status,
        },
        "policy_info": {
            "policy_number": claim.policy.policy_number if claim.policy else None,
            "policy_type": claim.policy.policy_type if claim.policy else None,
            "effective_date": claim.policy.effective_date.isoformat() if claim.policy else None,
        },
        "customer_info": {
            "customer_id": claim.customer.customer_id if claim.customer else None,
            "name": claim.customer.name if claim.customer else None,
            "national_id": claim.customer.national_id if claim.customer else None,
        },
        "assessment": {
            "risk_score": assessment.risk_score,
            "risk_category": assessment.risk_category,
            "risk_color": _risk_color(assessment.risk_category),
            "explanation": assessment.explanation,
            "model_version": assessment.model_version,
            "assessed_at": assessment.assessed_at.isoformat() if assessment.assessed_at else None,
            "indicator_count": len(indicators),
            "total_risk_weight": sum(ind.get("weight", 0) for ind in indicators),
        },
        "forensic_findings": forensic_findings,
        "ocr_evidence": ocr_summary,
        "investigation": {
            "id": investigation.id,
            "status": investigation.status,
            "notes": investigation.notes,
            "opened_at": investigation.opened_at.isoformat() if investigation.opened_at else None,
        } if investigation else None,
        "disclaimer": (
            "⚠ AI Forensic Disclaimer: These findings are decision-support indicators generated by the NEXA AI Engine. "
            "They do not independently establish fraud and must not replace human investigation and evidence review. "
            "All conclusions require validation by qualified Claims Officers and Fraud Investigators."
        ),
    }


@router.get("/document-analysis", summary="Cross-document forensic analysis: duplicates, inconsistencies, suspicious flags")
async def get_document_analysis(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Returns document-level forensic findings. All findings are for human
    review — they are not proof of fraud."""
    from ..services.document_forensics import generate_forensic_analysis

    return generate_forensic_analysis(db)


@router.get("/high-risk-queue", summary="Get priority queue of high and critical risk claims")
async def get_high_risk_forensic_queue(
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
        if not claim:
            continue
        investigation = db.query(Investigation).filter(Investigation.claim_id == claim.id).first()
        top_indicator = None
        if a.indicators:
            top_indicator = a.indicators[0].get("detail", "Multiple risk factors detected")

        results.append({
            "claim_id": claim.claim_id,
            "policy_number": claim.policy.policy_number if claim.policy else None,
            "customer_name": claim.customer.name if claim.customer else None,
            "claim_type": claim.claim_type,
            "amount": claim.amount,
            "claim_status": claim.status,
            "risk_score": a.risk_score,
            "risk_category": a.risk_category,
            "risk_color": _risk_color(a.risk_category),
            "top_indicator": top_indicator,
            "has_investigation": investigation is not None,
            "assessed_at": a.assessed_at.isoformat() if a.assessed_at else None,
        })

    return results


@router.get("/document/{doc_id}/report", summary="Per-document forensic report (Phase 4 format)")
async def get_document_forensic_report(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Returns a forensic report per document: suspicious fields, extracted
    vs expected values, explanations, confidence levels, recommended actions.

    Distinguishes actual evidence, technical anomalies, possible fraud
    indicators and OCR errors. Never confirms fraud by itself.
    """
    from ..services.document_forensics import generate_forensic_report_for_document

    return generate_forensic_report_for_document(db, doc_id)


@router.get("/documents/reuse", summary="Cross-claim document reuse detection (text-similarity)")
async def get_reused_documents(
    threshold: float = Query(0.9, ge=0.5, le=1.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Detects documents reused across claims via high text similarity."""
    from ..services.document_forensics import detect_reused_documents

    groups = detect_reused_documents(db, threshold=threshold)
    return {
        "threshold": threshold,
        "reused_groups": groups,
        "total_groups": len(groups),
        "honesty_note": "High text similarity is a technical indicator of document reuse; fraud linkage requires human review.",
    }
