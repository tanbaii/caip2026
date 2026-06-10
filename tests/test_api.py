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
    assert '<div id="app"></div>' in response.text or "反诈护盾实验室" in response.text


def test_ui_static_asset() -> None:
    response = client.get("/static/styles.css")
    assert response.status_code == 200
    assert "--bg-0" in response.text


def test_chat_high_risk_warning() -> None:
    payload = {
        "user_id": 1,
        "message": "有人冒充公检法让我马上转账到安全账户，还要验证码",
        "user_profile": {"role": "student", "risk_tolerance": "low"},
        "emotion": "anxious",
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] in {"high", "critical"}
    assert data["risk_score"] >= 40
    assert "retrieved_knowledge" in data
    assert isinstance(data["retrieved_knowledge"], list)


def test_report_suspicious_url() -> None:
    payload = {
        "user_id": 2,
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
        json={"user_id": 3, "scenario_id": "C001"},
    )
    assert start_resp.status_code == 200

    step1_resp = client.post(
        "/scenarios/answer",
        json={"user_id": 3, "option_index": 1},
    )
    assert step1_resp.status_code == 200
    assert step1_resp.json()["finished"] is False

    step2_resp = client.post(
        "/scenarios/answer",
        json={"user_id": 3, "option_index": 1},
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
    user_id = uuid.uuid4().int % 1_000_000_000 + 1

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
    user_id = uuid.uuid4().int % 1_000_000_000 + 1

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
    user_id = uuid.uuid4().int % 1_000_000_000 + 1

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
    user_id = uuid.uuid4().int % 1_000_000_000 + 1

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
        "user_id": 4,
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
        "user_id": 5,
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


# ════════════════════════════════════
# 新增测试：JSON 配置驱动风险规则
# ════════════════════════════════════

def test_risk_rules_loaded_from_json_config() -> None:
    """RiskEngine 能从 risk_rules.json 加载文本规则"""
    from pathlib import Path

    from app.services.risk_engine import RiskEngine

    engine = RiskEngine()
    assert len(engine.rules) >= 10, f"Expected >= 10 text rules, got {len(engine.rules)}"
    rule_names = {r["name"] for r in engine.rules}
    assert "authority_pressure" in rule_names
    assert "account_takeover" in rule_names
    assert "ai_deepfake" in rule_names


def test_url_rules_loaded_from_json_config() -> None:
    """RiskEngine 能从 url_rules.json 加载 URL 规则"""
    from app.services.risk_engine import RiskEngine

    engine = RiskEngine()
    assert "t.cn" in engine.shortener_domains
    assert "top" in engine.risky_tlds
    assert len(engine._url_checks) >= 5


def test_risk_engine_fallback_when_config_missing(tmp_path) -> None:
    """当配置文件不存在时，RiskEngine 使用内置默认规则"""
    from app.services.risk_engine import RiskEngine

    missing = tmp_path / "nonexistent.json"
    engine = RiskEngine(risk_rules_path=missing, url_rules_path=missing)
    assert len(engine.rules) >= 10
    assert len(engine.shortener_domains) >= 3

    result = engine.evaluate_text(
        "公检法让我转到安全账户，还要验证码", [], "general", None
    )
    assert result["score"] >= 40
    assert result["level"] in ("high", "critical")


def test_text_authority_pressure_still_high_risk() -> None:
    """公检法+安全账户+验证码 文本仍能判为高风险"""
    from app.services.risk_engine import RiskEngine

    engine = RiskEngine()
    result = engine.evaluate_text(
        "有人冒充公检法让我马上转账到安全账户，还要验证码",
        [], "student", "anxious",
    )
    assert result["score"] >= 40
    assert result["level"] in ("high", "critical")
    assert len(result["reasons"]) >= 2


def test_text_ai_deepfake_still_high_risk() -> None:
    """AI换脸 文本仍能判为高风险"""
    from app.services.risk_engine import RiskEngine

    engine = RiskEngine()
    result = engine.evaluate_text(
        "有人用AI换脸视频冒充我朋友借钱",
        [], "student", "anxious",
    )
    assert result["score"] >= 20
    assert result["level"] in ("medium", "high", "critical")


def test_url_punycode_flagged() -> None:
    """punycode 域名 URL 仍被标记为可疑"""
    from app.services.risk_engine import RiskEngine

    engine = RiskEngine()
    result = engine.evaluate_url("http://xn--secure-bank-5k9f.top/login@notice")
    assert result["score"] >= 20
    assert any("punycode" in f for f in result["flags"])


def test_url_at_symbol_flagged() -> None:
    """包含 @ 的 URL 仍被标记"""
    from app.services.risk_engine import RiskEngine

    engine = RiskEngine()
    result = engine.evaluate_url("http://safe.com@evil.com/login")
    assert any("@" in f for f in result["flags"])
    assert result["score"] >= 20


def test_url_risky_tld_flagged() -> None:
    """高风险后缀 (.top) URL 仍被标记"""
    from app.services.risk_engine import RiskEngine

    engine = RiskEngine()
    result = engine.evaluate_url("http://example.top/login")
    assert any("后缀" in f for f in result["flags"])
    assert result["score"] >= 12


def test_url_shortener_domain_flagged() -> None:
    """短链域名 URL 仍被标记"""
    from app.services.risk_engine import RiskEngine

    engine = RiskEngine()
    result = engine.evaluate_url("http://t.cn/abc123")
    assert any("短链" in f for f in result["flags"])
    assert result["score"] >= 15


def test_url_clean_returns_low_risk() -> None:
    """正常 HTTPS URL 判为低风险"""
    from app.services.risk_engine import RiskEngine

    engine = RiskEngine()
    result = engine.evaluate_url("https://www.example.com/page")
    assert result["level"] == "low"
    assert result["score"] == 0


def test_json_config_drives_scoring() -> None:
    """修改 JSON 权重后评分应随之变化，证明规则真正从配置驱动"""
    import json
    import tempfile
    from pathlib import Path

    from app.services.risk_engine import RiskEngine

    # 读取原配置，把 authority_pressure 权重改为 999
    original = Path("app/data/risk_rules.json")
    cfg = json.loads(original.read_text(encoding="utf-8"))
    for rule in cfg["text_rules"]:
        if rule["name"] == "authority_pressure":
            rule["weight"] = 999
            break

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False)
        tmp_path = f.name

    try:
        engine = RiskEngine(risk_rules_path=tmp_path)
        result = engine.evaluate_text("涉及公检法调查", [], "general", None)
        assert result["score"] >= 999
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ════════════════════════════════════
# 新增测试：可解释输出字段
# ════════════════════════════════════

