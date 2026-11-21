"""KnowledgeProvider abstraction and SQLAlchemy-backed implementation.

The chatbot calls ``provider.retrieve(...)``; the default provider is backed
by the knowledge store so RAG results flow into the chatbot without any
changes to the chatbot itself.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from ...core.config import settings
from ...models.sqlalchemy_models import KnowledgeDocument
from .store import search


@dataclass
class KnowledgeSource:
    document_id: int
    title: str
    department: str
    source: str
    doc_type: str
    excerpt: str
    score: float


class KnowledgeProvider(ABC):
    @abstractmethod
    def retrieve(
        self,
        query: str,
        department: str = "shared",
        top_k: int = 5,
    ) -> List[KnowledgeSource]:
        """Returns up to ``top_k`` knowledge sources relevant to ``query``."""


class SQLAlchemyKnowledgeProvider(KnowledgeProvider):
    """Retrieval over KnowledgeDocument/KnowledgeChunk via SessionLocal."""

    def retrieve(
        self,
        query: str,
        department: str = "shared",
        top_k: int = 5,
    ) -> List[KnowledgeSource]:
        from ...services.db import SessionLocal

        db = SessionLocal()
        try:
            sources: List[KnowledgeSource] = []
            for chunk in search(
                db,
                query,
                department=department or "shared",
                top_k=top_k,
                threshold=settings.CHATBOT_KB_THRESHOLD,
            ):
                doc: Optional[KnowledgeDocument] = db.get(
                    KnowledgeDocument, chunk.document_id
                )
                if doc is None:
                    continue
                sources.append(
                    KnowledgeSource(
                        document_id=doc.id,
                        title=doc.title,
                        department=doc.department,
                        source=doc.source,
                        doc_type=doc.doc_type,
                        excerpt=(chunk.text or "").strip()[:400],
                        score=0.0,
                    )
                )
            return sources
        finally:
            db.close()


_provider: Optional[KnowledgeProvider] = None


def set_provider(provider: Optional[KnowledgeProvider]) -> None:
    global _provider
    _provider = provider


def get_provider() -> KnowledgeProvider:
    global _provider
    if _provider is None:
        _provider = SQLAlchemyKnowledgeProvider()
    return _provider
