from __future__ import annotations

from app.services.ai_risk_service import (
    AIRiskAssessment,
    merge_rule_and_ai_risk,
)


def test_ai_assessment_can_escalate_rule_score() -> None:
    merged = merge_rule_and_ai_risk(
        rule_score=25,
        rule_level="medium",
        ai_assessment=AIRiskAssessment(
            risk_level="critical",
            risk_score=82,
            confidence=0.86,
            fraud_stage="money_lost",
            reasons=["用户明确说钱已经被转走"],
            recommended_actions=["联系银行止付", "报警"],
        ),
    )

    assert merged.final_score == 82
    assert merged.final_level == "critical"
    assert merged.ai_score_delta == 57
    assert merged.matched_rule["rule"] == "ai_risk_assessment"


def test_ai_assessment_cannot_downgrade_high_rule_score() -> None:
    merged = merge_rule_and_ai_risk(
        rule_score=72,
        rule_level="critical",
        ai_assessment=AIRiskAssessment(
            risk_level="low",
            risk_score=5,
            confidence=0.9,
            fraud_stage="unclear",
            reasons=["模型认为风险较低"],
            recommended_actions=[],
        ),
    )

    assert merged.final_score == 72
    assert merged.final_level == "critical"
    assert merged.ai_score_delta == 0
    assert merged.decision == "rule_kept"


def test_low_confidence_ai_assessment_is_observational_only() -> None:
    merged = merge_rule_and_ai_risk(
        rule_score=20,
        rule_level="medium",
        ai_assessment=AIRiskAssessment(
            risk_level="critical",
            risk_score=90,
            confidence=0.2,
            fraud_stage="unclear",
            reasons=["不确定"],
            recommended_actions=[],
        ),
    )

    assert merged.final_score == 20
    assert merged.final_level == "medium"
    assert merged.decision == "ai_low_confidence"
