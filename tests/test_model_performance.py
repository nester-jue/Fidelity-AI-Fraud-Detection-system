import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.services.db import init_db, SessionLocal
from backend.app.services import model_performance
from backend.app.models.sqlalchemy_models import Claim, FraudAssessment, Investigation, ModelRetrainingRequest
from tests.helpers import make_policy_and_claim, admin_headers


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db()


@pytest.fixture
def client():
    return TestClient(app)


def test_performance_metrics_from_real_records():
    db = SessionLocal()
    try:
        # Ensure at least one assessment exists
        assessment = db.query(FraudAssessment).first()
        if not assessment:
            claim = db.query(Claim).first()
            if claim:
                db.add(FraudAssessment(claim_id=claim.id, risk_score=25.0, risk_category="Low",
                                       indicators=[], explanation="seed"))
                db.commit()
        data = model_performance.compute_model_performance_metrics(db)
        assert "metrics" in data
        assert "claims_assessed" in data
        assert data["metrics"]["false_positive_rate"] is not None or data["claims_assessed"] == 0
        assert data["metrics"]["precision"] is None or 0 <= data["metrics"]["precision"] <= 1
        assert data["honesty_note"]
        assert "accuracy_proxy_flagged_confirmed_or_clear" in data["metrics"]
    finally:
        db.close()


def test_retraining_workflow_lifecycle():
    db = SessionLocal()
    try:
        from backend.app.models.sqlalchemy_models import User
        user = db.query(User).filter(User.username == "admin").first()
        req = model_performance.request_model_retraining(
            db, requested_by_id=user.id, new_model_version="v2.0-test",
            base_model_version="v1.2-ensemble-hybrid", dataset_version="ds-2026-01",
            dataset_records=100, training_method="statistical", notes="test",
        )
        assert req["status"] == "requested"
        approved = model_performance.approve_retraining_request(db, req["id"], user.id)
        assert approved["status"] == "approved"
        assert approved["approved_by"] == "admin"
        deployed = model_performance.deploy_retraining_request(db, req["id"])
        assert deployed["status"] == "deployed"
        # Cannot deploy twice
        with pytest.raises(ValueError):
            model_performance.deploy_retraining_request(db, req["id"])
    finally:
        db.close()


def test_model_performance_api(client):
    res = client.get("/model-performance/dashboard", headers=admin_headers())
    assert res.status_code == 200
    assert "metrics" in res.json()
    res2 = client.get("/model-performance/versions", headers=admin_headers())
    assert res2.status_code == 200
    assert isinstance(res2.json(), list)
    res3 = client.get("/model-performance/data-retention", headers=admin_headers())
    assert res3.status_code == 200
    assert "audit_retention_days" in res3.json()


def test_model_performance_unauthorised():
    from tests.helpers import officer_headers
    res = TestClient(app).get("/model-performance/dashboard", headers=officer_headers())
    # Officer has no model_performance capability → denied at API level
    assert res.status_code == 403
