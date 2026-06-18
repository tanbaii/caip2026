from fastapi.testclient import TestClient

from app.main import app
from app.services.chat_workflow import ChatWorkflowRunner


client = TestClient(app)


def test_chat_history_is_persisted_and_listed() -> None:
    user_id = 99001
    response = client.post("/chat", json={
        "user_id": user_id,
        "message": "有人让我先交保证金再返利",
        "user_profile": {"role": "student"},
    })
    assert response.status_code == 200

    history = client.get(f"/users/{user_id}/chat/history?limit=5")
    assert history.status_code == 200
    data = history.json()

    assert data["user_id"] == user_id
    assert data["total"] >= 1
    latest = data["items"][-1]
    assert latest["user_message"]
    assert latest["assistant_reply"]
    assert latest["risk_level"] in {"low", "medium", "high", "critical"}
    assert isinstance(latest["matched_scams"], list)


def test_chat_reset_keeps_persistent_history() -> None:
    user_id = 99002
    client.post("/chat", json={
        "user_id": user_id,
        "message": "客服说退款要验证码",
    })

    reset = client.post("/chat/reset", json={"user_id": user_id})
    assert reset.status_code == 200

    history = client.get(f"/users/{user_id}/chat/history")
    assert history.status_code == 200
    assert history.json()["total"] >= 1


def test_langgraph_runner_has_warning_branch() -> None:
    from app.main import dialogue_service

    runner = dialogue_service if isinstance(dialogue_service, ChatWorkflowRunner) else ChatWorkflowRunner(dialogue_service)

    assert "generate_warning_reply" in runner.workflow_nodes()
    assert "retrieve_knowledge" in runner.workflow_nodes()
    assert runner.route_after_conversation({"conv_data": {"session_stage": "warning"}}) == "generate_warning_reply"
    assert runner.route_after_conversation({"conv_data": {"session_stage": "assessing"}}) == "retrieve_knowledge"


def test_safety_acknowledgement_clears_high_risk_floor() -> None:
    user_id = 99003
    first = client.post("/chat", json={
        "user_id": user_id,
        "message": "对方让我下载会议软件并开启屏幕共享，还让我马上转账到安全账户并提供验证码",
        "user_profile": {"role": "student"},
        "emotion": "anxious",
    })
    assert first.status_code == 200
    assert first.json()["risk_level"] in {"high", "critical"}

    second = client.post("/chat", json={
        "user_id": user_id,
        "message": "我已经退出屏幕共享，也已经卸载了会议软件，没有转账",
        "user_profile": {"role": "student"},
    })
    assert second.status_code == 200
    data = second.json()

    assert data["risk_level"] not in {"high", "critical"}
    assert data["session_stage"] == "closure_check"
    assert data["known_facts"]["safety_action_taken"] is True
