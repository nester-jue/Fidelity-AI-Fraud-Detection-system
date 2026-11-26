"""End-to-end checks for the remaining enterprise operational controls."""
import hashlib
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.auth import _totp_at, create_access_token, get_password_hash
from backend.app.core.config import settings
from backend.app.integrations.mock_services import ClaimsService, PolicyService
from backend.app.main import app
from backend.app.models.sqlalchemy_models import (
    AuditLog, Claim, Customer, Enquiry, FirstNoticeOfLoss, Organisation, Policy,
    RoleEnum, User,
)
from backend.app.services import db as db_service
from tests.helpers import make_policy_and_claim, officer_headers


@pytest.fixture
def client():
    return TestClient(app)


def _unique(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _create_user(username, password="StrongPassphrase123!", role=RoleEnum.CLAIMS_OFFICER, org_id=None):
    db = db_service.SessionLocal()
    try:
        user = User(
            username=username,
            full_name="Enterprise Operations Test",
            email=f"{username}@example.invalid",
            hashed_password=get_password_hash(password),
            role=role,
            organisation_id=org_id,
            is_active=True,
        )
        db.add(user)
        db.commit()
        return user.id
    finally:
        db.close()


def _delete_user(username):
    db = db_service.SessionLocal()
    try:
        db.query(AuditLog).filter(AuditLog.target.contains(username)).delete(synchronize_session=False)
        db.query(User).filter(User.username == username).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


# ── Public enquiry capture ──────────────────────────────────────────────────
def test_enquiry_is_persisted_with_reference(client):
    email = f"{_unique('enquiry')}@example.invalid"
    res = client.post("/enquiries/", json={"organisation": "Test Insurer", "email": email, "interests": "Claims workflow"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["reference"].startswith("ENQ-")
    assert body["status"] == "received"

    db = db_service.SessionLocal()
    try:
        saved = db.query(Enquiry).filter(Enquiry.reference == body["reference"]).first()
        assert saved is not None and saved.email == email
        db.delete(saved)
        db.commit()
    finally:
        db.close()


def test_enquiry_rejects_invalid_email(client):
    res = client.post("/enquiries/", json={"organisation": "Test Insurer", "email": "not-an-email", "interests": ""})
    assert res.status_code == 400


# ── FNOL persistence ─────────────────────────────────────────────────────────
def test_fnol_is_stored_and_listed_without_invented_values(client):
    headers = officer_headers()
    unique = _unique("fnol-policy")
    claim = make_policy_and_claim(
        db_service.SessionLocal(), _unique("fnol-cust"), unique, _unique("fnol-claim"),
        amount=75000.0,
    )
    from tests.helpers import admin_headers
    res = client.post("/claims/fnol", data={
        "policy_number": unique,
        "claimant_name": "Recorded Claimant",
        "event_type": "Funeral Expense",
        "incident_date": "2026-03-15",
        "estimated_amount": "75000",
        "reporting_channel": "Contact Centre",
        "initial_notes": "Persisted FNOL verification",
    }, headers=admin_headers())
    assert res.status_code == 200, res.text
    reference = res.json()["fnol_reference"]
    assert res.json()["persisted"] is True
    assert res.json()["triage_queue"] == "High-Value Claims Review"
    assert res.json()["claim_id"] == claim.claim_id

    listed = client.get("/claims/fnol/list", headers=headers)
    assert listed.status_code == 200
    match = [f for f in listed.json()["fnol_intakes"] if f["fnol_reference"] == reference]
    assert len(match) == 1
    assert match[0]["claimant_name"] == "Recorded Claimant"
    assert match[0]["incident_date"] == "2026-03-15"
    assert match[0]["reporting_channel"] == "Contact Centre"

    bad = client.post("/claims/fnol", data={
        "policy_number": unique, "claimant_name": "X", "event_type": "Loss",
        "incident_date": "not-a-date", "estimated_amount": "100",
    }, headers=admin_headers())
    assert bad.status_code == 400

    db = db_service.SessionLocal()
    try:
        db.query(FirstNoticeOfLoss).filter(FirstNoticeOfLoss.fnol_reference == reference).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


# ── Password reset through configured SMTP ──────────────────────────────────
def test_password_reset_flow_is_real_and_token_is_single_use(monkeypatch, client):
    username = _unique("reset-user")
    password = "OldPassphrase123!"
    _create_user(username, password)
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            self.messages = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            pass

        def login(self, user, pw):
            pass

        def send_message(self, message):
            self.messages.append(message)
            sent.append(message.get_content())

    monkeypatch.setattr(settings, "PASSWORD_RESET_EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.invalid")
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "FRONTEND_RESET_URL", "https://app.example.invalid")
    monkeypatch.setattr("backend.app.api.auth.smtplib.SMTP", FakeSMTP)

    try:
        res = client.post("/auth/forgot-password", json={"email": f"{username}@example.invalid"})
        assert res.status_code == 200, res.text
        assert len(sent) == 1
        token = sent[0].split("token=")[1].split()[0].rstrip()

        reset = client.post("/auth/reset-password", json={"token": token, "new_password": "NewPassphrase123!"})
        assert reset.status_code == 200, reset.text
        assert client.post("/auth/token", data={"username": username, "password": "NewPassphrase123!"}).status_code == 200
        reused = client.post("/auth/reset-password", json={"token": token, "new_password": "AnotherPass123!"})
        assert reused.status_code == 400
    finally:
        _delete_user(username)


# ── MFA policy enforcement ──────────────────────────────────────────────────
def test_mfa_required_issues_enrolment_only_token(monkeypatch, client):
    username = _unique("mfa-policy")
    password = "StrongPassphrase123!"
    _create_user(username, password)
    monkeypatch.setattr(settings, "MFA_REQUIRED", True)
    try:
        login = client.post("/auth/token", data={"username": username, "password": password})
        assert login.status_code == 200, login.text
        assert login.json()["mfa_enrollment_required"] is True
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert client.get("/claims/", headers=headers).status_code == 403
        assert client.get("/auth/mfa/status", headers=headers).status_code == 200

        setup = client.post("/auth/mfa/setup", headers=headers)
        assert setup.status_code == 200, setup.text
        secret = setup.json()["secret"]
        code = _totp_at(secret, int(time.time()) // 30)
        enabled = client.post("/auth/mfa/enable", json={"code": code}, headers=headers)
        assert enabled.status_code == 200, enabled.text
        full_headers = {"Authorization": f"Bearer {enabled.json()['access_token']}"}
        assert client.get("/claims/", headers=full_headers).status_code == 200
        assert client.post("/auth/token", data={"username": username, "password": password}).status_code == 401
    finally:
        monkeypatch.setattr(settings, "MFA_REQUIRED", False)
        _delete_user(username)


# ── Tenant isolation ────────────────────────────────────────────────────────
def test_tenant_isolation_filters_reads_and_rejects_cross_tenant_access(monkeypatch, client):
    suffix = _unique("tenant")
    org_a_name, org_b_name = f"A-{suffix}", f"B-{suffix}"
    db = db_service.SessionLocal()
    try:
        org_a = Organisation(name=org_a_name, slug=f"{suffix}-a", is_active=True)
        org_b = Organisation(name=org_b_name, slug=f"{suffix}-b", is_active=True)
        db.add_all([org_a, org_b])
        db.commit()
        db.refresh(org_a)
        db.refresh(org_b)
        username_a, username_b = f"{suffix}-a", f"{suffix}-b"
        user_a = _create_user(username_a, role=RoleEnum.CLAIMS_MANAGER, org_id=org_a.id)
        user_b = _create_user(username_b, role=RoleEnum.CLAIMS_MANAGER, org_id=org_b.id)
        claim_a = make_policy_and_claim(db, f"CUST-{suffix}-A", f"POL-{suffix}-A", f"CLM-{suffix}-A")
        claim_b = make_policy_and_claim(db, f"CUST-{suffix}-B", f"POL-{suffix}-B", f"CLM-{suffix}-B")
        customer_b = db.query(Customer).filter(Customer.customer_id == f"CUST-{suffix}-B").first()
        policy_b = db.query(Policy).filter(Policy.policy_number == f"POL-{suffix}-B").first()
        for record in (claim_a, claim_b, customer_b, policy_b):
            record.organisation_id = org_b.id if record in (claim_b, customer_b, policy_b) else org_a.id
        db.commit()
        ids = (org_a.id, org_b.id, user_a, user_b, username_a, username_b)
    finally:
        db.close()

    monkeypatch.setattr(settings, "TENANT_ISOLATION_ENABLED", True)
    try:
        username_a, username_b = ids[4], ids[5]
        token_a = create_access_token({"sub": username_a, "role": "claims_manager", "user_id": ids[2], "organisation_id": ids[0]})
        token_b = create_access_token({"sub": username_b, "role": "claims_manager", "user_id": ids[3], "organisation_id": ids[1]})
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        seen_a = client.get("/claims/", headers=headers_a)
        seen_b = client.get("/claims/", headers=headers_b)
        assert seen_a.status_code == 200 and seen_b.status_code == 200, (seen_a.text, seen_b.text)
        ids_a = {c["claim_id"] for c in seen_a.json()}
        ids_b = {c["claim_id"] for c in seen_b.json()}
        assert f"CLM-{suffix}-A" in ids_a
        assert f"CLM-{suffix}-B" not in ids_a
        assert f"CLM-{suffix}-B" in ids_b
        assert f"CLM-{suffix}-A" not in ids_b

        assert client.get(f"/claims/CLM-{suffix}-B", headers=headers_a).status_code == 404
        token_no_org = create_access_token({"sub": username_a, "role": "claims_manager", "user_id": ids[2]})
        missing_org = {"Authorization": f"Bearer {token_no_org}"}
        # No organisation claim: the request fails closed (401 from the
        # filtered user lookup, 403 if the dependency rejects it first).
        assert client.get("/claims/", headers=missing_org).status_code in (401, 403)
        token_wrong_org = create_access_token({
            "sub": username_a, "role": "claims_manager", "user_id": ids[2], "organisation_id": ids[1],
        })
        # A token claiming another organisation cannot resolve the user at all
        # under the ORM filter; either 401 or 403 is a correct fail-closed result.
        assert client.get("/claims/", headers={"Authorization": f"Bearer {token_wrong_org}"}).status_code in (401, 403)
    finally:
        monkeypatch.setattr(settings, "TENANT_ISOLATION_ENABLED", False)
        db = db_service.SessionLocal()
        try:
            db.query(Claim).filter(Claim.claim_id.in_([f"CLM-{suffix}-A", f"CLM-{suffix}-B"])).delete(synchronize_session=False)
            db.query(Claim).filter(Claim.claim_id == f"CLM-{suffix}-B").delete(synchronize_session=False)
            db.query(Policy).filter(Policy.policy_number.in_([f"POL-{suffix}-A", f"POL-{suffix}-B"])).delete(synchronize_session=False)
            db.query(Customer).filter(Customer.customer_id.in_([f"CUST-{suffix}-A", f"CUST-{suffix}-B"])).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_([ids[2], ids[3]])).delete(synchronize_session=False)
            db.query(Organisation).filter(Organisation.id.in_([ids[0], ids[1]])).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


def test_tenant_insert_stamping_and_context_restoration(monkeypatch):
    from backend.app.services import tenant as tenant_service

    monkeypatch.setattr(settings, "TENANT_ISOLATION_ENABLED", True)
    suffix = _unique("stamp")
    username = f"{suffix}-user"
    db = db_service.SessionLocal()
    try:
        org = Organisation(name=f"Stamp {suffix}", slug=suffix, is_active=True)
        db.add(org)
        db.commit()
        db.refresh(org)
        with tenant_service.bound_tenant(org.id):
            assert tenant_service.current_tenant() == org.id
            user = _create_user(username, role=RoleEnum.CLAIMS_OFFICER, org_id=None)
            db.expire_all()
            assert db.get(User, user).organisation_id == org.id
        assert tenant_service.current_tenant() is None
    finally:
        db.close()
        _delete_user(username)
        db = db_service.SessionLocal()
        try:
            db.query(Organisation).filter(Organisation.slug == suffix).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()
        monkeypatch.setattr(settings, "TENANT_ISOLATION_ENABLED", False)


# ── Versioned migrations and verified backups ───────────────────────────────
def test_alembic_baseline_migration_on_disposable_database(tmp_path):
    import subprocess

    db_path = tmp_path / "migration.sqlite"
    env = dict(os.environ, DATABASE_URL=f"sqlite:///{db_path}", ENVIRONMENT="development")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    import sqlite3
    tables = {r[0] for r in sqlite3.connect(db_path).execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"users", "claims", "organisations", "first_notices_of_loss", "alembic_version"} <= tables


def test_backup_integrity_and_restore_roundtrip(monkeypatch, tmp_path):
    from scripts.backup_db import backup
    from scripts.restore_db import restore
    from scripts.verify_backup import verify

    source = tmp_path / "source.sqlite"
    target = tmp_path / "target.sqlite"
    import sqlite3
    conn = sqlite3.connect(source)
    conn.execute("CREATE TABLE marker (id INTEGER PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO marker (value) VALUES ('before')")
    conn.commit()
    conn.close()
    sqlite3.connect(target).execute("CREATE TABLE marker (id INTEGER PRIMARY KEY, value TEXT)")

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{source}")
    manifest = backup(str(tmp_path / "backups"))
    assert manifest["integrity_check"] == "ok"
    dump = tmp_path / "backups" / manifest["file"]
    assert verify(dump)["sha256"] == manifest["sha256"]

    conn = sqlite3.connect(source)
    conn.execute("UPDATE marker SET value='after'")
    conn.commit()
    conn.close()
    restore(dump, f"sqlite:///{target}")
    value = sqlite3.connect(target).execute("SELECT value FROM marker").fetchone()[0]
    assert value == "before"


def test_restore_refuses_production_without_confirmation(monkeypatch, tmp_path):
    from scripts.restore_db import restore

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    with pytest.raises(RuntimeError, match="Refusing to restore"):
        restore(tmp_path / "missing.sqlite", "postgresql://user:pw@db.internal:5432/frauddb", False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")


# ── Document ingestion and no-synthesis adapters ────────────────────────────
def test_docx_knowledge_ingestion_extracts_real_text(tmp_path):
    from backend.app.services.knowledge.documents import parse_document

    path = tmp_path / "procedure.docx"
    from docx import Document
    doc = Document()
    doc.add_paragraph("Fraud investigation procedure")
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Stage"
    table.rows[0].cells[1].text = "Review"
    doc.save(path)
    text = parse_document(path)
    assert "Fraud investigation procedure" in text
    assert "Stage | Review" in text


def test_system_of_record_adapters_never_invent_records():
    assert PolicyService().get_policy(f"POL-MISSING-{uuid.uuid4().hex}") == {}
    assert ClaimsService().list_previous_claims(f"POL-MISSING-{uuid.uuid4().hex}") == []
