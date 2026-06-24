from __future__ import annotations

import hashlib
import re
import uuid
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse, urlunparse

from app.services.gamification import GamificationService
from app.services.risk_engine import RiskEngine
from app.services.sanitizer import sanitize_text

if TYPE_CHECKING:
    from app.services.storage import SQLiteStorage


REPORT_CONTENT_SCORE_CAP = 70
REPORT_TOTAL_SCORE_CAP = 100
REPORT_EDUCATIONAL_CONTENT_SCORE_CAP = 19

_URL_PATTERN = re.compile(r"(https?://[^\s，。！？；、]+|www\.[^\s，。！？；、]+)", re.IGNORECASE)
_EDUCATIONAL_INTENT_TERMS = (
    "反诈",
    "防范",
    "怎么防",
    "如何防",
    "了解",
    "科普",
    "宣传",
    "提醒",
    "不会让你",
    "不要",
    "不能",
    "不应",
    "无需",
)
_ACTION_INDUCING_TERMS = (
    "让我",
    "要我",
    "要求我",
    "客服让我",
    "导师让我",
    "提供",
    "告诉",
    "输入",
    "转账",
    "充值",
    "付款",
    "交保证金",
    "交认证费",
    "扫码",
    "点击",
    "下载",
    "共享屏幕",
    "解冻",
    "解封",
)
_NEGATED_ACTION_TERMS = (
    "不会让你",
    "不会让我",
    "不要",
    "不能",
    "不应",
    "无需",
    "不需要",
    "反诈宣传",
    "官方提醒",
)


