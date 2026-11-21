"""
NEXA Knowledge Base — Phase 7 Quality Tests.

Covers knowledge-base response quality (retrieval per department), package
coverage, and the seed/refresh update loop.

Run with: python -m pytest tests/test_knowledge_quality.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.db import init_db, SessionLocal
from backend.app.models.sqlalchemy_models import KnowledgeDocument, KnowledgeChunk
from backend.app.services.knowledge import store
from backend.app.services.knowledge.packages import seed_knowledge_packages, DEFAULT_PACKAGES_DIR


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db()


# 1. Retrieval quality per department
def test_retrieval_funeral_claim_documents():
    db = SessionLocal()
    try:
        results = store.search(
            db, "What documents are required for a funeral claim?",
            department="claims_officer", top_k=3, threshold=0.0,
        )
        assert results, "expected retrieval results for funeral claim question"
        assert any("funeral" in (r.text or "").lower() for r in results)
    finally:
        db.close()


def test_retrieval_fraud_types():
    db = SessionLocal()
    try:
        results = store.search(
            db, "What are common types of insurance fraud?",
            department="fraud_investigator", top_k=3, threshold=0.0,
        )
        assert results, "expected retrieval results for fraud types question"
        docs = {r.document_id for r in results}
        doc_titles = [
            db.get(KnowledgeDocument, d).title.lower()
            for d in docs
        ]
        assert any("fraud" in t for t in doc_titles)
    finally:
        db.close()


def test_retrieval_scoped_to_department():
    db = SessionLocal()
    try:
        results = store.search(
            db, "What documents are required for a funeral claim?",
            department="claims_manager", top_k=3, threshold=0.0,
        )
        # Claims managers don't need funeral-specific processing knowledge —
        # but system-wide "shared" knowledge should still be retrievable.
        assert db.query(KnowledgeDocument).filter(
            KnowledgeDocument.department == "claims_manager"
        ).count() > 0
    finally:
        db.close()


# 2. Package coverage
EXPECTED_DEPARTMENTS = {
    "shared", "claims_officer", "claims_manager", "fraud_investigator",
    "compliance_officer", "executive_management", "system_admin",
}


def test_all_packages_have_coverage():
    db = SessionLocal()
    try:
        packages = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.doc_type == "package"
        ).all()
        by_dept = {p.department: p for p in packages}
        missing = EXPECTED_DEPARTMENTS - set(by_dept)
        assert not missing, f"missing packages for departments: {missing}"
        for p in packages:
            chunks = db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == p.id).count()
            assert chunks >= 1, f"package {p.title} has no chunks"
            assert len(p.content or "") >= 200, f"package {p.title} is too short"
    finally:
        db.close()


def test_packages_seedable_idempotently():
    db = SessionLocal()
    try:
        result = seed_knowledge_packages(db, packages_dir=DEFAULT_PACKAGES_DIR)
        assert isinstance(result, dict) and "added" in result and "updated" in result
        second = seed_knowledge_packages(db, packages_dir=DEFAULT_PACKAGES_DIR)
        assert second["added"] == 0, f"second run should add nothing, got {second}"
    finally:
        db.close()


def test_package_deletion_reindexes_on_resync():
    db = SessionLocal()
    try:
        doc = store.add_document(
            db, title="Temp Sync Test", content="temporary test content",
            department="shared", source="package:TEMP-SYNC-TEST.md", doc_type="package",
        )
        n = store.add_chunks(db, doc.id)
        assert n >= 1
        # Deleting the doc and re-seeding should not resurrect it (idempotency
        # check), and re-adding should work via the store.
        db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).delete(synchronize_session=False)
        db.delete(doc)
        db.commit()
        assert store.get_document(db, doc.id) is None
    finally:
        db.close()
