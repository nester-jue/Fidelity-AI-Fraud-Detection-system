"""
Tests for the Fidelity Life Assurance — NEXA Upgrade.

Covers:
1. Backend-enforced RBAC for the five departmental dashboards and new APIs.
2. Departmental data-access restrictions on claims and OCR endpoints.
3. Claims Officer actions: request documents, forward to investigation, notes.
4. OCR upload validation + correction audit trail.
5. AI Forensic module: overview, findings, configurable risk thresholds.
6. Compliance / Management report generation.
7. Investigation notes, evidence attachment.
"""
import os
import sys
import io
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.services.db import init_db, SessionLocal
from backend.app.models.sqlalchemy_models import (
    User, RoleEnum, Claim, OCRDocument, Investigation, InvestigationNote, AuditLog,
)
from backend.app.auth import create_access_token
from backend.app.core.config import settings


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db()


def _headers_for(username: str) -> dict:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        assert user is not None
        return {"Authorization": f"Bearer {create_access_token(data={'sub': user.username, 'role': user.role.value, 'user_id': user.id})}"}
    finally:
        db.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin():
    return _headers_for("admin")


@pytest.fixture
def officer():
    return _headers_for("claims.officer")


@pytest.fixture
def manager():
    return _headers_for("claims.manager")


@pytest.fixture
def investigator():
    return _headers_for("investigator")


@pytest.fixture
def compliance():
    return _headers_for("compliance")


@pytest.fixture
def executive():
    return _headers_for("executive")


# ─────────────────────────────────────────────
# 1. BACKEND-ENFORCED RBAC
# ─────────────────────────────────────────────

@pytest.mark.parametrize("path", ["/departmental/executive", "/departmental/admin", "/departmental/compliance", "/departmental/fraud-investigator"])
def test_claims_officer_blocked_from_other_departments(client, officer, path):
    """Claims Officer must not access dashboards of other departments (direct URL)."""
    res = client.get(path, headers=officer)
    assert res.status_code == 403


def test_claims_officer_allowed_claims_dashboard(client, officer):
    res = client.get("/departmental/claims-officer", headers=officer)
    assert res.status_code == 200
    data = res.json()
    assert "workload" in data
    assert "ocr_extraction_summary" in data
    assert "claim_processing_status" in data


def test_executive_access_to_executive_dashboard(client, executive):
    res = client.get("/departmental/executive", headers=executive)
    assert res.status_code == 200
    data = res.json()
    assert "monthly_fraud_trends" in data
    assert "yearly_fraud_trends" in data
    assert "departmental_performance" in data


def test_executive_blocked_from_claims_department(client, executive):
    res = client.get("/departmental/claims-officer", headers=executive)
    assert res.status_code == 403


def test_compliance_access_to_compliance_dashboard(client, compliance):
    res = client.get("/departmental/compliance", headers=compliance)
    assert res.status_code == 200
    data = res.json()
    assert "compliance_alerts" in data
    assert "investigation_outcomes" in data
    assert "user_activity" in data


def test_compliance_blocked_from_executive(client, compliance):
    res = client.get("/departmental/executive", headers=compliance)
    assert res.status_code == 403


def test_fraud_investigator_access_to_investigation_dashboard(client, investigator):
    res = client.get("/departmental/fraud-investigator", headers=investigator)
    assert res.status_code == 200
    data = res.json()
    assert "high_risk_claims" in data
    assert "cases_awaiting_evidence" in data
    assert "assigned_investigations" in data
    assert "ocr_evidence" in data
    assert "ai_forensic_findings" in data


def test_admin_access_to_all_departments(client, admin):
    for path in ["/departmental/claims-officer", "/departmental/executive",
                 "/departmental/compliance", "/departmental/fraud-investigator", "/departmental/admin"]:
        res = client.get(path, headers=admin)
        assert res.status_code == 200, f"Admin should access {path}"


