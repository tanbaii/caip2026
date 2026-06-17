from __future__ import annotations

import json
import ipaddress
import logging
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.services.text_semantics import (
    DEFAULT_CONTRAST_MARKERS,
    DEFAULT_NEGATION_PREFIXES,
    find_effective_terms,
)

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class _RuntimeConfig:
    risk_cfg: dict[str, Any]
    url_cfg: dict[str, Any]
    rules: list[dict[str, Any]]
    shortener_domains: set[str]
    risky_tlds: set[str]
    url_checks: list[dict[str, Any]]
    risk_ruleset_version: str
    url_ruleset_version: str

# ---------- Built-in defaults (used when JSON config is absent or broken) ----------

_DEFAULT_TEXT_RULES = [
    {"name": "transfer_before_service", "triggers": ["先转", "垫付", "保证金", "手续费", "解冻"], "weight": 18, "reason": "出现放款或服务前收费特征"},
    {"name": "high_return", "triggers": ["稳赚", "高收益", "内幕消息", "带单"], "weight": 15, "reason": "出现保本高收益话术"},
    {"name": "authority_pressure", "triggers": ["公检法", "安全账户", "涉嫌", "保密办案"], "weight": 20, "reason": "出现冒充机关施压特征"},
    {"name": "account_takeover", "triggers": ["验证码", "远程控制", "屏幕共享", "账号密码"], "weight": 22, "reason": "存在账户接管风险"},
    {"name": "off_platform_trade", "triggers": ["私下交易", "绕开平台", "线下转账"], "weight": 14, "reason": "交易绕开担保平台"},
    {"name": "fake_refund_or_compensation", "triggers": ["退款", "理赔", "双倍赔付", "订单异常", "客服来电"], "weight": 16, "reason": "命中冒充客服退款/理赔诈骗特征"},
    {"name": "acquaintance_impersonation", "triggers": ["急借", "别告诉别人", "同学借钱", "熟人借钱"], "weight": 14, "reason": "命中冒充熟人借钱施压特征"},
    {"name": "campus_loan", "triggers": ["校园贷", "征信修复", "刷流水", "学生专享"], "weight": 16, "reason": "命中校园金融诈骗风险特征"},
    {"name": "ai_deepfake", "triggers": ["AI换脸", "ai换脸", "深度伪造", "deepfake", "AI语音", "ai语音", "克隆声音", "合成声音", "数字人", "虚拟人视频", "AI生成视频", "ai生成视频", "人脸伪造", "声纹克隆", "视频合成", "AI冒充", "face swap", "voice clone"], "weight": 22, "reason": "命中 AI 深度伪造诈骗特征（换脸/语音克隆/数字人）"},
    {"name": "ai_investment_scam", "triggers": ["AI选股", "AI量化", "AI内幕", "智能投顾", "算法交易", "AI预测", "AI荐股", "量化内幕", "AI操盘手", "机器人理财"], "weight": 17, "reason": "命中 AI 虚假投资/量化骗局特征"},
    {"name": "scholarship_fraud", "triggers": ["助学金", "奖学金补录", "认证费", "教育资助", "学费返还", "助学贷款注销", "学信档案", "学校补助", "贫困补助"], "weight": 18, "reason": "命中奖学金/助学金诈骗特征"},
    {"name": "airline_ticket_refund", "triggers": ["航班取消", "机票改签", "延误理赔", "退票赔偿", "航司客服", "补差价", "改签链接", "延误险", "行程变动"], "weight": 17, "reason": "命中机票退改签诈骗特征"},
    {"name": "negation_semantics", "triggers": ["不是诈骗", "不是骗子", "不骗人", "正规平台", "有备案", "你放心", "绝对安全", "不会骗你"], "weight": 8, "reason": "出现否定式辩解话术"},
    {"name": "domain_impersonation_text", "triggers": ["官网链接", "登录链接", "认证链接", "安全链接", "仿冒页面", "钓鱼网站"], "weight": 12, "reason": "文本出现引导访问链接的关键词"},
]

