"""Hobbit-house father's office, rebuilt as a real 3D room from the 'Father's office' image: a dark beamed timber ceiling,
built-in bookcases with cupboards along the back and left walls, a big arched window onto the mountains with a cushioned
seat, a guitar on the wall, a massive dark wooden desk with a brass banker's lamp, books, a laptop, a leather case, a plant
and a white mug that says "World's Best Jew Dad", a tufted leather chesterfield chair, and a rug on wide plank floors.

Blender axes: the back wall (window) is at y = 0, the room runs toward the camera to y = -L.

    python blender/rooms/office.py --render docs/rooms/office.png --samples 96 --glb assets/rooms/office/office.glb
"""
import argparse, json, math, os, sys, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
from hero_room import A, pbr, flat, image_mat, obj_from_bm, box_uv, box, cyl, torus, cut, model, light, candle
from kitchen import group, kid, tex_mat, mat_alpha, arch_cutter_y, arch_cutter_x, leaf_cluster
from hallway import pillow, blocks
from bedroom import lamp
from dining import rod

W, L, H = 6.4, 6.6, 3.3
HW = W / 2
rnd = random.Random(151)
CAMS = {'main': (-2.55, -5.3, 1.6, 84, -32, 16), 'fire': (2.3, -0.85, 1.6, 82, 155, 18)}
BOOKS = []

def K(*p): return A('assets', 'rooms', 'office', *p)

def bookcase_run(a0, a1, wall, inward, along_x, wood, top=2.9, unit=0.9, base=0.95):
    """Built-in bookcase: cupboards below, open shelves of books and curios above, against a wall."""
    def bx(name, u0, u1, d0, d1, z0, z1, mat=wood, bev=0.004):
        w0, w1 = wall + inward * d0, wall + inward * d1
        if along_x: return box(name, u0, u1, min(w0, w1), max(w0, w1), z0, z1, mat, 1.0, bev)
        return box(name, min(w0, w1), max(w0, w1), u0, u1, z0, z1, mat, 1.0, bev)
    bx('case back', a0, a1, 0.0, 0.03, 0.0, top, wood, 0)
    bx('cupboard', a0, a1, 0.0, 0.5, 0.0, base - 0.04); bx('counter', a0 - 0.03, a1 + 0.03, 0.0, 0.54, base - 0.05, base, wood, 0.01)
    n = max(1, round((a1 - a0) / unit)); uw = (a1 - a0) / n
    for i in range(n):
        u0, u1 = a0 + i * uw, a0 + (i + 1) * uw; uc = (u0 + u1) / 2
        bx('cupboard door', u0 + 0.03, u1 - 0.03, 0.5, 0.52, 0.1, base - 0.1)
        bx('door panel', u0 + 0.1, u1 - 0.1, 0.52, 0.535, 0.18, base - 0.18)
        bx('knob', uc - 0.015, uc + 0.015, 0.535, 0.56, base / 2 - 0.015, base / 2 + 0.015, BRASS, 0)
    for i in range(n + 1): u = a0 + i * uw; bx('case stile', u - 0.04, u + 0.04, 0.0, 0.36, base, top)
    bx('case crown', a0 - 0.05, a1 + 0.05, 0.0, 0.42, top, top + 0.12, wood, 0.01)
    zs = [base + 0.35 + k * 0.4 for k in range(5) if base + 0.35 + k * 0.4 < top - 0.1]
    for z in zs: bx('case shelf', a0, a1, 0.03, 0.36, z - 0.025, z)
    for i in range(n):
        u0, u1 = a0 + i * uw + 0.05, a0 + (i + 1) * uw - 0.05
        for z in [base] + zs[:-1]:
            u = u0
            while u < u1 - 0.05:
                r = rnd.random()
                if r < 0.1:                                   # a curio: globe, vase, frame or lamp
                    p = (u + 0.08, wall + inward * 0.2, z) if along_x else (wall + inward * 0.2, u + 0.08, z)
                    rnd.choice((lambda: model('brass_vase_02', p, 0, height=0.22), lambda: model('standing_picture_frame_01', p, 0 if along_x else math.pi / 2, height=0.2),
                                lambda: model('ceramic_vase_04', p, 0, height=0.2)))(); u += 0.2; continue
                if r < 0.16:                                  # a stack of books lying flat
                    for j in range(rnd.randint(2, 4)):
                        it = (u + 0.12, wall + inward * 0.18, z + 0.02 + j * 0.04, 0.24, 0.2, 0.038) if along_x else (wall + inward * 0.18, u + 0.12, z + 0.02 + j * 0.04, 0.2, 0.24, 0.038)
                        BOOKS.append(it + (rnd.randrange(8),))
                    u += 0.28; continue
                t = rnd.uniform(0.025, 0.06); h = rnd.uniform(0.2, 0.32); d = rnd.uniform(0.18, 0.26)
                it = (u + t / 2, wall + inward * (0.04 + d / 2), z + h / 2, t, d, h) if along_x else (wall + inward * (0.04 + d / 2), u + t / 2, z + h / 2, d, t, h)
                BOOKS.append(it + (rnd.randrange(8),)); u += t + rnd.uniform(0, 0.006)
        p = (( a0 + (i + 0.5) * uw), wall + inward * 0.3, top - 0.15) if along_x else (wall + inward * 0.3, a0 + (i + 0.5) * uw, top - 0.15)
        light(p, 10, (1.0, 0.7, 0.4), radius=0.06)

