#!/usr/bin/env python3
"""Procedural square-bridge Fletcher-class destroyer study model.

Run (headless):

    blender -b --factory-startup -P build_destroyer.py -- --samples 48

Coordinates: meters, Z up, +X bow, +Y starboard, origin at midships on the
waterline. Hull number 560 is a display marking for this generic study, not a
claim about a specific historical ship.

Collections: Hull, Superstructure, Armament, Details, Environment.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

# ---------------------------------------------------------------------------
# Paths & CLI
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
ASSET_DIR = SCRIPT_DIR.parent
RENDER_DIR = ASSET_DIR / "renders"


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    p = argparse.ArgumentParser(description="Build the DD-560 study destroyer")
    p.add_argument("--fast", action="store_true", help="Lower resolution preview render")
    p.add_argument("--no-render", action="store_true")
    p.add_argument("--no-export", action="store_true")
    p.add_argument("--hull-only", action="store_true")
    p.add_argument("--samples", type=int, default=0)
    p.add_argument("--res", type=int, nargs=2, default=None, metavar=("W", "H"))
    p.add_argument("--outdir", default="")
    p.add_argument(
        "--views",
        default="bow_quarter,broadside,topdown",
        help="Comma-separated camera keys",
    )
    return p.parse_args(argv)


ARGS = parse_args()

# ---------------------------------------------------------------------------
# Ship parameters (Fletcher-class, square bridge, ~1943 massing)
# ---------------------------------------------------------------------------

LOA = 114.76          # 376 ft 6 in
BEAM = 12.09          # 39 ft 8 in
DRAFT = 3.90          # ~12 ft 10 in mean draft
FREEBOARD = 3.00      # main deck above WL amidships
FC_RISE = 2.38        # forecastle above main deck
BOW_SHEER = 1.72
STERN_SHEER = 0.64
BREAK_X = 15.20       # forecastle break, +X bow
X_BOW = LOA * 0.5
X_STERN = -LOA * 0.5
CAMBER = 0.10
HULL_NUMBER = "560"

FUNNEL_FWD_X = 10.6
FUNNEL_AFT_X = -6.4
TT_FWD_X = 2.6
TT_AFT_X = -14.0
MAST_FWD_X = 13.7
MAST_AFT_X = -10.4
SEARCHLIGHT_X = 7.35

GUN51_X = 46.4
GUN52_X = 35.4
GUN53_X = -23.6
GUN54_X = -36.6
GUN55_X = -48.2

HOUSE_HALF_W = 3.32
HOUSE_AFT_X0 = -19.8
HOUSE_AFT_DECK_X0 = -28.5
HOUSE_AFT_DECK_X1 = -42.4

# ---------------------------------------------------------------------------
# Math
# ---------------------------------------------------------------------------


def clamp(v, a, b):
    return a if v < a else b if v > b else v


def clamp01(t):
    return clamp(t, 0.0, 1.0)


def smoothstep(edge0, edge1, x):
    if edge0 == edge1:
        return 1.0 if x >= edge1 else 0.0
    t = clamp01((x - edge0) / (edge1 - edge0))
    return t * t * (3.0 - 2.0 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def srgb_to_linear(c):
    def f(u):
        return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4

    return tuple(f(x) for x in c)


def sheer(x):
    half = LOA * 0.5
    if x >= 0.0:
        t = min(1.0, x / half)
        return BOW_SHEER * (t ** 1.48)
    t = min(1.0, -x / half)
    return STERN_SHEER * (t ** 1.32)


def main_deck_z(x):
    return FREEBOARD + sheer(x)


def fc_deck_z(x):
    return main_deck_z(x) + FC_RISE


def deck_top_z(x):
    return fc_deck_z(x) if x >= BREAK_X else main_deck_z(x)


def keel_z(x):
    bow = smoothstep(36.0, 56.2, x)
    stern = smoothstep(-34.0, -56.0, x)
    return -DRAFT + bow * 2.55 + stern * 1.45


def max_half_beam(x):
    """Half-breadth of the design waterline, zero at the ends."""
    u = (x - X_STERN) / LOA
    left, right = 0.30, 0.73
    if u < left:
        c = math.sin((u / left) * math.pi * 0.5) ** 0.60
    elif u > right:
        c = math.cos(((u - right) / (1.0 - right)) * math.pi * 0.5) ** 0.52
    else:
        c = 1.0
    return (BEAM * 0.5) * max(0.0, c)


def half_beam(x, z):
    base = max_half_beam(x)
    zk = keel_z(x)
    h = max(0.0, z - zk)
    local = max(0.40, -zk)
    t = min(1.0, h / local)
    frac = 0.028 + 0.972 * (math.sin(t * math.pi * 0.5) ** 0.70)
    y = base * frac
    if z > 0.20 and base > 0.02:
        bow = smoothstep(16.0, 46.0, x)
        stern = smoothstep(-10.0, -46.0, x)
        tt = min(1.2, (z - 0.20) / 6.0)
        y *= (1.0 + bow * 0.16 * (tt ** 1.12)) * (1.0 - stern * 0.07 * tt)
    # Deck flare must not push the entrance wider than the midship beam.
    return min(max(0.0, y), BEAM * 0.5 * 1.01)


def actual_x(x_nom, z):
    """Deck-edge station x_nom, shifted for stem rake and stern overhang."""
    z_top = deck_top_z(x_nom)
    drop = max(0.0, z_top - z)
    drop_above = min(drop, max(z_top, 0.0))
    drop_below = max(0.0, drop - drop_above)
    bow = smoothstep(22.0, 50.0, x_nom)
    stern = smoothstep(-16.0, -48.0, x_nom)
    dx = -bow * (drop_above * 0.19 + drop_below * 0.58)
    dx += stern * (drop_above * 0.42 + drop_below * 0.62)
    return x_nom + dx


def section_point(x_nom, z):
    zk = keel_z(x_nom)
    zc = zk if z < zk else z
    return (actual_x(x_nom, zc), half_beam(x_nom, zc), zc)


def station_xs(n, x0, x1):
    xs = []
    for i in range(n):
        u = i / (n - 1)
        # Denser stations at bow and stern.
        u2 = 0.5 - 0.5 * math.cos(math.pi * u)
        xs.append(x0 + (x1 - x0) * u2)
    return xs


# ---------------------------------------------------------------------------
# Blender helpers
# ---------------------------------------------------------------------------

ROOT = None
COLS = {}
MATS = {}
_PRIM = {}


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "METERS"


def new_collection(name):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    COLS[name] = col
    return col


def mesh_from(name, verts, faces):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    return me


def link_obj(name, me, col, mat=None, smooth=False, split=None, parent=None):
    obj = bpy.data.objects.new(name, me)
    col.objects.link(obj)
    obj.parent = parent if parent is not None else ROOT
    if mat is not None:
        if isinstance(mat, (list, tuple)):
            for m in mat:
                me.materials.append(m)
        else:
            me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = smooth or split is not None
    if split is not None:
        mod = obj.modifiers.new("EdgeSplit", "EDGE_SPLIT")
        mod.split_angle = math.radians(split)
        mod.use_edge_angle = True
    return obj


def flip_normals(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def outward_side_score(obj):
    score = 0.0
    n = 0
    top = 0.0
    nt = 0
    for p in obj.data.polygons:
        c = p.center
        if abs(p.normal.z) < 0.55 and abs(c.y) > 0.15:
            score += p.normal.y * (1.0 if c.y >= 0.0 else -1.0)
            n += 1
        if p.normal.z > 0.65:
            top += p.normal.z
            nt += 1
    return (score / n if n else 0.0, top / nt if nt else 0.0, n, nt)


def ensure_outward(obj):
    side, top, n, nt = outward_side_score(obj)
    print(f"  normals {obj.name}: side {side:.2f} top {top:.2f} ({n} side / {nt} top)")
    if n and side < 0.0:
        flip_normals(obj)
        side, top, n, nt = outward_side_score(obj)
        print(f"  flipped {obj.name}: side {side:.2f} top {top:.2f}")
    return side, top


def primitive(kind, **kwargs):
    key = (kind, tuple(sorted((k, repr(v)) for k, v in kwargs.items())))
    if key not in _PRIM:
        bm = bmesh.new()
        if kind == "cube":
            bmesh.ops.create_cube(bm, size=1.0)
        elif kind == "cone":
            bmesh.ops.create_cone(bm, **kwargs)
        elif kind == "uv":
            bmesh.ops.create_uvsphere(bm, **kwargs)
        else:
            raise ValueError(kind)
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        verts = [Vector(v.co) for v in bm.verts]
        faces = [tuple(v.index for v in f.verts) for f in bm.faces]
        bm.free()
        _PRIM[key] = (verts, faces)
    verts, faces = _PRIM[key]
    return [v.copy() for v in verts], [tuple(f) for f in faces]


def transform_vf(verts, faces, matrix):
    return [matrix @ v for v in verts], faces


def cat(vf_list):
    verts = []
    faces = []
    for vs, fs in vf_list:
        base = len(verts)
        verts.extend(vs)
        faces.extend([tuple(i + base for i in f) for f in fs])
    return verts, faces


def cube_vf(size):
    """Cube centered on origin. size is full x,y,z."""
    verts, faces = primitive("cube")
    sx, sy, sz = size
    for v in verts:
        v.x *= sx
        v.y *= sy
        v.z *= sz
    return verts, faces


def cylinder_z_vf(radius, depth, n=12, caps=True, z0=None):
    """Cylinder along Z. If z0 is None, centered. radius may be (rx, ry)."""
    if isinstance(radius, (tuple, list)):
        rx, ry = radius
    else:
        rx = ry = radius
    kwargs = dict(cap_ends=caps, cap_tris=False, segments=n, radius1=1.0, radius2=1.0, depth=1.0)
    verts, faces = primitive("cone", **kwargs)
    if z0 is None:
        z_off = 0.0
        scale_z = depth
    else:
        # Template is centered depth 1, from -0.5 to 0.5. Map to z0 .. z0+depth.
        z_off = z0 + depth * 0.5
        scale_z = depth
    out = []
    for v in verts:
        out.append(Vector((v.x * rx, v.y * ry, v.z * scale_z + z_off)))
    return out, faces


def cone_z_vf(r1, r2, depth, n=16, caps=True, z0=0.0):
    verts, faces = primitive(
        "cone",
        cap_ends=caps,
        cap_tris=False,
        segments=n,
        radius1=1.0,
        radius2=1.0,
        depth=1.0,
    )
    out = []
    for v in verts:
        # v.z in [-0.5, 0.5]. Bottom (negative z) uses r1.
        t = v.z + 0.5
        r = lerp(r1, r2, t)
        out.append(Vector((v.x * r, v.y * r, z0 + (v.z + 0.5) * depth)))
    return out, faces


def sphere_vf(radius=1.0, u=16, v=10):
    verts, faces = primitive("uv", u_segments=u, v_segments=v, radius=1.0)
    return [Vector(p) * radius for p in verts], faces


def apply_matrix(verts, matrix):
    return [matrix @ v for v in verts]


def M_trs(loc, rot=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0)):
    return (
        Matrix.Translation(Vector(loc))
        @ Euler(rot, "XYZ").to_matrix().to_4x4()
        @ Matrix.Diagonal(Vector((scale[0], scale[1], scale[2], 1.0)))
    )


def M_basis(origin, x_axis, y_axis, z_axis):
    r = Matrix(
        (
            (x_axis.x, y_axis.x, z_axis.x),
            (x_axis.y, y_axis.y, z_axis.y),
            (x_axis.z, y_axis.z, z_axis.z),
        )
    ).to_4x4()
    return Matrix.Translation(origin) @ r


class MB:
    """Accumulates transformed primitives into one mesh."""

    def __init__(self):
        self.verts = []
        self.faces = []

    def add(self, verts, faces):
        base = len(self.verts)
        self.verts.extend(verts)
        self.faces.extend([tuple(i + base for i in f) for f in faces])

    def add_cube(self, loc, size, rot=(0.0, 0.0, 0.0)):
        v, f = cube_vf(size)
        self.add(apply_matrix(v, M_trs(loc, rot)), f)

    def add_cyl(self, loc, radius, depth, rot=(0.0, 0.0, 0.0), n=10, caps=True):
        v, f = cylinder_z_vf(radius, depth, n=n, caps=caps)
        self.add(apply_matrix(v, M_trs(loc, rot)), f)

    def add_between(self, p0, p1, radius, n=6, caps=True):
        p0 = Vector(p0)
        p1 = Vector(p1)
        d = p1 - p0
        length = d.length
        if length < 1e-5:
            return
        quat = Vector((0.0, 0.0, 1.0)).rotation_difference(d.normalized())
        mid = (p0 + p1) * 0.5
        v, f = cylinder_z_vf(radius, length, n=n, caps=caps)
        M = Matrix.Translation(mid) @ quat.to_matrix().to_4x4()
        self.add(apply_matrix(v, M), f)

    def add_sphere(self, loc, radius, scale=(1, 1, 1), n_u=12, n_v=8):
        v, f = sphere_vf(1.0, n_u, n_v)
        self.add(apply_matrix(v, M_trs(loc, scale=tuple(radius * s for s in scale))), f)

    def object(self, name, col, mat=None, smooth=False, split=None):
        me = mesh_from(name, self.verts, self.faces)
        return link_obj(name, me, col, mat=mat, smooth=smooth, split=split)


def solidify(obj, thickness, offset=-1.0):
    mod = obj.modifiers.new("Solidify", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = offset
    return obj


def quad_area(verts, f):
    pts = [Vector(verts[i]) for i in f]
    if len(pts) < 3:
        return 0.0
    a = 0.0
    for i in range(1, len(pts) - 1):
        a += (pts[i] - pts[0]).cross(pts[i + 1] - pts[0]).length * 0.5
    return a


def filter_faces(verts, faces, min_area=1e-6):
    return [f for f in faces if quad_area(verts, f) > min_area]


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------


def set_bsdf(bsdf, **values):
    for key, val in values.items():
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = val


def new_principled(name, color, rough=0.5, metal=0.0, alpha=1.0, emit=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    col = srgb_to_linear(color)
    set_bsdf(
        bsdf,
        **{
            "Base Color": (*col, 1.0),
            "Roughness": rough,
            "Metallic": metal,
            "Alpha": alpha,
            "Emission Color": (*col, 1.0),
            "Emission Strength": emit,
        },
    )
    MATS[name] = mat
    return mat


def make_materials():
    new_principled("HullNavy", (0.20, 0.28, 0.36), rough=0.46, metal=0.02)
    new_principled("HazeGray", (0.64, 0.66, 0.64), rough=0.48, metal=0.04)
    new_principled("BootBlack", (0.015, 0.015, 0.016), rough=0.28, metal=0.08)
    new_principled("AntiFoul", (0.45, 0.10, 0.07), rough=0.55, metal=0.0)
    new_principled("GunMetal", (0.045, 0.048, 0.052), rough=0.38, metal=0.55)
    new_principled("DarkMetal", (0.02, 0.02, 0.022), rough=0.45, metal=0.35)
    new_principled("Glass", (0.04, 0.07, 0.09), rough=0.08, metal=0.0)
    new_principled("Brass", (0.62, 0.46, 0.18), rough=0.35, metal=0.7)
    new_principled("Canvas", (0.55, 0.52, 0.42), rough=0.75)
    new_principled("LifeRaft", (0.07, 0.07, 0.06), rough=0.7)
    new_principled("White", (0.78, 0.78, 0.74), rough=0.45)
    new_principled("FlagRed", (0.55, 0.07, 0.06), rough=0.55)
    new_principled("FlagBlue", (0.07, 0.11, 0.26), rough=0.55)
    new_principled("Wake", (0.42, 0.52, 0.54), rough=0.78)
    new_principled("Foam", (0.70, 0.74, 0.72), rough=0.65)
    new_principled("WoodBoat", (0.36, 0.24, 0.13), rough=0.62)
    new_principled("NumberBlack", (0.01, 0.012, 0.015), rough=0.6)

    # Worn teak planks along X, seams across Y.
    mat = bpy.data.materials.new("DeckTeak")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "Y"
    wave.inputs["Scale"].default_value = 4.6
    wave.inputs["Distortion"].default_value = 0.35
    wave.inputs["Detail"].default_value = 2.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "LINEAR"
    els = ramp.color_ramp.elements
    els[0].position = 0.0
    els[0].color = (*srgb_to_linear((0.34, 0.22, 0.13)), 1)
    els[1].position = 1.0
    els[1].color = (*srgb_to_linear((0.42, 0.28, 0.16)), 1)
    els.new(0.46).color = (*srgb_to_linear((0.33, 0.21, 0.12)), 1)
    els.new(0.50).color = (*srgb_to_linear((0.09, 0.06, 0.04)), 1)
    els.new(0.54).color = (*srgb_to_linear((0.40, 0.26, 0.15)), 1)
    nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    set_bsdf(bsdf, **{"Roughness": 0.68, "Metallic": 0.0})
    MATS["DeckTeak"] = mat

    mat = bpy.data.materials.new("DeckSteel")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 22.0
    noise.inputs["Detail"].default_value = 5.0
    noise.inputs["Roughness"].default_value = 0.55
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.18
    bump.inputs["Distance"].default_value = 0.015
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    set_bsdf(
        bsdf,
        **{
            "Base Color": (*srgb_to_linear((0.27, 0.30, 0.32)), 1),
            "Roughness": 0.72,
            "Metallic": 0.08,
        },
    )
    MATS["DeckSteel"] = mat

    mat = bpy.data.materials.new("Ocean")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.6
    noise.inputs["Detail"].default_value = 4.0
    noise.inputs["Roughness"].default_value = 0.45
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.06
    bump.inputs["Distance"].default_value = 0.25
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    set_bsdf(
        bsdf,
        **{
            "Base Color": (*srgb_to_linear((0.10, 0.20, 0.26)), 1),
            "Roughness": 0.22,
            "Metallic": 0.0,
            "Specular IOR Level": 0.6,
        },
    )
    MATS["Ocean"] = mat

    # Soot gradient for funnel caps / upper stack is a flat dark metal; body uses haze.


def paint_hull(obj):
    me = obj.data
    me.materials.clear()
    for key in ("AntiFoul", "BootBlack", "HullNavy", "HazeGray"):
        me.materials.append(MATS[key])
    line = FREEBOARD + 0.05
    for p in me.polygons:
        z = p.center.z
        if z < -0.22:
            p.material_index = 0
        elif z < 0.58:
            p.material_index = 1
        elif z < line:
            p.material_index = 2
        else:
            p.material_index = 3


# ---------------------------------------------------------------------------
# Hull
# ---------------------------------------------------------------------------


def make_ring(x_nom, n_side=12):
    z_top = main_deck_z(x_nom)
    zk = keel_z(x_nom)
    stbd = []
    for i in range(n_side + 1):
        t = (i / n_side) ** 0.90
        z = z_top + (zk - z_top) * t
        stbd.append(section_point(x_nom, z))
    stbd[0] = section_point(x_nom, z_top)
    sx, sy, _sz = section_point(x_nom, zk)
    stbd[-1] = (sx, max(sy, 0.0), zk)
    port = [(p[0], -p[1], p[2]) for p in stbd]
    keel = ((stbd[-1][0] + port[-1][0]) * 0.5, 0.0, zk)
    ring = port + [keel] + list(reversed(stbd))
    return ring


def build_hull_shell():
    print("Hull shell...")
    xs = station_xs(96, X_STERN, X_BOW)
    # Guarantee the forecastle break is a station so the deck step is crisp.
    xs.append(BREAK_X)
    xs = sorted(set(round(x, 5) for x in xs))

    deck_xs = []
    prev = None
    for x in xs:
        ax = section_point(x, main_deck_z(x))[0]
        if prev is not None and ax < prev - 1e-3:
            print(f"  WARN station fold at nominal {x:.2f}: {prev:.2f} -> {ax:.2f}")
        prev = ax
        deck_xs.append(ax)

    verts = []
    rings = []
    for x in xs:
        ring = make_ring(x)
        idxs = []
        for p in ring:
            idxs.append(len(verts))
            verts.append(p)
        rings.append(idxs)

    faces = []
    for i in range(len(rings) - 1):
        a = rings[i]
        b = rings[i + 1]
        for j in range(len(a) - 1):
            faces.append((a[j], a[j + 1], b[j + 1], b[j]))

    # Forecastle topsides, sharing the main-deck edge vertices.
    n_band = 4
    fc_index = [i for i, x in enumerate(xs) if x >= BREAK_X - 1e-4]
    stbd_cols = []
    port_cols = []
    for i in fc_index:
        x = xs[i]
        z0 = main_deck_z(x)
        z1 = fc_deck_z(x)
        stbd = [rings[i][-1]]
        port = [rings[i][0]]
        for k in range(1, n_band + 1):
            z = z0 + (z1 - z0) * (k / n_band)
            xw, y, zw = section_point(x, z)
            stbd.append(len(verts))
            verts.append((xw, y, zw))
            port.append(len(verts))
            verts.append((xw, -y, zw))
        stbd_cols.append(stbd)
        port_cols.append(port)
    for i in range(len(fc_index) - 1):
        a_s, b_s = stbd_cols[i], stbd_cols[i + 1]
        a_p, b_p = port_cols[i], port_cols[i + 1]
        for k in range(n_band):
            faces.append((a_s[k], a_s[k + 1], b_s[k + 1], b_s[k]))
            faces.append((a_p[k + 1], a_p[k], b_p[k], b_p[k + 1]))

    faces = filter_faces(verts, faces, 1e-7)
    me = mesh_from("DD560_Hull_Shell", verts, faces)
    obj = link_obj("DD560_Hull_Shell", me, COLS["Hull"], smooth=True, split=36)
    ensure_outward(obj)
    paint_hull(obj)

    # Edge curves for decks / railings (starboard, stern -> bow).
    main_ids = [i for i, x in enumerate(xs) if x <= BREAK_X + 1e-4]
    stbd_main = []
    for i in main_ids:
        # Last vertex of the lower ring is the starboard main-deck edge.
        stbd_main.append(verts[rings[i][-1]])
    stbd_fc = []
    for col in stbd_cols:
        stbd_fc.append(verts[col[-1]])

    # Stats
    bow_tip = section_point(X_BOW, fc_deck_z(X_BOW))
    stern_tip = section_point(X_STERN, main_deck_z(X_STERN))
    wl_bow = section_point(X_BOW, 0.0)
    wl_stern = section_point(X_STERN, 0.0)
    print(
        f"  LOA deck {bow_tip[0] - stern_tip[0]:.2f} m  "
        f"LWL {wl_bow[0] - wl_stern[0]:.2f} m  "
        f"beam mid {2 * half_beam(0, 0.4):.2f} m"
    )
    print(f"  bow tip ({bow_tip[0]:.2f}, {bow_tip[2]:.2f}) stern tip ({stern_tip[0]:.2f}, {stern_tip[2]:.2f})")
    for x in (-54, -48, -30, 0, 20, 35, 45, 52, 56):
        print(
            f"  x {x:6.1f} keel {keel_z(x):6.2f} WL y {half_beam(x, 0):5.2f} "
            f"deck y {half_beam(x, deck_top_z(x)):5.2f} deck z {deck_top_z(x):5.2f} "
            f"ax {actual_x(x, deck_top_z(x)):6.2f}"
        )
    return {
        "xs": xs,
        "stbd_main": stbd_main,
        "stbd_fc": stbd_fc,
        "bow_tip": bow_tip,
        "stern_tip": stern_tip,
    }


def build_deck_from_edge(name, stbd_pts, z_shift=0.0, camber=CAMBER, overhang=1.012):
    """stbd_pts stern->bow. Returns an object with the deck top only."""
    rows = 8
    verts = []
    n = len(stbd_pts)
    for i, p in enumerate(stbd_pts):
        x, y, z = p
        y *= overhang
        z = z + z_shift
        port = (x, -y, z)
        star = (x, y, z)
        for r in range(rows + 1):
            f = r / rows
            px = lerp(port[0], star[0], f)
            py = lerp(port[1], star[1], f)
            pz = lerp(port[2], star[2], f)
            half = max(abs(y), 0.001)
            c = camber * (1.0 - (py / half) ** 2) if half > 0.05 else 0.0
            verts.append((px, py, pz + c))
    faces = []
    for i in range(n - 1):
        for r in range(rows):
            a = i * (rows + 1) + r
            faces.append((a, a + (rows + 1), a + (rows + 1) + 1, a + 1))
    faces = filter_faces(verts, faces, 1e-8)
    return verts, faces


def build_decks(curves):
    print("Decks...")
    v, f = build_deck_from_edge("main", curves["stbd_main"])
    me = mesh_from("DD560_Deck_Main", v, f)
    deck = link_obj("DD560_Deck_Main", me, COLS["Hull"], mat=MATS["DeckTeak"], smooth=True, split=55)
    solidify(deck, 0.10, offset=-1.0)

    v, f = build_deck_from_edge("fc", curves["stbd_fc"])
    me = mesh_from("DD560_Deck_Forecastle", v, f)
    deck = link_obj(
        "DD560_Deck_Forecastle", me, COLS["Hull"], mat=MATS["DeckSteel"], smooth=True, split=55
    )
    solidify(deck, 0.10, offset=-1.0)


def path_offset_dirs(path):
    dirs = []
    n = len(path)
    for i in range(n):
        if n == 1:
            d = Vector((1, 0, 0))
        elif i == 0:
            d = Vector(path[1]) - Vector(path[0])
        elif i == n - 1:
            d = Vector(path[-1]) - Vector(path[-2])
        else:
            d = Vector(path[i + 1]) - Vector(path[i - 1])
        d.z = 0.0
        if d.length < 1e-8:
            d = Vector((1, 0, 0))
        d.normalize()
        dirs.append(Vector((-d.y, d.x, 0.0)))
    return dirs


def build_bulwark(stbd_fc):
    """Solid forecastle bulwark around the bow."""
    print("Bulwark...")
    if len(stbd_fc) < 3:
        return
    # Drop the inboard break point slightly so the bulwark starts a touch forward,
    # leaving the break bulkhead clean. Use the whole curve.
    path = list(stbd_fc) + [(p[0], -p[1], p[2]) for p in reversed(stbd_fc[:-1])]
    # Remove near-duplicates
    clean = [path[0]]
    for p in path[1:]:
        if (Vector(p) - Vector(clean[-1])).length > 0.05:
            clean.append(p)
    path = clean
    outs = path_offset_dirs(path)
    height = 0.78
    thick = 0.07
    verts = []
    for p, o in zip(path, outs):
        base = Vector(p)
        outer = base + o * 0.012
        inner = base - o * thick
        verts.extend(
            [
                tuple(outer),
                tuple(inner),
                tuple(inner + Vector((0, 0, height))),
                tuple(outer + Vector((0, 0, height))),
            ]
        )
    faces = []
    n = len(path)
    for i in range(n - 1):
        a = i * 4
        b = (i + 1) * 4
        # 0 outer bot, 1 inner bot, 2 inner top, 3 outer top
        faces.append((a + 0, b + 0, b + 3, a + 3))  # outer
        faces.append((a + 1, a + 2, b + 2, b + 1))  # inner
        faces.append((a + 3, b + 3, b + 2, a + 2))  # top
        faces.append((a + 0, a + 1, b + 1, b + 0))  # bottom
    # End caps
    faces.append((0, 3, 2, 1))
    e = (n - 1) * 4
    faces.append((e + 0, e + 1, e + 2, e + 3))
    me = mesh_from("DD560_Bulwark_Forecastle", verts, faces)
    obj = link_obj("DD560_Bulwark_Forecastle", me, COLS["Hull"], mat=MATS["HazeGray"], smooth=False)
    ensure_outward(obj)

    # Cap rail
    mb = MB()
    for i in range(n - 1):
        p0 = Vector(path[i]) + Vector((0, 0, height))
        p1 = Vector(path[i + 1]) + Vector((0, 0, height))
        mb.add_between(p0, p1, 0.035, n=6)
    mb.object("DD560_Bulwark_CapRail", COLS["Hull"], mat=MATS["DarkMetal"], smooth=True, split=50)


def resample_path(path, spacing):
    if len(path) < 2:
        return [Vector(p) for p in path]
    pts = [Vector(p) for p in path]
    out = [pts[0]]
    acc = 0.0
    for i in range(len(pts) - 1):
        seg = pts[i + 1] - pts[i]
        L = seg.length
        if L < 1e-6:
            continue
        d = seg / L
        pos = 0.0
        while acc + (L - pos) >= spacing:
            need = spacing - acc
            pos += need
            out.append(pts[i] + d * pos)
            acc = 0.0
            if pos >= L - 1e-6:
                break
        else:
            acc += L - pos
            continue
    if (pts[-1] - out[-1]).length > spacing * 0.35:
        out.append(pts[-1])
    return out


def build_railings(stbd_main):
    print("Railings...")
    path = list(reversed(stbd_main)) + [(p[0], -p[1], p[2]) for p in stbd_main[1:]]
    clean = [path[0]]
    for p in path[1:]:
        if (Vector(p) - Vector(clean[-1])).length > 0.08:
            clean.append(p)
    samples = resample_path(clean, 0.85)
    mb = MB()
    h1, h2 = 0.48, 0.98
    for i, p in enumerate(samples):
        if i % 2 == 0:
            mb.add_between(p, p + Vector((0, 0, h2)), 0.018, n=5)
        if i:
            a = samples[i - 1]
            b = p
            mb.add_between(a + Vector((0, 0, h1)), b + Vector((0, 0, h1)), 0.012, n=4, caps=False)
            mb.add_between(a + Vector((0, 0, h2)), b + Vector((0, 0, h2)), 0.014, n=4, caps=False)
    mb.object("DD560_Railings_Main", COLS["Details"], mat=MATS["DarkMetal"], smooth=True)


def build_break_wings(curves):
    """Close the forecastle break outboard of the midship deckhouse."""
    if not curves["stbd_fc"] or not curves["stbd_main"]:
        return
    # Aft-most forecastle edge and the break station on the main edge.
    fc = curves["stbd_fc"][0]
    # Find main-edge point nearest the break (last main point).
    main = curves["stbd_main"][-1]
    hw = HOUSE_HALF_W
    verts = []
    faces = []
    for sign in (1.0, -1.0):
        y_in = sign * hw
        outer_fc = Vector((fc[0], sign * fc[1], fc[2]))
        outer_main = Vector((main[0], sign * main[1], main[2]))
        z_bot_in = main_deck_z(BREAK_X)
        z_top_in = fc_deck_z(BREAK_X)
        inner_bot = Vector((BREAK_X, y_in, z_bot_in))
        inner_top = Vector((BREAK_X, y_in, z_top_in))
        base = len(verts)
        verts.extend([tuple(outer_main), tuple(inner_bot), tuple(inner_top), tuple(outer_fc)])
        if sign > 0:
            faces.append((base, base + 1, base + 2, base + 3))
        else:
            faces.append((base, base + 3, base + 2, base + 1))
    me = mesh_from("DD560_Break_Wings", verts, faces)
    link_obj("DD560_Break_Wings", me, COLS["Hull"], mat=MATS["HazeGray"], smooth=False)


def build_bilge_keels():
    mb_v = []
    mb_f = []

    def strip(sign):
        xs = [ -20 + i * 1.6 for i in range(30) ]
        pts = []
        for x in xs:
            sx, sy, sz = section_point(x, -1.25)
            pts.append(Vector((sx, sign * sy, sz)))
        verts = []
        # Plate extends outboard and down.
        direction = Vector((0, sign * 0.55, -0.72)).normalized()
        for p in pts:
            verts.append(tuple(p + direction * 0.02))
            verts.append(tuple(p + direction * 0.48))
        faces = []
        for i in range(len(pts) - 1):
            a = i * 2
            b = a + 2
            if sign > 0:
                faces.append((a, b, b + 1, a + 1))
            else:
                faces.append((a, a + 1, b + 1, b))
        return verts, faces

    v1, f1 = strip(1.0)
    v2, f2 = strip(-1.0)
    base = len(v1)
    verts = v1 + v2
    faces = f1 + [tuple(i + base for i in f) for f in f2]
    me = mesh_from("DD560_BilgeKeels", verts, faces)
    link_obj("DD560_BilgeKeels", me, COLS["Hull"], mat=MATS["AntiFoul"], smooth=False)


# ---------------------------------------------------------------------------
# Superstructure
# ---------------------------------------------------------------------------


def loft_box(name, x0, x1, half_w, height, z_fn, n, col, mat, clamp_beam=True):
    # Stations run aft to forward so side-face winding stays outward.
    if x1 < x0:
        x0, x1 = x1, x0
    xs = [lerp(x0, x1, i / (n - 1)) for i in range(n)]
    verts = []
    rings = []
    for x in xs:
        zb = z_fn(x)
        hw = half_w
        if clamp_beam:
            hw = min(hw, max(0.4, half_beam(x, zb) - 0.55))
        cs = [
            (x, -hw, zb),
            (x, hw, zb),
            (x, hw, zb + height),
            (x, -hw, zb + height),
        ]
        idxs = []
        for p in cs:
            idxs.append(len(verts))
            verts.append(p)
        rings.append(idxs)
    faces = []
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(4):
            j2 = (j + 1) % 4
            faces.append((a[j], a[j2], b[j2], b[j]))
    # End caps: aft (first) normal -X, fwd (last) normal +X.
    faces.append(tuple(reversed(rings[0])))
    faces.append(tuple(rings[-1]))
    me = mesh_from(name, verts, faces)
    obj = link_obj(name, me, col, mat=mat, smooth=False)
    ensure_outward(obj)
    return obj


def add_funnel(name, x, height, rx=1.72, ry=1.18, rake_deg=-8.0):
    z_base = main_deck_z(x) + FC_RISE - 0.05
    n = 22
    parts = []

    def rings(r_bot, r_top, z0, z1, ellipse=True):
        vs = []
        for z, r in ((z0, r_bot), (z1, r_top)):
            for i in range(n):
                a = 2 * math.pi * i / n
                yy = math.sin(a) * (ry if ellipse else 1.0) * r
                xx = math.cos(a) * (rx if ellipse else 1.0) * r
                vs.append(Vector((xx, yy, z)))
        return vs

    def side_faces(base_index=0):
        fs = []
        for i in range(n):
            j = (i + 1) % n
            fs.append((base_index + i, base_index + j, base_index + n + j, base_index + n + i))
        return fs

    # Outer shell, open.
    outer = rings(1.0, 0.90, 0.0, height)
    faces = side_faces(0)
    # Cap skirt
    skirt = rings(0.92, 1.22, height - 0.05, height + 0.38)
    b = len(outer)
    outer.extend(skirt)
    faces.extend(side_faces(b))
    # Annulus at the lip (top face).
    lip_z = height + 0.38
    lip = rings(0.78, 1.22, lip_z, lip_z)
    # rings() emits two coincident rings; use first n as inner and we need outer.
    # Rebuild annulus explicitly.
    ann = []
    for r_scale, rad_x, rad_y in ((0.70, rx * 0.90, ry * 0.90), (1.22, rx, ry)):
        for i in range(n):
            a = 2 * math.pi * i / n
            ann.append(Vector((math.cos(a) * rad_x, math.sin(a) * rad_y, lip_z)))
    b = len(outer)
    outer.extend(ann)
    for i in range(n):
        j = (i + 1) % n
        # +Z facing annulus
        faces.append((b + i, b + n + i, b + n + j, b + j))
    # Inner flue
    inner = []
    for z, rs in ((0.15, 0.72), (height * 0.96, 0.62)):
        for i in range(n):
            a = 2 * math.pi * i / n
            inner.append(Vector((math.cos(a) * rx * rs, math.sin(a) * ry * rs, z)))
    b = len(outer)
    outer.extend(inner)
    for i in range(n):
        j = (i + 1) % n
        # Inward-facing: reverse of outward so the interior is visible dark
        faces.append((b + i, b + n + i, b + n + j, b + j))
    # Flue floor
    faces.append(tuple(range(b + n - 1, b - 1, -1)))

    rake = math.radians(rake_deg)
    M = Matrix.Translation(Vector((x, 0.0, z_base))) @ Euler((0.0, rake, 0.0), "XYZ").to_matrix().to_4x4()
    verts = [M @ v for v in outer]
    # Split materials: we'll use two objects instead for cap vs body. Simpler: one haze object
    # and a separate black cap. Rebuild as two meshes.
    # Keep a single mesh with haze; add black pieces separately.
    me = mesh_from(name, verts, filter_faces(verts, faces, 1e-8))
    obj = link_obj(name, me, COLS["Superstructure"], mat=MATS["HazeGray"], smooth=True, split=48)
    ensure_outward(obj)

    # Black cap ring + interior as a second mesh (same transform), dark.
    cap_vs = []
    cap_fs = []
    skirt_b = rings(0.95, 1.24, height + 0.05, height + 0.55)
    cap_vs.extend(skirt_b)
    cap_fs.extend(side_faces(0))
    inn = []
    for z, rs in ((0.2, 0.68), (height * 0.97, 0.58)):
        for i in range(n):
            a = 2 * math.pi * i / n
            inn.append(Vector((math.cos(a) * rx * rs, math.sin(a) * ry * rs, z)))
    b = len(cap_vs)
    cap_vs.extend(inn)
    for i in range(n):
        j = (i + 1) % n
        cap_fs.append((b + j, b + n + j, b + n + i, b + i))
    cap_vs = [M @ v for v in cap_vs]
    me = mesh_from(name + "_Cap", cap_vs, filter_faces(cap_vs, cap_fs, 1e-8))
    link_obj(name + "_Cap", me, COLS["Superstructure"], mat=MATS["DarkMetal"], smooth=True, split=48)

    # Whistle on the forward funnel only, added by caller if wanted.
    return z_base + height


def build_superstructure():
    print("Superstructure...")
    # Midship deckhouse: roof continues the forecastle level.
    loft_box(
        "DD560_Deckhouse_Mid",
        HOUSE_AFT_X0,
        BREAK_X,
        HOUSE_HALF_W,
        FC_RISE,
        main_deck_z,
        14,
        COLS["Superstructure"],
        MATS["HazeGray"],
    )
    # After deckhouse.
    loft_box(
        "DD560_Deckhouse_Aft",
        HOUSE_AFT_DECK_X0,
        HOUSE_AFT_DECK_X1,
        3.05,
        2.32,
        main_deck_z,
        8,
        COLS["Superstructure"],
        MATS["HazeGray"],
    )
    # Bridge trunk + pilothouse on the forecastle.
    loft_box(
        "DD560_Bridge_Trunk",
        16.5,
        23.2,
        2.40,
        2.48,
        fc_deck_z,
        6,
        COLS["Superstructure"],
        MATS["HazeGray"],
    )
    loft_box(
        "DD560_Pilothouse",
        23.2,
        30.5,
        2.55,
        2.48,
        fc_deck_z,
        6,
        COLS["Superstructure"],
        MATS["HazeGray"],
    )
    build_bridge_top()
    build_funnels_masts()
    build_director()


def build_bridge_top():
    """Open bridge, wings, and splinter shields sitting on the pilothouse roof."""
    mb = MB()
    # Wing platforms and a center floor, following forecastle sheer in short segments.
    x0, x1 = 18.2, 30.3
    segments = 8
    for i in range(segments):
        xa = lerp(x0, x1, i / segments)
        xb = lerp(x0, x1, (i + 1) / segments)
        xm = (xa + xb) * 0.5
        z = fc_deck_z(xm) + 2.48
        span = xb - xa
        # Center floor over pilothouse / trunk
        mb.add_cube(((xa + xb) * 0.5, 0.0, z + 0.06), (span + 0.02, 5.0, 0.12))
        # Wings
        for sign in (1.0, -1.0):
            beam = half_beam(xm, fc_deck_z(xm))
            y_in = 2.45
            y_out = min(beam - 0.35, 5.55)
            if y_out <= y_in + 0.2:
                continue
            yc = sign * (y_in + y_out) * 0.5
            w = abs(y_out - y_in)
            mb.add_cube(((xa + xb) * 0.5, yc, z + 0.05), (span + 0.02, w, 0.10))
            # Splinter shield at the outboard edge and a forward shield segment.
            mb.add_cube((xm, sign * (y_out - 0.04), z + 0.55), (span, 0.06, 0.95))
    # Front shield across the pilothouse face.
    zf = fc_deck_z(30.2) + 2.48
    mb.add_cube((30.25, 0.0, zf + 0.55), (0.08, 5.1, 1.05))
    # Side shields on the pilothouse itself.
    for sign in (1.0, -1.0):
        mb.add_cube((26.6, sign * 2.52, fc_deck_z(26.6) + 2.48 + 0.55), (7.2, 0.06, 1.05))
    # Windshield glass panels on the front.
    glass = MB()
    zf = fc_deck_z(30.15) + 2.55
    for i, y in enumerate((-1.15, 0.0, 1.15)):
        glass.add_cube((30.34, y, zf + 0.72), (0.03, 0.85, 0.42))
    # Side windows on pilothouse.
    for sign in (1.0, -1.0):
        for x in (25.0, 27.2, 29.0):
            glass.add_cube((x, sign * 2.60, fc_deck_z(x) + 1.35), (0.55, 0.03, 0.38))
        # Front corner windows
        glass.add_cube((30.55, sign * 1.7, fc_deck_z(30.2) + 1.35), (0.03, 0.48, 0.38))
    mb.object("DD560_OpenBridge", COLS["Superstructure"], mat=MATS["HazeGray"], smooth=False)
    glass.object("DD560_Bridge_Windows", COLS["Superstructure"], mat=MATS["Glass"], smooth=False)

    # Canvas dodgers on the wing rails (slightly darker).
    dod = MB()
    for sign in (1.0, -1.0):
        for x in (20.5, 24.0, 27.5):
            z = fc_deck_z(x) + 2.48
            beam = half_beam(x, fc_deck_z(x))
            y = sign * min(beam - 0.55, 5.35)
            dod.add_cube((x, y, z + 0.55), (1.3, 0.04, 0.7))
    dod.object("DD560_Bridge_Dodgers", COLS["Superstructure"], mat=MATS["Canvas"], smooth=False)


def build_director():
    x = 19.6
    z = fc_deck_z(x) + 2.48
    mb = MB()
    # Pedestal
    v, f = cylinder_z_vf(0.78, 2.15, n=16, caps=True, z0=0.0)
    mb.add(apply_matrix(v, M_trs((x, 0, z))), f)
    # Director tub
    v, f = cylinder_z_vf((1.35, 1.15), 2.15, n=18, caps=True, z0=0.0)
    mb.add(apply_matrix(v, M_trs((x, 0, z + 2.15))), f)
    # Rangefinder ears
    v, f = cylinder_z_vf(0.26, 3.7, n=12, caps=True)
    mb.add(apply_matrix(v, M_trs((x + 0.15, 0, z + 3.15), rot=(0, math.pi / 2, 0))), f)
    # Front visor
    mb.add_cube((x + 1.15, 0, z + 3.35), (0.55, 1.3, 0.45))
    # Mk 12 radar on the roof
    mb.add_cube((x + 0.15, 0.0, z + 4.55), (0.25, 1.5, 0.85))
    mb.object("DD560_Director_Mk37", COLS["Superstructure"], mat=MATS["HazeGray"], smooth=True, split=42)
    # Dark radar face
    face = MB()
    face.add_cube((x + 0.30, 0.0, z + 4.55), (0.06, 1.35, 0.7))
    face.object("DD560_Director_Radar", COLS["Armament"], mat=MATS["DarkMetal"], smooth=False)


def build_funnels_masts():
    h1 = add_funnel("DD560_Funnel_Fwd", FUNNEL_FWD_X, 7.7, rx=1.78, ry=1.22, rake_deg=-8.5)
    h2 = add_funnel("DD560_Funnel_Aft", FUNNEL_AFT_X, 7.05, rx=1.62, ry=1.12, rake_deg=-8.0)
    print(f"  funnel tops approx fwd {h1:.1f} aft {h2:.1f}")

    # Whistle
    mb = MB()
    z = main_deck_z(FUNNEL_FWD_X) + FC_RISE + 5.4
    mb.add_cyl((FUNNEL_FWD_X + 1.55, 0.35, z), 0.06, 0.55, rot=(0, math.radians(70), 0), n=8)
    mb.add_sphere((FUNNEL_FWD_X + 1.85, 0.35, z + 0.15), 0.10, n_u=8, n_v=6)
    mb.object("DD560_Whistle", COLS["Details"], mat=MATS["Brass"], smooth=True)

    build_mast(
        "DD560_Mast_Fore",
        MAST_FWD_X,
        main_deck_z(MAST_FWD_X) + FC_RISE,
        top_z=21.2,
        yard_z=15.6,
        yard_half=4.6,
        radar=True,
    )
    build_mast(
        "DD560_Mast_Main",
        MAST_AFT_X,
        main_deck_z(MAST_AFT_X) + FC_RISE,
        top_z=main_deck_z(MAST_AFT_X) + FC_RISE + 6.8,
        yard_z=main_deck_z(MAST_AFT_X) + FC_RISE + 4.6,
        yard_half=2.4,
        radar=False,
    )

    # Searchlight platform between the stacks, clear of the forward tubes.
    z = main_deck_z(SEARCHLIGHT_X) + FC_RISE
    plat = MB()
    plat.add_cube((SEARCHLIGHT_X, 0.0, z + 2.55), (1.5, 2.4, 0.08))
    for y in (-0.55, 0.55):
        for xoff in (-0.45, 0.45):
            plat.add_between(
                (SEARCHLIGHT_X + xoff, y, z + 0.05),
                (SEARCHLIGHT_X + xoff, y, z + 2.55),
                0.035,
                n=5,
            )
    plat.object("DD560_Searchlight_Platform", COLS["Superstructure"], mat=MATS["HazeGray"], smooth=False)
    lights = MB()
    for y in (-0.55, 0.55):
        lights.add_cyl((SEARCHLIGHT_X, y, z + 2.85), 0.22, 0.38, n=12)
        lights.add_sphere((SEARCHLIGHT_X + 0.18, y, z + 3.05), 0.20, scale=(0.7, 1, 1), n_u=12, n_v=8)
        lights.add_cyl((SEARCHLIGHT_X + 0.32, y, z + 3.05), 0.12, 0.06, rot=(0, math.pi / 2, 0), n=10)
    lights.object("DD560_Searchlights", COLS["Details"], mat=MATS["HazeGray"], smooth=True, split=40)
    glass = MB()
    for y in (-0.55, 0.55):
        glass.add_cyl((SEARCHLIGHT_X + 0.36, y, z + 3.05), 0.09, 0.02, rot=(0, math.pi / 2, 0), n=10)
    glass.object("DD560_Searchlight_Glass", COLS["Details"], mat=MATS["Glass"], smooth=True)


def build_mast(name, x, z_base, top_z, yard_z, yard_half, radar=False):
    mb = MB()
    mb.add_between((x, 0, z_base), (x, 0, top_z), 0.11, n=8)
    mb.add_between((x, -yard_half, yard_z), (x, yard_half, yard_z), 0.045, n=6)
    # Small truck / yard lifts
    for y in (-yard_half * 0.55, 0.0, yard_half * 0.55):
        mb.add_between((x, y, yard_z), (x, y, yard_z + 0.45), 0.02, n=4)
    # Stays
    stay_z = z_base + (top_z - z_base) * 0.72
    for y, x2 in ((2.6, x - 1.2), (-2.6, x - 1.2), (1.8, x + 1.5), (-1.8, x + 1.5)):
        mb.add_between((x, 0, stay_z), (x2, y, z_base + 0.15), 0.015, n=4, caps=False)
    if radar:
        # SC bedspring ahead of the masthead, tilted back.
        top = top_z - 0.3
        tilt = math.radians(-18)
        frame_w, frame_h = 4.3, 2.15
        cz = top - 0.2
        cx = x + 0.55
        # Vertical uprights and horizontal wires in a tilted plane.
        for i in range(7):
            yy = lerp(-frame_w * 0.5, frame_w * 0.5, i / 6)
            p0 = Vector((cx, yy, cz - frame_h * 0.5))
            p1 = Vector((cx - math.sin(tilt) * frame_h, yy, cz - frame_h * 0.5 + math.cos(tilt) * frame_h))
            # shift so the array sits just forward
            mb.add_between(p0, p1, 0.018, n=4, caps=False)
        for k in range(5):
            t = k / 4
            z0 = cz - frame_h * 0.5 + t * frame_h
            x0 = cx - math.sin(tilt) * (t * frame_h)
            mb.add_between(
                (x0, -frame_w * 0.5, z0),
                (x0, frame_w * 0.5, z0),
                0.016,
                n=4,
                caps=False,
            )
        # SG dish lower on the mast, facing forward.
        dish_z = z_base + (top_z - z_base) * 0.58
        v, f = cone_z_vf(0.85, 0.05, 0.35, n=14, caps=True, z0=0.0)
        # Point the dish forward (+X): cone axis +Z -> +X via Ry +90, then tilt up a little.
        M = M_trs((x + 0.9, 0.0, dish_z), rot=(0.0, math.radians(75), 0.0))
        mb.add(apply_matrix(v, M), f)
    mb.object(name, COLS["Superstructure"], mat=MATS["HazeGray"], smooth=True, split=50)


# ---------------------------------------------------------------------------
# Armament
# ---------------------------------------------------------------------------


def gun_house_vf():
    """Mk 30-like shield. Local +X forward, origin at the deck/barbette top, Z up."""
    # Start from a cube spanning x -2.25..2.25, y -1.85..1.85, z 0..2.30
    verts, faces = cube_vf((4.7, 3.70, 2.30))
    for v in verts:
        v.z += 1.15  # sit on z=0
        if v.z > 1.4 and v.x > 0.4:
            v.x -= 0.95  # slope the face back
        if v.z > 1.6 and v.x < -0.4:
            v.z -= 0.12
            v.x += 0.15
    # Side sight hoods: two small cubes
    extras = []
    for y in (-0.55, 0.55):
        v2, f2 = cube_vf((0.7, 0.38, 0.28))
        M = Matrix.Translation(Vector((0.35, y, 2.35)))
        extras.append((apply_matrix(v2, M), f2))
    # Rear bustle
    v3, f3 = cube_vf((0.85, 2.1, 1.15))
    extras.append((apply_matrix(v3, Matrix.Translation(Vector((-2.45, 0.0, 0.85)))), f3))
    verts, faces = cat([(verts, faces)] + extras)
    return verts, faces


def add_barrel(mb_verts_faces, length, radius, muzzle, n=12):
    v, f = cylinder_z_vf(radius, length, n=n, caps=True, z0=0.0)
    # Cylinder along Z starting at 0. Map Z to +X.
    M = Matrix.Translation(Vector(muzzle)) @ Euler((0.0, math.radians(90), 0.0), "XYZ").to_matrix().to_4x4()
    # Ry+90 maps +Z to +X, but the cylinder occupies z 0..length around? z0=0 means z from 0 to length
    # centered? cylinder_z_vf z0=0 places from 0 to depth. Ry+90 around origin maps that to +X. Good.
    return apply_matrix(v, M), f


def build_5in(name, x, z_deck, barbette_h, train_deg, elev_deg):
    """Enclosed 5\"/38. train 0 points forward (+X); 180 points aft."""
    parts = []
    # Barbette, fixed (no train), embedded slightly.
    v, f = cylinder_z_vf(1.55, barbette_h + 0.08, n=16, caps=True, z0=-0.08)
    parts.append((apply_matrix(v, Matrix.Translation(Vector((x, 0.0, z_deck)))), f))

    house_v, house_f = gun_house_vf()
    # Barrel exits the sloped face. Trunnion height ~1.15, start just outside the face.
    elev = math.radians(elev_deg)
    muzzle_local = Vector((2.05, 0.0, 1.18))
    direction = Vector((math.cos(elev), 0.0, math.sin(elev)))
    # Visible barrel
    barrel_len = 4.45
    bv, bf = cylinder_z_vf(0.085, barrel_len, n=12, caps=True, z0=0.0)
    # Jacket near the face
    jv, jf = cylinder_z_vf(0.14, 1.15, n=12, caps=True, z0=0.0)
    Rb = Matrix.Translation(muzzle_local) @ Euler((0.0, -elev, 0.0), "XYZ").to_matrix().to_4x4()
    # cylinder lies on Z; rotate onto the elevated +X axis.
    # Build barrel along local +X directly:
    barrel_pts = apply_matrix(bv, Euler((0.0, math.radians(90), 0.0), "XYZ").to_matrix().to_4x4())
    # After Ry90, cylinder that ran +Z from 0..len now runs +X from 0..len, still at origin.
    barrel_pts = apply_matrix(barrel_pts, Rb)
    jacket_pts = apply_matrix(jv, Euler((0.0, math.radians(90), 0.0), "XYZ").to_matrix().to_4x4())
    jacket_pts = apply_matrix(jacket_pts, Rb)

    train = math.radians(train_deg)
    Mt = Matrix.Translation(Vector((x, 0.0, z_deck + barbette_h))) @ Euler(
        (0.0, 0.0, train), "XYZ"
    ).to_matrix().to_4x4()
    parts.append((apply_matrix(house_v, Mt), house_f))
    parts.append((apply_matrix(barrel_pts, Mt), bf))
    parts.append((apply_matrix(jacket_pts, Mt), jf))
    verts, faces = cat(parts)
    me = mesh_from(name, verts, faces)
    link_obj(name, me, COLS["Armament"], mat=MATS["GunMetal"], smooth=True, split=48)


