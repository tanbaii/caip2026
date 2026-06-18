"""Lightweight multi-turn conversation state for anti-fraud dialogue.

In-memory only -- no database persistence.  Each user_id maintains
a ConversationState that tracks extracted facts, session stage,
and pending follow-up questions across turns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.services.text_semantics import find_effective_terms

# -- Fact extraction patterns --

_FACT_PATTERNS: dict[str, list[str]] = {
    "has_transfer_request": [
        "转账", "付款", "保证金", "认证费", "手续费", "解冻", "垫付", "缴费",
        "先交", "先付", "汇款", "打款", "转到", "转钱",
    ],
    "has_verification_code_request": [
        "验证码", "短信码", "动态码", "校验码", "安全码",
    ],
    "has_url": [],
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
        "钱被转走", "被转走了", "扣款了", "账户少了钱", "钱没了",
    ],
    "verification_code_exposed": [
        "看到验证码", "看见验证码", "验证码被看到", "验证码被看见", "验证码泄露", "知道验证码",
        "验证码发给", "验证码告诉", "验证码给了", "他看到验证码", "对方看到验证码",
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
    "mentions_scholarship": [
        "奖学金", "助学金", "教育资助", "学费返还", "助学贷款", "贫困补助",
        "学校补助", "资助中心", "学信档案", "认证费",
    ],
    "mentions_flight": [
        "航班取消", "机票改签", "延误理赔", "退票赔偿", "航司客服",
        "改签链接", "延误险", "行程变动", "机票退款",
    ],
    "mentions_negation_semantics": [
        "不是诈骗", "不是骗子", "不骗人", "正规平台", "你放心", "绝对安全", "不会骗你",
    ],
    "reported_to_police": [
        "已经报警", "报过警", "打了110", "打了96110", "联系了96110", "警察说", "派出所",
    ],
    "bank_frozen": [
        "银行冻结", "已经冻结", "冻结账户", "冻结银行卡", "申请止付", "已经止付", "支付平台冻结",
    ],
    "network_disconnected": [
        "已经断网", "断开网络", "关了网络", "拔网线", "开飞行模式",
    ],
    "password_changed": [
        "改了密码", "修改密码", "重置密码", "换了密码",
    ],
    "devices_kicked": [
        "踢出设备", "退出所有设备", "陌生设备退出", "下线其他设备",
    ],
    "remote_control_removed": [
        "卸载了会议软件", "卸载会议软件", "删了会议软件", "卸载远程", "退出屏幕共享",
        "停止屏幕共享", "关掉屏幕共享", "结束屏幕共享",
    ],
}

_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_SAFETY_ACTION_ACK_RE = re.compile(
    r"(已经|已|刚刚|现在|我).{0,16}"
    r"(停止|停了|不转了|退出|关掉|关闭|取消|卸载|删了|挂断|拉黑|报警|96110|110|联系银行|止付|冻结)"
)
_NO_TRANSFER_ACK_RE = re.compile(
    r"((没|没有|未|还没).{0,4}(转账|转钱|付款|付钱)|不转了|不会转)"
)

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
    ({"mentions_scholarship"}, "这个奖学金或助学金通知是通过学校官方渠道发送的吗？"),
    ({"mentions_flight"}, "你是否已通过航空公司官方客服核实过航班状态？"),
    ({"mentions_negation_semantics"}, "对方是否在主动强调'不是诈骗'或'绝对安全'？"),
]

_ESCALATION_RULES: list[tuple[set[str], int, str, str]] = [
    ({"has_transfer_request", "has_verification_code_request"}, 20, "conv_transfer_and_code", "多轮对话确认：对方既要求转账又索要验证码，高度可疑"),
    ({"mentions_authority", "has_transfer_request"}, 25, "conv_authority_transfer", "多轮对话确认：冒充公检法并要求转账，极高危"),
    ({"has_url", "has_verification_code_request"}, 18, "conv_url_and_code", "多轮对话确认：发送链接并索要验证码，疑似钓鱼"),
    ({"mentions_ai_deepfake", "has_transfer_request"}, 22, "conv_ai_fake_transfer", "多轮对话确认：AI伪造身份并要求转账"),
    ({"already_paid"}, 30, "conv_already_paid", "多轮对话确认：用户已转账，建议立即止付"),
    ({"has_secrecy_pressure", "has_transfer_request"}, 15, "conv_secrecy_transfer", "多轮对话确认：保密施压+转账要求，典型诈骗组合"),
    ({"mentions_reward_or_subsidy", "has_transfer_request"}, 16, "conv_reward_transfer", "多轮对话确认：以奖金/补贴为由要求缴费"),
    ({"mentions_reward_or_subsidy", "has_verification_code_request"}, 18, "conv_reward_code", "多轮对话确认：以奖金/补贴为由索要验证码"),
    ({"has_remote_control", "has_transfer_request"}, 20, "conv_remote_transfer", "多轮对话确认：要求屏幕共享+转账，极高危"),
    ({"mentions_scholarship", "has_transfer_request"}, 20, "conv_scholarship_transfer", "多轮对话确认：冒充校方以奖学金/助学金为由收费"),
    ({"mentions_scholarship", "has_verification_code_request"}, 22, "conv_scholarship_code", "多轮对话确认：以奖学金/助学金为由索要银行卡和验证码"),
    ({"mentions_flight", "has_transfer_request"}, 18, "conv_flight_transfer", "多轮对话确认：冒充航司以改签/理赔为由诱导转账"),
    ({"mentions_flight", "has_verification_code_request"}, 20, "conv_flight_code", "多轮对话确认：以航班改签为由索要验证码"),
    ({"mentions_negation_semantics", "has_transfer_request"}, 14, "conv_negation_transfer", "多轮对话确认：对方主动声称非诈骗+要求转账"),
    ({"mentions_negation_semantics", "has_verification_code_request"}, 16, "conv_negation_code", "多轮对话确认：对方强调安全+索要验证码"),
]


@dataclass
class ConversationState:
    """Per-user conversation state."""
    session_stage: str = "collecting"
    suspected_scam_type: str = ""
    known_facts: dict[str, bool] = field(default_factory=dict)
    pending_questions: list[str] = field(default_factory=list)
    triggered_conversation_rules: set[str] = field(default_factory=set)
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

    def update_and_get(self, user_id, message, risk_level, intent, matched_scams):
        state = self.get_state(user_id)
        current_scam_type = _top_scam_type(matched_scams)
        if _is_new_scam_topic(state, current_scam_type):
            state = ConversationState()
            self._states[user_id] = state
        state.turn_count += 1
        state.last_risk_level = risk_level
        state.last_intent = intent
        _extract_facts(
            message,
            state.known_facts,
            allow_no_transfer_ack=state.turn_count > 1,
        )
        if current_scam_type and not state.suspected_scam_type:
            state.suspected_scam_type = current_scam_type
        state.session_stage = _determine_stage(state, risk_level)
        state.pending_questions = _compute_follow_ups(state)
        return state.as_dict()

    def recompute_stage(self, user_id, risk_level):
        state = self.get_state(user_id)
        state.last_risk_level = risk_level
        state.session_stage = _determine_stage(state, risk_level)
        state.pending_questions = _compute_follow_ups(state)
        return state.as_dict()

    def compute_conversation_bonus(self, user_id):
        state = self.get_state(user_id)
        if state.turn_count <= 1:
            return 0, [], []
        if state.known_facts.get("safety_action_taken"):
            return 0, [], []
        bonus = 0
        extra_rules = []
        extra_reasons = []
        for required_facts, score, rule_name, reason in _ESCALATION_RULES:
            if rule_name in state.triggered_conversation_rules:
                continue
            if required_facts.issubset(k for k, v in state.known_facts.items() if v):
                bonus += score
                state.triggered_conversation_rules.add(rule_name)
                extra_rules.append({
                    "rule": rule_name,
                    "evidence": sorted(required_facts),
                    "weight": score,
                    "reason": reason,
                    "rule_version": "1.0",
                    "ruleset_version": "conversation-1.0",
                    "rationale": "基于跨轮已确认事实组合进行风险升级",
                })
                extra_reasons.append(reason)
        return bonus, extra_rules, extra_reasons


def _extract_facts(message, known_facts, allow_no_transfer_ack: bool = False):
    text = message.lower()
    if _SAFETY_ACTION_ACK_RE.search(text) or (
        allow_no_transfer_ack and _NO_TRANSFER_ACK_RE.search(text)
    ):
        known_facts["safety_action_taken"] = True
    for fact_key, triggers in _FACT_PATTERNS.items():
        if known_facts.get(fact_key):
            continue
        hits = find_effective_terms(
            text,
            triggers,
            negation_exempt=fact_key == "mentions_negation_semantics",
        )
        if hits:
            known_facts[fact_key] = True
    if not known_facts.get("has_url") and _URL_RE.search(message):
        known_facts["has_url"] = True


def _top_scam_type(matched_scams):
    if not matched_scams:
        return ""
    return str(matched_scams[0].get("type") or "")


def _is_new_scam_topic(state, current_scam_type):
    return bool(current_scam_type and state.suspected_scam_type and current_scam_type != state.suspected_scam_type)


def _determine_stage(state, risk_level):
    facts = state.known_facts
    if _has_closure_action(facts):
        return "closure_check"
    if facts.get("already_paid"):
        return "loss_recovery"
    if facts.get("verification_code_exposed"):
        return "account_recovery"
    if facts.get("safety_action_taken"):
        return "closure_check"
    if risk_level == "critical":
        return "active_blocking"
    if risk_level == "high" and state.turn_count >= 2:
        return "active_blocking"
    if risk_level == "high":
        signal_count = sum(1 for v in facts.values() if v)
        if signal_count >= 3:
            return "active_blocking"
        return "assessing"
    if risk_level == "medium" or state.turn_count >= 2:
        return "assessing"
    return "collecting"


def _compute_follow_ups(state):
    if state.session_stage in {"warning", "active_blocking", "account_recovery", "loss_recovery", "closure_check", "debriefing"}:
        return []
    questions = []
    seen = set()
    for required_missing, question in _FOLLOW_UPS:
        if len(questions) >= 2:
            break
        if question in seen:
            continue
        if any(not state.known_facts.get(f) for f in required_missing):
            questions.append(question)
            seen.add(question)
    return questions


def has_safety_action_taken(conv_data: dict[str, Any]) -> bool:
    facts = conv_data.get("known_facts", {})
    return bool(isinstance(facts, dict) and facts.get("safety_action_taken"))


def has_closure_action_taken(conv_data: dict[str, Any]) -> bool:
    facts = conv_data.get("known_facts", {})
    return bool(isinstance(facts, dict) and _has_closure_action(facts))


def _has_closure_action(facts: dict[str, bool]) -> bool:
    closure_keys = {
        "reported_to_police",
        "bank_frozen",
        "network_disconnected",
        "password_changed",
        "devices_kicked",
        "remote_control_removed",
    }
    return any(facts.get(key) for key in closure_keys)
