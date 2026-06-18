from __future__ import annotations

import os
from typing import Any

from app.services.llm_client import (
    chat_payload,
    env_int,
    first_choice_text,
    load_llm_config,
    post_chat_completion,
)
from app.services.sanitizer import sanitize_text


class RagReplyGenerator:
    """Optional LLM generator that uses RiskEngine output plus retrieved knowledge."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        require_retrieved_knowledge: bool | None = None,
    ) -> None:
        self.config = load_llm_config(
            base_url=base_url,
            model=model,
            timeout=timeout,
            timeout_env="RAG_LLM_TIMEOUT",
        )
        self.base_url = self.config.base_url
        self.model = self.config.model
        self.timeout = self.config.timeout
        self.require_retrieved_knowledge = (
            require_retrieved_knowledge
            if require_retrieved_knowledge is not None
            else os.getenv("CHAT_LLM_ENABLED", "0").lower() not in {"1", "true", "yes"}
        )

    def generate(
        self,
        *,
        message: str,
        risk_context: dict[str, Any],
        retrieved_knowledge: list[dict[str, Any]],
        fallback_reply: str,
    ) -> str:
        if self.require_retrieved_knowledge and not retrieved_knowledge:
            return _sanitize_reply(fallback_reply, risk_context, message)

        knowledge_instruction = (
            "可以参考召回知识，但要把它自然地说给用户听，不要像粘贴资料。"
            if retrieved_knowledge
            else "当前没有参考知识召回，只基于规则引擎结论生成自然中文劝阻话术。"
        )
        rules_text = _format_rules(risk_context.get("matched_rules", []))
        knowledge_text = _format_knowledge(retrieved_knowledge)
        ai_assessment = risk_context.get("ai_assessment", {})
        known_facts = risk_context.get("known_facts", {})
        risk_dimensions = risk_context.get("risk_dimensions", {})
        sanitized_message = sanitize_text(message)
        user_content = f"""用户刚说:
{sanitized_message}

规则引擎判断:
- 风险等级: {risk_context.get("risk_level")}
- 最终风险分: {risk_context.get("risk_score")}
- 会话阶段: {risk_context.get("session_stage") or "unknown"}
- 识别到的风险信号: {rules_text or "暂未命中明确风险信号"}
- 处置建议: {"；".join(risk_context.get("intervention_script", []))}
- 推荐动作: {"；".join(risk_context.get("recommendations", []))}
- 已确认事实: {_format_known_facts(known_facts)}
- AI复核: {_format_ai_assessment(ai_assessment)}
- 风险维度: {_format_risk_dimensions(risk_dimensions)}

参考知识:
{knowledge_text or "无"}

