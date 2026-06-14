# 反诈护盾实验室 — 接口文档

- 框架: FastAPI, 所有路由定义在 `app/main.py`
- 自动文档: `/docs` (Swagger UI), `/redoc` (ReDoc), `/openapi.json`
- 数据模型: `app/models/schemas.py` (Pydantic BaseModel)
- CORS: `allow_origins=["*"]`

---

## 接口总览

| # | 方法 | 路径 | 后端函数 (main.py) | 前端调用 | 鉴权 |
|---|------|------|---------------------|----------|------|
| 1 | GET | `/health` | `health()` :92 | app.js:676 | 无 |
| 2 | POST | `/chat` | `chat()` | Vue chat API | Bearer Token |
| 3 | POST | `/chat/reset` | `reset_chat()` | Vue chat API | Bearer Token |
| 4 | POST | `/report` | `report()` | Vue report API | Bearer Token |
| 4 | GET | `/knowledge/scams` | `list_scams()` :112 | app.js:630 | 无 |
| 5 | GET | `/knowledge/laws` | `list_laws()` :117 | app.js:631 | 无 |
| 6 | POST | `/knowledge/scams` | `add_scam()` :122 | 无 (管理员) | x-admin-token |
| 7 | GET | `/scenarios` | `list_scenarios()` :138 | app.js:775 | 无 |
| 8 | POST | `/scenarios/start` | `start_scenario()` | Vue scenario API | Bearer Token |
| 9 | POST | `/scenarios/answer` | `answer_scenario()` | Vue scenario API | Bearer Token |
| 10 | GET | `/users/{user_id}/progress` | `get_progress()` :161 | Vue profile/game API | Bearer Token |
| 11 | GET | `/users/{user_id}/reports` | `get_user_reports()` | Vue report API | Bearer Token |
| 12 | PATCH | `/reports/{report_id}/status` | `update_report_status()` | 管理端 | x-admin-token |
| 12 | POST | `/auth/register` | `register()` :209 | app.js:297 | 无 |
| 13 | POST | `/auth/login` | `login()` :223 | app.js:248 | 无 |
| 14 | GET | `/auth/me` | `get_me()` :232 | app.js:127 | Bearer Token |
| 15 | GET | `/leaderboard` | `leaderboard()` :245 | app.js:481 | 无 |
| 16 | POST | `/ai/chat` | `ai_chat()` :253 | app.js:379 | 无 |
| 17 | GET | `/` | `home()` :87 | — (HTML 入口) | 无 |

共 17 个端点 (9 GET / 8 POST)。

---

## 认证接口

### POST /auth/register — 注册

> main.py:209 → `auth_service.register()`

**请求体** `RegisterRequest` (schemas.py:134)

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| username | str | 是 | 3-32 字符 | 用户名 |
| password | str | 是 | 6-128 字符 | 密码 |
| role | str | 否 | "student" / "general", 默认 "general" | 角色 |
| nickname | str / null | 否 | max 32 字符 | 昵称 |

请求示例:
```json
{
  "username": "demo_user",
  "password": "demo123456",
  "role": "student",
  "nickname": "演示用户"
}
```

**响应** `LoginResponse` (schemas.py:146)

| 字段 | 类型 | 说明 |
|------|------|------|
| access_token | str | JWT 令牌 |
| token_type | str | 固定 "bearer" |
| user_id | int | 用户 ID |
| username | str | 用户名 |
| role | str | 角色 |
| nickname | str / null | 昵称 |

错误: 400 用户名已存在

---

### POST /auth/login — 登录

> main.py:223 → `auth_service.login()`

**请求体** `LoginRequest` (schemas.py:141)

| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| username | str | 是 | 1-32 字符 |
| password | str | 是 | 1-128 字符 |

请求示例:
```json
{
  "username": "demo_user",
  "password": "demo123456"
}
```

**响应**: 同 `LoginResponse` (见上)

错误: 401 用户名或密码错误

---

### GET /auth/me — 当前用户信息

> main.py:232 → `auth_service.get_current_user(token)`

**请求头**: `Authorization: Bearer <token>`

**响应** `UserInfoResponse` (schemas.py:155)

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | int | 用户 ID |
| username | str | 用户名 |
| role | str | 角色 |
| nickname | str / null | 昵称 |
| created_at | str | 注册时间 |

错误: 401 未提供有效令牌 / 令牌无效或已过期

> **已知问题**: USAGE_GUIDE 标注此接口存在 `id` vs `user_id` 字段映射不一致。

