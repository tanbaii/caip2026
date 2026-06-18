from __future__ import annotations

import logging
import os
import importlib.util
from dataclasses import dataclass
from pathlib import Path
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
        self.last_error: str | None = None
        self._missing_psycopg_warned = False

    @classmethod
    def from_env(cls) -> "KnowledgeRetriever | None":
        dsn = os.getenv("PGVECTOR_DSN") or os.getenv("DATABASE_URL")
        if not dsn:
            return None
        top_k = int(os.getenv("RAG_TOP_K", "5"))
        return cls(dsn=dsn, top_k=top_k)

    @staticmethod
    def model_status(model_name: str | None = None) -> dict[str, Any]:
        name = model_name or os.getenv("BGE_M3_MODEL_NAME", "BAAI/bge-m3")
        path = Path(name)
        is_local = (
            path.is_absolute()
            or "/" in name
            or "\\" in name
            or name.startswith(".")
        )
        required_files = ["config.json", "tokenizer.json"]
        weight_files = ["pytorch_model.bin", "model.safetensors"]
        exists = path.exists() if is_local else False
        missing_required = (
            [item for item in required_files if not (path / item).exists()]
            if exists
            else required_files
        )
        has_weight_file = any((path / item).exists() for item in weight_files) if exists else False
        return {
            "name": name,
            "is_local": is_local,
            "exists": exists,
            "has_required_files": exists and not missing_required and has_weight_file,
            "missing_required_files": missing_required,
            "has_weight_file": has_weight_file,
        }

    @classmethod
    def health_from_env(
        cls,
        retriever: "KnowledgeRetriever | None",
        *,
        enabled: bool,
    ) -> dict[str, Any]:
        dsn = os.getenv("PGVECTOR_DSN") or os.getenv("DATABASE_URL")
        status: dict[str, Any] = {
            "enabled": enabled,
            "retriever_configured": retriever is not None,
            "dsn_present": bool(dsn),
            "top_k": int(os.getenv("RAG_TOP_K", "5")),
            "model": cls.model_status(),
            "embedding_dependency": {
                "flag_embedding_installed": importlib.util.find_spec("FlagEmbedding") is not None,
            },
            "pgvector": {
                "connected": False,
                "vector_extension": False,
                "chunks_total": 0,
                "embedded_chunks": 0,
            },
            "last_error": retriever.last_error if retriever else None,
        }

        if not enabled:
            status["last_error"] = "RAG_RETRIEVAL_ENABLED is disabled."
            return status
        if not dsn:
            status["last_error"] = "PGVECTOR_DSN or DATABASE_URL is not configured."
            return status

        try:
            import psycopg
        except ImportError as exc:
            status["last_error"] = f"psycopg is not installed: {exc}"
            return status

        try:
            with psycopg.connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
                    vector_enabled = bool(cur.fetchone()[0])
                    cur.execute(
                        """
                        SELECT
                            COUNT(*) AS chunks_total,
                            COUNT(embedding) AS embedded_chunks
                        FROM knowledge_chunks
                        """
                    )
                    chunks_total, embedded_chunks = cur.fetchone()
            status["pgvector"] = {
                "connected": True,
                "vector_extension": vector_enabled,
                "chunks_total": int(chunks_total or 0),
                "embedded_chunks": int(embedded_chunks or 0),
            }
        except Exception as exc:
            status["last_error"] = f"pgvector health check failed: {exc}"

        return status

    def retrieve(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        if not query.strip():
            return []

        try:
            import psycopg
        except ImportError:
            self.last_error = "psycopg is not installed; RAG retrieval is disabled."
            if not self._missing_psycopg_warned:
                logger.warning(self.last_error)
                self._missing_psycopg_warned = True
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
            self.last_error = str(exc)
            logger.warning("RAG retrieval failed: %s", exc)
            return []

        self.last_error = None

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
