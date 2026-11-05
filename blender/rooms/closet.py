"""Hobbit-house parents' walk-in closet, rebuilt as a real 3D room from the 'Walk-in closet (parents)' image.
Blender axes: the back wall is at y = 0, the closet runs toward the camera to y = -L. Floor-to-ceiling wooden cabinetry
with lit cubbies all round (hanging clothes, folded stacks, boxes, shoes), a peaked plank ceiling with beams and an oval
skylight in the middle of the roof, framed in vines, a central island with drawers, plants and folded linens, a knit ottoman,
a dark kilim runner on pale stone.

    python blender/rooms/closet.py --render docs/rooms/closet.png --samples 96 --glb assets/rooms/closet/closet.glb
"""
import argparse, json, math, os, sys, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
from hero_room import A, pbr, flat, image_mat, obj_from_bm, box_uv, box, cyl, torus, cut, model, light, candle
from kitchen import leaf_cluster, group, kid, tex_mat, mat_alpha, arch_cutter_y, stone_arch
from bathroom import toilet
from hallway import pillow, blocks
from dining import rod

W, L, WALL_H, RIDGE = 5.2, 8.0, 2.9, 4.1
HW = W / 2
D = 0.5                                        # cabinet depth
rnd = random.Random(131)
SKY_Y, SKY_RX, SKY_RY = -3.8, 1.3, 1.0
CEILS = []
CAMS = {'main': (0.0, -L + 0.45, 1.55, 89, 0, 14)}
ITEMS = []                                     # (cx, cy, cz, sx, sy, sz, mat) boxes: clothes, boxes, shoes

def K(*p): return A('assets', 'rooms', 'closet', *p)

def put(along_x, u, w, d, z, su, sd, sz, m):
    """Add an item at position u along the wall, depth d from the wall plane w (w and d already signed)."""
    ITEMS.append((u, w + d, z + sz / 2, su, sd, sz, m) if along_x else (w + d, u, z + sz / 2, sd, su, sz, m))

