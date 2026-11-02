"""Hobbit-house master bathroom, rebuilt as a real 3D room from the 'Master bathroom' image.
Blender axes: the back wall is at y = 0 with the tall arched lake-and-mountain window on the left and the glass walk-in
shower on the right; the vanity with the arched mirror and the toilet are on the right wall; the room runs toward the
camera to y = -L. Flat beamed wooden ceiling, stone walls with timber posts, flagstones, a rug, vines round the window.

    python blender/rooms/master.py --render docs/rooms/master.png --samples 96 --glb assets/rooms/master/master.glb
"""
import argparse, json, math, os, sys, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
from hero_room import A, pbr, flat, image_mat, obj_from_bm, box_uv, box, cyl, torus, cut, model, light, candle
from kitchen import lantern, leaf_cluster, group, kid, tex_mat, mat_alpha, arch_cutter_y, stone_arch, bouquet
from bathroom import toilet, vessel_sink
from spa import candles_cluster
from hallway import pillow
from dining import rod

HW, L, H = 3.0, 6.6, 4.3
rnd = random.Random(91)
CAMS = {'main': (1.35, -6.2, 1.6, 87, 14, 15), 'tub': (0.6, -4.2, 1.5, 88, 28, 17)}
WX, WW, WRH, WZ = -1.3, 2.7, 1.95, 0.7                 # the big arched window
SHX0, SHX1, SHY0 = 0.75, HW, -2.05                       # the shower enclosure (to the back wall)

def K(*p): return A('assets', 'rooms', 'master', *p)

def copper_tub(cx, cy, sx, sy, h, copper, inner):
    """Freestanding copper tub; sx along x, sy along y (half sizes)."""
    o = cyl('tub', 1.0, h, (cx, cy, 0.1 + h / 2), (0, 0, 0), copper, 72); o.scale = (sx, sy, 1)
    c = cyl('c', 1.0, h, (cx, cy, 0.22 + h / 2), (0, 0, 0), inner, 72); c.scale = (sx - 0.04, sy - 0.04, 1)
    bpy.context.view_layer.update(); cut(o, [c])
    rim = torus('tub rim', 1.0, 0.03, (cx, cy, 0.1 + h), (0, 0, 0), copper); rim.scale = (sx - 0.015, sy - 0.015, 1)
    base = cyl('tub base', 1.0, 0.1, (cx, cy, 0.05), (0, 0, 0), copper, 64); base.scale = (sx * 0.8, sy * 0.8, 1)
    w = cyl('bath water', 1.0, 0.01, (cx, cy, 0.1 + h * 0.65), (0, 0, 0), flat('bath water', (0.45, 0.4, 0.3), 0.03, transmission=0.6), 64); w.scale = (sx - 0.05, sy - 0.05, 1)

