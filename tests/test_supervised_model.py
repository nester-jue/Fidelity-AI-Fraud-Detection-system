"""Tests for the optional supervised fraud-model integration."""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.ml import supervised
from backend.app.ml.fraud_engine import fraud_engine


class FakePipeline:
    """Picklable stub used to verify live-engine integration."""

    probability = 0.9

    def predict_proba(self, frame):
        import numpy as np
        return np.array([[1.0 - self.probability, self.probability]])


@pytest.fixture(autouse=True)
def reset_supervised_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(supervised, "MODEL_PATH", str(tmp_path / "absent.joblib"))
    monkeypatch.setattr(supervised, "_CACHE", None)
    monkeypatch.setattr(supervised, "_CACHE_PATH", None)
    monkeypatch.delenv("SUPERVISED_MODEL_ENABLED", raising=False)
    yield


def test_feature_mapping_uses_claim_dates_and_policy_inception():
    row = supervised.build_feature_row(
        claim_data={
            "amount": 12000,
            "incident_date": "2024-06-01",
            "submission_date": "2024-06-11",
            "claim_type": "Health",
            "country": "South Africa",
        },
        policy_data={"effective_date": "2024-01-01"},
        customer_data={"date_of_birth": "1984-06-01"},
        historical_claims=[{"amount": 10000}, {"amount": 11000}],
        indicators=[{"code": "DUPLICATE_CLAIM_DETECTED"}],
        metadata={"defaults": {"document_completeness_score": 0.7}},
    )
    assert row["claim_amount_usd"] == 12000.0
    assert row["reporting_delay_days"] == 10.0
    assert row["policy_duration_months"] == pytest.approx(152 / 30.4375, abs=0.01)
    assert row["claimant_age"] == pytest.approx(40.0, abs=0.1)
    assert row["previous_claims_count"] == 2.0
    assert row["duplicate_claim_flag"] == 1.0
    assert row["document_completeness_score"] == 0.7
    assert row["claim_type"] == "health"


def test_score_claim_returns_none_without_an_artefact():
    assert supervised.score_claim({"amount": 1000, "claim_type": "health"}) is None


def test_engine_stays_unchanged_when_supervised_model_is_disabled(monkeypatch):
    monkeypatch.setenv("SUPERVISED_MODEL_ENABLED", "false")
    result = fraud_engine.evaluate_claim(
        claim_data={
            "claim_id": "TEST-NO-MODEL",
            "policy_number": "POL-TEST",
            "amount": 5000,
            "incident_date": "2024-01-10",
            "submission_date": "2024-01-12",
            "claim_type": "Death",
        },
        policy_data={"effective_date": "2022-01-01", "coverage_amount": 50000},
        customer_data={"customer_id": "CUST-TEST"},
        historical_claims=[],
    )
    assert result["supervised_probability"] is None
    assert "supervised_advisory" not in result["ensemble_method"]
    assert not any(i["code"] == "SUPERVISED_MODEL_ALERT" for i in result["indicators"])


def test_engine_adds_bounded_advisory_evidence_when_model_is_installed(monkeypatch, tmp_path):
    import joblib

    artefact_path = tmp_path / "test_model.joblib"
    joblib.dump(
        {
            "pipeline": FakePipeline(),
            "metadata": {
                "version": "test-supervised-v1",
                "decision_threshold": 0.5,
                "roc_auc_mean": 0.8,
                "pr_auc_mean": 0.6,
                "feature_columns": list(supervised.FEATURE_COLUMNS),
                "defaults": {},
            },
        },
        artefact_path,
    )
    monkeypatch.setattr(supervised, "MODEL_PATH", str(artefact_path))

    result = fraud_engine.evaluate_claim(
        claim_data={
            "claim_id": "TEST-MODEL",
            "policy_number": "POL-TEST",
            "amount": 5000,
            "incident_date": "2024-01-10",
            "submission_date": "2024-01-12",
            "claim_type": "Death",
        },
        policy_data={"effective_date": "2022-01-01", "coverage_amount": 50000},
        customer_data={"customer_id": "CUST-TEST"},
        historical_claims=[],
    )
    alert = next(i for i in result["indicators"] if i["code"] == "SUPERVISED_MODEL_ALERT")
    assert result["supervised_probability"] == pytest.approx(0.9)
    assert result["supervised_model_version"] == "test-supervised-v1"
    assert "supervised_advisory" in result["ensemble_method"]
    assert alert["weight"] == pytest.approx(22.5)
    assert alert["weight"] <= 25.0
    status = supervised.describe_model()
    assert status["status"] == "INSTALLED"
    assert status["test_roc_auc_mean"] == pytest.approx(0.8)
    assert status["test_pr_auc_mean"] == pytest.approx(0.6)
