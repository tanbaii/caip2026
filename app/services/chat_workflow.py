from __future__ import annotations

import time
from typing import Any, TypedDict

from app.models.schemas import ChatRequest
from app.services.dialogue_service import (
    _build_chat_next_actions,
    _build_conversation_summary,
    _is_new_explicit_scam_topic,
    _last_history_score,
    _top_scam_type,
)
from app.services.sanitizer import sanitize_text

try:  # pragma: no cover - exercised when langgraph is installed in deployment.
    from langgraph.graph import END, START, StateGraph
except Exception:  # pragma: no cover - local tests run without optional dependency.
    END = START = None
    StateGraph = None


class ChatWorkflowState(TypedDict, total=False):
    request: ChatRequest
    start_time: float
    history: list[dict[str, str]]
    intent: str
    matched_scams: list[dict[str, Any]]
    matched_names: list[str]
    current_scam_type: str
    risk: dict[str, Any]
    url_bonus: int
    all_matched_rules: list[dict[str, Any]]
    total_score: int
    risk_level: str
    intervention_script: list[str]
    recommendations: list[str]
    breakdown: dict[str, Any]
    conv_data: dict[str, Any]
    retrieved_knowledge: list[dict[str, Any]]
    reply: str
    action: str
    reward: dict[str, Any]
    response: dict[str, Any]


