from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _uid() -> int:
    return uuid.uuid4().int % 1_000_000_000 + 100_000


def _chat(user_id: int, message: str) -> dict:
    response = client.post(
        "/chat",
        json={
            "user_id": user_id,
            "message": message,
            "user_profile": {"role": "student"},
        },
    )
    assert response.status_code == 200
    return response.json()


def test_requested_screen_share_is_not_treated_as_already_executed() -> None:
    user_id = _uid()

    data = _chat(user_id, "对方让我下载会议软件并开启屏幕共享")

    facts = data["known_facts"]
    assert facts.get("has_remote_control_request") is True
    assert facts.get("has_remote_control") is not True
    assert data["session_stage"] in {"assessing", "preventive_warning"}
    assert data["current_danger_level"] in {"low", "medium"}
    assert "你现在屏幕正被对方" not in data["reply"]
    assert "远程控制记录" not in data["reply"]


def test_joke_and_clear_denial_downgrade_current_danger_after_prior_risk() -> None:
    user_id = _uid()
    _chat(user_id, "对方让我下载会议软件并开启屏幕共享")
    _chat(user_id, "投资群老师保证高收益低风险")

    joke = _chat(user_id, "ok我骗你的")
    clarified = _chat(user_id, "我真的是骗你的，我没有下载也没有听他说的")

    assert joke["session_stage"] in {"test_mode", "clarifying"}
    assert joke["risk_level"] in {"low", "medium"}
    assert joke["current_danger_level"] == "low"

    assert clarified["known_facts"].get("test_mode") is True
    assert clarified["known_facts"].get("user_clarified_no_action") is True
    assert clarified["risk_level"] in {"low", "medium"}
    assert clarified["current_danger_level"] == "low"
    assert "冻结账户" not in clarified["reply"]
    assert "报警" not in clarified["reply"]


def test_pasted_advice_is_not_assumed_completed_or_escalated() -> None:
    user_id = _uid()
    _chat(user_id, "对方让我下载会议软件并开启屏幕共享")
    reported = _chat(user_id, "好吧，我报警了")
    pasted = _chat(
        user_id,
        "第一，马上联系银行冻结所有相关账户和支付功能；第二，检查并彻底卸载手机里所有远程控制或会议软件；第三，修改重要账号密码并开启双重验证。别急着删聊天记录，保留好作为证据",
    )

    assert reported["known_facts"].get("reported_to_police") is True
    assert pasted["known_facts"].get("quoted_advice") is True
    assert pasted["known_facts"].get("bank_frozen") is not True
    assert pasted["known_facts"].get("remote_control_removed") is not True
    assert pasted["known_facts"].get("password_changed") is not True
    assert "是否已经完成" in pasted["reply"] or "如果已经完成" in pasted["reply"]
    assert "挂失 SIM" not in pasted["reply"]
    assert "恢复出厂" not in pasted["reply"]


def test_executed_remote_control_and_code_exposure_still_trigger_recovery() -> None:
    user_id = _uid()

    data = _chat(user_id, "我已经下载会议软件并开启屏幕共享，验证码也被对方看到了")

    facts = data["known_facts"]
    assert facts.get("has_remote_control") is True
    assert facts.get("verification_code_exposed") is True
    assert data["session_stage"] in {"account_recovery", "active_blocking"}
    assert data["current_danger_level"] in {"high", "critical"}
    assert data["risk_level"] in {"high", "critical"}


def test_transfer_request_with_explicit_no_action_stays_preventive() -> None:
    user_id = _uid()

    data = _chat(user_id, "对方让我转账但我没转，也没输入验证码")

    facts = data["known_facts"]
    assert facts.get("has_transfer_request") is True
    assert facts.get("user_clarified_no_action") is True
    assert facts.get("already_paid") is not True
    assert facts.get("verification_code_exposed") is not True
    assert data["current_danger_level"] in {"low", "medium"}
    assert data["risk_level"] in {"low", "medium"}
    assert "冻结" not in data["reply"]


def test_completed_remote_control_closure_caps_current_danger_and_softens_reply() -> None:
    user_id = _uid()

    first = _chat(user_id, "对方让我下载会议软件并开启屏幕共享")
    assert first["known_facts"].get("has_remote_control_request") is True

    second = _chat(user_id, "好的，我现在卸载掉软件了")
    assert second["known_facts"].get("remote_control_removed") is True

    third = _chat(user_id, "没有扣款，我已经拉黑他了，证据也保存好了，我跟我妈妈说了")
    final = _chat(user_id, "密码修改了，没有异常，后台很干净")

    facts = final["known_facts"]
    assert facts.get("remote_control_removed") is True
    assert facts.get("no_abnormal_charge") is True
    assert facts.get("blocked_contact") is True
    assert facts.get("evidence_saved") is True
    assert facts.get("trusted_person_informed") is True
    assert facts.get("password_changed") is True
    assert facts.get("device_checked_clean") is True
    assert final["session_stage"] in {"closure_check", "low_risk_monitoring"}
    assert final["risk_dimensions"]["scam_likelihood"]["score"] >= 40
    assert final["risk_dimensions"]["current_danger"]["score"] <= 20
    assert 20 <= final["risk_dimensions"]["residual_risk"]["score"] <= 35
    assert final["risk_level"] in {"low", "medium"}
    assert "实时风险已经明显降低" in final["reply"]
    assert "恢复出厂" not in final["reply"]
    assert "冻结" not in final["reply"]
    assert "立刻报警" not in final["reply"]


