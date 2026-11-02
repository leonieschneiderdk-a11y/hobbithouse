"""Hobbit-house baby room, rebuilt as a real 3D room from the 'Baby room' image.
Blender axes: the round window with its window seat is in the back wall at y = 0, the room runs toward the camera to
y = -L. Left: a cream painted dresser with ornaments, wall shelves and a sconce. Right: the wooden crib under a sheer
canopy, a table lamp and shelves of toys. Floor: wide boards, fluffy sheepskins, a rocking sheep, baskets and a pouf.

    python blender/rooms/nursery.py --render docs/rooms/nursery.png --samples 96 --glb assets/rooms/nursery/nursery.glb
"""
import argparse, json, math, os, sys, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
from hero_room import A, pbr, flat, image_mat, obj_from_bm, box_uv, box, cyl, torus, cut, sweep_profile, model, light, candle
from kitchen import cabinet_run, leaf_cluster, group, kid, tex_mat, mat_alpha, shelf
from hallway import pillow
from dining import rod

W, L = 4.8, 5.6
HW = W / 2
WALL_H, APEX = 1.9, 3.5
rnd = random.Random(101)
CAMS = {'main': (0.1, -L + 0.4, 1.5, 85, 0, 16)}
WX, WZ, WR = -0.15, 1.45, 0.95                       # round window centre and radius

def K(*p): return A('assets', 'rooms', 'nursery', *p)

def vault_z(x, inset=0.0):
    t = max(-1.0, min(1.0, x / (HW - inset)))
    return WALL_H + math.sqrt(max(0.0, 1 - t * t)) * (APEX - WALL_H - inset)

def profile(n=40, inset=0.0):
    pts = [(-HW + inset, 0.0)]
    for i in range(n + 1):
        a = math.pi - i / n * math.pi
        pts.append((math.cos(a) * (HW - inset), WALL_H + math.sin(a) * (APEX - WALL_H - inset)))
    pts.append((HW - inset, 0.0)); return pts

def curtain(name, pts, z0, z1, mat, folds=0.06, freq=14):
    """A gathered drape hanging from a polyline pts (x, y) between heights z0 (bottom) and z1 (top)."""
    bm = bmesh.new(); n = 40; rows = []
    tot = sum((Vector(b) - Vector(a)).length for a, b in zip(pts, pts[1:])); seg = []
    for a, b in zip(pts, pts[1:]): seg.append((Vector(a), Vector(b), (Vector(b) - Vector(a)).length))
    def at(t):
        d = t * tot
        for a, b, l in seg:
            if d <= l or (a, b, l) == seg[-1]: return a + (b - a) * min(1.0, d / max(l, 1e-6)), (b - a).normalized()
            d -= l
    for j, z in enumerate((z0, (z0 + z1) / 2, z1)):
        row = []
        for i in range(n + 1):
            t = i / n; p, d = at(t); nrm = Vector((-d.y, d.x)); off = math.sin(t * freq * math.pi) * folds * (1.0 if j < 2 else 0.4)
            row.append(bm.verts.new((p.x + nrm.x * off, p.y + nrm.y * off, z)))
        rows.append(row)
    for j in range(2):
        for i in range(n): bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
    o = obj_from_bm(name, bm, mat, True); return o

def crib(x0, x1, y0, y1, wood, mattress, sheet):
    h, rail = 0.95, 0.04
    for x in (x0, x1):
        for y in (y0, y1): box('crib post', x - 0.03, x + 0.03, y - 0.03, y + 0.03, 0.0, h + 0.08, wood, 1.0, 0.01)
    for z in (0.32, h - 0.03):
        for y in (y0, y1): box('crib rail', x0, x1, y - 0.02, y + 0.02, z - rail / 2, z + rail / 2, wood, 1.0)
        for x in (x0, x1): box('crib rail', x - 0.02, x + 0.02, y0, y1, z - rail / 2, z + rail / 2, wood, 1.0)
    for y in (y0, y1):
        n = int((x1 - x0) / 0.075)
        for k in range(1, n): x = x0 + k * (x1 - x0) / n; cyl('crib spindle', 0.011, h - 0.35, (x, y, (h + 0.32) / 2), (0, 0, 0), wood, 8)
    for x in (x0, x1):
        n = int((y1 - y0) / 0.075)
        for k in range(1, n): y = y0 + k * (y1 - y0) / n; cyl('crib spindle', 0.011, h - 0.35, (x, y, (h + 0.32) / 2), (0, 0, 0), wood, 8)
    pillow((x0 + x1) / 2, (y0 + y1) / 2, 0.4, x1 - x0 - 0.06, y1 - y0 - 0.06, 0.12, mattress)
    pillow((x0 + x1) / 2, (y0 + y1) / 2 - 0.1, 0.48, x1 - x0 - 0.1, (y1 - y0) * 0.6, 0.05, sheet)
    pillow((x0 + x1) / 2, y1 - 0.2, 0.5, 0.36, 0.22, 0.08, sheet)

