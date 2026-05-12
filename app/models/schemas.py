from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class UserProfile(BaseModel):
    role: Literal["student", "general"] = "general"
    nickname: str | None = Field(default=None, max_length=32)
    risk_tolerance: Literal["low", "medium", "high"] = "medium"


class ChatRequest(BaseModel):
    user_id: int = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=1000)
    channel: Literal["web", "miniapp", "mobile", "voice"] = "web"
    emotion: Literal["positive", "neutral", "negative", "anxious"] | None = None
    user_profile: UserProfile = Field(default_factory=UserProfile)
    context: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    reply: str
    intent: str
    matched_scams: list[str]
    risk_level: Literal["low", "medium", "high", "critical"]
    risk_score: int
    intervention_script: list[str]
    recommendations: list[str]
    points_gained: int
    total_points: int
    badges: list[str]
    latency_ms: float


class ReportRequest(BaseModel):
    user_id: int = Field(min_length=1, max_length=64)
    url: str | None = Field(default=None, max_length=2048)
    content: str | None = Field(default=None, max_length=2000)
    channel: Literal["web", "miniapp", "mobile"] = "web"

    @model_validator(mode="after")
    def require_url_or_content(self) -> "ReportRequest":
        if not self.url and not self.content:
            raise ValueError("url 或 content 至少填写一项")
        return self


class ReportResponse(BaseModel):
    report_id: str
    verdict: Literal["safe", "suspicious", "high_risk"]
    risk_score: int
    reasons: list[str]
    recommendations: list[str]
    matched_keywords: list[str]
    url_flags: list[str]


class ReportHistoryItem(BaseModel):
    report_id: str
    user_id: int
    score: int
    verdict: Literal["safe", "suspicious", "high_risk"]
    matched_keywords: list[str]
    created_at: str


class ReportHistoryResponse(BaseModel):
    user_id: int
    total: int
    items: list[ReportHistoryItem]


class ScamEntryCreate(BaseModel):
    id: str = Field(min_length=3, max_length=16)
    type: str = Field(min_length=3, max_length=32)
    name: str = Field(min_length=2, max_length=32)
    keywords: list[str] = Field(min_length=1)
    tactics: list[str] = Field(min_length=1)
    red_flags: list[str] = Field(min_length=1)
    typical_case: str = Field(min_length=5, max_length=300)
    prevention: list[str] = Field(min_length=1)
    legal_refs: list[str] = Field(min_length=1)


class ScenarioSummary(BaseModel):
    id: str
    title: str
    scam_type: str


class ScenarioStartRequest(BaseModel):
    user_id: int = Field(min_length=1, max_length=64)
    scenario_id: str = Field(min_length=1, max_length=16)


class ScenarioStartResponse(BaseModel):
    scenario_id: str
    title: str
    step_index: int
    prompt: str
    options: list[str]


class ScenarioAnswerRequest(BaseModel):
    user_id: int = Field(min_length=1, max_length=64)
    option_index: int = Field(ge=0)


class ScenarioAnswerResponse(BaseModel):
    scenario_id: str
    step_index: int
    finished: bool
    feedback: str
    points_gained: int
    total_points: int
    badges: list[str]
    next_prompt: str | None
    next_options: list[str]


class UserProgressResponse(BaseModel):
    user_id: int
    level: int
    points: int
    badges: list[str]
    reports_submitted: int
    scenarios_completed: int


# ── 认证相关 ──

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)
    role: Literal["student", "general"] = "general"
    nickname: str | None = Field(default=None, max_length=32)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    role: str
    nickname: str | None


class UserInfoResponse(BaseModel):
    user_id: int
    username: str
    role: str
    nickname: str | None
    created_at: str


# ── 排行榜 ──

class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    username: str
    nickname: str | None
    role: str
    points: int
    level: int
    badges: list[str]


class LeaderboardResponse(BaseModel):
    total: int
    items: list[LeaderboardEntry]


# ── AI 对话 ──

class AIChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AIChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[AIChatMessage] = Field(default_factory=list)


class AIChatResponse(BaseModel):
    reply: str
    model: str = "deepseek-r1:1.5b"
    latency_ms: float = 0.0
