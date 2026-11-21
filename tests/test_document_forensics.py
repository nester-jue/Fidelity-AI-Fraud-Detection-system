"""
NEXA Document Forensics — Duplicate + Inconsistency Tests (Phase 8).

Covers: duplicate document groups (SHA-256), cross-document consistency
issues (conflicting claimant names / policy numbers / dates, missing fields
across a claim's documents), and the forensic analysis summary shape.

Run with: python -m pytest tests/test_document_forensics.py -v
"""
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.db import init_db, SessionLocal
from backend.app.models.sqlalchemy_models import Claim, OCRDocument, RoleEnum, User
from backend.app.services.document_forensics import (
    analyze_claim_documents,
    find_duplicate_document_groups,
    generate_forensic_analysis,
)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db()


def _admin_user_id(db: SessionLocal) -> int:
    user = db.query(User).filter(User.role == RoleEnum.SYSTEM_ADMIN).first()
    return user.id if user else db.query(User).first().id


def _mk_doc(db, filename, path, **kwargs):
    doc = OCRDocument(
        filename=filename,
        file_path=path,
        mime_type="application/pdf",
        uploaded_by_id=kwargs.pop("uploaded_by_id", None),
        processing_status=kwargs.pop("processing_status", "completed"),
        **kwargs,
    )
    db.add(doc)
    db.commit()
    return doc


def _cleanup(docs):
    db = SessionLocal()
    try:
        for d in docs:
            stored = db.get(OCRDocument, d.id)
            if stored:
                db.delete(stored)
        db.commit()
    finally:
        db.close()


# 1. Duplicate groups by SHA-256
def test_duplicate_document_groups():
    db = SessionLocal()
    created = []
    try:
        aid = _admin_user_id(db)
        d1 = _mk_doc(db, "dup-a.pdf", "/test/dup-a.pdf",
                     document_hash_sha256="f" * 64, uploaded_by_id=aid)
        d2 = _mk_doc(db, "dup-b.pdf", "/test/dup-b.pdf",
                     document_hash_sha256="f" * 64, uploaded_by_id=aid)
        created = [d1, d2]
        groups = [g for g in find_duplicate_document_groups(db) if g["hash"] == "f" * 64]
        assert len(groups) == 1
        assert len(groups[0]["documents"]) == 2
    finally:
        _cleanup(created)
        db.close()


# 2. Conflicting details across a claim's documents
def test_conflicting_claim_details():
    db = SessionLocal()
    created = []
    try:
        claim = db.query(Claim).first()
        assert claim is not None
        aid = _admin_user_id(db)
        d1 = _mk_doc(db, "conflict-1.pdf", "/test/conflict-1.pdf",
                     claim_id=claim.id, uploaded_by_id=aid,
                     extracted_fields={"claimant_name": "Alice Smith", "policy_number": "POL-111"},
                     extracted_dates=["2024-01-01"],
                     missing_fields=["Beneficiary Name"])
        d2 = _mk_doc(db, "conflict-2.pdf", "/test/conflict-2.pdf",
                     claim_id=claim.id, uploaded_by_id=aid,
                     extracted_fields={"claimant_name": "Bob Jones", "policy_number": "POL-222"},
                     extracted_dates=["2024-01-01"],
                     missing_fields=[])
        created = [d1, d2]
        issues = analyze_claim_documents(db, claim_id=claim.id)
        types = {i["type"] for i in issues}
        assert "conflicting_claimant_names" in types
        assert "conflicting_policy_numbers" in types
        assert "missing_fields_across_docs" in types
    finally:
        _cleanup(created)
        db.close()


# 3. Analysis summary shape + seeded docs flow
def test_generate_forensic_analysis_shape():
    db = SessionLocal()
    try:
        analysis = generate_forensic_analysis(db)
        assert set(analysis) >= {"duplicate_groups", "claim_consistency_issues", "suspicious_flags", "summary"}
        assert analysis["summary"]["duplicate_groups"] == len(analysis["duplicate_groups"])
        assert analysis["summary"]["claim_consistency_issues"] == len(analysis["claim_consistency_issues"])
        assert analysis["summary"]["suspicious_flags"] == len(analysis["suspicious_flags"])
    finally:
        db.close()
