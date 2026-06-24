from __future__ import annotations

import os
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.models.schemas import (
    AIChatRequest,
    AIChatResponse,
    ChatConversationCreateResponse,
    ChatConversationListResponse,
    ChatConversationMessagesResponse,
    ChatHistoryResponse,
    ChatRequest,
    ChatResetRequest,
    ChatResponse,
    LeaderboardResponse,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    AdminReportsResponse,
    ReportDetailResponse,
    ReportReviewRequest,
    ReportRequest,
    ReportResponse,
    ReportHistoryResponse,
    ReportStatusUpdate,
    RuleRollbackRequest,
    RuleUpdateRequest,
    ScamEntryCreate,
    ScenarioAnswerRequest,
    ScenarioAnswerResponse,
    ScenarioStartRequest,
    ScenarioStartResponse,
    ScenarioSummary,
    TextRuleCreateRequest,
    UserInfoResponse,
    UserProgressResponse,
)
from app.services.auth_service import AuthService
from app.services.ai_risk_service import AIRiskAssessor
from app.services.chat_workflow import ChatWorkflowRunner
from app.services.dashboard_service import DashboardService
from app.services.dialogue_service import DialogueService
from app.services.env_loader import load_dotenv
from app.services.gamification import GamificationService
from app.services.intent_recognizer import IntentRecognizer
from app.services.knowledge_base import KnowledgeBase
from app.services.knowledge_retriever import KnowledgeRetriever
from app.services.hybrid_retriever import HybridRetriever
from app.services.report_service import ReportService
from app.services.rag_reply_service import RagReplyGenerator
from app.services.risk_engine import RiskEngine
from app.services.rule_management import RuleManagementService
from app.services.scenario_service import ScenarioService
from app.services.storage import SQLiteStorage

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
load_dotenv(PROJECT_ROOT / ".env")
FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"
FRONTEND_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"
FRONTEND_GODOT_DIST_DIR = FRONTEND_DIST_DIR / "godot_game"
FRONTEND_GODOT_PUBLIC_DIR = PROJECT_ROOT / "frontend" / "public" / "godot_game"
LEGACY_WEB_DIR = BASE_DIR / "web"
SPA_ROUTES = {"login", "overview", "chat", "report", "game", "knowledge", "leaderboard", "profile", "admin"}
API_PREFIXES = {"health", "auth", "chat", "ai", "report", "reports", "scenarios", "users", "leaderboard", "knowledge", "admin"}
logger = logging.getLogger(__name__)
ADMIN_TOKEN = os.getenv("ANTI_FRAUD_ADMIN_TOKEN")
if ADMIN_TOKEN is not None:
    ADMIN_TOKEN = ADMIN_TOKEN.strip() or None
if ADMIN_TOKEN is None:
    logger.warning("ANTI_FRAUD_ADMIN_TOKEN is not configured; admin endpoints are disabled.")
JWT_SECRET = os.getenv("JWT_SECRET", "anti-fraud-lab-secret-key-change-in-production-2024")

# ── CORS ──
_cors_origins_env = os.getenv("CORS_ORIGINS", "")
DEV_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:8000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
]
ALLOWED_ORIGINS = (
    [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
    if _cors_origins_env
    else DEV_CORS_ORIGINS
)

# ── Rate Limiting (in-memory, no external deps) ──
RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "0"))  # 0 = disabled
REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "1").lower() not in {"0", "false", "no"}
RAG_RETRIEVAL_ENABLED = os.getenv("RAG_RETRIEVAL_ENABLED", "1").lower() not in {"0", "false", "no"}

