from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class UserProfile(BaseModel):
    role: Literal["student", "general"] = "general"
    nickname: str | None = Field(default=None, max_length=32)
    risk_tolerance: Literal["low", "medium", "high"] = "medium"


class ChatRequest(BaseModel):
    user_id: int = Field(ge=1)
    conversation_id: str | None = Field(default=None, max_length=64)
    message: str = Field(min_length=1, max_length=1000)
    channel: Literal["web", "miniapp", "mobile", "voice"] = "web"
    emotion: Literal["positive", "neutral", "negative", "anxious"] | None = None
    user_profile: UserProfile = Field(default_factory=UserProfile)
    context: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    conversation_id: str = ""
    emotion: Literal["positive", "neutral", "negative", "anxious"] = "neutral"
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
    matched_rules: list[dict[str, Any]] = Field(default_factory=list)
    risk_breakdown: dict[str, Any] = Field(default_factory=dict)
    ai_risk_assessment: dict[str, Any] = Field(default_factory=dict)
    risk_decision: str = ""
    risk_dimensions: dict[str, Any] = Field(default_factory=dict)
    current_danger_level: str = "low"
    scam_likelihood_level: str = "low"
    residual_risk_level: str = "low"
    privacy_risk_level: str = "low"
    next_actions: list[str] = Field(default_factory=list)
    session_stage: str = "collecting"
    known_facts: dict[str, bool] = Field(default_factory=dict)
    pending_questions: list[str] = Field(default_factory=list)
    conversation_summary: str = ""
    turn_count: int = 0
    retrieved_knowledge: list[dict[str, Any]] = Field(default_factory=list)
    ruleset_versions: dict[str, str] = Field(default_factory=dict)
    report_prefill: dict[str, Any] | None = None


class ChatResetRequest(BaseModel):
    user_id: int = Field(ge=1)
    conversation_id: str | None = Field(default=None, max_length=64)


class ChatConversationCreateResponse(BaseModel):
    conversation_id: str
    user_id: int
    title: str
    created_at: str
    updated_at: str


class ChatConversationSummary(BaseModel):
    conversation_id: str
    user_id: int
    title: str
    message_count: int
    risk_level: Literal["low", "medium", "high", "critical"] = "low"
    risk_score: int = 0
    preview: str = ""
    created_at: str
    updated_at: str


class ChatConversationListResponse(BaseModel):
    user_id: int
    total: int
    items: list[ChatConversationSummary]


class ChatHistoryItem(BaseModel):
    id: int
    user_id: int
    conversation_id: str = ""
    user_message: str
    assistant_reply: str
    risk_level: Literal["low", "medium", "high", "critical"]
    risk_score: int
    intent: str
    matched_scams: list[str] = Field(default_factory=list)
    session_stage: str
    created_at: str


class ChatHistoryResponse(BaseModel):
    user_id: int
    total: int
    items: list[ChatHistoryItem]


class ChatConversationMessagesResponse(BaseModel):
    user_id: int
    conversation_id: str
    messages: list[ChatHistoryItem]


class ReportRequest(BaseModel):
    user_id: int = Field(ge=1)
    url: str | None = Field(default=None, max_length=2048)
    content: str | None = Field(default=None, max_length=2000)
    channel: Literal["web", "miniapp", "mobile"] = "web"
    user_role: Literal["student", "general"] = "general"
    emotion: Literal["positive", "neutral", "negative", "anxious"] | None = None
    chat_risk_level: Literal["low", "medium", "high", "critical"] | None = None
    chat_risk_score: int | None = Field(default=None, ge=0, le=100)
    chat_context: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_url_or_content(self) -> "ReportRequest":
        if not self.url and not self.content:
            raise ValueError("url 或 content 至少填写一项")
        return self


class ReportResponse(BaseModel):
    report_id: str
    duplicated: bool = False
    channel: Literal["web", "miniapp", "mobile"] = "web"
    risk_level: Literal["low", "medium", "high", "critical"] = "low"
    verdict: Literal["safe", "suspicious", "high_risk"]
    risk_score: int
    score: int | None = None
    reasons: list[str]
    recommendations: list[str]
    matched_keywords: list[str]
    url_flags: list[str]
    matched_rules: list[dict[str, Any]] = Field(default_factory=list)
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
    risk_breakdown: dict[str, Any] = Field(default_factory=dict)
    next_actions: list[str] = Field(default_factory=list)
    status: Literal["pending", "reviewed", "closed"] = "pending"
    ruleset_versions: dict[str, str] = Field(default_factory=dict)


class ReportHistoryItem(BaseModel):
    report_id: str
    user_id: int
    score: int
    risk_score: int | None = None
    risk_level: Literal["low", "medium", "high", "critical"] = "low"
    verdict: Literal["safe", "suspicious", "high_risk"]
    channel: Literal["web", "miniapp", "mobile"] = "web"
    matched_keywords: list[str]
    url_host: str | None = None
    url: str | None = None
    content_summary: str | None = None
    reasons: list[str] = Field(default_factory=list)
    status: Literal["pending", "reviewed", "closed"] = "pending"
    reviewer: str | None = None
    review_note: str | None = None
    reviewed_at: str | None = None
    created_at: str
    updated_at: str | None = None


