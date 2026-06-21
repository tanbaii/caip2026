"""
Cross-Encoder Reranker
基于 BGE-Reranker 对初筛结果进行精排

Adapted from caip2026 sub-project rag_system/reranker.py
"""

import os
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class Reranker:
    """Cross-Encoder 重排序器

    将 Query 和每个候选 Document 拼接后一起编码打分，
    精度高于 Bi-Encoder（Embedding），适合精排阶段。

    工作流程:
    1. 接收初筛的 Top-K 候选文档
    2. 将每个候选文档与 Query 拼接
    3. Cross-Encoder 打分
    4. 按分数重新排序，返回 Top-K
    """

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
        max_length: int = 512,
    ) -> None:
        self.model_name = model_name or os.getenv(
            "RERANKER_MODEL_NAME",
            "BAAI/bge-reranker-large",
        )
        self.device = device or os.getenv("RERANKER_DEVICE", "cpu")
        self.max_length = max_length
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return
        logger.info("Loading reranker model: %s (device=%s)", self.model_name, self.device)
        try:
            from sentence_transformers import CrossEncoder  # noqa: F811
        except ImportError:
            raise RuntimeError(
                "sentence_transformers is not installed. "
                "Run: pip install sentence-transformers"
            )
        self._model = CrossEncoder(
            self.model_name,
            max_length=self.max_length,
            device=self.device,
        )
        logger.info("Reranker model loaded.")

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5,
        batch_size: int = 8,
    ) -> List[Dict[str, Any]]:
        if not documents:
            return []

        self._load_model()

        pairs = []
        for doc in documents:
            content = str(doc.get("content", ""))[:400]
            pairs.append([query, content])

        scores = self._model.predict(
            pairs,
            batch_size=batch_size,
            show_progress_bar=False,
        )

        for doc, score in zip(documents, scores):
            doc["rerank_score"] = float(score)

        sorted_docs = sorted(
            documents,
            key=lambda x: x.get("rerank_score", 0),
            reverse=True,
        )
        return sorted_docs[:top_k]
