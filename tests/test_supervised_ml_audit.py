"""Comprehensive audit tests for the FIDE-AI supervised fraud pipeline.

Covers: artifact loading / missing / invalid handling; feature preparation;
missing inputs; unknown countries & claim types; probability boundaries;
configurable thresholds; training/inference feature consistency; model-version
reporting; rule-based fraud detection; and integration with the fraud engine.

The supervised model is ADVISORY ONLY and a missing/invalid model never breaks
the rule-based engine.
"""
import math
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.ml import supervised
from backend.app.ml.fraud_engine import fraud_engine


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
class ConstantPipeline:
    """Picklable stub pipeline returning a fixed probability."""

    def __init__(self, probability=0.5):
        self.probability = probability

    def predict_proba(self, frame):
        n = len(frame)
        p = float(self.probability)
        return np.array([[1.0 - p, p]] * n)


class NaNPipe:
    """Picklable stub returning NaN probabilities."""

    def predict_proba(self, frame):
        return np.array([[float("nan"), float("nan")]] * len(frame))


def _reset(monkeypatch, tmp_path, name="absent.joblib"):
    monkeypatch.setattr(supervised, "MODEL_PATH", str(tmp_path / name))
    monkeypatch.setattr(supervised, "_CACHE", None)
    monkeypatch.setattr(supervised, "_CACHE_PATH", None)
    monkeypatch.delenv("SUPERVISED_MODEL_ENABLED", raising=False)


def _write_artifact(path, pipeline, metadata=None):
    import joblib
    joblib.dump({"pipeline": pipeline, "metadata": metadata or {}}, path)
    return str(path)


def _claim(**over):
    base = {
        "claim_id": "C1",
        "policy_number": "POL-1",
        "amount": 5000.0,
        "incident_date": "2024-06-01",
        "submission_date": "2024-06-10",
        "claim_type": "Death Benefit",
    }
    base.update(over)
    return base


# --------------------------------------------------------------------------
# 1. Feature-set guarantees (target leakage removed)
# --------------------------------------------------------------------------
def test_duplicate_claim_flag_and_year_not_features():
    assert "duplicate_claim_flag" not in supervised.FEATURE_COLUMNS
    assert "duplicate_claim_flag" not in supervised.NUMERIC_COLUMNS
    assert "year" not in supervised.FEATURE_COLUMNS
    assert "year" not in supervised.NUMERIC_COLUMNS
    for leak in ("fraud_label", "fraud_probability", "fraud_scheme_type",
                 "detection_method", "recovery_amount_usd", "record_id",
                 "duplicate_claim_flag", "year"):
        assert leak in supervised.LEAKAGE_COLUMNS


def test_build_feature_row_keys_and_order_match_feature_columns():
    row = supervised.build_feature_row(_claim(), {}, {}, [])
    assert list(row.keys()) == list(supervised.FEATURE_COLUMNS)
    assert len(row) == len(supervised.FEATURE_COLUMNS)


def test_duplicate_claim_indicator_not_a_supervised_feature():
    row = supervised.build_feature_row(
        _claim(), {}, {}, [], indicators=[{"code": "DUPLICATE_CLAIM_DETECTED"}]
    )
    assert "duplicate_claim_flag" not in row
    # nothing in the row references duplicate claims
    assert all("duplicate" not in k for k in row)


def test_rule_engine_retains_duplicate_claim_detection():
    """Removing duplicate_claim_flag from supervised must NOT remove rule-based duplicate detection."""
    hist = [_claim(claim_id="OLD", amount=5000.0, incident_date="2024-06-01", policy_number="POL-1")]
    res = fraud_engine.evaluate_claim(
        claim_data=_claim(claim_id="NEW", amount=5000.0, incident_date="2024-06-01", policy_number="POL-1"),
        policy_data={"effective_date": "2022-01-01", "coverage_amount": 100000},
        customer_data={"national_id": "63-1234567-A-01"},
        historical_claims=hist,
    )
    codes = {i["code"] for i in res["indicators"]}
    assert "DUPLICATE_CLAIM_DETECTED" in codes