def rocking_sheep(x, y, rot, fleece, wood):
    g = group((x, y, 0), rot)
    def blob(loc, scale, mat):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=loc, segments=24, ring_count=14); o = bpy.context.active_object; o.scale = scale; o.data.materials.append(mat)
        for p in o.data.polygons: p.use_smooth = True
        kid(o, g); return o
    blob((0, 0, 0.42), (0.18, 0.3, 0.16), fleece)
    blob((0, 0.32, 0.6), (0.1, 0.12, 0.11), fleece)
    for s in (-1, 1): blob((s * 0.1, 0.32, 0.66), (0.06, 0.025, 0.035), fleece)
    for sx in (-1, 1):
        for sy in (-1, 1): kid(cyl('sheep leg', 0.03, 0.2, (sx * 0.1, sy * 0.17, 0.2), (0, 0, 0), fleece, 10), g)
    for sx in (-1, 1):                                        # the rockers
        pts = [(sx * 0.12, -0.4 + k * 0.08, 0.06 + 0.12 * ((-0.4 + k * 0.08) / 0.4) ** 2) for k in range(11)]
        for a, b in zip(pts, pts[1:]): kid(rod('rocker', a, b, 0.022, wood, 10), g)
    for sy in (-0.25, 0.25): kid(rod('rocker bar', (-0.12, sy, 0.1), (0.12, sy, 0.1), 0.015, wood), g)
    return g

