# Vue3 + Vite + JavaScript 前端重构方案

## 1. 当前项目现状

当前项目是：

```text
FastAPI 后端 + 原生静态前端
```

当前前端入口是：

```text
app/web/index.html
app/web/app.js
app/web/styles.css
```

后端在 `app/main.py` 中通过：

```python
app.mount("/static", StaticFiles(directory=BASE_DIR / "web"), name="static")
```

托管当前原生前端。

当前前端特点：

- 没有 Vue
- 没有 Vite
- 没有 TypeScript
- 没有 Tailwind 构建链
- 没有 axios
- 没有独立 API client 文件
- 所有核心逻辑集中在 `app/web/app.js`
- 通过原生 DOM 查询、事件监听、`fetch` 调用后端接口

## 2. 当前 `app/web/app.js` 中已有接口与字段

### 2.1 统一请求封装

当前所有接口基本走：

```js
requestJson(url, options = {}, requireAuth = false)
```

位置：

```text
app/web/app.js:647
```

当前功能：

- 内部使用 `fetch`
- 自动加 `Content-Type: application/json`
- 自动附加 `Authorization: Bearer <token>`
- 401 时清理 token
- 统一解析 JSON / text 错误

Vue 重构后应迁移为：

```text
frontend/src/api/request.js
```

组件中不直接 `fetch`。

## 3. 必须保留的真实接口

这些接口不能 mock，不能用 Stitch 静态数据替代：

| 功能 | 接口 | Vue 中建议封装文件 |
| --- | --- | --- |
| 健康检查 | `GET /health` | `api/request.js` 或后续 `api/health.js` |
| 登录 | `POST /auth/login` | `api/auth.js` |
| 注册 | `POST /auth/register` | `api/auth.js` |
| 当前用户 | `GET /auth/me` | `api/auth.js` |
| AI 助手 | `POST /ai/chat` | `api/chat.js` |
| 风险对话 | `POST /chat` | `api/chat.js` |
| 举报分析 | `POST /report` | `api/report.js` |
| 关卡列表 | `GET /scenarios` | `api/scenario.js` |
| 开始闯关 | `POST /scenarios/start` | `api/scenario.js` |
| 提交答案 | `POST /scenarios/answer` | `api/scenario.js` |
| 用户进度 | `GET /users/{user_id}/progress` | `api/leaderboard.js` 或后续 `api/profile.js` |
| 举报历史 | `GET /users/{user_id}/reports` | `api/report.js` |
| 排行榜 | `GET /leaderboard?top=20` | `api/leaderboard.js` |
| 骗局知识库 | `GET /knowledge/scams` | `api/knowledge.js` |
| 法律知识库 | `GET /knowledge/laws` | `api/knowledge.js` |

## 4. 关键接口字段提取

### 4.1 `POST /auth/login`

请求：

```js
{
  username,
  password
}
```

响应：

```js
{
  access_token,
  token_type,
  user_id,
  username,
  role,
  nickname
}
```

### 4.2 `POST /auth/register`

请求：

```js
{
  username,
  password,
  role,
  nickname
}
```

响应同登录。

### 4.3 `GET /auth/me`

响应：

```js
{
  user_id,
  username,
  role,
  nickname,
  created_at
}
```

### 4.4 `POST /chat`

请求：

```js
{
  user_id,
  message,
  channel: "web",
  emotion,
  user_profile: {
    role,
    risk_tolerance
  },
  context
}
```

响应：

```js
{
  reply,
  intent,
  matched_scams,
  risk_level,
  risk_score,
  intervention_script,
  recommendations,
  points_gained,
  total_points,
  badges,
  latency_ms
}
```

这些字段应驱动：

```text
ChatPanel 消息流
RiskPanel 右侧风险分析面板
```

### 4.5 `POST /ai/chat`

请求：

```js
{
  message,
  history: [
    {
      role: "user" | "assistant",
      content
    }
  ]
}
```

响应：

```js
{
  reply,
  model,
  latency_ms
}
```

注意：这是本地 DeepSeek / Ollama 助手接口，可以保留，但核心风险识别应优先使用 `/chat`。

### 4.6 `POST /report`

请求：

```js
{
  user_id,
  url,
  content,
  channel: "web"
}
```