def guitar(x, y, z, rot, wood, dark):
    g = group((x, y, z), rot)
    for (dz, r) in ((0.0, 0.2), (0.27, 0.15)):
        o = cyl('guitar body', r, 0.09, (0, 0, dz), (math.pi / 2, 0, 0), wood, 40); kid(o, g)
    kid(cyl('sound hole', 0.05, 0.095, (0, -0.002, 0.16), (math.pi / 2, 0, 0), dark, 24), g)
    kid(box('guitar neck', -0.025, 0.025, -0.03, 0.02, 0.38, 0.95, dark, 1.0), g)
    kid(box('guitar head', -0.04, 0.04, -0.03, 0.02, 0.95, 1.1, dark, 1.0), g)
    kid(box('bridge', -0.06, 0.06, -0.06, -0.045, -0.08, -0.05, dark, 1.0), g)
    return g

BRASS = None
def build():
    global BRASS
    floor = pbr('wood_floor_worn', 'materials', (0.55, 0.38, 0.24), 0.5, 1.0)
    plaster = pbr('clay_plaster', 'materials', (0.42, 0.3, 0.2), 1.0, 1.4)
    wood = pbr('wood_cabinet_worn_long', 'materials', (0.4, 0.26, 0.16), 0.75)
    desk_w = pbr('wood_table_worn', 'materials', (0.42, 0.28, 0.18), 0.6)
    ceil = pbr('weathered_brown_planks', 'materials', (0.42, 0.29, 0.19), 0.9)
    beam = pbr('rough_wood', 'materials', (0.32, 0.21, 0.13), 0.9)
    rug = tex_mat('rug', A('assets', 'rooms', 'hallway', 'rug_diff.jpg'), rough=0.95)
    BRASS = flat('brass', (0.78, 0.55, 0.26), 0.3, 1.0)
    leather = flat('chair leather', (0.05, 0.022, 0.011), 0.38); case = flat('case leather', (0.08, 0.06, 0.05), 0.5)
    alu = flat('laptop aluminium', (0.72, 0.72, 0.74), 0.25, 1.0); screen = flat('laptop screen', (0.1, 0.2, 0.35), 0.1, emit=(0.35, 0.5, 0.7), strength=0.8)
    mug = flat('mug ceramic', (0.86, 0.86, 0.85), 0.15)
    decal = bpy.data.materials.new('mug decal'); decal.use_nodes = True; nt = decal.node_tree; bsdf = nt.nodes['Principled BSDF']
    ti = nt.nodes.new('ShaderNodeTexImage'); ti.image = bpy.data.images.load(K('mug_decal.png')); nt.links.new(ti.outputs[0], bsdf.inputs['Base Color']); bsdf.inputs['Roughness'].default_value = 0.15
    frame = flat('window frame', (0.25, 0.16, 0.09), 0.55); glass = flat('glass', (0.95, 0.97, 0.98), 0.02, transmission=1.0)
    lamp_green = flat('banker shade', (0.04, 0.12, 0.06), 0.25, 0.3)
    cushion = flat('cushion linen', (0.36, 0.27, 0.18), 0.9); ivy = mat_alpha('ivy', A('assets', 'rooms', 'kitchen', 'ivy.png'))
    bookm = [flat('book ' + n, c, 0.6) for n, c in (('red', (0.3, 0.05, 0.03)), ('brown', (0.22, 0.12, 0.06)), ('green', (0.08, 0.14, 0.07)), ('tan', (0.45, 0.32, 0.18)),
                                                  ('navy', (0.05, 0.07, 0.14)), ('maroon', (0.2, 0.04, 0.05)), ('cream', (0.55, 0.48, 0.36)), ('black', (0.03, 0.03, 0.03)))]
    # ------------------------------------------------------------ shell: plank floor, walls, beamed timber ceiling
    box('floor', -HW - 0.3, HW + 0.3, -L - 0.3, 0.3, -0.12, 0.0, floor, 2.2)
    back = box('back wall', -HW - 0.3, HW + 0.3, 0.0, 0.4, 0.0, H, plaster, 1.8)
    for nm, x0, x1, y0, y1 in (('front', -HW - 0.3, HW + 0.3, -L - 0.3, -L), ('left', -HW - 0.3, -HW, -L, 0.0), ('right', HW, HW + 0.3, -L, 0.0)):
        box(nm + ' wall', x0, x1, y0, y1, 0.0, H, plaster, 1.8)
    box('ceiling', -HW - 0.3, HW + 0.3, -L - 0.3, 0.4, H, H + 0.12, ceil, 1.4)
    for k in range(5): y = -0.4 - k * 1.5; box('ceiling beam', -HW, HW, y - 0.15, y + 0.15, H - 0.32, H, beam, 1.2)
    for x in (-1.6, 1.6): box('ceiling purlin', x - 0.12, x + 0.12, -L, 0.0, H - 0.5, H - 0.32, beam, 1.2)
    for x in (-HW + 0.15, HW - 0.15): box('corner post', x - 0.15, x + 0.15, -0.3, 0.0, 0.0, H, beam, 1.2)
    bulb = flat('bulb', (1, 0.8, 0.5), 1, emit=(1.0, 0.75, 0.45), strength=15)
    for y in (-1.15, -2.65, -4.15, -5.65):
        for x in (-0.8, 0.8):
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.025, location=(x, y, H - 0.03)); bpy.context.active_object.data.materials.append(bulb); light((x, y, H - 0.1), 12, radius=0.03)
    # ------------------------------------------------------------ the whole back wall is books (opposite the fireplace)
    bookcase_run(-HW + 0.3, HW - 0.3, 0.0, -1, True, wood)
    # ------------------------------------------------------------ the big arched window in the right wall, with a cushioned seat, a guitar beside it
    WY, WW, WRH, WZ = -3.0, 1.8, 1.2, 0.8
    right = next(o for o in bpy.context.scene.objects if o.name == 'right wall')
    cut(right, arch_cutter_x(WY, WW, WRH, WZ, HW - 0.2, HW + 0.8)); box_uv(right, 1.8)
    g = group((HW + 0.15, WY, WZ), -math.pi / 2); t = 0.08
    for x0, x1, z0, z1 in ((-WW / 2, -WW / 2 + t, 0, WRH), (WW / 2 - t, WW / 2, 0, WRH), (-WW / 2, WW / 2, 0, t)): kid(box('win frame', x0, x1, -0.05, 0.05, z0, z1, frame, 1.0), g)
    bpy.ops.mesh.primitive_torus_add(major_radius=WW / 2 - t / 2, minor_radius=t / 2, major_segments=48, minor_segments=8, location=(0, 0, WRH), rotation=(math.pi / 2, 0, 0))
    o = bpy.context.active_object; o.data.materials.append(frame)
    bm2 = bmesh.new(); bm2.from_mesh(o.data); bmesh.ops.delete(bm2, geom=[v for v in bm2.verts if v.co.y < -t * 0.4], context='VERTS'); bm2.to_mesh(o.data); bm2.free(); kid(o, g)
    for x in (-WW / 4, 0.0, WW / 4): kid(box('mullion', x - 0.025, x + 0.025, -0.035, 0.035, t, WRH + math.sqrt(max(0, (WW / 2) ** 2 - x * x)) - 0.07, frame, 1.0), g)
    for z in (WRH * 0.5, WRH): kid(box('transom', -WW / 2 + t, WW / 2 - t, -0.035, 0.035, z - 0.02, z + 0.02, frame, 1.0), g)
    bm = bmesh.new(); vs = [bm.verts.new((-WW / 2 + t, 0, 0.05)), bm.verts.new((WW / 2 - t, 0, 0.05))]
    for i in range(33): a = i / 32 * math.pi; vs.append(bm.verts.new((math.cos(a) * (WW / 2 - t), 0, WRH + math.sin(a) * (WW / 2 - t))))
    bm.faces.new(vs); kid(obj_from_bm('glass', bm, glass), g)
    from kitchen import stone_arch
    g2 = group((HW, WY, WZ), -math.pi / 2); stone_arch(g2, WW, WRH, 0.35, beam, 0.16, half=True)
    a = light((HW + 1.6, WY, WZ + 1.1), 500, (0.9, 0.94, 1.0), kind='AREA'); a.data.size = WW; a.rotation_euler = (0, math.radians(90), 0)
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1); bmesh.ops.scale(bm, vec=(15, 6.5, 1), verts=bm.verts)
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 4, 'X')); bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 4, 'Z'))
    bmesh.ops.translate(bm, vec=(HW + 12, WY, 2.4), verts=bm.verts)
    view = obj_from_bm('valley view', bm, image_mat('view', A('assets', 'rooms', 'kitchen', 'view.jpg'), 1.15)); uvl = view.data.uv_layers.new()
    for i, l in enumerate(uvl.data): co = view.data.vertices[view.data.loops[i].vertex_index].co; l.uv = (-(co.y - WY) / 30 + 0.5, (co.z - 2.4) / 13 + 0.5)
    box('window seat', HW - 0.6, HW, WY - WW / 2 - 0.35, WY + WW / 2 + 0.35, 0.0, 0.5, wood, 1.0, 0.01)
    pillow(HW - 0.3, WY, 0.56, 0.56, WW + 0.8, 0.12, cushion)
    for dy in (-0.6, 0.0, 0.65): pillow(HW - 0.12, WY + dy, 0.82, 0.14, 0.42, 0.38, cushion).rotation_euler = (0, math.radians(12), 0)
    model('potted_plant_04', (HW - 0.15, WY + 0.55, WZ), 0, height=0.28); model('potted_plant_01', (HW - 0.35, WY + WW / 2 + 0.85, 0), 0.4, height=1.6)
    guitar(HW - 0.06, WY - WW / 2 - 0.9, 1.25, -math.pi / 2, flat('guitar spruce', (0.4, 0.2, 0.07), 0.25), flat('guitar dark', (0.03, 0.015, 0.008), 0.35))
    for sy in (-1, 1):
        y = WY + sy * (WW / 2 + 0.45); box('sconce plate', HW - 0.05, HW, y - 0.03, y + 0.03, 2.25, 2.4, BRASS, 1.0)
        rod('sconce arm', (HW - 0.02, y, 2.3), (HW - 0.2, y, 2.35), 0.012, BRASS); lamp(HW - 0.22, y, 2.25, BRASS, flat('lamp shade', (0.95, 0.75, 0.55), 0.8, emit=(1.0, 0.65, 0.4), strength=3), 0.1, 25)
    # ------------------------------------------------------------ the door in the left wall, where you come in, a cabinet with the globe, a painting
    DOY = -3.0
    for y0, y1 in ((DOY - 0.62, DOY - 0.5), (DOY + 0.5, DOY + 0.62)): box('door jamb', -HW - 0.02, -HW + 0.08, y0, y1, 0.0, 2.3, beam, 1.0, 0.01)
    box('door lintel', -HW - 0.02, -HW + 0.08, DOY - 0.62, DOY + 0.62, 2.2, 2.36, beam, 1.0, 0.01)
    box('door', -HW - 0.02, -HW + 0.03, DOY - 0.5, DOY + 0.5, 0.0, 2.2, wood, 1.0, 0.01)
    for z0 in (0.2, 1.2): box('door panel', -HW + 0.03, -HW + 0.045, DOY - 0.38, DOY + 0.38, z0, z0 + 0.8, wood, 1.0)
    cyl('door knob', 0.03, 0.06, (-HW + 0.07, DOY + 0.38, 1.0), (0, math.pi / 2, 0), BRASS, 16)
    box('globe cabinet', -HW, -HW + 0.5, -5.55, -4.75, 0.0, 0.92, wood, 1.0, 0.01); box('globe cabinet top', -HW, -HW + 0.54, -5.6, -4.7, 0.92, 0.95, wood, 1.0, 0.01)
    box('side cabinet', -HW, -HW + 0.5, -1.6, -0.8, 0.0, 0.92, wood, 1.0, 0.01); box('side cabinet top', -HW, -HW + 0.54, -1.65, -0.75, 0.92, 0.95, wood, 1.0, 0.01)
    model('brass_vase_02', (-HW + 0.27, -1.2, 0.95), 0, height=0.3)
    model('fancy_picture_frame_01', (-HW + 0.03, -5.15, 1.85), math.pi / 2, width=0.8); model('fancy_picture_frame_01', (-HW + 0.03, -1.2, 1.85), math.pi / 2, width=0.7)
    # ------------------------------------------------------------ the big desk with its things, the leather chair
    DX, DY, DH = 0.0, -3.0, 0.8
    box('desk top', DX - 1.15, DX + 1.15, DY - 0.62, DY + 0.62, DH - 0.07, DH, desk_w, 1.2, 0.02)
    for sx in (-1, 1):
        box('desk pedestal', DX + sx * 0.85 - 0.3, DX + sx * 0.85 + 0.3, DY - 0.55, DY + 0.55, 0.06, DH - 0.07, desk_w, 1.0, 0.01)
        for k in range(3):
            z0 = 0.12 + k * 0.2; box('desk drawer', DX + sx * 0.85 - 0.26, DX + sx * 0.85 + 0.26, DY - 0.575, DY - 0.55, z0, z0 + 0.17, desk_w, 1.0, 0.006)
            box('drawer pull', DX + sx * 0.85 - 0.05, DX + sx * 0.85 + 0.05, DY - 0.6, DY - 0.575, z0 + 0.08, z0 + 0.1, BRASS, 1.0)
    box('desk modesty panel', DX - 0.55, DX + 0.55, DY - 0.55, DY - 0.5, 0.2, DH - 0.12, desk_w, 1.0)
    for k in range(9): box('desk stud', DX - 1.1 + k * 0.275, DX - 1.08 + k * 0.275, DY - 0.63, DY - 0.61, DH - 0.05, DH - 0.03, BRASS, 1.0)
    T = DH
    # brass banker's lamp on a stack of books
    for k, (w_, d_, col) in enumerate(((0.42, 0.3, 5), (0.38, 0.28, 1), (0.34, 0.25, 3))): BOOKS.append((DX - 0.75, DY - 0.05, T + 0.025 + k * 0.05, w_, d_, 0.048, col))
    lb = T + 0.15; cyl('lamp foot', 0.09, 0.03, (DX - 0.75, DY - 0.05, lb + 0.015), (0, 0, 0), BRASS, 24); cyl('lamp stem', 0.015, 0.5, (DX - 0.75, DY - 0.05, lb + 0.27), (0, 0, 0), BRASS, 12)
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=False, segments=32, radius1=0.24, radius2=0.04, depth=0.14); sh = obj_from_bm('lamp dome', bm, flat('banker glass', (0.02, 0.15, 0.05), 0.15, emit=(0.1, 0.5, 0.15), strength=0.6), True); sh.location = (DX - 0.75, DY - 0.05, lb + 0.58)
    light((DX - 0.75, DY - 0.05, lb + 0.48), 60, (1.0, 0.72, 0.42), radius=0.08)
    for k in range(4): BOOKS.append((DX - 0.25, DY - 0.35, T + 0.025 + k * 0.045, 0.32, 0.24, 0.042, [1, 7, 3, 2][k]))
    # leather case, laptop, the mug, a plant, papers
    box('leather case', DX + 0.5, DX + 0.95, DY - 0.42, DY - 0.12, T, T + 0.18, case, 1.0, 0.02); box('case strap', DX + 0.7, DX + 0.74, DY - 0.43, DY - 0.11, T + 0.02, T + 0.19, BRASS, 1.0)
    lx, ly = DX, DY + 0.24                                       # the laptop sits in the middle, right in front of the big chair
    box('laptop base', lx - 0.17, lx + 0.17, ly - 0.12, ly + 0.12, T, T + 0.015, alu, 1.0, 0.004)
    lid = box('laptop lid', -0.17, 0.17, -0.006, 0.006, 0.0, 0.23, alu, 1.0, 0.004); lid.location = (lx, ly - 0.12, T + 0.015); lid.rotation_euler = (math.radians(18), 0, 0)   # screen faces the big chair
    sc_ = box('laptop screen', -0.155, 0.155, 0.006, 0.008, 0.015, 0.215, screen, 1.0); sc_.location = lid.location; sc_.rotation_euler = lid.rotation_euler
    box('papers', DX - 0.52, DX - 0.24, DY + 0.04, DY + 0.3, T, T + 0.01, flat('paper', (0.85, 0.82, 0.74), 0.8), 1.0)
    mx, my = DX + 0.32, DY + 0.38
    mo = cyl('mug', 0.05, 0.11, (mx, my, T + 0.055), (0, 0, 0), mug, 32); bm = bmesh.new(); bm.from_mesh(mo.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.normal.z > 0.9], context='FACES'); bm.to_mesh(mo.data); bm.free()
    mod = mo.modifiers.new('wall', 'SOLIDIFY'); mod.thickness = 0.005
    torus('mug handle', 0.035, 0.009, (mx - 0.065, my, T + 0.06), (math.pi / 2, 0, 0), mug)
    cyl('coffee', 0.045, 0.005, (mx, my, T + 0.092), (0, 0, 0), flat('coffee', (0.06, 0.03, 0.015), 0.1), 32)
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new(); n = 12; vs = []
    for i in range(n + 1):
        a = 0.35 + i / n * (math.pi - 0.7)                                 # the half of the mug facing the big chair (+y), so dad reads it
        for z in (T + 0.004, T + 0.106): vs.append(bm.verts.new((mx + math.cos(a) * 0.0505, my + math.sin(a) * 0.0505, z)))
    for i in range(n):
        f = bm.faces.new((vs[2 * i], vs[2 * i + 2], vs[2 * i + 3], vs[2 * i + 1]))
        for l, (u, v) in zip(f.loops, ((i / n, 0), ((i + 1) / n, 0), ((i + 1) / n, 1), (i / n, 1))): l[uvl].uv = (u, v)
    obj_from_bm('mug decal', bm, decal, True)
    model('planter_pot_clay', (DX + 0.95, DY + 0.4, T), 0, height=0.14); leaf_cluster(ivy, DX + 0.95, DY + 0.4, T + 0.2, 12, 0.12, 0.05, (0.08, 0.14))
    bouquet_mat = [flat('petal pink', (0.9, 0.45, 0.55), 0.6), flat('petal white', (0.95, 0.92, 0.88), 0.6)]
    from kitchen import bouquet; bouquet(DX + 0.95, DY + 0.4, T + 0.15, bouquet_mat, ivy, 8, 0.1)
    BOOKS.append((DX - 0.3, DY + 0.42, T + 0.02, 0.2, 0.14, 0.035, 2))
    # tufted leather chesterfield chair behind the desk
    CX, CY = DX, DY + 1.0
    g = group((CX, CY, 0), 0.0)
    for o in (box('chair seat', -0.38, 0.38, -0.36, 0.36, 0.3, 0.5, leather, 1.0, 0.05), box('chair back', -0.38, 0.38, 0.22, 0.38, 0.5, 1.3, leather, 1.0, 0.06),
              box('chair arm', -0.46, -0.3, -0.34, 0.38, 0.45, 0.78, leather, 1.0, 0.06), box('chair arm', 0.3, 0.46, -0.34, 0.38, 0.45, 0.78, leather, 1.0, 0.06)):
        kid(o, g)
    for i in range(4):
        for j in range(4): kid(cyl('tuft', 0.012, 0.01, (-0.27 + i * 0.18, 0.215, 0.62 + j * 0.17), (math.pi / 2, 0, 0), BRASS, 8), g)
    kid(cyl('chair column', 0.04, 0.25, (0, 0, 0.17), (0, 0, 0), flat('chair metal', (0.1, 0.1, 0.1), 0.3, 1.0), 12), g)
    for k in range(5): a = k / 5 * 2 * math.pi; kid(rod('chair foot', (0, 0, 0.05), (math.cos(a) * 0.32, math.sin(a) * 0.32, 0.03), 0.02, flat('chair metal', (0.1, 0.1, 0.1), 0.3, 1.0)), g)
    # visitor's armchair and a side table at the front right; a rug on the left
    # two smaller visitor's armchairs on the door side of the desk, facing the big chair, with a little table between
    for sx, tw in ((-1, 0.2), (1, -0.2)): model('ArmChair_01', (DX + sx * 0.62, DY - 1.25, 0), math.pi + tw, width=0.72)
    for o in bpy.data.collections['lib_ArmChair_01'].all_objects:          # re-cover them in brown leather to match the desk chair
        for slot in getattr(o, 'material_slots', []):
            m = slot.material
            if not m or not m.use_nodes or m.get('tinted'): continue
            b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'); inp = b.inputs['Base Color']
            mix = m.node_tree.nodes.new('ShaderNodeMixRGB'); mix.blend_type = 'MULTIPLY'; mix.inputs[0].default_value = 1
            if inp.is_linked: m.node_tree.links.new(inp.links[0].from_socket, mix.inputs[1])
            else: mix.inputs[1].default_value = inp.default_value
            lt = 'leg' in m.name.lower() or 'wood' in m.name.lower()
            mix.inputs[2].default_value = (0.25, 0.14, 0.08, 1) if lt else (0.22, 0.1, 0.05, 1); m.node_tree.links.new(mix.outputs[0], inp)
            b.inputs['Roughness'].default_value = 0.42; m['tinted'] = 1
    # the fireplace against the right wall: stone chimney breast, firebox with logs and a fire, oak mantel with things on it
    stone = pbr('rustic_stone_wall', 'materials', (0.62, 0.54, 0.46), 1.0, 1.4); log = flat('office log', (0.018, 0.011, 0.007), 0.95)
    ember = flat('flame', (1, 0.35, 0.05), 1, emit=(1.0, 0.2, 0.01), strength=1.0); soot = flat('soot', (0.04, 0.03, 0.025), 0.9)
    FW = -L                                                     # the fireplace is in the front wall, behind the visitor's chairs
    def fx(name, d0, d1, u0, u1, z0, z1, mat, bev=0.0): return box(name, u0, u1, FW + d1, FW + d0, z0, z1, mat, 1.0, bev)
    fx('chimney breast', 0.0, 0.5, -1.0, 1.0, 0.0, H, stone)
    fb = fx('firebox surround', 0.5, 0.88, -1.15, 1.15, 0.0, 1.3, stone, 0.02)
    cut(fb, [box('c', -0.55, 0.55, FW + 0.3, FW + 1.0, 0.2, 0.9, stone)])
    fx('firebox', 0.36, 0.5, -0.55, 0.55, 0.2, 0.9, soot); fx('firebox inside', 0.36, 0.89, -0.56, 0.56, 0.18, 0.2, soot)
    fx('hearth', 0.5, 1.25, -1.3, 1.3, 0.0, 0.18, stone, 0.02)
    fx('mantel', 0.45, 1.02, -1.3, 1.3, 1.3, 1.44, beam, 0.01)
    for i in range(3): cyl('log', 0.06, 0.7, ((i - 1) * 0.05, FW + 0.66, 0.27 + (i // 2) * 0.11), (0, math.pi / 2, (i - 1) * 0.3), log, 12)
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.28); o = obj_from_bm('fire', bm, ember, True); o.location = (0, FW + 0.62, 0.3); o.scale = (0.8, 0.15, 0.22)
    for dx, hh in ((-0.2, 0.5), (0.05, 0.75), (0.25, 0.55)):
        bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.075, radius2=0.0, depth=0.3); f = obj_from_bm('flame', bm, ember, True)
        f.location = (dx, FW + 0.62, 0.38 + 0.18 * hh); f.scale = (1.0, 0.6, hh * 1.1)
    fx('ember bed', 0.52, 0.84, -0.4, 0.4, 0.2, 0.23, flat('embers', (0.3, 0.05, 0.01), 0.9, emit=(0.9, 0.15, 0.01), strength=0.35))
    light((0, FW + 1.2, 0.95), 60, (1.0, 0.45, 0.15), radius=0.25)
    for dx in (-0.75, 0.75): fx('firedog', 0.8, 0.98, dx - 0.03, dx + 0.03, 0.18, 0.5, flat('iron', (0.03, 0.03, 0.03), 0.5, 1.0))
    model('mantel_clock_01', (0, FW + 0.75, 1.44), math.pi, height=0.28); model('brass_vase_02', (0.8, FW + 0.75, 1.44), 0, height=0.3)
    model('standing_picture_frame_01', (-0.75, FW + 0.75, 1.44), math.pi, height=0.25)
    from spa import candles_cluster; candles_cluster(-1.1, FW + 0.75, 1.44, flat('wax', (0.92, 0.88, 0.78), 0.45), 3, 0.8)
    model('fancy_picture_frame_01', (0, FW + 0.52, 2.1), math.pi, width=0.9)
    for a0, a1 in ((-HW + 0.3, -1.3), (1.3, HW - 0.3)): bookcase_run(a0, a1, FW, 1, True, wood, top=2.7)   # shelves either side of the chimney
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5); uvl = bm.loops.layers.uv.new()
    for f in bm.faces:
        for l in f.loops: l[uvl].uv = (l.vert.co.x + 0.5, l.vert.co.y + 0.5)
    o = obj_from_bm('rug', bm, rug); o.scale = (3.2, 3.8, 1); o.location = (0.0, -3.1, 0.007)
    gx, gy, gz = -HW + 0.28, -5.15, 0.95                       # a globe on its brass stand on the left cupboard counter
    cyl('globe base', 0.09, 0.03, (gx, gy, gz + 0.015), (0, 0, 0), wood, 24); cyl('globe post', 0.012, 0.12, (gx, gy, gz + 0.09), (0, 0, 0), BRASS, 10)
    torus('globe meridian', 0.17, 0.008, (gx, gy, gz + 0.32), (0, math.radians(23), 0), BRASS)
    gm = tex_mat('globe map', A('assets', 'rooms', 'office', 'globe.jpg'), rough=0.35) if os.path.exists(A('assets', 'rooms', 'office', 'globe.jpg')) else flat('globe', (0.35, 0.3, 0.15), 0.4)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.16, segments=48, ring_count=24, location=(gx, gy, gz + 0.32), rotation=(0, math.radians(23), 0)); bpy.context.active_object.data.materials.append(gm)
    blocks('books', BOOKS, bookm)
    w = bpy.data.worlds.new('w'); bpy.context.scene.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0.4, 0.42, 0.45, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.06
    for y in (-2.0, -5.0):
        f = light((0, y, H - 0.4), 60, (1.0, 0.72, 0.45), kind='AREA'); f.data.size = 2.5

