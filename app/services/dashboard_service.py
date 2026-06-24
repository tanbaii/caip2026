from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.knowledge_base import KnowledgeBase
from app.services.rule_management import RuleManagementService
from app.services.storage import SQLiteStorage


class DashboardService:
    def __init__(
        self,
        *,
        storage: SQLiteStorage,
        knowledge_base: KnowledgeBase,
        rule_management: RuleManagementService,
    ) -> None:
        self.storage = storage
        self.knowledge_base = knowledge_base
        self.rule_management = rule_management

    def summary(self) -> dict[str, Any]:
        snapshot = self.storage.dashboard_snapshot()
        overview = self.rule_management.overview()
        history = self.rule_management.history(limit=8)
        scams = self.knowledge_base.scams
        laws = self.knowledge_base.laws
        sourced_scams = [item for item in scams if item.get("sources")]

        text_rules = overview.get("text_rules", [])
        url_rules = overview.get("url_rules", [])
        enabled_text = [rule for rule in text_rules if rule.get("enabled", True)]
        enabled_url = [rule for rule in url_rules if rule.get("enabled", True)]

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "users": snapshot["users"],
            "engagement": snapshot["engagement"],
            "reports": snapshot["reports"],
            "scenarios": snapshot["scenarios"],
            "knowledge": {
                "scam_count": len(scams),
                "law_count": len(laws),
                "sourced_scam_count": len(sourced_scams),
                "source_organizations": self._source_organizations(sourced_scams),
                "coverage": self.knowledge_base.meta.get("coverage", []),
            },
            "rules": {
                "active_revision": overview["active_revision"],
                "versions": overview["ruleset_versions"],
                "text_rule_count": len(text_rules),
                "url_rule_count": len(url_rules),
                "enabled_text_rule_count": len(enabled_text),
                "enabled_url_rule_count": len(enabled_url),
                "disabled_rule_count": len(text_rules) + len(url_rules) - len(enabled_text) - len(enabled_url),
                "recent_changes": history,
            },
        }

    @staticmethod
    def _source_organizations(scams: list[dict[str, Any]]) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for scam in scams:
            for source in scam.get("sources", []):
                if not isinstance(source, dict):
                    continue
                organization = str(source.get("organization") or "未知来源")
                counts[organization] = counts.get(organization, 0) + 1
        return [
            {"organization": organization, "count": count}
            for organization, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]
