extends Node

# Naval FTL - Game Constants & Tunables
# All gameplay values in one place for easy balancing

# SHIP MOVEMENT
const PLAYER_ROTATION_SPEED = 45.0  # degrees per second (was 90.0)
const PLAYER_MAX_SPEED = 100.0  # pixels per second (was 200.0)
const PLAYER_ACCELERATION = 50.0  # pixels per second^2 (was 100.0)
const PLAYER_DECELERATION = 75.0  # pixels per second^2 (was 150.0)

const ENEMY_ROTATION_SPEED = 30.0  # (was 60.0)
const ENEMY_MAX_SPEED = 60.0  # (was 120.0)
const ENEMY_ACCELERATION = 40.0  # (was 80.0)

# MODULE HEALTH
const MODULE_HP_HULL = 150.0
const MODULE_HP_CITADEL = 100.0
const MODULE_HP_ENGINE = 80.0
const MODULE_HP_TURRET = 60.0

# COMBAT
const TURRET_FIRE_RATE = 2.0  # seconds between shots
const TURRET_RANGE = 1200.0  # pixels (was 600.0)
const TURRET_ROTATION_SPEED = 45.0  # degrees per second
const PROJECTILE_SPEED = 400.0  # pixels per second
const PROJECTILE_DAMAGE = 25.0

# SHIP SCALE
const SHIP_SCALE = 1.7  # Scale multiplier for ships (hull + modules)

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
