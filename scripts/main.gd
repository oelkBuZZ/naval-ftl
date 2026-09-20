extends Node2D

@onready var player_ship: PlayerShip = $PlayerShip
@onready var enemy_ship: EnemyShip = $EnemyShip
@onready var ui: Control = $UI
@onready var target_label: Label = $UI/TargetInfo
@onready var focus_label: Label = $UI/FocusInfo
@onready var controls_label: Label = $UI/ControlsInfo
@onready var enemy_hp_container: VBoxContainer = $UI/EnemyHPInfo

var current_focus_module: ShipModule = null
var player_ship_hp_bar: ProgressBar = null
var enemy_ship_hp_bar: ProgressBar = null
var focus_module_label: Label = null

func _ready():
	_setup_ship_hp_bars()
	_setup_focus_label()
	
	player_ship.set_focused_target(enemy_ship)
	enemy_ship.set_player_target(player_ship)
	
	_connect_enemy_modules()
	
	enemy_ship.ship_destroyed.connect(_on_enemy_destroyed)
	player_ship.ship_destroyed.connect(_on_player_destroyed)
	
	player_ship.overall_hp_changed.connect(_on_player_hp_changed)
	enemy_ship.overall_hp_changed.connect(_on_enemy_hp_changed)

func _setup_ship_hp_bars():
	# Player HP bar
	player_ship_hp_bar = ProgressBar.new()
	player_ship_hp_bar.position = Vector2(20, 100)
	player_ship_hp_bar.size = Vector2(300, 30)
	player_ship_hp_bar.show_percentage = false
	ui.add_child(player_ship_hp_bar)
	
	var player_hp_label = Label.new()
	player_hp_label.position = Vector2(20, 80)
	player_hp_label.text = "Player Ship HP:"
	player_hp_label.add_theme_font_size_override("font_size", 16)
	ui.add_child(player_hp_label)
	
	# Enemy HP bar
	enemy_ship_hp_bar = ProgressBar.new()
	enemy_ship_hp_bar.position = Vector2(900, 200)
	enemy_ship_hp_bar.size = Vector2(300, 30)
	enemy_ship_hp_bar.show_percentage = false
	ui.add_child(enemy_ship_hp_bar)
	
	var enemy_hp_label = Label.new()
	enemy_hp_label.position = Vector2(900, 180)
	enemy_hp_label.text = "Enemy Ship HP:"
	enemy_hp_label.add_theme_font_size_override("font_size", 16)
	ui.add_child(enemy_hp_label)

func _setup_focus_label():
	focus_module_label = Label.new()
	focus_module_label.position = Vector2(640, 50)
	focus_module_label.size = Vector2(400, 40)
	focus_module_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	focus_module_label.add_theme_font_size_override("font_size", 24)
	focus_module_label.add_theme_color_override("font_color", Color(1.0, 1.0, 0.3))
	focus_module_label.text = ""
	ui.add_child(focus_module_label)

func _on_player_hp_changed(current: float, max_hp: float):
	if player_ship_hp_bar:
		player_ship_hp_bar.max_value = max_hp
		player_ship_hp_bar.value = current

func _on_enemy_hp_changed(current: float, max_hp: float):
	if enemy_ship_hp_bar:
		enemy_ship_hp_bar.max_value = max_hp
		enemy_ship_hp_bar.value = current

func _connect_enemy_modules():
	for module in enemy_ship.modules:
		if module.is_clickable:
			module.module_clicked.connect(_on_enemy_module_clicked)

func _on_enemy_module_clicked(module: ShipModule):
	# Clear previous focus highlight
	if current_focus_module:
		current_focus_module.set_focused(false)
	
	current_focus_module = module
	player_ship.set_focus_fire_module(module)
	
	# Set new focus highlight
	module.set_focused(true)
	
	_update_focus_label()
	
	# Update the center focus label
	if focus_module_label:
		var module_name = _get_module_name(module.module_type)
		focus_module_label.text = "FOCUSED: %s" % module_name

func _process(_delta):
	_update_ui()

func _update_ui():
	if enemy_ship:
		target_label.text = "Target: Enemy Ship"
	else:
		target_label.text = "Target: None"
	
	_update_enemy_hp_display()

func _update_focus_label():
	if current_focus_module:
		var module_name = _get_module_name(current_focus_module.module_type)
		focus_label.text = "Focus Fire: %s (%.0f%% HP)" % [module_name, current_focus_module.get_hp_percent() * 100]
	else:
		focus_label.text = "Focus Fire: None (click enemy module)"

func _update_enemy_hp_display():
	for child in enemy_hp_container.get_children():
		child.queue_free()
	
	if not enemy_ship:
		return
	
	for module in enemy_ship.modules:
		var hp_label = Label.new()
		var module_name = _get_module_name(module.module_type)
		var hp_percent = module.get_hp_percent() * 100
		var fire_indicator = " [FIRE]" if module.is_on_fire else ""
		var offline_indicator = " [OFFLINE]" if module.is_offline else ""
		hp_label.text = "%s: %.0f%%%s%s" % [module_name, hp_percent, fire_indicator, offline_indicator]
		
		if module.is_offline:
			hp_label.modulate = Color.DIM_GRAY
		elif hp_percent < 25:
			hp_label.modulate = Color.RED
		elif hp_percent < 50:
			hp_label.modulate = Color.ORANGE
		elif module.is_on_fire:
			hp_label.modulate = Color.ORANGE_RED
		
		enemy_hp_container.add_child(hp_label)

func _get_module_name(module_type) -> String:
	match module_type:
		0: return "Hull"
		1: return "Citadel"
		2: return "Engine"
		3: return "Turret"
		_: return "Unknown"

func _on_enemy_destroyed():
	target_label.text = "ENEMY DESTROYED - Victory!"
	focus_label.text = ""
	if focus_module_label:
		focus_module_label.text = "VICTORY!"
		focus_module_label.add_theme_color_override("font_color", Color(0.3, 1.0, 0.3))
	if current_focus_module:
		current_focus_module.set_focused(false)

func _on_player_destroyed():
	target_label.text = "PLAYER DESTROYED - Defeat!"
	get_tree().paused = true
