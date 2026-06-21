# 反诈护盾实验室（Anti-Fraud Lab）

一个基于 FastAPI 的反诈教育应用原型，包含：

- 规则驱动的诈骗风险研判（对话 / 举报）
- 反诈知识库（骗局 + 法律要点）
- 情景闯关与积分勋章体系
- 账号认证与排行榜
- 可选的本地 AI 助手（Ollama + deepseek-r1:1.5b）

**比赛文档：**

- [评分点映射表](SCORING_ALIGNMENT.md) — 方向三评分标准逐项对应
- [答辩演示脚本](DEMO_SCRIPT.md) — 5-7 分钟演示流程
- [安全设计文档](SECURITY_DESIGN.md) — 脱敏、认证、权限、LLM 边界

如果你希望快速落地部署，请先看本 README；如果你希望看完整交互手册，请看 `USAGE_GUIDE.md`。

---

## 1. 环境要求（可复现基线）

建议环境：

- Linux / macOS
- Python 3.10+
- 可联网安装依赖

已验证依赖来自 `requirements.txt`：

- fastapi
- uvicorn[standard]
- pydantic
- pytest
- httpx

---

## 2. 从零启动（保证可复现）

在项目根目录执行：

```bash
# 进入项目根目录
cd caip2026

# 1) 清理旧数据库（确保用户ID、积分状态可复现）
rm -f app/data/anti_fraud.db

# 2) 创建并激活虚拟环境
python -m venv .venv
source .venv/bin/activate

# 3) 安装依赖
pip install -r requirements.txt

# 4) （可选）设置安全相关环境变量
export ANTI_FRAUD_ADMIN_TOKEN="change-me"
export JWT_SECRET="anti-fraud-lab-secret-key-change-in-production-2024"

# 5) 启动服务
uvicorn app.main:app --reload --port 8000
```

访问地址：

- 前端页面：http://127.0.0.1:8000/
- Swagger：http://127.0.0.1:8000/docs
- ReDoc：http://127.0.0.1:8000/redoc

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

预期关键字段：

- `status: ok`
- `service: anti-fraud-dialogue`

---

## 3. 10 分钟烟雾测试（端到端）

以下步骤在新数据库下可重复执行。

### 3.1 注册并提取 token / user_id

```bash
REGISTER_RESP=$(curl -s -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "demo_student",
    "password": "demo123456",
    "role": "student",
    "nickname": "演示同学"
  }')

echo "$REGISTER_RESP"

TOKEN=$(echo "$REGISTER_RESP" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
USER_ID=$(echo "$REGISTER_RESP" | sed -n 's/.*"user_id":\([0-9]\+\).*/\1/p')

echo "USER_ID=$USER_ID"
echo "TOKEN=${TOKEN:0:20}..."
```

### 3.2 对话研判

```bash
curl -s -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{
    \"user_id\": $USER_ID,
    \"message\": \"有人让我先垫付刷单，说完成后返利\",
    \"channel\": \"web\",
    \"emotion\": \"anxious\",
    \"user_profile\": {\"role\": \"student\", \"risk_tolerance\": \"low\"}
  }"
```

预期关键字段：

- `risk_level`
- `risk_score`
- `intervention_script`
- `points_gained`

### 3.3 举报初判

```bash
curl -s -X POST http://127.0.0.1:8000/report \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{
    \"user_id\": $USER_ID,
    \"url\": \"http://xn--secure-bank-5k9f.top/login@notice\",
    \"content\": \"点击领取返利，先转账再提现\",
    \"channel\": \"web\"
  }"
```

预期关键字段：

- `verdict`
- `risk_score`
- `matched_keywords`

### 3.4 闯关

```bash
# 查询关卡
curl -s http://127.0.0.1:8000/scenarios

# 开始 C001
curl -s -X POST http://127.0.0.1:8000/scenarios/start \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"user_id\": $USER_ID, \"scenario_id\": \"C001\"}"

# 回答第 1 题（option_index 按返回选项序号填写）
curl -s -X POST http://127.0.0.1:8000/scenarios/answer \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"user_id\": $USER_ID, \"option_index\": 1}"
```

