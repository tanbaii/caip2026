# 反诈护盾 · 诈骗拦截大作战 — Godot 游戏项目

> ## ⚠ 2.0 玩法重做（请先读）
> 游戏已从「4R 选择闯关问答」重做为 **「诈骗拦截大作战」快速分拣反应游戏**，
> 与网页端「闯关训练」彻底差异化，且 **自包含**（内置信息卡池，无需登录、无需后端）。
>
> - **核心循环**：信息卡（短信 / 来电 / 通知 / 好友 / 群消息）限时滑入 → 玩家判断
>   【诈骗 → 拦截】或【正常 → 放行】→ 答对得分 + 连击（反应越快越高分、连击 5/10 触发特效）、
>   答错 / 超时扣防御并即时显示「类型 + 识别要点」。
> - **关卡系统（2.1 新增）**：`主菜单 → 关卡选择 → 游戏`。
>   - **关卡战役**：6 关递进（短信风暴 / 来电惊魂 / 熟人迷局 / 财路陷阱 / 全面突击 / BOSS·诈骗集团），
>     每关有**主题配色、关前提示、清理目标、防御值、时限**，通关按正确率评 **1~3 星**，
>     **本地存档（`user://interceptor_save.json`）并解锁下一关**。
>   - **无尽模式**：撑到防御耗尽，难度随进度提升，按正确率评 S/A/B/C。
> - **专属卡池（2.2）**：卡池扩充至 **52 张**（32 诈骗 / 20 正常），每关只出该关涉及类别的
>   诈骗 + 正常信息，**不同关卡内容不同**。
> - **道具（2.2）**：火眼金睛（高亮正确应对）/ 时间冻结（停表）/ 护盾（抵挡一次失误）；
>   每局有限，连击每满 6 随机再奖励 1 个；键盘 Q/W/E。
> - **本地最高分榜（2.2）**：无尽模式成绩存入 `user://`，选关页展示个人前 5 名，破纪录有提示。
> - **画面增强（2.3）**：每关**渐变光晕背景**（主题色径向辉光）+ 漂浮数据流；卡片**阴影 + 圆角**、
>   按「短信/来电/通知/好友/群消息」配色、滑入动画；浮动得分、低防御红色警示、连击进阶弹字与屏幕闪光；
>   按钮统一圆角。**修复**：题目卡与底部操作区重叠（CardLayer 开启 clip_contents + 留白）。
> - **音效（2.3）**：运行时合成（`AudioStreamWAV`，**无需音频素材**）——识破/失误/连击/道具/通关各有提示音。
> - **BOSS 特殊机制（2.3）**：① **伪装升级**——出现「高仿官方」迷惑卡（仿冒 95588/10086/反诈中心等，
>   正反都更难辨）；② **连环突袭**——每隔几张触发连续 3 张加成（更快更值，全对额外 +200，错一张中断）。
> - **新增/改写文件**：`scenes/game.tscn` + `scripts/game_scene.gd`（拦截玩法 + 28 张信息卡 + 关卡/无尽）、
>   `scenes/stage_select.tscn` + `scripts/stage_select.gd`（关卡选择，**新增**）、
>   `scripts/main_menu.gd`（进入关卡选择）、`scripts/game_manager.gd`（关卡配置 STAGES + 存档）。
> - **`scenes/level_select.tscn` 与 `scripts/level_select.gd` 已不再使用**（保留作旧版参考）。
> - **⚠ 必须重新导出 Web** 才能在网页生效：Godot 编辑器 → 项目 → 导出 → Web，
>   覆盖 `app/web/godot_export/`（详见第 7.4 / GUIDE 第三节）。否则网页加载的仍是旧版。
>
> 下文部分章节（4R 关卡、scenarios API 等）描述的是 **旧版** 内容，保留作历史参考。

---

## 1. 项目概述

> 注：本节描述旧版「4R 闯关」架构，新版玩法见顶部「2.0 玩法重做」。

基于 Godot 4.x 引擎构建的反诈实战训练游戏。游戏支持桌面端和 Web（HTML5）双模式运行。

| 属性 | 值 |
|------|-----|
| Godot 版本 | 4.x（兼容 4.2+） |
| 渲染后端 | `gl_compatibility`（兼容 WebGL） |
| 脚本语言 | GDScript 2.0（静态类型） |
| 默认窗口 | 1024×720 |
| Web 导出 | HTML5 + WebAssembly |
| 目标平台 | Windows / macOS / Linux / Web |

