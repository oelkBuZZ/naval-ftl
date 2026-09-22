# DD-560 Fletcher-class study

A procedural WWII US destroyer built in Blender as a visual stress test. It is a generic square-bridge Fletcher-class massing study, about a 1943 five-gun fit, with the display hull number **560**.

USS *Morrison* (DD-560) was a real Fletcher-class destroyer. This mesh is not a reconstruction of her. The lines, camouflage, and gun fit are simplified study choices, not her as-built or as-lost configuration. Nothing here is taken from World of Warships or other game assets.

## Open the model

Tested in Blender 4.5.12 LTS. Blender 4.2 or newer should open the file.

1. Open `blender/DD560_Fletcher.blend`.
2. Units are meters. The root empty `DD560` sits at midships on the waterline.
3. Axes: **+X bow**, **+Y starboard**, **+Z up**.
4. Collections: `Hull`, `Superstructure`, `Armament`, `Details`, `Environment`.
5. Hide `Environment` to inspect shafts, propellers, the rudder, and the sonar dome. The ocean plane covers them in the renders.
6. Cameras: `Cam_BowQuarter`, `Cam_Broadside`, `Cam_TopDown`.

Shipped renders (1920×1080, Cycles CPU, 48 samples, OpenImageDenoise, AgX):

- `renders/bow_quarter.png`
- `renders/broadside.png`
- `renders/topdown.png`

Optional mesh exports, parented ship meshes only (no ocean, wake, lights, or cameras):

- `blender/DD560_Fletcher.glb` (glTF, Y-up)
- `blender/DD560_Fletcher.fbx` (forward −Z, up Y)

Materials are Principled BSDF colors. They survive the glTF and FBX export as simple PBR values. There is no texture atlas.

## Rebuild

From a machine with Blender on `PATH`:

```bash
blender -b --factory-startup -P art/wwii-destroyer/blender/build_destroyer.py -- --samples 48 --res 1920 1080
```

Useful flags, after `--`:

| Flag | Effect |
| --- | --- |
| `--fast` | 1280×720, 16 samples |
| `--samples N` | Override the sample count |
| `--res W H` | Override the resolution |
| `--views bow_quarter,broadside,topdown` | Which cameras to render |
| `--no-render` | Save the blend and exports only |
| `--no-export` | Skip `.glb` / `.fbx` |
| `--hull-only` | Hull, decks, and underwater gear only |
| `--outdir PATH` | Write PNGs somewhere other than `renders/` |

The script rewrites `blender/DD560_Fletcher.blend`, `blender/build_report.json`, and the exports.

Nominal size: length overall 114.76 m (376 ft 6 in), beam 12.09 m (39 ft 8 in), mean draft 3.90 m. The mesh is a loft, not a lines plan. The builder clamps deck flare so the forecastle does not grow wider than the midship beam.

Paint is a Measure 22-style scheme: antifouling red below the boot, black boot topping, navy blue up to a horizontal line just above the main deck, haze gray above. The main deck is a procedural teak plank shader. The forecastle deck is dark non-skid steel. Guns are dark metal.

What is in the scene, at a glance: sheer and flare, forecastle break, cruiser stern, bulwark, railings, two raked funnels, square bridge with an Mk 37 director, SC-style bedspring and SG dish, five single 5-inch/38 mounts, two quintuple torpedo mounts trained to starboard, four twin 40 mm and eight 20 mm, depth-charge racks and K-guns, whaleboats, anchors, and the hull number on both bows and the transom.

## Gap versus a World of Warships production destroyer

This reads as a destroyer at a glance. It is not a production ship asset.

- **Hull.** The shell is a parametric loft (about 10k triangles) with a cosine entrance and run, sheer, flare, and a cruiser stern. A production hull is cut from a lines plan or a scanned/refit reference, with a knuckle, real stem bar, and propeller apertures that match the class. Draft and LWL here are close to published Fletcher figures; the section shape is not.
- **Density.** The whole ship is about 28k triangles. A WoWs high LOD is typically an order of magnitude heavier, with a LOD chain, collision mesh, and separate damage states. Railings here are tubes, not stanchion-and-wire geometry. Guns are shaped primitives, not Mk 30 / Mk 1 / Mk 2 CAD.
- **Surfaces.** Materials are tiled procedural shaders on generated coordinates. There are no UV atlases, rivet maps, panel breaks, weld beads, weathering, insignia sheets, or unique hull-number textures. The plank shader is a color wave, not boards.
- **Fit.** The AA layout is a simplified mid/late-1943 arrangement (four twin 40 mm, eight 20 mm), not a specific hull's bureau plan. Torpedo mounts are both trained to starboard so the hero side reads. Portholes, doors, and ladders are placed by station, not by a general arrangement drawing.
- **Systems that a game ship needs and this file does not have.** Interiors, crew, flags that simulate, gun elevation animation, damage modules, buoyancy, a water shader, wake particles, or a lighting rig aimed at an in-engine sky. The ocean in the renders is a flat plane under a Nishita sky.
- **Identity.** Hull number 560 is a display marking so the broadside has something to read. It is not a portrait of USS *Morrison*.

`blender/build_report.json` records the triangle counts from the last build.
