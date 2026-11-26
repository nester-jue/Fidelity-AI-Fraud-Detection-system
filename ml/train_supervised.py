"""Train and repeatedly evaluate the supervised NEXA fraud classifier.

Usage (from the repository root):

    python ml/train_supervised.py --runs 10

The labelled Hugging Face CSVs in ``datasets/huggingface`` are combined. Columns
that reveal the outcome (fraud_probability, fraud_scheme_type, detection_method,
recovery_amount_usd) are deliberately excluded so the model learns claim
features, not the answer. The model is advisory: it is never an automatic
claims-rejection decision.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

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
from sklearn.model_selection import train_test_split  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import OneHotEncoder, StandardScaler  # noqa: E402

from backend.app.ml.supervised import (  # noqa: E402
    CATEGORICAL_COLUMNS,
    FEATURE_COLUMNS,
    NUMERIC_COLUMNS,
)

LABEL = "fraud_label"
LEAKAGE_COLUMNS = {
    "fraud_probability",       # effectively a pre-computed answer
    "fraud_scheme_type",       # known only after investigation
    "detection_method",        # outcome/process metadata
    "recovery_amount_usd",     # post-decision outcome
    "record_id",               # identifier, not a claim attribute
}
DEFAULT_CSV_DIR = ROOT / "datasets" / "huggingface"
DEFAULT_MODEL_PATH = ROOT / "backend" / "app" / "ml" / "models" / "fraud_classifier.joblib"
DEFAULT_REPORT_PATH = ROOT / "ml" / "training_report.json"


def load_labelled_claims(csv_dir: Path) -> Tuple[pd.DataFrame, List[str]]:
    files = sorted(csv_dir.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in {csv_dir}")
    frames = []
    sources: List[str] = []
    for path in files:
        frame = pd.read_csv(path)
        required = [c for c in list(FEATURE_COLUMNS) + [LABEL] if c not in frame.columns]
        if required:
            raise ValueError(f"{path.name} is missing required columns: {required}")
        frame = frame[[c for c in FEATURE_COLUMNS if c in frame.columns] + [LABEL]].copy()
        frames.append(frame)
        sources.append(f"{path.name} ({len(frame):,} rows)")
        print(f"  loaded {path.name}: {len(frame):,} rows")
    data = pd.concat(frames, ignore_index=True)
    for column in NUMERIC_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    for column in CATEGORICAL_COLUMNS:
        data[column] = data[column].fillna("Unknown").astype(str).str.strip().str.lower()
    data[LABEL] = pd.to_numeric(data[LABEL], errors="coerce")
    before = len(data)
    data = data.dropna(subset=[LABEL])
    data[LABEL] = data[LABEL].astype(int)
    print(f"Combined {before:,} rows from {len(files)} files; {len(data):,} labelled rows retained.")
    return data, sources


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
    return Pipeline([("preprocess", preprocess), ("classifier", estimator)])


def evaluate_once(X: pd.DataFrame, y: pd.Series, kind: str, seed: int, test_size: float) -> Dict[str, float]:
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=seed, stratify=y
    )
    pipeline = make_pipeline(kind, seed)
    pipeline.fit(X_train, y_train)
    probability = pipeline.predict_proba(X_test)[:, 1]
    prediction = (probability >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, prediction, labels=[0, 1]).ravel()
    return {
        "seed": float(seed),
        "roc_auc": float(roc_auc_score(y_test, probability)),
        "pr_auc": float(average_precision_score(y_test, probability)),
        "precision": float(precision_score(y_test, prediction, zero_division=0)),
        "recall": float(recall_score(y_test, prediction, zero_division=0)),
        "f1": float(f1_score(y_test, prediction, zero_division=0)),
        "accuracy": float(accuracy_score(y_test, prediction)),
        "true_negatives": float(tn),
        "false_positives": float(fp),
        "false_negatives": float(fn),
        "true_positives": float(tp),
    }


def summarise(runs: List[Dict[str, float]]) -> Dict[str, float]:
    summary: Dict[str, float] = {}
    for key in runs[0]:
        values = [r[key] for r in runs]
        summary[f"{key}_mean"] = round(float(np.mean(values)), 6)
        summary[f"{key}_std"] = round(float(np.std(values)), 6)
    return summary


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
    print(f"  ROC-AUC : {summary['roc_auc_mean']:.4f} ± {summary['roc_auc_std']:.4f}")
    print(f"  PR-AUC  : {summary['pr_auc_mean']:.4f} ± {summary['pr_auc_std']:.4f}")
    print(f"  Precision: {summary['precision_mean']:.4f}  Recall: {summary['recall_mean']:.4f}")
    print(f"  F1      : {summary['f1_mean']:.4f}  Accuracy: {summary['accuracy_mean']:.4f}")
    print("-" * 68)


def train_final(data: pd.DataFrame, kind: str, summary: Dict[str, float], sources: List[str],
                args: argparse.Namespace) -> Dict[str, object]:
    X = data[list(FEATURE_COLUMNS)]
    y = data[LABEL]
    pipeline = make_pipeline(kind, args.seed)
    pipeline.fit(X, y)
    trained_at = datetime.now(timezone.utc)
    version = f"supervised-{kind}-{trained_at.strftime('%Y%m%dT%H%M%SZ')}"
    metadata = {
        "version": version,
        "model_kind": kind,
        "trained_at": trained_at.isoformat(),
        "training_rows": int(len(data)),
        "fraud_rows": int(y.sum()),
        "legitimate_rows": int((y == 0).sum()),
        "sources": sources,
        "excluded_leakage_columns": sorted(LEAKAGE_COLUMNS),
        "feature_columns": list(FEATURE_COLUMNS),
        "decision_threshold": 0.5,
        "runs": args.runs,
        "test_size": args.test_size,
        "defaults": defaults_from(data),
        "repeat_metrics": summary,
        "report_path": DEFAULT_REPORT_PATH.relative_to(ROOT).as_posix(),
        "limitation": (
            "Advisory signal only. Trained on the supplied labelled CSVs; "
            "human review remains required before any claim decision."
        ),
    }
    metadata.update({k: v for k, v in summary.items() if k.endswith("_mean")})
    artefact = {"pipeline": pipeline, "metadata": metadata}
    DEFAULT_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artefact, DEFAULT_MODEL_PATH, compress=3)
    DEFAULT_REPORT_PATH.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Saved model:  {DEFAULT_MODEL_PATH}")
    print(f"Saved report: {DEFAULT_REPORT_PATH}")
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=10, help="number of repeated stratified evaluations")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model", choices=("logistic", "random_forest"), default="logistic")
    parser.add_argument(
        "--compare-forest",
        action="store_true",
        help="also run one RandomForest split and use it if PR-AUC is better",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    print("=" * 68)
    print("NEXA SUPERVISED FRAUD MODEL TRAINING")
    print("=" * 68)
    data, sources = load_labelled_claims(DEFAULT_CSV_DIR)
    X = data[list(FEATURE_COLUMNS)]
    y = data[LABEL]

    runs = []
    for seed in range(args.seed, args.seed + args.runs):
        metrics = evaluate_once(X, y, args.model, seed, args.test_size)
        runs.append(metrics)
        print(
            f"run {seed - args.seed + 1:02d}/{args.runs}: "
            f"ROC-AUC={metrics['roc_auc']:.4f} PR-AUC={metrics['pr_auc']:.4f} "
            f"F1={metrics['f1']:.4f}"
        )
    summary = summarise(runs)
    print_summary(f"{args.model.upper()} — {args.runs} repeated stratified splits", summary)

    chosen_kind = args.model
    if args.compare_forest:
        forest = evaluate_once(X, y, "random_forest", args.seed, args.test_size)
        print_summary("RANDOM_FOREST — single comparison split", summarise([forest]))
        if forest["pr_auc"] > summary["pr_auc_mean"]:
            chosen_kind = "random_forest"
            summary = summarise([forest])
            summary["comparison_note"] = "Forest selected on one split; fewer repeats than the primary model."

    train_final(data, chosen_kind, summary, sources, args)
    print("Training complete. The model is advisory; no claim is auto-rejected.")


if __name__ == "__main__":
    main()