响应：

```js
{
  report_id,
  verdict,
  risk_score,
  reasons,
  recommendations,
  matched_keywords,
  url_flags
}
```

### 4.7 `GET /scenarios`

响应：

```js
[
  {
    id,
    title,
    scam_type
  }
]
```

### 4.8 `POST /scenarios/start`

请求：

```js
{
  user_id,
  scenario_id
}
```

响应：

```js
{
  scenario_id,
  title,
  step_index,
  prompt,
  options
}
```

### 4.9 `POST /scenarios/answer`

请求：

```js
{
  user_id,
  option_index
}
```

响应：

```js
{
  scenario_id,
  step_index,
  finished,
  feedback,
  points_gained,
  total_points,
  badges,
  next_prompt,
  next_options
}
```

### 4.10 `GET /users/{user_id}/progress`

响应：

```js
{
  user_id,
  level,
  points,
  badges,
  reports_submitted,
  scenarios_completed
}
```

### 4.11 `GET /leaderboard?top=20`

响应：

```js
{
  total,
  items: [
    {
      rank,
      user_id,
      username,
      nickname,
      role,
      points,
      level,
      badges
    }
  ]
}
```

### 4.12 `GET /knowledge/scams`

响应为骗局知识条目数组，字段来自知识库数据，大致包含：

```js
{
  id,
  type,
  name,
  keywords,
  tactics,
  red_flags,
  typical_case,
  prevention,
  legal_refs
}
```

### 4.13 `GET /knowledge/laws`

响应为法律知识条目数组，用于知识库页面和风险依据展示。

## 5. Stitch / shield-lab 可参考内容

参考项目路径：

```text
D:\Contest\raicom\sheid-lab
```

它是 Vue3 + Vite + TypeScript + Tailwind CSS v4 项目，但新要求是：

```text
Vue3 + Vite + JavaScript
```

所以只能参考 UI 和结构，不能直接复制 TypeScript 写法。

### 5.1 `src/components/Layout.vue`

可参考：

- 左侧固定 Sidebar
- 主内容区 `router-view`
- 整体 `slate` 背景
- 白色卡片
- 大圆角
- 轻阴影
- 响应式布局

迁移目标：

```text
frontend/src/components/layout/AppShell.vue
```

### 5.2 `src/components/Sidebar.vue`

可参考：

- 护盾品牌区
- 左侧导航项
- 图标风格
- 当前路由高亮
- 底部用户入口

迁移目标：

```text
frontend/src/components/layout/Sidebar.vue
```

### 5.3 `src/pages/Chat.vue`

最重要，可以参考：

- 中间聊天流
- 用户消息靠右
- AI 消息靠左
- 底部输入框
- 快捷提示
- 右侧风险状态卡片
- “Active Monitoring” 风格标签
- 风险命中特征展示方式

迁移目标：

```text
frontend/src/pages/ChatPage.vue
frontend/src/components/chat/ChatPanel.vue
frontend/src/components/chat/MessageBubble.vue
frontend/src/components/chat/ChatInput.vue
frontend/src/components/chat/QuickPrompts.vue
frontend/src/components/risk/RiskPanel.vue
```

### 5.4 `src/pages/Report.vue`

可参考：

- 举报类型选择按钮
- 链接输入
- 举报内容 textarea
- 右侧说明卡片
- 提交按钮视觉

迁移目标：

```text
frontend/src/pages/ReportPage.vue
frontend/src/components/report/ReportForm.vue
frontend/src/components/report/ReportResult.vue
```

### 5.5 `src/pages/Game.vue`

可参考：

- 闯关卡片
- 剧情式问题展示
- 选项按钮
- 完成态样式

迁移目标：

```text
frontend/src/pages/GamePage.vue
frontend/src/components/game/ScenarioCard.vue
frontend/src/components/game/ScenarioPlayer.vue
```

### 5.6 `src/pages/Home.vue`

可参考：

- 知识库首页卡片
- 搜索框
- 风险类别卡片
- 学习入口

迁移目标：

```text
frontend/src/pages/KnowledgePage.vue
```

### 5.7 `src/pages/Levels.vue`

可参考：

- 用户等级
- 积分进度
- 勋章
- 排行榜视觉

