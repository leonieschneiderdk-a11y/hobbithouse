"""Hobbit-house bathroom / spa, rebuilt as a real 3D room from the 'Bathroom / Spa' image.
Blender axes: the back wall with the arched mountain window is at y = 0, the room runs toward the camera to y = -L.
Left: double vanity with stone vessel sinks and a mirror, the toilet, the round stone walk-in shower in the back corner.
Back: arched window with a cushioned seat, plants and a little chair. Right: copper freestanding tub, a console with lamps.

    python blender/rooms/bathroom.py --render docs/rooms/bathroom.png --samples 96 --res 1600x900 --glb assets/rooms/bathroom/bathroom.glb
"""
import argparse, json, math, os, sys, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
from hero_room import A, pbr, flat, image_mat, obj_from_bm, box_uv, box, cyl, torus, cut, sweep_profile, model, light, candle
from kitchen import lantern, cabinet_run, leaf_cluster, group, kid, tex_mat, mat_alpha, arch_cutter_y, arch_window, stone_arch, bouquet
from hallway import pillow
from dining import rod

W, L = 5.4, 6.2
HW = W / 2
WALL_H, APEX = 2.6, 4.2
rnd = random.Random(71)
CAMS = {'main': (0.25, -L + 0.45, 1.6, 87, 0, 16), 'tub': (-1.2, -5.8, 1.5, 85, -40, 18)}

def K(*p): return A('assets', 'rooms', 'bathroom', *p)

def vault_z(x, inset=0.0):
    t = max(-1.0, min(1.0, x / (HW - inset)))
    return WALL_H + math.sqrt(max(0.0, 1 - t * t)) * (APEX - WALL_H - inset)

def profile(n=40, inset=0.0):
    pts = [(-HW + inset, 0.0)]
    for i in range(n + 1):
        a = math.pi - i / n * math.pi
        pts.append((math.cos(a) * (HW - inset), WALL_H + math.sin(a) * (APEX - WALL_H - inset)))
    pts.append((HW - inset, 0.0)); return pts

def vessel_sink(x, y, z, stone, brass):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=40, radius1=0.15, radius2=0.22, depth=0.15)
    o = obj_from_bm('vessel sink', bm, stone, True); o.location = (x, y, z + 0.075); box_uv(o, 0.6)
    cut(o, [cyl('c', 0.19, 0.16, (x, y, z + 0.16), (0, 0, 0), stone, 40)])
    # gooseneck tap from the counter behind the bowl
    bx = x - 0.3
    cyl('tap', 0.016, 0.38, (bx, y, z + 0.19), (0, 0, 0), brass, 12)
    pts = [(bx + 0.08 - 0.08 * math.cos(t / 6 * math.pi), z + 0.38 + 0.08 * math.sin(t / 6 * math.pi)) for t in range(7)]
    for (x0, z0), (x1, z1) in zip(pts, pts[1:]): rod('tap bend', (x0, y, z0), (x1, y, z1), 0.016, brass, 10)
    cyl('tap spout', 0.014, 0.08, (bx + 0.16, y, z + 0.34), (0, 0, 0), brass, 12)
    for s in (-1, 1): cyl('tap handle', 0.022, 0.05, (bx, y + s * 0.09, z + 0.025), (0, 0, 0), brass, 12)

def copper_tub(cx, cy, copper, inner):
    sx, sy, h = 0.47, 1.0, 0.62
    o = cyl('tub', 1.0, h, (cx, cy, 0.08 + h / 2), (0, 0, 0), copper, 64); o.scale = (sx, sy, 1)
    c = cyl('c', 1.0, h, (cx, cy, 0.18 + h / 2), (0, 0, 0), inner, 64); c.scale = (sx - 0.035, sy - 0.035, 1)
    bpy.context.view_layer.update(); cut(o, [c])
    o.data.materials.append(inner)
    for p in o.data.polygons:
        if (Vector((p.center.x * sx, p.center.y * sy)).length < 0.9 * min(sx, sy) and p.center.z > -h / 2 + 0.05) or (abs(p.normal.z) < 0.5 and math.hypot(p.center.x, p.center.y) < 0.97): p.material_index = 1
    rim = torus('tub rim', 1.0, 0.025, (cx, cy, 0.08 + h), (0, 0, 0), copper); rim.scale = (sx - 0.015, sy - 0.015, 1)
    # raised back end, like a slipper bath
    back = cyl('tub back', 1.0, 0.18, (cx, cy + sy * 0.55, 0.08 + h + 0.06), (0, 0, 0), copper, 48); back.scale = (sx, sy * 0.45, 1)
    c2 = cyl('c', 1.0, 0.3, (cx, cy + sy * 0.55, 0.08 + h + 0.06), (0, 0, 0), inner, 48); c2.scale = (sx - 0.035, sy * 0.45 - 0.035, 1); bpy.context.view_layer.update(); cut(back, [c2])
    box('tub plinth', cx - sx * 0.7, cx + sx * 0.7, cy - sy * 0.8, cy + sy * 0.8, 0.0, 0.08, copper, 1.0, 0.02)
    water = cyl('bath water', 1.0, 0.01, (cx, cy, 0.08 + h * 0.62), (0, 0, 0), flat('bath water', (0.5, 0.42, 0.3), 0.03, transmission=0.6), 48); water.scale = (sx - 0.04, sy - 0.04, 1)

