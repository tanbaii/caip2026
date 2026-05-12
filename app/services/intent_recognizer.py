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
