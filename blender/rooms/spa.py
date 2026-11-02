"""Hobbit-house spa & sauna, rebuilt as real 3D rooms from the two 'Spa & Sauna' images.
You enter the hot-tub room (second image), walk through the glass-fronted cedar sauna on its left, and come out into the
pool room (first image) on the other side.

Blender axes: hot-tub room x -3..3, y -7..0 (window and hot tub on the back wall y = 0, entrance door in the front wall);
sauna x -6.2..-3, y -5.5..-1.5; pool room x -14..-6.2, y -7.6..0.4.

    python blender/rooms/spa.py --render docs/rooms/spa.png --cam tub ; python blender/rooms/spa.py --render docs/rooms/spa_pool.png --cam pool
    python blender/rooms/spa.py --glb assets/rooms/spa/spa.glb
"""
import argparse, json, math, os, sys, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
from hero_room import A, pbr, flat, image_mat, obj_from_bm, box_uv, box, cyl, torus, cut, sweep_profile, model, light, candle
from kitchen import lantern, leaf_cluster, group, kid, tex_mat, mat_alpha, arch_cutter_y, arch_window, stone_arch
from hallway import pillow
from dining import rod

HW, LA = 4.1, 9.2                       # hot-tub room half width and length
WALL_H, APEX = 3.0, 5.0
SX0, SX1, SY0, SY1, SH = -8.4, -4.1, -6.9, -2.1, 2.45      # sauna box
PX0, PX1, PY0, PY1, PH = -19.6, -8.4, -10.2, 0.8, 3.7       # pool room box
QX0, QX1, QY0, QY1 = -16.4, -11.0, -7.4, -2.0               # the pool
DOOR_Y = -4.5                                              # sauna door centre (both glass walls)
rnd = random.Random(81)
CAMS = {'tub': (2.6, -8.7, 1.65, 87, 22, 16), 'pool': (-19.0, -9.6, 1.8, 82, -50, 15), 'sauna': (-6.2, -6.5, 1.5, 88, 0, 15)}

def K(*p): return A('assets', 'rooms', 'spa', *p)

def vault_z(x, inset=0.0):
    t = max(-1.0, min(1.0, x / (HW - inset)))
    return WALL_H + math.sqrt(max(0.0, 1 - t * t)) * (APEX - WALL_H - inset)

def profile(n=40, inset=0.0):
    pts = [(-HW + inset, 0.0)]
    for i in range(n + 1):
        a = math.pi - i / n * math.pi
        pts.append((math.cos(a) * (HW - inset), WALL_H + math.sin(a) * (APEX - WALL_H - inset)))
    pts.append((HW - inset, 0.0)); return pts

def candles_cluster(x, y, z, wax, n=3, s=1.0):
    for k in range(n):
        h = rnd.uniform(0.1, 0.3) * s; dx, dy = rnd.uniform(-0.12, 0.12) * s, rnd.uniform(-0.12, 0.12) * s; r = rnd.uniform(0.035, 0.055) * s
        cyl('pillar candle', r, h, (x + dx, y + dy, z + h / 2), (0, 0, 0), wax, 20); candle((x + dx, y + dy, z + h - 0.005), 0.01, 7)

def floor_lantern(x, y, iron, lglass, s=1.0):
    lantern(x, y, 0.0, 1.7 * s, None, iron, lglass, 30)

def glass_wall(x, y0, y1, z1, frame, glass, door=(DOOR_Y - 0.45, DOOR_Y + 0.45)):
    """A glazed partition in the plane x = x from y0 to y1 with an open doorway."""
    t = 0.06
    for y in (y0, y1, door[0], door[1]): box('sauna frame', x - t, x + t, y - t, y + t, 0.0, z1, frame, 1.0)
    box('sauna frame', x - t, x + t, y0, y1, z1 - 0.1, z1, frame, 1.0); box('sauna frame', x - t, x + t, y0, y1, 0.0, 0.06, frame, 1.0)
    box('sauna frame', x - t, x + t, door[0], door[1], 2.05, 2.12, frame, 1.0)
    for a, b in ((y0, door[0]), (door[1], y1)):
        n = max(1, round((b - a) / 0.9))
        for k in range(1, n): yy = a + k * (b - a) / n; box('sauna frame', x - 0.03, x + 0.03, yy - 0.025, yy + 0.025, 0.0, z1, frame, 1.0)
        box('sauna glass', x - 0.006, x + 0.006, a + t, b - t, 0.06, z1 - 0.1, glass, 1.0)
    box('sauna glass', x - 0.006, x + 0.006, door[0] + t, door[1] - t, 2.12, z1 - 0.1, glass, 1.0)

