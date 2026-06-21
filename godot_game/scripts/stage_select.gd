## stage_select.gd — 诈骗拦截大作战 · 关卡选择
## 展示战役关卡（主题 / 目标 / 最佳星级 / 解锁状态）+ 无尽模式入口。
## 进度存于 user://（GameManager.load_game_save）。
extends Control

const T = GameManager.PixelTheme

@onready var back: Button         = $Header/BackButton
@onready var title_lbl: Label     = $Header/Title
@onready var endless: Button      = $Header/EndlessButton
@onready var list: VBoxContainer  = $Scroll/List


func _ready() -> void:
	_style()
	back.pressed.connect(func(): GameManager.go_to("res://scenes/main_menu.tscn"))
	endless.pressed.connect(_start_endless)
	_build()


func _style() -> void:
	var bg := get_node_or_null("Background")
	if bg is ColorRect: bg.color = T.BG0
	title_lbl.add_theme_color_override("font_color", T.TX1)
	_btn(back, T.CYA)
	_btn(endless, T.ORG)


func _btn(b: Button, c: Color) -> void:
	b.add_theme_stylebox_override("normal",  T.box(c.darkened(0.55), c, 2))
	b.add_theme_stylebox_override("hover",   T.box(c.darkened(0.4), c.lightened(0.2), 2))
	b.add_theme_stylebox_override("pressed", T.box(c.darkened(0.65), c, 2))
	b.add_theme_color_override("font_color", c.lightened(0.3))
	b.add_theme_color_override("font_hover_color", T.TX1)
	b.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND


func _build() -> void:
	for c in list.get_children():
		c.queue_free()
	var save := GameManager.load_game_save()
	var cleared := 0
	var stars_total := 0
	for s in GameManager.STAGES:
		if int(save.get(str(s.get("id", "")), 0)) > 0:
			cleared += 1
		stars_total += int(save.get(str(s.get("id", "")), 0))
	title_lbl.text = "诈骗拦截 · 选择关卡    ★%d · 已通关 %d/%d" % [stars_total, cleared, GameManager.STAGES.size()]

	list.add_child(_records_card())

	var idx := 0
	for s in GameManager.STAGES:
		var card := _stage_card(idx, s, save)
		list.add_child(card)
		card.modulate.a = 0.0
		card.scale = Vector2(0.97, 0.97)
		var tw := create_tween().set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
		tw.tween_interval(0.04 * idx)
		tw.tween_property(card, "modulate:a", 1.0, 0.2)
		tw.parallel().tween_property(card, "scale", Vector2.ONE, 0.2)
		idx += 1