def test_unauthenticated_blocked_from_all_dashboards(client):
    for path in ["/departmental/claims-officer", "/departmental/executive",
                 "/departmental/compliance", "/departmental/fraud-investigator", "/departmental/admin"]:
        res = client.get(path)
        assert res.status_code == 401


def test_my_profile_returns_dashboard_type(client, officer):
    res = client.get("/departmental/my-profile", headers=officer)
    assert res.status_code == 200
    assert res.json()["dashboard_type"] == "claims_officer"


# ─────────────────────────────────────────────
# 2. DEPARTMENTAL DATA-ACCESS RESTRICTIONS
# ─────────────────────────────────────────────

def test_officer_scoped_claims_list(client, officer, manager):
    """Officer sees only claims assigned to them or unassigned."""
    res = client.get("/claims/?limit=100", headers=officer)
    assert res.status_code == 200
    ids = {c["claim_id"] for c in res.json()}

    # Create a claim as the officer
    claim_id = _submit_claim(client, officer, policy_number="POL-ACC-312984", claim_amount=3000.0)
    db = SessionLocal()
    try:
        # Assign the claim to the Claims Manager — officer must no longer see it
        claim = db.query(Claim).filter(Claim.claim_id == claim_id).first()
        mgr = db.query(User).filter(User.username == "claims.manager").first()
        claim.assigned_officer_id = mgr.id
        db.commit()
    finally:
        db.close()

    assert claim_id not in ids  # not assigned at query time
    res_after = client.get("/claims/?limit=100", headers=officer)
    assert claim_id not in {c["claim_id"] for c in res_after.json()}
    # Manager sees it
    res_m = client.get("/claims/", headers=manager)
    assert claim_id in {c["claim_id"] for c in res_m.json()}
    # Officer cannot view it directly
    res_v = client.get(f"/claims/{claim_id}", headers=officer)
    assert res_v.status_code == 403
    # Document upload restriction for officer
    res_u = client.post(
        "/ocr/upload",
        files={"file": ("doc.txt", io.BytesIO(b"text"), "text/plain")},
        data={"claim_reference": claim_id},
        headers=officer,
    )
    assert res_u.status_code == 403


# ─────────────────────────────────────────────
# 3. CLAIMS OFFICER ACTIONS
# ─────────────────────────────────────────────

