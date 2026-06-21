"""
Markdown-aware Text Splitter for Anti-Fraud Knowledge Documents
支持按 Markdown 标题层级智能分块，保持条款完整性

Adapted from caip2026 sub-project rag_system/utils/text_splitter.py
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class TextChunk:
    """文本块数据结构"""
    content: str
    source: str
    doc_type: str  # law / fraud_type / fraud_rule / fraud_script / faq
    title: str = ""
    section: str = ""
    chunk_id: str = ""
    metadata: Dict[str, Any] | None = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class MarkdownTextSplitter:
    """Markdown 感知文本分块器

    分块策略：
    1. 优先按二级标题 (##) 切分
    2. 若单节过长，按三级标题 (###) 进一步细分
    3. 若仍过长，按段落 + 滑动窗口切分
    4. Chunk 之间保留 overlap
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 128,
        max_chunk_size: int = 1024,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_chunk_size = max_chunk_size
        self.char_per_token = 1.5

    def _estimate_tokens(self, text: str) -> int:
        return int(len(text) / self.char_per_token)

    def _split_by_headers(self, text: str, header_level: str = "##") -> List[str]:
        pattern = rf'\n{header_level} '
        parts = re.split(pattern, text)
        if len(parts) <= 1:
            return [text]

        result = []
        prefix = parts[0].strip()
        for part in parts[1:]:
            part = part.strip()
            if not part:
                continue
            lines = part.split('\n', 1)
            header = lines[0].strip()
            content = lines[1].strip() if len(lines) > 1 else ""
            if prefix and not result:
                content = f"{prefix}\n\n{header}\n{content}"
            else:
                content = f"{header}\n{content}"
            result.append(content)
        return result

    def _split_paragraphs(self, text: str) -> List[str]:
        paragraphs = []
        current = []
        for line in text.split('\n'):
            stripped = line.strip()
            if stripped:
                current.append(line)
            else:
                if current:
                    paragraphs.append('\n'.join(current))
                    current = []
        if current:
            paragraphs.append('\n'.join(current))
        return paragraphs

    def _merge_chunks(self, chunks: List[str], max_tokens: int) -> List[str]:
        if not chunks:
            return []
        merged = []
        current = chunks[0]
        current_tokens = self._estimate_tokens(current)
        for chunk in chunks[1:]:
            chunk_tokens = self._estimate_tokens(chunk)
            if current_tokens + chunk_tokens <= max_tokens:
                current += '\n\n' + chunk
                current_tokens += chunk_tokens
            else:
                merged.append(current)
                current = chunk
                current_tokens = chunk_tokens
        if current:
            merged.append(current)
        return merged

    def _add_overlap(self, chunks: List[str]) -> List[str]:
        if len(chunks) <= 1 or self.chunk_overlap <= 0:
            return chunks
        result = [chunks[0]]
        overlap_chars = int(self.chunk_overlap * self.char_per_token)
        for i in range(1, len(chunks)):
            prev = chunks[i - 1]
            curr = chunks[i]
            overlap_text = prev[-overlap_chars:] if len(prev) > overlap_chars else prev
            result.append(f"[前文衔接]\n{overlap_text}\n\n[当前内容]\n{curr}")
        return result

    def split_text(
        self,
        text: str,
        source: str = "",
        doc_type: str = "",
        title: str = "",
    ) -> List[TextChunk]:
        sections = self._split_by_headers(text, "##")
        all_chunks: List[str] = []

        for section in sections:
            if self._estimate_tokens(section) <= self.max_chunk_size:
                all_chunks.append(section)
                continue
            sub_sections = self._split_by_headers(section, "###")
            for sub in sub_sections:
                if self._estimate_tokens(sub) <= self.max_chunk_size:
                    all_chunks.append(sub)
                    continue
                paragraphs = self._split_paragraphs(sub)
                merged = self._merge_chunks(paragraphs, self.chunk_size)
                all_chunks.extend(merged)

        all_chunks = self._add_overlap(all_chunks)

        result = []
        for idx, chunk_text in enumerate(all_chunks):
            section_title = ""
            for line in chunk_text.split('\n')[:3]:
                stripped = line.strip()
                if stripped.startswith('## ') or stripped.startswith('### '):
                    section_title = stripped.lstrip('#').strip()
                    break

            chunk = TextChunk(
                content=chunk_text,
                source=source,
                doc_type=doc_type,
                title=title,
                section=section_title,
                chunk_id=f"{doc_type}_{hash(source) % 10000:04d}_{idx:04d}",
                metadata={"chunk_index": idx, "total_chunks": len(all_chunks)},
            )
            result.append(chunk)
        return result


class JsonRuleSplitter:
    """将 fraud_rules/ 下的 JSON 规则转换为文本 Chunk"""

    @staticmethod
    def split_rule(rule_data: Dict[str, Any], source: str = "") -> List[TextChunk]:
        chunks = []
        rule_id = rule_data.get("rule_id", "")
        fraud_type = rule_data.get("fraud_type", "")
        risk_level = rule_data.get("risk_level", "")

        main_text = (
            f"规则编号：{rule_id}\n"
            f"诈骗类型：{fraud_type}\n"
            f"风险等级：{risk_level}\n\n"
            f"关键词：{', '.join(rule_data.get('keywords', []))}\n\n"
            f"危险信号：\n"
            + "\n".join(f"- {flag}" for flag in rule_data.get("red_flags", []))
            + "\n\n触发条件：\n"
            + "\n".join(f"- {cond}" for cond in rule_data.get("trigger_conditions", []))
            + "\n\n推荐处置动作：\n"
            + "\n".join(f"- {action}" for action in rule_data.get("recommended_action", []))
        )

        chunks.append(TextChunk(
            content=main_text,
            source=source,
            doc_type="fraud_rule",
            title=f"规则_{rule_id}",
            section=fraud_type,
            chunk_id=f"rule_{rule_id}",
            metadata=rule_data,
        ))

        for keyword in rule_data.get("keywords", []):
            keyword_text = (
                f"规则编号：{rule_id}\n"
                f"诈骗类型：{fraud_type}\n"
                f"风险等级：{risk_level}\n"
                f"关键词：{keyword}\n\n"
                f"该关键词命中时，提示可能存在{fraud_type}诈骗风险。\n"
                f"相关危险信号：{', '.join(rule_data.get('red_flags', []))}"
            )
            chunks.append(TextChunk(
                content=keyword_text,
                source=source,
                doc_type="fraud_rule",
                title=f"关键词_{rule_id}_{keyword}",
                section=fraud_type,
                chunk_id=f"rule_{rule_id}_kw_{hash(keyword) % 1000:03d}",
                metadata={"keyword": keyword, **rule_data},
            ))
        return chunks
