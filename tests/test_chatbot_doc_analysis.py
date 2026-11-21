"""
NEXA Chatbot — Document Analysis tests (Phase 8).

The forensics-chatbot answers document-level analysis questions (duplicates,
inconsistencies) — chatbot documents analysis.

Run with: python -m pytest tests/test_chatbot_doc_analysis.py -v
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.services.db import init_db
from backend.app.models.sqlalchemy_models import User
from backend.app.auth import create_access_token


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db()


@pytest.fixture
def client():
    return TestClient(app)


def _headers_for(username: str) -> dict:
    from backend.app.services.db import SessionLocal
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


def test_chatbot_document_analysis(client):
    res = client.post(
        "/chatbot/messages",
        json={"message": "Show me the document analysis for duplicates and inconsistencies."},
        headers=_headers_for("investigator"),
    )
    assert res.status_code == 200
    body = res.json()["response"]
    assert "duplicate" in body.lower() or "consistency" in body.lower() or "suspicious" in body.lower()


def test_chatbot_document_analysis_forensics_handler_denied_for_officer(client):
    res = client.post(
        "/chatbot/messages",
        json={"message": "Show me the document analysis for duplicates."},
        headers=_headers_for("claims.officer"),
    )
    assert res.status_code == 200
    assert "can't provide" in res.json()["response"]
