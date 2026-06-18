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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            self._ensure_column(conn, "reports", "content_summary", "TEXT")
            self._ensure_column(conn, "reports", "reasons_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "reports", "status", "TEXT NOT NULL DEFAULT 'pending'")
            conn.commit()

    def add_chat_message(
        self,
        *,
        user_id: int,
        user_message: str,
        assistant_reply: str,
        risk_level: str,
        risk_score: int,
        intent: str,
        matched_scams: list[str],
        session_stage: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_messages (
                    user_id, user_message, assistant_reply, risk_level, risk_score,
                    intent, matched_scams_json, session_stage
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
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
            conn.commit()

    def list_chat_messages(self, user_id: int, limit: int = 50) -> list[dict[str, Any]]:
        normalized_limit = max(1, min(200, int(limit)))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, user_message, assistant_reply, risk_level,
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
                       url_host, content_summary, reasons_json, status, created_at
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
