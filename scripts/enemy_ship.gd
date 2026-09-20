extends Ship
class_name EnemyShip

const GameConstants = preload("res://scripts/game_constants.gd")

var player_ship: Ship = null

func _ready():
	super._ready()
	max_speed = GameConstants.ENEMY_MAX_SPEED
	acceleration = GameConstants.ENEMY_ACCELERATION
	rotation_speed = GameConstants.ENEMY_ROTATION_SPEED
	current_speed = max_speed * 0.5

func _physics_process(delta):
	if player_ship:
		var to_player = player_ship.global_position - global_position
		var desired_angle = to_player.angle()
		var angle_diff = angle_difference(rotation, desired_angle)
		
		if abs(angle_diff) > 0.1:
			var rotation_dir = sign(angle_diff)
			rotation += rotation_dir * deg_to_rad(rotation_speed) * delta
	
	super._physics_process(delta)

func set_player_target(player: Ship):
	player_ship = player
	set_focused_target(player)
