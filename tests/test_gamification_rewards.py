from __future__ import annotations

from app.services.gamification import GamificationService


def test_risk_alert_reward_is_deduped_by_event_key() -> None:
    service = GamificationService()

    first = service.award(1, "risk_alert", risk_level="critical", event_key="chat:incident-1")
    second = service.award(1, "risk_alert", risk_level="critical", event_key="chat:incident-1")

    assert first["points_gained"] == 5
    assert second["points_gained"] == 0
    assert second["total_points"] == first["total_points"]
    assert service.profile(1)["high_risk_blocks"] == 0


def test_safety_action_confirmation_rewards_once_and_counts_block() -> None:
    service = GamificationService()

    first = service.award(2, "safety_action_confirmed", risk_level="high", event_key="chat:incident-2")
    second = service.award(2, "safety_action_confirmed", risk_level="high", event_key="chat:incident-2")

    profile = service.profile(2)
    assert first["points_gained"] == 20
    assert second["points_gained"] == 0
    assert profile["high_risk_blocks"] == 1
    assert "冷静止损王" not in profile["badges"]


def test_daily_chat_reward_has_small_daily_cap() -> None:
    service = GamificationService()

    gains = [
        service.award(3, "daily_chat", event_key=f"2026-06-18:{index}")["points_gained"]
        for index in range(5)
    ]

    assert gains == [1, 1, 1, 0, 0]
    assert service.profile(3)["points"] == 3