# --------------------------------------------------------------------------
# 2. Feature preparation & normalization
# --------------------------------------------------------------------------
def test_category_normalization_and_unknowns():
    row = supervised.build_feature_row(
        _claim(country="  South   AFRICA  ".replace("   ", " "), claim_type=" MOTOR "),
        {}, {}, [],
    )
    assert row["country"] == "south africa"
    assert row["claim_type"] == "motor"
    # unknown country / claim type -> not an error; passed through, one-hot ignores
    row2 = supervised.build_feature_row(_claim(country="Atlantis", claim_type="space"), {}, {}, [])
    assert row2["country"] == "atlantis"
    assert row2["claim_type"] == "space"


def test_missing_claim_type_falls_back_unknown_not_other():
    row = supervised.build_feature_row(_claim(claim_type=None), {}, {}, [])
    assert row["claim_type"] == supervised.UNKNOWN_CATEGORY
    row2 = supervised.build_feature_row(_claim(claim_type="   "), {}, {}, [])
    assert row2["claim_type"] == supervised.UNKNOWN_CATEGORY


def test_missing_country_unknown():
    row = supervised.build_feature_row(_claim(country=None), {}, {}, [])
    assert row["country"] == supervised.UNKNOWN_CATEGORY


def test_numeric_missing_invalid_become_nan_not_crash():
    row = supervised.build_feature_row(
        _claim(amount="not-a-number"), {}, {}, [],
    )
    assert math.isnan(row["claim_amount_usd"])
    row2 = supervised.build_feature_row(_claim(amount=None), {}, {}, [])
    assert math.isnan(row2["claim_amount_usd"])
    row3 = supervised.build_feature_row(_claim(amount=float("inf")), {}, {}, [])
    assert math.isnan(row3["claim_amount_usd"])


def test_missing_dates_not_yet_calculable():
    _, status = supervised.build_feature_row_with_status(
        _claim(incident_date=None, submission_date=None), {}, {}, [],
    )
    assert status["reporting_delay_days"] in ("not_yet_calculable", "missing_imputed")
    assert status["seasonality_flag"] in ("not_yet_calculable", "derived", "provided")
    # policy duration not calculable without effective date
    _, status2 = supervised.build_feature_row_with_status(_claim(), {}, {}, [])
    assert status2["policy_duration_months"] in ("not_yet_calculable", "missing_imputed", "derived", "provided")


def test_document_completeness_unavailable_in_live_app():
    _, status = supervised.build_feature_row_with_status(_claim(), {}, {}, [])
    assert status["document_completeness_score"] == supervised.STATUS_UNAVAILABLE_LIVE
    row = supervised.build_feature_row(_claim(), {}, {}, [])
    assert math.isnan(row["document_completeness_score"])  # not silently filled; pipeline imputes


def test_validate_feature_row_catches_problems():
    good = supervised.build_feature_row(_claim(), {}, {}, [])
    assert supervised.validate_feature_row(good) == []
    bad = dict(good)
    bad["claim_amount_usd"] = float("inf")
    assert any("infinite" in p for p in supervised.validate_feature_row(bad))
    bad2 = dict(good)
    del bad2["country"]
    assert any("missing feature" in p for p in supervised.validate_feature_row(bad2))
    bad3 = dict(good)
    bad3["country"] = "   "
    assert any("empty" in p for p in supervised.validate_feature_row(bad3))


# --------------------------------------------------------------------------
# 3. amount_deviation_zscore canonical definition (training == inference)
# --------------------------------------------------------------------------
def test_amount_reference_population_std_per_country():
    frame = pd.DataFrame({
        "country": ["South Africa"] * 4 + ["kenya"] * 2,
        "claim_amount_usd": [100.0, 200.0, 300.0, 400.0, 50.0, 150.0],
    })
    ref = supervised.compute_amount_reference(frame)
    sa = ref["per_country"]["south africa"]
    assert sa["n"] == 4
    assert sa["mean"] == pytest.approx(250.0)
    # population std ddof=0
    assert sa["std"] == pytest.approx(np.std([100, 200, 300, 400], ddof=0))
    assert "kenya" in ref["per_country"]
    assert ref["global"]["n"] == 6


