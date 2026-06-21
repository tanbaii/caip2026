## main_menu.gd — 终端风主菜单
extends Control

# 颜色常量
const BG1 = Color("0f1923")
const BG0 = Color("090d14")
const BG2 = Color("1a2a3a")
const BG3 = Color("243447")
const GRE = Color("00e676")
const CYA = Color("00c8ff")
const TX1 = Color("ebf0f6")
const TX2 = Color("8090a8")
const TX3 = Color("445566")
const BOR = Color("1c3040")

static func box(bg: Color, bc: Color, bw: int = 1) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.border_color = bc
	s.set_border_width_all(bw)
	return s

@onready var icon: TextureRect = $VBox/Icon
@onready var title: Label = $VBox/Title
@onready var subtitle: Label = $VBox/Subtitle
@onready var uid_in: LineEdit = $VBox/UserInput
@onready var tok_in: LineEdit = $VBox/TokenInput
@onready var start: Button = $VBox/StartButton
@onready var status: Label = $VBox/StatusLabel
@onready var pbar: ProgressBar = $ProgressBar


const TIPS: Array[String] = [
	"提示：刷单返利「先垫付」一定是诈骗",
	"提示：公检法绝不会要求转账到「安全账户」",
	"提示：陌生链接、二维码不点不扫",
	"提示：网恋荐股、稳赚不赔 = 杀猪盘",
	"提示：要求保密、催促转账，就是危险信号",
	"提示：核实身份请挂断后用官方号码回拨",
]


func _ready() -> void:
	_style()
	_add_bg_fx()
	start.pressed.connect(_go)
	if pbar:
		pbar.hide()

	_pulse_title()
	_start_tips()

	var items: Array[Control] = [icon, title, subtitle, uid_in, tok_in, start]
	var d: float = 0.0
	for c in items:
		if c == null: continue
		c.scale = Vector2(0.8, 0.8)
		var tw := create_tween().set_trans(Tween.TRANS_ELASTIC).set_ease(Tween.EASE_OUT)
		tw.tween_interval(d)
		tw.tween_property(c, "scale", Vector2.ONE, 0.35)
		d += 0.06

	uid_in.placeholder_text = "输入用户 ID (数字)"

	if OS.has_feature("web"):
		# 网页可能在 iframe 加载后才登录，这里再刷新一次登录态
		GameManager.refresh_web_auth()
		if GameManager.user_id > 0:
			uid_in.text = str(GameManager.user_id)
			status.text = "> AGENT #" + str(GameManager.user_id) + " 已就绪"
		if GameManager.auth_token != "":
			tok_in.text = "已同步网页凭证"
			tok_in.editable = false
		else:
			tok_in.text = ""
			tok_in.placeholder_text = "未登录可直接输入上方用户 ID"
	else:
		tok_in.text = ""
		tok_in.placeholder_text = "Token (可选，桌面模式)"

	# 新版为自包含的「诈骗拦截大作战」反应游戏，无需登录即可开玩
	uid_in.hide()
	tok_in.hide()
	start.text = "开始拦截 →"
	status.text = "玩法：信息卡限时滑入，快判断  拦截(诈骗) / 放行(安全)"
	subtitle.text = "—— 诈骗拦截大作战 · 反应训练 ——"


func _style() -> void:
	title.add_theme_color_override("font_color", GRE)
	title.add_theme_font_size_override("font_size", 30)
	subtitle.add_theme_color_override("font_color", TX3)
	subtitle.add_theme_font_size_override("font_size", 13)
	for le in [uid_in, tok_in]:
		if le == null: continue
		le.add_theme_stylebox_override("normal", box(BG0, BOR, 2))
		le.add_theme_color_override("font_color", GRE)
		le.add_theme_color_override("font_placeholder_color", TX3)
	_bstyle(start, GRE)
	status.add_theme_color_override("font_color", TX2)
	if pbar:
		pbar.add_theme_stylebox_override("background", box(BG0, BOR))
		var pf := StyleBoxFlat.new()
		pf.bg_color = GRE
		pbar.add_theme_stylebox_override("fill", pf)
	var bg = get_node_or_null("Background")
	if bg is ColorRect:
		bg.color = BG1


## 背景数据流 + 标题脉冲 + 反诈提示轮播
func _add_bg_fx() -> void:
	for _i in 16:
		var col := ColorRect.new()
		col.color = Color(GRE.r, GRE.g, GRE.b, randf_range(0.02, 0.07))
		col.size = Vector2(randf_range(1.0, 2.0), randf_range(40.0, 120.0))
		col.position = Vector2(randf_range(0.0, 1024.0), randf_range(-200.0, 720.0))
		col.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(col)
		move_child(col, 1)
		var dur := randf_range(3.5, 7.5)
		var tw := create_tween().set_loops()
		tw.tween_property(col, "position:y", 760.0, dur).from(-150.0)


func _pulse_title() -> void:
	var tw := create_tween().set_loops().set_trans(Tween.TRANS_SINE)
	tw.tween_property(title, "modulate", Color(1, 1, 1, 0.65), 1.3)
	tw.tween_property(title, "modulate", Color(1, 1, 1, 1.0), 1.3)


func _start_tips() -> void:
	var tip := Label.new()
	tip.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	tip.offset_top = -44.0
	tip.offset_bottom = -16.0
	tip.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	tip.add_theme_color_override("font_color", CYA)
	tip.add_theme_font_size_override("font_size", 13)
	GameManager.apply_font(tip)
	tip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(tip)
	_cycle_tip(tip, 0)


func _cycle_tip(tip: Label, i: int) -> void:
	if not is_instance_valid(tip): return
	tip.text = TIPS[i % TIPS.size()]
	tip.modulate.a = 0.0
	var tw := create_tween()
	tw.tween_property(tip, "modulate:a", 1.0, 0.6)
	tw.tween_interval(3.2)
	tw.tween_property(tip, "modulate:a", 0.0, 0.6)
	tw.finished.connect(func(): _cycle_tip(tip, i + 1))


func _bstyle(btn: Button, c: Color) -> void:
	btn.add_theme_stylebox_override("normal",  box(c.darkened(0.5), c, 2))
	btn.add_theme_stylebox_override("hover",   box(c.darkened(0.35), c.lightened(0.2), 2))
	btn.add_theme_stylebox_override("pressed", box(c.darkened(0.6), c, 2))
	btn.add_theme_color_override("font_color", c)
	btn.add_theme_font_size_override("font_size", 16)


func _go() -> void:
	# 自包含反应游戏：无需登录，进入「关卡选择」（含关卡战役 + 无尽模式）
	if OS.has_feature("web"):
		GameManager.refresh_web_auth()
	start.disabled = true
	status.text = "> 进入关卡选择..."
	GameManager.go_to("res://scenes/stage_select.tscn")