def cabinetry(a0, a1, wall, inward, along_x, wood, glow, kinds, unit=0.8, top=2.75):
    """A run of tall wooden closet bays against a wall; each bay is 'hang', 'fold', 'shoe' or 'box'."""
    def bx(name, u0, u1, d0, d1, z0, z1, mat=wood, bev=0.004):
        w0, w1 = wall + inward * d0, wall + inward * d1
        if along_x: return box(name, u0, u1, min(w0, w1), max(w0, w1), z0, z1, mat, 1.0, bev)
        return box(name, min(w0, w1), max(w0, w1), u0, u1, z0, z1, mat, 1.0, bev)
    bx('closet back', a0, a1, 0.0, 0.03, 0.0, top + 0.15, wood, 0)
    n = max(1, round((a1 - a0) / unit)); uw = (a1 - a0) / n
    for i in range(n + 1):
        u = a0 + i * uw; bx('closet stile', u - 0.035, u + 0.035, 0.0, D, 0.0, top)
        bx('stile face', u - 0.05, u + 0.05, D - 0.02, D + 0.01, 0.0, top + 0.15)
    bx('closet plinth', a0, a1, 0.0, D, 0.0, 0.1); bx('closet crown', a0 - 0.03, a1 + 0.03, 0.0, D + 0.06, top, top + 0.15, wood, 0.01)
    for i in range(n):
        u0, u1 = a0 + i * uw + 0.04, a0 + (i + 1) * uw - 0.04; uc = (u0 + u1) / 2; kind = kinds[i % len(kinds)]
        def shelfz(z, lit=True):
            bx('closet shelf', u0, u1, 0.03, D - 0.02, z - 0.03, z)
            if lit: bx('shelf glow', u0 + 0.02, u1 - 0.02, D - 0.06, D - 0.04, z - 0.045, z - 0.03, glow, 0)
        w = wall
        if kind == 'hang':
            for z in (2.15, 2.5): shelfz(z)
            rail_u = (u0, u1)
            if along_x: rod('rail', (u0, w + inward * D * 0.5, 2.0), (u1, w + inward * D * 0.5, 2.0), 0.012, BRASS)
            else: rod('rail', (w + inward * D * 0.5, u0, 2.0), (w + inward * D * 0.5, u1, 2.0), 0.012, BRASS)
            m = int((u1 - u0) / 0.07)
            for j in range(m):
                uu = u0 + (j + 0.5) * (u1 - u0) / m; ln = rnd.choice((0.95, 1.0, 1.1, 0.7, 1.3))
                put(along_x, uu, w, inward * D * 0.5, 1.98 - ln, 0.025, 0.42, ln, rnd.choice(CLOTH_HANG))
            shelfz(0.55); fold_stack(along_x, u0, u1, w, inward, 0.55, 2, 0.3)
            fold_stack(along_x, u0, u1, w, inward, 2.15, 2, 0.28); box_row(along_x, u0, u1, w, inward, 2.5)
        elif kind == 'fold':
            zs = [0.45, 0.8, 1.15, 1.5, 1.85, 2.2, 2.5]
            for z in zs: shelfz(z)
            for z in zs[:-1]: fold_stack(along_x, u0, u1, w, inward, z, rnd.choice((2, 3)), 0.3)
            box_row(along_x, u0, u1, w, inward, 2.5)
        elif kind == 'shoe':
            zs = [0.35, 0.62, 0.89, 1.16, 1.43, 1.7, 2.2, 2.5]
            for z in zs: shelfz(z)
            for z in zs[:6]:
                m = int((u1 - u0) / 0.2)
                for j in range(m):
                    uu = u0 + (j + 0.5) * (u1 - u0) / m; col = rnd.choice(SHOES)
                    for k in (-1, 1): put(along_x, uu + k * 0.045, w, inward * 0.28, z, 0.075, 0.26, 0.09 + rnd.choice((0, 0, 0.05)), col)
            fold_stack(along_x, u0, u1, w, inward, 2.2, 2, 0.28); box_row(along_x, u0, u1, w, inward, 2.5)
        else:
            zs = [0.55, 1.05, 1.55, 2.05, 2.5]
            for z in zs: shelfz(z)
            for z in zs[:-1]: box_row(along_x, u0, u1, w, inward, z, 0.3)
            box_row(along_x, u0, u1, w, inward, 2.5)
        # drawers under hanging and folded bays
        if kind in ('hang', 'fold'):
            for k, (z0, z1) in enumerate(((0.12, 0.3), (0.31, 0.5))) if kind == 'hang' else []:
                bx('drawer', u0, u1, D - 0.04, D, z0, z1)
                bx('drawer pull', uc - 0.08, uc + 0.08, D, D + 0.02, (z0 + z1) / 2 - 0.01, (z0 + z1) / 2 + 0.01, BRASS, 0)
        # a few lights inside each bay
        p = (uc, wall + inward * (D - 0.12), 2.0) if along_x else (wall + inward * (D - 0.12), uc, 2.0)
        light(p, 5, (1.0, 0.72, 0.42), radius=0.08)

def fold_stack(along_x, u0, u1, w, inward, z, n, h):
    m = max(1, int((u1 - u0) / 0.32)); sw = (u1 - u0) / m
    for j in range(m):
        uu = u0 + (j + 0.5) * sw; col = rnd.choice(CLOTH_FOLD); zz = z
        for k in range(rnd.randint(3, 6)):
            t = rnd.uniform(0.035, 0.055)
            put(along_x, uu + rnd.uniform(-0.01, 0.01), w, inward * 0.25, zz, sw - 0.04, 0.32, t, col if rnd.random() < 0.6 else rnd.choice(CLOTH_FOLD)); zz += t
            if zz > z + h: break

def box_row(along_x, u0, u1, w, inward, z, h=0.22):
    m = max(1, int((u1 - u0) / 0.36)); sw = (u1 - u0) / m
    for j in range(m):
        if rnd.random() < 0.15: continue
        uu = u0 + (j + 0.5) * sw; bh = h * rnd.uniform(0.7, 1.0)
        put(along_x, uu, w, inward * 0.25, z, sw - 0.05, 0.36, bh, rnd.choice(BOXES))

