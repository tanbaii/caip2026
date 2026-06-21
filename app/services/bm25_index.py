"""
BM25 Index Builder and Searcher
基于 jieba 分词和 rank-bm25 的关键词检索

Adapted from caip2026 sub-project rag_system/utils/bm25_index.py
"""

import pickle
from typing import Any, Dict, List

try:
    from rank_bm25 import BM25Okapi  # noqa: F401
except ImportError:
    BM25Okapi = None

try:
    import jieba
except ImportError:
    jieba = None


# jieba 初始化：添加反诈领域词典
_CUSTOM_WORDS = [
    "电信诈骗", "网络诈骗", "杀猪盘", "刷单返利", "冒充公检法",
    "钓鱼网站", "木马程序", "安全账户", "帮信罪", "跑分",
    "GOIP", "多卡宝", "银行卡", "支付账户", "个人信息",
    "安全账户", "验证码", "二维码", "裸聊敲诈", "AI换脸",
]
if jieba is not None:
    for word in _CUSTOM_WORDS:
        jieba.add_word(word)


def tokenize_chinese(text: str) -> List[str]:
    """中文分词，用于 BM25 索引构建"""
    if jieba is None:
        # Fallback: character-level bigrams (join to string for BM25Okapi)
        chars = [c for c in text if c.isalnum() or '一' <= c <= '鿿']
        return [''.join(chars[i:i + 2]) for i in range(0, len(chars) - 1)]

    stopwords = {
        "的", "了", "是", "在", "有", "和", "与", "或", "等", "及",
        "对", "为", "以", "可以", "进行", "需要", "通过", "根据",
        "按照", "关于", "及其", "其他", "相关", "下列", "以下",
        "以上", "第一", "第二", "第三", "第四", "第五", "应当",
        "不得", "必须", "应当", "或者", "以及", "作为", "由于",
        "因为", "所以", "因此", "但是", "然而", "如果", "则",
    }

    words = jieba.lcut(text)
    filtered = []
    for w in words:
        w = w.strip()
        if len(w) <= 1:
            continue
        if w in stopwords:
            continue
        if w.isdigit():
            continue
        if all(not c.isalnum() for c in w):
            continue
        filtered.append(w)
    return filtered


class BM25Index:
    """BM25 索引管理器"""

    def __init__(self):
        self.bm25: BM25Okapi | None = None
        self.corpus: List[str] = []
        self.tokenized_corpus: List[List[str]] = []
        self.doc_ids: List[str] = []

    def build(self, documents: List[Dict[str, Any]]) -> "BM25Index":
        if BM25Okapi is None:
            raise RuntimeError("rank_bm25 is not installed. Run: pip install rank-bm25")
        self.corpus = []
        self.tokenized_corpus = []
        self.doc_ids = []

        for doc in documents:
            content = doc.get("content", "")
            doc_id = doc.get("chunk_id", "")
            if not content or not doc_id:
                continue
            self.corpus.append(content)
            self.doc_ids.append(doc_id)
            self.tokenized_corpus.append(tokenize_chinese(content))

        self.bm25 = BM25Okapi(self.tokenized_corpus)
        return self

    def search(self, query: str, top_k: int = 20) -> List[Dict[str, Any]]:
        if self.bm25 is None:
            raise RuntimeError("BM25 index not built. Call build() first.")

        query_tokens = tokenize_chinese(query)
        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)
        top_indices = scores.argsort()[-top_k:][::-1]

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score <= 0:
                continue
            results.append({
                "chunk_id": str(self.doc_ids[idx]),
                "score": score,
                "index": int(idx),
                "source": "bm25",
            })
        return results

    def save(self, path: Any) -> None:
        import os as _os
        _path = str(path)
        _os.makedirs(_os.path.dirname(_path), exist_ok=True)
        data = {
            "corpus": self.corpus,
            "tokenized_corpus": self.tokenized_corpus,
            "doc_ids": self.doc_ids,
        }
        with open(_path, "wb") as f:
            pickle.dump(data, f)

    def load(self, path: Any) -> "BM25Index":
        if BM25Okapi is None:
            raise RuntimeError("rank_bm25 is not installed. Run: pip install rank-bm25")
        _path = str(path)
        if not __import__("os").path.exists(_path):
            raise FileNotFoundError(f"BM25 index not found: {_path}")
        with open(_path, "rb") as f:
            data = pickle.load(f)
        self.corpus = data["corpus"]
        self.tokenized_corpus = data["tokenized_corpus"]
        self.doc_ids = data["doc_ids"]
        self.bm25 = BM25Okapi(self.tokenized_corpus)
        return self
