"""Hobbit-house parents' bathroom (the second 'Master bathroom' image), rebuilt as a real 3D room.
Blender axes: the back wall (y = 0) holds a huge arched window onto the lake and mountains on the left; the copper slipper
tub stands in front of it on a round rug; the right wall has a long double vanity with stone tops and two arched mirrors,
a tall shelf of lanterns and jars, and the toilet in a little timber-framed nook at the front. Vines hang from the beams.

    python blender/rooms/parentsbath.py --render docs/rooms/parentsbath.png --samples 96 --glb assets/rooms/parentsbath/parentsbath.glb
"""
import argparse, json, math, os, sys, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
from hero_room import A, pbr, flat, image_mat, obj_from_bm, box_uv, box, cyl, torus, cut, model, light, candle
from kitchen import lantern, leaf_cluster, group, kid, tex_mat, mat_alpha, arch_cutter_y, stone_arch, bouquet, shelf, jars_row
from bathroom import toilet, vessel_sink
from spa import candles_cluster
from hallway import pillow
from dining import rod

HW, L, H = 3.6, 7.2, 4.4
rnd = random.Random(121)
CAMS = {'main': (-2.2, -6.8, 1.55, 86, -22, 15)}
WX, WW, WRH, WZ = -1.2, 3.4, 2.2, 0.45              # the huge arched window

def K(*p): return A('assets', 'rooms', 'parentsbath', *p)

def slipper_tub(cx, cy, copper, inner, brass):
    """Copper slipper bath: an oval shell whose rim rises toward both ends, on a plinth."""
    n, rings = 72, 7; sx, sy = 1.0, 0.5
    bm = bmesh.new(); prev = None
    for j in range(rings + 1):
        t = j / rings; s = 0.78 + 0.22 * math.sin(t * math.pi / 2)            # widens toward the top
        ring = []
        for i in range(n):
            a = i / n * 2 * math.pi; x, y = math.cos(a) * sx * s, math.sin(a) * sy * s
            z = 0.12 + t * (0.55 + 0.16 * abs(math.cos(a)) ** 3)                 # rim rises at the ends
            ring.append(bm.verts.new((cx + x, cy + y, z)))
        if prev:
            for i in range(n): bm.faces.new((prev[i], prev[(i + 1) % n], ring[(i + 1) % n], ring[i]))
        prev = ring
    bm.faces.new([bm.verts.new((cx + math.cos(i / n * 2 * math.pi) * sx * 0.78, cy + math.sin(i / n * 2 * math.pi) * sy * 0.78, 0.12)) for i in range(n)][::-1])
    o = obj_from_bm('tub', bm, copper, True); sol = o.modifiers.new('s', 'SOLIDIFY'); sol.thickness = 0.04; sol.offset = -1
    sub = o.modifiers.new('sub', 'SUBSURF'); sub.levels = 1; sub.render_levels = 2
    o.data.materials.append(inner)
    base = cyl('tub base', 1.0, 0.12, (cx, cy, 0.06), (0, 0, 0), copper, 64); base.scale = (sx * 0.7, sy * 0.7, 1)
    w = cyl('bath water', 1.0, 0.01, (cx, cy, 0.5), (0, 0, 0), flat('bath water', (0.45, 0.4, 0.3), 0.03, transmission=0.6), 64); w.scale = (sx * 0.88, sy * 0.88, 1)
    # tall brass floor-standing tap
    tx, ty = cx + 0.1, cy + sy + 0.2
    rod('tub tap', (tx, ty, 0.0), (tx, ty, 1.05), 0.022, brass); rod('tub spout', (tx, ty, 1.05), (tx, ty - 0.35, 0.95), 0.018, brass)
    for s in (-1, 1): cyl('tub tap handle', 0.03, 0.04, (tx + s * 0.08, ty, 0.85), (0, math.pi / 2, 0), brass, 12)

