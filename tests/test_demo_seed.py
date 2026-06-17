from pathlib import Path

from app.services.risk_engine import RiskEngine
from app.services.storage import SQLiteStorage
from scripts.seed_demo_data import DEMO_RULE_NAME, seed_demo_data


def test_seed_demo_data_creates_showcase_state(tmp_path: Path) -> None:
    db_path = tmp_path / "demo.db"

    result = seed_demo_data(db_path, reset=True)

    storage = SQLiteStorage(db_path)
    student_id = int(result["users"]["demo_student"]["user_id"])
    state = storage.load_user_state(student_id)
    reports = storage.list_reports(student_id)
    progress = storage.list_scenario_progress(student_id)
    history = storage.list_rule_versions(limit=10)

    assert state is not None
    assert state["points"] >= 100
    assert "风险守门人" in state["badges"]
    assert len(reports) >= 3
    assert {item["status"] for item in reports}.issuperset({"pending", "reviewed", "closed"})
    assert {item["scenario_id"] for item in progress}.issuperset({"C001", "C006", "C010"})
    assert history[0]["is_active"] is True
    assert any(item["action"] == "create" for item in history)
    assert any(item["action"] == "rollback" for item in history)

    engine = RiskEngine()
    active = storage.get_active_rule_version()
    assert active is not None
    engine.apply_configs(active["risk_config"], active["url_config"])
    evaluated = engine.evaluate_text("快递破损后让我扫理赔二维码领取专属补偿码", [], "general", None)
    assert DEMO_RULE_NAME in {item["rule"] for item in evaluated["matched_rules"]}
