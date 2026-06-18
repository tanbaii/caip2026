# Local BGE-M3 + pgvector Wiring

The project expects the local BGE-M3 model at:

```text
model/bge-m3
```

Local `.env` should include:

```env
PGVECTOR_DSN=postgresql://postgres:postgres@localhost:5432/anti_fraud_rag
RAG_RETRIEVAL_ENABLED=1
BGE_M3_MODEL_NAME=./model/bge-m3
```

Docker Compose mounts the same directory into the API container:

```text
./model/bge-m3 -> /models/bge-m3
```

The API container uses the `rag-tools` Docker target by default, so it has
`FlagEmbedding` installed for query-time embedding.

Initialize the pgvector knowledge table:

```bash
docker compose up --build -d postgres api
docker compose --profile rag run --rm rag-import
docker compose --profile rag run --rm rag-embed
```

Verify the chain without loading the embedding model:

```bash
curl http://127.0.0.1:8000/health/rag
```

Important healthy fields:

```json
{
  "retriever_configured": true,
  "pgvector": {
    "connected": true,
    "vector_extension": true,
    "embedded_chunks": 1
  }
}
```

`embedded_chunks` should be greater than zero before `/chat` can return
semantic `retrieved_knowledge`.
