from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class KnowledgeBase:
    def __init__(self, data_path: Path) -> None:
        self.data_path = data_path
        self._data = self._load_data()

    def _load_data(self) -> dict[str, Any]:
        with self.data_path.open("r", encoding="utf-8") as fp:
            return json.load(fp)

    def _save_data(self) -> None:
        with self.data_path.open("w", encoding="utf-8") as fp:
            json.dump(self._data, fp, ensure_ascii=False, indent=2)

    @property
    def scams(self) -> list[dict[str, Any]]:
        return self._data.get("scams", [])

    @property
    def laws(self) -> list[dict[str, Any]]:
        return self._data.get("laws", [])

    def search_scams(self, text: str, limit: int = 3) -> list[dict[str, Any]]:
        text_lower = text.lower()
        scored_entries: list[tuple[int, dict[str, Any]]] = []

        for scam in self.scams:
            score = 0
            for keyword in scam.get("keywords", []):
                if keyword.lower() in text_lower:
                    score += 3
            for flag in scam.get("red_flags", []):
                for token in flag.split("、"):
                    if token and token.lower() in text_lower:
                        score += 1
            if score > 0:
                scored_entries.append((score, scam))

        scored_entries.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored_entries[:limit]]

    def get_scam_by_type(self, scam_type: str) -> dict[str, Any] | None:
        for scam in self.scams:
            if scam.get("type") == scam_type:
                return scam
        return None

    def add_scam(self, new_scam: dict[str, Any]) -> None:
        for scam in self.scams:
            if scam.get("id") == new_scam.get("id"):
                raise ValueError("骗局ID已存在")
            if scam.get("type") == new_scam.get("type"):
                raise ValueError("骗局type已存在")

        self._data.setdefault("scams", []).append(new_scam)
        self._save_data()