def toilet(x, y, rot, ceramic, wood):
    g = group((x, y, 0), rot)
    for o in (cyl('toilet base', 0.13, 0.24, (0.0, 0.05, 0.12), (0, 0, 0), ceramic, 32),):
        o.scale = (1, 1.35, 1); kid(o, g)
    b = cyl('toilet bowl', 0.19, 0.17, (0.0, -0.02, 0.32), (0, 0, 0), ceramic, 40); b.scale = (1, 1.3, 1); kid(b, g)
    s = torus('toilet seat', 0.17, 0.03, (0.0, -0.03, 0.42), (0, 0, 0), wood); s.scale = (1, 1.3, 1); kid(s, g)
    lid = cyl('toilet lid', 0.19, 0.025, (0.0, 0.24, 0.66), (math.radians(-80), 0, 0), wood, 40); lid.scale = (1, 1.3, 1); kid(lid, g)
    kid(box('toilet tank', -0.2, 0.2, 0.28, 0.46, 0.4, 0.82, ceramic, 1.0, 0.03), g)
    kid(box('toilet tank lid', -0.22, 0.22, 0.26, 0.48, 0.82, 0.86, ceramic, 1.0, 0.02), g)
    kid(cyl('flush', 0.02, 0.03, (0.15, 0.25, 0.75), (math.pi / 2, 0, 0), flat('brass', (0.78, 0.55, 0.26), 0.3, 1.0), 12), g)
    return g

