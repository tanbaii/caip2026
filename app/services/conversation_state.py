"""Lightweight multi-turn conversation state for anti-fraud dialogue.

In-memory only — no database persistence.  Each user_id maintains
a ConversationState that tracks extracted facts, session stage,
and pending follow-up questions across turns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ── Fact extraction patterns ──

_FACT_PATTERNS: dict[str, list[str]] = {
    "has_transfer_request": [
        "转账", "付款", "保证金", "认证费", "手续费", "解冻", "垫付", "缴费",
        "先交", "先付", "汇款", "打款", "转到", "转钱",
    ],
    "has_verification_code_request": [
        "验证码", "短信码", "动态码", "校验码", "安全码",
    ],
    "has_url": [],  # detected by URL regex separately
    "has_remote_control": [
        "屏幕共享", "远程控制", "下载会议", "下载软件", "共享屏幕", "向日葵", "teamviewer",
    ],
    "has_secrecy_pressure": [
        "别告诉别人", "保密", "不准报警", "不能告诉", "不要跟人说", "悄悄的",
    ],
    "has_time_pressure": [
        "马上", "立刻", "限时", "24小时", "立即", "赶紧", "尽快", "过期", "即将",
    ],
    "already_paid": [
        "已经转", "已经付", "刚转了", "已转", "已付", "转过去了", "付过了", "转了",
    ],
    "mentions_authority": [
        "公检法", "警察", "安全账户", "公安局", "法院", "检察院", "涉嫌", "通缉", "保密办案",
    ],
    "mentions_investment": [
        "投资", "带单", "高收益", "内幕", "稳赚", "荐股", "量化", "跟单",
    ],
    "mentions_reward_or_subsidy": [
        "奖学金", "助学金", "中奖", "补贴", "退税", "返利", "补贴", "补录",
    ],
    "mentions_ai_deepfake": [
        "ai换脸", "视频通话借钱", "克隆声音", "deepfake", "数字人", "ai语音",
        "换脸", "声音变了", "视频借钱",
    ],
}

_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)

# ── Follow-up question templates ──

# Key: (fact still missing, context)  Value: question text
_FOLLOW_UPS: list[tuple[set[str], str]] = [
    ({"has_transfer_request"}, "对方是否要求你先交手续费、认证费或保证金？"),
    ({"has_verification_code_request"}, "是否让你填写银行卡、验证码或点击陌生链接？"),
    ({"has_transfer_request"}, "对方是否要求你转账到个人账户或陌生账户？"),
    ({"has_verification_code_request"}, "是否有人向你索要短信验证码？"),
    ({"has_url"}, "对方是否发送了陌生链接让你点击？"),
    ({"has_remote_control"}, "是否要求你下载会议软件或开启屏幕共享？"),
    ({"has_secrecy_pressure"}, "对方是否要求你保密，不告诉家人或朋友？"),
    ({"has_time_pressure"}, "对方是否在催促你限时操作？"),
    ({"already_paid"}, "你是否已经向对方转过钱了？"),
]

# ── Risk escalation rules based on multi-turn facts ──

_ESCALATION_RULES: list[tuple[set[str], int, str, str]] = [
    # (required_facts, bonus_score, rule_name, reason)
    ({"has_transfer_request", "has_verification_code_request"}, 20, "conv_transfer_and_code", "多轮对话确认：对方既要求转账又索要验证码，高度可疑"),
    ({"mentions_authority", "has_transfer_request"}, 25, "conv_authority_transfer", "多轮对话确认：冒充公检法并要求转账，极高危"),
    ({"has_url", "has_verification_code_request"}, 18, "conv_url_and_code", "多轮对话确认：发送链接并索要验证码，疑似钓鱼"),
    ({"mentions_ai_deepfake", "has_transfer_request"}, 22, "conv_ai_fake_transfer", "多轮对话确认：AI伪造身份并要求转账"),
    ({"already_paid"}, 30, "conv_already_paid", "多轮对话确认：用户已转账，建议立即止付"),
    ({"has_secrecy_pressure", "has_transfer_request"}, 15, "conv_secrecy_transfer", "多轮对话确认：保密施压+转账要求，典型诈骗组合"),
    ({"mentions_reward_or_subsidy", "has_transfer_request"}, 16, "conv_reward_transfer", "多轮对话确认：以奖金/补贴为由要求缴费"),
    ({"mentions_reward_or_subsidy", "has_verification_code_request"}, 18, "conv_reward_code", "多轮对话确认：以奖金/补贴为由索要验证码"),
    ({"has_remote_control", "has_transfer_request"}, 20, "conv_remote_transfer", "多轮对话确认：要求屏幕共享+转账，极高危"),
]


@dataclass
class ConversationState:
    """Per-user conversation state."""

    session_stage: str = "collecting"
    suspected_scam_type: str = ""
    known_facts: dict[str, bool] = field(default_factory=dict)
    pending_questions: list[str] = field(default_factory=list)
    turn_count: int = 0
    last_risk_level: str = "low"
    last_intent: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "session_stage": self.session_stage,
            "suspected_scam_type": self.suspected_scam_type,
            "known_facts": {k: v for k, v in self.known_facts.items() if v},
            "pending_questions": self.pending_questions,
            "turn_count": self.turn_count,
            "last_risk_level": self.last_risk_level,
            "last_intent": self.last_intent,
        }


class ConversationStateManager:
    """Manages in-memory conversation states for all users."""

    def __init__(self) -> None:
        self._states: dict[int, ConversationState] = {}

    def get_state(self, user_id: int) -> ConversationState:
        if user_id not in self._states:
            self._states[user_id] = ConversationState()
        return self._states[user_id]

    def reset(self, user_id: int) -> None:
        self._states.pop(user_id, None)

    def update_and_get(
        self,
        user_id: int,
        message: str,
        risk_level: str,
        intent: str,
        matched_scams: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Update state after a turn, return state as dict."""
        state = self.get_state(user_id)
        state.turn_count += 1
        state.last_risk_level = risk_level
        state.last_intent = intent

        # Extract facts from this message
        _extract_facts(message, state.known_facts)

        # Update suspected scam type from matched scams
        if matched_scams and not state.suspected_scam_type:
            state.suspected_scam_type = matched_scams[0].get("type", "")

        # Determine stage
        state.session_stage = _determine_stage(state, risk_level)

        # Compute follow-up questions
        state.pending_questions = _compute_follow_ups(state)

        return state.as_dict()

    def recompute_stage(self, user_id: int, risk_level: str) -> dict[str, Any]:
        """Re-evaluate stage and pending_questions after final risk_level is known.

        Call this after compute_conversation_bonus has potentially changed the
        risk level, so that session_stage and pending_questions are consistent
        with the final risk score.
        """
        state = self.get_state(user_id)
        state.last_risk_level = risk_level
        state.session_stage = _determine_stage(state, risk_level)
        state.pending_questions = _compute_follow_ups(state)
        return state.as_dict()

    def compute_conversation_bonus(self, user_id: int) -> tuple[int, list[dict[str, Any]], list[str]]:
        """Return (bonus_score, extra_matched_rules, extra_reasons) from multi-turn facts."""
        state = self.get_state(user_id)
        if state.turn_count <= 1:
            return 0, [], []

        bonus = 0
        extra_rules: list[dict[str, Any]] = []
        extra_reasons: list[str] = []

        for required_facts, score, rule_name, reason in _ESCALATION_RULES:
            if required_facts.issubset(k for k, v in state.known_facts.items() if v):
                bonus += score
                extra_rules.append({
                    "rule": rule_name,
                    "evidence": sorted(required_facts),
                    "weight": score,
                    "reason": reason,
                })
                extra_reasons.append(reason)

        return bonus, extra_rules, extra_reasons


