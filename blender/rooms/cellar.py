"""Hobbit-house wine & food cellar, rebuilt as a real 3D room from the 'Wine cellar' and 'Wine & food cellar' images.
One long vaulted room: the wine end (barrel table, barrels, crates) is at y = 0, the food end (long table with food,
stools, chest, stone pillar) at y = -L. Wine racks full of bottles line both walls.

    python blender/rooms/cellar.py --render docs/rooms/cellar.png --samples 128 --res 1600x900 --glb assets/rooms/cellar/cellar.glb
    python blender/rooms/cellar.py --render docs/rooms/cellar_food.png --cam food
"""
import argparse, json, math, os, sys, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
import numpy as np
from mathutils import Vector, Matrix
from hero_room import A, pbr, flat, obj_from_bm, box_uv, box, cyl, torus, cut, sweep_profile, model, light, candle
from kitchen import lantern, leaf_cluster, group, kid, tex_mat, mat_alpha, arch_cutter_y, stone_arch
from dining import stadium, rod

W, L = 6.2, 17.0
HW = W / 2
WALL_H, APEX = 2.7, 4.5
RD = 0.42                                   # rack depth
NW, NRH, ND = 2.5, 1.55, 1.0                # end niches: width, height of the straight part, depth
rnd = random.Random(41)
CAMS = {'wine': (0.25, -10.2, 1.62, 88, 0, 17), 'food': (-0.5, -7.6, 1.62, 88, 180, 18)}

def K(*p): return A('assets', 'rooms', 'cellar', *p)

def vault_z(x, inset=0.0):
    t = max(-1.0, min(1.0, x / (HW - inset)))
    return WALL_H + math.sqrt(max(0.0, 1 - t * t)) * (APEX - WALL_H - inset)

def profile(n=40, inset=0.0):
    pts = [(-HW + inset, 0.0)]
    for i in range(n + 1):
        a = math.pi - i / n * math.pi
        pts.append((math.cos(a) * (HW - inset), WALL_H + math.sin(a) * (APEX - WALL_H - inset)))
    pts.append((HW - inset, 0.0)); return pts

# ---------------------------------------------------------------- bottles: thousands, built as one mesh with numpy
_BT = None
def bottle_template(seg=8):
    global _BT
    if _BT: return _BT
    prof = [(0.0, 0.0), (0.0, 0.036), (0.19, 0.037), (0.225, 0.031), (0.25, 0.016), (0.30, 0.0135), (0.312, 0.0155), (0.322, 0.013), (0.322, 0.0)]
    V, F, M, idx = [], [], [], []
    for t, r in prof:
        if r == 0: idx.append([len(V)]); V.append((t, 0.0, 0.0))
        else:
            idx.append(list(range(len(V), len(V) + seg)))
            for k in range(seg): a = k / seg * 2 * math.pi; V.append((t, r * math.cos(a), r * math.sin(a)))
    for j in range(len(prof) - 1):
        a, b = idx[j], idx[j + 1]; foil = 1 if (prof[j][0] + prof[j + 1][0]) / 2 > 0.245 else 0
        for k in range(seg):
            k2 = (k + 1) % seg
            if len(a) == 1: F.append((a[0], b[k2], b[k]))
            elif len(b) == 1: F.append((a[k], a[k2], b[0]))
            else: F.append((a[k], a[k2], b[k2], b[k]))
            M.append(foil)
    _BT = (np.array(V, np.float32), F, np.array(M)); return _BT

def bottles(name, placements, mats):
    """placements: list of (origin, axis, glass_idx 0/1, foil_idx 0/1). mats: [glass0, glass1, foil0, foil1]."""
    if not placements: return None
    V, F, M = bottle_template(); nv = len(V); N = len(placements)
    O = np.array([p[0] for p in placements], np.float32); D = np.array([p[1] for p in placements], np.float32)
    up = np.tile(np.array([0, 0, 1], np.float32), (N, 1)); S = np.cross(up, D)
    verts = O[:, None, :] + V[None, :, 0:1] * D[:, None, :] + V[None, :, 1:2] * S[:, None, :] + V[None, :, 2:3] * up[:, None, :]
    verts = verts.reshape(-1, 3)
    faces = [tuple(i * nv + v for v in f) for i in range(N) for f in F]
    me = bpy.data.meshes.new(name); me.from_pydata(verts.tolist(), [], faces); me.update()
    for m in mats: me.materials.append(m)
    g = np.array([p[2] for p in placements]); fo = np.array([p[3] for p in placements])
    mi = (np.where(M[None, :] == 1, 2 + fo[:, None], g[:, None])).reshape(-1).astype(np.int32)
    me.polygons.foreach_set('material_index', mi); me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), bool))
    o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o); return o

