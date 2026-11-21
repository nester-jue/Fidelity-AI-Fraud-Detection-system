"""
NEXA AI Intelligence Assistant — Backend Tests

Covers authentication enforcement, role-based capability enforcement,
real-record data retrieval, conversation history persistence, and input
validation. Run with: python -m pytest tests/test_chatbot.py -v
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.services.db import init_db, SessionLocal
from backend.app.models.sqlalchemy_models import User, Claim, FraudAssessment
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
        assert user is not None, f"test user '{username}' not found in database"
        token = create_access_token(
            data={"sub": user.username, "role": user.role.value, "user_id": user.id}
        )
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


def _officer_user():
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == "claims.officer").first()
    finally:
        db.close()


# 1. Authentication
def test_chatbot_requires_authentication(client):
    assert client.get("/chatbot/suggested-questions").status_code == 401
    assert client.post("/chatbot/messages", json={"message": "Hello"}).status_code == 401
    assert client.get("/chatbot/history").status_code == 401
    assert client.delete("/chatbot/history").status_code == 401


# 2. Suggested questions per role
def test_chatbot_suggested_questions_per_role(client):
    for username, keyword in [
        ("claims.officer", "missing"),
        ("claims.manager", "outstanding"),
        ("investigator", "investigation"),
        ("compliance", "compliance"),
        ("executive", "organisation"),
        ("admin", "operational"),
    ]:
        res = client.get("/chatbot/suggested-questions", headers=_headers_for(username))
        assert res.status_code == 200, username
        questions = res.json()["questions"]
        assert questions, f"no suggested questions for {username}"
        assert any(keyword in q.lower() for q in questions), (username, questions)


# 3. Claims assistance (real records)
def test_chatbot_officer_missing_documents(client):
    res = client.post(
        "/chatbot/messages",
        json={"message": "Which documents are missing from my assigned claims?"},
        headers=_headers_for("claims.officer"),
    )
    assert res.status_code == 200
    data = res.json()
    assert "document" in data["response"].lower()
    assert data["ai_mode"] == "deterministic"
    assert data["suggestions"], "should include role-specific suggestions"


def test_chatbot_officer_claim_detail_visible(client):
    officer = _officer_user()
    db = SessionLocal()
    try:
        claim = (
            db.query(Claim)
            .filter((Claim.assigned_officer_id == officer.id) | (Claim.assigned_officer_id.is_(None)))
            .order_by(Claim.id.desc())
            .first()
        )
    finally:
        db.close()
    if claim is None:
        pytest.skip("no visible claims seeded in test database")

    res = client.post(
        "/chatbot/messages",
        json={"message": f"What is the status of claim {claim.claim_id}?"},
        headers=_headers_for("claims.officer"),
    )
    assert res.status_code == 200
    assert claim.claim_id in res.json()["response"]


def test_chatbot_officer_cannot_access_invisible_claim(client):
    officer = _officer_user()
    db = SessionLocal()
    try:
        claim = (
            db.query(Claim)
            .filter(Claim.assigned_officer_id.isnot(None), Claim.assigned_officer_id != officer.id)
            .order_by(Claim.id.desc())
            .first()
        )
    finally:
        db.close()
    if claim is None:
        pytest.skip("no other-assigned claims seeded in test database")

    res = client.post(
        "/chatbot/messages",
        json={"message": f"Explain why claim {claim.claim_id} received a critical fraud-risk score."},
        headers=_headers_for("claims.officer"),
    )
    assert res.status_code == 200
    body = res.json()["response"]
    assert "could not find an accessible claim" in body.lower()
    # No claim data (risk score, indicators, etc.) may leak to the officer.
    assert "risk score" not in body.lower()
    assert "AI explanation" not in body


def test_chatbot_officer_fraud_explanation_visible(client):
    officer = _officer_user()
    db = SessionLocal()
    try:
        claim = (
            db.query(Claim)
            .join(FraudAssessment, FraudAssessment.claim_id == Claim.id)
            .filter(
                (Claim.assigned_officer_id == officer.id) | (Claim.assigned_officer_id.is_(None)),
                FraudAssessment.risk_category.in_(["High", "Critical"]),
            )
            .order_by(FraudAssessment.risk_score.desc())
            .first()
        )
    finally:
        db.close()
    if claim is None:
        pytest.skip("no High/Critical visible claims seeded in test database")

    res = client.post(
        "/chatbot/messages",
        json={"message": f"Explain why claim {claim.claim_id} received a critical fraud-risk score."},
        headers=_headers_for("claims.officer"),
    )
    assert res.status_code == 200
    body = res.json()["response"]
    assert claim.claim_id in body
    assert "risk score" in body.lower()


# 4. Role enforcement — denied capabilities
def test_chatbot_officer_cannot_access_management_summary(client):
    res = client.post(
        "/chatbot/messages",
        json={"message": "Summarise the claims performance of the organisation."},
        headers=_headers_for("claims.officer"),
    )
    assert res.status_code == 200
    body = res.json()["response"]
    assert "can't provide" in body
    # Denials must not disclose the user's permitted capabilities/functions.
    assert "permitted functions" not in body
    assert "Your role" not in body


def test_chatbot_officer_cannot_access_investigations(client):
    res = client.post(
        "/chatbot/messages",
        json={"message": "Show me my open investigations."},
        headers=_headers_for("claims.officer"),
    )
    assert res.status_code == 200
    assert "can't provide" in res.json()["response"]


# 5. Role-appropriate answers for other roles
def test_chatbot_management_summary(client):
    res = client.post(
        "/chatbot/messages",
        json={"message": "Provide a management summary of the organisation's performance."},
        headers=_headers_for("executive"),
    )
    assert res.status_code == 200
    body = res.json()["response"]
    assert "claims received" in body.lower()
    assert "ai coverage rate" in body.lower()


def test_chatbot_investigator_sees_investigations(client):
    res = client.post(
        "/chatbot/messages",
        json={"message": "Show me my open investigations."},
        headers=_headers_for("investigator"),
    )
    assert res.status_code == 200
    assert "investigation case" in res.json()["response"].lower()


def test_chatbot_compliance_sees_compliance(client):
    res = client.post(
        "/chatbot/messages",
        json={"message": "Summarise the latest audit observations."},
        headers=_headers_for("compliance"),
    )
    assert res.status_code == 200
    assert "compliance summary" in res.json()["response"].lower()


def test_chatbot_claims_manager_departmental_performance(client):
    res = client.post(
        "/chatbot/messages",
        json={"message": "What is the processing performance of my Claims department?"},
        headers=_headers_for("claims.manager"),
    )
    assert res.status_code == 200
    body = res.json()["response"]
    assert "claims department performance" in body.lower()


# 6. History persistence
def test_chatbot_history_roundtrip(client):
    headers = _headers_for("claims.officer")
    res = client.post(
        "/chatbot/messages",
        json={"message": "What is the status of my assigned claims?"},
        headers=headers,
    )
    assert res.status_code == 200

    entries = client.get("/chatbot/history", headers=headers).json()
    assert any(e["direction"] == "user" for e in entries)
    assert any(e["direction"] == "assistant" for e in entries)
    assert all(e["content"] for e in entries)

    res = client.delete("/chatbot/history", headers=headers)
    assert res.status_code == 200
    assert client.get("/chatbot/history", headers=headers).json() == []


# 7. Input validation
def test_chatbot_message_validation(client):
    headers = _headers_for("claims.officer")
    assert client.post("/chatbot/messages", json={"message": ""}, headers=headers).status_code == 422
    assert client.post("/chatbot/messages", json={"message": "x" * 2500}, headers=headers).status_code == 422


# 8. General assistant fallback
def test_chatbot_general_fallback_for_officer(client):
    res = client.post(
        "/chatbot/messages",
        json={"message": "Something unrelated to the platform."},
        headers=_headers_for("claims.officer"),
    )
    assert res.status_code == 200
    assert "Hello" in res.json()["response"]