def build_torpedo_mount(name, x, train_deg=90.0):
    z = main_deck_z(x) + FC_RISE
    parts = []
    v, f = cylinder_z_vf(1.25, 0.48, n=16, caps=True, z0=0.0)
    parts.append((v, f))
    # Training mass
    v, f = cube_vf((1.6, 2.4, 0.35))
    parts.append((apply_matrix(v, Matrix.Translation(Vector((0.0, 0.0, 0.65)))), f))
    for i in range(5):
        y = (i - 2) * 0.66
        v, f = cylinder_z_vf(0.30, 8.3, n=12, caps=True, z0=0.0)
        # Along +X, centered so the mount center is the trunnion.
        M = Matrix.Translation(Vector((-4.15, y, 0.95))) @ Euler((0.0, math.radians(90), 0.0), "XYZ").to_matrix().to_4x4()
        # cylinder z0=0 runs 0..depth on Z. Ry90 maps +Z to +X so it runs 0..8.3 on X
        # then translation x=-4.15 puts it from -4.15 to 4.15. Good.
        parts.append((apply_matrix(v, M), f))
        # Muzzle ring at +X end
        v, f = cylinder_z_vf(0.36, 0.12, n=12, caps=False, z0=0.0)
        M2 = Matrix.Translation(Vector((4.05, y, 0.95))) @ Euler((0.0, math.radians(90), 0.0), "XYZ").to_matrix().to_4x4()
        parts.append((apply_matrix(v, M2), f))
    verts, faces = cat(parts)
    Mt = Matrix.Translation(Vector((x, 0.0, z))) @ Euler((0.0, 0.0, math.radians(train_deg)), "XYZ").to_matrix().to_4x4()
    verts = apply_matrix(verts, Mt)
    me = mesh_from(name, verts, faces)
    link_obj(name, me, COLS["Armament"], mat=MATS["GunMetal"], smooth=True, split=46)


