from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.storage import SQLiteStorage


class GamificationService:
    def __init__(self, storage: "SQLiteStorage | None" = None) -> None:
        self.storage = storage
        self._states: dict[str, dict[str, object]] = {}
        self._action_points = {
            "knowledge_query": 5,
            "daily_chat": 2,
            "report_submit": 12,
            "risk_block": 20,
            "scenario_step": 0,
            "scenario_complete": 15,
        }

    def _ensure_state(self, user_id: int) -> dict[str, object]:
        if user_id not in self._states:
            loaded_state = self.storage.load_user_state(user_id) if self.storage else None
            if loaded_state:
                self._states[user_id] = loaded_state
            else:
                self._states[user_id] = {
                    "points": 0,
                    "level": 1,
                    "badges": [],
                    "reports_submitted": 0,
                    "scenarios_completed": 0,
                    "high_risk_blocks": 0,
                    "knowledge_queries": 0,
                }
        return self._states[user_id]

    def award(
        self,
        user_id: int,
        action: str,
        risk_level: str | None = None,
        extra_points: int = 0,
    ) -> dict[str, object]:
        state = self._ensure_state(user_id)
        base_points = int(self._action_points.get(action, 0))
        gained = base_points + max(0, extra_points)

        if action == "report_submit":
            state["reports_submitted"] = int(state["reports_submitted"]) + 1
        if action == "knowledge_query":
            state["knowledge_queries"] = int(state["knowledge_queries"]) + 1
        if action == "scenario_complete":
            state["scenarios_completed"] = int(state["scenarios_completed"]) + 1
        if action == "risk_block" and risk_level in {"high", "critical"}:
            state["high_risk_blocks"] = int(state["high_risk_blocks"]) + 1

        state["points"] = int(state["points"]) + gained
        state["level"] = int(state["points"]) // 100 + 1
        state["badges"] = self._refresh_badges(state)
        self._persist(user_id, state)

        return {
            "points_gained": gained,
            "total_points": int(state["points"]),
            "level": int(state["level"]),
            "badges": list(state["badges"]),
        }

    def profile(self, user_id: int) -> dict[str, object]:
        state = self._ensure_state(user_id)
        return {
            "user_id": user_id,
            "level": int(state["level"]),
            "points": int(state["points"]),
            "badges": list(state["badges"]),
            "reports_submitted": int(state["reports_submitted"]),
            "scenarios_completed": int(state["scenarios_completed"]),
        }

    @staticmethod
    def _refresh_badges(state: dict[str, object]) -> list[str]:
        badges: list[str] = []
        if int(state["reports_submitted"]) >= 1:
            badges.append("线索侦察员")
        if int(state["points"]) >= 50:
            badges.append("反诈新兵")
        if int(state["points"]) >= 150:
            badges.append("风险守门人")
        if int(state["scenarios_completed"]) >= 3:
            badges.append("情景闯关达人")
        if int(state["high_risk_blocks"]) >= 2:
            badges.append("冷静止损王")
        return badges

    def _persist(self, user_id: int, state: dict[str, object]) -> None:
        if self.storage:
            self.storage.save_user_state(user_id, state)
