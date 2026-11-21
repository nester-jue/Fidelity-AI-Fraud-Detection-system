"""Shared fixtures/helpers for NEXA enterprise upgrade tests."""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.db import SessionLocal
from backend.app.models.sqlalchemy_models import (
    Customer, Policy, Claim, User,
)


def make_policy_and_claim(db, customer_id, policy_number, claim_id_ref,
                          amount=10000.0, incident_days_ago=200,
                          beneficiary_name=None, beneficiary_nin=None,
                          payment_refs=None, claim_type="Death Benefit"):
    """Creates customer + policy + claim with commit. Returns the Claim ORM object."""
    cust = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not cust:
        cust = Customer(customer_id=customer_id, name=f"Customer {customer_id}", national_id=None)
        db.add(cust)
        db.flush()
    pol = db.query(Policy).filter(Policy.policy_number == policy_number).first()
    if not pol:
        pol = Policy(policy_number=policy_number, policy_type=claim_type, customer_id=cust.id,
                     effective_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
                     expiry_date=datetime(2035, 1, 1, tzinfo=timezone.utc))
        db.add(pol)
        db.flush()
    claim = db.query(Claim).filter(Claim.claim_id == claim_id_ref).first()
    if not claim:
        claim = Claim(claim_id=claim_id_ref, policy_id=pol.id, customer_id=cust.id,
                      claim_type=claim_type, amount=amount,
                      incident_date=datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=incident_days_ago),
                      beneficiary_name=beneficiary_name, beneficiary_nin=beneficiary_nin,
                      payment_account_refs=payment_refs)
        db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


def new_db():
    return SessionLocal()


def admin_headers():
    from backend.app.auth import create_access_token
    return {"Authorization": "Bearer " + create_access_token(
        data={"sub": "admin", "role": "system_admin", "user_id": 1}
    )}


def officer_headers():
    from backend.app.auth import create_access_token
    return {"Authorization": "Bearer " + create_access_token(
        data={"sub": "claims.officer", "role": "claims_officer", "user_id": 2}
    )}


def investigator_headers():
    from backend.app.auth import create_access_token
    return {"Authorization": "Bearer " + create_access_token(
        data={"sub": "investigator", "role": "fraud_investigator", "user_id": 4}
    )}


def management_headers():
    from backend.app.auth import create_access_token
    return {"Authorization": "Bearer " + create_access_token(
        data={"sub": "executive", "role": "management", "user_id": 5}
    )}