---

## 对话与研判接口

### POST /chat — 智能对话研判

> main.py:97 → `dialogue_service.process_chat()`

**请求体** `ChatRequest` (schemas.py:14)

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| user_id | int | 是 | | 用户 ID |
| message | str | 是 | 1-1000 字符 | 对话文本 |
| channel | str | 否 | "web"/"miniapp"/"mobile"/"voice", 默认 "web" | 渠道 |
| emotion | str / null | 否 | "positive"/"neutral"/"negative"/"anxious" | 情绪 |
| user_profile | object | 否 | 默认 `{role:"general", risk_tolerance:"medium"}` | 用户画像 |
| context | dict | 否 | 默认 `{}` | 扩展上下文 |

`user_profile` 子字段:
| 字段 | 类型 | 默认值 |
|------|------|--------|
| role | "student" / "general" | "general" |
| nickname | str / null | null |
| risk_tolerance | "low" / "medium" / "high" | "medium" |

请求示例:
```json
{
  "user_id": 1,
  "message": "有人让我转到安全账户并提供验证码",
  "channel": "web",
  "emotion": "anxious",
  "user_profile": {
    "role": "student",
    "risk_tolerance": "low"
  }
}
```

**响应** `ChatResponse` (schemas.py:23)

| 字段 | 类型 | 说明 |
|------|------|------|
| reply | str | 回复文本 |
| intent | str | 识别意图 |
| matched_scams | list[str] | 匹配的骗局类型 |
| risk_level | "low"/"medium"/"high"/"critical" | 风险等级 |
| risk_score | int | 风险分 |
| intervention_script | list[str] | 劝阻话术 |
| recommendations | list[str] | 建议 |
| points_gained | int | 本次获得积分 |
| total_points | int | 总积分 |
| badges | list[str] | 勋章列表 |
| latency_ms | float | 处理延迟 (ms) |
| matched_rules | list[object] | 命中规则，含证据、权重、规则版本、规则集版本与判定依据 |
| risk_breakdown | object | 文本、URL、知识库、画像、情绪、多轮对话等分数拆解 |
| ruleset_versions | object | 实际加载的文本规则集与 URL 规则集版本 |

---

### POST /ai/chat — AI 助手 (DeepSeek R1)

> main.py:253 → `ai_service.chat()` (异步, 调用本地 Ollama)

**请求体** `AIChatRequest` (schemas.py:188)

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| message | str | 是 | 1-2000 字符 | 用户消息 |
| history | list | 否 | 默认 `[]` | 对话历史 |

`history` 元素 (`AIChatMessage`, schemas.py:183):
| 字段 | 类型 | 说明 |
|------|------|------|
| role | "user" / "assistant" | 角色 |
| content | str | 消息内容 |

请求示例:
```json
{
  "message": "AI换脸诈骗怎么识别？",
  "history": []
}
```

**响应** `AIChatResponse` (schemas.py:192)

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| reply | str | | AI 回复 |
| model | str | "deepseek-r1:1.5b" | 模型名称 |
| latency_ms | float | 0.0 | 延迟 (ms) |

> 若 Ollama 未启动, 返回降级提示而非错误码。

---

## 举报接口

### POST /report — 举报初判

> main.py:102 → `report_service.analyze()`

**请求体** `ReportRequest` (schemas.py:37)

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| user_id | int | 是 | | 用户 ID |
| url | str / null | 二者至少填一 | max 2048 | 可疑链接 |
| content | str / null | 二者至少填一 | max 2000 | 可疑文本内容 |
| channel | str | 否 | "web"/"miniapp"/"mobile", 默认 "web" | 渠道 |

请求示例:
```json
{
  "user_id": 1,
  "url": "http://xn--secure-bank-5k9f.top/login@notice",
  "content": "点击领取返利，先转账再提现",
  "channel": "web"
}
```

**响应** `ReportResponse` (schemas.py:50)

| 字段 | 类型 | 说明 |
|------|------|------|
| report_id | str | 举报 ID |
| verdict | "safe"/"suspicious"/"high_risk" | 判定结果 |
| risk_score | int | 风险分 |
| reasons | list[str] | 判定理由 |
| recommendations | list[str] | 建议 |
| matched_keywords | list[str] | 命中关键词 |
| url_flags | list[str] | URL 风险标记 |
| matched_rules | list[object] | 命中规则及 `rule_version`、`ruleset_version`、`rationale` |
| risk_breakdown | object | URL 分、文本分和总分 |
| ruleset_versions | object | 实际加载的文本规则集与 URL 规则集版本 |

