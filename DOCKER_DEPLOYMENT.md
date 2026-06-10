# Docker Compose 部署说明

## 服务组成

`docker-compose.yml` 提供以下服务：

- `api`：FastAPI 后端，同时托管构建后的 Vue 前端。
- `postgres`：PostgreSQL + pgvector。
- `rag-import`：可选任务，把 `knowledge_base.json` 导入 `knowledge_chunks`。
- `rag-download`：可选任务，从 ModelScope 下载 `BAAI/bge-m3` 到 Docker volume。
- `rag-embed`：可选任务，用本地 BGE-M3 模型给空 embedding 的 chunk 生成向量。

默认启动只跑 `api` 和 `postgres`。RAG 导入、模型下载和 embedding 通过 `rag` profile 手动执行。

## 首次启动

```bash
docker compose up --build -d
```

访问：

```text
http://localhost:8000
```

健康检查：

```bash
docker compose ps
curl http://localhost:8000/health
```

## 常用环境变量

可以在项目根目录 `.env` 中配置：

```env
APP_PORT=8000

POSTGRES_DB=anti_fraud_rag
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_PORT=5432

CHAT_FLOW_ENGINE=classic
CHAT_LLM_ENABLED=0
RAG_RETRIEVAL_ENABLED=0
RAG_LLM_ENABLED=0

DOCKER_OLLAMA_BASE_URL=http://host.docker.internal:11545
OLLAMA_MODEL=qwen3-lora

MODELSCOPE_BGE_M3_MODEL_ID=BAAI/bge-m3
BGE_M3_USE_FP16=0
```

启用 LangGraph：

```env
CHAT_FLOW_ENGINE=langgraph
```

如果宿主机已经开了本地大模型 11545 端口，容器内不要写 `localhost:11545`，应使用：

```env
DOCKER_OLLAMA_BASE_URL=http://host.docker.internal:11545
CHAT_LLM_ENABLED=1
```

Compose 已经配置：

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

## 初始化 pgvector

`postgres` 第一次创建数据卷时会自动执行：

```text
app/db/pgvector_schema.sql
```

它会创建：

- `vector` 扩展
- `knowledge_chunks` 表
- cosine ivfflat 索引
- `updated_at` 触发器

如果数据库卷已经存在，PostgreSQL 不会再次自动执行 `/docker-entrypoint-initdb.d`。此时运行 `rag-import` 会再次执行 schema SQL。

## 导入知识 chunk

```bash
docker compose --profile rag run --rm rag-import
```

这个任务会：

- 连接 compose 内的 `postgres`
- 执行 pgvector schema
- 清空并重建 `knowledge_chunks`
- 从 `app/data/knowledge_base.json` 导入 chunk

## 从 ModelScope 下载 BGE-M3

不走 HuggingFace。先从 ModelScope 下载到 Docker volume：

```bash
docker compose --profile rag run --rm rag-download
```

默认模型 ID：

```text
BAAI/bge-m3
```

容器内模型目录：

```text
/models/bge-m3
```

对应 Docker volume：

```text
modelscope_models
```

## 生成 BGE-M3 embedding

```bash
docker compose --profile rag run --rm rag-embed
```

`rag-embed` 会先确保 `/models/bge-m3` 已从 ModelScope 下载，再执行：

```bash
python scripts/embed_knowledge_chunks.py --model /models/bge-m3
```

注意：

- 首次下载模型时间较长。
- 模型文件保存在 Docker volume `modelscope_models`。
- ModelScope SDK 缓存在 Docker volume `modelscope_cache`。
- 默认 CPU 可跑，但会比较慢。
- 如果只想先验证系统流程，可以暂时不执行 embedding，并保持 `RAG_RETRIEVAL_ENABLED=0`。

## 启用 RAG 检索

导入 chunk 并生成 embedding 后，在 `.env` 中设置：

```env
RAG_RETRIEVAL_ENABLED=1
RAG_TOP_K=5
```

然后重启 API：

```bash
docker compose up -d --build api
```

RAG 仍然只是旁路召回，不会决定风险分。

## 启用本地 LLM 回复

宿主机模型服务已在 11545 端口时：

```env
CHAT_LLM_ENABLED=1
DOCKER_OLLAMA_BASE_URL=http://host.docker.internal:11545
OLLAMA_MODEL=qwen3-lora
```

重启：

```bash
docker compose up -d --build api
```

## 常用维护命令

查看日志：

```bash
docker compose logs -f api
docker compose logs -f postgres
```

停止服务：

```bash
docker compose down
```

停止并删除数据卷：

```bash
docker compose down -v
```

重新构建：

```bash
docker compose build --no-cache api
docker compose up -d
```

进入 API 容器：

```bash
docker compose exec api bash
```

## 数据持久化

Compose 使用四个 volume：

- `api_runtime`：保存 SQLite 运行库 `/app/runtime/anti_fraud.db`。
- `pgvector_data`：保存 PostgreSQL 数据。
- `modelscope_models`：保存从 ModelScope 下载的 BGE-M3 模型文件。
- `modelscope_cache`：保存 ModelScope SDK 缓存。

删除这些 volume 会清空对应数据。
