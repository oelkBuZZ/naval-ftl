# Naval FTL - Exact Systems-Locked Values Applied

## ✅ Exact Parameters Implemented

### Ship Scale
- **Visual/Collision Scale**: `1.6×` (applied to both player and enemy CharacterBody2D root nodes)

### Movement (Thrust/Speed)
**Baseline → New (-45% reduction)**
- Player Max Speed: `200 → 110` px/s
- Player Acceleration: `100 → 55` px/s²
- Player Deceleration: `150 → 82.5` px/s²
- Enemy Max Speed: `120 → 66` px/s
- Enemy Acceleration: `80 → 44` px/s²

### Rotation (Turn Rate)
**Baseline → New (-40% reduction)**
- Player Rotation: `90° → 54°` per second
- Enemy Rotation: `60° → 36°` per second

### Combat
- **Gun Range**: `1300` pixels (exact, was 600 baseline)
- **Shell Speed**: `480` px/s (exact, was 400 baseline)
- **ROF**: `2.0` seconds (unchanged)
- **Damage**: `25` per hit (unchanged)

---

## Implementation Details

### Files Modified
```
scripts/game_constants.gd    - All speed/turn/range constants
scenes/player_ship.tscn      - scale = Vector2(1.6, 1.6)
scenes/enemy_ship.tscn       - scale = Vector2(1.6, 1.6)
scripts/target_panel.gd      - Module position scaling * 1.6
```

### ESC Pause Menu
- Resume / Restart battle / Quit
- Full pause freeze with `get_tree().paused`
- Input blocking for player and module clicks

### FTL Target Panel Logic
**Changed from**: Show when enemy off-screen
**Changed to**: Show while focused module exists

- Panel appears when player has locked a module (focus fire active)
- Panel clicks set module lock on real modules
- Hides when no focus (no module locked)
- Right SubViewport displaying enemy ship layout

---

## Verification Commands
```bash
# Check ship scales
grep "scale = Vector2" scenes/*ship.tscn

# Check movement constants
grep "PLAYER_MAX_SPEED\|ENEMY_MAX_SPEED\|PLAYER_ROTATION" scripts/game_constants.gd

# Check combat constants
grep "TURRET_RANGE\|PROJECTILE_SPEED" scripts/game_constants.gd
```

---

## Current Values in Code
```gdscript
# scripts/game_constants.gd

# SHIP MOVEMENT
const PLAYER_ROTATION_SPEED = 54.0  # -40% from 90.0
const PLAYER_MAX_SPEED = 110.0      # -45% from 200.0
const PLAYER_ACCELERATION = 55.0    # -45% from 100.0
const PLAYER_DECELERATION = 82.5    # -45% from 150.0

const ENEMY_ROTATION_SPEED = 36.0   # -40% from 60.0
const ENEMY_MAX_SPEED = 66.0        # -45% from 120.0
const ENEMY_ACCELERATION = 44.0     # -45% from 80.0

# COMBAT
const TURRET_RANGE = 1300.0         # exact
const PROJECTILE_SPEED = 480.0      # exact
const TURRET_FIRE_RATE = 2.0        # unchanged
const PROJECTILE_DAMAGE = 25.0      # unchanged
```

---

## Git History
```
8ac1bcb - Apply exact systems-locked feel numbers
a949911 - Implement pause menu, ship tuning, and FTL-style off-screen target view
```

Branch: `cursor/pause-menu-ship-tuning-ftl-view-3169`
PR: https://github.com/oelkBuZZ/naval-ftl/pull/9
Status: **Ready for playtest** (not draft)

---

## Preserved Systems
✅ Wave spawning (5s/18s timers, 3-enemy cap)
✅ Hull-first damage routing
✅ Localized module damage
✅ Offline unrepairable modules
✅ Fire mechanics (15% start, 5 dmg/tick, auto-extinguish)
✅ Focus fire system (1.5× damage multiplier)
✅ Projectile lifetime culling
✅ Wake trail rendering
✅ Ship HP bars and status UI

