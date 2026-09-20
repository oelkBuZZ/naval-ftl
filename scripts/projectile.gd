extends Area2D
class_name Projectile

const GameConstants = preload("res://scripts/game_constants.gd")
const PROJECTILE_LIFETIME = 4.0  # seconds before auto-despawn

var velocity: Vector2
var damage: float = GameConstants.PROJECTILE_DAMAGE
var source_ship: Node2D = null
var target_module: Node2D = null
var lifetime: float = 0.0

func _ready():
	area_entered.connect(_on_area_entered)

func _process(delta):
	position += velocity * delta
	lifetime += delta
	
	# Despawn after lifetime expires
	if lifetime >= PROJECTILE_LIFETIME:
		queue_free()

func setup(start_pos: Vector2, direction: Vector2, proj_damage: float, source: Node2D, target: Node2D = null):
	position = start_pos
	velocity = direction.normalized() * GameConstants.PROJECTILE_SPEED
	damage = proj_damage
	source_ship = source
	target_module = target
	rotation = velocity.angle()

func _on_area_entered(area):
	if area.get_parent() is ShipModule:
		var module = area.get_parent()
		if module.get_parent() != source_ship:
			var actual_damage = damage
			if target_module and module == target_module:
				actual_damage *= GameConstants.FOCUS_FIRE_DAMAGE_MULTIPLIER
			module.take_damage(actual_damage)
			queue_free()
