"""Hobbit-house hallway, rebuilt as a real 3D room from the 'Hallway' image, made longer, with an arched oak door at the far
end instead of the fireplace. Blender axes: the door is in the end wall at y = 0, the hallway runs toward the camera to
y = -L. The left wall has big round windows with a cushioned window seat and arched bookcases; the right wall has
console tables, pictures, lanterns and plants. A timber-ribbed wooden vault, glossy stone tiles and runner rugs.

    python blender/rooms/hallway.py --render docs/rooms/hallway.png --samples 96 --res 1600x900 --glb assets/rooms/hallway/hallway.glb
"""
import argparse, json, math, os, sys, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
import numpy as np
from mathutils import Vector, Matrix
from hero_room import A, pbr, flat, image_mat, obj_from_bm, box_uv, box, cyl, torus, cut, sweep_profile, model, light, candle
from kitchen import lantern, leaf_cluster, group, kid, tex_mat, mat_alpha, arch_cutter_y, stone_arch
from dining import rod

W, L = 3.8, 19.0
HW = W / 2
WALL_H, APEX = 2.35, 3.75
rnd = random.Random(61)
CAMS = {'main': (0.15, -L + 0.5, 1.62, 87, 0, 17), 'door': (0.0, -6.0, 1.62, 88, 0, 20), 'back': (0.0, -1.0, 1.62, 87, 180, 17)}
ARCHES = [-1.6 - k * 2.55 for k in range(7)]       # stone arches across the hallway
BAYS = [(ARCHES[k] + ARCHES[k + 1]) / 2 for k in range(6)]   # -2.875 .. -15.625 (bay centres, far to near)
WINDOWS = (BAYS[5], BAYS[2])                       # round windows in the left wall (centre y)

def K(*p): return A('assets', 'rooms', 'hallway', *p)

def vault_z(x, inset=0.0):
    t = max(-1.0, min(1.0, x / (HW - inset)))
    return WALL_H + math.sqrt(max(0.0, 1 - t * t)) * (APEX - WALL_H - inset)

def profile(n=40, inset=0.0):
    pts = [(-HW + inset, 0.0)]
    for i in range(n + 1):
        a = math.pi - i / n * math.pi
        pts.append((math.cos(a) * (HW - inset), WALL_H + math.sin(a) * (APEX - WALL_H - inset)))
    pts.append((HW - inset, 0.0)); return pts

# ---------------------------------------------------------------- books: many little boxes in one mesh
def blocks(name, items, mats):
    """items: (cx, cy, cz, sx, sy, sz, mat_idx) axis-aligned boxes, built as one mesh."""
    cv = np.array([(x, y, z) for x in (-.5, .5) for y in (-.5, .5) for z in (-.5, .5)], np.float32)
    cf = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    C = np.array([it[:3] for it in items], np.float32); S = np.array([it[3:6] for it in items], np.float32)
    verts = (C[:, None, :] + cv[None] * S[:, None, :]).reshape(-1, 3)
    faces = [tuple(i * 8 + v for v in f) for i in range(len(items)) for f in cf]
    me = bpy.data.meshes.new(name); me.from_pydata(verts.tolist(), [], faces); me.update()
    for m in mats: me.materials.append(m)
    me.polygons.foreach_set('material_index', np.repeat(np.array([it[6] for it in items], np.int32), 6))
    o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o); return o

