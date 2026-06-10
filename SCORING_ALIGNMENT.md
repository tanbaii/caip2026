# 评分点映射表（方向三：面向反诈教育的智能客服）

> 本文档将赛题评分标准逐项映射到系统已实现功能，供答辩准备使用。

---

## 项目定位

面向学生及泛个人用户的反诈教育智能对话系统，融合配置化规则引擎、可选向量检索和游戏化交互，提供诈骗风险研判、实时劝阻、一键举报、情景闯关训练全流程服务。

**技术栈**：FastAPI + Vue 3 + SQLite + Tailwind CSS 4 + Vite

---

## 一、完成度（20 分）

### 1.1 反诈知识库构建（5 分）

| 维度 | 内容 |
|------|------|
| **对应功能** | 结构化反诈知识库，含 9 类骗局（刷单返利、游戏交易、冒充公检法、虚假投资、校园贷、冒充客服退款、冒充熟人、快递理赔、AI深度伪造）和 5 部法律法规 |
| **数据结构** | JSON Schema 化：每条骗局含 `id`、`type`、`name`、`keywords`、`tactics`、`red_flags`、`typical_case`、`prevention`、`legal_refs` |
| **演示入口** | `GET /knowledge/scams` → 返回全部骗局条目；`GET /knowledge/laws` → 返回法律要点 |
| **前端入口** | `/knowledge` 知识库页面，支持关键词搜索过滤 |
| **相关文件** | `app/data/knowledge_base.json`、`app/services/knowledge_base.py`、`frontend/src/pages/KnowledgePage.vue` |
| **可验证证据** | `test_knowledge_base_is_enriched`：验证 ≥8 条骗局、≥5 条法律；`test_knowledge_base_includes_ai_deepfake_scam`：验证 AI 深度伪造条目存在 |
| **扩展能力** | `POST /knowledge/scams`（管理员）可动态新增骗局知识；风险规则修改后需重启服务或重新创建规则引擎实例 |

### 1.2 规则引擎与意图识别（5 分）

| 维度 | 内容 |
|------|------|
| **对应功能** | ① JSON 配置驱动的风险规则引擎（`risk_rules.json`，10 条文本规则 + URL 规则）；② 轻量级意图识别器（5 类意图：知识查询、求助、举报、闯关、AI诈骗识别） |
| **规则配置** | 每条规则含 `name`、`triggers`（关键词列表）、`weight`（权重）、`reason`（原因）；URL 规则含 `shortener_domains`、`risky_tlds`、7 类结构检查 |
| **演示入口** | `/chat` 接口返回 `matched_rules`（命中规则详情）、`risk_breakdown`（分数拆解） |
| **相关文件** | `app/data/risk_rules.json`、`app/data/url_rules.json`、`app/services/risk_engine.py`、`app/services/intent_recognizer.py` |
| **可验证证据** | `test_risk_rules_loaded_from_json_config`：规则从 JSON 加载；`test_json_config_drives_scoring`：修改权重后评分变化；`test_text_authority_pressure_still_high_risk`：公检法+验证码→高风险；`test_intent_recognizer_detects_ai_fraud`：AI 诈骗意图识别 |
| **配置化证据** | 新增骗局规则只需编辑 JSON，无需改 Python 代码 |

### 1.3 风险劝阻与举报功能（5 分）

| 维度 | 内容 |
|------|------|
| **风险研判** | `/chat` 接口：输入对话文本 → 输出风险等级（low/medium/high/critical）、风险分、命中规则、劝阻话术、防护建议、下一步动作 |
| **URL 分析** | `/report` 接口：输入 URL + 文本 → 输出判定结果（safe/suspicious/high_risk）、URL 特征标记、关键词命中、风险分拆解（URL 分 + 文本分） |
| **劝阻话术** | 4 级劝阻话术（低/中/高/极高），学生场景追加辅导员联系建议 |
| **可解释输出** | `matched_rules`：命中规则名 + 证据 + 权重 + 原因；`risk_breakdown`：各维度分数（含 `conversation_score`）；`next_actions`：建议处置动作；`known_facts`：已识别事实；`pending_questions`：待确认问题 |
| **多轮上下文追问** | 系统支持状态机式多轮对话：自动抽取事实、跨轮累积、组合升级风险，支持 collecting/assessing/warning/debriefing 四阶段切换 |
| **演示入口** | `POST /chat`：输入"有人冒充公检法让我转账到安全账户"；`POST /report`：提交可疑 URL |
| **前端入口** | `/chat` 聊天页右侧面板、`/report` 举报页分析结果区 |
| **相关文件** | `app/services/risk_engine.py`、`app/services/dialogue_service.py`、`app/services/report_service.py`、`frontend/src/components/risk/RiskPanel.vue`、`frontend/src/components/report/ReportResult.vue` |
| **可验证证据** | `test_chat_high_risk_warning`：高危话术→高风险；`test_report_suspicious_url`：punycode URL→可疑；`test_chat_high_risk_shows_matched_rules`：命中规则详情完整；`test_report_url_risk_breakdown`：URL/文本分数拆分正确 |

