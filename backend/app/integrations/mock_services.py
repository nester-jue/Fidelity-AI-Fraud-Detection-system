"""Read-only adapters to NEXA's system-of-record tables.

Earlier revisions of this module generated random policies, customers and
claim histories, which could be persisted as if they were genuine records.
That behaviour has been removed. These adapters return only records that
exist in the configured database (or in an external system when one is
configured); missing records yield empty results, never invented values.

External integrations are intentionally opt-in: set POLICY_SYSTEM_URL (and
optional POLICY_SYSTEM_TOKEN) to read policy/customer data from an
OpenAPI-compatible policy administration service. Without that configuration
the adapters use the local operational tables, which are the system of record
for this deployment.
"""
import os
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..services.db import SessionLocal
from ..models.sqlalchemy_models import Claim, Customer, Policy


def _external_get(path: str) -> Optional[Dict[str, Any]]:
    base = os.getenv("POLICY_SYSTEM_URL", "").rstrip("/")
    if not base:
        return None
    try:
        import httpx

        headers = {}
        token = os.getenv("POLICY_SYSTEM_TOKEN", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = httpx.get(f"{base}{path}", headers=headers, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception:
        # An unavailable external system must not be replaced with synthetic
        # data. Callers see no record and report the lookup as unresolved.
        return None


def _session(db: Optional[Session]):
    return db or SessionLocal()


def _close_if_owned(db: Optional[Session], session: Session):
    if db is None:
        session.close()


class PolicyService:
    def get_policy(self, policy_number: str, db: Optional[Session] = None) -> Dict[str, Any]:
        external = _external_get(f"/policies/{policy_number}")
        if external is not None:
            return external
        session = _session(db)
        try:
            policy = session.query(Policy).filter(Policy.policy_number == policy_number).first()
            if not policy:
                return {}
            return {
                "policy_number": policy.policy_number,
                "policy_type": policy.policy_type,
                "effective_date": policy.effective_date.date().isoformat() if policy.effective_date else None,
                "expiry_date": policy.expiry_date.date().isoformat() if policy.expiry_date else None,
                "customer_id": policy.customer.customer_id if policy.customer else None,
                "coverage_amount": None,  # not stored in the operational schema
            }
        finally:
            _close_if_owned(db, session)


class CustomerService:
    def get_customer(self, customer_id: str, db: Optional[Session] = None) -> Dict[str, Any]:
        external = _external_get(f"/customers/{customer_id}")
        if external is not None:
            return external
        session = _session(db)
        try:
            customer = session.query(Customer).filter(Customer.customer_id == customer_id).first()
            if not customer:
                return {}
            return {
                "customer_id": customer.customer_id,
                "name": customer.name,
                "national_id": customer.national_id,
                "date_of_birth": customer.date_of_birth.date().isoformat() if customer.date_of_birth else None,
            }
        finally:
            _close_if_owned(db, session)


class ClaimsService:
    def list_previous_claims(self, policy_number: str, db: Optional[Session] = None) -> List[Dict[str, Any]]:
        external = _external_get(f"/policies/{policy_number}/claims")
        if external is not None and isinstance(external, list):
            return external
        session = _session(db)
        try:
            policy = session.query(Policy).filter(Policy.policy_number == policy_number).first()
            if not policy:
                return []
            claims = session.query(Claim).filter(Claim.policy_id == policy.id).order_by(Claim.incident_date.desc()).all()
            return [{
                "claim_id": c.claim_id,
                "policy_number": policy_number,
                "claim_type": c.claim_type,
                "amount": c.amount,
                "incident_date": c.incident_date.date().isoformat() if c.incident_date else None,
                "submission_date": c.submission_date.date().isoformat() if c.submission_date else None,
                "status": c.status,
            } for c in claims]
        finally:
            _close_if_owned(db, session)


class PaymentService:
    def verify_payment(self, claim_id: str) -> Dict[str, Any]:
        """No payment gateway is configured; never claim a payment was verified."""
        return {"verified": False, "status": "NOT_CONFIGURED", "claim_id": claim_id}


class IdentityVerificationService:
    def verify_identity(self, national_id: str, name: str) -> Dict[str, Any]:
        """No external identity provider is configured in this deployment."""
        return {"verified": False, "status": "NOT_CONFIGURED"}