def build():
    floor = pbr('monastery_stone_floor', 'materials', (0.72, 0.62, 0.5), 0.45, 1.2)
    wall = pbr('old_stone_wall', 'materials', (0.9, 0.76, 0.58), 1.0, 1.4)
    ceil = pbr('dark_wooden_planks', 'materials', (0.5, 0.34, 0.22), 0.9)
    beam = pbr('rough_wood', 'materials', (0.42, 0.29, 0.18), 0.9)
    cab = pbr('wood_cabinet_worn_long', 'materials', (0.62, 0.45, 0.3), 0.8)
    top = tex_mat('stone top', A('assets', 'rooms', 'kitchen', 'marble_diff.jpg'), A('assets', 'rooms', 'kitchen', 'marble_rough.jpg'), tint=(0.72, 0.68, 0.64))
    sink_stone = pbr('yellow_stone_wall', 'materials', (0.85, 0.8, 0.72), 0.5, 0.6)
    frame = flat('window frame', (0.3, 0.19, 0.1), 0.55)
    glass = flat('glass', (0.95, 0.97, 0.98), 0.02, transmission=1.0); lglass = flat('lantern glass', (1.0, 0.86, 0.66), 0.08, transmission=0.85)
    mirror = flat('mirror', (0.9, 0.9, 0.9), 0.02, 1.0)
    iron = flat('iron', (0.03, 0.028, 0.026), 0.55, 0.35); brass = flat('brass', (0.78, 0.55, 0.26), 0.3, 1.0)
    copper = flat('copper', (0.7, 0.36, 0.18), 0.25, 1.0); copper_in = flat('copper inside', (0.75, 0.42, 0.24), 0.2, 1.0)
    ceramic = flat('ceramic', (0.88, 0.86, 0.82), 0.12); seat_wood = flat('seat wood', (0.3, 0.18, 0.1), 0.4)
    towel = flat('towel', (0.85, 0.82, 0.76), 0.95); wax = flat('wax', (0.92, 0.88, 0.78), 0.45)
    ivy = mat_alpha('ivy', A('assets', 'rooms', 'kitchen', 'ivy.png'))
    rug = mat_alpha('rug', A('assets', 'rooms', 'entrance', 'rug_diff.png'), 0.95)
    jar_glass = flat('jar glass', (0.9, 0.93, 0.9), 0.05, transmission=0.9)
    fills = [flat('fill salt', (0.9, 0.86, 0.8), 0.6), flat('fill amber', (0.6, 0.32, 0.08), 0.2), flat('fill herb', (0.3, 0.35, 0.18), 0.7)]
    petals = [flat('petal white', (0.95, 0.92, 0.88), 0.6), flat('petal blush', (0.95, 0.78, 0.72), 0.6)]
    # ------------------------------------------------------------ shell: flagstones, stone walls, plank ceiling, heavy beams
    box('floor', -HW - 0.3, HW + 0.3, -L - 0.3, 0.3, -0.12, 0.0, floor, 1.6)
    back = box('back wall', -HW - 0.4, HW + 0.4, 0.0, 0.45, 0.0, H, wall, 1.6)
    for x0, x1 in ((-HW - 0.4, -HW), (HW, HW + 0.4)): box('side wall', x0, x1, -L - 0.4, 0.0, 0.0, H, wall, 1.6)
    front = box('front wall', -HW - 0.4, HW + 0.4, -L - 0.4, -L, 0.0, H, wall, 1.6)
    box('ceiling', -HW - 0.4, HW + 0.4, -L - 0.4, 0.45, H, H + 0.15, ceil, 1.4)
    for k in range(6): y = -0.4 - k * 1.3; box('ceiling beam', -HW, HW, y - 0.14, y + 0.14, H - 0.3, H, beam, 1.2)
    for x in (-1.8, 0.0, 1.8): box('ceiling purlin', x - 0.12, x + 0.12, -L, 0.0, H - 0.5, H - 0.3, beam, 1.2)
    for (x, y) in ((-HW + 0.15, -0.15), (HW - 0.15, -0.15), (-HW + 0.15, -L + 0.15), (HW - 0.15, -L + 0.15), (HW - 0.15, -3.6)):
        box('timber post', x - 0.15, x + 0.15, y - 0.15, y + 0.15, 0.0, H, beam, 1.2)
    # vines everywhere overhead, like the image
    for k in range(70):
        x, y = rnd.uniform(-HW + 0.2, HW - 0.2), rnd.uniform(-L + 0.4, -0.2)
        leaf_cluster(ivy, x, y, H - 0.35, 10, 0.4, rnd.choice((0.2, 0.5, 1.2)))
    # ------------------------------------------------------------ the huge arched window onto the lake
    cut(back, arch_cutter_y(WX, WW, WRH, WZ, -0.2, 0.8)); box_uv(back, 1.6)
    g = group((WX, 0.25, WZ)); t = 0.1
    for x0, x1, z0, z1 in ((-WW / 2, -WW / 2 + t, 0, WRH), (WW / 2 - t, WW / 2, 0, WRH), (-WW / 2, WW / 2, 0, t)): kid(box('win frame', x0, x1, -0.05, 0.05, z0, z1, frame, 1.0), g)
    bpy.ops.mesh.primitive_torus_add(major_radius=WW / 2 - t / 2, minor_radius=t / 2, major_segments=64, minor_segments=8, location=(0, 0, WRH), rotation=(math.pi / 2, 0, 0))
    o = bpy.context.active_object; o.data.materials.append(frame); kid(o, g)
    bm2 = bmesh.new(); bm2.from_mesh(o.data); bmesh.ops.delete(bm2, geom=[v for v in bm2.verts if v.co.y < -t * 0.4], context='VERTS'); bm2.to_mesh(o.data); bm2.free()
    for x in (-WW / 4, WW / 4): kid(box('mullion', x - 0.035, x + 0.035, -0.04, 0.04, t, WRH + math.sqrt(max(0, (WW / 2) ** 2 - x * x)) - 0.1, frame, 1.0), g)
    bm = bmesh.new(); vs = [bm.verts.new((-WW / 2 + t, 0, 0.05)), bm.verts.new((WW / 2 - t, 0, 0.05))]
    for i in range(41): a = i / 40 * math.pi; vs.append(bm.verts.new((math.cos(a) * (WW / 2 - t), 0, WRH + math.sin(a) * (WW / 2 - t))))
    bm.faces.new(vs); kid(obj_from_bm('glass', bm, glass), g)
    g2 = group((WX, 0.0, WZ)); stone_arch(g2, WW, WRH, 0.3, beam, 0.24, half=True)
    box('window sill', WX - WW / 2 - 0.15, WX + WW / 2 + 0.15, -0.45, 0.25, WZ - 0.08, WZ, wall, 1.0)
    a = light((WX, 1.8, WZ + 1.6), 450, (1.0, 0.92, 0.82), kind='AREA'); a.data.size = WW; a.rotation_euler = (math.radians(-90), 0, 0)
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1); bmesh.ops.scale(bm, vec=(44, 19, 1), verts=bm.verts)
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 4, 'X')); bmesh.ops.translate(bm, vec=(WX, 14, 2.6), verts=bm.verts)
    view = obj_from_bm('lake view', bm, image_mat('view', A('assets', 'rooms', 'master', 'view.jpg'), 0.9)); uvl = view.data.uv_layers.new()
    for i, l in enumerate(uvl.data): co = view.data.vertices[view.data.loops[i].vertex_index].co; l.uv = ((co.x - WX) / 44 + 0.45, (co.z - 2.6) / 19 + 0.5)
    for (x, h) in ((WX - 1.2, 0.35), (WX + 0.2, 0.3), (WX + 1.3, 0.38)): model('potted_plant_04', (x, -0.2, WZ), rnd.uniform(0, 6), height=h)
    for k in range(24):
        a_ = k / 23 * math.pi; r = WW / 2 + 0.35
        leaf_cluster(ivy, WX + math.cos(a_) * r, -0.1, WZ + WRH + math.sin(a_) * r, 10, 0.25, 0.4 if k % 3 else 0.9)
    model('potted_plant_01', (-HW + 0.55, -0.6, 0), 0.5, height=2.0); model('potted_plant_01', (WX + WW / 2 + 0.45, -0.5, 0), 1.6, height=1.5)
    # ------------------------------------------------------------ the copper slipper tub on a round rug
    TX, TY = -1.0, -2.1
    bm = bmesh.new(); bmesh.ops.create_circle(bm, cap_ends=True, segments=96, radius=1.6); uv = bm.loops.layers.uv.new()
    for f in bm.faces:
        for l in f.loops: l[uv].uv = (l.vert.co.x / 3.2 + 0.5, l.vert.co.y / 3.2 + 0.5)
    o = obj_from_bm('rug', bm, rug); o.location = (TX, TY, 0.007); o.scale = (1.25, 1.0, 1)
    tub = slipper_tub(TX, TY, copper, copper_in, brass)
    for p in bpy.data.objects['tub'].data.polygons: pass
    candles_cluster(TX - 0.9, TY - 1.1, 0.0, wax, 3, 1.1); candles_cluster(TX + 0.8, TY + 1.0, 0.0, wax, 2, 1.0)
    model('wooden_stool_02', (TX + 1.45, TY - 0.3, 0), 0.4, height=0.45)
    for k in range(3): cyl('rolled towel', 0.06, 0.3, (TX + 1.45, TY - 0.42 + k * 0.12, 0.51), (0, math.pi / 2, 0), towel, 16)
    model('potted_plant_02', (TX + 1.4, -0.7, 0), 0.6, height=0.9)
    # a cushioned chair in the front-left corner with a throw, like the image
    model('ArmChair_01', (-HW + 0.75, -5.6, 0), math.radians(-60), width=0.8)
    model('potted_plant_01', (-HW + 0.45, -4.4, 0), 2.2, height=1.3)
    # ------------------------------------------------------------ right wall: double vanity, two arched mirrors, lantern shelf
    VY0, VY1, VH = -3.4, -0.45, 0.88; RX = HW
    box('vanity top', RX - 0.66, RX, VY0, VY1, VH - 0.07, VH, top, 1.0, 0.012)
    box('vanity body', RX - 0.6, RX, VY0 + 0.03, VY1 - 0.03, 0.12, VH - 0.07, cab, 1.0)
    n = 4; u = (VY1 - VY0) / n
    for i in range(n):
        c = VY0 + (i + 0.5) * u
        box('vanity door', RX - 0.625, RX - 0.6, c - u / 2 + 0.04, c + u / 2 - 0.04, 0.18, VH - 0.13, cab, 1.0, 0.004)
        box('vanity panel', RX - 0.64, RX - 0.625, c - u / 2 + 0.12, c + u / 2 - 0.12, 0.28, VH - 0.23, cab, 1.0, 0.006)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.016, location=(RX - 0.645, c + u / 2 - 0.1, VH - 0.25)); bpy.context.active_object.data.materials.append(brass)
    for y in (VY0 + 0.04, VY1 - 0.04): box('vanity leg', RX - 0.64, RX - 0.56, y - 0.04, y + 0.04, 0.0, 0.14, cab, 1.0)
    for sy in (VY0 + u, VY1 - u):
        box('sink basin', RX - 0.52, RX - 0.12, sy - 0.25, sy + 0.25, VH - 0.02, VH + 0.005, sink_stone, 0.6, 0.02)
        rod('vanity tap', (RX - 0.08, sy, VH), (RX - 0.08, sy, VH + 0.3), 0.015, brass); rod('vanity spout', (RX - 0.08, sy, VH + 0.3), (RX - 0.28, sy, VH + 0.25), 0.013, brass)
        mz0, mz1, mw = VH + 0.35, VH + 1.35, 0.85
        box('mirror glass', RX - 0.04, RX - 0.02, sy - mw / 2, sy + mw / 2, mz0, mz1, mirror, 1.0)
        cyl('mirror glass top', mw / 2, 0.02, (RX - 0.03, sy, mz1), (0, math.pi / 2, 0), mirror, 40)
        gm = group((RX - 0.03, sy, mz0), -math.pi / 2); stone_arch(gm, mw, mz1 - mz0, 0.07, beam, 0.1, half=True)
        box('mirror sill', RX - 0.1, RX, sy - mw / 2 - 0.08, sy + mw / 2 + 0.08, mz0 - 0.08, mz0, beam, 1.0)
    for y in (VY0 + 0.15, (VY0 + VY1) / 2, VY1 - 0.15):
        box('sconce arm', RX - 0.22, RX, y - 0.015, y + 0.015, 2.05, 2.08, iron, 1.0); lantern(RX - 0.22, y, 1.72, 0.8, 2.06, iron, lglass, 40)
    candles_cluster(RX - 0.25, (VY0 + VY1) / 2, VH, wax, 3, 0.9); model('ceramic_vase_04', (RX - 0.3, VY0 + 0.15, VH), 0, height=0.22)
    model('potted_plant_04', (RX - 0.3, VY1 - 0.15, VH), 0, height=0.28); bouquet(RX - 0.3, (VY0 + VY1) / 2 + 0.45, VH + 0.18, petals, ivy, 12, 0.12)
    model('ceramic_vase_02', (RX - 0.3, (VY0 + VY1) / 2 + 0.45, VH), 0, height=0.2)
    box('hanging towel', RX - 0.7, RX - 0.66, VY0 + 0.4, VY0 + 0.75, 0.42, 0.86, towel, 1.0, 0.02)
    # the tall open shelf of lanterns and jars beside the vanity (back-right corner)
    for z in (0.5, 1.0, 1.5, 2.0, 2.5): shelf(RX - 0.4, RX, -0.4, 0.0, z, beam) if False else box('corner shelf', 1.6, 2.6, -0.42, -0.02, z - 0.03, z, beam, 1.0)
    for x in (1.6, 2.6): box('corner shelf side', x - 0.03, x + 0.03, -0.42, -0.02, 0.0, 2.8, beam, 1.0)
    for z in (0.5, 1.5, 2.5): jars_row(1.65, 2.55, -0.2, z, True, 5, jar_glass, fills, brass)
    for z in (1.0, 2.0): lantern(2.1, -0.22, z, 0.6, None, iron, lglass, 20)
    # ------------------------------------------------------------ the toilet in a timber-framed nook at the front right
    box('nook wall', HW - 1.45, HW - 1.3, -6.1, -4.6, 0.0, 2.2, cab, 1.0)
    box('nook lintel', HW - 1.45, HW, -4.7, -4.55, 2.1, 2.25, beam, 1.0)
    toilet(HW - 0.45, -5.4, -math.pi / 2, ceramic, seat_wood)
    box('toilet roll arm', HW - 0.12, HW, -5.92, -5.9, 0.68, 0.7, brass, 1.0); cyl('toilet roll', 0.055, 0.11, (HW - 0.1, -5.91, 0.62), (math.pi / 2, 0, 0), towel, 16)
    model('wicker_basket_01', (HW - 0.4, -6.4, 0), 0, width=0.3); model('potted_plant_04', (HW - 1.37, -4.8, 2.2), 0, height=0.3)
    box('sconce arm', HW - 0.22, HW, -5.4, -5.37, 1.9, 1.93, iron, 1.0); lantern(HW - 0.22, -5.4, 1.58, 0.75, 1.91, iron, lglass, 30)
    # ------------------------------------------------------------ front wall door, fill light
    cut(front, arch_cutter_y(-0.4, 1.1, 1.6, 0.0, -L - 1, -L + 1)); box_uv(front, 1.6)
    g = group((-0.4, -L, 0.0)); stone_arch(g, 1.1, 1.6, 0.5, beam, 0.18, half=True)
    box('door', -1.0, 0.2, -L - 0.25, -L - 0.18, 0.0, 2.2, cab, 0.8)
    w = bpy.data.worlds.new('w'); bpy.context.scene.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0.6, 0.62, 0.66, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.15
    for y in (-2.0, -5.0):
        f = light((0.4, y, H - 0.6), 160, (1.0, 0.75, 0.5), kind='AREA'); f.data.size = 2.5

