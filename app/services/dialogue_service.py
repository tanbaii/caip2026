from __future__ import annotations

import re
import time
from typing import Any

from app.models.schemas import ChatRequest
from app.services.gamification import GamificationService
from app.services.intent_recognizer import IntentRecognizer
from app.services.knowledge_base import KnowledgeBase
from app.services.conversation_state import ConversationStateManager
from app.services.risk_engine import RiskEngine
from app.services.sanitizer import sanitize_text


class DialogueService:
    def __init__(
        self,
        knowledge_base: KnowledgeBase,
        intent_recognizer: IntentRecognizer,
        risk_engine: RiskEngine,
        gamification: GamificationService,
        knowledge_retriever: Any | None = None,
        rag_reply_generator: Any | None = None,
    ) -> None:
        self.knowledge_base = knowledge_base
        self.intent_recognizer = intent_recognizer
        self.risk_engine = risk_engine
        self.gamification = gamification
        self.knowledge_retriever = knowledge_retriever
        self.rag_reply_generator = rag_reply_generator
        self._history: dict[str, list[dict[str, str]]] = {}
        self._url_pattern = re.compile(r"(https?://\S+|www\.\S+)", re.IGNORECASE)
        self._conv_state = ConversationStateManager()

    def reset_conversation(self, user_id: int) -> None:
        self._history.pop(user_id, None)
        self._conv_state.reset(user_id)

    def process_chat(self, request: ChatRequest) -> dict[str, Any]:
        start_time = time.perf_counter()
        history = self._history.get(request.user_id, [])

        intent, _, _ = self.intent_recognizer.detect_intent(request.message, history)
        matched_scams = self.knowledge_base.search_scams(request.message)
        matched_names = [item["name"] for item in matched_scams]
        current_scam_type = _top_scam_type(matched_scams)

        if _is_new_explicit_scam_topic(history, current_scam_type):
            history = []
            self._history[request.user_id] = []
            self._conv_state.reset(request.user_id)
            intent, _, _ = self.intent_recognizer.detect_intent(request.message, history)

        risk = self.risk_engine.evaluate_text(
            request.message,
            matched_scams,
            request.user_profile.role,
            request.emotion,
        )

        url_bonus = 0
        all_matched_rules = list(risk.get("matched_rules", []))
        for url in self._url_pattern.findall(request.message):
            url_risk = self.risk_engine.evaluate_url(url)
            if int(url_risk["score"]) >= 25:
                risk["reasons"].append(f"检测到可疑链接: {url}")
                url_bonus += 10
            all_matched_rules.extend(url_risk.get("matched_rules", []))

        total_score = int(risk["score"]) + url_bonus
        risk_level = self.risk_engine._score_to_level(total_score)
        intervention_script = self.risk_engine._build_intervention(risk_level, request.user_profile.role)
        recommendations = self.risk_engine._build_recommendations(risk_level)

        breakdown = dict(risk.get("risk_breakdown", {}))
        breakdown["url_score"] = url_bonus
        breakdown["total"] = total_score

        # --- Multi-turn conversation state ---
        conv_data = self._conv_state.update_and_get(
            user_id=request.user_id,
            message=request.message,
            risk_level=risk_level,
            intent=intent,
            matched_scams=matched_scams,
        )

        conv_bonus, conv_rules, conv_reasons = self._conv_state.compute_conversation_bonus(
            request.user_id,
        )

        if conv_bonus > 0:
            total_score += conv_bonus
            all_matched_rules.extend(conv_rules)
            risk["reasons"].extend(conv_reasons)
            breakdown["conversation_score"] = conv_bonus
            breakdown["total"] = total_score
            risk_level = self.risk_engine._score_to_level(total_score)
            intervention_script = self.risk_engine._build_intervention(risk_level, request.user_profile.role)
            recommendations = self.risk_engine._build_recommendations(risk_level)
            # Recompute stage + pending_questions against final risk_level
            conv_data = self._conv_state.recompute_stage(request.user_id, risk_level)

        previous_score = _last_history_score(history)
        if previous_score is not None and previous_score > total_score:
            total_score = previous_score
            breakdown["context_score_floor"] = previous_score
            breakdown["total"] = total_score
            risk_level = self.risk_engine._score_to_level(total_score)
            intervention_script = self.risk_engine._build_intervention(risk_level, request.user_profile.role)
            recommendations = self.risk_engine._build_recommendations(risk_level)
            conv_data = self._conv_state.recompute_stage(request.user_id, risk_level)

        retrieved_knowledge = self._retrieve_knowledge(request.message)

        reply = self._build_reply(
            message=request.message,
            intent=intent,
            matched_scams=matched_scams,
            risk_level=risk_level,
            user_role=request.user_profile.role,
            stage=conv_data["session_stage"],
            pending_questions=conv_data["pending_questions"],
            known_facts=conv_data["known_facts"],
            turn_count=conv_data["turn_count"],
        )

        if self.rag_reply_generator:
            reply = self.rag_reply_generator.generate(
                message=request.message,
                risk_context={
                    "risk_score": total_score,
                    "risk_level": risk_level,
                    "matched_rules": all_matched_rules,
                    "risk_breakdown": breakdown,
                    "intervention_script": intervention_script,
                    "recommendations": recommendations,
                },
                retrieved_knowledge=retrieved_knowledge,
                fallback_reply=reply,
            )

        action = "daily_chat"
        if risk_level in {"high", "critical"}:
            action = "risk_block"
        elif intent in {"ask_knowledge", "report_content"}:
            action = "knowledge_query"

        reward = self.gamification.award(
            request.user_id,
            action=action,
            risk_level=risk_level,
        )

        new_history = history + [
            {
                "message": sanitize_text(request.message),
                "intent": intent,
                "risk_level": risk_level,
                "risk_score": str(total_score),
                "scam_type": current_scam_type,
            }
        ]
        self._history[request.user_id] = new_history[-12:]

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return {
            "reply": reply,
            "intent": intent,
            "matched_scams": matched_names,
            "risk_level": risk_level,
            "risk_score": total_score,
            "intervention_script": intervention_script,
            "recommendations": recommendations,
            "points_gained": int(reward["points_gained"]),
            "total_points": int(reward["total_points"]),
            "badges": list(reward["badges"]),
            "latency_ms": latency_ms,
            "matched_rules": all_matched_rules,
            "risk_breakdown": breakdown,
            "next_actions": _build_chat_next_actions(risk_level),
            "session_stage": conv_data["session_stage"],
            "known_facts": conv_data["known_facts"],
            "pending_questions": conv_data["pending_questions"],
            "conversation_summary": _build_conversation_summary(conv_data),
            "turn_count": conv_data["turn_count"],
            "retrieved_knowledge": retrieved_knowledge,
        }

    def _retrieve_knowledge(self, message: str) -> list[dict[str, Any]]:
        if not self.knowledge_retriever:
            return []
        try:
            return list(self.knowledge_retriever.retrieve(message))
        except Exception:
            return []

    def _build_reply(
        self,
        message: str,
        intent: str,
        matched_scams: list[dict[str, Any]],
        risk_level: str,
        user_role: str,
        stage: str = "collecting",
        pending_questions: list[str] | None = None,
        known_facts: dict[str, bool] | None = None,
        turn_count: int = 1,
    ) -> str:
        role_prefix = "同学" if user_role == "student" else "你"

        if intent == "scenario_practice":
            return (
                "已切换到反诈闯关模式。你可以先调用 /scenarios 查看关卡，再用 /scenarios/start 开始实战演练。"
            )

        if intent == "report_content":
            return (
                "可以一键举报：把可疑链接或聊天内容提交到 /report，我会给出初判结果、风险原因和下一步建议。"
            )

        # --- Stage-aware reply ---
        if stage == "warning":
            return self._build_warning_reply(role_prefix, matched_scams, risk_level, known_facts or {})

        if matched_scams:
            top = matched_scams[0]
            prevention = "；".join(top.get("prevention", [])[:2])
            red_flags = "；".join(top.get("red_flags", [])[:2])
            core = (
                f"你当前描述与“{top['name']}”高度相关。"
                f"高危信号包括：{red_flags}。"
                f"建议：{prevention}。"
            )
        else:
            core = (
                "我暂未匹配到单一骗局模型，但你可以继续提供对方话术、转账要求或链接，我会实时研判风险。"
            )

        if risk_level in {"high", "critical"}:
            return f"{role_prefix}现在要先止损。{core}当前风险较高，请先停止任何付款或验证码操作。"

        # collecting / assessing: provide analysis + follow-up questions
        parts = [core]

        if pending_questions:
            parts.append("为了更准确判断，请补充以下信息：")
            for q in pending_questions[:2]:
                parts.append(f"  {q}")

        if intent == "ask_knowledge":
            parts.append("如果你愿意，我还能给你一个30秒自检清单，帮助快速判断是否诈骗。")
        elif re.search(r"(转账|验证码|付款|链接)", message):
            parts.append("涉及资金和账号信息时，请务必先核验身份与平台真伪。")
        elif turn_count <= 1 and not pending_questions:
            parts.append("你也可以发“来一关模拟”进入情景训练。")

        return "".join(parts)

    @staticmethod
    def _build_warning_reply(
        role_prefix: str,
        matched_scams: list[dict[str, Any]],
        risk_level: str,
        known_facts: dict[str, bool],
    ) -> str:
        parts = [f"{role_prefix}当前情况非常危险，请立即执行以下操作："]

        if known_facts.get("already_paid"):
            parts.append("你已经转过钱了，请立刻联系银行申请紧急止付，并拨打110报案。")
        else:
            parts.append("立即停止所有转账和验证码操作。")

        if known_facts.get("has_remote_control"):
            parts.append("退出屏幕共享，卸载远程控制软件。")

        if matched_scams:
            top = matched_scams[0]
            parts.append("当前情况与“" + top.get("name", "") + "”高度吻合。")

        if known_facts.get("mentions_authority"):
            parts.append("公检法不会通过电话要求转账或共享屏幕，请不要相信。")

        if risk_level == "critical":
            parts.append("请保留所有聊天记录和转账凭证，作为报案证据。")

        return "".join(parts)