def build_40mm(name, x, y, z, train_deg=0.0, elev_deg=40.0):
    parts = []
    # Tub
    v, f = cylinder_z_vf(1.08, 1.02, n=16, caps=True, z0=0.0)
    parts.append((v, f))
    # Carriage
    v, f = cube_vf((0.7, 0.7, 0.45))
    parts.append((apply_matrix(v, Matrix.Translation(Vector((0, 0, 1.05)))), f))
    elev = math.radians(elev_deg)
    for dy in (-0.16, 0.16):
        bv, bf = cylinder_z_vf(0.045, 2.55, n=8, caps=True, z0=0.0)
        muzzle = Vector((0.35, dy, 1.35))
        Rb = Matrix.Translation(muzzle) @ Euler((0.0, -elev, 0.0), "XYZ").to_matrix().to_4x4()
        pts = apply_matrix(bv, Euler((0.0, math.radians(90), 0.0), "XYZ").to_matrix().to_4x4())
        pts = apply_matrix(pts, Rb)
        parts.append((pts, bf))
    verts, faces = cat(parts)
    Mt = Matrix.Translation(Vector((x, y, z))) @ Euler((0.0, 0.0, math.radians(train_deg)), "XYZ").to_matrix().to_4x4()
    verts = apply_matrix(verts, Mt)
    me = mesh_from(name, verts, faces)
    link_obj(name, me, COLS["Armament"], mat=MATS["GunMetal"], smooth=True, split=48)


