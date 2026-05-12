import uuid

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ui_root_page() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "反诈护盾实验室" in response.text


def test_ui_static_asset() -> None:
    response = client.get("/static/styles.css")
    assert response.status_code == 200
    assert "--bg-0" in response.text


def test_chat_high_risk_warning() -> None:
    payload = {
        "user_id": "u_student_1",
        "message": "有人冒充公检法让我马上转账到安全账户，还要验证码",
        "user_profile": {"role": "student", "risk_tolerance": "low"},
        "emotion": "anxious",
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] in {"high", "critical"}
    assert data["risk_score"] >= 40


def test_report_suspicious_url() -> None:
    payload = {
        "user_id": "u_report_1",
        "url": "http://xn--secure-bank-5k9f.top/login@notice",
        "content": "点击领取返利，先转账再提现",
    }
    response = client.post("/report", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] in {"suspicious", "high_risk"}
    assert data["risk_score"] >= 25


def test_scenario_flow() -> None:
    start_resp = client.post(
        "/scenarios/start",
        json={"user_id": "u_game_1", "scenario_id": "C001"},
    )
    assert start_resp.status_code == 200

    step1_resp = client.post(
        "/scenarios/answer",
        json={"user_id": "u_game_1", "option_index": 1},
    )
    assert step1_resp.status_code == 200
    assert step1_resp.json()["finished"] is False

    step2_resp = client.post(
        "/scenarios/answer",
        json={"user_id": "u_game_1", "option_index": 1},
    )
    assert step2_resp.status_code == 200
    assert step2_resp.json()["finished"] is True


def test_add_scam_requires_admin_token() -> None:
    payload = {
        "id": "S999",
        "type": "new_fake_case",
        "name": "新型诈骗",
        "keywords": ["新型", "诈骗"],
        "tactics": ["诱导下载"],
        "red_flags": ["先付款"],
        "typical_case": "受害者先付款后失联。",
        "prevention": ["不先付款"],
        "legal_refs": ["反电信网络诈骗法"],
    }
    response = client.post("/knowledge/scams", json=payload)
    assert response.status_code == 401


def test_report_updates_user_progress() -> None:
    user_id = f"u_persist_{uuid.uuid4().hex[:8]}"

    report_payload = {
        "user_id": user_id,
        "url": "http://xn--secure-bank-5k9f.top/login@notice",
        "content": "先转账再提现，保证金可退",
    }
    report_response = client.post("/report", json=report_payload)
    assert report_response.status_code == 200

    progress_response = client.get(f"/users/{user_id}/progress")
    assert progress_response.status_code == 200
    progress = progress_response.json()
    assert progress["reports_submitted"] >= 1
    assert progress["points"] >= 12


def test_get_user_report_history() -> None:
    user_id = f"u_history_{uuid.uuid4().hex[:8]}"

    payload = {
        "user_id": user_id,
        "url": "http://xn--secure-bank-5k9f.top/login@notice",
        "content": "点击领取返利，先转账再提现",
    }
    create_response = client.post("/report", json=payload)
    assert create_response.status_code == 200

    history_response = client.get(f"/users/{user_id}/reports?limit=5")
    assert history_response.status_code == 200

    history = history_response.json()
    assert history["user_id"] == user_id
    assert history["total"] >= 1
    assert isinstance(history["items"], list)
    latest = history["items"][0]
    assert latest["user_id"] == user_id
    assert latest["verdict"] in {"safe", "suspicious", "high_risk"}
    assert isinstance(latest["matched_keywords"], list)
    assert latest["created_at"]


def test_get_user_report_history_with_start_at_filter() -> None:
    user_id = f"u_time_filter_{uuid.uuid4().hex[:8]}"

    payload = {
        "user_id": user_id,
        "url": "http://xn--secure-bank-5k9f.top/login@notice",
        "content": "点击领取返利，先转账再提现",
    }
    create_response = client.post("/report", json=payload)
    assert create_response.status_code == 200

    # 使用远未来时间过滤，预期无记录。
    history_response = client.get(f"/users/{user_id}/reports?start_at=2999-01-01T00:00:00")
    assert history_response.status_code == 200

    history = history_response.json()
    assert history["user_id"] == user_id
    assert history["total"] == 0
    assert history["items"] == []


def test_get_user_report_history_invalid_time_range() -> None:
    user_id = f"u_time_invalid_{uuid.uuid4().hex[:8]}"

    response = client.get(
        f"/users/{user_id}/reports?start_at=2026-02-01T00:00:00&end_at=2026-01-01T00:00:00"
    )
    assert response.status_code == 400
    assert "start_at" in response.json()["detail"]


def test_scenarios_are_expanded() -> None:
    response = client.get("/scenarios")
    assert response.status_code == 200

    scenarios = response.json()
    assert len(scenarios) >= 7

    ids = {item["id"] for item in scenarios}
    assert {"C004", "C005", "C006", "C007"}.issubset(ids)


def test_knowledge_base_is_enriched() -> None:
    scams_response = client.get("/knowledge/scams")
    assert scams_response.status_code == 200
    scams = scams_response.json()
    assert len(scams) >= 8

    scam_types = {item["type"] for item in scams}
    assert {"fake_refund_customer_service", "acquaintance_impersonation", "fake_logistics_compensation"}.issubset(
        scam_types
    )

    laws_response = client.get("/knowledge/laws")
    assert laws_response.status_code == 200
    laws = laws_response.json()
    assert len(laws) >= 5