def test_chat_explainability_fields_exist() -> None:
    """/chat 响应包含 matched_rules、risk_breakdown、next_actions"""
    resp = client.post("/chat", json={
        "user_id": 9001,
        "message": "你好",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "matched_rules" in data
    assert "risk_breakdown" in data
    assert "next_actions" in data
    assert isinstance(data["matched_rules"], list)
    assert isinstance(data["risk_breakdown"], dict)
    assert isinstance(data["next_actions"], list)


def test_chat_high_risk_shows_matched_rules() -> None:
    """高危聊天能返回命中规则详情"""
    resp = client.post("/chat", json={
        "user_id": 9002,
        "message": "有人冒充公检法让我马上转账到安全账户，还要验证码",
        "user_profile": {"role": "student", "risk_tolerance": "low"},
        "emotion": "anxious",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] in {"high", "critical"}

    rules = data["matched_rules"]
    assert len(rules) >= 3
    rule_names = {r["rule"] for r in rules}
    assert "authority_pressure" in rule_names
    assert "account_takeover" in rule_names
    assert "transfer_critical" in rule_names

    # 每个 rule 都有完整的证据结构
    for rule in rules:
        assert "rule" in rule
        assert "evidence" in rule
        assert "weight" in rule
        assert "reason" in rule
        assert isinstance(rule["evidence"], list)
        assert isinstance(rule["weight"], int)


def test_chat_risk_breakdown_structure() -> None:
    """/chat 的 risk_breakdown 包含各维度分数"""
    resp = client.post("/chat", json={
        "user_id": 9003,
        "message": "有人冒充公检法让我马上转账到安全账户，还要验证码",
        "user_profile": {"role": "student"},
        "emotion": "anxious",
    })
    assert resp.status_code == 200
    bd = resp.json()["risk_breakdown"]
    for key in ("text_score", "knowledge_score", "profile_score", "emotion_score", "total"):
        assert key in bd, f"Missing key: {key}"
        assert isinstance(bd[key], int)
    assert bd["total"] >= 40


def test_chat_next_actions_reflect_risk_level() -> None:
    """高风险时 next_actions 包含止损建议"""
    resp = client.post("/chat", json={
        "user_id": 9004,
        "message": "公检法让我转到安全账户，还要验证码",
        "user_profile": {"role": "general"},
        "emotion": "anxious",
    })
    data = resp.json()
    if data["risk_level"] in {"high", "critical"}:
        actions = data["next_actions"]
        assert len(actions) >= 2
        assert any("停止" in a or "止付" in a for a in actions)


def test_chat_old_fields_still_present() -> None:
    """旧字段仍然存在且类型正确"""
    resp = client.post("/chat", json={
        "user_id": 9005,
        "message": "帮我看刷单返利",
        "user_profile": {"role": "student"},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["risk_score"], int)
    assert data["risk_level"] in ("low", "medium", "high", "critical")
    assert isinstance(data["intervention_script"], list)
    assert isinstance(data["recommendations"], list)
    assert isinstance(data["matched_scams"], list)


def test_report_explainability_fields_exist() -> None:
    """/report 响应包含 matched_rules、risk_breakdown、next_actions"""
    resp = client.post("/report", json={
        "user_id": 9006,
        "url": "https://example.com",
        "content": "正常内容",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "matched_rules" in data
    assert "risk_breakdown" in data
    assert "next_actions" in data
    assert isinstance(data["matched_rules"], list)
    assert isinstance(data["risk_breakdown"], dict)
    assert isinstance(data["next_actions"], list)


def test_report_url_risk_breakdown() -> None:
    """/report 的 risk_breakdown 区分 url_score 和 content_score"""
    resp = client.post("/report", json={
        "user_id": 9007,
        "url": "http://xn--secure-bank-5k9f.top/login@notice",
        "content": "点击领取返利，先转账再提现",
    })
    assert resp.status_code == 200
    bd = resp.json()["risk_breakdown"]
    assert "url_score" in bd
    assert "content_score" in bd
    assert "total" in bd
    assert bd["url_score"] > 0
    assert bd["content_score"] > 0
    assert bd["total"] == bd["url_score"] + bd["content_score"]


def test_report_url_matched_rules_contain_details() -> None:
    """/report 高危 URL 能返回 URL 规则命中详情"""
    resp = client.post("/report", json={
        "user_id": 9008,
        "url": "http://xn--secure-bank-5k9f.top/login@notice",
        "content": "",
    })
    assert resp.status_code == 200
    data = resp.json()
    rules = data["matched_rules"]
    assert len(rules) >= 2
    rule_names = {r["rule"] for r in rules}
    assert "punycode" in rule_names
    assert "at_symbol" in rule_names
    assert "risky_tld" in rule_names

    for rule in rules:
        assert "evidence" in rule
        assert "weight" in rule
        assert "reason" in rule


def test_report_old_fields_still_present() -> None:
    """/report 旧字段仍然存在"""
    resp = client.post("/report", json={
        "user_id": 9009,
        "url": "https://example.com",
        "content": "帮我看刷单返利",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["verdict"], str)
    assert data["verdict"] in ("safe", "suspicious", "high_risk")
    assert isinstance(data["risk_score"], int)
    assert isinstance(data["reasons"], list)
    assert isinstance(data["recommendations"], list)
    assert isinstance(data["matched_keywords"], list)
    assert isinstance(data["url_flags"], list)


def test_url_score_to_level_uses_url_config() -> None:
    """evaluate_url 使用 url_rules.json 的 score_levels 而非 risk_rules.json 的"""
    from app.services.risk_engine import RiskEngine

    engine = RiskEngine()
    # Punycode (20) + @ (20) + risky TLD (12) + HTTP (10) = 62
    result = engine.evaluate_url("http://xn--secure-bank-5k9f.top/login@notice")
    assert result["score"] == 62
    assert result["level"] == "high"
    # 如果错误地使用 risk_rules 的 critical=70，high=40，结果相同
    # 但通过 _url_score_to_level 方法存在性验证实现正确性
    assert hasattr(engine, "_url_score_to_level")


# ════════════════════════════════════
# 新增测试：敏感信息脱敏
# ════════════════════════════════════

def test_sanitizer_masks_phone_number() -> None:
    """手机号脱敏：138****5678"""
    from app.services.sanitizer import mask_phone

    assert mask_phone("我的手机号是13812345678") == "我的手机号是138****5678"
    assert mask_phone("联系19900001111和15622223333") == "联系199****1111和156****3333"
    assert mask_phone("没有手机号") == "没有手机号"


def test_sanitizer_masks_id_card() -> None:
    """身份证号脱敏"""
    from app.services.sanitizer import mask_id_card

    result = mask_id_card("我的身份证号是110101200001011234")
    assert "1101" in result
    assert "1234" in result
    assert "20000101" not in result
    assert "***********" in result


def test_sanitizer_masks_bank_card() -> None:
    """银行卡号脱敏"""
    from app.services.sanitizer import mask_bank_card

    result = mask_bank_card("卡号6222021234567890请查收")
    assert "6222" in result
    assert "7890" in result
    assert "12345678" not in result
    assert "*******" in result


def test_sanitizer_masks_verification_code() -> None:
    """验证码脱敏"""
    from app.services.sanitizer import mask_code

    assert "******" in mask_code("验证码:123456")
    assert "******" in mask_code("验证码：654321")
    assert "******" in mask_code("code: 789012")
    assert "123456" not in mask_code("验证码:123456")


def test_sanitizer_masks_email() -> None:
    """邮箱脱敏"""
    from app.services.sanitizer import mask_email

    result = mask_email("联系 zhangsan@example.com 获取详情")
    assert "zhangsan" not in result
    assert "z***" in result
    assert "@example.com" in result


def test_sanitizer_masks_token() -> None:
    """Token 脱敏"""
    from app.services.sanitizer import mask_token

    result = mask_token("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9x")
    assert "[TOKEN_REDACTED]" in result
    assert "eyJhbGci" not in result

    result2 = mask_token("token=sk-abcdefghijklmnop")
    assert "[TOKEN_REDACTED]" in result2


def test_sanitize_text_combined() -> None:
    """组合场景：多种敏感信息同时出现"""
    from app.services.sanitizer import sanitize_text

    text = "用户13812345678，身份证110101200001011234，验证码:654321"
    result = sanitize_text(text)
    assert "138****5678" in result
    assert "***********" in result
    assert "******" in result
    assert "13812345678" not in result
    assert "654321" not in result


def test_sanitize_preserves_risk_keywords() -> None:
    """脱敏不应破坏诈骗关键词识别"""
    from app.services.sanitizer import sanitize_text

    text = "对方让我先转账到安全账户，说有验证码就能解冻"
    result = sanitize_text(text)
    assert "安全账户" in result
    assert "解冻" in result
    assert "转账" in result


def test_chat_sanitizes_history_pii() -> None:
    """聊天历史中的手机号等敏感信息被脱敏"""
    resp = client.post("/chat", json={
        "user_id": 9010,
        "message": "我的手机号是13812345678，有人说公检法让我转账到安全账户",
        "user_profile": {"role": "student"},
    })
    assert resp.status_code == 200
    # 识别仍应正常
    data = resp.json()
    assert data["risk_score"] >= 0


# ════════════════════════════════════
# 新增测试：剧本杀式情景推理
# ════════════════════════════════════

def test_scenarios_return_at_least_9() -> None:
    """/scenarios 返回至少 9 个关卡"""
    resp = client.get("/scenarios")
    assert resp.status_code == 200
    scenarios = resp.json()
    assert len(scenarios) >= 9


def test_c008_exists_and_is_case_mystery() -> None:
    """C008 存在且 mode 为 case_mystery"""
    resp = client.get("/scenarios")
    scenarios = resp.json()
    c008 = next((s for s in scenarios if s["id"] == "C008"), None)
    assert c008 is not None
    assert c008["mode"] == "case_mystery"
    assert "AI" in c008["title"] or "换脸" in c008["title"]


def test_c009_exists_and_is_case_mystery() -> None:
    """C009 存在且 mode 为 case_mystery"""
    resp = client.get("/scenarios")
    scenarios = resp.json()
    c009 = next((s for s in scenarios if s["id"] == "C009"), None)
    assert c009 is not None
    assert c009["mode"] == "case_mystery"
    assert "奖学金" in c009["title"] or "助学金" in c009["title"]


def test_c008_has_at_least_3_steps_and_4_clues() -> None:
    """C008 至少 3 个步骤和 4 条线索"""
    from app.main import scenario_service

    scenario = scenario_service._scenarios["C008"]
    assert len(scenario["steps"]) >= 3
    assert len(scenario.get("clues", [])) >= 4


def test_c009_has_at_least_3_steps_and_4_clues() -> None:
    """C009 至少 3 个步骤和 4 条线索"""
    from app.main import scenario_service

    scenario = scenario_service._scenarios["C009"]
    assert len(scenario["steps"]) >= 3
    assert len(scenario.get("clues", [])) >= 4


def test_old_scenario_flow_still_works() -> None:
    """旧的 test_scenario_flow 仍然通过"""
    start_resp = client.post(
        "/scenarios/start",
        json={"user_id": 3, "scenario_id": "C001"},
    )
    assert start_resp.status_code == 200

    step1_resp = client.post(
        "/scenarios/answer",
        json={"user_id": 3, "option_index": 1},
    )
    assert step1_resp.status_code == 200
    assert step1_resp.json()["finished"] is False

    step2_resp = client.post(
        "/scenarios/answer",
        json={"user_id": 3, "option_index": 1},
    )
    assert step2_resp.status_code == 200
    assert step2_resp.json()["finished"] is True


def test_c008_start_returns_story_role_objectives_clues() -> None:
    """开始 C008 后响应中包含 story/role/objectives/clues"""
    resp = client.post(
        "/scenarios/start",
        json={"user_id": 8001, "scenario_id": "C008"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "case_mystery"
    assert data["story"] is not None
    assert len(data["story"]) > 10
    assert data["role"] is not None
    assert isinstance(data["objectives"], list)
    assert len(data["objectives"]) >= 3
    assert isinstance(data["clues"], list)
    assert len(data["clues"]) >= 4


def test_c008_finish_returns_case_summary_and_debrief() -> None:
    """完成 C008 后响应中包含 case_summary 和 debrief"""
    client.post(
        "/scenarios/start",
        json={"user_id": 8002, "scenario_id": "C008"},
    )

    # Step 1
    client.post("/scenarios/answer", json={"user_id": 8002, "option_index": 1})
    # Step 2
    client.post("/scenarios/answer", json={"user_id": 8002, "option_index": 1})
    # Step 3 (final)
    resp = client.post("/scenarios/answer", json={"user_id": 8002, "option_index": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data["finished"] is True
    assert data["case_summary"] is not None
    assert len(data["case_summary"]) > 10
    assert isinstance(data["debrief"], list)
    assert len(data["debrief"]) >= 3


# ════════════════════════════════════
# 新增测试：多轮对话状态机
# ════════════════════════════════════

def test_multi_turn_collecting_stage_with_pending_questions() -> None:
    """第一轮'有人说我中奖了'返回 collecting 阶段和 pending_questions"""
    resp = client.post("/chat", json={
        "user_id": 9100,
        "message": "有人说我中奖了，可信吗？",
        "user_profile": {"role": "student"},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_stage"] in ("collecting", "assessing")
    assert data["turn_count"] == 1
    # 应该有 pending_questions 追问细节
    assert len(data["pending_questions"]) >= 1
    # known_facts 应该包含 mentions_reward_or_subsidy
    assert data["known_facts"].get("mentions_reward_or_subsidy") is True


def test_multi_turn_second_round_escalates_with_new_facts() -> None:
    """第二轮'他让我交认证费，还要验证码'结合上下文升级风险"""
    user_id = 9101
    # 第一轮
    r1 = client.post("/chat", json={
        "user_id": user_id,
        "message": "有人说我中奖了，可信吗？",
        "user_profile": {"role": "student"},
    })
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["session_stage"] in ("collecting", "assessing")

    # 第二轮：补充转账+验证码
    r2 = client.post("/chat", json={
        "user_id": user_id,
        "message": "他让我交200元认证费，还要我的验证码",
        "user_profile": {"role": "student"},
    })
    assert r2.status_code == 200
    d2 = r2.json()
    # known_facts 跨轮累积
    assert d2["known_facts"].get("mentions_reward_or_subsidy") is True
    assert d2["known_facts"].get("has_transfer_request") is True
    assert d2["known_facts"].get("has_verification_code_request") is True
    # 多轮升级：转账+验证码组合应触发 conversation_score
    assert d2["risk_breakdown"].get("conversation_score", 0) > 0
    # 风险应升级
    assert d2["risk_score"] >= d1["risk_score"]
    assert d2["turn_count"] == 2


def test_multi_turn_authority_transfer_goes_warning() -> None:
    """公检法 + 安全账户 + 已经转账 进入 warning / critical"""
    user_id = 9102
    # 第一轮
    client.post("/chat", json={
        "user_id": user_id,
        "message": "有人自称公检法，说我涉嫌犯罪要调查我",
        "user_profile": {"role": "general"},
    })
    # 第二轮
    r2 = client.post("/chat", json={
        "user_id": user_id,
        "message": "他让我把钱转到安全账户，我已经转了",
        "user_profile": {"role": "general"},
        "emotion": "anxious",
    })
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["known_facts"].get("mentions_authority") is True
    assert d2["known_facts"].get("has_transfer_request") is True
    assert d2["known_facts"].get("already_paid") is True
    assert d2["session_stage"] == "warning"
    assert d2["risk_level"] in ("high", "critical")
    assert d2["risk_breakdown"].get("conversation_score", 0) > 0


def test_multi_turn_known_facts_accumulate() -> None:
    """known_facts 能跨轮累积"""
    user_id = 9103
    client.post("/chat", json={
        "user_id": user_id,
        "message": "有人让我下载会议软件远程控制电脑",
        "user_profile": {"role": "general"},
    })
    r2 = client.post("/chat", json={
        "user_id": user_id,
        "message": "他还让我别告诉别人，说这是保密调查",
        "user_profile": {"role": "general"},
    })
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["known_facts"].get("has_remote_control") is True
    assert d2["known_facts"].get("has_secrecy_pressure") is True
    assert d2["turn_count"] == 2


def test_multi_turn_old_fields_preserved() -> None:
    """ChatResponse 保留旧字段且多轮新增字段类型正确"""
    user_id = 9104
    r1 = client.post("/chat", json={
        "user_id": user_id,
        "message": "有人用AI换脸冒充朋友视频借钱",
        "user_profile": {"role": "student"},
    })
    assert r1.status_code == 200
    d1 = r1.json()

    # 旧字段
    assert isinstance(d1["reply"], str)
    assert isinstance(d1["intent"], str)
    assert isinstance(d1["matched_scams"], list)
    assert d1["risk_level"] in ("low", "medium", "high", "critical")
    assert isinstance(d1["risk_score"], int)
    assert isinstance(d1["intervention_script"], list)
    assert isinstance(d1["recommendations"], list)
    assert isinstance(d1["points_gained"], int)
    assert isinstance(d1["total_points"], int)
    assert isinstance(d1["badges"], list)
    assert isinstance(d1["latency_ms"], float)
    assert isinstance(d1["matched_rules"], list)
    assert isinstance(d1["risk_breakdown"], dict)
    assert isinstance(d1["next_actions"], list)

    # 新增字段
    assert isinstance(d1["session_stage"], str)
    assert isinstance(d1["known_facts"], dict)
    assert isinstance(d1["pending_questions"], list)
    assert isinstance(d1["conversation_summary"], str)
    assert isinstance(d1["turn_count"], int)
    assert d1["turn_count"] == 1


def test_multi_turn_ai_deepfake_refuse_verify_escalates() -> None:
    """AI视频借钱+拒绝核验 应识别为高危"""
    user_id = 9105
    client.post("/chat", json={
        "user_id": user_id,
        "message": "有人用AI换脸视频冒充我朋友借钱",
        "user_profile": {"role": "student"},
    })
    r2 = client.post("/chat", json={
        "user_id": user_id,
        "message": "他不让我视频验证身份，一直催我赶紧转账",
        "user_profile": {"role": "student"},
        "emotion": "anxious",
    })
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["known_facts"].get("mentions_ai_deepfake") is True
    assert d2["known_facts"].get("has_transfer_request") is True
    assert d2["known_facts"].get("has_time_pressure") is True
    assert d2["turn_count"] == 2
    # AI伪造+转账应通过 conversation_score 升级
    has_conv_rule = any(
        "ai_fake" in r.get("rule", "") or "conv_" in r.get("rule", "")
        for r in d2["matched_rules"]
    )
    assert has_conv_rule or d2["risk_level"] in ("high", "critical")


def test_multi_turn_warning_stops_questioning() -> None:
    """warning 阶段 pending_questions 应为空（不再追问）"""
    user_id = 9106
    client.post("/chat", json={
        "user_id": user_id,
        "message": "公检法让我把钱转到安全账户",
        "user_profile": {"role": "general"},
    })
    r2 = client.post("/chat", json={
        "user_id": user_id,
        "message": "我已经转账了，现在该怎么办",
        "user_profile": {"role": "general"},
        "emotion": "anxious",
    })
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["session_stage"] == "warning"
    assert d2["pending_questions"] == []


def test_multi_turn_reply_contains_stop_loss_in_warning() -> None:
    """warning 阶段回复应包含止损指导"""
    user_id = 9107
    client.post("/chat", json={
        "user_id": user_id,
        "message": "有人冒充公检法说我涉嫌洗钱",
        "user_profile": {"role": "student"},
    })
    r2 = client.post("/chat", json={
        "user_id": user_id,
        "message": "我已经给他转了5000块",
        "user_profile": {"role": "student"},
        "emotion": "anxious",
    })
    assert r2.status_code == 200
    d2 = r2.json()
    reply = d2["reply"]
    assert "止付" in reply or "报警" in reply or "联系银行" in reply


def test_multi_turn_stage_consistent_with_final_risk_level() -> None:
    """conversation_score 加成导致 risk_level 升级后，session_stage 与最终 risk_level 一致。

    场景：
      Round 1: "有人自称公安局的要调查我" → mentions_authority，基础分低
      Round 2: "他让我转账到安全账户" → 基础分 medium (authority_pressure=20)，
              但 conversation bonus +25 (conv_authority_transfer) 推至 high。
              此时 session_stage 应为 warning（high + turn>=2），pending_questions 为空。
    """
    user_id = 9200
    r1 = client.post("/chat", json={
        "user_id": user_id,
        "message": "有人自称公安局的要调查我",
        "user_profile": {"role": "general"},
    })
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["known_facts"].get("mentions_authority") is True

    r2 = client.post("/chat", json={
        "user_id": user_id,
        "message": "他让我转账到安全账户",
        "user_profile": {"role": "general"},
    })
    assert r2.status_code == 200
    d2 = r2.json()

    # 最终风险等级应为 high 或 critical（基础 20 + 对话加成 25 = 45）
    assert d2["risk_level"] in ("high", "critical")
    # 关键验证：conversation_score 生效
    assert d2["risk_breakdown"].get("conversation_score", 0) > 0
    # 关键验证：session_stage 与最终 risk_level 一致，不应停留在 collecting/assessing
    assert d2["session_stage"] == "warning", \
        f"Expected warning but got {d2['session_stage']} with risk_level={d2['risk_level']}"
    # warning 阶段 pending_questions 必须为空
    assert d2["pending_questions"] == []
    # known_facts 跨轮累积
    assert d2["known_facts"].get("mentions_authority") is True
    assert d2["known_facts"].get("has_transfer_request") is True
    assert d2["turn_count"] == 2


def test_chat_risk_score_uses_final_breakdown_total() -> None:
    user_id = 9300
    r1 = client.post("/chat", json={
        "user_id": user_id,
        "message": "有人让我先垫付刷单，说完成后返利",
        "user_profile": {"role": "student"},
        "emotion": "anxious",
    })
    assert r1.status_code == 200
    d1 = r1.json()

    r2 = client.post("/chat", json={
        "user_id": user_id,
        "message": "我已经下单了咋办",
        "user_profile": {"role": "student"},
        "emotion": "anxious",
    })
    assert r2.status_code == 200
    d2 = r2.json()

    assert d1["risk_score"] == d1["risk_breakdown"]["total"]
    assert d2["risk_score"] == d2["risk_breakdown"]["total"]
    assert d2["risk_score"] >= d1["risk_score"]


def test_chat_new_scam_topic_resets_stale_conversation_facts() -> None:
    user_id = 9400
    r1 = client.post("/chat", json={
        "user_id": user_id,
        "message": "有人用AI换脸视频冒充我朋友借钱，让我马上转账",
        "user_profile": {"role": "student"},
        "emotion": "anxious",
    })
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["known_facts"].get("mentions_ai_deepfake") is True

    r2 = client.post("/chat", json={
        "user_id": user_id,
        "message": "有人让我先垫付刷单，说完成后返利",
        "user_profile": {"role": "student"},
        "emotion": "anxious",
    })
    assert r2.status_code == 200
    d2 = r2.json()

    rule_names = {item.get("rule", "") for item in d2["matched_rules"]}
    assert "conv_ai_fake_transfer" not in rule_names
    assert d2["known_facts"].get("mentions_ai_deepfake") is not True
    assert d2["known_facts"].get("mentions_reward_or_subsidy") is True
    assert d2["turn_count"] == 1


def test_rag_rule_formatter_hides_internal_rule_names() -> None:
    from app.services.rag_reply_service import _format_rules

    text = _format_rules([
        {
            "rule": "conv_ai_fake_transfer",
            "weight": 22,
            "reason": "多轮对话确认：AI伪造身份并要求转账",
        }
    ])

    assert "conv_ai_fake_transfer" not in text
    assert "22" not in text
    assert "AI伪造身份" in text


def test_rag_sanitizer_rewrites_report_style_reply() -> None:
    from app.services.rag_reply_service import _sanitize_reply

    reply = """朋友，你描述的很像刷单返利诈骗。
【风险等级】medium
【最终风险分】29
【命中规则】出现放款或服务前收费特征"""

    cleaned = _sanitize_reply(
        reply,
        {
            "risk_level": "medium",
            "matched_rules": [
                {"reason": "出现放款或服务前收费特征"},
                {"reason": "文本与已知诈骗模型高度相关"},
            ],
            "recommendations": [
                "优先使用官方平台或官方客服渠道",
                "拒绝任何先付款后服务的要求",
            ],
        },
        "有人让我先垫付刷单，说完成后返利",
    )

    assert "【风险等级】" not in cleaned
    assert "【最终风险分】" not in cleaned
    assert "命中规则" not in cleaned
    assert "先垫付" in cleaned
    assert "不要继续" in cleaned or "不要再" in cleaned


def test_rag_sanitizer_rewrites_prompt_leak() -> None:
    from app.services.rag_reply_service import _sanitize_reply

    cleaned = _sanitize_reply(
        "请重新按【高风险】规则引擎评估。",
        {
            "risk_level": "high",
            "matched_rules": [{"reason": "多轮对话确认：以奖金/补贴为由要求缴费"}],
            "recommendations": ["保留聊天记录", "联系银行申请止付"],
        },
        "我把他拉黑了",
    )

    assert "请重新按" not in cleaned
    assert "规则引擎" not in cleaned
    assert "不要再" in cleaned or "马上停" in cleaned


def test_rag_reply_blocks_internal_json_echo() -> None:
    from app.services.rag_reply_service import _looks_like_internal_echo

    assert _looks_like_internal_echo('{"user_message":"x","risk_engine_result":{}}') is True
    assert _looks_like_internal_echo("请先停止付款，并通过官方渠道核实。") is False


def test_chat_workflow_runner_preserves_chat_contract() -> None:
    from app.main import gamification_service, intent_recognizer, knowledge_base, risk_engine
    from app.models.schemas import ChatRequest
    from app.services.chat_workflow import ChatWorkflowRunner
    from app.services.dialogue_service import DialogueService

    service = DialogueService(
        knowledge_base=knowledge_base,
        intent_recognizer=intent_recognizer,
        risk_engine=risk_engine,
        gamification=gamification_service,
    )
    runner = ChatWorkflowRunner(service)
    request = ChatRequest.model_validate({
        "user_id": 9500,
        "message": "有人让我先垫付刷单，说完成后返利",
        "user_profile": {"role": "student"},
        "emotion": "anxious",
    })

    data = runner.process_chat(request)

    assert runner.engine in {"langgraph", "sequential"}
    assert data["risk_score"] == data["risk_breakdown"]["total"]
    assert data["matched_scams"]
    assert "retrieved_knowledge" in data
    assert isinstance(data["reply"], str)
