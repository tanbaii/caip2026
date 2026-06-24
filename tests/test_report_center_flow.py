import hashlib
import uuid

from fastapi.testclient import TestClient

from app.main import ADMIN_TOKEN, app, report_service


client = TestClient(app)


def _user_id() -> int:
    return uuid.uuid4().int % 1_000_000_000 + 10_000


def _report(user_id: int, **overrides):
    payload = {
        "user_id": user_id,
        "content": "公检法让我马上转账到安全账户，还要求保密办案",
        "channel": "web",
    }
    payload.update(overrides)
    return client.post("/report", json=payload)


def _register_user(role: str = "general") -> dict:
    response = client.post(
        "/auth/register",
        json={
            "username": f"report_user_{uuid.uuid4().hex[:10]}",
            "password": "reportpass123",
            "role": role,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_report_channel_is_saved_and_returned_in_all_report_views() -> None:
    user_id = _user_id()
    created = _report(user_id, channel="mobile")
    assert created.status_code == 200
    report_id = created.json()["report_id"]
    assert created.json()["channel"] == "mobile"

    history = client.get(f"/users/{user_id}/reports").json()["items"][0]
    assert history["channel"] == "mobile"

    detail = client.get(
        f"/reports/{report_id}",
        headers={"x-admin-token": ADMIN_TOKEN},
    ).json()
    assert detail["channel"] == "mobile"

    admin = client.get(
        "/admin/reports?channel=mobile",
        headers={"x-admin-token": ADMIN_TOKEN},
    ).json()
    assert admin["items"][0]["report_id"] == report_id
    assert admin["items"][0]["channel"] == "mobile"


def test_report_service_does_not_keep_in_memory_report_list() -> None:
    assert not hasattr(report_service, "reports")


def test_report_analysis_uses_risk_engine_rules_with_traceable_rule_ids() -> None:
    user_id = _user_id()
    response = _report(user_id)
    assert response.status_code == 200
    data = response.json()
    rule_ids = {item["rule"] for item in data["matched_rules"]}
    assert "authority_pressure" in rule_ids
    assert any(item["ruleset_version"] for item in data["matched_rules"])
    assert data["risk_level"] in {"high", "critical"}


def test_report_content_score_is_capped_for_many_keyword_hits() -> None:
    user_id = _user_id()
    content = " ".join(
        [
            "公检法 安全账户 涉嫌 保密办案",
            "远程控制 屏幕共享 账号密码",
            "刷单 返利 垫付 充值 转账 提现失败",
            "投资 理财 高收益 导师带单 充值",
            "USDT 虚拟币 钱包地址 转账 保证金",
        ]
        * 8
    )
    response = _report(user_id, content=content)
    assert response.status_code == 200
    data = response.json()
    assert data["score_breakdown"]["content_score"] <= 70
    assert data["risk_score"] <= 100


def test_report_verification_code_safety_advice_is_not_high_risk() -> None:
    user_id = _user_id()
    response = _report(user_id, content="不要把验证码告诉别人，也不要发给陌生人")
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "low"
    assert data["verdict"] == "safe"


def test_report_authority_safe_account_transfer_is_high_or_critical() -> None:
    user_id = _user_id()
    response = _report(user_id, content="公检法让我转账到安全账户，并且要求马上保密办案")
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] in {"high", "critical"}
    assert data["verdict"] == "high_risk"


def test_admin_reports_support_pagination_and_filters() -> None:
    user_a = _user_id()
    user_b = _user_id()
    first = _report(user_a, channel="web", content="公检法让我转账到安全账户").json()
    second = _report(user_b, channel="miniapp", content="刷单返利让我先垫付").json()

    reviewed = client.patch(
        f"/reports/{second['report_id']}/status",
        headers={"x-admin-token": ADMIN_TOKEN},
        json={"status": "reviewed"},
    )
    assert reviewed.status_code == 200

    page = client.get(
        "/admin/reports?page=1&page_size=1&status=reviewed&channel=miniapp&keyword=刷单",
        headers={"x-admin-token": ADMIN_TOKEN},
    )
    assert page.status_code == 200
    data = page.json()
    assert data["page"] == 1
    assert data["page_size"] == 1
    assert data["total"] == 1
    assert data["items"][0]["report_id"] == second["report_id"]
    assert data["items"][0]["report_id"] != first["report_id"]


def test_admin_can_review_report_with_note_and_manual_verdict() -> None:
    created = _report(
        _user_id(),
        content="公检法让我转账到安全账户，并且要求马上保密办理",
        channel="web",
    ).json()
    report_id = created["report_id"]

    reviewed = client.patch(
        f"/admin/reports/{report_id}/review",
        headers={"x-admin-token": ADMIN_TOKEN},
        json={
            "status": "reviewed",
            "reviewer": "admin-demo",
            "review_note": "人工复核后确认已联系用户，按低风险归档。",
            "verdict": "safe",
            "risk_level": "low",
            "score": 12,
        },
    )
    assert reviewed.status_code == 200
    reviewed_data = reviewed.json()
    assert reviewed_data["report_id"] == report_id
    assert reviewed_data["status"] == "reviewed"
    assert reviewed_data["reviewer"] == "admin-demo"
    assert reviewed_data["review_note"] == "人工复核后确认已联系用户，按低风险归档。"
    assert reviewed_data["reviewed_at"]
    assert reviewed_data["verdict"] == "safe"
    assert reviewed_data["risk_level"] == "low"
    assert reviewed_data["score"] == 12
    assert reviewed_data["risk_score"] == 12

    detail = client.get(
        f"/reports/{report_id}",
        headers={"x-admin-token": ADMIN_TOKEN},
    ).json()
    assert detail["reviewer"] == "admin-demo"
    assert detail["review_note"] == "人工复核后确认已联系用户，按低风险归档。"
    assert detail["reviewed_at"] == reviewed_data["reviewed_at"]

    admin = client.get(
        "/admin/reports?status=reviewed&verdict=safe",
        headers={"x-admin-token": ADMIN_TOKEN},
    ).json()
    ids = {item["report_id"] for item in admin["items"]}
    assert report_id in ids


def test_report_owner_can_see_admin_review_note_in_history_and_detail() -> None:
    owner = _register_user()
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    created = client.post(
        "/report",
        headers=headers,
        json={
            "user_id": owner["user_id"],
            "content": "manual owner review visibility case",
            "channel": "web",
        },
    )
    assert created.status_code == 200
    report_id = created.json()["report_id"]

    reviewed = client.patch(
        f"/admin/reports/{report_id}/review",
        headers={"x-admin-token": ADMIN_TOKEN},
        json={
            "status": "reviewed",
            "reviewer": "admin-demo",
            "review_note": "owner visible follow-up note",
            "verdict": "safe",
            "risk_level": "low",
            "score": 8,
        },
    )
    assert reviewed.status_code == 200

    history = client.get(
        f"/users/{owner['user_id']}/reports",
        headers=headers,
    )
    assert history.status_code == 200
    history_item = next(item for item in history.json()["items"] if item["report_id"] == report_id)
    assert history_item["status"] == "reviewed"
    assert history_item["reviewer"] == "admin-demo"
    assert history_item["review_note"] == "owner visible follow-up note"
    assert history_item["reviewed_at"]

    detail = client.get(f"/reports/{report_id}", headers=headers)
    assert detail.status_code == 200
    detail_data = detail.json()
    assert detail_data["review_note"] == "owner visible follow-up note"
    assert detail_data["reviewed_at"] == history_item["reviewed_at"]


def test_admin_review_requires_admin_token_and_does_not_update_on_failure() -> None:
    created = _report(_user_id(), content="公检法让我转账到安全账户").json()
    report_id = created["report_id"]

    denied = client.patch(
        f"/admin/reports/{report_id}/review",
        json={
            "status": "reviewed",
            "reviewer": "not-admin",
            "review_note": "不应写入",
        },
    )
    assert denied.status_code == 401

    detail = client.get(
        f"/reports/{report_id}",
        headers={"x-admin-token": ADMIN_TOKEN},
    ).json()
    assert detail["status"] == "pending"
    assert detail["reviewer"] is None
    assert detail["review_note"] is None
    assert detail["reviewed_at"] is None


def test_admin_dashboard_recent_reports_include_review_metadata() -> None:
    created = _report(
        _user_id(),
        content="manual review dashboard sync case",
        channel="web",
    ).json()
    report_id = created["report_id"]

    reviewed = client.patch(
        f"/admin/reports/{report_id}/review",
        headers={"x-admin-token": ADMIN_TOKEN},
        json={
            "status": "closed",
            "reviewer": "admin-demo",
            "review_note": "confirmed and archived",
            "verdict": "safe",
            "risk_level": "low",
            "score": 10,
        },
    )
    assert reviewed.status_code == 200

    summary = client.get(
        "/admin/dashboard/summary",
        headers={"x-admin-token": ADMIN_TOKEN},
    )
    assert summary.status_code == 200
    recent = summary.json()["reports"]["recent"]
    item = next(report for report in recent if report["report_id"] == report_id)
    assert item["status"] == "closed"
    assert item["reviewer"] == "admin-demo"
    assert item["review_note"] == "confirmed and archived"
    assert item["reviewed_at"]


def test_report_detail_returns_complete_analysis_details() -> None:
    user_id = _user_id()
    created = _report(
        user_id,
        url="http://secure-bank.top/login",
        content="公检法让我转账到安全账户",
        channel="web",
    )
    report_id = created.json()["report_id"]

    detail = client.get(
        f"/reports/{report_id}",
        headers={"x-admin-token": ADMIN_TOKEN},
    )
    assert detail.status_code == 200
    data = detail.json()
    for field in [
        "content",
        "url",
        "channel",
        "risk_level",
        "verdict",
        "score",
        "score_breakdown",
        "matched_rules",
        "url_flags",
        "reasons",
        "status",
        "created_at",
        "updated_at",
    ]:
        assert field in data
    assert data["report_id"] == report_id


def test_duplicate_report_returns_existing_report_id_with_duplicated_true() -> None:
    user_id = _user_id()
    payload = {
        "url": "HTTPS://Secure-Bank.Top/login?utm_source=test#frag",
        "content": "公检法让我转账到安全账户",
        "channel": "web",
    }
    first = _report(user_id, **payload).json()
    second = _report(user_id, **payload).json()

    assert second["report_id"] == first["report_id"]
    assert second["duplicated"] is True


def test_report_rate_limit_returns_429_for_high_frequency_submits() -> None:
    user_id = _user_id()
    statuses = []
    for index in range(7):
        response = _report(
            user_id,
            content=f"公检法让我转账到安全账户 第{index}次 {uuid.uuid4().hex}",
        )
        statuses.append(response.status_code)

    assert statuses[:5] == [200, 200, 200, 200, 200]
    assert 429 in statuses[5:]


def test_chat_high_risk_response_includes_report_prefill() -> None:
    user_id = _user_id()
    message = "公检法让我转账到安全账户，还要求马上发验证码"
    response = client.post(
        "/chat",
        json={
            "user_id": user_id,
            "message": message,
            "user_profile": {"role": "student"},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] in {"high", "critical"}
    assert data["report_prefill"]["content"] == message
    assert data["report_prefill"]["risk_level"] == data["risk_level"]
    assert data["report_prefill"]["reasons"]


def test_report_content_hash_is_sha256_for_duplicate_lookup() -> None:
    user_id = _user_id()
    content = "公检法让我转账到安全账户"
    created = _report(user_id, content=content).json()
    detail = client.get(
        f"/reports/{created['report_id']}",
        headers={"x-admin-token": ADMIN_TOKEN},
    ).json()
    assert detail["content_hash"] == hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


def test_report_detail_requires_owner_or_admin() -> None:
    owner = _register_user()
    other = _register_user()
    created = _report(owner["user_id"], content="公检法让我转账到安全账户").json()
    report_id = created["report_id"]

    anonymous = client.get(f"/reports/{report_id}")
    assert anonymous.status_code == 401

    denied = client.get(
        f"/reports/{report_id}",
        headers={"Authorization": f"Bearer {other['access_token']}"},
    )
    assert denied.status_code == 403

    allowed_owner = client.get(
        f"/reports/{report_id}",
        headers={"Authorization": f"Bearer {owner['access_token']}"},
    )
    assert allowed_owner.status_code == 200

    allowed_admin = client.get(
        f"/reports/{report_id}",
        headers={"x-admin-token": ADMIN_TOKEN},
    )
    assert allowed_admin.status_code == 200


def test_admin_reports_fail_closed_when_admin_token_is_unconfigured(monkeypatch) -> None:
    import app.main as main_module

    monkeypatch.setattr(main_module, "ADMIN_TOKEN", None)
    response = client.get(
        "/admin/reports",
        headers={"x-admin-token": "change-me"},
    )
    assert response.status_code == 503


def test_student_report_matches_chat_medium_floor_for_scholarship_context() -> None:
    response = client.post(
        "/report",
        json={
            "user_id": _user_id(),
            "content": "有人说奖学金补录要先交认证费",
            "channel": "web",
            "user_role": "student",
        },
    )
    assert response.status_code == 200
    assert response.json()["risk_level"] in {"medium", "high", "critical"}


def test_chat_and_report_levels_are_consistent_for_refund_deposit() -> None:
    user_id = _user_id()
    content = "退款前需要先交保证金"
    chat = client.post(
        "/chat",
        json={
            "user_id": user_id,
            "message": content,
            "user_profile": {"role": "general"},
        },
    )
    report = client.post(
        "/report",
        json={
            "user_id": user_id,
            "content": content,
            "channel": "web",
            "user_role": "general",
        },
    )
    assert chat.status_code == 200
    assert report.status_code == 200
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    assert abs(order[chat.json()["risk_level"]] - order[report.json()["risk_level"]]) <= 1


def test_report_extracts_urls_from_content_for_url_risk() -> None:
    response = client.post(
        "/report",
        json={
            "user_id": _user_id(),
            "content": "对方发来 http://secure-bank.top/login 让我核验",
            "channel": "web",
        },
    )
    assert response.status_code == 200
    assert response.json()["score_breakdown"]["url_score"] > 0


def test_educational_or_consultation_reports_do_not_escalate_to_high() -> None:
    samples = [
        "我想了解刷单返利、投资理财、USDT虚拟币、奖学金补录、机票退改签这些骗局怎么防范",
        "反诈宣传说不要把验证码告诉别人",
        "公检法不会让你转账到安全账户",
    ]
    for sample in samples:
        response = client.post(
            "/report",
            json={"user_id": _user_id(), "content": sample, "channel": "web"},
        )
        assert response.status_code == 200
        assert response.json()["risk_level"] in {"low", "medium"}


def test_action_inducing_reports_remain_medium_or_high() -> None:
    samples = [
        "客服让我提供验证码解冻账户",
        "导师带单稳赚不赔，让我充值 USDT",
        "公检法让我转账到安全账户",
    ]
    for sample in samples:
        response = client.post(
            "/report",
            json={"user_id": _user_id(), "content": sample, "channel": "web"},
        )
        assert response.status_code == 200
        assert response.json()["risk_level"] in {"medium", "high", "critical"}


def test_duplicate_report_uses_url_when_url_is_present() -> None:
    user_id = _user_id()
    first = _report(
        user_id,
        url="http://first-risk.top/login",
        content="这个链接让我转账到安全账户",
    ).json()
    second = _report(
        user_id,
        url="http://first-risk.top/login?utm=test",
        content="这个链接让我转账到安全账户",
    ).json()
    third = _report(
        user_id,
        url="http://second-risk.top/login",
        content="这个链接让我转账到安全账户",
    ).json()
    other_user = _report(
        _user_id(),
        url="http://first-risk.top/login",
        content="这个链接让我转账到安全账户",
    ).json()

    assert second["report_id"] == first["report_id"]
    assert second["duplicated"] is True
    assert third["report_id"] != first["report_id"]
    assert third["duplicated"] is False
    assert other_user["report_id"] != first["report_id"]
    assert other_user["duplicated"] is False


def test_admin_report_keyword_escapes_like_wildcards() -> None:
    first = _report(_user_id(), content="普通举报内容").json()
    second = _report(_user_id(), content="包含百分号 % 的举报内容").json()

    response = client.get(
        "/admin/reports?keyword=%",
        headers={"x-admin-token": ADMIN_TOKEN},
    )
    assert response.status_code == 200
    ids = {item["report_id"] for item in response.json()["items"]}
    assert second["report_id"] in ids
    assert first["report_id"] not in ids
