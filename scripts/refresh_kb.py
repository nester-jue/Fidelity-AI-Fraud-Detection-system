"""
NEXA Knowledge Base — Phase 7 Refresh Script

Re-syncs the knowledge base: seeds any missing departmental packages and
re-ingests packages whose files changed since the last run. Prints store
statistics (documents per department, chunk totals, empty-chunk documents).

Usage:
    python scripts/refresh_kb.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import func

from backend.app.services.db import SessionLocal
from backend.app.models.sqlalchemy_models import KnowledgeChunk, KnowledgeDocument
from backend.app.services.knowledge.packages import seed_knowledge_packages


def main() -> int:
    db = SessionLocal()
    try:
        result = seed_knowledge_packages(db)
        total_docs = db.query(KnowledgeDocument).count()
        total_chunks = db.query(KnowledgeChunk).count()
        empty = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.id.not_in(
                db.query(KnowledgeChunk.document_id).subquery()
            )
        ).count()
        per_dept = db.query(
            KnowledgeDocument.department, func.count(KnowledgeDocument.id)
        ).group_by(KnowledgeDocument.department).order_by(KnowledgeDocument.department).all()

        print(f"Knowledge base sync — added: {result['added']}, updated: {result['updated']}")
        print(f"Documents: {total_docs} (chunks: {total_chunks})")
        if empty:
            print(f"WARNING: {empty} document(s) have zero chunks (check source files).")
        for dept, count in per_dept:
            print(f"  {dept}: {count} document(s)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
