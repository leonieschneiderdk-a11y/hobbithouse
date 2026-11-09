"""Hobbit-house red room, rebuilt as a real 3D room from the 'Red room' image: deep red damask walls and red velvet
everywhere, a four-poster bed hung with heavy crimson drapes, a gilded mirror over a console of candles, red-shaded wall
sconces, a carved stone fireplace with a fire, red armchairs, a coffered dark wood ceiling and a red-and-gold rug.

Blender axes: the back wall (mirror) is at y = 0, the room runs toward the camera to y = -L; the bed is on the left,
the fireplace on the right.

    python blender/rooms/redroom.py --render docs/rooms/redroom.png --samples 96 --glb assets/rooms/redroom/redroom.glb
"""
import argparse, json, math, os, sys, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
from hero_room import A, pbr, flat, obj_from_bm, box_uv, box, cyl, torus, cut, model, light, candle
from kitchen import group, kid, tex_mat, mat_alpha, stone_arch, arch_cutter_y, bouquet, leaf_cluster
from hallway import pillow
from spa import candles_cluster
from nursery import curtain
from bedroom import lamp, throw
from dining import rod

W, L, H = 6.6, 8.2, 3.5
HW = W / 2
rnd = random.Random(141)
CAMS = {'main': (-0.5, -L + 0.4, 1.6, 86, -12, 14), 'bed': (1.8, -6.6, 1.5, 86, 50, 16)}

def K(*p): return A('assets', 'rooms', 'redroom', *p)

