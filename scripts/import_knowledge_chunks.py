from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.env_loader import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")
DEFAULT_KNOWLEDGE_PATH = PROJECT_ROOT / "app" / "data" / "knowledge_base.json"
SCHEMA_PATH = PROJECT_ROOT / "app" / "db" / "pgvector_schema.sql"


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if value:
        return [str(value)]
    return []


def _join_section(label: str, values: list[str]) -> str:
    if not values:
        return ""
    return f"{label}: " + " ; ".join(values)


def build_chunks(data: dict[str, Any]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []

    for scam in data.get("scams", []):
        source_id = str(scam.get("id", ""))
        scam_type = str(scam.get("type", ""))
        name = str(scam.get("name", scam_type or source_id))
        keywords = _as_list(scam.get("keywords"))

        sections = [
            ("overview", "典型案例", _as_list(scam.get("typical_case"))),
            ("tactics", "常见套路", _as_list(scam.get("tactics"))),
            ("red_flags", "风险信号", _as_list(scam.get("red_flags"))),
            ("prevention", "处置建议", _as_list(scam.get("prevention"))),
        ]

        for chunk_kind, label, values in sections:
            content_parts = [
                f"骗局类型: {name}",
                f"类型标识: {scam_type}",
                _join_section("关键词", keywords),
                _join_section(label, values),
                _join_section("法律参考", _as_list(scam.get("legal_refs"))),
            ]
            content = "\n".join(part for part in content_parts if part)
            if not content.strip():
                continue
            chunks.append(
                {
                    "source_type": "scam",
                    "source_id": source_id,
                    "scam_type": scam_type,
                    "title": f"{name} - {label}",
                    "content": content,
                    "keywords": keywords,
                    "metadata": {"chunk_kind": chunk_kind, "source_name": name},
                }
            )

    for index, law in enumerate(data.get("laws", []), start=1):
        name = str(law.get("name", f"law-{index}"))
        highlights = _as_list(law.get("highlights"))
        content = "\n".join(
            part
            for part in [
                f"法规名称: {name}",
                _join_section("要点", highlights),
            ]
            if part
        )
        if content.strip():
            chunks.append(
                {
                    "source_type": "law",
                    "source_id": f"L{index:03d}",
                    "scam_type": None,
                    "title": name,
                    "content": content,
                    "keywords": [],
                    "metadata": {"chunk_kind": "law_highlight"},
                }
            )

    return chunks


def _load_dsn(cli_dsn: str | None) -> str:
    dsn = cli_dsn or os.getenv("PGVECTOR_DSN") or os.getenv("DATABASE_URL")
    if not dsn:
        raise SystemExit("Set PGVECTOR_DSN or pass --dsn to connect to PostgreSQL.")
    return dsn


def main() -> None:
    parser = argparse.ArgumentParser(description="Import knowledge_base.json into pgvector chunks.")
    parser.add_argument("--dsn", default=None, help="PostgreSQL DSN. Defaults to PGVECTOR_DSN or DATABASE_URL.")
    parser.add_argument("--knowledge-path", type=Path, default=DEFAULT_KNOWLEDGE_PATH)
    parser.add_argument("--reset", action="store_true", help="Delete existing rows before importing.")
    args = parser.parse_args()

    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("Install RAG dependencies first: pip install -r requirements-rag.txt") from exc

    dsn = _load_dsn(args.dsn)
    data = json.loads(args.knowledge_path.read_text(encoding="utf-8"))
    chunks = build_chunks(data)

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
            if args.reset:
                cur.execute("TRUNCATE TABLE knowledge_chunks RESTART IDENTITY")
            for chunk in chunks:
                cur.execute(
                    """
                    INSERT INTO knowledge_chunks
                        (source_type, source_id, scam_type, title, content, keywords, metadata)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        chunk["source_type"],
                        chunk["source_id"],
                        chunk["scam_type"],
                        chunk["title"],
                        chunk["content"],
                        chunk["keywords"],
                        json.dumps(chunk["metadata"], ensure_ascii=False),
                    ),
                )
        conn.commit()

    print(f"Imported {len(chunks)} knowledge chunks.")


if __name__ == "__main__":
    main()
