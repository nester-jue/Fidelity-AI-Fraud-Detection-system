"""Enterprise Security Centre — read-only views built from real records.

Nothing in this module reports a green status unless the corresponding check
has actually been performed. Counts are derived from audit_logs and the live
database session; deployment controls (MFA, backups, password reset email)
are reported from explicit configuration only.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ..core.config import settings
from ..dependencies import require_roles, log_audit_trail
from ..models.sqlalchemy_models import AuditLog, RoleEnum, User
from ..services.db import get_db, engine

router = APIRouter(prefix="/security", tags=["Enterprise Security Centre"])

SECURITY_ROLES = [RoleEnum.SYSTEM_ADMIN, RoleEnum.COMPLIANCE_OFFICER, RoleEnum.MANAGEMENT, RoleEnum.CHIEF_RISK_OFFICER]
AUTH_ACTIONS = {"USER_LOGIN", "LOGIN_FAILED", "PASSWORD_RESET_REQUESTED", "USER_REGISTERED", "USER_DEACTIVATED"}
SENSITIVE_ACTIONS = {
    "USER_LOGIN", "LOGIN_FAILED", "PASSWORD_RESET_REQUESTED", "USER_REGISTERED",
    "PERMISSION_CHANGED", "USER_PERMISSION_CHANGE", "CONFIGURATION_CHANGED",
    "DOCUMENT_DOWNLOADED", "CLAIM_MODIFIED", "APPROVAL_DECISION", "INVESTIGATION_UPDATED",
}

security_guard = require_roles(SECURITY_ROLES)


class SecurityEvent(BaseModel):
    id: int
    timestamp: Optional[str]
    user: str
    action: str
    target: Optional[str]
    detail: Optional[dict]
    classification: str


@router.get("/overview", summary="Security status, authentication activity and audit telemetry from real records")
async def security_overview(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(security_guard),
):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    base = db.query(AuditLog).filter(AuditLog.timestamp >= start)

    by_action = dict(
        db.query(AuditLog.action, func.count(AuditLog.id))
        .filter(AuditLog.timestamp >= start)
        .group_by(AuditLog.action)
        .all()
    )
    daily = (
        db.query(func.date(AuditLog.timestamp), AuditLog.action, func.count(AuditLog.id))
        .filter(AuditLog.timestamp >= start)
        .group_by(func.date(AuditLog.timestamp), AuditLog.action)
        .all()
    )
    daily_logins = {}
    daily_failures = {}
    for day, action, count in daily:
        key = str(day)
        if action == "USER_LOGIN":
            daily_logins[key] = daily_logins.get(key, 0) + count
        elif action == "LOGIN_FAILED":
            daily_failures[key] = daily_failures.get(key, 0) + count

    # JWT tokens are stateless: the platform cannot enumerate live tokens.
    # Report only a verifiable proxy — distinct users authenticated within
    # one token lifetime — and label it as such.
    active_since = end - timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    recent_user_ids = (
        db.query(func.distinct(AuditLog.user_id))
        .filter(AuditLog.action == "USER_LOGIN", AuditLog.timestamp >= active_since, AuditLog.user_id.isnot(None))
        .all()
    )

    # Database check — actually executes a query against the live engine.
    db_health = {"status": "UNKNOWN", "dialect": engine.dialect.name, "checked_at": end.isoformat()}
    try:
        db.execute(select(1)).scalar_one()
        db_health["status"] = "CONNECTED"
    except Exception as exc:  # pragma: no cover - defensive database failure path
        db_health["status"] = "UNAVAILABLE"
        db_health["detail"] = type(exc).__name__

    backup_ok = bool(settings.BACKUP_VERIFICATION_CONFIGURED and settings.BACKUP_LAST_VERIFIED_AT)
    backup = {
        "status": "VERIFIED" if backup_ok else "NOT_VERIFIED",
        "last_verified_at": settings.BACKUP_LAST_VERIFIED_AT or None,
        "detail": None if backup_ok else "No verified backup record is configured for this deployment.",
    }

    controls = [
        {"name": "Role-based access control", "status": "ENFORCED", "basis": "Backend role checks on protected API routes."},
        {"name": "Audit logging", "status": "ENFORCED" if base.count() > 0 else "NO_EVENTS_RECORDED", "basis": f"{base.count()} audit event(s) in the reporting period."},
        {
            "name": "Multi-factor authentication",
            "status": "REQUIRED" if settings.MFA_REQUIRED else "AVAILABLE",
            "basis": (
                "Authenticator-app TOTP enrolment via /auth/mfa/setup. MFA_REQUIRED=true: "
                "un-enrolled accounts receive an enrolment-only token and cannot access workspaces."
                if settings.MFA_REQUIRED else
                "Authenticator-app TOTP enrolment via /auth/mfa/setup. MFA is optional for this deployment (MFA_REQUIRED=false)."
            ),
        },
        {
            "name": "Tenant isolation",
            "status": "ENFORCED" if settings.TENANT_ISOLATION_ENABLED else "SINGLE_TENANT",
            "basis": (
                "ORM-level organisation filtering and insert stamping are active."
                if settings.TENANT_ISOLATION_ENABLED else
                "TENANT_ISOLATION_ENABLED=false; all records share one organisation scope."
            ),
        },
        {
            "name": "Password reset email",
            "status": "ENABLED" if settings.PASSWORD_RESET_EMAIL_ENABLED and settings.SMTP_HOST else "NOT_CONFIGURED",
            "basis": (
                "PASSWORD_RESET_EMAIL_ENABLED and SMTP_HOST are both configured."
                if settings.PASSWORD_RESET_EMAIL_ENABLED and settings.SMTP_HOST else
                "Automated reset delivery requires PASSWORD_RESET_EMAIL_ENABLED=true and SMTP_HOST."
            ),
        },
        {"name": "Database backup verification", "status": backup["status"], "basis": backup["detail"] or "Verified backup record present."},
    ]

    log_audit_trail(db, current_user, "SECURITY_OVERVIEW_VIEWED", "SecurityCentre", {"period_days": days})

    return {
        "reporting_period": {"from": start.date().isoformat(), "to": end.date().isoformat(), "days": days},
        "generated_at": end.isoformat(),
        "authentication": {
            "successful_logins": by_action.get("USER_LOGIN", 0),
            "failed_logins": by_action.get("LOGIN_FAILED", 0),
            "password_reset_requests": by_action.get("PASSWORD_RESET_REQUESTED", 0),
            "registrations": by_action.get("USER_REGISTERED", 0),
            "recently_authenticated_users": len(recent_user_ids),
            "recent_users_note": "Distinct users with a login event inside one token lifetime. JWT sessions are stateless and cannot be enumerated.",
        },
        "authentication_trend": [
            {"date": d, "successful": daily_logins.get(d, 0), "failed": daily_failures.get(d, 0)}
            for d in sorted(set(daily_logins) | set(daily_failures))
        ],
        "audit": {
            "events_in_period": base.count(),
            "events_by_action": by_action,
            "security_relevant_events": sum(v for k, v in by_action.items() if k in SENSITIVE_ACTIONS),
        },
        "database": db_health,
        "backup": backup,
        "password_policy": {
            "min_length": settings.PASSWORD_MIN_LENGTH,
            "public_registration_enabled": settings.ALLOW_PUBLIC_REGISTRATION,
        },
        "controls": controls,
    }


@router.get("/events", response_model=List[SecurityEvent], summary="Security-relevant audit events")
async def security_events(
    days: int = Query(30, ge=1, le=365),
    action: Optional[str] = Query(None, description="Exact audit action code"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(security_guard),
):
    start = datetime.now(timezone.utc) - timedelta(days=days)
    query = db.query(AuditLog).filter(AuditLog.timestamp >= start)
    if action:
        query = query.filter(AuditLog.action == action.upper())
    logs = query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()
    return [
        SecurityEvent(
            id=log.id,
            timestamp=log.timestamp.isoformat() if log.timestamp else None,
            user=log.user.username if log.user else "System",
            action=log.action,
            target=log.target,
            detail=log.detail,
            classification="SECURITY" if log.action in SENSITIVE_ACTIONS else "ACTIVITY",
        )
        for log in logs
    ]