def build_20mm(name, x, y, z, train_deg=90.0, elev_deg=35.0):
    mb_parts = []
    v, f = cylinder_z_vf(0.16, 1.05, n=8, caps=True, z0=0.0)
    mb_parts.append((v, f))
    v, f = cube_vf((0.08, 0.55, 0.42))
    mb_parts.append((apply_matrix(v, Matrix.Translation(Vector((0.25, 0.0, 1.25)))), f))
    elev = math.radians(elev_deg)
    bv, bf = cylinder_z_vf(0.025, 1.35, n=6, caps=True, z0=0.0)
    Rb = Matrix.Translation(Vector((0.30, 0.0, 1.22))) @ Euler((0.0, -elev, 0.0), "XYZ").to_matrix().to_4x4()
    pts = apply_matrix(bv, Euler((0.0, math.radians(90), 0.0), "XYZ").to_matrix().to_4x4())
    pts = apply_matrix(pts, Rb)
    mb_parts.append((pts, bf))
    verts, faces = cat(mb_parts)
    Mt = Matrix.Translation(Vector((x, y, z))) @ Euler((0.0, 0.0, math.radians(train_deg)), "XYZ").to_matrix().to_4x4()
    verts = apply_matrix(verts, Mt)
    me = mesh_from(name, verts, faces)
    link_obj(name, me, COLS["Armament"], mat=MATS["GunMetal"], smooth=True, split=50)


