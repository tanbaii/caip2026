from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from app.services.gamification import GamificationService
from app.services.risk_engine import RiskEngine
from app.services.sanitizer import sanitize_text

if TYPE_CHECKING:
    from app.services.storage import SQLiteStorage


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
        self.keyword_blacklist = {
            "刷单", "返利", "安全账户", "验证码", "远程控制",
            "内幕消息", "带单", "校园贷", "解冻", "保证金", "私下交易",
            "AI换脸", "深度伪造", "deepfake", "克隆声音", "数字人",
            "AI语音合成", "AI生成视频", "虚拟人视频", "AI冒充",
            "face swap", "voice clone",
            "助学金", "奖学金补录", "认证费", "学费返还",
            "助学贷款注销", "学信档案异常", "教育资助",
            "航班取消", "机票改签", "退票赔偿", "延误理赔",
            "航司客服", "改签链接", "延误险", "补差价",
            "不是诈骗", "不是骗子", "官网链接", "安全链接", "仿冒页面",
        }
        self.reports: list[dict[str, object]] = []

    def analyze(self, user_id: int, url: str | None, content: str | None) -> dict[str, object]:
        url_score = 0
        content_score = 0
        reasons: list[str] = []
        matched_keywords: list[str] = []
        url_flags: list[str] = []
        matched_rules: list[dict[str, object]] = []

        if url:
            url_result = self.risk_engine.evaluate_url(url)
            url_score = int(url_result["score"])
            url_flags.extend(list(url_result["flags"]))
            matched_rules.extend(url_result.get("matched_rules", []))
            if url_score >= 30:
                reasons.append("URL结构命中多个风险特征")

        if content:
            effective_keywords = self.risk_engine.effective_terms(
                content,
                sorted(self.keyword_blacklist),
            )
            for word in effective_keywords:
                content_score += 8
                matched_keywords.append(word)
                matched_rules.append({
                    "rule": "keyword_blacklist",
                    "evidence": [word],
                    "weight": 8,
                    "reason": f"文本命中诈骗关键词：{word}",
                    "rule_version": "1.1",
                    "ruleset_version": self.risk_engine.risk_ruleset_version,
                    "rationale": "举报内容关键词用于快速初筛，并受同分句否定语义抑制",
                })

            urgency_hits = self.risk_engine.effective_terms(
                content,
                ["先转账", "立刻付款", "限时到账", "点击领取"],
            )
            if urgency_hits:
                content_score += 10
                reasons.append("文本出现强催促或诱导支付话术")
                matched_rules.append({
                    "rule": "urgency_pattern",
                    "evidence": urgency_hits,
                    "weight": 10,
                    "reason": "文本出现强催促或诱导支付话术",
                    "rule_version": "1.1",
                    "ruleset_version": self.risk_engine.risk_ruleset_version,
                    "rationale": "限时催促和立即付款是社会工程诈骗常见施压方式",
                })

            if matched_keywords:
                reasons.append("文本命中诈骗关键词黑名单")

        score = url_score + content_score
        verdict = self._score_to_verdict(score)
        recommendations = self._build_recommendations(verdict)

        if not reasons:
            reasons.append("未识别到明显诈骗内容，建议继续保持核验")
        if not url_flags:
            url_flags.append("未提供URL或URL未命中明显风险")

        report_id = uuid.uuid4().hex[:12]
        url_host = self._extract_url_host(url)
        content_summary = sanitize_text(content)[:240] if content else None
        report_record = {
            "report_id": report_id,
            "user_id": user_id,
            "score": score,
            "verdict": verdict,
            "matched_keywords": sorted(set(matched_keywords)),
        }
        self.reports.append(report_record)
        if self.storage:
            self.storage.add_report(
                report_id=report_id,
                user_id=user_id,
                score=score,
                verdict=verdict,
                matched_keywords=matched_keywords,
                url_host=url_host,
                content_summary=content_summary,
                reasons=reasons,
                status="pending",
            )
        self.gamification.award(user_id, action="report_submit")

        return {
            "report_id": report_id,
            "verdict": verdict,
            "risk_score": score,
            "reasons": reasons,
            "recommendations": recommendations,
            "matched_keywords": sorted(set(matched_keywords)),
            "url_flags": url_flags,
            "matched_rules": matched_rules,
            "risk_breakdown": {"url_score": url_score, "content_score": content_score, "total": score},
            "next_actions": self._build_next_actions(verdict),
            "status": "pending",
            "ruleset_versions": self.risk_engine.ruleset_versions,
        }

    def list_reports(self, user_id: int, limit: int = 20, start_at: str | None = None, end_at: str | None = None) -> list[dict[str, object]]:
        if not self.storage:
            return []
        return self.storage.list_reports(user_id=user_id, limit=limit, start_at=start_at, end_at=end_at)

    @staticmethod
    def _score_to_verdict(score: int) -> str:
        if score >= 55:
            return "high_risk"
        if score >= 25:
            return "suspicious"
        return "safe"

    @staticmethod
    def _extract_url_host(url: str | None) -> str | None:
        if not url:
            return None
        has_protocol = bool(re.match(r"^https?://", url, flags=re.IGNORECASE))
        parsed = urlparse(url if has_protocol else f"http://{url}")
        return (parsed.hostname or "")[:253] or None

    @staticmethod
    def _build_recommendations(verdict: str) -> list[str]:
        if verdict == "high_risk":
            return ["请勿点击链接或继续沟通", "立即保存证据并通过110/96110咨询", "若涉及转账，联系银行尝试紧急止付"]
        if verdict == "suspicious":
            return ["先暂停操作，通过官方渠道二次核验", "避免在陌生页面输入账号密码和验证码"]
        return ["暂未见明显风险，仍建议保持谨慎，不泄露敏感信息"]

    @staticmethod
    def _build_next_actions(verdict: str) -> list[str]:
        if verdict == "high_risk":
            return ["立即停止与可疑方的一切联系", "保存所有聊天记录、转账截图和链接", "拨打110或96110进行举报咨询"]
        if verdict == "suspicious":
            return ["暂停操作，通过官方渠道二次核验", "不在陌生页面输入账号密码和验证码"]
        return ["保持警惕，遇到可疑信息及时举报"]
