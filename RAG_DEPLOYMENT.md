# RAG 部署与初始化指南

本文说明如何部署 PostgreSQL + pgvector + BGE-M3 RAG 知识库旁路能力。

## 1. 前置要求

- Python 3.10+
- PostgreSQL 14+
- pgvector 扩展
- 可访问 ModelScope 下载 `BAAI/bge-m3`，或提前准备本地模型目录

RAG 只负责召回知识，不参与风险评分。

## 2. 安装依赖

普通后端依赖：

```powershell
pip install -r requirements.txt
```

RAG 额外依赖：

```powershell
pip install -r requirements-rag.txt
```

`requirements-rag.txt` 会安装：

- `psycopg[binary]`
- `FlagEmbedding`
- `modelscope`

## 3. 准备 PostgreSQL 与 pgvector

创建数据库示例：

```sql
CREATE DATABASE anti_fraud_rag;
```

执行项目内 schema：

```powershell
$env:PGVECTOR_DSN="postgresql://user:password@localhost:5432/anti_fraud_rag"
psql $env:PGVECTOR_DSN -f app/db/pgvector_schema.sql
```

该 schema 会创建：

- `vector` 扩展
- `knowledge_chunks` 表
- cosine ivfflat 索引
- `updated_at` 触发器

## 4. 导入知识 chunk

导入现有 `app/data/knowledge_base.json`：

```powershell
$env:PGVECTOR_DSN="postgresql://user:password@localhost:5432/anti_fraud_rag"
python scripts/import_knowledge_chunks.py --reset
```

说明：

- `--reset` 会清空 `knowledge_chunks` 并重新导入。
- 不加 `--reset` 会追加导入。
- 默认读取 `app/data/knowledge_base.json`。

## 5. 从 ModelScope 下载 BGE-M3

不走 HuggingFace。先下载到本地目录：

```powershell
python scripts/download_modelscope_model.py `
  --model-id BAAI/bge-m3 `
  --local-dir D:\models\bge-m3
```

也可以用 `.env` 配置：

```env
MODELSCOPE_BGE_M3_MODEL_ID=BAAI/bge-m3
MODELSCOPE_BGE_M3_LOCAL_DIR=D:\models\bge-m3
BGE_M3_MODEL_NAME=D:\models\bge-m3
```

## 6. 生成 embedding

使用本地模型目录生成向量：

```powershell
$env:PGVECTOR_DSN="postgresql://user:password@localhost:5432/anti_fraud_rag"
python scripts/embed_knowledge_chunks.py `
  --model D:\models\bge-m3 `
  --batch-size 4 `
  --limit 100
```

显存较充足时可启用 fp16：

```powershell
python scripts/embed_knowledge_chunks.py `
  --model D:\models\bge-m3 `
  --use-fp16 `
  --batch-size 8
```

## 7. 启用 RAG 检索

后端和脚本会读取项目根目录 `.env`：

```env
PGVECTOR_DSN=postgresql://user:password@localhost:5432/anti_fraud_rag
RAG_RETRIEVAL_ENABLED=1
RAG_TOP_K=5
BGE_M3_MODEL_NAME=D:\models\bge-m3
```

启动后端：

```powershell
uvicorn app.main:app --reload --port 8000
```

此时 `/chat` 会返回 `retrieved_knowledge`。

## 8. 可选：启用 LLM 劝阻话术

如果本地模型服务在 11545 端口：

```env
CHAT_LLM_ENABLED=1
OLLAMA_BASE_URL=http://localhost:11545
OLLAMA_MODEL=qwen3-lora
```

RAG 和 LLM 都不会直接决定风险分。风险分仍由 `RiskEngine` 和多轮规则评分负责。

## 9. Docker Compose 方式

推荐直接使用 Docker Compose：

```bash
docker compose up --build -d postgres api
docker compose --profile rag run --rm rag-import
docker compose --profile rag run --rm rag-download
docker compose --profile rag run --rm rag-embed
```

`rag-download` 和 `rag-embed` 都使用 ModelScope。