def build_armament():
    print("Armament...")
    build_5in("DD560_Gun51_5in38", GUN51_X, fc_deck_z(GUN51_X), 0.38, train_deg=0, elev_deg=8)
    build_5in("DD560_Gun52_5in38", GUN52_X, fc_deck_z(GUN52_X), 2.20, train_deg=0, elev_deg=12)
    build_5in("DD560_Gun53_5in38", GUN53_X, main_deck_z(GUN53_X), 2.05, train_deg=180, elev_deg=10)
    z54 = main_deck_z(GUN54_X) + 2.32
    build_5in("DD560_Gun54_5in38", GUN54_X, z54, 0.42, train_deg=180, elev_deg=8)
    build_5in("DD560_Gun55_5in38", GUN55_X, main_deck_z(GUN55_X), 0.40, train_deg=180, elev_deg=5)

    # Both quintuple mounts trained to starboard so the starboard views read the tubes.
    build_torpedo_mount("DD560_Torpedo_Fwd", TT_FWD_X, train_deg=90)
    build_torpedo_mount("DD560_Torpedo_Aft", TT_AFT_X, train_deg=90)

    # 40 mm twins: beside the after funnel, and on the after deckhouse shoulders.
    z_main_f = main_deck_z(FUNNEL_AFT_X)
    for sign, tag in ((1.0, "Stbd"), (-1.0, "Port")):
        build_40mm(
            f"DD560_Bofors40_Funnel_{tag}",
            FUNNEL_AFT_X,
            sign * 4.55,
            z_main_f,
            train_deg=90 * sign,
            elev_deg=45,
        )
    z_roof = main_deck_z(-30.2) + 2.32
    for sign, tag in ((1.0, "Stbd"), (-1.0, "Port")):
        build_40mm(
            f"DD560_Bofors40_Aft_{tag}",
            -30.2,
            sign * 1.85,
            z_roof,
            train_deg=70 * sign,
            elev_deg=50,
        )

    # 20 mm Oerlikons
    mounts = [
        ("FC_Stbd", 40.5, 2.4, fc_deck_z(40.5), 70),
        ("FC_Port", 40.5, -2.4, fc_deck_z(40.5), -70),
        ("Wing_Stbd", 26.8, 4.6, fc_deck_z(26.8) + 2.48, 80),
        ("Wing_Port", 26.8, -4.6, fc_deck_z(26.8) + 2.48, -80),
        ("Mid_Stbd", -1.5, 5.15, main_deck_z(-1.5), 90),
        ("Mid_Port", -1.5, -5.15, main_deck_z(-1.5), -90),
        ("Qtr_Stbd", -44.0, 3.3, main_deck_z(-44.0), 110),
        ("Qtr_Port", -44.0, -3.3, main_deck_z(-44.0), -110),
    ]
    for tag, x, y, z, train in mounts:
        # Keep mounts on deck: clamp y inside the local rail.
        y_lim = half_beam(x, z) - 0.45
        y = clamp(y, -y_lim, y_lim)
        build_20mm(f"DD560_Oerlikon20_{tag}", x, y, z, train_deg=train, elev_deg=32)

    build_depth_charges()


