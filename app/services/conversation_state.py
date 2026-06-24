"""Evidence-aware multi-turn conversation state for anti-fraud dialogue.

The state machine separates three ideas that were previously conflated:

* a scammer asked the user to do something;
* the user actually executed the dangerous action;
* the user later clarified, quoted advice, or completed official handling.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Hashable

from app.services.text_semantics import find_effective_terms


_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")

_REQUEST_PATTERNS: dict[str, list[str]] = {
    "has_transfer_request": [
        "让我转账",
        "叫我转账",
        "要求转账",
        "催我转账",
        "催我赶紧转账",
        "赶紧转账",
        "让我付款",
        "要求付款",
        "让我缴费",
        "先交",
        "先付",
        "保证金",
        "认证费",
        "手续费",
        "解冻费",
        "垫付",
        "汇款",
        "打款",
        "转到",
        "转钱",
    ],
    "has_verification_code_request": [
        "要验证码",
        "还要验证码",
        "还要我的验证码",
        "要我的验证码",
        "问我要验证码",
        "对方问我要验证码",
        "索要验证码",
        "让我发验证码",
        "让我给验证码",
        "看验证码",
        "屏幕共享看验证码",
        "让我填验证码",
        "让我输入验证码",
        "短信码",
        "动态码",
        "校验码",
        "安全码",
    ],
    "has_remote_control_request": [
        "让我下载会议软件",
        "让我下载软件",
        "让我开屏幕共享",
        "让我开启屏幕共享",
        "让我共享屏幕",
        "对方让我下载会议软件",
        "开屏幕共享",
        "开启屏幕共享",
        "要求屏幕共享",
        "要求共享屏幕",
        "下载会议软件并开启屏幕共享",
        "远程指导",
        "远程控制",
        "向日葵",
        "teamviewer",
    ],
}

_SCAM_CONTEXT_PATTERNS: dict[str, list[str]] = {
    "mentions_authority": [
        "公检法",
        "警察",
        "安全账户",
        "公安局",
        "法院",
        "检察院",
        "涉嫌",
        "通缉",
        "保密办案",
    ],
    "mentions_investment": [
        "投资",
        "投资群",
        "老师",
        "带单",
        "高收益",
        "低风险",
        "内幕",
        "稳赚",
        "荐股",
        "量化",
        "跟单",
    ],
    "mentions_reward_or_subsidy": [
        "奖学金",
        "助学金",
        "中奖",
        "补贴",
        "退税",
        "返利",
        "补录",
    ],
    "mentions_ai_deepfake": [
        "ai换脸",
        "AI换脸",
        "视频通话借钱",
        "克隆声音",
        "deepfake",
        "数字人",
        "AI语音",
        "声音克隆",
    ],
    "mentions_scholarship": [
        "奖学金",
        "助学金",
        "教育资助",
        "学费返还",
        "助学贷款",
        "贫困补助",
        "学校补助",
        "资助中心",
        "学信档案",
        "认证费",
    ],
    "mentions_flight": [
        "航班取消",
        "机票改签",
        "延误理赔",
        "退票赔偿",
        "航司客服",
        "改签链接",
        "机票退款",
    ],
    "mentions_negation_semantics": [
        "不是诈骗",
        "不是骗子",
        "正规平台",
        "你放心",
        "绝对安全",
        "不会骗你",
    ],
    "has_secrecy_pressure": [
        "别告诉别人",
        "保密",
        "不准报警",
        "不能告诉",
        "不要跟人说",
        "悄悄的",
    ],
    "has_time_pressure": [
        "马上",
        "立刻",
        "限时",
        "24小时",
        "立即",
        "赶紧",
        "尽快",
        "过期",
        "即将",
    ],
}

_EXECUTED_PATTERNS: dict[str, list[str]] = {
    "has_remote_control": [
        "我已经下载会议软件",
        "已经下载会议软件",
        "我下载了会议软件",
        "下载了会议软件",
        "我已经开启屏幕共享",
        "已经开启屏幕共享",
        "我开了屏幕共享",
        "开了屏幕共享",
        "开过屏幕共享",
        "正在屏幕共享",
        "正在共享屏幕",
        "对方正在看我的屏幕",
        "已经远程控制",
        "被远程控制",
    ],
    "verification_code_exposed": [
        "看到验证码",
        "看见验证码",
        "验证码被看到",
        "验证码被看见",
        "验证码泄露",
        "知道验证码",
        "验证码发给",
        "验证码发给他",
        "把验证码发给他",
        "把验证码也发给他",
        "验证码告诉",
        "验证码给了",
        "对方看到了验证码",
        "验证码也被对方看到了",
        "他看到了验证码",
    ],
    "already_paid": [
        "已经转账",
        "已经转了",
        "我已经转了",
        "转账了",
        "给他转了",
        "已经付款",
        "刚转了",
        "已转",
        "已付",
        "转过去了",
        "付过了",
        "转了钱",
        "钱被转走",
        "被转走了",
        "扣款了",
        "账户少了钱",
        "钱没了",
    ],
}

_CLOSURE_PATTERNS: dict[str, list[str]] = {
    "reported_to_police": [
        "已经报警",
        "报警了",
        "报过警",
        "打了110",
        "打了96110",
        "联系了96110",
        "警察说",
        "派出所",
    ],
    "bank_frozen": [
        "银行冻结",
        "已经冻结",
        "冻结账户",
        "冻结银行卡",
        "申请止付",
        "已经止付",
        "支付平台冻结",
    ],
    "network_disconnected": [
        "已经断网",
        "断网",
        "断开网络",
        "关了网络",
        "拔网线",
        "开飞行模式",
    ],
    "password_changed": [
        "改了密码",
        "修改密码",
        "密码修改",
        "重置密码",
        "换了密码",
        "密码彻底重设",
    ],
    "devices_kicked": [
        "踢出设备",
        "退出所有设备",
        "陌生设备退出",
        "下线其他设备",
    ],
    "remote_control_removed": [
        "卸载掉软件",
        "卸载软件",
        "卸载了软件",
        "删掉软件",
        "卸载了会议软件",
        "卸载会议软件",
        "删了会议软件",
        "卸载远程",
        "退出屏幕共享",
        "停止屏幕共享",
        "关掉屏幕共享",
        "结束屏幕共享",
    ],
    "phone_reset_completed": [
        "手机彻底重置",
        "恢复出厂设置完成",
        "已经恢复出厂",
        "重置了手机",
    ],
    "blocked_contact": [
        "拉黑他",
        "拉黑对方",
        "已经拉黑",
        "把他拉黑",
        "屏蔽对方",
    ],
    "evidence_saved": [
        "证据保存",
        "保存证据",
        "证据也保存",
        "证据保存好",
        "存证",
        "截图保存",
        "聊天记录保存",
        "通话记录保存",
    ],
    "trusted_person_informed": [
        "告诉家人",
        "告知家人",
        "跟我妈妈说",
        "跟妈妈说",
        "跟爸爸说",
        "告诉朋友",
        "可信任的人",
    ],
    "no_abnormal_charge": [
        "没有扣款",
        "无扣款",
        "没有异常扣款",
        "没有资金异常",
        "账户没有异常",
        "没有异常",
    ],
    "device_checked_clean": [
        "后台很干净",
        "后台干净",
        "没有陌生应用",
        "无陌生应用",
        "没有异常后台",
        "手机无异常",
        "检查无异常",
    ],
    "no_transfer": [
        "没有转账",
        "没转账",
        "没转",
        "未转账",
        "没有付款",
        "没付款",
    ],
    "no_verification_code": [
        "没有验证码",
        "没给验证码",
        "没发验证码",
        "没输入验证码",
        "未输入验证码",
        "验证码没给",
    ],
}

_TEST_OR_JOKE_RE = re.compile(
    r"(骗你的|开玩笑|玩笑|测试|演示|模拟|我编的|随便试试|逗你|没有这回事)"
)
_NO_ACTION_RE = re.compile(
    r"(没有|没|未|还没|并未|没听|没有听).{0,8}"
    r"(下载|转账|付款|输入验证码|填验证码|开屏幕共享|开启屏幕共享|共享屏幕|听他说|照做|操作)"
)
_QUOTE_ADVICE_RE = re.compile(r"(第一[，,、].{0,80}第二[，,、]|^一是.{0,80}二是)")
_FIRST_PERSON_DONE_RE = re.compile(r"(我|已经|已|刚刚|刚才|现在).{0,12}(报警|冻结|止付|卸载|修改|重置|挂失|断网|关闭|退出)")

_FOLLOW_UPS: list[tuple[set[str], str]] = [
    ({"has_transfer_request"}, "对方是否要求你先交手续费、认证费或保证金？"),
    ({"has_verification_code_request"}, "对方是否让你填写银行卡、验证码或点击陌生链接？"),
    ({"has_remote_control_request"}, "你是否已经下载会议软件或开启过屏幕共享？"),
    ({"already_paid"}, "你是否已经向对方转过钱？"),
    ({"verification_code_exposed"}, "验证码、支付密码或银行卡信息是否已经被对方看到？"),
    ({"has_url"}, "对方是否发送了陌生链接让你点击？"),
]

_ESCALATION_RULES: list[tuple[set[str], int, str, str]] = [
    ({"has_transfer_request", "has_verification_code_request"}, 16, "conv_transfer_and_code", "多轮信息显示：对方既要求转账又索要验证码，诈骗可能性升高"),
    ({"mentions_authority", "has_transfer_request"}, 22, "conv_authority_transfer", "多轮信息显示：冒充公检法并要求转账，诈骗可能性极高"),
    ({"has_url", "has_verification_code_request"}, 16, "conv_url_and_code", "多轮信息显示：链接和验证码同时出现，疑似钓鱼"),
    ({"mentions_ai_deepfake", "has_transfer_request"}, 18, "conv_ai_fake_transfer", "多轮信息显示：AI伪造身份并要求转账"),
    ({"already_paid"}, 30, "conv_already_paid", "用户表述资金已经转出，进入止损阶段"),
    ({"has_secrecy_pressure", "has_transfer_request"}, 14, "conv_secrecy_transfer", "保密压力和转账要求同时出现"),
    ({"mentions_reward_or_subsidy", "has_transfer_request"}, 14, "conv_reward_transfer", "以奖金或补贴为由要求缴费"),
    ({"has_remote_control_request", "has_transfer_request"}, 16, "conv_remote_request_transfer", "屏幕共享/远程指导要求和转账要求同时出现"),
    ({"has_remote_control", "has_transfer_request"}, 22, "conv_remote_executed_transfer", "已执行远程控制或屏幕共享且存在转账要求"),
]

_CLEAR_ON_DENIAL = {
    "has_remote_control",
    "has_remote_control_request",
    "verification_code_exposed",
    "has_verification_code_request",
    "already_paid",
}


@dataclass
class ConversationState:
    session_stage: str = "collecting"
    suspected_scam_type: str = ""
    known_facts: dict[str, bool] = field(default_factory=dict)
    pending_questions: list[str] = field(default_factory=list)
    triggered_conversation_rules: set[str] = field(default_factory=set)
    turn_count: int = 0
    last_risk_level: str = "low"
    last_intent: str = ""
    safety_evidence_turns: int = 0
    pii_memory: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "session_stage": self.session_stage,
            "suspected_scam_type": self.suspected_scam_type,
            "known_facts": {key: value for key, value in self.known_facts.items() if value},
            "pending_questions": self.pending_questions,
            "turn_count": self.turn_count,
            "last_risk_level": self.last_risk_level,
            "last_intent": self.last_intent,
            "safety_evidence_turns": self.safety_evidence_turns,
            "pii_memory": dict(self.pii_memory),
        }


class ConversationStateManager:
    def __init__(self) -> None:
        self._states: dict[Hashable, ConversationState] = {}

    def get_state(self, user_id: Hashable) -> ConversationState:
        if user_id not in self._states:
            self._states[user_id] = ConversationState()
        return self._states[user_id]

    def reset(self, user_id: Hashable) -> None:
        self._states.pop(user_id, None)

    def update_and_get(
        self,
        user_id: Hashable,
        message: str,
        risk_level: str,
        intent: str,
        matched_scams: list[dict[str, Any]],
    ) -> dict[str, Any]:
        state = self.get_state(user_id)
        current_scam_type = _top_scam_type(matched_scams)
        if _is_new_scam_topic(state, current_scam_type):
            state = ConversationState()
            self._states[user_id] = state

        state.turn_count += 1
        state.last_risk_level = risk_level
        state.last_intent = intent

        message_mode = _message_mode(message)
        had_safety_evidence = _extract_facts(message, state, message_mode)
        if had_safety_evidence:
            state.safety_evidence_turns += 1

        if current_scam_type and not state.suspected_scam_type:
            state.suspected_scam_type = current_scam_type

        state.session_stage = _determine_stage(state, risk_level)
        state.pending_questions = _compute_follow_ups(state)
        return state.as_dict()

    def recompute_stage(self, user_id: Hashable, risk_level: str) -> dict[str, Any]:
        state = self.get_state(user_id)
        state.last_risk_level = risk_level
        state.session_stage = _determine_stage(state, risk_level)
        state.pending_questions = _compute_follow_ups(state)
        return state.as_dict()

    def compute_conversation_bonus(self, user_id: Hashable) -> tuple[int, list[dict[str, Any]], list[str]]:
        state = self.get_state(user_id)
        facts = state.known_facts
        if state.turn_count <= 1:
            return 0, [], []
        if any(facts.get(key) for key in ("test_mode", "user_clarified_no_action", "quoted_advice")):
            return 0, [], []
        if facts.get("safety_action_taken"):
            return 0, [], []

        active_facts = {key for key, value in facts.items() if value}
        bonus = 0
        extra_rules: list[dict[str, Any]] = []
        extra_reasons: list[str] = []
        for required_facts, score, rule_name, reason in _ESCALATION_RULES:
            if rule_name in state.triggered_conversation_rules:
                continue
            if required_facts.issubset(active_facts):
                bonus += score
                state.triggered_conversation_rules.add(rule_name)
                extra_rules.append(
                    {
                        "rule": rule_name,
                        "evidence": sorted(required_facts),
                        "weight": score,
                        "reason": reason,
                        "rule_version": "2.0",
                        "ruleset_version": "conversation-2.0",
                        "rationale": "基于跨轮信息组合升级诈骗可能性；不直接证明用户已经执行危险动作。",
                    }
                )
                extra_reasons.append(reason)
        return bonus, extra_rules, extra_reasons


def _message_mode(message: str) -> str:
    text = message.strip()
    if _TEST_OR_JOKE_RE.search(text):
        return "test_mode"
    if _QUOTE_ADVICE_RE.search(text) and not _FIRST_PERSON_DONE_RE.search(text):
        return "quoted_advice"
    if _NO_ACTION_RE.search(text):
        return "clarification"
    return "normal"


def _extract_facts(message: str, state: ConversationState, message_mode: str) -> bool:
    known_facts = state.known_facts
    text = message.lower()
    had_safety_evidence = False

    if message_mode == "test_mode":
        known_facts.clear()
        known_facts["test_mode"] = True
        if _NO_ACTION_RE.search(message):
            known_facts["user_clarified_no_action"] = True
        return False

    if message_mode == "quoted_advice":
        known_facts["quoted_advice"] = True
        return False

    if message_mode == "clarification":
        for key in _CLEAR_ON_DENIAL:
            known_facts.pop(key, None)
        known_facts["user_clarified_no_action"] = True
    else:
        known_facts.pop("quoted_advice", None)
        known_facts.pop("test_mode", None)
        if _has_executed_evidence(text):
            known_facts.pop("user_clarified_no_action", None)

    for fact_key, triggers in _REQUEST_PATTERNS.items():
        if known_facts.get(fact_key):
            continue
        hits = find_effective_terms(text, triggers)
        if hits:
            known_facts[fact_key] = True

    for fact_key, triggers in _SCAM_CONTEXT_PATTERNS.items():
        if known_facts.get(fact_key):
            continue
        hits = find_effective_terms(
            text,
            triggers,
            negation_exempt=fact_key == "mentions_negation_semantics",
        )
        if hits:
            known_facts[fact_key] = True

    for fact_key, triggers in _EXECUTED_PATTERNS.items():
        if known_facts.get(fact_key):
            continue
        hits = find_effective_terms(text, triggers)
        if hits:
            known_facts[fact_key] = True

    for fact_key, triggers in _CLOSURE_PATTERNS.items():
        if known_facts.get(fact_key):
            continue
        hits = find_effective_terms(text, triggers)
        if hits:
            known_facts[fact_key] = True
            had_safety_evidence = True

    _extract_pii_facts(message, state)

    if not known_facts.get("has_url") and _URL_RE.search(message):
        known_facts["has_url"] = True

    if _has_closure_action(known_facts):
        known_facts["safety_action_taken"] = True
    return had_safety_evidence


def _extract_pii_facts(message: str, state: ConversationState) -> None:
    facts = state.known_facts
    text = message.lower()
    phones = _PHONE_RE.findall(message)
    if phones:
        state.pii_memory["phone"] = _mask_phone(phones[-1])

    pii_terms = ("手机号", "手机号码", "电话", "身份证", "身份证号", "地址", "住址")
    has_pii_term = any(term in text for term in pii_terms)
    third_party_terms = ("对方", "陌生人", "客服", "骗子", "他", "她")
    request_terms = ("问我要", "问我的", "问我", "要我", "让我发", "让我提供", "要求我", "索要")

    if phones and re.search(r"(我.*(手机号|手机号码|电话).*(是|:|：)|我的手机号)", text):
        facts["self_pii_provide"] = True

    if has_pii_term and any(party in text for party in third_party_terms) and any(term in text for term in request_terms):
        facts["third_party_pii_request"] = True
    elif has_pii_term and any(term in text for term in ("我的手机号是多少", "我手机号是多少", "刚才的手机号")):
        facts["self_pii_recall"] = True

    if has_pii_term and re.search(r"我.{0,8}把.{0,8}(手机号|手机号码|电话|身份证|地址).{0,12}(发|给|告诉).{0,8}(他|她|对方|客服|陌生人)", text):
        facts["pii_disclosed_to_third_party"] = True

    if (
        facts.get("self_pii_provide")
        or facts.get("self_pii_recall")
        or facts.get("third_party_pii_request")
        or facts.get("pii_disclosed_to_third_party")
    ):
        facts["privacy_risk"] = True


def _mask_phone(phone: str) -> str:
    return f"{phone[:3]}****{phone[-4:]}"


def _has_executed_evidence(text: str) -> bool:
    return any(
        find_effective_terms(text, triggers)
        for triggers in list(_EXECUTED_PATTERNS.values()) + list(_CLOSURE_PATTERNS.values())
    )


def _top_scam_type(matched_scams: list[dict[str, Any]]) -> str:
    if not matched_scams:
        return ""
    return str(matched_scams[0].get("type") or "")


def _is_new_scam_topic(state: ConversationState, current_scam_type: str) -> bool:
    return bool(current_scam_type and state.suspected_scam_type and current_scam_type != state.suspected_scam_type)


def _determine_stage(state: ConversationState, risk_level: str) -> str:
    facts = state.known_facts
    if facts.get("test_mode"):
        return "test_mode"
    if facts.get("quoted_advice"):
        return "action_confirmation"
    if facts.get("already_paid"):
        return "loss_recovery"
    if facts.get("verification_code_exposed"):
        return "account_recovery"
    if state.last_intent in {"self_pii_recall", "third_party_pii_request", "pii_disclosure_warning"}:
        return "privacy_reminder"
    if facts.get("pii_disclosed_to_third_party") and not _has_active_financial_or_remote_risk(facts):
        return "privacy_reminder"
    if _has_closure_action(facts):
        return "closure_check"
    if facts.get("user_clarified_no_action"):
        return "clarifying" if state.turn_count > 1 else "preventive_warning"
    if facts.get("has_remote_control"):
        return "active_blocking" if risk_level in {"high", "critical"} else "assessing"
    if facts.get("has_remote_control_request") and facts.get("has_verification_code_request"):
        return "active_blocking"
    if facts.get("has_verification_code_request"):
        return "active_blocking"
    if _has_request_only_risk(facts):
        return "preventive_warning" if risk_level in {"medium", "high", "critical"} else "assessing"
    if risk_level == "critical":
        return "active_blocking"
    if risk_level == "high":
        return "assessing"
    if risk_level == "medium" or state.turn_count >= 2:
        return "assessing"
    return "collecting"


def _has_active_financial_or_remote_risk(facts: dict[str, bool]) -> bool:
    return bool(
        facts.get("already_paid")
        or facts.get("verification_code_exposed")
        or facts.get("has_remote_control")
        or (facts.get("has_remote_control_request") and facts.get("has_verification_code_request"))
    )


def _has_request_only_risk(facts: dict[str, bool]) -> bool:
    return any(
        facts.get(key)
        for key in {"has_transfer_request", "has_verification_code_request", "has_remote_control_request"}
    )


def _compute_follow_ups(state: ConversationState) -> list[str]:
    if state.session_stage in {
        "test_mode",
        "active_blocking",
        "account_recovery",
        "loss_recovery",
        "closure_check",
        "low_risk_monitoring",
        "privacy_reminder",
    }:
        return []
    if state.session_stage == "action_confirmation":
        return ["你刚才是在复述待办清单，还是这些动作已经完成？"]

    questions: list[str] = []
    seen: set[str] = set()
    for required_missing, question in _FOLLOW_UPS:
        if len(questions) >= 2:
            break
        if question in seen:
            continue
        if any(not state.known_facts.get(fact) for fact in required_missing):
            questions.append(question)
            seen.add(question)
    return questions


def has_safety_action_taken(conv_data: dict[str, Any]) -> bool:
    facts = conv_data.get("known_facts", {})
    return bool(isinstance(facts, dict) and facts.get("safety_action_taken"))


def has_closure_action_taken(conv_data: dict[str, Any]) -> bool:
    facts = conv_data.get("known_facts", {})
    return bool(isinstance(facts, dict) and _has_closure_action(facts))


def is_deescalation_context(conv_data: dict[str, Any]) -> bool:
    facts = conv_data.get("known_facts", {})
    if not isinstance(facts, dict):
        return False
    return bool(
        facts.get("test_mode")
        or facts.get("user_clarified_no_action")
        or facts.get("quoted_advice")
        or facts.get("self_pii_recall")
        or facts.get("self_pii_provide")
        or facts.get("third_party_pii_request")
        or facts.get("pii_disclosed_to_third_party")
    )


def has_executed_high_risk_action(conv_data: dict[str, Any]) -> bool:
    facts = conv_data.get("known_facts", {})
    if not isinstance(facts, dict):
        return False
    return bool(
        facts.get("has_remote_control")
        or facts.get("verification_code_exposed")
        or facts.get("already_paid")
    )


def _has_closure_action(facts: dict[str, bool]) -> bool:
    closure_keys = {
        "reported_to_police",
        "bank_frozen",
        "network_disconnected",
        "password_changed",
        "devices_kicked",
        "remote_control_removed",
        "phone_reset_completed",
        "blocked_contact",
        "evidence_saved",
        "trusted_person_informed",
        "no_abnormal_charge",
        "device_checked_clean",
        "no_transfer",
        "no_verification_code",
    }
    return any(facts.get(key) for key in closure_keys)
