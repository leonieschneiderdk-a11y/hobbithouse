"""Hobbit-house pantry, rebuilt as a real 3D room from the 'Pantry' image, made longer: the far end (y = 0) is the view in the
image (long wooden table with chairs and candles, shelves of jars all round), the near end (y = -L) is a prep area with
baskets of vegetables, sacks and herbs hanging from the beams.

    python blender/rooms/pantry.py --render docs/rooms/pantry.png --samples 96 --res 1600x900 --glb assets/rooms/pantry/pantry.glb
"""
import argparse, json, math, os, sys, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
import numpy as np
from mathutils import Vector, Matrix
from hero_room import A, pbr, flat, obj_from_bm, box_uv, box, cyl, torus, cut, model, light, candle
from kitchen import lantern, cabinet_run, leaf_cluster, group, kid, tex_mat, mat_alpha
from dining import spindle_chair, rod

W, L, H = 4.4, 10.0, 3.1
HW = W / 2
SD = 0.42                                  # shelf depth
rnd = random.Random(53)
CAMS = {'main': (0.1, -6.0, 1.6, 87, 0, 18), 'long': (0.05, -L + 0.45, 1.62, 86, 0, 17), 'back': (0.0, -0.6, 1.62, 86, 180, 17)}

def K(*p): return A('assets', 'rooms', 'pantry', *p)

# ---------------------------------------------------------------- jars and tins: thousands, one mesh, built with numpy
_JT = None
def jar_template(seg=10):
    """Unit jar: body 0..1 split in three bands (low / label / high), then a lid 1..1.13. Face tags: 0 body, 1 band, 2 lid."""
    global _JT
    if _JT: return _JT
    rings = [(0.0, 0.0, 0), (0.0, 1.0, 0), (0.35, 1.0, 0), (0.65, 1.0, 1), (1.0, 1.0, 0), (1.0, 0.0, 0)]
    lid = [(1.0, 1.06, 2), (1.13, 1.06, 2), (1.13, 0.0, 2)]
    V, F, T, idx = [], [], [], []
    def add_prof(prof):
        ids = []
        for z, r, tag in prof:
            if r == 0: ids.append(([len(V)], tag)); V.append((0.0, 0.0, z))
            else:
                ids.append((list(range(len(V), len(V) + seg)), tag))
                for k in range(seg): a = k / seg * 2 * math.pi; V.append((r * math.cos(a), r * math.sin(a), z))
        for j in range(len(ids) - 1):
            (a, _), (b, tag) = ids[j], ids[j + 1]
            for k in range(seg):
                k2 = (k + 1) % seg
                if len(a) == 1: F.append((a[0], b[k], b[k2]))
                elif len(b) == 1: F.append((a[k], a[k2], b[0])) if False else F.append((a[k2], a[k], b[0]))
                else: F.append((a[k], a[k2], b[k2], b[k]))
                T.append(tag)
    add_prof(rings); add_prof(lid)
    _JT = (np.array(V, np.float32), F, np.array(T)); return _JT

def canisters(name, items, mats, nfill):
    """items: (x, y, z, r, h, fill_idx, band_idx, lid_idx). mats: fills..., then band mats..., then lid mats... (indices already absolute)."""
    V, F, T = jar_template(); nv = len(V); N = len(items)
    P = np.array([(it[0], it[1], it[2]) for it in items], np.float32); S = np.array([(it[3], it[3], it[4]) for it in items], np.float32)
    verts = (P[:, None, :] + V[None, :, :] * S[:, None, :]).reshape(-1, 3)
    faces = [tuple(i * nv + v for v in f) for i in range(N) for f in F]
    me = bpy.data.meshes.new(name); me.from_pydata(verts.tolist(), [], faces); me.update()
    for m in mats: me.materials.append(m)
    fi = np.array([it[5] for it in items]); bi = np.array([it[6] for it in items]); li = np.array([it[7] for it in items])
    mi = np.where(T[None, :] == 0, fi[:, None], np.where(T[None, :] == 1, bi[:, None], li[:, None])).reshape(-1).astype(np.int32)
    me.polygons.foreach_set('material_index', mi); me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), bool))
    o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o); return o

