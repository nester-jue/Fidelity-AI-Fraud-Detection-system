"""NEXA Departmental AI Knowledge Base (RAG) services."""

from .provider import KnowledgeProvider, KnowledgeSource, get_provider, set_provider
from .store import add_chunks, add_document, list_documents, search

__all__ = [
    "KnowledgeProvider",
    "KnowledgeSource",
    "get_provider",
    "set_provider",
    "add_document",
    "add_chunks",
    "list_documents",
    "search",
]
