import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.services.db import init_db, SessionLocal
from backend.app.services import predictive_monitoring
from backend.app.models.sqlalchemy_models import Claim, PredictiveAlert
from tests.helpers import make_policy_and_claim, admin_headers


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db()


@pytest.fixture
def client():
    return TestClient(app)


def test_scan_creates_alerts_and_transitions():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        cust_id = f"PRED-CUST-{int(now.timestamp()) % 100000}"
        make_policy_and_claim(db, cust_id, f"POL-PRED-{cust_id}", f"CLM-PRED-1-{cust_id}",
                              amount=10000.0)
        # Force a second submission pattern: create claim directly with recent dates
        c2 = make_policy_and_claim(db, cust_id, f"POL-PRED-{cust_id}", f"CLM-PRED-2-{cust_id}",
                                   amount=10200.0)
        new_alerts = predictive_monitoring.scan_for_pending_alerts(db, max_alerts=5)
        assert isinstance(new_alerts, list)
        # If alerts were created, lifecycle transitions must work
        alerts = predictive_monitoring.get_alerts(db, status="new", limit=10)
        if alerts:
            alert_id = alerts[0]["id"]
            ok = predictive_monitoring.acknowledge_alert(db, alert_id, 1)
            assert ok and ok["status"] == "acknowledged"
            ok2 = predictive_monitoring.resolve_alert(db, alert_id, 1, "verified as benign")
            assert ok2 and ok2["status"] == "resolved"
            # Dismissed for a separate id
            alert_id2 = alerts[-1]["id"] if len(alerts) > 1 else alerts[0]["id"]
            ok3 = predictive_monitoring.dismiss_alert(db, alert_id2, 1)
            assert ok3 and ok3["status"] == "dismissed"
    finally:
        db.close()


def test_predictive_api_summary_and_alerts(client):
    res = client.get("/predictive/summary", headers=admin_headers())
    assert res.status_code == 200
    body = res.json()
    assert "total" in body
    assert "by_severity" in body
    res2 = client.get("/predictive/alerts", headers=admin_headers())
    assert res2.status_code == 200
    assert isinstance(res2.json(), list)


def test_predictive_requires_authentication():
    client = TestClient(app)
    res = client.get("/predictive/alerts")
    assert res.status_code == 401


def test_predictive_summary_for_management_and_officer():
    from tests.helpers import officer_headers as _officer_headers
    res = TestClient(app).get("/predictive/summary", headers=admin_headers())
    assert res.status_code == 200
    res2 = TestClient(app).get("/predictive/summary", headers=_officer_headers())
    assert res2.status_code == 200
    assert set(res2.json().keys()) >= {"total", "new"}