ITEMS = []
NF, NB, NL = 12, 6, 4                     # number of fill, label-band and lid materials (set in build)
def stock_shelf(a0, a1, wall, inward, z, depth, along_x, max_h):
    """Fill one shelf with two rows of jars and tins (taller ones at the back)."""
    for row, (d, hmul) in enumerate(((depth * 0.32, 1.0), (depth * 0.72, 0.8))):
        u = a0 + rnd.uniform(0.0, 0.04)
        while u < a1 - 0.05:
            kind = rnd.random()
            if kind < 0.62: r, h = rnd.uniform(0.04, 0.065), rnd.uniform(0.12, 0.24)          # glass jar
            elif kind < 0.78: r, h = rnd.uniform(0.035, 0.05), rnd.uniform(0.08, 0.13)        # tin
            else: r, h = rnd.uniform(0.06, 0.08), rnd.uniform(0.1, 0.16)                      # crock
            h = min(h * hmul, max_h - 0.03); u += r
            if u > a1 - r: break
            if rnd.random() < 0.07: u += r + 0.03; continue
            w = wall + inward * (d + rnd.uniform(-0.02, 0.02))
            x, y = (u, w) if along_x else (w, u)
            if kind < 0.62: fi = rnd.choice((0, 0, 1, 1, 2, 2, 3, 3, 4, 6, 7, 7, 8, 9, 5)); bi = NF + rnd.randrange(1, NB) if rnd.random() < 0.25 else fi; li = NF + NB + rnd.randrange(0, NL)
            elif kind < 0.78: fi = NF - 2; bi = NF + rnd.randrange(0, NB); li = NF - 2
            else: fi = NF - 1; bi = NF - 1; li = NF + NB + 1
            ITEMS.append((x, y, z, r, h, fi, bi, li)); u += r + rnd.uniform(0.006, 0.02)

def shelving(a0, a1, wall, inward, z0, z1, along_x, wood, depth=SD, step=0.36, unit=0.92, baskets=True, lamps=()):
    """Floor-to-ceiling open shelving against a wall, stocked with jars and tins; baskets on the bottom shelf."""
    def bx(name, u0, u1, d0, d1, zz0, zz1):
        w0, w1 = wall + inward * d0, wall + inward * d1
        if along_x: return box(name, u0, u1, min(w0, w1), max(w0, w1), zz0, zz1, wood, 1.0, 0.004)
        return box(name, min(w0, w1), max(w0, w1), u0, u1, zz0, zz1, wood, 1.0, 0.004)
    bx('shelf back', a0, a1, 0.0, 0.02, z0, z1)
    n = max(1, round((a1 - a0) / unit)); uw = (a1 - a0) / n
    for i in range(n + 1): u = a0 + i * uw; bx('shelf upright', u - 0.025, u + 0.025, 0.0, depth, z0, z1)
    zs = [z0 + 0.12 + k * step for k in range(int((z1 - z0 - 0.15) / step) + 1)]
    for z in zs: bx('shelf board', a0, a1, 0.02, depth, z - 0.03, z)
    bx('shelf top', a0 - 0.03, a1 + 0.03, 0.0, depth + 0.05, z1, z1 + 0.06)
    for i in range(n):
        u0, u1 = a0 + i * uw + 0.03, a0 + (i + 1) * uw - 0.03
        for k, z in enumerate(zs):
            if k == 0 and baskets and z0 < 0.2:
                for j in range(max(1, int((u1 - u0) / 0.42))):
                    u = u0 + (j + 0.5) * (u1 - u0) / max(1, int((u1 - u0) / 0.42)); w = wall + inward * depth * 0.5
                    model('wicker_basket_02' if (i + j) % 2 else 'wicker_basket_01', (u, w, z) if along_x else (w, u, z), (0 if along_x else math.pi / 2) + rnd.uniform(-0.1, 0.1), width=0.36)
                continue
            if (i, k) in lamps:
                u = (u0 + u1) / 2; w = wall + inward * depth * 0.55
                lantern(u if along_x else w, w if along_x else u, z, 0.6, None, IRON, LGLASS, 18); continue
            stock_shelf(u0, u1, wall, inward, z, depth, along_x, step - 0.04)

