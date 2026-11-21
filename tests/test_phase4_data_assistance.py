"""
NEXA Chatbot — Phase 4 Tests: assistance using existing system data.

Covers the new data-assistance capabilities: audit activity, notifications,
claim notes, management reports, user management, customers, policies, and
forensic/AI model performance. Run with: python -m pytest tests/test_phase4_data_assistance.py -v
"""
import os
import sys
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.services.db import init_db, SessionLocal
from backend.app.models.sqlalchemy_models import (
    Claim, ClaimNote, ManagementReport, RoleEnum, User,
)
from backend.app.auth import create_access_token


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
        assert user is not None
        token = create_access_token(
            data={"sub": user.username, "role": user.role.value, "user_id": user.id}
        )
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


def _ask(client, headers, message):
    return client.post("/chatbot/messages", json={"message": message}, headers=headers)


# 1. Audit activity (compliance/admin/management)
def test_audit_summary(client):
    res = _ask(client, _headers_for("admin"), "Show me the audit log activity.")
    assert res.status_code == 200
    assert "audit" in res.json()["response"].lower()


def test_audit_denied_for_officer(client):
    res = _ask(client, _headers_for("claims.officer"), "Show me the audit log activity.")
    assert res.status_code == 200
    assert "can't provide" in res.json()["response"]


# 2. Notifications (own)
def test_notifications(client):
    res = _ask(client, _headers_for("claims.officer"), "Show me my notifications.")
    assert res.status_code == 200
    assert "notification" in res.json()["response"].lower()


# 3. Claim notes (claims dept)
def test_claim_notes(client):
    db = SessionLocal()
    try:
        manager = db.query(User).filter(User.username == "claims.manager").first()
        claims = db.query(Claim).filter(
            Claim.assigned_officer_id.in_([
                u.id for u in db.query(User).filter(User.role == RoleEnum.CLAIMS_OFFICER).all()
            ])
        ).limit(1).all()
        if claims:
            db.add(ClaimNote(claim_id=claims[0].id, user_id=manager.id,
                             note="Phase 4 test note", created_at=datetime.now(timezone.utc)))
            db.commit()
            ref = claims[0].claim_id
        else:
            ref = None
    finally:
        db.close()
    if ref is None:
        pytest.skip("no claims assigned to claims officers in test DB")
    res = _ask(client, _headers_for("claims.manager"), f"Show my departmental notes for claim {ref}.")
    assert res.status_code == 200
    assert "note" in res.json()["response"].lower() or "no departmental notes" in res.json()["response"].lower()


# 4. Management reports (management/admin)
def test_management_reports(client):
    db = SessionLocal()
    try:
        if not db.query(ManagementReport).count():
            db.add(ManagementReport(
                generated_by_id=1,
                report_type="EXECUTIVE_KPI_SNAPSHOT",
                title="EXECUTIVE_KPI_SNAPSHOT — Phase 4 Test",
                summary={"claims_received": 10, "fraud_alerts_high_critical": 2},
                generated_at=datetime.now(timezone.utc),
            ))
            db.commit()
    finally:
        db.close()
    res = _ask(client, _headers_for("executive"), "Show my management reports.")
    assert res.status_code == 200
    assert "report" in res.json()["response"].lower()


# 5. User management (admin)
def test_user_counts(client):
    res = _ask(client, _headers_for("admin"), "How many users are active?")
    assert res.status_code == 200
    assert "user" in res.json()["response"].lower()


# 6. Customers (officer sees seeded customers)
def test_customer_details(client):
    res = _ask(client, _headers_for("claims.officer"), "Tell me about customer CUST-1001.")
    assert res.status_code == 200
    body = res.json()["response"]
    assert "CUST-1001" in body or "Mpofu" in body


def test_customer_not_found(client):
    res = _ask(client, _headers_for("claims.officer"), "Tell me about customer ZZNOMATCH123.")
    assert res.status_code == 200
    assert "could not find" in res.json()["response"].lower()


# 7. Policies
def test_policy_details(client):
    res = _ask(client, _headers_for("claims.officer"), "What is the coverage of policy POL-LIF-801294?")
    assert res.status_code == 200
    assert "POL-LIF-801294" in res.json()["response"]


# 8. Forensic/AI performance (investigator)
def test_forensic_performance(client):
    res = _ask(client, _headers_for("investigator"), "Show me model performance benchmarks.")
    assert res.status_code == 200
    body = res.json()["response"]
    assert "performance" in body.lower() or "risk breakdown" in body.lower()


def test_forensic_denied_for_officer(client):
    res = _ask(client, _headers_for("claims.officer"), "Show me the forensic queue.")
    assert res.status_code == 200
    assert "can't provide" in res.json()["response"]
