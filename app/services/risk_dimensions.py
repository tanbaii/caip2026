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
    else:
        facts = dict(facts)
    facts["safety_evidence_turns"] = int(conv_data.get("safety_evidence_turns", 0) or 0)

    scam_likelihood_score = _scam_likelihood_score(_clamp(risk_score), facts)
    current_danger_score = _current_danger_score(scam_likelihood_score, facts)
    loss_impact_score = _loss_impact_score(facts)
    residual_risk_score = _residual_risk_score(scam_likelihood_score, facts)
    privacy_risk_score = _privacy_risk_score(facts)

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
        "privacy_risk": {
            "score": privacy_risk_score,
            "level": _score_to_level(privacy_risk_score),
            "meaning": "手机号、身份证、地址等个人信息暴露或被索要的风险",
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
    if facts.get("test_mode") or facts.get("user_clarified_no_action"):
        return _apply_current_danger_caps(5, facts)
    if facts.get("quoted_advice"):
        return _apply_current_danger_caps(10, facts)
    if _has_closure_action(facts):
        if facts.get("already_paid") or facts.get("verification_code_exposed"):
            return _apply_current_danger_caps(30, facts)
        return _apply_current_danger_caps(18, facts)
    if facts.get("already_paid"):
        return 70
    if facts.get("verification_code_exposed"):
        return 65
    if facts.get("has_remote_control"):
        if facts.get("remote_control_removed") and not _has_account_or_funds_emergency(facts):
            return _apply_current_danger_caps(30, facts)
        return max(base_score, 60)
    if facts.get("pii_disclosed_to_third_party") or facts.get("third_party_pii_request"):
        return _apply_current_danger_caps(25, facts)
    if facts.get("has_remote_control_request"):
        if facts.get("has_verification_code_request"):
            return 45
        return min(max(base_score, 25), 35)
    if facts.get("has_transfer_request") or facts.get("has_verification_code_request"):
        return min(max(base_score, 25), 45 if facts.get("has_verification_code_request") else 35)
    if facts.get("self_pii_provide") or facts.get("self_pii_recall") or facts.get("privacy_risk"):
        return 10
    return _apply_current_danger_caps(base_score, facts)


def _loss_impact_score(facts: dict[str, Any]) -> int:
    if facts.get("already_paid"):
        return 80
    if facts.get("verification_code_exposed"):
        return 55
    return 0


def _residual_risk_score(base_score: int, facts: dict[str, Any]) -> int:
    if facts.get("test_mode") or facts.get("user_clarified_no_action"):
        return 5
    if facts.get("quoted_advice"):
        return 20
    if _has_closure_action(facts):
        if facts.get("already_paid"):
            return 65
        if facts.get("verification_code_exposed"):
            return 50
        return 30 if _safe_evidence_count(facts) >= 4 else (35 if base_score >= 40 else 20)
    if facts.get("already_paid") or facts.get("verification_code_exposed"):
        return 70
    if facts.get("pii_disclosed_to_third_party") or facts.get("third_party_pii_request"):
        return 25
    return min(base_score, 40)


def _scam_likelihood_score(base_score: int, facts: dict[str, Any]) -> int:
    if facts.get("already_paid") or facts.get("verification_code_exposed"):
        return max(base_score, 70)
    if facts.get("has_remote_control_request") and facts.get("has_verification_code_request"):
        return max(base_score, 65)
    if facts.get("has_remote_control_request"):
        return max(base_score, 55)
    if facts.get("has_transfer_request") or facts.get("has_verification_code_request"):
        return max(base_score, 45)
    if facts.get("third_party_pii_request") or facts.get("pii_disclosed_to_third_party"):
        return max(base_score, 20)
    return base_score


def _privacy_risk_score(facts: dict[str, Any]) -> int:
    if facts.get("verification_code_exposed"):
        return 60
    if facts.get("pii_disclosed_to_third_party"):
        return 45
    if facts.get("third_party_pii_request"):
        return 35
    if facts.get("self_pii_provide") or facts.get("self_pii_recall") or facts.get("privacy_risk"):
        return 25
    return 0


def _apply_current_danger_caps(score: int, facts: dict[str, Any]) -> int:
    if _has_account_or_funds_emergency(facts):
        return score
    if facts.get("safety_evidence_turns", 0) >= 2:
        score = min(score, 20)
    if _safe_evidence_count(facts) >= 4:
        score = min(score, 25)
    if (
        facts.get("remote_control_removed")
        and (facts.get("no_transfer") or facts.get("no_abnormal_charge"))
        and not facts.get("has_remote_control")
    ):
        score = min(score, 35)
    if facts.get("remote_control_removed") and not _has_account_or_funds_emergency(facts):
        score = min(score, 35)
    return score


def _has_account_or_funds_emergency(facts: dict[str, Any]) -> bool:
    return bool(facts.get("already_paid") or facts.get("verification_code_exposed"))


def _safe_evidence_count(facts: dict[str, Any]) -> int:
    return sum(
        1
        for key in {
            "remote_control_removed",
            "no_transfer",
            "no_verification_code",
            "no_abnormal_charge",
            "blocked_contact",
            "evidence_saved",
            "trusted_person_informed",
            "password_changed",
            "device_checked_clean",
            "devices_kicked",
        }
        if facts.get(key)
    )


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
            "phone_reset_completed",
            "blocked_contact",
            "evidence_saved",
            "trusted_person_informed",
            "no_abnormal_charge",
            "device_checked_clean",
            "no_transfer",
            "no_verification_code",
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
