"""Optional supervised fraud classifier integration.

The model is trained from the labelled CSV datasets by ``ml/train_supervised.py``.
It is deliberately an *advisory signal*: the score is added to the explainable
rule engine and never rejects a claim by itself. If no artefact is present, or
the artefact cannot be loaded, the engine continues unchanged.

Feature-set guarantees (see section "CORRECT DATA LEAKAGE" of the audit):

* ``duplicate_claim_flag`` is NOT a supervised-model feature. Duplicate-claim
  detection lives in the rule-based fraud engine (``DUPLICATE_CLAIM_DETECTED``).
  In the synthetic datasets this flag is partly generated *from* ``fraud_label``
  (``dup_base = 0.05 + 0.25 * fraud_label`` in ``datasets/generate_dataset.py``),
  so training on it would leak the target.
* ``year`` is NOT a feature. Every supplied training dataset contains only 2024.
* Nothing derived from the label or from post-decision investigation outcomes
  (``fraud_label``, ``fraud_probability``, ``fraud_scheme_type``,
  ``detection_method``, ``recovery_amount_usd``, ``record_id``) is used.

Training/inference consistency:

* One shared :func:`build_feature_row` maps a live claim into the exact feature
  space used at training time; feature names and order come from the saved
  artifact (``metadata.feature_columns``), falling back to :data:`FEATURE_COLUMNS`.
* Category strings are normalised (``strip().lower()``); unknown categories are
  passed through and ignored by the one-hot encoder, never an error.
* ``amount_deviation_zscore`` has ONE canonical definition everywhere:
  ``(claim_amount_usd - reference_mean[country]) / reference_std[country]`` with
  population std (ddof=0), per-country reference falling back to a global
  reference. References are fitted on training data only and stored inside the
  pipeline (:class:`AmountDeviationZscoreTransformer`). Live inference recomputes
  it from the live claim amount + country; it is NOT estimated from claimant
  history and no dataset median is silently substituted.
* Missing / un-calculable features are reported explicitly in
  ``feature_status`` (``provided`` / ``derived`` / ``missing_imputed`` /
  ``not_yet_calculable`` / ``unavailable_in_live_app`` / ``invalid_imputed`` /
  ``unknown_category`` / ``recomputed_by_pipeline``). Numeric imputation then
  uses training-fold medians inside the saved pipeline; consequences are
  documented, not silent.
* ``score_claim`` returns a probability in ``[0.0, 1.0]``; a claim can never
  produce NaN/inf or crash scoring. ``None`` is returned when no usable model
  is installed so the rule engine continues unchanged.
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

# ---------------------------------------------------------------------------
# Feature set. Must stay in the same order as ml/train_supervised.py.
# Removed for target leakage: "duplicate_claim_flag"; removed as constant: "year".
# ---------------------------------------------------------------------------
FEATURE_COLUMNS: Tuple[str, ...] = (
    "country",
    "claim_amount_usd",
    "policy_duration_months",
    "previous_claims_count",
    "reporting_delay_days",
    "document_completeness_score",
    "claimant_age",
    "claim_type",
    "seasonality_flag",
    "amount_deviation_zscore",
)
NUMERIC_COLUMNS: Tuple[str, ...] = (
    "claim_amount_usd",
    "policy_duration_months",
    "previous_claims_count",
    "reporting_delay_days",
    "document_completeness_score",
    "claimant_age",
    "seasonality_flag",
    "amount_deviation_zscore",
)
CATEGORICAL_COLUMNS: Tuple[str, ...] = ("country", "claim_type")

# Columns present in the source CSVs that must never be model inputs.
LEAKAGE_COLUMNS: Tuple[str, ...] = (
    "fraud_label",            # the target itself
    "fraud_probability",      # effectively a pre-computed answer; label is sampled from it
    "fraud_scheme_type",      # known only after investigation; 'none' iff non-fraud
    "detection_method",       # outcome/process metadata; 'none' iff non-fraud
    "recovery_amount_usd",    # post-decision outcome; >0 iff fraud
    "record_id",              # identifier, not a claim attribute
    "duplicate_claim_flag",   # partly generated from fraud_label; rule engine keeps duplicate detection
    "year",                   # constant 2024 in every supplied dataset
)

UNKNOWN_CATEGORY = "unknown"

# Feature-status vocabulary (surfaced to callers; never silent).
STATUS_PROVIDED = "provided"
STATUS_DERIVED = "derived"
STATUS_MISSING_IMPUTED = "missing_imputed"
STATUS_NOT_YET_CALCULABLE = "not_yet_calculable"
STATUS_UNAVAILABLE_LIVE = "unavailable_in_live_app"
STATUS_INVALID_IMPUTED = "invalid_imputed"
STATUS_UNKNOWN_CATEGORY = "unknown_category"
STATUS_RECOMPUTED = "recomputed_by_pipeline"

# Numeric features this live application does not collect at all. They are
# imputed by the trained pipeline and flagged ``unavailable_in_live_app``.
LIVE_UNAVAILABLE_NUMERIC: Tuple[str, ...] = ("document_completeness_score",)

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


def _normalize_category(value: Any, fallback: str = UNKNOWN_CATEGORY) -> str:
    """Match training-time normalisation: strip + lowercase; empty -> unknown."""
    if value is None:
        return fallback
    text = str(value).strip().lower()
    return text if text else fallback


def _numeric_or_nan(value: Any) -> float:
    """Return a finite float or NaN (NaN is imputed inside the trained pipeline)."""
    try:
        result = float(value)
        return result if math.isfinite(result) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def _default(metadata: Dict[str, Any], name: str, fallback: float) -> float:
    return _number(metadata.get("defaults", {}).get(name), fallback)


# ---------------------------------------------------------------------------
# Canonical amount_deviation_zscore (shared by training and live inference)
# ---------------------------------------------------------------------------
def normalize_country_for_reference(value: Any) -> str:
    return _normalize_category(value, fallback="")


def compute_amount_reference(frame: Any) -> Dict[str, Any]:
    """Population mean/std (ddof=0) of claim_amount_usd per country + global.

    ``frame`` is a pandas DataFrame containing ``claim_amount_usd`` and,
    optionally, ``country``. Only the data passed in is used (training folds).
    """
    import pandas as pd  # local import; backend works without pandas until scoring

    amounts = pd.to_numeric(frame["claim_amount_usd"], errors="coerce")
    # Drop NaN AND +/-inf: a single inf would poison mean/std.
    finite = amounts.notna() & (amounts != float("inf")) & (amounts != float("-inf"))
    valid = amounts[finite]
    global_mean = float(valid.mean()) if len(valid) else 0.0
    global_std = float(valid.std(ddof=0)) if len(valid) else 0.0
    per_country: Dict[str, Dict[str, float]] = {}
    if "country" in frame.columns:
        tmp = pd.DataFrame({
            "country": frame["country"].map(normalize_country_for_reference),
            "amount": amounts,
        })
        tmp = tmp[finite.to_numpy() if hasattr(finite, "to_numpy") else finite]
        for country, group in tmp.groupby("country"):
            if not country or len(group) < 1:
                continue
            vals = group["amount"]
            per_country[country] = {
                "mean": float(vals.mean()),
                "std": float(vals.std(ddof=0)) if len(vals) > 1 else 0.0,
                "n": int(len(vals)),
            }
    return {
        "global": {"mean": global_mean, "std": global_std, "n": int(len(valid))},
        "per_country": per_country,
        "definition": "(claim_amount_usd - mean) / std; population std ddof=0; "
                      "per-country reference with global fallback; fitted on training data only",
    }


def apply_amount_reference(amount: Any, country: Any, reference: Dict[str, Any]) -> float:
    """Compute canonical zscore for one claim. NaN when not calculable."""
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return float("nan")
    if not math.isfinite(value) or not reference:
        return float("nan")
    key = normalize_country_for_reference(country)
    stats = (reference.get("per_country") or {}).get(key) or reference.get("global") or {}
    mean = _number(stats.get("mean"), float("nan"))
    std = _number(stats.get("std"), float("nan"))
    if not math.isfinite(mean) or not math.isfinite(std):
        return float("nan")
    if std <= 1e-9:
        return 0.0
    return (value - mean) / std


try:  # pragma: no cover - sklearn is a hard dependency for training; optional at runtime
    from sklearn.base import BaseEstimator, TransformerMixin

    class AmountDeviationZscoreTransformer(BaseEstimator, TransformerMixin):
        """sklearn pipeline step that (re)computes ``amount_deviation_zscore``.

        Fitted inside every CV training fold (never on test data). In
        ``transform`` it OVERWRITES ``amount_deviation_zscore`` with the
        canonical population z-score derived from ``claim_amount_usd`` and
        ``country`` using statistics learned in ``fit``. Rows whose amount is
        missing get NaN, which the downstream imputer fills with the training
        median. Output is not yet scaled.
        """

        def __init__(self, amount_column: str = "claim_amount_usd",
                     country_column: str = "country",
                     target_column: str = "amount_deviation_zscore"):
            self.amount_column = amount_column
            self.country_column = country_column
            self.target_column = target_column

        def fit(self, X: Any, y: Any = None) -> "AmountDeviationZscoreTransformer":
            self.amount_reference_ = compute_amount_reference(
                X if hasattr(X, "columns") else _to_frame(X)
            )
            return self

        def transform(self, X: Any) -> Any:
            import pandas as pd

            frame = X.copy() if hasattr(X, "copy") else _to_frame(X)
            reference = getattr(self, "amount_reference_", {}) or {}
            amounts = frame[self.amount_column] if self.amount_column in frame.columns else None
            countries = (frame[self.country_column] if self.country_column in frame.columns
                         else pd.Series([None] * len(frame), index=frame.index))
            targets = [
                apply_amount_reference(a, c, reference)
                for a, c in zip(
                    amounts if amounts is not None else [None] * len(frame),
                    countries,
                )
            ]
            frame[self.target_column] = targets
            return frame

except Exception:  # pragma: no cover - sklearn unavailable
    AmountDeviationZscoreTransformer = None  # type: ignore[assignment]


def _to_frame(X: Any) -> Any:
    import pandas as pd

    return pd.DataFrame(X)


# ---------------------------------------------------------------------------
# Live feature construction
# ---------------------------------------------------------------------------
def build_feature_row(
    claim_data: Dict[str, Any],
    policy_data: Optional[Dict[str, Any]] = None,
    customer_data: Optional[Dict[str, Any]] = None,
    historical_claims: Optional[List[Dict[str, Any]]] = None,
    indicators: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Map a live claim into the exact feature space used during training.

    ``indicators`` (rule-engine findings) is accepted for API compatibility but
    is NOT used as a supervised feature; ``duplicate_claim_flag`` was removed.
    ``historical_claims`` is used only for ``previous_claims_count`` when the
    claim does not supply it. Missing values are passed as NaN for the trained
    pipeline to impute; nothing is silently filled with dataset statistics.
    """
    row, _status = build_feature_row_with_status(
        claim_data, policy_data, customer_data, historical_claims, indicators, metadata
    )
    return row