class ReportService:
    def __init__(
        self,
        risk_engine: RiskEngine,
        gamification: GamificationService,
        storage: "SQLiteStorage | None" = None,
    ) -> None:
        self.risk_engine = risk_engine
        self.gamification = gamification
        self.storage = storage

    def analyze(
        self,
        user_id: int,
        url: str | None,
        content: str | None,
        channel: str = "web",
        user_role: str = "general",
        emotion: str | None = None,
        chat_risk_level: str | None = None,
        chat_risk_score: int | None = None,
    ) -> dict[str, object]:
        extracted_urls = self.extract_urls(content)
        urls_to_analyze = self._unique_urls([candidate for candidate in [url, *extracted_urls] if candidate])
        primary_url = url or (urls_to_analyze[0] if urls_to_analyze else None)
        normalized_url = self.normalize_url(primary_url)
        content_hash = self.content_hash(content)
        dedupe_hash = None if normalized_url else content_hash

        if self.storage:
            duplicate = self.storage.find_recent_duplicate_report(
                user_id=user_id,
                normalized_url=normalized_url,
                content_hash=dedupe_hash,
            )
            if duplicate:
                return self._response_from_record(duplicate, duplicated=True)

        url_score = 0
        content_score_raw = 0
        reasons: list[str] = []
        url_flags: list[str] = []
        matched_rules: list[dict[str, object]] = []

        for candidate_url in urls_to_analyze:
            url_result = self.risk_engine.evaluate_url(candidate_url)
            candidate_score = int(url_result["score"])
            url_score = min(REPORT_TOTAL_SCORE_CAP, url_score + candidate_score)
            url_flags.extend(str(flag) for flag in url_result.get("flags", []))
            matched_rules.extend(url_result.get("matched_rules", []))
            if candidate_score >= 20:
                reasons.append(f"检测到可疑链接: {candidate_url}")

        text_breakdown: dict[str, Any] = {}
        if content:
            text_result = self.risk_engine.evaluate_text(
                content,
                matched_scams=[],
                user_role=user_role,
                emotion=emotion,
            )
            content_score_raw = int(text_result["score"])
            text_breakdown = dict(text_result.get("risk_breakdown", {}))
            matched_rules.extend(text_result.get("matched_rules", []))
            text_reasons = [str(reason) for reason in text_result.get("reasons", [])]
            if content_score_raw > 0:
                reasons.extend(text_reasons)

        educational_suppressed = self.is_educational_or_consultation(content)
        effective_content_score_raw = content_score_raw
        if educational_suppressed:
            effective_content_score_raw = min(effective_content_score_raw, REPORT_EDUCATIONAL_CONTENT_SCORE_CAP)
            reasons.append("检测到科普/防范意图且未出现明确行动诱导，已降低内容风险权重")

        content_score_capped = min(REPORT_CONTENT_SCORE_CAP, effective_content_score_raw)
        score = min(REPORT_TOTAL_SCORE_CAP, url_score + content_score_capped)
        if chat_risk_score is not None and chat_risk_level in {"high", "critical"}:
            score = max(score, min(REPORT_TOTAL_SCORE_CAP, int(chat_risk_score)))
            reasons.append("沿用聊天侧高风险预判作为举报分析下限")
        content_score = max(0, score - url_score)
        risk_level = self.risk_engine._score_to_level(score)
        verdict = self._level_to_verdict(risk_level)

        if not reasons:
            reasons.append("暂未识别到明显诈骗风险，仍建议通过官方渠道核验。")
        if not url_flags:
            url_flags.append("未提供URL或URL结构未命中明显高危特征。")

        score_breakdown = {
            **text_breakdown,
            "url_score": url_score,
            "content_score_raw": content_score_raw,
            "content_score_after_intent": effective_content_score_raw,
            "content_score_capped": content_score_capped,
            "content_score": content_score,
            "content_score_cap": REPORT_CONTENT_SCORE_CAP,
            "educational_intent_suppressed": educational_suppressed,
            "total": score,
        }
        matched_keywords = self._matched_keywords(matched_rules)
        report_id = uuid.uuid4().hex[:12]
        url_host = self._extract_url_host(primary_url)
        sanitized_content = sanitize_text(content) if content else None
        content_summary = sanitized_content[:240] if sanitized_content else None
        ruleset_versions = self.risk_engine.ruleset_versions

        if self.storage:
            self.storage.add_report(
                report_id=report_id,
                user_id=user_id,
                score=score,
                verdict=verdict,
                risk_level=risk_level,
                channel=channel,
                matched_keywords=matched_keywords,
                matched_rules=matched_rules,
                url_host=url_host,
                url=primary_url,
                normalized_url=normalized_url,
                content_summary=content_summary,
                content=sanitized_content,
                content_hash=content_hash,
                reasons=reasons,
                url_flags=url_flags,
                score_breakdown=score_breakdown,
                ruleset_versions=ruleset_versions,
                status="pending",
            )
        self.gamification.award(user_id, action="report_submit")

        return {
            "report_id": report_id,
            "duplicated": False,
            "channel": channel,
            "risk_level": risk_level,
            "verdict": verdict,
            "risk_score": score,
            "score": score,
            "score_breakdown": score_breakdown,
            "risk_breakdown": score_breakdown,
            "reasons": reasons,
            "recommendations": self.risk_engine._build_recommendations(risk_level),
            "matched_keywords": matched_keywords,
            "url_flags": url_flags,
            "matched_rules": matched_rules,
            "next_actions": self._build_next_actions(risk_level),
            "status": "pending",
            "ruleset_versions": ruleset_versions,
        }

    def list_reports(
        self,
        user_id: int,
        limit: int = 20,
        start_at: str | None = None,
        end_at: str | None = None,
    ) -> list[dict[str, object]]:
        if not self.storage:
            return []
        return self.storage.list_reports(user_id=user_id, limit=limit, start_at=start_at, end_at=end_at)

    def get_report(self, report_id: str) -> dict[str, object] | None:
        if not self.storage:
            return None
        return self.storage.get_report(report_id)

    def list_admin_reports(self, **filters: object) -> dict[str, object]:
        if not self.storage:
            return {"total": 0, "page": filters.get("page", 1), "page_size": filters.get("page_size", 20), "items": []}
        return self.storage.list_admin_reports(**filters)

    def review_report(
        self,
        *,
        report_id: str,
        status: str,
        reviewer: str | None = None,
        review_note: str | None = None,
        verdict: str | None = None,
        risk_level: str | None = None,
        score: int | None = None,
    ) -> dict[str, object] | None:
        if not self.storage:
            return None
        return self.storage.review_report(
            report_id=report_id,
            status=status,
            reviewer=reviewer,
            review_note=review_note,
            verdict=verdict,
            risk_level=risk_level,
            score=score,
        )

    def _response_from_record(self, record: dict[str, Any], duplicated: bool) -> dict[str, object]:
        risk_level = str(record.get("risk_level") or "low")
        score_breakdown = dict(record.get("score_breakdown") or record.get("risk_breakdown") or {})
        return {
            "report_id": str(record["report_id"]),
            "duplicated": duplicated,
            "channel": str(record.get("channel") or "web"),
            "risk_level": risk_level,
            "verdict": str(record["verdict"]),
            "risk_score": int(record["score"]),
            "score": int(record["score"]),
            "score_breakdown": score_breakdown,
            "risk_breakdown": score_breakdown,
            "reasons": list(record.get("reasons") or []),
            "recommendations": self.risk_engine._build_recommendations(risk_level),
            "matched_keywords": list(record.get("matched_keywords") or []),
            "url_flags": list(record.get("url_flags") or []),
            "matched_rules": list(record.get("matched_rules") or []),
            "next_actions": self._build_next_actions(risk_level),
            "status": str(record.get("status") or "pending"),
            "ruleset_versions": dict(record.get("ruleset_versions") or {}),
        }

    @staticmethod
    def _level_to_verdict(level: str) -> str:
        if level == "low":
            return "safe"
        if level == "medium":
            return "suspicious"
        return "high_risk"

    @staticmethod
    def _matched_keywords(matched_rules: list[dict[str, object]]) -> list[str]:
        keywords: list[str] = []
        for rule in matched_rules:
            for item in rule.get("evidence", []):
                text = str(item).strip()
                if text:
                    keywords.append(text)
        return sorted(set(keywords))

    @staticmethod
    def _extract_url_host(url: str | None) -> str | None:
        if not url:
            return None
        has_protocol = bool(re.match(r"^https?://", url, flags=re.IGNORECASE))
        parsed = urlparse(url if has_protocol else f"http://{url}")
        return (parsed.hostname or "")[:253] or None

    @staticmethod
    def extract_urls(content: str | None) -> list[str]:
        if not content:
            return []
        return [
            match.group(0).rstrip(").],;")
            for match in _URL_PATTERN.finditer(content)
        ]

    @classmethod
    def _unique_urls(cls, urls: list[str]) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for url in urls:
            normalized = cls.normalize_url(url)
            key = normalized or url.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(url)
        return unique

    @staticmethod
    def is_educational_or_consultation(content: str | None) -> bool:
        if not content:
            return False
        text = content.lower()
        has_education_intent = any(term.lower() in text for term in _EDUCATIONAL_INTENT_TERMS)
        if not has_education_intent:
            return False
        has_action_inducing = any(term.lower() in text for term in _ACTION_INDUCING_TERMS)
        has_negated_action = any(term.lower() in text for term in _NEGATED_ACTION_TERMS)
        return not has_action_inducing or has_negated_action

    @staticmethod
    def normalize_url(url: str | None) -> str | None:
        if not url:
            return None
        raw = url.strip()
        if not raw:
            return None
        has_protocol = bool(re.match(r"^https?://", raw, flags=re.IGNORECASE))
        parsed = urlparse(raw if has_protocol else f"http://{raw}")
        scheme = (parsed.scheme or "http").lower()
        host = (parsed.hostname or "").strip(".").lower()
        if not host:
            return raw.lower()
        path = parsed.path or ""
        return urlunparse((scheme, host, path, "", "", ""))

    @staticmethod
    def content_hash(content: str | None) -> str | None:
        if not content or not content.strip():
            return None
        return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()

    @staticmethod
    def _build_next_actions(level: str) -> list[str]:
        if level == "critical":
            return ["立即停止付款和验证码操作", "保存聊天记录、链接和收款信息", "拨打110或96110并联系银行止付"]
        if level == "high":
            return ["停止转账、扫码、验证码和屏幕共享", "通过官方渠道核验身份", "保存证据，必要时报警"]
        if level == "medium":
            return ["暂停当前操作", "换用官方 App、官网或官方客服电话核实", "不要在陌生页面输入敏感信息"]
        return ["保持警惕", "不点击未知链接", "不向陌生账户转账"]