def build():
    floor = pbr('monastery_stone_floor', 'materials', (0.66, 0.56, 0.46), 0.45, 1.2)
    wall = pbr('old_stone_wall', 'materials', (0.86, 0.72, 0.56), 1.0, 1.4)
    shower_wall = pbr('yellow_stone_wall', 'materials', (0.62, 0.56, 0.5), 0.6, 1.4)
    ceil = pbr('dark_wooden_planks', 'materials', (0.55, 0.38, 0.24), 0.9)
    beam = pbr('rough_wood', 'materials', (0.4, 0.28, 0.18), 0.9)
    cab = pbr('wood_cabinet_worn_long', 'materials', (0.55, 0.4, 0.26), 0.8)
    top = tex_mat('stone top', A('assets', 'rooms', 'kitchen', 'marble_diff.jpg'), A('assets', 'rooms', 'kitchen', 'marble_rough.jpg'), tint=(0.95, 0.85, 0.72))
    sink_stone = pbr('yellow_stone_wall', 'materials', (0.8, 0.72, 0.62), 0.6, 0.8)
    frame = flat('window frame', (0.12, 0.07, 0.035), 0.55)
    glass = flat('glass', (0.95, 0.97, 0.98), 0.02, transmission=1.0); lglass = flat('lantern glass', (1.0, 0.86, 0.66), 0.08, transmission=0.85)
    iron = flat('iron', (0.03, 0.028, 0.026), 0.55, 0.35); brass = flat('brass', (0.78, 0.55, 0.26), 0.3, 1.0)
    copper = flat('copper', (0.62, 0.3, 0.16), 0.3, 1.0); copper_in = flat('copper inside', (0.7, 0.38, 0.22), 0.25, 1.0)
    ceramic = flat('ceramic', (0.88, 0.86, 0.82), 0.12); seat_wood = flat('seat wood', (0.3, 0.18, 0.1), 0.4)
    towel = flat('towel', (0.85, 0.82, 0.76), 0.95); towel2 = flat('towel oat', (0.72, 0.64, 0.52), 0.95)
    wax = flat('wax', (0.92, 0.88, 0.78), 0.45); ivy = mat_alpha('ivy', A('assets', 'rooms', 'kitchen', 'ivy.png'))
    rug = tex_mat('rug', A('assets', 'rooms', 'cellar', 'rug_diff.jpg'), rough=0.95, tint=(1.0, 0.9, 0.85))
    petals = [flat('petal white', (0.95, 0.92, 0.88), 0.6), flat('petal pink', (0.92, 0.6, 0.66), 0.6), flat('petal blush', (0.95, 0.78, 0.72), 0.6)]
    # ------------------------------------------------------------ shell: flagstones, stone walls, beamed plank ceiling
    box('floor', -HW - 0.3, HW + 0.3, -L - 0.3, 0.3, -0.12, 0.0, floor, 1.6)
    back = box('back wall', -HW - 0.4, HW + 0.4, 0.0, 0.45, 0.0, H, wall, 1.6)
    for x0, x1 in ((-HW - 0.4, -HW), (HW, HW + 0.4)): box('side wall', x0, x1, -L - 0.4, 0.0, 0.0, H, wall, 1.6)
    front = box('front wall', -HW - 0.4, HW + 0.4, -L - 0.4, -L, 0.0, H, wall, 1.6)
    box('ceiling', -HW - 0.4, HW + 0.4, -L - 0.4, 0.45, H, H + 0.15, ceil, 1.4)
    for k in range(6): y = -0.35 - k * 1.2; box('ceiling beam', -HW, HW, y - 0.13, y + 0.13, H - 0.28, H, beam, 1.2)
    for x in (-1.5, 1.5): box('ceiling purlin', x - 0.11, x + 0.11, -L, 0.0, H - 0.46, H - 0.28, beam, 1.2)
    bulb = flat('bulb', (1, 0.8, 0.5), 1, emit=(1.0, 0.75, 0.45), strength=15)
    for k in range(5):
        y = -0.95 - k * 1.2
        for x in (-0.6, 0.6, 2.2):
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.025, location=(x, y, H - 0.03)); bpy.context.active_object.data.materials.append(bulb); light((x, y, H - 0.1), 14, radius=0.03)
    for (x, y) in ((-HW + 0.15, -0.15), (HW - 0.15, -0.15), (-HW + 0.15, -L + 0.15), (HW - 0.15, -L + 0.15), (-HW + 0.15, -3.3), (HW - 0.15, -5.6)):
        box('timber post', x - 0.15, x + 0.15, y - 0.15, y + 0.15, 0.0, H, beam, 1.2)
    # ------------------------------------------------------------ the big arched window with the lake and mountains, vines all round
    cut(back, arch_cutter_y(WX, WW, WRH, WZ, -0.2, 0.8)); box_uv(back, 1.6)
    g = group((WX, 0.25, WZ))
    t = 0.09
    for x0, x1, z0, z1 in ((-WW / 2, -WW / 2 + t, 0, WRH), (WW / 2 - t, WW / 2, 0, WRH), (-WW / 2, WW / 2, 0, t)): kid(box('win frame', x0, x1, -0.05, 0.05, z0, z1, frame, 1.0), g)
    bpy.ops.mesh.primitive_torus_add(major_radius=WW / 2 - t / 2, minor_radius=t / 2, major_segments=64, minor_segments=8, location=(0, 0, WRH), rotation=(math.pi / 2, 0, 0))
    o = bpy.context.active_object; o.data.materials.append(frame); kid(o, g)
    bm = bmesh.new(); bm.from_mesh(o.data); bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y < -t * 0.4], context='VERTS'); bm.to_mesh(o.data); bm.free()
    for x in (-WW / 6, WW / 6): kid(box('mullion', x - 0.03, x + 0.03, -0.035, 0.035, t, WRH + math.sqrt(max(0, (WW / 2) ** 2 - x * x)) - 0.08, frame, 1.0), g)
    kid(box('transom', -WW / 2 + t, WW / 2 - t, -0.035, 0.035, WRH - 0.03, WRH + 0.03, frame, 1.0), g)
    bm = bmesh.new(); vs = [bm.verts.new((-WW / 2 + t, 0, 0.05)), bm.verts.new((WW / 2 - t, 0, 0.05))]
    for i in range(41): a = i / 40 * math.pi; vs.append(bm.verts.new((math.cos(a) * (WW / 2 - t), 0, WRH + math.sin(a) * (WW / 2 - t))))
    bm.faces.new(vs); kid(obj_from_bm('glass', bm, glass), g)
    g2 = group((WX, 0.0, WZ)); stone_arch(g2, WW, WRH, 0.3, beam, 0.2, half=True)
    box('window sill', WX - WW / 2 - 0.15, WX + WW / 2 + 0.15, -0.2, 0.25, WZ - 0.08, WZ, beam, 1.0)
    a = light((WX, 1.8, WZ + 1.3), 1100, (0.85, 0.92, 1.0), kind='AREA'); a.data.size = WW; a.rotation_euler = (math.radians(90), 0, 0)
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1); bmesh.ops.scale(bm, vec=(40, 17.3, 1), verts=bm.verts)
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 4, 'X')); bmesh.ops.translate(bm, vec=(WX, 13, 2.2), verts=bm.verts)
    view = obj_from_bm('lake view', bm, image_mat('view', K('view.jpg'), 1.25)); uvl = view.data.uv_layers.new()
    for i, l in enumerate(uvl.data): co = view.data.vertices[view.data.loops[i].vertex_index].co; l.uv = ((co.x - WX) / 40 + 0.45, (co.z - 2.2) / 17.3 + 0.5)
    for k in range(22):
        a_ = k / 21 * math.pi; r = WW / 2 + 0.3
        leaf_cluster(ivy, WX + math.cos(a_) * r, -0.1, WZ + WRH + math.sin(a_) * r, 9, 0.22, 0.25 if k % 3 else 0.7)
    for k in range(6): leaf_cluster(ivy, WX + (-1 if k % 2 else 1) * (WW / 2 + 0.3), -0.1, WZ + 0.2 + k * 0.25, 8, 0.2, 0.3)
    for k in range(10): leaf_cluster(ivy, -HW + 0.4 + k * 0.6, -0.2, H - 0.35, 10, 0.25, 0.8 if k % 2 else 0.3)
    # wall lanterns either side of the window
    for x in (WX - WW / 2 - 0.45, WX + WW / 2 + 0.45):
        box('sconce arm', x - 0.015, x + 0.015, -0.25, 0.0, 2.15, 2.18, iron, 1.0); lantern(x, -0.25, 1.8, 0.95, 2.16, iron, lglass, 45)
    # ------------------------------------------------------------ the copper tub under the window, a stool of candles, towels
    TX, TY = WX, -1.25
    copper_tub(TX, TY, 1.12, 0.52, 0.62, copper, copper_in)
    rod('tub tap', (TX + 0.55, TY + 0.68, 0.0), (TX + 0.55, TY + 0.68, 1.0), 0.02, brass); rod('tub spout', (TX + 0.55, TY + 0.68, 1.0), (TX + 0.55, TY + 0.38, 0.95), 0.016, brass)
    for s in (-1, 1): cyl('tub tap handle', 0.03, 0.04, (TX + 0.55 + s * 0.08, TY + 0.68, 0.9), (0, math.pi / 2, 0), brass, 12)
    model('wooden_stool_02', (TX + 1.55, TY - 0.55, 0), 0.4, height=0.48); candles_cluster(TX + 1.55, TY - 0.55, 0.48, wax, 2, 0.8)
    model('wooden_stool_02', (TX - 0.6, TY - 1.15, 0), 1.1, height=0.42)
    for k in range(3): box('rolled towel', TX - 0.78, TX - 0.42, TY - 1.25 + k * 0.1 - 0.05, TY - 1.25 + k * 0.1 + 0.05, 0.43 + (k % 2) * 0.09, 0.53 + (k % 2) * 0.09, towel, 1.0, 0.04) if False else None
    for k in range(3): cyl('rolled towel', 0.06, 0.34, (TX - 0.6, TY - 1.25 + k * 0.12, 0.48), (0, math.pi / 2, 0), towel, 16)
    candles_cluster(TX + 0.2, TY - 1.0, 0.0, wax, 3, 1.1)
    # flowers and plants in the left foreground
    for (x, y, h) in ((-HW + 0.45, -2.4, 0.5), (-HW + 0.5, -3.8, 0.85), (-HW + 0.4, -5.0, 0.6)):
        model('planter_pot_clay', (x, y, 0), rnd.uniform(0, 6), height=0.3); bouquet(x, y, 0.32, petals, ivy, 30, 0.3); leaf_cluster(ivy, x, y, h, 14, 0.3, 0.2)
    model('potted_plant_01', (WX + WW / 2 + 0.55, -0.45, 0), 0.4, height=1.4)
    # ------------------------------------------------------------ the glass walk-in shower in the back-right corner
    box('shower tiles', SHX0, HW, -0.02, 0.0, 0.0, H, shower_wall, 0.9)
    box('shower tiles', HW - 0.02, HW, SHY0, 0.0, 0.0, H, shower_wall, 0.9)
    box('shower floor', SHX0, HW, SHY0, 0.0, 0.0, 0.05, floor, 0.8)
    DOOR = (1.1, 1.85)
    for x0, x1 in ((SHX0, DOOR[0]), (DOOR[1], HW)): box('shower glass', x0, x1, SHY0 - 0.006, SHY0 + 0.006, 0.05, 2.25, glass, 1.0)
    box('shower glass', DOOR[0] - 0.006, DOOR[0] + 0.006, SHY0 - 0.006, SHY0 + 0.45, 0.05, 2.25, glass, 1.0)
    box('shower glass', SHX0 - 0.006, SHX0 + 0.006, SHY0, 0.0, 0.05, 2.25, glass, 1.0)
    for (x, y) in ((SHX0, SHY0), (DOOR[0], SHY0), (DOOR[1], SHY0)): cyl('shower post', 0.012, 2.2, (x, y, 1.15), (0, 0, 0), brass, 10)
    box('shower rail', SHX0, HW, SHY0 - 0.012, SHY0 + 0.012, 2.24, 2.27, brass, 1.0); box('shower rail', SHX0 - 0.012, SHX0 + 0.012, SHY0, 0.0, 2.24, 2.27, brass, 1.0)
    for sx in (1.4, 2.4):
        cyl('shower pipe', 0.016, 2.25, (sx, -0.06, 1.12), (0, 0, 0), brass, 10); rod('shower arm', (sx, -0.06, 2.25), (sx, -0.45, 2.3), 0.014, brass)
        cyl('rain head', 0.15, 0.025, (sx, -0.45, 2.29), (0, 0, 0), brass, 32)
    for s in (-1, 1): cyl('shower valve', 0.045, 0.03, (1.9 + s * 0.14, -0.04, 1.15), (math.pi / 2, 0, 0), brass, 16)
    box('shower niche', HW - 0.12, HW - 0.02, -1.4, -0.7, 1.1, 1.13, shower_wall, 1.0)
    for k, y in enumerate((-1.3, -1.1, -0.9)): cyl('soap bottle', 0.03, 0.16, (HW - 0.08, y, 1.21), (0, 0, 0), [ceramic, brass, glass][k], 12)
    light((1.9, -1.0, 2.6), 60, radius=0.3); light((1.9, -1.0, 0.6), 25, (1.0, 0.65, 0.35), radius=0.2)
    # towel bar on the shower glass, towels hanging
    rod('towel bar', (SHX0 - 0.05, -0.55, 1.6), (SHX0 - 0.05, -1.75, 1.6), 0.012, brass)
    for y, m in ((-0.8, towel), (-1.15, towel2), (-1.5, towel)): box('hanging towel', SHX0 - 0.09, SHX0 - 0.01, y - 0.16, y + 0.16, 0.85, 1.62, m, 1.0, 0.02)
    # ------------------------------------------------------------ right wall: the toilet, then the vanity with the arched mirror
    toilet(HW - 0.48, -2.65, -math.pi / 2, ceramic, seat_wood)
    box('toilet roll arm', HW - 0.12, HW, -3.12, -3.1, 0.68, 0.7, brass, 1.0); cyl('toilet roll', 0.055, 0.11, (HW - 0.1, -3.11, 0.62), (math.pi / 2, 0, 0), towel, 16)
    model('potted_plant_04', (HW - 0.35, -2.1, 0.86), 0, height=0.3) if False else None
    VY0, VY1, VH = -5.35, -3.45, 0.86
    box('vanity top', HW - 0.62, HW, VY0, VY1, VH - 0.06, VH, top, 1.0, 0.01)
    box('vanity apron', HW - 0.58, HW, VY0 + 0.04, VY1 - 0.04, VH - 0.2, VH - 0.06, cab, 1.0)
    for y in (VY0 + 0.06, VY1 - 0.06):
        for x in (HW - 0.55, HW - 0.08): box('vanity leg', x - 0.04, x + 0.04, y - 0.04, y + 0.04, 0.0, VH - 0.06, cab, 1.0, 0.01)
    box('vanity shelf', HW - 0.55, HW - 0.05, VY0 + 0.05, VY1 - 0.05, 0.22, 0.26, cab, 1.0)
    for k in range(3): cyl('rolled towel', 0.06, 0.4, (HW - 0.3, VY0 + 0.4 + k * 0.13, 0.32), (0, math.pi / 2, 0), towel2 if k == 1 else towel, 16)
    model('wicker_basket_02', (HW - 0.3, VY1 - 0.45, 0.26), math.pi / 2, width=0.36)
    vessel_sink(HW - 0.33, (VY0 + VY1) / 2, VH, sink_stone, brass)
    box('hanging towel', HW - 0.66, HW - 0.6, VY1 - 0.38, VY1 - 0.1, 0.45, 0.88, towel, 1.0, 0.02)
    # arched mirror
    mz0, mz1, mw = VH + 0.25, VH + 1.25, 1.0; my = (VY0 + VY1) / 2
    box('mirror glass', HW - 0.04, HW - 0.02, my - mw / 2, my + mw / 2, mz0, mz1, flat('mirror', (0.9, 0.9, 0.9), 0.02, 1.0), 1.0)
    cyl('mirror glass top', mw / 2, 0.02, (HW - 0.03, my, mz1), (0, math.pi / 2, 0), flat('mirror', (0.9, 0.9, 0.9), 0.02, 1.0), 40)
    gm = group((HW - 0.03, my, mz0), -math.pi / 2); stone_arch(gm, mw, mz1 - mz0, 0.06, beam, 0.09, half=True)
    for y in (my - 0.8, my + 0.8): box('sconce arm', HW - 0.22, HW, y - 0.015, y + 0.015, 1.95, 1.98, iron, 1.0); lantern(HW - 0.22, y, 1.62, 0.85, 1.96, iron, lglass, 40)
    candles_cluster(HW - 0.2, VY0 + 0.25, VH, wax, 3, 0.9); model('ceramic_vase_04', (HW - 0.2, VY1 - 0.2, VH), 0, height=0.22)
    model('potted_plant_04', (HW - 0.18, VY1 - 0.5, VH), 0, height=0.28)
    model('potted_plant_02', (HW - 0.45, -L + 0.5, 0), 0.3, height=0.9)
    # ------------------------------------------------------------ the rug, floor candles, the door
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5); uvl = bm.loops.layers.uv.new()
    for f in bm.faces:
        for l in f.loops: l[uvl].uv = (l.vert.co.y + 0.5, l.vert.co.x + 0.5)
    o = obj_from_bm('rug', bm, rug); o.scale = (2.0, 3.0, 1); o.location = (0.9, -4.2, 0.007)
    candles_cluster(0.3, -2.35, 0.0, wax, 3, 1.0)
    cut(front, arch_cutter_y(-1.4, 1.1, 1.6, 0.0, -L - 1, -L + 1)); box_uv(front, 1.6)
    g = group((-1.4, -L, 0.0)); stone_arch(g, 1.1, 1.6, 0.5, beam, 0.18, half=True)
    box('door', -2.0, -0.8, -L - 0.25, -L - 0.18, 0.0, 2.2, cab, 0.8)
    w = bpy.data.worlds.new('w'); bpy.context.scene.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0.45, 0.55, 0.7, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.1
    for y in (-1.8, -4.6):
        f = light((0.0, y, H - 0.5), 110, (1.0, 0.72, 0.45), kind='AREA'); f.data.size = 2.5; f.rotation_euler = (math.pi, 0, 0)

