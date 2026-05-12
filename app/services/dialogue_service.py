from __future__ import annotations

import re
import time
from typing import Any

from app.models.schemas import ChatRequest
from app.services.gamification import GamificationService
from app.services.intent_recognizer import IntentRecognizer
from app.services.knowledge_base import KnowledgeBase
from app.services.risk_engine import RiskEngine


class DialogueService:
    def __init__(
        self,
        knowledge_base: KnowledgeBase,
        intent_recognizer: IntentRecognizer,
        risk_engine: RiskEngine,
        gamification: GamificationService,
    ) -> None:
        self.knowledge_base = knowledge_base
        self.intent_recognizer = intent_recognizer
        self.risk_engine = risk_engine
        self.gamification = gamification
        self._history: dict[str, list[dict[str, str]]] = {}
        self._url_pattern = re.compile(r"(https?://\S+|www\.\S+)", re.IGNORECASE)

    def process_chat(self, request: ChatRequest) -> dict[str, Any]:
        start_time = time.perf_counter()
        history = self._history.get(request.user_id, [])

        intent, _, _ = self.intent_recognizer.detect_intent(request.message, history)
        matched_scams = self.knowledge_base.search_scams(request.message)
        matched_names = [item["name"] for item in matched_scams]

        risk = self.risk_engine.evaluate_text(
            request.message,
            matched_scams,
            request.user_profile.role,
            request.emotion,
        )

        for url in self._url_pattern.findall(request.message):
            url_risk = self.risk_engine.evaluate_url(url)
            if int(url_risk["score"]) >= 25:
                risk["reasons"].append(f"检测到可疑链接: {url}")
                risk["score"] = int(risk["score"]) + 10

        risk_level = self.risk_engine._score_to_level(int(risk["score"]))
        intervention_script = self.risk_engine._build_intervention(risk_level, request.user_profile.role)
        recommendations = self.risk_engine._build_recommendations(risk_level)

        reply = self._build_reply(
            message=request.message,
            intent=intent,
            matched_scams=matched_scams,
            risk_level=risk_level,
            user_role=request.user_profile.role,
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
                "message": request.message,
                "intent": intent,
                "risk_level": risk_level,
            }
        ]
        self._history[request.user_id] = new_history[-12:]

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return {
            "reply": reply,
            "intent": intent,
            "matched_scams": matched_names,
            "risk_level": risk_level,
            "risk_score": int(risk["score"]),
            "intervention_script": intervention_script,
            "recommendations": recommendations,
            "points_gained": int(reward["points_gained"]),
            "total_points": int(reward["total_points"]),
            "badges": list(reward["badges"]),
            "latency_ms": latency_ms,
        }

    def _build_reply(
        self,
        message: str,
        intent: str,
        matched_scams: list[dict[str, Any]],
        risk_level: str,
        user_role: str,
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

        if intent == "ask_knowledge":
            return f"{core}如果你愿意，我还能给你一个30秒自检清单，帮助快速判断是否诈骗。"

        if re.search(r"(转账|验证码|付款|链接)", message):
            return f"{core}涉及资金和账号信息时，请务必先核验身份与平台真伪。"

        return f"{core}你也可以发“来一关模拟”进入情景训练。"