---

## 2. 项目结构

```
godot_game/
├── project.godot                  # Godot 引擎配置文件
├── .godot/                        # Godot 编辑器缓存（自动生成）
├── README.md                      # 本文件
│
├── scenes/                        # 场景文件 (.tscn)
│   ├── main_menu.tscn             # 主菜单 / 启动画面
│   ├── level_select.tscn          # 关卡选择界面
│   └── game.tscn                  # 核心游戏场景
│
├── scripts/                       # GDScript 脚本 (.gd)
│   ├── game_manager.gd            # Autoload 全局管理器
│   ├── main_menu.gd               # 主菜单逻辑
│   ├── level_select.gd            # 关卡选择逻辑
│   └── game_scene.gd              # 游戏核心逻辑
│
├── assets/ui/                     # UI 资源
│   ├── icon.svg                   # 应用图标 (128×128)
│   └── icon.svg.import            # Godot 导入配置（自动生成）
│
└── export/                        # HTML5 导出输出目录
    ├── index.html                 # Web 入口
    ├── index.js                   # Godot 引擎 JS 桥接
    ├── index.wasm                 # WebAssembly 二进制
    └── index.pck                  # 资源打包文件
```

---

## 3. 场景详细说明

### 3.1 主菜单 `main_menu.tscn`

**文件头**：`[gd_scene load_steps=3 format=3 uid="uid://c001main"]`
- 加载步骤 = 2 个外部资源（脚本 + 图标）+ 1 个场景本体

**外部资源引用**：
| 资源 ID | 类型 | 路径 | 用途 |
|---------|------|------|------|
| `1_script` | Script | `res://scripts/main_menu.gd` | 主菜单脚本 |
| `2_icon` | Texture2D | `res://assets/ui/icon.svg` | 应用图标纹理 |

**节点树**：
```
MainMenu (Control)                              ← 根节点，挂载 main_menu.gd
├── Background (ColorRect)                      ← 深蓝背景填充
└── VBox (VBoxContainer)                        ← 垂直居中布局容器
    ├── Icon (TextureRect)                      ← 应用图标显示
    ├── Title (Label)                           ← "反诈护盾实战训练"（32px）
    ├── Subtitle (Label)                        ← 版本号 "v1.0.0 | 12 关..."
    ├── UserInput (LineEdit)                    ← 桌面模式：用户 ID 输入
    ├── TokenInput (LineEdit, secret=true)      ← 桌面模式：Token 输入（密码遮盖）
    ├── StartButton (Button)                    ← "开始训练 ▶" 按钮
    └── StatusLabel (Label)                     ← 状态提示 / 错误信息
```

**关键属性**：
- `Background` 颜色：`Color(0.06, 0.125, 0.22, 1)` — 深海军蓝
- `VBox` 容器宽度：440px（offset_left=-220, offset_right=220）
- `VBox` 间距：16px（`theme_override_constants/separation`）
- `TokenInput.secret = true` — 密码模式，输入内容以圆点显示
- `Icon` 最小高度 80px，拉伸模式 `keep_centered` + `scale_on_expand`

**脚本逻辑（main_menu.gd）**：
1. **`_ready()`**：连接按钮信号；Web 模式下隐藏 `UserInput` 并预填 token 提示
2. **`_on_start()`**：校验输入 → 显示加载状态 → 连接 API 信号 → 调用 `GameManager.fetch_scenarios()`
3. **`_on_loaded()`**：关卡数据返回 → 隐藏进度条 → 1 秒延迟 → 切换到 `level_select.tscn`
4. **`_on_load_error()`**：恢复按钮可用，显示错误信息
5. **`_parse_user_id_from_token()`**：从 JWT token 的 payload 中提取 `sub` 字段

**信号连接**：
| 信号源 | 信号 | 目标方法 |
|--------|------|----------|
| `StartButton.pressed` | `pressed` | `_on_start` |
| `GameManager` | `scenario_list_loaded` | `_on_loaded` |
| `GameManager` | `api_error` | `_on_load_error` |

---

### 3.2 关卡选择 `level_select.tscn`

**文件头**：`[gd_scene load_steps=2 format=3 uid="uid://c002level"]`

