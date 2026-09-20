extends Area2D
class_name Projectile

const GameConstants = preload("res://scripts/game_constants.gd")

var velocity: Vector2
var damage: float = GameConstants.PROJECTILE_DAMAGE
var source_ship: Node2D = null
var target_module: Node2D = null

func _ready():
	body_entered.connect(_on_body_entered)
	area_entered.connect(_on_area_entered)

func _process(delta):
	position += velocity * delta
	
	if not get_viewport_rect().has_point(position):
		queue_free()

func setup(start_pos: Vector2, direction: Vector2, proj_damage: float, source: Node2D, target: Node2D = null):
	position = start_pos
	velocity = direction.normalized() * GameConstants.PROJECTILE_SPEED
	damage = proj_damage
	source_ship = source
	target_module = target
	rotation = velocity.angle()

func _on_body_entered(body):
	if body != source_ship and body.has_method("hit_by_projectile"):
		body.hit_by_projectile(self)
		queue_free()

func _on_area_entered(area):
	if area.get_parent() is ShipModule:
		var module = area.get_parent()
		if module.get_parent() != source_ship:
			var actual_damage = damage
			if target_module and module == target_module:
				actual_damage *= GameConstants.FOCUS_FIRE_DAMAGE_MULTIPLIER
			module.take_damage(actual_damage)
			queue_free()
