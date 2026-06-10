from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class SQLiteStorage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'general',
                    nickname TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_state (
                    user_id INTEGER PRIMARY KEY,
                    points INTEGER NOT NULL,
                    level INTEGER NOT NULL,
                    badges_json TEXT NOT NULL,
                    reports_submitted INTEGER NOT NULL,
                    scenarios_completed INTEGER NOT NULL,
                    high_risk_blocks INTEGER NOT NULL,
                    knowledge_queries INTEGER NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    report_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    score INTEGER NOT NULL,
                    verdict TEXT NOT NULL,
                    matched_keywords_json TEXT NOT NULL,
                    url_host TEXT,
                    content_summary TEXT,
                    reasons_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._ensure_column(conn, "reports", "url_host", "TEXT")
            self._ensure_column(conn, "reports", "content_summary", "TEXT")
            self._ensure_column(conn, "reports", "reasons_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "reports", "status", "TEXT NOT NULL DEFAULT 'pending'")
            conn.commit()

    @staticmethod
    def _ensure_column(
        conn: sqlite3.Connection,
        table: str,
        column: str,
        definition: str,
    ) -> None:
        columns = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def load_user_state(self, user_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT user_id, points, level, badges_json, reports_submitted,
                       scenarios_completed, high_risk_blocks, knowledge_queries
                FROM user_state
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

        if not row:
            return None

        return {
            "points": int(row["points"]),
            "level": int(row["level"]),
            "badges": json.loads(row["badges_json"]),
            "reports_submitted": int(row["reports_submitted"]),
            "scenarios_completed": int(row["scenarios_completed"]),
            "high_risk_blocks": int(row["high_risk_blocks"]),
            "knowledge_queries": int(row["knowledge_queries"]),
        }

    def save_user_state(self, user_id: int, state: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_state (
                    user_id, points, level, badges_json, reports_submitted,
                    scenarios_completed, high_risk_blocks, knowledge_queries, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    points = excluded.points,
                    level = excluded.level,
                    badges_json = excluded.badges_json,
                    reports_submitted = excluded.reports_submitted,
                    scenarios_completed = excluded.scenarios_completed,
                    high_risk_blocks = excluded.high_risk_blocks,
                    knowledge_queries = excluded.knowledge_queries,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    int(state["points"]),
                    int(state["level"]),
                    json.dumps(list(state["badges"]), ensure_ascii=False),
                    int(state["reports_submitted"]),
                    int(state["scenarios_completed"]),
                    int(state["high_risk_blocks"]),
                    int(state["knowledge_queries"]),
                ),
            )
            conn.commit()

    def add_report(
        self,
        report_id: str,
        user_id: int,
        score: int,
        verdict: str,
        matched_keywords: list[str],
        url_host: str | None = None,
        content_summary: str | None = None,
        reasons: list[str] | None = None,
        status: str = "pending",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reports (
                    report_id, user_id, score, verdict, matched_keywords_json,
                    url_host, content_summary, reasons_json, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    user_id,
                    int(score),
                    verdict,
                    json.dumps(sorted(set(matched_keywords)), ensure_ascii=False),
                    url_host,
                    content_summary,
                    json.dumps(reasons or [], ensure_ascii=False),
                    status,
                ),
            )
            conn.commit()

    def list_reports(
        self,
        user_id: int,
        limit: int = 20,
        start_at: str | None = None,
        end_at: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized_limit = max(1, min(100, int(limit)))
        sql = (
            """
            SELECT report_id, user_id, score, verdict, matched_keywords_json,
                   url_host, content_summary, reasons_json, status, created_at
            FROM reports
            WHERE user_id = ?
            """
        )
        params: list[Any] = [user_id]

        if start_at:
            sql += " AND created_at >= ?"
            params.append(start_at)

        if end_at:
            sql += " AND created_at <= ?"
            params.append(end_at)

        sql += " ORDER BY created_at DESC, report_id DESC LIMIT ?"
        params.append(normalized_limit)

        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()

        return [
            {
                "report_id": str(row["report_id"]),
                "user_id": int(row["user_id"]),
                "score": int(row["score"]),
                "verdict": str(row["verdict"]),
                "matched_keywords": json.loads(row["matched_keywords_json"]),
                "url_host": str(row["url_host"]) if row["url_host"] else None,
                "content_summary": str(row["content_summary"]) if row["content_summary"] else None,
                "reasons": json.loads(row["reasons_json"] or "[]"),
                "status": str(row["status"] or "pending"),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]

    def update_report_status(self, report_id: str, status: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE reports SET status = ? WHERE report_id = ?",
                (status, report_id),
            )
            conn.commit()
        return cursor.rowcount > 0

    # ── 用户认证 CRUD ──

    def create_user(
        self,
        username: str,
        password_hash: str,
        role: str = "general",
        nickname: str | None = None,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (username, password_hash, role, nickname)
                VALUES (?, ?, ?, ?)
                """,
                (username, password_hash, role, nickname),
            )
            conn.commit()
            user_id = cursor.lastrowid
            return self.get_user_by_id(user_id)  # type: ignore[return-value]

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, username, role, nickname, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "id": int(row["id"]),
            "username": str(row["username"]),
            "role": str(row["role"]),
            "nickname": row["nickname"],
            "created_at": str(row["created_at"]),
        }

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, role, nickname, created_at FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        if not row:
            return None
        return {
            "id": int(row["id"]),
            "username": str(row["username"]),
            "password_hash": str(row["password_hash"]),
            "role": str(row["role"]),
            "nickname": row["nickname"],
            "created_at": str(row["created_at"]),
        }

    def update_password_hash(self, user_id: int, password_hash: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (password_hash, user_id),
            )
            conn.commit()

    def get_leaderboard(self, limit: int = 20) -> list[dict[str, Any]]:
        normalized_limit = max(1, min(100, limit))
        sql = """
            SELECT u.id, u.username, u.nickname, u.role,
                   COALESCE(us.points, 0) AS points,
                   COALESCE(us.level, 1) AS level,
                   COALESCE(us.badges_json, '[]') AS badges_json
            FROM users u
                   LEFT JOIN user_state us ON u.id = us.user_id
                   ORDER BY points DESC, u.created_at ASC
            LIMIT ?
        """
        with self._connect() as conn:
            rows = conn.execute(sql, (normalized_limit,)).fetchall()
        return [
            {
                "rank": idx + 1,
                "user_id": int(row["id"]),
                "username": str(row["username"]),
                "nickname": row["nickname"],
                "role": str(row["role"]),
                "points": int(row["points"]),
                "level": int(row["level"]),
                "badges": json.loads(row["badges_json"]),
            }
            for idx, row in enumerate(rows)
        ]
