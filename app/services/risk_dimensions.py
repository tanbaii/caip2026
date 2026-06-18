from __future__ import annotations

from typing import Any


def build_risk_dimensions(
    *,
    risk_score: int,
    risk_level: str,
    conv_data: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    facts = conv_data.get("known_facts", {})
    if not isinstance(facts, dict):
        facts = {}

    scam_likelihood_score = _clamp(risk_score)
    current_danger_score = _current_danger_score(scam_likelihood_score, facts)
    loss_impact_score = _loss_impact_score(facts)
    residual_risk_score = _residual_risk_score(scam_likelihood_score, facts)

    return {
        "scam_likelihood": {
            "score": scam_likelihood_score,
            "level": _score_to_level(scam_likelihood_score),
            "meaning": "这件事像诈骗的程度",
        },
        "current_danger": {
            "score": current_danger_score,
            "level": _score_to_level(current_danger_score),
            "meaning": "用户此刻仍被操控或继续损失的危险程度",
        },
        "loss_impact": {
            "score": loss_impact_score,
            "level": _score_to_level(loss_impact_score),
            "meaning": "资金、账号或隐私已经造成损失的程度",
        },
        "residual_risk": {
            "score": residual_risk_score,
            "level": _score_to_level(residual_risk_score),
            "meaning": "完成阻断后仍需要收尾检查的风险",
        },
    }


def overall_level_from_dimensions(dimensions: dict[str, dict[str, Any]]) -> str:
    current = str(dimensions.get("current_danger", {}).get("level", "low"))
    loss = str(dimensions.get("loss_impact", {}).get("level", "low"))
    if current in {"critical", "high"}:
        return current
    if loss == "critical":
        return "high"
    return current if current in {"medium", "low"} else "low"


def _current_danger_score(base_score: int, facts: dict[str, Any]) -> int:
    if _has_closure_action(facts):
        if facts.get("already_paid") or facts.get("verification_code_exposed"):
            return 30
        return 15
    if facts.get("already_paid"):
        return 70
    if facts.get("verification_code_exposed"):
        return 65
    if facts.get("has_remote_control"):
        return max(base_score, 60)
    return base_score


def _loss_impact_score(facts: dict[str, Any]) -> int:
    if facts.get("already_paid"):
        return 80
    if facts.get("verification_code_exposed"):
        return 55
    return 0


def _residual_risk_score(base_score: int, facts: dict[str, Any]) -> int:
    if _has_closure_action(facts):
        if facts.get("already_paid"):
            return 65
        if facts.get("verification_code_exposed"):
            return 50
        return 35 if base_score >= 40 else 20
    if facts.get("already_paid") or facts.get("verification_code_exposed"):
        return 70
    return min(base_score, 40)


def _has_closure_action(facts: dict[str, Any]) -> bool:
    return any(
        facts.get(key)
        for key in {
            "reported_to_police",
            "bank_frozen",
            "network_disconnected",
            "password_changed",
            "devices_kicked",
            "remote_control_removed",
            "safety_action_taken",
        }
    )


def _score_to_level(score: int) -> str:
    if score >= 70:
        return "critical"
    if score >= 40:
        return "high"
    if score >= 20:
        return "medium"
    return "low"


def _clamp(score: int) -> int:
    return max(0, min(100, int(score)))