### 1.4 游戏化交互与泛终端适配（5 分）

| 维度 | 内容 |
|------|------|
| **情景闯关** | 9 个剧本化情景推理关卡（C001-C009），含案件背景、角色扮演、线索收集、目标引导、案件复盘和反诈知识点；其中 C008（AI换脸借钱）和 C009（奖学金冒充通知）为完整剧本杀式推理模式 |
| **积分体系** | 聊天研判、举报提交、闯关完成均可获得积分，积分实时累计 |
| **勋章系统** | 达成条件自动授予勋章，展示在排行榜和个人主页 |
| **排行榜** | `/leaderboard` 全局排行，展示用户昵称、积分、等级、勋章 |
| **泛终端适配** | Vue 3 + Tailwind CSS 4 响应式布局，适配桌面端和移动端；FastAPI 后端 RESTful API 适配网页/小程序/移动端接入 |
| **演示入口** | `/game` 闯关页、`/leaderboard` 排行榜、`/profile` 个人主页 |
| **相关文件** | `app/services/scenario_service.py`、`app/data/scenarios.json`、`app/services/gamification.py`、`frontend/src/pages/GamePage.vue`、`frontend/src/pages/LeaderboardPage.vue` |
| **可验证证据** | `test_scenario_flow`：闯关流程完整；`test_scenarios_return_at_least_9`：9 个关卡；`test_c008_start_returns_story_role_objectives_clues`：剧本杀字段完整；`test_c008_finish_returns_case_summary_and_debrief`：复盘和知识点返回；`test_leaderboard_returns_data`：排行榜有数据 |

---

## 二、创新性（20 分）

| 创新点 | 说明 |
|--------|------|
| **剧本杀式反诈推理训练** | C008/C009 采用完整剧本杀模式：案件背景→角色扮演→线索卡片→分步推理→案件复盘→反诈知识点，用户不是简单答题，而是在剧情中收集线索、识别诈骗话术、做出处置决策 |
| **JSON 配置驱动规则引擎** | 风险规则、URL 规则均从 JSON 文件加载；内置默认规则兜底，配置缺失不崩溃；当前规则在服务启动时加载 |
| **AI 深度伪造诈骗识别** | 新增 AI 换脸、语音克隆、数字人等 18 个触发词，覆盖 2025-2026 年新型 AI 诈骗手法 |
| **全链路可解释输出** | 每次研判返回命中规则详情（规则名、证据、权重、原因）、风险分拆解（文本/URL/知识库/用户画像/情绪/多轮对话维度）、建议下一步动作，无黑盒 LLM 参与风险判定 |
| **状态机式多轮反诈对话** | 基于内存状态机的多轮追问系统：自动从用户消息中抽取 11 类事实（转账、验证码、URL、远程控制、保密施压、限时催促、已转账、公检法、投资、奖金补贴、AI 伪造），按 collecting→assessing→warning→debriefing 四阶段推进，已知事实跨轮累积，组合事实触发风险升级（如转账+验证码→高危、公检法+已转账→极高危），warning 阶段自动停止追问并输出止损动作 |
| **情绪感知研判** | 支持传入用户情绪状态（anxious/negative/positive/neutral），情绪信号影响风险评分 |
| **学生群体适配** | 用户角色区分 student/general，学生场景（校园/学费/奖学金/兼职）触发额外风险加分，高危时追加辅导员联系建议 |
| **知识库快速接入** | 管理员通过 `POST /knowledge/scams` 动态新增骗局类型，系统自动纳入后续研判 |
| **本地 AI 助手降级** | `/ai/chat` 调用本地 Ollama（deepseek-r1:1.5b），Ollama 未运行时返回降级提示，不影响核心功能 |
| **演示入口** | `/chat` 输入 AI 换脸话术 → 查看 `matched_rules` 中 `ai_deepfake` 规则详情；修改 `risk_rules.json` 权重 → 重新请求验证评分变化 |
| **相关文件** | `app/services/risk_engine.py`（`_load_json` + fallback）、`app/data/risk_rules.json`、`app/data/url_rules.json` |

---

## 三、实用性（20 分）

| 维度 | 说明 |
|------|------|
| **真实场景覆盖** | 覆盖刷单返利、冒充公检法、虚假投资、校园贷、冒充客服退款、冒充熟人、快递理赔、游戏交易、AI 深度伪造 9 类高频骗局 |
| **URL 风险检测** | 7 类 URL 结构检查：协议缺失、IP 直连、@ 符号跳转伪装、punycode 域名、短链域名、高风险后缀、HTTP 明文 |
| **关键词黑名单** | 举报服务内置 20+ 诈骗关键词，覆盖传统话术和新型 AI 诈骗术语 |
| **一键举报** | `/report` 接口支持 URL + 文本同时提交，返回判定结果、风险分、命中关键词、处置建议 |
| **历史记录** | `/users/{id}/reports` 查询举报历史，管理员可更新待复核/已复核/已关闭状态；仅保存 URL 主机、脱敏内容摘要与原因，不保存完整敏感内容 |
| **轻量部署** | 单进程 FastAPI + SQLite，无需 Redis/Kafka/数据库服务，`pip install` + `uvicorn` 即可启动 |
| **前端完整** | Vue 3 SPA 含登录/注册、聊天、举报、闯关、知识库、排行榜、个人主页 7 个功能页面 |
| **演示入口** | 完整走通：注册 → 聊天研判 → 举报 → 闯关 → 查看积分 → 查看排行榜 |
| **相关文件** | `app/services/storage.py`、`app/services/report_service.py`、`app/main.py`（所有 API 路由）、`frontend/src/pages/*.vue` |

