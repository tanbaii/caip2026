## GameManager — Autoload 全局管理器
## 职责: 主题定义 + API 通信 + 状态缓存 + 场景切换
extends Node

# ── 信号 ──
signal scenario_list_loaded(scenarios: Array[Dictionary])
signal scenario_started(data: Dictionary)
signal answer_received(data: Dictionary)
signal api_error(code: int, message: String)
signal level_completed(scenario_id: String, stars: int, score: int)

# ── 用户态 ──
var user_id: int = 0
var api_base: String = "http://127.0.0.1:8000"
var auth_token: String = ""

# ── 关卡态 ──
var scenario_catalog:  Array[Dictionary] = []
var active_scenario_id: String = ""
var current_step: int = 0
var total_steps: int = 0
var lives: int = 3
var streak: int = 0
var correct_count: int = 0
var total_points: int = 0
var last_scenario_payload: Dictionary = {}

# ── 诈骗拦截大作战：模式与关卡 ──
var game_mode: String = "campaign"   # "campaign"（关卡战役）/ "endless"（无尽）
var game_stage: int = 0              # 当前战役关卡索引

## 战役模式已用卡牌文本（关卡间去重）
var campaign_used_texts: PackedStringArray = []

# ── HTTP ──
var _http: HTTPRequest
var _cb: Callable
var _cb_method: String = ""
var _http_busy: bool = false

# ── 场景过渡 ──
var _mx: CanvasLayer
var _mx_rect: ColorRect
var _mx_tween: Tween
var _mx_busy: bool = false


# ═══════════════════════════════════════
#  像素主题 — 全局色板
# ═══════════════════════════════════════
class PixelTheme:
	const BG0  = Color("090d14")   # 最暗
	const BG1  = Color("0f1923")   # 深蓝黑
	const BG2  = Color("1a2a3a")   # 卡片
	const BG3  = Color("243447")   # 悬停

	const GRE  = Color("00e676")   # 成功
	const CYA  = Color("00c8ff")   # 信息
	const MAG  = Color("ff3d80")   # 危险
	const YEL  = Color("ffcf00")   # 警告
	const ORG  = Color("ff7a00")   # 强调

	const TX1  = Color("ebf0f6")   # 主文字
	const TX2  = Color("8090a8")   # 次文字
	const TX3  = Color("445566")   # 暗文字

	const BOR  = Color("1c3040")   # 普通边框
	const BOR_H = Color("3a6080")  # 悬停边框

	const PX   = 0                 # 圆角 = 0 (像素风)
	const BW   = 1                 # 默认边框宽

	const DIF_LABEL = {"easy":"初级","medium":"中级","hard":"高级"}
	const DIF_COLOR = {"easy":GRE,"medium":YEL,"hard":MAG}
	const STEP_ICON = {"recognize":"●","reason":"▲","act":"◆","reflect":"■"}
	const STEP_NAME = {"recognize":"识破","reason":"分析","act":"反击","reflect":"复盘"}

	## 创建一个带背景色和边框的 StyleBoxFlat (像素风方角)
	static func box(bg: Color, bc: Color, bw: int = BW) -> StyleBoxFlat:
		var s := StyleBoxFlat.new()
		s.bg_color = bg; s.border_color = bc
		s.set_border_width_all(bw)
		return s