def _extract_facts(message: str, known_facts: dict[str, bool]) -> None:
    """Extract facts from a message and merge into known_facts."""
    text = message.lower()

    for fact_key, triggers in _FACT_PATTERNS.items():
        if known_facts.get(fact_key):
            continue  # already known
        if any(t in text for t in triggers):
            known_facts[fact_key] = True

    # URL detection
    if not known_facts.get("has_url") and _URL_RE.search(message):
        known_facts["has_url"] = True


def _determine_stage(state: ConversationState, risk_level: str) -> str:
    """Determine session stage based on accumulated facts and risk level."""
    facts = state.known_facts

    # If already paid or critical risk -> warning (stop questioning, focus on rescue)
    if facts.get("already_paid") or risk_level == "critical":
        return "warning"

    # High risk with enough facts -> warning
    if risk_level == "high" and state.turn_count >= 2:
        return "warning"

    # High risk from first turn or many risk signals -> warning
    if risk_level == "high":
        signal_count = sum(1 for v in facts.values() if v)
        if signal_count >= 3:
            return "warning"
        return "assessing"

    # Medium risk or multiple turns with some facts -> assessing
    if risk_level == "medium" or state.turn_count >= 2:
        return "assessing"

    return "collecting"


def _compute_follow_ups(state: ConversationState) -> list[str]:
    """Generate up to 2 follow-up questions based on missing facts."""
    if state.session_stage == "warning":
        return []  # no more questions — time to act

    questions: list[str] = []
    seen: set[str] = set()

    for required_missing, question in _FOLLOW_UPS:
        if len(questions) >= 2:
            break
        if question in seen:
            continue
        # Ask if ANY of the required facts are still unknown
        if any(not state.known_facts.get(f) for f in required_missing):
            questions.append(question)
            seen.add(question)

    return questions