def lounger(x, y, rot, wood, cushion):
    g = group((x, y, 0), rot)
    kid(box('lounger frame', -0.34, 0.34, -0.95, 0.95, 0.22, 0.3, wood, 1.0, 0.01), g)
    for sx in (-1, 1):
        for sy in (-1, 1): kid(box('lounger leg', sx * 0.3 - 0.03, sx * 0.3 + 0.03, sy * 0.88 - 0.03, sy * 0.88 + 0.03, 0.0, 0.22, wood, 1.0), g)
    kid(pillow(0, -0.25, 0.36, 0.64, 1.35, 0.12, cushion), g)
    back = pillow(0, 0.72, 0.58, 0.64, 0.6, 0.12, cushion); back.rotation_euler = (math.radians(-55), 0, 0); kid(back, g)
    kid(pillow(0, 0.6, 0.78, 0.5, 0.18, 0.28, cushion), g)
    kid(box('folded towel', -0.25, 0.25, -0.85, -0.55, 0.42, 0.5, flat('towel', (0.85, 0.82, 0.76), 0.95), 1.0, 0.02), g)

def build():
    floor = pbr('monastery_stone_floor', 'materials', (0.66, 0.56, 0.46), 0.45, 1.2)
    wallA = pbr('old_stone_wall', 'materials', (0.86, 0.72, 0.56), 1.0, 1.4)
    vaultA = pbr('rustic_stone_wall', 'materials', (0.8, 0.68, 0.54), 1.0, 1.4)
    wallB = pbr('rustic_stone_wall', 'materials', (0.42, 0.38, 0.34), 1.0, 1.8)
    rib = pbr('rough_wood', 'materials', (0.34, 0.23, 0.15), 0.9)
    cedar = pbr('oak_wood_planks', 'materials', (0.95, 0.62, 0.34), 0.8)
    cedar_dark = pbr('wood_cabinet_worn_long', 'materials', (0.62, 0.42, 0.26), 0.8)
    ceilB = pbr('dark_wooden_planks', 'materials', (0.32, 0.22, 0.15), 0.9)
    coping = pbr('yellow_stone_wall', 'materials', (0.8, 0.72, 0.62), 0.5, 0.8)
    pool_tile = pbr('yellow_stone_wall', 'materials', (0.2, 0.42, 0.42), 0.4, 0.8)
    tub_stone = pbr('stacked_stone_wall', 'materials', (0.62, 0.56, 0.5), 0.8, 1.6) if os.path.exists(A('assets', 'materials', 'stacked_stone_wall_diff.jpg')) else pbr('old_stone_wall', 'materials', (0.62, 0.55, 0.48), 0.8, 1.6)
    frame = flat('sauna frame wood', (0.32, 0.18, 0.08), 0.5); wframe = flat('window frame', (0.12, 0.07, 0.035), 0.55)
    glass = flat('glass', (0.95, 0.97, 0.98), 0.02, transmission=1.0); lglass = flat('lantern glass', (1.0, 0.86, 0.66), 0.08, transmission=0.85)
    water = flat('pool water', (0.06, 0.32, 0.3), 0.02, transmission=0.7); tubwater = flat('tub water', (0.25, 0.62, 0.6), 0.02, transmission=0.55)
    iron = flat('iron', (0.03, 0.028, 0.026), 0.55, 0.35); brass = flat('brass', (0.78, 0.55, 0.26), 0.3, 1.0)
    cushion = flat('cushion linen', (0.5, 0.45, 0.38), 0.9); towel = flat('towel', (0.85, 0.82, 0.76), 0.95)
    wax = flat('wax', (0.92, 0.88, 0.78), 0.45); ivy = mat_alpha('ivy', A('assets', 'rooms', 'kitchen', 'ivy.png'))
    sauna_glow = flat('sauna glow', (1, 0.7, 0.4), 1, emit=(1.0, 0.62, 0.28), strength=6)

    # ============================================================ ROOM A: the hot-tub room (second image)
    box('floor A', -HW - 0.3, HW + 0.3, -LA - 0.3, 0.3, -0.12, 0.0, floor, 1.6)
    prof = profile()
    bm = bmesh.new(); r0 = [bm.verts.new((x, 0.0, z)) for x, z in prof]; r1 = [bm.verts.new((x, -LA, z)) for x, z in prof]
    for i in range(len(prof) - 1): bm.faces.new((r0[i + 1], r0[i], r1[i], r1[i + 1]))
    shell = obj_from_bm('vault', bm, vaultA, True); shell.data.materials.append(wallA)
    for p in shell.data.polygons: p.material_index = 1 if p.center.z < WALL_H - 0.01 else 0
    box_uv(shell, 1.6); sol = shell.modifiers.new('s', 'SOLIDIFY'); sol.thickness = 0.3; sol.offset = 1
    bpy.context.view_layer.objects.active = shell; bpy.ops.object.modifier_apply(modifier='s')
    cut(shell, [box('c', -HW - 1, -HW + 0.5, SY0, SY1, 0.0, SH, wallA)])
    def end_wall(name, y, thick, sgn):
        bm = bmesh.new(); vs = [bm.verts.new((x, y, z)) for x, z in prof]; bm.faces.new(vs); w = obj_from_bm(name, bm, wallA)
        s = w.modifiers.new('s', 'SOLIDIFY'); s.thickness = thick; s.offset = 1.0 if sgn > 0 else -1.0
        bpy.context.view_layer.objects.active = w; bpy.ops.object.modifier_apply(modifier='s'); return w
    back = end_wall('back wall', 0.0, 0.45, 1); front = end_wall('front wall', -LA, 0.4, -1)
    rp = profile(40, 0.02)[1:-1]
    for k in range(8): sweep_profile('rib', rp, -0.5 - k * 1.18, 0.26, 0.28, rib)
    box('ridge', -0.12, 0.12, -LA, 0.0, APEX - 0.26, APEX - 0.02, rib, 1.2)
    bulb = flat('bulb', (1, 0.8, 0.5), 1, emit=(1.0, 0.75, 0.45), strength=15)
    for k in range(5):
        y = -1.1 - k * 1.65
        for x in (-1.4, 1.4):
            z = vault_z(x, 0.05) - 0.02; bpy.ops.mesh.primitive_uv_sphere_add(radius=0.025, location=(x, y, z)); bpy.context.active_object.data.materials.append(bulb); light((x, y, z - 0.08), 12, radius=0.03)
    # back wall: arched window onto the mountains, the stone hot tub in front of it
    WX, WW, WRH, WZ = 1.0, 2.3, 1.6, 1.05
    cut(back, arch_cutter_y(WX, WW, WRH, WZ, -0.2, 0.8)); box_uv(back, 1.6)
    g = group((WX, 0.22, WZ)); arch_window(g, WW, WRH, 3, 2, wframe, glass, 0, ring=False)
    g2 = group((WX, 0.0, WZ)); stone_arch(g2, WW, WRH, 0.2, vaultA, 0.2)
    a = light((WX, 1.4, WZ + 1.0), 700, (0.85, 0.92, 1.0), kind='AREA'); a.data.size = WW; a.rotation_euler = (math.radians(90), 0, 0)
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1); bmesh.ops.scale(bm, vec=(34, 14.5, 1), verts=bm.verts)
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 4, 'X')); bmesh.ops.translate(bm, vec=(WX, 14, 2.1), verts=bm.verts)
    view = obj_from_bm('valley view', bm, image_mat('view', A('assets', 'rooms', 'kitchen', 'view.jpg'), 1.2)); uvl = view.data.uv_layers.new()
    for i, l in enumerate(uvl.data): co = view.data.vertices[view.data.loops[i].vertex_index].co; l.uv = ((co.x - WX) / 34 + 0.3, (co.z - 2.1) / 14.5 + 0.5)
    TX0, TX1, TY0, TY1 = -1.2, 3.2, -2.9, -0.05
    tub = box('hot tub', TX0, TX1, TY0, TY1, 0.0, 0.62, tub_stone, 0.9, 0.02)
    cut(tub, [box('c', TX0 + 0.22, TX1 - 0.22, TY0 + 0.22, TY1 - 0.22, 0.12, 1.0, tub_stone)]); box_uv(tub, 0.9)
    box('tub ledge', TX0 - 0.04, TX1 + 0.04, TY0 - 0.04, TY0 + 0.24, 0.62, 0.68, coping, 1.0, 0.01)
    for x0, x1 in ((TX0 - 0.04, TX0 + 0.24), (TX1 - 0.24, TX1 + 0.04)): box('tub ledge', x0, x1, TY0, TY1, 0.62, 0.68, coping, 1.0, 0.01)
    box('tub water', TX0 + 0.22, TX1 - 0.22, TY0 + 0.22, TY1 - 0.22, 0.5, 0.52, tubwater, 1.0)
    for k in range(4): light((TX0 + 0.5 + k * (TX1 - TX0 - 1.0) / 3, (TY0 + TY1) / 2, 0.3), 25, (0.4, 0.9, 1.0), radius=0.1)
    for x in (TX0 + 0.12, TX1 - 0.12): candles_cluster(x, TY0 + 0.12, 0.68, wax, 2, 0.8)
    model('potted_plant_01', (TX1 + 0.3, -0.45, 0), 0.3, height=1.8); model('potted_plant_01', (TX0 - 0.45, -0.4, 0), 1.6, height=1.6)
    model('potted_plant_04', (TX0 + 0.4, -0.15, 0.68), 0, height=0.3)
    leaf_cluster(ivy, WX, -0.2, WZ + WRH + WW / 2 + 0.2, 26, 0.9, 0.6)
    # right wall: a console of candles and towels, a lantern, a plant; ivy climbing the wall
    CX = HW - 0.3
    box('console', CX - 0.25, CX + 0.15, -6.6, -4.4, 0.75, 0.8, cedar_dark, 1.0, 0.01)
    for y in (-6.55, -4.45):
        for dx in (-0.2, 0.1): box('console leg', CX + dx - 0.025, CX + dx + 0.025, y - 0.025, y + 0.025, 0.0, 0.75, cedar_dark, 1.0)
    box('console shelf', CX - 0.22, CX + 0.12, -6.55, -4.45, 0.2, 0.24, cedar_dark, 1.0)
    for k in range(4): box('rolled towel', CX - 0.2, CX + 0.1, -6.45 + k * 0.17, -6.32 + k * 0.17, 0.24, 0.34, towel, 1.0, 0.04)
    candles_cluster(CX - 0.05, -5.8, 0.8, wax, 4, 1.1); candles_cluster(CX - 0.05, -4.8, 0.8, wax, 3, 1.0)
    model('ceramic_vase_04', (CX - 0.05, -5.3, 0.8), 0, height=0.28)
    for y in (-7.4, -3.6): box('sconce arm', HW - 0.25, HW, y - 0.015, y + 0.015, 1.95, 1.98, iron, 1.0); lantern(HW - 0.25, y, 1.62, 0.9, 1.96, iron, lglass, 40)
    model('potted_plant_02', (HW - 0.45, -8.4, 0), 0.6, height=0.95); model('potted_plant_01', (HW - 0.5, -3.3, 0), 2.0, height=1.5)
    for k in range(8): leaf_cluster(ivy, HW - 0.2, -0.8 - k * 1.1, WALL_H + 0.15, 10, 0.25, 0.9)
    # left wall: the sauna front, lanterns and candles on the floor, towels on hooks
    glass_wall(-HW, SY0, SY1, SH, frame, glass)
    for y in (SY1 + 0.25, SY0 - 0.3): box('sauna post', -HW - 0.1, -HW + 0.12, y - 0.12, y + 0.12, 0.0, SH + 0.1, cedar_dark, 1.0)
    box('sauna lintel', -HW - 0.1, -HW + 0.14, SY0 - 0.4, SY1 + 0.4, SH, SH + 0.22, cedar_dark, 1.0)
    for y in (SY0 - 0.25, SY0 - 0.05):
        cyl('towel hook', 0.012, 0.08, (-HW + 0.06, y, 1.75), (0, math.pi / 2, 0), brass, 8)
        box('hanging towel', -HW + 0.06, -HW + 0.12, y - 0.09, y + 0.09, 0.9, 1.75, towel, 1.0, 0.02)
    for (x, y, s) in ((-HW + 0.45, -7.4, 1.0), (-HW + 0.7, -7.8, 0.75), (-HW + 0.45, -1.4, 0.9)): floor_lantern(x, y, iron, lglass, s)
    candles_cluster(-HW + 0.5, -8.3, 0.0, wax, 4, 1.2); candles_cluster(-HW + 0.85, -1.6, 0.0, wax, 3, 1.1)
    model('potted_plant_02', (-HW + 0.5, -0.6, 0), 2.1, height=0.9)
    model('painted_wooden_bench', (-1.2, -7.6, 0), 0.0, width=1.5)
    for k in range(3): box('rolled towel', -1.65 + k * 0.32, -1.38 + k * 0.32, -7.75, -7.45, 0.45, 0.55, towel, 1.0, 0.04)
    model('potted_plant_02', (-2.6, -8.4, 0), 1.2, height=0.9)
    # front wall: the entrance door
    cut(front, arch_cutter_y(2.0, 1.2, 1.6, 0.0, -LA - 1, -LA + 1)); box_uv(front, 1.6)
    g = group((2.0, -LA, 0.0)); stone_arch(g, 1.2, 1.6, 0.5, vaultA, 0.2)
    box('door', 1.4, 2.6, -LA - 0.25, -LA - 0.18, 0.0, 2.2, cedar_dark, 0.8)
    for y in (-2.2, -5.2, -8.0):
        f = light((0.3, y, WALL_H), 120, (1.0, 0.7, 0.42), kind='AREA'); f.data.size = 2.2; f.rotation_euler = (math.pi, 0, 0)

    # ============================================================ THE SAUNA: cedar box with tiered benches, glass on both ends
    box('sauna floor', SX0, SX1, SY0, SY1, 0.0, 0.04, cedar, 0.8)
    box('sauna ceiling', SX0 - 0.1, SX1 + 0.1, SY0 - 0.1, SY1 + 0.1, SH, SH + 0.12, cedar, 0.8)
    box('sauna wall', SX0 - 0.1, SX1 + 0.1, SY1, SY1 + 0.12, 0.0, SH + 0.12, cedar, 0.8)
    box('sauna wall', SX0 - 0.1, SX1 + 0.1, SY0 - 0.12, SY0, 0.0, SH + 0.12, cedar, 0.8)
    box('sauna roof block', SX0 - 0.1, SX1 + 0.1, SY0 - 0.12, SY1 + 0.12, SH + 0.12, 5.2, wallA, 1.6)
    for y0, y1 in ((PY0, SY0 - 0.12), (SY1 + 0.12, PY1)): box('party wall', SX0, SX1, y0, y1, 0.0, 5.2, wallA, 1.6)
    glass_wall(SX0, SY0, SY1, SH, frame, glass)
    for z, d in ((0.45, 0.62), (0.9, 0.5), (1.3, 0.42)):
        y0 = SY1 - (0.62 + 0.5 + 0.42) + {0.45: 0, 0.9: 0.62, 1.3: 1.12}[z]
        for k in range(int(d / 0.1)):
            yy = SY1 - (1.54 - {0.45: 0, 0.9: 0.62, 1.3: 1.12}[z]) + k * 0.1 + 0.05
            box('bench slat', SX0 + 0.3, SX1 - 0.3, yy - 0.04, yy + 0.04, z - 0.04, z, cedar, 0.8, 0.004)
        box('bench riser', SX0 + 0.3, SX1 - 0.3, y0 - 0.02, y0, 0.0, z - 0.04, cedar, 0.8)
        box('bench glow', SX0 + 0.35, SX1 - 0.35, y0 + 0.01, y0 + 0.03, z - 0.08, z - 0.06, sauna_glow, 1.0)
    for k in range(int((SX1 - SX0) / 0.12)):                     # vertical cedar boards on the back wall
        x = SX0 + 0.06 + k * 0.12; box('sauna board', x - 0.055, x + 0.055, SY1 - 0.02, SY1, 0.04, SH, cedar, 0.8)
    box('sauna stove', SX1 - 0.75, SX1 - 0.25, SY0 + 0.15, SY0 + 0.6, 0.04, 0.75, iron, 1.0, 0.02)
    rock = flat('sauna rock', (0.18, 0.17, 0.16), 0.8)
    for k in range(18):
        bpy.ops.mesh.primitive_ico_sphere_add(radius=rnd.uniform(0.05, 0.08), subdivisions=1, location=(SX1 - 0.5 + rnd.uniform(-0.2, 0.2), SY0 + 0.37 + rnd.uniform(-0.17, 0.17), 0.8 + rnd.uniform(0, 0.08)))
        bpy.context.active_object.data.materials.append(rock)
    box('stove guard', SX1 - 0.85, SX1 - 0.82, SY0 + 0.1, SY0 + 0.7, 0.04, 0.9, cedar, 0.8)
    model('wooden_bucket_01', (SX0 + 0.5, SY0 + 0.35, 0.04), 0.3, height=0.3)
    for x in (SX0 + 0.7, SX1 - 0.7):
        box('sauna lamp', x - 0.1, x + 0.1, SY1 - 0.08, SY1, 1.7, 1.9, sauna_glow, 1.0); light((x, SY1 - 0.3, 1.8), 45, (1.0, 0.6, 0.3), radius=0.15)
    light(((SX0 + SX1) / 2, (SY0 + SY1) / 2, SH - 0.2), 60, (1.0, 0.6, 0.3), radius=0.4)

    # ============================================================ ROOM B: the pool room (first image)
    for x0, x1, y0, y1 in ((PX0, PX1, PY0, QY0 - 0.3), (PX0, PX1, QY1 + 0.3, PY1), (PX0, QX0 - 0.3, QY0 - 0.3, QY1 + 0.3), (QX1 + 0.3, PX1, QY0 - 0.3, QY1 + 0.3)):
        box('floor B', x0, x1, y0, y1, -0.12, 0.0, floor, 1.6)
    # coping stones round the pool, the basin, the water
    for x0, x1, y0, y1 in ((QX0 - 0.3, QX1 + 0.3, QY0 - 0.3, QY0), (QX0 - 0.3, QX1 + 0.3, QY1, QY1 + 0.3), (QX0 - 0.3, QX0, QY0, QY1), (QX1, QX1 + 0.3, QY0, QY1)):
        box('pool coping', x0, x1, y0, y1, -0.1, 0.06, coping, 0.6, 0.02)
    for x0, x1, y0, y1 in ((QX0 - 0.2, QX1 + 0.2, QY0 - 0.2, QY0), (QX0 - 0.2, QX1 + 0.2, QY1, QY1 + 0.2), (QX0 - 0.2, QX0, QY0, QY1), (QX1, QX1 + 0.2, QY0, QY1)):
        box('pool wall', x0, x1, y0, y1, -1.4, -0.1, pool_tile, 0.6)
    box('pool floor', QX0, QX1, QY0, QY1, -1.5, -1.4, pool_tile, 0.6)
    box('pool water', QX0, QX1, QY0, QY1, -0.16, -0.14, water, 1.0)
    for k in range(3): light((QX0 + 0.6 + k * (QX1 - QX0 - 1.2) / 2, (QY0 + QY1) / 2, -0.8), 60, (0.3, 0.85, 0.85), radius=0.2)
    box('pool step', QX1 - 1.1, QX1, QY0, QY0 + 0.45, -1.4, -0.55, coping, 0.6)
    # walls: dark rough stone with warm uplights, a beamed dark wood ceiling with little spots
    for x0, x1, y0, y1 in ((PX0 - 0.3, PX0, PY0, PY1), (PX0 - 0.3, PX1, PY1, PY1 + 0.3), (PX0 - 0.3, PX1, PY0 - 0.3, PY0)):
        box('pool room wall', x0, x1, y0, y1, 0.0, PH, wallB, 1.6)
    box('pool room ceiling', PX0 - 0.3, PX1, PY0 - 0.3, PY1 + 0.3, PH, PH + 0.15, ceilB, 1.4)
    for k in range(7): x = PX0 + 0.8 + k * (PX1 - PX0 - 1.6) / 6; box('ceiling beam', x - 0.13, x + 0.13, PY0, PY1, PH - 0.26, PH, rib, 1.2)
    for y in (PY0 + 1.5, (PY0 + PY1) / 2, PY1 - 1.5): box('ceiling beam', PX0, PX1, y - 0.1, y + 0.1, PH - 0.2, PH - 0.0, rib, 1.2)
    for k in range(6):
        for y in (PY0 + 2.6, PY1 - 2.6):
            x = PX0 + 1.4 + k * 1.75; bpy.ops.mesh.primitive_uv_sphere_add(radius=0.025, location=(x, y, PH - 0.03)); bpy.context.active_object.data.materials.append(bulb); light((x, y, PH - 0.1), 14, radius=0.03)
    for x in [PX0 + 0.6 + k * 1.2 for k in range(10)]:
        light((x, PY1 - 0.18, 0.15), 30, (1.0, 0.65, 0.35), radius=0.05)                    # uplights washing the back wall
    for y in [PY0 + 0.6 + k * 1.2 for k in range(9)]: light((PX0 + 0.18, y, 0.15), 30, (1.0, 0.65, 0.35), radius=0.05)
    for k in range(8): leaf_cluster(ivy, PX0 + 0.2, PY0 + 1.0 + k * 1.2, PH - 0.3, 10, 0.3, 1.2)
    # the sauna's glass side (east wall) and stone walls either side of it
    for y0, y1 in ((PY0, SY0 - 0.12), (SY1 + 0.12, PY1)): box('pool room wall', PX1 - 0.02, PX1 + 0.3, y0, y1, 0.0, PH, wallB, 1.6)
    box('pool room wall', PX1 - 0.02, PX1 + 0.3, SY0 - 0.12, SY1 + 0.12, SH + 0.12, PH, wallB, 1.6)
    # loungers along the west side, candles and lanterns round the pool, a stone console with a basin, plants
    for y in (-7.6, -5.6, -3.6, -1.6): lounger(PX0 + 1.0, y, math.pi, cedar_dark, cushion)
    for (x, y) in ((QX0 - 0.15, QY0 - 0.15), (QX1 + 0.15, QY0 - 0.15), (QX0 - 0.15, QY1 + 0.15), (QX1 + 0.15, QY1 + 0.15)): candles_cluster(x, y, 0.06, wax, 3, 1.0)
    for (x, y) in ((PX1 - 0.6, PY0 + 0.5), (PX0 + 0.5, PY0 + 0.5), (PX1 - 0.6, PY1 - 0.6)): floor_lantern(x, y, iron, lglass, 1.0)
    box('stone console', -14.7, -12.7, PY1 - 0.5, PY1 - 0.02, 0.0, 0.85, coping, 0.8, 0.02)
    cyl('stone basin', 0.25, 0.14, (-13.7, PY1 - 0.26, 0.92), (0, 0, 0), coping, 32)
    candles_cluster(-14.3, PY1 - 0.26, 0.85, wax, 3, 1.0); candles_cluster(-13.1, PY1 - 0.26, 0.85, wax, 3, 1.0)
    model('potted_plant_01', (-15.5, PY1 - 0.45, 0), 0.3, height=1.8); model('potted_plant_01', (-11.9, PY1 - 0.45, 0), 1.1, height=1.6)
    model('potted_plant_02', (PX0 + 0.5, PY1 - 0.5, 0), 0.5, height=1.0); model('potted_plant_02', (PX1 - 0.6, PY0 + 1.3, 0), 2.4, height=0.95)
    model('potted_plant_01', (PX0 + 0.5, PY0 + 1.4, 0), 1.7, height=1.6)
    for x in (-17.5, -10.0): box('sconce arm', x - 0.015, x + 0.015, PY1 - 0.25, PY1, 1.95, 1.98, iron, 1.0); lantern(x, PY1 - 0.25, 1.62, 0.9, 1.96, iron, lglass, 35)
    w = bpy.data.worlds.new('w'); bpy.context.scene.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0.4, 0.45, 0.5, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.05
    for (x, y) in ((-16.5, -8.6), (-11.5, -8.6), (-16.5, -0.4), (-11.5, -0.4)):
        f = light((x, y, PH - 0.4), 90, (1.0, 0.68, 0.4), kind='AREA'); f.data.size = 3.0; f.rotation_euler = (math.pi, 0, 0)