# ═══════════════════════════════════════
#  关卡战役配置 + 本地存档（诈骗拦截大作战）
# ═══════════════════════════════════════
## 每关：id / 名称 / 主题色键 / 关前提示 / 涉及诈骗类别(空=全部) / 卡牌渠道过滤(空=全部) / 通关目标(清理张数) / 防御值 / 单卡基准时限(秒)
const STAGES = [
	{"id": "S1", "name": "短信风暴",   "theme": "cya", "intro": "伪基站短信轮番轰炸——看清链接与套路，别手滑。",      "cats": ["钓鱼短信", "刷单返利", "中奖免费送", "虚假贷款", "机票退改签"], "kinds": ["短信"], "goal": 10, "lives": 3, "time": 5.5},
	{"id": "S2", "name": "来电惊魂",   "theme": "mag", "intro": "陌生来电步步紧逼——沉住气，公检法没有安全账户。",    "cats": ["冒充公检法", "冒充客服理赔", "冒充客服扣费", "快递理赔"],     "kinds": ["来电"], "goal": 10, "lives": 3, "time": 5.0},
	{"id": "S3", "name": "熟人迷局",   "theme": "org", "intro": "领导、老师、老同学？凡涉钱，先核实再说。",          "cats": ["冒充熟人", "冒充领导", "冒充老师收费"],                    "kinds": ["好友", "群消息"], "goal": 9,  "lives": 3, "time": 4.8},
	{"id": "S4", "name": "财路陷阱",   "theme": "yel", "intro": "高收益、内部消息、注销账户……稳住你的钱袋子。",   "cats": ["虚假投资", "杀猪盘", "解冻民族资产", "注销校园贷"],         "kinds": [], "goal": 10, "lives": 3, "time": 4.5},
	{"id": "S5", "name": "全面突击",   "theme": "gre", "intro": "各类骗局混合来袭，全凭你的真功夫！",                 "cats": [],                                                          "kinds": [], "goal": 14, "lives": 3, "time": 4.0},
	{"id": "S6", "name": "BOSS·诈骗集团", "theme": "mag", "intro": "诈骗集团总攻！防御仅 2 点，节奏极快，证明你是反诈高手！", "cats": [],                                                     "kinds": [], "goal": 18, "lives": 2, "time": 3.3},
]

const SAVE_PATH := "user://interceptor_save.json"

static func theme_color(key: String) -> Color:
	match key:
		"cya": return PixelTheme.CYA
		"mag": return PixelTheme.MAG
		"org": return PixelTheme.ORG
		"yel": return PixelTheme.YEL
		"gre": return PixelTheme.GRE
		_: return PixelTheme.CYA

func load_game_save() -> Dictionary:
	if not FileAccess.file_exists(SAVE_PATH):
		return {}
	var f := FileAccess.open(SAVE_PATH, FileAccess.READ)
	if f == null:
		return {}
	var txt := f.get_as_text()
	f.close()
	var j := JSON.new()
	if j.parse(txt) == OK and typeof(j.data) == TYPE_DICTIONARY:
		return j.data
	return {}

func save_stage_result(stage_id: String, stars: int) -> void:
	var d := load_game_save()
	if stars > int(d.get(stage_id, 0)):
		d[stage_id] = stars
		var f := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
		if f:
			f.store_string(JSON.stringify(d))
			f.close()

func stage_unlocked(idx: int) -> bool:
	if idx <= 0:
		return true
	if idx >= STAGES.size():
		return false
	var prev_id := str(STAGES[idx - 1].get("id", ""))
	return int(load_game_save().get(prev_id, 0)) > 0

## 无尽模式本地最高分榜（保存前 8 名）。返回本次成绩的名次（1 起；0 表示未进榜）
func add_endless_score(score: int, rating: String) -> int:
	var d := load_game_save()
	var arr: Array = d.get("endless", [])
	arr.append({"score": score, "rating": rating})
	arr.sort_custom(func(a, b): return int(a.get("score", 0)) > int(b.get("score", 0)))
	if arr.size() > 8:
		arr = arr.slice(0, 8)
	d["endless"] = arr
	var f := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(d))
		f.close()
	for i in arr.size():
		if int(arr[i].get("score", 0)) == score:
			return i + 1
	return 0

func endless_scores() -> Array:
	return load_game_save().get("endless", [])

func best_endless() -> int:
	var arr := endless_scores()
	return int(arr[0].get("score", 0)) if arr.size() > 0 else 0


# ═══════════════════════════════════════
#  初始化
# ═══════════════════════════════════════

func _ready() -> void:
	_http = HTTPRequest.new()
	add_child(_http)
	_http.request_completed.connect(_on_http_done)

	# 场景过渡遮罩
	_mx = CanvasLayer.new(); _mx.layer = 128; add_child(_mx)
	_mx_rect = ColorRect.new()
	_mx_rect.color = Color(0, 0, 0, 0)
	_mx_rect.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_mx_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_mx.add_child(_mx_rect)

	_init_theme()
	if OS.has_feature("web"):
		_configure_web_api_base()
		_read_web_token()
		_listen_web_msg()