def test_apply_amount_reference_zscore_and_fallback():
    ref = supervised.compute_amount_reference(pd.DataFrame({
        "country": ["South Africa"] * 4, "claim_amount_usd": [100.0, 200.0, 300.0, 400.0],
    }))
    z = supervised.apply_amount_reference(250.0, "South Africa", ref)
    assert z == pytest.approx(0.0, abs=1e-9)
    # unknown country -> global fallback
    z_unknown = supervised.apply_amount_reference(250.0, "Atlantis", ref)
    assert math.isfinite(z_unknown)
    # missing amount -> NaN (not silently zero)
    assert math.isnan(supervised.apply_amount_reference(None, "South Africa", ref))
    assert math.isnan(supervised.apply_amount_reference(float("nan"), "South Africa", ref))
    # no reference -> NaN
    assert math.isnan(supervised.apply_amount_reference(250.0, "South Africa", {}))


def test_amount_deviation_transformer_recomputes_and_is_canonical():
    T = supervised.AmountDeviationZscoreTransformer
    assert T is not None
    train = pd.DataFrame({
        "country": ["South Africa"] * 4 + ["kenya"] * 4,
        "claim_amount_usd": [100.0, 200.0, 300.0, 400.0, 50.0, 100.0, 150.0, 200.0],
        "claim_type": ["motor"] * 8,
        "policy_duration_months": [12.0] * 8,
        "previous_claims_count": [0.0] * 8,
        "reporting_delay_days": [5.0] * 8,
        "document_completeness_score": [0.8] * 8,
        "claimant_age": [40.0] * 8,
        "seasonality_flag": [0.0] * 8,
        "amount_deviation_zscore": [999.0] * 8,  # must be OVERWRITTEN
    })
    t = T()
    t.fit(train)
    out = t.transform(train)
    # canonical recompute equals apply_amount_reference for each row
    for amt, country, got in zip(train["claim_amount_usd"], train["country"], out["amount_deviation_zscore"]):
        expect = supervised.apply_amount_reference(amt, country, t.amount_reference_)
        assert got == pytest.approx(expect, abs=1e-9)
    # not the poisoned 999 input
    assert not any(out["amount_deviation_zscore"] == 999.0)


def test_amount_deviation_live_matches_training_reference():
    """Live recomputation uses stored training reference == pipeline reference."""
    ref = supervised.compute_amount_reference(pd.DataFrame({
        "country": ["South Africa"] * 4, "claim_amount_usd": [100.0, 200.0, 300.0, 400.0],
    }))
    metadata = {"amount_reference": ref}
    row = supervised.build_feature_row(
        _claim(amount=250.0, country="South Africa"), {}, {}, [], metadata=metadata
    )
    assert row["amount_deviation_zscore"] == pytest.approx(0.0, abs=1e-9)


# --------------------------------------------------------------------------
# 4. Artifact loading / missing / invalid
# --------------------------------------------------------------------------
def test_load_model_valid_artifact(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path, "m.joblib")
    path = _write_artifact(tmp_path / "m.joblib", ConstantPipeline(0.3),
                           {"version": "v1", "feature_columns": list(supervised.FEATURE_COLUMNS)})
    monkeypatch.setattr(supervised, "MODEL_PATH", path)
    art = supervised.load_model()
    assert art is not None
    assert art["metadata"]["version"] == "v1"
    assert hasattr(art["pipeline"], "predict_proba")


def test_missing_model_returns_none(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path)
    assert supervised.load_model() is None
    assert supervised.score_claim(_claim()) is None


def test_invalid_model_artifact_returns_none(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path, "bad.joblib")
    # corrupt bytes
    (tmp_path / "bad.joblib").write_bytes(b"not a joblib file at all")
    assert supervised.load_model() is None
    assert supervised.score_claim(_claim()) is None
    # not a dict
    p = _write_artifact(tmp_path / "notdict.joblib", ConstantPipeline(), None)
    import joblib
    joblib.dump([1, 2, 3], tmp_path / "notdict.joblib")
    monkeypatch.setattr(supervised, "MODEL_PATH", str(tmp_path / "notdict.joblib"))
    supervised.reset_cache()
    assert supervised.load_model() is None


