import os
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..services.db import get_db
from ..models.sqlalchemy_models import User, RoleEnum
from ..auth import verify_password, get_password_hash, create_access_token
from ..dependencies import get_current_active_user, log_audit_trail
from ..core.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=2)
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)
    role: RoleEnum = RoleEnum.CLAIMS_OFFICER

class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str | None = None
    email: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}

@router.post("/token", summary="Obtain JWT access token via username and password")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter((User.username == form_data.username) | (User.email == form_data.username.lower())).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
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

    expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={"sub": user.username, "role": user.role.value, "user_id": user.id},
        expires_delta=expires,
    )
    
    log_audit_trail(db, user, action="USER_LOGIN", target=f"User:{user.username}", detail={"ip": "127.0.0.1"})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role.value,
        },
    }

@router.post("/register", response_model=UserResponse, summary="Register a new system user")
async def register_user(user_in: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter((User.username == user_in.username) | (User.email == user_in.email)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email is already registered in the system",
        )
    
    new_user = User(
        username=user_in.username.strip(),
        full_name=user_in.full_name.strip(),
        email=user_in.email.strip().lower(),
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_audit_trail(db, new_user, action="USER_REGISTERED", target=f"User:{new_user.username}", detail={"role": new_user.role.value})
    return new_user

class ForgotPasswordRequest(BaseModel):
    email: str

@router.post("/forgot-password", summary="Request password reset instructions")
async def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email.strip().lower()).first()
    if user:
        log_audit_trail(db, user, action="PASSWORD_RESET_REQUESTED", target=f"User:{user.username}", detail={"email": req.email})
    return {
        "message": f"If an active account is associated with {req.email}, password reset instructions have been dispatched to your corporate inbox.",
        "status": "dispatched"
    }

@router.get("/me", response_model=UserResponse, summary="Get authenticated profile information")
async def get_my_profile(current_user: User = Depends(get_current_active_user)):
    return current_user