func _stage_card(idx: int, s: Dictionary, save: Dictionary) -> Control:
	var sid := str(s.get("id", ""))
	var unlocked := GameManager.stage_unlocked(idx)
	var stars := int(save.get(sid, 0))
	var accent: Color = GameManager.theme_color(str(s.get("theme", "cya")))
	var bc: Color = accent if unlocked else T.TX3

	var card := PanelContainer.new()
	card.custom_minimum_size = Vector2(0, 96)
	var sty := T.box(T.BG2, bc, 1)
	sty.border_width_left = 5
	sty.content_margin_left = 14; sty.content_margin_right = 14
	sty.content_margin_top = 12; sty.content_margin_bottom = 12
	card.add_theme_stylebox_override("panel", sty)

	var sty_hov := T.box(T.BG3, bc.lightened(0.25), 1)
	sty_hov.border_width_left = 5
	sty_hov.content_margin_left = 14; sty_hov.content_margin_right = 14
	sty_hov.content_margin_top = 12; sty_hov.content_margin_bottom = 12

	var hb := HBoxContainer.new()
	hb.add_theme_constant_override("separation", 14)
	card.add_child(hb)

	# 关序号圆牌
	var num := Label.new()
	num.text = str(idx + 1)
	num.custom_minimum_size = Vector2(46, 0)
	num.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	num.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	num.add_theme_font_size_override("font_size", 30)
	num.add_theme_color_override("font_color", bc)
	GameManager.apply_font(num)
	hb.add_child(num)

	# 文本区
	var vb := VBoxContainer.new()
	vb.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vb.add_theme_constant_override("separation", 4)
	hb.add_child(vb)

	var tl := Label.new()
	tl.text = "第 %d 关 · %s" % [idx + 1, GameManager.clean(str(s.get("name", "")))]
	tl.add_theme_font_size_override("font_size", 17)
	tl.add_theme_color_override("font_color", T.TX1)
	GameManager.apply_font(tl)
	vb.add_child(tl)

	var ml := Label.new()
	ml.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	if unlocked:
		ml.text = GameManager.clean(str(s.get("intro", "")))
		ml.add_theme_color_override("font_color", T.TX2)
	else:
		ml.text = "未解锁 · 先通关「第 %d 关」" % idx
		ml.add_theme_color_override("font_color", T.MAG)
	ml.add_theme_font_size_override("font_size", 12)
	GameManager.apply_font(ml)
	vb.add_child(ml)

	var info := Label.new()
	info.text = "目标 清理 %d 条 · 防御 %d · 时限 %.1f 秒" % [int(s.get("goal", 10)), int(s.get("lives", 3)), float(s.get("time", 5.0))]
	info.add_theme_font_size_override("font_size", 11)
	info.add_theme_color_override("font_color", T.TX3)
	GameManager.apply_font(info)
	vb.add_child(info)

	# 星级
	var sl := Label.new()
	sl.text = "★".repeat(stars) + "☆".repeat(max(0, 3 - stars))
	sl.add_theme_font_size_override("font_size", 17)
	sl.add_theme_color_override("font_color", T.YEL if stars > 0 else T.TX3)
	sl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	GameManager.apply_font(sl)
	hb.add_child(sl)

	if unlocked:
		card.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
		card.mouse_entered.connect(func(): card.add_theme_stylebox_override("panel", sty_hov))
		card.mouse_exited.connect(func(): card.add_theme_stylebox_override("panel", sty))
		card.gui_input.connect(func(ev: InputEvent):
			if ev is InputEventMouseButton and ev.pressed and ev.button_index == MOUSE_BUTTON_LEFT:
				_start_stage(idx))
	else:
		card.modulate = Color(1, 1, 1, 0.4)
	return card


func _start_stage(idx: int) -> void:
	GameManager.game_mode = "campaign"
	GameManager.game_stage = idx
	if idx == 0:
		GameManager.campaign_used_texts.clear()
	GameManager.go_to("res://scenes/game.tscn")


func _start_endless() -> void:
	GameManager.game_mode = "endless"
	GameManager.go_to("res://scenes/game.tscn")


## 个人纪录卡：无尽模式本地最高分榜
func _records_card() -> Control:
	var card := PanelContainer.new()
	var sty := T.box(T.BG2, T.ORG, 1)
	sty.border_width_left = 5
	sty.content_margin_left = 14; sty.content_margin_right = 14
	sty.content_margin_top = 12; sty.content_margin_bottom = 12
	card.add_theme_stylebox_override("panel", sty)

	var vb := VBoxContainer.new()
	vb.add_theme_constant_override("separation", 6)
	card.add_child(vb)

	var t := Label.new()
	t.text = "个人纪录 · 无尽模式最高分榜"
	t.add_theme_color_override("font_color", T.ORG)
	t.add_theme_font_size_override("font_size", 15)
	GameManager.apply_font(t)
	vb.add_child(t)

	var scores := GameManager.endless_scores()
	if scores.is_empty():
		var e := Label.new()
		e.text = "还没有无尽模式成绩，去右上角「无尽模式」挑战一下吧！"
		e.add_theme_color_override("font_color", T.TX2)
		e.add_theme_font_size_override("font_size", 12)
		GameManager.apply_font(e)
		vb.add_child(e)
	else:
		var n: int = min(5, scores.size())
		for i in n:
			var row := Label.new()
			row.text = "  %d.  %d 分    评级 %s" % [i + 1, int(scores[i].get("score", 0)), str(scores[i].get("rating", ""))]
			row.add_theme_color_override("font_color", T.TX1 if i == 0 else T.TX2)
			row.add_theme_font_size_override("font_size", 13)
			GameManager.apply_font(row)
			vb.add_child(row)
	return card
