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

    def list_scenarios(self) -> list[dict[str, str]]:
        return [
            {
                "id": scenario["id"],
                "title": scenario["title"],
                "scam_type": scenario["scam_type"],
            }
            for scenario in self._scenarios.values()
        ]

    def start(self, user_id: int, scenario_id: str) -> dict[str, Any]:
        scenario = self._scenarios.get(scenario_id)
        if not scenario:
            raise ValueError("未找到对应情景")

        self._sessions[user_id] = {"scenario_id": scenario_id, "step_index": 0}
        first_step = scenario["steps"][0]

        return {
            "scenario_id": scenario_id,
            "title": scenario["title"],
            "step_index": 0,
            "prompt": first_step["prompt"],
            "options": [opt["text"] for opt in first_step["options"]],
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
        option_points = int(selected.get("points", 0))
        reward_result = self.gamification.award(
            user_id,
            action="scenario_step",
            extra_points=option_points,
        )

        next_step_index = step_index + 1
        finished = next_step_index >= len(scenario["steps"])
        completion_bonus = 0

        next_prompt = None
        next_options: list[str] = []

        if finished:
            completion_result = self.gamification.award(user_id, action="scenario_complete")
            completion_bonus = int(completion_result["points_gained"])
            reward_result = completion_result
            self._sessions.pop(user_id, None)
        else:
            session["step_index"] = next_step_index
            next_step = scenario["steps"][next_step_index]
            next_prompt = next_step["prompt"]
            next_options = [opt["text"] for opt in next_step["options"]]

        return {
            "scenario_id": scenario_id,
            "step_index": step_index,
            "finished": finished,
            "feedback": selected["feedback"],
            "points_gained": option_points + completion_bonus,
            "total_points": int(reward_result["total_points"]),
            "badges": list(reward_result["badges"]),
            "next_prompt": next_prompt,
            "next_options": next_options,
        }
