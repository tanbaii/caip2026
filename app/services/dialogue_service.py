from __future__ import annotations

import re
import os
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
    has_executed_high_risk_action,
    has_safety_action_taken,
    is_deescalation_context,
)
from app.services.risk_engine import RiskEngine
from app.services.risk_dimensions import build_risk_dimensions, overall_level_from_dimensions
from app.services.sanitizer import sanitize_text

EmotionLabel = str

_ANXIOUS_EMOTION_TERMS = (
    "怎么办",
    "害怕",
    "慌",
    "焦虑",
    "担心",
    "来不及",
    "催我",
    "马上",
    "立刻",
    "赶紧",
    "急",
    "一直催",
    "不处理就",
    "否则",
)
_NEGATIVE_EMOTION_TERMS = (
    "生气",
    "烦",
    "崩溃",
    "绝望",
    "被骗了",
    "后悔",
    "难受",
)
_POSITIVE_EMOTION_TERMS = (
    "谢谢",
    "放心",
    "已经解决",
    "明白了",
    "学到了",
)


def infer_emotion_signal(message: str, explicit_emotion: str | None = None) -> EmotionLabel:
    if explicit_emotion:
        return explicit_emotion

    normalized = message.strip().lower()
    if any(term in normalized for term in _ANXIOUS_EMOTION_TERMS):
        return "anxious"
    if any(term in normalized for term in _NEGATIVE_EMOTION_TERMS):
        return "negative"
    if any(term in normalized for term in _POSITIVE_EMOTION_TERMS):
        return "positive"
    return "neutral"


