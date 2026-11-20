"""
Management Reports API

Generates downloadable executive management summaries: fraud trends,
financial exposure, performance metrics, and departmental performance.
All reports are recorded with the generating user for auditability.
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from ..services.db import get_db
from ..models.sqlalchemy_models import (
    ManagementReport, Claim, FraudAssessment, Investigation, User, RoleEnum
)
from ..dependencies import get_current_active_user, require_roles, log_audit_trail

router = APIRouter(prefix="/management-reports", tags=["Management Reports"])


def _fraud_trends(db: Session, months: int = 12) -> List[Dict[str, Any]]:
    """Monthly claims received + exposure (DB-agnostic aggregation in Python)."""
    agg: Dict[str, List[Any]] = {}
    rows = db.query(Claim.submission_date, Claim.amount).order_by(Claim.submission_date).all()
    for dt, amount in rows:
        if dt is None:
            continue
        month = str(dt)[:7]  # YYYY-MM
        entry = agg.setdefault(month, [0, 0.0])
        entry[0] += 1
        entry[1] += float(amount or 0)
    return [
        {
            "period": m,
            "claims_received": c,
            "exposure_amount": round(a, 2),
        }
        for m, (c, a) in sorted(agg.items())[-months:]
    ]


def _performance_snapshot(db: Session) -> Dict[str, Any]:
    total_claims = db.query(Claim).count()
    total_assessed = db.query(FraudAssessment).count()
    pending = db.query(Claim).filter(Claim.status.in_(["submitted", "in_review", "pending_documents"])).count()
    flagged = db.query(Claim).filter(Claim.status == "flagged").count()
    processed = db.query(Claim).filter(Claim.status.in_(["approved", "rejected", "cleared"])).count()
    confirmed_fraud = db.query(Investigation).filter(Investigation.status == "confirmed_fraud").count()
    total_exposure = db.query(func.sum(Claim.amount)).scalar() or 0.0
    return {
        "claims_received": total_claims,
        "claims_processed": processed,
        "claims_pending": pending,
        "claims_flagged": flagged,
        "confirmed_fraud_cases": confirmed_fraud,
        "ai_coverage_rate": round((total_assessed / max(total_claims, 1)) * 100, 1),
        "fraud_detection_rate": round((flagged / max(total_assessed, 1)) * 100, 1),
        "total_financial_exposure": round(float(total_exposure), 2),
    }


@router.get("/", summary="List generated executive management reports")
async def list_management_reports(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    reports = db.query(ManagementReport).order_by(desc(ManagementReport.generated_at)).limit(limit).all()
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


@router.post("/", summary="Generate a downloadable executive management report (Management/Admin)")
async def generate_management_report(
    report_type: Optional[str] = "EXECUTIVE_KPI_SNAPSHOT",
    period_months: int = Query(12, ge=1, le=36),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([RoleEnum.MANAGEMENT, RoleEnum.SYSTEM_ADMIN])),
):
    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(days=period_months * 30)
    trends = _fraud_trends(db, period_months)
    summary = _performance_snapshot(db)
    summary["fraud_trends"] = trends

    report = ManagementReport(
        generated_by_id=current_user.id,
        report_type=report_type,
        title=f"{report_type} — {period_end.strftime('%Y-%m')}",
        summary=summary,
        period_start=period_start,
        period_end=period_end,
        generated_at=period_end,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    log_audit_trail(db, current_user, action="MANAGEMENT_REPORT_GENERATED", target=f"ManagementReport:{report.id}")
    return {
        "message": "Management report generated and downloadable.",
        "id": report.id,
        "report_type": report.report_type,
        "title": report.title,
        "summary": summary,
        "generated_at": report.generated_at.isoformat(),
    }


@router.get("/{report_id}", summary="Get details of a management report")
async def get_management_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([RoleEnum.MANAGEMENT, RoleEnum.SYSTEM_ADMIN])),
):
    report = db.query(ManagementReport).filter(ManagementReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Management report not found.")
    return {
        "id": report.id,
        "report_type": report.report_type,
        "title": report.title,
        "summary": report.summary,
        "period_start": report.period_start.isoformat() if report.period_start else None,
        "period_end": report.period_end.isoformat() if report.period_end else None,
        "generated_by": report.generated_by.full_name if report.generated_by else "Unknown",
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
    }
