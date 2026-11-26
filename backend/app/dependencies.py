from typing import List, Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .services.db import get_db
from .auth import decode_access_token
from .core.config import settings
from .models.sqlalchemy_models import User, RoleEnum, AuditLog

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)

# Endpoints reachable with a short-lived enrolment token issued when
# MFA_REQUIRED=true and an account has not enrolled an authenticator yet.
MFA_ENROLMENT_PATHS = {
    "/auth/me", "/auth/mfa/status", "/auth/mfa/setup",
    "/auth/mfa/enable", "/auth/mfa/disable",
}

# Department assignments per role. System admins are not bound to one
# department: they may access every department's data for administration.
DEPARTMENT_BY_ROLE = {
    RoleEnum.SYSTEM_ADMIN: ["Claims", "Executive", "Compliance", "Investigations", "Risk", "IT", "All"],
    RoleEnum.CLAIMS_OFFICER: ["Claims"],
    RoleEnum.CLAIMS_MANAGER: ["Claims"],
    RoleEnum.FRAUD_INVESTIGATOR: ["Investigations"],
    RoleEnum.COMPLIANCE_OFFICER: ["Compliance"],
    RoleEnum.MANAGEMENT: ["Executive"],
    RoleEnum.CHIEF_RISK_OFFICER: ["Risk", "Executive"],
}

def get_user_departments(user: User) -> List[str]:
    """Returns the departments a user may access (admin: all)."""
    if user.role == RoleEnum.SYSTEM_ADMIN:
        return ["Claims", "Executive", "Compliance", "Investigations", "Risk", "IT"]
    if user.department:
        return [user.department]
    return DEPARTMENT_BY_ROLE.get(user.role, [])

def is_department_admin(user: User) -> bool:
    return user.role == RoleEnum.SYSTEM_ADMIN

def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    username = payload.get("sub")
    if not username:
        return None
    return db.query(User).filter(User.username == username).first()

def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    request: Request = None,
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing user identity",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("mfa_pending") and (request is None or request.url.path not in MFA_ENROLMENT_PATHS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MFA_REQUIRED: complete authenticator enrolment before using the workspace",
        )
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    if settings.TENANT_ISOLATION_ENABLED:
        claimed_org = payload.get("organisation_id")
        if not isinstance(claimed_org, int) or user.organisation_id != claimed_org:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organisation membership changed. Sign in again to continue.",
            )
    return user

def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user

def require_roles(allowed_roles: List[RoleEnum]):
    """Enforces that the authenticated user possesses one of the allowed roles."""
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role == RoleEnum.SYSTEM_ADMIN:
            # System admin always has full access
            return current_user
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Requires role in {[r.value for r in allowed_roles]}, user has '{current_user.role.value}'",
            )
        return current_user
    return role_checker

def require_role(single_role: RoleEnum):
    return require_roles([single_role])

def _normalize_departments(allowed) -> List[str]:
    """Maps role enums in the allowed list to their departments."""
    depts = []
    for item in allowed:
        if isinstance(item, RoleEnum):
            depts.extend(DEPARTMENT_BY_ROLE.get(item, []))
        else:
            depts.append(item)
    return depts


def require_department(allowed):
    """Enforces that the user's department is in the allowed list.

    Items may be plain departments ("Claims") or roles (RoleEnum.CLAIMS_OFFICER,
    mapped via DEPARTMENT_BY_ROLE). System admins bypass the department check
    (they can access every department's data). Backend-enforced: this protects
    the data APIs even when the frontend hides the pages.
    """
    depts = _normalize_departments(allowed)

    def department_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if is_department_admin(current_user):
            return current_user
        user_depts = get_user_departments(current_user)
        if not any(d in user_depts for d in depts):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: user is not authorised for department(s) {depts}",
            )
        return current_user
    return department_checker

def require_role_or_department(allowed_roles: List[RoleEnum], allowed_departments: List[str]):
    """Allows access if the user has one of the roles OR is in the allowed departments."""
    role_deps = [DEPARTMENT_BY_ROLE.get(r, []) for r in allowed_roles]
    combined = allowed_departments + [d for rd in role_deps for d in rd]
    def checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role in allowed_roles:
            return current_user
        user_depts = get_user_departments(current_user)
        if not any(d in user_depts for d in combined):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: user role/department is not authorised for this workspace",
            )
        return current_user
    return checker

def log_audit_trail(db: Session, user: Optional[User], action: str, target: str, detail: Optional[dict] = None):
    """Helper function to record system audit trail."""
    try:
        log = AuditLog(
            user_id=user.id if user else None,
            action=action,
            target=target,
            detail=detail or {},
        )
        db.add(log)
        db.commit()
    except Exception:
        db.rollback()