**节点树**：
```
LevelSelect (Control)                           ← 根节点，挂载 level_select.gd
├── Background (ColorRect)                      ← 深蓝背景
├── TopBar (HBoxContainer)                      ← 顶部导航栏（高60px）
│   ├── BackButton (Button)                     ← "← 返回" 按钮
│   ├── UserLabel (Label)                       ← 显示 "特工 #ID"
│   └── PointsLabel (Label)                     ← 显示 "💰 N 分"
├── Title (Label)                               ← "选择训练关卡"（24px）
├── ScrollContainer                             ← 可滚动关卡列表
│   └── ScenarioList (VBoxContainer)            ← 动态生成关卡卡片
└── LoadingLabel (Label)                        ← "加载关卡数据..."（居中）
```

**脚本逻辑（level_select.gd）**：

- **`_ready()`**：连接信号 → 调用 `_refresh()` 获取关卡列表
- **`_refresh()`**：显示加载提示 → `GameManager.fetch_scenarios()`
- **`_on_scenarios_loaded()`**：动态生成 `PanelContainer` 卡片，每张卡片包含：
  - 状态图标：✅ 已完成 / 🔓 已解锁 / 🔒 锁定
  - 关卡 ID + 标题
  - 难度标签 + 步数 + 描述
  - 已完成关卡显示星级（⭐/☆）
- **`_on_card_pressed()`**：调用 `GameManager.start_scenario(scenario_id)`
- **`_on_level_done()`**：通关返回后自动刷新列表

**关卡卡片组件（动态创建）**：
```gdscript
PanelContainer (80px 高)
└── HBoxContainer
    ├── Label (状态图标, 48px 宽)
    ├── VBoxContainer (自动扩展)
    │   ├── Label (关卡标题, 16px)
    │   └── Label (难度+步数+描述, 13px)
    └── Label (星级评价, 仅已完成关卡显示)
```

**信号连接**：
| 信号源 | 信号 | 目标方法 |
|--------|------|----------|
| `BackButton.pressed` | `pressed` | `_on_back` |
| `GameManager` | `scenario_list_loaded` | `_on_scenarios_loaded` |
| `GameManager` | `level_completed` | `_on_level_done` |

---

### 3.3 游戏场景 `game.tscn`

**文件头**：`[gd_scene load_steps=2 format=3 uid="uid://c003game"]`

**节点树**：
```
GameScene (Control)                             ← 根节点，挂载 game_scene.gd
├── Background (ColorRect)                      ← 深蓝背景
├── TopBar (HBoxContainer, 高50px)              ← 顶部信息栏
│   ├── Title (Label)                           ← "🎯 关卡名称"
│   ├── Difficulty (Label)                      ← 难度标签
│   ├── Step (Label)                            ← "📋 当前步/总步"
│   ├── Lives (Label)                           ← "❤️❤️🖤" 生命值
│   └── Streak (Label)                          ← "🔥 x5" 连击（≥3 显示）
│
├── GameArea (VBoxContainer)                    ← 游戏主区域
│   ├── ProgressBar                             ← 进度条（高20px, 不显示百分比）
│   ├── ProgressLabel                           ← "0%" 文字显示
│   ├── StageIndicator (Label, 22px)            ← "🔍 识别" 阶段指示
│   ├── TeachingPoint (Label, 13px)             ← "💡 知识点"
│   ├── CaseBrief (RichTextLabel)               ← "📋 案情简介"（斜体, 自适应高度）
│   ├── Prompt (RichTextLabel, 16px)            ← 题目描述
│   └── Options (VBoxContainer)                 ← 动态生成选项按钮
│
├── Feedback (PanelContainer)                   ← 答题反馈面板（默认隐藏）
│   └── Margin (MarginContainer, 边距20px)
│       └── VBox (VBoxContainer)
│           ├── Icon (Label, 32px)              ← ✅/⚠️/❌
│           ├── Title (Label, 20px)             ← "正确！"/"部分正确"/"错误"
│           ├── Text (Label, 15px, 自动换行)    ← 详细反馈+得分
│           └── NextButton (Button)             ← "继续 ▶"（初始禁用）
│
└── FinishPanel (PanelContainer)                ← 通关/失败面板（默认隐藏）
    └── Margin (MarginContainer, 边距30px)
        └── VBox (VBoxContainer)
            ├── Title (Label, 24px)             ← "🎉 闯关完成！" / "💀 生命耗尽！"
            ├── Stars (HBoxContainer)            ← 动态生成 ⭐/☆（含弹出动画）
            ├── Score (Label, 18px)              ← 得分显示（金色）
            ├── Message (Label, 14px, 自动换行)  ← 鼓励/总结文字
            └── Buttons (HBoxContainer)          ← 动态生成操作按钮
```