def test_invalid_model_artifact_no_predict_proba(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path, "noproba.joblib")
    import joblib
    joblib.dump({"pipeline": object(), "metadata": {}}, tmp_path / "noproba.joblib")
    monkeypatch.setattr(supervised, "MODEL_PATH", str(tmp_path / "noproba.joblib"))
    assert supervised.load_model() is None


def test_missing_model_does_not_break_rule_engine(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path)
    res = fraud_engine.evaluate_claim(
        claim_data=_claim(), policy_data={"effective_date": "2022-01-01", "coverage_amount": 100000},
        customer_data={"national_id": "63-1234567-A-01"}, historical_claims=[],
    )
    assert res["risk_score"] >= 0
    assert res["supervised_probability"] is None
    assert "supervised_advisory" not in res["ensemble_method"]
    assert not any(i["code"] == "SUPERVISED_MODEL_ALERT" for i in res["indicators"])


def test_disabled_model(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path, "m.joblib")
    p = _write_artifact(tmp_path / "m.joblib", ConstantPipeline(0.9),
                        {"version": "v1", "feature_columns": list(supervised.FEATURE_COLUMNS)})
    monkeypatch.setattr(supervised, "MODEL_PATH", p)
    monkeypatch.setenv("SUPERVISED_MODEL_ENABLED", "false")
    supervised.reset_cache()
    assert supervised.load_model() is None
    assert supervised.score_claim(_claim()) is None
    status = supervised.describe_model()
    assert status["enabled"] is False
    assert status["status"] == "DISABLED"


# --------------------------------------------------------------------------
# 5. Prediction probability boundaries
# --------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [(1.0, 1.0), (0.0, 0.0), (1.5, 1.0), (-0.3, 0.0), (0.5, 0.5)])
def test_probability_boundaries(monkeypatch, tmp_path, raw, expected):
    _reset(monkeypatch, tmp_path, "m.joblib")
    p = _write_artifact(tmp_path / "m.joblib", ConstantPipeline(raw),
                        {"version": "v", "feature_columns": list(supervised.FEATURE_COLUMNS)})
    monkeypatch.setattr(supervised, "MODEL_PATH", p)
    supervised.reset_cache()
    res = supervised.score_claim(_claim())
    assert res is not None
    prob = res[0]
    assert 0.0 <= prob <= 1.0
    assert prob == pytest.approx(expected)
    assert math.isfinite(prob)


def test_nonfinite_probability_returns_none(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path, "m.joblib")
    p = _write_artifact(tmp_path / "m.joblib", NaNPipe(),
                        {"version": "v", "feature_columns": list(supervised.FEATURE_COLUMNS)})
    monkeypatch.setattr(supervised, "MODEL_PATH", p)
    supervised.reset_cache()
    assert supervised.score_claim(_claim()) is None


def test_scoring_never_raises_on_garbage(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path, "m.joblib")
    p = _write_artifact(tmp_path / "m.joblib", ConstantPipeline(0.7),
                        {"version": "v", "feature_columns": list(supervised.FEATURE_COLUMNS)})
    monkeypatch.setattr(supervised, "MODEL_PATH", p)
    supervised.reset_cache()
    # garbage claim should not raise
    res = supervised.score_claim_detailed({"amount": "x", "incident_date": "nope", "country": None})
    assert res is not None and 0.0 <= res["fraud_probability"] <= 1.0
    assert res["feature_validation"] is not None


# --------------------------------------------------------------------------
# 6. Configurable thresholds
# --------------------------------------------------------------------------
def test_threshold_from_metadata(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path, "m.joblib")
    p = _write_artifact(tmp_path / "m.joblib", ConstantPipeline(0.6),
                        {"version": "v", "feature_columns": list(supervised.FEATURE_COLUMNS),
                         "decision_threshold": 0.4})
    monkeypatch.setattr(supervised, "MODEL_PATH", p)
    supervised.reset_cache()
    prob, threshold, version = supervised.score_claim(_claim())
    assert prob == pytest.approx(0.6)
    assert threshold == pytest.approx(0.4)
    assert version == "v"