class DialogueService:
    def __init__(
        self,
        knowledge_base: KnowledgeBase,
        intent_recognizer: IntentRecognizer,
        risk_engine: RiskEngine,
        gamification: GamificationService,
        knowledge_retriever: Any | None = None,
        rag_reply_generator: Any | None = None,
        hybrid_retriever: Any | None = None,
        ai_risk_assessor: AIRiskAssessor | None = None,
        storage: Any | None = None,
    ) -> None:
        self.knowledge_base = knowledge_base
        self.intent_recognizer = intent_recognizer
        self.risk_engine = risk_engine
        self.gamification = gamification
        self.knowledge_retriever = knowledge_retriever
        self.hybrid_retriever = hybrid_retriever
        self.rag_reply_generator = rag_reply_generator
        self.ai_risk_assessor = ai_risk_assessor
        self.storage = storage
        self._history: dict[str, list[dict[str, str]]] = {}
        self._skip_restore_keys: set[str] = set()
        self._url_pattern = re.compile(r"(https?://\S+|www\.\S+)", re.IGNORECASE)
        self._conv_state = ConversationStateManager()

    def _default_conversation_id(self, user_id: int) -> str:
        if self.storage and hasattr(self.storage, "default_chat_conversation_id"):
            return str(self.storage.default_chat_conversation_id(user_id))
        return f"default-{int(user_id)}"

    @staticmethod
    def _conversation_key(user_id: int, conversation_id: str) -> str:
        return f"{int(user_id)}:{conversation_id}"

    def _conversation_key_for_request(self, request: ChatRequest) -> str:
        return self._conversation_key(
            request.user_id,
            request.conversation_id or self._default_conversation_id(request.user_id),
        )

    def _ensure_conversation_id(self, request: ChatRequest) -> str:
        conversation_id = request.conversation_id or self._default_conversation_id(request.user_id)
        if self.storage and hasattr(self.storage, "ensure_chat_conversation"):
            conversation = self.storage.ensure_chat_conversation(
                user_id=request.user_id,
                conversation_id=conversation_id,
                title_hint=request.message,
            )
            return str(conversation["conversation_id"])
        return conversation_id

    def _restore_persisted_conversation(self, user_id: int, conversation_id: str) -> None:
        if not self.storage or not hasattr(self.storage, "list_chat_conversation_messages"):
            return
        key = self._conversation_key(user_id, conversation_id)
        if key in self._skip_restore_keys:
            self._skip_restore_keys.discard(key)
            return
        if key in self._history:
            return
        messages = self.storage.list_chat_conversation_messages(
            user_id=user_id,
            conversation_id=conversation_id,
        )
        if not messages:
            return
        self._conv_state.reset(key)
        restored_history: list[dict[str, str]] = []
        for item in messages[-12:]:
            self._conv_state.update_and_get(
                user_id=key,
                message=str(item.get("user_message", "")),
                risk_level=str(item.get("risk_level", "low")),
                intent=str(item.get("intent", "")),
                matched_scams=[],
            )
            restored_history.append(
                {
                    "message": sanitize_text(str(item.get("user_message", ""))),
                    "intent": str(item.get("intent", "")),
                    "risk_level": str(item.get("risk_level", "low")),
                    "risk_score": str(item.get("risk_score", 0)),
                    "scam_type": "",
                }
            )
        self._history[key] = restored_history[-12:]

    def reset_conversation(self, user_id: int, conversation_id: str | None = None) -> None:
        normalized_id = conversation_id or self._default_conversation_id(user_id)
        key = self._conversation_key(user_id, normalized_id)
        self._history.pop(key, None)
        self._skip_restore_keys.add(key)
        self._conv_state.reset(key)

    def process_chat(self, request: ChatRequest) -> dict[str, Any]:
        start_time = time.perf_counter()
        conversation_id = self._ensure_conversation_id(request)
        request = request.model_copy(update={"conversation_id": conversation_id})
        conversation_key = self._conversation_key(request.user_id, conversation_id)
        self._restore_persisted_conversation(request.user_id, conversation_id)
        history = self._history.get(conversation_key, [])
        emotion = infer_emotion_signal(request.message, request.emotion)

        intent, _, _ = self.intent_recognizer.detect_intent(request.message, history)
        matched_scams = self.knowledge_base.search_scams(request.message)
        matched_names = [item["name"] for item in matched_scams]
        current_scam_type = _top_scam_type(matched_scams)

        if _is_new_explicit_scam_topic(history, current_scam_type):
            history = []
            self._history[conversation_key] = []
            self._conv_state.reset(conversation_key)
            intent, _, _ = self.intent_recognizer.detect_intent(request.message, history)

        risk = self.risk_engine.evaluate_text(
            request.message,
            matched_scams,
            request.user_profile.role,
            emotion,
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
            user_id=conversation_key,
            message=request.message,
            risk_level=risk_level,
            intent=intent,
            matched_scams=matched_scams,
        )

        conv_bonus, conv_rules, conv_reasons = self._conv_state.compute_conversation_bonus(
            conversation_key,
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
            conv_data = self._conv_state.recompute_stage(conversation_key, risk_level)

        (
            total_score,
            risk_level,
            intervention_script,
            recommendations,
            breakdown,
            all_matched_rules,
            conv_data,
        ) = self._apply_evidence_risk_adjustments(
            conversation_key,
            total_score,
            risk_level,
            breakdown,
            all_matched_rules,
            conv_data,
            request.user_profile.role,
        )

        previous_score = _last_history_score(history)
        if (
            previous_score is not None
            and previous_score > total_score
            and not has_safety_action_taken(conv_data)
            and not has_closure_action_taken(conv_data)
            and not is_deescalation_context(conv_data)
        ):
            total_score = previous_score
            breakdown["context_score_floor"] = previous_score
            breakdown["total"] = total_score
            risk_level = self.risk_engine._score_to_level(total_score)
            intervention_script = self.risk_engine._build_intervention(risk_level, request.user_profile.role)
            recommendations = self.risk_engine._build_recommendations(risk_level)
            conv_data = self._conv_state.recompute_stage(conversation_key, risk_level)

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

        (
            total_score,
            risk_level,
            intervention_script,
            recommendations,
            breakdown,
            all_matched_rules,
            conv_data,
        ) = self._apply_evidence_risk_adjustments(
            conversation_key,
            total_score,
            risk_level,
            breakdown,
            all_matched_rules,
            conv_data,
            request.user_profile.role,
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
            pii_memory=conv_data.get("pii_memory", {}),
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
        event_key = _reward_event_key(
            conv_data=conv_data,
            risk_level=risk_level,
            current_scam_type=current_scam_type,
        )
        if current_action_level in {"high", "critical"}:
            action = "risk_alert"
        if has_closure_action_taken(conv_data):
            action = "safety_action_confirmed"
        elif intent in {"ask_knowledge", "report_content"}:
            action = "knowledge_query"

        reward_risk_level = risk_level
        if action == "safety_action_confirmed":
            reward_risk_level = _max_level(risk_level, _max_history_risk_level(history))

        reward = self.gamification.award(
            request.user_id,
            action=action,
            risk_level=reward_risk_level,
            event_key=event_key,
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
        self._history[conversation_key] = new_history[-12:]

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        response = {
            "conversation_id": conversation_id,
            "emotion": emotion,
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
            "privacy_risk_level": str(risk_dimensions["privacy_risk"]["level"]),
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
                conversation_id=str(response.get("conversation_id", "")) or None,
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
        # Prefer hybrid retriever (Dense + BM25 + RRF)
        if self.hybrid_retriever is not None:
            try:
                return list(self.hybrid_retriever.retrieve(
                    message,
                    top_k=int(os.getenv("RAG_TOP_K", "5")),
                    use_reranker=os.getenv("RAG_RERANK_ENABLED", "0").lower() in {"1", "true", "yes"},
                ))
            except Exception:
                pass
        # Fallback to dense-only retriever
        if not self.knowledge_retriever:
            return []
        try:
            return list(self.knowledge_retriever.retrieve(message))
        except Exception:
            return []

    def _apply_evidence_risk_adjustments(
        self,
        user_id: int,
        total_score: int,
        risk_level: str,
        breakdown: dict[str, Any],
        all_matched_rules: list[dict[str, Any]],
        conv_data: dict[str, Any],
        user_role: str,
    ) -> tuple[int, str, list[str], list[str], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
        facts = conv_data.get("known_facts", {})
        if not isinstance(facts, dict):
            facts = {}

        cap: int | None = None
        reason = ""
        if facts.get("test_mode"):
            cap = 5
            reason = "用户明确表示只是测试、玩笑或虚构场景，当前实际危险降级。"
        elif facts.get("user_clarified_no_action"):
            cap = 25 if _has_request_facts(facts) else 15
            reason = "用户明确澄清没有下载、转账、输入验证码或执行对方指令。"
        elif facts.get("quoted_advice") and not has_executed_high_risk_action(conv_data):
            cap = 20
            reason = "用户正在复述处置建议，不能据此认定这些动作已经完成。"
        elif _is_privacy_only_context(facts):
            cap = 30 if facts.get("third_party_pii_request") or facts.get("pii_disclosed_to_third_party") else 15
            reason = "当前只涉及个人信息提供、回忆或被索要，未出现验证码、转账、远控或资金异常证据。"
        elif int(conv_data.get("safety_evidence_turns", 0) or 0) >= 2 and not has_executed_high_risk_action(conv_data):
            cap = 20
            reason = "用户已连续两轮提供安全处置完成证据，当前实时危险应降到低位。"
        elif _safe_evidence_count(facts) >= 4 and not has_executed_high_risk_action(conv_data):
            cap = 25
            reason = "用户已连续提供卸载、无扣款、拉黑、存证、告知亲友、改密或设备检查等收尾证据。"
        elif (
            facts.get("remote_control_removed")
            and not facts.get("verification_code_exposed")
            and not facts.get("already_paid")
            and (facts.get("no_transfer") or facts.get("no_abnormal_charge"))
        ):
            cap = 35
            reason = "可疑软件已卸载，且未确认验证码泄露、转账或异常扣款，当前实时危险受上限约束。"

        if cap is None or total_score <= cap:
            return (
                total_score,
                risk_level,
                self.risk_engine._build_intervention(risk_level, user_role),
                self.risk_engine._build_recommendations(risk_level),
                breakdown,
                all_matched_rules,
                conv_data,
            )

        total_score = cap
        risk_level = self.risk_engine._score_to_level(total_score)
        breakdown["evidence_cap"] = cap
        breakdown["evidence_cap_reason"] = reason
        breakdown["total"] = total_score
        all_matched_rules = [
            *all_matched_rules,
            {
                "rule": "evidence_based_deescalation",
                "evidence": [key for key, value in facts.items() if value],
                "weight": 0,
                "reason": reason,
                "rule_version": "1.0",
                "ruleset_version": "conversation-2.0",
                "rationale": "明确区分诈骗话术风险、用户实际执行状态和事后残留风险。",
            },
        ]
        conv_data = self._conv_state.recompute_stage(user_id, risk_level)
        return (
            total_score,
            risk_level,
            self.risk_engine._build_intervention(risk_level, user_role),
            self.risk_engine._build_recommendations(risk_level),
            breakdown,
            all_matched_rules,
            conv_data,
        )

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
            conv_data = self._conv_state.recompute_stage(
                self._conversation_key_for_request(request),
                risk_level,
            )

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
            allow_score_escalation=os.getenv("AI_RISK_SCORE_ESCALATION_ENABLED", "0").lower() in {"1", "true", "yes"},
            max_escalation_delta=int(os.getenv("AI_RISK_MAX_SCORE_DELTA", "10")),
        )
        breakdown["ai_assessment"] = merged.breakdown()
        if merged.matched_rule:
            all_matched_rules = [*all_matched_rules, merged.matched_rule]
        if merged.final_score != total_score:
            total_score = merged.final_score
            risk_level = merged.final_level
            breakdown["ai_score"] = merged.ai_score_delta
            breakdown["total"] = total_score
            conv_data = self._conv_state.recompute_stage(
                self._conversation_key_for_request(request),
                risk_level,
            )

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
        pii_memory: dict[str, str] | None = None,
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
        if stage == "test_mode":
            return (
                "收到，那我按测试/演示场景处理。因为你明确说没有真实下载、转账或开启屏幕共享，"
                "当前实际危险降到低位；这类话术本身仍值得标注为高诈骗可能。演示时可以继续发不同话术，"
                "我会区分“对方要求”和“你已经执行”。"
            )

        if stage == "clarifying":
            return (
                "明白，你已经澄清没有下载、没有转账，也没有按对方要求操作，所以当前实时危险先降下来。"
                "这不等于对方话术安全，只是说明还停在预防阶段。接下来不要下载会议/远控软件、不要开屏幕共享、"
                "不要输入验证码；如果只是测试，可以直接说“这是测试”。"
            )

        if stage == "action_confirmation":
            return (
                "你刚才这段更像是在复述待办清单，我不能默认这些动作已经完成。"
                "请你只回复一句：这些步骤是否已经完成，还是“只是复制给我看”？"
                "如果只是复制，我不会继续升级到更重的处置动作。"
            )

        if stage == "preventive_warning":
            return self._build_preventive_reply(role_prefix, matched_scams, known_facts or {})

        if stage == "privacy_reminder":
            return self._build_privacy_reply(intent, known_facts or {}, pii_memory or {})

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
    def _build_privacy_reply(
        intent: str,
        known_facts: dict[str, bool],
        pii_memory: dict[str, str],
    ) -> str:
        if intent == "self_pii_recall" or known_facts.get("self_pii_recall"):
            masked_phone = pii_memory.get("phone")
            if masked_phone:
                return (
                    f"你刚才提供过一个手机号。出于隐私安全，我建议只脱敏显示：{masked_phone}。"
                    "以后不要在陌生链接、陌生客服或不可信聊天里发送完整手机号，更不能发送验证码。"
                )
            return (
                "你刚才提到过个人信息，但我这边只建议按脱敏方式回忆和展示。"
                "如果是在陌生链接、陌生客服或不可信聊天里，对方要完整手机号或验证码，都先不要发。"
            )

        if known_facts.get("pii_disclosed_to_third_party"):
            return (
                "手机号这类个人信息已经发给对方，主要风险是后续骚扰、精准冒充客服或二次诈骗。"
                "目前如果没有验证码、支付密码、银行卡、转账、屏幕共享或异常扣款证据，先按隐私收尾处理即可。"
                "接下来留意陌生来电和短信，不再补发验证码、银行卡或支付密码。"
            )

        return (
            "对方索要手机号、身份证号或地址时要谨慎，先确认对方身份和官方渠道。"
            "单独的手机号索要属于个人信息泄露风险，不等于资金正在损失；不要继续提供验证码、支付密码、银行卡信息，也不要开屏幕共享。"
        )

    @staticmethod
    def _build_closure_check_reply(
        role_prefix: str,
        known_facts: dict[str, bool],
    ) -> str:
        if not known_facts.get("already_paid") and not known_facts.get("verification_code_exposed"):
            completed: list[str] = []
            labels = [
                ("remote_control_removed", "卸载或退出可疑软件"),
                ("no_abnormal_charge", "确认没有异常扣款"),
                ("blocked_contact", "拉黑对方"),
                ("evidence_saved", "保存证据"),
                ("trusted_person_informed", "告知家人或可信任的人"),
                ("password_changed", "修改重要密码"),
                ("device_checked_clean", "检查手机无异常后台或陌生应用"),
            ]
            for key, label in labels:
                if known_facts.get(key):
                    completed.append(label)
            done = "、".join(completed) if completed else "关键止损动作"
            return (
                f"{role_prefix}你已经完成了主要收尾动作：{done}。"
                "现在实时风险已经明显降低，不需要继续升级处理。"
                "接下来 24-48 小时留意账户流水，警惕冒充客服、警方或“追回损失”的二次诈骗即可；"
                "除非出现验证码泄露、资金异常、远程控制仍在进行或软件无法卸载，否则不需要做更激烈的手机或账户处置。"
            )

        parts = [f"{role_prefix}你已经在做正确的止损动作了，现在从“紧急阻断”转到收尾检查。"]
        if known_facts.get("reported_to_police") and not any(
            known_facts.get(key)
            for key in ("has_remote_control", "verification_code_exposed", "already_paid")
        ):
            parts.append("目前只确认你已经报警，尚不能认定你开过屏幕共享、泄露验证码或发生资金损失。")
        if known_facts.get("already_paid"):
            parts.append("确认银行或支付平台的止付/冻结是否受理，记录工单号或报警回执。")
        else:
            parts.append("接下来不要恢复联系、不要重新开启屏幕共享，也不要再点对方发来的链接。")
        if known_facts.get("verification_code_exposed"):
            parts.append("再检查一次账号安全：改密、退出陌生设备、关闭免密支付。")
        parts.append("把聊天记录、对方账号、链接和软件截图保存下来即可，不需要反复和对方周旋。")
        return "".join(parts)

    @staticmethod
    def _build_preventive_reply(
        role_prefix: str,
        matched_scams: list[dict[str, Any]],
        known_facts: dict[str, bool],
    ) -> str:
        scenario = ""
        if matched_scams:
            scenario = f"这类话术和“{matched_scams[0].get('name', '诈骗话术')}”相似。"
        if known_facts.get("has_remote_control_request"):
            return (
                f"{role_prefix}{scenario}目前我只看到“对方要求你下载/共享屏幕”，还不能认定你已经执行。"
                "先不要下载会议或远控软件，也不要开启屏幕共享；如果你已经开过，再告诉我，我会切到紧急阻断流程。"
            )
        if known_facts.get("has_transfer_request"):
            return (
                f"{role_prefix}{scenario}目前重点是对方提出了转账或缴费要求，但你还没说已经转出。"
                "先不要付款，不要扫对方二维码，核实渠道必须换成官方 App、官网或官方客服电话。"
            )
        if known_facts.get("has_verification_code_request"):
            return (
                f"{role_prefix}{scenario}对方索要验证码是高危信号，但只有在验证码已输入或被看到时才进入账号恢复流程。"
                "现在先不要输入验证码，也不要让对方看屏幕。"
            )
        return f"{role_prefix}{scenario}先暂停当前操作，通过官方渠道核实；如果没有执行风险动作，当前以预防提醒为主。"

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
            "停止当前付款、下载或验证码操作，与可信任的人二次确认",
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


def _max_history_risk_level(history: list[dict[str, str]]) -> str:
    level = "low"
    for item in history:
        level = _max_level(level, item.get("risk_level", "low"))
    return level


def _max_level(left: str, right: str | None) -> str:
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    left_value = order.get(str(left), 0)
    right_value = order.get(str(right), 0)
    return str(left if left_value >= right_value else right)


def _has_request_facts(facts: dict[str, Any]) -> bool:
    return any(
        facts.get(key)
        for key in {
            "has_transfer_request",
            "has_verification_code_request",
            "has_remote_control_request",
        }
    )


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


def _is_privacy_only_context(facts: dict[str, Any]) -> bool:
    has_privacy = any(
        facts.get(key)
        for key in {
            "self_pii_provide",
            "self_pii_recall",
            "third_party_pii_request",
            "pii_disclosed_to_third_party",
            "privacy_risk",
        }
    )
    has_emergency = any(
        facts.get(key)
        for key in {
            "already_paid",
            "verification_code_exposed",
            "has_remote_control",
            "has_transfer_request",
            "has_verification_code_request",
        }
    )
    return bool(has_privacy and not has_emergency)


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


def _reward_event_key(
    *,
    conv_data: dict,
    risk_level: str,
    current_scam_type: str,
) -> str:
    facts = conv_data.get("known_facts", {})
    fact_names = sorted(key for key, value in facts.items() if value) if isinstance(facts, dict) else []
    stage = str(conv_data.get("session_stage", ""))
    scam = current_scam_type or "unknown"
    if stage in {"active_blocking", "account_recovery", "loss_recovery", "closure_check"}:
        return f"{stage}:{scam}:{','.join(fact_names[:8])}"
    return f"{stage}:{risk_level}"