def build():
    damask = tex_mat('damask', K('damask_diff.jpg'), K('damask_rough.jpg'))
    floor = pbr('wood_floor_worn', 'materials', (0.42, 0.24, 0.16), 0.5, 1.0)
    panel = pbr('wood_cabinet_worn_long', 'materials', (0.36, 0.14, 0.1), 0.7)
    ceil = pbr('wood_cabinet_worn_long', 'materials', (0.3, 0.12, 0.08), 0.8)
    beam = pbr('rough_wood', 'materials', (0.3, 0.14, 0.09), 0.8)
    stone = pbr('rustic_stone_wall', 'materials', (0.62, 0.52, 0.46), 0.9, 1.2)
    rug = tex_mat('rug', K('rug_diff.jpg'), rough=0.95)
    velvet = flat('red velvet', (0.22, 0.01, 0.015), 0.65); velvet2 = flat('crimson velvet', (0.32, 0.02, 0.025), 0.6)
    satin = flat('red satin', (0.4, 0.04, 0.05), 0.35); cream = flat('cream linen', (0.62, 0.48, 0.4), 0.9)
    gold = flat('gold', (0.8, 0.55, 0.22), 0.28, 1.0); brass = flat('brass', (0.78, 0.55, 0.26), 0.3, 1.0)
    mirror = flat('mirror', (0.85, 0.82, 0.8), 0.02, 1.0); dark = flat('dark wood', (0.14, 0.04, 0.03), 0.4)
    wax = flat('wax', (0.92, 0.88, 0.78), 0.45); ivy = mat_alpha('ivy', A('assets', 'rooms', 'kitchen', 'ivy.png'))
    red_shade = flat('red shade', (0.8, 0.2, 0.12), 0.8, emit=(1.0, 0.32, 0.15), strength=2.5)
    shade_m = flat('lamp shade', (0.95, 0.75, 0.55), 0.8, emit=(1.0, 0.65, 0.4), strength=3)
    log = flat('log', (0.22, 0.13, 0.07), 0.9); ember = flat('ember', (1, 0.4, 0.1), 1, emit=(1.0, 0.4, 0.1), strength=30)
    petals = [flat('petal red', (0.55, 0.03, 0.05), 0.6), flat('petal deep', (0.3, 0.01, 0.03), 0.6)]
    # ------------------------------------------------------------ shell: red damask walls over dark wood panelling, coffered ceiling
    box('floor', -HW - 0.3, HW + 0.3, -L - 0.3, 0.3, -0.12, 0.0, floor, 1.6)
    for nm, x0, x1, y0, y1 in (('back', -HW - 0.3, HW + 0.3, 0.0, 0.3), ('front', -HW - 0.3, HW + 0.3, -L - 0.3, -L), ('left', -HW - 0.3, -HW, -L, 0.0), ('right', HW, HW + 0.3, -L, 0.0)):
        box(nm + ' wall', x0, x1, y0, y1, 0.0, H, damask, 0.42)
    def wainscot(x0, x1, y0, y1, along_x):
        box('dado', x0, x1, y0, y1, 0.0, 0.95, panel, 1.0)
        box('dado rail', x0 - (0 if along_x else 0.02), x1 + (0 if along_x else 0.02), y0 - (0.02 if along_x else 0), y1 + (0.02 if along_x else 0), 0.93, 1.0, dark, 1.0, 0.01)
        box('picture rail', x0, x1, y0, y1, H - 0.4, H - 0.32, dark, 1.0, 0.01)
    wainscot(-HW, HW, -0.04, 0.0, True); wainscot(-HW, HW, -L, -L + 0.04, True); wainscot(-HW, -HW + 0.04, -L, 0, False); wainscot(HW - 0.04, HW, -L, 0, False)
    box('ceiling', -HW - 0.3, HW + 0.3, -L - 0.3, 0.3, H, H + 0.12, ceil, 1.4)
    for k in range(5): x = -HW + (k + 0.5) * W / 5; box('coffer beam', x - 0.09, x + 0.09, -L, 0, H - 0.22, H, beam, 1.0, 0.01) if k else None
    for k in range(1, 5): x = -HW + k * W / 5; box('coffer beam', x - 0.09, x + 0.09, -L, 0, H - 0.22, H, beam, 1.0, 0.01)
    for k in range(1, 6): y = -k * L / 6; box('coffer beam', -HW, HW, y - 0.09, y + 0.09, H - 0.22, H, beam, 1.0, 0.01)
    for k in range(6): box('cornice', -HW, HW, -0.12, 0.0, H - 0.18, H, gold, 1.0, 0.01) if k == 0 else None
    model('Chandelier_01', (0.4, -3.8, H - 0.85), 0, height=0.8); light((0.4, -3.8, H - 0.85), 60, (1.0, 0.6, 0.35), radius=0.3)
    # ------------------------------------------------------------ back wall: gilded mirror over a console of candles, tall drapes, sconces
    MX = 0.6
    box('console', MX - 0.9, MX + 0.9, -0.5, -0.04, 0.8, 0.86, dark, 1.0, 0.01)
    box('console apron', MX - 0.85, MX + 0.85, -0.46, -0.04, 0.66, 0.8, dark, 1.0)
    for x in (MX - 0.8, MX + 0.8):
        for y in (-0.42, -0.1): rod('console leg', (x, y, 0.0), (x + (0.03 if x > MX else -0.03), y, 0.66), 0.03, gold, 10)
    box('mirror glass', MX - 0.55, MX + 0.55, -0.06, -0.04, 1.05, 2.4, mirror, 1.0)
    for z0, z1, x0, x1 in ((0.95, 1.05, MX - 0.7, MX + 0.7), (2.4, 2.55, MX - 0.7, MX + 0.7), (0.95, 2.55, MX - 0.7, MX - 0.55), (0.95, 2.55, MX + 0.55, MX + 0.7)):
        box('mirror frame', x0, x1, -0.12, -0.04, z0, z1, gold, 1.0, 0.02)
    for k in range(9):
        a = k / 8 * math.pi; bpy.ops.mesh.primitive_uv_sphere_add(radius=0.07, location=(MX + math.cos(a) * 0.45, -0.1, 2.6 + math.sin(a) * 0.25)); bpy.context.active_object.data.materials.append(gold)
    for x in (MX - 0.55, MX + 0.55): model('brass_candleholders', (x, -0.27, 0.86), 0, width=0.36)
    candles_cluster(MX, -0.27, 0.86, wax, 4, 1.1); model('ceramic_vase_02', (MX + 0.2, -0.3, 0.86), 0, height=0.22); bouquet(MX + 0.2, -0.3, 1.06, petals, ivy, 14, 0.13)
    for x in (MX - 1.2, MX + 1.2):
        box('sconce plate', x - 0.06, x + 0.06, -0.06, -0.02, 1.7, 1.9, gold, 1.0, 0.01); rod('sconce arm', (x, -0.04, 1.8), (x, -0.25, 1.85), 0.012, gold)
        bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=False, segments=16, radius1=0.1, radius2=0.06, depth=0.14); obj_from_bm('sconce shade', bm, red_shade, True).location = (x, -0.25, 1.95)
        light((x, -0.3, 1.95), 30, (1.0, 0.45, 0.25), radius=0.06)
    # tall crimson drapes on the back-left, as if over a window
    box('curtain rod', -HW + 0.1, -0.6, -0.25, -0.21, H - 0.45, H - 0.41, gold, 1.0)
    for x0, x1 in ((-HW + 0.15, -HW + 1.25), (-1.8, -0.7)):
        curtain('drape', [(x0, -0.2), (x1, -0.22)], 0.0, H - 0.43, velvet2, 0.08, 10)
    box('curtain pelmet', -HW + 0.05, -0.55, -0.32, -0.04, H - 0.62, H - 0.36, velvet, 1.0, 0.02)
    # ------------------------------------------------------------ left: the four-poster bed with red velvet drapes
    BX0, BY, BL, BWD = -HW + 0.15, -4.6, 2.3, 2.1
    bx1 = BX0 + BL
    box('headboard', BX0, BX0 + 0.12, BY - BWD / 2 - 0.1, BY + BWD / 2 + 0.1, 0.0, 1.6, velvet, 1.0, 0.03)
    for k in range(4):
        for j in range(3): bpy.ops.mesh.primitive_uv_sphere_add(radius=0.02, location=(BX0 + 0.13, BY - 0.75 + k * 0.5, 0.75 + j * 0.28)); bpy.context.active_object.data.materials.append(gold)
    box('bed frame', BX0 + 0.1, bx1, BY - BWD / 2, BY + BWD / 2, 0.15, 0.45, dark, 1.0, 0.02)
    pillow((BX0 + bx1) / 2 + 0.05, BY, 0.6, BL - 0.15, BWD - 0.06, 0.28, cream)
    pillow((BX0 + bx1) / 2 + 0.25, BY, 0.78, BL - 0.55, BWD + 0.1, 0.14, satin)
    throw(bx1 - 0.85, bx1 - 0.15, BY - BWD / 2 - 0.05, BY + BWD / 2 + 0.05, 0.86, velvet, 0.5)
    for k, (dy, m, sz) in enumerate(((-0.6, velvet2, 0.6), (0.05, velvet2, 0.6), (0.7, velvet2, 0.6), (-0.35, satin, 0.45), (0.4, satin, 0.45), (0.0, velvet, 0.35))):
        z = 1.0 if k < 3 else 1.05; pillow(BX0 + 0.32 + (0.13 if k >= 3 else 0), BY + dy, z, 0.18, sz, sz * 0.75, m).rotation_euler = (0, math.radians(-16), 0)
    TOP = 2.75
    for (x, y) in ((BX0 + 0.08, BY - BWD / 2 - 0.05), (BX0 + 0.08, BY + BWD / 2 + 0.05), (bx1, BY - BWD / 2 - 0.05), (bx1, BY + BWD / 2 + 0.05)):
        cyl('bed post', 0.06, TOP, (x, y, TOP / 2), (0, 0, 0), dark, 16); bpy.ops.mesh.primitive_uv_sphere_add(radius=0.08, location=(x, y, TOP)); bpy.context.active_object.data.materials.append(gold)
    box('canopy', BX0, bx1 + 0.08, BY - BWD / 2 - 0.12, BY + BWD / 2 + 0.12, TOP - 0.25, TOP, velvet, 1.0, 0.02)
    for s in (-1, 1):                                                        # drapes on the four posts, tied back
        y = BY + s * (BWD / 2 + 0.05)
        curtain('bed drape', [(bx1 + 0.05, y), (bx1 - 0.6, y + s * 0.05)], 0.0, TOP - 0.25, velvet2, 0.07, 9)
        curtain('bed drape', [(BX0 + 0.15, y), (BX0 + 0.8, y + s * 0.05)], 0.0, TOP - 0.25, velvet2, 0.07, 9)
        torus('tie back', 0.07, 0.015, (bx1 - 0.1, y, 1.0), (0, 0, 0), gold)
    curtain('bed back drape', [(BX0 + 0.1, BY - BWD / 2), (BX0 + 0.1, BY + BWD / 2)], 1.55, TOP - 0.25, velvet2, 0.06, 12)
    box('bench', bx1 + 0.25, bx1 + 0.7, BY - 0.8, BY + 0.8, 0.12, 0.45, velvet, 1.0, 0.05)
    for (x, y) in ((bx1 + 0.3, BY - 0.75), (bx1 + 0.65, BY - 0.75), (bx1 + 0.3, BY + 0.75), (bx1 + 0.65, BY + 0.75)): cyl('bench leg', 0.025, 0.12, (x, y, 0.06), (0, 0, 0), gold, 10)
    for s in (-1, 1):
        ny = BY + s * (BWD / 2 + 0.5)
        box('nightstand', BX0, BX0 + 0.5, ny - 0.28, ny + 0.28, 0.0, 0.62, dark, 1.0, 0.01)
        lamp(BX0 + 0.25, ny, 0.62, brass, shade_m, 0.42, 45); candles_cluster(BX0 + 0.3, ny + s * 0.15, 0.62, wax, 1, 0.8)
    # ------------------------------------------------------------ right: carved stone fireplace with a fire, a painting, an armchair
    FY = -4.4
    box('chimney breast', HW - 0.6, HW, FY - 1.0, FY + 1.0, 0.0, H, damask, 0.42)
    fb = box('fire surround', HW - 0.85, HW - 0.55, FY - 0.95, FY + 0.95, 0.0, 1.3, stone, 1.0, 0.02)
    cut(fb, [box('c', HW - 1.2, HW - 0.3, FY - 0.55, FY + 0.55, 0.2, 0.95, stone)])
    box('firebox', HW - 0.62, HW - 0.55, FY - 0.55, FY + 0.55, 0.2, 0.95, flat('soot', (0.04, 0.03, 0.025), 0.9), 1.0)
    box('hearth', HW - 1.2, HW - 0.55, FY - 1.05, FY + 1.05, 0.0, 0.2, stone, 1.0, 0.02)
    box('mantel', HW - 1.0, HW - 0.5, FY - 1.1, FY + 1.1, 1.3, 1.42, stone, 1.0, 0.02)
    for i in range(3): cyl('log', 0.07, 0.7, (HW - 0.75, FY + (i - 1) * 0.05, 0.28 + (i // 2) * 0.12), (math.pi / 2, 0, (i - 1) * 0.3), log, 12)
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.28); o = obj_from_bm('fire', bm, ember, True); o.location = (HW - 0.75, FY, 0.42); o.scale = (0.5, 1.3, 0.6)
    light((HW - 1.0, FY, 0.55), 240, (1.0, 0.45, 0.15), radius=0.3)
    candles_cluster(HW - 0.75, FY - 0.85, 1.42, wax, 3, 0.9); candles_cluster(HW - 0.75, FY + 0.85, 1.42, wax, 3, 0.9)
    model('mantel_clock_01', (HW - 0.75, FY, 1.42), -math.pi / 2, height=0.28)
    model('fancy_picture_frame_01', (HW - 0.62, FY, 2.2), -math.pi / 2, width=0.9)
    for y in (FY - 1.4, FY + 1.4):
        box('sconce plate', HW - 0.04, HW, y - 0.06, y + 0.06, 1.7, 1.9, gold, 1.0, 0.01); rod('sconce arm', (HW - 0.02, y, 1.8), (HW - 0.25, y, 1.85), 0.012, gold)
        bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=False, segments=16, radius1=0.1, radius2=0.06, depth=0.14); obj_from_bm('sconce shade', bm, red_shade, True).location = (HW - 0.25, y, 1.95)
        light((HW - 0.3, y, 1.95), 30, (1.0, 0.45, 0.25), radius=0.06)
    # two red velvet armchairs facing the fire, a little table with a lamp between them
    def armchair(x, y, rot):
        g = group((x, y, 0), rot)
        for o in (box('chair base', -0.42, 0.42, -0.4, 0.4, 0.12, 0.45, velvet2, 1.0, 0.05), box('chair back', -0.42, 0.42, 0.25, 0.42, 0.45, 1.15, velvet2, 1.0, 0.06),
                  box('chair arm', -0.45, -0.3, -0.38, 0.42, 0.45, 0.72, velvet2, 1.0, 0.05), box('chair arm', 0.3, 0.45, -0.38, 0.42, 0.45, 0.72, velvet2, 1.0, 0.05)): kid(o, g)
        kid(pillow(0, -0.05, 0.5, 0.6, 0.6, 0.14, velvet2), g)
        for (dx, dy) in ((-0.36, -0.34), (0.36, -0.34), (-0.36, 0.36), (0.36, 0.36)): kid(cyl('chair leg', 0.025, 0.12, (dx, dy, 0.06), (0, 0, 0), gold, 10), g)
    armchair(HW - 2.0, FY - 1.1, math.radians(-125)); armchair(HW - 2.0, FY + 1.1, math.radians(-55))
    box('side table', HW - 2.25, HW - 1.85, FY - 0.2, FY + 0.2, 0.6, 0.64, dark, 1.0, 0.01); rod('side table leg', (HW - 2.05, FY, 0), (HW - 2.05, FY, 0.6), 0.04, gold)
    lamp(HW - 2.05, FY, 0.64, brass, red_shade, 0.38, 35)
    # front-right: a red chaise and a cabinet; front-left: a dressing chair; plants and candles on the floor
    box('chaise', HW - 0.9, HW - 0.15, -L + 0.4, -L + 2.0, 0.12, 0.45, velvet, 1.0, 0.05); box('chaise back', HW - 0.3, HW - 0.12, -L + 0.4, -L + 1.3, 0.45, 0.95, velvet, 1.0, 0.05)
    throw(HW - 0.85, HW - 0.25, -L + 1.0, -L + 1.6, 0.5, velvet2, 0.3)
    model('GothicCommode_01', (HW - 0.32, -0.9, 0), -math.pi / 2, width=1.1); candles_cluster(HW - 0.3, -0.7, 1.15, wax, 3, 0.9)
    model('potted_plant_02', (-HW + 0.45, -L + 0.5, 0), 0.4, height=0.9); model('potted_plant_02', (HW - 0.45, -2.4, 0), 1.0, height=0.8)
    candles_cluster(-0.8, -L + 0.4, 0.0, wax, 3, 1.2)
    # ------------------------------------------------------------ the rug, the door
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5); uvl = bm.loops.layers.uv.new()
    for f in bm.faces:
        for l in f.loops: l[uvl].uv = (l.vert.co.x + 0.5, l.vert.co.y + 0.5)
    o = obj_from_bm('rug', bm, rug); o.scale = (3.6, 5.2, 1); o.location = (0.3, -4.2, 0.007)
    box('door', -0.6, 0.6, -L - 0.02, -L + 0.04, 0.0, 2.2, dark, 1.0, 0.01); box('door frame', -0.72, 0.72, -L, -L + 0.08, 2.2, 2.34, gold, 1.0, 0.01)
    w = bpy.data.worlds.new('w'); bpy.context.scene.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0.3, 0.1, 0.08, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.04
    for y in (-2.0, -6.0):
        f = light((0, y, H - 0.4), 45, (1.0, 0.6, 0.38), kind='AREA'); f.data.size = 2.5