### 3.5 查看进度、历史与排行榜

```bash
curl -s "http://127.0.0.1:8000/users/$USER_ID/progress" \
  -H "Authorization: Bearer $TOKEN"

curl -s "http://127.0.0.1:8000/users/$USER_ID/reports?limit=10" \
  -H "Authorization: Bearer $TOKEN"

curl -s "http://127.0.0.1:8000/leaderboard?top=20"
```

---

## 4. 管理员：新增骗局知识

`POST /knowledge/scams` 需要请求头 `x-admin-token`。

管理员还可通过 `PATCH /reports/{report_id}/status` 将举报标记为 `pending`、`reviewed` 或 `closed`。

```bash
curl -s -X POST http://127.0.0.1:8000/knowledge/scams \
  -H "Content-Type: application/json" \
  -H "x-admin-token: ${ANTI_FRAUD_ADMIN_TOKEN:-change-me}" \
  -d '{
    "id": "S998",
    "type": "demo_case",
    "name": "演示型骗局",
    "keywords": ["演示词"],
    "tactics": ["演示手法"],
    "red_flags": ["演示风险点"],
    "typical_case": "用于演示的案例描述",
    "prevention": ["先核验后操作"],
    "legal_refs": ["反电信网络诈骗法"]
  }'
```

---

## 5. 可选：启用 AI 助手（Ollama）

`/ai/chat` 默认走本地 Ollama：`http://localhost:11434`，模型 `deepseek-r1:1.5b`。

```bash
# 启动 Ollama 服务
ollama serve

# 拉取模型
ollama pull deepseek-r1:1.5b
```

如果 Ollama 未启动，接口会返回降级提示，不会直接导致服务崩溃。

---

## 6. 压测

服务启动后，执行：

```bash
python scripts/benchmark_api.py \
  --base-url http://127.0.0.1:8000 \
  --rounds 120 \
  --concurrency 30
```

输出包含：

- chat/report 成功率
- 平均延迟、P50、P95、最大延迟
- chat 高危命中率、report 可疑命中率

---

## 7. 演示数据一键初始化

为了保证答辩现场稳定复现，可用脚本生成固定演示用户、举报历史、闯关进度、积分勋章和规则变更审计记录：

```bash
python scripts/seed_demo_data.py --reset
```

默认写入 `DB_PATH` 指向的 SQLite，未设置时写入 `app/data/anti_fraud.db`。脚本输出会列出演示账号：

| 用户名 | 密码 | 用途 |
|--------|------|------|
| `demo_student` | `Demo@123456` | 学生端完整演示：聊天、举报、闯关、积分、规则命中 |
| `demo_guardian` | `Demo@123456` | 泛个人用户体验账号 |

初始化后可访问：

- `/profile`：查看积分、等级、勋章与闯关进度；
- `/report`：查看举报记录与状态；
- `/admin`：输入管理员令牌，通过校验后进入后台运营看板；
- `/admin/dashboard`：查看后台运营看板，包括举报态势、Top 关键词/域名、学习效果、知识来源覆盖和规则状态；
- `/admin/rules`：查看“新增快递理赔规则、临时调权、回滚”的规则审计轨迹。

---

## 8. 自动化测试现状

执行：

```bash
pytest -q
```

自动化测试覆盖：**106 个用例**（API、规则引擎、规则热加载、后台看板、演示数据、游戏化、脱敏与离线评测等）。本机若 Python 环境可用，执行 `pytest -q` 进行完整验证。

### 8.1 规则离线评测

仓库内置文本与 URL 风险规则回归集，覆盖刷单返利、游戏交易、冒充公检法、虚假投资、校园贷、助学金、机票退改签、人社/社保补贴钓鱼、银行账户异常认证、高考招生录取诈骗、否定语义、白名单边界和域名仿冒。评测会输出准确率、精确率、召回率、F1、误报率、规则断言通过率和 P95 延迟：

```bash
python scripts/evaluate_rules.py \
  --iterations 100 \
  --output RULE_EVALUATION.md \
  --fail-on-regression
```

评测数据位于 `evaluation/risk_cases.json`。新增骗局或调整规则时，应同时增加风险正例和安全反例，避免只提高召回而放大误报。