**脚本逻辑（game_scene.gd）**：

1. **`_ready()`**：清空选项 → 隐藏反馈/结束面板 → 连接所有信号

2. **`load_scenario(data)`**：场景管理器调用，设置关卡标题、难度、案情简介

3. **`_on_scenario_loaded(data)`**：GameManager 发射信号后渲染本步 UI：
   - `_stage_ui()`：设置阶段图标（🔍识别/🧠推理/⚡行动/📝反思）、知识点、题目、动态生成选项按钮

4. **`_on_option_pressed(index)`**：禁用所有选项 → 高亮选中 → 调用 `GameManager.answer_question()`

5. **`_on_answer(data)`**：渲染反馈面板：
   - ✅ 正确 → 绿底半透明面板
   - ⚠️ 部分正确 → 橙底半透明面板
   - ❌ 错误 → 红底半透明面板
   - 显示反馈文字 + 得分 + 总分

6. **`_on_next()`**：隐藏反馈 → 禁用继续按钮 → 等待下一步渲染

7. **`_on_completed()`**：显示通关面板：
   - 动态生成 ⭐ 星星（带弹性缩放动画：1.3x → 1.0x，0.35 秒）
   - 动态生成"下一关 ▶"和"返回关卡列表"按钮

8. **`_show_game_over()`**：显示失败面板 → 生成"重新挑战"和"返回列表"按钮

9. **`_retry_level()`**：重新调用 `GameManager.start_scenario()`

10. **`_find_and_play_next()`**：在已解锁关卡中找下一个 → 自动开始

**颜色常量**：
| 常量 | 颜色值 | 用途 |
|------|--------|------|
| `COLOR_CORRECT` | `(0, 0.7, 0.3)` | 正确反馈 |
| `COLOR_PARTIAL` | `(0.9, 0.6, 0)` | 部分正确 |
| `COLOR_WRONG` | `(0.9, 0.2, 0.2)` | 错误反馈 |
| 难度 easy | `(0, 0.7, 0.3)` | 🟢 初级 |
| 难度 medium | `(0.9, 0.6, 0)` | 🟡 中级 |
| 难度 hard | `(0.9, 0.2, 0.2)` | 🔴 高级 |

**信号连接**：
| 信号源 | 信号 | 目标方法 |
|--------|------|----------|
| `NextButton.pressed` | `pressed` | `_on_next` |
| `GameManager` | `scenario_started` | `_on_scenario_loaded` |
| `GameManager` | `answer_received` | `_on_answer` |
| `GameManager` | `level_completed` | `_on_completed` |
| `GameManager` | `api_error` | `_on_api_error` |
| 各选项 `Button.pressed` | `pressed` | `_on_option_pressed.bind(index)` |

---

## 4. Autoload 全局管理器 `GameManager`

### 4.1 配置
```ini
# project.godot
[autoload]
GameManager="*res://scripts/game_manager.gd"
```
使用 `*` 前缀表示无论场景切换，该单例始终激活。

### 4.2 信号定义

| 信号 | 参数 | 说明 |
|------|------|------|
| `scenario_list_loaded` | `scenarios: Array[Dictionary]` | 关卡列表加载完成 |
| `scenario_started` | `data: Dictionary` | 关卡开始，含首步题目 |
| `answer_received` | `data: Dictionary` | 答题结果返回 |
| `api_error` | `code: int, message: String` | API 请求失败 |
| `level_completed` | `scenario_id: String, stars: int, score: int` | 关卡通关 |