直接回复用户。不要输出 JSON、字段名、内部变量、规则名、权重或报告式标题。"""
        messages = [
            {
                "role": "system",
                    "content": (
                        "你是一个反诈劝阻助手，但说话要像冷静、有耐心的真人朋友。"
                        "必须以给定 RiskEngine 结果为准，不得修改 risk_score、risk_level 或命中规则。"
                        f"{knowledge_instruction}"
                        "先接住用户当前处境，再给最关键的一到三步。"
                        "必须根据当前轮次变化调整建议：验证码被看见就优先改密码、踢出登录设备、冻结支付；钱被转走就优先止付、报警、保存证据；已停止/已卸载就进入复盘和证据保全。"
                        "必须区分诈骗可能性、当前危险和事后残留风险：如果用户已经报警、冻结、断网或卸载，不要继续说成正在被实时操控。"
                        "不要使用【风险等级】【命中规则】【处置建议】这类标题。"
                        "不要复述内部规则名、分数计算或 JSON。"
                        "不要机械重复“深呼吸、冷静30秒、找家人、官方客服”这类通用句；除非当前轮次确实需要。"
                        "语气可以口语化，但必须给出具体、可执行、和当前事实匹配的动作。"
                        "控制在 180 字以内。"
                    ),
                },
            {
                "role": "user",
                "content": user_content,
            },
        ]
        payload = chat_payload(
            config=self.config,
            messages=messages,
            temperature=0.35,
            max_tokens=env_int("RAG_LLM_MAX_TOKENS", env_int("LLM_MAX_TOKENS", 256)),
        )

        try:
            data = post_chat_completion(self.config, payload)
            reply = first_choice_text(data)
            return _sanitize_reply(reply, risk_context, message)
        except Exception:
            return _sanitize_reply(fallback_reply, risk_context, message)


def _format_rules(rules: Any) -> str:
    if not isinstance(rules, list):
        return ""
    parts: list[str] = []
    for rule in rules[:5]:
        if not isinstance(rule, dict):
            continue
        reason = str(rule.get("reason", "")).strip()
        evidence = rule.get("evidence", [])
        if reason:
            parts.append(reason)
        elif isinstance(evidence, list) and evidence:
            parts.append("、".join(str(item) for item in evidence[:3]))
    return "；".join(dict.fromkeys(parts))


def _format_knowledge(items: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in items[:3]:
        title = item.get("title", "")
        content = str(item.get("content", "")).replace("\n", " ")
        lines.append(f"- {title}: {content[:180]}")
    return "\n".join(lines)


def _format_ai_assessment(value: Any) -> str:
    if not isinstance(value, dict) or not value.get("enabled"):
        return "未启用或无结果"
    reasons = value.get("reasons", [])
    actions = value.get("recommended_actions", [])
    reason_text = "；".join(str(item) for item in reasons[:3]) if isinstance(reasons, list) else ""
    action_text = "；".join(str(item) for item in actions[:3]) if isinstance(actions, list) else ""
    return (
        f"{value.get('risk_level')}/{value.get('risk_score')} "
        f"confidence={value.get('confidence')} "
        f"stage={value.get('fraud_stage')} "
        f"原因:{reason_text or '无'} "
        f"建议:{action_text or '无'}"
    )


def _format_known_facts(value: Any) -> str:
    if not isinstance(value, dict):
        return "无"
    active = [key for key, enabled in value.items() if enabled]
    return "、".join(active) if active else "无"


def _format_risk_dimensions(value: Any) -> str:
    if not isinstance(value, dict):
        return "未计算"
    parts: list[str] = []
    for key in ("scam_likelihood", "current_danger", "loss_impact", "residual_risk"):
        item = value.get(key, {})
        if isinstance(item, dict):
            parts.append(f"{key}={item.get('level')}/{item.get('score')}")
    return "；".join(parts) if parts else "未计算"


def _looks_like_internal_echo(reply: str) -> bool:
    if not reply:
        return False
    markers = [
        '"user_message"',
        '"risk_engine_result"',
        '"retrieved_knowledge"',
        "risk_engine_result",
        "retrieved_knowledge",
        "{'user_message'",
    ]
    compact = reply.strip()
    return compact.startswith("{") or any(marker in compact for marker in markers)


def _sanitize_reply(reply: str, risk_context: dict[str, Any], message: str) -> str:
    if not reply or _looks_like_internal_echo(reply) or _looks_like_report(reply):
        return _human_fallback(risk_context, message)
    return reply.strip()


def _looks_like_report(reply: str) -> bool:
    markers = [
        "【风险等级】",
        "【最终风险分】",
        "【命中规则】",
        "【处置建议】",
        "【推荐动作】",
        "【关键动作】",
        "【最终建议】",
        "请重新按",
        "规则引擎",
        "RiskEngine",
        "risk_score",
        "risk_level",
        "matched_rules",
    ]
    return any(marker in reply for marker in markers)


def _human_fallback(risk_context: dict[str, Any], message: str) -> str:
    level = str(risk_context.get("risk_level") or "low")
    signals = _format_rules(risk_context.get("matched_rules", []))
    actions = _compact_actions(risk_context.get("recommendations", []))
    scam_hint = _infer_scam_hint(message, signals)

    if level in {"high", "critical"}:
        opener = "先别慌，但这一步要马上停。"
        stop_line = "现在不要再转账、不要填验证码，也不要点对方发来的链接或下载陌生 App。"
    elif level == "medium":
        opener = "你先停一下，这个情况已经有明显风险。"
        stop_line = "先不要继续下单或付款，也别再按对方的话操作。"
    else:
        opener = "我先帮你按谨慎方式处理。"
        stop_line = "暂时不要给陌生账户转钱，也不要提交验证码、银行卡或身份证信息。"

    evidence = f"你提到的{scam_hint}，是反诈里很常见的危险信号。" if scam_hint else ""
    next_step = "你把聊天记录、收款账号、链接和付款页面先留好；如果已经转钱，马上联系银行或平台客服申请止付，并拨打 96110/110 咨询。"
    action_line = f"接下来优先做这几件事：{actions}。" if actions else next_step
    return "".join(part for part in [opener, evidence, stop_line, action_line] if part)


def _compact_actions(recommendations: Any) -> str:
    if not isinstance(recommendations, list):
        return ""
    clean = [str(item).strip("。；; ") for item in recommendations if str(item).strip()]
    return "；".join(clean[:3])


def _infer_scam_hint(message: str, signals: str) -> str:
    text = f"{message} {signals}"
    if any(token in text for token in ["刷单", "返利", "垫付", "做任务"]):
        return "“先垫付、做任务、完成后返利”"
    if any(token in text for token in ["验证码", "短信码", "银行卡"]):
        return "“索要验证码或银行卡信息”"
    if any(token in text for token in ["AI换脸", "deepfake", "AI语音", "克隆声音"]):
        return "“视频或语音里借钱”"
    if any(token in text for token in ["公检法", "安全账户", "涉案"]):
        return "“公检法/安全账户”"
    if any(token in text for token in ["投资", "高收益", "带单"]):
        return "“高收益投资带单”"
    return ""