knowledge_base = KnowledgeBase(BASE_DIR / "data" / "knowledge_base.json")
intent_recognizer = IntentRecognizer()
risk_engine = RiskEngine()
_db_path = os.getenv("DB_PATH") or str(BASE_DIR / "data" / "anti_fraud.db")
storage = SQLiteStorage(Path(_db_path))
rule_management_service = RuleManagementService(risk_engine=risk_engine, storage=storage)
dashboard_service = DashboardService(
    storage=storage,
    knowledge_base=knowledge_base,
    rule_management=rule_management_service,
)
gamification_service = GamificationService(storage=storage)
auth_service = AuthService(storage=storage, secret_key=JWT_SECRET)
report_service = ReportService(
    risk_engine=risk_engine,
    gamification=gamification_service,
    storage=storage,
)
scenario_service = ScenarioService(
    data_path=BASE_DIR / "data" / "scenarios.json",
    gamification=gamification_service,
)
knowledge_retriever = (
    KnowledgeRetriever.from_env()
    if RAG_RETRIEVAL_ENABLED
    else None
)
_bm25_index_path = os.getenv("RAG_BM25_INDEX_PATH") or str(BASE_DIR / "data" / "knowledge_base" / "bm25_index.pkl")
hybrid_retriever = HybridRetriever(
    dense_retriever=knowledge_retriever,
    bm25_index_path=_bm25_index_path,
)
rag_reply_generator = (
    RagReplyGenerator()
    if (
        os.getenv("RAG_LLM_ENABLED", "0").lower() in {"1", "true", "yes"}
        or os.getenv("CHAT_LLM_ENABLED", "0").lower() in {"1", "true", "yes"}
    )
    else None
)
ai_risk_assessor = AIRiskAssessor()
dialogue_service = DialogueService(
    knowledge_base=knowledge_base,
    intent_recognizer=intent_recognizer,
    risk_engine=risk_engine,
    gamification=gamification_service,
    knowledge_retriever=knowledge_retriever,
    hybrid_retriever=hybrid_retriever,
    rag_reply_generator=rag_reply_generator,
    ai_risk_assessor=ai_risk_assessor,
    storage=storage,
)
if os.getenv("CHAT_FLOW_ENGINE", "classic").lower() in {"langgraph", "graph"}:
    dialogue_service = ChatWorkflowRunner(dialogue_service)

app = FastAPI(
    title="Anti-Fraud Multi-modal Dialogue System",
    description="面向学生与泛个人用户的反诈科普、实时劝阻、举报与闯关训练系统",
    version="0.1.0",
)

if FRONTEND_ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS_DIR), name="frontend-assets")

_godot_static_dir = FRONTEND_GODOT_PUBLIC_DIR if FRONTEND_GODOT_PUBLIC_DIR.exists() else FRONTEND_GODOT_DIST_DIR
if _godot_static_dir.exists():
    app.mount("/godot_game", StaticFiles(directory=_godot_static_dir, html=True), name="godot-game")

app.mount("/static", StaticFiles(directory=LEGACY_WEB_DIR), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Rate limiter middleware ──

if RATE_LIMIT_RPM > 0:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    _request_counts: dict[str, list[float]] = {}

    class RateLimitMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            client_ip = request.client.host if request.client else "unknown"
            now = time.time()
            window_start = now - 60.0

            hits = _request_counts.get(client_ip, [])
            hits = [t for t in hits if t > window_start]

            if len(hits) >= RATE_LIMIT_RPM:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "请求过于频繁，请稍后再试"},
                )

            hits.append(now)
            _request_counts[client_ip] = hits
            return await call_next(request)

    app.add_middleware(RateLimitMiddleware)


def _frontend_index_file() -> Path:
    vue_index = FRONTEND_DIST_DIR / "index.html"
    if vue_index.exists():
        return vue_index
    return LEGACY_WEB_DIR / "index.html"


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(_frontend_index_file())


@app.get("/login", include_in_schema=False)
@app.get("/overview", include_in_schema=False)
@app.get("/chat", include_in_schema=False)
@app.get("/report", include_in_schema=False)
@app.get("/game", include_in_schema=False)
@app.get("/knowledge", include_in_schema=False)
@app.get("/profile", include_in_schema=False)
@app.get("/admin/rules", include_in_schema=False)
def vue_page() -> FileResponse:
    return FileResponse(_frontend_index_file())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "anti-fraud-dialogue"}


@app.get("/health/rag")
def rag_health() -> dict[str, object]:
    health = KnowledgeRetriever.health_from_env(
        knowledge_retriever,
        enabled=RAG_RETRIEVAL_ENABLED,
    )
    health["hybrid"] = {
        "configured": hybrid_retriever is not None,
        "bm25_index": hybrid_retriever is not None and hybrid_retriever.bm25_index is not None,
        "bm25_docs": hybrid_retriever.bm25_docs if hybrid_retriever is not None else 0,
        "bm25_index_path": _bm25_index_path,
        "reranker_enabled": os.getenv("RAG_RERANK_ENABLED", "0").lower() in {"1", "true", "yes"},
    }
    return health