def build_depth_charges():
    mb = MB()
    # Two stern racks, four charges each.
    for sign in (1.0, -1.0):
        y = sign * 1.15
        for i in range(4):
            x = -52.2 - i * 0.85
            z = main_deck_z(x) + 0.38
            mb.add_cyl((x, y, z), 0.24, 0.62, rot=(0.0, math.radians(90), 0.0), n=10)
        # Rack rails
        z0 = main_deck_z(-52.2) + 0.12
        z1 = main_deck_z(-54.8) + 0.12
        for dy in (-0.22, 0.22):
            mb.add_between((-52.0, y + dy, z0), (-55.2, y + dy, z1), 0.03, n=4)
    # K-guns, three per side
    for sign in (1.0, -1.0):
        for x in (-32.5, -37.5, -42.2):
            y = sign * 3.5
            z = main_deck_z(x)
            mb.add_cyl((x, y, z + 0.35), 0.12, 0.7, n=8)
            # Barrel outboard and up
            p0 = Vector((x, y, z + 0.7))
            p1 = p0 + Vector((0.2, sign * 0.85, 0.7))
            mb.add_between(p0, p1, 0.07, n=6)
            mb.add_cyl(tuple(p1), 0.16, 0.28, rot=(math.radians(50 * sign), 0, 0), n=8)
    mb.object("DD560_DepthCharges", COLS["Armament"], mat=MATS["DarkMetal"], smooth=True, split=45)


# ---------------------------------------------------------------------------
# Details
# ---------------------------------------------------------------------------


def build_portholes(curves):
    print("Portholes...")
    mb = MB()

    def place(x_nom, z, side):
        if z < 1.05:
            return
        sx, sy, sz = section_point(x_nom, z)
        if sy < 0.9:
            return
        # Outward offset using a longitudinal tangent.
        x2, y2, _ = section_point(min(X_BOW - 0.2, x_nom + 0.45), z)
        x1, y1, _ = section_point(max(X_STERN + 0.2, x_nom - 0.45), z)
        tx, ty = x2 - x1, y2 - y1
        ox, oy = -ty, tx
        L = math.hypot(ox, oy) or 1.0
        ox, oy = ox / L, oy / L
        pos = Vector((sx + ox * 0.03, sy + oy * 0.03, sz))
        if side < 0:
            pos.y *= -1
            oy *= -1
        # Disk facing outward. Cylinder axis along outward XY.
        axis = Vector((ox, oy if side > 0 else -abs(oy), 0.0))
        if side < 0:
            axis = Vector((ox, -oy if False else axis.y, 0))
        axis.normalize()
        quat = Vector((0, 0, 1)).rotation_difference(axis)
        v, f = cylinder_z_vf(0.13, 0.04, n=8, caps=True)
        M = Matrix.Translation(pos) @ quat.to_matrix().to_4x4()
        mb.add(apply_matrix(v, M), f)

    x = -46.0
    while x < 50.0:
        z = main_deck_z(x) - 1.15
        # Skip where the midship house covers the hull? Portholes are on the shell, visible
        # outboard of the house. Keep them.
        for side in (1, -1):
            place(x, z, side)
        if x > BREAK_X + 2.0:
            z2 = fc_deck_z(x) - 1.15
            for side in (1, -1):
                place(x, z2, side)
        x += 3.15
    mb.object("DD560_Portholes", COLS["Details"], mat=MATS["Glass"], smooth=True)


def digit_rects(ch):
    t = 0.18
    if ch == "0":
        return [(0, 0, 1, t), (0, 1 - t, 1, 1), (0, t, t, 1 - t), (1 - t, t, 1, 1 - t)]
    if ch == "5":
        return [
            (0, 1 - t, 1, 1),
            (0, 0.46, 1, 0.46 + t),
            (0, 0, 1, t),
            (0, 0.46, t, 1),
            (1 - t, 0, 1, 0.46 + t),
        ]
    if ch == "6":
        return [
            (0, 1 - t, 1, 1),
            (0, 0.46, 1, 0.46 + t),
            (0, 0, 1, t),
            (0, 0, t, 1),
            (1 - t, 0, 1, 0.46 + t),
        ]
    if ch == "4":
        return [(0.62, 0, 0.62 + t, 1), (0, 0.42, 1, 0.42 + t), (0, 0.42, t, 1)]
    if ch == "1":
        return [(0.38, 0, 0.38 + t, 1), (0.15, 0.72, 0.38 + t, 0.72 + t)]
    return [(0.1, 0.1, 0.9, 0.9)]


def add_hull_numbers():
    print("Hull numbers...")
    mb = MB()
    height = 1.65
    digit_w = height * 0.62
    gap = height * 0.16
    text = HULL_NUMBER

    def emit(origin, right, up, normal):
        pen = 0.0
        for ch in text:
            rects = digit_rects(ch)
            for x0, z0, x1, z1 in rects:
                cx = (x0 + x1) * 0.5 * digit_w
                cz = (z0 + z1) * 0.5 * height
                sx = (x1 - x0) * digit_w
                sz = (z1 - z0) * height
                center = origin + right * (pen + cx) + up * cz + normal * 0.02
                v, f = cube_vf((sx, 0.035, sz))
                M = M_basis(center, right, normal, up)
                mb.add(apply_matrix(v, M), f)
            pen += digit_w + gap

    def place(x_nom, z, side):
        sx, sy, sz = section_point(x_nom, z)
        x2, y2, _ = section_point(min(X_BOW - 0.3, x_nom + 0.5), z)
        x1, y1, _ = section_point(max(X_STERN + 0.3, x_nom - 0.5), z)
        tx, ty = x2 - x1, y2 - y1
        ox, oy = -ty, tx
        L = math.hypot(ox, oy) or 1.0
        normal = Vector((ox / L, oy / L, 0.0))
        if side < 0:
            normal = Vector((normal.x, -normal.y, 0.0))
            sy = -sy
            sx_p = sx
        else:
            sx_p = sx
        normal.normalize()
        up = Vector((0, 0, 1))
        # Pen runs toward the viewer's right when looking in from outboard,
        # so the digits read correctly on both bows.
        right = up.cross(-normal).normalized()
        width = len(text) * digit_w + (len(text) - 1) * gap
        origin = Vector((sx_p, sy, sz)) + normal * 0.04 - right * (width * 0.5)
        emit(origin, right, up, normal)

    place(49.0, 4.55, 1)
    place(49.0, 4.55, -1)

    # Stern transom number, smaller.
    stern = section_point(X_STERN, main_deck_z(X_STERN))
    normal = Vector((-1, 0, 0))
    up = Vector((0, 0, 1))
    right = up.cross(-normal).normalized()
    height_s = 0.9
    # temporarily scale by using a local copy — call emit with adjusted globals via closure rewrite
    # Just place a short "560" manually at reduced size by scaling basis.
    width = len(text) * digit_w + (len(text) - 1) * gap
    # Use the same emit (1.45 m) would be large for the stern; build a second pass.
    origin = Vector((stern[0] - 0.02, 0.0, main_deck_z(X_STERN) * 0.72)) - right * (width * 0.55 * 0.62)
    # Skip the large emit; draw scaled digits directly.
    pen = 0.0
    hs = 0.85
    dw = hs * 0.62
    gp = hs * 0.14
    width = len(text) * dw + (len(text) - 1) * gp
    origin = Vector((stern[0] - 0.05, 0.0, main_deck_z(X_STERN) * 0.62)) - right * (width * 0.5)
    for ch in text:
        for x0, z0, x1, z1 in digit_rects(ch):
            cx = (x0 + x1) * 0.5 * dw
            cz = (z0 + z1) * 0.5 * hs
            sx = (x1 - x0) * dw
            sz = (z1 - z0) * hs
            center = origin + right * (pen + cx) + up * cz + normal * 0.02
            v, f = cube_vf((sx, 0.03, sz))
            mb.add(apply_matrix(v, M_basis(center, right, normal, up)), f)
        pen += dw + gp

    mb.object("DD560_HullNumbers", COLS["Details"], mat=MATS["NumberBlack"], smooth=False)


def build_anchors_and_fittings():
    print("Bow fittings...")
    mb = MB()
    # Windlass and breakwater sit forward of the bow-gun muzzle.
    x = 54.2
    z = fc_deck_z(x) + 0.28
    mb.add_cube((x, 0, z), (0.9, 0.55, 0.40))
    mb.add_cyl((x, 0.0, z + 0.12), 0.18, 0.7, rot=(math.pi / 2, 0, 0), n=10)
    z = fc_deck_z(52.4)
    bw = min(4.6, max(1.2, half_beam(52.4, z) * 1.7))
    mb.add_cube((52.4, 0.0, z + 0.40), (0.08, bw, 0.78), rot=(0.0, math.radians(-16), 0.0))
    obj_preview = None
    # Anchors + hawse
    for sign in (1.0, -1.0):
        x_nom = 53.2
        zz = 2.35
        sx, sy, sz = section_point(x_nom, zz)
        y = sign * sy
        # Hawse pipe
        mb.add_cyl((sx - 0.1, y * 0.92, sz), 0.18, 0.9, rot=(0.2 * sign, math.radians(55), 0), n=8)
        # Stockless anchor on the side of the bow
        base = Vector((sx + 0.05, y + sign * 0.05, sz - 0.2))
        shank_top = base + Vector((-0.15, sign * 0.05, 1.35))
        mb.add_between(base, shank_top, 0.055, n=6)
        mb.add_sphere(tuple(base + Vector((0, 0, -0.05))), 0.12, scale=(1.1, 0.8, 0.8), n_u=8, n_v=6)
        for s2 in (1.0, -1.0):
            fluke = base + Vector((0.15, sign * 0.05, -0.15)) + Vector((0.35, s2 * sign * 0.28, 0.55))
            mb.add_between(base, fluke, 0.04, n=5)
    mb.object("DD560_BowFittings", COLS["Details"], mat=MATS["DarkMetal"], smooth=True, split=40)

    # Bitts
    bitts = MB()
    spots = [
        (49.5, 1.3, True),
        (49.5, -1.3, True),
        (-50.5, 1.6, False),
        (-50.5, -1.6, False),
        (4.0, 5.0, False),
        (4.0, -5.0, False),
    ]
    for x, y, fore in spots:
        z = (fc_deck_z(x) if fore else main_deck_z(x)) + 0.02
        if abs(y) > half_beam(x, z) - 0.3:
            continue
        for dy in (-0.16, 0.16):
            bitts.add_cyl((x, y + dy, z + 0.28), 0.07, 0.56, n=6)
        bitts.add_cyl((x, y, z + 0.42), 0.05, 0.42, rot=(math.pi / 2, 0, 0), n=6)
    bitts.object("DD560_Bitts", COLS["Details"], mat=MATS["DarkMetal"], smooth=True)


