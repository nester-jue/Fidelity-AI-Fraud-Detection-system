"""
NEXA Sample Claim Documents — Ingestion & OCR Tests (genuine public claim forms).

Covers: ingestion of the 12 genuine claim forms from data/sample_claim_documents,
document classification per category, OCR extraction sanity, the admin
dashboard endpoints (list + detail), and idempotency of the ingestor.

Run with: python -m pytest tests/test_sample_documents.py -v
"""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.services.db import init_db, SessionLocal
from backend.app.models.sqlalchemy_models import OCRDocument, User
from backend.app.auth import create_access_token
from backend.app.services.sample_documents import ingest_sample_documents

def _files_in(subdir: str) -> list:
    base = Path("data/sample_claim_documents")
    return sorted(p.name for p in (base / subdir).glob("*.pdf"))


# Category group sizes expected for the 12 ingested documents.
EXPECTED_CATEGORIES = {
    "funeral_claims": 3,
    "life_insurance": 2,
    "medical_insurance": 2,
    "hospitalisation": 2,
    "accident_disability": 3,
    "other": 0,
}

# Filename prefixes derived from the register's category directories.
FILENAME_PREFIX_CATEGORIES = [
    (f, "funeral_claims") for f in _files_in("funeral_claims")
] + [
    (f, "life_insurance") for f in _files_in("life_insurance")
] + [
    (f, "medical_insurance") for f in _files_in("medical_insurance")
] + [
    (f, "hospitalisation") for f in _files_in("hospitalisation")
] + [
    (f, "accident_disability") for f in _files_in("accident_disability")
]


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db()


@pytest.fixture(scope="session", autouse=True)
def seed_sample_documents():
    db = SessionLocal()
    try:
        ingest_sample_documents(db)
    finally:
        db.close()


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


def _sample_docs():
    db = SessionLocal()
    try:
        return db.query(OCRDocument).filter(OCRDocument.is_sample_document == True).all()  # noqa: E712
    finally:
        db.close()


def test_all_genuine_documents_ingested():
    docs = _sample_docs()
    assert len(docs) == 12, f"expected 12 ingested sample documents, got {len(docs)}"
    categories = {d.sample_category: 0 for d in docs}
    for d in docs:
        categories[d.sample_category] = categories.get(d.sample_category, 0) + 1
    for category, expected_count in EXPECTED_CATEGORIES.items():
        assert categories.get(category, 0) == expected_count, \
            f"expected {expected_count} documents in {category}, got {categories}"


def test_document_classification():
    db = SessionLocal()
    try:
        docs = db.query(OCRDocument).filter(OCRDocument.is_sample_document == True).all()  # noqa: E712
        by_name = {d.filename: d for d in docs}
        for prefix, category in FILENAME_PREFIX_CATEGORIES:
            matches = [n for n in by_name if n.startswith(prefix)]
            assert matches, f"missing ingested document matching {prefix}"
            for n in matches:
                assert by_name[n].sample_category == category, \
                    f"{n}: expected {category}, got {by_name[n].sample_category}"
    finally:
        db.close()


def test_ocr_extraction_results_populated():
    db = SessionLocal()
    try:
        docs = [d for d in db.query(OCRDocument).filter(OCRDocument.is_sample_document == True).all()]  # noqa: E712
        # All documents should have confidence and flags.
        for d in docs:
            assert d.confidence_score is not None
            assert d.flags is not None
        # Text extraction should succeed on all documents except the image-based Magma form.
        magma = [d for d in docs if d.filename.startswith("accident_disability_magma")]
        for d in docs:
            if d.filename.startswith("accident_disability_magma"):
                continue  # image-based PDF; extraction quality recorded in flags
            assert (d.raw_text or "").strip(), f"no extracted text for {d.filename}"
    finally:
        db.close()


def test_source_registration_read():
    from backend.app.services.sample_documents import parse_source_info, REGISTER_FILE

    assert REGISTER_FILE.exists()
    text = REGISTER_FILE.read_text(encoding="utf-8")
    # Register rows must carry institution + source URL for downloaded documents.
    assert "Fiji Care" in text and "fiji_care_funeral_benefit_claim_form.pdf" in text

    # parse_source_info reads the register for a real sample file.
    info = parse_source_info(Path("accident_disability_mua_personal_accident_claim_form.pdf"))
    assert info[0] and info[1].startswith("https://")


def test_api_list_sample_documents(client):
    headers = _headers_for("claims.officer")
    res = client.get("/ocr/sample-documents/", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 12
    first = data[0]
    assert first["is_sample_document"] is True
    assert first["sample_category"]
    assert first["source_url"]
    assert "raw_text_snippet" in first


def test_api_sample_document_detail(client):
    headers = _headers_for("claims.officer")
    docs = _sample_docs()
    res = client.get(f"/ocr/sample-documents/{docs[0].id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["sample_category"] == docs[0].sample_category


def test_api_sample_document_detail_404(client):
    headers = _headers_for("admin")
    res = client.get("/ocr/sample-documents/99999", headers=headers)
    assert res.status_code == 404


def test_api_sample_documents_role_scoping(client):
    for username in ("admin", "claims.officer", "claims.manager", "investigator", "compliance", "executive"):
        res = client.get("/ocr/sample-documents/", headers=_headers_for(username))
        assert res.status_code == 200, username


def test_ingest_idempotent():
    db = SessionLocal()
    try:
        count_before = db.query(OCRDocument).filter(OCRDocument.is_sample_document == True).count()  # noqa: E712
        result = ingest_sample_documents(db)
        assert result["errors"] == []
        count_after = db.query(OCRDocument).filter(OCRDocument.is_sample_document == True).count()  # noqa: E712
        assert count_before == count_after == 12
        assert result["skipped"] or not result["ingested"]
    finally:
        db.close()
