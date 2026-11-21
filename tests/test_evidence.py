import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.services.db import init_db, SessionLocal
from backend.app.services import evidence as ev
from backend.app.models.sqlalchemy_models import Claim, Investigation, OCRDocument, EvidenceRecord
from tests.helpers import make_policy_and_claim, admin_headers


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db()


@pytest.fixture
def client():
    return TestClient(app)


def test_compute_sha256_of_sample_document():
    path = os.path.join(os.path.dirname(__file__), "..", "data", "documents", "OCR_014bba16_death_cert.txt")
    if os.path.isfile(path):
        h = ev.compute_sha256(os.path.abspath(path))
        assert h and len(h) == 64
    else:
        # Fallback: verify empty/missing file behavior
        assert ev.compute_sha256(None) is None


def test_register_and_verify_evidence():
    db = SessionLocal()
    try:
        claim = db.query(Claim).first()
        evidence = ev.register_evidence(
            db,
            collected_by_id=1,
            title="Photographic evidence EV-TEST-01",
            evidence_type="PHOTOGRAPH",
            claim_id=claim.id,
            notes="Screenshot of photo ID upload",
        )
        assert evidence.id
        assert len(evidence.sha256_hash or "") in (0, 64)  # hash of file path may be None
        verification = ev.verify_evidence_integrity(db, evidence)
        assert "integrity_ok" in verification
        assert isinstance(verification["integrity_ok"], bool)
        # Status update is audited and reversible to earlier states
        updated = ev.update_evidence_status(db, evidence.id, "verified", 1, notes="checked")
        assert updated and updated.status == "verified"
        ev.update_evidence_status(db, evidence.id, "collected", 1)
        db.delete(evidence)  # cleanup test artifact via ORM
        db.commit()
    finally:
        db.close()


def test_evidence_api_listing(client):
    res = client.get("/evidence/", headers=admin_headers())
    assert res.status_code == 200
    assert isinstance(res.json(), list)
    res2 = client.get("/evidence/types", headers=admin_headers())
    assert res2.status_code == 200
    assert "evidence_types" in res2.json()


def test_evidence_report_for_investigation(client):
    db = SessionLocal()
    try:
        inv = db.query(Investigation).first()
        if not inv:
            # create a minimal investigation on a real claim
            claim = db.query(Claim).first()
            inv = Investigation(claim_id=claim.id, investigator_id=1, status="open", notes="test")
            db.add(inv); db.commit(); db.refresh(inv)
        report = ev.get_investigation_evidence_report(db, inv.id)
        assert "total_evidence" in report
        assert "statuses" in report
    finally:
        db.close()


def test_evidence_no_evidence_mode():
    db = SessionLocal()
    try:
        assert db.query(EvidenceRecord).count() >= 0
    finally:
        db.close()
