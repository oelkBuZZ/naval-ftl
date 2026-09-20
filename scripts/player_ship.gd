extends Ship
class_name PlayerShip

const GameConstants = preload("res://scripts/game_constants.gd")

var target_speed: float = 0.0

func _ready():
	super._ready()
	max_speed = GameConstants.PLAYER_MAX_SPEED
	acceleration = GameConstants.PLAYER_ACCELERATION
	rotation_speed = GameConstants.PLAYER_ROTATION_SPEED

func _physics_process(delta):
	_handle_input(delta)
	
	if current_speed < target_speed:
		current_speed = min(current_speed + acceleration * delta, target_speed)
	elif current_speed > target_speed:
		current_speed = max(current_speed - GameConstants.PLAYER_DECELERATION * delta, target_speed)
	
	super._physics_process(delta)

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
