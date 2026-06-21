import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.knowledge_base import KnowledgeBase
from scripts.import_knowledge_chunks import build_chunks


client = TestClient(app)


def test_knowledge_base_exposes_playbooks_faqs_and_quality_report() -> None:
    kb = KnowledgeBase(Path("app/data/knowledge_base.json"))

    assert len(kb.response_playbooks) >= 4
    assert len(kb.faqs) >= 5

    quality = kb.quality_report()
    assert quality["scam_count"] >= 14
    assert quality["playbook_count"] >= 4
    assert quality["faq_count"] >= 5
    assert quality["source_coverage"] >= 0.25
    assert quality["missing_required_fields"] == []


def test_knowledge_api_returns_operational_knowledge_sections() -> None:
    playbooks = client.get("/knowledge/playbooks")
    faqs = client.get("/knowledge/faqs")
    quality = client.get("/knowledge/quality")

    assert playbooks.status_code == 200
    assert faqs.status_code == 200
    assert quality.status_code == 200

    assert any(item["stage"] == "active_blocking" for item in playbooks.json())
    assert any("验证码" in item["question"] for item in faqs.json())
    assert quality.json()["playbook_count"] >= 4


def test_pgvector_import_builds_chunks_for_playbooks_and_faqs() -> None:
    data = json.loads(Path("app/data/knowledge_base.json").read_text(encoding="utf-8"))
    chunks = build_chunks(data)

    source_types = {item["source_type"] for item in chunks}
    assert {"scam", "law", "response_playbook", "faq"}.issubset(source_types)

    assert any(
        item["source_type"] == "response_playbook" and "屏幕共享" in item["content"]
        for item in chunks
    )
    assert any(
        item["source_type"] == "faq" and "验证码" in item["content"]
        for item in chunks
    )
