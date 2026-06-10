from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.gamification import GamificationService


class ScenarioService:
    def __init__(self, data_path: Path, gamification: GamificationService) -> None:
        self.gamification = gamification
        with data_path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        self._scenarios: dict[str, dict[str, Any]] = {
            item["id"]: item for item in data.get("scenarios", [])
        }
        self._sessions: dict[str, dict[str, Any]] = {}

    def list_scenarios(self) -> list[dict[str, Any]]:
        return [
            {
                "id": scenario["id"],
                "title": scenario["title"],
                "scam_type": scenario["scam_type"],
                "mode": scenario.get("mode", "quiz"),
                "story": scenario.get("story"),
                "objectives": scenario.get("objectives", []),
                "max_score": self._max_score(scenario),
                "completion_bonus": self.gamification.scenario_completion_bonus,
            }
            for scenario in self._scenarios.values()
        ]

    def start(self, user_id: int, scenario_id: str) -> dict[str, Any]:
        scenario = self._scenarios.get(scenario_id)
        if not scenario:
            raise ValueError("未找到对应情景")

        self._sessions[user_id] = {
            "scenario_id": scenario_id,
            "step_index": 0,
            "run_score": 0,
        }
        first_step = scenario["steps"][0]
        progress = self.gamification.scenario_progress(user_id, scenario_id)

        return {
            "scenario_id": scenario_id,
            "title": scenario["title"],
            "step_index": 0,
            "prompt": first_step["prompt"],
            "options": [opt["text"] for opt in first_step["options"]],
            "mode": scenario.get("mode", "quiz"),
            "story": scenario.get("story"),
            "role": scenario.get("role"),
            "characters": scenario.get("characters", []),
            "clues": scenario.get("clues", []),
            "objectives": scenario.get("objectives", []),
            "total_steps": len(scenario["steps"]),
            "max_score": self._max_score(scenario),
            "previous_best": int(progress["best_score"]) if progress else 0,
            "attempts": int(progress["attempts"]) if progress else 0,
            "completed": progress is not None,
        }

    def answer(self, user_id: int, option_index: int) -> dict[str, Any]:
        session = self._sessions.get(user_id)
        if not session:
            raise ValueError("请先开始情景闯关")

        scenario_id = str(session["scenario_id"])
        step_index = int(session["step_index"])
        scenario = self._scenarios[scenario_id]
        step = scenario["steps"][step_index]

        if option_index < 0 or option_index >= len(step["options"]):
            raise ValueError("选项序号无效")

        selected = step["options"][option_index]
        option_points = max(0, int(selected.get("points", 0)))
        session["run_score"] = int(session.get("run_score", 0)) + option_points
        run_score = int(session["run_score"])
        max_score = self._max_score(scenario)

        next_step_index = step_index + 1
        finished = next_step_index >= len(scenario["steps"])
        next_prompt = None
        next_options: list[str] = []

        if finished:
            reward_result = self.gamification.complete_scenario(
                user_id=user_id,
                scenario_id=scenario_id,
                score=run_score,
                max_score=max_score,
            )
            self._sessions.pop(user_id, None)
        else:
            reward_result = self.gamification.profile(user_id)
            session["step_index"] = next_step_index
            next_step = scenario["steps"][next_step_index]
            next_prompt = next_step["prompt"]
            next_options = [opt["text"] for opt in next_step["options"]]

        result: dict[str, Any] = {
            "scenario_id": scenario_id,
            "step_index": step_index,
            "finished": finished,
            "feedback": selected["feedback"],
            "points_gained": int(reward_result.get("points_gained", 0)),
            "total_points": int(reward_result.get("total_points", reward_result.get("points", 0))),
            "badges": list(reward_result["badges"]),
            "new_badges": list(reward_result.get("new_badges", [])),
            "next_prompt": next_prompt,
            "next_options": next_options,
            "total_steps": len(scenario["steps"]),
            "run_score": run_score,
            "max_score": max_score,
            "score_percent": round(run_score / max_score * 100) if max_score > 0 else 0,
            "best_score": int(reward_result.get("best_score", 0)),
            "first_clear": bool(reward_result.get("first_clear", False)),
            "score_improvement": int(reward_result.get("score_improvement", 0)),
            "attempts": int(reward_result.get("attempts", 0)),
            "completions": int(reward_result.get("completions", 0)),
        }

        if finished:
            result["case_summary"] = scenario.get("case_summary")
            result["debrief"] = scenario.get("debrief", [])

        return result

    @staticmethod
    def _max_score(scenario: dict[str, Any]) -> int:
        return sum(
            max((int(option.get("points", 0)) for option in step.get("options", [])), default=0)
            for step in scenario.get("steps", [])
        )