迁移目标：

```text
frontend/src/pages/LeaderboardPage.vue
frontend/src/pages/ProfilePage.vue
```

### 5.8 `src/pages/Detection.vue`

可参考：

- 风险分圆环
- 风险报告卡片
- 风险因素列表
- 行动建议按钮

但当前项目不建议照搬成独立假检测页。风险检测应主要由：

```text
POST /chat
POST /report
```

真实结果驱动。

## 6. Stitch / shield-lab 不能复制的内容

### 6.1 不能复制 TypeScript

不能复制：

```vue
<script setup lang="ts">
```

不能复制：

```ts
interface Xxx {}
type Xxx = {}
```

不能生成：

```text
.ts 文件
```

所有新文件必须是：

```text
.js
.vue
.css
```

Vue 文件必须使用：

```vue
<script setup>
```

### 6.2 不能复制 `@google/genai`

参考项目 `package.json` 中有：

```json
"@google/genai": "^1.29.0"
```

不能引入。

原因：

- 当前后端已有 `/ai/chat`
- 前端不能暴露 API Key
- 不需要前端直连 Google AI

### 6.3 不能复制 `vite.config.ts`

参考项目中有：

```js
define: {
  'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY),
}
```

不能复制。

新项目应使用：

```text
vite.config.js
```

并且只配置：

- Vue plugin
- Tailwind plugin，如使用
- dev server proxy

不配置任何前端 API Key。

### 6.4 不能复制 setTimeout 模拟分析

Stitch 中有静态模拟逻辑，例如：

```js
setTimeout(() => {
  // 假装 AI 分析完成
}, ...)
```

不能作为业务逻辑迁入。

真实逻辑必须调用：

```text
POST /chat
POST /report
POST /scenarios/start
POST /scenarios/answer
```

### 6.5 不能复制静态风险结果

例如静态：

- 风险等级
- 风险分
- 假命中特征
- 假推荐建议
- 假积分
- 假勋章

这些都必须来自后端真实响应。

### 6.6 不建议复制整套路由命名

Stitch 有：

```text
/detection
/profile -> Levels
```

新项目可以保留更贴近当前业务的页面：

```text
/chat
/report
/game
/knowledge
/leaderboard
/profile
/login
```

其中“风险检测”可以作为 Sidebar 文案指向 `/chat` 或后续单独检测页面，但第一轮不建议做静态假检测页。

## 7. Vue3 + Vite + JavaScript 重构方案

### 7.1 总体策略

新建独立目录：

```text
frontend/
```

保留当前后端 `app/` 不动。

第一轮目标是让 Vue 前端可以独立开发运行，并通过 Vite proxy 调用 FastAPI 后端。

开发时：

```text
Vue dev server -> Vite proxy -> FastAPI
```

生产时后续有两种选择：

1. `npm run build` 后把 `frontend/dist` 交给 FastAPI 托管。
2. 前后端分离部署。

第一轮只需要先搭建 `frontend/`。

## 8. 推荐路由设计

```text
/login
/chat
/report
game
/knowledge
/leaderboard
/profile
```

默认路由：

```text
/ -> /chat
```

建议：

- 登录页不使用 `AppShell`
- 业务页使用 `AppShell`

结构：

```js
[
  {
    path: "/login",
    component: LoginPage
  },
  {
    path: "/",
    component: AppShell,
    children: [
      { path: "", redirect: "/chat" },
      { path: "chat", component: ChatPage },
      { path: "report", component: ReportPage },
      { path: "game", component: GamePage },
      { path: "knowledge", component: KnowledgePage },
      { path: "leaderboard", component: LeaderboardPage },
      { path: "profile", component: ProfilePage }
    ]
  }
]
```

## 9. API 层设计

所有 `fetch` 只在：

```text
frontend/src/api/request.js
```

### 9.1 `request.js`

职责：

- 读取 `VITE_API_BASE_URL`
- 拼接 URL
- 自动附加 token
- 统一 `Content-Type`
- 统一 JSON 解析
- 统一错误消息
- 401 时清除 token
- 不直接依赖 Vue

建议暴露：

```js
request(path, options)
get(path)
post(path, body)
```

### 9.2 `auth.js`

封装：

