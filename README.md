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

## 7. 自动化测试现状

执行：

```bash
pytest -q
```

当前仓库实测结果：**86 个通过，0 个失败**

---

## 8. 目录结构

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
    web/
      index.html
      app.js
      styles.css
    main.py
  scripts/
    benchmark_api.py
  tests/
    test_api.py
  requirements.txt
  README.md
  USAGE_GUIDE.md
```

---

## 9. 故障排查

- 端口占用：`uvicorn` 启动失败时，改端口 `--port 8001`
- 依赖安装慢：优先升级 pip，或换镜像源
- 前端一直显示未登录：清理浏览器 `localStorage` 后重新登录
- AI 回复报连接失败：先检查 `ollama serve` 是否在运行

---

## 10. 安全提示

- 默认密钥仅用于开发演示，生产环境必须替换
- 管理员 token 不要写死在前端
- 涉及真实资金风险场景时，优先执行止损与报警流程