### 4.3 状态属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `user_id` | `int` | `0` | 当前用户 ID |
| `api_base` | `String` | `"http://127.0.0.1:8000"` | 后端 API 基础地址 |
| `auth_token` | `String` | `""` | JWT 认证令牌 |
| `scenario_catalog` | `Array[Dictionary]` | `[]` | 关卡目录缓存 |
| `active_scenario_id` | `String` | `""` | 当前游玩的关卡 ID |
| `current_step` | `int` | `0` | 当前步索引（0-based） |
| `total_steps` | `int` | `0` | 总步数 |
| `lives` | `int` | `3` | 剩余生命值 |
| `streak` | `int` | `0` | 连续正确次数 |
| `correct_count` | `int` | `0` | 本关正确次数 |
| `total_points` | `int` | `0` | 累计总分 |

### 4.4 公共方法

**`fetch_scenarios()`**
- 请求：`GET /scenarios?user_id={id}`
- 响应：`_on_scenarios_loaded(data)` → 发射 `scenario_list_loaded` 信号

**`start_scenario(scenario_id: String)`**
- 请求：`POST /scenarios/start`，body 含 `user_id` + `scenario_id`
- 响应：`_on_scenario_started(data)` → 更新状态 → 发射 `scenario_started` 信号

**`answer_question(option_index: int)`**
- 请求：`POST /scenarios/answer`，body 含 `user_id` + `option_index`
- 响应：`_on_answer_received(data)` → 更新状态；通关时额外发射 `level_completed` 信号 → 发射 `answer_received` 信号

**`get_scenario(id: String) -> Dictionary`**
- 遍历 `scenario_catalog` 查找指定 ID 的关卡；未找到返回空字典

**`get_unlocked_scenarios() -> Array[Dictionary]`**
- 过滤 `scenario_catalog` 中 `unlocked == true` 的关卡

### 4.5 Web 模式特殊处理

在 `_ready()` 中检测 `OS.has_feature("web")`：
1. 通过 `JavaScriptBridge` 从浏览器 `localStorage` 读取 `anti_fraud_token`
2. 自动同步网页端的登录状态，无需重新输入

---

## 5. API 对接详情

### 5.1 请求封装

`GameManager` 内部维护一个 `HTTPRequest` 节点，通过 `_api_get()` / `_api_post()` 封装：

```gdscript
func _api_get(path: String, callback: Callable) -> void:
    var headers := PackedStringArray(["Content-Type: application/json"])
    if auth_token != "":
        headers.append("Authorization: Bearer " + auth_token)
    _http.request(api_base + path, headers, HTTPClient.METHOD_GET)

func _api_post(path: String, body: Dictionary, callback: Callable) -> void:
    var headers := PackedStringArray(["Content-Type: application/json"])
    if auth_token != "":
        headers.append("Authorization: Bearer " + auth_token)
    _http.request(api_base + path, headers, HTTPClient.METHOD_POST, JSON.stringify(body))
```

**请求完成处理**：
- 2xx：JSON 解析 → 调用 `callback(data)`
- 非 2xx：发射 `api_error(code, body_text)` 信号

### 5.2 API 端点

| 方法 | 路径 | Body | 响应 | 典型用法 |
|------|------|------|------|----------|
| `GET` | `/scenarios?user_id=` | — | `[{id, title, ...}]` | 主菜单点击"开始训练" |
| `POST` | `/scenarios/start` | `{user_id, scenario_id}` | `{scenario_id, step_index, ...prompt, options}` | 关卡选择点击卡片 |
| `POST` | `/scenarios/answer` | `{user_id, option_index}` | `{is_correct, feedback, points...}` | 选择答案 |
| `GET` | `/scenarios/progress/{uid}` | — | `{progress...}` | （预留）进度查询 |

### 5.3 响应数据结构

**`/scenarios/start` 响应**：
```json
{
    "scenario_id": "C001",
    "title": "刷单返利识别",
    "difficulty": "easy",
    "case_brief": "你收到一条短信...",
    "step_index": 0,
    "total_steps": 5,
    "step_type": "recognize",
    "teaching_point": "刷单返利的典型特征...",
    "prompt": "以下哪项是刷单诈骗的常见手法？",
    "options": [
        {"text": "先垫付小额资金", "is_correct": true},
        {"text": "对方直接送你钱", "is_correct": false}
    ],
    "lives": 3
}
```

**`/scenarios/answer` 响应**：
```json
{
    "is_correct": true,
    "is_partial": false,
    "feedback": "正确！刷单诈骗的核心套路就是先让你尝到甜头...",
    "points_gained": 10,
    "total_points": 50,
    "step_index": 1,
    "lives": 3,
    "streak": 2,
    "finished": false,
    "game_over": false
}
```