BOOKS = []
def bookcase(y0, y1, wood, trim, depth=0.34, z0=0.0, z1=2.25, arch=True, nm=8):
    """Built-in arched bookcase against the left wall, filled with books and a few ornaments."""
    x0 = -HW; x1 = -HW + depth; yc = (y0 + y1) / 2; w = y1 - y0
    box('bookcase back', x0, x0 + 0.03, y0, y1, z0, z1, wood, 1.0)
    for y in (y0, y1): box('bookcase side', x0, x1, y - 0.03, y + 0.03, z0, z1, wood, 1.0)
    box('bookcase plinth', x0, x1 + 0.02, y0, y1, z0, z0 + 0.1, wood, 1.0)
    zs = [z0 + 0.1 + k * 0.36 for k in range(6) if z0 + 0.1 + k * 0.36 < z1 - 0.2]
    for z in zs + [z1 - 0.05]: box('book shelf', x0 + 0.03, x1, y0 + 0.03, y1 - 0.03, z - 0.025, z, wood, 1.0, 0.003)
    if arch:
        g = group((x1 + 0.02, yc, z1 - w / 2), math.pi / 2); stone_arch(g, w, 0.0, 0.12, trim, 0.16)
        for s in (-1, 1): box('bookcase pilaster', x1 - 0.02, x1 + 0.08, yc + s * (w / 2 + 0.08) - 0.08, yc + s * (w / 2 + 0.08) + 0.08, 0.0, z1 - w / 2, trim, 1.0)
    for k, z in enumerate(zs):
        y = y0 + 0.05
        while y < y1 - 0.06:
            if rnd.random() < 0.08:            # an ornament or a gap
                if rnd.random() < 0.5: candle((x0 + depth * 0.55, y + 0.05, z), 0.12, 5)
                else: model(rnd.choice(('brass_vase_02', 'ceramic_vase_04', 'ceramic_vase_03')), (x0 + depth * 0.55, y + 0.06, z), rnd.uniform(0, 6), height=rnd.uniform(0.14, 0.24))
                y += 0.14; continue
            t = rnd.uniform(0.025, 0.06); h = rnd.uniform(0.18, 0.3); d = rnd.uniform(0.16, 0.24)
            if y + t > y1 - 0.05: break
            BOOKS.append((x0 + 0.04 + d / 2, y + t / 2, z + h / 2, d, t, h, rnd.randrange(nm))); y += t + rnd.uniform(0.0, 0.006)
            if rnd.random() < 0.04:            # a few books lying flat in a stack
                for j in range(rnd.randint(2, 4)): BOOKS.append((x0 + 0.15, y + 0.13, z + 0.02 + j * 0.04, 0.2, 0.22, 0.038, rnd.randrange(nm)))
                y += 0.27

def round_window(shell, yc, zc, r, frame, glass, stone, view_mat):
    cut(shell, [cyl('c', r, 1.4, (-HW, yc, zc), (0, math.pi / 2, 0), frame, 48)])
    g = group((-HW - 0.05, yc, zc), math.pi / 2)
    t = torus('round window frame', r - 0.04, 0.05, (0, 0, 0), (math.pi / 2, 0, 0), frame); kid(t, g)
    t = torus('round window surround', r + 0.12, 0.13, (0, 0.1, 0), (math.pi / 2, 0, 0), stone); t.scale = (1, 1, 2.2); kid(t, g)
    kid(box('mullion', -0.025, 0.025, -0.03, 0.03, -r, r, frame, 1.0), g)
    for z in (-r * 0.35, r * 0.25): hz = math.sqrt(max(0, (r - 0.04) ** 2 - z * z)); kid(box('transom', -hz, hz, -0.03, 0.03, z - 0.02, z + 0.02, frame, 1.0), g)
    for s in (-1, 1): kid(box('mullion', s * r * 0.5 - 0.02, s * r * 0.5 + 0.02, -0.03, 0.03, -math.sqrt(r * r - (r * 0.5) ** 2) + 0.04, math.sqrt(r * r - (r * 0.5) ** 2) - 0.04, frame, 1.0), g)
    gl = cyl('glass', r - 0.04, 0.01, (0, 0, 0), (math.pi / 2, 0, 0), glass, 48); kid(gl, g)
    a = light((-HW - 1.2, yc, zc), 160, (0.85, 0.95, 0.85), kind='AREA'); a.data.size = r * 2; a.rotation_euler = (0, math.radians(-90), 0)

def pillow(x, y, z, sx, sy, sz, mat, rx=0.0, rz=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z)); o = bpy.context.active_object; o.scale = (sx, sy, sz); o.rotation_euler = (rx, 0, rz)
    b = o.modifiers.new('bevel', 'BEVEL'); b.width = min(sx, sy, sz) * 0.45; b.segments = 4; o.data.materials.append(mat)
    s = o.modifiers.new('smooth', 'SUBSURF'); s.levels = 1; s.render_levels = 2
    for p in o.data.polygons: p.use_smooth = True
    return o

