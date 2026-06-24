import json
from pathlib import Path

import pytest

from app.services.bm25_index import BM25Index
from app.services.hybrid_retriever import HybridRetriever
from scripts import build_knowledge_center


def test_knowledge_center_builder_preserves_enriched_existing_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "knowledge_center.json"
    enriched = {
        "meta": {
            "title": "反诈知识中心",
            "version": "2.2.0",
            "stats": {"fraud_types": 68, "categories": 6, "laws": 8, "quiz": 48},
        },
        "frauds": [{"id": f"F{i:02d}", "name": f"诈骗{i}"} for i in range(68)],
        "quiz": [{"q": f"题{i}", "answer": 1} for i in range(48)],
        "laws": [{"name": f"法规{i}"} for i in range(8)],
    }
    output.write_text(json.dumps(enriched, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(build_knowledge_center, "DATA_PATH", output)

    build_knowledge_center.main([])

    rebuilt = json.loads(output.read_text(encoding="utf-8"))
    assert rebuilt["meta"]["stats"]["fraud_types"] == 68
    assert rebuilt["meta"]["stats"]["quiz"] == 48
    assert len(rebuilt["frauds"]) == 68


def test_knowledge_center_builder_help_does_not_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "knowledge_center.json"
    monkeypatch.setattr(build_knowledge_center, "DATA_PATH", output)

    with pytest.raises(SystemExit) as exc_info:
        build_knowledge_center.main(["--help"])

    assert exc_info.value.code == 0
    assert "usage:" in capsys.readouterr().out
    assert not output.exists()


def test_hybrid_retriever_loads_bm25_index_with_content(tmp_path: Path) -> None:
    index_path = tmp_path / "bm25_index.pkl"
    BM25Index().build(
        [
            {
                "chunk_id": "rule_fake_authority",
                "title": "冒充公检法",
                "content": "冒充公检法要求转账到安全账户并索要验证码，是高风险诈骗。",
                "source_type": "fraud_rule",
            }
        ]
    ).save(index_path)

    retriever = HybridRetriever(bm25_index_path=index_path)
    results = retriever.retrieve("公检法 安全账户 验证码", top_k=3)

    assert retriever.bm25_docs == 1
    assert results
    assert results[0]["content"] == "冒充公检法要求转账到安全账户并索要验证码，是高风险诈骗。"
    assert results[0]["title"] == "冒充公检法"


def test_default_rag_health_reports_loaded_bm25_index() -> None:
    from app.main import rag_health

    hybrid = rag_health()["hybrid"]
    assert hybrid["bm25_docs"] >= 900


def test_base_requirements_include_default_bm25_dependencies() -> None:
    requirements = Path("requirements.txt").read_text(encoding="utf-8")

    assert "rank-bm25" in requirements
    assert "jieba" in requirements


def test_game_page_requires_user_action_before_godot_embed() -> None:
    page = Path("frontend/src/pages/GamePage.vue").read_text(encoding="utf-8")

    assert "showArcade" in page
    assert '@click="showArcade = true"' in page
    assert 'role="dialog"' in page
    assert 'aria-modal="true"' in page
    assert "arcadeGameUrl" in page
    assert "index.html?v=arcade-" in page
    assert ':src="arcadeGameUrl"' in page
    assert ':href="arcadeGameUrl"' in page
    assert "iframe" in page


def test_arcade_dialog_is_scoped_to_game_page_content() -> None:
    page = Path("frontend/src/pages/GamePage.vue").read_text(encoding="utf-8")

    assert '<div class="page-shell relative' in page
    assert "<Teleport" not in page
    assert 'class="absolute inset-0' in page
    assert 'class="fixed inset-0' not in page


def test_fastapi_serves_arcade_game_entry() -> None:
    from fastapi.testclient import TestClient

    from app.main import FRONTEND_GODOT_PUBLIC_DIR, app, _godot_static_dir

    response = TestClient(app).get("/godot_game/index.html")

    assert _godot_static_dir == FRONTEND_GODOT_PUBLIC_DIR
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "data-game-root" in response.text
    assert "GODOT_CONFIG" not in response.text


def test_arcade_entry_is_playable_without_broken_godot_pack() -> None:
    html = Path("frontend/public/godot_game/index.html").read_text(encoding="utf-8")

    assert "data-game-root" in html
    assert 'data-action="intercept"' in html
    assert 'data-action="allow"' in html
    assert "const CARD_DECK" in html
    assert "GODOT_CONFIG" not in html


def test_arcade_entry_has_strong_feedback_and_settlement_screen() -> None:
    html = Path("frontend/public/godot_game/index.html").read_text(encoding="utf-8")

    assert "data-feedback-burst" in html
    assert "data-float-score" in html
    assert "screen-shake" in html
    assert "data-settlement" in html
    assert "data-final-score" in html
    assert "data-final-accuracy" in html


def test_arcade_deck_includes_migrated_godot_card_pool() -> None:
    html = Path("frontend/public/godot_game/index.html").read_text(encoding="utf-8")

    assert html.count("kind:") >= 30
    for migrated_phrase in ["注销校园贷", "冒充老师收费", "百万保障", "民族资产", "ETC", "机票退改签"]:
        assert migrated_phrase in html


def test_arcade_uses_sixty_second_rounds_and_settlement_leaderboard() -> None:
    html = Path("frontend/public/godot_game/index.html").read_text(encoding="utf-8")

    assert "const GAME_DURATION_SECONDS = 60" in html
    assert "<strong data-time>60</strong>" in html
    assert "data-leaderboard" in html
    assert "ARCADE_LEADERBOARD_KEY" in html
    assert "function saveLeaderboard" in html
    assert "function renderLeaderboard" in html


def test_arcade_entry_waits_on_start_screen_with_best_score() -> None:
    html = Path("frontend/public/godot_game/index.html").read_text(encoding="utf-8")

    assert "data-start-screen" in html
    assert "data-start-game" in html
    assert "data-best-score" in html
    assert "function showStartScreen" in html
    assert "nodes.startGame.addEventListener" in html
    assert "showStartScreen();" in html
    assert "startGame();" not in html
