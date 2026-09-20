extends Control
class_name TargetPanel

@onready var viewport_container: SubViewportContainer = $PanelContainer/SubViewportContainer
@onready var sub_viewport: SubViewport = $PanelContainer/SubViewportContainer/SubViewport
@onready var title_label: Label = $PanelContainer/VBoxContainer/Title
@onready var vbox: VBoxContainer = $PanelContainer/VBoxContainer

var enemy_ship: Ship = null
var enemy_clone: Node2D = null
var main_camera: Camera2D = null
var current_focus_module: ShipModule = null
var main_scene: Node = null

func _ready():
	hide()
	process_mode = Node.PROCESS_MODE_ALWAYS

func setup(enemy: Ship, camera: Camera2D, main_node: Node):
	enemy_ship = enemy
	main_camera = camera
	main_scene = main_node
	
	if enemy_ship:
		_create_enemy_visualization()

func update_enemy(enemy: Ship):
	enemy_ship = enemy
	if enemy_ship:
		_create_enemy_visualization()
	else:
		# Clear visualization if no enemy
		if enemy_clone:
			enemy_clone.queue_free()
			enemy_clone = null

func _create_enemy_visualization():
	# Clear previous clone
	if enemy_clone:
		enemy_clone.queue_free()
	
	if not enemy_ship:
		return
	
	# Create a visual clone of the enemy ship for the viewport
	enemy_clone = Node2D.new()
	sub_viewport.add_child(enemy_clone)
	
	# Position the clone in the center of the viewport
	enemy_clone.position = Vector2(200, 150)
	enemy_clone.rotation = 0
	
	# Clone all modules
	for module in enemy_ship.modules:
		var module_visual = _create_module_visual(module)
		enemy_clone.add_child(module_visual)

func has_focused_module() -> bool:
	if not main_scene or not main_scene.has_method("get"):
		return false
	var focus_module = main_scene.get("current_focus_module")
	return focus_module != null

func _create_module_visual(original_module: ShipModule) -> Node2D:
	var visual = Node2D.new()
	visual.position = original_module.position * 1.6  # Match ship scale
	
	# Create sprite
	var sprite = Sprite2D.new()
	if original_module.has_node("Sprite2D"):
		var original_sprite = original_module.get_node("Sprite2D")
		sprite.texture = original_sprite.texture
		sprite.modulate = original_sprite.modulate
	visual.add_child(sprite)
	
	# Create clickable area
	var area = Area2D.new()
	area.input_pickable = true
	visual.add_child(area)
	
	var collision_shape = CollisionShape2D.new()
	var shape = RectangleShape2D.new()
	shape.size = Vector2(64, 64)
	collision_shape.shape = shape
	area.add_child(collision_shape)
	
	# Connect click event
	area.input_event.connect(func(_viewport, event, _shape_idx):
		if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
			_on_module_clicked(original_module, sprite)
	)
	
	# Store reference to update visual state
	visual.set_meta("original_module", original_module)
	visual.set_meta("sprite", sprite)
	
	return visual

func _on_module_clicked(module: ShipModule, sprite: Sprite2D):
	# Clear previous focus
	if current_focus_module:
		current_focus_module.set_focused(false)
	
	# Set new focus
	current_focus_module = module
	module.module_clicked.emit(module)
	
	# Visual feedback
	_update_visuals()

func _process(_delta):
	if not enemy_ship or not is_instance_valid(enemy_ship):
		hide()
		return
	
	# Show panel while focused target exists
	if has_focused_module():
		if not visible:
			show()
		_update_visuals()
	else:
		if visible:
			hide()

func _update_visuals():
	if not enemy_clone:
		return
	
	# Update all module visuals based on original state
	for child in enemy_clone.get_children():
		if child.has_meta("original_module"):
			var original_module: ShipModule = child.get_meta("original_module")
			var sprite: Sprite2D = child.get_meta("sprite")
			
			if is_instance_valid(original_module) and is_instance_valid(sprite):
				# Copy the visual state from the original module
				if original_module.has_node("Sprite2D"):
					sprite.modulate = original_module.get_node("Sprite2D").modulate
