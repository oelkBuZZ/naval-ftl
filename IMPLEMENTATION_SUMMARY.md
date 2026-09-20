# Naval FTL - Playtest Features Implementation Summary

## Features Implemented

### 1. ESC Pause Menu ✓
**Files**: `scripts/pause_menu.gd`, `scenes/pause_menu.tscn`

**Implementation Details**:
- Press ESC (ui_cancel action) to pause/unpause
- Game paused using `get_tree().paused = true`
- Menu has `process_mode = PROCESS_MODE_ALWAYS` (value 3)
- Three functional buttons:
  - Resume: Unpauses game
  - Restart Battle: Reloads scene with `get_tree().reload_current_scene()`
  - Quit: Exits with `get_tree().quit()`

**Input Blocking**:
- Player controls check `get_tree().paused` in `_handle_input()`
- Module clicks check `get_tree().paused` in `_on_input_event()`

**Integration**: Added to `main.tscn` as child of root node

---

### 2. Ship Feel Tuning ✓
**Files**: `scripts/game_constants.gd`, `scenes/player_ship.tscn`, `scenes/enemy_ship.tscn`

**Changes**:
- **Ship Scale**: 1.7× larger (added `scale = Vector2(1.7, 1.7)` to ship root nodes)
- **Speed Reductions** (~50% slower):
  - Player max speed: 200 → 100 px/s
  - Player rotation: 90° → 45°/s
  - Enemy max speed: 120 → 60 px/s
  - Enemy rotation: 60° → 30°/s
  - Acceleration/deceleration scaled proportionally
- **Turret Range**: 600 → 1200 pixels (2× increase)

**Preserved**: All combat math, damage calculations, and wave timers unchanged

---

### 3. FTL-Style Off-Screen Target View ✓
**Files**: `scripts/target_panel.gd`, `scenes/target_panel.tscn`

**Implementation Details**:
- Side panel at top-right (420×320 px)
- Uses `SubViewport` + `SubViewportContainer` for rendering
- Appears when enemy is within 150px of viewport edge or off-screen
- Shows enemy ship layout with all modules positioned correctly

**Module Visualization**:
- Clones enemy modules into viewport at scaled positions
- Each module has clickable Area2D
- Visual state syncs from original modules (HP, fire, offline, focus)
- Click handling emits `module_clicked` signal on original module

**Integration**:
- Added to `main.tscn` as child of UI
- Setup in `main.gd` _ready() with enemy reference and camera
- Panel has `process_mode = PROCESS_MODE_ALWAYS` (works while paused)

**Preserved**: World-space HP bars, existing click targeting, focus highlight system

---

## Preserved Features
✅ Wave timers (5s/18s spawn, 3-enemy cap)
✅ Hull-first damage routing
✅ Localized module damage
✅ Ship HP bars and status UI
✅ Offline unrepairable modules
✅ Fire mechanics (15% chance, 5 dmg/tick, auto-extinguish)
✅ Projectile lifetime culling
✅ Wake trail rendering
✅ Focus fire system (1.5× damage multiplier)

---

## Files Modified
- `scenes/main.tscn` - Added pause menu and target panel
- `scenes/player_ship.tscn` - Added 1.7× scale
- `scenes/enemy_ship.tscn` - Added 1.7× scale
- `scripts/main.gd` - Integrated target panel setup
- `scripts/player_ship.gd` - Added pause check in input handler
- `scripts/ship_module.gd` - Added pause check in click handler
- `scripts/game_constants.gd` - Updated speeds, rotation, range

## Files Created
- `scripts/pause_menu.gd` - Pause menu controller
- `scenes/pause_menu.tscn` - Pause menu UI
- `scripts/target_panel.gd` - Off-screen target view controller
- `scenes/target_panel.tscn` - Target panel UI with SubViewport

---

## Testing Checklist

### Pause Menu
- [ ] ESC key pauses game
- [ ] ESC again resumes
- [ ] Resume button works
- [ ] Restart Battle reloads scene
- [ ] Quit exits game
- [ ] Player cannot move/rotate while paused
- [ ] Cannot click modules while paused

### Ship Feel
- [ ] Ships appear larger (1.7×)
- [ ] Movement slower and more deliberate
- [ ] Turning slower
- [ ] Turrets fire from longer range
- [ ] Combat feels balanced

### Off-Screen Target View
- [ ] Panel appears when enemy near edge/off-screen
- [ ] Panel shows enemy ship layout
- [ ] All 4 modules visible in panel (Hull, Citadel, Engine, Turret)
- [ ] Clicking modules in panel sets focus fire
- [ ] Visual states sync (damage, fire, offline)
- [ ] Panel hides when enemy returns to center
- [ ] Works while game is paused

---

## Known Godot Version
Godot 4.3 (specified in project.godot)

## Build Commands
```bash
# No build required - Godot project runs directly
# Open project.godot in Godot 4.3 editor
# Or run headless: godot4 --headless --path /workspace
```

---

## PR Information
Branch: `cursor/pause-menu-ship-tuning-ftl-view-3169`
PR: https://github.com/oelkBuZZ/naval-ftl/pull/9
Status: Open, Ready for Review (not draft)
