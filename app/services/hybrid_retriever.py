"""
Hybrid Retriever: Dense (pgvector) + BM25 (keywords) + RRF Fusion + optional Reranker

Composes the existing KnowledgeRetriever (pgvector/Dense) with BM25 keyword
retrieval and RRF (Reciprocal Rank Fusion) to boost recall diversity.
Optionally applies Cross-Encoder reranking for precision improvement.

Adapted from caip2026 sub-project rag_system/retriever.py
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

try:
    from app.services.bm25_index import BM25Index  # noqa: F401
except ImportError:
    BM25Index = None

logger = logging.getLogger(__name__)

# Default RRF and retrieval parameters (tunable via env)
RRF_K = int(os.environ.get("RAG_RRF_K", "60"))
RETRIEVAL_WEIGHTS = {
    "dense": float(os.environ.get("RAG_DENSE_WEIGHT", "1.0")),
    "bm25": float(os.environ.get("RAG_BM25_WEIGHT", "0.8")),
}
TOP_K_DENSE = int(os.environ.get("RAG_TOP_K_DENSE", "20"))
TOP_K_BM25 = int(os.environ.get("RAG_TOP_K_BM25", "20"))


def rrf_fusion(
    dense_results: List[Dict[str, Any]],
    bm25_results: List[Dict[str, Any]],
    *,
    top_k: int = 20,
    rrf_k: int = RRF_K,
    weights: Dict[str, float] | None = None,
) -> List[Dict[str, Any]]:
    """RRF (Reciprocal Rank Fusion) 融合多路检索结果

    公式: score = sum(weight / (k + rank)) for each source
    """
    if weights is None:
        weights = RETRIEVAL_WEIGHTS

    chunk_scores: Dict[str, Dict[str, Any]] = {}

    def add_scores(results: list, weight: float, source_name: str):
        for rank, item in enumerate(results):
            chunk_id = str(item.get("chunk_id", ""))
            if not chunk_id:
                continue
            if chunk_id not in chunk_scores:
                chunk_scores[chunk_id] = {
                    "rrf_score": 0.0,
                    "sources": [],
                    "content": item.get("content", ""),
                    "title": item.get("title", ""),
                    "scam_type": item.get("scam_type"),
                    "source_type": item.get("source_type", ""),
                    "source_id": item.get("source_id", ""),
                    "metadata": item.get("metadata", {}),
                    "raw_scores": {},
                }
            rrf = weight / (rrf_k + rank + 1)
            chunk_scores[chunk_id]["rrf_score"] += rrf
            chunk_scores[chunk_id]["sources"].append(source_name)
            chunk_scores[chunk_id]["raw_scores"][source_name] = {
                "rank": rank + 1,
                "raw_score": item.get("score", item.get("similarity", 0)),
            }

    add_scores(dense_results, weights["dense"], "dense")
    add_scores(bm25_results, weights["bm25"], "bm25")

    sorted_chunks = sorted(
        chunk_scores.values(),
        key=lambda x: x["rrf_score"],
        reverse=True,
    )

    for chunk in sorted_chunks:
        chunk["sources"] = list(set(chunk["sources"]))

    return sorted_chunks[:top_k]


class HybridRetriever:
    """混合检索器: Dense(pgvector) + BM25(keywords) + 可选 Reranker

    用法:
        retriever = HybridRetriever(dense_retriever=knowledge_retriever)
        retriever.build_bm25_index(documents)      # from chunk data
        results = retriever.retrieve(query)
    """

    def __init__(
        self,
        dense_retriever: Any = None,
        bm25_index: Any = None,
        reranker: Any = None,
    ) -> None:
        self.dense_retriever = dense_retriever
        self.reranker = reranker
        if bm25_index is not None:
            self.bm25_index = bm25_index
        elif BM25Index is not None:
            self.bm25_index = BM25Index()
        else:
            self.bm25_index = None

    def build_bm25_index(self, documents: List[Dict[str, Any]]) -> "HybridRetriever":
        """从文档列表构建 BM25 索引

        documents: [{"chunk_id": str, "content": str}, ...]
        """
        self.bm25_index.build(documents)
        return self

    def set_reranker(self, reranker: Any) -> None:
        self.reranker = reranker

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 20,
        use_reranker: bool = False,
        return_details: bool = False,
    ) -> List[Dict[str, Any]]:
        """执行混合检索"""
        if not query.strip():
            return []

        dense_results: List[Dict[str, Any]] = []
        bm25_results: List[Dict[str, Any]] = []

        # 1. Dense retrieval (pgvector)
        if self.dense_retriever is not None:
            try:
                dense_results = self.dense_retriever.retrieve(query, top_k=TOP_K_DENSE)
            except Exception:
                logger.debug("Dense retrieval failed, continuing with BM25 only", exc_info=True)

        # 2. BM25 keyword retrieval
        if self.bm25_index is not None:
            try:
                bm25_results = self.bm25_index.search(query, top_k=TOP_K_BM25)
            except Exception:
                logger.debug("BM25 retrieval failed", exc_info=True)

        # If only one source has results, return that directly
        if not dense_results and not bm25_results:
            return []
        if not dense_results:
            return bm25_results[:top_k]
        if not bm25_results:
            return dense_results[:top_k]

        # 3. RRF fuse
        fused = rrf_fusion(dense_results, bm25_results, top_k=top_k)

        # 4. Optional reranker
        if use_reranker and self.reranker is not None:
            try:
                fused = self.reranker.rerank(query, fused, top_k=min(top_k, 5))
            except Exception:
                logger.debug("Reranking failed", exc_info=True)

        if not return_details:
            for chunk in fused:
                chunk.pop("raw_scores", None)

        return fused