def walk_rects():
    R = [(-0.5, HW - 2.55, -L + 0.5, -0.65),               # the middle, between the bed and the armchairs
         (-HW + 0.5, HW - 1.0, -L + 0.5, -L + 1.3) if False else (-HW + 0.9, HW - 1.0, -L + 0.5, -6.3),   # the front
         (HW - 1.5, HW - 1.0, -6.3, -5.7), (-HW + 0.5, -0.5, -2.65, -0.6)]   # by the fire; behind the bed
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
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'; sc.view_settings.exposure = -0.1
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
    cfg.update(name='Red Room', glb='assets/rooms/redroom/redroom.glb', spawn=dict(x=-0.2, z=L - 0.7, yaw=-0.2), walk=walk_rects(), probe=False, tints=tints, floor='wood_floor_worn')
    cfg.setdefault('lights', [{'x': HW - 1.0, 'y': 0.6, 'z': 4.4, 'color': '#ff7a2e', 'power': 10, 'range': 6}, {'x': 0.4, 'y': 2.6, 'z': 3.8, 'color': '#ff9a5a', 'power': 9, 'range': 6},
                              {'x': 0.6, 'y': 1.9, 'z': 0.4, 'color': '#ff7a4a', 'power': 6, 'range': 4}, {'x': -1.5, 'y': 1.4, 'z': 4.6, 'color': '#ffb070', 'power': 6, 'range': 4}])
    cfg.setdefault('exposure', 0.95); cfg.setdefault('version', 1); cfg.setdefault('wallBoost', 1.0); cfg.setdefault('maxFlameLights', 10); cfg.setdefault('flameColor', '#ffa060')
    json.dump(cfg, open(cfgp, 'w'), indent=1)
    if a.render: sc.render.filepath = os.path.abspath(a.render); bpy.ops.render.render(write_still=True)
    if a.glb:
        keep = ('planks', 'rough_wood', 'wood_floor', 'wood_cabinet', 'stone', 'damask', 'rug', 'ivy')
        for im in bpy.data.images:
            if im.size[0] > 512 and not any(k in im.name for k in keep): im.scale(512, 512)
        bpy.ops.object.select_all(action='DESELECT')
        for o in list(sc.objects):
            if o.type == 'EMPTY' and o.instance_type == 'COLLECTION': o.select_set(True)
        if any(o.select_get() for o in sc.objects): bpy.ops.object.duplicates_make_real()
        bpy.ops.export_scene.gltf(filepath=os.path.abspath(a.glb), export_format='GLB', export_lights=False, export_cameras=False, export_apply=True, export_image_format='AUTO')

if __name__ == '__main__':
    main()
