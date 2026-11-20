import os
import sys
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

# Ensure root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.services.db import init_db, SessionLocal
from backend.app.models.sqlalchemy_models import User, RoleEnum, Claim, FraudAssessment, Investigation
from backend.app.auth import create_access_token, get_password_hash
from backend.app.ml.fraud_engine import fraud_engine
from backend.app.ocr.ocr_service import process_document

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db()

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def auth_headers():
    token = create_access_token(data={"sub": "admin", "role": "system_admin", "user_id": 1})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def officer_headers():
    token = create_access_token(data={"sub": "claims.officer", "role": "claims_officer", "user_id": 2})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def investigator_headers():
    token = create_access_token(data={"sub": "investigator", "role": "fraud_investigator", "user_id": 4})
    return {"Authorization": f"Bearer {token}"}

# 1. System Health & Info
def test_system_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

    res_root = client.get("/")
    assert res_root.status_code == 200
    if "application/json" in res_root.headers.get("content-type", ""):
        assert "Fidelity Life Assurance" in res_root.json()["organization"]
    else:
        assert "FIDELITY LIFE ASSURANCE" in res_root.text or "Fidelity Life" in res_root.text

# 2. Authentication & JWT Flow
def test_auth_login_success(client):
    res = client.post(
        "/auth/token",
        data={"username": "admin", "password": "AdminPass123!"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["role"] == "system_admin"

def test_auth_login_invalid(client):
    res = client.post(
        "/auth/token",
        data={"username": "admin", "password": "WrongPassword!"},
    )
    assert res.status_code == 401

def test_auth_me_profile(client, auth_headers):
    res = client.get("/auth/me", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["username"] == "admin"

# 3. Role-Based Access Control
def test_rbac_admin_route_restricted(client, officer_headers):
    # Claims officer cannot access admin user list
    res = client.get("/users/", headers=officer_headers)
    assert res.status_code == 403

def test_rbac_admin_route_allowed(client, auth_headers):
    res = client.get("/users/", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

# 4. Claims Submission & Workflow
def test_submit_claim_and_fetch(client, officer_headers):
    payload = {
        "policy_number": "POL-LIF-801294",
        "claim_type": "Death Benefit",
        "claim_amount": 28000.0,
        "incident_date": "2026-04-10",
        "description": "Automated test claim submission",
    }
    res = client.post("/claims/submit", data=payload, headers=officer_headers)
    assert res.status_code == 200
    claim_id = res.json()["claim_id"]
    assert claim_id.startswith("CLM-2026-")

    # Fetch claim
    detail_res = client.get(f"/claims/{claim_id}", headers=officer_headers)
    assert detail_res.status_code == 200
    data = detail_res.json()
    assert data["claim_id"] == claim_id
    assert data["amount"] == 28000.0

# 5. Duplicate Claim Detection Logic
def test_duplicate_claim_scoring():
    claim_data = {
        "claim_id": "TEST-DUP-02",
        "policy_number": "POL-TEST-001",
        "amount": 50000.0,
        "incident_date": "2026-05-15",
        "submission_date": "2026-05-20",
        "claim_type": "Death Benefit",
    }
    policy_data = {
        "policy_number": "POL-TEST-001",
        "coverage_amount": 100000.0,
        "effective_date": "2023-01-01",
    }
    customer_data = {"customer_id": "CUST-001", "national_id": "63-123456-A-00"}
    history = [
        {"claim_id": "TEST-DUP-01", "policy_number": "POL-TEST-001", "amount": 50000.0, "incident_date": "2026-05-15"}
    ]

    assessment = fraud_engine.evaluate_claim(
        claim_data=claim_data,
        policy_data=policy_data,
        customer_data=customer_data,
        historical_claims=history,
    )
    assert assessment["risk_score"] >= 50.0
    indicator_codes = [ind["code"] for ind in assessment["indicators"]]
    assert "DUPLICATE_CLAIM_DETECTED" in indicator_codes

# 6. Policy Inception Fraud Detection
def test_policy_inception_fraud_scoring():
    claim_data = {
        "claim_id": "TEST-INC-01",
        "policy_number": "POL-TEST-002",
        "amount": 40000.0,
        "incident_date": "2026-01-10",
        "submission_date": "2026-01-15",
        "claim_type": "Death Benefit",
    }
    policy_data = {
        "policy_number": "POL-TEST-002",
        "coverage_amount": 50000.0,
        "effective_date": "2026-01-01",  # 9 days before incident!
    }
    customer_data = {"customer_id": "CUST-002", "national_id": "63-999888-B-11"}

    assessment = fraud_engine.evaluate_claim(
        claim_data=claim_data,
        policy_data=policy_data,
        customer_data=customer_data,
        historical_claims=[],
    )
    assert assessment["risk_category"] in ["High", "Critical"]
    indicator_codes = [ind["code"] for ind in assessment["indicators"]]
    assert "EARLY_POLICY_INCEPTION_CLAIM" in indicator_codes

# 7. OCR Processing & Tampering Check
def test_ocr_processing_and_hash():
    # Test text file processing
    test_doc = "README.md"
    res = process_document(test_doc, expected_claim_data={"incident_date": "2026-05-10"})
    assert "document_hash_sha256" in res
    assert len(res["document_hash_sha256"]) == 64
    assert "document_type" in res

# 8. Investigation Case Management
def test_investigations_lifecycle(client, investigator_headers):
    # List investigations
    inv_res = client.get("/investigations/", headers=investigator_headers)
    assert inv_res.status_code == 200
    cases = inv_res.json()
    assert len(cases) > 0

    first_id = cases[0]["id"]
    # Update investigation
    update_res = client.put(
        f"/investigations/{first_id}",
        json={"status": "in_review", "notes": "Automated verification test completed by fraud investigator."},
        headers=investigator_headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["status"] == "in_review"

# 9. Dashboard Statistics & Overview
def test_dashboard_overview(client, auth_headers):
    res = client.get("/dashboard/overview", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "kpis" in data
    kpis = data["kpis"]
    assert kpis["total_claims_received"] >= 5
    assert kpis["claims_analysed_by_ai"] >= 5
    assert "risk_distribution" in data
    assert "recent_suspicious_claims" in data

# 10. FNOL Preliminary Intake Workflow
def test_fnol_workflow(client, officer_headers):
    # Test FNOL list
    list_res = client.get("/claims/fnol/list", headers=officer_headers)
    assert list_res.status_code == 200
    data = list_res.json()
    assert "fnol_intakes" in data

    # Test FNOL submission
    payload = {
        "policy_number": "POL-LIF-801294",
        "claimant_name": "Tendai Moyo",
        "event_type": "Death Benefit",
        "incident_date": "2026-05-10",
        "estimated_amount": 25000.0,
        "reporting_channel": "Branch Walk-In",
        "initial_notes": "Automated verification test of loss notification",
    }
    submit_res = client.post("/claims/fnol", data=payload, headers=officer_headers)
    assert submit_res.status_code == 200
    fnol_data = submit_res.json()
    assert "fnol_reference" in fnol_data
    assert fnol_data["fnol_reference"].startswith("FNOL-2026-")

# 11. Fraud Network Intelligence Graph
def test_network_graph_endpoint(client, auth_headers):
    res = client.get("/dashboard/network-graph", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "nodes" in data
    assert "links" in data
    assert "clusters" in data
    assert len(data["nodes"]) > 0

# 12. AI Model Governance & Metrics
def test_model_governance_endpoint(client, auth_headers):
    res = client.get("/dashboard/model-governance", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "active_model" in data
    assert "metrics" in data
    assert data["metrics"]["precision"] > 90.0
    assert "confusion_matrix" in data