def test_threshold_defaults_half_when_absent(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path, "m.joblib")
    p = _write_artifact(tmp_path / "m.joblib", ConstantPipeline(0.6),
                        {"version": "v", "feature_columns": list(supervised.FEATURE_COLUMNS)})
    monkeypatch.setattr(supervised, "MODEL_PATH", p)
    supervised.reset_cache()
    _, threshold, _ = supervised.score_claim(_claim())
    assert threshold == pytest.approx(0.5)


def test_threshold_clamped(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path, "m.joblib")
    p = _write_artifact(tmp_path / "m.joblib", ConstantPipeline(0.6),
                        {"version": "v", "feature_columns": list(supervised.FEATURE_COLUMNS),
                         "decision_threshold": 5.0})
    monkeypatch.setattr(supervised, "MODEL_PATH", p)
    supervised.reset_cache()
    _, threshold, _ = supervised.score_claim(_claim())
    assert threshold == pytest.approx(1.0)


def test_engine_alert_uses_configurable_threshold(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path, "m.joblib")
    # probability 0.55; threshold 0.6 -> no alert; threshold 0.5 -> alert
    for thr, expect_alert in ((0.6, False), (0.5, True)):
        p = _write_artifact(tmp_path / "m.joblib", ConstantPipeline(0.55),
                            {"version": "v", "feature_columns": list(supervised.FEATURE_COLUMNS),
                             "decision_threshold": thr})
        monkeypatch.setattr(supervised, "MODEL_PATH", p)
        supervised.reset_cache()
        res = fraud_engine.evaluate_claim(
            claim_data=_claim(), policy_data={"effective_date": "2022-01-01", "coverage_amount": 100000},
            customer_data={"national_id": "63-1234567-A-01"}, historical_claims=[],
        )
        assert any(i["code"] == "SUPERVISED_MODEL_ALERT" for i in res["indicators"]) is expect_alert
        assert res["supervised_threshold"] == pytest.approx(thr)
        # advisory only: never an automatic rejection decision
        assert "auto_reject" not in res and res["risk_category"] in ("Low", "Medium", "High", "Critical")


def test_training_threshold_selection_not_accuracy():
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from ml import train_supervised as ts
    y = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    prob = np.array([0.1, 0.2, 0.35, 0.4, 0.55, 0.6, 0.65, 0.7])
    table = ts.threshold_table(y, prob, ts.DEFAULT_THRESHOLDS)
    assert [r["threshold"] for r in table] == list(ts.DEFAULT_THRESHOLDS)
    for r in table:
        assert {"precision", "recall", "f1"} <= set(r)
    chosen, table2, rationale = ts.select_threshold(y, prob, ts.DEFAULT_THRESHOLDS, objective="f1")
    assert chosen in ts.DEFAULT_THRESHOLDS
    assert "accuracy" not in rationale.lower() or "not accuracy" in rationale.lower()
    # operator override respected
    chosen_o, _, _ = ts.select_threshold(y, prob, ts.DEFAULT_THRESHOLDS, override=0.42)
    assert chosen_o == pytest.approx(0.42)


def test_threshold_table_thresholds_list():
    from ml import train_supervised as ts
    y = np.array([0, 1, 0, 1, 1, 0])
    prob = np.array([0.2, 0.8, 0.4, 0.6, 0.55, 0.1])
    rows = ts.threshold_table(y, prob, ts.DEFAULT_THRESHOLDS)
    assert len(rows) == len(ts.DEFAULT_THRESHOLDS)
    assert {0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70} == {r["threshold"] for r in rows}


