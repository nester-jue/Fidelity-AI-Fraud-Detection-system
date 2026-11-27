"""Train and repeatedly evaluate the supervised FIDE-AI fraud classifier.

Usage (from the repository root):

    python ml/train_supervised.py --runs 10                 # repeated stratified splits
    python ml/train_supervised.py --cv-folds 5              # stratified cross-validation
    python ml/train_supervised.py --model random_forest     # force a kind (still compares both)
    python ml/train_supervised.py --threshold 0.4           # override selected threshold
    python ml/train_supervised.py --output <candidate>      # write candidate, do NOT touch production
    python ml/train_supervised.py --promote                 # validate, backup, replace production

The labelled Hugging Face CSVs in ``datasets/huggingface`` are combined. Columns
that reveal the outcome or that leak the target are deliberately excluded so the
model learns claim features, not the answer. The model is advisory: it is never
an automatic claims-rejection decision.

TARGET LEAKAGE REMOVED (see PHASE 2 audit):
  * duplicate_claim_flag  - generated as dup_base = 0.05 + 0.25*fraud_label
  * year                  - constant 2024 in every supplied dataset
  * fraud_probability     - fraud_label ~ Bernoulli(fraud_probability)
  * fraud_scheme_type     - 'none' iff non-fraud
  * detection_method      - 'none' iff non-fraud
  * recovery_amount_usd   - >0 iff fraud (post-decision outcome)
  * record_id             - pure identifier
  * fraud_label           - the target
Duplicate-claim detection is preserved in the rule-based fraud engine
(DUPLICATE_CLAIM_DETECTED); it is NOT a supervised-model feature.

amount_deviation_zscore has ONE canonical definition shared by training and
live inference: (claim_amount_usd - mean[country]) / std[country], population
std ddof=0, per-country reference with global fallback, reference fitted on
training data only and stored inside the pipeline + metadata. Preprocessing is
fitted only on training folds; never on test data.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.compose import ColumnTransformer  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.impute import SimpleImputer  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import OneHotEncoder, StandardScaler  # noqa: E402

from backend.app.ml.supervised import (  # noqa: E402
    AmountDeviationZscoreTransformer,
    CATEGORICAL_COLUMNS,
    FEATURE_COLUMNS,
    LEAKAGE_COLUMNS as SUPERVISED_LEAKAGE_COLUMNS,
    NUMERIC_COLUMNS,
    apply_amount_reference,
)

LABEL = "fraud_label"

# Columns that reveal the outcome / leak the target / are pure identifiers.
# Union of the supervised-module list with the extra names seen in source CSVs.
LEAKAGE_COLUMNS: set = set(SUPERVISED_LEAKAGE_COLUMNS) | {
    LABEL,                  # the target itself
    "fraud_probability",    # label is sampled from this
    "fraud_scheme_type",    # known only after investigation; 'none' iff non-fraud
    "detection_method",     # outcome/process metadata; 'none' iff non-fraud
    "recovery_amount_usd",  # post-decision outcome; >0 iff fraud
    "record_id",            # identifier, not a claim attribute
    "duplicate_claim_flag", # partly generated FROM fraud_label; rule engine keeps duplicate detection
    "year",                 # constant 2024 in every supplied dataset
    "synthetic_indicators", # ground-truth label source in other datasets
    "fraud_scheme",         # synonym guard
    "recovery_amount",      # synonym guard
}

# Columns that must never accidentally re-enter even if named differently.
assert "duplicate_claim_flag" not in FEATURE_COLUMNS
assert "duplicate_claim_flag" not in NUMERIC_COLUMNS
assert "year" not in FEATURE_COLUMNS
assert "year" not in NUMERIC_COLUMNS

DEFAULT_CSV_DIR = ROOT / "datasets" / "huggingface"
PRODUCTION_MODEL_PATH = ROOT / "backend" / "app" / "ml" / "models" / "fraud_classifier.joblib"
DEFAULT_MODEL_PATH = PRODUCTION_MODEL_PATH  # backwards-compatible name
DEFAULT_CANDIDATE_PATH = PRODUCTION_MODEL_PATH.with_name("fraud_classifier.candidate.joblib")
DEFAULT_REPORT_PATH = ROOT / "ml" / "training_report.json"
BACKUP_DIR = PRODUCTION_MODEL_PATH.parent / "backups"

# Operational threshold sweep (fraud is imbalanced; do NOT pick on accuracy).
DEFAULT_THRESHOLDS: Tuple[float, ...] = (
    0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70,
)

SYNTHETIC_DATA_LIMITATION = (
    "Training data are three SYNTHETIC datasets (baseline.csv, "
    "enhanced_detection.csv, fraud_wave.csv; 120,000 records each; ~360,000 "
    "combined), generated by datasets/generate_dataset.py. They are NOT "
    "independently verified historical insurance fraud cases. Reported metrics "
    "are measured on synthetic held-out data only; they are NOT evidence of "
    "real-world insurance-fraud detection accuracy, are NOT production-validated, "
    "and must NOT be used as proof of commercial effectiveness. Per-country fraud "
    "rates reflect synthetic generator parameters, not real-world fraud in any "
    "country."
)

KNOWN_LIMITATIONS: List[str] = [
    SYNTHETIC_DATA_LIMITATION,
    "Advisory fraud intelligence only. The model NEVER automatically rejects a "
    "claim, approves a payout, declares a customer guilty, suspends a "
    "policyholder, or makes a final investigation decision. All high-risk "
    "claims follow the existing human review / investigation workflow.",
    "Domain mismatch: training data is generic insurance (motor/health/property/"
    "life/travel/crop; 12 African countries; year=2024), while the live app is "
    "Zimbabwean life assurance with claim types such as Death Benefit / Funeral "
    "Cash Plan / Accident / Critical Illness. Unknown claim_type is ignored by "
    "the one-hot encoder; unknown country falls back to global statistics.",
    "Live application does not collect country on claims/policies; live "
    "'country' is 'unknown' unless supplied, and amount reference falls back to "
    "a global (not per-country) statistic.",
    "claimant_age is imputed with the training median when absent; live value "
    "is derived from Customer.date_of_birth (when present) vs incident date. "
    "Imputation reduces accuracy for claims missing age/DOB.",
    "document_completeness_score is UNAVAILABLE in the live application; it is "
    "imputed with the training median (~0.77). The feature carries no live "
    "signal. (feature_status=unavailable_in_live_app).",
    "previous_claims_count live is derived from len(historical_claims) or a "
    "provided value; partial/limited history UNDERCOUNTS prior claims vs "
    "training. 'not_yet_calculable'/'derived' status is reported.",
    "reporting_delay_days live is derived from submission_date - incident_date "
    "(or provided); missing dates -> imputed. 'not_yet_calculable' when dates "
    "are absent.",
    "policy_duration_months live is (incident_date - effective_date)/30.4375, "
    "clamped >=0; synthetic training uses integer months 1..120. Missing dates "
    "-> imputed.",
    "amount_deviation_zscore canonical = (claim_amount_usd - mean[country]) / "
    "std[country], population std ddof=0, per-country reference with global "
    "fallback, fitted on training only; missing amount -> imputed.",
    "Missing numeric features are imputed with TRAINING medians inside the "
    "saved pipeline; this is reported via feature_status, never silent. Unknown "
    "categories are ignored; missing categories -> 'unknown'.",
    "Trained on a mixed-scenario synthetic pool (baseline + enhanced_detection "
    "+ fraud_wave); prevalence ~13.7%. Threshold selection used out-of-fold "
    "predictions on synthetic data; re-tune on verified production labels.",
    "Fairness results are measured on synthetic data and cannot establish "
    "real-world fairness; country/age disparities require real labelled audit.",
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_labelled_claims(csv_dir: Path) -> Tuple[pd.DataFrame, List[str]]:
    files = sorted(csv_dir.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in {csv_dir}")
    frames = []
    sources: List[str] = []
    for path in files:
        frame = pd.read_csv(path)
        # never let leakage columns through even if a future dataset adds them
        frame = frame.drop(columns=[c for c in LEAKAGE_COLUMNS if c in frame.columns and c != LABEL], errors="ignore")
        required = [c for c in list(FEATURE_COLUMNS) + [LABEL] if c not in frame.columns]
        # amount_deviation_zscore is recomputed inside the pipeline; not required.
        required = [c for c in required if c != "amount_deviation_zscore"]
        if required:
            raise ValueError(f"{path.name} is missing required columns: {required}")
        keep = [c for c in FEATURE_COLUMNS if c in frame.columns] + [LABEL]
        frame = frame[keep].copy()
        if "amount_deviation_zscore" not in frame.columns:
            frame["amount_deviation_zscore"] = np.nan
        frames.append(frame)
        sources.append(f"{path.name} ({len(frame):,} rows)")
        print(f"  loaded {path.name}: {len(frame):,} rows")
    data = pd.concat(frames, ignore_index=True)
    for column in NUMERIC_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    for column in CATEGORICAL_COLUMNS:
        data[column] = data[column].fillna("unknown").astype(str).str.strip().str.lower()
    data[LABEL] = pd.to_numeric(data[LABEL], errors="coerce")
    before = len(data)
    data = data.dropna(subset=[LABEL])
    data[LABEL] = data[LABEL].astype(int)
    print(f"Combined {before:,} rows from {len(files)} files; {len(data):,} labelled rows retained.")
    return data, sources


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
def make_pipeline(kind: str, seed: int) -> Pipeline:
    numeric = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    categorical = Pipeline([
        ("impute", SimpleImputer(strategy="constant", fill_value="unknown")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    preprocess = ColumnTransformer([
        ("num", numeric, list(NUMERIC_COLUMNS)),
        ("cat", categorical, list(CATEGORICAL_COLUMNS)),
    ])
    if kind == "random_forest":
        estimator = RandomForestClassifier(
            n_estimators=180,
            max_depth=16,
            min_samples_leaf=4,
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=seed,
        )
    else:
        estimator = LogisticRegression(
            max_iter=1200,
            class_weight="balanced",
            solver="lbfgs",
            random_state=seed,
        )
    steps: List[Tuple[str, Any]] = []
    # Canonical amount_deviation_zscore recomputed per fold; fitted on train only.
    if AmountDeviationZscoreTransformer is not None:
        steps.append(("amount_zscore", AmountDeviationZscoreTransformer()))
    steps.extend([("preprocess", preprocess), ("classifier", estimator)])
    return Pipeline(steps)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def compute_metrics(y_true: Any, probability: Any, threshold: float = 0.5) -> Dict[str, float]:
    y_true = np.asarray(y_true).astype(int)
    probability = np.clip(np.asarray(probability, dtype=float), 0.0, 1.0)
    prediction = (probability >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, prediction, labels=[0, 1]).ravel()
    total = tn + fp + fn + tp
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    fnr = fn / (fn + tp) if (fn + tp) else 0.0
    prevalence = (tp + fn) / total if total else 0.0
    try:
        roc = float(roc_auc_score(y_true, probability)) if len(np.unique(y_true)) > 1 else float("nan")
    except Exception:
        roc = float("nan")
    try:
        pr = float(average_precision_score(y_true, probability)) if len(np.unique(y_true)) > 1 else float("nan")
    except Exception:
        pr = float("nan")
    return {
        "n": float(total),
        "prevalence": round(float(prevalence), 6),
        "accuracy": round(float(accuracy_score(y_true, prediction)), 6),
        "precision": round(float(precision_score(y_true, prediction, zero_division=0)), 6),
        "recall": round(float(recall_score(y_true, prediction, zero_division=0)), 6),
        "f1": round(float(f1_score(y_true, prediction, zero_division=0)), 6),
        "roc_auc": round(roc, 6),
        "pr_auc": round(pr, 6),
        "true_negatives": float(tn),
        "false_positives": float(fp),
        "false_negatives": float(fn),
        "true_positives": float(tp),
        "false_positive_rate": round(float(fpr), 6),
        "false_negative_rate": round(float(fnr), 6),
        "confusion_matrix": [[float(tn), float(fp)], [float(fn), float(tp)]],
    }


def summarise(runs: List[Dict[str, float]]) -> Dict[str, float]:
    summary: Dict[str, float] = {}
    if not runs:
        return summary
    keys = [k for k in runs[0] if k != "confusion_matrix"]
    for key in keys:
        values = [r[key] for r in runs if isinstance(r.get(key), (int, float)) and np.isfinite(r[key])]
        if not values:
            continue
        summary[f"{key}_mean"] = round(float(np.mean(values)), 6)
        summary[f"{key}_std"] = round(float(np.std(values)), 6)
    return summary


# ---------------------------------------------------------------------------
# Stratified cross-validation (preprocessing fitted on training folds only)
# ---------------------------------------------------------------------------
def evaluate_with_cv(X: pd.DataFrame, y: pd.Series, kind: str, seed: int, folds: int) -> Dict[str, Any]:
    skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    per_fold: List[Dict[str, float]] = []
    oof = np.zeros(len(y), dtype=float)
    oof_index = np.arange(len(y))
    y_arr = np.asarray(y).astype(int)
    X_reset = X.reset_index(drop=True)
    y_reset = pd.Series(y_arr)
    for fold_train, fold_test in skf.split(X_reset, y_reset):
        pipeline = make_pipeline(kind, seed)
        pipeline.fit(X_reset.iloc[fold_train], y_reset.iloc[fold_train])
        prob = pipeline.predict_proba(X_reset.iloc[fold_test])[:, 1]
        prob = np.clip(np.nan_to_num(prob, nan=0.5, posinf=1.0, neginf=0.0), 0.0, 1.0)
        oof[fold_test] = prob
        per_fold.append(compute_metrics(y_arr[fold_test], prob, threshold=0.5))
    summary = summarise(per_fold)
    # out-of-fold combined metrics at default 0.5 (threshold re-selected later)
    oof_metrics = compute_metrics(y_arr, oof, threshold=0.5)
    return {
        "kind": kind,
        "folds": folds,
        "per_fold": per_fold,
        "cv_mean_std": summary,
        "out_of_fold": oof_metrics,
        "oof_probability": oof,
        "oof_index": oof_index,
    }


def evaluate_once(X: pd.DataFrame, y: pd.Series, kind: str, seed: int, test_size: float) -> Dict[str, float]:
    """Single repeated stratified split (kept for backward compatibility)."""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=seed, stratify=y
    )
    pipeline = make_pipeline(kind, seed)
    pipeline.fit(X_train, y_train)
    probability = pipeline.predict_proba(X_test)[:, 1]
    probability = np.clip(np.nan_to_num(probability, nan=0.5, posinf=1.0, neginf=0.0), 0.0, 1.0)
    m = compute_metrics(y_test, probability, threshold=0.5)
    m["seed"] = float(seed)
    return m


# ---------------------------------------------------------------------------
# Threshold selection (NOT accuracy; fraud is imbalanced)
# ---------------------------------------------------------------------------
def threshold_table(y_true: Any, probability: Any, thresholds: Tuple[float, ...]) -> List[Dict[str, float]]:
    rows: List[Dict[str, float]] = []
    y_arr = np.asarray(y_true).astype(int)
    prob = np.clip(np.asarray(probability, dtype=float), 0.0, 1.0)
    for t in thresholds:
        m = compute_metrics(y_arr, prob, threshold=t)
        rows.append({
            "threshold": round(float(t), 4),
            "precision": m["precision"],
            "recall": m["recall"],
            "f1": m["f1"],
            "accuracy": m["accuracy"],
            "false_positive_rate": m["false_positive_rate"],
            "false_negative_rate": m["false_negative_rate"],
            "true_positives": m["true_positives"],
            "false_positives": m["false_positives"],
            "true_negatives": m["true_negatives"],
            "false_negatives": m["false_negatives"],
        })
    return rows


def select_threshold(y_true: Any, probability: Any, thresholds: Tuple[float, ...],
                     objective: str = "f1", override: Optional[float] = None) -> Tuple[float, List[Dict[str, float]], str]:
    """Pick a threshold from `thresholds`. Never selects on accuracy alone.

    objective='f1'      -> maximise F1 (balances precision & recall; imbalanced-safe)
    tie-break           -> higher precision, then higher recall, then lower FPR
    override            -> explicit operator threshold (still reported in table)
    """
    table = threshold_table(y_true, probability, thresholds)
    if override is not None:
        chosen = float(min(1.0, max(0.0, override)))
        rationale = f"operator override threshold={chosen}; full sweep reported; not accuracy-selected"
        return chosen, table, rationale
    if objective == "precision_at_recall":
        # maximise precision subject to recall >= 0.5 floor, fall back to best F1
        eligible = [r for r in table if r["recall"] >= 0.5]
        pool = eligible if eligible else table
        best = sorted(pool, key=lambda r: (-r["precision"], -r["recall"], r["threshold"]))[0]
        rationale = "maximise precision subject to recall>=0.5 (fallback best F1); not accuracy"
    else:
        best = sorted(table, key=lambda r: (-r["f1"], -r["precision"], -r["recall"],
                                            r["false_positive_rate"], r["threshold"]))[0]
        rationale = "maximise F1 at listed thresholds; tie-break higher precision/recall, lower FPR; not accuracy"
    return float(best["threshold"]), table, rationale


# ---------------------------------------------------------------------------
# Fairness (per-country + claimant-age); synthetic data caveats apply
# ---------------------------------------------------------------------------
def _subgroup_metrics(y_true: Any, prob: Any, mask: Any, threshold: float) -> Optional[Dict[str, float]]:
    y_true = np.asarray(y_true).astype(int)
    prob = np.asarray(prob, dtype=float)
    mask = np.asarray(mask)
    if mask.sum() == 0:
        return None
    m = compute_metrics(y_true[mask], prob[mask], threshold=threshold)
    positives = int((y_true[mask] == 1).sum())
    negatives = int((y_true[mask] == 0).sum())
    # require enough data for honest rates
    insufficient = positives == 0 or negatives == 0 or int(mask.sum()) < 30
    out = {
        "n": int(mask.sum()),
        "n_fraud": positives,
        "n_legitimate": negatives,
        "fraud_prevalence": round(positives / int(mask.sum()), 6),
        "precision": m["precision"],
        "recall": m["recall"],
        "false_positive_rate": m["false_positive_rate"],
        "false_negative_rate": m["false_negative_rate"],
        "accuracy": m["accuracy"],
        "f1": m["f1"],
    }
    out["sufficient_data"] = not insufficient
    if insufficient:
        # rates not reliable; still reported but flagged
        out["note"] = "insufficient data (n<30 or no positive/negative cases); rates not reliable"
    return out


def fairness_report(X: pd.DataFrame, y: Any, probability: Any, threshold: float,
                    feature: str = "country") -> Dict[str, Any]:
    y_arr = np.asarray(y).astype(int)
    prob = np.clip(np.asarray(probability, dtype=float), 0.0, 1.0)
    groups: Dict[str, Dict[str, Any]] = {}
    if feature in X.columns:
        col = X[feature].fillna("unknown").astype(str).str.strip().str.lower()
        values = col.to_numpy()
        for value in sorted(set(values.tolist())):
            mask = values == value
            res = _subgroup_metrics(y_arr, prob, mask, threshold)
            if res is not None:
                groups[str(value)] = res
    return {
        "feature": feature,
        "threshold": round(float(threshold), 4),
        "groups": groups,
        "note": (
            "Computed on out-of-fold synthetic-data predictions. Differences may "
            "reflect synthetic generator parameters, not real-world fraud; no "
            "claim of fairness or unfairness is made for any real population."
        ),
    }


def claimant_age_fairness(X: pd.DataFrame, y: Any, probability: Any, threshold: float) -> Dict[str, Any]:
    y_arr = np.asarray(y).astype(int)
    prob = np.clip(np.asarray(probability, dtype=float), 0.0, 1.0)
    if "claimant_age" not in X.columns:
        return {"feature": "claimant_age", "groups": {}, "note": "claimant_age unavailable"}
    age = pd.to_numeric(X["claimant_age"], errors="coerce").to_numpy()
    bins = [(-1, 25, "<25"), (25, 35, "25-34"), (35, 45, "35-44"),
            (45, 55, "45-54"), (55, 65, "55-64"), (65, 200, "65+")]
    groups: Dict[str, Any] = {}
    valid = np.isfinite(age)
    for lo, hi, label in bins:
        mask = valid & (age > lo) & (age <= hi)
        res = _subgroup_metrics(y_arr, prob, mask, threshold)
        if res is not None:
            groups[label] = res
    unknown_mask = ~valid
    res = _subgroup_metrics(y_arr, prob, unknown_mask, threshold)
    if res is not None:
        groups["unknown_age"] = res
    return {
        "feature": "claimant_age",
        "bins": [b[2] for b in bins],
        "threshold": round(float(threshold), 4),
        "groups": groups,
        "note": (
            "Age-binned subgroup metrics on synthetic out-of-fold data. "
            "claimant_age is itself a model input; subgroup differences must not "
            "be read as justified real-world disparity. Verify on real labelled "
            "data with a protected-attribute audit before any operational use."
        ),
    }


# ---------------------------------------------------------------------------
# Artifact extraction
# ---------------------------------------------------------------------------
def _extract_amount_reference(pipeline: Pipeline, data: pd.DataFrame) -> Dict[str, Any]:
    step = None
    for name in ("amount_zscore", "amount_deviation", "zscore"):
        if hasattr(pipeline, "named_steps") and name in pipeline.named_steps:
            step = pipeline.named_steps[name]
            break
    ref = getattr(step, "amount_reference_", None) if step is not None else None
    if ref:
        return ref
    # fall back to computing canonical reference on full training data
    from backend.app.ml.supervised import compute_amount_reference
    return compute_amount_reference(data)


def _extract_categories(pipeline: Pipeline) -> Dict[str, List[str]]:
    cats: Dict[str, List[str]] = {}
    try:
        pre = pipeline.named_steps["preprocess"]
        for name, _trans, cols in pre.transformers_:
            if name != "cat":
                continue
            onehot = _trans.named_steps["onehot"] if hasattr(_trans, "named_steps") else None
            if onehot is None or not hasattr(onehot, "categories_"):
                continue
            for col, values in zip(cols, onehot.categories_):
                cats[str(col)] = [str(v) for v in values.tolist()]
    except Exception:
        pass
    return cats


# ---------------------------------------------------------------------------
# Old vs new comparison
# ---------------------------------------------------------------------------
def _load_existing_metadata(model_path: Path) -> Optional[Dict[str, Any]]:
    try:
        if not model_path.exists():
            return None
        artefact = joblib.load(model_path)
        if isinstance(artefact, dict):
            return dict(artefact.get("metadata", {}))
    except Exception:
        return None
    return None


def _metric(meta: Dict[str, Any], *names: str) -> Optional[float]:
    for name in names:
        v = meta.get(name)
        if isinstance(v, (int, float)) and np.isfinite(float(v)):
            return float(v)
    return None


def compare_old_new(old_meta: Optional[Dict[str, Any]], new_meta: Dict[str, Any],
                    production_path: Path) -> Dict[str, Any]:
    keys = ("roc_auc", "pr_auc", "precision", "recall", "f1", "accuracy",
            "false_positive_rate", "false_negative_rate")
    out: Dict[str, Any] = {"production_artifact": str(production_path)}
    if not old_meta:
        out["old"] = None
        out["note"] = "No existing production artifact to compare against."
    else:
        old_src = "roc_auc_mean"
        out["old"] = {
            "version": old_meta.get("version"),
            "trained_at": old_meta.get("trained_at"),
            "training_rows": old_meta.get("training_rows"),
            "decision_threshold": old_meta.get("decision_threshold"),
            "feature_columns": old_meta.get("feature_columns"),
            "had_target_leakage": sorted(set(old_meta.get("feature_columns", [])) & LEAKAGE_COLUMNS),
            "note": ("Old artifact's own reported metrics; it was trained with target "
                     "leakage (duplicate_claim_flag/year) and NOT evaluated on this "
                     "clean split. Not apples-to-apples; see new clean metrics."),
        }
        for k in keys:
            out["old"][k] = _metric(old_meta, k, f"{k}_mean", f"test_{k}_mean")
        _ = old_src
    # new
    nm = new_meta
    new_block = {
        "version": nm.get("version"),
        "trained_at": nm.get("trained_at"),
        "training_rows": nm.get("training_rows"),
        "decision_threshold": nm.get("decision_threshold"),
        "feature_columns": nm.get("feature_columns"),
        "had_target_leakage": [],
        "metrics_source": nm.get("evaluation_metrics", {}).get("source"),
    }
    evalm = nm.get("evaluation_metrics", {})
    for k in keys:
        value = _metric(evalm, k, f"{k}_mean")
        if value is None:
            value = _metric(nm, k, f"{k}_mean")
        new_block[k] = value
    out["new"] = new_block
    return out


# ---------------------------------------------------------------------------
# Final training
# ---------------------------------------------------------------------------
def defaults_from(data: pd.DataFrame) -> Dict[str, object]:
    defaults: Dict[str, object] = {}
    for column in NUMERIC_COLUMNS:
        value = pd.to_numeric(data[column], errors="coerce").median()
        defaults[column] = float(value) if pd.notna(value) else 0.0
    for column in CATEGORICAL_COLUMNS:
        mode = data[column].mode(dropna=True)
        defaults[column] = str(mode.iloc[0]) if len(mode) else "unknown"
    return defaults


def print_summary(label: str, summary: Dict[str, float]) -> None:
    print("-" * 68)
    print(label)
    if "roc_auc_mean" in summary:
        print(f"  ROC-AUC : {summary['roc_auc_mean']:.4f} ± {summary.get('roc_auc_std', 0):.4f}")
    if "pr_auc_mean" in summary:
        print(f"  PR-AUC  : {summary['pr_auc_mean']:.4f} ± {summary.get('pr_auc_std', 0):.4f}")
    print(f"  Precision: {summary.get('precision_mean', 0):.4f}  Recall: {summary.get('recall_mean', 0):.4f}")
    print(f"  F1      : {summary.get('f1_mean', 0):.4f}  Accuracy: {summary.get('accuracy_mean', 0):.4f}")
    print(f"  FPR     : {summary.get('false_positive_rate_mean', 0):.4f}  FNR: {summary.get('false_negative_rate_mean', 0):.4f}")
    print("-" * 68)


def _select_model_kind(cv_results: Dict[str, Dict[str, Any]], forced: Optional[str]) -> Tuple[str, str]:
    if forced:
        return forced, f"operator forced model='{forced}'; both kinds still evaluated"
    def score(kind: str) -> Tuple[float, float, float]:
        s = cv_results[kind]["cv_mean_std"]
        pr = s.get("pr_auc_mean", 0.0)
        f1 = s.get("f1_mean", 0.0)
        prec = s.get("precision_mean", 0.0)
        return (pr, f1, prec)
    kinds = sorted(cv_results.keys())
    chosen = max(kinds, key=score)
    rationale = ("selected on stratified CV: highest PR-AUC (primary; imbalanced fraud), "
                 "tie-break F1 then precision; NOT accuracy. Both kinds evaluated.")
    return chosen, rationale


def train_final(data: pd.DataFrame, kind: str, sources: List[str], args: argparse.Namespace,
                *, decision_threshold: float, threshold_table_rows: List[Dict[str, float]],
                threshold_rationale: str, cv_summary: Dict[str, float],
                holdout_metrics: Dict[str, float], fairness: Dict[str, Any],
                age_fairness: Dict[str, Any], model_selection_rationale: str,
                output_path: Path, old_meta: Optional[Dict[str, Any]],
                production_path: Path, cv_folds: int) -> Dict[str, object]:
    X = data[list(FEATURE_COLUMNS)]
    y = data[LABEL]
    pipeline = make_pipeline(kind, args.seed)
    pipeline.fit(X, y)
    trained_at = datetime.now(timezone.utc)
    version = f"supervised-{kind}-{trained_at.strftime('%Y%m%dT%H%M%SZ')}"
    amount_reference = _extract_amount_reference(pipeline, X.assign(**{LABEL: y}))
    categories = _extract_categories(pipeline)
    evaluation_metrics = {
        "source": ("stratified K-fold out-of-fold + fixed stratified holdout on "
                   "synthetic combined dataset; NOT real-world validation"),
        "cv_folds": cv_folds,
        "roc_auc": cv_summary.get("roc_auc_mean"),
        "pr_auc": cv_summary.get("pr_auc_mean"),
        "precision": holdout_metrics.get("precision"),
        "recall": holdout_metrics.get("recall"),
        "f1": holdout_metrics.get("f1"),
        "accuracy": holdout_metrics.get("accuracy"),
        "roc_auc_mean": cv_summary.get("roc_auc_mean"),
        "pr_auc_mean": cv_summary.get("pr_auc_mean"),
        "precision_mean": cv_summary.get("precision_mean"),
        "recall_mean": cv_summary.get("recall_mean"),
        "f1_mean": cv_summary.get("f1_mean"),
        "accuracy_mean": cv_summary.get("accuracy_mean"),
        "false_positive_rate": holdout_metrics.get("false_positive_rate"),
        "false_negative_rate": holdout_metrics.get("false_negative_rate"),
        "confusion_matrix": holdout_metrics.get("confusion_matrix"),
        "holdout": holdout_metrics,
        "cv_mean_std": cv_summary,
    }
    metadata = {
        "version": version,
        "model_version": version,
        "model_kind": kind,
        "trained_at": trained_at.isoformat(),
        "training_rows": int(len(data)),
        "fraud_rows": int(y.sum()),
        "legitimate_rows": int((y == 0).sum()),
        "fraud_prevalence": round(float(y.mean()), 6),
        "sources": sources,
        "training_data_sources": sources,
        "training_data_limitations": SYNTHETIC_DATA_LIMITATION,
        "synthetic_data_limitation": SYNTHETIC_DATA_LIMITATION,
        "known_limitations": KNOWN_LIMITATIONS,
        "excluded_leakage_columns": sorted(LEAKAGE_COLUMNS),
        "feature_columns": list(FEATURE_COLUMNS),
        "numeric_columns": list(NUMERIC_COLUMNS),
        "categorical_columns": list(CATEGORICAL_COLUMNS),
        "categories": categories,
        "decision_threshold": round(float(decision_threshold), 6),
        "threshold_objective": args.threshold_objective,
        "threshold_rationale": threshold_rationale,
        "threshold_table": threshold_table_rows,
        "thresholds_tested": list(DEFAULT_THRESHOLDS),
        "cv_folds": cv_folds,
        "runs": args.runs,
        "test_size": args.test_size,
        "seed": args.seed,
        "defaults": defaults_from(data),  # documented; NOT silently applied at inference
        "amount_reference": amount_reference,
        "amount_deviation_zscore_definition": (
            "(claim_amount_usd - mean[country]) / std[country]; population std "
            "ddof=0; per-country reference with global fallback; fitted on "
            "training only; recomputed inside pipeline; canonical shared with "
            "live inference."
        ),
        "repeat_metrics": cv_summary,
        "evaluation_metrics": evaluation_metrics,
        "fairness": {"country": fairness, "claimant_age": age_fairness},
        "model_selection_rationale": model_selection_rationale,
        "report_path": _safe_rel(DEFAULT_REPORT_PATH, ROOT),
        "limitation": KNOWN_LIMITATIONS[0],
        "advisory_only": True,
        "never_auto_decision": (
            "Never automatically rejects a claim, approves a payout, declares "
            "guilt, suspends a policyholder, or makes a final investigation "
            "decision. Human review/investigation workflow is mandatory."
        ),
    }
    # top-level convenience metrics (describe_model reads these; nothing invented)
    metadata.update({k: v for k, v in cv_summary.items() if k.endswith("_mean")})
    metadata["roc_auc"] = evaluation_metrics["roc_auc"]
    metadata["pr_auc"] = evaluation_metrics["pr_auc"]
    metadata["precision"] = evaluation_metrics["precision"]
    metadata["recall"] = evaluation_metrics["recall"]
    metadata["f1"] = evaluation_metrics["f1"]
    metadata["f1_score"] = evaluation_metrics["f1"]
    metadata["accuracy"] = evaluation_metrics["accuracy"]
    metadata["confusion_matrix"] = evaluation_metrics["confusion_matrix"]

    artefact = {"pipeline": pipeline, "metadata": metadata}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artefact, output_path, compress=3)
    # stash comparison on side; not inside artifact metrics
    metadata["old_vs_new"] = compare_old_new(old_meta, metadata, production_path)
    joblib.dump(artefact | {"metadata": metadata}, output_path, compress=3)
    print(f"Saved candidate model: {output_path}")
    return metadata


def _safe_rel(p: Path, root: Path) -> str:
    try:
        return p.relative_to(root).as_posix()
    except Exception:
        return str(p)


def backup_production(production_path: Path, backup_dir: Path) -> Optional[Path]:
    if not production_path.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = backup_dir / f"fraud_classifier.{ts}.joblib"
    shutil.copy2(production_path, dest)
    print(f"Timestamped backup created: {dest}")
    return dest


def promote_candidate(candidate_path: Path, production_path: Path, backup_dir: Path) -> Path:
    """Validate candidate, backup existing production, then replace it."""
    if not candidate_path.exists():
        raise FileNotFoundError(f"candidate not found: {candidate_path}")
    # validate loads + has fitted pipeline + clean features
    artefact = joblib.load(candidate_path)
    if not isinstance(artefact, dict) or "pipeline" not in artefact or "metadata" not in artefact:
        raise ValueError("candidate artefact invalid: needs pipeline + metadata")
    if not hasattr(artefact["pipeline"], "predict_proba"):
        raise ValueError("candidate pipeline has no predict_proba")
    cols = artefact["metadata"].get("feature_columns", list(FEATURE_COLUMNS))
    if list(cols) != list(FEATURE_COLUMNS):
        raise ValueError(f"candidate feature_columns mismatch: {cols} != {list(FEATURE_COLUMNS)}")
    for bad in ("duplicate_claim_flag", "year"):
        if bad in cols:
            raise ValueError(f"leakage feature present in candidate: {bad}")
    backup_production(production_path, backup_dir)
    production_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate_path, production_path)
    print(f"Production artifact replaced: {production_path}")
    return production_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=10, help="number of repeated stratified evaluations")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model", choices=("logistic", "random_forest", "auto"), default="auto",
                        help="force kind; 'auto' selects on CV PR-AUC. Both kinds are always evaluated.")
    parser.add_argument("--cv-folds", type=int, default=5, help="stratified K-folds (preprocessing fitted per fold)")
    parser.add_argument("--threshold", type=float, default=None, help="explicit operator decision threshold")
    parser.add_argument("--threshold-objective", choices=("f1", "precision_at_recall"), default="f1")
    parser.add_argument("--thresholds", type=str, default=",".join(str(t) for t in DEFAULT_THRESHOLDS),
                        help="comma-separated thresholds to test")
    parser.add_argument("--output", type=str, default=str(DEFAULT_CANDIDATE_PATH), help="candidate output path")
    parser.add_argument("--report", type=str, default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--promote", action="store_true", help="validate + timestamped backup + replace production")
    parser.add_argument("--production-path", type=str, default=str(PRODUCTION_MODEL_PATH))
    parser.add_argument("--backup-dir", type=str, default=str(BACKUP_DIR))
    # backwards-compatible no-op flags kept so old invocations don't break
    parser.add_argument("--compare-forest", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    if args.cv_folds < 2:
        raise SystemExit("--cv-folds must be at least 2")
    thresholds = tuple(sorted(float(t) for t in args.thresholds.split(",") if t.strip()))
    production_path = Path(args.production_path)
    output_path = Path(args.output)
    report_path = Path(args.report)

    print("=" * 68)
    print("FIDE-AI SUPERVISED FRAUD MODEL TRAINING")
    print("=" * 68)
    print("SYNTHETIC DATA NOTICE:", SYNTHETIC_DATA_LIMITATION)
    data, sources = load_labelled_claims(DEFAULT_CSV_DIR)
    X = data[list(FEATURE_COLUMNS)]
    y = data[LABEL]
    print(f"Features ({len(FEATURE_COLUMNS)}): {list(FEATURE_COLUMNS)}")
    print("Leakage excluded:", sorted(LEAKAGE_COLUMNS))

    # ---------------- repeated stratified splits (kept) ----------------
    forced_kind = None if args.model == "auto" else args.model
    primary_kind = forced_kind or "logistic"
    runs = []
    for seed in range(args.seed, args.seed + args.runs):
        metrics = evaluate_once(X, y, primary_kind, seed, args.test_size)
        runs.append(metrics)
    repeat_summary = summarise(runs)
    print_summary(f"{primary_kind.upper()} — {args.runs} repeated stratified splits (threshold 0.5)", repeat_summary)

    # ---------------- stratified CV: compare LogisticRegression + RandomForest ----
    kinds = ["logistic", "random_forest"]
    cv_results: Dict[str, Dict[str, Any]] = {}
    for kind in kinds:
        print(f"\nStratified {args.cv_folds}-fold CV: {kind} ...")
        cv_results[kind] = evaluate_with_cv(X, y, kind, args.seed, args.cv_folds)
        print_summary(f"{kind.upper()} — {args.cv_folds}-fold CV", cv_results[kind]["cv_mean_std"])

    chosen_kind, model_selection_rationale = _select_model_kind(cv_results, forced_kind)
    if args.compare_forest and forced_kind is None:
        chosen_kind, model_selection_rationale = _select_model_kind(cv_results, None)
    print(f"\nSelected model kind: {chosen_kind}\n  {model_selection_rationale}")

    chosen = cv_results[chosen_kind]
    oof = chosen["oof_probability"]
    y_arr = np.asarray(y).astype(int)

    # ---------------- threshold sweep + selection ----------------
    chosen_threshold, threshold_rows, threshold_rationale = select_threshold(
        y_arr, oof, thresholds, objective=args.threshold_objective, override=args.threshold
    )
    print("\nThreshold sweep (out-of-fold, selected model):")
    print(f"  {'thr':>6} {'prec':>8} {'rec':>8} {'f1':>8} {'fpr':>8} {'fnr':>8}")
    for r in threshold_rows:
        print(f"  {r['threshold']:>6.2f} {r['precision']:>8.4f} {r['recall']:>8.4f} "
              f"{r['f1']:>8.4f} {r['false_positive_rate']:>8.4f} {r['false_negative_rate']:>8.4f}")
    print(f"Selected threshold: {chosen_threshold}  ({threshold_rationale})")

    # ---------------- fixed stratified holdout for chosen model ----------------
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=args.test_size,
                                              random_state=args.seed, stratify=y)
    holdout_pipe = make_pipeline(chosen_kind, args.seed)
    holdout_pipe.fit(X_tr, y_tr)
    holdout_prob = np.clip(np.nan_to_num(holdout_pipe.predict_proba(X_te)[:, 1], nan=0.5, posinf=1.0, neginf=0.0), 0.0, 1.0)
    holdout_metrics = compute_metrics(y_te, holdout_prob, threshold=chosen_threshold)
    print("\nFixed stratified holdout (selected model + selected threshold):")
    for k in ("accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc",
              "false_positive_rate", "false_negative_rate"):
        print(f"  {k}: {holdout_metrics[k]:.4f}")
    print(f"  confusion_matrix [tn fp; fn tp]: {holdout_metrics['confusion_matrix']}")

    # ---------------- fairness on out-of-fold (selected threshold) ----------------
    fairness_country = fairness_report(X.reset_index(drop=True), y_arr, oof, chosen_threshold, feature="country")
    age_fairness = claimant_age_fairness(X.reset_index(drop=True), y_arr, oof, chosen_threshold)
    print("\nFairness per country (OOF, selected threshold):")
    print(f"  {'country':24} {'n':>7} {'prev':>7} {'prec':>7} {'rec':>7} {'fpr':>7} {'fnr':>7} ok")
    for c, g in fairness_country["groups"].items():
        print(f"  {c[:24]:24} {g['n']:>7} {g['fraud_prevalence']:>7.4f} {g['precision']:>7.4f} "
              f"{g['recall']:>7.4f} {g['false_positive_rate']:>7.4f} {g['false_negative_rate']:>7.4f} {g['sufficient_data']}")

    # ---------------- train final candidate ----------------
    old_meta = _load_existing_metadata(production_path)
    cv_summary = chosen["cv_mean_std"]
    metadata = train_final(
        data, chosen_kind, sources, args,
        decision_threshold=chosen_threshold, threshold_table_rows=threshold_rows,
        threshold_rationale=threshold_rationale, cv_summary=cv_summary,
        holdout_metrics=holdout_metrics, fairness=fairness_country, age_fairness=age_fairness,
        model_selection_rationale=model_selection_rationale, output_path=output_path,
        old_meta=old_meta, production_path=production_path, cv_folds=args.cv_folds,
    )
    # enrich report with repeated-split + CV comparison + fairness + old/new
    metadata["repeat_metrics"] = repeat_summary
    metadata["cv_comparison"] = {k: v["cv_mean_std"] for k, v in cv_results.items()}
    metadata["old_vs_new"] = compare_old_new(old_meta, metadata, production_path)
    joblib.dump({"pipeline": joblib.load(output_path)["pipeline"], "metadata": metadata}, output_path, compress=3)

    report = dict(metadata)
    report["cv_detail"] = {k: {"cv_mean_std": v["cv_mean_std"], "out_of_fold": v["out_of_fold"],
                               "folds": v["folds"]} for k, v in cv_results.items()}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(f"\nSaved report: {report_path}")
    print(f"Saved candidate model: {output_path}")

    # ---------------- promote (only after validation) ----------------
    if args.promote:
        promote_candidate(output_path, production_path, Path(args.backup_dir))
        print("Production artifact updated. The model remains advisory; no claim is auto-rejected.")
    else:
        print("Production artifact NOT modified. Re-run with --promote to validate + backup + replace.")
    print("Training complete. The model is advisory; no claim is auto-rejected.")


if __name__ == "__main__":
    main()
