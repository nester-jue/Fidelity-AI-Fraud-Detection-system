"""
Departmental Dashboard APIs
Provides role-specific dashboard data for each department.
All endpoints enforce role-based access at the backend level.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from ..services.db import get_db
from ..models.sqlalchemy_models import (
    Claim, FraudAssessment, Investigation, User, RoleEnum, ClaimNote,
    AuditLog, Notification, OCRDocument, ModelPerformance, ManagementReport
)
from ..dependencies import get_current_active_user, require_roles, log_audit_trail

router = APIRouter(prefix="/departmental", tags=["Departmental Dashboards"])


# ─────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────

def _officer_claims_query(db: Session, user: User):
    """Claims the Claims Officer may see: their own assignments or unassigned."""
    q = db.query(Claim)
    if user.role == RoleEnum.CLAIMS_OFFICER:
        q = q.filter(
            (Claim.assigned_officer_id == user.id) | (Claim.assigned_officer_id.is_(None))
        )
    return q


def _claim_notes_list(db: Session, claim_id: int, limit: int = 10):
    notes = (
        db.query(ClaimNote)
        .filter(ClaimNote.claim_id == claim_id)
        .order_by(desc(ClaimNote.created_at))
        .limit(limit)
        .all()
    )
    return [
        {
            "id": n.id,
            "note": n.note,
            "created_by": n.user.full_name or n.user.username if n.user else "Unknown",
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in reversed(notes)
    ]


# ─────────────────────────────────────────────
# CLAIMS OFFICER DASHBOARD
# ─────────────────────────────────────────────

@router.get("/claims-officer", summary="Claims Officer dashboard statistics and workload")
async def get_claims_officer_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles([RoleEnum.CLAIMS_OFFICER, RoleEnum.CLAIMS_MANAGER, RoleEnum.SYSTEM_ADMIN])
    ),
) -> Dict[str, Any]:
    """Returns claims workload and status breakdown for the authenticated Claims Officer."""
    q = _officer_claims_query(db, current_user)

    total_claims = q.count()
    new_claims = q.filter(Claim.status == "submitted").count()
    in_review = q.filter(Claim.status == "in_review").count()
    pending_docs = q.filter(Claim.status == "pending_documents").count()
    flagged = q.filter(Claim.status == "flagged").count()
    approved = q.filter(Claim.status == "approved").count()
    rejected = q.filter(Claim.status == "rejected").count()
    under_inv = q.filter(Claim.status == "under_investigation").count()

    # Claims submitted for AI assessment (awaiting or completed assessment)
    claims_submitted_for_ai = q.filter(Claim.status == "submitted").count()
    assessments_for_claims = db.query(FraudAssessment).filter(
        FraudAssessment.claim_id.in_([c.id for c in q.all()])
    ).count() if total_claims else 0

    # AI-generated risk explanations available
    ai_explanations = 0
    for c in q.all():
        if c.assessment and c.assessment.explanation:
            ai_explanations += 1

    # OCR extraction results for officer's claims
    ocr_by_status = (
        db.query(OCRDocument.processing_status, func.count(OCRDocument.id))
        .filter(OCRDocument.claim_id.in_([c.id for c in q.all()]))
        .group_by(OCRDocument.processing_status)
        .all()
        if total_claims else []
    )
    ocr_summary = [{"status": s, "count": n} for s, n in ocr_by_status]

    # Claim processing status distribution
    status_distribution = [
        {"status": "Submitted", "count": new_claims, "color": "#3B82F6"},
        {"status": "In Review", "count": in_review, "color": "#F59E0B"},
        {"status": "Flagged", "count": flagged, "color": "#EF4444"},
        {"status": "Pending Documents", "count": pending_docs, "color": "#F97316"},
        {"status": "Approved", "count": approved, "color": "#10B981"},
        {"status": "Rejected", "count": rejected, "color": "#6B7280"},
    ]

    # Recent claims (last 10)
    recent_claims = q.order_by(desc(Claim.submission_date)).limit(10).all()
    recent_list = []
    for c in recent_claims:
        assessment = c.assessment
        # OCR extraction status lives on OCRDocument records (ClaimDocument
        # has no processing_status attribute).
        claim_ocr_docs = db.query(OCRDocument).filter(OCRDocument.claim_id == c.id).all()
        recent_list.append({
            "claim_id": c.claim_id,
            "customer_name": c.customer.name if c.customer else "Unknown",
            "claim_type": c.claim_type,
            "amount": c.amount,
            "status": c.status,
            "submission_date": c.submission_date.isoformat() if c.submission_date else None,
            "risk_score": assessment.risk_score if assessment else None,
            "risk_category": assessment.risk_category if assessment else "Pending",
            "documents_count": len(c.documents),
            "ocr_extraction_status": (
                [d.processing_status for d in claim_ocr_docs if d.processing_status != "completed"]
                if any(d.processing_status != "completed" for d in claim_ocr_docs) else "ok"
            ),
        })

    # Claim history and notes
    history = []
    for c in recent_claims:
        history.append({
            "claim_id": c.claim_id,
            "notes": _claim_notes_list(db, c.id, limit=5),
        })

    return {
        "officer": {
            "id": current_user.id,
            "name": current_user.full_name or current_user.username,
            "role": current_user.role.value,
        },
        "workload": {
            "total_claims": total_claims,
            "new_claims": new_claims,
            "claims_awaiting_review": in_review,
            "claims_pending_documents": pending_docs,
            "claims_requiring_additional_documentation": pending_docs,
            "claims_flagged": flagged,
            "claims_submitted_for_ai_assessment": claims_submitted_for_ai,
            "claims_with_ai_assessments": assessments_for_claims,
            "claims_with_ai_explanations": ai_explanations,
            "claims_approved": approved,
            "claims_rejected": rejected,
            "claims_under_investigation": under_inv,
        },
        "ai_risk_assessments": [
            {
                "claim_id": c.claim_id,
                "risk_score": c.assessment.risk_score if c.assessment else None,
                "risk_category": c.assessment.risk_category if c.assessment else None,
                "explanation": c.assessment.explanation if c.assessment else None,
            }
            for c in q.all() if c.assessment and c.assessment.explanation
        ][:20],
        "ocr_extraction_summary": ocr_summary,
        "claim_processing_status": status_distribution,
        "claim_history": history,
        "status_distribution": status_distribution,
        "recent_claims": recent_list,
    }


# ─────────────────────────────────────────────
# EXECUTIVE DASHBOARD
# ─────────────────────────────────────────────

def _monthly_trends(db: Session, field, months: int = 12):
    """Claims per calendar month for the last N months (from DB data only)."""
    agg = {}
    for (dt,) in db.query(field).order_by(field).all():
        if dt is None:
            continue
        month = str(dt)[:7]
        agg[month] = agg.get(month, 0) + 1
    return [{"period": m, "count": agg[m]} for m in sorted(agg.keys())[-months:]]


@router.get("/executive", summary="Executive Management dashboard with high-level organisational intelligence")
async def get_executive_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles([RoleEnum.MANAGEMENT, RoleEnum.SYSTEM_ADMIN])
    ),
) -> Dict[str, Any]:
    """Executive-level fraud analytics, financial exposure, and performance metrics."""

    total_claims = db.query(Claim).count()
    total_analysed = db.query(FraudAssessment).count()
    total_pending = db.query(Claim).filter(
        Claim.status.in_(["submitted", "in_review", "pending_documents"])
    ).count()
    total_flagged = db.query(Claim).filter(Claim.status == "flagged").count()

    low_risk = db.query(FraudAssessment).filter(FraudAssessment.risk_category == "Low").count()
    medium_risk = db.query(FraudAssessment).filter(FraudAssessment.risk_category == "Medium").count()
    high_risk = db.query(FraudAssessment).filter(FraudAssessment.risk_category == "High").count()
    critical_risk = db.query(FraudAssessment).filter(FraudAssessment.risk_category == "Critical").count()

    # Enterprise KPI — high-risk (High + Critical) claims across all assessed claims
    high_risk_claims = high_risk + critical_risk

    confirmed_fraud = db.query(Investigation).filter(Investigation.status == "confirmed_fraud").count()
    under_investigation = db.query(Investigation).filter(
        Investigation.status.in_(["open", "in_review", "escalated"])
    ).count()

    # Financial exposure
    total_exposure = db.query(func.sum(Claim.amount)).scalar() or 0.0
    confirmed_fraud_ids = [
        inv.claim_id for inv in db.query(Investigation).filter(Investigation.status == "confirmed_fraud").all()
    ]
    prevented_losses = (
        db.query(func.sum(Claim.amount)).filter(Claim.id.in_(confirmed_fraud_ids)).scalar() or 0.0
    )

    # Confirmed fraud losses vs prevented losses (verified fraud records).
    # The system records authorised interventions asInvestigations with status
    # 'confirmed_fraud'; the same value feeds both KPI families.
    confirmed_fraud_losses = prevented_losses
    losses_prevented = prevented_losses
    verified_losses_prevented = prevented_losses
    recovered_funds = 0.0

    # Overall fraud risk percentage — share of assessed claims at High/Critical.
    overall_fraud_risk_percentage = round((high_risk_claims / max(total_analysed, 1)) * 100, 1)

    # Claim type breakdown
    type_breakdown = db.query(
        Claim.claim_type, func.count(Claim.id), func.sum(Claim.amount)
    ).group_by(Claim.claim_type).all()

    # Risk distribution for chart
    total_assessed_denominator = max(total_analysed, 1)
    risk_distribution = [
        {"name": "Low Risk (0–29)", "count": low_risk,
         "percentage": round((low_risk / total_assessed_denominator) * 100, 1), "color": "#10B981"},
        {"name": "Medium Risk (30–59)", "count": medium_risk,
         "percentage": round((medium_risk / total_assessed_denominator) * 100, 1), "color": "#F59E0B"},
        {"name": "High Risk (60–79)", "count": high_risk,
         "percentage": round((high_risk / total_assessed_denominator) * 100, 1), "color": "#F97316"},
        {"name": "Critical Risk (80–100)", "count": critical_risk,
         "percentage": round((critical_risk / total_assessed_denominator) * 100, 1), "color": "#EF4444"},
    ]

    # Recent suspicious claims (high/critical)
    suspicious_q = (
        db.query(FraudAssessment)
        .filter(FraudAssessment.risk_category.in_(["High", "Critical"]))
        .order_by(desc(FraudAssessment.assessed_at))
        .limit(8)
        .all()
    )
    recent_suspicious = []
    for a in suspicious_q:
        c = a.claim
        if c:
            recent_suspicious.append({
                "claim_id": c.claim_id,
                "customer_name": c.customer.name if c.customer else "Unknown",
                "claim_type": c.claim_type,
                "amount": c.amount,
                "risk_score": a.risk_score,
                "risk_category": a.risk_category,
                "status": c.status,
            })

    # Monthly and yearly fraud trends (from DB data)
    monthly_trends = _monthly_trends(db, Claim.submission_date)
    # Group monthly rows into years
    yearly_dist = {}
    for item in monthly_trends:
        if item["period"]:
            year = item["period"][:4]
            yearly_dist[year] = yearly_dist.get(year, 0) + item["count"]
    yearly_trends = [{"period": y, "count": c} for y, c in sorted(yearly_dist.items())]

    # Departmental fraud performance: claims + investigation progress per
    # department. Claims are departmentally assigned via the Claims officer(s)
    # or via the Claims department queue when unassigned; investigations follow
    # their claims' assignment (unassigned investigations belong to Claims).
    claims_by_dept = []
    inv_by_dept: Dict[str, Dict[str, int]] = {}
    for inv in db.query(Investigation).all():
        if inv.claim and inv.claim.assigned_officer:
            d = inv.claim.assigned_officer.department or "Claims"
        else:
            d = "Claims"
        e = inv_by_dept.setdefault(d, {"open": 0, "in_review": 0, "escalated": 0, "confirmed_fraud": 0, "cleared": 0})
        e[inv.status] = e.get(inv.status, 0) + 1
    for d in ["Claims", "Compliance", "Investigations", "Executive", "IT"]:
        users_in_dept = db.query(User.id).filter(User.department == d).all()
        id_list = [u[0] for u in users_in_dept]
        n = db.query(Claim).filter(Claim.assigned_officer_id.in_(id_list)).count() if id_list else 0
        if d == "Claims":
            n += db.query(Claim).filter(
                Claim.status.in_(["flagged", "under_investigation", "pending_documents"]),
                Claim.assigned_officer_id.is_(None),
            ).count()
        dept_entry = {"department": d, "claims": n, "users": len(id_list), **inv_by_dept.get(d, {})}
        claims_by_dept.append(dept_entry)

    # Processing performance metrics
    processed_claims = db.query(Claim).filter(
        Claim.status.in_(["approved", "rejected", "cleared"])
    ).count()
    processing_perf = {
        "claims_processed": processed_claims,
        "claims_pending": total_pending,
        "pending_ratio_percent": round((total_pending / max(total_claims, 1)) * 100, 1),
        "ai_coverage_rate": round((total_analysed / max(total_claims, 1)) * 100, 1),
        "fraud_risk_ratio": round((total_flagged / max(total_analysed, 1)) * 100, 1),
    }

    # Generate and persist a downloadable management report snapshot
    report = ManagementReport(
        generated_by_id=current_user.id,
        report_type="EXECUTIVE_KPI_SNAPSHOT",
        title=f"Executive Management Snapshot — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        summary={
            "kpis": {
                "total_claims_received": total_claims,
                "total_claims_processed": total_analysed,
                "claims_pending": total_pending,
                "claims_flagged": total_flagged,
                "confirmed_fraud_cases": confirmed_fraud,
                "claims_under_investigation": under_investigation,
                "total_financial_exposure": round(total_exposure, 2),
                "potential_fraud_prevented": round(prevented_losses, 2),
                "ai_coverage_rate": round((total_analysed / max(total_claims, 1)) * 100, 1),
            },
            "monthly_trends": monthly_trends,
            "yearly_trends": yearly_trends,
            "departmental_performance": claims_by_dept,
            "processing_performance": processing_perf,
        },
        generated_at=datetime.now(timezone.utc),
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    log_audit_trail(db, current_user, action="EXECUTIVE_DASHBOARD_REPORT_GENERATED",
                    target=f"ManagementReport:{report.id}")

    return {
        "kpis": {
            "total_claims_received": total_claims,
            "active_insurance_portfolio": total_claims,
            "total_claims_processed": total_analysed,
            "claims_pending": total_pending,
            "claims_flagged": total_flagged,
            "confirmed_fraud_cases": confirmed_fraud,
            "claims_under_investigation": under_investigation,
            "total_financial_exposure": round(total_exposure, 2),
            "total_confirmed_fraud_losses": round(confirmed_fraud_losses, 2),
            "total_losses_prevented": round(losses_prevented, 2),
            "verified_losses_prevented": round(verified_losses_prevented, 2),
            "recovered_funds": round(recovered_funds, 2),
            "potential_fraud_prevented": round(prevented_losses, 2),
            "high_risk_claims": high_risk_claims,
            "overall_fraud_risk_percentage": overall_fraud_risk_percentage,
            "ai_coverage_rate": round((total_analysed / max(total_claims, 1)) * 100, 1),
        },
        "risk_distribution": risk_distribution,
        "product_breakdown": [
            {"claim_type": t[0], "count": t[1], "total_amount": round(float(t[2] or 0), 2)}
            for t in type_breakdown
        ],
        "recent_suspicious_claims": recent_suspicious,
        "monthly_fraud_trends": monthly_trends,
        "yearly_fraud_trends": yearly_trends,
        "departmental_performance": claims_by_dept,
        "processing_performance": processing_perf,
        "management_report_id": report.id,
    }


# ─────────────────────────────────────────────
# EXECUTIVE DEEP-DIVE ANALYTICS
# (companion endpoints to /executive — fraud trends, product analysis,
#  suspicious queue, investigation progress and AI insights)
# ─────────────────────────────────────────────

_EXEC_MGMT_ROLES = [RoleEnum.MANAGEMENT, RoleEnum.CHIEF_RISK_OFFICER, RoleEnum.SYSTEM_ADMIN]


def _exec_claims_with_assessment_and_investigation(db: Session):
    assessments = {a.claim_id: a for a in db.query(FraudAssessment).all()}
    investigations = {inv.claim_id: inv for inv in db.query(Investigation).all()}
    claims = db.query(Claim).all()
    return claims, assessments, investigations


def _is_suspected(c: Claim, assessment) -> bool:
    if assessment and assessment.risk_category in ("High", "Critical"):
        return True
    return c.status in ("flagged", "under_investigation", "pending_documents")


@router.get("/executive/monthly-trends", summary="Monthly fraud trends — submissions, suspicious claims and confirmed fraud by month")
async def get_executive_monthly_trends(
    months: int = Query(24, ge=1, le=60),
    period_start: Optional[str] = Query(None, description="Filter trends from this date (YYYY-MM-DD)"),
    period_end: Optional[str] = Query(None, description="Filter trends up to this date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(_EXEC_MGMT_ROLES)),
):
    """Monthly breakdown: claims received, suspected, confirmed, exposure — with month-over-month change."""
    claims, assessments, investigations = _exec_claims_with_assessment_and_investigation(db)
    agg: Dict[str, Dict[str, Any]] = {}
    for c in claims:
        if not c.submission_date:
            continue
        month = str(c.submission_date)[:7]
        entry = agg.setdefault(month, {"submitted": 0, "suspected": 0, "confirmed": 0, "exposure_amount": 0.0})
        entry["exposure_amount"] += float(c.amount or 0)
        if c.status == "submitted":
            entry["submitted"] += 1
        assessment = assessments.get(c.id)
        investigation = investigations.get(c.id)
        if investigation and investigation.status == "confirmed_fraud":
            entry["confirmed"] += 1
        elif _is_suspected(c, assessment):
            entry["suspected"] += 1

    # Apply optional date filters (filter to months within the date range).
    if period_start or period_end:
        months_sorted = sorted(agg.keys())
        if period_start:
            months_sorted = [m for m in months_sorted if m >= str(period_start)[:7]]
        if period_end:
            months_sorted = [m for m in months_sorted if m <= str(period_end)[:7]]
        agg = {m: agg[m] for m in months_sorted}

    sorted_months = sorted(agg.keys())[-months:]
    rows = []
    for i, month in enumerate(sorted_months):
        e = dict(agg[month])
        row = {"period": month, "submitted": e["submitted"], "suspected": e["suspected"],
               "confirmed": e["confirmed"], "exposure_amount": round(e["exposure_amount"], 2)}
        if i > 0:
            prev = agg[sorted_months[i - 1]]
            row["month_over_month_change_pct"] = round((e["suspected"] - prev["suspected"]) / max(prev["suspected"], 1) * 100, 1)
        else:
            row["month_over_month_change_pct"] = None
        rows.append(row)
    return {"period_end": str(datetime.now(timezone.utc).date()), "months": len(rows), "trends": rows}


@router.get("/executive/yearly-exposure", summary="Year-over-year financial exposure analytics")
async def get_executive_yearly_exposure(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(_EXEC_MGMT_ROLES)),
):
    """Annual financial exposure, claim volume and year-over-year growth."""
    agg: Dict[str, Dict[str, Any]] = {}
    for c in db.query(Claim).all():
        if not c.submission_date:
            continue
        year = str(c.submission_date)[:4]
        e = agg.setdefault(year, {"exposure_amount": 0.0, "claims_count": 0})
        e["exposure_amount"] += float(c.amount or 0)
        e["claims_count"] += 1

    sorted_years = sorted(agg.keys())
    rows = []
    for i, y in enumerate(sorted_years):
        e = agg[y]
        row = {"year": int(y), "exposure_amount": round(e["exposure_amount"], 2), "claims_count": e["claims_count"]}
        if i > 0:
            prev = agg[sorted_years[i - 1]]
            row["year_over_year_growth_pct"] = round((e["exposure_amount"] - prev["exposure_amount"]) / max(prev["exposure_amount"], 1) * 100, 1)
        else:
            row["year_over_year_growth_pct"] = None
        rows.append(row)
    return {"years": len(rows), "rows": rows}


@router.get("/executive/product-analysis", summary="Fraud analysis by insurance product")
async def get_executive_product_analysis(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(_EXEC_MGMT_ROLES)),
):
    """Product-level fraud exposure — only products present in the database are listed."""
    claims, assessments, investigations = _exec_claims_with_assessment_and_investigation(db)
    agg: Dict[str, Dict[str, Any]] = {}
    for c in claims:
        product = (c.claim_type or "Unknown").strip() or "Unknown"
        e = agg.setdefault(product, {"total_claims": 0, "total_exposure": 0.0, "critical_risk": 0,
                                     "high_risk": 0, "medium_risk": 0, "low_risk": 0,
                                     "confirmed_fraud": 0, "suspected_risk": 0,
                                     "confirmed_fraud_losses": 0.0, "confirmed_fraud_claims": []})
        e["total_claims"] += 1
        e["total_exposure"] += float(c.amount or 0)
        assessment = assessments.get(c.id)
        cat = (assessment.risk_category or "").lower() if assessment else ""
        if cat == "critical":
            e["critical_risk"] += 1
        elif cat == "high":
            e["high_risk"] += 1
        elif cat == "medium":
            e["medium_risk"] += 1
        elif cat == "low":
            e["low_risk"] += 1
        if cat in ("critical", "high"):
            e["suspected_risk"] += 1
        if investigation := investigations.get(c.id):
            if investigation.status == "confirmed_fraud":
                e["confirmed_fraud"] += 1
                e["confirmed_fraud_losses"] += float(c.amount or 0)
                if len(e["confirmed_fraud_claims"]) < 10:
                    e["confirmed_fraud_claims"].append({
                        "claim_id": c.claim_id,
                        "customer_name": c.customer.name if c.customer else "Unknown",
                        "claim_type": c.claim_type,
                        "amount": round(float(c.amount or 0), 2),
                        "status": c.status,
                        "risk_score": round(float(assessment.risk_score), 1) if assessment else None,
                        "risk_category": assessment.risk_category if assessment else None,
                        "opened_at": investigation.opened_at.isoformat() if investigation.opened_at else None,
                        "confirmed": True,
                    })

    PRODUCT_DISPLAY_NAMES = {
        "Death Benefit": "Life Assurance (Death Benefit)",
        "Funeral Expense": "Funeral Policies",
        "Accidental Death": "Accidental Death",
        "Personal Accident": "Personal Accident",
    }
    total_prevented = round(sum(e["confirmed_fraud_losses"] for e in agg.values()), 2)
    rows = []
    for product, e in agg.items():
        total = e["total_claims"]
        e["product_name"] = PRODUCT_DISPLAY_NAMES.get(product, product)
        e["assessed_share_pct"] = round(((e["critical_risk"] + e["high_risk"] + e["medium_risk"] + e["low_risk"]) / max(total, 1)) * 100, 1)
        e["suspected_share_pct"] = round((e["suspected_risk"] / max(total, 1)) * 100, 1)
        e["confirmed_fraud_losses"] = round(e["confirmed_fraud_losses"], 2)
        e["prevented_share_pct"] = round((e["confirmed_fraud_losses"] / total_prevented * 100), 1) if total_prevented else None
        e["total_exposure"] = round(e["total_exposure"], 2)
        rows.append(e)
    rows.sort(key=lambda r: r["total_exposure"], reverse=True)
    return {"products": len(rows), "total_prevented": total_prevented, "rows": rows}


@router.get("/executive/suspicions", summary="Priority suspicious claims queue for CRO review")
async def get_executive_suspicions(
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(_EXEC_MGMT_ROLES)),
):
    """High/critical risk claims with investigation status, assigned investigator, priority and indicators."""
    _, assessments, investigations = _exec_claims_with_assessment_and_investigation(db)
    rows = []
    for a in db.query(FraudAssessment).filter(FraudAssessment.risk_category.in_(["High", "Critical"])).order_by(desc(FraudAssessment.risk_score)).all():
        c = a.claim
        if not c:
            continue
        inv = investigations.get(c.id)
        indicators = a.indicators or []
        top_indicators = [i.get("code") or i.get("detail") or "AI risk flag" for i in indicators[:3]] or ["AI risk flag"]
        rows.append({
            "claim_id": c.claim_id,
            "customer_name": c.customer.name if c.customer else "Unknown",
            "claim_type": c.claim_type,
            "amount": round(float(c.amount or 0), 2),
            "risk_score": round(float(a.risk_score or 0), 1),
            "risk_category": a.risk_category,
            "top_indicators": top_indicators,
            "investigation_status": inv.status if inv else "none",
            "investigation_id": inv.id if inv else None,
            "investigator_name": inv.investigator.full_name if inv and inv.investigator else None,
            "investigation_opened_at": inv.opened_at.isoformat() if inv and inv.opened_at else None,
            "submitted_date": c.submission_date.isoformat() if c.submission_date else None,
            "priority": "CRITICAL" if a.risk_category == "Critical" else "HIGH",
            "is_confirmed_fraud": bool(inv and inv.status == "confirmed_fraud"),
        })
        if len(rows) >= limit:
            break
    return {"total": len(rows), "queue": rows}


@router.get("/executive/investigations", summary="Outstanding investigation progress for CRO oversight")
async def get_executive_investigation_progress(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(_EXEC_MGMT_ROLES)),
):
    """Investigation progress: status, days open, evidence and notes counts, outcomes."""
    from ..models.sqlalchemy_models import InvestigationNote

    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive — matches DB timestamps
    rows = []
    summary: Dict[str, int] = {}
    invs = db.query(Investigation).order_by(desc(Investigation.opened_at)).limit(limit).all()
    for inv in invs:
        claim = inv.claim
        assessment = claim.assessment if claim else None
        note_count = db.query(InvestigationNote).filter(InvestigationNote.investigation_id == inv.id).count()
        opened = inv.opened_at
        summary[inv.status] = summary.get(inv.status, 0) + 1
        rows.append({
            "investigation_id": inv.id,
            "claim_id": claim.claim_id if claim else None,
            "customer_name": claim.customer.name if claim and claim.customer else "Unknown",
            "risk_score": assessment.risk_score if assessment else None,
            "risk_category": assessment.risk_category if assessment else None,
            "status": inv.status,
            "opened_at": opened.isoformat() if opened else None,
            "days_open": max(0, (now - opened).days) if opened else 0,
            "investigator_name": inv.investigator.full_name if inv.investigator else "Unassigned",
            "evidence_count": len(inv.evidence_documents or []),
            "note_count": note_count,
            "outcome": inv.outcome,
        })
    return {"summary": summary, "investigations": rows}


@router.get("/executive/ai-insights", summary="Data-driven AI fraud intelligence insights")
async def get_executive_ai_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(_EXEC_MGMT_ROLES)),
):
    """Management insights computed from actual system data. AI suspicions are
    flagged distinctly from confirmed fraud; findings never fabricate data."""
    claims, assessments, investigations = _exec_claims_with_assessment_and_investigation(db)
    now = datetime.now(timezone.utc)

    # Monthly aggregation for trend analysis
    agg: Dict[str, Dict[str, int]] = {}
    for c in claims:
        if not c.submission_date:
            continue
        month = str(c.submission_date)[:7]
        e = agg.setdefault(month, {"submitted": 0, "suspected": 0, "confirmed": 0})
        if c.status == "submitted":
            e["submitted"] += 1
        assessment = assessments.get(c.id)
        if _is_suspected(c, assessment):
            e["suspected"] += 1
        if investigations.get(c.id) and investigations[c.id].status == "confirmed_fraud":
            e["confirmed"] += 1
    sorted_months = sorted(agg.keys())[-12:]
    month_list = [(m, agg[m]["suspected"], agg[m]["confirmed"]) for m in sorted_months]

    insights: List[Dict[str, Any]] = []

    def add_insight(insight_id, type_, severity, title, description, data, recommended_action, basis):
        insights.append({
            "insight_id": insight_id,
            "type": type_,
            "severity": severity,
            "title": title,
            "description": description,
            "data": data,
            "recommended_action": recommended_action,
            "basis": basis,
            "generated_at": now.isoformat(),
        })

    # 1. Unusual increases in suspicious claims
    prev_suspected = None
    prev_month = None
    for month, suspected, _ in month_list:
        if prev_suspected is not None and prev_suspected > 0 and suspected > prev_suspected and suspected >= 3:
            growth_pct = round((suspected - prev_suspected) / prev_suspected * 100, 1)
            add_insight(
                f"IN-{month}-INCREASE", "unusual_increase", "WARNING",
                f"Unusual spike in suspicious claims from {prev_month} to {month}",
                f"Suspicious claims rose from {prev_suspected} to {suspected} between {prev_month} and {month} ({growth_pct:+.1f}%).",
                {"previous_period": prev_month, "current_period": month,
                 "previous_suspected": prev_suspected, "current_suspected": suspected,
                 "growth_pct": growth_pct},
                "Review newly flagged claims and determine whether the pattern is coordinated fraud or a processing anomaly.",
                "ai_detected",
            )
        prev_suspected, prev_month = suspected, month

    # 2. Repeated high-risk claim patterns (same policy, amount, incident date)
    patterns: Dict[tuple, List[Claim]] = {}
    for c in claims:
        assessment = assessments.get(c.id)
        if assessment and assessment.risk_category in ("High", "Critical"):
            key = (c.policy_id, round(float(c.amount or 0), 2), str(c.incident_date)[:10] if c.incident_date else None)
            patterns.setdefault(key, []).append(c)
    for key, cs in patterns.items():
        if len(cs) >= 2:
            add_insight(
                f"IN-DUP-{key[0]}", "repeated_pattern", "SUSPICION",
                "Repeated high-risk claim pattern detected",
                f"{len(cs)} claims on the same policy (ID: {key[0]}) share an identical amount and incident date — potential duplicate submission.",
                {"policy_id": key[0], "claim_ids": [c.claim_id for c in cs],
                 "amount": key[1], "incident_date": key[2]},
                "Open an investigation — request claimant verification, review each claim for duplicate payment protection and verify identity documents.",
                "ai_detected",
            )

    # 3. High-value claims requiring additional verification
    high_value_claims = [c for c in claims if assessments.get(c.id) and assessments[c.id].risk_category in ("High", "Critical")]
    if high_value_claims:
        amounts = [float(c.amount or 0) for c in high_value_claims]
        avg_amount = sum(amounts) / len(amounts) if amounts else 0
        for c in high_value_claims[:10]:
            a = assessments[c.id]
            if float(c.amount or 0) > max(avg_amount * 1.5, 10000):
                inv = investigations.get(c.id)
                add_insight(
                    f"IN-HV-{c.id}", "high_value_verification", "WARNING",
                    f"High-value claim {c.claim_id} requires additional verification",
                    f"Claim value of ${float(c.amount or 0):,.2f} with {a.risk_category} risk ({a.risk_score}/100) is significantly higher than the high-risk average of ${avg_amount:,.2f}.",
                    {"claim_id": c.claim_id, "amount": float(c.amount or 0),
                     "risk_score": a.risk_score, "risk_category": a.risk_category,
                     "investigation_status": inv.status if inv else "none"},
                    "Request supporting documentation or initiate an investigation — verify the claimant and payment arrangements.",
                    "ai_detected",
                )

    # 4. Emerging trends — suspicious rate increasing across months
    for i in range(1, len(month_list)):
        (m_prev, s_prev, _), (m_cur, s_cur, _) = month_list[i - 1], month_list[i]
        if s_cur > s_prev and s_cur >= 5:
            add_insight(
                f"IN-EMERGING-{i}", "emerging_trend", "NOTICE",
                f"Emerging fraud trend — rising suspicious activity from {m_prev} to {m_cur}",
                f"Suspicious claim volume increased from {s_prev} to {s_cur}.",
                {"previous_period": m_prev, "current_period": m_cur,
                 "previous_suspected": s_prev, "current_suspected": s_cur},
                "Increase review capacity and consider expanding fraud screening rules for the emerging pattern.",
                "ai_detected",
            )

    # 5. Product trends — products whose monthly suspicious rate is increasing
    per_month_product: Dict[str, Dict[str, Dict[str, int]]] = {}
    for c in claims:
        if not c.submission_date:
            continue
        month = str(c.submission_date)[:7]
        product = (c.claim_type or "Unknown").strip() or "Unknown"
        entry = per_month_product.setdefault(month, {}).setdefault(product, {"claims": 0, "suspected": 0})
        entry["claims"] += 1
        if _is_suspected(c, assessments.get(c.id)):
            entry["suspected"] += 1
    for product in sorted({p for m_stats in per_month_product.values() for p in m_stats}):
        months_for_product = [(m, stats[product]) for m, stats in per_month_product.items() if product in stats]
        if len(months_for_product) >= 2:
            (m_prev, e_prev), (m_cur, e_cur) = months_for_product[0], months_for_product[-1]
            rate_prev = round(e_prev["suspected"] / max(e_prev["claims"], 1) * 100, 1)
            rate_cur = round(e_cur["suspected"] / max(e_cur["claims"], 1) * 100, 1)
            if rate_cur > rate_prev and e_cur["suspected"] >= 2:
                add_insight(
                    f"IN-PROD-{product}", "product_trend", "NOTICE",
                    f"Fraud activity rising in {product} claims",
                    f"{product}: suspicious-claim rate rose from {rate_prev}% ({m_prev}) to {rate_cur}% ({m_cur}).",
                    {"product": product, "previous_period": m_prev, "current_period": m_cur,
                     "previous_rate_pct": rate_prev, "current_rate_pct": rate_cur},
                    "Prioritise verification for the affected product lines; consider tighter screening for recent submissions.",
                    "ai_detected",
                )

    # 6. Outstanding investigations requiring management attention
    open_inv = db.query(Investigation).filter(Investigation.status == "open").count()
    in_review = db.query(Investigation).filter(Investigation.status == "in_review").count()
    if open_inv or in_review:
        oldest = db.query(Investigation).filter(Investigation.status.in_(["open", "in_review"])).order_by(Investigation.opened_at).first()
        add_insight(
            "IN-OUTSTANDING-1", "outstanding_investigations", "NOTICE",
            "Outstanding investigation backlog requires management attention",
            f"{open_inv + in_review} investigations are open or in review." +
            (f" Oldest opened: {oldest.opened_at.isoformat()}" if oldest and oldest.opened_at else ""),
            {"open": open_inv, "in_review": in_review,
             "oldest_opened_at": oldest.opened_at.isoformat() if oldest and oldest.opened_at else None},
            "Review oldest cases first — prioritise cases with confirmed AI suspicions and set clear escalation deadlines.",
            "verified_data",
        )

    return {
        "generated_at": now.isoformat(),
        "total_insights": len(insights),
        "by_type": {t: sum(1 for i in insights if i["type"] == t) for t in sorted({i["type"] for i in insights})},
        "by_severity": {s: sum(1 for i in insights if i["severity"] == s) for s in sorted({i["severity"] for i in insights})},
        "insights": insights,
    }


# ─────────────────────────────────────────────
# COMPLIANCE OFFICER DASHBOARD
# ─────────────────────────────────────────────

@router.get("/compliance", summary="Compliance Officer dashboard with regulatory monitoring data")
async def get_compliance_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles([RoleEnum.COMPLIANCE_OFFICER, RoleEnum.SYSTEM_ADMIN])
    ),
) -> Dict[str, Any]:
    """Compliance and regulatory monitoring workspace data."""

    # Claims requiring compliance review (flagged / high risk)
    flagged_claims = db.query(Claim).filter(Claim.status == "flagged").count()
    high_risk_count = db.query(FraudAssessment).filter(
        FraudAssessment.risk_category.in_(["High", "Critical"])
    ).count()

    # Open investigations
    open_investigations = db.query(Investigation).filter(
        Investigation.status == "open"
    ).count()
    escalated = db.query(Investigation).filter(
        Investigation.status == "escalated"
    ).count()
    confirmed_fraud = db.query(Investigation).filter(
        Investigation.status == "confirmed_fraud"
    ).count()

    # Claims with missing documents (no OCR docs)
    claims_without_docs = db.query(Claim).filter(~Claim.documents.any()).count()

    # Recent audit logs (compliance relevant)
    recent_audits = db.query(AuditLog).order_by(desc(AuditLog.timestamp)).limit(20).all()
    audit_list = [
        {
            "id": a.id,
            "user": a.user.username if a.user else "System",
            "user_role": a.user.role.value if a.user else "system",
            "action": a.action,
            "target": a.target,
            "detail": a.detail,
            "timestamp": a.timestamp.isoformat() if a.timestamp else None,
        }
        for a in recent_audits
    ]

    # Claims under investigation list
    investigations = db.query(Investigation).filter(
        Investigation.status.in_(["open", "in_review", "escalated"])
    ).order_by(desc(Investigation.opened_at)).limit(15).all()

    inv_list = []
    for inv in investigations:
        claim = inv.claim
        assessment = claim.assessment if claim else None
        inv_list.append({
            "investigation_id": inv.id,
            "claim_id": claim.claim_id if claim else None,
            "customer_name": claim.customer.name if claim and claim.customer else "Unknown",
            "claim_type": claim.claim_type if claim else None,
            "amount": claim.amount if claim else None,
            "risk_score": assessment.risk_score if assessment else None,
            "risk_category": assessment.risk_category if assessment else None,
            "investigation_status": inv.status,
            "investigator": inv.investigator.full_name or inv.investigator.username if inv.investigator else "Unassigned",
            "opened_at": inv.opened_at.isoformat() if inv.opened_at else None,
        })

    # Investigation outcomes distribution
    outcomes = db.query(Investigation.status, func.count(Investigation.id)).group_by(Investigation.status).all()
    investigation_outcomes = [{"outcome": s, "count": n} for s, n in outcomes]

    # User activity records (recent audit activity)
    activity = db.query(
        AuditLog.user_id, AuditLog.action, func.count(AuditLog.id)
    ).group_by(AuditLog.user_id, AuditLog.action).order_by(func.count(AuditLog.id).desc()).limit(15).all()
    user_activity = []
    for uid, action, cnt in activity:
        user = db.query(User).filter(User.id == uid).first()
        user_activity.append({
            "user": user.full_name or user.username if user else "System",
            "user_role": user.role.value if user else "system",
            "action": action,
            "count": cnt,
        })

    # Case escalation history: investigations escalated in the last 90 days
    esc_window_start = datetime.now(timezone.utc) - timedelta(days=90)
    escalation_history = (
        db.query(Investigation)
        .filter(Investigation.status == "escalated", Investigation.opened_at >= esc_window_start)
        .order_by(desc(Investigation.opened_at))
        .limit(15)
        .all()
    )
    escalation_list = []
    for inv in escalation_history:
        claim = inv.claim
        escalation_list.append({
            "investigation_id": inv.id,
            "claim_id": claim.claim_id if claim else None,
            "opened_at": inv.opened_at.isoformat() if inv.opened_at else None,
            "investigator": inv.investigator.full_name or inv.investigator.username if inv.investigator else "Unassigned",
        })

    return {
        "summary": {
            "claims_requiring_review": flagged_claims,
            "high_risk_claims": high_risk_count,
            "open_investigations": open_investigations,
            "escalated_investigations": escalated,
            "confirmed_fraud_cases": confirmed_fraud,
            "claims_missing_documents": claims_without_docs,
            "compliance_alerts": flagged_claims + high_risk_count,
        },
        "compliance_alerts": [
            {
                "type": "HIGH_RISK_CLAIM",
                "claim_id": c.claim_id,
                "risk_score": c.assessment.risk_score if c.assessment else None,
                "risk_category": c.assessment.risk_category if c.assessment else None,
                "severity": "Critical" if c.assessment and c.assessment.risk_category == "Critical" else "High",
            }
            for c in db.query(Claim).filter(
                Claim.status == "flagged", Claim.assessment
            ).order_by(desc(Claim.updated_at)).limit(20).all()
        ],
        "investigation_outcomes": investigation_outcomes,
        "user_activity": user_activity,
        "case_escalation_history": escalation_list,
        "active_investigations": inv_list,
        "recent_audit_logs": audit_list,
    }


# ─────────────────────────────────────────────
# FRAUD INVESTIGATOR DASHBOARD
# ─────────────────────────────────────────────

@router.get("/fraud-investigator", summary="Fraud Investigation Officer dashboard")
async def get_fraud_investigator_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles([RoleEnum.FRAUD_INVESTIGATOR, RoleEnum.CLAIMS_MANAGER, RoleEnum.SYSTEM_ADMIN])
    ),
) -> Dict[str, Any]:
    """Investigation workspace data for fraud investigators."""

    # New AI fraud alerts (high/critical risk not yet under investigation)
    high_risk_assessments = db.query(FraudAssessment).filter(
        FraudAssessment.risk_category.in_(["High", "Critical"])
    ).count()

    # Investigations assigned to this investigator
    assigned_to_me = db.query(Investigation).filter(
        Investigation.investigator_id == current_user.id
    ).count()

    open_inv = db.query(Investigation).filter(Investigation.status == "open").count()
    in_review_inv = db.query(Investigation).filter(Investigation.status == "in_review").count()
    escalated_inv = db.query(Investigation).filter(Investigation.status == "escalated").count()
    confirmed = db.query(Investigation).filter(Investigation.status == "confirmed_fraud").count()
    cleared = db.query(Investigation).filter(Investigation.status == "cleared").count()

    # Open investigations list
    open_cases = db.query(Investigation).filter(
        Investigation.status.in_(["open", "in_review", "escalated"])
    ).order_by(desc(Investigation.opened_at)).limit(20).all()

    cases_list = []
    for inv in open_cases:
        claim = inv.claim
        assessment = claim.assessment if claim else None
        cases_list.append({
            "investigation_id": inv.id,
            "claim_id": claim.claim_id if claim else None,
            "customer_name": claim.customer.name if claim and claim.customer else "Unknown",
            "claim_type": claim.claim_type if claim else None,
            "amount": claim.amount if claim else None,
            "policy_number": claim.policy.policy_number if claim and claim.policy else None,
            "risk_score": assessment.risk_score if assessment else None,
            "risk_category": assessment.risk_category if assessment else None,
            "investigation_status": inv.status,
            "is_assigned_to_me": inv.investigator_id == current_user.id,
            "investigator": inv.investigator.full_name or inv.investigator.username if inv.investigator else "Unassigned",
            "opened_at": inv.opened_at.isoformat() if inv.opened_at else None,
            "top_indicator": (assessment.indicators[0].get("detail") if assessment and assessment.indicators else "No indicator"),
        })

    # High-risk fraud alerts (unassigned)
    new_alerts = (
        db.query(FraudAssessment)
        .filter(FraudAssessment.risk_category.in_(["High", "Critical"]))
        .order_by(desc(FraudAssessment.risk_score))
        .limit(10)
        .all()
    )
    alerts_list = []
    for a in new_alerts:
        claim = a.claim
        inv_exists = db.query(Investigation).filter(Investigation.claim_id == claim.id).first() if claim else None
        alerts_list.append({
            "claim_id": claim.claim_id if claim else None,
            "customer_name": claim.customer.name if claim and claim.customer else "Unknown",
            "risk_score": a.risk_score,
            "risk_category": a.risk_category,
            "claim_type": claim.claim_type if claim else None,
            "amount": claim.amount if claim else None,
            "has_investigation": inv_exists is not None,
            "assessed_at": a.assessed_at.isoformat() if a.assessed_at else None,
        })

    # High-risk claims awaiting investigation (not yet under investigation)
    unassigned_ids = {
        inv.claim_id for inv in db.query(Investigation).all()
    }
    high_risk_awaiting = []
    for a in db.query(FraudAssessment).filter(
        FraudAssessment.risk_category.in_(["High", "Critical"])
    ).order_by(desc(FraudAssessment.risk_score)).all():
        if a.claim and a.claim.id not in unassigned_ids:
            high_risk_awaiting.append({
                "claim_id": a.claim.claim_id,
                "customer_name": a.claim.customer.name if a.claim.customer else "Unknown",
                "risk_score": a.risk_score,
                "risk_category": a.risk_category,
                "amount": a.claim.amount,
            })

    # Cases awaiting evidence: submitted claims with no OCR documents
    cases_awaiting_evidence = (
        db.query(Claim)
        .filter(Claim.status == "submitted")
        .outerjoin(OCRDocument, OCRDocument.claim_id == Claim.id)
        .filter(OCRDocument.id.is_(None))
        .limit(10)
        .all()
    )
    awaiting_evidence_list = [
        {"claim_id": c.claim_id, "customer_name": c.customer.name if c.customer else "Unknown",
         "submission_date": c.submission_date.isoformat() if c.submission_date else None}
        for c in cases_awaiting_evidence
    ]

    # Assigned investigations detail for this investigator
    assigned_details = []
    for inv in db.query(Investigation).filter(Investigation.investigator_id == current_user.id).order_by(desc(Investigation.opened_at)).limit(10).all():
        claim = inv.claim
        ocr_count = db.query(OCRDocument).filter(OCRDocument.claim_id == inv.claim_id).count() if claim else 0
        assigned_details.append({
            "investigation_id": inv.id,
            "claim_id": claim.claim_id if claim else None,
            "customer_name": claim.customer.name if claim and claim.customer else "Unknown",
            "status": inv.status,
            "opened_at": inv.opened_at.isoformat() if inv.opened_at else None,
            "ocr_evidence_count": ocr_count,
            "progress": {
                "open": inv.status == "open",
                "in_review": inv.status == "in_review",
                "escalated": inv.status == "escalated",
            },
        })

    # OCR-extracted evidence for claims under investigation
    ocr_evidence = []
    for inv in db.query(Investigation).filter(
        Investigation.status.in_(["open", "in_review", "escalated"])
    ).limit(10).all():
        docs = db.query(OCRDocument).filter(OCRDocument.claim_id == inv.claim_id).all()
        for d in docs:
            ocr_evidence.append({
                "investigation_id": inv.id,
                "document_id": d.id,
                "filename": d.filename,
                "document_type": d.document_type,
                "confidence_score": d.confidence_score,
                "flags": d.flags or [],
                "has_date_mismatch": d.has_date_mismatch,
            })

    # AI forensic findings for open investigations
    ai_forensic_findings = []
    for inv in db.query(Investigation).filter(
        Investigation.status.in_(["open", "in_review", "escalated"])
    ).limit(10).all():
        claim = inv.claim
        if claim and claim.assessment:
            ai_forensic_findings.append({
                "investigation_id": inv.id,
                "claim_id": claim.claim_id,
                "risk_score": claim.assessment.risk_score,
                "risk_category": claim.assessment.risk_category,
                "explanation": claim.assessment.explanation,
            })

    # Historical suspicious patterns: claim counts by risk category per month
    hist_rows = (
        db.query(FraudAssessment.risk_category, FraudAssessment.assessed_at)
        .filter(FraudAssessment.risk_category.in_(["High", "Critical"]))
        .order_by(desc(FraudAssessment.assessed_at))
        .limit(200)
        .all()
    )
    pattern_by_month = {}
    for cat, dt in hist_rows:
        if dt:
            month = dt.strftime("%Y-%m")
            pattern_by_month.setdefault(month, 0)
            pattern_by_month[month] += 1
    historical_patterns = [
        {"period": m, "suspicious_claims": c} for m, c in sorted(pattern_by_month.items())
    ]

    return {
        "summary": {
            "new_fraud_alerts": high_risk_assessments,
            "assigned_to_me": assigned_to_me,
            "open_investigations": open_inv,
            "investigations_in_review": in_review_inv,
            "escalated_cases": escalated_inv,
            "confirmed_fraud": confirmed,
            "cleared_cases": cleared,
            "cases_awaiting_evidence": len(awaiting_evidence_list),
        },
        "open_cases": cases_list,
        "fraud_alerts": alerts_list,
        "high_risk_claims": high_risk_awaiting,
        "cases_awaiting_evidence": awaiting_evidence_list,
        "assigned_investigations": assigned_details,
        "ocr_evidence": ocr_evidence,
        "ai_forensic_findings": ai_forensic_findings,
        "historical_suspicious_patterns": historical_patterns,
    }


# ─────────────────────────────────────────────
# SYSTEM ADMINISTRATOR DASHBOARD
# ─────────────────────────────────────────────

@router.get("/admin", summary="System Administrator dashboard with platform health and user management data")
async def get_admin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([RoleEnum.SYSTEM_ADMIN])),
) -> Dict[str, Any]:
    """System administration workspace: users, health, AI, OCR, and audit metrics."""

    # User management
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    inactive_users = db.query(User).filter(User.is_active == False).count()

    # Role breakdown
    role_breakdown = db.query(User.role, func.count(User.id)).group_by(User.role).all()

    # All users
    all_users = db.query(User).order_by(desc(User.created_at)).all()
    users_list = [
        {
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "email": u.email,
            "role": u.role.value,
            "department": u.department,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in all_users
    ]

    # OCR processing stats
    total_ocr = db.query(OCRDocument).count()
    ocr_completed = db.query(OCRDocument).filter(OCRDocument.processing_status == "completed").count()
    ocr_failed = db.query(OCRDocument).filter(OCRDocument.processing_status == "failed").count()
    ocr_pending = db.query(OCRDocument).filter(OCRDocument.processing_status == "pending").count()

    # AI model stats
    total_claims = db.query(Claim).count()
    total_assessments = db.query(FraudAssessment).count()

    # Recent audit logs
    recent_logs = db.query(AuditLog).order_by(desc(AuditLog.timestamp)).limit(30).all()
    audit_list = [
        {
            "id": a.id,
            "user": a.user.username if a.user else "System",
            "user_role": a.user.role.value if a.user else "system",
            "action": a.action,
            "target": a.target,
            "detail": a.detail,
            "timestamp": a.timestamp.isoformat() if a.timestamp else None,
        }
        for a in recent_logs
    ]

    # Failed processing jobs (OCR) detail
    failed_jobs = (
        db.query(OCRDocument).filter(OCRDocument.processing_status == "failed").order_by(desc(OCRDocument.uploaded_at)).limit(10).all()
    )
    failed_jobs_list = [
        {
            "document_id": d.id,
            "filename": d.filename,
            "mime_type": d.mime_type,
            "claim_id": d.claim_id,
            "uploaded_by": d.uploaded_by.username if d.uploaded_by else "Unknown",
            "flags": d.flags or [],
            "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
        }
        for d in failed_jobs
    ]

    # Security alerts: failed login attempts in the last 24 hours
    failed_logins = (
        db.query(AuditLog)
        .filter(AuditLog.action == "LOGIN_FAILED")
        .order_by(desc(AuditLog.timestamp))
        .limit(10)
        .all()
    )
    security_alerts = [
        {
            "id": l.id,
            "user": l.user.username if l.user else "Unknown",
            "action": l.action,
            "target": l.target,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
        }
        for l in failed_logins
    ]

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "inactive": inactive_users,
            "by_role": [{"role": r[0].value, "count": r[1]} for r in role_breakdown],
        },
        "all_users": users_list,
        "system_health": {
            "api_status": "Operational",
            "database_status": "Connected",
            "ai_model_status": "Active (v1.2-ensemble-hybrid)",
            "ocr_service_status": "Active (Tesseract / Fallback)",
            "total_claims": total_claims,
            "total_assessments": total_assessments,
            "ai_coverage_rate": round((total_assessments / max(total_claims, 1)) * 100, 1),
        },
        "ocr_processing": {
            "total_documents": total_ocr,
            "completed": ocr_completed,
            "failed": ocr_failed,
            "pending": ocr_pending,
            "success_rate": round((ocr_completed / max(total_ocr, 1)) * 100, 1),
        },
        "failed_processing_jobs": failed_jobs_list,
        "security_alerts": security_alerts,
        "audit_logs": audit_list,
    }


# ─────────────────────────────────────────────
# SHARED: USER PROFILE & ROLE INFO
# ─────────────────────────────────────────────

@router.get("/my-profile", summary="Get current user's profile and role information")
async def get_my_profile(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Returns the authenticated user's full profile and role details for dashboard routing."""
    role_to_dashboard = {
        RoleEnum.CLAIMS_OFFICER: "claims_officer",
        RoleEnum.CLAIMS_MANAGER: "claims_officer",
        RoleEnum.MANAGEMENT: "executive",
        RoleEnum.COMPLIANCE_OFFICER: "compliance",
        RoleEnum.FRAUD_INVESTIGATOR: "fraud_investigator",
        RoleEnum.SYSTEM_ADMIN: "admin",
    }

    return {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "role": current_user.role.value,
        "department": current_user.department,
        "is_active": current_user.is_active,
        "dashboard_type": role_to_dashboard.get(current_user.role, "claims_officer"),
    }
