from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..services.db import get_db
from ..models.sqlalchemy_models import AuditLog, User, RoleEnum
from ..dependencies import require_roles

router = APIRouter(prefix="/audit-logs", tags=["Compliance & Audit Logs"])

@router.get("/", summary="List system activity and risk decision audit trails")
async def list_audit_logs(
    action: Optional[str] = Query(None, description="Filter by action code, e.g. USER_LOGIN, CLAIM_SUBMITTED"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([RoleEnum.COMPLIANCE_OFFICER, RoleEnum.SYSTEM_ADMIN, RoleEnum.MANAGEMENT])),
):
    query = db.query(AuditLog).order_by(desc(AuditLog.timestamp))
    if action:
        query = query.filter(AuditLog.action == action.upper())

    logs = query.offset(skip).limit(limit).all()
    results = []
    for log in logs:
        results.append({
            "id": log.id,
            "user": log.user.username if log.user else "System",
            "user_role": log.user.role.value if log.user else "system",
            "action": log.action,
            "target": log.target,
            "detail": log.detail,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        })
    return results
