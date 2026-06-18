from __future__ import annotations

import re
import time
from typing import Any

from app.models.schemas import ChatRequest
from app.services.ai_risk_service import AIRiskAssessor, merge_rule_and_ai_risk
from app.services.gamification import GamificationService
from app.services.intent_recognizer import IntentRecognizer
from app.services.knowledge_base import KnowledgeBase
from app.services.conversation_state import (
    ConversationStateManager,
    has_closure_action_taken,
    has_safety_action_taken,
)
from app.services.risk_engine import RiskEngine
from app.services.risk_dimensions import build_risk_dimensions, overall_level_from_dimensions
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
        ai_risk_assessor: AIRiskAssessor | None = None,
        storage: Any | None = None,
    ) -> None:
        self.knowledge_base = knowledge_base
        self.intent_recognizer = intent_recognizer
        self.risk_engine = risk_engine
        self.gamification = gamification
        self.knowledge_retriever = knowledge_retriever
        self.rag_reply_generator = rag_reply_generator
        self.ai_risk_assessor = ai_risk_assessor
        self.storage = storage
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
        if (
            previous_score is not None
            and previous_score > total_score
            and not has_safety_action_taken(conv_data)
            and not has_closure_action_taken(conv_data)
        ):
            total_score = previous_score
            breakdown["context_score_floor"] = previous_score
            breakdown["total"] = total_score
            risk_level = self.risk_engine._score_to_level(total_score)
            intervention_script = self.risk_engine._build_intervention(risk_level, request.user_profile.role)
            recommendations = self.risk_engine._build_recommendations(risk_level)
            conv_data = self._conv_state.recompute_stage(request.user_id, risk_level)

        (
            total_score,
            risk_level,
            intervention_script,
            recommendations,
            breakdown,
            all_matched_rules,
            conv_data,
        ) = self._apply_ai_risk_review(
            request=request,
            history=history,
            total_score=total_score,
            risk_level=risk_level,
            breakdown=breakdown,
            all_matched_rules=all_matched_rules,
            conv_data=conv_data,
        )

        retrieved_knowledge = self._retrieve_knowledge(request.message)
        risk_dimensions = build_risk_dimensions(
            risk_score=total_score,
            risk_level=risk_level,
            conv_data=conv_data,
        )
        current_action_level = overall_level_from_dimensions(risk_dimensions)

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
            risk_dimensions=risk_dimensions,
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
                    "session_stage": conv_data["session_stage"],
                    "known_facts": conv_data["known_facts"],
                    "ai_assessment": breakdown.get("ai_assessment", {}),
                    "risk_dimensions": risk_dimensions,
                },
                retrieved_knowledge=retrieved_knowledge,
                fallback_reply=reply,
            )

        action = "daily_chat"
        if current_action_level in {"high", "critical"}:
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

        response = {
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
            "ai_risk_assessment": breakdown.get("ai_assessment", {}),
            "risk_decision": str(breakdown.get("ai_assessment", {}).get("decision", "")),
            "risk_dimensions": risk_dimensions,
            "current_danger_level": str(risk_dimensions["current_danger"]["level"]),
            "scam_likelihood_level": str(risk_dimensions["scam_likelihood"]["level"]),
            "residual_risk_level": str(risk_dimensions["residual_risk"]["level"]),
            "next_actions": _build_chat_next_actions(current_action_level),
            "session_stage": conv_data["session_stage"],
            "known_facts": conv_data["known_facts"],
            "pending_questions": conv_data["pending_questions"],
            "conversation_summary": _build_conversation_summary(conv_data),
            "turn_count": conv_data["turn_count"],
            "retrieved_knowledge": retrieved_knowledge,
            "ruleset_versions": self.risk_engine.ruleset_versions,
        }
        self.persist_chat_exchange(request.user_id, response, request.message)
        return response

    def persist_chat_exchange(
        self,
        user_id: int,
        response: dict[str, Any],
        user_message: str,
    ) -> None:
        if not self.storage:
            return
        try:
            self.storage.add_chat_message(
                user_id=user_id,
                user_message=sanitize_text(user_message),
                assistant_reply=sanitize_text(str(response.get("reply", ""))),
                risk_level=str(response.get("risk_level", "low")),
                risk_score=int(response.get("risk_score", 0)),
                intent=str(response.get("intent", "")),
                matched_scams=[str(item) for item in response.get("matched_scams", [])],
                session_stage=str(response.get("session_stage", "collecting")),
            )
        except Exception:
            # Persistence must not block real-time risk intervention.
            return

    def _retrieve_knowledge(self, message: str) -> list[dict[str, Any]]:
        if not self.knowledge_retriever:
            return []
        try:
            return list(self.knowledge_retriever.retrieve(message))
        except Exception:
            return []

    def _apply_ai_risk_review(
        self,
        *,
        request: ChatRequest,
        history: list[dict[str, str]],
        total_score: int,
        risk_level: str,
        breakdown: dict[str, Any],
        all_matched_rules: list[dict[str, Any]],
        conv_data: dict[str, Any],
    ) -> tuple[
        int,
        str,
        list[str],
        list[str],
        dict[str, Any],
        list[dict[str, Any]],
        dict[str, Any],
    ]:
        known_facts = conv_data.get("known_facts", {})
        fact_floor = 0
        fact_rule: dict[str, Any] | None = None
        if isinstance(known_facts, dict) and known_facts.get("already_paid"):
            fact_floor = 70
            fact_rule = {
                "rule": "conversation_funds_lost",
                "evidence": ["already_paid"],
                "reason": "用户表述资金已转出或被扣款，按已受骗止损阶段处理",
                "rationale": "资金已经损失时，处置优先级高于一般风险识别。",
            }
        elif isinstance(known_facts, dict) and known_facts.get("verification_code_exposed"):
            fact_floor = 55
            fact_rule = {
                "rule": "conversation_code_exposed",
                "evidence": ["verification_code_exposed"],
                "reason": "用户表述验证码可能已泄露，按账号恢复阶段处理",
                "rationale": "验证码泄露可能导致账号接管或非本人交易。",
            }
        elif isinstance(known_facts, dict) and known_facts.get("has_remote_control"):
            fact_floor = 45
            fact_rule = {
                "rule": "conversation_remote_control",
                "evidence": ["has_remote_control"],
                "reason": "用户表述正在或曾经开启屏幕共享/远程控制",
                "rationale": "远程控制和屏幕共享会暴露验证码、账户和支付操作。",
            }

        if fact_rule and total_score < fact_floor:
            delta = fact_floor - total_score
            total_score = fact_floor
            risk_level = self.risk_engine._score_to_level(total_score)
            breakdown["conversation_fact_floor"] = fact_floor
            breakdown["total"] = total_score
            all_matched_rules = [
                *all_matched_rules,
                {
                    "rule": fact_rule["rule"],
                    "evidence": fact_rule["evidence"],
                    "weight": delta,
                    "reason": fact_rule["reason"],
                    "rule_version": "1.0",
                    "ruleset_version": "conversation-1.1",
                    "rationale": fact_rule["rationale"],
                },
            ]
            conv_data = self._conv_state.recompute_stage(request.user_id, risk_level)

        if not self.ai_risk_assessor:
            breakdown.setdefault("ai_assessment", {"enabled": False})
            return (
                total_score,
                risk_level,
                self.risk_engine._build_intervention(risk_level, request.user_profile.role),
                self.risk_engine._build_recommendations(risk_level),
                breakdown,
                all_matched_rules,
                conv_data,
            )

        assessment = self.ai_risk_assessor.assess(
            message=request.message,
            history=history,
            rule_context={
                "risk_score": total_score,
                "risk_level": risk_level,
                "session_stage": conv_data.get("session_stage"),
                "known_facts": conv_data.get("known_facts", {}),
                "matched_rule_names": [
                    str(item.get("rule") or item.get("name") or "")
                    for item in all_matched_rules[:12]
                    if isinstance(item, dict)
                ],
            },
        )
        merged = merge_rule_and_ai_risk(
            rule_score=total_score,
            rule_level=risk_level,
            ai_assessment=assessment,
        )
        breakdown["ai_assessment"] = merged.breakdown()
        if merged.matched_rule:
            all_matched_rules = [*all_matched_rules, merged.matched_rule]
        if merged.final_score != total_score:
            total_score = merged.final_score
            risk_level = merged.final_level
            breakdown["ai_score"] = merged.ai_score_delta
            breakdown["total"] = total_score
            conv_data = self._conv_state.recompute_stage(request.user_id, risk_level)

        return (
            total_score,
            risk_level,
            self.risk_engine._build_intervention(risk_level, request.user_profile.role),
            self.risk_engine._build_recommendations(risk_level),
            breakdown,
            all_matched_rules,
            conv_data,
        )

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
        risk_dimensions: dict[str, Any] | None = None,
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
        if stage in {"closure_check", "debriefing"}:
            return self._build_closure_check_reply(role_prefix, known_facts or {})

        if stage == "loss_recovery":
            return self._build_loss_recovery_reply(role_prefix, known_facts or {})

        if stage == "account_recovery":
            return self._build_account_recovery_reply(role_prefix, known_facts or {})

        if stage in {"warning", "active_blocking"}:
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
    def _build_closure_check_reply(
        role_prefix: str,
        known_facts: dict[str, bool],
    ) -> str:
        parts = [f"{role_prefix}你已经在做正确的止损动作了，现在从“紧急阻断”转到收尾检查。"]
        if known_facts.get("already_paid"):
            parts.append("确认银行或支付平台的止付/冻结是否受理，记录工单号或报警回执。")
        else:
            parts.append("接下来不要恢复联系、不要重新开启屏幕共享，也不要再点对方发来的链接。")
        if known_facts.get("verification_code_exposed"):
            parts.append("再检查一次账号安全：改密、退出陌生设备、关闭免密支付。")
        parts.append("把聊天记录、对方账号、链接和软件截图保存下来即可，不需要反复和对方周旋。")
        return "".join(parts)

    @staticmethod
    def _build_loss_recovery_reply(
        role_prefix: str,
        known_facts: dict[str, bool],
    ) -> str:
        return (
            f"{role_prefix}钱已经被转走时，重点不是再判断真假，而是止损取证："
            "立刻联系银行或支付平台申请止付/冻结，同时拨打110或96110报案。"
            "保存聊天记录、收款账户、转账单号、会议软件和屏幕共享截图；不要再回复对方，也不要按对方要求撤销报案。"
        )

    @staticmethod
    def _build_account_recovery_reply(
        role_prefix: str,
        known_facts: dict[str, bool],
    ) -> str:
        return (
            f"{role_prefix}验证码已经被对方看到，就按账号可能被接管处理："
            "立刻退出屏幕共享，在官方App里改密码，退出陌生登录设备，关闭免密支付或临时冻结账户。"
            "如果银行卡、支付账户或社交账号出现异常，马上联系官方客服或96110处理。"
        )

    @staticmethod
    def _build_warning_reply(
        role_prefix: str,
        matched_scams: list[dict[str, Any]],
        risk_level: str,
        known_facts: dict[str, bool],
    ) -> str:
        if known_facts.get("already_paid"):
            return (
                f"{role_prefix}这已经不是普通提醒了，先按止损流程来：马上联系银行或支付平台申请止付/冻结，"
                "同时拨打110或96110说明“疑似诈骗转账”。不要再回复对方，也不要按对方说的撤销报案。"
                "把聊天记录、收款账户、转账单号和屏幕共享软件截图保存好。"
            )

        if known_facts.get("has_verification_code_request"):
            return (
                f"{role_prefix}验证码如果被对方看到，先按账户可能被接管处理：立刻退出屏幕共享，"
                "在官方App里修改密码，踢出陌生登录设备，关闭免密支付或临时冻结账户。"
                "不要再输入新的验证码，也不要点对方发来的任何链接。"
            )

        if known_facts.get("has_remote_control"):
            return (
                f"{role_prefix}现在最关键是切断对方视线：马上停止屏幕共享，关闭会议软件，"
                "把远程控制/会议软件卸载或结束进程。之后检查银行、支付平台和社交账号有没有异常登录。"
            )

        if known_facts.get("mentions_authority"):
            return (
                f"{role_prefix}如果对方自称公检法或安全账户，直接挂断。真正的公检法不会让你转账、共享屏幕或提供验证码。"
                "用官方号码重新核实，不要沿用对方给你的电话和链接。"
            )

        if matched_scams:
            top = matched_scams[0]
            return (
                f"{role_prefix}这和“{top.get('name', '诈骗话术')}”很像。先停止付款、验证码和链接操作，"
                "把对方账号、链接、收款信息截图留好，再通过官方渠道核实。"
            )

        return f"{role_prefix}当前风险偏高，先停止付款、验证码和屏幕共享相关操作，再补充对方具体让你做哪一步，我来帮你继续判断。"


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
        "active_blocking": "正在紧急阻断",
        "account_recovery": "正在处理账号泄露风险",
        "loss_recovery": "正在止损取证",
        "closure_check": "正在收尾检查",
        "debriefing": "正在复盘总结",
    }.get(stage, stage)

    parts = [f"第{turn}轮对话 | {stage_text}"]
    if true_facts:
        parts.append(f"已识别{len(true_facts)}条风险信号")
    if stage in {"warning", "active_blocking"}:
        parts.append("请立即执行阻断操作")
    if stage in {"account_recovery", "loss_recovery", "closure_check"}:
        parts.append("请按当前阶段完成收尾动作")
    return " · ".join(parts)
