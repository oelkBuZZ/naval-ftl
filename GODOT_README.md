# Naval FTL - MVP Combat Sandbox

Godot 4 WWII-themed FTL-like top-down naval combat game.

## How to Run

### Prerequisites
- **Godot 4.3** or later ([download here](https://godotengine.org/download))

### Opening the Project
1. Launch Godot 4
2. Click "Import" on the project manager
3. Browse to this directory and select `project.godot`
4. Click "Import & Edit"

### Running the Game
- Press **F5** in the Godot editor, or
- Click the "Play" button (▶) in the top-right corner
- The main combat scene will launch automatically

## Controls

| Key | Action |
|-----|--------|
| **A** | Rotate ship left |
| **D** | Rotate ship right |
| **W** | Increase throttle |
| **S** | Decrease throttle |
| **Left Click** | Click on enemy ship modules to set focus fire target |

## Gameplay

### Objective
Destroy the enemy ship by targeting its modules while keeping your own ship operational.

### Combat Mechanics
- **Autofire**: Your main turret automatically fires at the focused enemy ship when in range
- **Focus Fire**: Click on specific enemy modules (Turret, Citadel, Hull, Engine) to deal bonus damage to that module
- **Module Damage**: Each ship has 4 modules with independent HP:
  - **Hull**: Main structure (150 HP)
  - **Citadel**: Armored core (100 HP)
  - **Engine**: Propulsion (80 HP)
  - **Turret**: Main weapon (60 HP)
- **Fires**: Hits can start fires that deal damage over time until auto-extinguished
- **Repair**: Modules slowly auto-repair when not on fire
- **Victory**: Destroy all enemy modules to win

### UI Elements
- **Top Left**: Target information and current focus fire module
- **Top Right**: Enemy ship module HP status with fire indicators
- **Bottom Left**: Controls reminder

## Project Structure

```
/
├── project.godot          # Godot project configuration
├── scenes/                # Scene files (.tscn)
│   ├── main.tscn         # Main combat scene (run this)
│   ├── player_ship.tscn  # Player ship with modules
│   ├── enemy_ship.tscn   # Enemy ship with clickable modules
│   └── projectile.tscn   # Turret shell projectile
├── scripts/               # GDScript files (.gd)
│   ├── game_constants.gd # All tunables in one place
│   ├── ship.gd           # Base ship class
│   ├── player_ship.gd    # Player ship controls
│   ├── enemy_ship.gd     # Enemy AI (basic)
│   ├── ship_module.gd    # Module HP/fire/repair logic
│   ├── projectile.gd     # Projectile behavior
│   └── main.gd           # Main scene coordinator
└── art_placeholders/      # Placeholder sprites
    ├── mod_hull_placeholder.png
    ├── mod_citadel_placeholder.png
    ├── mod_engine_placeholder.png
    └── mod_turret_placeholder.png
```

## Tuning Gameplay

All gameplay constants are centralized in `scripts/game_constants.gd`:
- Ship speeds and rotation rates
- Module HP values
- Turret fire rate and range
- Fire mechanics (start chance, damage, extinguish time)
- Repair rates
- Damage values

Edit these values to tune the combat feel.

## MVP Scope

This is the **MVP combat sandbox** only. Future features (not yet implemented):
- Harbor/base screen with upgrades
- Multiple enemy types and spawning
- Boss encounters
- Loot and progression systems
- Map progression
- Multiple ship classes
- Manual turret control

## Development Notes

- Built with Godot 4.3
- Uses GDScript for all game logic
- Placeholder art uses "Nearest" texture filtering for pixel-art style
- Ship sprites face local +Y (forward/bow direction)
- Simple modular damage system ready for expansion

## Design Reference

See `DESIGN.md` for the full vision and design document.