_DEFAULT_RISK_RULES = {
    "_meta": {
        "version": "2.2.0",
        "updated": "2026-06-14",
        "rationale": "内置回退规则，依据反电信网络诈骗法与常见高发诈骗案例整理",
    },
    "text_rules": _DEFAULT_TEXT_RULES,
    "semantic_negation": {
        "version": "1.0",
        "window": 12,
        "prefixes": list(DEFAULT_NEGATION_PREFIXES),
        "contrast_markers": list(DEFAULT_CONTRAST_MARKERS),
        "exempt_rules": ["trust_reassurance", "negation_semantics"],
        "rationale": "否定词仅在同一分句和有限窗口内生效，避免把安全提醒误判为风险行为",
    },
    "transfer_critical": {"pattern": "(准备转账|已经转账|马上转|立刻转)", "weight": 20, "reason": "用户可能正处于转账关键节点"},
    "scam_match_bonus": {"base": 6, "cap": 20, "reason": "文本与已知诈骗模型高度相关"},
    "student_campus": {"keywords": ["校园", "学费", "奖学金", "助学金", "兼职", "补助"], "weight": 10, "reason": "学生群体相关场景，建议提高警惕"},
    "emotion_bonus": {"emotions": ["anxious", "negative"], "weight": 5, "reason": "情绪信号提示可能受压或焦虑"},
    "score_levels": {"critical": 70, "high": 40, "medium": 20, "low": 0},
    "interventions": {
        "low": ["保持核验习惯：不点未知链接，不向陌生账户转账。"],
        "medium": ["先暂停当前操作，和可信任的人二次确认。", "通过官方电话或App核实，不依据聊天截图做决定。"],
        "high": ["立即停止转账与验证码提供，退出可疑群聊或App。", "保留聊天记录、收款账户、链接截图，准备报警材料。"],
        "critical": ["你当前处于高危受骗阶段，请立刻中断所有付款操作。", "立即联系银行申请止付，并拨打110或96110咨询。", "通知家人、辅导员或同伴协助判断，避免单独处理。"],
        "student_append": {"levels": ["high", "critical"], "text": "可同步联系学校保卫处或辅导员获取线下支持。"},
    },
    "recommendations": {
        "common": ["优先使用官方平台或官方客服渠道", "拒绝任何先付款后服务的要求", "涉及资金操作前执行30秒冷静核验"],
        "high_extra": ["如已转账，第一时间联系银行与警方进行止损"],
        "high_extra_levels": ["high", "critical"],
    },
}

