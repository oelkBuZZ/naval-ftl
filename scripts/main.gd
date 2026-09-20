extends Node2D

@onready var player_ship: PlayerShip = $PlayerShip
@onready var ui: Control = $UI
@onready var target_label: Label = $UI/TargetInfo
@onready var focus_label: Label = $UI/FocusInfo
@onready var controls_label: Label = $UI/ControlsInfo
@onready var enemy_hp_container: VBoxContainer = $UI/EnemyHPInfo

# Wave system
const FIRST_WAVE_DELAY = 5.0  # First enemy at t=5s
const WAVE_INTERVAL = 18.0    # Every 18s after
const MAX_ENEMIES = 3         # Cap at 3 alive

var enemy_scene: PackedScene
var active_enemies: Array[EnemyShip] = []
var wave_timer: float = 0.0
var first_wave_spawned: bool = false

# UI tracking
var current_focus_module: ShipModule = null
var current_focus_enemy: EnemyShip = null
var player_ship_hp_bar: ProgressBar = null
var enemy_ship_hp_bar: ProgressBar = null
var focus_module_label: Label = null

func _ready():
	# Load enemy scene for wave spawning
	enemy_scene = preload("res://scenes/enemy_ship.tscn")
	
	# Remove any baked enemy ship from the scene
	if has_node("EnemyShip"):
		var baked_enemy = get_node("EnemyShip")
		baked_enemy.queue_free()
	
	_setup_ship_hp_bars()
	_setup_focus_label()
	
	player_ship.ship_destroyed.connect(_on_player_destroyed)
	player_ship.overall_hp_changed.connect(_on_player_hp_changed)
	
	# Start wave timer
	wave_timer = FIRST_WAVE_DELAY

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
	# Only update HP bar for currently focused enemy
	if enemy_ship_hp_bar and current_focus_enemy:
		enemy_ship_hp_bar.max_value = max_hp
		enemy_ship_hp_bar.value = current

func _connect_enemy_modules(enemy: EnemyShip):
	for module in enemy.modules:
		if module.is_clickable:
			module.module_clicked.connect(_on_enemy_module_clicked.bind(enemy))

func _on_enemy_module_clicked(module: ShipModule, enemy: EnemyShip):
	# Clear previous focus highlight
	if current_focus_module:
		current_focus_module.set_focused(false)
	
	current_focus_module = module
	current_focus_enemy = enemy
	
	# Set target to this enemy
	player_ship.set_focused_target(enemy)
	player_ship.set_focus_fire_module(module)
	
	# Set new focus highlight
	module.set_focused(true)
	
	_update_focus_label()
	
	# Update the center focus label
	if focus_module_label:
		var module_name = _get_module_name(module.module_type)
		focus_module_label.text = "FOCUSED: %s" % module_name

func _process(delta):
	_update_wave_spawning(delta)
	_update_ui()

func _update_wave_spawning(delta):
	wave_timer -= delta
	
	if wave_timer <= 0:
		# Try to spawn if under cap
		if active_enemies.size() < MAX_ENEMIES:
			_spawn_enemy()
		
		# Reset timer for next wave (18s interval after first wave)
		if not first_wave_spawned:
			first_wave_spawned = true
			wave_timer = WAVE_INTERVAL
		else:
			wave_timer = WAVE_INTERVAL

func _spawn_enemy():
	var enemy = enemy_scene.instantiate()
	add_child(enemy)
	
	# Position enemy at distance from player
	var spawn_angle = randf() * TAU
	var spawn_distance = 600.0 + randf() * 200.0
	enemy.position = player_ship.position + Vector2(cos(spawn_angle), sin(spawn_angle)) * spawn_distance
	enemy.rotation = randf() * TAU
	
	# Setup enemy
	enemy.set_player_target(player_ship)
	enemy.ship_destroyed.connect(_on_enemy_destroyed.bind(enemy))
	enemy.overall_hp_changed.connect(_on_enemy_hp_changed)
	
	# Connect modules for clicking
	_connect_enemy_modules(enemy)
	
	# Track active enemy
	active_enemies.append(enemy)
	
	# Auto-target first enemy if player has no target
	if active_enemies.size() == 1:
		player_ship.set_focused_target(enemy)
		current_focus_enemy = enemy

func _update_ui():
	var alive_count = active_enemies.size()
	if alive_count > 0:
		target_label.text = "Enemies: %d" % alive_count
	else:
		target_label.text = "No Enemies"
	
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
	
	# Show HP for currently focused enemy
	if not current_focus_enemy or not is_instance_valid(current_focus_enemy):
		return
	
	for module in current_focus_enemy.modules:
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

func _on_enemy_destroyed(enemy: EnemyShip):
	# Remove from active enemies
	active_enemies.erase(enemy)
	
	# Clear focus if this was the focused enemy
	if current_focus_enemy == enemy:
		if current_focus_module:
			current_focus_module.set_focused(false)
		current_focus_module = null
		current_focus_enemy = null
		
		# Auto-target next available enemy
		if active_enemies.size() > 0:
			var next_enemy = active_enemies[0]
			player_ship.set_focused_target(next_enemy)
			current_focus_enemy = next_enemy
		else:
			player_ship.set_focused_target(null)
		
		if focus_module_label:
			focus_module_label.text = ""

func _on_player_destroyed():
	target_label.text = "PLAYER DESTROYED - Defeat!"
	get_tree().paused = true
