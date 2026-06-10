from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.models.schemas import (
    AIChatRequest,
    AIChatResponse,
    ChatRequest,
    ChatResponse,
    LeaderboardResponse,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    ReportRequest,
    ReportResponse,
    ReportHistoryResponse,
    ScamEntryCreate,
    ScenarioAnswerRequest,
    ScenarioAnswerResponse,
    ScenarioStartRequest,
    ScenarioStartResponse,
    ScenarioSummary,
    UserInfoResponse,
    UserProgressResponse,
)
from app.services.auth_service import AuthService
from app.services.chat_workflow import ChatWorkflowRunner
from app.services.dialogue_service import DialogueService
from app.services.env_loader import load_dotenv
from app.services.gamification import GamificationService
from app.services.intent_recognizer import IntentRecognizer
from app.services.knowledge_base import KnowledgeBase
from app.services.knowledge_retriever import KnowledgeRetriever
from app.services.report_service import ReportService
from app.services.rag_reply_service import RagReplyGenerator
from app.services.risk_engine import RiskEngine
from app.services.scenario_service import ScenarioService
from app.services.storage import SQLiteStorage

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
load_dotenv(PROJECT_ROOT / ".env")
FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"
FRONTEND_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"
LEGACY_WEB_DIR = BASE_DIR / "web"
SPA_ROUTES = {"login", "chat", "report", "game", "knowledge", "leaderboard", "profile"}
API_PREFIXES = {"health", "auth", "chat", "ai", "report", "scenarios", "users", "leaderboard", "knowledge"}
ADMIN_TOKEN = os.getenv("ANTI_FRAUD_ADMIN_TOKEN", "change-me")
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

knowledge_base = KnowledgeBase(BASE_DIR / "data" / "knowledge_base.json")
intent_recognizer = IntentRecognizer()
risk_engine = RiskEngine()
_db_path = os.getenv("DB_PATH") or str(BASE_DIR / "data" / "anti_fraud.db")
storage = SQLiteStorage(Path(_db_path))
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
    if os.getenv("RAG_RETRIEVAL_ENABLED", "1").lower() not in {"0", "false", "no"}
    else None
)
rag_reply_generator = (
    RagReplyGenerator()
    if (
        os.getenv("RAG_LLM_ENABLED", "0").lower() in {"1", "true", "yes"}
        or os.getenv("CHAT_LLM_ENABLED", "0").lower() in {"1", "true", "yes"}
    )
    else None
)
dialogue_service = DialogueService(
    knowledge_base=knowledge_base,
    intent_recognizer=intent_recognizer,
    risk_engine=risk_engine,
    gamification=gamification_service,
    knowledge_retriever=knowledge_retriever,
    rag_reply_generator=rag_reply_generator,
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
@app.get("/chat", include_in_schema=False)
@app.get("/report", include_in_schema=False)
@app.get("/game", include_in_schema=False)
@app.get("/knowledge", include_in_schema=False)
@app.get("/profile", include_in_schema=False)
def vue_page() -> FileResponse:
    return FileResponse(_frontend_index_file())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "anti-fraud-dialogue"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return ChatResponse.model_validate(dialogue_service.process_chat(request))


@app.post("/report", response_model=ReportResponse)
def report(request: ReportRequest) -> ReportResponse:
    result = report_service.analyze(
        user_id=request.user_id,
        url=request.url,
        content=request.content,
    )
    return ReportResponse.model_validate(result)


@app.get("/knowledge/scams")
def list_scams() -> list[dict[str, object]]:
    return knowledge_base.scams


@app.get("/knowledge/laws")
def list_laws() -> list[dict[str, object]]:
    return knowledge_base.laws


@app.post("/knowledge/scams")
def add_scam(
    entry: ScamEntryCreate,
    x_admin_token: str | None = Header(default=None),
) -> dict[str, str]:
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="管理员令牌错误")

    try:
        knowledge_base.add_scam(entry.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"message": "新增骗局已接入知识库", "type": entry.type}


@app.get("/scenarios", response_model=list[ScenarioSummary])
def list_scenarios() -> list[ScenarioSummary]:
    return [ScenarioSummary.model_validate(item) for item in scenario_service.list_scenarios()]


@app.post("/scenarios/start", response_model=ScenarioStartResponse)
def start_scenario(request: ScenarioStartRequest) -> ScenarioStartResponse:
    try:
        data = scenario_service.start(user_id=request.user_id, scenario_id=request.scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ScenarioStartResponse.model_validate(data)


@app.post("/scenarios/answer", response_model=ScenarioAnswerResponse)
def answer_scenario(request: ScenarioAnswerRequest) -> ScenarioAnswerResponse:
    try:
        data = scenario_service.answer(user_id=request.user_id, option_index=request.option_index)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ScenarioAnswerResponse.model_validate(data)


@app.get("/users/{user_id}/progress", response_model=UserProgressResponse)
def get_progress(user_id: int) -> UserProgressResponse:
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
) -> ReportHistoryResponse:
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
