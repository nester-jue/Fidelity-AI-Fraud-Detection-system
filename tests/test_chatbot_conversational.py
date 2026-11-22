"""
NEXA AI Intelligence Assistant — Conversational Intelligence Tests.

Verifies natural-language conversational behavior:
- Intent recognition: greetings, gratitude, farewells, acknowledgements,
  follow-up questions, introductions.
- Conversation context maintenance ("Explain further" after a question).
- Personalised greetings (employee name, role).
- "Thank you" must never trigger the generic welcome introduction.
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.services.db import init_db, SessionLocal
from backend.app.models.sqlalchemy_models import User
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
        assert user is not None, f"test user '{username}' not found"
        token = create_access_token(
            data={"sub": user.username, "role": user.role.value, "user_id": user.id}
        )
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


def _clear_history(client, headers):
    client.delete("/chatbot/history", headers=headers)


# ── Intent recognition: greetings ────────────────────────────────────────

def test_greeting_hello(client):
    headers = _headers_for("claims.officer")
    _clear_history(client, headers)
    res = client.post("/chatbot/messages", json={"message": "Hello"}, headers=headers)
    assert res.status_code == 200
    body = res.json()["response"]
    assert "Hello" in body
    assert "NEXA AI Intelligence Assistant" in body


def test_greeting_good_morning(client):
    headers = _headers_for("claims.officer")
    _clear_history(client, headers)
    res = client.post("/chatbot/messages", json={"message": "Good morning"}, headers=headers)
    assert res.status_code == 200
    assert "Hello" in res.json()["response"]


def test_new_conversation_greeting(client):
    """A fresh conversation greets with a natural greeting."""
    headers = _headers_for("claims.officer")
    _clear_history(client, headers)
    res = client.post("/chatbot/messages", json={"message": "Hi"}, headers=headers)
    assert res.status_code == 200
    assert "Hello" in res.json()["response"]


# ── Gratitude — the core complaint: "Thank you" must not trigger the
#    generic welcome ──────────────────────────────────────────────────────

def test_gratitude_no_generic_welcome(client):
    headers = _headers_for("claims.officer")
    _clear_history(client, headers)
    res = client.post("/chatbot/messages", json={"message": "Thank you"}, headers=headers)
    assert res.status_code == 200
    body = res.json()["response"]
    assert "You're welcome" in body
    # The generic welcome must NOT appear for a thank-you.
    assert "Ask me anything about your work" not in body


def test_gratitude_thanks_a_lot(client):
    headers = _headers_for("claims.officer")
    _clear_history(client, headers)
    res = client.post("/chatbot/messages", json={"message": "Thanks a lot, that was helpful."}, headers=headers)
    assert res.status_code == 200
    assert "You're welcome" in res.json()["response"]


# ── Acknowledgements — short responses ───────────────────────────────────

def test_acknowledgement_okay(client):
    headers = _headers_for("claims.officer")
    _clear_history(client, headers)
    res = client.post("/chatbot/messages", json={"message": "Okay"}, headers=headers)
    assert res.status_code == 200
    body = res.json()["response"]
    assert len(body) < 100
    assert "You're welcome" not in body  # acknowledgements are not thanks


def test_acknowledgement_understood(client):
    headers = _headers_for("claims.officer")
    _clear_history(client, headers)
    res = client.post("/chatbot/messages", json={"message": "Understood"}, headers=headers)
    assert res.status_code == 200
    assert len(res.json()["response"]) < 100


# ── Farewells ────────────────────────────────────────────────────────────

def test_farewell_goodbye(client):
    headers = _headers_for("claims.officer")
    _clear_history(client, headers)
    res = client.post("/chatbot/messages", json={"message": "Goodbye"}, headers=headers)
    assert res.status_code == 200
    assert "goodbye" in res.json()["response"].lower()


def test_farewell_see_you_later(client):
    headers = _headers_for("claims.officer")
    _clear_history(client, headers)
    res = client.post("/chatbot/messages", json={"message": "See you later"}, headers=headers)
    assert res.status_code == 200
    assert "see you" in res.json()["response"].lower() or "bye" in res.json()["response"].lower()


# ── Questions — real data answers ────────────────────────────────────────

def test_question_fraud_explanation(client):
    headers = _headers_for("claims.officer")
    _clear_history(client, headers)
    res = client.post("/chatbot/messages", json={"message": "Why was this claim flagged?"}, headers=headers)
    assert res.status_code == 200
    body = res.json()["response"]
    assert len(body) > 0


def test_question_missing_documents(client):
    """A real question about missing documents is NOT captured by the
    follow-up classifier (which only matches context questions)."""
    headers = _headers_for("claims.officer")
    _clear_history(client, headers)
    res = client.post(
        "/chatbot/messages",
        json={"message": "Which documents are missing from my assigned claims?"},
        headers=headers,
    )
    assert res.status_code == 200
    assert len(res.json()["response"]) > 0


# ── Follow-ups — context-aware responses ─────────────────────────────────

def test_followup_explain_further(client):
    headers = _headers_for("claims.officer")
    _clear_history(client, headers)
    r1 = client.post("/chatbot/messages", json={"message": "Why was this claim flagged?"}, headers=headers)
    assert r1.status_code == 200
    r2 = client.post("/chatbot/messages", json={"message": "Explain further."}, headers=headers)
    assert r2.status_code == 200
    assert len(r2.json()["response"]) > 0


def test_followup_which_document_contains_inconsistency(client):
    headers = _headers_for("claims.officer")
    _clear_history(client, headers)
    res = client.post(
        "/chatbot/messages",
        json={"message": "Which document contains the inconsistency?"},
        headers=headers,
    )
    assert res.status_code == 200
    assert len(res.json()["response"]) > 0


# ── Personalisation ──────────────────────────────────────────────────────

def test_personalised_greeting_per_role(client):
    for username in ("claims.officer", "claims.manager", "investigator",
                     "compliance", "executive", "admin"):
        headers = _headers_for(username)
        _clear_history(client, headers)
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == username).first()
            expected_name = user.full_name or user.username
        finally:
            db.close()
        res = client.post("/chatbot/messages", json={"message": "Hello"}, headers=headers)
        assert res.status_code == 200
        assert expected_name in res.json()["response"], f"greeting should include {expected_name} for {username}"


# ── Conversational history persistence (existing behavior preserved) ─────

def test_conversation_context_maintained(client):
    """The backend loads previous messages for context — history persists."""
    headers = _headers_for("claims.officer")
    _clear_history(client, headers)
    client.post("/chatbot/messages", json={"message": "What is the status of my assigned claims?"}, headers=headers)
    entries = client.get("/chatbot/history", headers=headers).json()
    assert entries, "history should persist after a message is sent"
    assert any(e["direction"] == "user" for e in entries)
    assert any(e["direction"] == "assistant" for e in entries)
    client.delete("/chatbot/history", headers=headers)
