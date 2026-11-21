"""SQLAlchemy-backed storage for knowledge documents and chunks.

Documents are tagged with a ``department`` scope (e.g. ``claims_officer``,
``executive_management``, ``system_admin``, or ``shared`` which applies to all
roles). The chatbot only retrieves chunks whose department matches the caller's
role department.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from ...models.sqlalchemy_models import KnowledgeChunk, KnowledgeDocument
from .chunking import chunk_text
from .embedding import embed
from .retrieval import rank_chunks

SHARED_DEPARTMENT = "shared"


def add_document(
    db: Session,
    title: str,
    content: str,
    department: str,
    source: str,
    doc_type: str = "manual",
    status: str = "draft",
) -> KnowledgeDocument:
    doc = KnowledgeDocument(
        title=title,
        department=department or SHARED_DEPARTMENT,
        source=source,
        doc_type=doc_type,
        status=status,
        content=content,
    )
    db.add(doc)
    db.flush()
    return doc


def add_chunks(db: Session, document_id: int, text: Optional[str] = None) -> int:
    """Chunks ``text`` (or the document content) and embeds each chunk."""
    doc = db.get(KnowledgeDocument, document_id)
    if doc is None:
        raise ValueError(f"Knowledge document {document_id} not found")
    segments = chunk_text(text if text is not None else (doc.content or ""))
    for idx, segment in enumerate(segments):
        db.add(
            KnowledgeChunk(
                document_id=document_id,
                chunk_index=idx,
                text=segment,
                embedding=embed(segment),
            )
        )
    db.flush()
    return len(segments)


def get_document(db: Session, document_id: int) -> Optional[KnowledgeDocument]:
    return db.get(KnowledgeDocument, document_id)


def list_documents(
    db: Session,
    department: Optional[str] = None,
    doc_type: Optional[str] = None,
    limit: int = 500,
) -> List[KnowledgeDocument]:
    q = db.query(KnowledgeDocument)
    if department:
        q = q.filter(KnowledgeDocument.department == department)
    if doc_type:
        q = q.filter(KnowledgeDocument.doc_type == doc_type)
    return q.order_by(KnowledgeDocument.created_at.desc()).limit(limit).all()


def chunk_count(db: Session, document_id: int) -> int:
    return db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document_id).count()


def search(
    db: Session,
    query: str,
    department: Optional[str] = None,
    top_k: int = 5,
    threshold: float = 0.0,
) -> List[KnowledgeChunk]:
    """Returns the top-scoring chunks for ``query``, filtered by scope.

    ``department=None`` searches across all departments; callers (the chatbot)
    always pass the caller's role department, with ``shared`` covering the
    company-wide knowledge that applies to everyone.
    """
    q = db.query(KnowledgeChunk).join(KnowledgeDocument)
    if department:
        q = q.filter(
            KnowledgeDocument.department.in_([department, SHARED_DEPARTMENT])
        )
    chunks = q.all()
    if not chunks:
        return []
    ranked = rank_chunks(query, chunks, top_k=top_k, threshold=threshold)
    return [c for c, _s in ranked]
