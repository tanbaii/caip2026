# Alibaba Cloud Bailian API

本项目已经把大模型调用封装成 OpenAI 兼容协议，阿里云百炼/DashScope 可以直接接入，不需要微调。

## 1. 获取 API Key

在阿里云百炼控制台创建 API Key。官方文档：<https://help.aliyun.com/zh/model-studio/get-api-key>

不要把真实 Key 提交到 Git。只放在本机 `.env`、服务器环境变量或部署平台的 Secret 配置里。

## 2. 配置 `.env`

北京地域常用配置：

```env
LLM_PROVIDER=bailian
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=sk-你的百炼APIKey
LLM_MODEL=qwen-plus
LLM_TIMEOUT=30
LLM_ENABLE_THINKING=0
LLM_MAX_TOKENS=512
```

如果你更习惯按 DashScope 官方变量名，也可以写：

```env
LLM_PROVIDER=bailian
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_API_KEY=sk-你的百炼APIKey
LLM_MODEL=qwen-plus
```

## 3. 打开聊天模型

普通 `/ai/chat`：

```env
CHAT_LLM_ENABLED=1
```

RAG 检索后让云端模型组织回答：

```env
RAG_RETRIEVAL_ENABLED=1
RAG_LLM_ENABLED=1
RAG_LLM_MAX_TOKENS=256
```

如果只是演示稳定性，可以先只开 `CHAT_LLM_ENABLED=1`，确认百炼能通后再开 `RAG_LLM_ENABLED=1`。

## 4. 直接验证 API Key

官方 OpenAI 兼容 Chat 地址是：

```text
POST https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
Authorization: Bearer $DASHSCOPE_API_KEY
```

curl 验证：

```bash
curl -X POST "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions" \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-plus",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "你是谁？"}
    ]
  }'
```

官方 OpenAI 兼容 Chat 文档：<https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions>

## 5. 模型建议

- `qwen-plus`：默认推荐，效果和成本比较均衡。
- `qwen-turbo`：更便宜、更快，演示压测或简单聊天可以用。
- `qwen-max`：效果更强，成本也更高，适合最终演示或复杂问答。

当前代码会在发送云端前调用 `sanitize_text()`，手机号、身份证、银行卡、验证码、token 等敏感信息会先脱敏。

## 6. 延迟优化

如果使用 `qwen3` / `qwen3.5` 系列模型，短对话场景建议关闭思考模式：

```env
LLM_ENABLE_THINKING=0
```

如果只是生成反诈劝阻话术，把输出长度限制短一点会明显降低等待时间：

```env
LLM_MAX_TOKENS=512
RAG_LLM_MAX_TOKENS=256
```

如果日志出现 `psycopg is not installed; RAG retrieval is disabled.`，说明当前运行后端的 Python 环境没有装 pgvector 访问依赖。重新安装依赖或重建容器即可：

```bash
pip install -r requirements.txt
```

## 7. AI 风险复核

如果希望云端大模型辅助判断当前风险，可以打开：

```env
AI_RISK_ASSESSMENT_ENABLED=1
AI_RISK_TIMEOUT=8
AI_RISK_MAX_TOKENS=240
```

合并策略是保守的：规则引擎先给确定性分数；AI 复核输出 `risk_level`、`risk_score`、`confidence`、原因和建议。只有当 AI 置信度足够且判断更高时，才会抬高最终分数；如果 AI 判断更低，不会降低规则引擎的高危结论。

返回体会包含 `ai_risk_assessment`、`risk_decision`，同时 `risk_breakdown.ai_assessment` 会记录完整对比结果。
