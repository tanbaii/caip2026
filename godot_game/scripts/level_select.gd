## level_select.gd — 案件档案选择
extends Control

const T = GameManager.PixelTheme

@onready var list: VBoxContainer   = $ScrollContainer/ScenarioList
@onready var loading: Label       = $LoadingLabel
@onready var user_lbl: Label      = $TopBar/UserLabel
@onready var pts_lbl: Label       = $TopBar/PointsLabel
@onready var back: Button         = $TopBar/BackButton
@onready var title_lbl: Label     = $Title

var _title_map: Dictionary = {}


func _ready() -> void:
	_style()
	back.pressed.connect(func(): GameManager.go_to("res://scenes/main_menu.tscn"))
	GameManager.scenario_list_loaded.connect(draw_list)
	GameManager.level_completed.connect(func(_a,_b,_c): await get_tree().create_timer(0.3).timeout; _refresh())
	_refresh()


func _style() -> void:
	# 背景
	var bg := get_node_or_null("Background")
	if bg is ColorRect: bg.color = T.BG1

	# 返回按钮
	back.add_theme_stylebox_override("normal", T.box(T.BG2, T.BOR))
	back.add_theme_stylebox_override("hover",  T.box(T.BG3, T.CYA))
	back.add_theme_color_override("font_color", T.CYA)

	# 用户标签
	user_lbl.add_theme_color_override("font_color", T.GRE)
	pts_lbl.add_theme_color_override("font_color", T.YEL)
	title_lbl.add_theme_color_override("font_color", T.CYA)
	title_lbl.add_theme_font_size_override("font_size", 22)
	title_lbl.text = "案件档案库"


func _refresh() -> void:
	loading.show(); list.hide()
	GameManager.fetch_scenarios()
	if GameManager.user_id > 0:
		user_lbl.text = "AGENT #" + str(GameManager.user_id)
		pts_lbl.text = "积分 " + str(GameManager.total_points)


func draw_list(arr: Array) -> void:
	loading.hide(); list.show()
	for c in list.get_children(): c.queue_free()

	if arr.is_empty():
		var e := Label.new(); e.text = "暂无数据"; e.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		e.add_theme_color_override("font_color", T.TX3); list.add_child(e); return

	# ── 统计 + 标题映射 ──
	_title_map.clear()
	var done := 0
	var stars_total := 0
	for s in arr:
		_title_map[str(s.get("id", ""))] = str(s.get("title", ""))
		if s.get("completed", false): done += 1
		stars_total += int(s.get("best_stars", 0))

	title_lbl.text = "案件档案库   ★%d · 已破 %d/%d" % [stars_total, done, arr.size()]
	list.add_child(_summary_card(done, arr.size(), stars_total))

	# ── 按难度分组渲染 ──
	var groups := {"easy": [], "medium": [], "hard": []}
	for s in arr:
		var diff: String = s.get("difficulty", "easy")
		if not groups.has(diff): groups[diff] = []
		groups[diff].append(s)

	var idx := 0
	for diff in ["easy", "medium", "hard"]:
		var bucket: Array = groups.get(diff, [])
		if bucket.is_empty(): continue
		list.add_child(_section_header(diff, bucket.size()))
		for s in bucket:
			var card := _card(s)
			list.add_child(card)
			card.modulate.a = 0.0; card.scale = Vector2(0.95, 0.95)
			var tw := create_tween().set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
			tw.tween_interval(0.03 * idx)
			tw.tween_property(card, "modulate:a", 1.0, 0.2)
			tw.parallel().tween_property(card, "scale", Vector2.ONE, 0.2)
			idx += 1


## 顶部总进度卡片
func _summary_card(done: int, total: int, stars: int) -> Control:
	var card := PanelContainer.new()
	var sty := T.box(T.BG2, T.BOR)
	sty.content_margin_left = 12; sty.content_margin_right = 12
	sty.content_margin_top = 10; sty.content_margin_bottom = 10
	card.add_theme_stylebox_override("panel", sty)

	var vb := VBoxContainer.new()
	vb.add_theme_constant_override("separation", 6)
	card.add_child(vb)

	var lbl := Label.new()
	lbl.text = "训练进度   %d / %d 关已通关   ·   累计 ★%d / %d" % [done, total, stars, total * 3]
	lbl.add_theme_color_override("font_color", T.TX1)
	lbl.add_theme_font_size_override("font_size", 13)
	vb.add_child(lbl)

	var bar := ProgressBar.new()
	bar.custom_minimum_size = Vector2(0, 14)
	bar.show_percentage = false
	bar.max_value = max(1, total)
	bar.value = 0
	bar.add_theme_stylebox_override("background", T.box(T.BG0, T.BOR))
	var pf := StyleBoxFlat.new(); pf.bg_color = T.GRE
	bar.add_theme_stylebox_override("fill", pf)
	vb.add_child(bar)
	var tw := create_tween()
	tw.tween_property(bar, "value", float(done), 0.5).set_trans(Tween.TRANS_CUBIC)
	return card