def build():
    floor = pbr('wood_floor_worn', 'materials', (0.86, 0.66, 0.46), 0.6, 1.0)
    plaster = pbr('clay_plaster', 'materials', (1.06, 0.97, 0.84), 1.0, 1.4)
    rib = pbr('rough_wood', 'materials', (0.42, 0.3, 0.2), 0.9)
    timber = pbr('dark_wooden_planks', 'materials', (0.52, 0.36, 0.22), 0.9)
    light_wood = pbr('oak_wood_planks', 'materials', (1.0, 0.82, 0.62), 0.8)
    paint = flat('cream paint', (0.78, 0.7, 0.56), 0.55); brass = flat('brass', (0.78, 0.55, 0.26), 0.3, 1.0)
    sheer = flat('sheer curtain', (0.96, 0.9, 0.8), 0.8)
    sheer.node_tree.nodes['Principled BSDF'].inputs['Alpha'].default_value = 0.42
    for attr, val in (('blend_method', 'BLEND'), ('surface_render_method', 'BLENDED')):
        try: setattr(sheer, attr, val)
        except Exception: pass
    linen = flat('cushion linen', (0.8, 0.72, 0.6), 0.9); mattress = flat('mattress', (0.9, 0.86, 0.8), 0.9); sheet = flat('blanket', (0.92, 0.88, 0.82), 0.95)
    fleece = flat('fleece', (0.56, 0.46, 0.36), 1.0); plush = flat('plush', (0.85, 0.8, 0.72), 0.95); pink = flat('pouf rose', (0.42, 0.24, 0.24), 0.9)
    frame = flat('window frame', (0.55, 0.4, 0.26), 0.55); glass = flat('glass', (0.95, 0.97, 0.98), 0.02, transmission=1.0)
    iron = flat('iron', (0.03, 0.028, 0.026), 0.55, 0.35); wax = flat('wax', (0.92, 0.88, 0.78), 0.45)
    skin = mat_alpha('sheepskin', K('sheepskin.png'), 1.0)
    ivy = mat_alpha('ivy', A('assets', 'rooms', 'kitchen', 'ivy.png'))
    toyc = [flat('toy cream', (0.85, 0.78, 0.66), 0.8), flat('toy tan', (0.6, 0.45, 0.3), 0.8), flat('toy blue', (0.4, 0.5, 0.6), 0.6), flat('toy pink', (0.8, 0.56, 0.56), 0.7)]
    # ------------------------------------------------------------ shell: wide boards, cream plaster barrel vault, dark timber ribs
    box('floor', -HW - 0.3, HW + 0.3, -L - 0.3, 0.3, -0.12, 0.0, floor, 2.2)
    prof = profile()
    bm = bmesh.new(); r0 = [bm.verts.new((x, 0.0, z)) for x, z in prof]; r1 = [bm.verts.new((x, -L, z)) for x, z in prof]
    for i in range(len(prof) - 1): bm.faces.new((r0[i + 1], r0[i], r1[i], r1[i + 1]))
    shell = obj_from_bm('vault', bm, plaster, True); box_uv(shell, 2.0)
    sol = shell.modifiers.new('s', 'SOLIDIFY'); sol.thickness = 0.3; sol.offset = 1
    def end_wall(name, y, thick, sgn):
        bm = bmesh.new(); vs = [bm.verts.new((x, y, z)) for x, z in prof]; bm.faces.new(vs); w = obj_from_bm(name, bm, plaster)
        s = w.modifiers.new('s', 'SOLIDIFY'); s.thickness = thick; s.offset = 1.0 if sgn > 0 else -1.0
        bpy.context.view_layer.objects.active = w; bpy.ops.object.modifier_apply(modifier='s'); return w
    back = end_wall('back wall', 0.0, 0.45, 1); front = end_wall('front wall', -L, 0.4, -1)
    rp = profile(40, 0.03)[1:-1]
    for y in (-0.3, -1.9, -3.5, -L + 0.3): sweep_profile('rib', [(prof[1][0] + 0.03, 0.0)] + rp + [(prof[-2][0] - 0.03, 0.0)], y, 0.24, 0.26, rib)
    for s in (-1, 1): box('wall post', s * HW - (0.12 if s > 0 else -0.12) - 0.12, s * HW - (0.12 if s > 0 else -0.12) + 0.12, -0.42, -0.18, 0.0, WALL_H, rib, 1.2)
    # ------------------------------------------------------------ the round window with a deep sill seat, cushions and sheer curtains
    cut(back, [cyl('c', WR, 1.4, (WX, 0.2, WZ), (math.pi / 2, 0, 0), plaster, 64)]); box_uv(back, 2.0)
    g = group((WX, 0.25, WZ))
    kid(torus('round window frame', WR - 0.04, 0.05, (0, 0, 0), (math.pi / 2, 0, 0), frame), g)
    kid(box('mullion', -0.03, 0.03, -0.03, 0.03, -WR, WR, frame, 1.0), g)
    for z in (-0.35, 0.2): hz = math.sqrt(max(0, (WR - 0.04) ** 2 - z * z)); kid(box('transom', -hz, hz, -0.03, 0.03, z - 0.02, z + 0.02, frame, 1.0), g)
    for x in (-WR * 0.5, WR * 0.5): hz = math.sqrt(WR * WR - x * x) - 0.04; kid(box('mullion', x - 0.02, x + 0.02, -0.03, 0.03, -hz, hz, frame, 1.0), g)
    kid(cyl('glass', WR - 0.04, 0.01, (0, 0, 0), (math.pi / 2, 0, 0), glass, 64), g)
    t = torus('window reveal', WR + 0.06, 0.12, (WX, 0.05, WZ), (math.pi / 2, 0, 0), plaster); t.scale = (1, 1, 2.4)
    a = light((WX, 1.6, WZ + 0.5), 700, (0.9, 0.95, 0.85), kind='AREA'); a.data.size = WR * 2; a.rotation_euler = (math.radians(90), 0, 0)
    box('window seat', WX - 1.2, WX + 1.2, -0.62, 0.05, 0.0, 0.5, light_wood, 1.0, 0.01)
    for k in range(3): box('seat panel', WX - 1.1 + k * 0.75, WX - 0.45 + k * 0.75, -0.635, -0.62, 0.08, 0.42, light_wood, 1.0, 0.004)
    pillow(WX, -0.3, 0.56, 2.3, 0.6, 0.1, linen)
    for dx, sx in ((-0.85, 0.42), (0.75, 0.4)): pillow(WX + dx, -0.15, 0.82, sx, 0.14, 0.4, linen).rotation_euler = (math.radians(12), 0, 0)
    model('wooden_bowl_02', (WX + 0.1, -0.35, 0.62), 0, width=0.16)
    for s in (-1, 1): curtain('curtain', [(WX + s * (WR + 0.15), -0.25), (WX + s * (WR + 0.55), -0.3)], 0.5, WZ + WR + 0.2, sheer, 0.05, 6)
    box('curtain rod', WX - WR - 0.7, WX + WR + 0.7, -0.3, -0.27, WZ + WR + 0.2, WZ + WR + 0.23, brass, 1.0)
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1); bmesh.ops.scale(bm, vec=(30, 19, 1), verts=bm.verts)
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 4, 'X')); bmesh.ops.translate(bm, vec=(WX, 12, 3.0), verts=bm.verts)
    view = obj_from_bm('garden view', bm, image_mat('view', A('assets', 'rooms', 'dining', 'view.jpg'), 1.0)); uvl = view.data.uv_layers.new()
    for i, l in enumerate(uvl.data): co = view.data.vertices[view.data.loops[i].vertex_index].co; l.uv = ((co.x - WX) / 30 + 0.5, (co.z - 3.0) / 19 + 0.5)
    model('potted_plant_02', (WX - 1.5, -0.5, 0), 0.4, height=0.95)
    # ------------------------------------------------------------ left: cream dresser with ornaments, wall shelves, a sconce
    cabinet_run(-HW, -HW + 0.55, -3.9, -1.6, '+x', paint, light_wood, brass, 0.58, 0.92)
    box('dresser top', -HW, -HW + 0.6, -3.95, -1.55, 0.92, 0.96, light_wood, 1.0, 0.01)
    for k, (y, nm, h) in enumerate(((-1.85, 'ceramic_vase_02', 0.2), (-2.35, 'Lantern_01', 0.24), (-3.2, 'potted_plant_04', 0.3), (-3.65, 'brass_vase_02', 0.2))):
        model(nm, (-HW + 0.3, y, 0.96), 0.3, height=h)
    candle((-HW + 0.3, -2.35, 0.99), 0.06, 8)
    for y, h in ((-2.75, 0.12), (-2.9, 0.18)): cyl('pillar candle', 0.035, h, (-HW + 0.32, y, 0.96 + h / 2), (0, 0, 0), wax, 20); candle((-HW + 0.32, y, 0.96 + h - 0.005), 0.01, 8)
    for k in range(3):                                        # little toys on the dresser
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.05, location=(-HW + 0.28, -2.05 - k * 0.12, 1.01)); bpy.context.active_object.data.materials.append(toyc[k])
    for z in (1.45, 1.85, 2.2):
        shelf(-HW, -HW + 0.28, -3.6, -1.85, z, light_wood)
        for k in range(5): model(rnd.choice(('ceramic_vase_04', 'brass_vase_02', 'ceramic_vase_03', 'wooden_bowl_02')), (-HW + 0.14, -3.45 + k * 0.38, z), rnd.uniform(0, 6), height=rnd.uniform(0.1, 0.18))
    model('standing_picture_frame_01', (-HW + 0.12, -2.4, 1.85), math.pi / 2, height=0.24)
    for y in (-1.6, -3.85): box('shelf side', -HW, -HW + 0.28, y - 0.02, y + 0.02, 1.4, 2.25, light_wood, 1.0)
    box('sconce arm', -HW, -HW + 0.2, -1.5, -1.47, 1.7, 1.73, brass, 1.0)
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=False, segments=20, radius1=0.09, radius2=0.05, depth=0.14)
    obj_from_bm('sconce shade', bm, flat('lamp shade', (0.95, 0.82, 0.6), 0.8, emit=(1.0, 0.75, 0.45), strength=3), True).location = (-HW + 0.2, -1.48, 1.82)
    light((-HW + 0.25, -1.48, 1.8), 40, radius=0.08)
    # ------------------------------------------------------------ right: the crib with its sheer canopy, a lamp, toy shelves
    CX0, CX1, CY0, CY1 = HW - 1.55, HW - 0.25, -3.6, -1.0
    crib(CX0, CX1, CY0, CY1, light_wood, mattress, sheet)
    cx, cy = (CX0 + CX1) / 2, (CY0 + CY1) / 2
    crown_z = 2.95
    torus('canopy crown', 0.22, 0.02, (cx, cy, crown_z), (0, 0, 0), brass); cyl('canopy hook', 0.006, APEX - crown_z, (cx, cy, (APEX + crown_z) / 2), (0, 0, 0), brass, 6)
    # sheer drapes falling from the crown: gathered at the top, spreading round the back and sides of the crib, open at the front
    for k in range(36):
        a0 = math.radians(-20 + k * 6.1); a1 = math.radians(-20 + (k + 1) * 6.1)     # from the front-right round the back to the front-left
        bm = bmesh.new(); n = 8
        for i in range(n):
            t0, t1 = i / n, (i + 1) / n
            def P(a, t):
                sp = 0.2 + (t ** 0.8) * 0.85; wob = (0.07 if int(round(math.degrees(a) / 6.1)) % 2 else -0.02) * t
                return (cx + math.cos(a) * (sp + wob) * 0.85, cy + math.sin(a) * (sp + wob) * 1.25, crown_z - t * (crown_z - 0.08))
            bm.faces.new([bm.verts.new(P(a0, t0)), bm.verts.new(P(a1, t0)), bm.verts.new(P(a1, t1)), bm.verts.new(P(a0, t1))])
        obj_from_bm('canopy', bm, sheer, True)
    box('crib side table', HW - 0.5, HW - 0.02, -0.95, -0.45, 0.62, 0.66, light_wood, 1.0, 0.01)
    for (x, y) in ((HW - 0.46, -0.9), (HW - 0.06, -0.9), (HW - 0.46, -0.5), (HW - 0.06, -0.5)): box('table leg', x - 0.02, x + 0.02, y - 0.02, y + 0.02, 0.0, 0.62, light_wood, 1.0)
    cyl('lamp base', 0.06, 0.3, (HW - 0.26, -0.7, 0.81), (0, 0, 0), brass, 20)
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=False, segments=24, radius1=0.17, radius2=0.1, depth=0.2)
    obj_from_bm('lamp shade', bm, flat('lamp shade', (0.95, 0.82, 0.6), 0.8, emit=(1.0, 0.75, 0.45), strength=3), True).location = (HW - 0.26, -0.7, 1.06)
    light((HW - 0.26, -0.7, 1.05), 60, radius=0.12)
    for z in (1.4, 1.75, 2.1):
        shelf(HW - 0.26, HW, -1.0, -0.35, z, light_wood)
        for k in range(3):
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.055, location=(HW - 0.13, -0.88 + k * 0.2, z + 0.06)); o = bpy.context.active_object; o.data.materials.append(rnd.choice(toyc))
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.035, location=(HW - 0.13, -0.88 + k * 0.2, z + 0.15)); bpy.context.active_object.data.materials.append(o.data.materials[0])
    # ------------------------------------------------------------ the floor: sheepskins, rocking sheep, baskets of plush toys, a pouf
    for (x, y, s, r) in ((-0.3, -2.9, 1.9, 0.2), (0.1, -4.2, 2.2, -0.15)):
        bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5); uvl = bm.loops.layers.uv.new()
        for f in bm.faces:
            for l in f.loops: l[uvl].uv = (l.vert.co.x + 0.5, l.vert.co.y + 0.5)
        o = obj_from_bm('sheepskin', bm, skin); o.scale = (s, s * 0.75, 1); o.location = (x, y, 0.012 + 0.003 * r); o.rotation_euler = (0, 0, r)
    g = rocking_sheep(0.0, -1.5, 0.15, fleece, timber); g.scale = (1.35, 1.35, 1.35)
    model('wicker_basket_02', (HW - 0.6, -4.3, 0), 0.4, width=0.55)
    for k in range(3):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=(HW - 0.6 + rnd.uniform(-0.1, 0.1), -4.3 + rnd.uniform(-0.1, 0.1), 0.25 + k * 0.05)); o = bpy.context.active_object; o.scale = (1, 1, 0.8); o.data.materials.append(plush)
    model('wicker_basket_02', (-1.0, -L + 0.6, 0), 0.2, width=0.6); pillow(-1.0, -L + 0.6, 0.24, 0.45, 0.32, 0.1, plush)
    p = cyl('pouf', 0.26, 0.36, (-HW + 1.0, -1.15, 0.18), (0, 0, 0), pink, 32); p.scale = (1, 1, 1)
    bv = p.modifiers.new('bevel', 'BEVEL'); bv.width = 0.08; bv.segments = 4
    model('wicker_basket_01', (-HW + 0.95, -1.6, 0), 0.3, width=0.38)
    # pendant lamp from the vault
    cyl('pendant chain', 0.006, APEX - 2.75, (0.0, -2.2, (APEX + 2.75) / 2), (0, 0, 0), brass, 6)
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=False, segments=24, radius1=0.16, radius2=0.04, depth=0.18)
    obj_from_bm('pendant shade', bm, flat('lamp shade', (0.95, 0.82, 0.6), 0.8, emit=(1.0, 0.75, 0.45), strength=3), True).location = (0.0, -2.2, 2.68)
    light((0.0, -2.2, 2.55), 60, radius=0.1)
    # front wall: the door
    from kitchen import arch_cutter_y, stone_arch
    cut(front, arch_cutter_y(-1.2, 1.0, 1.5, 0.0, -L - 1, -L + 1)); box_uv(front, 2.0)
    g = group((-1.2, -L, 0.0)); stone_arch(g, 1.0, 1.5, 0.5, rib, 0.16, half=True)
    box('door', -1.7, -0.7, -L - 0.25, -L - 0.18, 0.0, 2.1, timber, 0.8)
    w = bpy.data.worlds.new('w'); bpy.context.scene.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0.5, 0.55, 0.5, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.08
    for y in (-1.6, -4.2):
        f = light((0.0, y, WALL_H + 0.2), 80, (1.0, 0.72, 0.45), kind='AREA'); f.data.size = 2.0; f.rotation_euler = (math.pi, 0, 0)