---

## 6. 场景间信号通信流

```
┌──────────────────────────────────────────────────────┐
│                    GameManager (Autoload)              │
│  信号: scenario_list_loaded / scenario_started         │
│        answer_received / level_completed / api_error   │
└──────┬──────────────────────┬─────────────────────────┘
       │                      │
       ▼                      ▼
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│  MainMenu   │       │ LevelSelect │       │  GameScene  │
│  监听:      │       │ 监听:       │       │ 监听:       │
│  · loaded   │       │ · loaded    │       │ · started   │
│  · error    │       │ · completed │       │ · answer    │
│             │       │             │       │ · completed │
│  发射:      │       │  发射:      │       │ · error     │
│  (无)       │       │  (无)       │       │             │
└─────────────┘       └─────────────┘       └─────────────┘

流程：
1. MainMenu 点击 → fetch_scenarios() → loaded 信号 → 切换 LevelSelect
2. LevelSelect 点击卡片 → start_scenario(id) → GameScene 显示
3. GameScene 答题 → answer_question(i) → answer 信号 → 显示反馈
4. 全部答完 → completed 信号 → GameScene 显示通关面板 + LevelSelect 刷新
```

---

## 7. 快速开始

### 7.1 环境要求

| 工具 | 版本 | 说明 |
|------|------|------|
| Godot Engine | 4.2+ (推荐 4.4) | 编辑器 + 运行时 |
| 后端服务 | anti_fraud_system | FastAPI 运行在 `http://127.0.0.1:8000` |
| 浏览器 | Chrome / Firefox / Edge | Web 导出模式 |

### 7.2 用 Godot 编辑器打开

```bash
# 1. 下载 Godot 4.x
#    https://godotengine.org/download

# 2. 打开项目
#    方法 A：Godot 项目管理器 → Import → 选择 godot_game/ 目录
#    方法 B：命令行
Godot_v4.x.exe --path /path/to/godot_game/
```

### 7.3 运行和调试

- **编辑器内运行**：按 `F5`（或点击右上角"播放"按钮）
- **独立场景运行**：打开 `.tscn` 文件后按 `F6`
- **查看日志**：编辑器底部 `Output` 面板（GameManager 使用 `printerr()` 输出调试信息）

### 7.4 导出为 HTML5（Web）

```
1. 编辑器菜单: Project → Export...
2. 点击 Add... → 选择 Web
3. 配置导出模板（首次需下载 HTML5 模板）
4. 输出路径: godot_game/export/index.html
5. 点击 Export Project

导出产物：
  godot_game/export/
  ├── index.html      # Web 入口文件
  ├── index.js        # Godot JavaScript 桥接
  ├── index.wasm      # WebAssembly 引擎
  └── index.pck       # 打包的场景和资源
```

### 7.5 嵌入现有网页

将 `export/` 目录复制到 `app/web/godot_export/`（或后端静态文件目录），在前端页面中嵌入：

```html
<div id="godot-game-container"
     style="width:100%; height:620px; border-radius:12px; overflow:hidden;">
  <iframe src="/static/godot_export/index.html"
          width="100%" height="100%" frameborder="0"
          allow="autoplay; fullscreen"></iframe>
</div>
```

Godot 游戏会通过 `JavaScriptBridge` 自动从浏览器 `localStorage` 读取 `anti_fraud_token`，与网页端登录状态保持一致。

---

## 8. 配置说明

### 8.1 `project.godot` 关键配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `config/name` | `"反诈护盾实战训练"` | 窗口标题 |
| `config/version` | `"1.0.0"` | 应用版本 |
| `config/features` | `PackedStringArray("4.6")` | 目标 Godot 功能版本 |
| `config/icon` | `"res://assets/ui/icon.svg"` | 应用图标 |
| `run/main_scene` | `"res://scenes/main_menu.tscn"` | 启动时加载的第一个场景 |
| `window/size/viewport_width` | `1024` | 默认窗口宽度 |
| `window/size/viewport_height` | `720` | 默认窗口高度 |
| `window/stretch/mode` | `"canvas_items"` | 窗口拉伸模式 |
| `html/canvas_resize_policy` | `2` | Web: Canvas 自适应 |
| `html/experimental_virtual_keyboard` | `true` | Web: 虚拟键盘支持 |
| `renderer/rendering_method` | `"gl_compatibility"` | GLES2 兼容模式（Web 导出必须） |
| `environment/default_clear_color` | `Color(0.06, 0.125, 0.22, 1)` | 背景清屏色 |