def build():
    floor = pbr('stonetile', os.path.join('rooms', 'entrance'), (0.74, 0.68, 0.6), 0.9, 0.5)
    wall = pbr('plastered_stone_wall', 'materials', (1.15, 1.02, 0.86), 1.0, 1.3)
    stone = pbr('rustic_stone_wall', 'materials', (1.0, 0.9, 0.76), 1.0, 1.3)
    boards = pbr('weathered_brown_planks', 'materials', (0.62, 0.44, 0.28), 0.9)
    rib = pbr('rough_wood', 'materials', (0.36, 0.25, 0.16), 0.9)
    wood = pbr('wood_cabinet_worn_long', 'materials', (0.6, 0.44, 0.3), 0.8)
    trim = pbr('dark_wooden_planks', 'materials', (0.5, 0.34, 0.22), 0.9)
    door_wood = pbr('dark_wooden_planks', 'materials', (0.42, 0.28, 0.17), 0.8)
    frame = flat('window frame', (0.12, 0.07, 0.035), 0.55)
    glass = flat('glass', (0.95, 0.97, 0.98), 0.02, transmission=1.0); lglass = flat('lantern glass', (1.0, 0.86, 0.66), 0.08, transmission=0.85)
    iron = flat('iron', (0.03, 0.028, 0.026), 0.55, 0.35); brass = flat('brass', (0.78, 0.55, 0.26), 0.3, 1.0)
    linen = flat('cushion linen', (0.62, 0.55, 0.45), 0.9); linen2 = flat('cushion oat', (0.5, 0.42, 0.32), 0.9); throw = flat('throw', (0.42, 0.36, 0.3), 0.95)
    runner = tex_mat('runner', K('rug_diff.jpg'), rough=0.95)
    ivy = mat_alpha('ivy', A('assets', 'rooms', 'kitchen', 'ivy.png'))
    bookm = [flat('book ' + n, c, 0.6) for n, c in (('red', (0.3, 0.05, 0.03)), ('brown', (0.22, 0.12, 0.06)), ('green', (0.08, 0.14, 0.07)), ('tan', (0.45, 0.32, 0.18)),
                                                  ('navy', (0.05, 0.07, 0.14)), ('maroon', (0.2, 0.04, 0.05)), ('cream', (0.55, 0.48, 0.36)), ('black', (0.03, 0.03, 0.03)))]
    # ------------------------------------------------------------ shell: glossy stone tiles, stone walls, timber-ribbed plank vault
    box('floor', -HW - 0.3, HW + 0.3, -L - 0.3, 0.3, -0.12, 0.0, floor, 1.6)
    prof = profile()
    bm = bmesh.new(); r0 = [bm.verts.new((x, 0.0, z)) for x, z in prof]; r1 = [bm.verts.new((x, -L, z)) for x, z in prof]
    for i in range(len(prof) - 1): bm.faces.new((r0[i + 1], r0[i], r1[i], r1[i + 1]))
    shell = obj_from_bm('vault', bm, boards, True); shell.data.materials.append(wall)
    for p in shell.data.polygons: p.material_index = 1 if p.center.z < WALL_H - 0.01 else 0
    box_uv(shell, 1.8); sol = shell.modifiers.new('s', 'SOLIDIFY'); sol.thickness = 0.3; sol.offset = 1
    bpy.context.view_layer.objects.active = shell; bpy.ops.object.modifier_apply(modifier='s')
    def end_wall(name, y, thick, sgn):
        bm = bmesh.new(); vs = [bm.verts.new((x, y, z)) for x, z in prof]; bm.faces.new(vs); w = obj_from_bm(name, bm, wall)
        s = w.modifiers.new('s', 'SOLIDIFY'); s.thickness = thick; s.offset = 1.0 if sgn > 0 else -1.0
        bpy.context.view_layer.objects.active = w; bpy.ops.object.modifier_apply(modifier='s'); return w
    door_wall = end_wall('door wall', 0.0, 0.4, 1); end_wall('near wall', -L, 0.4, -1)
    # stone arches every few metres: stone piers up the walls and a timber arch over, plus thinner ribs between
    rp = profile(40, 0.02)[1:-1]
    for y in ARCHES:
        sweep_profile('arch rib', [(prof[1][0] + 0.2, 0.0)] + profile(40, 0.2)[1:-1] + [(prof[-2][0] - 0.2, 0.0)], y, 0.34, 0.32, rib)
        for s in (-1, 1): box('stone pier', s * HW - (0.24 if s > 0 else -0.24) - 0.16, s * HW - (0.24 if s > 0 else -0.24) + 0.16, y - 0.24, y + 0.24, 0.0, WALL_H + 0.25, stone, 1.0, 0.02)
    for k in range(int(L / 0.85)):
        y = -0.4 - k * 0.85
        if min(abs(y - a) for a in ARCHES) > 0.4: sweep_profile('rib', rp, y, 0.14, 0.16, rib)
    box('ridge', -0.1, 0.1, -L, 0.0, APEX - 0.2, APEX - 0.02, rib, 1.2)
    for s in (-1, 1): box('purlin', s * 1.05 - 0.07, s * 1.05 + 0.07, -L, 0, vault_z(s * 1.05, 0.15) - 0.16, vault_z(s * 1.05, 0.15), rib, 1.2)
    # ------------------------------------------------------------ the far end: an arched oak door with lanterns and plants either side
    DW, DRH = 1.3, 1.6
    cut(door_wall, arch_cutter_y(0.0, DW, DRH, 0.0, -1, 1)); box_uv(door_wall, 2.0)
    g = group((0, 0.0, 0.0)); stone_arch(g, DW, DRH, 0.6, stone, 0.24)
    hinge = group((-DW / 2 + 0.02, 0.1, 0.0))
    kid(box('door', 0, DW - 0.04, -0.05, 0.05, 0.0, DRH, door_wood, 0.8), hinge)
    dt = cyl('door top', DW / 2 - 0.02, 0.1, (DW / 2 - 0.02, 0, DRH), (math.pi / 2, 0, 0), door_wood, 40); cut(dt, [box('c', -1, 3, -1, 1, DRH - 2, DRH, door_wood)]); kid(dt, hinge)
    for k in range(5):
        z = 0.25 + k * 0.38; kid(box('door strap', 0.05, DW - 0.25, -0.07, -0.05, z, z + 0.05, iron, 1.0), hinge)
    for k in range(1, 6): x = k * (DW - 0.04) / 6; kid(box('door plank line', x - 0.004, x + 0.004, -0.055, -0.05, 0.05, DRH + 0.4 * math.sin(math.acos(min(1, abs(x - DW / 2) / (DW / 2))) ), trim, 1.0), hinge)
    kn = cyl('door ring', 0.012, 0.03, (DW - 0.22, -0.08, 1.0), (math.pi / 2, 0, 0), brass, 12); kid(kn, hinge)
    kid(torus('door ring', 0.06, 0.009, (DW - 0.22, -0.09, 0.95), (math.pi / 2, 0, 0), brass), hinge)
    box('threshold', -DW / 2 - 0.1, DW / 2 + 0.1, -0.25, 0.25, 0.0, 0.025, stone, 1.0)
    box('behind door', -1, 1, 0.45, 0.6, 0.0, 3.0, wall, 2.0)
    for s in (-1, 1):
        x = s * (DW / 2 + 0.45)
        box('sconce arm', x - 0.015, x + 0.015, -0.25, 0.0, 1.95, 1.98, iron, 1.0); lantern(x, -0.25, 1.6, 1.0, 1.96, iron, lglass, 60)
        model('potted_plant_01', (s * 1.4, -0.45, 0), s, height=1.25)
    model('fancy_picture_frame_01', (0, -0.04, 2.55), 0, width=0.75)
    # two armchairs and a little table near the door, like the image
    model('ArmChair_01', (-0.95, -2.75, 0), math.pi / 2 - 0.55, width=0.78); model('ArmChair_01', (0.95, -2.75, 0), -math.pi / 2 + 0.55, width=0.78)
    cyl('chair table', 0.26, 0.04, (0, -2.35, 0.55), (0, 0, 0), wood, 32); cyl('chair table post', 0.04, 0.53, (0, -2.35, 0.27), (0, 0, 0), wood, 12)
    candle((0.05, -2.35, 0.57), 0.14, 10); model('ceramic_vase_04', (-0.1, -2.3, 0.57), 0, height=0.2)
    model('WoodenTable_02', (0, -2.9, 0), 0, height=0.5) if False else None
    # ------------------------------------------------------------ left wall: round windows with a window seat, arched bookcases
    view = image_mat('view', A('assets', 'rooms', 'dining', 'view.jpg'), 0.6)
    for i, wy in enumerate(WINDOWS):
        round_window(shell, wy, 1.6, 0.95, frame, glass, stone, view)
        # the cushioned window seat with drawers of baskets underneath, pillows and a throw
        sy0, sy1 = wy - 0.95, wy + 0.95
        box('seat base', -HW, -HW + 0.7, sy0, sy1, 0.0, 0.42, wood, 1.0, 0.01)
        for k in range(4):
            yy = sy0 + 0.12 + k * (sy1 - sy0 - 0.24) / 4; box('seat cubby', -HW + 0.66, -HW + 0.7, yy + 0.04, yy + (sy1 - sy0 - 0.24) / 4 - 0.04, 0.06, 0.34, trim, 1.0)
            model('wicker_basket_01', (-HW + 0.45, yy + (sy1 - sy0 - 0.24) / 8, 0.06), math.pi / 2, width=0.4)
        pillow(-HW + 0.36, wy, 0.5, 0.66, sy1 - sy0 - 0.06, 0.16, linen)
        for k, (dy, m) in enumerate(((-0.62, linen2), (0.0, linen), (0.62, linen2))):
            pillow(-HW + 0.14, wy + dy, 0.82, 0.14, 0.52, 0.5, m, 0, 0).rotation_euler = (0, math.radians(-14), 0)
        pillow(-HW + 0.3, wy - 0.3, 0.72, 0.12, 0.38, 0.36, linen2).rotation_euler = (0, math.radians(-28), 0.2)
        pillow(-HW + 0.62, sy1 - 0.25, 0.42, 0.06, 0.55, 0.5, throw).rotation_euler = (0, 0.2, 0)
        # a lantern on a little stand at the window end, plants with trailing ivy either side
        model('wooden_lantern_01', (-HW + 0.3, sy1 - 0.2, 0.58), 0.3, height=0.45); candle((-HW + 0.3, sy1 - 0.2, 0.6), 0.14, 18)
        model('potted_plant_02', (-HW + 0.4, sy0 - 0.3, 0.0), 0.4, height=0.5) if False else None
        leaf_cluster(ivy, -HW + 0.3, sy0 + 0.1, 0.9, 16, 0.25, 0.4)
        for k in range(8): leaf_cluster(ivy, -HW + 0.25, wy - 0.85 + k * 0.24, 2.3 + 0.25 * math.sin(k / 9 * math.pi), 6, 0.16, 0.8 if k in (0, 9) else 0.2)
        # outside: the garden
        bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1); bmesh.ops.scale(bm, vec=(30, 20, 1), verts=bm.verts)
        bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 4, 'X') @ Matrix.Rotation(0, 4, 'Z'))
        v = obj_from_bm('garden view', bm, view); v.rotation_euler = (0, 0, math.pi / 2); v.location = (-HW - 9, wy, 3.0)
        uvl = v.data.uv_layers.new()
        for j, l in enumerate(uvl.data): co = v.data.vertices[v.data.loops[j].vertex_index].co; l.uv = (co.x / 30 + 0.5 + 0.2 * i, co.z / 20 + 0.5)
    for yc in (BAYS[4], BAYS[3], BAYS[1]): bookcase(yc - 0.72, yc + 0.72, wood, trim)
    # plants and lanterns along the left wall between the bookcases
    model('potted_plant_01', (-HW + 0.45, -L + 0.8, 0), 1.0, height=1.2)
    for y in ARCHES[1::2]:
        box('sconce arm', -HW + 0.4, -HW + 0.62, y - 0.015, y + 0.015, 2.05, 2.08, iron, 1.0); lantern(-HW + 0.62, y, 1.7, 0.9, 2.06, iron, lglass, 28)
    # ------------------------------------------------------------ right wall: console tables with plants, pictures, lanterns, potted plants
    RX = HW - 0.3
    for k, y in enumerate((BAYS[5], BAYS[4], BAYS[3], BAYS[2], BAYS[1])):
        box('console top', RX - 0.38, RX + 0.02, y - 0.6, y + 0.6, 0.8, 0.85, wood, 1.0, 0.01)
        box('console apron', RX - 0.36, RX, y - 0.56, y + 0.56, 0.7, 0.8, wood, 1.0)
        for dy in (-0.52, 0.52):
            for dx in (-0.32, -0.04): box('console leg', RX + dx - 0.03, RX + dx + 0.03, y + dy - 0.03, y + dy + 0.03, 0.0, 0.7, wood, 1.0)
        box('console shelf', RX - 0.36, RX, y - 0.55, y + 0.55, 0.18, 0.22, wood, 1.0)
        model('potted_plant_02', (RX - 0.18, y - 0.25, 0.85), k, height=0.45); leaf_cluster(ivy, RX - 0.18, y - 0.25, 1.15, 12, 0.2, 0.5)
        candle((RX - 0.18, y + 0.3, 0.85), 0.16, 8); model('brass_candleholders', (RX - 0.18, y + 0.1, 0.85), math.pi / 2, width=0.25) if k % 2 else model('ceramic_vase_04', (RX - 0.2, y + 0.12, 0.85), 0, height=0.25)
        model('wicker_basket_02', (RX - 0.18, y, 0.22), math.pi / 2, width=0.4)
        model('hanging_picture_frame_02' if k % 2 else 'fancy_picture_frame_01', (HW - 0.06, y, 1.65), -math.pi / 2, width=0.7)
        model('potted_plant_04', (RX - 0.2, y + 0.82, 0), rnd.uniform(0, 6), height=0.5) if k % 2 else None
    for y in ARCHES[2::2]:
        box('sconce arm', HW - 0.62, HW - 0.4, y - 0.015, y + 0.015, 2.05, 2.08, iron, 1.0); lantern(HW - 0.62, y, 1.7, 0.9, 2.06, iron, lglass, 28)
    for y in BAYS[1:]: model('hanging_picture_frame_01', (HW - 0.06, y + 0.85, 1.75), -math.pi / 2, width=0.4)
    for y in ARCHES[::2]:
        for s in (-1, 1): leaf_cluster(ivy, s * (HW - 0.3), y, 1.6 + rnd.uniform(0, 0.8), 10, 0.2, 1.0)
    # ------------------------------------------------------------ runner rugs and pendant lanterns down the middle
    for k in range(5):
        yc = -L + 2.0 + k * 3.5
        bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5); uvl = bm.loops.layers.uv.new()
        for f in bm.faces:
            for l in f.loops: l[uvl].uv = (l.vert.co.x + 0.5, l.vert.co.y + 0.5)
        o = obj_from_bm('runner', bm, runner); o.scale = (1.3, 2.9, 1); o.location = (0.1, yc, 0.006)
    for y in ARCHES[::1]:
        lantern(0.0, y + 1.25, 2.55, 1.15, vault_z(0, 0.1) - 0.05, iron, lglass, 45)
    w = bpy.data.worlds.new('w'); bpy.context.scene.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0.3, 0.22, 0.15, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.05
    for k in range(6):
        f = light((0, -1.5 - k * 3.2, WALL_H), 160, (1.0, 0.7, 0.42), kind='AREA'); f.data.size = 2.4; f.rotation_euler = (math.pi, 0, 0)
    bpy.ops.object.select_all(action='DESELECT')
    blocks('books', BOOKS, bookm)

