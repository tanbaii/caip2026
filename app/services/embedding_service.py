from __future__ import annotations

import os
from typing import Protocol


class EmbeddingService(Protocol):
    def embed(self, text: str) -> list[float]:
        """Return a 1024-dimension embedding for text."""


class BgeM3EmbeddingService:
    """Lazy BGE-M3 dense embedding provider.

    The FlagEmbedding dependency is imported only when the first embedding is
    requested, so the app can keep running without RAG dependencies installed.
    """

    def __init__(
        self,
        model_name: str | None = None,
        use_fp16: bool | None = None,
        max_length: int = 8192,
    ) -> None:
        self.model_name = model_name or os.getenv("BGE_M3_MODEL_NAME", "BAAI/bge-m3")
        self.use_fp16 = (
            use_fp16
            if use_fp16 is not None
            else os.getenv("BGE_M3_USE_FP16", "0").lower() in {"1", "true", "yes"}
        )
        self.max_length = max_length
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                from FlagEmbedding import BGEM3FlagModel
            except ImportError as exc:
                raise RuntimeError("FlagEmbedding is not installed. Run: pip install -r requirements-rag.txt") from exc
            self._model = BGEM3FlagModel(self.model_name, use_fp16=self.use_fp16)
        return self._model

    def embed(self, text: str) -> list[float]:
        model = self._load_model()
        encoded = model.encode(
            [text],
            batch_size=1,
            max_length=self.max_length,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        vector = encoded["dense_vecs"][0]
        return [float(value) for value in vector.tolist()]