### 8.2 规则管理与热加载

登录后访问 `/admin` 可打开管理端入口。前端会先校验 `ANTI_FRAUD_ADMIN_TOKEN` 对应的 `X-Admin-Token`，校验通过后才在侧边栏显示“后台看板”和“规则管理”。后端管理接口仍强制校验 `X-Admin-Token`，前端隐藏菜单只是体验层权限控制。

访问 `/admin/rules` 可打开规则控制台，支持：

- 查看当前文本规则集、URL 规则集版本及生效修订；
- 在线启停规则、调整 0-100 权重；
- 新增可配置文本骗局规则并立即进入聊天和举报研判链路；
- 查看 SQLite 中的不可变变更记录，并将任意历史快照回滚为新的生效修订；
- 发布前校验规则名称、触发词、权重、URL condition、正则和风险等级阈值。

热加载采用完整运行时快照替换，同一服务进程中的现有 `DialogueService` 与 `ReportService` 无需重建。生产部署建议使用单进程应用实例，或在多实例环境中增加配置发布消息通知。

访问 `/admin/dashboard` 可打开后台运营看板，聚合注册用户、举报风险分布、待处理队列、Top 关键词/域名、闯关学习效果、知识来源覆盖和当前规则版本。看板接口只返回脱敏后的举报摘要与 URL host，不返回原始举报文本。

### 规则与知识库版本

- 文本规则集当前版本为 `2.2.0`，URL 规则集为 `2.3.0`；接口通过 `ruleset_versions` 返回实际加载版本。
- 每条命中规则返回 `rule_version`、`ruleset_version` 和 `rationale`，前端可展开查看判定依据。
- 知识库新增助学金/奖学金、机票退改签、人社/社保补贴钓鱼、银行账户异常认证、高考招生录取诈骗条目；闯关新增 `C010` 机票退改签场景。
- 新增条目支持 `sources` 字段，保留 12321、12377 等公开来源的标题、机构、URL 和采集日期；知识页会直接展示权威来源链接。
- 否定语义只在同一分句和有限窗口内生效，例如“没有要求转账”“不要提供验证码”不会被当作风险行为。
- URL 白名单采用主域名边界匹配，`service.edu.cn` 可命中，`evilgov.cn` 不会冒充 `gov.cn` 进入白名单。

### 游戏化积分规则

- 关卡答题分在本局结束时统一结算，中途退出不会产生积分。
- 首次通关获得 `15` 分固定奖励，并计入本局有效答题分。
- 重复挑战只奖励超过历史最佳成绩的增量，相同成绩不重复加分。
- 系统持久化每关挑战次数、最佳成绩、累计奖励与完成时间，个人中心和闯关页均可查看。

---

## 9. 目录结构

```text
anti_fraud_system/
  app/
    data/
      anti_fraud.db
      knowledge_base.json
      scenarios.json
    models/
      schemas.py
    services/
      *.py
      rule_management.py
    web/
      index.html
      app.js
      styles.css
    main.py
  scripts/
    benchmark_api.py
    evaluate_rules.py
    seed_demo_data.py
  evaluation/
    risk_cases.json
  tests/
    test_api.py
    test_rule_evaluation.py
  requirements.txt
  README.md
  USAGE_GUIDE.md
```

---

## 10. 故障排查

- 端口占用：`uvicorn` 启动失败时，改端口 `--port 8001`
- 依赖安装慢：优先升级 pip，或换镜像源
- 前端一直显示未登录：清理浏览器 `localStorage` 后重新登录
- 管理规则提示 401：确认 `ANTI_FRAUD_ADMIN_TOKEN` 与页面输入一致，管理令牌只保存在浏览器会话
- AI 回复报连接失败：先检查 `ollama serve` 是否在运行

---

## 11. 安全提示

- 默认密钥仅用于开发演示，生产环境必须替换
- 管理员 token 不要写死在前端
- `scripts/seed_demo_data.py --reset` 只清理固定演示用户及其业务记录，不清理真实用户
- 涉及真实资金风险场景时，优先执行止损与报警流程