## 难度分组标题
func _section_header(diff: String, n: int) -> Control:
	var lbl := Label.new()
	lbl.text = "  " + T.DIF_LABEL.get(diff, diff) + "   (" + str(n) + ")"
	lbl.add_theme_color_override("font_color", T.DIF_COLOR.get(diff, T.TX2))
	lbl.add_theme_font_size_override("font_size", 15)
	lbl.custom_minimum_size = Vector2(0, 28)
	lbl.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
	return lbl


func _card(d: Dictionary) -> Control:
	var unlocked: bool = d.get("unlocked", false)
	var completed: bool = d.get("completed", false)
	var stars: int = d.get("best_stars", 0)
	var diff: String = d.get("difficulty", "easy")
	var sid: String = d.get("id", "")

	var card := PanelContainer.new()
	card.custom_minimum_size = Vector2(0, 70)

	var bc: Color
	if completed:       bc = T.GRE
	elif unlocked:      bc = T.CYA
	else:               bc = T.TX3

	var sty := T.box(T.BG2, bc)
	sty.set_corner_radius_all(T.PX)
	sty.content_margin_left = 12; sty.content_margin_right = 12
	sty.content_margin_top = 8; sty.content_margin_bottom = 8
	card.add_theme_stylebox_override("panel", sty)

	# 悬停 (仅未锁定)
	var sty_hov: StyleBoxFlat = null
	if unlocked:
		sty_hov = T.box(T.BG3, bc.lightened(0.3))
		sty_hov.content_margin_left = 12; sty_hov.content_margin_right = 12
		sty_hov.content_margin_top = 8; sty_hov.content_margin_bottom = 8

	var hb := HBoxContainer.new()
	hb.add_theme_constant_override("separation", 12)
	card.add_child(hb)

	# 图标
	var ic := Label.new()
	ic.text = "●" if completed else ("○" if unlocked else "■")
	ic.add_theme_font_size_override("font_size", 20)
	ic.add_theme_color_override("font_color", bc)
	ic.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	ic.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	ic.custom_minimum_size = Vector2(34, 0)
	hb.add_child(ic)

	# 文本
	var vb := VBoxContainer.new()
	vb.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hb.add_child(vb)

	var tl := Label.new()
	tl.text = "CASE " + sid + "  " + GameManager.clean(str(d.get("title", "")))
	tl.add_theme_font_size_override("font_size", 15)
	tl.add_theme_color_override("font_color", T.TX1)
	vb.add_child(tl)

	var ml := Label.new()
	if not unlocked:
		ml.text = _lock_hint(d)
		ml.add_theme_color_override("font_color", T.MAG)
	else:
		ml.text = T.DIF_LABEL.get(diff, diff) + " · " + str(d.get("step_count", 0)) + "步 · " + GameManager.clean(str(d.get("description", "")))
		ml.add_theme_color_override("font_color", T.TX2)
	ml.add_theme_font_size_override("font_size", 12)
	vb.add_child(ml)

	# 星级
	if completed and stars > 0:
		var sl := Label.new()
		sl.text = "★".repeat(stars) + "☆".repeat(max(0, 3 - stars))
		sl.add_theme_color_override("font_color", T.YEL)
		sl.add_theme_font_size_override("font_size", 16)
		hb.add_child(sl)

	# 点击
	if unlocked:
		card.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
		card.mouse_entered.connect(func(): card.add_theme_stylebox_override("panel", sty_hov))
		card.mouse_exited.connect(func():  card.add_theme_stylebox_override("panel", sty))
		card.gui_input.connect(func(ev: InputEvent):
			if ev is InputEventMouseButton and ev.pressed and ev.button_index == MOUSE_BUTTON_LEFT:
				_start_scenario(sid)
		)
	else:
		card.modulate = Color(1, 1, 1, 0.35)

	return card


## 拼出锁定提示：需先通关哪些前置关卡
func _lock_hint(d: Dictionary) -> String:
	var reqs: Array = d.get("unlock_requires", [])
	if reqs.is_empty():
		return "暂未解锁"
	var names := PackedStringArray()
	for r in reqs:
		names.append(str(_title_map.get(str(r), str(r))))
	return "未解锁 · 需先通关：" + ", ".join(names)


func _start_scenario(sid: String) -> void:
	if not GameManager.scenario_started.is_connected(_on_scenario_ready):
		GameManager.scenario_started.connect(_on_scenario_ready, CONNECT_ONE_SHOT)
	if not GameManager.api_error.is_connected(_on_scenario_start_err):
		GameManager.api_error.connect(_on_scenario_start_err, CONNECT_ONE_SHOT)
	loading.show()
	loading.text = "加载关卡..."
	GameManager.start_scenario(sid)


func _on_scenario_ready(_data: Dictionary) -> void:
	GameManager.go_to("res://scenes/game.tscn")


func _on_scenario_start_err(_code: int, msg: String) -> void:
	loading.text = "加载失败: " + msg
	await get_tree().create_timer(2.0).timeout
	_refresh()
