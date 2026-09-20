extends Node

# Naval FTL - Game Constants & Tunables
# All gameplay values in one place for easy balancing

# SHIP MOVEMENT
const PLAYER_ROTATION_SPEED = 54.0  # degrees per second (-40% from 90.0)
const PLAYER_MAX_SPEED = 110.0  # pixels per second (-45% from 200.0)
const PLAYER_ACCELERATION = 55.0  # pixels per second^2 (-45% from 100.0)
const PLAYER_DECELERATION = 82.5  # pixels per second^2 (-45% from 150.0)

const ENEMY_ROTATION_SPEED = 36.0  # (-40% from 60.0)
const ENEMY_MAX_SPEED = 66.0  # (-45% from 120.0)
const ENEMY_ACCELERATION = 44.0  # (-45% from 80.0)

# MODULE HEALTH
const MODULE_HP_HULL = 150.0
const MODULE_HP_CITADEL = 100.0
const MODULE_HP_ENGINE = 80.0
const MODULE_HP_TURRET = 60.0

# COMBAT
const TURRET_FIRE_RATE = 2.0  # seconds between shots
const TURRET_RANGE = 1300.0  # pixels
const TURRET_ROTATION_SPEED = 45.0  # degrees per second
const PROJECTILE_SPEED = 480.0  # pixels per second
const PROJECTILE_DAMAGE = 25.0

# SHIP SCALE
const SHIP_SCALE = 1.6  # Scale multiplier for ships (hull + modules)

# FIRE & REPAIR
const FIRE_START_CHANCE = 0.15  # 15% chance per hit
const FIRE_DAMAGE_PER_TICK = 5.0
const FIRE_TICK_INTERVAL = 1.0  # seconds
const REPAIR_RATE = 3.0  # HP per second (auto-repair)
const FIRE_EXTINGUISH_TIME = 3.0  # seconds to auto-extinguish

# TARGETING
const FOCUS_FIRE_DAMAGE_MULTIPLIER = 1.5

# VISUAL
const HIT_FLASH_DURATION = 0.1
const FIRE_PARTICLE_COLOR = Color(1.0, 0.3, 0.0)

# Module types enum
enum ModuleType {
	HULL,
	CITADEL,
	ENGINE,
	TURRET
}

static func get_module_max_hp(module_type: ModuleType) -> float:
	match module_type:
		ModuleType.HULL:
			return MODULE_HP_HULL
		ModuleType.CITADEL:
			return MODULE_HP_CITADEL
		ModuleType.ENGINE:
			return MODULE_HP_ENGINE
		ModuleType.TURRET:
			return MODULE_HP_TURRET
		_:
			return 100.0
