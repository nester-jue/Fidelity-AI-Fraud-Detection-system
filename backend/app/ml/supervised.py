"""Optional supervised fraud classifier integration.

The model is trained from the labelled CSV datasets by ``ml/train_supervised.py``.
It is deliberately an *advisory signal*: the score is added to the explainable
rule engine and never rejects a claim by itself. If no artefact is present, the
engine continues unchanged.
"""
from __future__ import annotations

import json
import logging
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("fraud_ml")

MODEL_PATH = Path(
    os.getenv(
        "FRAUD_MODEL_PATH",
        str(Path(__file__).resolve().parent / "models" / "fraud_classifier.joblib"),
    )
)
ENABLED_ENV = "SUPERVISED_MODEL_ENABLED"

# Must stay in the same order as ml/train_supervised.py.
FEATURE_COLUMNS: Tuple[str, ...] = (
    "country",
    "year",
    "claim_amount_usd",
    "policy_duration_months",
    "previous_claims_count",
    "reporting_delay_days",
    "document_completeness_score",
    "claimant_age",
    "claim_type",
    "seasonality_flag",
    "amount_deviation_zscore",
    "duplicate_claim_flag",
)
NUMERIC_COLUMNS: Tuple[str, ...] = (
    "year",
    "claim_amount_usd",
    "policy_duration_months",
    "previous_claims_count",
    "reporting_delay_days",
    "document_completeness_score",
    "claimant_age",
    "seasonality_flag",
    "amount_deviation_zscore",
    "duplicate_claim_flag",
)
CATEGORICAL_COLUMNS: Tuple[str, ...] = ("country", "claim_type")

_CACHE: Optional[Dict[str, Any]] = None
_CACHE_PATH: Optional[str] = None


def supervised_enabled(settings: Any = None) -> bool:
    """Explicit opt-out wins; otherwise the model is used when it exists."""
    raw = os.getenv(ENABLED_ENV)
    if raw is not None:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if settings is not None and hasattr(settings, "SUPERVISED_MODEL_ENABLED"):
        return bool(settings.SUPERVISED_MODEL_ENABLED)
    return True


