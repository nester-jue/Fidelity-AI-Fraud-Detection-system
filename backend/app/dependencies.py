from typing import List, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .services.db import get_db
from .auth import decode_access_token
from .models.sqlalchemy_models import User, RoleEnum, AuditLog

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)

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
