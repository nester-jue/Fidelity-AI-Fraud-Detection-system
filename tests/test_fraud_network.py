import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.services.db import init_db, SessionLocal
from backend.app.services import fraud_network
from backend.app.models.sqlalchemy_models import Customer, Policy, Claim, OCRDocument, User, RoleEnum
from tests.helpers import make_policy_and_claim as _make_policy_and_claim, admin_headers, officer_headers


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db()


@pytest.fixture
def client():
    return TestClient(app)


def test_network_build_and_identical_document_edge(client):
    db = SessionLocal()
    try:
        claim = _make_policy_and_claim(db, "NET-N1", "POL-NET-N1", "CLM-NET-N1",
                                       beneficiary_name="Net Beneficial")
        dup_path = os.path.join(os.path.dirname(__file__), "..", "data", "documents", "OCR_014bba16_death_cert.txt")
        for i in range(2):
            doc = OCRDocument(claim_id=claim.id, uploaded_by_id=1,
                              filename=f"net_dup_{i}.txt", file_path=os.path.abspath(dup_path),
                              mime_type="text/plain", document_hash_sha256="netduphash123",
                              raw_text="death certificate text net test", document_type="Death Certificate",
                              processing_status="completed")
            db.add(doc)
        db.commit()

        net = fraud_network.build_fraud_network(db)
        assert net["summary"]["total_nodes"] > 0
        assert net["summary"]["total_edges"] > 0
        dup_edges = [e for e in net["edges"] if e["relationship_type"] == "IDENTICAL_DOCUMENT_REUSE"]
        assert len(dup_edges) >= 1
        assert dup_edges[0]["is_suspicious"] is True
        # Policy and customer nodes exist
        types = {n["entity_type"] for n in net["nodes"]}
        assert {"customer", "policy", "claim"} <= types
        # Endpoint smoke tests
        res = client.get("/fraud-network/insights", headers=admin_headers())
        assert res.status_code == 200
        assert "summary" in res.json()
        res = client.get("/fraud-network/claim/CLM-NET-N1", headers=admin_headers())
        assert res.status_code == 200
        assert res.json()["edges"] or res.json()["nodes"]
    finally:
        db.close()


def test_network_shared_beneficiary_edge(client):
    db = SessionLocal()
    try:
        # Two customers with same beneficiary name across different policies
        claim_a = db.query(Claim).filter(Claim.claim_id == "CLM-NET-A").first()
        if not claim_a:
            claim_a = _make_policy_and_claim(db, "NET-A", "POL-NET-A", "CLM-NET-A",
                                             beneficiary_name="Shared Beneficiary")
        claim_b = db.query(Claim).filter(Claim.claim_id == "CLM-NET-B").first()
        if not claim_b:
            claim_b = _make_policy_and_claim(db, "NET-B", "POL-NET-B", "CLM-NET-B",
                                             beneficiary_name="Shared Beneficiary")
        net = fraud_network.build_fraud_network(db)
        ben_edges = [e for e in net["edges"]
                     if e["relationship_type"] in ("SHARED_BENEFICIARY_ACROSS_POLICIES", "BENEFICIARY_OF_CLAIM", "BENEFICIARY_OF_CUSTOMER")]
        assert ben_edges, "Expected beneficiary relationship edges"
        # Endpoint smoke test
        res = client.get("/fraud-network/graph", headers=officer_headers())
        assert res.status_code == 200
        assert "nodes" in res.json() and "edges" in res.json()
    finally:
        db.close()