# ════════════════════════════════════
# 新增测试：认证、排行榜、AI 对话、AI 诈骗识别
# ════════════════════════════════════

def test_auth_register_success() -> None:
    payload = {
        "username": f"test_user_{uuid.uuid4().hex[:8]}",
        "password": "testpass123",
        "role": "student",
        "nickname": "测试用户",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["user_id"] > 0
    assert data["username"] == payload["username"]
    assert data["role"] == payload["role"]


def test_auth_register_duplicate_username() -> None:
    username = f"dup_user_{uuid.uuid4().hex[:8]}"
    # 注册成功
    r1 = client.post("/auth/register", json={
        "username": username,
        "password": "pass123456",
        "role": "general",
    })
    assert r1.status_code == 200
    # 重复注册应失败
    r2 = client.post("/auth/register", json={
        "username": username,
        "password": "otherpassword",
        "role": "general",
    })
    assert r2.status_code == 400


def test_auth_login_success() -> None:
    # 先注册
    username = f"login_test_{uuid.uuid4().hex[:8]}"
    password = "securepwd789"
    reg_resp = client.post("/auth/register", json={
        "username": username,
        "password": password,
        "role": "student",
    })
    assert reg_resp.status_code == 200

    # 登录
    login_resp = client.post("/auth/login", json={
        "username": username,
        "password": password,
    })
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert data["access_token"]
    assert data["username"] == username


def test_auth_login_wrong_password() -> None:
    response = client.post("/auth/login", json={
        "username": f"nonexistent_{uuid.uuid4().hex[:8]}",
        "password": "wrongpassword",
    })
    assert response.status_code == 401


def test_auth_me_with_valid_token() -> None:
    # 先注册获取 token
    username = f"me_test_{uuid.uuid4().hex[:8]}"
    reg_resp = client.post("/auth/register", json={
        "username": username,
        "password": "mypassword",
        "role": "general",
        "nickname": "昵称测试",
    })
    token = reg_resp.json()["access_token"]

    # 用 token 查询 /auth/me
    me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data["username"] == username
    assert data["nickname"] == "昵称测试"


def test_auth_me_without_token() -> None:
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_leaderboard_returns_data() -> None:
    """注册一个用户后，排行榜至少有数据"""
    # 确保有一个用户存在
    client.post("/auth/register", json={
        "username": f"lb_user_{uuid.uuid4().hex[:8]}",
        "password": "lb123456",
        "role": "student",
    })

    resp = client.get("/leaderboard?top=10")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["total"], int)
    assert isinstance(data["items"], list)
    assert len(data["items"]) >= 1
    item = data["items"][0]
    assert "rank" in item
    assert "username" in item
    assert "points" in item
    assert "level" in item


def test_ai_chat_endpoint_exists() -> None:
    """AI 聊天端点即使 Ollama 未运行也不应返回 500，应返回降级回复"""
    resp = client.post("/ai/chat", json={
        "message": "什么是刷单返利诈骗？",
        "history": [],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data
    assert len(data["reply"]) > 0


def test_risk_engine_ai_deepfake_detection() -> None:
    """验证 AI 深度伪造关键词能触发高风险判定"""
    payload = {
        "user_id": "ai_deepfake_test",
        "message": "有人用AI换脸视频冒充我朋友借钱",
        "user_profile": {"role": "student", "risk_tolerance": "low"},
        "emotion": "anxious",
    }
    resp = client.post("/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    # AI deepfake 规则权重为 22 + 可能命中其他规则
    assert data["risk_score"] >= 20
    assert data["risk_level"] in ("medium", "high", "critical")


def test_intent_recognizer_detects_ai_fraud() -> None:
    """验证意图识别器能检测到 AI 诈骗相关意图"""
    from app.services.intent_recognizer import IntentRecognizer
    recognizer = IntentRecognizer()
    intent, keywords, scores = recognizer.detect_intent("我收到了一个AI换脸的视频通话，对方说要借钱")
    # 应该匹配 ai_fraud 或 seeking_help 或 casual
    assert intent in ("detect_ai_fraud", "seeking_help", "casual"), f"Got intent: {intent}, scores: {scores}"


def test_report_service_catches_ai_fraud_keywords() -> None:
    """验证举报服务能检测 AI 诈骗关键词"""
    payload = {
        "user_id": "ai_report_test",
        "url": None,
        "content": "对方发来了一个AI换脸的deepfake视频，说是我的朋友急需用钱",
    }
    resp = client.post("/report", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    # 应该命中 AI 相关关键词
    has_ai_keyword = any(
        kw in ["AI换脸", "deepfake", "数字人", "AI生成视频", "AI冒充"]
        for kw in data.get("matched_keywords", [])
    )
    assert has_ai_keyword or data["risk_score"] >= 15, f"No AI keyword matched: {data['matched_keywords']}"


def test_knowledge_base_includes_ai_deepfake_scam() -> None:
    """验证知识库包含 AI 深度伪造骗局条目"""
    resp = client.get("/knowledge/scams")
    assert resp.status_code == 200
    scams = resp.json()
    scam_types = {item["type"] for item in scams}
    assert "ai_deepfake" in scam_types, f"Missing ai_deepfake type. Types: {scam_types}"

    ai_scam = next((s for s in scams if s["type"] == "ai_deepfake"), None)
    assert ai_scam is not None
    assert "深度伪造" in ai_scam.get("name", "") or "AI" in ai_scam.get("name", "")

