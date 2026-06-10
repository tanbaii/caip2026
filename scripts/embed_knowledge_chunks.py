from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.env_loader import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")
DEFAULT_MODEL = "BAAI/bge-m3"


def _load_dsn(cli_dsn: str | None) -> str:
    dsn = cli_dsn or os.getenv("PGVECTOR_DSN") or os.getenv("DATABASE_URL")
    if not dsn:
        raise SystemExit("Set PGVECTOR_DSN or pass --dsn to connect to PostgreSQL.")
    return dsn


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.8f}" for value in values) + "]"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate BGE-M3 embeddings for empty knowledge chunks.")
    parser.add_argument("--dsn", default=None, help="PostgreSQL DSN. Defaults to PGVECTOR_DSN or DATABASE_URL.")
    parser.add_argument("--model", default=os.getenv("BGE_M3_MODEL_NAME", DEFAULT_MODEL))
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--max-length", type=int, default=8192)
    parser.add_argument("--use-fp16", action="store_true")
    args = parser.parse_args()

    try:
        import psycopg
        from FlagEmbedding import BGEM3FlagModel
    except ImportError as exc:
        raise SystemExit("Install RAG dependencies first: pip install -r requirements-rag.txt") from exc

    model = BGEM3FlagModel(args.model, use_fp16=args.use_fp16)
    dsn = _load_dsn(args.dsn)
    updated = 0

    with psycopg.connect(dsn) as conn:
        while True:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, title, content
                    FROM knowledge_chunks
                    WHERE embedding IS NULL
                    ORDER BY id
                    LIMIT %s
                    """,
                    (args.limit,),
                )
                rows = cur.fetchall()

            if not rows:
                break

            texts = [f"{title}\n{content}" for _, title, content in rows]
            encoded = model.encode(
                texts,
                batch_size=args.batch_size,
                max_length=args.max_length,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )
            vectors = encoded["dense_vecs"]

            with conn.cursor() as cur:
                for (chunk_id, _, _), vector in zip(rows, vectors, strict=True):
                    cur.execute(
                        "UPDATE knowledge_chunks SET embedding = %s::vector WHERE id = %s",
                        (_vector_literal(vector.tolist()), chunk_id),
                    )
                    updated += 1
            conn.commit()
            print(f"Updated {updated} chunks...")

    print(f"Embedding complete. Updated {updated} chunks.")


if __name__ == "__main__":
    main()