### 8.2 修改 API 地址

编辑 `scripts/game_manager.gd` 第 14 行：

```gdscript
# 本地开发
var api_base: String = "http://127.0.0.1:8000"

# 生产环境（示例）
# var api_base: String = "https://your-server.com/api"
```

---

## 9. 关卡数据说明

### 9.1 15 关完整列表

| ID | 诈骗类型 (scam_type) | 难度 | 步数 | 说明 |
|----|---------|------|------|------|
| C001 | 刷单返利 (shuadan_rebate) | 🟢 初级 | 4 | 4R 入门教程关 |
| C002 | 游戏交易 (game_trade) | 🟢 初级 | 4 | 虚拟物品交易陷阱（已补全为完整 4R） |
| C003 | 校园贷 (campus_loan) | 🟢 初级 | 4 | 放款前收费识别（已补全为完整 4R） |
| C004 | 冒充公检法 (fake_authority) | 🟡 中级 | 3 | 三幕高压攻防战 |
| C005 | 杀猪盘 (fake_investment) | 🟡 中级 | 3 | 养猪→喂猪→杀猪生命周期 |
| C006 | 冒充客服退款 (fake_refund_customer_service) | 🟡 中级 | 3 | 物流理赔信息战 |
| C007 | 冒充熟人 (acquaintance_impersonation) | 🔴 高级 | 3 | 情感绑架 + 多通道验证 |
| C008 | 裸聊敲诈 (sextortion) | 🔴 高级 | 3 | 羞耻感操控破解 |
| C009 | AI 语音克隆 (ai_deepfake) | 🔴 高级 | 3 | 跨人物交叉验证 |
| C010 | 杀猪盘全链条 (fake_investment) | 🔴 高级 | 3 | 情感操纵系统瓦解 |
| C011 | 校园贷/套路贷 (campus_loan) | 🟡 中级 | 3 | 砍头息与以贷养贷 |
| C012 | 综合实战 (mixed) | 🔴 高级 | 3 | 终极 Boss：多源信息轰炸 |
| C013 | 注销校园贷 (cancel_loan_scam) | 🟡 中级 | 3 | 毕业季"征信恐吓"骗局 |
| C014 | 冒充领导 (boss_impersonation) | 🟡 中级 | 3 | 职场权威服从陷阱 |
| C015 | 虚假网购 (fake_shopping) | 🟢 初级 | 3 | 超低价 + 脱离平台 + 返现 |

> 解锁依赖（`unlock_requires`）：C013←C003、C014←C002、C015 无依赖（入门即玩）；终极关 C012 需通关 C007/C008/C009/C010/C011。

### 9.2 数据类型

关卡配置存储在后端 `scenarios.json` 中，`GameManager.fetch_scenarios()` 从 API 获取。每个关卡的 key：

```json
{
    "id": "C001",
    "title": "刷单返利识别",
    "description": "学会识别刷单诈骗的经典套路",
    "difficulty": "easy",
    "step_count": 5,
    "unlocked": true,
    "completed": false,
    "best_stars": 0
}
```

---

## 10. 故障排查

### 10.1 场景文件解析失败

**症状**：Godot 编辑器打开 `.tscn` 文件时报错

**常见原因**：
| 原因 | 检查方法 | 修复 |
|------|----------|------|
| 缺少 `[ext_resource]` 声明 | 搜索文件中 `ExtResource("X")` 引用，确认 `id="X"` 的声明存在 | 补全缺失的资源声明 |
| `load_steps` 数量不对 | 数 `load_steps` 应为 ext数 + sub数 + 1（场景） | 修正为正确值 |
| 引用资源文件不存在 | 检查 `path="res://..."` 指向的实际文件 | 修正路径或恢复文件 |
| 未使用的 `[sub_resource]` | 搜索 `SubResource("X")` 无引用 | 可安全删除 |

### 10.2 按钮/信号无响应

- 检查 `@onready` 节点路径是否与实际节点名一致（区分大小写）
- 检查 `pressed.connect()` 是否在 `_ready()` 中调用
- 检查事件处理函数是否有 `while _is_showing_feedback` 之类的状态锁