def walk_rects():
    R = [(-HW + 0.6, HW - 0.8, -L + 0.4, -3.7),            # the front, between the chair, tub and vanity
         (-0.05, HW - 0.8, -3.7, -0.6),                     # beside the tub, in front of the vanity
         (-HW + 0.6, -2.0, -3.7, -0.6),                     # the left of the tub, to the window
         (HW - 1.25, HW - 0.25, -6.6, -4.7) if False else (-0.7, -0.1, -L - 0.4, -L + 0.5)]   # the doorway
    return [[x0, x1, -y1, -y0] for x0, x1, y0, y1 in R]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--render', default=''); ap.add_argument('--samples', type=int, default=96); ap.add_argument('--res', default='1600x900')
    ap.add_argument('--glb', default=''); ap.add_argument('--cam', default='main')
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
    bpy.ops.wm.read_factory_settings(use_empty=True); build()
    for o in bpy.context.scene.objects:
        if o.type == 'LIGHT' and hasattr(o, 'visible_camera'): o.visible_camera = False
        if o.type == 'LIGHT' and hasattr(o, 'visible_transmission'): o.visible_transmission = False
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = a.samples; sc.cycles.use_denoising = True; sc.cycles.max_bounces = 8
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'; sc.view_settings.exposure = 0.35
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
    cfg.update(name="Parents' Bathroom", glb='assets/rooms/parentsbath/parentsbath.glb', spawn=dict(x=-0.4, z=L - 0.6, yaw=0.1), walk=walk_rects(), probe=[0.0, 1.4, 4.0], tints=tints, floor='monastery_stone_floor')
    cfg.setdefault('lights', [{'x': WX, 'y': 2.4, 'z': 1.4, 'color': '#ffe8d0', 'power': 14, 'range': 8}, {'x': 2.8, 'y': 2.0, 'z': 2.0, 'color': '#ffb877', 'power': 7, 'range': 5},
                              {'x': 0.4, 'y': 3.2, 'z': 4.5, 'color': '#ffb877', 'power': 8, 'range': 6}])
    cfg.setdefault('exposure', 0.9); cfg.setdefault('version', 1); cfg.setdefault('wallBoost', 1.0); cfg.setdefault('maxFlameLights', 24); cfg.setdefault('flameColor', '#ffb877')
    cfg.setdefault('env', {'copper': 0.35, 'copper inside': 0.3, 'dark_wooden_planks': 0.2, 'rough_wood': 0.2})
    cfg.setdefault('webTint', {'copper': [0.85, 0.7, 0.6], 'copper inside': [0.85, 0.65, 0.55]})
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
        bpy.ops.export_scene.gltf(filepath=os.path.abspath(a.glb), export_format='GLB', export_lights=False, export_cameras=False, export_apply=True, export_image_format='AUTO')

if __name__ == '__main__':
    main()
