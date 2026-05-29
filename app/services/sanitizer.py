"""Sensitive data sanitizer — masks PII before storage or API response.

All functions are pure: they accept a string and return a new string with
sensitive patterns replaced by non-reversible masks.  The original value
is never stored alongside the masked version.
"""

from __future__ import annotations

import re

# ── Core patterns ─────────────────────────────────────────────────────────

# Chinese mobile: 1[3-9]X-XXXX-XXXX  (keep first 3 + last 2)
_PHONE_RE = re.compile(r"(1[3-9]\d)\d{4}(\d{4})")

# Chinese ID card: 18 digits (or 17 + X)  (keep first 4 + last 4)
_ID_CARD_RE = re.compile(r"(\d{4})\d{10}(\d{3}[\dXx])")

# Bank card: 13-19 consecutive digits surrounded by non-digits or boundaries
# (keep first 4 + last 4)
_BANK_CARD_RE = re.compile(r"(?<!\d)(\d{4})\d{5,11}(\d{4})(?!\d)")

# Verification code: 4-8 digits immediately after a trigger word
_CODE_RE = re.compile(
    r"(验证码|校验码|动态码|短信码|code|captcha)\s*[:：]?\s*(\d{4,8})",
    re.IGNORECASE,
)

# Email: keep first char of local part + domain
_EMAIL_RE = re.compile(r"([a-zA-Z0-9])[a-zA-Z0-9.+_-]*(@[a-zA-Z0-9._-]+\.[a-zA-Z]{2,})")

# Generic secret-like tokens (JWT, API keys, long hex/base64 strings)
_TOKEN_RE = re.compile(
    r"(?:bearer\s+|token\s*[:=]\s*|sk[-_])[a-zA-Z0-9_-]{16,}",
    re.IGNORECASE,
)

# ── Public API ────────────────────────────────────────────────────────────

def mask_phone(text: str) -> str:
    """13812345678 → 138****5678"""
    return _PHONE_RE.sub(r"\1****\2", text)


def mask_id_card(text: str) -> str:
    """110101200001011234 → 1101***********1234"""
    return _ID_CARD_RE.sub(r"\1***********\2", text)


def mask_bank_card(text: str) -> str:
    """6222021234567890 → 6222*******7890"""
    return _BANK_CARD_RE.sub(r"\1*******\2", text)


def mask_code(text: str) -> str:
    """验证码:123456 → 验证码:******"""
    return _CODE_RE.sub(lambda m: f"{m.group(1)}:******", text)


def mask_email(text: str) -> str:
    """user@example.com → u***@example.com"""
    return _EMAIL_RE.sub(r"\1***\2", text)


def mask_token(text: str) -> str:
    """Bearer eyJhb...long → [TOKEN_REDACTED]"""
    return _TOKEN_RE.sub("[TOKEN_REDACTED]", text)


def sanitize_text(text: str) -> str:
    """Apply all masking rules in order.  Idempotent."""
    result = mask_phone(text)
    result = mask_id_card(result)
    result = mask_bank_card(result)
    result = mask_code(result)
    result = mask_email(result)
    result = mask_token(result)
    return result
