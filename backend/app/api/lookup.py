from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..services.db import get_db
from ..models.sqlalchemy_models import Customer, Policy, Notification, User
from ..dependencies import get_current_active_user

router = APIRouter(tags=["Entity Lookups & Notifications"])

@router.get("/customers", summary="Search and list policyholder customers")
async def list_customers(
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = db.query(Customer)
    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.filter(
            (Customer.name.ilike(search_fmt)) |
            (Customer.customer_id.ilike(search_fmt)) |
            (Customer.national_id.ilike(search_fmt))
        )
    custs = query.offset(skip).limit(limit).all()
    return [
        {
            "id": c.id,
            "customer_id": c.customer_id,
            "name": c.name,
            "national_id": c.national_id,
            "date_of_birth": c.date_of_birth.isoformat() if c.date_of_birth else None,
            "policies_count": len(c.policies),
            "claims_count": len(c.claims),
        }
        for c in custs
    ]

@router.get("/policies", summary="Search and list active insurance policies")
async def list_policies(
    policy_number: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = db.query(Policy)
    if policy_number:
        query = query.filter(Policy.policy_number.ilike(f"%{policy_number.strip()}%"))
    if customer_id:
        query = query.join(Customer).filter(Customer.customer_id == customer_id.strip())

    policies = query.offset(skip).limit(limit).all()
    return [
        {
            "id": p.id,
            "policy_number": p.policy_number,
            "policy_type": p.policy_type,
            "customer_name": p.customer.name if p.customer else "",
            "customer_id": p.customer.customer_id if p.customer else "",
            "effective_date": p.effective_date.isoformat() if p.effective_date else None,
            "expiry_date": p.expiry_date.isoformat() if p.expiry_date else None,
            "claims_count": len(p.claims),
        }
        for p in policies
    ]

@router.get("/notifications", summary="List system notifications and fraud alerts")
async def list_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Fetch notifications for user or global alerts
    notifs = (
        db.query(Notification)
        .order_by(desc(Notification.created_at))
        .limit(20)
        .all()
    )
    return [
        {
            "id": n.id,
            "message": n.message,
            "read": n.read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notifs
    ]

@router.put("/notifications/{notification_id}/read", summary="Mark a notification as read")
async def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if notif:
        notif.read = True
        db.commit()
    return {"message": "Notification marked as read."}


@router.get("/notifications/unread-count", summary="Get the count of unread notifications for the current user")
async def get_unread_notification_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Global alerts are addressed to all users; personal ones are recipient-specific
    count = (
        db.query(Notification)
        .filter(
            Notification.read == False,
            (Notification.recipient_id == current_user.id) | (Notification.recipient_id.is_(None)),
        )
        .count()
    )
    return {"unread_count": count}
