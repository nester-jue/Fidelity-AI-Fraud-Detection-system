"""Validate a trained candidate and promote it to production with a timestamped backup.

PHASE 5 -> PHASE 6. Usage (repo root):

    python ml/promote_model.py --candidate backend/app/ml/models/fraud_classifier.candidate.joblib

Creates a timestamped backup of the existing production artifact, verifies the
candidate loads + has a fitted pipeline + correct (leakage-free) feature order,
then replaces production. The model remains advisory.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.train_supervised import (  # noqa: E402
    BACKUP_DIR,
    PRODUCTION_MODEL_PATH,
    promote_candidate,
)

DEFAULT_CANDIDATE = PRODUCTION_MODEL_PATH.with_name("fraud_classifier.candidate.joblib")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=str, default=str(DEFAULT_CANDIDATE))
    parser.add_argument("--production-path", type=str, default=str(PRODUCTION_MODEL_PATH))
    parser.add_argument("--backup-dir", type=str, default=str(BACKUP_DIR))
    args = parser.parse_args()
    promote_candidate(Path(args.candidate), Path(args.production_path), Path(args.backup_dir))
    print("Done. Production artifact updated; model remains advisory.")


if __name__ == "__main__":
    main()
