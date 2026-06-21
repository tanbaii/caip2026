from __future__ import annotations

import re
import threading
from copy import deepcopy
from datetime import date
from typing import Any

from app.services.risk_engine import RiskEngine
from app.services.storage import SQLiteStorage


class RuleManagementService:
    def __init__(self, risk_engine: RiskEngine, storage: SQLiteStorage) -> None:
        self.risk_engine = risk_engine
        self.storage = storage
        self._lock = threading.RLock()
        self._bootstrap()

    def _bootstrap(self) -> None:
        active = self.storage.get_active_rule_version()
        if active:
            repo_risk_cfg, repo_url_cfg = self.risk_engine.export_configs()
            if self._should_sync_repository_config(active):
                self.storage.create_rule_version(
                    action="sync",
                    change_summary="同步仓库规则配置更新",
                    text_version=self.risk_engine.risk_ruleset_version,
                    url_version=self.risk_engine.url_ruleset_version,
                    risk_config=repo_risk_cfg,
                    url_config=repo_url_cfg,
                    source_version_id=active["id"],
                )
                return
            self.risk_engine.apply_configs(active["risk_config"], active["url_config"])
            return
        risk_cfg, url_cfg = self.risk_engine.export_configs()
        self.storage.create_rule_version(
            action="bootstrap",
            change_summary="从仓库配置初始化规则管理",
            text_version=self.risk_engine.risk_ruleset_version,
            url_version=self.risk_engine.url_ruleset_version,
            risk_config=risk_cfg,
            url_config=url_cfg,
        )

    def overview(self) -> dict[str, Any]:
        active = self.storage.get_active_rule_version()
        if active is None:
            raise RuntimeError("未找到生效中的规则版本")
        risk_cfg, url_cfg = self.risk_engine.export_configs()
        return {
            "active_revision": self._version_summary(active),
            "ruleset_versions": self.risk_engine.ruleset_versions,
            "text_rules": [self._public_rule(rule, "text") for rule in risk_cfg["text_rules"]],
            "url_rules": [self._public_rule(rule, "url") for rule in url_cfg["checks"]],
        }

    def history(self, limit: int = 30) -> list[dict[str, Any]]:
        return self.storage.list_rule_versions(limit=limit)

    def update_rule(
        self,
        ruleset: str,
        rule_name: str,
        *,
        enabled: bool | None,
        weight: int | None,
        change_note: str,
    ) -> dict[str, Any]:
        if enabled is None and weight is None:
            raise ValueError("enabled 和 weight 至少修改一项")
        with self._lock:
            risk_cfg, url_cfg = self.risk_engine.export_configs()
            rules, cfg = self._select_rules(ruleset, risk_cfg, url_cfg)
            rule = next((item for item in rules if item.get("name") == rule_name), None)
            if rule is None:
                raise ValueError(f"规则不存在: {rule_name}")
            changes: list[str] = []
            if enabled is not None and bool(rule.get("enabled", True)) != enabled:
                rule["enabled"] = enabled
                changes.append("启用" if enabled else "停用")
            if weight is not None and int(rule.get("weight", 0)) != weight:
                rule["weight"] = weight
                changes.append(f"权重调整为 {weight}")
            if not changes:
                raise ValueError("规则配置没有发生变化")
            self._bump_ruleset(cfg)
            return self._publish(
                risk_cfg,
                url_cfg,
                action="update",
                summary=f"{ruleset}:{rule_name} {'、'.join(changes)}；{change_note}",
            )

    def add_text_rule(self, rule: dict[str, Any], change_note: str) -> dict[str, Any]:
        with self._lock:
            risk_cfg, url_cfg = self.risk_engine.export_configs()
            if any(item.get("name") == rule.get("name") for item in risk_cfg["text_rules"]):
                raise ValueError(f"规则名称已存在: {rule.get('name')}")
            normalized = deepcopy(rule)
            normalized["enabled"] = bool(normalized.get("enabled", True))
            risk_cfg["text_rules"].append(normalized)
            self._bump_ruleset(risk_cfg)
            return self._publish(
                risk_cfg,
                url_cfg,
                action="create",
                summary=f"新增文本骗局规则 {normalized['name']}；{change_note}",
            )

    def rollback(self, version_id: int, change_note: str) -> dict[str, Any]:
        with self._lock:
            target = self.storage.get_rule_version(version_id)
            if target is None:
                raise ValueError("目标规则版本不存在")
            return self._publish(
                target["risk_config"],
                target["url_config"],
                action="rollback",
                summary=f"回滚至修订 #{version_id}；{change_note}",
                source_version_id=version_id,
            )

    def _publish(
        self,
        risk_cfg: dict[str, Any],
        url_cfg: dict[str, Any],
        *,
        action: str,
        summary: str,
        source_version_id: int | None = None,
    ) -> dict[str, Any]:
        RiskEngine.validate_configs(risk_cfg, url_cfg)
        previous = self.storage.get_active_rule_version()
        version = self.storage.create_rule_version(
            action=action,
            change_summary=summary.strip("； "),
            text_version=str(risk_cfg["_meta"]["version"]),
            url_version=str(url_cfg["_meta"]["version"]),
            risk_config=risk_cfg,
            url_config=url_cfg,
            source_version_id=source_version_id,
        )
        try:
            self.risk_engine.apply_configs(risk_cfg, url_cfg)
        except Exception:
            if previous:
                self.storage.create_rule_version(
                    action="recovery",
                    change_summary=f"发布修订 #{version['id']} 失败，自动恢复",
                    text_version=previous["text_version"],
                    url_version=previous["url_version"],
                    risk_config=previous["risk_config"],
                    url_config=previous["url_config"],
                    source_version_id=previous["id"],
                )
                self.risk_engine.apply_configs(previous["risk_config"], previous["url_config"])
            raise
        return self.overview()

    def _should_sync_repository_config(self, active: dict[str, Any]) -> bool:
        repository_managed = str(active.get("action", "")) in {"bootstrap", "sync"}
        if not repository_managed:
            return False
        return (
            self._version_tuple(self.risk_engine.risk_ruleset_version)
            > self._version_tuple(active.get("text_version", ""))
            or self._version_tuple(self.risk_engine.url_ruleset_version)
            > self._version_tuple(active.get("url_version", ""))
        )

    @staticmethod
    def _version_tuple(version: object) -> tuple[int, int, int]:
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", str(version))
        if not match:
            return (0, 0, 0)
        return tuple(int(value) for value in match.groups())

    @staticmethod
    def _select_rules(
        ruleset: str,
        risk_cfg: dict[str, Any],
        url_cfg: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if ruleset == "text":
            return risk_cfg["text_rules"], risk_cfg
        if ruleset == "url":
            return url_cfg["checks"], url_cfg
        raise ValueError("ruleset 仅支持 text 或 url")

    @staticmethod
    def _bump_ruleset(cfg: dict[str, Any]) -> None:
        meta = cfg.setdefault("_meta", {})
        current = str(meta.get("version", "1.0.0"))
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", current)
        if match:
            major, minor, patch = (int(value) for value in match.groups())
            meta["version"] = f"{major}.{minor}.{patch + 1}"
        else:
            meta["version"] = f"{current}.1"
        meta["updated"] = date.today().isoformat()

    @staticmethod
    def _public_rule(rule: dict[str, Any], ruleset: str) -> dict[str, Any]:
        return {
            "ruleset": ruleset,
            "name": str(rule.get("name", "unknown")),
            "enabled": bool(rule.get("enabled", True)),
            "weight": int(rule.get("weight", 0)),
            "version": str(rule.get("version", "unknown")),
            "reason": str(rule.get("reason", rule.get("flag", ""))),
            "rationale": str(rule.get("rationale", "")),
            "triggers": list(rule.get("triggers", [])),
            "condition": rule.get("condition"),
        }

    @staticmethod
    def _version_summary(version: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in version.items() if key not in {"risk_config", "url_config"}}