def build_boats():
    print("Boats...")
    for sign, tag in ((1.0, "Stbd"), (-1.0, "Port")):
        x = 4.2
        y = sign * 4.85
        z = main_deck_z(x) + 1.55
        # Keep the boat inside the rail.
        y_lim = half_beam(x, main_deck_z(x)) - 1.15
        y = sign * min(abs(y), y_lim)
        verts = []
        # Simple round-bottomed hull, bow +X local, then yaw 180 so bow faces outboard? Keep bow forward.
        stations = [
            (-3.7, 0.05, 0.10, 0.28),
            (-2.6, 0.55, 0.38, 0.48),
            (-1.2, 0.95, 0.55, 0.52),
            (0.4, 1.02, 0.58, 0.50),
            (1.8, 0.78, 0.42, 0.46),
            (3.0, 0.28, 0.16, 0.32),
            (3.6, 0.04, 0.05, 0.22),
        ]
        rings = []
        for s, hb, kd, sh in stations:
            ring = []
            for i in range(7):
                t = i / 6
                # t 0 keel, 1 sheer, port side then we'll mirror in the same ring
                zc = -kd + (sh + kd) * (math.sin(t * math.pi * 0.5) ** 0.85)
                yy = hb * math.sin(t * math.pi * 0.5)
                ring.append((s, yy, zc))
            # port
            full = [(p[0], -p[1], p[2]) for p in reversed(ring)] + ring[1:]
            idxs = []
            for p in full:
                idxs.append(len(verts))
                verts.append(p)
            rings.append(idxs)
        faces = []
        for i in range(len(rings) - 1):
            a, b = rings[i], rings[i + 1]
            for j in range(len(a) - 1):
                faces.append((a[j], a[j + 1], b[j + 1], b[j]))
        M = Matrix.Translation(Vector((x, y, z)))
        verts = [M @ Vector(v) for v in verts]
        me = mesh_from(f"DD560_Whaleboat_{tag}", verts, filter_faces(verts, faces, 1e-8))
        obj = link_obj(
            f"DD560_Whaleboat_{tag}", me, COLS["Details"], mat=MATS["HazeGray"], smooth=True, split=48
        )
        ensure_outward(obj)
        # Davits: two arms from the deckhouse side up and out over the boat.
        dav = MB()
        z_deck = main_deck_z(x)
        for dx in (-2.2, 2.2):
            p0 = Vector((x + dx, sign * (HOUSE_HALF_W + 0.05), z_deck + FC_RISE * 0.15))
            p1 = Vector((x + dx, sign * (HOUSE_HALF_W + 0.4), z_deck + 2.5))
            p2 = Vector((x + dx, y, z_deck + 2.7))
            p3 = Vector((x + dx, y, z + 0.7))
            pts = []
            for k in range(7):
                t = k / 6
                u = 1 - t
                pts.append((u ** 3) * p0 + 3 * (u ** 2) * t * p1 + 3 * u * (t ** 2) * p2 + (t ** 3) * p3)
            for a, b in zip(pts, pts[1:]):
                dav.add_between(a, b, 0.045, n=5)
            dav.add_between(p3, Vector((x + dx, y, z + 0.55)), 0.012, n=3, caps=False)
        dav.object(f"DD560_Davits_{tag}", COLS["Details"], mat=MATS["HazeGray"], smooth=True)


def build_life_rafts_and_vents():
    mb = MB()
    # Carley floats: squashed tori along the deckhouse sides.
    def add_torus(loc, major=0.85, minor=0.16, scale_z=0.45, rot=(0, 0, 0)):
        n_maj, n_min = 14, 6
        verts = []
        for i in range(n_maj):
            a = 2 * math.pi * i / n_maj
            ca, sa = math.cos(a), math.sin(a)
            for j in range(n_min):
                b = 2 * math.pi * j / n_min
                cb, sb = math.cos(b), math.sin(b)
                x = (major + minor * cb) * ca
                y = (major + minor * cb) * sa
                z = minor * sb * scale_z
                verts.append(Vector((x, y, z)))
        faces = []
        for i in range(n_maj):
            for j in range(n_min):
                i2 = (i + 1) % n_maj
                j2 = (j + 1) % n_min
                a = i * n_min + j
                b = i2 * n_min + j
                c = i2 * n_min + j2
                d = i * n_min + j2
                faces.append((a, b, c, d))
        mb.add(apply_matrix(verts, M_trs(loc, rot)), faces)

    for sign in (1.0, -1.0):
        for x in (8.5, 0.5, -8.5):
            y = sign * (HOUSE_HALF_W + 0.15)
            z = main_deck_z(x) + 1.15
            add_torus((x, y, z), rot=(math.pi / 2, 0, 0))
        # After deckhouse
        add_torus((-34.0, sign * 2.3, main_deck_z(-34) + 2.55), major=0.7, minor=0.14)

    # Mushroom vents on the midship roof
    for x, y in ((12.4, 1.4), (12.4, -1.4), (-3.5, 1.6), (-3.5, -1.6), (-16.5, 0.0)):
        z = main_deck_z(x) + FC_RISE
        mb.add_cyl((x, y, z + 0.28), 0.12, 0.4, n=8)
        mb.add_cyl((x, y, z + 0.52), 0.28, 0.1, n=10)
    # Skylight aft of the after tubes
    z = main_deck_z(-17.2) + FC_RISE
    mb.add_cube((-17.2, 0.0, z + 0.18), (1.4, 1.0, 0.28))
    mb.object("DD560_RaftsVents", COLS["Details"], mat=MATS["LifeRaft"], smooth=True, split=45)
    glass = MB()
    glass.add_cube((-17.2, 0.0, main_deck_z(-17.2) + FC_RISE + 0.34), (1.1, 0.7, 0.04))
    glass.object("DD560_Skylight", COLS["Details"], mat=MATS["Glass"], smooth=False)

    # Life rings
    rings = MB()
    for loc in ((28.8, 2.7, fc_deck_z(28.8) + 1.6), (28.8, -2.7, fc_deck_z(28.8) + 1.6),
                (-46.5, 2.2, main_deck_z(-46.5) + 1.1), (-46.5, -2.2, main_deck_z(-46.5) + 1.1)):
        add_ring = []
        # small torus in MB-like local, reuse add_torus into rings via a fresh builder
    rings_mb = MB()
    # Duplicate torus helper quickly
    def small_ring(loc):
        n_maj, n_min = 12, 5
        verts = []
        major, minor = 0.32, 0.06
        for i in range(n_maj):
            a = 2 * math.pi * i / n_maj
            for j in range(n_min):
                b = 2 * math.pi * j / n_min
                x = (major + minor * math.cos(b)) * math.cos(a)
                y = (major + minor * math.cos(b)) * math.sin(a)
                z = minor * math.sin(b)
                verts.append(Vector((x, y, z)))
        faces = []
        for i in range(n_maj):
            for j in range(n_min):
                i2 = (i + 1) % n_maj
                j2 = (j + 1) % n_min
                faces.append(
                    (
                        i * n_min + j,
                        i2 * n_min + j,
                        i2 * n_min + j2,
                        i * n_min + j2,
                    )
                )
        rings_mb.add(apply_matrix(verts, M_trs(loc, (math.pi / 2, 0, 0))), faces)

    for loc in (
        (28.6, 2.65, fc_deck_z(28.6) + 1.7),
        (28.6, -2.65, fc_deck_z(28.6) + 1.7),
        (-45.8, 2.4, main_deck_z(-45.8) + 1.15),
        (-45.8, -2.4, main_deck_z(-45.8) + 1.15),
    ):
        small_ring(loc)
    rings_mb.object("DD560_LifeRings", COLS["Details"], mat=MATS["White"], smooth=True)


def build_ladders():
    mb = MB()

    def ladder(x, y, z0, z1, face_y=1.0):
        h = z1 - z0
        if h < 0.4:
            return
        yb = y
        for dy in (-0.12, 0.12):
            mb.add_between((x, yb + dy, z0), (x, yb + dy, z1), 0.018, n=4)
        steps = max(2, int(h / 0.28))
        for i in range(steps + 1):
            z = lerp(z0 + 0.15, z1 - 0.05, i / steps)
            mb.add_between((x, yb - 0.12, z), (x, yb + 0.12, z), 0.016, n=4)

    # Forecastle break, outboard of the deckhouse.
    for sign in (1.0, -1.0):
        y = sign * (HOUSE_HALF_W + 0.55)
        ladder(BREAK_X - 0.15, y, main_deck_z(BREAK_X), fc_deck_z(BREAK_X))
        ladder(-27.0, sign * 2.2, main_deck_z(-27), main_deck_z(-27) + 2.32)
    mb.object("DD560_Ladders", COLS["Details"], mat=MATS["DarkMetal"], smooth=True)


def build_underwater(curves):
    print("Underwater gear...")
    # Rudder under the stern overhang.
    rx = -52.4
    mb = MB()
    zk = keel_z(rx)
    # Shape a rudder blade as a tapered box.
    v, f = cube_vf((1.3, 0.12, 2.4))
    M = Matrix.Translation(Vector((actual_x(rx, zk + 1.2), 0.0, zk + 0.7)))
    mb.add(apply_matrix(v, M), f)
    # Skeg
    v, f = cube_vf((3.2, 0.08, 1.3))
    M = Matrix.Translation(Vector((actual_x(-48.5, -2.5), 0.0, keel_z(-48.5) + 0.4)))
    mb.add(apply_matrix(v, M), f)
    mb.object("DD560_Rudder", COLS["Hull"], mat=MATS["AntiFoul"], smooth=False)

    # Sonar dome under the forefoot.
    sx = 42.0
    dome = MB()
    zk = keel_z(sx)
    dome.add_sphere((actual_x(sx, zk), 0.0, zk - 0.15), 1.0, scale=(0.7, 0.55, 0.85), n_u=12, n_v=8)
    dome.object("DD560_SonarDome", COLS["Hull"], mat=MATS["AntiFoul"], smooth=True)

    props = MB()
    for sign in (1.0, -1.0):
        x_nom = -50.2
        y = sign * 1.85
        zk = keel_z(x_nom)
        z = zk + 0.15
        loc = Vector((actual_x(x_nom, z), y, z))
        # Hub along X
        props.add_cyl(tuple(loc), 0.16, 0.5, rot=(0, math.pi / 2, 0), n=10)
        for k in range(3):
            ang = k * 2 * math.pi / 3 + 0.35
            radial = Vector((0.0, math.cos(ang), math.sin(ang)))
            v, f = cone_z_vf(0.20, 0.03, 1.15, n=8, caps=True, z0=0.0)
            quat = Vector((0, 0, 1)).rotation_difference(radial)
            M = Matrix.Translation(loc) @ quat.to_matrix().to_4x4() @ Matrix.Translation(Vector((0, 0, 0.15)))
            props.add(apply_matrix(v, M), f)
        # Shaft
        p_prop = loc + Vector((0.3, 0, 0))
        p_hull = Vector((actual_x(-36.0, -2.8), y * 0.85, keel_z(-36) + 0.25))
        props.add_between(p_hull, p_prop, 0.10, n=8)
        # Strut just ahead of the prop
        strut_top = Vector((loc.x + 1.3, y * 0.15, loc.z + 1.15))
        props.add_between(strut_top, loc + Vector((0.7, 0.05 * sign, 0.05)), 0.06, n=5)
        props.add_between(strut_top + Vector((0, -y * 0.3, 0)), loc + Vector((0.7, 0, 0)), 0.05, n=5)
    props.object("DD560_ShaftsProps", COLS["Hull"], mat=MATS["DarkMetal"], smooth=True, split=42)


def build_flag_and_staffs(curves):
    mb = MB()
    bow = curves["bow_tip"]
    stern = curves["stern_tip"]
    # Jackstaff
    mb.add_between((bow[0] - 0.05, 0, bow[2]), (bow[0] - 0.05, 0, bow[2] + 2.4), 0.025, n=5)
    # Ensign staff
    staff_top = Vector((stern[0] + 0.4, 0.0, stern[2] + 3.3))
    mb.add_between((stern[0] + 0.15, 0, stern[2] + 0.05), staff_top, 0.03, n=5)
    mb.object("DD560_Staffs", COLS["Details"], mat=MATS["DarkMetal"], smooth=True)

    # Ensign flying aft, drooped slightly. Hoist at the staff, fly toward -X? 
    # Stern is -X, aft is further -X. Flag flies to -X.
    flag = MB()
    hoist = staff_top + Vector((-0.05, 0, -0.05))
    # 13 stripes
    length = 1.55
    height = 0.82
    for i in range(13):
        z0 = hoist.z - i * (height / 13)
        z1 = z0 - height / 13
        col_is_red = (i % 2 == 0)
        # We'll color via two materials by splitting objects.
        v, f = cube_vf((length, 0.012, height / 13))
        center = Vector((hoist.x - length * 0.5, hoist.y, (z0 + z1) * 0.5))
        # Droop the fly end
        droop = Matrix.Translation(center) @ Euler((0.0, math.radians(-8), math.radians(6)), "XYZ").to_matrix().to_4x4()
        if col_is_red:
            if not hasattr(build_flag_and_staffs, "_red"):
                build_flag_and_staffs._red = MB()
                build_flag_and_staffs._white = MB()
            build_flag_and_staffs._red.add(apply_matrix(v, droop), f)
        else:
            build_flag_and_staffs._white.add(apply_matrix(v, droop), f)
    # Canton
    cw, ch = length * 0.4, height * 7 / 13
    v, f = cube_vf((cw, 0.014, ch))
    canton_c = Vector((hoist.x - cw * 0.5, hoist.y - 0.004, hoist.z - ch * 0.5))
    droop = Matrix.Translation(canton_c) @ Euler((0.0, math.radians(-8), math.radians(6)), "XYZ").to_matrix().to_4x4()
    build_flag_and_staffs._blue = MB()
    build_flag_and_staffs._blue.add(apply_matrix(v, droop), f)
    build_flag_and_staffs._red.object("DD560_Ensign_Red", COLS["Details"], mat=MATS["FlagRed"], smooth=False)
    build_flag_and_staffs._white.object("DD560_Ensign_White", COLS["Details"], mat=MATS["White"], smooth=False)
    build_flag_and_staffs._blue.object("DD560_Ensign_Canton", COLS["Details"], mat=MATS["FlagBlue"], smooth=False)