BRASS = None; CLOTH_HANG = CLOTH_FOLD = SHOES = BOXES = None
def build():
    global BRASS, CLOTH_HANG, CLOTH_FOLD, SHOES, BOXES
    floor = pbr('monastery_stone_floor', 'materials', (1.0, 0.9, 0.76), 0.5, 0.8)
    plaster = pbr('clay_plaster', 'materials', (0.9, 0.76, 0.58), 1.0, 1.4)
    wood = pbr('wood_cabinet_worn_long', 'materials', (0.56, 0.38, 0.24), 0.75)
    ceil = pbr('weathered_brown_planks', 'materials', (0.62, 0.44, 0.3), 0.9)
    beam = pbr('rough_wood', 'materials', (0.42, 0.29, 0.18), 0.9)
    table_top = pbr('wood_table_worn', 'materials', (0.72, 0.56, 0.4), 0.7)
    BRASS = flat('brass', (0.78, 0.55, 0.26), 0.3, 1.0)
    glow = flat('shelf glow', (1, 0.8, 0.5), 1, emit=(1.0, 0.72, 0.4), strength=1.6)
    frame = flat('window frame', (0.3, 0.19, 0.1), 0.55); glass = flat('glass', (0.95, 0.97, 0.98), 0.02, transmission=1.0)
    ivy = mat_alpha('ivy', A('assets', 'rooms', 'kitchen', 'ivy.png'))
    runner = tex_mat('runner', K('runner_diff.jpg'), rough=0.95)
    knit = flat('ottoman knit', (0.42, 0.36, 0.3), 1.0)
    ceramic = flat('ceramic', (0.88, 0.86, 0.82), 0.12); seat_wood = flat('seat wood', (0.3, 0.18, 0.1), 0.4)
    CLOTH_HANG = [flat('cloth ' + n, c, 0.9) for n, c in (('cream', (0.5, 0.43, 0.33)), ('white', (0.6, 0.56, 0.5)), ('stone', (0.34, 0.3, 0.25)), ('taupe', (0.24, 0.19, 0.15)),
                                                         ('grey', (0.26, 0.26, 0.27)), ('navy', (0.08, 0.09, 0.15)), ('charcoal', (0.1, 0.1, 0.1)), ('camel', (0.45, 0.3, 0.16)))]
    CLOTH_FOLD = CLOTH_HANG[:4] + [flat('cloth knit', (0.4, 0.35, 0.29), 1.0), flat('cloth slate', (0.2, 0.21, 0.24), 0.9)]
    SHOES = [flat('leather brown', (0.24, 0.13, 0.07), 0.4), flat('leather black', (0.04, 0.035, 0.03), 0.35), flat('leather tan', (0.5, 0.3, 0.16), 0.45)]
    BOXES = [flat('box linen', (0.3, 0.24, 0.17), 0.9), flat('box leather', (0.2, 0.11, 0.06), 0.5), flat('box wicker', (0.38, 0.27, 0.14), 0.9)]
    # ------------------------------------------------------------ shell: pale stone floor, walls, a peaked plank ceiling with beams
    box('floor', -HW - 0.3, HW + 0.3, -L - 0.3, 0.3, -0.12, 0.0, floor, 1.6)
    for x0, x1 in ((-HW - 0.3, -HW), (HW, HW + 0.3)): box('side wall', x0, x1, -L, 0.0, 0.0, WALL_H + 0.2, plaster, 1.8)
    def gable(name, y, thick, sgn):
        bm = bmesh.new(); vs = [bm.verts.new(p) for p in ((-HW - 0.3, y, 0), (HW + 0.3, y, 0), (HW + 0.3, y, WALL_H), (0, y, RIDGE + 0.1), (-HW - 0.3, y, WALL_H))]
        bm.faces.new(vs); o = obj_from_bm(name, bm, plaster); s = o.modifiers.new('s', 'SOLIDIFY'); s.thickness = thick; s.offset = 1.0 if sgn > 0 else -1.0
        bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier='s'); box_uv(o, 1.8); return o
    back = gable('back wall', 0.0, 0.4, 1); front = gable('front wall', -L, 0.4, -1)
    for s in (-1, 1):
        bm = bmesh.new(); vs = [bm.verts.new(p) for p in ((s * (HW + 0.3), 0.3, WALL_H - 0.08), (0, 0.3, RIDGE), (0, -L - 0.3, RIDGE), (s * (HW + 0.3), -L - 0.3, WALL_H - 0.08))]
        bm.faces.new(vs if s > 0 else vs[::-1]); o = obj_from_bm('ceiling', bm, ceil); box_uv(o, 1.4)
        sl = o.modifiers.new('s', 'SOLIDIFY'); sl.thickness = 0.12; sl.offset = 1
        bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier='s'); CEILS.append(o)
    CEILS_ = None
    for k in range(7):
        y = -0.5 - k * (L - 1.0) / 6
        if abs(y - SKY_Y) < SKY_RY + 0.2: continue
        for s in (-1, 1):
            a_ = math.atan2(RIDGE - WALL_H, HW); ln = math.hypot(HW, RIDGE - WALL_H)
            b = box('rafter', -ln / 2, ln / 2, y - 0.09, y + 0.09, -0.2, 0.0, beam, 1.2); b.rotation_euler = (0, a_ if s > 0 else -a_, 0); b.location = (s * HW / 2, 0, (WALL_H + RIDGE) / 2 - 0.02)
        box('collar tie', -HW + 0.5, HW - 0.5, y - 0.08, y + 0.08, WALL_H + 0.35, WALL_H + 0.5, beam, 1.2)
    for y0, y1 in ((-L, SKY_Y - SKY_RY), (SKY_Y + SKY_RY, 0.0)): box('ridge beam', -0.12, 0.12, y0, y1, RIDGE - 0.28, RIDGE - 0.04, beam, 1.2)
    for s in (-1, 1): box('wall plate', s * HW - 0.2, s * HW + 0.2, -L, 0.0, WALL_H - 0.2, WALL_H, beam, 1.2)
    # ------------------------------------------------------------ the oval skylight window high in the back wall, with mountains and vines
    # the oval skylight in the middle of the roof, framed in vines, with the mountains and sky above
    for o in CEILS:
        c = cyl('c', 1.0, 3.0, (0, SKY_Y, RIDGE), (0, 0, 0), ceil, 64); c.scale = (SKY_RX, SKY_RY, 1); bpy.context.view_layer.update(); cut(o, [c])
    zc = RIDGE - 0.15
    for z in (zc - 0.12, zc + 0.12):
        t = torus('skylight frame', 1.0, 0.07, (0, SKY_Y, z), (0, 0, 0), frame); t.scale = (SKY_RX, SKY_RY, 1)
    box('skylight curb', -SKY_RX, SKY_RX, SKY_Y - 0.035, SKY_Y + 0.035, zc + 0.3, zc + 0.38, frame, 1.0)
    for x in (-SKY_RX * 0.5, SKY_RX * 0.5): box('skylight bar', x - 0.03, x + 0.03, SKY_Y - SKY_RY * 0.87, SKY_Y + SKY_RY * 0.87, zc + 0.3, zc + 0.36, frame, 1.0)
    g = cyl('glass', 1.0, 0.01, (0, SKY_Y, zc + 0.4), (0, 0, 0), glass, 64); g.scale = (SKY_RX, SKY_RY, 1)
    shaft = cyl('skylight shaft', 1.06, 0.55, (0, SKY_Y, zc + 0.15), (0, 0, 0), ceil, 64); shaft.scale = (SKY_RX, SKY_RY, 1)
    sc_ = cyl('c', 1.0, 0.8, (0, SKY_Y, zc + 0.15), (0, 0, 0), ceil, 64); sc_.scale = (SKY_RX - 0.04, SKY_RY - 0.04, 1); bpy.context.view_layer.update(); cut(shaft, [sc_])
    a = light((0, SKY_Y, zc + 0.6), 700, (0.85, 0.92, 1.0), kind='AREA'); a.data.shape = 'ELLIPSE'; a.data.size = SKY_RX * 2; a.data.size_y = SKY_RY * 2
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1); bmesh.ops.scale(bm, vec=(30, 13, 1), verts=bm.verts)
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 4, 'X'))
    view = obj_from_bm('valley view', bm, image_mat('view', A('assets', 'rooms', 'kitchen', 'view.jpg'), 1.1)); uvl = view.data.uv_layers.new()
    for i, l in enumerate(uvl.data): co = view.data.vertices[view.data.loops[i].vertex_index].co; l.uv = (co.x / 30 + 0.5, 0.42 + (co.z / 13 + 0.5) * 0.58)
    view.location = (0, SKY_Y + 10, RIDGE + 7.0); view.rotation_euler = (math.radians(-35), 0, 0)
    sky = box('sky', -30, 30, -30, 30, RIDGE + 11, RIDGE + 11.1, flat('sky', (0.45, 0.62, 0.85), 1, emit=(0.45, 0.62, 0.85), strength=1.2), 40.0)
    for k in range(30):
        a_ = k / 30 * 2 * math.pi; leaf_cluster(ivy, math.cos(a_) * (SKY_RX + 0.15), SKY_Y + math.sin(a_) * (SKY_RY + 0.15), zc - 0.2, 9, 0.22, 0.7 if k % 3 == 0 else 0.25)
    # ------------------------------------------------------------ cabinetry all round
    cabinetry(-HW + 0.05, HW - 0.05, 0.0, -1, True, wood, glow, ['fold', 'hang', 'hang', 'fold'], unit=1.27)       # back wall
    WC_Y = -L + 1.55                                                                                                 # water closet at the front left
    cabinetry(-L + 0.05, -0.55, -HW, 1, False, wood, glow, ['shoe', 'fold', 'hang', 'hang', 'fold', 'box', 'fold', 'shoe'], unit=0.85) if False else None
    cabinetry(-L + 0.05, -D - 0.05, -HW, 1, False, wood, glow, ['fold', 'hang', 'shoe', 'fold', 'hang', 'box', 'fold', 'hang', 'shoe'], unit=0.82)
    cabinetry(-L + 0.05, -D - 0.05, HW, -1, False, wood, glow, ['shoe', 'fold', 'hang', 'fold', 'box', 'hang', 'fold', 'shoe', 'fold'], unit=0.82)
    blocks('closet contents', ITEMS, CLOTH_HANG + CLOTH_FOLD[4:] + SHOES + BOXES) if False else None
    mats = []
    for it in ITEMS:
        if it[6] not in mats: mats.append(it[6])
    blocks('closet contents', [it[:6] + (mats.index(it[6]),) for it in ITEMS], mats)
    # ------------------------------------------------------------ the island with drawers, plants and folded linens; the runner and the ottoman
    IX, IY0, IY1, IH = 0.0, -5.2, -2.4, 0.95
    box('island', IX - 0.55, IX + 0.55, IY0, IY1, 0.1, IH - 0.06, wood, 1.0, 0.01)
    box('island plinth', IX - 0.5, IX + 0.5, IY0 + 0.05, IY1 - 0.05, 0.0, 0.1, wood, 1.0)
    box('island top', IX - 0.62, IX + 0.62, IY0 - 0.07, IY1 + 0.07, IH - 0.06, IH, table_top, 1.2, 0.01)
    n = 4; u = (IY1 - IY0) / n
    for sgn in (-1, 1):
        for i in range(n):
            c = IY0 + (i + 0.5) * u
            for z0, z1 in ((0.15, 0.45), (0.5, IH - 0.12)):
                box('island drawer', IX + sgn * 0.55 - (0.02 if sgn > 0 else 0.0), IX + sgn * 0.55 + (0.0 if sgn > 0 else 0.02), c - u / 2 + 0.03, c + u / 2 - 0.03, z0, z1, wood, 1.0, 0.006)
                box('island pull', IX + sgn * 0.57 - 0.01, IX + sgn * 0.57 + 0.01, c - 0.08, c + 0.08, (z0 + z1) / 2 - 0.012, (z0 + z1) / 2 + 0.012, BRASS, 1.0)
    for z0, z1 in ((0.15, 0.45), (0.5, IH - 0.12)):
        for yf, sg in ((IY0, -1), (IY1, 1)): box('island end panel', IX - 0.45, IX + 0.45, yf + sg * 0.0 - (0.02 if sg < 0 else 0), yf + (0.02 if sg > 0 else 0), z0, z1, wood, 1.0, 0.006)
    for y in (IY0 + 0.45, IY1 - 0.45):
        model('planter_pot_clay', (IX, y, IH), 0, height=0.22); leaf_cluster(ivy, IX, y, IH + 0.4, 18, 0.22, 0.1, (0.12, 0.24))
    for k, col in enumerate((CLOTH_HANG[0], CLOTH_HANG[2], CLOTH_FOLD[4])):
        box('folded linen', IX - 0.3, IX + 0.3, -3.95 + k * 0.03, -3.45 + k * 0.03, IH + k * 0.05, IH + 0.05 + k * 0.05, col, 1.0, 0.012)
    box('folded linen', IX - 0.25, IX + 0.25, -4.55, -4.15, IH, IH + 0.08, CLOTH_HANG[5], 1.0, 0.012)
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5); uvl = bm.loops.layers.uv.new()
    for f in bm.faces:
        for l in f.loops: l[uvl].uv = (l.vert.co.x + 0.5, l.vert.co.y + 0.5)
    o = obj_from_bm('runner', bm, runner); o.scale = (2.0, 6.2, 1); o.location = (0.0, -4.0, 0.007)
    pillow(0.0, -5.95, 0.24, 1.0, 0.55, 0.42, knit)
    for (x, y) in ((-0.4, -6.15), (0.4, -6.15), (-0.4, -5.75), (0.4, -5.75)): cyl('ottoman leg', 0.03, 0.06, (x, y, 0.03), (0, 0, 0), wood, 10)
    # pendant over the island and soft fill
    lt = flat('lamp shade', (0.95, 0.82, 0.6), 0.8, emit=(1.0, 0.75, 0.45), strength=3)
    for y in (-2.4, -5.3):
        cyl('pendant cord', 0.006, RIDGE - 0.3 - 2.55, (0, y, (RIDGE - 0.3 + 2.55) / 2), (0, 0, 0), BRASS, 6)
        bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=False, segments=24, radius1=0.2, radius2=0.06, depth=0.2); obj_from_bm('pendant shade', bm, lt, True).location = (0, y, 2.5)
        light((0, y, 2.38), 55, radius=0.1)
    w = bpy.data.worlds.new('w'); bpy.context.scene.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0.4, 0.42, 0.45, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.05
    for y in (-2.0, -5.5):
        f = light((0, y, WALL_H), 70, (1.0, 0.72, 0.45), kind='AREA'); f.data.size = 2.0