IRON = LGLASS = None
def build():
    global IRON, LGLASS
    wood = pbr('oak_wood_planks', 'materials', (0.84, 0.62, 0.42), 0.8)                    # warm honey shelving
    cab = pbr('oak_wood_planks', 'materials', (0.78, 0.56, 0.37), 0.8)
    table_wood = pbr('wood_table_worn', 'materials', (0.62, 0.44, 0.3), 0.7)
    ceil = pbr('weathered_brown_planks', 'materials', (0.95, 0.66, 0.4), 0.9)
    beam = pbr('rough_wood', 'materials', (0.42, 0.3, 0.2), 0.9)
    floor = pbr('wood_floor_worn', 'materials', (0.6, 0.52, 0.44), 0.7, 1.0)
    plaster = pbr('clay_plaster', 'materials', (0.9, 0.76, 0.58), 1.0, 1.4)
    chair_wood = flat('chair wood', (0.12, 0.075, 0.045), 0.55)
    IRON = flat('iron', (0.03, 0.028, 0.026), 0.55, 0.35); LGLASS = flat('lantern glass', (1.0, 0.86, 0.66), 0.08, transmission=0.85)
    wax = flat('wax', (0.92, 0.88, 0.78), 0.45)
    ivy = mat_alpha('ivy', A('assets', 'rooms', 'kitchen', 'ivy.png'))
    # jar contents: tomato, honey, orange, pickles, beans, flour, jam, peach, olive, mustard, (tin), (crock)
    fills = [flat('jar tomato', (0.45, 0.06, 0.03), 0.08), flat('jar honey', (0.62, 0.32, 0.04), 0.06), flat('jar orange', (0.7, 0.28, 0.05), 0.15),
             flat('jar pickles', (0.16, 0.2, 0.05), 0.15), flat('jar beans', (0.26, 0.11, 0.05), 0.3), flat('jar flour', (0.8, 0.74, 0.62), 0.6),
             flat('jar jam', (0.22, 0.03, 0.06), 0.12), flat('jar peach', (0.78, 0.44, 0.18), 0.15), flat('jar olive', (0.22, 0.24, 0.1), 0.2),
             flat('jar mustard', (0.66, 0.5, 0.1), 0.2), flat('tin', (0.42, 0.38, 0.33), 0.28, 0.9), flat('crock', (0.38, 0.24, 0.14), 0.35)]
    bands = [flat('label cream', (0.6, 0.5, 0.36), 0.7), flat('label red', (0.5, 0.08, 0.05), 0.6), flat('label green', (0.16, 0.24, 0.12), 0.6),
             flat('label brown', (0.35, 0.2, 0.1), 0.6), flat('label blue', (0.12, 0.16, 0.28), 0.6), flat('label gold', (0.7, 0.5, 0.18), 0.5)]
    lids = [flat('lid brass', (0.7, 0.5, 0.22), 0.3, 1.0), flat('lid cloth', (0.6, 0.48, 0.34), 0.8), flat('lid iron', (0.08, 0.07, 0.06), 0.5, 0.6), flat('lid red', (0.45, 0.08, 0.06), 0.6)]
    # ------------------------------------------------------------ shell: plank floor, plaster walls, plank ceiling with beams
    box('floor', -HW - 0.3, HW + 0.3, -L - 0.3, 0.3, -0.12, 0.0, floor, 2.2)
    box('ceiling', -HW - 0.3, HW + 0.3, -L - 0.3, 0.3, H, H + 0.15, ceil, 1.6)
    for x0, x1, y0, y1 in ((-HW - 0.3, -HW, -L, 0), (HW, HW + 0.3, -L, 0), (-HW, HW, 0, 0.3), (-HW, HW, -L - 0.3, -L)):
        box('wall', x0, x1, y0, y1, 0.0, H, plaster, 1.8)
    for k in range(7):
        y = -0.6 - k * (L - 1.2) / 6; box('beam', -HW, HW, y - 0.12, y + 0.12, H - 0.24, H, beam, 1.2)
    for s in (-1, 1): box('purlin', s * 0.9 - 0.09, s * 0.9 + 0.09, -L, 0, H - 0.4, H - 0.24, beam, 1.2)
    # ------------------------------------------------------------ shelving: left wall full height, far wall, near wall either side of the door
    ZT = H - 0.1
    shelving(-L + 0.05, -0.05, -HW, 1, 0.0, ZT, False, wood, lamps={(2, 4), (7, 4)})
    shelving(-HW + SD, HW - 0.6, 0.0, -1, 0.0, ZT, True, wood, lamps={(2, 4)})
    shelving(-HW + SD, -0.75, -L, 1, 0.0, ZT, True, wood); shelving(0.75, HW - 0.6, -L, 1, 0.0, ZT, True, wood)
    # right wall: base cupboards with a worktop all along, open shelves above
    cabinet_run(HW - 0.58, HW, -L + 0.05, -0.05, '-x', cab, table_wood, flat('brass', (0.78, 0.55, 0.26), 0.3, 1.0), 0.55, 0.9)
    shelving(-L + 0.05, -0.05, HW, -1, 1.35, ZT, False, wood, 0.32, 0.36, 0.92, False, lamps={(3, 2), (8, 1)})
    for k in range(10):
        y = -L + 0.6 + k * (L - 1.2) / 9; x = HW - 0.3
        r = rnd.random()
        if r < 0.3: model('ceramic_pot', (x, y, 0.9), rnd.uniform(0, 6), width=0.3)
        elif r < 0.5: model('wicker_basket_02', (x, y, 0.9), math.pi / 2, width=0.34)
        elif r < 0.7: model('jug_01', (x, y, 0.9), rnd.uniform(0, 6), height=0.2)
        else: model('ceramic_vase_02', (x, y, 0.9), 0, height=0.2)
    # door in the near wall
    box('door', -0.6, 0.6, -L + 0.02, -L + 0.08, 0.0, 2.1, beam, 0.8); box('door frame', -0.72, 0.72, -L + 0.0, -L + 0.12, 2.1, 2.22, beam, 1.0)
    for sx in (-1, 1): box('door frame', sx * 0.66 - 0.06, sx * 0.66 + 0.06, -L + 0.0, -L + 0.12, 0.0, 2.1, beam, 1.0)
    # ------------------------------------------------------------ the far end: long table, chairs, candles, a plant underneath
    TX, TY0, TY1, TH = -0.15, -4.7, -1.2, 0.78
    box('table top', TX - 0.42, TX + 0.42, TY0, TY1, TH - 0.06, TH, table_wood, 1.3, 0.01)
    box('table apron', TX - 0.36, TX + 0.36, TY0 + 0.08, TY1 - 0.08, TH - 0.16, TH - 0.06, table_wood, 1.0)
    for y in (TY0 + 0.1, TY1 - 0.1):
        for sx in (-1, 1): box('table leg', TX + sx * 0.32 - 0.05, TX + sx * 0.32 + 0.05, y - 0.05, y + 0.05, 0.0, TH - 0.06, table_wood, 1.0, 0.01)
    box('table stretcher', TX - 0.04, TX + 0.04, TY0 + 0.15, TY1 - 0.15, 0.15, 0.22, table_wood, 1.0)
    for i in range(3):
        y = TY0 + 0.65 + i * (TY1 - TY0 - 1.3) / 2
        spindle_chair(TX - 0.62, y, math.pi / 2 + rnd.uniform(-0.1, 0.1), chair_wood); spindle_chair(TX + 0.62, y, -math.pi / 2 + rnd.uniform(-0.1, 0.1), chair_wood)
    model('potted_plant_02', (TX, (TY0 + TY1) / 2, 0), 0.4, height=0.55)
    for y in (-4.2, -3.4, -2.2, -1.6):
        h = rnd.uniform(0.1, 0.22); cyl('pillar candle', 0.04, h, (TX + rnd.uniform(-0.1, 0.1), y, TH + h / 2), (0, 0, 0), wax, 20); candle((TX, y, TH + h - 0.005), 0.01, 12)
    model('Lantern_01', (TX + 0.1, -2.8, TH), 0, height=0.24); candle((TX + 0.1, -2.8, TH + 0.03), 0.06, 10)
    model('potted_plant_04', (TX - 0.05, -3.0, TH), 0.5, height=0.3); leaf_cluster(ivy, TX, -3.0, TH + 0.25, 12, 0.2, 0.1)
    model('wooden_bowl_01', (TX, -3.85, TH), 0, width=0.34)
    for k in range(5): model(['food_apple_01', 'lemon', 'food_pears_asian_01'][k % 3], (TX + 0.06 * math.cos(k), -3.85 + 0.06 * math.sin(k), TH + 0.04), k, height=0.08)
    for y in (-4.45, -1.45): model('jug_01', (TX + 0.15, y, TH), 0.5, height=0.18)
    # pendant lanterns from the beams over the table
    for y in (-1.8, -3.0, -4.2): lantern(TX, y, 2.15, 1.1, H - 0.24, IRON, LGLASS, 55)
    # ------------------------------------------------------------ the near end: prep table, baskets of vegetables, sacks, hanging herbs
    PX, PY0, PY1 = -0.1, -8.6, -6.6
    box('prep top', PX - 0.45, PX + 0.45, PY0, PY1, 0.84, 0.92, table_wood, 1.2, 0.01)
    for y in (PY0 + 0.08, PY1 - 0.08):
        for sx in (-1, 1): box('prep leg', PX + sx * 0.37 - 0.05, PX + sx * 0.37 + 0.05, y - 0.05, y + 0.05, 0.0, 0.84, table_wood, 1.0)
    box('prep shelf', PX - 0.4, PX + 0.4, PY0 + 0.05, PY1 - 0.05, 0.2, 0.24, table_wood, 1.0)
    for k, y in enumerate((-8.3, -7.8, -7.3, -6.9)):
        model('wicker_basket_01', (PX, y, 0.92), rnd.uniform(-0.2, 0.2), width=0.38)
        produce = [('yellow_onion', 0.07), ('sweet_potato', 0.07), ('food_apple_01', 0.08), ('lemon', 0.08)][k]
        for j in range(5): model(produce[0], (PX + 0.07 * math.cos(j * 1.3), y + 0.05 * math.sin(j * 1.3), 0.96), j, height=produce[1])
    for y in (-8.2, -7.0): model('wicker_basket_02', (PX, y, 0.24), 0.3, width=0.4)
    model('wooden_cutting_board', (PX + 0.15, -7.6, 0.92), 0.3, width=0.4)
    sack = flat('sack', (0.62, 0.5, 0.34), 0.95)
    for x, y in ((-1.4, -9.3), (-1.0, -9.5), (1.0, -6.0)):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.26, location=(x, y, 0.3)); o = bpy.context.active_object; o.scale = (1, 0.9, 1.3); o.data.materials.append(sack)
        for p in o.data.polygons: p.use_smooth = True
        cyl('sack neck', 0.08, 0.12, (x, y, 0.68), (0, 0, 0), sack, 12)
    model('wine_barrel_01', (-1.45, -6.3, 0), 0.4, height=0.75); cyl('barrel lid', 0.3, 0.03, (-1.45, -6.3, 0.76), (0, 0, 0), table_wood, 32)
    model('wooden_crate_01', (1.2, -9.4, 0), 0.0, width=0.6); model('wooden_crate_01', (1.2, -9.4, 0.27), 0.1, width=0.58)
    # herbs and garlic hanging from the beams
    herb = flat('dried herb', (0.32, 0.3, 0.14), 0.9); garlic = flat('garlic', (0.62, 0.52, 0.42), 0.7)
    for k in range(14):
        y = -L + 0.9 + k * 0.62; x = rnd.choice((-0.9, 0.9)) + rnd.uniform(-0.2, 0.2)
        cyl('string', 0.004, 0.35, (x, y, H - 0.42), (0, 0, 0), herb, 4)
        if k % 2: leaf_cluster(ivy, x, y, H - 0.75, 8, 0.1, 0.25, (0.08, 0.16))
        else:
            for j in range(6):
                bpy.ops.mesh.primitive_uv_sphere_add(radius=0.035, segments=10, ring_count=6, location=(x + rnd.uniform(-0.04, 0.04), y + rnd.uniform(-0.04, 0.04), H - 0.62 - j * 0.06)); bpy.context.active_object.data.materials.append(garlic)
    for y in (-7.6, -9.0): lantern(PX, y, 2.15, 1.05, H - 0.24, IRON, LGLASS, 50)
    bulb = flat('bulb', (1, 0.8, 0.5), 1, emit=(1.0, 0.72, 0.4), strength=12)
    for k in range(7):
        y = -0.6 - k * (L - 1.2) / 6
        for x in (-1.5, -0.5, 0.5, 1.5):
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.025, location=(x, y - 0.13, H - 0.2)); bpy.context.active_object.data.materials.append(bulb)
            light((x, y - 0.13, H - 0.25), 8, radius=0.03)
    # ------------------------------------------------------------ all the jars and tins as one mesh
    canisters('pantry jars', ITEMS, fills + bands + lids, NF)
    w = bpy.data.worlds.new('w'); bpy.context.scene.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0.3, 0.2, 0.12, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.04
    for y in (-2.5, -7.5):
        f = light((0, y, 1.2), 90, (1.0, 0.66, 0.36), kind='AREA'); f.data.size = 2.0; f.rotation_euler = (0, 0, 0)

