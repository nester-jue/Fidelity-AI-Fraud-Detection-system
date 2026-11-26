"""Tests for enterprise access-control hardening, MFA and the Security Centre.

These tests use unique, clearly named throwaway users and remove every row
they create. Assertions deliberately reject "green" security statuses that
are not backed by a real check or explicit configuration.
"""
import os
import sys
import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.auth import _totp_at, generate_totp_secret, verify_totp
from backend.app.core.config import settings
from backend.app.services import db as db_service
from backend.app.models.sqlalchemy_models import AuditLog, RoleEnum, User
from tests.helpers import admin_headers, officer_headers


@pytest.fixture
def client():
    return TestClient(app)


def _unique(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _cleanup_user(username):
    db = db_service.SessionLocal()
    try:
        db.query(AuditLog).filter(AuditLog.target.contains(username)).delete(synchronize_session=False)
        db.query(User).filter(User.username == username).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _create_user(username, password, role=RoleEnum.CLAIMS_OFFICER):
    from backend.app.auth import get_password_hash
    db = db_service.SessionLocal()
    try:
        user = User(
            username=username,
            full_name="Security Test User",
            email=f"{username}@example.invalid",
            hashed_password=get_password_hash(password),
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        return user.id
    finally:
        db.close()


# ── Registration hardening ──────────────────────────────────────────────────

def test_registration_cannot_grant_privileged_role(client):
    username = _unique("reg-admin")
    payload = {
        "username": username,
        "full_name": "Registration Test",
        "email": f"{username}@example.invalid",
        "password": "StrongPassphrase123!",
        "role": "system_admin",
    }
    try:
        res = client.post("/auth/register", json=payload)
        assert res.status_code == 403
        assert "Privileged roles" in res.json()["detail"]
        db = db_service.SessionLocal()
        try:
            assert db.query(User).filter(User.username == username).first() is None
        finally:
            db.close()
    finally:
        _cleanup_user(username)


def test_registration_enforces_password_policy(client):
    username = _unique("reg-short")
    payload = {
        "username": username,
        "full_name": "Registration Test",
        "email": f"{username}@example.invalid",
        "password": "shortpass1",
        "role": "claims_officer",
    }
    try:
        res = client.post("/auth/register", json=payload)
        # Pydantic rejects short values at the boundary (422); the endpoint's
        # own check covers deployments that override the policy at runtime.
        assert res.status_code in (400, 422)
        assert "at least" in str(res.json()["detail"]).lower() or "shorter" in str(res.json()["detail"]).lower()
    finally:
        _cleanup_user(username)


def test_registration_can_be_disabled(monkeypatch, client):
    username = _unique("reg-disabled")
    monkeypatch.setattr(settings, "ALLOW_PUBLIC_REGISTRATION", False)
    payload = {
        "username": username,
        "full_name": "Registration Test",
        "email": f"{username}@example.invalid",
        "password": "StrongPassphrase123!",
        "role": "claims_officer",
    }
    try:
        res = client.post("/auth/register", json=payload)
        assert res.status_code == 403
        assert "disabled" in res.json()["detail"].lower()
    finally:
        _cleanup_user(username)


def test_forgot_password_never_claims_dispatch(monkeypatch, client):
    monkeypatch.setattr(settings, "PASSWORD_RESET_EMAIL_ENABLED", False)
    res = client.post("/auth/forgot-password", json={"email": "nobody@example.invalid"})
    assert res.status_code == 503
    assert "dispatched" not in res.json()["detail"].lower()


# ── TOTP / MFA ──────────────────────────────────────────────────────────────

def test_totp_verification_roundtrip_and_rejection():
    secret = generate_totp_secret()
    current = _totp_at(secret, int(time.time()) // 30)
    assert len(current) == 6 and current.isdigit()
    assert verify_totp(secret, current)
    assert not verify_totp(secret, "abcdef")
    assert not verify_totp(secret, "")
    assert not verify_totp(generate_totp_secret(), current)


def test_mfa_enrolment_enforced_at_sign_in(client):
    username = _unique("mfa-user")
    password = "StrongPassphrase123!"
    user_id = _create_user(username, password)
    try:
        login = client.post("/auth/token", data={"username": username, "password": password})
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        status = client.get("/auth/mfa/status", headers=headers)
        assert status.status_code == 200 and status.json()["mfa_enabled"] is False

        setup = client.post("/auth/mfa/setup", headers=headers)
        assert setup.status_code == 200, setup.text
        secret = setup.json()["secret"]
        assert setup.json()["provisioning_uri"].startswith("otpauth://totp/")

        code = _totp_at(secret, int(time.time()) // 30)
        enable = client.post("/auth/mfa/enable", json={"code": code}, headers=headers)
        assert enable.status_code == 200, enable.text

        without_code = client.post("/auth/token", data={"username": username, "password": password})
        assert without_code.status_code == 401
        assert without_code.json()["detail"].startswith("MFA_REQUIRED")

        with_code = client.post(
            "/auth/token",
            data={"username": username, "password": password, "mfa_code": code},
        )
        assert with_code.status_code == 200, with_code.text

        disable = client.post(
            "/auth/mfa/disable",
            json={"code": code, "password": password},
            headers=headers,
        )
        assert disable.status_code == 200, disable.text
        assert client.post("/auth/token", data={"username": username, "password": password}).status_code == 200
    finally:
        _cleanup_user(username)


# ── Security Centre ─────────────────────────────────────────────────────────

def test_security_overview_is_role_protected_and_reports_real_data(monkeypatch, client):
    monkeypatch.setattr(settings, "BACKUP_VERIFICATION_CONFIGURED", False)
    monkeypatch.setattr(settings, "BACKUP_LAST_VERIFIED_AT", "")

    denied = client.get("/security/overview", headers=officer_headers())
    assert denied.status_code == 403

    res = client.get("/security/overview", headers=admin_headers())
    assert res.status_code == 200, res.text
    data = res.json()
    auth = data["authentication"]
    for key in ("successful_logins", "failed_logins", "registrations", "recently_authenticated_users"):
        assert isinstance(auth[key], int) and auth[key] >= 0
    assert data["database"]["status"] == "CONNECTED"
    assert data["backup"]["status"] == "NOT_VERIFIED"
    assert data["backup"]["last_verified_at"] is None
    assert any(c["name"] == "Multi-factor authentication" and c["status"] == "AVAILABLE" for c in data["controls"])
    assert "cannot be enumerated" in auth["recent_users_note"]

    events = client.get("/security/events?limit=5", headers=admin_headers())
    assert events.status_code == 200
    assert isinstance(events.json(), list)


# ── Production database safety ──────────────────────────────────────────────

def test_production_rejects_explicit_sqlite_database(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:////tmp/nexa-not-allowed.sqlite")
    with pytest.raises(RuntimeError, match="SQLite is not permitted"):
        db_service.get_database_url()


def test_development_still_allows_explicit_sqlite(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:////tmp/nexa-dev-allowed.sqlite")
    assert db_service.get_database_url().startswith("sqlite:///")


# ── Static login/register UI matches backend policy ─────────────────────────

def test_static_ui_uses_same_origin_api_and_no_privileged_registration():
    html = (Path(__file__).resolve().parents[1] / "backend" / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert 'const API_BASE = "";' in html
    assert 'id="regRole"' not in html
    assert 'role: "claims_officer"' in html
    assert 'mfa_code' in html

    proxy = (Path(__file__).resolve().parents[1] / "frontend" / "server.js").read_text(encoding="utf-8")
    assert "'/security'" in proxy
    assert "'/enquiries'" in proxy