### 10.3 API 连接失败

- **桌面模式**：确认 FastAPI 后端运行在 `http://127.0.0.1:8000`
- **Web 模式**：检查浏览器 Console 是否有 CORS 错误；确认 API 地址在该环境下可访问
- 观察 Godot 编辑器 `Output` 面板的 `[GameManager]` 日志

### 10.4 Web 导出白屏

- 确认渲染后端为 `gl_compatibility`（非 `forward_plus` 或 `mobile`）
- 确认 HTML5 导出模板已正确安装
- 检查浏览器 WebAssembly 支持（Chrome 57+ / Firefox 52+）

---

## 11. 开发注意事项

1. **GDScript 2.0 类型约定**：所有变量和函数参数必须有显式类型声明（已全局配置 `strict` 模式）
2. **信号命名**：使用 `snake_case`，文档注释使用 `##`
3. **节点引用**：只能通过 `@onready var` 在 `_ready()` 中获取，不得在 `_init()` 中访问节点树
4. **API 地址**：修改 `game_manager.gd` 第 14 行的 `api_base` 变量
5. **新增关卡**：在后端 `scenarios.json` 中添加配置 → `GameManager.fetch_scenarios()` 自动拉取
6. **新增场景**：在 `project.godot` 中无需注册（`change_scene_to_file()` 按路径加载）
7. **样式**：深蓝主题色 `Color(0.06, 0.125, 0.22, 1)`；文字色 `Color(1, 1, 1, x)` 通过 alpha 控制亮度

---

## 12. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-05 | 初始版本：3 个场景 + 4 个脚本 + 12 关关卡数据 |
| 1.1.0 | 2026-05 | 修复最后一题"反馈面板"与"结算面板"同帧叠加的显示问题（结算改为读完反馈后点击「继续」再弹出）；修复 `_shake()` 向 `randi_range` 传入浮点数的类型问题。游戏增强：① 答题支持键盘 `1~9` 选项 / `Enter`·`Space` 继续；② 连击 ≥3 触发上浮"连击 xN"特效；③ 通关战报显示正确率/剩余生命/累计积分；④ 游戏场景 CRT 扫描线氛围；⑤ 关卡选择新增总进度卡片、按难度分组、总星数、锁定关卡的前置提示；⑥ 主菜单新增数据流动画背景、标题呼吸光、反诈提示轮播。 |
| 1.2.0 | 2026-05 | 关卡内容扩充：12 关 → 15 关。① 将 `C002`（游戏交易）、`C003`（校园贷）由 2 步补全为完整的 4R 结构（识破→推理→行动→复盘）；② 新增 `C013` 注销校园贷"征信恐吓"、`C014` 冒充领导转账、`C015` 虚假低价网购+返现三关。后端数据位于 `app/data/scenarios.json`，游戏通过 `/scenarios` 动态拉取，无需改 Godot 代码即可生效（Web 端仍需重新导出以更新计数等静态文案）。 |
| 1.3.0 | 2026-05 | **核心玩法重做 + 彻底解决乱码**。① 乱码根因：`zh_font.ttf` 不含彩色 emoji（🔍🧠⚔⚡❤✓✗⭐🟢🔒… 全部缺字形 → 方块乱码）。新增 `GameManager.clean()` 在渲染时剥离字体不支持的 emoji/符号，并把全部 UI 的 emoji 替换为字体已含的字形（`● ▲ ◆ ■ ★ ☆ → ①②③`）与代码绘制图形。② `game.tscn` / `game_scene.gd` 重做为**聊天对战式**：诈骗方消息带"正在输入…"+打字机逐字浮现；玩家以聊天气泡回击；分析师按对错变色点评；顶部绘制式防御值（◆）、连击、积分、进度条；每题响应计时（超时给分析师提示，不强制提交）；答对粒子迸发、答错抖动；结算按正确率+反应速度评 S/A/B/C 级并显示星级与战报。③ `level_select` 状态图标/星级去 emoji。无需改后端。 |

> ⚠️ 修改脚本后需在 Godot 编辑器中重新导出 Web（菜单 → 项目 → 导出 → Web），导出产物会覆盖 `app/web/godot_export/`，否则网页加载的仍是旧版本。