def walk_rects():
    R = [(-HW + SD + 0.3, -0.85, -L + 0.5, -0.75),      # left aisle
         (0.55, HW - 0.9, -L + 0.5, -0.75),             # right aisle
         (-HW + SD + 0.3, HW - 0.9, -L + 0.5, -L + 1.1),  # by the door
         (-HW + SD + 0.3, HW - 0.9, -6.3, -5.3),        # between the prep table and the dining table
         (-HW + SD + 0.3, HW - 0.9, -0.95, -0.75),
         (-0.5, 0.5, -L - 0.4, -L + 0.6)]                # the doorway
    return [[x0, x1, -y1, -y0] for x0, x1, y0, y1 in R]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--render', default=''); ap.add_argument('--samples', type=int, default=96); ap.add_argument('--res', default='1280x720')
    ap.add_argument('--glb', default=''); ap.add_argument('--cam', default='main')
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
    bpy.ops.wm.read_factory_settings(use_empty=True); build()
    for o in bpy.context.scene.objects:
        if o.type == 'LIGHT' and hasattr(o, 'visible_camera'): o.visible_camera = False
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = a.samples; sc.cycles.use_denoising = True; sc.cycles.max_bounces = 8
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'; sc.view_settings.exposure = 0.45
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
    cfg.update(name='Pantry', glb='assets/rooms/pantry/pantry.glb', spawn=dict(x=0.05, z=L - 0.6, yaw=0), walk=walk_rects(), lights=[], probe=[0, 1.4, 3.0], tints=tints, floor='wood_floor_worn')
    cfg.setdefault('exposure', 0.9); cfg.setdefault('version', 1); cfg.setdefault('wallBoost', 1.0); cfg.setdefault('maxFlameLights', 30); cfg.setdefault('flameColor', '#ffb070')
    json.dump(cfg, open(cfgp, 'w'), indent=1)
    if a.render: sc.render.filepath = os.path.abspath(a.render); bpy.ops.render.render(write_still=True)
    if a.glb:
        keep = ('planks', 'rough_wood', 'wood_floor', 'wood_cabinet', 'wood_table', 'plaster', 'ivy')
        for im in bpy.data.images:
            if im.size[0] > 512 and not any(k in im.name for k in keep): im.scale(512, 512)
        bpy.ops.object.select_all(action='DESELECT')
        for o in list(sc.objects):
            if o.type == 'EMPTY' and o.instance_type == 'COLLECTION': o.select_set(True)
        if any(o.select_get() for o in sc.objects): bpy.ops.object.duplicates_make_real()
        bpy.ops.export_scene.gltf(filepath=os.path.abspath(a.glb), export_format='GLB', export_lights=False, export_cameras=False, export_apply=True, export_image_format='JPEG', export_jpeg_quality=82)

if __name__ == '__main__':
    main()