# --------------------------------------------------------------------------
# 7. Training/inference feature consistency
# --------------------------------------------------------------------------
def test_training_and_inference_same_feature_space():
    from ml import train_supervised as ts
    assert list(ts.FEATURE_COLUMNS) == list(supervised.FEATURE_COLUMNS)
    assert list(ts.NUMERIC_COLUMNS) == list(supervised.NUMERIC_COLUMNS)
    assert list(ts.CATEGORICAL_COLUMNS) == list(supervised.CATEGORICAL_COLUMNS)
    # no leakage columns in training feature list
    assert not (set(ts.FEATURE_COLUMNS) & ts.LEAKAGE_COLUMNS)


def test_training_pipeline_has_canonical_zscore_step():
    from ml import train_supervised as ts
    pipe = ts.make_pipeline("logistic", 42)
    assert "amount_zscore" in pipe.named_steps
    assert isinstance(pipe.named_steps["amount_zscore"], supervised.AmountDeviationZscoreTransformer)
    # preprocessing + classifier inside one pipeline (fitted per fold)
    assert "preprocess" in pipe.named_steps and "classifier" in pipe.named_steps


def test_training_pipeline_feature_order_matches_inference():
    from ml import train_supervised as ts
    pipe = ts.make_pipeline("random_forest", 42)
    pre = pipe.named_steps["preprocess"]
    num = list(pre.transformers[0][2])
    cat = list(pre.transformers[1][2])
    assert num == list(supervised.NUMERIC_COLUMNS)
    assert cat == list(supervised.CATEGORICAL_COLUMNS)
    assert set(num) | set(cat) == set(supervised.FEATURE_COLUMNS)


# --------------------------------------------------------------------------
# 8. Model version reporting / monitoring
# --------------------------------------------------------------------------
def test_describe_model_not_installed(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path)
    status = supervised.describe_model()
    assert status["installed"] is False
    assert status["status"] == "NOT_INSTALLED"
    assert status["advisory_only"] is True
    # nothing invented
    assert status.get("roc_auc") is None
    assert status.get("version") is None


def test_describe_model_installed_fields(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path, "m.joblib")
    meta = {
        "version": "supervised-test-v1",
        "model_kind": "logistic",
        "trained_at": "2026-11-26T00:00:00+00:00",
        "training_rows": 360000,
        "fraud_rows": 49197,
        "legitimate_rows": 310803,
        "sources": ["baseline.csv (120,000 rows)", "enhanced_detection.csv (120,000 rows)", "fraud_wave.csv (120,000 rows)"],
        "decision_threshold": 0.42,
        "roc_auc": 0.7, "roc_auc_mean": 0.7,
        "pr_auc": 0.4, "pr_auc_mean": 0.4,
        "precision": 0.5, "precision_mean": 0.5,
        "recall": 0.6, "recall_mean": 0.6,
        "f1": 0.55, "f1_mean": 0.55,
        "known_limitations": ["synthetic data only", "not production-validated"],
        "training_data_limitations": "synthetic",
        "feature_columns": list(supervised.FEATURE_COLUMNS),
    }
    p = _write_artifact(tmp_path / "m.joblib", ConstantPipeline(0.5), meta)
    monkeypatch.setattr(supervised, "MODEL_PATH", p)
    supervised.reset_cache()
    s = supervised.describe_model()
    assert s["installed"] is True and s["enabled"] is True
    assert s["version"] == "supervised-test-v1" and s["model_version"] == "supervised-test-v1"
    assert s["last_training_date"] == "2026-11-26T00:00:00+00:00"
    assert s["training_rows"] == 360000
    assert s["roc_auc"] == pytest.approx(0.7)
    assert s["pr_auc"] == pytest.approx(0.4)
    assert s["precision"] == pytest.approx(0.5)
    assert s["recall"] == pytest.approx(0.6)
    assert s["f1"] == pytest.approx(0.55)
    assert s["decision_threshold"] == pytest.approx(0.42)
    assert "synthetic data only" in s["known_limitations"]
    assert s["training_data_limitations"] == "synthetic"
    assert len(s["training_data_sources"]) == 3
    assert s["feature_columns"] == list(supervised.FEATURE_COLUMNS)