def walk_rects():
    R = [(-HW + 0.65, -1.45, -L + 0.75, -0.75),               # by the door on the left, from the fireplace corner to the books
         (1.45, HW - 0.65, -L + 0.75, -0.75),                  # the right side, along the window seat
         (-1.45, 1.45, -1.5, -0.7),                           # between the big chair and the bookcase
         (-1.45, 1.45, -5.3, -4.7)]                           # between the visitor's chairs and the hearth
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
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'; sc.view_settings.exposure = 0.3
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
    cfg.update(name="Father's Office", glb='assets/rooms/office/office.glb', spawn=dict(x=-HW + 0.75, z=3.0, yaw=-1.5708), walk=walk_rects(), probe=False, tints=tints, floor='wood_floor_worn')
    cfg.setdefault('lights', [{'x': HW - 0.8, 'y': 1.8, 'z': 3.0, 'color': '#ffe8d0', 'power': 10, 'range': 6}, {'x': -0.75, 'y': 1.45, 'z': 3.05, 'color': '#ffb877', 'power': 7, 'range': 4},
                              {'x': 0.0, 'y': 2.2, 'z': 0.6, 'color': '#ffb877', 'power': 7, 'range': 5}, {'x': 0.0, 'y': 0.6, 'z': L - 1.0, 'color': '#ff8a3a', 'power': 9, 'range': 5}])
    cfg.setdefault('exposure', 0.85); cfg.setdefault('version', 1); cfg.setdefault('wallBoost', 1.0); cfg.setdefault('maxFlameLights', 6); cfg.setdefault('flameColor', '#ffb877')
    json.dump(cfg, open(cfgp, 'w'), indent=1)
    if a.render: sc.render.filepath = os.path.abspath(a.render); bpy.ops.render.render(write_still=True)
    if a.glb:
        keep = ('plaster', 'planks', 'rough_wood', 'wood_floor', 'wood_cabinet', 'wood_table', 'view', 'ivy', 'rug', 'mug_decal')
        for im in bpy.data.images:
            if im.size[0] > 512 and not any(k in im.name for k in keep): im.scale(512, 512)
        bpy.ops.object.select_all(action='DESELECT')
        for o in list(sc.objects):
            if o.type == 'EMPTY' and o.instance_type == 'COLLECTION': o.select_set(True)
        if any(o.select_get() for o in sc.objects): bpy.ops.object.duplicates_make_real()
        bpy.ops.export_scene.gltf(filepath=os.path.abspath(a.glb), export_format='GLB', export_lights=False, export_cameras=False, export_apply=True, export_image_format='AUTO')

if __name__ == '__main__':
    main()