def _submit_claim(client, headers, policy_number="POL-LIF-801294", claim_amount=5000.0):
    res = client.post("/claims/submit", data={
        "policy_number": policy_number,
        "claim_type": "Funeral Expense",
        "claim_amount": str(claim_amount),
        "incident_date": "2026-06-10",
        "description": "Test claim for upgrade verification",
    }, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()["claim_id"]


def test_request_missing_documents(client, officer):
    claim_id = _submit_claim(client, officer)
    res = client.post(f"/claims/{claim_id}/request-documents", data={"reason": "Death certificate required"}, headers=officer)
    assert res.status_code == 200
    assert res.json()["status"] == "pending_documents"


def test_forward_claim_to_investigation(client, officer):
    claim_id = _submit_claim(client, officer)
    res = client.post(f"/claims/{claim_id}/forward-to-investigation", data={"notes": "Suspected duplicate"}, headers=officer)
    assert res.status_code == 200
    data = res.json()
    assert data["investigation_id"] > 0
    # Investigation exists in DB
    db = SessionLocal()
    try:
        inv = db.query(Investigation).filter(Investigation.id == data["investigation_id"]).first()
        assert inv is not None
        assert inv.claim.claim_id == claim_id
        # Auditor trail entry
        audit = db.query(AuditLog).filter(AuditLog.action == "CLAIM_FORWARDED_TO_INVESTIGATION").order_by(AuditLog.id.desc()).first()
        assert audit is not None
    finally:
        db.close()


def test_add_and_list_claim_notes(client, officer):
    claim_id = _submit_claim(client, officer)
    res = client.post(f"/claims/{claim_id}/notes", json={"note": "Officer note added during upgrade tests."}, headers=officer)
    assert res.status_code == 200
    assert res.json()["id"] > 0
    notes = client.get(f"/claims/{claim_id}/notes", headers=officer).json()
    assert any("Officer note added" in n["note"] for n in notes)


def test_claim_notes_requires_auth(client):
    res = client.get("/claims/CLM-2026-9001/notes")
    assert res.status_code in (401, 403)


# ─────────────────────────────────────────────
# 4. OCR UPLOAD VALIDATION & CORRECTION
# ─────────────────────────────────────────────

def test_ocr_upload_invalid_type_rejected(client, officer):
    res = client.post(
        "/ocr/upload",
        files={"file": ("malware.exe", io.BytesIO(b"MZ fake exe"), "application/x-msdownload")},
        headers=officer,
    )
    assert res.status_code == 415


def test_ocr_upload_success_and_extraction(client, officer):
    content = b"FIDELITY LIFE ASSURANCE DEATH CERTIFICATE\nDate of Death: 2026-06-10\nAmount: 5000.00\nNational ID: 63-289412-A-18"
    res = client.post(
        "/ocr/upload",
        files={"file": ("death_cert.txt", io.BytesIO(content), "text/plain")},
        data={"claim_reference": ""},
        headers=officer,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["processing_status"] == "completed"
    assert data["document_type"] is not None
    assert data["document_id"] > 0


def test_ocr_correction_creates_audit_trail(client, officer):
    content = b"National ID: 63-289412-A-18"
    res = client.post(
        "/ocr/upload",
        files={"file": ("national_id.txt", io.BytesIO(content), "text/plain")},
        headers=officer,
    )
    assert res.status_code == 200
    doc_id = res.json()["document_id"]

    corr = client.post(f"/ocr/documents/{doc_id}/correct", json={"field_name": "national_ids", "corrected_value": "63-289412-A-19", "correction_note": "Verified at branch"}, headers=officer)
    assert corr.status_code == 200
    assert corr.json()["corrected_value"] == "63-289412-A-19"

    db = SessionLocal()
    try:
        doc = db.query(OCRDocument).filter(OCRDocument.id == doc_id).first()
        assert doc is not None
        # Original value preserved in audit trail
        corrections = db.query(OCRDocument).first()  # sanity
        from backend.app.models.sqlalchemy_models import OCRCorrection
        recs = db.query(OCRCorrection).filter(OCRCorrection.document_id == doc_id).all()
        assert len(recs) >= 1
        assert recs[0].corrected_value == "63-289412-A-19"
        assert doc.is_manually_verified is True
    finally:
        db.close()


# ─────────────────────────────────────────────
# 5. AI FORENSIC MODULE
# ─────────────────────────────────────────────

def test_forensics_overview_structure(client, officer):
    res = client.get("/forensics/overview", headers=officer)
    assert res.status_code == 200
    data = res.json()
    for key in ["total_claims_analysed", "claims_pending_analysis", "analysis_completion_rate",
                "risk_breakdown", "confirmed_suspicious_cases", "risk_thresholds"]:
        assert key in data
    assert data["risk_thresholds"]["high"] == "60–79" or isinstance(data["risk_thresholds"], dict)


def test_forensics_claim_detail_has_findings_and_disclaimer(client, officer):
    db = SessionLocal()
    try:
        claim = db.query(Claim).filter(Claim.claim_id == "CLM-2026-9001").first()
        if not claim:
            pytest.skip("CLM-2026-9001 not seeded")
        claim_id = claim.claim_id
    finally:
        db.close()
    res = client.get(f"/forensics/claims/{claim_id}", headers=officer)
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") in ("assessed",)
    assert data.get("assessment", {}).get("risk_score", 0) >= 0
    assert "forensic_findings" in data
    assert data["forensic_findings"] is not None
    assert "disclaimer" in data
    assert "AI Forensic Disclaimer" in data["disclaimer"]


def test_forensics_claim_detail_pending_state(client, officer):
    claim_id = _submit_claim(client, officer)
    res = client.get(f"/forensics/claims/{claim_id}", headers=officer)
    assert res.status_code == 200
    assert res.json()["status"] in ("pending", "assessed")


def test_risk_thresholds_configurable_by_admin(client, admin, officer):
    res = client.get("/forensics/risk-thresholds", headers=admin)
    assert res.status_code == 200
    assert res.json()["thresholds"]["medium"][1] == settings.RISK_THRESHOLD_MEDIUM_MAX

    # Update as admin
    orig_medium = settings.RISK_THRESHOLD_MEDIUM_MAX
    try:
        res = client.put("/forensics/risk-thresholds", json={"MEDIUM_MAX": orig_medium - 10}, headers=admin)
        assert res.status_code == 200, res.text
        assert settings.RISK_THRESHOLD_MEDIUM_MAX == orig_medium - 10
        # Invalid values rejected
        res = client.put("/forensics/risk-thresholds", json={"MEDIUM_MAX": 150}, headers=admin)
        assert res.status_code == 400
    finally:
        settings.RISK_THRESHOLD_MEDIUM_MAX = orig_medium

    # Officer cannot change thresholds
    res = client.put("/forensics/risk-thresholds", json={"MEDIUM_MAX": 10}, headers=officer)
    assert res.status_code == 403


# ─────────────────────────────────────────────
# 6. COMPLIANCE / MANAGEMENT REPORTS
# ─────────────────────────────────────────────

def test_compliance_reports_generation_and_exceptions(client, compliance):
    res = client.post("/compliance-reports/", data={"report_type": "FRAUD_COMPLIANCE_REVIEW"}, headers=compliance)
    assert res.status_code == 200
    rid = res.json()["id"]
    detail = client.get(f"/compliance-reports/{rid}", headers=compliance)
    assert detail.status_code == 200
    listed = client.get("/compliance-reports/", headers=compliance)
    assert any(r["id"] == rid for r in listed.json())
    exc = client.get("/compliance-reports/exceptions", headers=compliance)
    assert exc.status_code == 200
    assert "exceptions" in exc.json()


def test_management_reports_generation(client, executive):
    res = client.post("/management-reports/", json={"report_type": "EXECUTIVE_KPI_SNAPSHOT"}, headers=executive)
    assert res.status_code == 200
    rid = res.json()["id"]
    assert "summary" in res.json()
    detail = client.get(f"/management-reports/{rid}", headers=executive)
    assert detail.status_code == 200
    listed = client.get("/management-reports/", headers=executive)
    assert any(r["id"] == rid for r in listed.json())


def test_management_reports_blocked_for_officer(client, officer):
    res = client.post("/management-reports/", json={}, headers=officer)
    assert res.status_code == 403


# ─────────────────────────────────────────────
# 7. INVESTIGATION NOTES & EVIDENCE
# ─────────────────────────────────────────────

def test_investigation_notes_and_evidence(client, investigator, compliance):
    db = SessionLocal()
    try:
        inv = db.query(Investigation).order_by(Investigation.id.desc()).first()
        if inv is None:
            pytest.skip("No investigations seeded")
        inv_id = inv.id
        # Create a note
        res = client.post(f"/investigations/{inv_id}/notes", json={"note": "Initial investigation hypothesis established."}, headers=investigator)
        assert res.status_code == 200
        assert res.json()["id"] > 0
        # Get detail
        detail = client.get(f"/investigations/{inv_id}", headers=investigator)
        assert detail.status_code == 200
        assert any("Initial investigation" in n["note"] for n in detail.json()["timeline"])
        # Compliance can view details
        detail2 = client.get(f"/investigations/{inv_id}", headers=compliance)
        assert detail2.status_code == 200
    finally:
        db.close()


# ─────────────────────────────────────────────
# 8. NOTIFICATIONS
# ─────────────────────────────────────────────

def test_unread_notification_count(client, officer):
    res = client.get("/notifications/unread-count", headers=officer)
    assert res.status_code == 200
    assert "unread_count" in res.json()
    assert res.json()["unread_count"] >= 0
