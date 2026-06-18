import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.knowledge_retriever import KnowledgeRetriever


client = TestClient(app)


def test_rag_health_endpoint_exposes_configuration() -> None:
    response = client.get("/health/rag")

    assert response.status_code == 200
    data = response.json()
    assert "enabled" in data
    assert "retriever_configured" in data
    assert "dsn_present" in data
    assert "model" in data
    assert data["model"]["name"]


def test_model_status_recognizes_local_bge_directory(tmp_path: Path) -> None:
    model_dir = tmp_path / "bge-m3"
    model_dir.mkdir()
    for name in ("config.json", "tokenizer.json", "pytorch_model.bin"):
        (model_dir / name).write_text("{}", encoding="utf-8")

    previous = os.environ.get("BGE_M3_MODEL_NAME")
    os.environ["BGE_M3_MODEL_NAME"] = str(model_dir)
    try:
        status = KnowledgeRetriever.model_status()
    finally:
        if previous is None:
            os.environ.pop("BGE_M3_MODEL_NAME", None)
        else:
            os.environ["BGE_M3_MODEL_NAME"] = previous

    assert status["is_local"] is True
    assert status["exists"] is True
    assert status["has_required_files"] is True
