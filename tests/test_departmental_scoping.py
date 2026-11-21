"""
NEXA Departmental Access Restrictions — Backend Tests (Phase 3)

Claims Managers are scoped to the Claims department (claims assigned to Claims
officers or unassigned); Claims Officers see their own + unassigned claims;
claim-detail queries respect the same scoping.

Run with: python -m pytest tests/test_departmental_scoping.py -v
"""
import os
import sys
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.services.db import init_db, SessionLocal
from backend.app.models.sqlalchemy_models import Claim, FraudAssessment, User
from backend.app.auth import create_access_token

TEST_CLAIM_IDS = ["CLM-SCOPETEST-DEPT", "CLM-SCOPETEST-FOREIGN", "CLM-SCOPETEST-UNASSIGNED"]


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db()


@pytest.fixture
def client():
    return TestClient(app)


def _headers_for(username: str) -> dict:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        assert user is not None, f"test user '{username}' not found in database"
        token = create_access_token(
            data={"sub": user.username, "role": user.role.value, "user_id": user.id}
        )
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


def _manager():
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == "claims.manager").first()
    finally:
        db.close()


def _create_test_claims():
    """Creates (idempotently) one Claims-dept claim (assigned to the Claims
    Officer), one foreign-dept claim (assigned to the Fraud Investigator), and
    one unassigned claim; the first two get High fraud assessments."""
    db = SessionLocal()
    try:
        # Idempotent setup: remove leftovers from prior partial runs
        # (including assessments orphaned by earlier runs).
        removed_ids = [r[0] for r in db.query(Claim.id).filter(Claim.claim_id.in_(TEST_CLAIM_IDS)).all()]
        db.query(FraudAssessment).filter(FraudAssessment.claim_id.in_(removed_ids)).delete(synchronize_session=False)
        db.query(Claim).filter(Claim.id.in_(removed_ids)).delete(synchronize_session=False)
        # Delete orphaned assessments (claim_id not backed by any claim) —
        # their claim ids get reused by new claims and would collide.
        db.query(FraudAssessment).filter(
            FraudAssessment.claim_id.not_in(select(Claim.id))
        ).delete(synchronize_session=False)
        db.commit()

        officer = db.query(User).filter(User.username == "claims.officer").first()
        investigator = db.query(User).filter(User.username == "investigator").first()
        assert officer and investigator

        template = db.query(Claim).first()
        assert template is not None, "no seeded claims available for test setup"

        base = {
            "policy_id": template.policy_id,
            "customer_id": template.customer_id,
            "claim_type": "Death",
            "amount": 50000.0,
            "incident_date": datetime.now(timezone.utc),
            "submission_date": datetime.now(timezone.utc),
        }
        c_dept = Claim(claim_id="CLM-SCOPETEST-DEPT", assigned_officer_id=officer.id,
                       status="flagged", **base)
        c_foreign = Claim(claim_id="CLM-SCOPETEST-FOREIGN", assigned_officer_id=investigator.id,
                          status="flagged", **base)
        c_unassigned = Claim(claim_id="CLM-SCOPETEST-UNASSIGNED", status="submitted", **base)
        for c in (c_dept, c_foreign, c_unassigned):
            db.add(c)
        db.flush()
        for c in (c_dept, c_foreign):
            db.add(FraudAssessment(claim_id=c.id, risk_score=90.0, risk_category="High",
                                   indicators=[], model_version="v1.0-fidelity-rf-iso"))
        db.commit()
        created = [c_dept.id, c_foreign.id, c_unassigned.id]
    finally:
        db.close()
    return created


def _cleanup():
    db = SessionLocal()
    try:
        removed_ids = [r[0] for r in db.query(Claim.id).filter(Claim.claim_id.in_(TEST_CLAIM_IDS)).all()]
        if removed_ids:
            db.query(FraudAssessment).filter(FraudAssessment.claim_id.in_(removed_ids)).delete(synchronize_session=False)
            db.query(Claim).filter(Claim.id.in_(removed_ids)).delete(synchronize_session=False)
            db.commit()
    finally:
        db.close()


@pytest.fixture
def scoped_claims():
    _create_test_claims()
    yield
    _cleanup()


# 1. Unit — Claims Managers do not see other departments' claims
def test_manager_scope_excludes_foreign_claims(scoped_claims):
    from backend.app.api.chatbot import _officer_claims_query

    db = SessionLocal()
    try:
        manager = _manager()
        visible_ids = {c.id for c in _officer_claims_query(db, manager).all()}
        dept = db.query(Claim).filter(Claim.claim_id == "CLM-SCOPETEST-DEPT").first()
        foreign = db.query(Claim).filter(Claim.claim_id == "CLM-SCOPETEST-FOREIGN").first()
        unassigned = db.query(Claim).filter(Claim.claim_id == "CLM-SCOPETEST-UNASSIGNED").first()
        assert dept is not None and foreign is not None and unassigned is not None
        assert dept.id in visible_ids, "manager should see Claims-dept claim"
        assert unassigned.id in visible_ids, "manager should see unassigned claim"
        assert foreign.id not in visible_ids, "manager must not see other departments' claims"
    finally:
        db.close()


# 2. Unit — manager performance + fraud visibility exclude foreign claims
def test_manager_performance_excludes_foreign_claims(scoped_claims):
    from backend.app.api.chatbot import _department_performance, _officer_claims_query

    db = SessionLocal()
    try:
        manager = _manager()
        perf = _department_performance(db, manager)
        visible_ids = {c.id for c in _officer_claims_query(db, manager).all()}
        foreign = db.query(Claim).filter(Claim.claim_id == "CLM-SCOPETEST-FOREIGN").first()
        assert foreign.id not in visible_ids
        # The foreign High claim must not be part of the department view.
        high_claim_ids = {
            a.claim_id for a in db.query(FraudAssessment).filter(
                FraudAssessment.claim_id.in_(visible_ids),
                FraudAssessment.risk_category.in_(["High", "Critical"]),
            )
        }
        assert foreign.id not in high_claim_ids
        assert perf["department_claims_total"] >= 1
        # Foreign claim has no visible fraud assessment for the manager.
        assert not db.query(FraudAssessment).filter(
            FraudAssessment.claim_id == foreign.id, FraudAssessment.claim_id.in_(visible_ids)
        ).first()
    finally:
        db.close()


# 3. Unit — claim detail is blocked for out-of-department claims (manager)
def test_manager_cannot_view_foreign_claim_detail(scoped_claims):
    from backend.app.api.chatbot import _get_claim_visible

    db = SessionLocal()
    try:
        manager = _manager()
        assert _get_claim_visible(db, manager, "CLM-SCOPETEST-FOREIGN") is None
        assert _get_claim_visible(db, manager, "CLM-SCOPETEST-DEPT") is not None
    finally:
        db.close()


# 4. API — manager chatbot answers cannot see foreign claims
def test_manager_chatbot_blocks_foreign_claim(client, scoped_claims):
    headers = _headers_for("claims.manager")
    res = client.post(
        "/chatbot/messages",
        json={"message": "What is the status of claim CLM-SCOPETEST-FOREIGN?"},
        headers=headers,
    )
    assert res.status_code == 200
    assert "could not find an accessible claim" in res.json()["response"].lower()
    # And the department claim is reachable from the manager.
    res2 = client.post(
        "/chatbot/messages",
        json={"message": "What is the status of claim CLM-SCOPETEST-DEPT?"},
        headers=headers,
    )
    assert res2.status_code == 200
    assert "CLM-SCOPETEST-DEPT" in res2.json()["response"]
