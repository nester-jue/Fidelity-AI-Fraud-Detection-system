import hashlib
import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..services.db import get_db
from ..services import tenant as tenant_service
from ..models.sqlalchemy_models import User, Organisation, RoleEnum
from ..auth import (
    verify_password, get_password_hash, create_access_token,
    generate_totp_secret, verify_totp, totp_provisioning_uri,
)
from ..dependencies import get_current_active_user, log_audit_trail, require_roles
from ..core.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=2)
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=settings.PASSWORD_MIN_LENGTH)
    role: RoleEnum = RoleEnum.CLAIMS_OFFICER

class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str | None = None
    email: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}

@router.post("/token", summary="Obtain JWT access token via username and password (MFA code when enrolled)")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    mfa_code: str | None = Form(None, description="Authenticator app code, required for MFA-enrolled users"),
    request: Request = None,
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request and request.client else "unknown"
    user = db.query(User).filter((User.username == form_data.username) | (User.email == form_data.username.lower())).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        log_audit_trail(db, user, action="LOGIN_FAILED", target=f"User:{form_data.username}", detail={"ip": client_ip})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account has been deactivated",
        )
    if settings.TENANT_ISOLATION_ENABLED and user.organisation_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not assigned to an organisation. Contact your system administrator.",
        )
    if user.mfa_enabled:
        if not mfa_code or not verify_totp(user.mfa_secret or "", str(mfa_code)):
            log_audit_trail(db, user, action="MFA_CHALLENGE_FAILED", target=f"User:{user.username}", detail={"ip": client_ip})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="MFA_REQUIRED: Enter the current 6-digit code from your authenticator app",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # When policy requires MFA but the account has not enrolled, issue a
    # short-lived token restricted to the enrolment endpoints. It cannot read
    # or modify any business data.
    enrollment_required = bool(settings.MFA_REQUIRED and not user.mfa_enabled)
    expires = timedelta(minutes=15 if enrollment_required else settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={
            "sub": user.username,
            "role": user.role.value,
            "user_id": user.id,
            "organisation_id": user.organisation_id,
            "mfa_pending": enrollment_required,
        },
        expires_delta=expires,
    )

    log_audit_trail(db, user, action="USER_LOGIN", target=f"User:{user.username}", detail={"ip": client_ip, "mfa": bool(user.mfa_enabled), "enrollment_required": enrollment_required})

    return {
        "access_token": token,
        "token_type": "bearer",
        "mfa_enrollment_required": enrollment_required,
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role.value,
        },
    }

@router.post("/register", response_model=UserResponse, summary="Request a standard claims-officer account")
async def register_user(user_in: UserRegister, db: Session = Depends(get_db)):
    if not settings.ALLOW_PUBLIC_REGISTRATION:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Public registration is disabled for this deployment. Contact your system administrator.")
    # Privileged roles can only be granted by an authenticated administrator
    # through /users. Self-registration never grants elevated access.
    if user_in.role != RoleEnum.CLAIMS_OFFICER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Privileged roles cannot be self-registered. Contact your system administrator for access.",
        )
    if len(user_in.password) < settings.PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters.",
        )
    existing = db.query(User).filter((User.username == user_in.username) | (User.email == user_in.email)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email is already registered in the system",
        )

    organisation_id = None
    if settings.TENANT_ISOLATION_ENABLED:
        organisation_id = settings.DEFAULT_ORGANISATION_ID
        if organisation_id is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Self-registration requires a configured DEFAULT_ORGANISATION_ID. Contact your system administrator.",
            )
        org = db.query(Organisation).filter(
            Organisation.id == organisation_id, Organisation.is_active.is_(True)
        ).first()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The configured registration organisation is unavailable. Contact your system administrator.",
            )

    new_user = User(
        username=user_in.username.strip(),
        full_name=user_in.full_name.strip(),
        email=user_in.email.strip().lower(),
        hashed_password=get_password_hash(user_in.password),
        role=RoleEnum.CLAIMS_OFFICER,
        organisation_id=organisation_id,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_audit_trail(db, new_user, action="USER_REGISTERED", target=f"User:{new_user.username}", detail={"role": new_user.role.value})
    return new_user

class ForgotPasswordRequest(BaseModel):
    email: str

@router.post("/forgot-password", summary="Send a one-time password reset link via configured SMTP")
async def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    email = req.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    log_audit_trail(db, user, action="PASSWORD_RESET_REQUESTED", target=f"User:{user.username if user else email}", detail={"email": email})

    if not settings.PASSWORD_RESET_EMAIL_ENABLED or not settings.SMTP_HOST:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Automated password reset is not configured for this deployment. Contact your system administrator.",
        )

    generic = "If the address matches an account, a reset link has been sent."
    if not user:
        return {"message": generic}

    raw_token = secrets.token_urlsafe(32)
    user.password_reset_token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.PASSWORD_RESET_TOKEN_MINUTES
    )
    db.commit()

    link = (
        f"{settings.FRONTEND_RESET_URL.rstrip('/')}/reset-password?token={raw_token}"
        if settings.FRONTEND_RESET_URL else f"Reset token (use /auth/reset-password): {raw_token}"
    )
    message = EmailMessage()
    message["Subject"] = "NEXA password reset"
    message["From"] = settings.PASSWORD_RESET_FROM_EMAIL
    message["To"] = user.email
    message.set_content(
        f"Use the following link to reset your NEXA password. It expires in "
        f"{settings.PASSWORD_RESET_TOKEN_MINUTES} minutes.\n\n{link}\n\n"
        "If you did not request this, no action is required."
    )
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(message)
    except Exception:
        # Never leave a usable token behind when delivery could not be proven.
        user.password_reset_token_hash = None
        user.password_reset_expires_at = None
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The reset email could not be delivered. Contact your system administrator.",
        )
    return {"message": generic}


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=20)
    new_password: str = Field(..., min_length=settings.PASSWORD_MIN_LENGTH)


