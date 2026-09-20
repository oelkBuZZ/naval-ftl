extends Node2D

@onready var player_ship: PlayerShip = $PlayerShip
@onready var ui: Control = $UI
@antml:parameter name="target_label: Label = $UI/TargetInfo
@onready var focus_label: Label = $UI/FocusInfo
@onready var controls_label: Label = $UI/ControlsInfo

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

func _ready():
	# Load enemy scene for wave spawning
	enemy_scene = preload("res://scenes/enemy_ship.tscn")
	
	# Remove any baked enemy ship from the scene
	if has_node("EnemyShip"):
		var baked_enemy = get_node("EnemyShip")
		baked_enemy.queue_free()
	
	player_ship.ship_destroyed.connect(_on_player_destroyed)
	
	# Start wave timer
	wave_timer = FIRST_WAVE_DELAY

func _unhandled_input(event):
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		_handle_click(event.position)

func _handle_click(screen_pos: Vector2):
	# Convert screen position to world position
	var world_pos = get_viewport().get_canvas_transform().affine_inverse() * screen_pos
	
	# Check which enemy module was clicked across all active enemies
	var clicked_module: ShipModule = null
	var clicked_enemy: EnemyShip = null
	var min_distance = 999999.0
	
	for enemy in active_enemies:
		if not is_instance_valid(enemy):
			continue
		
		for module in enemy.modules:
			if not module.is_clickable:
				continue
			
			var module_pos = module.global_position
			var distance = world_pos.distance_to(module_pos)
			
			# Check if click is within module bounds (rough approximation)
			if distance < 50.0 and distance < min_distance:
				clicked_module = module
				clicked_enemy = enemy
				min_distance = distance
	
	if clicked_module and clicked_enemy:
		_on_enemy_module_clicked(clicked_module, clicked_enemy)

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

func _update_focus_label():
	if current_focus_module:
		var module_name = _get_module_name(current_focus_module.module_type)
		focus_label.text = "FOCUSED: %s (%.0f%% HP)" % [module_name, current_focus_module.get_hp_percent() * 100]
	else:
		focus_label.text = "Focus Fire: None (click enemy module)"

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

func _on_player_destroyed():
	target_label.text = "PLAYER DESTROYED - Defeat!"
	get_tree().paused = true
