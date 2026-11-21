import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.db import init_db, SessionLocal
from backend.app.services import historical_behavior
from backend.app.models.sqlalchemy_models import Claim, ClaimBeneficiaryChange, ClaimNote
from tests.helpers import make_policy_and_claim, admin_headers, officer_headers
from fastapi.testclient import TestClient
from backend.app.main import app


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db()


def _unique(suffix):
    return suffix


def test_analyze_claim_vs_history_uses_real_records():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        cust_id = f"HB-CUST-{int(now.timestamp()) % 100000}"
        claim = make_policy_and_claim(db, cust_id, f"POL-HB-{cust_id}", f"CLM-HB-{cust_id}", amount=8000.0)
        analysis = historical_behavior.analyze_claim_vs_history(db, claim.id)
        assert analysis["claim"]["claim_id"] == claim.claim_id
        assert "previous_claims" in analysis
        assert "similar_historical_claims" in analysis
        assert "comparisons" in analysis
        assert "history_anomalies" in analysis
        assert analysis["claim"]["customer_id"] is not None
    finally:
        db.close()


def test_analyze_customer_history_detects_repeated_patterns():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        cust_id = f"HB-C2-{int(now.timestamp()) % 100000}"
        c1 = make_policy_and_claim(db, cust_id, f"POL-HB2-{cust_id}", f"CLM-HB2-1-{cust_id}", amount=9000.0)
        c2 = make_policy_and_claim(db, cust_id, f"POL-HB2-{cust_id}", f"CLM-HB2-2-{cust_id}", amount=9200.0)
        c3 = make_policy_and_claim(db, cust_id, f"POL-HB2-{cust_id}", f"CLM-HB2-3-{cust_id}", amount=9400.0)
        # Claims use Claim.customer_id (the FK), not the Customer.customer_id string.
        fk_id = c1.customer_id
        stats = historical_behavior.compute_customer_claim_stats(db, fk_id)
        assert stats["claim_count"] >= 2
        history = historical_behavior.analyze_customer_history(db, fk_id, current_claim_id=c3.id)
        assert history["claim_count_excluded_current"] >= 2
        assert isinstance(history["anomalies"], list)
    finally:
        db.close()


def test_similar_claims_detection():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        cust_id = f"HB-C3-{int(now.timestamp()) % 100000}"
        claim = make_policy_and_claim(db, cust_id, f"POL-HB3-{cust_id}", f"CLM-HB3-{cust_id}", amount=9000.0)
        db.query(Claim).filter(Claim.id == claim.id).update({"description": "Third party death claim payout"})
        db.commit()
        similar = historical_behavior.find_similar_historical_claims(db, claim)
        assert isinstance(similar, list)
    finally:
        db.close()


def test_historical_api_endpoints(client=TestClient(app)):
    db = SessionLocal()
    try:
        claim = db.query(Claim).first()
        if not claim:
            claim = make_policy_and_claim(db, "HB-C4", "POL-HB4", "CLM-HB4")
        res = client.get(f"/historical/claim/{claim.claim_id}", headers=officer_headers())
        assert res.status_code == 200
        assert "previous_claims" in res.json()
        res2 = client.get(f"/historical/claim/CLM-HB4-NOT", headers=officer_headers())
        assert res2.status_code == 404
        res3 = client.get(f"/historical/customer/{claim.customer_id}", headers=admin_headers())
        assert res3.status_code == 200
        assert "stats" in res3.json()
    finally:
        db.close()