def test_unversioned_model_reported_honestly(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path, "m.joblib")
    p = _write_artifact(tmp_path / "m.joblib", ConstantPipeline(0.5),
                        {"feature_columns": list(supervised.FEATURE_COLUMNS)})
    monkeypatch.setattr(supervised, "MODEL_PATH", p)
    supervised.reset_cache()
    s = supervised.describe_model()
    assert s["version"] == "unversioned"
    assert s["roc_auc"] is None and s["pr_auc"] is None and s["precision"] is None


def test_model_status_api(monkeypatch, tmp_path):
    """Wired to GET /model-performance/supervised-model."""
    _reset(monkeypatch, tmp_path)
    from fastapi.testclient import TestClient
    from backend.app.main import app
    # ensure no artifact
    monkeypatch.setattr(supervised, "MODEL_PATH", str(tmp_path / "absent.joblib"))
    supervised.reset_cache()
    # find a way to authenticate: admin in seeded ephemeral db
    from tests.helpers import admin_headers
    client = TestClient(app)
    r = client.get("/model-performance/supervised-model", headers=admin_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["installed"] is False
    assert body["advisory_only"] is True
    assert body["status"] == "NOT_INSTALLED"


# --------------------------------------------------------------------------
# 9. Existing rule-based fraud detection preserved
# --------------------------------------------------------------------------
def _policy():
    return {"effective_date": "2024-01-01", "coverage_amount": 100000.0}


def _customer():
    return {"customer_id": "C", "national_id": "63-1234567-A-01"}


def test_rule_inception_fraud():
    res = fraud_engine.evaluate_claim(
        claim_data={"claim_id": "X", "policy_number": "P", "amount": 1000.0,
                    "incident_date": "2024-01-10", "submission_date": "2024-01-12", "claim_type": "Accident"},
        policy_data=_policy(), customer_data=_customer(), historical_claims=[],
    )
    assert any(i["code"] == "EARLY_POLICY_INCEPTION_CLAIM" for i in res["indicators"])


def test_rule_incident_before_policy():
    res = fraud_engine.evaluate_claim(
        claim_data={"claim_id": "X", "policy_number": "P", "amount": 1000.0,
                    "incident_date": "2023-12-01", "submission_date": "2024-01-12", "claim_type": "Accident"},
        policy_data=_policy(), customer_data=_customer(), historical_claims=[],
    )
    assert any(i["code"] == "INCIDENT_PRIOR_TO_POLICY_START" for i in res["indicators"])


def test_rule_exceeds_coverage():
    res = fraud_engine.evaluate_claim(
        claim_data={"claim_id": "X", "policy_number": "P", "amount": 200000.0,
                    "incident_date": "2024-06-01", "submission_date": "2024-06-02", "claim_type": "Death"},
        policy_data=_policy(), customer_data=_customer(), historical_claims=[],
    )
    assert any(i["code"] == "CLAIM_EXCEEDS_COVERAGE_LIMIT" for i in res["indicators"])


def test_rule_excessive_latency():
    res = fraud_engine.evaluate_claim(
        claim_data={"claim_id": "X", "policy_number": "P", "amount": 1000.0,
                    "incident_date": "2024-01-01", "submission_date": "2025-06-01", "claim_type": "Death"},
        policy_data={"effective_date": "2020-01-01", "coverage_amount": 100000}, customer_data=_customer(),
        historical_claims=[],
    )
    assert any(i["code"] == "EXCESSIVE_SUBMISSION_LATENCY" for i in res["indicators"])


def test_rule_unverified_national_id():
    res = fraud_engine.evaluate_claim(
        claim_data=_claim(), policy_data=_policy(), customer_data={"customer_id": "C", "national_id": ""},
        historical_claims=[],
    )
    assert any(i["code"] == "UNVERIFIED_NATIONAL_IDENTITY" for i in res["indicators"])


def test_rule_recent_beneficiary_alteration():
    res = fraud_engine.evaluate_claim(
        claim_data=_claim(), policy_data=_policy(), customer_data=_customer(),
        historical_claims=[], recent_beneficiary_change=True,
    )
    assert any(i["code"] == "RECENT_BENEFICIARY_ALTERATION" for i in res["indicators"])


def test_rule_high_claim_frequency():
    hist = [{"claim_id": f"h{i}", "amount": 100.0, "incident_date": "2023-01-01", "policy_number": "P"} for i in range(3)]
    res = fraud_engine.evaluate_claim(
        claim_data=_claim(policy_number="P", incident_date="2024-06-01"), policy_data={"effective_date": "2020-01-01", "coverage_amount": 100000},
        customer_data=_customer(), historical_claims=hist,
    )
    assert any(i["code"] == "HIGH_CLAIM_FREQUENCY" for i in res["indicators"])


def test_advisory_only_no_auto_decision(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path, "m.joblib")
    p = _write_artifact(tmp_path / "m.joblib", ConstantPipeline(1.0),
                        {"version": "v", "feature_columns": list(supervised.FEATURE_COLUMNS), "decision_threshold": 0.0})
    monkeypatch.setattr(supervised, "MODEL_PATH", p)
    supervised.reset_cache()
    res = fraud_engine.evaluate_claim(
        claim_data=_claim(), policy_data=_policy(), customer_data=_customer(), historical_claims=[],
    )
    # supervised adds bounded advisory weight only; never an automatic rejection
    sup = [i for i in res["indicators"] if i["code"] == "SUPERVISED_MODEL_ALERT"]
    assert sup and sup[0]["weight"] <= 25.0
    assert res["risk_category"] in ("Low", "Medium", "High", "Critical")


# --------------------------------------------------------------------------
# 10. Integration with existing fraud scoring engine
# --------------------------------------------------------------------------
def test_engine_integration_supervised_plus_rules(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path, "m.joblib")
    p = _write_artifact(tmp_path / "m.joblib", ConstantPipeline(0.9),
                        {"version": "sup-v1", "feature_columns": list(supervised.FEATURE_COLUMNS), "decision_threshold": 0.5})
    monkeypatch.setattr(supervised, "MODEL_PATH", p)
    supervised.reset_cache()
    res = fraud_engine.evaluate_claim(
        claim_data=_claim(incident_date="2024-01-05", submission_date="2024-01-06"),
        policy_data={"effective_date": "2024-01-01", "coverage_amount": 100000},
        customer_data={"national_id": "63-1234567-A-01"}, historical_claims=[],
    )
    assert res["supervised_probability"] == pytest.approx(0.9)
    assert res["supervised_model_version"] == "sup-v1"
    assert "supervised_advisory" in res["ensemble_method"]
    # rule indicators still present alongside supervised
    codes = {i["code"] for i in res["indicators"]}
    assert "SUPERVISED_MODEL_ALERT" in codes
    assert "EARLY_POLICY_INCEPTION_CLAIM" in codes  # incident 4 days after inception


def test_engine_robust_to_missing_fields(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path, "m.joblib")
    p = _write_artifact(tmp_path / "m.joblib", ConstantPipeline(0.5),
                        {"version": "v", "feature_columns": list(supervised.FEATURE_COLUMNS)})
    monkeypatch.setattr(supervised, "MODEL_PATH", p)
    supervised.reset_cache()
    # minimal claim: no dates, no type, no amount, unknown everything
    res = fraud_engine.evaluate_claim(
        claim_data={}, policy_data={}, customer_data={}, historical_claims=[],
    )
    assert 0.0 <= res["risk_score"] <= 100.0
    assert res["supervised_probability"] is None or 0.0 <= res["supervised_probability"] <= 1.0


def test_assess_claim_fraud_no_fabrication(monkeypatch, tmp_path):
    _reset(monkeypatch, tmp_path)
    from backend.app.ml.inference import assess_claim_fraud
    res = assess_claim_fraud({"amount": 1000.0})  # no history/policy/customer
    codes = {i["code"] for i in res["indicators"]}
    # no synthetic history fabricated -> HIGH_CLAIM_FREQUENCY not triggered
    assert "HIGH_CLAIM_FREQUENCY" not in codes
    # no fake national id -> UNVERIFIED_NATIONAL_IDENTITY honestly triggered
    assert "UNVERIFIED_NATIONAL_IDENTITY" in codes
    assert res["supervised_probability"] is None