def walk_rects():
    R = [(-HW + 0.75, HW - 0.75, -L + 0.4, -2.35),          # the open middle
         (-HW + 0.75, SHX0 - 0.2, -2.35, -1.95),            # in front of the tub
         (DOOR_X0 + 0.1, DOOR_X1 - 0.1, -2.5, -1.6),        # through the shower door
         (SHX0 + 0.3, HW - 0.3, -1.7, -0.35),               # inside the shower
         (-1.85, -0.95, -L - 0.2, -L + 0.5)]                # the doorway
    return [[x0, x1, -y1, -y0] for x0, x1, y0, y1 in R]
DOOR_X0, DOOR_X1 = 1.1, 1.85

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--render', default=''); ap.add_argument('--samples', type=int, default=96); ap.add_argument('--res', default='1600x900')
    ap.add_argument('--glb', default=''); ap.add_argument('--cam', default='main')
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
    bpy.ops.wm.read_factory_settings(use_empty=True); build()
    for o in bpy.context.scene.objects:
        if o.type == 'LIGHT' and hasattr(o, 'visible_camera'): o.visible_camera = False
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
    cfg.update(name='Master Bathroom', glb='assets/rooms/master/master.glb', spawn=dict(x=0.6, z=L - 0.7, yaw=0.15), walk=walk_rects(), probe=[0.2, 1.4, 3.5], tints=tints, floor='monastery_stone_floor')
    cfg.setdefault('lights', [{'x': WX, 'y': 2.2, 'z': 1.3, 'color': '#ffe8d0', 'power': 12, 'range': 7}, {'x': 1.9, 'y': 2.4, 'z': 1.0, 'color': '#ffd0a0', 'power': 6, 'range': 4},
                              {'x': 0.5, 'y': 2.8, 'z': 4.0, 'color': '#ffb877', 'power': 8, 'range': 6}])
    cfg.setdefault('exposure', 0.85); cfg.setdefault('version', 1); cfg.setdefault('wallBoost', 1.0); cfg.setdefault('maxFlameLights', 26); cfg.setdefault('flameColor', '#ffb877')
    cfg.setdefault('env', {'copper': 0.3, 'copper inside': 0.25, 'dark_wooden_planks': 0.2, 'rough_wood': 0.2})
    cfg.setdefault('webTint', {'copper': [0.8, 0.65, 0.58], 'copper inside': [0.8, 0.62, 0.52]})
    json.dump(cfg, open(cfgp, 'w'), indent=1)
    if a.render: sc.render.filepath = os.path.abspath(a.render); bpy.ops.render.render(write_still=True)
    if a.glb:
        keep = ('stone', 'planks', 'rough_wood', 'wood_cabinet', 'view', 'ivy', 'rug', 'marble')
        for im in bpy.data.images:
            if im.size[0] > 512 and not any(k in im.name for k in keep): im.scale(512, 512)
        bpy.ops.object.select_all(action='DESELECT')
        for o in list(sc.objects):
            if o.type == 'EMPTY' and o.instance_type == 'COLLECTION': o.select_set(True)
        if any(o.select_get() for o in sc.objects): bpy.ops.object.duplicates_make_real()
        bpy.ops.export_scene.gltf(filepath=os.path.abspath(a.glb), export_format='GLB', export_lights=False, export_cameras=False, export_apply=True, export_image_format='JPEG', export_jpeg_quality=82)

if __name__ == '__main__':
    main()
