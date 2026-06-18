from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.auth_service import AuthService  # noqa: E402
from app.services.gamification import GamificationService  # noqa: E402
from app.services.report_service import ReportService  # noqa: E402
from app.services.risk_engine import RiskEngine  # noqa: E402
from app.services.rule_management import RuleManagementService  # noqa: E402
from app.services.storage import SQLiteStorage  # noqa: E402


DEMO_USERS = [
    {
        "username": "demo_student",
        "password": "Demo@123456",
        "role": "student",
        "nickname": "答辩演示学生",
    },
    {
        "username": "demo_guardian",
        "password": "Demo@123456",
        "role": "general",
        "nickname": "家长体验账号",
    },
]

DEMO_RULE_NAME = "demo_fake_delivery_compensation"


def _connect_storage(db_path: Path) -> tuple[SQLiteStorage, RiskEngine, GamificationService]:
    storage = SQLiteStorage(db_path)
    risk_engine = RiskEngine()
    gamification = GamificationService(storage=storage)
    return storage, risk_engine, gamification


def _reset_demo_users(storage: SQLiteStorage) -> None:
    usernames = [item["username"] for item in DEMO_USERS]
    placeholders = ",".join("?" for _ in usernames)
    with storage._connect() as conn:
        rows = conn.execute(
            f"SELECT id FROM users WHERE username IN ({placeholders})",
            tuple(usernames),
        ).fetchall()
        user_ids = [int(row["id"]) for row in rows]
        if user_ids:
            user_placeholders = ",".join("?" for _ in user_ids)
            for table in ("reports", "user_state", "scenario_progress"):
                conn.execute(
                    f"DELETE FROM {table} WHERE user_id IN ({user_placeholders})",
                    tuple(user_ids),
                )
            conn.execute(
                f"DELETE FROM users WHERE id IN ({user_placeholders})",
                tuple(user_ids),
            )
        conn.commit()


def _upsert_users(auth: AuthService) -> dict[str, dict[str, Any]]:
    created: dict[str, dict[str, Any]] = {}
    for user in DEMO_USERS:
        try:
            result = auth.register(**user)
        except ValueError:
            result = auth.login(user["username"], user["password"])
        created[user["username"]] = result
    return created


def _scenario_max_score(scenario_id: str) -> int:
    data = json.loads((ROOT_DIR / "app" / "data" / "scenarios.json").read_text(encoding="utf-8"))
    scenario = next(item for item in data["scenarios"] if item["id"] == scenario_id)
    return sum(
        max(int(option.get("points", 0)) for option in step.get("options", []))
        for step in scenario.get("steps", [])
    )


def _seed_reports(
    user_id: int,
    risk_engine: RiskEngine,
    gamification: GamificationService,
    storage: SQLiteStorage,
) -> list[str]:
    report_service = ReportService(
        risk_engine=risk_engine,
        gamification=gamification,
        storage=storage,
    )
    examples = [
        {
            "url": "https://gov.cn@secure-bank-login.top/verify",
            "content": "航司客服说航班取消，点击领取延误理赔并提供验证码",
        },
        {
            "url": "https://taobao.com.evil.top/login",
            "content": "客服说订单异常，可以双倍赔付，但要先转保证金",
        },
        {
            "url": None,
            "content": "官方提醒：不要提供验证码，也不要向陌生账户转账",
        },
    ]
    report_ids: list[str] = []
    for item in examples:
        result = report_service.analyze(
            user_id=user_id,
            url=item["url"],
            content=item["content"],
        )
        report_ids.append(str(result["report_id"]))

    for report_id, status in zip(report_ids, ("reviewed", "pending", "closed")):
        storage.update_report_status(report_id, status)
    return report_ids


def _seed_progress(user_id: int, gamification: GamificationService) -> None:
    for _ in range(2):
        gamification.award(user_id, "knowledge_query")
    for _ in range(2):
        gamification.award(user_id, "risk_block", risk_level="critical")

    for scenario_id, score_ratio in (("C001", 1.0), ("C006", 0.8), ("C010", 1.0)):
        max_score = _scenario_max_score(scenario_id)
        score = round(max_score * score_ratio)
        gamification.complete_scenario(user_id, scenario_id, score=score, max_score=max_score)


def _seed_rule_history(
    risk_engine: RiskEngine,
    storage: SQLiteStorage,
) -> dict[str, Any]:
    manager = RuleManagementService(risk_engine=risk_engine, storage=storage)
    overview = manager.overview()
    existing_names = {rule["name"] for rule in overview["text_rules"]}

    if DEMO_RULE_NAME not in existing_names:
        overview = manager.add_text_rule(
            {
                "name": DEMO_RULE_NAME,
                "triggers": ["快递破损", "专属补偿码", "理赔二维码"],
                "weight": 24,
                "reason": "命中快递理赔诱导话术",
                "rationale": "冒充快递客服以破损理赔、二维码赔付诱导点击链接或提供验证码",
                "version": "1.0",
                "enabled": True,
            },
            "演示数据：接入快递理赔新骗局",
        )

    rule_added_revision = int(overview["active_revision"]["id"])
    trust_rule = next(rule for rule in overview["text_rules"] if rule["name"] == "trust_reassurance")
    temporary_weight = min(20, int(trust_rule["weight"]) + 1)
    manager.update_rule(
        "text",
        "trust_reassurance",
        enabled=None,
        weight=temporary_weight,
        change_note="演示数据：临时调高消除戒心话术权重",
    )
    overview = manager.rollback(
        rule_added_revision,
        "演示数据：回滚临时调权，保留新增快递理赔规则",
    )
    return overview


def seed_demo_data(db_path: Path, *, reset: bool = False) -> dict[str, Any]:
    storage, risk_engine, gamification = _connect_storage(db_path)
    if reset:
        _reset_demo_users(storage)
        gamification = GamificationService(storage=storage)

    auth = AuthService(
        storage=storage,
        secret_key=os.getenv("JWT_SECRET", "anti-fraud-lab-secret-key-change-in-production-2024"),
    )
    users = _upsert_users(auth)
    student_id = int(users["demo_student"]["user_id"])
    report_ids = _seed_reports(student_id, risk_engine, gamification, storage)
    _seed_progress(student_id, gamification)
    overview = _seed_rule_history(risk_engine, storage)

    return {
        "db_path": str(db_path),
        "users": {
            username: {
                "user_id": data["user_id"],
                "username": data["username"],
                "password": next(item["password"] for item in DEMO_USERS if item["username"] == username),
                "role": data["role"],
                "nickname": data["nickname"],
            }
            for username, data in users.items()
        },
        "report_ids": report_ids,
        "rule_revision": overview["active_revision"],
        "ruleset_versions": overview["ruleset_versions"],
        "demo_rule": DEMO_RULE_NAME,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed stable demo data for the anti-fraud system.")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path(os.getenv("DB_PATH", ROOT_DIR / "app" / "data" / "anti_fraud.db")),
        help="SQLite database path. Defaults to DB_PATH or app/data/anti_fraud.db.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing demo users and their reports/progress before seeding.",
    )
    args = parser.parse_args()

    result = seed_demo_data(args.db_path, reset=args.reset)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
