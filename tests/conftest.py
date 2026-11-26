"""Run the whole pytest suite against an ephemeral SQLite database.

``backend.app.core.config.Settings`` and ``backend.app.services.db`` capture
``DATABASE_URL`` and build the SQLAlchemy engine at import time.  pytest imports
this conftest before any test module, so redirecting the environment variable
here keeps every test (and the FastAPI app) away from the tracked working
database in ``data/frauddb.sqlite``.
"""
from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEMP_DIR = Path(tempfile.mkdtemp(prefix="fide-pytest-"))
_DB_PATH = _TEMP_DIR / "frauddb.sqlite"
# Forward slashes keep the URL valid on Windows as well as POSIX.
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH.as_posix()}"

# Deliberately distinct from hashes used by the tests themselves.
_SEED_DOC_HASH = "b" * 64

import pytest  # noqa: E402

from backend.app.services.db import SessionLocal, engine, init_db  # noqa: E402
from backend.app.models.sqlalchemy_models import (  # noqa: E402
    AuditLog, Claim, OCRDocument, Policy, User,
)
from tests.helpers import make_policy_and_claim  # noqa: E402


def _cleanup() -> None:
    """Release SQLite connections and remove the throwaway database."""
    try:
        engine.dispose()
    finally:
        shutil.rmtree(_TEMP_DIR, ignore_errors=True)


# Belt-and-braces: also clean up if pytest exits before fixture teardown.
atexit.register(_cleanup)


def _seed() -> None:
    """Populate the ephemeral DB with the standard demo data and test fixtures.

    The application's own seed routine creates the six demo users (with
    correctly hashed passwords), customers, policies, claims, AI assessments
    and investigations.  The extra rows below reproduce durable records that
    the existing suite assumes are already present in the working database.
    """
    from data.seed_db import seed_database

    seed_database()

    db = SessionLocal()
    try:
        investigator = db.query(User).filter(User.username == "investigator").first()
        policy = db.query(Policy).filter(Policy.policy_number == "POL-LIF-801294").first()
        existing = db.query(Claim).filter(Claim.claim_id == "CLM-TEST-FOREIGN").first()
        if investigator and policy and existing is None:
            now = datetime.now(timezone.utc)
            db.add(Claim(
                claim_id="CLM-TEST-FOREIGN",
                policy_id=policy.id,
                customer_id=policy.customer_id,
                assigned_officer_id=investigator.id,
                claim_type="Death Benefit",
                amount=10000.0,
                incident_date=now,
                submission_date=now,
                status="flagged",
                description="Seeded claim owned by another department for access-control tests.",
            ))

        # Chatbot history and claim-timeline tests refer to this claim by name.
        if db.query(Claim).filter(Claim.claim_id == "CLM-NET-N1").first() is None:
            make_policy_and_claim(
                db, "NET-N1", "POL-NET-N1", "CLM-NET-N1", amount=10000.0,
            )

        # The forward-to-investigation test looks for a previously recorded
        # audit entry of this action (already present in the shipped DB).
        if not db.query(AuditLog).filter(
            AuditLog.action == "CLAIM_FORWARDED_TO_INVESTIGATION"
        ).first():
            db.add(AuditLog(
                user_id=3,
                action="CLAIM_FORWARDED_TO_INVESTIGATION",
                target="Claim:CLM-2026-9001",
                detail={"investigation_id": 1},
            ))

        # Network insights indexes its top suspicious nodes by ``claim_id``.
        # Seeded duplicate-hash documents carry that key, so they occupy the
        # top slots instead of generic customer/policy nodes (which do not).
        claims = db.query(Claim).order_by(Claim.id).limit(12).all()
        if claims and not db.query(OCRDocument).filter(
            OCRDocument.document_hash_sha256 == _SEED_DOC_HASH
        ).first():
            for index, claim in enumerate(claims):
                db.add(OCRDocument(
                    claim_id=claim.id,
                    uploaded_by_id=1,
                    filename=f"seed_network_doc_{index}.txt",
                    file_path="",
                    mime_type="text/plain",
                    processing_status="completed",
                    document_hash_sha256=_SEED_DOC_HASH,
                ))

        db.commit()
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def ephemeral_database():
    """Initialise schema and seed demo data exactly once per test session."""
    init_db()
    _seed()
    yield
    _cleanup()