```js
login(payload)
register(payload)
getCurrentUser()
```

### 9.3 `chat.js`

封装：

```js
sendRiskChat(payload)    // POST /chat
sendAiChat(payload)      // POST /ai/chat
```

### 9.4 `report.js`

封装：

```js
submitReport(payload)
getUserReports(userId, params)
```

### 9.5 `scenario.js`

封装：

```js
getScenarios()
startScenario(payload)
answerScenario(payload)
```

### 9.6 `knowledge.js`

封装：

```js
getScams()
getLaws()
```

### 9.7 `leaderboard.js`

封装：

```js
getLeaderboard(top)
getUserProgress(userId)
```

## 10. 存储层设计

```text
frontend/src/utils/storage.js
```

职责：

- token 存取
- 当前用户缓存，如需要
- 不在组件里直接操作 `localStorage`

建议封装：

```js
getToken()
setToken(token)
clearToken()
getStoredUser()
setStoredUser(user)
clearStoredUser()
```

为了未来迁移 uni-app / Taro，组件不应直接依赖 `localStorage`。

## 11. composables 设计

### 11.1 `useAuth.js`

职责：

- 当前用户状态
- 登录
- 注册
- 退出
- 初始化登录态
- 是否已登录

依赖：

```text
api/auth.js
utils/storage.js
```

### 11.2 `useChat.js`

职责：

- 消息列表
- 输入发送
- loading 状态
- 调用 `POST /chat`
- 保存最新风险分析结果
- 可选维护 `/ai/chat` 历史

依赖：

```text
api/chat.js
```

不直接 `fetch`。

### 11.3 `useRiskPanel.js`

职责：

- 把 `/chat` 返回结果转换成 UI 友好的展示对象
- 风险等级 label / color
- 风险分展示
- 空状态

不请求接口，只处理数据。

### 11.4 `useScenario.js`

职责：

- 加载关卡列表
- 开始关卡
- 提交答案
- 当前步骤
- 完成状态
- loading / error

依赖：

```text
api/scenario.js
```

## 12. 页面职责设计

### 12.1 `ChatPage.vue`

职责：

- 页面级布局
- 左/中/右结构中的中间和右侧组合
- 使用 `useChat`
- 向 `ChatPanel` 传消息、loading
- 向 `RiskPanel` 传最新风险结果

不直接 `fetch`。

### 12.2 `ReportPage.vue`

职责：

- 使用 `ReportForm`
- 展示 `ReportResult`
- 调用 `api/report.js` 或一个简单页面级状态方法
- 使用真实 `/report`

### 12.3 `GamePage.vue`

职责：

- 加载 `GET /scenarios`
- 展示 `ScenarioCard`
- 进入 `ScenarioPlayer`
- 使用 `useScenario`

### 12.4 `KnowledgePage.vue`

职责：

- 加载骗局知识库
- 加载法律知识库
- 展示知识卡片

### 12.5 `LeaderboardPage.vue`

职责：

- 调用 `GET /leaderboard?top=20`
- 展示排行、积分、等级、勋章

### 12.6 `ProfilePage.vue`

职责：

- 从 `useAuth` 获取当前用户
- 使用当前 `user_id` 调用 `/users/{user_id}/progress`
- 展示等级、积分、勋章、举报数、闯关数

### 12.7 `LoginPage.vue`

职责：

- 登录/注册切换
- 调用 `useAuth`
- 登录成功后跳转 `/chat`

## 13. 第一轮需要创建的文件

第一轮建议完整创建这些文件：