def build_feature_row_with_status(
    claim_data: Dict[str, Any],
    policy_data: Optional[Dict[str, Any]] = None,
    customer_data: Optional[Dict[str, Any]] = None,
    historical_claims: Optional[List[Dict[str, Any]]] = None,
    indicators: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Return ``(feature_row, feature_status)``.

    ``feature_status`` maps every model feature to one of:
    provided / derived / missing_imputed / not_yet_calculable /
    unavailable_in_live_app / invalid_imputed / unknown_category /
    recomputed_by_pipeline.
    """
    metadata = metadata or {}
    policy_data = policy_data or {}
    customer_data = customer_data or {}
    history = historical_claims or []
    status: Dict[str, str] = {}

    incident = _parse_date(claim_data.get("incident_date"))
    submission = _parse_date(claim_data.get("submission_date"))
    effective = _parse_date(policy_data.get("effective_date"))

    # ---- claim_amount_usd -------------------------------------------------
    raw_amount = claim_data.get("amount", claim_data.get("claim_amount_usd"))
    amount = _numeric_or_nan(raw_amount)
    if math.isnan(amount):
        status["claim_amount_usd"] = STATUS_INVALID_IMPUTED if raw_amount is not None else STATUS_MISSING_IMPUTED
    else:
        status["claim_amount_usd"] = STATUS_PROVIDED

    # ---- policy_duration_months ------------------------------------------
    inception_days = claim_data.get("days_since_inception")
    if inception_days is None and incident and effective:
        inception_days = (incident - effective).days
        inception_source = STATUS_DERIVED
    else:
        inception_source = STATUS_PROVIDED
    if inception_days is None:
        duration = float("nan")
        status["policy_duration_months"] = (
            STATUS_NOT_YET_CALCULABLE if (incident and not effective) or (effective and not incident)
            else STATUS_MISSING_IMPUTED
        )
    else:
        duration = max(0.0, _numeric_or_nan(inception_days))
        if math.isnan(duration):
            status["policy_duration_months"] = STATUS_INVALID_IMPUTED
        else:
            duration = duration / 30.4375
            status["policy_duration_months"] = inception_source

    # ---- previous_claims_count -------------------------------------------
    previous = claim_data.get("previous_claims_count")
    if previous is None:
        previous = len(history)
        status["previous_claims_count"] = STATUS_DERIVED
    else:
        status["previous_claims_count"] = STATUS_PROVIDED
    previous = _numeric_or_nan(previous)
    if math.isnan(previous):
        status["previous_claims_count"] = STATUS_INVALID_IMPUTED
    else:
        previous = max(0.0, previous)

    # ---- reporting_delay_days --------------------------------------------
    raw_delay = claim_data.get("reporting_delay_days")
    if raw_delay is not None:
        delay = _numeric_or_nan(raw_delay)
        if math.isnan(delay):
            status["reporting_delay_days"] = STATUS_INVALID_IMPUTED
        else:
            delay = max(0.0, delay)
            status["reporting_delay_days"] = STATUS_PROVIDED
    elif incident and submission:
        delay = max(0.0, float((submission - incident).days))
        status["reporting_delay_days"] = STATUS_DERIVED
    else:
        delay = float("nan")
        status["reporting_delay_days"] = STATUS_NOT_YET_CALCULABLE

    # ---- document_completeness_score -------------------------------------
    completeness = claim_data.get("document_completeness_score")
    if completeness is None:
        status["document_completeness_score"] = STATUS_UNAVAILABLE_LIVE
        completeness_value = float("nan")
    else:
        raw_completeness = _numeric_or_nan(completeness)
        if math.isnan(raw_completeness):
            status["document_completeness_score"] = STATUS_INVALID_IMPUTED
            completeness_value = float("nan")
        else:
            clamped = min(1.0, max(0.0, raw_completeness))
            status["document_completeness_score"] = (
                STATUS_PROVIDED if clamped == raw_completeness else "provided_out_of_range_clamped"
            )
            completeness_value = clamped

    # ---- claimant_age -----------------------------------------------------
    dob = _parse_date(customer_data.get("date_of_birth"))
    raw_age = claim_data.get("claimant_age", customer_data.get("claimant_age"))
    if raw_age is not None:
        age = _numeric_or_nan(raw_age)
        status["claimant_age"] = STATUS_PROVIDED if not math.isnan(age) else STATUS_INVALID_IMPUTED
    elif dob and incident:
        age = (incident - dob).days / 365.2425
        status["claimant_age"] = STATUS_DERIVED
    else:
        age = float("nan")
        status["claimant_age"] = (
            STATUS_NOT_YET_CALCULABLE if (dob and not incident) else STATUS_MISSING_IMPUTED
        )
    if not math.isnan(age):
        age = max(0.0, age)

    # ---- country ----------------------------------------------------------
    raw_country = claim_data.get("country") or policy_data.get("country") or customer_data.get("country")
    country = _normalize_category(raw_country, fallback=UNKNOWN_CATEGORY)
    known_countries = _known_categories(metadata, "country")
    if raw_country is None or not str(raw_country).strip():
        status["country"] = STATUS_MISSING_IMPUTED
    elif known_countries and country not in known_countries:
        status["country"] = STATUS_UNKNOWN_CATEGORY
    else:
        status["country"] = STATUS_PROVIDED

    # ---- claim_type -------------------------------------------------------
    raw_claim_type = claim_data.get("claim_type")
    # Consistency with training: missing -> UNKNOWN_CATEGORY (never 'other');
    # unseen categories are ignored by the one-hot encoder, never an error.
    claim_type = _normalize_category(raw_claim_type, fallback=UNKNOWN_CATEGORY)
    known_claim_types = _known_categories(metadata, "claim_type")
    if raw_claim_type is None or not str(raw_claim_type).strip():
        status["claim_type"] = STATUS_MISSING_IMPUTED
    elif known_claim_types and claim_type not in known_claim_types:
        status["claim_type"] = STATUS_UNKNOWN_CATEGORY
    else:
        status["claim_type"] = STATUS_PROVIDED

    # ---- seasonality_flag -------------------------------------------------
    seasonality = claim_data.get("seasonality_flag")
    if seasonality is None:
        if incident:
            seasonality = 1 if incident.month in (11, 12, 1) else 0
            status["seasonality_flag"] = STATUS_DERIVED
        else:
            seasonality = float("nan")
            status["seasonality_flag"] = STATUS_NOT_YET_CALCULABLE
    else:
        status["seasonality_flag"] = STATUS_PROVIDED
    seasonality_value = _numeric_or_nan(seasonality)
    seasonality_value = 1.0 if (not math.isnan(seasonality_value) and seasonality_value >= 0.5) else (
        0.0 if not math.isnan(seasonality_value) else float("nan")
    )

    # ---- amount_deviation_zscore -----------------------------------------
    # Canonical population zscore vs stored training reference. The value in
    # `claim_data` (if any) is validated but the saved pipeline recomputes it
    # from amount + country, so training and live definitions cannot diverge.
    explicit_z = _numeric_or_nan(claim_data.get("amount_deviation_zscore")) \
        if claim_data.get("amount_deviation_zscore") is not None else float("nan")
    reference = metadata.get("amount_reference") or {}
    zscore = apply_amount_reference(amount, country if country != UNKNOWN_CATEGORY else None, reference)
    if not math.isnan(explicit_z) and not reference:
        zscore = explicit_z  # no stored reference: trust an explicit value
    if math.isnan(amount):
        status["amount_deviation_zscore"] = STATUS_NOT_YET_CALCULABLE
        zscore = float("nan")
    elif reference:
        status["amount_deviation_zscore"] = STATUS_RECOMPUTED
    elif not math.isnan(explicit_z):
        status["amount_deviation_zscore"] = STATUS_PROVIDED
    else:
        status["amount_deviation_zscore"] = STATUS_NOT_YET_CALCULABLE
        zscore = float("nan")

    row = {
        "country": country,
        "claim_amount_usd": amount,
        "policy_duration_months": duration,
        "previous_claims_count": previous,
        "reporting_delay_days": delay if not math.isnan(delay) else float("nan"),
        "document_completeness_score": completeness_value,
        "claimant_age": age,
        "claim_type": claim_type,
        "seasonality_flag": seasonality_value,
        "amount_deviation_zscore": zscore,
    }
    return row, status


def _known_categories(metadata: Dict[str, Any], feature: str) -> List[str]:
    """Trained categories for a feature, if recorded in artifact metadata."""
    cats = (metadata.get("categories") or {}).get(feature)
    if cats:
        return [str(c) for c in cats]
    ref = metadata.get("amount_reference")
    if feature == "country" and ref and ref.get("per_country"):
        return list(ref["per_country"].keys())
    return []


# ---------------------------------------------------------------------------
# Feature validation
# ---------------------------------------------------------------------------
def validate_feature_row(row: Dict[str, Any], columns: Optional[List[str]] = None) -> List[str]:
    """Return a list of problems (empty == valid). Missing numerics allowed
    (the pipeline imputes) but must be NaN, never inf; strings must be str."""
    problems: List[str] = []
    cols = list(columns) if columns else list(FEATURE_COLUMNS)
    for name in cols:
        if name not in row:
            problems.append(f"missing feature: {name}")
            continue
        value = row[name]
        if name in NUMERIC_COLUMNS:
            try:
                num = float(value)
            except (TypeError, ValueError):
                problems.append(f"{name}: not numeric ({value!r})")
                continue
            if math.isinf(num):
                problems.append(f"{name}: infinite value")
        else:
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{name}: empty or non-string category ({value!r})")
    return problems


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------
def _validate_artefact(artefact: Any) -> Dict[str, Any]:
    if not isinstance(artefact, dict):
        raise ValueError("unexpected model artefact format: not a dict")
    pipeline = artefact.get("pipeline")
    if pipeline is None or not hasattr(pipeline, "predict_proba"):
        raise ValueError("unexpected model artefact format: no fitted pipeline with predict_proba")
    metadata = artefact.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("unexpected model artefact format: metadata is not a dict")
    columns = metadata.get("feature_columns", list(FEATURE_COLUMNS))
    if not isinstance(columns, (list, tuple)) or not columns:
        raise ValueError("unexpected model artefact format: empty feature_columns")
    return artefact


def _load_artifact_file(path: str) -> Dict[str, Any]:
    """Load + validate an artefact file (does NOT check enabled flag)."""
    import joblib  # imported lazily so the engine works without ML deps
    artefact = joblib.load(path)
    _validate_artefact(artefact)
    return artefact


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
        artefact = _load_artifact_file(path)
        _CACHE = artefact
        _CACHE_PATH = path
        return artefact
    except Exception as exc:  # never let a broken artefact break scoring
        logger.warning("Supervised fraud model could not be loaded: %s", exc)
        _CACHE = None
        return None


def reset_cache() -> None:
    global _CACHE, _CACHE_PATH
    _CACHE = None
    _CACHE_PATH = None


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def score_claim(
    claim_data: Dict[str, Any],
    policy_data: Optional[Dict[str, Any]] = None,
    customer_data: Optional[Dict[str, Any]] = None,
    historical_claims: Optional[List[Dict[str, Any]]] = None,
    indicators: Optional[List[Dict[str, Any]]] = None,
    settings: Any = None,
) -> Optional[Tuple[float, float, str]]:
    """Return ``(fraud_probability, decision_threshold, model_version)``.

    Probability is always finite and clamped to ``[0.0, 1.0]``. Returns None
    when no usable model is installed or scoring fails; scoring never raises.
    """
    detailed = score_claim_detailed(
        claim_data, policy_data, customer_data, historical_claims, indicators, settings
    )
    if detailed is None:
        return None
    return (
        detailed["fraud_probability"],
        detailed["decision_threshold"],
        detailed["model_version"],
    )


def score_claim_detailed(
    claim_data: Dict[str, Any],
    policy_data: Optional[Dict[str, Any]] = None,
    customer_data: Optional[Dict[str, Any]] = None,
    historical_claims: Optional[List[Dict[str, Any]]] = None,
    indicators: Optional[List[Dict[str, Any]]] = None,
    settings: Any = None,
) -> Optional[Dict[str, Any]]:
    """Like :func:`score_claim` but also returns feature validation/status."""
    try:
        artefact = load_model(settings)
        if not artefact:
            return None
        metadata = artefact.get("metadata", {})
        row, status = build_feature_row_with_status(
            claim_data, policy_data, customer_data, historical_claims, indicators, metadata
        )
        columns = [str(c) for c in metadata.get("feature_columns", FEATURE_COLUMNS)]
        import pandas as pd  # lazy: only needed when a model is actually installed

        # Unknown/extra requested columns -> NaN so an older artifact still
        # loads and its imputer handles them; never KeyError.
        frame = pd.DataFrame(
            [[row.get(c, float("nan")) for c in columns]], columns=columns
        )
        raw_probability = artefact["pipeline"].predict_proba(frame)[0, 1]
        probability = _number(raw_probability, float("nan"))
        if not math.isfinite(probability):
            logger.warning("Supervised model returned non-finite probability; scoring skipped.")
            return None
        probability = min(1.0, max(0.0, probability))  # boundary clamp
        threshold = _number(metadata.get("decision_threshold", 0.5), 0.5)
        threshold = min(1.0, max(0.0, threshold))
        problems = validate_feature_row(row, columns)
        feature_status = {c: status.get(c, STATUS_MISSING_IMPUTED) for c in columns}
        return {
            "fraud_probability": probability,
            "decision_threshold": threshold,
            "model_version": str(metadata.get("version", "unversioned")),
            "feature_columns": columns,
            "feature_status": feature_status,
            "feature_validation": problems,
            "model_known_limitations": metadata.get("known_limitations", []),
        }
    except Exception as exc:  # scoring must never crash the rule engine
        logger.warning("Supervised scoring skipped: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Status / reporting
# ---------------------------------------------------------------------------
def metadata_summary() -> Optional[Dict[str, Any]]:
    artefact = load_model()
    if not artefact:
        return None
    meta = dict(artefact.get("metadata", {}))
    return meta


def _metric(meta: Dict[str, Any], *names: str) -> Optional[float]:
    """First present numeric metric; None when unavailable (never invented)."""
    for name in names:
        value = meta.get(name)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return float(value)
    return None


def describe_model(settings: Any = None) -> Dict[str, Any]:
    """Small, honest status payload for the Security Centre / model dashboard.

    Every field is taken from the saved artifact; nothing is invented.
    """
    enabled = supervised_enabled(settings)
    installed_path = str(MODEL_PATH)
    file_exists = os.path.exists(installed_path)
    # Assess installation independently of the enabled flag: a disabled model
    # is still "installed" but not "enabled".
    artefact: Optional[Dict[str, Any]] = None
    if file_exists:
        try:
            artefact = _load_artifact_file(installed_path)
        except Exception as exc:
            logger.warning("Supervised fraud model could not be loaded: %s", exc)
            artefact = None
    installed = artefact is not None
    base = {
        "enabled": enabled,
        "installed": installed,
        "model_path": installed_path,
        "model_type": "supervised_advisory",
        "advisory_only": True,
    }
    if not installed:
        if not file_exists:
            status = "NOT_INSTALLED"
            detail = "No supervised model artefact is present. Rule and isolation scoring remain active."
        else:
            status = "LOAD_ERROR"
            detail = "Supervised model artefact could not be loaded. Rule and isolation scoring remain active."
        base.update({"status": status, "detail": detail, "enabled": enabled})
        return base
    meta = dict(artefact.get("metadata", {}))
    known_limitations = meta.get("known_limitations") or meta.get("limitations") or (
        [meta["limitation"]] if meta.get("limitation") else []
    )
    base.update({
        "status": "INSTALLED" if enabled else "DISABLED",
        "detail": (
            "Supervised classifier is installed and used as an advisory signal only."
            if enabled else
            "Supervised classifier is installed but disabled; rule and isolation scoring remain active."
        ),
        "version": meta.get("version") or "unversioned",
        "model_version": meta.get("version") or "unversioned",
        "model_kind": meta.get("model_kind"),
        "trained_at": meta.get("trained_at"),
        "last_training_date": meta.get("trained_at"),
        "training_rows": meta.get("training_rows"),
        "fraud_rows": meta.get("fraud_rows"),
        "legitimate_rows": meta.get("legitimate_rows"),
        "training_data_sources": meta.get("sources", meta.get("training_data_sources")),
        "training_data_limitations": meta.get("training_data_limitations", meta.get("synthetic_data_limitation")),
        "roc_auc": _metric(meta, "roc_auc", "roc_auc_mean", "test_roc_auc_mean"),
        "pr_auc": _metric(meta, "pr_auc", "pr_auc_mean", "test_pr_auc_mean"),
        "precision": _metric(meta, "precision", "precision_mean", "test_precision_mean"),
        "recall": _metric(meta, "recall", "recall_mean", "test_recall_mean"),
        "f1": _metric(meta, "f1", "f1_score", "f1_mean", "test_f1_mean"),
        "f1_score": _metric(meta, "f1", "f1_score", "f1_mean", "test_f1_mean"),
        "decision_threshold": _metric(meta, "decision_threshold"),
        "threshold_objective": meta.get("threshold_objective"),
        "feature_columns": meta.get("feature_columns", list(FEATURE_COLUMNS)),
        "known_limitations": known_limitations,
        "evaluation_metrics": {
            k: v for k, v in meta.items()
            if k.endswith("_mean") and isinstance(v, (int, float))
        },
        "report": meta.get("report_path"),
    })
    return base


def write_report(path: str) -> bool:
    meta = metadata_summary()
    if not meta:
        return False
    meta.pop("defaults", None)
    Path(path).write_text(json.dumps(meta, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return True
