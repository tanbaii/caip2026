from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.storage import SQLiteStorage


class GamificationService:
    def __init__(self, storage: "SQLiteStorage | None" = None) -> None:
        self.storage = storage
        self._states: dict[int, dict[str, object]] = {}
        self._scenario_records: dict[str, dict[str, object]] = {}
        self._action_points = {
            "knowledge_query": 5,
            "daily_chat": 2,
            "report_submit": 12,
            "risk_block": 20,
            "scenario_step": 0,
            "scenario_complete": 15,
        }

    @property
    def scenario_completion_bonus(self) -> int:
        return int(self._action_points["scenario_complete"])

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
        scenario_progress = self.storage.list_scenario_progress(user_id) if self.storage else [
            record
            for key, record in self._scenario_records.items()
            if key.startswith(f"{user_id}:")
        ]
        if scenario_progress:
            state["scenarios_completed"] = len(scenario_progress)
        return {
            "user_id": user_id,
            "level": int(state["level"]),
            "points": int(state["points"]),
            "badges": list(state["badges"]),
            "reports_submitted": int(state["reports_submitted"]),
            "scenarios_completed": int(state["scenarios_completed"]),
            "high_risk_blocks": int(state["high_risk_blocks"]),
            "scenario_progress": scenario_progress,
        }

    def complete_scenario(
        self,
        user_id: int,
        scenario_id: str,
        score: int,
        max_score: int,
    ) -> dict[str, object]:
        state = self._ensure_state(user_id)
        previous_badges = set(str(item) for item in state["badges"])

        if self.storage:
            progress = self.storage.record_scenario_completion(
                user_id=user_id,
                scenario_id=scenario_id,
                score=score,
                max_score=max_score,
                completion_bonus=self.scenario_completion_bonus,
            )
            state["scenarios_completed"] = int(progress["unique_completed"])
        else:
            key = f"{user_id}:{scenario_id}"
            record = self._scenario_records.get(key)
            first_clear = record is None
            previous_best = int(record["best_score"]) if record else 0
            improvement = max(0, score - previous_best)
            points_gained = improvement + (self.scenario_completion_bonus if first_clear else 0)
            progress = {
                "scenario_id": scenario_id,
                "first_clear": first_clear,
                "previous_best": previous_best,
                "score_improvement": improvement,
                "points_gained": points_gained,
                "attempts": int(record["attempts"]) + 1 if record else 1,
                "completions": int(record["completions"]) + 1 if record else 1,
                "best_score": max(score, previous_best),
                "max_score": max_score,
                "points_earned": int(record["points_earned"]) + points_gained if record else points_gained,
                "unique_completed": int(state["scenarios_completed"]) + (1 if first_clear else 0),
            }
            self._scenario_records[key] = progress
            state["scenarios_completed"] = int(progress["unique_completed"])

        points_gained = int(progress["points_gained"])
        state["points"] = int(state["points"]) + points_gained
        state["level"] = int(state["points"]) // 100 + 1
        state["badges"] = self._refresh_badges(state)
        self._persist(user_id, state)

        badges = list(str(item) for item in state["badges"])
        new_badges = [badge for badge in badges if badge not in previous_badges]
        return {
            **progress,
            "total_points": int(state["points"]),
            "level": int(state["level"]),
            "badges": badges,
            "new_badges": new_badges,
        }

    def scenario_progress(self, user_id: int, scenario_id: str) -> dict[str, object] | None:
        if self.storage:
            return self.storage.get_scenario_progress(user_id, scenario_id)
        return self._scenario_records.get(f"{user_id}:{scenario_id}")

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