BOTTLES = []
def rack(a0, a1, wall, inward, z0, z1, along_x, wood, cubby=0.62, shelf=0.155, skip=None, candles=True):
    """A wine rack against a wall. along_x=False: the wall is x = wall and the rack runs along y from a0 to a1;
    along_x=True: the wall is y = wall and the rack runs along x. Bottles lie with their necks toward the room."""
    def bx(name, u0, u1, d0, d1, zz0, zz1, tile=1.0):
        w0, w1 = wall + inward * d0, wall + inward * d1
        if along_x: return box(name, u0, u1, min(w0, w1), max(w0, w1), zz0, zz1, wood, tile)
        return box(name, min(w0, w1), max(w0, w1), u0, u1, zz0, zz1, wood, tile)
    bx('rack back', a0, a1, 0.0, 0.03, z0, z1, 1.4)
    n = max(1, round((a1 - a0) / cubby)); cw = (a1 - a0) / n
    for i in range(n + 1): u = a0 + i * cw; bx('rack upright', u - 0.022, u + 0.022, 0.0, RD, z0, z1)
    rows = int((z1 - z0 - 0.1) / shelf)
    for k in range(rows + 1):
        z = z0 + 0.08 + k * shelf; bx('rack shelf', a0, a1, 0.03, RD, z - 0.018, z)
    bx('rack top', a0 - 0.04, a1 + 0.04, 0.0, RD + 0.04, z1, z1 + 0.06)
    bx('rack plinth', a0, a1, 0.0, RD, 0.0, z0 + 0.06)
    ax = Vector((0, inward, 0)) if along_x else Vector((inward, 0, 0))
    for i in range(n):
        u0 = a0 + i * cw + 0.03; m = int((cw - 0.06) / 0.077)
        for k in range(rows):
            z = z0 + 0.08 + k * shelf + 0.04
            lit = candles and rnd.random() < 0.025
            for j in range(m):
                if lit and j in (m // 2 - 1, m // 2, m // 2 + 1): continue
                if skip and skip(u0 + (j + 0.5) * (cw - 0.06) / m, z): continue
                if rnd.random() < 0.06: continue
                u = u0 + (j + 0.5) * (cw - 0.06) / m
                d = 0.05 + rnd.uniform(-0.01, 0.025); w = wall + inward * d
                o = Vector((u, w, z)) if along_x else Vector((w, u, z))
                BOTTLES.append((tuple(o), tuple(ax), 0 if rnd.random() < 0.6 else 1, 0 if rnd.random() < 0.55 else 1))
                if j < m - 1 and rnd.random() < 0.9:
                    u2 = u + 0.5 * (cw - 0.06) / m; o2 = Vector((u2, w + inward * 0.01, z + 0.065)) if along_x else Vector((w + inward * 0.01, u2, z + 0.065))
                    BOTTLES.append((tuple(o2), tuple(ax), 0 if rnd.random() < 0.6 else 1, 0 if rnd.random() < 0.5 else 1))
            if lit:
                u = u0 + (m // 2 + 0.5) * (cw - 0.06) / m; w = wall + inward * (RD - 0.12)
                p = (u, w, z - 0.04) if along_x else (w, u, z - 0.04); candle(p, 0.08, 4)

def candle_chandelier(cx, cy, z, top, iron, r=0.5, n=8):
    cyl('chain', 0.01, top - (z + 0.55), (cx, cy, (top + z + 0.55) / 2), (0, 0, 0), iron, 6)
    cyl('hub', 0.03, 0.6, (cx, cy, z + 0.25), (0, 0, 0), iron, 10)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.06, location=(cx, cy, z - 0.06)); bpy.context.active_object.data.materials.append(iron)
    torus('chandelier ring', r, 0.016, (cx, cy, z), (0, 0, 0), iron); torus('chandelier ring', r * 0.45, 0.012, (cx, cy, z + 0.38), (0, 0, 0), iron)
    for k in range(n):
        a = k / n * 2 * math.pi; ex, ey = cx + math.cos(a) * r, cy + math.sin(a) * r
        rod('arm', (cx, cy, z + 0.5), (ex, ey, z + 0.02), 0.008, iron); cyl('cup', 0.035, 0.025, (ex, ey, z + 0.02), (0, 0, 0), iron, 12)
        candle((ex, ey, z + 0.033), 0.13, 14)
    for k in range(n // 2):
        a = (k + 0.5) / (n // 2) * 2 * math.pi; ex, ey = cx + math.cos(a) * r * 0.45, cy + math.sin(a) * r * 0.45
        cyl('cup', 0.03, 0.02, (ex, ey, z + 0.39), (0, 0, 0), iron, 12); candle((ex, ey, z + 0.4), 0.11, 10)
    light((cx, cy, z - 0.2), 90, radius=0.4)

def stool(x, y, wood, h=0.66):
    cyl('stool seat', 0.19, 0.055, (x, y, h - 0.027), (0, 0, 0), wood, 24)
    for k in range(4):
        a = k / 4 * 2 * math.pi + 0.4; rod('stool leg', (x + math.cos(a) * 0.24, y + math.sin(a) * 0.24, 0), (x + math.cos(a) * 0.13, y + math.sin(a) * 0.13, h - 0.05), 0.022, wood, 10)
    torus('stool rung', 0.19, 0.012, (x, y, 0.25), (0, 0, 0), wood)

def grapes(x, y, z, mat):
    for i in range(22):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.018, segments=10, ring_count=6, location=(x + rnd.uniform(-0.05, 0.05), y + rnd.uniform(-0.04, 0.04), z + 0.02 + rnd.uniform(0, 0.07) * (1 - i / 30)))
        bpy.context.active_object.data.materials.append(mat)

def bread(x, y, z, mat, s=1.0, rot=0.0):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.1 * s, location=(x, y, z + 0.06 * s)); o = bpy.context.active_object; o.scale = (1.4, 0.8, 0.62); o.rotation_euler = (0, 0, rot); o.data.materials.append(mat)
    for p in o.data.polygons: p.use_smooth = True

def cheese(x, y, z, r, h, mat, rind):
    cyl('cheese', r, h, (x, y, z + h / 2), (0, 0, 0), mat, 32); torus('cheese rind', r, 0.006, (x, y, z + h), (0, 0, 0), rind)

def build():
    vault = pbr('sandstone_blocks_08', 'materials', (0.5, 0.38, 0.27), 1.0, 1.8)
    wstone = pbr('old_stone_wall', 'materials', (0.6, 0.48, 0.36), 1.0, 1.6)
    pillar_stone = pbr('yellow_stone_wall', 'materials', (0.62, 0.52, 0.42), 1.0, 1.6)
    floor = pbr('monastery_stone_floor', 'materials', (0.5, 0.42, 0.34), 0.6, 1.2)
    rib = pbr('rough_wood', 'materials', (0.24, 0.16, 0.1), 0.9)
    rackw = pbr('wood_cabinet_worn_long', 'materials', (0.62, 0.42, 0.26), 0.85)
    tablew = pbr('wood_table_worn', 'materials', (0.62, 0.46, 0.32), 0.7)
    top = tex_mat('stone top', A('assets', 'rooms', 'kitchen', 'marble_diff.jpg'), A('assets', 'rooms', 'kitchen', 'marble_rough.jpg'), tint=(1.35, 1.22, 1.05))
    rug = tex_mat('rug', K('rug_diff.jpg'), rough=0.95)
    iron = flat('iron', (0.03, 0.028, 0.026), 0.55, 0.35); brass = flat('brass', (0.78, 0.55, 0.26), 0.3, 1.0)
    glass = flat('glass', (0.95, 0.97, 0.98), 0.02, transmission=1.0); lglass = flat('lantern glass', (1.0, 0.86, 0.66), 0.08, transmission=0.85)
    g0 = flat('bottle glass green', (0.012, 0.035, 0.016), 0.08); g1 = flat('bottle glass brown', (0.045, 0.016, 0.006), 0.08)
    f0 = flat('foil red', (0.32, 0.03, 0.03), 0.35, 0.6); f1 = flat('foil gold', (0.55, 0.38, 0.12), 0.3, 0.9)
    cheese_m = flat('cheese', (0.82, 0.6, 0.22), 0.6); rind = flat('cheese rind', (0.55, 0.35, 0.12), 0.7)
    bread_m = flat('bread', (0.55, 0.3, 0.12), 0.75); grape_m = flat('grape', (0.18, 0.05, 0.14), 0.25)
    ivy = mat_alpha('ivy', A('assets', 'rooms', 'kitchen', 'ivy.png'))
    wax = flat('wax', (0.92, 0.88, 0.78), 0.45)

    # ------------------------------------------------------------ shell: flagstone floor, stone barrel vault with timber ribs
    box('floor', -HW - 0.3, HW + 0.3, -L - ND - 0.3, ND + 0.3, -0.12, 0.0, floor, 2.2)
    prof = profile()
    bm = bmesh.new(); r0 = [bm.verts.new((x, 0.0, z)) for x, z in prof]; r1 = [bm.verts.new((x, -L, z)) for x, z in prof]
    for i in range(len(prof) - 1): bm.faces.new((r0[i + 1], r0[i], r1[i], r1[i + 1]))
    shell = obj_from_bm('vault', bm, vault, True); shell.data.materials.append(wstone)
    for p in shell.data.polygons: p.material_index = 1 if p.center.z < WALL_H - 0.01 else 0
    box_uv(shell, 1.1); sol = shell.modifiers.new('s', 'SOLIDIFY'); sol.thickness = 0.3; sol.offset = 1
    RIBS = [-0.25 - k * 1.65 for k in range(11)]
    rp = profile(40, 0.02)[1:-1]
    for y in RIBS: sweep_profile('rib', [(prof[1][0] + 0.03, 0.0)] + rp + [(prof[-2][0] - 0.03, 0.0)], y, 0.26, 0.24, rib)
    for s in (-1, 1): box('wall plate', s * (HW - RD / 2) - RD / 2 - 0.02, s * (HW - RD / 2) + RD / 2 + 0.02, -L, 0.0, WALL_H - 0.1, WALL_H + 0.05, rib, 1.2)
    # end walls with a deep arched niche full of racks
    def end_wall(name, y, thick, sgn):
        bm = bmesh.new(); vs = [bm.verts.new((x, y, z)) for x, z in prof]; bm.faces.new(vs); w = obj_from_bm(name, bm, wstone)
        s = w.modifiers.new('s', 'SOLIDIFY'); s.thickness = thick; s.offset = 1.0 if sgn > 0 else -1.0
        bpy.context.view_layer.objects.active = w; bpy.ops.object.modifier_apply(modifier='s')
        cut(w, arch_cutter_y(0.0, NW, NRH, 0.0, y - 1, y + 1)); box_uv(w, 1.6); return w
    for y, sgn in ((0.0, 1), (-L, -1)):
        end_wall('end wall', y, 0.4, sgn)
        g = group((0.0, y - sgn * 0.02, 0.0)); stone_arch(g, NW, NRH, 0.5, rib, 0.22)
        yb = y + sgn * ND
        # niche: back, sides and a little barrel vault
        box('niche back', -NW / 2 - 0.1, NW / 2 + 0.1, min(yb, yb + sgn * 0.2), max(yb, yb + sgn * 0.2), 0.0, NRH + NW / 2 + 0.2, wstone, 1.6)
        for sx in (-1, 1): box('niche side', sx * NW / 2 - (0.2 if sx < 0 else 0), sx * NW / 2 + (0.2 if sx > 0 else 0), min(y, yb), max(y, yb), 0.0, NRH + NW / 2 + 0.2, wstone, 1.6)
        nv = cyl('niche vault', NW / 2 + 0.15, ND, (0, y + sgn * ND / 2, NRH), (math.pi / 2, 0, 0), vault, 32)
        cut(nv, [cyl('c', NW / 2, ND + 0.2, (0, y + sgn * ND / 2, NRH), (math.pi / 2, 0, 0), vault, 32), box('c', -3, 3, min(y, yb) - 1, max(y, yb) + 1, NRH - 3, NRH, vault)])
        box_uv(nv, 1.4)
        rack(-NW / 2 + 0.05, NW / 2 - 0.05, yb, -sgn, 0.0, NRH + 0.95, True, rackw)
        for sx in (-1, 1): rack(min(sx * NW / 2, sx * (HW - RD - 0.02)), max(sx * NW / 2, sx * (HW - RD - 0.02)), y, -sgn, 0.0, 2.55, True, rackw, 0.55)
        lantern(0.0, yb - sgn * 0.25, NRH + 0.55, 0.9, NRH + NW / 2, iron, lglass, 45)
        light((0, y + sgn * 0.6, 2.0), 80, radius=0.3)
    # ------------------------------------------------------------ wine racks down both side walls, in bays between timber posts
    PILLAR = (-L + 5.6, 1.1)                               # the big stone pillar on the left at the food end (centre y, width)
    DOOR = (-8.6, 1.3)                                     # an arched oak door in the left wall leading back into the house
    bays = [(-L + 0.05, -L + 3.4), (-L + 3.4, -L + 6.8), (-L + 6.8, -10.2), (-10.2, -6.85), (-6.85, -3.45), (-3.45, -0.05)]
    for s in (-1, 1):
        wall = s * HW
        for b0, b1 in bays:
            pieces = [(b0 + 0.12, b1 - 0.12)]
            if True:
                for c, w_ in ((PILLAR,) if s > 0 else (DOOR,)):
                    new = []
                    for p0, p1 in pieces:
                        if p1 <= c - w_ / 2 or p0 >= c + w_ / 2: new.append((p0, p1)); continue
                        if p0 < c - w_ / 2 - 0.15: new.append((p0, c - w_ / 2 - 0.05))
                        if p1 > c + w_ / 2 + 0.15: new.append((c + w_ / 2 + 0.05, p1))
                    pieces = new
            for p0, p1 in pieces: rack(p0, p1, wall, -s, 0.0, 2.55, False, rackw)
            xp = wall - s * 0.2
            box('post', xp - 0.16, xp + 0.16, b1 - 0.12, b1 + 0.12, 0.0, WALL_H + 0.05, rib, 1.2) if b1 < -0.1 else None
        for y in (-2.0, -5.2, -12.0, -15.0) if s < 0 else (-2.0, -5.2, -8.6, -15.0):
            xl = wall - s * (RD + 0.25)
            box('sconce arm', min(wall - s * RD, xl), max(wall - s * RD, xl), y - 0.015, y + 0.015, 2.42, 2.45, iron, 1.0); lantern(xl, y, 2.05, 0.95, 2.43, iron, lglass, 55)
    # the stone pillar (left, food end) and the oak door (left, middle)
    py, pw = PILLAR
    box('stone pillar', HW - 0.75, HW, py - pw / 2, py + pw / 2, 0.0, WALL_H + 0.3, pillar_stone, 1.2)
    for k in range(9):
        z = 0.15 + k * 0.32; box('pillar stone', HW - 0.8 - rnd.uniform(-0.03, 0.04), HW - 0.6, py - pw / 2 + rnd.uniform(0, 0.15), py + pw / 2 - rnd.uniform(0, 0.15), z, z + 0.28, pillar_stone, 0.9, 0.03)
    box('sconce arm', HW - 1.0, HW - 0.75, py - 0.015, py + 0.015, 2.12, 2.15, iron, 1.0); lantern(HW - 1.0, py, 1.75, 0.95, 2.13, iron, lglass, 55)
    dy, dw = DOOR
    box('door', -HW + 0.02, -HW + 0.12, dy - dw / 2, dy + dw / 2, 0.0, 1.85, rackw, 0.8)
    dt = cyl('door top', dw / 2, 0.1, (-HW + 0.07, dy, 1.85), (0, math.pi / 2, 0), rackw, 32); cut(dt, [box('c', -HW - 1, -HW + 1, dy - 1, dy + 1, 0.5, 1.85, rackw)])
    for k in range(5): z = 0.25 + k * 0.4; box('door strap', -HW + 0.12, -HW + 0.14, dy - dw / 2 + 0.05, dy + dw / 2 - 0.05, z, z + 0.05, iron, 1.0)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.06, minor_radius=0.01, location=(-HW + 0.17, dy + 0.4, 1.0), rotation=(0, math.pi / 2, 0)); bpy.context.active_object.data.materials.append(iron)
    g = group((-HW + 0.05, dy, 0.0), math.pi / 2); stone_arch(g, dw, 1.85, 0.5, rib, 0.16)

    # ------------------------------------------------------------ WINE END (y from -7 to 0): barrel table, barrels, crates, a counter, a rug
    def rugplane(cx, cy, sx, sy):
        bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5); uvl = bm.loops.layers.uv.new()
        for f in bm.faces:
            for l in f.loops: l[uvl].uv = (l.vert.co.x + 0.5, l.vert.co.y + 0.5)
        o = obj_from_bm('rug', bm, rug); o.scale = (sx, sy, 1); o.location = (cx, cy, 0.008)
    rugplane(0.1, -4.1, 3.6, 5.2)
    BT = (0.25, -4.3)
    model('wine_barrel_01', (BT[0], BT[1], 0), 0.3, height=0.98)
    t = stadium('barrel table top', 1.75, 0.82, 0.98, 1.05, tablew); t.location = (BT[0], BT[1], 0); t.rotation_euler = (0, 0, math.radians(72))
    model('wine_bottles_01', (BT[0] - 0.2, BT[1] + 0.05, 1.05), 1.4, width=0.42)
    for dx, dy_, h in ((0.35, -0.1, 0.18), (0.15, 0.22, 0.12), (-0.45, 0.25, 0.22), (0.55, 0.12, 0.1)):
        cyl('pillar candle', 0.04, h, (BT[0] + dx, BT[1] + dy_, 1.05 + h / 2), (0, 0, 0), wax, 20); candle((BT[0] + dx, BT[1] + dy_, 1.05 + h - 0.005), 0.01, 12)
    model('brass_goblets', (BT[0] + 0.05, BT[1] - 0.3, 1.05), 0.6, width=0.3)
    # left: barrels on a cradle, a small round table, standing barrels
    for k, y in enumerate((-6.4, -5.5)):
        b = model('wine_barrel_01', (-HW + RD + 0.55, y, 0.42), 0, height=0.98); b.rotation_euler = (0, math.pi / 2, 0)
    box('cradle', -HW + RD + 0.1, -HW + RD + 1.0, -6.95, -5.0, 0.0, 0.1, rib, 1.0)
    for y in (-6.75, -5.95, -5.15): box('cradle chock', -HW + RD + 0.15, -HW + RD + 0.95, y - 0.06, y + 0.06, 0.08, 0.22, rib, 1.0)
    model('wine_barrel_01', (-HW + RD + 0.45, -1.35, 0), 0.8, height=0.95); model('wine_barrel_01', (-HW + RD + 0.4, -2.3, 0), 2.1, height=0.9)
    cyl('side table top', 0.38, 0.05, (-HW + RD + 0.55, -3.7, 0.66), (0, 0, 0), tablew, 32); cyl('side table post', 0.06, 0.62, (-HW + RD + 0.55, -3.7, 0.33), (0, 0, 0), tablew, 16)
    for k in range(3): a = k / 3 * 6.28; rod('side table foot', (-HW + RD + 0.55, -3.7, 0.1), (-HW + RD + 0.55 + math.cos(a) * 0.3, -3.7 + math.sin(a) * 0.3, 0.0), 0.03, tablew)
    candle((-HW + RD + 0.55, -3.7, 0.685), 0.16, 10); model('jug_01', (-HW + RD + 0.4, -3.55, 0.685), 0.4, height=0.18)
    # right: stacked crates and a plant
    for y, n in ((-6.2, 2), (-5.4, 3), (-2.4, 1)):
        for k in range(n): model('wooden_crate_01', (HW - RD - 0.33, y, k * 0.27), math.pi / 2 + rnd.uniform(-0.08, 0.08), width=0.6)
    model('potted_plant_02', (HW - RD - 0.4, -1.3, 0), 0.4, height=0.9)
    # a long counter in front of the wine niche with bottles and candles
    box('counter', -1.65, 1.65, -1.05, -0.45, 0.06, 0.92, rackw, 1.2); box('counter top', -1.72, 1.72, -1.1, -0.4, 0.92, 0.97, tablew, 1.2, 0.01)
    model('wine_bottles_01', (-0.9, -0.75, 0.97), 0, width=0.5); model('wine_bottles_01', (1.0, -0.72, 0.97), 0.3, width=0.45)
    for x in (-1.4, -0.2, 0.4, 1.5): candle((x, -0.7, 0.97), rnd.uniform(0.1, 0.2), 10)
    leaf_cluster(ivy, -1.2, -0.6, 1.1, 10, 0.2, 0.3); leaf_cluster(ivy, 1.3, -0.6, 1.1, 8, 0.2, 0.3)
    candle_chandelier(0.0, -3.9, 2.7, vault_z(0.0) - 0.15, iron, 0.55, 8)
    for y in (-1.3, -6.5): candle_chandelier(0.0, y, 3.0, vault_z(0.0) - 0.15, iron, 0.3, 6)

    # ------------------------------------------------------------ FOOD END (y from -L to -10): long table full of food, stools, chest, round barrel table
    rugplane(0.2, -L + 4.2, 4.6, 6.2)
    TX0, TX1, TY0, TY1, TH = -1.0, 1.7, -L + 2.55, -L + 3.65, 0.9
    box('food table top', TX0, TX1, TY0, TY1, TH - 0.06, TH, top, 1.4, 0.01)
    box('food table apron', TX0 + 0.06, TX1 - 0.06, TY0 + 0.06, TY1 - 0.06, TH - 0.2, TH - 0.06, rackw, 1.0)
    for x in (TX0 + 0.1, TX1 - 0.1):
        for y in (TY0 + 0.1, TY1 - 0.1): box('food table leg', x - 0.06, x + 0.06, y - 0.06, y + 0.06, 0.0, TH - 0.06, rackw, 1.0, 0.01)
    box('food table shelf', TX0 + 0.12, TX1 - 0.12, TY0 + 0.12, TY1 - 0.12, 0.18, 0.22, rackw, 1.0)
    cy_ = (TY0 + TY1) / 2
    model('wine_bottles_01', (TX0 + 0.35, cy_ - 0.2, TH), 0.2, width=0.42); model('wine_bottles_01', (TX1 - 0.4, cy_ - 0.25, TH), 2.8, width=0.42)
    model('wooden_cutting_board', (0.0, cy_ + 0.15, TH), 0.1, width=0.5); cheese(0.0, cy_ + 0.15, TH + 0.04, 0.13, 0.09, cheese_m, rind); cheese(0.2, cy_ + 0.22, TH + 0.04, 0.07, 0.06, cheese_m, rind)
    model('CheeseBox_01', (0.55, cy_ - 0.05, TH), 0.3, width=0.26)
    bread(-0.45, cy_ + 0.05, TH, bread_m, 1.0, 0.4); bread(-0.6, cy_ + 0.25, TH, bread_m, 0.85, 1.2)
    model('wooden_bowl_01', (0.95, cy_ + 0.15, TH), 0, width=0.36); grapes(0.95, cy_ + 0.15, TH + 0.05, grape_m)
    for k in range(4): model('food_apple_01', (1.25 + 0.08 * (k % 2), cy_ + 0.3 + 0.07 * (k // 2), TH), k, height=0.08)
    model('jug_01', (0.3, cy_ + 0.35, TH), 0.5, height=0.2); model('potted_plant_04', (-0.85, cy_ - 0.25, TH), 0.2, height=0.32); model('potted_plant_04', (1.5, cy_ - 0.3, TH), 1.3, height=0.28)
    model('Lantern_01', (-0.2, cy_ - 0.3, TH), 0, height=0.24); candle((-0.2, cy_ - 0.3, TH + 0.03), 0.06, 8)
    for x in (0.7, 1.35): candle((x, cy_ - 0.35, TH), 0.14, 8)
    for x in (-0.55, 0.2, 0.95): stool(x, TY1 + 0.45, rackw)
    model('treasure_chest', (0.2, TY1 + 1.3, 0), 0.0, width=0.85)
    # left: round barrel-top table with plants and a candle, crates and a lying barrel by the stone pillar
    RTX, RTY = HW - 1.35, -L + 6.9
    model('wine_barrel_01', (RTX, RTY, 0), 0.5, height=0.85); cyl('barrel table top', 0.52, 0.05, (RTX, RTY, 0.875), (0, 0, 0), tablew, 40)
    model('potted_plant_02', (RTX - 0.15, RTY + 0.1, 0.9), 0.3, height=0.55); model('planter_pot_clay', (RTX + 0.25, RTY - 0.2, 0.9), 0, height=0.16); leaf_cluster(ivy, RTX + 0.25, RTY - 0.2, 1.15, 12, 0.18, 0.2)
    cyl('pillar candle', 0.045, 0.16, (RTX + 0.15, RTY + 0.3, 0.98), (0, 0, 0), wax, 20); candle((RTX + 0.15, RTY + 0.3, 1.055), 0.01, 12)
    cyl('hurricane', 0.08, 0.24, (RTX + 0.15, RTY + 0.3, 1.02), (0, 0, 0), glass, 24)
    for k in range(2): model('wooden_crate_01', (RTX + 0.1, RTY - 1.0, k * 0.27), math.pi / 2, width=0.55)
    b = model('wine_barrel_01', (RTX - 0.25, -L + 4.4, 0.4), 0, height=0.9); b.rotation_euler = (0, math.pi / 2, 0.15)
    model('wooden_bucket_01', (RTX + 0.35, -L + 3.0, 0), 0.5, height=0.32)
    # right: a floor lantern and a few crates
    model('wooden_lantern_01', (-HW + RD + 0.35, -L + 4.6, 0), 0.4, height=0.55); light((-HW + RD + 0.35, -L + 4.6, 0.3), 30)
    for k in range(2): model('wooden_crate_01', (-HW + RD + 0.35, -L + 6.0, k * 0.27), math.pi / 2, width=0.55)
    candle_chandelier(0.3, -L + 3.1, 2.6, vault_z(0.3) - 0.15, iron, 0.45, 8)
    candle_chandelier(0.0, -L + 0.7, 2.9, vault_z(0.0) - 0.15, iron, 0.3, 6)
    candle_chandelier(0.0, -8.6, 2.75, vault_z(0.0) - 0.15, iron, 0.5, 8)
    # ------------------------------------------------------------ all the bottles as one mesh
    bottles('wine bottles', BOTTLES, [g0, g1, f0, f1])
    w = bpy.data.worlds.new('w'); bpy.context.scene.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0.3, 0.2, 0.12, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.04
    for y in (-3.0, -8.5, -14.0):
        f = light((0, y, APEX - 1.0), 35, (1.0, 0.62, 0.32), kind='AREA'); f.data.size = 3.0

def walk_rects():
    m = HW - RD - 0.3
    R = [(-m, m, -10.4, -5.35),                    # the open middle
         (-1.85, -0.75, -5.35, -1.25), (1.25, m - 0.45, -5.35, -1.25), (-1.85, m - 0.45, -1.6, -1.25),   # round the barrel table (wine end)
         (-m, 0.85, -11.7, -10.4),                  # beside the round barrel table
         (-m, -0.4, -12.6, -11.7), (0.8, 1.2, -12.6, -11.7),            # either side of the chest
         (-m, -1.15, -L + 0.8, -12.6), (1.85, m - 0.5, -L + 0.8, -13.0)]  # round the food table
    return [[x0, x1, -y1, -y0] for x0, x1, y0, y1 in R]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--render', default=''); ap.add_argument('--samples', type=int, default=96); ap.add_argument('--res', default='1280x720')
    ap.add_argument('--glb', default=''); ap.add_argument('--cam', default='wine')
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
    bpy.ops.wm.read_factory_settings(use_empty=True); build()
    for o in bpy.context.scene.objects:
        if o.type == 'LIGHT' and hasattr(o, 'visible_camera'): o.visible_camera = False
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = a.samples; sc.cycles.use_denoising = True; sc.cycles.max_bounces = 8
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'; sc.view_settings.exposure = -0.6
    w, h = map(int, a.res.split('x')); sc.render.resolution_x, sc.render.resolution_y = w, h
    x, y, z, tilt, head, lens = CAMS[a.cam] if a.cam in CAMS else map(float, a.cam.split(','))
    cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera')); sc.collection.objects.link(cam); sc.camera = cam
    cam.location = (x, y, z); cam.rotation_euler = (math.radians(tilt), 0, math.radians(head)); cam.data.lens = lens
    cfgp = K('room.json'); cfg = json.load(open(cfgp)) if os.path.exists(cfgp) else {}
    tints = {}
    for m in bpy.data.materials:
        if m.use_nodes:
            for n in m.node_tree.nodes:
                if n.type == 'MIX_RGB' and n.blend_type == 'MULTIPLY': tints[m.name] = [round(v, 3) for v in n.inputs[2].default_value[:3]]
    cfg.update(name='Wine & Food Cellar', glb='assets/rooms/cellar/cellar.glb', spawn=dict(x=0.25, z=9.8, yaw=0), walk=walk_rects(), lights=[], probe=[0, 1.4, 8.5], tints=tints, floor='monastery_stone_floor')
    cfg.setdefault('exposure', 1.0); cfg.setdefault('version', 1); cfg.setdefault('wallBoost', 1.0); cfg.setdefault('maxFlameLights', 40)
    json.dump(cfg, open(cfgp, 'w'), indent=1)
    if a.render: sc.render.filepath = os.path.abspath(a.render); bpy.ops.render.render(write_still=True)
    if a.glb:
        keep = ('stone', 'sandstone', 'planks', 'rough_wood', 'wood_table', 'rug', 'ivy', 'marble')
        for im in bpy.data.images:
            if im.size[0] > 512 and not any(k in im.name for k in keep): im.scale(512, 512)
        bpy.ops.object.select_all(action='DESELECT')
        for o in list(sc.objects):
            if o.type == 'EMPTY' and o.instance_type == 'COLLECTION': o.select_set(True)
        if any(o.select_get() for o in sc.objects): bpy.ops.object.duplicates_make_real()
        bpy.ops.export_scene.gltf(filepath=os.path.abspath(a.glb), export_format='GLB', export_lights=False, export_cameras=False, export_apply=True, export_image_format='JPEG', export_jpeg_quality=82)

if __name__ == '__main__':
    main()
