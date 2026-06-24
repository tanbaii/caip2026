from __future__ import annotations

import re
from collections import defaultdict


class IntentRecognizer:
    def __init__(self) -> None:
        self.url_pattern = re.compile(r"(https?://\S+|www\.\S+)", re.IGNORECASE)
        self.intent_keywords: dict[str, list[str]] = {
            "ask_knowledge": [
                "是什么",
                "怎么防",
                "如何防",
                "套路",
                "骗局",
                "反诈",
                "刷单",
                "校园贷",
                "投资",
                "公检法",
                "游戏交易",
                "退款",
                "理赔",
                "冒充客服",
                "快递丢失",
                "冒充熟人",
            ],
            "seeking_help": [
                "让我转账",
                "准备转",
                "已经转",
                "验证码",
                "安全账户",
                "下载",
                "远程控制",
                "带单",
                "保证金",
                "解冻",
                "刷流水",
                "双倍赔付",
                "屏幕共享",
                "保密调查",
                "别告诉别人",
                "急借",
            ],
            "report_content": [
                "举报",
                "可疑链接",
                "可疑网址",
                "帮我看",
                "这个链接",
                "这个网址",
                "钓鱼网站",
                "退款链接",
                "理赔链接",
            ],
            "scenario_practice": ["闯关", "模拟", "演练", "情景", "练习", "推荐关卡"],
            "detect_ai_fraud": [
                "AI换脸", "ai换脸", "深度伪造", "deepfake",
                "AI语音", "克隆声音", "数字人", "虚拟人",
                "AI生成", "合成视频", "人脸识别诈骗",
                "视频里的朋友", "声音变了", "视频通话借钱",
                "AI诈骗", "人工智能诈骗",
            ],
        }

    def detect_intent(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
    ) -> tuple[str, list[str], dict[str, int]]:
        text = message.lower()
        pii_intent = self._detect_pii_or_emergency_intent(text, history or [])
        if pii_intent:
            return pii_intent, [], {pii_intent: 10}

        scores: dict[str, int] = defaultdict(int)
        matched_keywords: list[str] = []

        for intent, keywords in self.intent_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    scores[intent] += 2
                    matched_keywords.append(keyword)

        if self.url_pattern.search(message):
            scores["report_content"] += 3

        if "?" in message or "？" in message:
            scores["ask_knowledge"] += 1

        if history:
            last_intent = history[-1].get("intent", "")
            if last_intent in scores:
                scores[last_intent] += 1

        if not scores:
            return "casual", [], {}

        intent = max(scores.items(), key=lambda item: item[1])[0]
        return intent, sorted(set(matched_keywords)), dict(scores)

    @staticmethod
    def _detect_pii_or_emergency_intent(
        text: str,
        history: list[dict[str, str]],
    ) -> str:
        has_phone = "手机号" in text or "手机号码" in text or "电话" in text
        has_pii = has_phone or any(token in text for token in ("身份证", "身份证号", "地址", "住址", "银行卡"))
        has_code = "验证码" in text or "短信码" in text or "动态码" in text
        has_remote = "屏幕共享" in text or "共享屏幕" in text or "远程控制" in text
        third_party = any(token in text for token in ("对方", "陌生人", "客服", "骗子", "他", "她"))
        request = any(token in text for token in ("问我要", "问我的", "问我", "要我", "让我", "要求", "索要"))

        if has_code and any(token in text for token in ("发给", "给他", "给对方", "告诉", "看验证码", "问我要", "要我", "让我")):
            return "credential_leakage_emergency"
        if has_remote and has_code:
            return "active_remote_control"
        if has_remote and any(token in text for token in ("正在", "已经", "开了", "开启", "打开")):
            return "active_remote_control"

        if has_pii and third_party and request:
            return "third_party_pii_request"
        if has_pii and any(token in text for token in ("发给他", "发给对方", "告诉他", "告诉对方")):
            return "pii_disclosure_warning"
        if has_pii and any(token in text for token in ("我的手机号是多少", "我手机号是多少", "刚才的手机号")):
            return "self_pii_recall"

        if has_phone and ("我的手机号" in text and re.search(r"1[3-9]\d{9}", text)):
            return "self_pii_provide"
        return ""
