import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.db import init_db, SessionLocal
from backend.app.services import claim_timeline
from backend.app.models.sqlalchemy_models import (
    Claim, FraudAssessment, Investigation,
)
from tests.helpers import make_policy_and_claim as _make_policy_and_claim, admin_headers


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    return TestClient(app)


def test_timeline_for_claim_with_events():
    db = SessionLocal()
    try:
        claim = db.query(Claim).filter(Claim.claim_id == "CLM-NET-N1").first()
        if not claim:
            claim = _make_policy_and_claim(db, "TL-1", "POL-TL-1", "CLM-TL-1")
        data = claim_timeline.build_claim_timeline(db, claim.id)
        assert data["claim_id"] == claim.id
        assert data["summary"]["total_events"] >= 1
        types = {e["event_type"] for e in data["events"]}
        assert "incident_occurred" in types
        assert "claim_submitted" in types
        # Timeline is chronological
        timestamps = [e["timestamp"] for e in data["events"]]
        assert timestamps == sorted(timestamps)
    finally:
        db.close()


def test_timeline_includes_real_records():
    db = SessionLocal()
    try:
        claim = db.query(Claim).filter(Claim.claim_id == "CLM-NET-N1").first()
        data = claim_timeline.build_claim_timeline(db, claim.id)
        types = {e["event_type"] for e in data["events"]}
        assert "incident_occurred" in types
        assert "claim_submitted" in types
        assert "policy_activated" in types or claim.policy is None
        if claim.documents:
            assert "documents_submitted" in types
        # Missing steps are detected, never fabricated
        assert isinstance(data["summary"]["missing_steps"], list)
        # Anomalies are findings, never fabricated events
        assert all(a["anomaly_id"] for a in data["anomalies"])
    finally:
        db.close()


def test_timeline_missing_steps_detected():
    db = SessionLocal()
    try:
        claim = db.query(Claim).filter(Claim.claim_id == "CLM-NET-N1").first()
        data = claim_timeline.build_claim_timeline(db, claim.id)
        assert isinstance(data["summary"]["missing_steps"], list)
        # Every event must have a real timestamp source
        valid_types = {t for t, _ in claim_timeline.EVENT_ORDER} | {"investigation_actions"}
        for e in data["events"]:
            assert e["source"]
            assert e["event_type"] in valid_types
        # The claim without documents should be flagged as a missing step
        assert "DOCUMENT_SUBMISSION" in data["summary"]["missing_steps"] or claim.documents
    finally:
        db.close()


def test_timeline_api_endpoint(client):
    res = client.get("/timeline/CLM-NET-N1", headers=admin_headers())
    assert res.status_code == 200
    assert "events" in res.json()
    assert "anomalies" in res.json()
    assert "summary" in res.json()
    res2 = client.get("/timeline/does-not-exist", headers=admin_headers())
    assert res2.status_code == 404
