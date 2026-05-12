# 反诈护盾实验室详细使用说明

本文档面向三类人群：

- 学生与普通用户（直接使用系统进行识别与训练）
- 老师/家长（组织训练、复盘与干预）
- 项目维护者（接口调用、配置、排障、扩展知识库）

文档目标是让你完整走通“识别 -> 阻断 -> 复盘 -> 提升”的闭环。

---

## 1. 你会得到什么

系统提供以下能力：

- 智能对话研判：根据话术识别意图、风险等级、劝阻建议
- 可疑链接/内容举报：URL 与文本联合评分，输出处置建议
- 情景闯关：分步题目训练常见诈骗场景
- 反诈知识速览：骗局要点、法律提醒、30 秒自检清单
- 账号体系与排行榜：注册登录、积分、勋章、Top 排名
- 历史复盘与导出：按时间过滤举报历史并导出 CSV/JSON
- 可选 AI 助手：接入本地 Ollama 的 deepseek-r1:1.5b

---

## 2. 快速启动

```bash
cd anti_fraud_system
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

入口：

- 前端主页：http://127.0.0.1:8000/
- API 文档：http://127.0.0.1:8000/docs

---

## 3. 关键约定（非常重要）

### 3.1 用户 ID 类型

当前后端接口按整数处理 `user_id`。请使用登录/注册返回的 `user_id`（例如 `1`、`2`），不要使用字符串（如 `"u_student_1"`）。

### 3.2 鉴权方式

- 注册/登录后返回 `access_token`
- 需要鉴权的接口通过请求头传递：

```text
Authorization: Bearer <token>
```

### 3.3 数据落盘

默认 SQLite 数据库路径：

- `app/data/anti_fraud.db`

存储内容包括：

- 用户信息
- 用户积分与勋章状态
- 举报历史记录

---

## 4. 前端页面使用（逐模块）

### 4.1 登录 / 注册

操作：

1. 打开主页后会先进入认证遮罩层。
2. 在“注册”页创建账号，角色可选 `student` / `general`。
3. 注册成功后会自动登录并进入主界面。

说明：

- 页面会把当前登录用户的数值 `user_id` 自动写入各功能卡片。
- 退出登录会清理本地 token。

### 4.2 AI 反诈助手（可选增强）

入口：页面顶部“AI 反诈助手（DeepSeek R1）”。

使用方式：

1. 输入自然语言问题。
2. 系统调用 `/ai/chat`。
3. 显示 AI 回复与思考状态。

适合问题：

- “AI 换脸诈骗怎么识别？”
- “冒充公检法电话应该怎么处理？”

若本地 Ollama 未启动，会收到降级提示，不影响其余模块。

### 4.3 智能对话研判

输入：

- 用户角色（student/general）
- 风险容忍度（low/medium/high）
- 情绪（positive/neutral/negative/anxious）
- 对话文本

输出：

- 意图（intent）
- 风险等级（low/medium/high/critical）
- 风险分（risk_score）
- 劝阻话术、建议
- 积分与勋章变更

推荐做法：

- 先输入原始聊天话术，不要过度概括
- 包含链接时一并贴入，可触发 URL 风险加分

### 4.4 可疑链接/内容举报

输入：

- URL（可选）
- 文本内容（可选）
- 两者至少填一个

输出：

- `report_id`
- 判定：`safe` / `suspicious` / `high_risk`
- 风险分、命中关键词、URL 风险标记、建议

典型动作：

- 举报后立即去“我的积分与勋章”查看累计变化
- 对 `high_risk` 结果保留证据并及时线下处置

### 4.5 典型骗局情景闯关

流程：

1. 点击“刷新关卡”加载列表。
2. 选择关卡（如 `C001`~`C007`）并点击“开始闯关”。
3. 每一步选择一个 `option_index`。
4. 完成后获得步骤积分 + 完成奖励。

建议：

- 每周至少完成 2 个关卡
- 对错误选项的反馈进行复盘

### 4.6 积分排行榜

显示字段：

- 排名
- 用户昵称/用户名
- 角色
- 等级
- 积分
- 勋章

可用于班级/小组激励。

### 4.7 我的积分与勋章

功能：

- 查询当前等级、积分、勋章
- 查询历史举报
- 按时间范围筛选（`start_at` / `end_at`）
- 导出 CSV / JSON

适用场景：

- 老师按周导出班级干预记录
- 家长按月观察风险行为变化

### 4.8 反诈知识速览与训练建议

功能：

- 查看高频骗局摘要
- 查看法律要点
- 查看 30 秒风险自检清单
- 随机推荐闯关关卡

适合课前 1~2 分钟快速预热。

---

## 5. API 使用说明

### 5.1 认证相关

#### 注册 `POST /auth/register`

请求示例：

```json
{
  "username": "demo_user",
  "password": "demo123456",
  "role": "student",
  "nickname": "演示用户"
}
```

响应关键字段：

- `access_token`
- `user_id`（整数）
- `username`
- `role`

#### 登录 `POST /auth/login`

```json
{
  "username": "demo_user",
  "password": "demo123456"
}
```

#### 当前用户 `GET /auth/me`

需要 `Authorization: Bearer <token>`。

注：当前版本该接口存在字段映射问题（见“常见问题”）。

### 5.2 对话研判 `POST /chat`

请求示例：

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

响应包含：

- `reply`
- `intent`
- `matched_scams`
- `risk_level`
- `risk_score`
- `intervention_script`
- `recommendations`
- `points_gained`
- `total_points`
- `badges`
- `latency_ms`

### 5.3 举报初判 `POST /report`

请求示例：

```json
{
  "user_id": 1,
  "url": "http://xn--secure-bank-5k9f.top/login@notice",
  "content": "点击领取返利，先转账再提现",
  "channel": "web"
}
```

判定阈值：

- `score >= 55` -> `high_risk`
- `score >= 25` -> `suspicious`
- 其余 -> `safe`

### 5.4 情景闯关

- 列表：`GET /scenarios`
- 开始：`POST /scenarios/start`
- 作答：`POST /scenarios/answer`

开始示例：

```json
{
  "user_id": 1,
  "scenario_id": "C001"
}
```

作答示例：

```json
{
  "user_id": 1,
  "option_index": 1
}
```

### 5.5 用户进度与历史

- 进度：`GET /users/{user_id}/progress`
- 举报历史：`GET /users/{user_id}/reports?limit=20&start_at=...&end_at=...`

时间参数使用 ISO 格式，例如：

- `2026-04-01T00:00:00`

若 `start_at > end_at`，返回 400。

### 5.6 排行榜与健康检查

- 健康检查：`GET /health`
- 排行榜：`GET /leaderboard?top=20`

### 5.7 知识库接口

- `GET /knowledge/scams`
- `GET /knowledge/laws`
- `POST /knowledge/scams`（需 `x-admin-token`）

新增骗局请求字段：

- `id`
- `type`
- `name`
- `keywords`
- `tactics`
- `red_flags`
- `typical_case`
- `prevention`
- `legal_refs`

### 5.8 AI 对话

- `POST /ai/chat`

请求：

```json
{
  "message": "AI换脸诈骗怎么识别？",
  "history": []
}
```

响应：

- `reply`
- `model`
- `latency_ms`

---

## 6. 积分与勋章规则

积分动作：

- `daily_chat`：+2
- `knowledge_query`：+5
- `report_submit`：+12
- `risk_block`：+20
- `scenario_step`：按选项 points
- `scenario_complete`：+15

等级规则：

- `level = points // 100 + 1`