func _configure_web_api_base() -> void:
	var origin: Variant = JavaScriptBridge.eval("window.location.origin", true)
	if origin != null and str(origin) != "" and str(origin) != "null":
		api_base = str(origin)


## 缓存字体引用，供动态创建的 Label 显式设置（CanvasLayer 不继承主题）
var cached_font: Font = null

## 为动态创建的 Control 节点显式设置字体
func apply_font(node: Control) -> void:
	if cached_font != null:
		node.add_theme_font_override("font", cached_font)

func _init_theme() -> void:
	## 根视口设字体 + 背景色 — 不碰按钮样式，引擎默认主题负责控件外观
	var fnt: Font = load("res://assets/ui/zh_font.ttf")
	if fnt == null: return
	cached_font = fnt
	var t := Theme.new()
	t.default_font = fnt
	t.default_font_size = 14
	t.set_color("font_color", "Label", PixelTheme.TX1)
	get_tree().root.theme = t


func _read_web_token() -> void:
	var v: Variant = JavaScriptBridge.eval("localStorage.getItem('anti_fraud_token') || ''", true)
	if v != null and str(v) != "":
		auth_token = str(v)
		var sub := jwt_sub(auth_token)
		if sub > 0:
			user_id = sub

## 重新从浏览器读取登录态（token / postMessage 同步的 user_id）——
## 网页常常在 iframe 加载后才登录，启动时读不到，需要在「开始」时再刷新一次
func refresh_web_auth() -> void:
	if not OS.has_feature("web"):
		return
	_read_web_token()
	sync_web_user_id()

func _listen_web_msg() -> void:
	JavaScriptBridge.eval(
		"window.addEventListener('message',function(e){" +
		"if(e.data&&e.data.type==='user_logged_in')window._godot_uid=e.data.user_id;});", false)

func sync_web_user_id() -> void:
	if not OS.has_feature("web"):
		return
	var uid: Variant = JavaScriptBridge.eval("window._godot_uid||0", true)
	if uid != null and int(uid) > 0:
		user_id = int(uid)

func jwt_sub(token: String) -> int:
	var p := token.split(".")
	if p.size() < 2:
		return 0
	var payload := p[1].replace("-", "+").replace("_", "/")
	while payload.length() % 4 != 0:
		payload += "="
	var j := JSON.new()
	if j.parse(Marshalls.base64_to_utf8(payload)) == OK:
		return int(j.data.get("sub", 0))
	return 0


## 去除字体不支持的 emoji / 符号（zh_font.ttf 不含彩色 emoji，否则显示为乱码方块）
## 保留 CJK、①-⑤、★☆、几何符号 ●▲◆■ 等字体已包含的字形
static func clean(text: String) -> String:
	if text == "":
		return text
	var out := ""
	for i in text.length():
		var c := text.unicode_at(i)
		if c >= 0x1F000:                       # 所有 emoji / 补充符号平面
			continue
		if c >= 0x2600 and c <= 0x27BF:        # 杂项符号 + 装饰符（⚡⚔✓✗✦…），保留 ★☆
			if c == 0x2605 or c == 0x2606:
				out += String.chr(c)
			continue
		if c >= 0x2B00 and c <= 0x2BFF:        # ⭐⬛ 等
			continue
		if c >= 0xFE00 and c <= 0xFE0F:        # 变体选择符
			continue
		if c == 0x20E3 or c == 0x2049 or c == 0x203C:
			continue
		if c == 0x25B6 or c == 0x25B7 or c == 0x25B8 or c == 0x25B9 or c == 0x25C0:  # ▶▷▸ 等字体缺失
			continue
		out += String.chr(c)
	return out.strip_edges()


static func normalize_options(raw: Array) -> Array:
	var out: Array = []
	for item in raw:
		if typeof(item) == TYPE_STRING:
			out.append({"text": str(item)})
		elif typeof(item) == TYPE_DICTIONARY:
			out.append(item)
	return out


static func normalize_scenario_payload(data: Dictionary) -> Dictionary:
	var out := data.duplicate(true)
	if out.has("options"):
		out["options"] = normalize_options(out.get("options", []))
	return out


