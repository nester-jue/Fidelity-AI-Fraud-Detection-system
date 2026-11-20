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
    Claim, FraudAssessment, Investigation, User, RoleEnum,
    AuditLog, Notification, OCRDocument, ModelPerformance
)
from ..dependencies import get_current_active_user, require_roles

router = APIRouter(prefix="/departmental", tags=["Departmental Dashboards"])


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

    # Total claims in system (officer sees all assigned + general)
    total_claims = db.query(Claim).count()
    new_claims = db.query(Claim).filter(Claim.status == "submitted").count()
    in_review = db.query(Claim).filter(Claim.status == "in_review").count()
    flagged = db.query(Claim).filter(Claim.status == "flagged").count()
    approved = db.query(Claim).filter(Claim.status == "approved").count()
    rejected = db.query(Claim).filter(Claim.status == "rejected").count()
    pending_docs = db.query(Claim).filter(Claim.status == "pending_documents").count()

    # Claims submitted for AI assessment
    ai_assessed = db.query(FraudAssessment).count()

    # Recent claims (last 10)
    recent_claims = db.query(Claim).order_by(desc(Claim.submission_date)).limit(10).all()
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
        })

    # Status distribution
    status_distribution = [
        {"status": "Submitted", "count": new_claims, "color": "#3B82F6"},
        {"status": "In Review", "count": in_review, "color": "#F59E0B"},
        {"status": "Flagged", "count": flagged, "color": "#EF4444"},
        {"status": "Approved", "count": approved, "color": "#10B981"},
        {"status": "Rejected", "count": rejected, "color": "#6B7280"},
    ]

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
            "claims_flagged": flagged,
            "claims_submitted_for_ai": ai_assessed,
            "claims_approved": approved,
            "claims_rejected": rejected,
        },
        "status_distribution": status_distribution,
        "recent_claims": recent_list,
    }


# ─────────────────────────────────────────────
# EXECUTIVE DASHBOARD
# ─────────────────────────────────────────────

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

    return {
        "summary": {
            "claims_requiring_review": flagged_claims,
            "high_risk_claims": high_risk_count,
            "open_investigations": open_investigations,
            "escalated_investigations": escalated,
            "confirmed_fraud_cases": confirmed_fraud,
            "claims_missing_documents": claims_without_docs,
        },
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

    return {
        "summary": {
            "new_fraud_alerts": high_risk_assessments,
            "assigned_to_me": assigned_to_me,
            "open_investigations": open_inv,
            "investigations_in_review": in_review_inv,
            "escalated_cases": escalated_inv,
            "confirmed_fraud": confirmed,
            "cleared_cases": cleared,
        },
        "open_cases": cases_list,
        "fraud_alerts": alerts_list,
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
