extends Ship
class_name PlayerShip

const GameConstants = preload("res://scripts/game_constants.gd")

var target_speed: float = 0.0
var wake_trail: Line2D = null
var wake_points: Array = []
const MAX_WAKE_POINTS = 50
const WAKE_POINT_DISTANCE = 10.0
var last_wake_position: Vector2 = Vector2.ZERO

func _ready():
	super._ready()
	max_speed = GameConstants.PLAYER_MAX_SPEED
	acceleration = GameConstants.PLAYER_ACCELERATION
	rotation_speed = GameConstants.PLAYER_ROTATION_SPEED
	
	if has_node("WakeTrail"):
		wake_trail = $WakeTrail
	
	last_wake_position = global_position

func _physics_process(delta):
	_handle_input(delta)
	
	if current_speed < target_speed:
		current_speed = min(current_speed + acceleration * delta, target_speed)
	elif current_speed > target_speed:
		current_speed = max(current_speed - GameConstants.PLAYER_DECELERATION * delta, target_speed)
	
	super._physics_process(delta)
	_update_wake_trail()

func _handle_input(delta):
	var rotation_input = 0.0
	if Input.is_action_pressed("rotate_left"):
		rotation_input -= 1.0
	if Input.is_action_pressed("rotate_right"):
		rotation_input += 1.0
	
	rotation += deg_to_rad(rotation_input * rotation_speed * delta)
	
	if Input.is_action_pressed("throttle_up"):
		target_speed = min(target_speed + acceleration * delta, max_speed)
	if Input.is_action_pressed("throttle_down"):
		target_speed = max(target_speed - acceleration * delta, 0.0)

func _update_wake_trail():
	if not wake_trail or current_speed < 10.0:
		if wake_trail:
			wake_trail.clear_points()
		return
	
	var stern_pos = global_position + Vector2(0, 90).rotated(global_rotation)
	
	if last_wake_position.distance_to(stern_pos) >= WAKE_POINT_DISTANCE:
		wake_points.append(stern_pos)
		last_wake_position = stern_pos
		
		if wake_points.size() > MAX_WAKE_POINTS:
			wake_points.pop_front()
	
	wake_trail.clear_points()
	for point in wake_points:
		wake_trail.add_point(wake_trail.to_local(point))
