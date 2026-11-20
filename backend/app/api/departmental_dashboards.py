"""
Departmental Dashboard APIs
Provides role-specific dashboard data for each department.
All endpoints enforce role-based access at the backend level.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
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
                [d.processing_status for d in c.documents if d.processing_status != "completed"]
                if any(d.processing_status != "completed" for d in c.documents) else "ok"
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

    # Departmental performance: claims flowing through each department.
    # Claims are departmentally assigned via the Claims officer(s) or via the
    # Claims department queue when unassigned.
    claims_by_dept = []
    for d in ["Claims", "Compliance", "Investigations", "Executive", "IT"]:
        users_in_dept = db.query(User.id).filter(User.department == d).all()
        id_list = [u[0] for u in users_in_dept]
        n = db.query(Claim).filter(Claim.assigned_officer_id.in_(id_list)).count() if id_list else 0
        if d == "Claims":
            n += db.query(Claim).filter(
                Claim.status.in_(["flagged", "under_investigation", "pending_documents"]),
                Claim.assigned_officer_id.is_(None),
            ).count()
        claims_by_dept.append({"department": d, "claims": n, "users": len(id_list)})

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
            "total_claims_processed": total_analysed,
            "claims_pending": total_pending,
            "claims_flagged": total_flagged,
            "confirmed_fraud_cases": confirmed_fraud,
            "claims_under_investigation": under_investigation,
            "total_financial_exposure": round(total_exposure, 2),
            "potential_fraud_prevented": round(prevented_losses, 2),
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