def build():
    floor = pbr('monastery_stone_floor', 'materials', (0.62, 0.5, 0.4), 0.5, 1.2)
    wall = pbr('old_stone_wall', 'materials', (0.86, 0.72, 0.58), 1.0, 1.4)
    stone = pbr('rustic_stone_wall', 'materials', (0.72, 0.62, 0.52), 1.0, 1.4)
    shower_stone = pbr('stacked_stone_wall', 'materials', (0.7, 0.62, 0.54), 0.8, 1.6) if os.path.exists(A('assets', 'materials', 'stacked_stone_wall_diff.jpg')) else pbr('yellow_stone_wall', 'materials', (0.62, 0.56, 0.5), 0.7, 1.6)
    boards = pbr('weathered_brown_planks', 'materials', (0.62, 0.44, 0.28), 0.9)
    rib = pbr('rough_wood', 'materials', (0.36, 0.25, 0.16), 0.9)
    cab = pbr('wood_cabinet_worn_long', 'materials', (0.5, 0.36, 0.24), 0.8)
    top = tex_mat('stone top', A('assets', 'rooms', 'kitchen', 'marble_diff.jpg'), A('assets', 'rooms', 'kitchen', 'marble_rough.jpg'), tint=(0.95, 0.82, 0.68))
    sink_stone = pbr('yellow_stone_wall', 'materials', (0.78, 0.7, 0.6), 0.6, 0.8)
    frame = flat('window frame', (0.12, 0.07, 0.035), 0.55)
    glass = flat('glass', (0.95, 0.97, 0.98), 0.02, transmission=1.0); lglass = flat('lantern glass', (1.0, 0.86, 0.66), 0.08, transmission=0.85)
    iron = flat('iron', (0.03, 0.028, 0.026), 0.55, 0.35); brass = flat('brass', (0.78, 0.55, 0.26), 0.3, 1.0)
    copper = flat('copper', (0.55, 0.27, 0.15), 0.32, 1.0); copper_in = flat('copper inside', (0.66, 0.36, 0.22), 0.25, 1.0)
    ceramic = flat('ceramic', (0.88, 0.86, 0.82), 0.12); seat_wood = flat('seat wood', (0.3, 0.18, 0.1), 0.4)
    linen = flat('cushion linen', (0.66, 0.6, 0.52), 0.9); towel = flat('towel', (0.85, 0.82, 0.76), 0.95)
    rug = mat_alpha('rug', A('assets', 'rooms', 'entrance', 'rug_diff.png'), 0.95)
    ivy = mat_alpha('ivy', A('assets', 'rooms', 'kitchen', 'ivy.png'))
    petals = [flat('petal pink', (0.9, 0.45, 0.55), 0.6), flat('petal white', (0.95, 0.92, 0.88), 0.6), flat('petal peach', (0.95, 0.65, 0.45), 0.6)]
    wax = flat('wax', (0.92, 0.88, 0.78), 0.45)
    # ------------------------------------------------------------ shell: flagstones, stone walls, timber-ribbed plank vault
    box('floor', -HW - 0.3, HW + 0.3, -L - 0.3, 0.3, -0.12, 0.0, floor, 1.8)
    prof = profile()
    bm = bmesh.new(); r0 = [bm.verts.new((x, 0.0, z)) for x, z in prof]; r1 = [bm.verts.new((x, -L, z)) for x, z in prof]
    for i in range(len(prof) - 1): bm.faces.new((r0[i + 1], r0[i], r1[i], r1[i + 1]))
    shell = obj_from_bm('vault', bm, boards, True); shell.data.materials.append(wall)
    for p in shell.data.polygons: p.material_index = 1 if p.center.z < WALL_H - 0.01 else 0
    box_uv(shell, 1.6); sol = shell.modifiers.new('s', 'SOLIDIFY'); sol.thickness = 0.3; sol.offset = 1
    bpy.context.view_layer.objects.active = shell; bpy.ops.object.modifier_apply(modifier='s')
    def end_wall(name, y, thick, sgn):
        bm = bmesh.new(); vs = [bm.verts.new((x, y, z)) for x, z in prof]; bm.faces.new(vs); w = obj_from_bm(name, bm, wall)
        s = w.modifiers.new('s', 'SOLIDIFY'); s.thickness = thick; s.offset = 1.0 if sgn > 0 else -1.0
        bpy.context.view_layer.objects.active = w; bpy.ops.object.modifier_apply(modifier='s'); return w
    back = end_wall('back wall', 0.0, 0.45, 1); front = end_wall('front wall', -L, 0.4, -1)
    rp = profile(40, 0.02)[1:-1]
    for k in range(6):
        y = -0.45 - k * 1.06; sweep_profile('rib', rp, y, 0.26, 0.28, rib)
    box('ridge', -0.13, 0.13, -L, 0.0, APEX - 0.28, APEX - 0.02, rib, 1.2)
    for s in (-1, 1): box('purlin', s * 1.45 - 0.1, s * 1.45 + 0.1, -L, 0, vault_z(s * 1.45, 0.2) - 0.22, vault_z(s * 1.45, 0.2), rib, 1.2)
    bulb = flat('bulb', (1, 0.8, 0.5), 1, emit=(1.0, 0.75, 0.45), strength=15)
    for k in range(5):
        y = -1.0 - k * 1.06
        for x in (-0.9, 0.9):
            z = vault_z(x, 0.05) - 0.02; bpy.ops.mesh.primitive_uv_sphere_add(radius=0.03, location=(x, y, z)); bpy.context.active_object.data.materials.append(bulb); light((x, y, z - 0.08), 18, radius=0.04)
    # ------------------------------------------------------------ back wall: big arched window onto the mountains, a cushioned seat, plants
    WX, WW, WRH, WZ = 0.85, 2.05, 1.75, 0.95
    cut(back, arch_cutter_y(WX, WW, WRH, WZ, -0.2, 0.8)); box_uv(back, 1.6)
    g = group((WX, 0.22, WZ)); arch_window(g, WW, WRH, 4, 3, frame, glass, 0, ring=False)
    g2 = group((WX, 0.0, WZ)); stone_arch(g2, WW, WRH, 0.2, stone, 0.22)
    a = light((WX, 1.4, WZ + 1.0), 700, (0.85, 0.92, 1.0), kind='AREA'); a.data.size = WW; a.rotation_euler = (math.radians(90), 0, 0)
    box('window seat', WX - 1.1, WX + 1.1, -0.65, -0.0, 0.0, 0.48, stone, 1.2, 0.02)
    pillow(WX, -0.33, 0.56, 2.1, 0.62, 0.14, linen)
    for dx in (-0.8, -0.28, 0.75): pillow(WX + dx, -0.14, 0.8, 0.46, 0.14, 0.4, linen).rotation_euler = (math.radians(12), 0, 0)
    model('ArmChair_01', (WX - 0.75, -1.25, 0), math.radians(200), width=0.7)
    model('potted_plant_01', (WX + 1.4, -0.45, 0), 0.4, height=1.75)
    model('potted_plant_04', (WX + 0.7, -0.12, WZ), 0, height=0.3)
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1); bmesh.ops.scale(bm, vec=(34, 14.5, 1), verts=bm.verts)
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 4, 'X')); bmesh.ops.translate(bm, vec=(0.7, 14, 2.0), verts=bm.verts)
    view = obj_from_bm('valley view', bm, image_mat('view', A('assets', 'rooms', 'kitchen', 'view.jpg'), 1.2)); uvl = view.data.uv_layers.new()
    for i, l in enumerate(uvl.data): co = view.data.vertices[view.data.loops[i].vertex_index].co; l.uv = ((co.x - 0.7) / 34 + 0.3, (co.z - 2.0) / 14.5 + 0.5)
    # ------------------------------------------------------------ the round stone walk-in shower in the back-left corner
    SX, SY, SR = -HW + 1.15, -1.2, 1.0
    sh = cyl('shower wall', SR + 0.14, 2.35, (SX, SY, 1.175), (0, 0, 0), shower_stone, 64)
    cut(sh, [cyl('c', SR, 2.6, (SX, SY, 1.2), (0, 0, 0), shower_stone, 64), box('c', SX - 2, SX + 2, SY - 2, SY - 0.25, -1, 4, shower_stone)])
    box_uv(sh, 1.0)
    box_uv(cyl('shower floor', SR + 0.1, 0.1, (SX, SY, 0.05), (0, 0, 0), floor, 64), 0.8)
    bm = bmesh.new(); n = 48
    for i in range(n):
        a0, a1 = math.pi + i / n * math.pi * 0.62, math.pi + (i + 1) / n * math.pi * 0.62     # front-left arc of glass, open toward the room on the right
        v = [bm.verts.new((SX + math.cos(a) * SR, SY + math.sin(a) * SR, z)) for a, z in ((a0, 0.1), (a1, 0.1), (a1, 2.2), (a0, 2.2))]
        bm.faces.new(v)
    obj_from_bm('shower glass', bm, glass, True)
    for a_ in (math.radians(-160), math.radians(-90), math.radians(-60)):
        cyl('shower post', 0.015, 2.1, (SX + math.cos(a_) * SR, SY + math.sin(a_) * SR, 1.15), (0, 0, 0), brass, 10)
    torus('shower rail', SR, 0.012, (SX, SY, 2.2), (0, 0, 0), brass)
    cyl('shower pipe', 0.018, 2.0, (SX - 0.35, SY + 0.85, 1.1), (0, 0, 0), brass, 12)
    rod('shower arm', (SX - 0.35, SY + 0.85, 2.1), (SX - 0.1, SY + 0.35, 2.15), 0.016, brass)
    cyl('shower head', 0.14, 0.03, (SX - 0.1, SY + 0.35, 2.13), (0, 0, 0), brass, 32)
    for s in (-1, 1): cyl('shower valve', 0.04, 0.03, (SX - 0.35 + s * 0.12, SY + 0.86, 1.15), (math.pi / 2, 0, 0), brass, 16)
    light((SX, SY, 2.2), 40, radius=0.2)
    # ------------------------------------------------------------ left wall: the toilet, then the double vanity with vessel sinks, mirror and sconces
    toilet(-HW + 0.48, -2.85, math.pi / 2, ceramic, seat_wood)
    box('toilet roll arm', -HW, -HW + 0.12, -3.3, -3.28, 0.68, 0.7, brass, 1.0); cyl('toilet roll', 0.055, 0.11, (-HW + 0.1, -3.29, 0.62), (math.pi / 2, 0, 0), towel, 16)
    model('wicker_basket_01', (-HW + 0.3, -2.35, 0), 0, width=0.28)
    VY0, VY1, VH = -5.85, -3.45, 0.86
    cabinet_run(-HW, -HW + 0.62, VY0, VY1, '+x', cab, top, brass, 0.53, VH)
    for y in (-5.25, -4.05):
        vessel_sink(-HW + 0.32, y, VH, sink_stone, brass)
    model('ornate_mirror_01', (-HW + 0.03, -4.65, 1.25), math.pi / 2, width=1.2)
    for y in (-5.7, -3.6):
        box('sconce arm', -HW, -HW + 0.22, y - 0.015, y + 0.015, 1.92, 1.95, iron, 1.0); lantern(-HW + 0.22, y, 1.6, 0.85, 1.93, iron, lglass, 40)
    for y, h in ((-5.7, 0.12), (-4.65, 0.16), (-3.6, 0.1)): cyl('pillar candle', 0.035, h, (-HW + 0.45, y, VH + h / 2), (0, 0, 0), wax, 20); candle((-HW + 0.45, y, VH + h - 0.005), 0.01, 8)
    model('ceramic_vase_02', (-HW + 0.3, -4.65, VH), 0, height=0.2); bouquet(-HW + 0.3, -4.65, VH + 0.18, petals, ivy, 14, 0.13)
    model('jug_01', (-HW + 0.38, -3.6, VH), 0, height=0.18) if False else None
    for k in range(3): box('folded towel', -HW + 0.12, -HW + 0.52, -5.75 + k * 0.02, -5.35 + k * 0.02, 0.2 + k * 0.09, 0.28 + k * 0.09, towel, 1.0, 0.02)
    model('potted_plant_02', (-HW + 0.4, -L + 0.3, 0), 0.5, height=0.75)
    # ------------------------------------------------------------ the middle: a big round rug; right: the copper tub with a towel, a console with lamps
    bm = bmesh.new(); bmesh.ops.create_circle(bm, cap_ends=True, segments=96, radius=1.45); uv = bm.loops.layers.uv.new()
    for f in bm.faces:
        for l in f.loops: l[uv].uv = (l.vert.co.x / 2.9 + 0.5, l.vert.co.y / 2.9 + 0.5)
    obj_from_bm('rug', bm, rug).location = (-0.15, -3.9, 0.006)
    TX, TY = HW - 0.78, -3.75
    copper_tub(TX, TY, copper, copper_in)
    box('towel', TX - 0.56, TX - 0.47, TY - 0.45, TY + 0.1, 0.25, 0.78, towel, 1.0, 0.02); box('towel fold', TX - 0.56, TX - 0.38, TY - 0.45, TY + 0.1, 0.74, 0.8, towel, 1.0, 0.02)
    cyl('tub tap', 0.02, 1.0, (TX, TY + 1.15, 0.5), (0, 0, 0), brass, 12); rod('tub spout', (TX, TY + 1.15, 1.0), (TX, TY + 0.85, 0.95), 0.016, brass)
    model('wooden_stool_02', (TX - 0.85, TY + 0.55, 0), 0, height=0.42); candle((TX - 0.85, TY + 0.55, 0.42), 0.14, 8)
    model('potted_plant_01', (HW - 0.45, -5.45, 0), 2.0, height=1.45)
    CX = HW - 0.25
    box('console', CX - 0.25, CX + 0.15, -2.15, -0.95, 0.75, 0.8, cab, 1.0, 0.01)
    for y in (-2.1, -1.0):
        for dx in (-0.2, 0.1): box('console leg', CX + dx - 0.025, CX + dx + 0.025, y - 0.025, y + 0.025, 0.0, 0.75, cab, 1.0)
    for y in (-1.95, -1.15):
        cyl('lamp base', 0.08, 0.3, (CX - 0.05, y, 0.95), (0, 0, 0), brass, 20)
        bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=False, segments=24, radius1=0.17, radius2=0.1, depth=0.2)
        sh_ = obj_from_bm('lamp shade', bm, flat('lamp shade', (0.95, 0.82, 0.6), 0.8, emit=(1.0, 0.75, 0.45), strength=2.5), True); sh_.location = (CX - 0.05, y, 1.2)
        light((CX - 0.05, y, 1.2), 45, radius=0.12)
    model('wicker_basket_02', (CX - 0.05, -1.65, 0.0), 0, width=0.36)
    for k in range(3): box('rolled towel', CX - 0.2, CX + 0.1, -1.85 + k * 0.17, -1.72 + k * 0.17, 0.8, 0.9, towel, 1.0, 0.04)
    for y in (-5.5,):
        box('sconce arm', HW - 0.22, HW, y - 0.015, y + 0.015, 1.92, 1.95, iron, 1.0); lantern(HW - 0.22, y, 1.6, 0.85, 1.93, iron, lglass, 40)
    for s in (-1, 1):
        for k in range(4): leaf_cluster(ivy, s * (HW - 0.2), -0.9 - k * 1.45, WALL_H + 0.1, 10, 0.25, 0.7)
    # ------------------------------------------------------------ front wall: the door
    cut(front, arch_cutter_y(0.4, 1.2, 1.6, 0.0, -L - 1, -L + 1)); box_uv(front, 1.6)
    g = group((0.4, -L, 0.0)); stone_arch(g, 1.2, 1.6, 0.5, stone, 0.2)
    box('door', -0.2, 1.0, -L - 0.25, -L - 0.18, 0.0, 2.2, cab, 0.8)
    w = bpy.data.worlds.new('w'); bpy.context.scene.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0.4, 0.45, 0.5, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.08
    for y in (-1.8, -4.5):
        f = light((0.2, y, WALL_H), 140, (1.0, 0.72, 0.45), kind='AREA'); f.data.size = 2.5; f.rotation_euler = (math.pi, 0, 0)

