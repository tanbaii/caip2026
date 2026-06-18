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

DEFAULT_MODEL_ID = "BAAI/bge-m3"
DEFAULT_LOCAL_DIR = PROJECT_ROOT / "data" / "models" / "bge-m3"


def main() -> None:
    parser = argparse.ArgumentParser(description="Download BGE-M3 from ModelScope into a local directory.")
    parser.add_argument(
        "--model-id",
        default=os.getenv("MODELSCOPE_BGE_M3_MODEL_ID", DEFAULT_MODEL_ID),
        help="ModelScope model id, for example BAAI/bge-m3.",
    )
    parser.add_argument(
        "--local-dir",
        type=Path,
        default=Path(os.getenv("MODELSCOPE_BGE_M3_LOCAL_DIR", str(DEFAULT_LOCAL_DIR))),
        help="Directory where the model files will be stored.",
    )
    args = parser.parse_args()

    try:
        from modelscope import snapshot_download
    except ImportError as exc:
        raise SystemExit("Install RAG dependencies first: pip install -r requirements-rag.txt") from exc

    args.local_dir.mkdir(parents=True, exist_ok=True)
    model_dir = snapshot_download(
        args.model_id,
        local_dir=str(args.local_dir),
    )
    print(f"ModelScope model downloaded: {model_dir}")
    print(f"Set BGE_M3_MODEL_NAME={model_dir}")


if __name__ == "__main__":
    main()