def test_downloaded_then_uninstalled_without_screen_share_is_capped() -> None:
    user_id = _uid()

    data = _chat(user_id, "我下载了会议软件，但没开屏幕共享，现在已经卸载软件了，没有转账，也没有验证码")

    assert data["known_facts"].get("remote_control_removed") is True
    assert data["known_facts"].get("no_transfer") is True
    assert data["known_facts"].get("no_verification_code") is True
    assert data["risk_dimensions"]["current_danger"]["score"] <= 35
    assert data["session_stage"] == "closure_check"
    assert "冻结" not in data["reply"]
    assert "报警" not in data["reply"]


def test_screen_share_ended_without_code_or_transfer_is_not_emergency() -> None:
    user_id = _uid()

    data = _chat(user_id, "我开过屏幕共享，但没输入验证码，也没转账，现在断网并卸载了软件")

    assert data["known_facts"].get("has_remote_control") is True
    assert data["known_facts"].get("remote_control_removed") is True
    assert data["known_facts"].get("network_disconnected") is True
    assert data["known_facts"].get("no_transfer") is True
    assert data["known_facts"].get("no_verification_code") is True
    assert data["risk_dimensions"]["current_danger"]["score"] <= 35
    assert data["session_stage"] == "closure_check"
    assert "冻结" not in data["reply"]
    assert "恢复出厂" not in data["reply"]


def test_pii_recall_after_self_provided_phone_is_masked_not_escalated() -> None:
    user_id = _uid()

    provided = _chat(user_id, "我的手机号是 13566632222")
    recalled = _chat(user_id, "我的手机号是多少")

    assert provided["known_facts"].get("self_pii_provide") is True
    assert recalled["intent"] == "self_pii_recall"
    assert recalled["known_facts"].get("self_pii_recall") is True
    assert recalled["known_facts"].get("third_party_pii_request") is not True
    assert recalled["risk_dimensions"]["privacy_risk"]["score"] >= 20
    assert recalled["risk_dimensions"]["current_danger"]["score"] <= 15
    assert recalled["session_stage"] == "privacy_reminder"
    assert "135****2222" in recalled["reply"]
    assert "远程控制" not in recalled["reply"]
    assert "冻结" not in recalled["reply"]
    assert "报警" not in recalled["reply"]


def test_third_party_phone_request_raises_privacy_only_not_emergency() -> None:
    user_id = _uid()

    data = _chat(user_id, "对方问我的手机号是多少")

    assert data["intent"] in {"third_party_pii_request", "pii_disclosure_warning"}
    assert data["known_facts"].get("third_party_pii_request") is True
    assert data["risk_dimensions"]["privacy_risk"]["score"] >= 30
    assert data["risk_dimensions"]["current_danger"]["score"] <= 35
    assert data["session_stage"] in {"privacy_reminder", "preventive_warning"}
    assert "冻结" not in data["reply"]
    assert "报警" not in data["reply"]
    assert "远程控制" not in data["reply"]


def test_credential_and_remote_control_requests_still_enter_blocking() -> None:
    user_id = _uid()

    code = _chat(user_id, "对方问我要验证码")
    remote_code = _chat(user_id, "对方让我开屏幕共享看验证码")

    assert code["intent"] == "credential_leakage_emergency"
    assert code["session_stage"] in {"active_blocking", "preventive_warning", "account_recovery"}
    assert code["risk_dimensions"]["current_danger"]["score"] >= 35

    assert remote_code["intent"] in {"active_remote_control", "credential_leakage_emergency"}
    assert remote_code["known_facts"].get("has_remote_control_request") is True
    assert remote_code["known_facts"].get("has_verification_code_request") is True
    assert remote_code["session_stage"] in {"active_blocking", "preventive_warning"}
    assert remote_code["risk_dimensions"]["current_danger"]["score"] >= 35


def test_phone_sent_without_code_or_transfer_is_privacy_risk_not_funds_emergency() -> None:
    user_id = _uid()

    data = _chat(user_id, "我把手机号发给他了，但没有验证码、没有转账")

    assert data["known_facts"].get("pii_disclosed_to_third_party") is True
    assert data["known_facts"].get("verification_code_exposed") is not True
    assert data["known_facts"].get("already_paid") is not True
    assert data["risk_dimensions"]["privacy_risk"]["score"] >= 40
    assert data["risk_dimensions"]["current_danger"]["score"] <= 35
    assert "冻结" not in data["reply"]
    assert "报警" not in data["reply"]


def test_code_sent_to_other_party_escalates_to_account_protection() -> None:
    user_id = _uid()

    data = _chat(user_id, "我把验证码也发给他了")

    assert data["intent"] == "credential_leakage_emergency"
    assert data["known_facts"].get("verification_code_exposed") is True
    assert data["session_stage"] in {"account_recovery", "active_blocking"}
    assert data["risk_dimensions"]["current_danger"]["score"] >= 55