def walk_rects():
    R = [(-HW + 0.75, HW - 1.45, -L + 0.4, -2.3),     # the middle, between the vanity and the tub
         (HW - 1.45, HW - 0.4, -L + 0.4, -4.9),        # in front of the tub
         (-0.2, HW - 0.6, -2.3, -1.6),                  # by the window seat
         (-HW + 0.75, -0.2, -2.3, -2.05)]
    return [[x0, x1, -y1, -y0] for x0, x1, y0, y1 in R]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--render', default=''); ap.add_argument('--samples', type=int, default=96); ap.add_argument('--res', default='1280x720')
    ap.add_argument('--glb', default=''); ap.add_argument('--cam', default='main')
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
    bpy.ops.wm.read_factory_settings(use_empty=True); build()
    for o in bpy.context.scene.objects:
        if o.type == 'LIGHT' and hasattr(o, 'visible_camera'): o.visible_camera = False
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = a.samples; sc.cycles.use_denoising = True; sc.cycles.max_bounces = 8
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'; sc.view_settings.exposure = 0.6
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
    cfg.update(name='Bathroom & Spa', glb='assets/rooms/bathroom/bathroom.glb', spawn=dict(x=0.25, z=L - 0.6, yaw=0), walk=walk_rects(), lights=[], probe=[0.0, 1.4, 3.4], tints=tints, floor='monastery_stone_floor')
    cfg.setdefault('exposure', 0.8); cfg.setdefault('version', 1); cfg.setdefault('wallBoost', 1.0); cfg.setdefault('maxFlameLights', 24); cfg.setdefault('flameColor', '#ffb877')
    json.dump(cfg, open(cfgp, 'w'), indent=1)
    if a.render: sc.render.filepath = os.path.abspath(a.render); bpy.ops.render.render(write_still=True)
    if a.glb:
        keep = ('stone', 'plaster', 'planks', 'rough_wood', 'wood_cabinet', 'view', 'ivy', 'rug', 'marble')
        for im in bpy.data.images:
            if im.size[0] > 512 and not any(k in im.name for k in keep): im.scale(512, 512)
        bpy.ops.object.select_all(action='DESELECT')
        for o in list(sc.objects):
            if o.type == 'EMPTY' and o.instance_type == 'COLLECTION': o.select_set(True)
        if any(o.select_get() for o in sc.objects): bpy.ops.object.duplicates_make_real()
        bpy.ops.export_scene.gltf(filepath=os.path.abspath(a.glb), export_format='GLB', export_lights=False, export_cameras=False, export_apply=True, export_image_format='JPEG', export_jpeg_quality=82)

if __name__ == '__main__':
    main()