_DEFAULT_URL_RULES = {
    "_meta": {
        "version": "2.1.0",
        "updated": "2026-06-14",
        "rationale": "内置回退规则，依据常见钓鱼域名结构与品牌仿冒方式整理",
    },
    "shortener_domains": ["t.cn", "bit.ly", "tinyurl.com", "dwz.cn", "is.gd", "suo.im", "url.cn", "t.co", "ow.ly", "buff.ly"],
    "risky_tlds": ["top", "xyz", "click", "fit", "work", "icu", "buzz", "site", "online", "club", "info", "pro", "cc", "tk", "ml", "ga", "cf", "gq"],
    "whitelist_domains": ["gov.cn", "edu.cn", "ac.cn", "mil.cn", "12321.cn", "nic.edu.cn"],
    "whitelist_note": "白名单域名在URL检测中直接标记为safe",
    "impersonation_patterns": {
        "famous_domains": {
            "taobao.com": "\u6dd8\u5b9d", "tmall.com": "\u5929\u732b", "jd.com": "\u4eac\u4e1c",
            "qq.com": "\u817e\u8bafQQ", "weixin.qq.com": "\u5fae\u4fe1", "12306.cn": "\u94c1\u8def12306",
            "alipay.com": "\u652f\u4ed8\u5b9d", "icbc.com.cn": "\u5de5\u5546\u94f6\u884c",
            "ccb.com": "\u5efa\u8bbe\u94f6\u884c", "cmbchina.com": "\u62db\u5546\u94f6\u884c",
            "boc.cn": "\u4e2d\u56fd\u94f6\u884c", "airchina.com.cn": "\u4e2d\u56fd\u56fd\u822a",
            "ceair.com": "\u4e1c\u65b9\u822a\u7a7a", "csair.com": "\u5357\u65b9\u822a\u7a7a",
            "gov.cn": "\u4e2d\u56fd\u653f\u5e9c\u7f51\u7ad9", "edu.cn": "\u4e2d\u56fd\u6559\u80b2\u673a\u6784",
        },
        "weight": 25,
        "flag_template": "\u57df\u540d\u7591\u4f3c\u4eff\u5192{target}\uff0c\u5b9e\u9645\u57df\u540d\u4e3a{actual}",
        "rationale": "\u4f9d\u636ePhishTank\u7edf\u8ba1\u6570\u636e\uff0c\u4eff\u5192\u77e5\u540d\u7535\u5546\u3001\u94f6\u884c\u3001\u822a\u53f8\u57df\u540d\u662f\u9493\u9c7c\u653b\u51fb\u6700\u5e38\u89c1\u624b\u6cd5",
    },
    "checks": [
        {"name": "missing_protocol", "condition": "missing_protocol", "weight": 15, "flag": "\u94fe\u63a5\u672a\u4f7f\u7528\u6807\u51c6http/https\u534f\u8bae"},
        {"name": "ip_direct", "condition": "ip_direct", "weight": 20, "flag": "\u57df\u540d\u4f7f\u7528IP\u76f4\u8fde"},
        {"name": "at_symbol", "condition": "at_symbol", "weight": 20, "flag": "URL\u5305\u542b@\u7b26\u53f7\uff0c\u53ef\u80fd\u5b58\u5728\u8df3\u8f6c\u4f2a\u88c5"},
        {"name": "punycode", "condition": "punycode", "weight": 20, "flag": "\u68c0\u6d4b\u5230punycode\u57df\u540d"},
        {"name": "shortener", "condition": "shortener_domain", "weight": 15, "flag": "\u77ed\u94fe\u57df\u540d\u9700\u8981\u4e8c\u6b21\u6838\u9a8c"},
        {"name": "risky_tld", "condition": "risky_tld", "weight": 12, "flag": "\u57df\u540d\u540e\u7f00\u547d\u4e2d\u9ad8\u98ce\u9669\u96c6\u5408"},
        {"name": "plain_http", "condition": "plain_http", "weight": 10, "flag": "\u672a\u4f7f\u7528HTTPS\u52a0\u5bc6"},
        {"name": "subdomain_disguise", "condition": "subdomain_disguise", "weight": 20, "flag": "\u68c0\u6d4b\u5230\u5b50\u57df\u540d\u4f2a\u88c5"},
        {"name": "typosquatting", "version": "2.2", "condition": "typosquatting", "weight": 20, "flag": "\u68c0\u6d4b\u5230\u6253\u5b57\u62a2\u6ce8\u578b\u57df\u540d", "rationale": "\u6253\u5b57\u62a2\u6ce8\u662f\u660e\u786e\u7684\u54c1\u724c\u4eff\u5192\u7279\u5f81\uff0c\u5355\u72ec\u547d\u4e2d\u5e94\u8fbe\u5230\u4e2d\u98ce\u9669\u544a\u8b66\u9608\u503c"},
        {"name": "keyword_impersonation", "condition": "keyword_impersonation", "weight": 15, "flag": "\u57df\u540d\u5305\u542b\u5b89\u5168\u3001\u8ba4\u8bc1\u3001\u5b98\u7f51\u7b49\u8bf1\u5bfc\u6027\u5173\u952e\u8bcd\u7ec4\u5408"},
    ],
    "score_levels": {"critical": 70, "high": 40, "medium": 20, "low": 0},
}

def _load_json(path: Path, fallback: dict) -> dict:
    """Load a JSON config file; return *fallback* if the file is missing or broken."""
    if not path.exists():
        logger.warning("Config file not found: %s -- using built-in defaults", path)
        return fallback
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("top-level value must be an object")
        return data
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        logger.warning("Failed to parse %s (%s) -- using built-in defaults", path, exc)
        return fallback