def walk_rects():
    R = [(-HW + D + 0.3, -0.85, -L + 0.4, -D - 0.35),           # left aisle
         (0.85, HW - D - 0.3, -L + 0.4, -D - 0.35),             # right aisle
         (-HW + D + 0.3, HW - D - 0.3, -2.25, -D - 0.35),        # behind the island
         (-HW + D + 0.3, HW - D - 0.3, -L + 0.4, -6.35),   # the front, by the ottoman
         (-HW + 1.45, 0.85, -5.45, -5.3) if False else (-1.3, -0.85, -6.35, -5.3),
         ]
    return [[x0, x1, -y1, -y0] for x0, x1, y0, y1 in R]
WC_Y_W = -L + 1.55

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--render', default=''); ap.add_argument('--samples', type=int, default=96); ap.add_argument('--res', default='1600x900')
    ap.add_argument('--glb', default=''); ap.add_argument('--cam', default='main')
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
    bpy.ops.wm.read_factory_settings(use_empty=True); build()
    for o in bpy.context.scene.objects:
        if o.type == 'LIGHT' and hasattr(o, 'visible_camera'): o.visible_camera = False
        if o.type == 'LIGHT' and hasattr(o, 'visible_transmission'): o.visible_transmission = False
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = a.samples; sc.cycles.use_denoising = True; sc.cycles.max_bounces = 8
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'; sc.view_settings.exposure = 0.1
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
    cfg.update(name="Parents' Walk-in Closet", glb='assets/rooms/closet/closet.glb', spawn=dict(x=0.9, z=L - 0.6, yaw=0.05), walk=walk_rects(), probe=False, tints=tints, floor='monastery_stone_floor')
    cfg.setdefault('lights', [{'x': 0, 'y': 3.2, 'z': 0.8, 'color': '#ffe8d0', 'power': 8, 'range': 6}, {'x': -1.9, 'y': 2.0, 'z': 4.0, 'color': '#ffb877', 'power': 9, 'range': 5},
                              {'x': 1.9, 'y': 2.0, 'z': 4.0, 'color': '#ffb877', 'power': 9, 'range': 5}, {'x': 0, 'y': 2.4, 'z': 3.8, 'color': '#ffb877', 'power': 8, 'range': 5},
                              {'x': 1.9, 'y': 2.0, 'z': 7.0, 'color': '#ffb877', 'power': 8, 'range': 5}, {'x': -1.9, 'y': 2.0, 'z': 6.2, 'color': '#ffb877', 'power': 6, 'range': 4}])
    cfg.setdefault('exposure', 0.9); cfg.setdefault('version', 1); cfg.setdefault('wallBoost', 1.0); cfg.setdefault('maxFlameLights', 4); cfg.setdefault('flameColor', '#ffb877')
    json.dump(cfg, open(cfgp, 'w'), indent=1)
    if a.render: sc.render.filepath = os.path.abspath(a.render); bpy.ops.render.render(write_still=True)
    if a.glb:
        keep = ('stone', 'plaster', 'planks', 'rough_wood', 'wood_cabinet', 'wood_table', 'view', 'ivy', 'runner')
        for im in bpy.data.images:
            if im.size[0] > 512 and not any(k in im.name for k in keep): im.scale(512, 512)
        bpy.ops.object.select_all(action='DESELECT')
        for o in list(sc.objects):
            if o.type == 'EMPTY' and o.instance_type == 'COLLECTION': o.select_set(True)
        if any(o.select_get() for o in sc.objects): bpy.ops.object.duplicates_make_real()
        bpy.ops.export_scene.gltf(filepath=os.path.abspath(a.glb), export_format='GLB', export_lights=False, export_cameras=False, export_apply=True, export_image_format='AUTO')

if __name__ == '__main__':
    main()