static func next_step_from_answer(data: Dictionary) -> Dictionary:
	var nested: Variant = data.get("next_step", {})
	if typeof(nested) == TYPE_DICTIONARY and not nested.is_empty():
		return normalize_scenario_payload(nested)
	var prompt: Variant = data.get("next_prompt", null)
	if prompt == null or str(prompt) == "":
		return {}
	return normalize_scenario_payload({
		"step_index": int(data.get("step_index", 0)) + 1,
		"step_type": str(data.get("next_step_type", "")),
		"teaching_point": str(data.get("next_teaching_point", "")),
		"prompt": str(prompt),
		"options": data.get("next_options", []),
	})


# ═══════════════════════════════════════
#  API
# ═══════════════════════════════════════

func api_get(path: String, cb: Callable) -> void:
	if _http_busy:
		api_error.emit(429, "请求进行中，请稍候")
		return
	_cb = cb; _cb_method = "GET"; _http_busy = true
	var h := _headers()
	_http.request(api_base + path, h, HTTPClient.METHOD_GET)

func _post(path: String, body: Dictionary, cb: Callable) -> void:
	if _http_busy:
		api_error.emit(429, "请求进行中，请稍候")
		return
	_cb = cb; _cb_method = "POST"; _http_busy = true
	_http.request(api_base + path, _headers(), HTTPClient.METHOD_POST, JSON.stringify(body))

func _headers() -> PackedStringArray:
	var h := PackedStringArray(["Content-Type: application/json"])
	if auth_token != "": h.append("Authorization: Bearer " + auth_token)
	return h

func _on_http_done(result: int, code: int, _h: PackedStringArray, body: PackedByteArray) -> void:
	_http_busy = false
	if result != HTTPRequest.RESULT_SUCCESS:
		api_error.emit(0, "网络请求失败")
		return
	var txt := body.get_string_from_utf8()
	if code >= 200 and code < 300:
		var j := JSON.new()
		_cb.call(j.data if j.parse(txt) == OK else {})
	else:
		api_error.emit(code, txt)


func fetch_scenarios() -> void:
	sync_web_user_id()
	if user_id <= 0:
		api_error.emit(401, "请先在网页端登录")
		return
	api_get("/scenarios?user_id=" + str(user_id), func(data: Variant):
		if typeof(data) == TYPE_ARRAY: scenario_catalog.assign(data)
		else: scenario_catalog.clear()
		scenario_list_loaded.emit(scenario_catalog))

func start_scenario(sid: String) -> void:
	sync_web_user_id()
	_post("/scenarios/start", {"user_id": user_id, "scenario_id": sid}, func(d: Dictionary):
		active_scenario_id = str(d.get("scenario_id", ""))
		current_step = int(d.get("step_index", 0))
		total_steps = int(d.get("total_steps", 1))
		lives = int(d.get("lives", 3))
		streak = 0; correct_count = 0
		last_scenario_payload = normalize_scenario_payload(d)
		scenario_started.emit(last_scenario_payload))

func answer(opt_idx: int) -> void:
	_post("/scenarios/answer", {"user_id": user_id, "option_index": opt_idx}, func(d: Dictionary):
		current_step = int(d.get("step_index", 0))
		lives = int(d.get("lives", 3))
		streak = int(d.get("streak", 0))
		total_points = int(d.get("total_points", 0))
		if d.get("is_correct", false): correct_count += 1
		if d.get("finished", false) and not d.get("game_over", false):
			level_completed.emit(active_scenario_id, d.get("stars", 0), d.get("points_gained", 0))
		answer_received.emit(d))


func unlocked_scenarios() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for s in scenario_catalog:
		if s.get("unlocked", false): out.append(s)
	return out


# ═══════════════════════════════════════
#  场景切换
# ═══════════════════════════════════════

func go_to(path: String, dur: float = 0.3) -> void:
	if _mx_busy: return
	_mx_busy = true
	if _mx_tween and _mx_tween.is_valid(): _mx_tween.kill()
	_mx_tween = create_tween()
	_mx_tween.tween_property(_mx_rect, "color:a", 1.0, dur)
	_mx_tween.tween_callback(func(): get_tree().change_scene_to_file(path))
	_mx_tween.tween_interval(0.05)
	_mx_tween.tween_property(_mx_rect, "color:a", 0.0, dur)
	_mx_tween.tween_callback(func(): _mx_busy = false)