def build_doors():
    mb = MB()
    # Dark door rectangles on the midship house sides and aft house.
    for x in (12.0, 4.0, -4.0, -12.0):
        z = main_deck_z(x) + 0.85
        for sign in (1.0, -1.0):
            y = sign * (HOUSE_HALF_W + 0.02)
            mb.add_cube((x, y, z), (0.55, 0.04, 1.15))
    for x in (-31.5, -38.0):
        z = main_deck_z(x) + 0.85
        for sign in (1.0, -1.0):
            mb.add_cube((x, sign * 3.08, z), (0.5, 0.04, 1.1))
    mb.object("DD560_Doors", COLS["Details"], mat=MATS["DarkMetal"], smooth=False)


# ---------------------------------------------------------------------------
# Environment, cameras, render
# ---------------------------------------------------------------------------


def look_at(obj, target, up="Y"):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", up).to_euler()


def build_environment():
    print("Environment...")
    # Ocean
    v, f = cube_vf((4000, 4000, 0.2))
    M = Matrix.Translation(Vector((0.0, 0.0, -0.10)))
    verts = apply_matrix(v, M)
    me = mesh_from("Ocean", verts, f)
    ocean = link_obj("Ocean", me, COLS["Environment"], mat=MATS["Ocean"], smooth=False, parent=None)
    # Don't parent the ocean to the ship root: re-parent clear.
    ocean.parent = None

    # Wake
    wake = MB()
    stern_x = section_point(X_STERN, 0.02)[0]
    # Short, narrow streak. A long sheet ran off the broadside and top-down frames.
    for i in range(8):
        t0 = i / 8
        t1 = (i + 1) / 8
        x0 = lerp(stern_x - 0.3, stern_x - 10.0, t0)
        x1 = lerp(stern_x - 0.3, stern_x - 10.0, t1)
        w0 = lerp(0.22, 1.45, t0 ** 0.85)
        w1 = lerp(0.22, 1.45, t1 ** 0.85)
        z = 0.03
        base = len(wake.verts)
        wake.verts.extend([(x0, -w0, z), (x0, w0, z), (x1, w1, z), (x1, -w1, z)])
        wake.faces.append((base, base + 1, base + 2, base + 3))
    wo = wake.object("Wake", COLS["Environment"], mat=MATS["Wake"], smooth=False)
    wo.parent = None

    # Lights
    def add_sun(name, travel, energy, angle_deg, color):
        light = bpy.data.lights.new(name, "SUN")
        light.energy = energy
        light.angle = math.radians(angle_deg)
        light.color = srgb_to_linear(color)
        obj = bpy.data.objects.new(name, light)
        COLS["Environment"].objects.link(obj)
        obj.parent = None
        quat = Vector((0.0, 0.0, -1.0)).rotation_difference(Vector(travel).normalized())
        obj.rotation_euler = quat.to_euler()
        return obj

    # Photons travel from starboard-bow, downward, so the hero side is lit.
    add_sun("Light_Key", (-0.35, -0.78, -0.55), 4.4, 0.45, (1.0, 0.97, 0.90))
    add_sun("Light_Fill", (0.55, 0.70, -0.45), 1.15, 2.5, (0.75, 0.84, 1.0))
    add_sun("Light_Rim", (0.85, 0.15, -0.35), 0.7, 1.2, (1.0, 0.95, 0.88))

    world = bpy.data.worlds.new("NorthAtlantic")
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "NISHITA"
    sky.sun_disc = False
    try:
        sky.sun_elevation = math.radians(34)
        sky.sun_rotation = math.radians(55)
        sky.air_density = 1.6
        sky.dust_density = 0.35
        sky.ozone_density = 1.0
    except Exception as exc:
        print("  sky params", exc)
    bg.inputs["Strength"].default_value = 0.55
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    bpy.context.scene.world = world

    # Cameras
    cams = {}

    def add_cam(key, loc, target, lens, ortho=False, ortho_scale=140.0, rot=None, up="Y"):
        cam_d = bpy.data.cameras.new(key)
        cam_d.lens = lens
        cam_d.clip_start = 0.1
        cam_d.clip_end = 8000
        if ortho:
            cam_d.type = "ORTHO"
            cam_d.ortho_scale = ortho_scale
            cam_d.sensor_fit = "HORIZONTAL"
        obj = bpy.data.objects.new(key, cam_d)
        COLS["Environment"].objects.link(obj)
        obj.parent = None
        obj.location = Vector(loc)
        if rot is not None:
            obj.rotation_euler = Euler(rot, "XYZ")
        else:
            look_at(obj, target, up=up)
        cams[key] = obj
        return obj

    # Bow 3/4 matches the framing the owner already liked. Broadside and
    # top-down sit far enough back that the hull, not the wake, owns the frame.
    add_cam("Cam_BowQuarter", (138.0, 102.0, 24.0), (-4.0, 0.0, 4.6), 38)
    add_cam("Cam_Broadside", (0.0, 305.0, 16.0), (0.0, 0.0, 5.6), 70)
    add_cam("Cam_TopDown", (0.0, 0.0, 240.0), (0.0, 0.0, 0.0), 50, ortho=True, ortho_scale=148.0, rot=(0.0, 0.0, 0.0))
    bpy.context.scene.camera = cams["Cam_BowQuarter"]
    return cams


def poly_report():
    report = {"collections": {}, "objects": 0, "tris": 0}
    for name, col in COLS.items():
        tris = 0
        objs = 0
        for obj in col.objects:
            if obj.type != "MESH":
                continue
            objs += 1
            tris += sum(max(0, len(p.vertices) - 2) for p in obj.data.polygons)
        report["collections"][name] = {"mesh_objects": objs, "tris": tris}
        report["tris"] += tris
        report["objects"] += objs
    # bbox of root children meshes
    xs, ys, zs = [], [], []
    for obj in bpy.data.objects:
        if obj.type != "MESH" or obj.parent != ROOT:
            continue
        for corner in obj.bound_box:
            w = obj.matrix_world @ Vector(corner)
            xs.append(w.x)
            ys.append(w.y)
            zs.append(w.z)
    if xs:
        report["bbox_m"] = {
            "x": [min(xs), max(xs)],
            "y": [min(ys), max(ys)],
            "z": [min(zs), max(zs)],
            "length": max(xs) - min(xs),
            "beam": max(ys) - min(ys),
            "air_draft": max(zs) - 0.0,
        }
    return report


def export_meshes():
    bpy.ops.object.select_all(action="DESELECT")

    def walk(o):
        if o.type == "MESH":
            o.select_set(True)
        for c in o.children:
            walk(c)

    walk(ROOT)
    glb = SCRIPT_DIR / "DD560_Fletcher.glb"
    fbx = SCRIPT_DIR / "DD560_Fletcher.fbx"
    try:
        bpy.ops.export_scene.gltf(
            filepath=str(glb),
            export_format="GLB",
            use_selection=True,
            export_apply=True,
            export_cameras=False,
            export_lights=False,
            export_yup=True,
        )
        print("Exported", glb)
    except Exception as exc:
        print("GLB export failed:", exc)
    try:
        bpy.ops.export_scene.fbx(
            filepath=str(fbx),
            use_selection=True,
            apply_scale_options="FBX_SCALE_ALL",
            object_types={"MESH"},
            mesh_smooth_type="FACE",
            path_mode="AUTO",
            axis_forward="-Z",
            axis_up="Y",
        )
        print("Exported", fbx)
    except Exception as exc:
        print("FBX export failed:", exc)


def render_views(cams):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.max_bounces = 6
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 2
    scene.cycles.transmission_bounces = 2
    scene.cycles.transparent_max_bounces = 4
    scene.cycles.sample_clamp_indirect = 6.0
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    scene.view_settings.exposure = -0.15

    if ARGS.res:
        rx, ry = ARGS.res
    elif ARGS.fast:
        rx, ry = 1280, 720
    else:
        rx, ry = 1920, 1080
    samples = ARGS.samples or (16 if ARGS.fast else 48)
    scene.cycles.samples = samples
    scene.render.resolution_x = rx
    scene.render.resolution_y = ry
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False

    outdir = Path(ARGS.outdir) if ARGS.outdir else RENDER_DIR
    outdir.mkdir(parents=True, exist_ok=True)
    wanted = [v.strip() for v in ARGS.views.split(",") if v.strip()]
    key_to_cam = {
        "bow_quarter": "Cam_BowQuarter",
        "broadside": "Cam_Broadside",
        "topdown": "Cam_TopDown",
    }
    for key in wanted:
        cam_name = key_to_cam.get(key, key)
        cam = cams.get(cam_name)
        if cam is None:
            print("Unknown view", key)
            continue
        scene.camera = cam
        path = outdir / f"{key}.png"
        scene.render.filepath = str(path)
        print(f"Rendering {key} -> {path} ({rx}x{ry}, {samples} spp)")
        bpy.ops.render.render(write_still=True)
        print("  saved", path)


def build():
    reset_scene()
    make_materials()
    global ROOT
    for name in ("Hull", "Superstructure", "Armament", "Details", "Environment"):
        new_collection(name)
    ROOT = bpy.data.objects.new("DD560", None)
    ROOT.empty_display_type = "PLAIN_AXES"
    ROOT.empty_display_size = 6.0
    COLS["Hull"].objects.link(ROOT)
    ROOT["ship_class"] = "Fletcher-class study, square bridge, circa 1943 massing"
    ROOT["hull_number_display"] = HULL_NUMBER
    ROOT["units"] = "meters"
    ROOT["axis"] = "+X bow, +Y starboard, +Z up, origin midships waterline"
    ROOT["loa_m"] = LOA
    ROOT["beam_m"] = BEAM
    ROOT["draft_m"] = DRAFT

    curves = build_hull_shell()
    build_decks(curves)
    build_bulwark(curves["stbd_fc"])
    build_break_wings(curves)
    build_bilge_keels()
    build_underwater(curves)

    if not ARGS.hull_only:
        build_superstructure()
        build_armament()
        build_railings(curves["stbd_main"])
        build_portholes(curves)
        add_hull_numbers()
        build_anchors_and_fittings()
        build_boats()
        build_life_rafts_and_vents()
        build_ladders()
        build_doors()
        build_flag_and_staffs(curves)

    cams = build_environment()
    report = poly_report()
    report["hull_number"] = HULL_NUMBER
    report["loa_nominal_m"] = LOA
    report["beam_nominal_m"] = BEAM
    print(json.dumps(report, indent=2))
    (SCRIPT_DIR / "build_report.json").write_text(json.dumps(report, indent=2))

    blend_path = SCRIPT_DIR / "DD560_Fletcher.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    print("Saved", blend_path)

    if not ARGS.no_export and not ARGS.hull_only:
        export_meshes()
        # Export can change selection; the file on disk is the pre-export state.
        # Save once more so the blend matches the final scene.
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    if not ARGS.no_render:
        render_views(cams)


if __name__ == "__main__":
    build()
