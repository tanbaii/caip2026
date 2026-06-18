# LangGraph 聊天流程编排说明

## 当前流程

`/chat` 的核心职责原本集中在 `DialogueService.process_chat()`：

1. 读取用户会话历史。
2. 识别意图。
3. 匹配本地 `knowledge_base.json` 中的骗局类型。
4. 调用 `RiskEngine` 生成基础风险分、风险等级、命中规则和风险构成。
5. 叠加 URL 风险和多轮会话状态风险。
6. 可选执行 pgvector RAG 召回。
7. 可选调用本地 LLM 生成自然劝阻话术。
8. 发放积分并持久化本轮会话摘要。
9. 返回旧接口兼容的 `ChatResponse`。

这个流程可运行，但所有阶段写在一个函数里。后续要加入条件分支、可观测 trace、人工复核节点、不同风险等级路由时，会变得不好维护。

## 新增编排层

新增文件：

- `app/services/chat_workflow.py`

新增 runner：

- `ChatWorkflowRunner`

它把 `/chat` 拆成 7 个节点：

```text
recognize_context
  -> evaluate_risk
  -> update_conversation
  -> retrieve_knowledge
  -> generate_reply
  -> award_and_persist
  -> build_response
```

节点职责：

- `recognize_context`：意图识别、骗局知识库匹配、跨骗局话题切换重置。
- `evaluate_risk`：只调用 `RiskEngine` 和 URL 规则，生成基础风险。
- `update_conversation`：更新多轮 facts，叠加 conversation bonus，应用上下文风险保底。
- `retrieve_knowledge`：旁路执行 RAG 召回，不参与风险评分。
- `generate_reply`：基于风险结果和召回知识生成自然劝阻话术。
- `award_and_persist`：积分发放、会话历史落入内存。
- `build_response`：组装兼容旧前端的响应字段。

## 风险评分边界

LangGraph 不负责决定风险分。

风险评分仍由以下模块决定：

- `RiskEngine`
- URL 规则
- `ConversationStateManager.compute_conversation_bonus()`
- 历史风险分保底逻辑

LangGraph 只做流程编排、状态传递和后续分支扩展。

## 启用方式

安装依赖：

```bash
pip install -r requirements.txt
```

在 `.env` 中配置：

```env
CHAT_FLOW_ENGINE=langgraph
```

默认值是：

```env
CHAT_FLOW_ENGINE=classic
```

默认保持旧流程，避免影响现有前端和接口。

## 无 LangGraph 依赖时

`ChatWorkflowRunner` 带顺序执行 fallback。

如果运行环境暂时没有安装 `langgraph`，runner 会按同样节点顺序串行执行，保证最小可运行；安装后会自动用 `StateGraph` 编译执行。

## 后续适合加的分支

可以在 `update_conversation` 后加条件路由：

```text
update_conversation
  -> risk_router
      high/critical -> generate_strong_intervention
      low/medium    -> retrieve_knowledge -> generate_reply
      report        -> build_report_guidance
```

也可以加入：

- `human_review`：高风险人工复核。
- `rag_router`：低风险闲聊不召回，高风险或知识问答才召回。
- `safety_rewrite`：统一清洗模型输出，禁止暴露内部规则字段。
- `trace_logger`：记录每个节点输入输出，方便比赛演示和调试。

## 验证

已新增测试：

- `test_chat_workflow_runner_preserves_chat_contract`

验证内容：

- workflow runner 可独立跑通。
- `risk_score == risk_breakdown.total`。
- `retrieved_knowledge` 字段保留。
- `reply` 字段正常返回。
- 旧接口结构不被破坏。

测试命令：

```bash
python -m pytest tests/test_api.py -q
```
