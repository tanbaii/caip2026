from __future__ import annotations

import re
from collections.abc import Iterable


DEFAULT_NEGATION_PREFIXES = (
    "没有",
    "并未",
    "未曾",
    "未",
    "没让",
    "没要",
    "没",
    "不需要",
    "无需",
    "不会",
    "不应",
    "不能",
    "不要",
    "拒绝",
    "禁止",
    "避免",
    "no ",
    "not ",
    "never ",
)

DEFAULT_CONTRAST_MARKERS = ("但是", "不过", "然而", "而是", "但")
_CLAUSE_SEPARATORS = "，。！？；,!?;\n"


def find_effective_terms(
    text: str,
    terms: Iterable[str],
    *,
    prefixes: Iterable[str] = DEFAULT_NEGATION_PREFIXES,
    contrast_markers: Iterable[str] = DEFAULT_CONTRAST_MARKERS,
    window: int = 12,
    negation_exempt: bool = False,
) -> list[str]:
    normalized = text.lower()
    hits: list[str] = []

    for term in terms:
        normalized_term = str(term).lower()
        if not normalized_term:
            continue
        for match in re.finditer(re.escape(normalized_term), normalized):
            if negation_exempt or not is_negated(
                normalized,
                match.start(),
                match.end(),
                prefixes=prefixes,
                contrast_markers=contrast_markers,
                window=window,
            ):
                hits.append(str(term))
                break

    return hits


def is_negated(
    text: str,
    start: int,
    end: int,
    *,
    prefixes: Iterable[str] = DEFAULT_NEGATION_PREFIXES,
    contrast_markers: Iterable[str] = DEFAULT_CONTRAST_MARKERS,
    window: int = 12,
) -> bool:
    clause_start, clause_end = _clause_bounds(text, start, end, contrast_markers)
    prefix = text[max(clause_start, start - window):start]
    suffix = text[end:min(clause_end, end + window)]
    normalized_prefixes = tuple(str(item).lower() for item in prefixes if item)

    if any(token in prefix for token in normalized_prefixes):
        return True

    # Handles educational statements such as "公检法不会要求转账" where the
    # negation follows the subject trigger rather than preceding it.
    return any(suffix.startswith(token) for token in normalized_prefixes)


def _clause_bounds(
    text: str,
    start: int,
    end: int,
    contrast_markers: Iterable[str],
) -> tuple[int, int]:
    left = 0
    right = len(text)

    for index in range(start - 1, -1, -1):
        if text[index] in _CLAUSE_SEPARATORS:
            left = index + 1
            break

    for marker in contrast_markers:
        marker_text = str(marker).lower()
        marker_index = text.rfind(marker_text, left, start)
        if marker_index >= left:
            left = max(left, marker_index + len(marker_text))

    for index in range(end, len(text)):
        if text[index] in _CLAUSE_SEPARATORS:
            right = index
            break

    for marker in contrast_markers:
        marker_text = str(marker).lower()
        marker_index = text.find(marker_text, end, right)
        if marker_index != -1:
            right = min(right, marker_index)

    return left, right
