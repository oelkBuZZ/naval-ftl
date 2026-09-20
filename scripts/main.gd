extends Node2D

@onready var player_ship: PlayerShip = $PlayerShip
@onready var enemy_ship: EnemyShip = $EnemyShip
@onready var ui: Control = $UI
@onready var target_label: Label = $UI/TargetInfo
@onready var focus_label: Label = $UI/FocusInfo
@onready var controls_label: Label = $UI/ControlsInfo
@onready var enemy_hp_container: VBoxContainer = $UI/EnemyHPInfo

var current_focus_module: ShipModule = null

func _ready():
	player_ship.set_focused_target(enemy_ship)
	enemy_ship.set_player_target(player_ship)
	
	_connect_enemy_modules()
	
	enemy_ship.ship_destroyed.connect(_on_enemy_destroyed)
	player_ship.ship_destroyed.connect(_on_player_destroyed)

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
	if current_focus_module:
		current_focus_module.set_focused(false)

func _on_player_destroyed():
	target_label.text = "PLAYER DESTROYED - Defeat!"
	get_tree().paused = true