class RiskEngine:
    def __init__(
        self,
        risk_rules_path: Path | str | None = None,
        url_rules_path: Path | str | None = None,
    ) -> None:
        risk_path = Path(risk_rules_path) if risk_rules_path else _DATA_DIR / "risk_rules.json"
        url_path = Path(url_rules_path) if url_rules_path else _DATA_DIR / "url_rules.json"

        self._runtime = self._build_runtime(
            _load_json(risk_path, _DEFAULT_RISK_RULES),
            _load_json(url_path, _DEFAULT_URL_RULES),
        )

    @property
    def _risk_cfg(self) -> dict[str, Any]:
        return self._runtime.risk_cfg

    @property
    def _url_cfg(self) -> dict[str, Any]:
        return self._runtime.url_cfg

    @property
    def rules(self) -> list[dict[str, Any]]:
        return self._runtime.rules

    @property
    def shortener_domains(self) -> set[str]:
        return self._runtime.shortener_domains

    @property
    def risky_tlds(self) -> set[str]:
        return self._runtime.risky_tlds

    @property
    def _url_checks(self) -> list[dict[str, Any]]:
        return self._runtime.url_checks

    @property
    def risk_ruleset_version(self) -> str:
        return self._runtime.risk_ruleset_version

    @property
    def url_ruleset_version(self) -> str:
        return self._runtime.url_ruleset_version

    @classmethod
    def validate_configs(cls, risk_cfg: dict[str, Any], url_cfg: dict[str, Any]) -> None:
        if not isinstance(risk_cfg.get("text_rules"), list) or not risk_cfg["text_rules"]:
            raise ValueError("文本规则集不能为空")
        if not isinstance(url_cfg.get("checks"), list) or not url_cfg["checks"]:
            raise ValueError("URL 规则集不能为空")

        cls._validate_rule_list(risk_cfg["text_rules"], "文本")
        cls._validate_rule_list(url_cfg["checks"], "URL", require_triggers=False)

        supported_conditions = {
            "missing_protocol", "ip_direct", "at_symbol", "punycode",
            "shortener_domain", "risky_tld", "plain_http",
            "subdomain_disguise", "typosquatting", "keyword_impersonation",
        }
        for rule in url_cfg["checks"]:
            if rule.get("condition") not in supported_conditions:
                raise ValueError(f"URL 规则 {rule.get('name')} 使用了不支持的 condition")

        pattern = str(risk_cfg.get("transfer_critical", {}).get("pattern", ""))
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"转账关键节点正则无效: {exc}") from exc

        for label, cfg in (("文本", risk_cfg), ("URL", url_cfg)):
            levels = cfg.get("score_levels", {})
            values = [levels.get(name) for name in ("low", "medium", "high", "critical")]
            if not all(isinstance(value, int) for value in values) or values != sorted(values):
                raise ValueError(f"{label}风险等级阈值必须按 low/medium/high/critical 递增")
            if not str(cfg.get("_meta", {}).get("version", "")).strip():
                raise ValueError(f"{label}规则集缺少版本号")

    @staticmethod
    def _validate_rule_list(
        rules: list[dict[str, Any]],
        label: str,
        *,
        require_triggers: bool = True,
    ) -> None:
        names: set[str] = set()
        for rule in rules:
            name = str(rule.get("name", "")).strip()
            if not name:
                raise ValueError(f"{label}规则缺少名称")
            if name in names:
                raise ValueError(f"{label}规则名称重复: {name}")
            names.add(name)
            if not isinstance(rule.get("enabled", True), bool):
                raise ValueError(f"规则 {name} 的 enabled 必须是布尔值")
            weight = rule.get("weight")
            if not isinstance(weight, int) or not 0 <= weight <= 100:
                raise ValueError(f"规则 {name} 的权重必须是 0 到 100 的整数")
            if require_triggers:
                triggers = rule.get("triggers")
                if not isinstance(triggers, list) or not triggers or not all(
                    isinstance(item, str) and item.strip() for item in triggers
                ):
                    raise ValueError(f"文本规则 {name} 至少需要一个有效触发词")

    @classmethod
    def _build_runtime(
        cls,
        risk_cfg: dict[str, Any],
        url_cfg: dict[str, Any],
    ) -> _RuntimeConfig:
        risk_copy = deepcopy(risk_cfg)
        url_copy = deepcopy(url_cfg)
        cls.validate_configs(risk_copy, url_copy)
        return _RuntimeConfig(
            risk_cfg=risk_copy,
            url_cfg=url_copy,
            rules=risk_copy.get("text_rules", _DEFAULT_TEXT_RULES),
            shortener_domains=set(url_copy.get("shortener_domains", [])),
            risky_tlds=set(url_copy.get("risky_tlds", [])),
            url_checks=url_copy.get("checks", []),
            risk_ruleset_version=str(risk_copy.get("_meta", {}).get("version", "unknown")),
            url_ruleset_version=str(url_copy.get("_meta", {}).get("version", "unknown")),
        )

    def apply_configs(self, risk_cfg: dict[str, Any], url_cfg: dict[str, Any]) -> None:
        """Validate both rule sets, then atomically swap the runtime snapshot."""
        self._runtime = self._build_runtime(risk_cfg, url_cfg)

    def export_configs(self) -> tuple[dict[str, Any], dict[str, Any]]:
        return deepcopy(self._risk_cfg), deepcopy(self._url_cfg)

    @property
    def ruleset_versions(self) -> dict[str, str]:
        return {
            "text": self.risk_ruleset_version,
            "url": self.url_ruleset_version,
        }

    def effective_terms(
        self,
        text: str,
        terms: list[str] | set[str] | tuple[str, ...],
        *,
        negation_exempt: bool = False,
    ) -> list[str]:
        negation_cfg = self._risk_cfg.get("semantic_negation", {})
        return find_effective_terms(
            text,
            terms,
            prefixes=negation_cfg.get("prefixes", DEFAULT_NEGATION_PREFIXES),
            contrast_markers=negation_cfg.get("contrast_markers", DEFAULT_CONTRAST_MARKERS),
            window=int(negation_cfg.get("window", 12)),
            negation_exempt=negation_exempt,
        )

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

        negation_cfg = cfg.get("semantic_negation", {})
        exempt_rules = set(negation_cfg.get("exempt_rules", []))
        for rule in self.rules:
            if not rule.get("enabled", True):
                continue
            hits = self.effective_terms(
                text,
                rule.get("triggers", []),
                negation_exempt=rule.get("name") in exempt_rules,
            )
            if hits:
                text_score += int(rule["weight"])
                reasons.append(str(rule["reason"]))
                matched_rules.append(self._rule_match(rule, hits, "text"))

        tc = cfg.get("transfer_critical", {})
        transfer_matches = list(re.finditer(tc.get("pattern", r"(?!x)x"), message))
        transfer_hits = [
            match.group(0)
            for match in transfer_matches
            if self.effective_terms(text, [match.group(0)])
        ]
        if transfer_hits:
            w = int(tc.get("weight", 20))
            text_score += w
            reasons.append(str(tc.get("reason", "用户可能正处于转账关键节点")))
            matched_rules.append(self._rule_match({"name": "transfer_critical", **tc}, transfer_hits, "text"))

        smb = cfg.get("scam_match_bonus", {})
        if matched_scams:
            base = int(smb.get("base", 6))
            cap = int(smb.get("cap", 20))
            knowledge_score = min(cap, base * len(matched_scams))
            reasons.append(str(smb.get("reason", "文本与已知诈骗模型高度相关")))
            matched_rules.append(self._rule_match({"name": "scam_match", "weight": knowledge_score, **smb}, [s.get("name", "") for s in matched_scams], "text"))

        sc = cfg.get("student_campus", {})
        if user_role == "student" and any(token in message for token in sc.get("keywords", ["校园", "学费", "奖学金", "兼职"])):
            w = int(sc.get("weight", 10))
            profile_score = w
            reasons.append(str(sc.get("reason", "学生群体相关场景，建议提高警惕")))
            matched_rules.append(self._rule_match({"name": "student_campus", "weight": w, **sc}, [t for t in sc.get("keywords", []) if t in message], "text"))

        eb = cfg.get("emotion_bonus", {})
        if emotion in set(eb.get("emotions", ["anxious", "negative"])):
            w = int(eb.get("weight", 5))
            emotion_score = w
            reasons.append(str(eb.get("reason", "情绪信号提示可能受压或焦虑")))
            matched_rules.append(self._rule_match({"name": "emotion_bonus", "weight": w, **eb}, [emotion], "text"))

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
            "ruleset_version": self.risk_ruleset_version,
        }

    def evaluate_url(self, url: str) -> dict[str, object]:
        cfg = self._url_cfg
        score = 0
        flags: list[str] = []
        matched_rules: list[dict[str, object]] = []

        has_protocol = bool(re.match(r"^https?://", url, flags=re.IGNORECASE))
        parsed = urlparse(url if has_protocol else f"http://{url}")
        host_no_port = self._normalize_host(parsed.hostname or "")
        ip_host = host_no_port
        tld = host_no_port.split(".")[-1] if "." in host_no_port else ""

        whitelist = cfg.get("whitelist_domains", [])
        whitelisted_domain = next(
            (domain for domain in whitelist if self._is_same_or_subdomain(host_no_port, str(domain))),
            None,
        )
        if whitelisted_domain:
            reason = "域名命中配置白名单，跳过域名结构风险加分；仍需核对页面内容"
            return {
                "score": 0,
                "level": "low",
                "flags": [reason],
                "matched_rules": [self._url_rule_match(
                    {"name": "domain_whitelist", "weight": 0, "flag": reason, "rationale": cfg.get("whitelist_note", reason)},
                    [whitelisted_domain],
                )],
                "ruleset_version": self.url_ruleset_version,
            }

        for check in self._url_checks:
            if not check.get("enabled", True):
                continue
            cond = check["condition"]
            hit = False
            if cond == "missing_protocol":
                hit = not has_protocol
            elif cond == "ip_direct":
                hit = self._is_ip_address(ip_host)
            elif cond == "at_symbol":
                hit = "@" in url
            elif cond == "punycode":
                hit = "xn--" in host_no_port
            elif cond == "shortener_domain":
                hit = host_no_port in self.shortener_domains
            elif cond == "risky_tld":
                hit = tld in self.risky_tlds
            elif cond == "plain_http":
                hit = parsed.scheme == "http"
            elif cond == "subdomain_disguise":
                hit = self._check_subdomain_disguise(host_no_port, cfg)
            elif cond == "typosquatting":
                hit = self._check_typosquatting(host_no_port, cfg)
            elif cond == "keyword_impersonation":
                hit = self._check_keyword_impersonation(host_no_port)
            if hit:
                score += int(check["weight"])
                flags.append(str(check["flag"]))
                matched_rules.append(self._url_rule_match(check, [cond]))

        imp_check = self._check_domain_impersonation(host_no_port, cfg)
        if imp_check:
            imp_weight, imp_flag = imp_check
            score += imp_weight
            flags.append(imp_flag)
            matched_rules.append(self._url_rule_match(
                {"name": "domain_impersonation", "weight": imp_weight, "flag": imp_flag, "rationale": cfg.get("impersonation_patterns", {}).get("rationale", "")},
                [host_no_port],
            ))

        level = self._url_score_to_level(score)
        if not flags:
            flags.append("URL结构未见明显高危特征")
        return {"score": score, "level": level, "flags": flags, "matched_rules": matched_rules, "ruleset_version": self.url_ruleset_version}

    @staticmethod
    def _check_subdomain_disguise(host: str, cfg: dict) -> bool:
        famous = cfg.get("impersonation_patterns", {}).get("famous_domains", {})
        for famous_domain in famous:
            normalized = str(famous_domain).lower().strip(".")
            if RiskEngine._is_same_or_subdomain(host, normalized):
                continue
            if normalized + "." in host:
                return True
        return False

    @staticmethod
    def _check_typosquatting(host: str, cfg: dict) -> bool:
        famous = cfg.get("impersonation_patterns", {}).get("famous_domains", {})
        host_parts = [part for part in re.split(r"[.-]", host) if part]
        for famous_domain in famous:
            normalized = str(famous_domain).lower().strip(".")
            if RiskEngine._is_same_or_subdomain(host, normalized):
                continue
            famous_base = normalized.split(".")[0]
            if len(famous_base) < 4:
                continue
            if any(RiskEngine._is_one_edit_or_transposition(part, famous_base) for part in host_parts):
                return True
        return False

    @staticmethod
    def _check_keyword_impersonation(host: str) -> bool:
        suspicious = ["secure", "security", "verify", "login", "account", "auth", "official", "cert", "safe", "protect", "bank", "pay", "refund", "claim", "reward"]
        host_lower = host.lower()
        return sum(1 for kw in suspicious if kw in host_lower) >= 2

    @staticmethod
    def _check_domain_impersonation(host: str, cfg: dict) -> tuple | None:
        famous = cfg.get("impersonation_patterns", {}).get("famous_domains", {})
        weight = cfg.get("impersonation_patterns", {}).get("weight", 25)
        flag_template = cfg.get("impersonation_patterns", {}).get("flag_template", "")
        for famous_domain, brand_name in famous.items():
            normalized = str(famous_domain).lower().strip(".")
            if RiskEngine._is_same_or_subdomain(host, normalized):
                continue
            if normalized in host:
                return (weight, flag_template.format(target=brand_name, actual=host))
            brand_token = normalized.split(".")[0]
            host_parts = [part for part in re.split(r"[.-]", host) if part]
            if brand_token in host_parts or (
                len(brand_token) >= 5 and any(brand_token in part for part in host_parts)
            ):
                return (weight, flag_template.format(target=brand_name, actual=host))
        return None

    def _rule_match(
        self,
        rule: dict,
        evidence: list[object],
        ruleset: str,
    ) -> dict[str, object]:
        meta = self._risk_cfg.get("_meta", {})
        return {
            "rule": str(rule.get("name", "unknown")),
            "evidence": list(dict.fromkeys(str(item) for item in evidence if item is not None)),
            "weight": int(rule.get("weight", 0)),
            "reason": str(rule.get("reason", "")),
            "rule_version": str(rule.get("version", meta.get("version", "unknown"))),
            "ruleset_version": self.risk_ruleset_version if ruleset == "text" else self.url_ruleset_version,
            "rationale": str(rule.get("rationale", meta.get("rationale", ""))),
        }

    def _url_rule_match(self, rule: dict, evidence: list[object]) -> dict[str, object]:
        normalized = {
            "name": rule.get("name", "unknown"),
            "weight": rule.get("weight", 0),
            "reason": rule.get("flag", rule.get("reason", "")),
            "version": rule.get("version", self.url_ruleset_version),
            "rationale": rule.get("rationale", self._url_cfg.get("_meta", {}).get("rationale", "")),
        }
        return self._rule_match(normalized, evidence, "url")

    @staticmethod
    def _normalize_host(host: str) -> str:
        normalized = host.strip().strip(".").lower()
        if not normalized:
            return ""
        try:
            return normalized.encode("idna").decode("ascii")
        except UnicodeError:
            return normalized

    @staticmethod
    def _is_same_or_subdomain(host: str, domain: str) -> bool:
        normalized_host = host.lower().strip(".")
        normalized_domain = domain.lower().strip(".")
        return normalized_host == normalized_domain or normalized_host.endswith("." + normalized_domain)

    @staticmethod
    def _is_ip_address(host: str) -> bool:
        try:
            ipaddress.ip_address(host)
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_one_edit_or_transposition(value: str, target: str) -> bool:
        if value == target or abs(len(value) - len(target)) > 1:
            return False
        if len(value) == len(target):
            differences = [index for index, pair in enumerate(zip(value, target)) if pair[0] != pair[1]]
            if len(differences) == 1:
                return True
            if len(differences) == 2:
                first, second = differences
                return (
                    second == first + 1
                    and value[first] == target[second]
                    and value[second] == target[first]
                )
            return False

        shorter, longer = (value, target) if len(value) < len(target) else (target, value)
        short_index = long_index = differences = 0
        while short_index < len(shorter) and long_index < len(longer):
            if shorter[short_index] == longer[long_index]:
                short_index += 1
                long_index += 1
                continue
            differences += 1
            if differences > 1:
                return False
            long_index += 1
        return True

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
