from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ..services.db import get_db
from ..models.sqlalchemy_models import User, RoleEnum
from ..auth import get_password_hash
from ..dependencies import require_role, get_current_active_user, log_audit_trail

router = APIRouter(prefix="/users", tags=["User Management"])

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = None
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)
    role: RoleEnum = RoleEnum.CLAIMS_OFFICER
    department: Optional[str] = None

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[RoleEnum] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None

class UserOut(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    email: str
    role: str
    department: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}

@router.get("/", response_model=List[UserOut], summary="List all system users (admin only)")
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleEnum.SYSTEM_ADMIN)),
):
    return db.query(User).all()

@router.post("/", response_model=UserOut, summary="Create a new user (admin only)")
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleEnum.SYSTEM_ADMIN)),
):
    existing = db.query(User).filter(
        (User.username == user_in.username) | (User.email == user_in.email)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username or email already exists")

    new_user = User(
        username=user_in.username,
        full_name=user_in.full_name,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
        department=user_in.department,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_audit_trail(db, current_user, action="ADMIN_CREATED_USER", target=f"User:{new_user.username}", detail={"role": new_user.role.value, "department": new_user.department})
    return new_user

@router.put("/{user_id}", response_model=UserOut, summary="Update user role, department, or status (admin only)")
def update_user(
    user_id: int,
    update_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleEnum.SYSTEM_ADMIN)),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if update_in.full_name is not None:
        user.full_name = update_in.full_name
    if update_in.role is not None:
        user.role = update_in.role
    if update_in.department is not None:
        user.department = update_in.department
    if update_in.is_active is not None:
        user.is_active = update_in.is_active

    db.commit()
    db.refresh(user)

    log_audit_trail(db, current_user, action="ADMIN_UPDATED_USER", target=f"User:{user.username}",
                    detail={"role": user.role.value, "is_active": user.is_active, "department": user.department})
    return user

@router.delete("/{user_id}", summary="Deactivate a user account (admin only)")
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleEnum.SYSTEM_ADMIN)),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account.")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    db.commit()
    log_audit_trail(db, current_user, action="ADMIN_DEACTIVATED_USER", target=f"User:{user.username}")
    return {"message": f"User '{user.username}' has been deactivated."}