勋章触发：

- 线索侦察员：举报 >= 1
- 反诈新兵：积分 >= 50
- 风险守门人：积分 >= 150
- 情景闯关达人：完成关卡 >= 3
- 冷静止损王：高风险阻断 >= 2

---

## 7. 老师/家长使用建议

推荐节奏：

1. 每周 1 次，15 分钟。
2. 先看本周高风险举报样本。
3. 做 1 个情景关卡。
4. 导出本周数据并给出个性化提醒。

推荐观察指标：

- `high_risk` 占比是否下降
- 关卡完成数是否上升
- 重复命中关键词是否减少

---

## 8. 运维与扩展

### 8.1 管理员令牌

建议通过环境变量注入：

```bash
export ANTI_FRAUD_ADMIN_TOKEN="replace-with-strong-token"
```

### 8.2 JWT 密钥

建议覆盖默认值：

```bash
export JWT_SECRET="replace-with-strong-jwt-secret"
```

### 8.3 重置状态

删除数据库文件即可回到初始状态：

```bash
rm -f app/data/anti_fraud.db
```

---

## 9. 常见问题与排查

### 9.1 报 422（校验失败）

常见原因：`user_id` 传成字符串。

修复：改为整数，例如 `"user_id": 1`。

### 9.2 报 401（未授权）

常见原因：缺少或过期 token。

修复：重新登录并携带 Bearer token。

### 9.3 `GET /auth/me` 异常

当前版本存在字段映射不一致问题（`id` / `user_id`）。

建议：

- 先使用登录接口返回信息作为当前用户信息
- 后续版本统一该字段后再启用强依赖

### 9.4 AI 模块不可用

请检查：

```bash
ollama serve
ollama pull deepseek-r1:1.5b
```

---

## 10. 合规与风险边界

- 本系统用于教育和预警，不替代公安与司法结论
- 发现真实资金风险时，优先停止转账、保留证据、报警咨询
- 不建议在日志中存储完整敏感信息（银行卡、验证码等）

---

## 11. 关联文档

- 快速复现与启动：`README.md`
- 自动化与回归：`tests/test_api.py`
- 压测脚本：`scripts/benchmark_api.py`