def _resolve_user(
    requested_user_id: int,
    authorization: str | None,
) -> dict[str, object] | None:
    if not authorization:
        if REQUIRE_AUTH:
            raise HTTPException(status_code=401, detail="请先登录后再使用该功能")
        return None

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供有效令牌")

    user = auth_service.get_current_user(authorization.removeprefix("Bearer "))
    if not user:
        raise HTTPException(status_code=401, detail="令牌无效或已过期")
    if int(user["id"]) != requested_user_id:
        raise HTTPException(status_code=403, detail="不能访问或修改其他用户的数据")
    return user


def _require_admin(x_admin_token: str | None) -> None:
    # TODO: Replace this shared token check with real role-based admin authorization.
    if ADMIN_TOKEN is None:
        logger.error("Admin access denied because ANTI_FRAUD_ADMIN_TOKEN is not configured.")
        raise HTTPException(status_code=503, detail="Admin token is not configured")
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="管理员令牌错误")


def _require_authenticated_user(authorization: str | None) -> dict[str, object]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    user = auth_service.get_current_user(authorization.removeprefix("Bearer "))
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


_REPORT_RATE_LIMIT_WINDOW_SECONDS = 60
_REPORT_RATE_LIMIT_MAX_REQUESTS = 5
_report_rate_limits: dict[str, list[float]] = {}


def _check_report_rate_limit(user_id: int, request: Request) -> None:
    client_host = request.client.host if request.client else "unknown"
    key = f"{int(user_id)}:{client_host}"
    now = time.monotonic()
    window_start = now - _REPORT_RATE_LIMIT_WINDOW_SECONDS
    recent = [timestamp for timestamp in _report_rate_limits.get(key, []) if timestamp >= window_start]
    if len(recent) >= _REPORT_RATE_LIMIT_MAX_REQUESTS:
        _report_rate_limits[key] = recent
        raise HTTPException(status_code=429, detail="举报提交过于频繁，请稍后再试")
    recent.append(now)
    _report_rate_limits[key] = recent


@app.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    authorization: str | None = Header(default=None),
) -> ChatResponse:
    user = _resolve_user(request.user_id, authorization)
    if user:
        request = request.model_copy(
            update={
                "user_profile": request.user_profile.model_copy(update={"role": user["role"]}),
            }
        )
    response = dialogue_service.process_chat(request)
    if response.get("risk_level") in {"high", "critical"}:
        response["report_prefill"] = {
            "content": request.message,
            "url": None,
            "channel": request.channel,
            "risk_level": response.get("risk_level"),
            "risk_score": response.get("risk_score"),
            "reasons": response.get("intervention_script") or response.get("recommendations") or [],
            "matched_rules": response.get("matched_rules", []),
            "score_breakdown": response.get("risk_breakdown", {}),
        }
    return ChatResponse.model_validate(response)


