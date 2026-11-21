"""
NEXA Departmental AI Knowledge Base (RAG) — Backend Tests

Covers package seeding, departmental retrieval scoping, natural-question
answers from company knowledge, the disabled flag, and admin upload/search
endpoints. Run with: python -m pytest tests/test_knowledge_base.py -v
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.services.db import init_db, SessionLocal
from backend.app.models.sqlalchemy_models import KnowledgeDocument, User
from backend.app.auth import create_access_token
from backend.app.services.knowledge import search
from backend.app.services.knowledge.packages import seed_knowledge_packages


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db()


@pytest.fixture(scope="session", autouse=True)
def seed_packages(setup_database):
    db = SessionLocal()
    try:
        seed_knowledge_packages(db)
        # Seeding is idempotent; assert the store actually holds the packages.
        count = (
            db.query(KnowledgeDocument)
            .filter(KnowledgeDocument.doc_type == "package")
            .count()
        )
        assert count >= 7, f"expected >=7 knowledge packages in store, got {count}"
    finally:
        db.close()


def test_seed_is_idempotent():
    db = SessionLocal()
    try:
        result = seed_knowledge_packages(db)
        assert result["added"] == 0, f"expected 0 added on second run, got {result}"
        assert result["updated"] >= 0
    finally:
        db.close()


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


def _cleanup_doc(doc_id: int):
    db = SessionLocal()
    try:
        doc = db.get(KnowledgeDocument, doc_id)
        if doc:
            db.delete(doc)
            db.commit()
    finally:
        db.close()


# 1. Package seeding
def test_knowledge_packages_seeded_per_department():
    db = SessionLocal()
    try:
        packages = {d.department: d for d in db.query(KnowledgeDocument).filter(
            KnowledgeDocument.doc_type == "package"
        ).all()}
        for dept in ("claims_officer", "claims_manager", "fraud_investigator",
                     "compliance_officer", "executive_management", "system_admin", "shared"):
            assert dept in packages, f"missing knowledge package for {dept}"
            assert packages[dept].status == "verified"
            assert packages[dept].id
    finally:
        db.close()


# 2. Retrieval
def test_retrieval_finds_funeral_documents():
    db = SessionLocal()
    try:
        results = search(db, "What documents are required for a funeral claim?",
                         department="claims_officer", top_k=3)
        assert results, "expected retrieval results for funeral claim question"
        assert any("funeral" in (r.text or "").lower() for r in results)
    finally:
        db.close()


def test_retrieval_scoped_to_department():
    """A claims officer must not retrieve fraud-investigator-only knowledge."""
    db = SessionLocal()
    try:
        results = search(db, "identity fraud and duplicate claim detection",
                         department="claims_officer", top_k=5)
        docs = {r.document_id for r in results}
        if docs:
            doc_departments = {
                d.id: d.department for d in db.query(KnowledgeDocument)
                .filter(KnowledgeDocument.id.in_(docs)).all()
            }
            assert all(dep in ("claims_officer", "shared") for dep in doc_departments.values())
    finally:
        db.close()


# 3. Natural questions via the chatbot
def test_chatbot_natural_question_from_knowledge(client):
    headers = _headers_for("claims.officer")
    res = client.post(
        "/chatbot/messages",
        json={"message": "How do I register a new claim?"},
        headers=headers,
    )
    assert res.status_code == 200
    body = res.json()["response"]
    assert "claim" in body.lower()
    # With knowledge enabled the answer comes from company knowledge context.
    if settings.CHATBOT_KB_ENABLED:
        assert any(s["type"] == "knowledge" for s in res.json()["sources"]) or \
               "company knowledge" in body.lower()


# 4. KB disabled flag
def test_kb_disabled_returns_no_knowledge_sources(client, monkeypatch):
    monkeypatch.setattr(settings, "CHATBOT_KB_ENABLED", False)
    headers = _headers_for("claims.officer")
    res = client.post(
        "/chatbot/messages",
        json={"message": "What documents are required for a funeral claim?"},
        headers=headers,
    )
    assert res.status_code == 200
    assert all(s["type"] != "knowledge" for s in res.json()["sources"])


# 5. Admin endpoints
def test_knowledge_upload_requires_admin(client):
    headers = _headers_for("claims.officer")
    res = client.post(
        "/chatbot/documents",
        json={"title": "Test Doc", "content": "Some content", "department": "claims_officer"},
        headers=headers,
    )
    assert res.status_code == 403


def test_knowledge_upload_and_search_admin(client):
    headers = _headers_for("admin")
    res = client.post(
        "/chatbot/documents",
        json={"title": "Test Package Alpha", "content": "Unique keyword zephyr in the alpha test body",
              "department": "system_admin", "doc_type": "package"},
        headers=headers,
    )
    assert res.status_code == 200
    doc_id = res.json()["document_id"]
    try:
        assert res.json()["chunks_added"] >= 1

        # System admin can find it.
        res = client.get("/chatbot/documents/search", params={"q": "zephyr", "top_k": 50}, headers=headers)
        assert res.status_code == 200
        assert any("zephyr" in r["excerpt"] for r in res.json()["results"])

        # Knowledge endpoints are admin-only (scoping verified at the store level).
        officer = client.get("/chatbot/documents/search", params={"q": "zephyr", "top_k": 50},
                             headers=_headers_for("claims.officer"))
        assert officer.status_code == 403
    finally:
        _cleanup_doc(doc_id)


def test_knowledge_endpoints_require_auth(client):
    assert client.get("/chatbot/documents").status_code == 401
    assert client.post("/chatbot/documents", json={"title": "T", "content": "C"}).status_code == 401
    assert client.get("/chatbot/documents/search", params={"q": "x"}).status_code == 401
