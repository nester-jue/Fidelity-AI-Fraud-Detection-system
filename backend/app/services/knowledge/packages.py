"""Seeds the structured departmental knowledge packages into the store.

Packages live in ``docs/knowledge_packages/*.md`` (prepared for later export
to Word). Each package declares its ``Department:`` in its header; ``shared``
packages apply to every role. Seeding is idempotent (matches on source id).
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from ...core.config import settings
from ...models.sqlalchemy_models import KnowledgeChunk, KnowledgeDocument
from .store import add_chunks, add_document

logger = logging.getLogger("knowledge_packages")

DEFAULT_PACKAGES_DIR = Path(settings.CHATBOT_KB_PACKAGES_DIR)


def _package_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return path.stem.replace("_", " ").title()


def _package_department(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines()[:12]:
        stripped = line.strip().lstrip("-").strip()
        if stripped.lower().startswith("department:"):
            value = stripped.split(":", 1)[1].strip()
            return value or "shared"
    return "shared"


def list_packages(packages_dir: Optional[Path] = None) -> List[Path]:
    directory = Path(packages_dir or DEFAULT_PACKAGES_DIR)
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.glob("*.md") if p.name.lower() != "readme.md")


def seed_knowledge_packages(
    db: Optional[Session] = None,
    packages_dir: Optional[Path] = None,
) -> Dict[str, int]:
    """Add or update packages in the store. Returns {"added": int, "updated": int}.

    Idempotent: unchanged packages are skipped. Packages whose file content,
    title or declared department changed are re-ingested (old chunks are
    deleted, fresh chunks re-embedded) — the Phase 7 knowledge-update loop.
    """
    from ...services.db import SessionLocal

    session = db or SessionLocal()
    added = updated = 0
    try:
        for path in list_packages(packages_dir):
            source = f"package:{path.name}"
            content = path.read_text(encoding="utf-8")
            title = _package_title(path)
            dept = _package_department(path)
            existing = (
                session.query(KnowledgeDocument)
                .filter(KnowledgeDocument.source == source)
                .first()
            )
            if existing is not None:
                if (
                    existing.title == title
                    and existing.department == dept
                    and (existing.content or "") == content
                ):
                    continue  # unchanged
                # Re-ingest: replace stale chunks with fresh embeddings.
                session.query(KnowledgeChunk) \
                    .filter(KnowledgeChunk.document_id == existing.id) \
                    .delete(synchronize_session=False)
                existing.title = title
                existing.department = dept
                existing.content = content
                existing.status = "verified"
                session.flush()
                new_chunks = add_chunks(session, existing.id)
                session.commit()
                updated += 1
                logger.info(
                    "Updated knowledge package %s (doc_id=%s, new chunks=%s)",
                    path.name, existing.id, new_chunks,
                )
                continue
            doc = add_document(
                session,
                title=title,
                content=content,
                department=dept,
                source=source,
                doc_type="package",
                status="verified",
            )
            chunks = add_chunks(session, doc.id)
            session.commit()
            added += 1
            logger.info("Seeded knowledge package %s (doc_id=%s, chunks=%s)", path.name, doc.id, chunks)
        return {"added": added, "updated": updated}
    finally:
        if db is None:
            session.close()
