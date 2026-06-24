from __future__ import annotations

import json
import sqlite3
import uuid
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
                    risk_level TEXT NOT NULL DEFAULT 'low',
                    channel TEXT NOT NULL DEFAULT 'web',
                    matched_keywords_json TEXT NOT NULL,
                    matched_rules_json TEXT NOT NULL DEFAULT '[]',
                    url_host TEXT,
                    url TEXT,
                    normalized_url TEXT,
                    content_summary TEXT,
                    content TEXT,
                    content_hash TEXT,
                    reasons_json TEXT NOT NULL DEFAULT '[]',
                    url_flags_json TEXT NOT NULL DEFAULT '[]',
                    score_breakdown_json TEXT NOT NULL DEFAULT '{}',
                    ruleset_versions_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'pending',
                    reviewer TEXT,
                    review_note TEXT,
                    reviewed_at TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_conversations (
                    conversation_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL DEFAULT '新对话',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT,
                    user_id INTEGER NOT NULL,
                    user_message TEXT NOT NULL,
                    assistant_reply TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    risk_score INTEGER NOT NULL,
                    intent TEXT NOT NULL,
                    matched_scams_json TEXT NOT NULL DEFAULT '[]',
                    session_stage TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scenario_progress (
                    user_id INTEGER NOT NULL,
                    scenario_id TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    completions INTEGER NOT NULL DEFAULT 0,
                    best_score INTEGER NOT NULL DEFAULT 0,
                    max_score INTEGER NOT NULL DEFAULT 0,
                    points_earned INTEGER NOT NULL DEFAULT 0,
                    first_completed_at TEXT,
                    last_completed_at TEXT,
                    PRIMARY KEY (user_id, scenario_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rule_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    change_summary TEXT NOT NULL,
                    text_version TEXT NOT NULL,
                    url_version TEXT NOT NULL,
                    risk_config_json TEXT NOT NULL,
                    url_config_json TEXT NOT NULL,
                    source_version_id INTEGER,
                    is_active INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._ensure_column(conn, "reports", "url_host", "TEXT")
            self._ensure_column(conn, "reports", "url", "TEXT")
            self._ensure_column(conn, "reports", "normalized_url", "TEXT")
            self._ensure_column(conn, "reports", "content_summary", "TEXT")
            self._ensure_column(conn, "reports", "content", "TEXT")
            self._ensure_column(conn, "reports", "content_hash", "TEXT")
            self._ensure_column(conn, "reports", "channel", "TEXT NOT NULL DEFAULT 'web'")
            self._ensure_column(conn, "reports", "risk_level", "TEXT NOT NULL DEFAULT 'low'")
            self._ensure_column(conn, "reports", "reasons_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "reports", "matched_rules_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "reports", "url_flags_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "reports", "score_breakdown_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(conn, "reports", "ruleset_versions_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(conn, "reports", "status", "TEXT NOT NULL DEFAULT 'pending'")
            self._ensure_column(conn, "reports", "reviewer", "TEXT")
            self._ensure_column(conn, "reports", "review_note", "TEXT")
            self._ensure_column(conn, "reports", "reviewed_at", "TEXT")
            self._ensure_column(conn, "reports", "updated_at", "TEXT")
            conn.execute(
                """
                UPDATE reports
                SET updated_at = COALESCE(NULLIF(updated_at, ''), created_at, CURRENT_TIMESTAMP)
                WHERE updated_at IS NULL OR updated_at = ''
                """
            )
            self._ensure_column(conn, "chat_messages", "conversation_id", "TEXT")
            conn.execute(
                """
                UPDATE chat_messages
                SET conversation_id = 'default-' || user_id
                WHERE conversation_id IS NULL OR conversation_id = ''
                """
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO chat_conversations (
                    conversation_id, user_id, title, created_at, updated_at
                )
                SELECT
                    conversation_id,
                    user_id,
                    '历史对话',
                    MIN(created_at),
                    MAX(created_at)
                FROM chat_messages
                WHERE conversation_id IS NOT NULL AND conversation_id != ''
                GROUP BY conversation_id, user_id
                """
            )
            conn.commit()

    @staticmethod
    def default_chat_conversation_id(user_id: int) -> str:
        return f"default-{int(user_id)}"

    def create_chat_conversation(
        self,
        *,
        user_id: int,
        title: str = "新对话",
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        normalized_id = conversation_id or uuid.uuid4().hex
        normalized_title = title.strip()[:80] if title.strip() else "新对话"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO chat_conversations (
                    conversation_id, user_id, title
                ) VALUES (?, ?, ?)
                """,
                (normalized_id, int(user_id), normalized_title),
            )
            conn.commit()
        conversation = self.get_chat_conversation(user_id=user_id, conversation_id=normalized_id)
        if conversation is None:
            raise RuntimeError("对话窗口创建失败")
        return conversation

    def get_chat_conversation(
        self,
        *,
        user_id: int,
        conversation_id: str,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT conversation_id, user_id, title, created_at, updated_at
                FROM chat_conversations
                WHERE user_id = ? AND conversation_id = ?
                """,
                (int(user_id), conversation_id),
            ).fetchone()
        return self._chat_conversation_row(row) if row else None

    def ensure_chat_conversation(
        self,
        *,
        user_id: int,
        conversation_id: str | None,
        title_hint: str = "",
    ) -> dict[str, Any]:
        normalized_id = conversation_id or self.default_chat_conversation_id(user_id)
        existing = self.get_chat_conversation(user_id=user_id, conversation_id=normalized_id)
        if existing is not None:
            return existing
        title = title_hint.strip()[:28] if title_hint.strip() else "新对话"
        return self.create_chat_conversation(
            user_id=user_id,
            conversation_id=normalized_id,
            title=title,
        )

    def add_chat_message(
        self,
        *,
        user_id: int,
        conversation_id: str | None = None,
        user_message: str,
        assistant_reply: str,
        risk_level: str,
        risk_score: int,
        intent: str,
        matched_scams: list[str],
        session_stage: str,
    ) -> None:
        conversation = self.ensure_chat_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
            title_hint=user_message,
        )
        normalized_id = str(conversation["conversation_id"])
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_messages (
                    conversation_id, user_id, user_message, assistant_reply, risk_level, risk_score,
                    intent, matched_scams_json, session_stage
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_id,
                    user_id,
                    user_message,
                    assistant_reply,
                    risk_level,
                    int(risk_score),
                    intent,
                    json.dumps(matched_scams, ensure_ascii=False),
                    session_stage,
                ),
            )
            conn.execute(
                """
                UPDATE chat_conversations
                SET
                    title = CASE WHEN title = '新对话' THEN ? ELSE title END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND conversation_id = ?
                """,
                ((user_message.strip()[:28] or "新对话"), int(user_id), normalized_id),
            )
            conn.commit()

    def list_chat_messages(self, user_id: int, limit: int = 50) -> list[dict[str, Any]]:
        normalized_limit = max(1, min(200, int(limit)))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, conversation_id, user_id, user_message, assistant_reply, risk_level,
                       risk_score, intent, matched_scams_json, session_stage, created_at
                FROM chat_messages
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (user_id, normalized_limit),
            ).fetchall()
        items = [
            {
                "id": int(row["id"]),
                "conversation_id": str(row["conversation_id"] or ""),
                "user_id": int(row["user_id"]),
                "user_message": str(row["user_message"]),
                "assistant_reply": str(row["assistant_reply"]),
                "risk_level": str(row["risk_level"]),
                "risk_score": int(row["risk_score"]),
                "intent": str(row["intent"]),
                "matched_scams": json.loads(row["matched_scams_json"] or "[]"),
                "session_stage": str(row["session_stage"]),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]
        return list(reversed(items))

    @staticmethod
    def _chat_message_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "conversation_id": str(row["conversation_id"] or ""),
            "user_id": int(row["user_id"]),
            "user_message": str(row["user_message"]),
            "assistant_reply": str(row["assistant_reply"]),
            "risk_level": str(row["risk_level"]),
            "risk_score": int(row["risk_score"]),
            "intent": str(row["intent"]),
            "matched_scams": json.loads(row["matched_scams_json"] or "[]"),
            "session_stage": str(row["session_stage"]),
            "created_at": str(row["created_at"]),
        }

    @staticmethod
    def _chat_conversation_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "conversation_id": str(row["conversation_id"]),
            "user_id": int(row["user_id"]),
            "title": str(row["title"] or "新对话"),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }

    def list_chat_conversations(self, user_id: int, limit: int = 50) -> list[dict[str, Any]]:
        normalized_limit = max(1, min(200, int(limit)))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    c.conversation_id,
                    c.user_id,
                    c.title,
                    c.created_at,
                    MAX(m.created_at) AS updated_at,
                    COUNT(m.id) AS message_count,
                    latest.user_message AS preview,
                    latest.risk_level AS risk_level,
                    latest.risk_score AS risk_score
                FROM chat_conversations c
                JOIN chat_messages m
                    ON m.conversation_id = c.conversation_id
                    AND m.user_id = c.user_id
                JOIN chat_messages latest
                    ON latest.id = (
                        SELECT id
                        FROM chat_messages
                        WHERE user_id = c.user_id
                            AND conversation_id = c.conversation_id
                        ORDER BY created_at DESC, id DESC
                        LIMIT 1
                    )
                WHERE c.user_id = ?
                GROUP BY c.conversation_id, c.user_id, c.title, c.created_at
                ORDER BY updated_at DESC, c.conversation_id DESC
                LIMIT ?
                """,
                (int(user_id), normalized_limit),
            ).fetchall()
        return [
            {
                "conversation_id": str(row["conversation_id"]),
                "user_id": int(row["user_id"]),
                "title": str(row["title"] or "新对话"),
                "message_count": int(row["message_count"] or 0),
                "risk_level": str(row["risk_level"] or "low"),
                "risk_score": int(row["risk_score"] or 0),
                "preview": str(row["preview"] or ""),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"] or row["created_at"]),
            }
            for row in rows
        ]

    def list_chat_conversation_messages(
        self,
        *,
        user_id: int,
        conversation_id: str,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, conversation_id, user_id, user_message, assistant_reply, risk_level,
                       risk_score, intent, matched_scams_json, session_stage, created_at
                FROM chat_messages
                WHERE user_id = ? AND conversation_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (int(user_id), conversation_id),
            ).fetchall()
        return [self._chat_message_row(row) for row in rows]

    def delete_chat_conversation(self, *, user_id: int, conversation_id: str) -> bool:
        with self._connect() as conn:
            existing = conn.execute(
                """
                SELECT conversation_id
                FROM chat_conversations
                WHERE user_id = ? AND conversation_id = ?
                """,
                (int(user_id), conversation_id),
            ).fetchone()
            if existing is None:
                return False
            conn.execute(
                "DELETE FROM chat_messages WHERE user_id = ? AND conversation_id = ?",
                (int(user_id), conversation_id),
            )
            conn.execute(
                "DELETE FROM chat_conversations WHERE user_id = ? AND conversation_id = ?",
                (int(user_id), conversation_id),
            )
            conn.commit()
        return True

    def create_rule_version(
        self,
        *,
        action: str,
        change_summary: str,
        text_version: str,
        url_version: str,
        risk_config: dict[str, Any],
        url_config: dict[str, Any],
        source_version_id: int | None = None,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute("UPDATE rule_versions SET is_active = 0 WHERE is_active = 1")
            cursor = conn.execute(
                """
                INSERT INTO rule_versions (
                    action, change_summary, text_version, url_version,
                    risk_config_json, url_config_json, source_version_id, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    action,
                    change_summary,
                    text_version,
                    url_version,
                    json.dumps(risk_config, ensure_ascii=False),
                    json.dumps(url_config, ensure_ascii=False),
                    source_version_id,
                ),
            )
            version_id = int(cursor.lastrowid)
            conn.commit()
        version = self.get_rule_version(version_id)
        if version is None:
            raise RuntimeError("规则版本写入失败")
        return version

    def get_active_rule_version(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM rule_versions WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return self._rule_version_row(row) if row else None

    def get_rule_version(self, version_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM rule_versions WHERE id = ?",
                (version_id,),
            ).fetchone()
        return self._rule_version_row(row) if row else None

    def list_rule_versions(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM rule_versions ORDER BY id DESC LIMIT ?",
                (max(1, min(int(limit), 100)),),
            ).fetchall()
        return [self._rule_version_row(row, include_configs=False) for row in rows]

    @staticmethod
    def _rule_version_row(
        row: sqlite3.Row,
        *,
        include_configs: bool = True,
    ) -> dict[str, Any]:
        result = {
            "id": int(row["id"]),
            "action": str(row["action"]),
            "change_summary": str(row["change_summary"]),
            "text_version": str(row["text_version"]),
            "url_version": str(row["url_version"]),
            "source_version_id": row["source_version_id"],
            "is_active": bool(row["is_active"]),
            "created_at": str(row["created_at"]),
        }
        if include_configs:
            result["risk_config"] = json.loads(row["risk_config_json"])
            result["url_config"] = json.loads(row["url_config_json"])
        return result

    def record_scenario_completion(
        self,
        user_id: int,
        scenario_id: str,
        score: int,
        max_score: int,
        completion_bonus: int,
    ) -> dict[str, Any]:
        normalized_score = max(0, int(score))
        normalized_max = max(0, int(max_score))

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT attempts, completions, best_score, points_earned,
                       first_completed_at, last_completed_at
                FROM scenario_progress
                WHERE user_id = ? AND scenario_id = ?
                """,
                (user_id, scenario_id),
            ).fetchone()

            first_clear = row is None
            previous_best = int(row["best_score"]) if row else 0
            improvement = max(0, normalized_score - previous_best)
            points_gained = improvement + (max(0, int(completion_bonus)) if first_clear else 0)

            if row:
                conn.execute(
                    """
                    UPDATE scenario_progress
                    SET attempts = attempts + 1,
                        completions = completions + 1,
                        best_score = MAX(best_score, ?),
                        max_score = MAX(max_score, ?),
                        points_earned = points_earned + ?,
                        last_completed_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND scenario_id = ?
                    """,
                    (normalized_score, normalized_max, points_gained, user_id, scenario_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO scenario_progress (
                        user_id, scenario_id, attempts, completions, best_score,
                        max_score, points_earned, first_completed_at, last_completed_at
                    )
                    VALUES (?, ?, 1, 1, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (user_id, scenario_id, normalized_score, normalized_max, points_gained),
                )

            saved = conn.execute(
                """
                SELECT attempts, completions, best_score, max_score, points_earned,
                       first_completed_at, last_completed_at
                FROM scenario_progress
                WHERE user_id = ? AND scenario_id = ?
                """,
                (user_id, scenario_id),
            ).fetchone()
            unique_completed = conn.execute(
                "SELECT COUNT(*) FROM scenario_progress WHERE user_id = ? AND completions > 0",
                (user_id,),
            ).fetchone()[0]
            conn.commit()

        return {
            "scenario_id": scenario_id,
            "first_clear": first_clear,
            "previous_best": previous_best,
            "score_improvement": improvement,
            "points_gained": points_gained,
            "attempts": int(saved["attempts"]),
            "completions": int(saved["completions"]),
            "best_score": int(saved["best_score"]),
            "max_score": int(saved["max_score"]),
            "points_earned": int(saved["points_earned"]),
            "first_completed_at": saved["first_completed_at"],
            "last_completed_at": saved["last_completed_at"],
            "unique_completed": int(unique_completed),
        }

    def get_scenario_progress(self, user_id: int, scenario_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT scenario_id, attempts, completions, best_score, max_score,
                       points_earned, first_completed_at, last_completed_at
                FROM scenario_progress
                WHERE user_id = ? AND scenario_id = ?
                """,
                (user_id, scenario_id),
            ).fetchone()
        return self._scenario_progress_row(row) if row else None

    def list_scenario_progress(self, user_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT scenario_id, attempts, completions, best_score, max_score,
                       points_earned, first_completed_at, last_completed_at
                FROM scenario_progress
                WHERE user_id = ?
                ORDER BY last_completed_at DESC, scenario_id ASC
                """,
                (user_id,),
            ).fetchall()
        return [self._scenario_progress_row(row) for row in rows]

    @staticmethod
    def _scenario_progress_row(row: sqlite3.Row) -> dict[str, Any]:
        max_score = int(row["max_score"])
        best_score = int(row["best_score"])
        return {
            "scenario_id": str(row["scenario_id"]),
            "attempts": int(row["attempts"]),
            "completions": int(row["completions"]),
            "best_score": best_score,
            "max_score": max_score,
            "best_percent": round(best_score / max_score * 100) if max_score > 0 else 0,
            "points_earned": int(row["points_earned"]),
            "first_completed_at": row["first_completed_at"],
            "last_completed_at": row["last_completed_at"],
        }

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
        risk_level: str = "low",
        channel: str = "web",
        matched_rules: list[dict[str, Any]] | None = None,
        url_host: str | None = None,
        url: str | None = None,
        normalized_url: str | None = None,
        content_summary: str | None = None,
        content: str | None = None,
        content_hash: str | None = None,
        reasons: list[str] | None = None,
        url_flags: list[str] | None = None,
        score_breakdown: dict[str, Any] | None = None,
        ruleset_versions: dict[str, str] | None = None,
        status: str = "pending",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reports (
                    report_id, user_id, score, verdict, risk_level, channel,
                    matched_keywords_json, matched_rules_json,
                    url_host, url, normalized_url,
                    content_summary, content, content_hash,
                    reasons_json, url_flags_json, score_breakdown_json,
                    ruleset_versions_json, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    user_id,
                    int(score),
                    verdict,
                    risk_level,
                    channel,
                    json.dumps(sorted(set(matched_keywords)), ensure_ascii=False),
                    json.dumps(matched_rules or [], ensure_ascii=False),
                    url_host,
                    url,
                    normalized_url,
                    content_summary,
                    content,
                    content_hash,
                    json.dumps(reasons or [], ensure_ascii=False),
                    json.dumps(url_flags or [], ensure_ascii=False),
                    json.dumps(score_breakdown or {}, ensure_ascii=False),
                    json.dumps(ruleset_versions or {}, ensure_ascii=False),
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
            SELECT *
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

        return [self._report_row(row) for row in rows]

    def get_report(self, report_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM reports WHERE report_id = ?", (report_id,)).fetchone()
        return self._report_row(row) if row else None

    def find_recent_duplicate_report(
        self,
        *,
        user_id: int,
        normalized_url: str | None,
        content_hash: str | None,
    ) -> dict[str, Any] | None:
        clauses = ["user_id = ?", "created_at >= datetime('now', '-24 hours')"]
        params: list[Any] = [int(user_id)]
        if normalized_url:
            duplicate_clause = "normalized_url = ?"
            params.append(normalized_url)
        elif content_hash:
            duplicate_clause = "content_hash = ?"
            params.append(content_hash)
        else:
            return None

        sql = f"""
            SELECT *
            FROM reports
            WHERE {' AND '.join(clauses)} AND {duplicate_clause}
            ORDER BY created_at DESC, report_id DESC
            LIMIT 1
        """
        with self._connect() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
        return self._report_row(row) if row else None

    def list_admin_reports(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        risk_level: str | None = None,
        verdict: str | None = None,
        channel: str | None = None,
        user_id: int | None = None,
        keyword: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> dict[str, Any]:
        normalized_page = max(1, int(page))
        normalized_page_size = max(1, min(100, int(page_size)))
        where: list[str] = []
        params: list[Any] = []

        for column, value in (
            ("status", status),
            ("risk_level", risk_level),
            ("verdict", verdict),
            ("channel", channel),
        ):
            if value:
                where.append(f"{column} = ?")
                params.append(value)
        if user_id is not None:
            where.append("user_id = ?")
            params.append(int(user_id))
        if start_time:
            where.append("created_at >= ?")
            params.append(start_time)
        if end_time:
            where.append("created_at <= ?")
            params.append(end_time)
        if keyword:
            like = f"%{self._escape_like(keyword)}%"
            where.append(
                """
                (
                    content LIKE ? ESCAPE '\\'
                    OR content_summary LIKE ? ESCAPE '\\'
                    OR url LIKE ? ESCAPE '\\'
                    OR matched_keywords_json LIKE ? ESCAPE '\\'
                    OR reasons_json LIKE ? ESCAPE '\\'
                )
                """
            )
            params.extend([like, like, like, like, like])

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        count_sql = f"SELECT COUNT(*) AS total FROM reports {where_sql}"
        list_sql = f"""
            SELECT *
            FROM reports
            {where_sql}
            ORDER BY created_at DESC, report_id DESC
            LIMIT ? OFFSET ?
        """

        with self._connect() as conn:
            total = int(conn.execute(count_sql, tuple(params)).fetchone()["total"])
            rows = conn.execute(
                list_sql,
                tuple(params + [normalized_page_size, (normalized_page - 1) * normalized_page_size]),
            ).fetchall()

        return {
            "total": total,
            "page": normalized_page,
            "page_size": normalized_page_size,
            "items": [self._report_row(row) for row in rows],
        }

    def update_report_status(self, report_id: str, status: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE reports SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE report_id = ?",
                (status, report_id),
            )
            conn.commit()
        return cursor.rowcount > 0

    def review_report(
        self,
        *,
        report_id: str,
        status: str,
        reviewer: str | None = None,
        review_note: str | None = None,
        verdict: str | None = None,
        risk_level: str | None = None,
        score: int | None = None,
    ) -> dict[str, Any] | None:
        assignments = [
            "status = ?",
            "reviewer = ?",
            "review_note = ?",
            "reviewed_at = CURRENT_TIMESTAMP",
            "updated_at = CURRENT_TIMESTAMP",
        ]
        params: list[Any] = [status, reviewer, review_note]

        if verdict is not None:
            assignments.append("verdict = ?")
            params.append(verdict)
        if risk_level is not None:
            assignments.append("risk_level = ?")
            params.append(risk_level)
        if score is not None:
            assignments.append("score = ?")
            params.append(int(score))

        params.append(report_id)
        sql = f"UPDATE reports SET {', '.join(assignments)} WHERE report_id = ?"

        with self._connect() as conn:
            cursor = conn.execute(sql, tuple(params))
            conn.commit()
        if cursor.rowcount <= 0:
            return None
        return self.get_report(report_id)

    @staticmethod
    def _escape_like(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    @staticmethod
    def _json_loads(value: Any, default: Any) -> Any:
        try:
            return json.loads(value or json.dumps(default))
        except (TypeError, json.JSONDecodeError):
            return default

    @classmethod
    def _report_row(cls, row: sqlite3.Row) -> dict[str, Any]:
        verdict = str(row["verdict"])
        risk_level = str(row["risk_level"] or "")
        if not risk_level or risk_level == "low":
            risk_level = {"safe": "low", "suspicious": "medium", "high_risk": "high"}.get(verdict, "low")
        score_breakdown = cls._json_loads(row["score_breakdown_json"], {})
        return {
            "report_id": str(row["report_id"]),
            "user_id": int(row["user_id"]),
            "score": int(row["score"]),
            "risk_score": int(row["score"]),
            "risk_level": risk_level,
            "verdict": verdict,
            "channel": str(row["channel"] or "web"),
            "matched_keywords": cls._json_loads(row["matched_keywords_json"], []),
            "matched_rules": cls._json_loads(row["matched_rules_json"], []),
            "url_host": str(row["url_host"]) if row["url_host"] else None,
            "url": str(row["url"]) if row["url"] else None,
            "normalized_url": str(row["normalized_url"]) if row["normalized_url"] else None,
            "content_summary": str(row["content_summary"]) if row["content_summary"] else None,
            "content": str(row["content"]) if row["content"] else None,
            "content_hash": str(row["content_hash"]) if row["content_hash"] else None,
            "reasons": cls._json_loads(row["reasons_json"], []),
            "url_flags": cls._json_loads(row["url_flags_json"], []),
            "score_breakdown": score_breakdown,
            "risk_breakdown": score_breakdown,
            "ruleset_versions": cls._json_loads(row["ruleset_versions_json"], {}),
            "status": str(row["status"] or "pending"),
            "reviewer": str(row["reviewer"]) if row["reviewer"] else None,
            "review_note": str(row["review_note"]) if row["review_note"] else None,
            "reviewed_at": str(row["reviewed_at"]) if row["reviewed_at"] else None,
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"] or row["created_at"]),
        }

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

    def dashboard_snapshot(self) -> dict[str, Any]:
        """Return read-only aggregate data for the admin dashboard."""
        with self._connect() as conn:
            user_rows = conn.execute(
                "SELECT role, COUNT(*) AS count FROM users GROUP BY role"
            ).fetchall()
            user_totals = conn.execute(
                """
                SELECT
                    COUNT(*) AS state_users,
                    COALESCE(SUM(points), 0) AS total_points,
                    COALESCE(SUM(reports_submitted), 0) AS reports_submitted,
                    COALESCE(SUM(scenarios_completed), 0) AS scenarios_completed,
                    COALESCE(SUM(high_risk_blocks), 0) AS high_risk_blocks,
                    COALESCE(SUM(knowledge_queries), 0) AS knowledge_queries,
                    COALESCE(AVG(level), 0) AS avg_level
                FROM user_state
                """
            ).fetchone()
            level_rows = conn.execute(
                """
                SELECT level, COUNT(*) AS count
                FROM user_state
                GROUP BY level
                ORDER BY level ASC
                """
            ).fetchall()
            badge_rows = conn.execute("SELECT badges_json FROM user_state").fetchall()

            report_totals = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_reports,
                    COALESCE(AVG(score), 0) AS avg_score,
                    COALESCE(MAX(score), 0) AS max_score
                FROM reports
                """
            ).fetchone()
            verdict_rows = conn.execute(
                "SELECT verdict, COUNT(*) AS count FROM reports GROUP BY verdict"
            ).fetchall()
            status_rows = conn.execute(
                "SELECT status, COUNT(*) AS count FROM reports GROUP BY status"
            ).fetchall()
            trend_rows = conn.execute(
                """
                SELECT DATE(created_at) AS day,
                       COUNT(*) AS total,
                       SUM(CASE WHEN verdict = 'high_risk' THEN 1 ELSE 0 END) AS high_risk
                FROM reports
                GROUP BY DATE(created_at)
                ORDER BY day DESC
                LIMIT 7
                """
            ).fetchall()
            recent_reports = conn.execute(
                """
                SELECT report_id, user_id, score, verdict, matched_keywords_json,
                       url_host, content_summary, reasons_json, status, created_at,
                       updated_at, reviewer, review_note, reviewed_at
                FROM reports
                ORDER BY created_at DESC, report_id DESC
                LIMIT 12
                """
            ).fetchall()
            report_keyword_rows = conn.execute(
                "SELECT matched_keywords_json FROM reports"
            ).fetchall()
            host_rows = conn.execute(
                """
                SELECT url_host, COUNT(*) AS count, MAX(score) AS max_score
                FROM reports
                WHERE url_host IS NOT NULL AND url_host <> ''
                GROUP BY url_host
                ORDER BY count DESC, max_score DESC
                LIMIT 10
                """
            ).fetchall()

            scenario_rows = conn.execute(
                """
                SELECT scenario_id,
                       SUM(attempts) AS attempts,
                       SUM(completions) AS completions,
                       COALESCE(AVG(CASE WHEN max_score > 0 THEN best_score * 100.0 / max_score ELSE 0 END), 0) AS avg_best_percent,
                       MAX(last_completed_at) AS last_completed_at
                FROM scenario_progress
                GROUP BY scenario_id
                ORDER BY completions DESC, attempts DESC, scenario_id ASC
                LIMIT 10
                """
            ).fetchall()

        role_counts = {str(row["role"]): int(row["count"]) for row in user_rows}
        level_distribution = [
            {"level": int(row["level"]), "count": int(row["count"])}
            for row in level_rows
        ]

        badge_counts: dict[str, int] = {}
        for row in badge_rows:
            for badge in json.loads(row["badges_json"] or "[]"):
                badge_counts[str(badge)] = badge_counts.get(str(badge), 0) + 1

        keyword_counts: dict[str, int] = {}
        for row in report_keyword_rows:
            for keyword in json.loads(row["matched_keywords_json"] or "[]"):
                keyword_counts[str(keyword)] = keyword_counts.get(str(keyword), 0) + 1

        verdict_counts = {str(row["verdict"]): int(row["count"]) for row in verdict_rows}
        status_counts = {str(row["status"]): int(row["count"]) for row in status_rows}

        return {
            "users": {
                "total": sum(role_counts.values()),
                "roles": role_counts,
                "state_users": int(user_totals["state_users"] or 0),
                "total_points": int(user_totals["total_points"] or 0),
                "avg_level": round(float(user_totals["avg_level"] or 0), 2),
                "level_distribution": level_distribution,
                "badge_distribution": [
                    {"badge": badge, "count": count}
                    for badge, count in sorted(badge_counts.items(), key=lambda item: (-item[1], item[0]))
                ],
            },
            "engagement": {
                "reports_submitted": int(user_totals["reports_submitted"] or 0),
                "scenarios_completed": int(user_totals["scenarios_completed"] or 0),
                "high_risk_blocks": int(user_totals["high_risk_blocks"] or 0),
                "knowledge_queries": int(user_totals["knowledge_queries"] or 0),
            },
            "reports": {
                "total": int(report_totals["total_reports"] or 0),
                "avg_score": round(float(report_totals["avg_score"] or 0), 2),
                "max_score": int(report_totals["max_score"] or 0),
                "verdict_distribution": {
                    "safe": verdict_counts.get("safe", 0),
                    "suspicious": verdict_counts.get("suspicious", 0),
                    "high_risk": verdict_counts.get("high_risk", 0),
                },
                "status_distribution": {
                    "pending": status_counts.get("pending", 0),
                    "reviewed": status_counts.get("reviewed", 0),
                    "closed": status_counts.get("closed", 0),
                },
                "trend": [
                    {
                        "day": str(row["day"]),
                        "total": int(row["total"] or 0),
                        "high_risk": int(row["high_risk"] or 0),
                    }
                    for row in reversed(trend_rows)
                ],
                "top_keywords": [
                    {"keyword": keyword, "count": count}
                    for keyword, count in sorted(keyword_counts.items(), key=lambda item: (-item[1], item[0]))[:10]
                ],
                "top_hosts": [
                    {
                        "host": str(row["url_host"]),
                        "count": int(row["count"]),
                        "max_score": int(row["max_score"] or 0),
                    }
                    for row in host_rows
                ],
                "recent": [
                    {
                        "report_id": str(row["report_id"]),
                        "user_id": int(row["user_id"]),
                        "score": int(row["score"]),
                        "verdict": str(row["verdict"]),
                        "matched_keywords": json.loads(row["matched_keywords_json"] or "[]"),
                        "url_host": str(row["url_host"]) if row["url_host"] else None,
                        "content_summary": str(row["content_summary"]) if row["content_summary"] else None,
                        "reasons": json.loads(row["reasons_json"] or "[]"),
                        "status": str(row["status"] or "pending"),
                        "created_at": str(row["created_at"]),
                        "updated_at": str(row["updated_at"] or row["created_at"]),
                        "reviewer": str(row["reviewer"]) if row["reviewer"] else None,
                        "review_note": str(row["review_note"]) if row["review_note"] else None,
                        "reviewed_at": str(row["reviewed_at"]) if row["reviewed_at"] else None,
                    }
                    for row in recent_reports
                ],
            },
            "scenarios": [
                {
                    "scenario_id": str(row["scenario_id"]),
                    "attempts": int(row["attempts"] or 0),
                    "completions": int(row["completions"] or 0),
                    "avg_best_percent": round(float(row["avg_best_percent"] or 0), 1),
                    "last_completed_at": str(row["last_completed_at"]) if row["last_completed_at"] else None,
                }
                for row in scenario_rows
            ],
        }