class ReportHistoryResponse(BaseModel):
    user_id: int
    total: int
    items: list[ReportHistoryItem]


class ReportDetailResponse(ReportHistoryItem):
    content: str | None = None
    normalized_url: str | None = None
    content_hash: str | None = None
    matched_rules: list[dict[str, Any]] = Field(default_factory=list)
    url_flags: list[str] = Field(default_factory=list)
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
    risk_breakdown: dict[str, Any] = Field(default_factory=dict)
    ruleset_versions: dict[str, str] = Field(default_factory=dict)


class AdminReportsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ReportDetailResponse]


class ReportStatusUpdate(BaseModel):
    status: Literal["pending", "reviewed", "closed"]


class ReportReviewRequest(BaseModel):
    status: Literal["reviewed", "closed"] = "reviewed"
    reviewer: str | None = Field(default=None, max_length=64)
    review_note: str | None = Field(default=None, max_length=500)
    verdict: Literal["safe", "suspicious", "high_risk"] | None = None
    risk_level: Literal["low", "medium", "high", "critical"] | None = None
    score: int | None = Field(default=None, ge=0, le=100)

    @field_validator("reviewer", "review_note", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


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
    sources: list[dict[str, str]] = Field(default_factory=list)


class RuleUpdateRequest(BaseModel):
    enabled: bool | None = None
    weight: int | None = Field(default=None, ge=0, le=100)
    change_note: str = Field(min_length=2, max_length=200)


class TextRuleCreateRequest(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    triggers: list[str] = Field(min_length=1, max_length=50)
    weight: int = Field(ge=0, le=100)
    reason: str = Field(min_length=2, max_length=120)
    rationale: str = Field(min_length=2, max_length=300)
    version: str = Field(default="1.0", min_length=1, max_length=24)
    enabled: bool = True
    change_note: str = Field(min_length=2, max_length=200)

    @model_validator(mode="after")
    def normalize_triggers(self) -> "TextRuleCreateRequest":
        cleaned = list(dict.fromkeys(item.strip() for item in self.triggers if item.strip()))
        if not cleaned:
            raise ValueError("至少需要一个有效触发词")
        self.triggers = cleaned
        return self


class RuleRollbackRequest(BaseModel):
    change_note: str = Field(min_length=2, max_length=200)


class ScenarioSummary(BaseModel):
    id: str
    title: str
    scam_type: str
    mode: str = "quiz"
    story: str | None = None
    objectives: list[str] = Field(default_factory=list)
    max_score: int = Field(ge=0)
    completion_bonus: int = Field(ge=0)


class ScenarioStartRequest(BaseModel):
    user_id: int = Field(ge=1)
    scenario_id: str = Field(min_length=1, max_length=16)


class ScenarioStartResponse(BaseModel):
    scenario_id: str
    title: str
    step_index: int
    prompt: str
    options: list[str]
    mode: str = "quiz"
    story: str | None = None
    role: str | None = None
    characters: list[dict[str, Any]] = Field(default_factory=list)
    clues: list[dict[str, Any]] = Field(default_factory=list)
    objectives: list[str] = Field(default_factory=list)
    total_steps: int = Field(ge=1)
    max_score: int = Field(ge=0)
    previous_best: int = Field(ge=0)
    attempts: int = Field(ge=0)
    completed: bool = False


class ScenarioAnswerRequest(BaseModel):
    user_id: int = Field(ge=1)
    option_index: int = Field(ge=0)


class ScenarioAnswerResponse(BaseModel):
    scenario_id: str
    step_index: int
    finished: bool
    feedback: str
    points_gained: int
    total_points: int
    badges: list[str]
    new_badges: list[str] = Field(default_factory=list)
    next_prompt: str | None
    next_options: list[str]
    case_summary: str | None = None
    debrief: list[str] = Field(default_factory=list)
    total_steps: int = Field(ge=1)
    run_score: int = Field(ge=0)
    max_score: int = Field(ge=0)
    score_percent: int = Field(ge=0, le=100)
    best_score: int = Field(ge=0)
    first_clear: bool = False
    score_improvement: int = Field(ge=0)
    attempts: int = Field(ge=0)
    completions: int = Field(ge=0)


class ScenarioProgressItem(BaseModel):
    scenario_id: str
    attempts: int = Field(ge=0)
    completions: int = Field(ge=0)
    best_score: int = Field(ge=0)
    max_score: int = Field(ge=0)
    best_percent: int = Field(ge=0, le=100)
    points_earned: int = Field(ge=0)
    first_completed_at: str | None = None
    last_completed_at: str | None = None


class UserProgressResponse(BaseModel):
    user_id: int
    level: int
    points: int
    badges: list[str]
    reports_submitted: int
    scenarios_completed: int
    high_risk_blocks: int
    scenario_progress: list[ScenarioProgressItem] = Field(default_factory=list)


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
