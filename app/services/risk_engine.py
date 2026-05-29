from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ── Built-in defaults (used when JSON config is absent or broken) ──

_DEFAULT_TEXT_RULES = [
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

_DEFAULT_RISK_RULES = {
    "text_rules": _DEFAULT_TEXT_RULES,
    "transfer_critical": {
        "pattern": "(准备转账|已经转账|马上转|立刻转)",
        "weight": 20,
        "reason": "用户可能正处于转账关键节点",
    },
    "scam_match_bonus": {"base": 6, "cap": 20, "reason": "文本与已知诈骗模型高度相关"},
    "student_campus": {
        "keywords": ["校园", "学费", "奖学金", "兼职"],
        "weight": 10,
        "reason": "学生群体相关场景，建议提高警惕",
    },
    "emotion_bonus": {
        "emotions": ["anxious", "negative"],
        "weight": 5,
        "reason": "情绪信号提示可能受压或焦虑",
    },
    "score_levels": {"critical": 70, "high": 40, "medium": 20, "low": 0},
    "interventions": {
        "low": ["保持核验习惯：不点未知链接，不向陌生账户转账。"],
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
        "student_append": {
            "levels": ["high", "critical"],
            "text": "可同步联系学校保卫处或辅导员获取线下支持。",
        },
    },
    "recommendations": {
        "common": [
            "优先使用官方平台或官方客服渠道",
            "拒绝任何先付款后服务的要求",
            "涉及资金操作前执行30秒冷静核验",
        ],
        "high_extra": ["如已转账，第一时间联系银行与警方进行止损"],
        "high_extra_levels": ["high", "critical"],
    },
}

_DEFAULT_URL_RULES = {
    "shortener_domains": ["t.cn", "bit.ly", "tinyurl.com", "dwz.cn", "is.gd"],
    "risky_tlds": ["top", "xyz", "click", "fit", "work", "icu", "buzz"],
    "checks": [
        {"name": "missing_protocol", "condition": "missing_protocol", "weight": 15, "flag": "链接未使用标准http/https协议"},
        {"name": "ip_direct", "condition": "ip_direct", "weight": 20, "flag": "域名使用IP直连"},
        {"name": "at_symbol", "condition": "at_symbol", "weight": 20, "flag": "URL包含@符号，可能存在跳转伪装"},
        {"name": "punycode", "condition": "punycode", "weight": 20, "flag": "检测到punycode域名"},
        {"name": "shortener", "condition": "shortener_domain", "weight": 15, "flag": "短链域名需要二次核验"},
        {"name": "risky_tld", "condition": "risky_tld", "weight": 12, "flag": "域名后缀命中高风险集合"},
        {"name": "plain_http", "condition": "plain_http", "weight": 10, "flag": "未使用HTTPS加密"},
    ],
    "score_levels": {"critical": 70, "high": 40, "medium": 20, "low": 0},
}


def _load_json(path: Path, fallback: dict) -> dict:
    """Load a JSON config file; return *fallback* if the file is missing or broken."""
    if not path.exists():
        logger.warning("Config file not found: %s — using built-in defaults", path)
        return fallback
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("top-level value must be an object")
        return data
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        logger.warning("Failed to parse %s (%s) — using built-in defaults", path, exc)
        return fallback


class RiskEngine:
    def __init__(
        self,
        risk_rules_path: Path | str | None = None,
        url_rules_path: Path | str | None = None,
    ) -> None:
        risk_path = Path(risk_rules_path) if risk_rules_path else _DATA_DIR / "risk_rules.json"
        url_path = Path(url_rules_path) if url_rules_path else _DATA_DIR / "url_rules.json"

        self._risk_cfg = _load_json(risk_path, _DEFAULT_RISK_RULES)
        self._url_cfg = _load_json(url_path, _DEFAULT_URL_RULES)

        self.rules: list[dict] = self._risk_cfg["text_rules"]
        self.shortener_domains: set[str] = set(self._url_cfg["shortener_domains"])
        self.risky_tlds: set[str] = set(self._url_cfg["risky_tlds"])
        self._url_checks: list[dict] = self._url_cfg["checks"]

    # ── Text risk evaluation ──

    def evaluate_text(
        self,
        message: str,
        matched_scams: list[dict[str, str]],
        user_role: str,
        emotion: str | None,
    ) -> dict[str, object]:
        cfg = self._risk_cfg
        text = message.lower()
        text_score = 0
        knowledge_score = 0
        profile_score = 0
        emotion_score = 0
        reasons: list[str] = []
        matched_rules: list[dict[str, object]] = []

        for rule in self.rules:
            hits = [t for t in rule["triggers"] if t in text]
            if hits:
                text_score += int(rule["weight"])
                reasons.append(str(rule["reason"]))
                matched_rules.append({
                    "rule": rule["name"],
                    "evidence": hits,
                    "weight": int(rule["weight"]),
                    "reason": str(rule["reason"]),
                })

        tc = cfg.get("transfer_critical", {})
        if tc.get("pattern") and re.search(tc["pattern"], message):
            w = int(tc.get("weight", 20))
            text_score += w
            reasons.append(str(tc.get("reason", "用户可能正处于转账关键节点")))
            matched_rules.append({
                "rule": "transfer_critical",
                "evidence": re.findall(tc["pattern"], message),
                "weight": w,
                "reason": str(tc.get("reason", "")),
            })

        smb = cfg.get("scam_match_bonus", {})
        if matched_scams:
            base = int(smb.get("base", 6))
            cap = int(smb.get("cap", 20))
            knowledge_score = min(cap, base * len(matched_scams))
            reasons.append(str(smb.get("reason", "文本与已知诈骗模型高度相关")))
            matched_rules.append({
                "rule": "scam_match",
                "evidence": [s.get("name", "") for s in matched_scams],
                "weight": knowledge_score,
                "reason": str(smb.get("reason", "")),
            })

        sc = cfg.get("student_campus", {})
        if user_role == "student" and any(
            token in message for token in sc.get("keywords", ["校园", "学费", "奖学金", "兼职"])
        ):
            w = int(sc.get("weight", 10))
            profile_score = w
            reasons.append(str(sc.get("reason", "学生群体相关场景，建议提高警惕")))
            matched_rules.append({
                "rule": "student_campus",
                "evidence": [t for t in sc.get("keywords", []) if t in message],
                "weight": w,
                "reason": str(sc.get("reason", "")),
            })

        eb = cfg.get("emotion_bonus", {})
        if emotion in set(eb.get("emotions", ["anxious", "negative"])):
            w = int(eb.get("weight", 5))
            emotion_score = w
            reasons.append(str(eb.get("reason", "情绪信号提示可能受压或焦虑")))
            matched_rules.append({
                "rule": "emotion_bonus",
                "evidence": [emotion],
                "weight": w,
                "reason": str(eb.get("reason", "")),
            })

        score = text_score + knowledge_score + profile_score + emotion_score
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
            "matched_rules": matched_rules,
            "risk_breakdown": {
                "text_score": text_score,
                "knowledge_score": knowledge_score,
                "profile_score": profile_score,
                "emotion_score": emotion_score,
                "total": score,
            },
        }

    # ── URL risk evaluation ──

    def evaluate_url(self, url: str) -> dict[str, object]:
        cfg = self._url_cfg
        score = 0
        flags: list[str] = []
        matched_rules: list[dict[str, object]] = []

        has_protocol = bool(re.match(r"^https?://", url, flags=re.IGNORECASE))
        parsed = urlparse(url if has_protocol else f"http://{url}")
        host = (parsed.netloc or parsed.path).lower()
        host_no_port = host.split(":")[0]
        ip_host = host_no_port.split(":")[0]
        tld = host_no_port.split(".")[-1] if "." in host_no_port else ""

        for check in self._url_checks:
            cond = check["condition"]
            hit = False
            if cond == "missing_protocol":
                hit = not has_protocol
            elif cond == "ip_direct":
                hit = bool(re.match(r"^\d+\.\d+\.\d+\.\d+$", ip_host))
            elif cond == "at_symbol":
                hit = "@" in url
            elif cond == "punycode":
                hit = "xn--" in host
            elif cond == "shortener_domain":
                hit = host_no_port in self.shortener_domains
            elif cond == "risky_tld":
                hit = tld in self.risky_tlds
            elif cond == "plain_http":
                hit = parsed.scheme == "http"
            if hit:
                score += int(check["weight"])
                flags.append(str(check["flag"]))
                matched_rules.append({
                    "rule": check["name"],
                    "evidence": [cond],
                    "weight": int(check["weight"]),
                    "reason": str(check["flag"]),
                })

        level = self._url_score_to_level(score)
        if not flags:
            flags.append("URL结构未见明显高危特征")

        return {"score": score, "level": level, "flags": flags, "matched_rules": matched_rules}

    # ── Shared helpers ──

    def _score_to_level(self, score: int) -> str:
        levels = self._risk_cfg.get("score_levels", _DEFAULT_RISK_RULES["score_levels"])
        if score >= levels.get("critical", 70):
            return "critical"
        if score >= levels.get("high", 40):
            return "high"
        if score >= levels.get("medium", 20):
            return "medium"
        return "low"

    def _url_score_to_level(self, score: int) -> str:
        levels = self._url_cfg.get("score_levels", _DEFAULT_URL_RULES["score_levels"])
        if score >= levels.get("critical", 70):
            return "critical"
        if score >= levels.get("high", 40):
            return "high"
        if score >= levels.get("medium", 20):
            return "medium"
        return "low"

    def _build_intervention(self, level: str, user_role: str) -> list[str]:
        iv = self._risk_cfg.get("interventions", _DEFAULT_RISK_RULES["interventions"])
        scripts = dict(iv)
        scripts.pop("student_append", None)
        result = list(scripts.get(level, []))

        sa = iv.get("student_append", {})
        if user_role == "student" and level in sa.get("levels", []):
            result.append(sa["text"])
        return result

    def _build_recommendations(self, level: str) -> list[str]:
        rec = self._risk_cfg.get("recommendations", _DEFAULT_RISK_RULES["recommendations"])
        common = list(rec.get("common", []))
        if level in set(rec.get("high_extra_levels", ["high", "critical"])):
            common.extend(rec.get("high_extra", []))
        return common
