from __future__ import annotations

import re
from urllib.parse import urlparse


class RiskEngine:
    def __init__(self) -> None:
        self.rules = [
            {
                "name": "transfer_before_service",
                "triggers": ["先转", "垫付", "保证金", "手续费", "解冻"],
                "weight": 18,
                "reason": "出现放款或服务前收费特征",
            },
            {
                "name": "high_return",
                "triggers": ["稳赚", "高收益", "内幕消息", "带单"],
                "weight": 15,
                "reason": "出现保本高收益话术",
            },
            {
                "name": "authority_pressure",
                "triggers": ["公检法", "安全账户", "涉嫌", "保密办案"],
                "weight": 20,
                "reason": "出现冒充机关施压特征",
            },
            {
                "name": "account_takeover",
                "triggers": ["验证码", "远程控制", "屏幕共享", "账号密码"],
                "weight": 22,
                "reason": "存在账户接管风险",
            },
            {
                "name": "off_platform_trade",
                "triggers": ["私下交易", "绕开平台", "线下转账"],
                "weight": 14,
                "reason": "交易绕开担保平台",
            },
            {
                "name": "fake_refund_or_compensation",
                "triggers": ["退款", "理赔", "双倍赔付", "订单异常", "客服来电"],
                "weight": 16,
                "reason": "命中冒充客服退款/理赔诈骗特征",
            },
            {
                "name": "acquaintance_impersonation",
                "triggers": ["急借", "别告诉别人", "同学借钱", "熟人借钱"],
                "weight": 14,
                "reason": "命中冒充熟人借钱施压特征",
            },
            {
                "name": "campus_loan",
                "triggers": ["校园贷", "征信修复", "刷流水", "学生专享"],
                "weight": 16,
                "reason": "命中校园金融诈骗风险特征",
            },
            {
                "name": "ai_deepfake",
                "triggers": [
                    "AI换脸", "ai换脸", "深度伪造", "deepfake",
                    "AI语音", "ai语音", "克隆声音", "合成声音",
                    "数字人", "虚拟人视频", "AI生成视频", "ai生成视频",
                    "人脸伪造", "声纹克隆", "视频合成", "AI冒充",
                    "face swap", "voice clone",
                ],
                "weight": 22,
                "reason": "命中 AI 深度伪造诈骗特征（换脸/语音克隆/数字人）",
            },
            {
                "name": "ai_investment_scam",
                "triggers": [
                    "AI选股", "AI量化", "AI内幕", "智能投顾",
                    "算法交易", "AI预测", "AI荐股", "量化内幕",
                    "AI操盘手", "机器人理财",
                ],
                "weight": 17,
                "reason": "命中 AI 虚假投资/量化骗局特征",
            },
        ]
        self.shortener_domains = {"t.cn", "bit.ly", "tinyurl.com", "dwz.cn", "is.gd"}
        self.risky_tlds = {"top", "xyz", "click", "fit", "work", "icu", "buzz"}

    def evaluate_text(
        self,
        message: str,
        matched_scams: list[dict[str, str]],
        user_role: str,
        emotion: str | None,
    ) -> dict[str, object]:
        text = message.lower()
        score = 0
        reasons: list[str] = []

        for rule in self.rules:
            if any(trigger in text for trigger in rule["triggers"]):
                score += int(rule["weight"])
                reasons.append(str(rule["reason"]))

        if re.search(r"(准备转账|已经转账|马上转|立刻转)", message):
            score += 20
            reasons.append("用户可能正处于转账关键节点")

        if matched_scams:
            score += min(20, 6 * len(matched_scams))
            reasons.append("文本与已知诈骗模型高度相关")

        if user_role == "student" and any(token in message for token in ["校园", "学费", "奖学金", "兼职"]):
            score += 10
            reasons.append("学生群体相关场景，建议提高警惕")

        if emotion in {"anxious", "negative"}:
            score += 5
            reasons.append("情绪信号提示可能受压或焦虑")

        level = self._score_to_level(score)
        intervention_script = self._build_intervention(level, user_role)
        recommendations = self._build_recommendations(level)

        if not reasons:
            reasons.append("暂未命中显著诈骗风险特征")

        return {
            "score": score,
            "level": level,
            "reasons": reasons,
            "intervention_script": intervention_script,
            "recommendations": recommendations,
        }

    def evaluate_url(self, url: str) -> dict[str, object]:
        score = 0
        flags: list[str] = []

        if not re.match(r"^https?://", url, flags=re.IGNORECASE):
            score += 15
            flags.append("链接未使用标准http/https协议")

        parsed = urlparse(url if re.match(r"^https?://", url, flags=re.IGNORECASE) else f"http://{url}")
        host = (parsed.netloc or parsed.path).lower()

        if re.match(r"^\d+\.\d+\.\d+\.\d+$", host.split(":")[0]):
            score += 20
            flags.append("域名使用IP直连")

        if "@" in url:
            score += 20
            flags.append("URL包含@符号，可能存在跳转伪装")

        if "xn--" in host:
            score += 20
            flags.append("检测到punycode域名")

        host_no_port = host.split(":")[0]
        if host_no_port in self.shortener_domains:
            score += 15
            flags.append("短链域名需要二次核验")

        tld = host_no_port.split(".")[-1] if "." in host_no_port else ""
        if tld in self.risky_tlds:
            score += 12
            flags.append("域名后缀命中高风险集合")

        if parsed.scheme == "http":
            score += 10
            flags.append("未使用HTTPS加密")

        level = self._score_to_level(score)
        if not flags:
            flags.append("URL结构未见明显高危特征")

        return {"score": score, "level": level, "flags": flags}

    @staticmethod
    def _score_to_level(score: int) -> str:
        if score >= 70:
            return "critical"
        if score >= 40:
            return "high"
        if score >= 20:
            return "medium"
        return "low"

    @staticmethod
    def _build_intervention(level: str, user_role: str) -> list[str]:
        scripts = {
            "low": [
                "保持核验习惯：不点未知链接，不向陌生账户转账。",
            ],
            "medium": [
                "先暂停当前操作，和可信任的人二次确认。",
                "通过官方电话或App核实，不依据聊天截图做决定。",
            ],
            "high": [
                "立即停止转账与验证码提供，退出可疑群聊或App。",
                "保留聊天记录、收款账户、链接截图，准备报警材料。",
            ],
            "critical": [
                "你当前处于高危受骗阶段，请立刻中断所有付款操作。",
                "立即联系银行申请止付，并拨打110或96110咨询。",
                "通知家人、辅导员或同伴协助判断，避免单独处理。",
            ],
        }
        if user_role == "student" and level in {"high", "critical"}:
            scripts[level].append("可同步联系学校保卫处或辅导员获取线下支持。")
        return scripts[level]

    @staticmethod
    def _build_recommendations(level: str) -> list[str]:
        common = [
            "优先使用官方平台或官方客服渠道",
            "拒绝任何先付款后服务的要求",
            "涉及资金操作前执行30秒冷静核验",
        ]
        if level in {"high", "critical"}:
            common.append("如已转账，第一时间联系银行与警方进行止损")
        return common