def walk_rects():
    R = [(-HW + 0.5, HW - 0.6, -LA + 0.4, TY0_W),            # hot-tub room, in front of the tub
         (-HW + 0.5, -1.6, TY0_W, -0.7),                      # beside the tub
         (SX0 - 0.4, SX1 + 0.55, DOOR_Y - 0.4, DOOR_Y + 0.4),  # through the sauna
         (PX1 - 1.5, PX1 - 0.15, PY0 + 0.4, PY1 - 0.6),        # east side of the pool room
         (PX0 + 1.5, PX1 - 0.15, PY0 + 0.4, QY0 - 0.35),       # south side
         (PX0 + 1.5, PX1 - 0.15, QY1 + 0.35, PY1 - 0.6),       # north side
         (PX0 + 1.5, QX0 - 0.35, PY0 + 0.4, PY1 - 0.6)]        # west side, in front of the loungers
    return [[x0, x1, -y1, -y0] for x0, x1, y0, y1 in R]
TY0_W = -3.15

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--render', default=''); ap.add_argument('--samples', type=int, default=96); ap.add_argument('--res', default='1600x900')
    ap.add_argument('--glb', default=''); ap.add_argument('--cam', default='tub')
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
    bpy.ops.wm.read_factory_settings(use_empty=True); build()
    for o in bpy.context.scene.objects:
        if o.type == 'LIGHT' and hasattr(o, 'visible_camera'): o.visible_camera = False
        if o.type == 'LIGHT' and hasattr(o, 'visible_transmission'): o.visible_transmission = False; o.visible_glossy = o.location.z > 0
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = a.samples; sc.cycles.use_denoising = True; sc.cycles.max_bounces = 8
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'; sc.view_settings.exposure = 0.5
    w, h = map(int, a.res.split('x')); sc.render.resolution_x, sc.render.resolution_y = w, h
    x, y, z, tilt, head, lens = CAMS[a.cam] if a.cam in CAMS else map(float, a.cam.split(','))
    cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera')); sc.collection.objects.link(cam); sc.camera = cam
    cam.location = (x, y, z); cam.rotation_euler = (math.radians(tilt), 0, math.radians(head)); cam.data.lens = lens
    os.makedirs(K(), exist_ok=True); cfgp = K('room.json'); cfg = json.load(open(cfgp)) if os.path.exists(cfgp) else {}
    tints = {}
    for m in bpy.data.materials:
        if m.use_nodes:
            for n in m.node_tree.nodes:
                if n.type == 'MIX_RGB' and n.blend_type == 'MULTIPLY': tints[m.name] = [round(v, 3) for v in n.inputs[2].default_value[:3]]
    cfg.update(name='Spa & Sauna', glb='assets/rooms/spa/spa.glb', spawn=dict(x=2.0, z=LA - 0.7, yaw=0.35), walk=walk_rects(), probe=[0.3, 1.4, 4.0], tints=tints, floor='monastery_stone_floor')
    cfg.setdefault('lights', [{'x': 0.75, 'y': 2.0, 'z': 1.2, 'color': '#ffe2c0', 'power': 10, 'range': 6}, {'x': -4.6, 'y': 1.6, 'z': 3.5, 'color': '#ff9a4a', 'power': 10, 'range': 4},
                              {'x': -10.0, 'y': -0.6, 'z': 3.6, 'color': '#5fd6d0', 'power': 10, 'range': 5}, {'x': -10.0, 'y': 2.4, 'z': 1.6, 'color': '#ffb877', 'power': 8, 'range': 7}])
    cfg.setdefault('exposure', 0.85); cfg.setdefault('version', 1); cfg.setdefault('wallBoost', 1.0); cfg.setdefault('maxFlameLights', 30); cfg.setdefault('flameColor', '#ffb877')
    json.dump(cfg, open(cfgp, 'w'), indent=1)
    if a.render: sc.render.filepath = os.path.abspath(a.render); bpy.ops.render.render(write_still=True)
    if a.glb:
        keep = ('stone', 'planks', 'rough_wood', 'wood_cabinet', 'view', 'ivy')
        for im in bpy.data.images:
            if im.size[0] > 512 and not any(k in im.name for k in keep): im.scale(512, 512)
        bpy.ops.object.select_all(action='DESELECT')
        for o in list(sc.objects):
            if o.type == 'EMPTY' and o.instance_type == 'COLLECTION': o.select_set(True)
        if any(o.select_get() for o in sc.objects): bpy.ops.object.duplicates_make_real()
        bpy.ops.export_scene.gltf(filepath=os.path.abspath(a.glb), export_format='GLB', export_lights=False, export_cameras=False, export_apply=True, export_image_format='JPEG', export_jpeg_quality=82)

if __name__ == '__main__':
    main()