判定阈值:
- `score >= 55` → `high_risk`
- `score >= 25` → `suspicious`
- 其余 → `safe`

---

## 情景闯关接口

### GET /scenarios — 关卡列表

> main.py:138 → `scenario_service.list_scenarios()`

**请求参数**: 无

**响应**: `list[ScenarioSummary]` (schemas.py:87)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | 关卡 ID (如 C001) |
| title | str | 关卡标题 |
| scam_type | str | 骗局类型 |
| max_score | int | 关卡最高答题分 |
| completion_bonus | int | 首次通关固定奖励 |

---

### POST /scenarios/start — 开始闯关

> main.py:143 → `scenario_service.start()`

**请求体** `ScenarioStartRequest` (schemas.py:93)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | int | 是 | 用户 ID |
| scenario_id | str | 是 | 关卡 ID (如 "C001") |

请求示例:
```json
{
  "user_id": 1,
  "scenario_id": "C001"
}
```

**响应** `ScenarioStartResponse` (schemas.py:98)

| 字段 | 类型 | 说明 |
|------|------|------|
| scenario_id | str | 关卡 ID |
| title | str | 标题 |
| step_index | int | 当前步骤 |
| prompt | str | 题目文本 |
| options | list[str] | 选项列表 |
| max_score | int | 关卡最高答题分 |
| previous_best | int | 用户历史最佳成绩 |
| attempts | int | 历史挑战次数 |
| completed | bool | 是否已经通关 |

错误: 404 关卡不存在

---

### POST /scenarios/answer — 提交答案

> main.py:152 → `scenario_service.answer()`

**请求体** `ScenarioAnswerRequest` (schemas.py:106)

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| user_id | int | 是 | | 用户 ID |
| option_index | int | 是 | >= 0 | 选项索引 |

请求示例:
```json
{
  "user_id": 1,
  "option_index": 1
}
```

**响应** `ScenarioAnswerResponse` (schemas.py:111)

| 字段 | 类型 | 说明 |
|------|------|------|
| scenario_id | str | 关卡 ID |
| step_index | int | 当前步骤 |
| finished | bool | 是否完成全部步骤 |
| feedback | str | 本题反馈 |
| points_gained | int | 本次积分 |
| total_points | int | 总积分 |
| badges | list[str] | 勋章列表 |
| new_badges | list[str] | 本次新解锁勋章 |
| next_prompt | str / null | 下一题文本 (finished=false 时) |
| next_options | list[str] | 下一题选项 |
| run_score / max_score | int | 本局成绩与关卡满分 |
| score_percent | int | 本局得分百分比 |
| best_score | int | 结算后的历史最佳成绩 |
| first_clear | bool | 是否首次通关 |
| score_improvement | int | 相比历史最佳提升的分数 |
| attempts / completions | int | 挑战与完成次数 |

错误: 400 参数错误 / 无进行中的关卡

---

## 用户与排行接口

### GET /users/{user_id}/progress — 用户进度

> main.py:161 → `gamification_service.profile()`

**路径参数**: `user_id: int`

**响应** `UserProgressResponse` (schemas.py:123)

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | int | 用户 ID |
| level | int | 等级 |
| points | int | 总积分 |
| badges | list[str] | 勋章列表 |
| reports_submitted | int | 举报次数 |
| scenarios_completed | int | 完成关卡数 |
| scenario_progress | list | 每关挑战次数、最佳成绩、累计奖励和完成时间 |

---

### GET /users/{user_id}/reports — 举报历史

> main.py:179 → `report_service.list_reports()`

**路径参数**: `user_id: int`

**Query 参数**:

| 字段 | 类型 | 默认值 | 约束 | 说明 |
|------|------|--------|------|------|
| limit | int | 20 | 1-100 | 每页条数 |
| start_at | datetime / null | null | ISO 格式 | 起始时间 |
| end_at | datetime / null | null | ISO 格式 | 截止时间 |

时间格式示例: `2026-04-01T00:00:00`

请求示例:
```
GET /users/1/reports?limit=10&start_at=2026-04-01T00:00:00&end_at=2026-05-01T00:00:00
```

**响应** `ReportHistoryResponse` (schemas.py:69)

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | int | 用户 ID |
| total | int | 总记录数 |
| items | list | 举报记录列表 |

