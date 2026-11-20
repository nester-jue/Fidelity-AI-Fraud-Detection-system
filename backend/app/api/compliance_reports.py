"""
Compliance & Regulatory Monitoring Reports API

Generates regulatory compliance exceptions and fraud compliance review
reports from live system data. Compliance-generated reports are immutable
downloads and are recorded in the compliance_reports audit trail.
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from ..services.db import get_db
from ..models.sqlalchemy_models import (
    ComplianceReport, Claim, FraudAssessment, Investigation, User, RoleEnum, OCRDocument
)
from ..dependencies import get_current_active_user, require_roles, log_audit_trail

router = APIRouter(prefix="/compliance-reports", tags=["Compliance Reports"])


def _compliance_summary(db: Session) -> Dict[str, Any]:
    flagged = db.query(Claim).filter(Claim.status == "flagged").count()
    high_risk = db.query(FraudAssessment).filter(FraudAssessment.risk_category == "High").count()
    critical_risk = db.query(FraudAssessment).filter(FraudAssessment.risk_category == "Critical").count()
    missing_docs = db.query(Claim).filter(~Claim.documents.any()).count()
    return {
        "flagged_claims": flagged,
        "high_risk_claims": high_risk,
        "critical_risk_claims": critical_risk,
        "claims_missing_documentation": missing_docs,
    }


@router.get("/", summary="List generated compliance and regulatory reports")
async def list_compliance_reports(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    reports = db.query(ComplianceReport).order_by(desc(ComplianceReport.generated_at)).limit(limit).all()
    return [
        {
            "id": r.id,
            "report_type": r.report_type,
            "title": r.title,
            "period_start": r.period_start.isoformat() if r.period_start else None,
            "period_end": r.period_end.isoformat() if r.period_end else None,
            "generated_by": r.generated_by.full_name if r.generated_by else "Unknown",
            "generated_at": r.generated_at.isoformat() if r.generated_at else None,
        }
        for r in reports
    ]


@router.post("/", summary="Generate a new compliance/regulatory monitoring report (Compliance/Admin)")
async def generate_compliance_report(
    report_type: str = "FRAUD_COMPLIANCE_REVIEW",
    title: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([RoleEnum.COMPLIANCE_OFFICER, RoleEnum.SYSTEM_ADMIN])),
):
    period_start = datetime.now(timezone.utc) - timedelta(days=30)
    report = ComplianceReport(
        generated_by_id=current_user.id,
        report_type=report_type,
        title=title or f"{report_type} — Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
        details=_compliance_summary(db),
        period_start=period_start,
        period_end=datetime.now(timezone.utc),
        generated_at=datetime.now(timezone.utc),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    log_audit_trail(db, current_user, action="COMPLIANCE_REPORT_GENERATED", target=f"ComplianceReport:{report.id}")
    return {
        "message": "Compliance report generated and recorded.",
        "id": report.id,
        "report_type": report.report_type,
        "title": report.title,
        "details": report.details,
        "generated_at": report.generated_at.isoformat(),
    }


@router.get("/exceptions", summary="Compliance exceptions: claims under review and high-risk claims")
async def list_compliance_exceptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([RoleEnum.COMPLIANCE_OFFICER, RoleEnum.SYSTEM_ADMIN])),
):
    high_risk_claims = (
        db.query(Claim).join(FraudAssessment).filter(
            FraudAssessment.risk_category.in_(["High", "Critical"])
        ).order_by(desc(FraudAssessment.risk_score)).all()
    )
    exceptions = []
    for c in high_risk_claims:
        inv = db.query(Investigation).filter(Investigation.claim_id == c.id).first()
        exceptions.append({
            "claim_id": c.claim_id,
            "customer_name": c.customer.name if c.customer else "Unknown",
            "risk_score": c.assessment.risk_score if c.assessment else None,
            "risk_category": c.assessment.risk_category if c.assessment else None,
            "claim_status": c.status,
            "investigation_status": inv.status if inv else "none",
            "exception_type": "FRAUD_RISK_EXCEPTION" if not inv else "INVESTIGATION_PENDING",
        })
    return {"exceptions": exceptions, "total": len(exceptions), "summary": _compliance_summary(db)}


@router.get("/{report_id}", summary="Get details of a generated compliance report")
async def get_compliance_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    report = db.query(ComplianceReport).filter(ComplianceReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Compliance report not found.")
    return {
        "id": report.id,
        "report_type": report.report_type,
        "title": report.title,
        "details": report.details,
        "period_start": report.period_start.isoformat() if report.period_start else None,
        "period_end": report.period_end.isoformat() if report.period_end else None,
        "generated_by": report.generated_by.full_name if report.generated_by else "Unknown",
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
    }
