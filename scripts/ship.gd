extends CharacterBody2D
class_name Ship

const GameConstants = preload("res://scripts/game_constants.gd")

@export var max_speed: float = 200.0
@export var acceleration: float = 100.0
@export var rotation_speed: float = 90.0

var current_speed: float = 0.0
var modules: Array[ShipModule] = []
var hull_module: ShipModule = null
var turret_module: ShipModule = null
var turret_cooldown: float = 0.0
var focused_target: Ship = null
var focus_fire_module: ShipModule = null

# Ship overall HP
var max_overall_hp: float = 0.0
var current_overall_hp: float = 0.0

signal ship_destroyed
signal overall_hp_changed(current: float, max_hp: float)

func _ready():
	_setup_modules()
	_calculate_overall_hp()

func _process(delta):
	if turret_cooldown > 0:
		turret_cooldown -= delta
	
	_update_turret(delta)

func _physics_process(_delta):
	velocity = Vector2(0, -current_speed).rotated(rotation)
	move_and_slide()

func _setup_modules():
	for child in get_children():
		if child is ShipModule:
			modules.append(child)
			child.module_destroyed.connect(_on_module_destroyed)
			child.module_damaged.connect(_on_module_damaged)
			if child.module_type == GameConstants.ModuleType.TURRET:
				turret_module = child
			elif child.module_type == GameConstants.ModuleType.HULL:
				hull_module = child

func _calculate_overall_hp():
	max_overall_hp = 0.0
	for module in modules:
		max_overall_hp += module.max_hp
	current_overall_hp = max_overall_hp
	overall_hp_changed.emit(current_overall_hp, max_overall_hp)

func _update_turret(delta):
	if not turret_module or not focused_target:
		return
	
	var target_pos = focused_target.global_position
	if focus_fire_module:
		target_pos = focus_fire_module.global_position
	
	var to_target = target_pos - turret_module.global_position
	var target_angle = to_target.angle() + PI/2
	
	var current_turret_rotation = turret_module.global_rotation
	var angle_diff = angle_difference(current_turret_rotation, target_angle)
	
	if abs(angle_diff) > 0.01:
		var rotation_dir = sign(angle_diff)
		turret_module.rotation += rotation_dir * deg_to_rad(GameConstants.TURRET_ROTATION_SPEED) * delta
	
	if turret_cooldown <= 0 and to_target.length() <= GameConstants.TURRET_RANGE:
		if abs(angle_diff) < deg_to_rad(25.0):
			_fire_turret()

func _fire_turret():
	if not turret_module:
		return
	
	turret_cooldown = GameConstants.TURRET_FIRE_RATE
	
	var projectile_scene = preload("res://scenes/projectile.tscn")
	var projectile = projectile_scene.instantiate()
	get_parent().add_child(projectile)
	
	var fire_pos = turret_module.global_position + Vector2(0, -30).rotated(turret_module.global_rotation)
	var fire_dir = Vector2(0, -1).rotated(turret_module.global_rotation)
	
	projectile.setup(fire_pos, fire_dir, GameConstants.PROJECTILE_DAMAGE, self, focus_fire_module)

func set_focused_target(target: Ship):
	focused_target = target
	focus_fire_module = null

func set_focus_fire_module(module: ShipModule):
	focus_fire_module = module

func _on_module_damaged(damage: float):
	# When a module is damaged, also reduce overall ship HP by the same amount
	current_overall_hp = max(0, current_overall_hp - damage)
	overall_hp_changed.emit(current_overall_hp, max_overall_hp)
	
	# Check if ship should be destroyed (overall HP depleted)
	if current_overall_hp <= 0:
		ship_destroyed.emit()
		queue_free()

func _on_module_destroyed(module: ShipModule):
	if module == turret_module:
		turret_module = null
	
	# Check if all modules are offline → ship is destroyed
	var all_offline = true
	for mod in modules:
		if not mod.is_offline:
			all_offline = false
			break
	
	if all_offline:
		ship_destroyed.emit()
		queue_free()

func angle_difference(from_angle: float, to_angle: float) -> float:
	var diff = fmod(to_angle - from_angle, TAU)
	if diff > PI:
		diff -= TAU
	elif diff < -PI:
		diff += TAU
	return diff
