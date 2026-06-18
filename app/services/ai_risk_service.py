from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from app.services.llm_client import (
    chat_payload,
    env_int,
    first_choice_text,
    load_llm_config,
    post_chat_completion,
)
from app.services.sanitizer import sanitize_text


_LEVEL_FLOORS = {"low": 0, "medium": 20, "high": 40, "critical": 70}
_VALID_LEVELS = set(_LEVEL_FLOORS)


@dataclass(frozen=True)
class AIRiskAssessment:
    risk_level: str
    risk_score: int
    confidence: float
    fraud_stage: str
    reasons: list[str]
    recommended_actions: list[str]
    raw: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "confidence": round(self.confidence, 3),
            "fraud_stage": self.fraud_stage,
            "reasons": self.reasons,
            "recommended_actions": self.recommended_actions,
        }


@dataclass(frozen=True)
class MergedRiskAssessment:
    final_score: int
    final_level: str
    ai_score_delta: int
    decision: str
    ai_assessment: AIRiskAssessment | None
    matched_rule: dict[str, Any] | None

    def breakdown(self) -> dict[str, Any]:
        if not self.ai_assessment:
            return {"enabled": False}
        return {
            "enabled": True,
            "decision": self.decision,
            "score_delta": self.ai_score_delta,
            **self.ai_assessment.as_dict(),
        }


class AIRiskAssessor:
    """LLM-assisted risk reviewer.

    The model is advisory only. `merge_rule_and_ai_risk` keeps deterministic
    rules as the safety floor and only lets confident AI findings escalate.
    """

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.enabled = (
            enabled
            if enabled is not None
            else os.getenv("AI_RISK_ASSESSMENT_ENABLED", "0").lower() in {"1", "true", "yes"}
        )
        self.config = load_llm_config(
            model=model,
            timeout=timeout,
            timeout_env="AI_RISK_TIMEOUT",
        )

    def assess(
        self,
        *,
        message: str,
        history: list[dict[str, str]],
        rule_context: dict[str, Any],
    ) -> AIRiskAssessment | None:
        if not self.enabled:
            return None

        history_lines = []
        for item in history[-5:]:
            user_message = sanitize_text(str(item.get("message", "")))
            risk_level = str(item.get("risk_level", ""))
            risk_score = str(item.get("risk_score", ""))
            if user_message:
                history_lines.append(f"- {user_message} | previous={risk_level}/{risk_score}")

        prompt = {
            "current_user_message": sanitize_text(message),
            "recent_history": history_lines,
            "rule_engine_context": rule_context,
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "你是反诈风险复核员，只输出 JSON。"
                    "任务是判断当前用户是否处于诈骗风险中，并给出0-100风险分。"
                    "如果用户说验证码已被看到、账户被接管、钱已转走、正在屏幕共享或远程控制，通常是high或critical。"
                    "如果用户已经报警、银行冻结、断网、卸载远程软件或改密，说明当前实时危险下降，但诈骗可能性和残留风险仍需记录。"
                    "不要安抚，不要写长文，不要给Markdown。"
                    'JSON字段: risk_level(low|medium|high|critical), risk_score(0-100), '
                    'confidence(0-1), fraud_stage, reasons(array), recommended_actions(array)。'
                ),
            },
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ]
        payload = chat_payload(
            config=self.config,
            messages=messages,
            temperature=0.1,
            max_tokens=env_int("AI_RISK_MAX_TOKENS", 240),
        )

        try:
            data = post_chat_completion(self.config, payload)
            return parse_ai_risk_assessment(first_choice_text(data))
        except Exception:
            return None


def parse_ai_risk_assessment(text: str) -> AIRiskAssessment | None:
    if not text.strip():
        return None
    start = text.find("{")
    end = text.rfind("}") + 1
    if start < 0 or end <= start:
        return None
    try:
        raw = json.loads(text[start:end])
    except json.JSONDecodeError:
        return None

    level = _normalize_level(raw.get("risk_level"))
    confidence = _clamp_float(raw.get("confidence"), 0.0, 1.0)
    score = _clamp_int(raw.get("risk_score"), 0, 100)
    if score < _LEVEL_FLOORS[level]:
        score = _LEVEL_FLOORS[level]

    return AIRiskAssessment(
        risk_level=level,
        risk_score=score,
        confidence=confidence,
        fraud_stage=str(raw.get("fraud_stage") or "unclear")[:80],
        reasons=_string_list(raw.get("reasons"), limit=4),
        recommended_actions=_string_list(raw.get("recommended_actions"), limit=4),
        raw=text,
    )


def merge_rule_and_ai_risk(
    *,
    rule_score: int,
    rule_level: str,
    ai_assessment: AIRiskAssessment | None,
    min_confidence: float = 0.55,
) -> MergedRiskAssessment:
    normalized_rule_level = _normalize_level(rule_level)
    if not ai_assessment:
        return MergedRiskAssessment(
            final_score=rule_score,
            final_level=normalized_rule_level,
            ai_score_delta=0,
            decision="no_ai_assessment",
            ai_assessment=None,
            matched_rule=None,
        )

    if ai_assessment.confidence < min_confidence:
        return MergedRiskAssessment(
            final_score=rule_score,
            final_level=normalized_rule_level,
            ai_score_delta=0,
            decision="ai_low_confidence",
            ai_assessment=ai_assessment,
            matched_rule=None,
        )

    if ai_assessment.risk_score <= rule_score:
        return MergedRiskAssessment(
            final_score=rule_score,
            final_level=normalized_rule_level,
            ai_score_delta=0,
            decision="rule_kept",
            ai_assessment=ai_assessment,
            matched_rule=None,
        )

    delta = ai_assessment.risk_score - rule_score
    return MergedRiskAssessment(
        final_score=ai_assessment.risk_score,
        final_level=_score_to_level(ai_assessment.risk_score),
        ai_score_delta=delta,
        decision="ai_escalated",
        ai_assessment=ai_assessment,
        matched_rule={
            "rule": "ai_risk_assessment",
            "evidence": ai_assessment.reasons,
            "weight": delta,
            "reason": "AI复核认为当前风险高于规则引擎初判",
            "rule_version": "1.0",
            "ruleset_version": "ai-review-1.0",
            "rationale": "仅用于补强召回和语义判断；不会降低规则引擎给出的高风险结论。",
        },
    )


def _score_to_level(score: int) -> str:
    if score >= 70:
        return "critical"
    if score >= 40:
        return "high"
    if score >= 20:
        return "medium"
    return "low"


def _normalize_level(value: Any) -> str:
    level = str(value or "low").strip().lower()
    return level if level in _VALID_LEVELS else "low"


def _clamp_int(value: Any, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return minimum
    return max(minimum, min(maximum, number))


def _clamp_float(value: Any, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return minimum
    return max(minimum, min(maximum, number))


def _string_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip()[:120] for item in value[:limit] if str(item).strip()]