class ChatWorkflowRunner:
    """LangGraph orchestration wrapper for the existing DialogueService.

    RiskEngine remains the only risk scorer. LangGraph only makes the flow
    explicit and easier to extend with routing/observability later.
    """

    def __init__(self, dialogue_service: Any) -> None:
        self.service = dialogue_service
        self.engine = "sequential"
        self._graph = self._compile_graph()

    def process_chat(self, request: ChatRequest) -> dict[str, Any]:
        initial_state: ChatWorkflowState = {
            "request": request,
            "start_time": time.perf_counter(),
        }
        if self._graph is not None:
            final_state = self._graph.invoke(initial_state)
        else:
            final_state = self._invoke_sequential(initial_state)
        return final_state["response"]

    def reset_conversation(self, user_id: int) -> None:
        self.service.reset_conversation(user_id)

    def _compile_graph(self) -> Any | None:
        if StateGraph is None:
            return None

        builder = StateGraph(ChatWorkflowState)
        builder.add_node("recognize_context", self._recognize_context)
        builder.add_node("evaluate_risk", self._evaluate_risk)
        builder.add_node("update_conversation", self._update_conversation)
        builder.add_node("retrieve_knowledge", self._retrieve_knowledge)
        builder.add_node("generate_reply", self._generate_reply)
        builder.add_node("award_and_persist", self._award_and_persist)
        builder.add_node("build_response", self._build_response)

        builder.add_edge(START, "recognize_context")
        builder.add_edge("recognize_context", "evaluate_risk")
        builder.add_edge("evaluate_risk", "update_conversation")
        builder.add_edge("update_conversation", "retrieve_knowledge")
        builder.add_edge("retrieve_knowledge", "generate_reply")
        builder.add_edge("generate_reply", "award_and_persist")
        builder.add_edge("award_and_persist", "build_response")
        builder.add_edge("build_response", END)

        self.engine = "langgraph"
        return builder.compile()

    def _invoke_sequential(self, state: ChatWorkflowState) -> ChatWorkflowState:
        for node in (
            self._recognize_context,
            self._evaluate_risk,
            self._update_conversation,
            self._retrieve_knowledge,
            self._generate_reply,
            self._award_and_persist,
            self._build_response,
        ):
            state.update(node(state))
        return state

    def _recognize_context(self, state: ChatWorkflowState) -> dict[str, Any]:
        request = state["request"]
        history = self.service._history.get(request.user_id, [])

        intent, _, _ = self.service.intent_recognizer.detect_intent(request.message, history)
        matched_scams = self.service.knowledge_base.search_scams(request.message)
        current_scam_type = _top_scam_type(matched_scams)

        if _is_new_explicit_scam_topic(history, current_scam_type):
            history = []
            self.service._history[request.user_id] = []
            self.service._conv_state.reset(request.user_id)
            intent, _, _ = self.service.intent_recognizer.detect_intent(request.message, history)

        return {
            "history": history,
            "intent": intent,
            "matched_scams": matched_scams,
            "matched_names": [item["name"] for item in matched_scams],
            "current_scam_type": current_scam_type,
        }

    def _evaluate_risk(self, state: ChatWorkflowState) -> dict[str, Any]:
        request = state["request"]
        risk = self.service.risk_engine.evaluate_text(
            request.message,
            state["matched_scams"],
            request.user_profile.role,
            request.emotion,
        )

        url_bonus = 0
        all_matched_rules = list(risk.get("matched_rules", []))
        for url in self.service._url_pattern.findall(request.message):
            url_risk = self.service.risk_engine.evaluate_url(url)
            if int(url_risk["score"]) >= 25:
                risk["reasons"].append(f"检测到可疑链接: {url}")
                url_bonus += 10
            all_matched_rules.extend(url_risk.get("matched_rules", []))

        total_score = int(risk["score"]) + url_bonus
        risk_level = self.service.risk_engine._score_to_level(total_score)
        breakdown = dict(risk.get("risk_breakdown", {}))
        breakdown["url_score"] = url_bonus
        breakdown["total"] = total_score

        return {
            "risk": risk,
            "url_bonus": url_bonus,
            "all_matched_rules": all_matched_rules,
            "total_score": total_score,
            "risk_level": risk_level,
            "intervention_script": self.service.risk_engine._build_intervention(
                risk_level, request.user_profile.role
            ),
            "recommendations": self.service.risk_engine._build_recommendations(risk_level),
            "breakdown": breakdown,
        }

    def _update_conversation(self, state: ChatWorkflowState) -> dict[str, Any]:
        request = state["request"]
        total_score = state["total_score"]
        risk_level = state["risk_level"]
        breakdown = dict(state["breakdown"])
        all_matched_rules = list(state["all_matched_rules"])
        risk = dict(state["risk"])

        conv_data = self.service._conv_state.update_and_get(
            user_id=request.user_id,
            message=request.message,
            risk_level=risk_level,
            intent=state["intent"],
            matched_scams=state["matched_scams"],
        )
        conv_bonus, conv_rules, conv_reasons = self.service._conv_state.compute_conversation_bonus(
            request.user_id
        )

        if conv_bonus > 0:
            total_score += conv_bonus
            all_matched_rules.extend(conv_rules)
            risk.setdefault("reasons", []).extend(conv_reasons)
            breakdown["conversation_score"] = conv_bonus
            breakdown["total"] = total_score
            risk_level = self.service.risk_engine._score_to_level(total_score)
            conv_data = self.service._conv_state.recompute_stage(request.user_id, risk_level)

        previous_score = _last_history_score(state["history"])
        if previous_score is not None and previous_score > total_score:
            total_score = previous_score
            breakdown["context_score_floor"] = previous_score
            breakdown["total"] = total_score
            risk_level = self.service.risk_engine._score_to_level(total_score)
            conv_data = self.service._conv_state.recompute_stage(request.user_id, risk_level)

        return {
            "risk": risk,
            "all_matched_rules": all_matched_rules,
            "total_score": total_score,
            "risk_level": risk_level,
            "intervention_script": self.service.risk_engine._build_intervention(
                risk_level, request.user_profile.role
            ),
            "recommendations": self.service.risk_engine._build_recommendations(risk_level),
            "breakdown": breakdown,
            "conv_data": conv_data,
        }

    def _retrieve_knowledge(self, state: ChatWorkflowState) -> dict[str, Any]:
        return {"retrieved_knowledge": self.service._retrieve_knowledge(state["request"].message)}

    def _generate_reply(self, state: ChatWorkflowState) -> dict[str, Any]:
        request = state["request"]
        conv_data = state["conv_data"]
        reply = self.service._build_reply(
            message=request.message,
            intent=state["intent"],
            matched_scams=state["matched_scams"],
            risk_level=state["risk_level"],
            user_role=request.user_profile.role,
            stage=conv_data["session_stage"],
            pending_questions=conv_data["pending_questions"],
            known_facts=conv_data["known_facts"],
            turn_count=conv_data["turn_count"],
        )

        if self.service.rag_reply_generator:
            reply = self.service.rag_reply_generator.generate(
                message=request.message,
                risk_context={
                    "risk_score": state["total_score"],
                    "risk_level": state["risk_level"],
                    "matched_rules": state["all_matched_rules"],
                    "risk_breakdown": state["breakdown"],
                    "intervention_script": state["intervention_script"],
                    "recommendations": state["recommendations"],
                },
                retrieved_knowledge=state["retrieved_knowledge"],
                fallback_reply=reply,
            )

        return {"reply": reply}

    def _award_and_persist(self, state: ChatWorkflowState) -> dict[str, Any]:
        request = state["request"]
        risk_level = state["risk_level"]
        intent = state["intent"]

        action = "daily_chat"
        if risk_level in {"high", "critical"}:
            action = "risk_block"
        elif intent in {"ask_knowledge", "report_content"}:
            action = "knowledge_query"

        reward = self.service.gamification.award(
            request.user_id,
            action=action,
            risk_level=risk_level,
        )

        new_history = state["history"] + [
            {
                "message": sanitize_text(request.message),
                "intent": intent,
                "risk_level": risk_level,
                "risk_score": str(state["total_score"]),
                "scam_type": state["current_scam_type"],
            }
        ]
        self.service._history[request.user_id] = new_history[-12:]

        return {
            "action": action,
            "reward": reward,
        }

    def _build_response(self, state: ChatWorkflowState) -> dict[str, Any]:
        reward = state["reward"]
        conv_data = state["conv_data"]
        latency_ms = round((time.perf_counter() - state["start_time"]) * 1000, 2)

        return {
            "response": {
                "reply": state["reply"],
                "intent": state["intent"],
                "matched_scams": state["matched_names"],
                "risk_level": state["risk_level"],
                "risk_score": state["total_score"],
                "intervention_script": state["intervention_script"],
                "recommendations": state["recommendations"],
                "points_gained": int(reward["points_gained"]),
                "total_points": int(reward["total_points"]),
                "badges": list(reward["badges"]),
                "latency_ms": latency_ms,
                "matched_rules": state["all_matched_rules"],
                "risk_breakdown": state["breakdown"],
                "next_actions": _build_chat_next_actions(state["risk_level"]),
                "session_stage": conv_data["session_stage"],
                "known_facts": conv_data["known_facts"],
                "pending_questions": conv_data["pending_questions"],
                "conversation_summary": _build_conversation_summary(conv_data),
                "turn_count": conv_data["turn_count"],
                "retrieved_knowledge": state["retrieved_knowledge"],
            }
        }
