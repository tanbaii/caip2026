#!/usr/bin/env python3
"""
Build BM25 index for hybrid retrieval.

Reads knowledge documents from app/data/knowledge_base/ and builds
a BM25 keyword index for use with HybridRetriever.

Usage:
    python scripts/build_knowledge_index.py
    python scripts/build_knowledge_index.py --output ./bm25_index.pkl
"""

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))

from app.services.bm25_index import BM25Index
from app.services.text_splitter import MarkdownTextSplitter, JsonRuleSplitter


KNOWLEDGE_DIR = PROJECT_DIR / "app" / "data" / "knowledge_base"
DEFAULT_OUTPUT = KNOWLEDGE_DIR / "bm25_index.pkl"


def load_all_documents() -> list[dict]:
    """Load and chunk all knowledge documents."""
    splitter = MarkdownTextSplitter(chunk_size=512, chunk_overlap=128, max_chunk_size=1024)
    all_docs: list[dict] = []

    # 1. Fraud rules (JSON)
    rules_dir = KNOWLEDGE_DIR / "fraud_rules"
    if rules_dir.exists():
        for rf in sorted(rules_dir.glob("*.json")):
            try:
                with open(rf, "r", encoding="utf-8") as f:
                    rule = json.load(f)
                chunks = JsonRuleSplitter.split_rule(rule, source=str(rf.name))
                for c in chunks:
                    all_docs.append({"chunk_id": c.chunk_id, "content": c.content})
            except Exception as e:
                print(f"  Skip {rf.name}: {e}")

    # 2. Markdown knowledge files
    md_dirs: dict[str, str] = {
        "fraud_types": "fraud_type",
        "fraud_scripts": "fraud_script",
        "laws": "law",
        "faq": "faq",
    }
    for subdir, doc_type in md_dirs.items():
        sub_path = KNOWLEDGE_DIR / subdir
        if sub_path.exists():
            for mf in sorted(sub_path.glob("*.md")):
                try:
                    text = mf.read_text(encoding="utf-8")
                    title = mf.stem
                    chunks = splitter.split_text(
                        text,
                        source=str(mf.name),
                        doc_type=doc_type,
                        title=title,
                    )
                    for c in chunks:
                        all_docs.append({"chunk_id": c.chunk_id, "content": c.content})
                except Exception as e:
                    print(f"  Skip {mf.name}: {e}")

    print(f"Loaded {len(all_docs)} chunks from knowledge base")
    return all_docs


def main():
    parser = argparse.ArgumentParser(description="Build BM25 index for hybrid retrieval")
    parser.add_argument("--output", "-o", type=str, default=str(DEFAULT_OUTPUT),
                        help="Output path for BM25 index pickle")
    parser.add_argument("--force", action="store_true", help="Force rebuild")
    args = parser.parse_args()

    output_path = Path(args.output)

    if output_path.exists() and not args.force:
        print(f"Index already exists: {output_path}")
        print("Use --force to rebuild.")
        return

    docs = load_all_documents()
    if not docs:
        print("No documents found. Aborting.")
        return

    print(f"Building BM25 index with {len(docs)} documents...")
    index = BM25Index()
    index.build(docs)
    index.save(output_path)
    print(f"BM25 index saved to {output_path}")
    print(f"Documents: {len(index.corpus)}")


if __name__ == "__main__":
    main()