`items` 元素 (`ReportHistoryItem`, schemas.py:60):

| 字段 | 类型 | 说明 |
|------|------|------|
| report_id | str | 举报 ID |
| user_id | int | 用户 ID |
| score | int | 风险分 |
| verdict | "safe"/"suspicious"/"high_risk" | 判定 |
| matched_keywords | list[str] | 命中关键词 |
| created_at | str | 创建时间 |

错误: 400 start_at 晚于 end_at

---

### GET /leaderboard — 排行榜

> main.py:245 → `storage.get_leaderboard()`

**Query 参数**:

| 字段 | 类型 | 默认值 | 约束 |
|------|------|--------|------|
| top | int | 20 | 1-100 |

**响应** `LeaderboardResponse` (schemas.py:176)

| 字段 | 类型 | 说明 |
|------|------|------|
| total | int | 条目数 |
| items | list | 排行列表 |

`items` 元素 (`LeaderboardEntry`, schemas.py:165):

| 字段 | 类型 | 说明 |
|------|------|------|
| rank | int | 排名 |
| user_id | int | 用户 ID |
| username | str | 用户名 |
| nickname | str / null | 昵称 |
| role | str | 角色 |
| points | int | 积分 |
| level | int | 等级 |
| badges | list[str] | 勋章列表 |

---

## 知识库接口

### GET /knowledge/scams — 骗局知识列表

> main.py:112 → `knowledge_base.scams` (直接返回 JSON)

**请求参数**: 无

**响应**: `list[dict]` — 无 response_model, 结构由 `app/data/knowledge_base.json` 决定。

---

### GET /knowledge/laws — 法律知识列表

> main.py:117 → `knowledge_base.laws`

**请求参数**: 无

**响应**: `list[dict]` — 无 response_model。

---

### POST /knowledge/scams — 新增骗局 (管理员)

> main.py:122 → `knowledge_base.add_scam()`

**请求头**: `x-admin-token: <管理员令牌>` (默认 "change-me", 生产环境通过 `ANTI_FRAUD_ADMIN_TOKEN` 环境变量配置)

**请求体** `ScamEntryCreate` (schemas.py:75)

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| id | str | 是 | 3-16 字符 | 骗局 ID |
| type | str | 是 | 3-32 字符 | 骗局类型 |
| name | str | 是 | 2-32 字符 | 骗局名称 |
| keywords | list[str] | 是 | min 1 项 | 关键词列表 |
| tactics | list[str] | 是 | min 1 项 | 话术列表 |
| red_flags | list[str] | 是 | min 1 项 | 红旗信号 |
| typical_case | str | 是 | 5-300 字符 | 典型案例描述 |
| prevention | list[str] | 是 | min 1 项 | 防范建议 |
| legal_refs | list[str] | 是 | min 1 项 | 法律依据 |

**响应**: `{"message": "新增骗局已接入知识库", "type": "<type>"}`

错误: 401 管理员令牌错误 / 400 数据校验失败

---

## 系统接口

### GET /health — 健康检查

> main.py:92 → 直接返回 dict

**请求参数**: 无

**响应**:
```json
{"status": "ok", "service": "anti-fraud-dialogue"}
```

无 response_model。

---

### GET / — 静态页面入口

> main.py:87 → 返回 `index.html`, `include_in_schema=False`

返回前端 HTML 页面, 不计入 OpenAPI schema。

---

## 附录

### 积分规则

| 动作 | 积分 |
|------|------|
| daily_chat | +2 |
| knowledge_query | +5 |
| report_submit | +12 |
| risk_block | +20 |
| scenario 首次通关 | 本局答题分 + 15 |
| scenario 重复挑战 | 仅奖励超过历史最佳成绩的增量 |

关卡积分在完成全部步骤后统一结算；重复获得相同或更低成绩不会增加积分，避免排行榜刷分。

等级: `level = points // 100 + 1`

### 勋章触发条件

| 勋章 | 条件 |
|------|------|
| 线索侦察员 | 举报 >= 1 |
| 反诈新兵 | 积分 >= 50 |
| 风险守门人 | 积分 >= 150 |
| 情景闯关达人 | 完成关卡 >= 3 |
| 冷静止损王 | 高风险阻断 >= 2 |

### 前后端一致性

前端调用的 15 个接口, 后端全部有对应实现。后端独有的接口:
- `POST /knowledge/scams` — 管理员功能, 前端无入口
- `GET /` — HTML 入口, 浏览器直接访问