def walk_rects():
    R = [(-HW + 0.75, HW - 1.75, -L + 0.4, -1.7),       # between the dresser and the crib
         (-HW + 0.75, HW - 0.4, -L + 0.4, -3.85),        # in front of the crib
         (-1.55, -1.0, -1.7, -0.8)]                      # up to the window seat
    return [[x0, x1, -y1, -y0] for x0, x1, y0, y1 in R]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--render', default=''); ap.add_argument('--samples', type=int, default=96); ap.add_argument('--res', default='1600x900')
    ap.add_argument('--glb', default=''); ap.add_argument('--cam', default='main')
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
    bpy.ops.wm.read_factory_settings(use_empty=True); build()
    for o in bpy.context.scene.objects:
        if o.type == 'LIGHT' and hasattr(o, 'visible_camera'): o.visible_camera = False
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = a.samples; sc.cycles.use_denoising = True; sc.cycles.max_bounces = 8
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'; sc.view_settings.exposure = 0.4
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
    cfg.update(name='Baby Room', glb='assets/rooms/nursery/nursery.glb', spawn=dict(x=-0.3, z=L - 0.6, yaw=0), walk=walk_rects(), probe=[0.0, 1.3, 2.8], tints=tints, floor='wood_floor_worn')
    cfg.setdefault('lights', [{'x': WX, 'y': 1.6, 'z': 1.0, 'color': '#ffe8c8', 'power': 9, 'range': 5}, {'x': 0.0, 'y': 2.4, 'z': 3.0, 'color': '#ffb877', 'power': 8, 'range': 5},
                              {'x': HW - 0.26, 'y': 1.05, 'z': 0.7, 'color': '#ffb877', 'power': 5, 'range': 3}])
    cfg.setdefault('exposure', 0.85); cfg.setdefault('version', 1); cfg.setdefault('wallBoost', 1.0); cfg.setdefault('maxFlameLights', 12); cfg.setdefault('flameColor', '#ffb877')
    json.dump(cfg, open(cfgp, 'w'), indent=1)
    if a.render: sc.render.filepath = os.path.abspath(a.render); bpy.ops.render.render(write_still=True)
    if a.glb:
        keep = ('plaster', 'planks', 'rough_wood', 'wood_floor', 'view', 'ivy', 'sheepskin')
        for im in bpy.data.images:
            if im.size[0] > 512 and not any(k in im.name for k in keep): im.scale(512, 512)
        bpy.ops.object.select_all(action='DESELECT')
        for o in list(sc.objects):
            if o.type == 'EMPTY' and o.instance_type == 'COLLECTION': o.select_set(True)
        if any(o.select_get() for o in sc.objects): bpy.ops.object.duplicates_make_real()
        bpy.ops.export_scene.gltf(filepath=os.path.abspath(a.glb), export_format='GLB', export_lights=False, export_cameras=False, export_apply=True, export_image_format='AUTO')

if __name__ == '__main__':
    main()