def _parse_date(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    return None


def _number(value: Any, default: float) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def _default(metadata: Dict[str, Any], name: str, fallback: float) -> float:
    return _number(metadata.get("defaults", {}).get(name), fallback)


def build_feature_row(
    claim_data: Dict[str, Any],
    policy_data: Optional[Dict[str, Any]] = None,
    customer_data: Optional[Dict[str, Any]] = None,
    historical_claims: Optional[List[Dict[str, Any]]] = None,
    indicators: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Map a live claim into the exact feature space used during training."""
    metadata = metadata or {}
    policy_data = policy_data or {}
    customer_data = customer_data or {}
    history = historical_claims or []

    incident = _parse_date(claim_data.get("incident_date"))
    submission = _parse_date(claim_data.get("submission_date"))
    effective = _parse_date(policy_data.get("effective_date"))

    amount = _number(claim_data.get("amount"), _default(metadata, "claim_amount_usd", 0.0))
    delay = claim_data.get("reporting_delay_days")
    if delay is None and incident and submission:
        delay = (submission - incident).days
    delay = max(0.0, _number(delay, _default(metadata, "reporting_delay_days", 0.0)))

    inception_days = claim_data.get("days_since_inception")
    if inception_days is None and incident and effective:
        inception_days = (incident - effective).days
    if inception_days is None:
        duration = _default(metadata, "policy_duration_months", 0.0)
    else:
        duration = max(0.0, float(inception_days)) / 30.4375

    previous = claim_data.get("previous_claims_count")
    if previous is None:
        previous = len(history)
    previous = max(0.0, _number(previous, _default(metadata, "previous_claims_count", 0.0)))

    dob = _parse_date(customer_data.get("date_of_birth"))
    age = claim_data.get("claimant_age") or customer_data.get("claimant_age")
    if age is None and dob and incident:
        age = (incident - dob).days / 365.2425
    age = max(0.0, _number(age, _default(metadata, "claimant_age", 0.0)))

    completeness = claim_data.get("document_completeness_score")
    completeness = min(1.0, max(0.0, _number(
        completeness, _default(metadata, "document_completeness_score", 0.5)
    )))

    deviation = claim_data.get("amount_deviation_zscore")
    if deviation is None:
        prior_amounts = [
            _number(c.get("amount"), 0.0) for c in history
            if _number(c.get("amount"), 0.0) > 0
        ]
        if len(prior_amounts) >= 2:
            mean = sum(prior_amounts) / len(prior_amounts)
            variance = sum((v - mean) ** 2 for v in prior_amounts) / len(prior_amounts)
            std = math.sqrt(variance)
            deviation = (amount - mean) / std if std > 1e-9 else 0.0
    deviation = _number(deviation, _default(metadata, "amount_deviation_zscore", 0.0))

    seasonality = claim_data.get("seasonality_flag")
    if seasonality is None:
        seasonality = 1 if incident and incident.month in (11, 12, 1) else 0
    seasonality = 1 if _number(seasonality, 0) >= 0.5 else 0

    duplicate_flag = claim_data.get("duplicate_claim_flag")
    if duplicate_flag is None:
        duplicate_flag = any(
            str(i.get("code", "")).upper() == "DUPLICATE_CLAIM_DETECTED"
            for i in (indicators or [])
        )
    duplicate_flag = 1 if _number(duplicate_flag, 0) >= 0.5 else 0

    return {
        "country": str(claim_data.get("country") or policy_data.get("country")
                       or metadata.get("defaults", {}).get("country") or "Unknown"),
        "year": float(incident.year if incident else _default(metadata, "year", 2024)),
        "claim_amount_usd": amount,
        "policy_duration_months": duration,
        "previous_claims_count": previous,
        "reporting_delay_days": delay,
        "document_completeness_score": completeness,
        "claimant_age": age,
        "claim_type": str(claim_data.get("claim_type") or "other").strip().lower(),
        "seasonality_flag": float(seasonality),
        "amount_deviation_zscore": deviation,
        "duplicate_claim_flag": float(duplicate_flag),
    }


def load_model(settings: Any = None) -> Optional[Dict[str, Any]]:
    """Load (and cache) the trained pipeline; return None when unavailable."""
    global _CACHE, _CACHE_PATH
    if not supervised_enabled(settings):
        return None
    path = str(MODEL_PATH)
    if _CACHE is not None and _CACHE_PATH == path:
        return _CACHE
    if not os.path.exists(path):
        return None
    try:
        import joblib  # imported lazily so the engine works without ML deps
        artefact = joblib.load(path)
        if not isinstance(artefact, dict) or "pipeline" not in artefact:
            raise ValueError("unexpected model artefact format")
        _CACHE = artefact
        _CACHE_PATH = path
        return artefact
    except Exception as exc:  # never let a broken artefact break scoring
        logger.warning("Supervised fraud model could not be loaded: %s", exc)
        _CACHE = None
        return None


def score_claim(
    claim_data: Dict[str, Any],
    policy_data: Optional[Dict[str, Any]] = None,
    customer_data: Optional[Dict[str, Any]] = None,
    historical_claims: Optional[List[Dict[str, Any]]] = None,
    indicators: Optional[List[Dict[str, Any]]] = None,
    settings: Any = None,
) -> Optional[Tuple[float, float, str]]:
    """Return ``(fraud_probability, decision_threshold, model_version)``."""
    artefact = load_model(settings)
    if not artefact:
        return None
    metadata = artefact.get("metadata", {})
    row = build_feature_row(
        claim_data, policy_data, customer_data, historical_claims, indicators, metadata
    )
    columns = tuple(metadata.get("feature_columns", FEATURE_COLUMNS))
    import pandas as pd  # lazy: only needed when a model is actually installed
    frame = pd.DataFrame([[row[c] for c in columns]], columns=list(columns))
    probability = float(artefact["pipeline"].predict_proba(frame)[0, 1])
    threshold = float(metadata.get("decision_threshold", 0.5))
    return probability, threshold, str(metadata.get("version", "unversioned"))


def metadata_summary() -> Optional[Dict[str, Any]]:
    artefact = load_model()
    if not artefact:
        return None
    meta = dict(artefact.get("metadata", {}))
    meta.pop("defaults", None)
    return meta


def describe_model() -> Dict[str, Any]:
    """Small, honest status payload for the Security Centre / model dashboard."""
    meta = metadata_summary()
    if not meta:
        return {
            "status": "NOT_INSTALLED",
            "detail": "No supervised model artefact is present. Rule and isolation scoring remain active.",
        }
    roc_auc = meta.get("roc_auc_mean", meta.get("test_roc_auc_mean"))
    pr_auc = meta.get("pr_auc_mean", meta.get("test_pr_auc_mean"))
    return {
        "status": "INSTALLED",
        "detail": "Supervised classifier is installed and used as an advisory signal only.",
        "version": meta.get("version"),
        "trained_at": meta.get("trained_at"),
        "training_rows": meta.get("training_rows"),
        "test_roc_auc_mean": roc_auc,
        "test_pr_auc_mean": pr_auc,
        "decision_threshold": meta.get("decision_threshold"),
        "report": meta.get("report_path"),
    }


def write_report(path: str) -> bool:
    meta = metadata_summary()
    if not meta:
        return False
    Path(path).write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
    return True