def _build_chat_next_actions(risk_level: str) -> list[str]:
    if risk_level == "critical":
        return [
            "立即拨打110或96110报警",
            "联系银行申请紧急止付并冻结账户",
            "保留所有聊天记录和转账凭证作为证据",
            "告知家人或辅导员协助处理",
        ]
    if risk_level == "high":
        return [
            "停止所有转账和验证码操作",
            "通过官方渠道（如110、96110）核验对方身份",
            "保留聊天记录、收款账户、链接截图",
            "不要点击任何对方发送的链接",
        ]
    if risk_level == "medium":
        return [
            "暂停当前操作，与可信任的人二次确认",
            "通过官方电话或App核实信息真伪",
            "警惕对方提出的转账、验证码或链接要求",
        ]
    return [
        "保持警惕，不点击未知链接",
        "不向陌生账户转账",
        "继续提供对方话术细节以便更准确研判",
    ]


def _last_history_score(history: list[dict[str, str]]) -> int | None:
    for item in reversed(history):
        raw_score = item.get("risk_score")
        if raw_score is None:
            continue
        try:
            return int(raw_score)
        except (TypeError, ValueError):
            return None
    return None


def _top_scam_type(matched_scams: list[dict[str, Any]]) -> str:
    if not matched_scams:
        return ""
    return str(matched_scams[0].get("type") or "")


def _last_history_scam_type(history: list[dict[str, str]]) -> str:
    for item in reversed(history):
        scam_type = item.get("scam_type")
        if scam_type:
            return scam_type
    return ""


def _is_new_explicit_scam_topic(history: list[dict[str, str]], current_scam_type: str) -> bool:
    previous_scam_type = _last_history_scam_type(history)
    return bool(current_scam_type and previous_scam_type and current_scam_type != previous_scam_type)


def _build_conversation_summary(conv_data: dict) -> str:
    stage = conv_data.get("session_stage", "collecting")
    turn = conv_data.get("turn_count", 0)
    facts = conv_data.get("known_facts", {})
    true_facts = [k for k, v in facts.items() if v]

    stage_text = {
        "collecting": "正在收集信息",
        "assessing": "正在评估风险",
        "warning": "已触发高危预警",
        "debriefing": "正在复盘总结",
    }.get(stage, stage)

    parts = [f"第{turn}轮对话 | {stage_text}"]
    if true_facts:
        parts.append(f"已识别{len(true_facts)}条风险信号")
    if stage == "warning":
        parts.append("请立即执行止损操作")
    return " · ".join(parts)