@router.post("/reset-password", summary="Complete a password reset with a one-time token")
async def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    user = db.query(User).filter(User.password_reset_token_hash == token_hash).first()
    expires_at = user.password_reset_expires_at if user else None
    now = datetime.now(timezone.utc)
    if expires_at and expires_at.tzinfo is None:
        now = now.replace(tzinfo=None)  # SQLite stores naive UTC timestamps
    if not user or not expires_at or expires_at < now:
        raise HTTPException(status_code=400, detail="The reset link is invalid or has expired. Request a new one.")
    user.hashed_password = get_password_hash(payload.new_password)
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    db.commit()
    log_audit_trail(db, user, action="PASSWORD_RESET_COMPLETED", target=f"User:{user.username}")
    return {"message": "Password updated. Sign in with the new password."}

@router.get("/me", response_model=UserResponse, summary="Get authenticated profile information")
async def get_my_profile(current_user: User = Depends(get_current_active_user)):
    return current_user


class MfaCodeRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class MfaDisableRequest(MfaCodeRequest):
    password: str


@router.get("/mfa/status", summary="Current user's MFA enrolment status")
async def mfa_status(current_user: User = Depends(get_current_active_user)):
    return {
        "mfa_enabled": bool(current_user.mfa_enabled),
        "mfa_required_by_policy": bool(settings.MFA_REQUIRED),
    }


@router.post("/mfa/setup", summary="Begin authenticator-app enrolment for the current user")
async def mfa_setup(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    secret = generate_totp_secret()
    current_user.mfa_secret = secret
    db.commit()
    log_audit_trail(db, current_user, "MFA_ENROLMENT_STARTED", f"User:{current_user.username}")
    return {
        "secret": secret,
        "provisioning_uri": totp_provisioning_uri(current_user.username, secret),
        "issuer": settings.ORGANIZATION,
        "instructions": "Add this secret to an authenticator app, then submit the current 6-digit code to /auth/mfa/enable.",
    }


@router.post("/mfa/enable", summary="Verify an enrolment code and enable MFA")
async def mfa_enable(
    payload: MfaCodeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not current_user.mfa_secret or not verify_totp(current_user.mfa_secret, payload.code):
        raise HTTPException(status_code=400, detail="Invalid authenticator code. Check the time on your device and try again.")
    current_user.mfa_enabled = True
    db.commit()
    log_audit_trail(db, current_user, "MFA_ENABLED", f"User:{current_user.username}")
    # Upgrade a short-lived enrolment token so the user can continue without
    # an extra sign-in round trip.
    token = create_access_token(data={
        "sub": current_user.username,
        "role": current_user.role.value,
        "user_id": current_user.id,
        "organisation_id": current_user.organisation_id,
        "mfa_pending": False,
    })
    return {
        "mfa_enabled": True,
        "access_token": token,
        "message": "MFA is now required for this account.",
    }


@router.post("/mfa/disable", summary="Disable MFA after password and code verification")
async def mfa_disable(
    payload: MfaDisableRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password.")
    if not current_user.mfa_secret or not verify_totp(current_user.mfa_secret, payload.code):
        raise HTTPException(status_code=400, detail="Invalid authenticator code.")
    current_user.mfa_enabled = False
    current_user.mfa_secret = None
    db.commit()
    log_audit_trail(db, current_user, "MFA_DISABLED", f"User:{current_user.username}")
    return {"mfa_enabled": False}