def walk_rects():
    R = [(-0.95, 1.05, -L + 0.45, -3.25),             # the hallway between the furniture
         (-0.55, -0.32, -3.3, -1.85), (0.32, 0.55, -3.3, -1.85),   # either side of the little table
         (-1.4, 1.4, -1.95, -0.6)]                     # in front of the door
    return [[x0, x1, -y1, -y0] for x0, x1, y0, y1 in R]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--render', default=''); ap.add_argument('--samples', type=int, default=96); ap.add_argument('--res', default='1280x720')
    ap.add_argument('--glb', default=''); ap.add_argument('--cam', default='main')
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
    bpy.ops.wm.read_factory_settings(use_empty=True); build()
    for o in bpy.context.scene.objects:
        if o.type == 'LIGHT' and hasattr(o, 'visible_camera'): o.visible_camera = False
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = a.samples; sc.cycles.use_denoising = True; sc.cycles.max_bounces = 8
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'; sc.view_settings.exposure = 0.8
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
    cfg.update(name='Hallway', glb='assets/rooms/hallway/hallway.glb', spawn=dict(x=0.15, z=L - 0.6, yaw=0), walk=walk_rects(), lights=[], probe=[0, 1.4, 9.0], tints=tints, floor='stonetile')
    cfg.setdefault('exposure', 0.9); cfg.setdefault('version', 1); cfg.setdefault('wallBoost', 1.0); cfg.setdefault('maxFlameLights', 34); cfg.setdefault('flameColor', '#ffb877')
    json.dump(cfg, open(cfgp, 'w'), indent=1)
    if a.render: sc.render.filepath = os.path.abspath(a.render); bpy.ops.render.render(write_still=True)
    if a.glb:
        keep = ('stone', 'plaster', 'planks', 'rough_wood', 'wood_cabinet', 'runner', 'view', 'ivy', 'stonetile')
        for im in bpy.data.images:
            if im.size[0] > 512 and not any(k in im.name for k in keep): im.scale(512, 512)
        bpy.ops.object.select_all(action='DESELECT')
        for o in list(sc.objects):
            if o.type == 'EMPTY' and o.instance_type == 'COLLECTION': o.select_set(True)
        if any(o.select_get() for o in sc.objects): bpy.ops.object.duplicates_make_real()
        bpy.ops.export_scene.gltf(filepath=os.path.abspath(a.glb), export_format='GLB', export_lights=False, export_cameras=False, export_apply=True, export_image_format='JPEG', export_jpeg_quality=82)

if __name__ == '__main__':
    main()
