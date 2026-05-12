from __future__ import annotations

import httpx

# ── Ollama 配置（WSL 本地部署）──
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "deepseek-r1:1.5b"
REQUEST_TIMEOUT = 90  # R1 推理模型较慢，给足时间

SYSTEM_PROMPT = """你是一个专业的反诈安全顾问助手「反诈护盾」。你的任务是帮助用户识别、预防和应对各类诈骗行为。

核心能力：
1. **诈骗识别**：分析用户描述的场景/话术/链接，判断是否为诈骗
2. **风险预警**：指出高危信号（先转账、验证码、远程控制等）
3. **防骗指导**：给出具体可操作的防范步骤
4. **知识科普**：解释常见骗局的运作原理（刷单返利、冒充公检法、AI换脸诈骗等）
5. **心理支持**：对已受骗用户给予冷静建议，引导止损

回答原则：
- 用中文回答，语言亲切但专业
- 对高风险场景明确警告，不要模棱两可
- 提供具体行动建议而非空泛道理
- 如果用户描述涉及紧急资金风险，优先建议停止操作并报警
- 保持简洁，一般控制在 200 字以内（复杂问题可以稍长）
- 不要编造法律条文，引用时标注"根据《反电信网络诈骗法》等相关法规"

当前支持的诈骗类型：
- 刷单返利诈骗 / 虚假投资理财 / 冒充公检法 / 冒充客服退款
- 校园贷 / 征信修复骗局 / 游戏交易诈骗 / 熟人冒充借钱
- AI 深度伪造诈骗（AI换脸、AI语音克隆、数字人视频） / 杀猪盘 / 快递丢失理赔
"""


class AIService:
    """通过 Ollama API 调用本地 DeepSeek R1:1.5b 模型。"""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self._base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")
        self._model = model or OLLAMA_MODEL

    async def chat(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        """发送消息给 DeepSeek R1，返回模型回复文本。"""
        messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]

        # 注入历史对话上下文（最近 6 条）
        if history:
            for msg in history[-6:]:
                messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": message})

        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 1024,  # 限制输出长度避免过长
            },
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(
                    f"{self._base_url}/v1/chat/completions",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()

            return (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
                or "抱歉，我暂时没有有效的回复。请换个方式提问。"
            )

        except httpx.ConnectError:
            return (
                "⚠️ 无法连接到 AI 服务（Ollama）。请确认 WSL 中 Ollama 服务正在运行：\n"
                "```bash\nollama serve\n```\n"
                "同时确保 deepseek-r1:1.5b 模型已拉取：\n"
                "```bash\nollama pull deepseek-r1:1.5b\n```\n\n"
                "在等待期间，你可以使用上方的「智能对话研判」功能进行基础反诈分析。"
            )
        except httpx.TimeoutException:
            return "⚠️ AI 响应超时。DeepSeek R1 是推理模型，首次响应可能较慢。请缩短问题后重试，或使用「智能对话研判」功能。"
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 404:
                return f"⚠️ 模型 '{self._model}' 未找到。请在终端执行：`ollama pull {self._model}`"
            return f"⚠️ AI 服务返回错误 (HTTP {status})。请联系管理员检查 Ollama 配置。"
        except Exception as exc:
            return f"⚠️ AI 服务异常：{exc}。请稍后重试或使用其他功能。"

    async def analyze_fraud_risk(self, text: str) -> dict:
        """用 AI 对文本进行深度诈骗风险评估（可选增强功能）。"""
        analysis_prompt = (
            "请对以下用户输入的文本进行诈骗风险分析。\n"
            "以 JSON 格式严格返回（不要包含其他文字）：\n"
            '{\n'
            '  "is_fraudulent": true/false,\n'
            '  "fraud_type": "类型名称或null",\n'
            '  "risk_level": "low/medium/high/critical",\n'
            '  "confidence": 0.0~1.0,\n'
            '  "reasoning": "简短分析理由"\n'
            "}\n\n"
            f"用户文本：{text}"
        )
        reply = await self.chat(analysis_prompt)
        import json

        try:
            # 尝试从回复中提取 JSON
            start = reply.find("{")
            end = reply.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(reply[start:end])
        except (json.JSONDecodeError, ValueError):
            pass
        return {
            "is_fraudulent": False,
            "fraud_type": None,
            "risk_level": "low",
            "confidence": 0.0,
            "reasoning": f"AI 分析结果无法解析。原始回复：{reply[:200]}",
        }