@app.post("/chat/reset")
def reset_chat(
    request: ChatResetRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    _resolve_user(request.user_id, authorization)
    dialogue_service.reset_conversation(request.user_id, request.conversation_id)
    return {"message": "对话状态已重置"}


@app.post("/users/{user_id}/chat/conversations", response_model=ChatConversationCreateResponse)
def create_user_chat_conversation(
    user_id: int,
    authorization: str | None = Header(default=None),
) -> ChatConversationCreateResponse:
    _resolve_user(user_id, authorization)
    conversation = storage.create_chat_conversation(user_id=user_id)
    dialogue_service.reset_conversation(user_id, str(conversation["conversation_id"]))
    return ChatConversationCreateResponse.model_validate(conversation)


@app.get("/users/{user_id}/chat/conversations", response_model=ChatConversationListResponse)
def get_user_chat_conversations(
    user_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    authorization: str | None = Header(default=None),
) -> ChatConversationListResponse:
    _resolve_user(user_id, authorization)
    items = storage.list_chat_conversations(user_id=user_id, limit=limit)
    return ChatConversationListResponse.model_validate(
        {
            "user_id": user_id,
            "total": len(items),
            "items": items,
        }
    )


@app.get(
    "/users/{user_id}/chat/conversations/{conversation_id}/messages",
    response_model=ChatConversationMessagesResponse,
)
def get_user_chat_conversation_messages(
    user_id: int,
    conversation_id: str,
    authorization: str | None = Header(default=None),
) -> ChatConversationMessagesResponse:
    _resolve_user(user_id, authorization)
    messages = storage.list_chat_conversation_messages(
        user_id=user_id,
        conversation_id=conversation_id,
    )
    if not messages and not storage.get_chat_conversation(user_id=user_id, conversation_id=conversation_id):
        raise HTTPException(status_code=404, detail="对话不存在")
    return ChatConversationMessagesResponse.model_validate(
        {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "messages": messages,
        }
    )


@app.delete("/users/{user_id}/chat/conversations/{conversation_id}")
def delete_user_chat_conversation(
    user_id: int,
    conversation_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    _resolve_user(user_id, authorization)
    deleted = storage.delete_chat_conversation(
        user_id=user_id,
        conversation_id=conversation_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="对话不存在")
    dialogue_service.reset_conversation(user_id, conversation_id)
    return {"message": "对话已删除"}


@app.get("/users/{user_id}/chat/history", response_model=ChatHistoryResponse)
def get_user_chat_history(
    user_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    authorization: str | None = Header(default=None),
) -> ChatHistoryResponse:
    _resolve_user(user_id, authorization)
    items = storage.list_chat_messages(user_id=user_id, limit=limit)
    return ChatHistoryResponse.model_validate(
        {
            "user_id": user_id,
            "total": len(items),
            "items": items,
        }
    )


@app.post("/report", response_model=ReportResponse)
def report(
    request: ReportRequest,
    raw_request: Request,
    authorization: str | None = Header(default=None),
) -> ReportResponse:
    user = _resolve_user(request.user_id, authorization)
    _check_report_rate_limit(request.user_id, raw_request)
    user_role = str(user["role"]) if user else request.user_role
    result = report_service.analyze(
        user_id=request.user_id,
        url=request.url,
        content=request.content,
        channel=request.channel,
        user_role=user_role,
        emotion=request.emotion,
        chat_risk_level=request.chat_risk_level,
        chat_risk_score=request.chat_risk_score,
    )
    return ReportResponse.model_validate(result)


@app.get("/knowledge/scams")
def list_scams() -> list[dict[str, object]]:
    return knowledge_base.scams


@app.get("/knowledge/laws")
def list_laws() -> list[dict[str, object]]:
    return knowledge_base.laws


@app.get("/knowledge/playbooks")
def list_response_playbooks() -> list[dict[str, object]]:
    return knowledge_base.response_playbooks


@app.get("/knowledge/faqs")
def list_faqs() -> list[dict[str, object]]:
    return knowledge_base.faqs


@app.get("/knowledge/quality")
def knowledge_quality() -> dict[str, object]:
    return knowledge_base.quality_report()


@app.post("/knowledge/scams")
def add_scam(
    entry: ScamEntryCreate,
    x_admin_token: str | None = Header(default=None),
) -> dict[str, str]:
    _require_admin(x_admin_token)

    try:
        knowledge_base.add_scam(entry.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"message": "新增骗局已接入知识库", "type": entry.type}


@app.get("/scenarios", response_model=list[ScenarioSummary])
def list_scenarios() -> list[ScenarioSummary]:
    return [ScenarioSummary.model_validate(item) for item in scenario_service.list_scenarios()]


@app.post("/scenarios/start", response_model=ScenarioStartResponse)
def start_scenario(
    request: ScenarioStartRequest,
    authorization: str | None = Header(default=None),
) -> ScenarioStartResponse:
    _resolve_user(request.user_id, authorization)
    try:
        data = scenario_service.start(user_id=request.user_id, scenario_id=request.scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ScenarioStartResponse.model_validate(data)


@app.post("/scenarios/answer", response_model=ScenarioAnswerResponse)
def answer_scenario(
    request: ScenarioAnswerRequest,
    authorization: str | None = Header(default=None),
) -> ScenarioAnswerResponse:
    _resolve_user(request.user_id, authorization)
    try:
        data = scenario_service.answer(user_id=request.user_id, option_index=request.option_index)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ScenarioAnswerResponse.model_validate(data)


@app.get("/users/{user_id}/progress", response_model=UserProgressResponse)
def get_progress(
    user_id: int,
    authorization: str | None = Header(default=None),
) -> UserProgressResponse:
    _resolve_user(user_id, authorization)
    data = gamification_service.profile(user_id)
    return UserProgressResponse.model_validate(data)


def _to_storage_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None

    if value.tzinfo is None:
        normalized = value
    else:
        normalized = value.astimezone(timezone.utc).replace(tzinfo=None)

    return normalized.strftime("%Y-%m-%d %H:%M:%S")


@app.get("/users/{user_id}/reports", response_model=ReportHistoryResponse)
def get_user_reports(
    user_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> ReportHistoryResponse:
    _resolve_user(user_id, authorization)
    normalized_start_at = _to_storage_datetime(start_at)
    normalized_end_at = _to_storage_datetime(end_at)

    if normalized_start_at and normalized_end_at and normalized_start_at > normalized_end_at:
        raise HTTPException(status_code=400, detail="start_at 不能晚于 end_at")

    items = report_service.list_reports(
        user_id=user_id,
        limit=limit,
        start_at=normalized_start_at,
        end_at=normalized_end_at,
    )
    return ReportHistoryResponse.model_validate(
        {
            "user_id": user_id,
            "total": len(items),
            "items": items,
        }
    )


@app.get("/reports/{report_id}", response_model=ReportDetailResponse)
def get_report_detail(
    report_id: str,
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
) -> ReportDetailResponse:
    item = report_service.get_report(report_id)
    if item is None:
        raise HTTPException(status_code=404, detail="举报记录不存在")
    if x_admin_token is not None:
        _require_admin(x_admin_token)
        return ReportDetailResponse.model_validate(item)
    user = _require_authenticated_user(authorization)
    if int(user["id"]) != int(item["user_id"]):
        raise HTTPException(status_code=403, detail="Cannot access another user's report")
    return ReportDetailResponse.model_validate(item)


@app.get("/admin/reports", response_model=AdminReportsResponse)
def get_admin_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    verdict: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    user_id: int | None = Query(default=None, ge=1),
    keyword: str | None = Query(default=None, max_length=120),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    x_admin_token: str | None = Header(default=None),
) -> AdminReportsResponse:
    _require_admin(x_admin_token)
    normalized_start_time = _to_storage_datetime(start_time)
    normalized_end_time = _to_storage_datetime(end_time)
    if normalized_start_time and normalized_end_time and normalized_start_time > normalized_end_time:
        raise HTTPException(status_code=400, detail="start_time 不能晚于 end_time")

    allowed = {
        "status": {"pending", "reviewed", "closed"},
        "risk_level": {"low", "medium", "high", "critical"},
        "verdict": {"safe", "suspicious", "high_risk"},
        "channel": {"web", "miniapp", "mobile"},
    }
    for name, value in (
        ("status", status),
        ("risk_level", risk_level),
        ("verdict", verdict),
        ("channel", channel),
    ):
        if value and value not in allowed[name]:
            raise HTTPException(status_code=400, detail=f"{name} 筛选值无效")

    result = report_service.list_admin_reports(
        page=page,
        page_size=page_size,
        status=status,
        risk_level=risk_level,
        verdict=verdict,
        channel=channel,
        user_id=user_id,
        keyword=keyword,
        start_time=normalized_start_time,
        end_time=normalized_end_time,
    )
    return AdminReportsResponse.model_validate(result)


@app.patch("/reports/{report_id}/status")
def update_report_status(
    report_id: str,
    update: ReportStatusUpdate,
    x_admin_token: str | None = Header(default=None),
) -> dict[str, str]:
    _require_admin(x_admin_token)
    if not storage.update_report_status(report_id, update.status):
        raise HTTPException(status_code=404, detail="举报记录不存在")
    return {"report_id": report_id, "status": update.status}


@app.patch("/admin/reports/{report_id}/review", response_model=ReportDetailResponse)
def review_report(
    report_id: str,
    review: ReportReviewRequest,
    x_admin_token: str | None = Header(default=None),
) -> ReportDetailResponse:
    _require_admin(x_admin_token)
    item = report_service.review_report(
        report_id=report_id,
        status=review.status,
        reviewer=review.reviewer,
        review_note=review.review_note,
        verdict=review.verdict,
        risk_level=review.risk_level,
        score=review.score,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="举报记录不存在")
    return ReportDetailResponse.model_validate(item)


# ── 规则管理与热加载 ──

@app.get("/admin/rules/overview")
def rule_overview(
    x_admin_token: str | None = Header(default=None),
) -> dict[str, object]:
    _require_admin(x_admin_token)
    return rule_management_service.overview()


@app.get("/admin/dashboard/summary")
def admin_dashboard_summary(
    x_admin_token: str | None = Header(default=None),
) -> dict[str, object]:
    _require_admin(x_admin_token)
    return dashboard_service.summary()


@app.get("/admin/rules/history")
def rule_history(
    limit: int = Query(default=30, ge=1, le=100),
    x_admin_token: str | None = Header(default=None),
) -> list[dict[str, object]]:
    _require_admin(x_admin_token)
    return rule_management_service.history(limit=limit)


@app.patch("/admin/rules/{ruleset}/{rule_name}")
def update_rule(
    ruleset: str,
    rule_name: str,
    request: RuleUpdateRequest,
    x_admin_token: str | None = Header(default=None),
) -> dict[str, object]:
    _require_admin(x_admin_token)
    try:
        return rule_management_service.update_rule(
            ruleset,
            rule_name,
            enabled=request.enabled,
            weight=request.weight,
            change_note=request.change_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/admin/rules/text")
def create_text_rule(
    request: TextRuleCreateRequest,
    x_admin_token: str | None = Header(default=None),
) -> dict[str, object]:
    _require_admin(x_admin_token)
    payload = request.model_dump(exclude={"change_note"})
    try:
        return rule_management_service.add_text_rule(payload, request.change_note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/admin/rules/rollback/{version_id}")
def rollback_rules(
    version_id: int,
    request: RuleRollbackRequest,
    x_admin_token: str | None = Header(default=None),
) -> dict[str, object]:
    _require_admin(x_admin_token)
    try:
        return rule_management_service.rollback(version_id, request.change_note)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── 认证路由 ──

@app.post("/auth/register", response_model=LoginResponse)
def register(request: RegisterRequest) -> LoginResponse:
    try:
        result = auth_service.register(
            username=request.username,
            password=request.password,
            role=request.role,
            nickname=request.nickname,
        )
        return LoginResponse.model_validate(result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/auth/login", response_model=LoginResponse)
def login(request: LoginRequest) -> LoginResponse:
    try:
        result = auth_service.login(username=request.username, password=request.password)
        return LoginResponse.model_validate(result)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/auth/me", response_model=UserInfoResponse)
def get_me(authorization: str | None = Header(default=None)) -> UserInfoResponse:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供有效令牌")
    token = authorization.removeprefix("Bearer ")
    user = auth_service.get_current_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="令牌无效或已过期")
    return UserInfoResponse.model_validate({**user, "user_id": user["id"]})


# ── 排行榜 ──

@app.get("/leaderboard", response_model=LeaderboardResponse | None)
def leaderboard(request: Request, top: int | None = Query(default=None, ge=1, le=100)) -> LeaderboardResponse | FileResponse:
    if "top" not in request.query_params:
        return FileResponse(_frontend_index_file())

    items = storage.get_leaderboard(limit=top or 20)
    return LeaderboardResponse(total=len(items), items=items)


# ── AI 对话路由（DeepSeek R1:1.5b）──

@app.post("/ai/chat", response_model=AIChatResponse)
async def ai_chat(request: AIChatRequest) -> AIChatResponse:
    """调用本地 DeepSeek R1 模型进行反诈对话。"""
    start = time.perf_counter()
    try:
        from app.services.ai_service import AIService
        ai = AIService()
        reply = await ai.chat(request.message, request.history)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return AIChatResponse(reply=reply, latency_ms=latency_ms)
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return AIChatResponse(
            reply=f"抱歉，AI 助手暂时无法响应：{exc}。请稍后重试，或使用上方「智能对话研判」功能。",
            latency_ms=latency_ms,
        )


@app.get("/{path:path}", include_in_schema=False)
def spa_fallback(path: str) -> FileResponse:
    first_segment = path.split("/", 1)[0]
    if first_segment in SPA_ROUTES:
        return FileResponse(_frontend_index_file())
    if first_segment in API_PREFIXES:
        raise HTTPException(status_code=404, detail="Not Found")
    raise HTTPException(status_code=404, detail="Not Found")