---

## 四、成熟度（20 分）

| 维度 | 说明 |
|------|------|
| **测试覆盖** | 86 个自动化测试（`pytest -q`），覆盖：API 端点、风险引擎、URL 检测、知识库、认证与越权防护、举报复核、排行榜、意图识别、JSON 配置加载、可解释输出、敏感信息脱敏、多轮对话与重置 |
| **测试隔离** | 每个测试使用独立临时数据库（`conftest.py`），测试间零状态污染 |
| **代码规范** | Pydantic v2 Schema 校验所有入参和出参；类型注解全覆盖；模块化服务架构（RiskEngine、DialogueService、ReportService 独立可测） |
| **配置管理** | 风险规则 JSON 配置化；数据库路径、JWT 密钥、管理员令牌、CORS 来源、限流参数均通过环境变量配置 |
| **错误降级** | 配置文件缺失时回退内置默认规则；Ollama 未运行时返回降级提示；API 返回统一错误格式 |
| **文档完整** | README（部署指南 + 烟雾测试）、SECURITY_DESIGN.md（安全设计）、USAGE_GUIDE.md（交互手册）、SCORING_ALIGNMENT.md（评分映射）、DEMO_SCRIPT.md（答辩脚本） |
| **前端构建** | `npm run build` 通过，Vite 生产构建，CSS 7.96 KB + JS 56.15 KB（gzip） |
| **可验证证据** | `pytest -q` → 86 passed；`npm run build` → 生产构建通过 |

---

## 五、安全性（20 分）

| 维度 | 说明 |
|------|------|
| **数据脱敏** | `app/services/sanitizer.py`：手机号（`138****5678`）、身份证号（`1101***********1234`）、银行卡号（`6222*******7890`）、验证码（`******`）、邮箱（`u***@example.com`）、Token（`[TOKEN_REDACTED]`）；聊天历史写入前自动脱敏 |
| **密码安全** | PBKDF2-HMAC-SHA256 + 每用户随机盐 + 210,000 次迭代，兼容旧 SHA-256 账户登录后迁移 |
| **JWT 认证** | HS256 签名 + 24 小时过期 + 签名验证 |
| **CORS 配置** | 不再 `allow_origins=["*"]`，通过 `CORS_ORIGINS` 环境变量配置允许来源，默认仅允许 localhost |
| **管理员权限** | `POST /knowledge/scams` 需 `x-admin-token` 请求头，令牌从 `ANTI_FRAUD_ADMIN_TOKEN` 环境变量读取 |
| **SQL 注入防护** | 全部数据库操作使用参数化查询（`?` 占位符），无字符串拼接 |
| **限流机制** | 可选内存级限流（`RATE_LIMIT_RPM` 环境变量），超限返回 429 |
| **LLM 安全边界** | 风险判定由规则引擎完成，不依赖 LLM；`/ai/chat` 输出不参与风险评分；LLM 不可用时降级处理 |
| **可验证证据** | `test_sanitizer_masks_phone_number`、`test_sanitizer_masks_id_card`、`test_sanitize_preserves_risk_keywords` 等 10 个脱敏测试；`test_add_scam_requires_admin_token`：管理员令牌校验 |
| **设计文档** | `SECURITY_DESIGN.md`：脱敏策略、认证鉴权、管理员权限、文件上传预案、LLM 安全边界、日志审计、用途边界声明 |

---

## 六、团队表现（10 分，加分项）

| 维度 | 准备要点 |
|------|---------|
| **答辩逻辑** | 按 `DEMO_SCRIPT.md` 流程演示：登录 → 高危话术研判 → 可疑 URL 举报 → 情景闯关 → 积分勋章 → 管理员新增知识 |
| **技术深度** | 展示 JSON 配置驱动、可解释输出、脱敏机制的代码实现 |
| **问题应答** | 准备常见问题：规则扩展方式、与 LLM 的关系、脱敏不影响识别的实现、移动端适配方案 |

---

## 快速验证命令

```bash
# 后端测试
pytest -q                           # 86 passed

# 前端构建
cd frontend && npm run build        # built in ~30s

# 启动服务
uvicorn app.main:app --port 8000

# 烟雾测试
curl http://127.0.0.1:8000/health   # {"status":"ok"}
```