```text
frontend/package.json
frontend/index.html
frontend/vite.config.js
frontend/src/main.js
frontend/src/App.vue
frontend/src/router/index.js
frontend/src/styles/index.css
frontend/src/utils/storage.js
frontend/src/api/request.js
frontend/src/api/auth.js
frontend/src/api/chat.js
frontend/src/api/report.js
frontend/src/api/scenario.js
frontend/src/api/knowledge.js
frontend/src/api/leaderboard.js
frontend/src/composables/useAuth.js
frontend/src/composables/useChat.js
frontend/src/composables/useScenario.js
frontend/src/composables/useRiskPanel.js
frontend/src/components/layout/AppShell.vue
frontend/src/components/layout/Sidebar.vue
frontend/src/components/chat/ChatPanel.vue
frontend/src/components/chat/MessageBubble.vue
frontend/src/components/chat/ChatInput.vue
frontend/src/components/chat/QuickPrompts.vue
frontend/src/components/risk/RiskPanel.vue
frontend/src/components/risk/RiskScoreCard.vue
frontend/src/components/risk/ScamMatchList.vue
frontend/src/components/risk/RecommendationList.vue
frontend/src/components/report/ReportForm.vue
frontend/src/components/report/ReportResult.vue
frontend/src/components/game/ScenarioCard.vue
frontend/src/components/game/ScenarioPlayer.vue
frontend/src/components/common/BaseCard.vue
frontend/src/components/common/BaseButton.vue
frontend/src/components/common/StatusBadge.vue
frontend/src/pages/ChatPage.vue
frontend/src/pages/ReportPage.vue
frontend/src/pages/GamePage.vue
frontend/src/pages/KnowledgePage.vue
frontend/src/pages/LeaderboardPage.vue
frontend/src/pages/ProfilePage.vue
frontend/src/pages/LoginPage.vue
```

可以暂时创建空目录：

```text
frontend/src/assets/
```

但第一轮不一定需要放资源。

## 14. `package.json` 依赖建议

只使用 JavaScript，不使用 TypeScript。

建议依赖：

```json
{
  "dependencies": {
    "@tailwindcss/vite": "^4.1.14",
    "lucide-vue-next": "^0.477.0",
    "vite": "^6.2.3",
    "vue": "^3.5.13",
    "vue-router": "^4.5.0",
    "tailwindcss": "^4.1.14"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^6.0.6"
  }
}
```

不加入：

```text
typescript
vue-tsc
@types/*
@google/genai
pinia
react
react-dom
```

## 15. `vite.config.js` 设计

只使用 JS：

```text
frontend/vite.config.js
```

建议配置：

- `@vitejs/plugin-vue`
- `@tailwindcss/vite`
- dev server proxy 到 FastAPI

例如开发时：

```text
Vue: http://localhost:5173
FastAPI: http://localhost:8000
```

请求 `/api/chat` 可代理到 `http://localhost:8000/chat`，或者保持请求 `/chat` 直接 proxy。

更简单方案：

```js
server: {
  proxy: {
    "/health": "http://127.0.0.1:8000",
    "/auth": "http://127.0.0.1:8000",
    "/ai": "http://127.0.0.1:8000",
    "/chat": "http://127.0.0.1:8000",
    "/report": "http://127.0.0.1:8000",
    "/scenarios": "http://127.0.0.1:8000",
    "/users": "http://127.0.0.1:8000",
    "/leaderboard": "http://127.0.0.1:8000",
    "/knowledge": "http://127.0.0.1:8000"
  }
}
```

这样 API 文件可以继续请求原始路径：

```js
post("/chat", payload)
```

以后生产环境可用：

```text
VITE_API_BASE_URL
```

切换到完整后端地址。

## 16. 第一轮实现边界建议

第一轮不建议做太多额外能力。

应该完成：

- Vue/Vite/JS 工程骨架
- 路由
- AppShell + Sidebar
- 登录/注册
- ChatPage + RiskPanel
- ReportPage
- GamePage
- KnowledgePage
- LeaderboardPage
- ProfilePage
- API 层真实调用
- 基础错误提示和 loading 状态

暂不做：

- 前端 API Key
- Google AI
- Pinia
- TypeScript
- 复杂动画
- 复杂历史会话持久化
- 把 FastAPI 静态托管改成 dist 托管
- 删除旧 `app/web`

旧前端建议先保留，直到 Vue 前端功能验证通过。

## 17. 结论

推荐方案是：

```text
新建 frontend/，使用 Vue3 + Vite + JavaScript 重构前端。
Stitch / shield-lab 只作为 UI 和布局参考。
所有真实业务继续调用当前 FastAPI 接口。
不引入 TypeScript、React、@google/genai、Pinia。
```

第一轮重构核心应优先落地：

```text
LoginPage -> AppShell -> ChatPage -> RiskPanel
```

因为这是当前项目定位“反诈智能对话系统”的主链路。
