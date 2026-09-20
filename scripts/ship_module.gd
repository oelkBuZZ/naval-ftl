extends Node2D
class_name ShipModule

const GameConstants = preload("res://scripts/game_constants.gd")

@export var module_type: GameConstants.ModuleType = GameConstants.ModuleType.HULL
@export var is_clickable: bool = false

var max_hp: float
var current_hp: float
var is_on_fire: bool = false
var fire_time: float = 0.0
var repair_timer: float = 0.0
var is_focused: bool = false
var is_offline: bool = false

@onready var sprite: Sprite2D = $Sprite2D
@onready var fire_particles: CPUParticles2D = null
@onready var collision_area: Area2D = null

signal module_destroyed(module: ShipModule)
signal module_clicked(module: ShipModule)

func _ready():
	max_hp = GameConstants.get_module_max_hp(module_type)
	current_hp = max_hp
	
	if is_clickable and has_node("ClickArea"):
		collision_area = $ClickArea
		collision_area.input_event.connect(_on_input_event)
	
	if has_node("FireParticles"):
		fire_particles = $FireParticles
		fire_particles.emitting = false

func _process(delta):
	if is_on_fire:
		fire_time += delta
		
		if fire_time >= GameConstants.FIRE_TICK_INTERVAL:
			fire_time = 0.0
			take_damage(GameConstants.FIRE_DAMAGE_PER_TICK, false)
		
		if fire_particles and randf() < delta * 2.0:
			if fire_time >= GameConstants.FIRE_EXTINGUISH_TIME:
				extinguish_fire()
	
	if current_hp < max_hp and not is_on_fire and not is_offline:
		repair_timer += delta
		if repair_timer >= 1.0:
			repair_timer = 0.0
			current_hp = min(current_hp + GameConstants.REPAIR_RATE, max_hp)
			_update_visual_state()

func take_damage(damage: float, can_start_fire: bool = true):
	if is_offline:
		return
	
	current_hp -= damage
	
	# Red-tinted damage flash
	if sprite:
		sprite.modulate = Color(1.5, 1.0, 1.0)
		await get_tree().create_timer(GameConstants.HIT_FLASH_DURATION).timeout
		if sprite and not is_offline:
			_update_visual_state()
	
	if can_start_fire and not is_on_fire and current_hp > 0:
		if randf() < GameConstants.FIRE_START_CHANCE:
			start_fire()
	
	if current_hp <= 0:
		current_hp = 0
		_enter_offline_state()
		module_destroyed.emit(self)

func start_fire():
	is_on_fire = true
	fire_time = 0.0
	if fire_particles:
		fire_particles.emitting = true
	_update_visual_state()

func extinguish_fire():
	is_on_fire = false
	fire_time = 0.0
	if fire_particles:
		fire_particles.emitting = false
	_update_visual_state()

func set_focused(focused: bool):
	is_focused = focused
	_update_visual_state()

func get_hp_percent() -> float:
	return current_hp / max_hp if max_hp > 0 else 0.0

func _update_visual_state():
	if not sprite:
		return
	
	if is_offline:
		# Offline state: dark gray with red tint
		sprite.modulate = Color(0.3, 0.2, 0.2, 1.0)
		return
	
	var hp_percent = get_hp_percent()
	
	if is_focused:
		# Focused: bright yellow-green highlight
		sprite.modulate = Color(1.3, 1.5, 1.0, 1.0)
	elif is_on_fire:
		# On fire: orange tint
		sprite.modulate = Color(1.2, 0.7, 0.5, 1.0)
	elif hp_percent < 0.25:
		# Critical damage: dark red
		sprite.modulate = Color(0.7, 0.3, 0.3, 1.0)
	elif hp_percent < 0.50:
		# Heavy damage: orange-red
		sprite.modulate = Color(0.9, 0.5, 0.4, 1.0)
	elif hp_percent < 0.75:
		# Moderate damage: yellow-orange
		sprite.modulate = Color(1.0, 0.8, 0.6, 1.0)
	else:
		# Full or light damage: restore default tint if present
		# Keep existing enemy module tints from scene
		if abs(sprite.modulate.r - 1.0) < 0.1 and abs(sprite.modulate.g - 1.0) < 0.1:
			sprite.modulate = Color(1.0, 1.0, 1.0, 1.0)

func _enter_offline_state():
	is_offline = true
	is_on_fire = false
	
	if fire_particles:
		fire_particles.emitting = false
	
	_update_visual_state()

func _on_input_event(_viewport, event, _shape_idx):
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		module_clicked.emit(self)
