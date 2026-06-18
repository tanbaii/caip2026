# RAG 知识库旁路增强说明

本文档说明当前项目新增的 PostgreSQL + pgvector + bge-m3 RAG 旁路能力。

## 1. 设计目标

RAG 模块用于召回相似骗局知识、典型案例、风险信号和处置建议，辅助生成更自然、更有依据的反诈劝阻话术。

它不替代现有 `RiskEngine`。

当前边界如下：

- `RiskEngine` 继续负责 `risk_score`、`risk_level`、`matched_rules`、`risk_breakdown`
- `KnowledgeRetriever` 只负责 `retrieved_knowledge`
- 可选 LLM 只基于规则结果和参考知识生成 `reply`
- pgvector 相似度和 LLM 输出都不参与风险分数计算

## 2. 架构

```text
用户输入
  |
  |-- KnowledgeBase 关键词匹配
  |-- RiskEngine 规则评分
  |-- ConversationState 多轮规则加分
  |
  |-- KnowledgeRetriever
  |     |-- bge-m3 生成 query embedding
  |     |-- pgvector cosine similarity top-k
  |     `-- 返回 retrieved_knowledge
  |
  |-- 可选 RagReplyGenerator
        |-- 输入 RiskEngine 结果
        |-- 输入 retrieved_knowledge
        `-- 生成更自然的劝阻话术
```

## 3. 新增文件

| 文件 | 作用 |
| --- | --- |
| `app/db/pgvector_schema.sql` | PostgreSQL 表结构与 pgvector 索引 |
| `app/services/embedding_service.py` | bge-m3 embedding 服务，维度 1024 |
| `app/services/knowledge_retriever.py` | pgvector 语义检索服务 |
| `app/services/rag_reply_service.py` | 可选 LLM RAG 劝阻话术生成器 |
| `scripts/import_knowledge_chunks.py` | 将 `knowledge_base.json` 切分并导入数据库 |
| `scripts/embed_knowledge_chunks.py` | 为未生成 embedding 的 chunk 写入向量 |
| `requirements-rag.txt` | RAG 额外依赖 |

## 4. 数据表

`knowledge_chunks` 字段：

- `id`
- `source_type`
- `source_id`
- `scam_type`
- `title`
- `content`
- `keywords`
- `metadata`
- `embedding vector(1024)`
- `created_at`
- `updated_at`

`embedding` 使用 bge-m3 dense embedding，维度为 1024。

## 5. Chat 响应变化

`/chat` 响应新增字段：

```json
{
  "retrieved_knowledge": [
    {
      "title": "刷单返利 - 典型案例",
      "content": "...",
      "scam_type": "shuadan_rebate",
      "similarity": 0.8123,
      "source_type": "scam",
      "source_id": "S001",
      "metadata": {
        "chunk_kind": "overview",
        "source_name": "刷单返利"
      }
    }
  ]
}
```

如果未配置 PostgreSQL 或 RAG 依赖未安装，该字段返回空列表，不影响旧前端和旧接口。

## 6. 环境变量

项目会自动读取根目录 `.env`。可以复制 `.env.example` 后修改：

```powershell
Copy-Item .env.example .env
```

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `PGVECTOR_DSN` | 启用 RAG 时必填 | 无 | PostgreSQL 连接串 |
| `DATABASE_URL` | 否 | 无 | `PGVECTOR_DSN` 的备选 |
| `RAG_TOP_K` | 否 | `5` | 检索返回条数 |
| `RAG_RETRIEVAL_ENABLED` | 否 | `1` | 是否启用 pgvector 检索，设为 `0` 可关闭 |
| `BGE_M3_MODEL_NAME` | 否 | `BAAI/bge-m3` | embedding 模型名或本地路径 |
| `BGE_M3_USE_FP16` | 否 | `0` | 是否使用 fp16 |
| `RAG_LLM_ENABLED` | 否 | `0` | 是否启用 LLM 基于 RAG 生成 reply |
| `CHAT_LLM_ENABLED` | 否 | `0` | 是否允许 `/chat` 在无 RAG 召回时直接用 LLM 生成 reply |
| `RAG_LLM_TIMEOUT` | 否 | `15` | RAG LLM 请求超时时间，单位秒 |
| `OLLAMA_BASE_URL` | 否 | `http://localhost:11434` | Ollama 地址 |
| `OLLAMA_MODEL` | 否 | `deepseek-r1:1.5b` | Ollama 模型 |

## 7. 简单聊天模式

如果只想让 `/chat` 使用大模型生成自然回复，不想走 pgvector 召回，可以这样设置：

```powershell
$env:CHAT_LLM_ENABLED="1"
$env:RAG_RETRIEVAL_ENABLED="0"
$env:OLLAMA_BASE_URL="http://localhost:11545"
$env:OLLAMA_MODEL="qwen3-lora"
```

此时：

- `RiskEngine` 仍然正常输出风险分
- `retrieved_knowledge` 返回空列表
- 大模型只生成 `reply`
- 大模型不修改 `risk_score`、`risk_level`、`matched_rules`

## 8. 安全边界

RAG 只提供“参考知识”和“相似案例”，不能改变风险分。

代码中接入点位于 `DialogueService.process_chat()`：

- 先完成原有规则评分
- 再执行 `_retrieve_knowledge()`
- 如果 `RAG_LLM_ENABLED=1` 且检索到知识，才调用 `RagReplyGenerator`
- 返回体追加 `retrieved_knowledge`

因此，即使 pgvector、bge-m3 或 Ollama 不可用，规则评分仍然正常工作。
