from __future__ import annotations

import hashlib
import hmac
import time
import base64
import json
import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.storage import SQLiteStorage


class AuthService:
    """轻量级认证服务：密码哈希 + JWT 签发/验证。"""

    def __init__(self, storage: "SQLiteStorage", secret_key: str) -> None:
        self.storage = storage
        self._secret_key = secret_key
        self._token_expiry = 86400  # 24 小时

    # ── 密码工具 ──

    @staticmethod
    def hash_password(plain_password: str) -> str:
        """Use PBKDF2-HMAC-SHA256 with a random per-user salt."""
        iterations = 210_000
        salt = secrets.token_bytes(16)
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt,
            iterations,
        )
        return "pbkdf2_sha256${}${}${}".format(
            iterations,
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(derived).decode("ascii"),
        )

    @staticmethod
    def verify_password(plain_password: str, stored_hash: str) -> bool:
        if not stored_hash or "$" not in stored_hash:
            return False
        try:
            parts = stored_hash.split("$")
            if parts[0] == "pbkdf2_sha256" and len(parts) == 4:
                iterations = int(parts[1])
                salt = base64.urlsafe_b64decode(parts[2].encode("ascii"))
                expected = hashlib.pbkdf2_hmac(
                    "sha256",
                    plain_password.encode("utf-8"),
                    salt,
                    iterations,
                )
                received = base64.urlsafe_b64decode(parts[3].encode("ascii"))
                return hmac.compare_digest(expected, received)

            # Backward compatibility for accounts created by earlier builds.
            if parts[0] == "sha256" and len(parts) == 3:
                expected = hashlib.sha256((plain_password + parts[1]).encode("utf-8")).hexdigest()
                return hmac.compare_digest(expected, parts[2])
            return False
        except (ValueError, AttributeError):
            return False

    # ── JWT 简易实现（无外部依赖） ──

    def _encode_jwt(self, payload: dict[str, object]) -> str:
        """手动构建 JWT（header.payload.signature）。"""
        import hashlib
        import base64
        import json
        import time

        header = {"alg": "HS256", "typ": "JWT"}
        payload["exp"] = int(time.time()) + self._token_expiry
        payload["iat"] = int(time.time())

        def b64url(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

        h = b64url(json.dumps(header, separators=(",", ":")).encode())
        p = b64url(json.dumps(payload, separators=(",", ":")).encode())
        signing_input = f"{h}.{p}"
        sig = hmac.new(
            self._secret_key.encode(),
            signing_input.encode(),
            hashlib.sha256,
        ).digest()
        return f"{signing_input}.{b64url(sig)}"

    def decode_jwt(self, token: str) -> dict[str, object] | None:
        """解码并验证 JWT，返回 payload 或 None。"""
        import hashlib
        import base64
        import json
        import time

        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            signing_input = f"{parts[0]}.{parts[1]}"
            sig_expected = hmac.new(
                self._secret_key.encode(),
                signing_input.encode(),
                hashlib.sha256,
            ).digest()

            # 补齐 padding
            padded = parts[2] + "=" * (4 - len(parts[2]) % 4)
            sig_received = base64.urlsafe_b64decode(padded)

            if not hmac.compare_digest(sig_expected, sig_received):
                return None

            payload_json = base64.urlsafe_b64decode(
                parts[1] + "=" * (4 - len(parts[1]) % 4)
            )
            payload = json.loads(payload_json)

            if payload.get("exp", 0) < time.time():
                return None
            return payload
        except (ValueError, KeyError, json.JSONDecodeError, Exception):
            return None

    # ── 业务方法 ──

    def register(
        self,
        username: str,
        password: str,
        role: str = "general",
        nickname: str | None = None,
    ) -> dict[str, object]:
        """注册新用户，返回登录响应（自动签发 token）。"""
        existing = self.storage.get_user_by_username(username)
        if existing:
            raise ValueError("用户名已被注册")

        password_hash = self.hash_password(password)
        user = self.storage.create_user(username, password_hash, role, nickname)

        token_payload = {
            "sub": str(user["id"]),
            "username": user["username"],
            "role": user["role"],
        }
        token = self._encode_jwt(token_payload)

        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "nickname": user.get("nickname"),
        }

    def login(self, username: str, password: str) -> dict[str, object]:
        """验证凭据并签发 JWT。"""
        user = self.storage.get_user_by_username(username)
        if not user:
            raise ValueError("用户名或密码错误")

        if not self.verify_password(password, user["password_hash"]):
            raise ValueError("用户名或密码错误")

        if str(user["password_hash"]).startswith("sha256$"):
            self.storage.update_password_hash(user["id"], self.hash_password(password))

        token_payload = {
            "sub": str(user["id"]),
            "username": user["username"],
            "role": user["role"],
        }
        token = self._encode_jwt(token_payload)

        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "nickname": user.get("nickname"),
        }

    def get_current_user(self, token: str) -> dict[str, object] | None:
        """从 JWT 提取用户信息并补充 DB 数据。"""
        payload = self.decode_jwt(token)
        if not payload:
            return None

        user_id = int(payload["sub"])
        user = self.storage.get_user_by_id(user_id)
        if not user:
            return None

        return user
