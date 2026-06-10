from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from app.services.embedding_service import BgeM3EmbeddingService, EmbeddingService

logger = logging.getLogger(__name__)


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.8f}" for value in values) + "]"


@dataclass
class RetrievedKnowledge:
    title: str
    content: str
    scam_type: str | None
    similarity: float
    source_type: str
    source_id: str | None
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content,
            "scam_type": self.scam_type,
            "similarity": round(self.similarity, 4),
            "source_type": self.source_type,
            "source_id": self.source_id,
            "metadata": self.metadata,
        }


class KnowledgeRetriever:
    """pgvector-backed semantic retriever for anti-fraud knowledge.

    This service is intentionally side-channel only: it returns context for
    explanations, but never produces or changes risk scores.
    """

    def __init__(
        self,
        dsn: str,
        embedding_service: EmbeddingService | None = None,
        top_k: int = 5,
    ) -> None:
        self.dsn = dsn
        self.embedding_service = embedding_service or BgeM3EmbeddingService()
        self.top_k = top_k

    @classmethod
    def from_env(cls) -> "KnowledgeRetriever | None":
        dsn = os.getenv("PGVECTOR_DSN") or os.getenv("DATABASE_URL")
        if not dsn:
            return None
        top_k = int(os.getenv("RAG_TOP_K", "5"))
        return cls(dsn=dsn, top_k=top_k)

    def retrieve(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        if not query.strip():
            return []

        try:
            import psycopg
        except ImportError:
            logger.warning("psycopg is not installed; RAG retrieval is disabled.")
            return []

        try:
            query_vector = _vector_literal(self.embedding_service.embed(query))
            limit = top_k or self.top_k

            with psycopg.connect(self.dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT
                            title,
                            content,
                            scam_type,
                            1 - (embedding <=> %s::vector) AS similarity,
                            source_type,
                            source_id,
                            metadata
                        FROM knowledge_chunks
                        WHERE embedding IS NOT NULL
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                        """,
                        (query_vector, query_vector, limit),
                    )
                    rows = cur.fetchall()
        except Exception as exc:
            logger.warning("RAG retrieval failed: %s", exc)
            return []

        results: list[dict[str, Any]] = []
        for title, content, scam_type, similarity, source_type, source_id, metadata in rows:
            metadata_dict = metadata if isinstance(metadata, dict) else {}
            item = RetrievedKnowledge(
                title=str(title),
                content=str(content),
                scam_type=str(scam_type) if scam_type else None,
                similarity=float(similarity),
                source_type=str(source_type),
                source_id=str(source_id) if source_id else None,
                metadata=metadata_dict,
            )
            results.append(item.as_dict())
        return results
