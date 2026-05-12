from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING

from app.services.gamification import GamificationService
from app.services.risk_engine import RiskEngine

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
            "刷单",
            "返利",
            "安全账户",
            "验证码",
            "远程控制",
            "内幕消息",
            "带单",
            "校园贷",
            "解冻",
            "保证金",
            "私下交易",
            # ── AI 诈骗关键词 ──
            "AI换脸",
            "深度伪造",
            "deepfake",
            "克隆声音",
            "数字人",
            "AI语音合成",
            "AI生成视频",
            "虚拟人视频",
            "AI冒充",
            "face swap",
            "voice clone",
        }
        self.reports: list[dict[str, object]] = []

    def analyze(self, user_id: int, url: str | None, content: str | None) -> dict[str, object]:
        score = 0
        reasons: list[str] = []
        matched_keywords: list[str] = []
        url_flags: list[str] = []

        if url:
            url_result = self.risk_engine.evaluate_url(url)
            score += int(url_result["score"])
            url_flags.extend(list(url_result["flags"]))
            if int(url_result["score"]) >= 30:
                reasons.append("URL结构命中多个风险特征")

        if content:
            content_lower = content.lower()
            for word in self.keyword_blacklist:
                if word in content_lower:
                    score += 8
                    matched_keywords.append(word)

            if re.search(r"(先转账|立刻付款|限时到账|点击领取)", content):
                score += 10
                reasons.append("文本出现强催促或诱导支付话术")

            if matched_keywords:
                reasons.append("文本命中诈骗关键词黑名单")

        verdict = self._score_to_verdict(score)
        recommendations = self._build_recommendations(verdict)

        if not reasons:
            reasons.append("未识别到明显诈骗内容，建议继续保持核验")
        if not url_flags:
            url_flags.append("未提供URL或URL未命中明显风险")

        report_id = uuid.uuid4().hex[:12]
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

        return self.storage.list_reports(
            user_id=user_id,
            limit=limit,
            start_at=start_at,
            end_at=end_at,
        )

    @staticmethod
    def _score_to_verdict(score: int) -> str:
        if score >= 55:
            return "high_risk"
        if score >= 25:
            return "suspicious"
        return "safe"

    @staticmethod
    def _build_recommendations(verdict: str) -> list[str]:
        if verdict == "high_risk":
            return [
                "请勿点击链接或继续沟通",
                "立即保存证据并通过110/96110咨询",
                "若涉及转账，联系银行尝试紧急止付",
            ]
        if verdict == "suspicious":
            return [
                "先暂停操作，通过官方渠道二次核验",
                "避免在陌生页面输入账号密码和验证码",
            ]
        return ["暂未见明显风险，仍建议保持谨慎，不泄露敏感信息"]
