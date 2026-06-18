from __future__ import annotations

from app.services.conversation_state import ConversationStateManager
from app.services.risk_dimensions import build_risk_dimensions


def test_safety_actions_reduce_current_danger_not_scam_likelihood() -> None:
    manager = ConversationStateManager()
    manager.update_and_get(
        1,
        "对方让我下载会议软件并开启屏幕共享，还让我马上转账到安全账户",
        "critical",
        "seeking_help",
        [],
    )
    safe = manager.update_and_get(
        1,
        "我已经断网，卸载了会议软件，也已经报警，银行说已经冻结账户",
        "low",
        "seeking_help",
        [],
    )

    dimensions = build_risk_dimensions(
        risk_score=70,
        risk_level="critical",
        conv_data=safe,
    )

    assert safe["session_stage"] == "closure_check"
    assert dimensions["scam_likelihood"]["level"] == "critical"
    assert dimensions["current_danger"]["level"] in {"low", "medium"}
    assert dimensions["residual_risk"]["level"] in {"medium", "high"}


def test_repeated_same_fact_does_not_duplicate_conversation_bonus() -> None:
    manager = ConversationStateManager()
    manager.update_and_get(2, "对方让我转账，还要验证码", "high", "seeking_help", [])
    manager.update_and_get(2, "还是让我转账，还一直要验证码", "high", "seeking_help", [])

    first_bonus, first_rules, _ = manager.compute_conversation_bonus(2)
    second_bonus, second_rules, _ = manager.compute_conversation_bonus(2)

    assert first_bonus > 0
    assert first_rules
    assert second_bonus == 0
    assert second_rules == []


def test_money_lost_enters_loss_recovery_stage() -> None:
    manager = ConversationStateManager()
    data = manager.update_and_get(
        3,
        "我的钱被转走了",
        "critical",
        "seeking_help",
        [],
    )

    assert data["known_facts"]["already_paid"] is True
    assert data["session_stage"] == "loss_recovery"


def test_verification_code_exposure_enters_account_recovery_stage() -> None:
    manager = ConversationStateManager()
    data = manager.update_and_get(
        4,
        "他看到验证码了怎么办",
        "high",
        "seeking_help",
        [],
    )

    assert data["known_facts"]["verification_code_exposed"] is True
    assert data["session_stage"] == "account_recovery"
