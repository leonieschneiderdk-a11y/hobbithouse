"""Hobbit-house master (parents') bedroom, rebuilt as a real 3D room from the 'Parent's bedroom' image. Big and grand:
a shallow plank vault criss-crossed with heavy timber beams, a stone fireplace with bookcases, a huge bed on the left,
a sitting area with a sectional sofa on the right, an arched alcove with a round window, and a great arched window
onto the mountains with a window seat.

Blender axes: the fireplace wall is at y = 0, the room runs toward the camera to y = -L, x is left/right.

    python blender/rooms/bedroom.py --render docs/rooms/bedroom.png --samples 96 --glb assets/rooms/bedroom/bedroom.glb
"""
import argparse, json, math, os, sys, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
from hero_room import A, pbr, flat, image_mat, obj_from_bm, box_uv, box, cyl, torus, cut, sweep_profile, model, light, candle
from kitchen import lantern, leaf_cluster, group, kid, tex_mat, mat_alpha, arch_cutter_y, arch_cutter_x, stone_arch, shelf, plates_row, bouquet
from hallway import pillow, bookcase, blocks, BOOKS
from spa import candles_cluster
from cellar import candle_chandelier
from nursery import curtain
from dining import rod

W, L = 12.0, 16.0
HW = W / 2
WALL_H, APEX = 2.7, 4.0
rnd = random.Random(111)
CAMS = {'main': (0.3, -L + 0.4, 1.7, 85, 0, 14), 'bed': (2.5, -8.0, 1.6, 86, 35, 17), 'sofa': (-1.0, -8.5, 1.6, 86, -30, 17)}
AX0, AX1, AD = 2.3, 5.3, 2.8                              # alcove behind the back wall (x range, depth)
BIGW = (-4.6, 2.4, 1.6, 0.55)                             # right-wall arched window: centre y, width, straight height, sill z

def K(*p): return A('assets', 'rooms', 'bedroom', *p)

def vault_z(x, inset=0.0):
    t = max(-1.0, min(1.0, x / (HW - inset)))
    return WALL_H + math.sqrt(max(0.0, 1 - t * t)) * (APEX - WALL_H - inset)

def profile(n=48, inset=0.0):
    pts = [(-HW + inset, 0.0)]
    for i in range(n + 1):
        a = math.pi - i / n * math.pi
        pts.append((math.cos(a) * (HW - inset), WALL_H + math.sin(a) * (APEX - WALL_H - inset)))
    pts.append((HW - inset, 0.0)); return pts

def lamp(x, y, z, brass, shade_m, h=0.42, power=45):
    cyl('lamp base', 0.07, h * 0.6, (x, y, z + h * 0.3), (0, 0, 0), brass, 20)
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=False, segments=24, radius1=0.2, radius2=0.12, depth=0.24)
    obj_from_bm('lamp shade', bm, shade_m, True).location = (x, y, z + h * 0.6 + 0.12); light((x, y, z + h * 0.6 + 0.1), power, radius=0.12)

def throw(x0, x1, y0, y1, z, mat, drop=0.35, fringe=None):
    """A blanket lying flat across a bed or ottoman and hanging down both long sides (y0/y1 edges)."""
    bm = bmesh.new(); pts = [(y0, z - drop), (y0 + 0.02, z), (y1 - 0.02, z), (y1, z - drop)]
    rows = [[bm.verts.new((x, y, zz + 0.012 * math.sin(x * 23 + y * 7))) for (y, zz) in pts] for x in (x0, (x0 + x1) / 2, x1)]
    for i in range(2):
        for j in range(3): bm.faces.new((rows[i][j], rows[i + 1][j], rows[i + 1][j + 1], rows[i][j + 1]))
    o = obj_from_bm('throw', bm, mat, True); s = o.modifiers.new('s', 'SOLIDIFY'); s.thickness = 0.02; return o

def build():
    floor = pbr('wood_floor_worn', 'materials', (0.62, 0.44, 0.3), 0.45, 1.0)
    plaster = pbr('clay_plaster', 'materials', (1.0, 0.86, 0.66), 1.0, 1.4)
    boards = pbr('weathered_brown_planks', 'materials', (0.5, 0.36, 0.24), 0.9)
    beam = pbr('rough_wood', 'materials', (0.27, 0.18, 0.11), 0.9)
    stone = pbr('rustic_stone_wall', 'materials', (0.78, 0.7, 0.6), 1.0, 1.4)
    wood = pbr('wood_cabinet_worn_long', 'materials', (0.55, 0.38, 0.24), 0.8)
    trim = pbr('dark_wooden_planks', 'materials', (0.46, 0.31, 0.2), 0.9)
    rug = tex_mat('rug', K('rug_diff.jpg'), rough=0.95, tint=(1.05, 1.0, 0.95))
    linen = flat('bed linen', (0.7, 0.64, 0.55), 0.9); linen2 = flat('duvet cream', (0.58, 0.5, 0.4), 0.9)
    green = flat('throw green', (0.12, 0.16, 0.1), 0.95); knit = flat('throw knit', (0.4, 0.34, 0.28), 1.0)
    p1, p2, p3 = flat('cushion oat', (0.48, 0.4, 0.3), 0.9), flat('cushion olive', (0.2, 0.2, 0.13), 0.9), flat('cushion taupe', (0.3, 0.23, 0.16), 0.9)
    sofa_m = flat('sofa fabric', (0.17, 0.085, 0.035), 0.8); leather = flat('ottoman leather', (0.13, 0.075, 0.04), 0.45)
    brass = flat('brass', (0.78, 0.55, 0.26), 0.3, 1.0); iron = flat('iron', (0.03, 0.028, 0.026), 0.55, 0.35)
    shade_m = flat('lamp shade', (0.95, 0.82, 0.6), 0.8, emit=(1.0, 0.75, 0.45), strength=3)
    frame = flat('window frame', (0.14, 0.08, 0.04), 0.55); glass = flat('glass', (0.95, 0.97, 0.98), 0.02, transmission=1.0)
    lglass = flat('lantern glass', (1.0, 0.86, 0.66), 0.08, transmission=0.85); wax = flat('wax', (0.92, 0.88, 0.78), 0.45)
    log = flat('log', (0.22, 0.13, 0.07), 0.9); ember = flat('ember', (1, 0.4, 0.1), 1, emit=(1.0, 0.4, 0.1), strength=30)
    sheer = flat('sheer curtain', (0.9, 0.84, 0.74), 0.8); sheer.node_tree.nodes['Principled BSDF'].inputs['Alpha'].default_value = 0.6
    for attr, val in (('blend_method', 'BLEND'), ('surface_render_method', 'BLENDED')):
        try: setattr(sheer, attr, val)
        except Exception: pass
    drape = flat('drape', (0.36, 0.3, 0.24), 0.9)
    ivy = mat_alpha('ivy', A('assets', 'rooms', 'kitchen', 'ivy.png'))
    petals = [flat('petal white', (0.95, 0.92, 0.88), 0.6), flat('petal cream', (0.95, 0.85, 0.65), 0.6), flat('petal rust', (0.7, 0.3, 0.15), 0.6)]
    bookm = [flat('book ' + n, c, 0.6) for n, c in (('red', (0.3, 0.05, 0.03)), ('brown', (0.22, 0.12, 0.06)), ('green', (0.08, 0.14, 0.07)), ('tan', (0.45, 0.32, 0.18)),
                                                  ('navy', (0.05, 0.07, 0.14)), ('maroon', (0.2, 0.04, 0.05)), ('cream', (0.55, 0.48, 0.36)), ('black', (0.03, 0.03, 0.03)))]
    # ------------------------------------------------------------ shell: wide boards, plaster walls, a shallow plank vault
    box('floor', -HW - 0.3, HW + 0.3, -L - 0.3, AD + 0.3, -0.12, 0.0, floor, 2.4)
    prof = profile()
    bm = bmesh.new(); r0 = [bm.verts.new((x, 0.0, z)) for x, z in prof]; r1 = [bm.verts.new((x, -L, z)) for x, z in prof]
    for i in range(len(prof) - 1): bm.faces.new((r0[i + 1], r0[i], r1[i], r1[i + 1]))
    shell = obj_from_bm('vault', bm, boards, True); shell.data.materials.append(plaster)
    for p in shell.data.polygons: p.material_index = 1 if p.center.z < WALL_H - 0.01 else 0
    box_uv(shell, 2.0); sol = shell.modifiers.new('s', 'SOLIDIFY'); sol.thickness = 0.3; sol.offset = 1
    bpy.context.view_layer.objects.active = shell; bpy.ops.object.modifier_apply(modifier='s')
    def end_wall(name, y, thick, sgn):
        bm = bmesh.new(); vs = [bm.verts.new((x, y, z)) for x, z in prof]; bm.faces.new(vs); w = obj_from_bm(name, bm, plaster)
        s = w.modifiers.new('s', 'SOLIDIFY'); s.thickness = thick; s.offset = 1.0 if sgn > 0 else -1.0
        bpy.context.view_layer.objects.active = w; bpy.ops.object.modifier_apply(modifier='s'); return w
    back = end_wall('back wall', 0.0, 0.45, 1); front = end_wall('front wall', -L, 0.4, -1)
    # the beams: heavy cross ribs, longitudinal purlins and short joists between, like the image's grid
    rp = profile(48, 0.03)[1:-1]
    RIBS = [-0.3 - k * 1.75 for k in range(10)]
    for y in RIBS: sweep_profile('rib', rp, y, 0.3, 0.32, beam)
    for x in (-4.0, -2.0, 0.0, 2.0, 4.0):
        box('purlin', x - 0.14, x + 0.14, -L, 0.0, vault_z(x, 0.3) - 0.28, vault_z(x, 0.3), beam, 1.2)
    for s in (-1, 1): box('wall plate', s * HW - (0.15 if s > 0 else -0.15) - 0.15, s * HW - (0.15 if s > 0 else -0.15) + 0.15, -L, 0.0, WALL_H - 0.15, WALL_H + 0.1, beam, 1.2)
    for y in RIBS[1:]:
        for s in (-1, 1): box('wall post', s * HW - (0.14 if s > 0 else -0.14) - 0.14, s * HW - (0.14 if s > 0 else -0.14) + 0.14, y - 0.15, y + 0.15, 0.0, WALL_H, beam, 1.2)
    bulb = flat('bulb', (1, 0.8, 0.5), 1, emit=(1.0, 0.75, 0.45), strength=15)
    for y in [(RIBS[k] + RIBS[k + 1]) / 2 for k in range(len(RIBS) - 1)]:
        for x in (-3.0, 3.0):
            z = vault_z(x, 0.05) - 0.02; bpy.ops.mesh.primitive_uv_sphere_add(radius=0.025, location=(x, y, z)); bpy.context.active_object.data.materials.append(bulb); light((x, y, z - 0.08), 14, radius=0.03)
    # ------------------------------------------------------------ back wall: the stone fireplace with bookcases either side, pictures, the alcove
    FX = -0.8
    box('chimney breast', FX - 1.2, FX + 1.2, -0.75, 0.0, 0.0, vault_z(FX) + 0.1, stone, 1.0)
    fb = box('firebox surround', FX - 1.35, FX + 1.35, -0.95, -0.7, 0.0, 1.35, stone, 1.0, 0.02)
    cut(fb, [box('c', FX - 0.6, FX + 0.6, -1.2, -0.4, 0.25, 0.95, stone)])
    box('firebox', FX - 0.6, FX + 0.6, -0.7, -0.55, 0.25, 0.95, flat('soot', (0.04, 0.03, 0.025), 0.9), 1.0)
    box('hearth', FX - 1.5, FX + 1.5, -1.45, -0.7, 0.0, 0.25, stone, 1.0, 0.02)
    box('mantel', FX - 1.5, FX + 1.5, -1.05, -0.6, 1.35, 1.5, trim, 1.0, 0.01)
    for i in range(3): cyl('log', 0.07, 0.8, (FX + (i - 1) * 0.06, -0.8, 0.33 + (i // 2) * 0.12), (0, math.pi / 2, (i - 1) * 0.3), log, 12)
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.3); o = obj_from_bm('fire', bm, ember, True); o.location = (FX, -0.8, 0.45); o.scale = (1.3, 0.5, 0.6)
    light((FX, -1.1, 0.6), 260, (1.0, 0.45, 0.15), radius=0.3)
    candles_cluster(FX - 1.1, -0.82, 1.5, wax, 3, 0.9); candles_cluster(FX + 1.1, -0.82, 1.5, wax, 3, 0.9)
    model('mantel_clock_01', (FX, -0.85, 1.5), 0, height=0.3); model('brass_vase_02', (FX - 0.55, -0.85, 1.5), 0, height=0.3); model('ceramic_vase_04', (FX + 0.55, -0.85, 1.5), 0, height=0.28)
    leaf_cluster(ivy, FX - 1.0, -0.9, 1.62, 12, 0.35, 0.4); leaf_cluster(ivy, FX + 1.0, -0.9, 1.62, 12, 0.35, 0.4)
    model('fancy_picture_frame_01', (FX, -0.78, 2.15), 0, width=0.8)
    model('wooden_lantern_01', (FX - 1.2, -1.2, 0.25), 0, height=0.5); light((FX - 1.2, -1.2, 0.5), 25)
    # bookcases (built in, either side of the chimney) - reuse the hallway bookcase, rotated to the back wall
    def back_bookcase(x0, x1):
        z1 = 2.45; d = 0.36
        box('bookcase back', x0, x1, -0.03, 0.0, 0.0, z1, trim, 1.0)
        for x in (x0, x1): box('bookcase side', x - 0.03, x + 0.03, -d, 0.0, 0.0, z1, trim, 1.0)
        box('bookcase crown', x0 - 0.05, x1 + 0.05, -d - 0.05, 0.0, z1, z1 + 0.1, trim, 1.0, 0.01)
        zs = [0.1 + k * 0.38 for k in range(6)]
        for z in zs: box('book shelf', x0 + 0.03, x1 - 0.03, -d, -0.03, z - 0.025, z, trim, 1.0, 0.003)
        for z in zs[:-1]:
            x = x0 + 0.05
            while x < x1 - 0.06:
                if rnd.random() < 0.08:
                    if rnd.random() < 0.5: candle((x + 0.05, -d * 0.55, z), 0.12, 5)
                    else: model(rnd.choice(('brass_vase_02', 'ceramic_vase_04')), (x + 0.06, -d * 0.55, z), 0, height=rnd.uniform(0.14, 0.22))
                    x += 0.14; continue
                t = rnd.uniform(0.025, 0.06); h = rnd.uniform(0.2, 0.31); dd = rnd.uniform(0.18, 0.26)
                if x + t > x1 - 0.05: break
                BOOKS.append((x + t / 2, -0.04 - dd / 2, z + h / 2, t, dd, h, rnd.randrange(8))); x += t + rnd.uniform(0, 0.005)
        lamp((x0 + x1) / 2, -0.5, 0.0, brass, shade_m, 0.0, 0) if False else None
    back_bookcase(FX - 2.55, FX - 1.3); back_bookcase(FX + 1.3, FX + 2.4)
    for x in (FX - 1.9, FX + 1.85): light((x, -0.7, 2.2), 30, radius=0.2)
    # left part of the back wall: pictures, a console with a lamp and plants
    model('hanging_picture_frame_02', (-4.9, -0.06, 1.75), 0, width=0.9); model('hanging_picture_frame_01', (-5.6, -0.06, 2.3), 0, width=0.55)
    box('console', -5.7, -3.8, -0.5, -0.05, 0.78, 0.83, wood, 1.0, 0.01)
    for x in (-5.65, -3.85):
        for y in (-0.45, -0.1): box('console leg', x - 0.03, x + 0.03, y - 0.03, y + 0.03, 0.0, 0.78, wood, 1.0)
    lamp(-5.3, -0.28, 0.83, brass, shade_m, 0.45, 50); model('potted_plant_02', (-4.2, -0.3, 0.83), 0.3, height=0.55); bouquet(-4.8, -0.28, 1.0, petals, ivy, 16, 0.14)
    model('ceramic_vase_02', (-4.8, -0.28, 0.83), 0, height=0.2)
    model('potted_plant_01', (-5.4, -1.3, 0), 0.4, height=1.6)
    # the arched alcove to the right of the fireplace, with a round window and a cushioned bench
    cut(back, arch_cutter_y((AX0 + AX1) / 2, AX1 - AX0, 1.5, 0.0, -0.2, 0.8)); box_uv(back, 2.0)
    g = group(((AX0 + AX1) / 2, 0.0, 0.0)); stone_arch(g, AX1 - AX0, 1.5, 0.5, trim, 0.22, half=True)
    acx = (AX0 + AX1) / 2; ar = (AX1 - AX0) / 2
    box('alcove wall', AX0 - 0.3, AX0, 0.45, AD, 0.0, 3.4, plaster, 2.0); box('alcove wall', AX1, AX1 + 0.3, 0.45, AD, 0.0, 3.4, plaster, 2.0)
    av = cyl('alcove vault', ar + 0.2, AD, (acx, 0.45 + AD / 2, 1.5), (math.pi / 2, 0, 0), plaster, 48)
    cut(av, [cyl('c', ar, AD + 0.2, (acx, 0.45 + AD / 2, 1.5), (math.pi / 2, 0, 0), plaster, 48), box('c', acx - 3, acx + 3, -1, AD + 1, -2, 1.5, plaster)]); box_uv(av, 2.0)
    for k in range(3): sweep_profile('alcove rib', [(acx + math.cos(math.pi - i / 24 * math.pi) * (ar - 0.05), 1.5 + math.sin(math.pi - i / 24 * math.pi) * (ar - 0.05)) for i in range(25)], 0.8 + k * 0.85, 0.2, 0.2, beam)
    aw = box('alcove end', AX0 - 0.3, AX1 + 0.3, AD, AD + 0.35, 0.0, 3.4, plaster, 2.0)
    cut(aw, [cyl('c', 0.8, 1.0, (acx, AD + 0.17, 1.55), (math.pi / 2, 0, 0), plaster, 48)])
    gw = group((acx, AD + 0.1, 1.55)); kid(torus('round window frame', 0.77, 0.05, (0, 0, 0), (math.pi / 2, 0, 0), frame), gw)
    kid(box('mullion', -0.025, 0.025, -0.03, 0.03, -0.8, 0.8, frame, 1.0), gw); kid(box('transom', -0.78, 0.78, -0.03, 0.03, -0.02, 0.02, frame, 1.0), gw)
    kid(cyl('glass', 0.77, 0.01, (0, 0, 0), (math.pi / 2, 0, 0), glass, 48), gw)
    a = light((acx, AD + 1.5, 1.8), 350, (0.85, 0.92, 1.0), kind='AREA'); a.data.size = 1.5; a.rotation_euler = (math.radians(90), 0, 0)
    box('alcove bench', AX0, AX1, AD - 0.6, AD, 0.0, 0.45, wood, 1.0, 0.01); pillow(acx, AD - 0.3, 0.52, AX1 - AX0 - 0.05, 0.56, 0.12, p1)
    for k, m in enumerate((p2, p1, p3, p2)): pillow(AX0 + 0.45 + k * 0.75, AD - 0.12, 0.8, 0.45, 0.14, 0.4, m).rotation_euler = (math.radians(12), 0, 0)
    for x in (AX0 + 0.35, AX1 - 0.35): box('sconce arm', x - 0.015, x + 0.015, AD - 0.25, AD, 2.1, 2.13, iron, 1.0); lantern(x, AD - 0.25, 1.78, 0.85, 2.11, iron, lglass, 40)
    model('potted_plant_01', (AX1 - 0.4, 0.9, 0), 2.0, height=1.3)
    # ------------------------------------------------------------ left: the huge bed, nightstands with lamps, an ottoman bench at its foot
    BY, BL, BW = -9.2, 2.3, 2.5           # bed centre y, length (along x), width (along y)
    bx0 = -HW + 0.25
    box('headboard', bx0, bx0 + 0.12, BY - BW / 2 - 0.1, BY + BW / 2 + 0.1, 0.0, 1.45, wood, 1.0, 0.02)
    for k in range(5): yy = BY - BW / 2 + 0.25 + k * (BW - 0.5) / 4; box('headboard panel', bx0 + 0.12, bx0 + 0.15, yy - 0.2, yy + 0.2, 0.55, 1.3, trim, 1.0, 0.01)
    box('bed frame', bx0 + 0.1, bx0 + BL, BY - BW / 2, BY + BW / 2, 0.12, 0.42, wood, 1.0, 0.02)
    for (x, y) in ((bx0 + 0.15, BY - BW / 2 + 0.05), (bx0 + 0.15, BY + BW / 2 - 0.05), (bx0 + BL - 0.05, BY - BW / 2 + 0.05), (bx0 + BL - 0.05, BY + BW / 2 - 0.05)):
        box('bed leg', x - 0.06, x + 0.06, y - 0.06, y + 0.06, 0.0, 0.14, wood, 1.0)
    box('footboard', bx0 + BL - 0.08, bx0 + BL + 0.04, BY - BW / 2 - 0.05, BY + BW / 2 + 0.05, 0.0, 0.62, wood, 1.0, 0.02)
    pillow(bx0 + BL / 2 + 0.05, BY, 0.56, BL - 0.15, BW - 0.06, 0.28, linen)                       # mattress
    pillow(bx0 + BL / 2 + 0.25, BY, 0.74, BL - 0.6, BW + 0.05, 0.12, linen2)                      # duvet
    throw(bx0 + BL - 0.95, bx0 + BL - 0.35, BY - BW / 2 - 0.02, BY + BW / 2 + 0.02, 0.82, green, 0.45)
    throw(bx0 + BL - 0.4, bx0 + BL - 0.08, BY - BW / 2 + 0.2, BY + BW / 2 + 0.05, 0.84, knit, 0.55)
    for k, (dy, m, sz) in enumerate(((-0.75, linen, 0.62), (0.0, linen, 0.62), (0.75, linen, 0.62), (-0.55, p1, 0.5), (0.2, p3, 0.5), (0.85, p1, 0.45), (-0.2, p2, 0.36))):
        z = 0.95 if k < 3 else 1.0; xo = bx0 + 0.3 + (0.12 if k >= 3 else 0) + (0.12 if k == 6 else 0)
        pillow(xo, BY + dy, z, 0.18, sz, sz * 0.75, m).rotation_euler = (0, math.radians(-16), 0)
    for s in (-1, 1):
        ny = BY + s * (BW / 2 + 0.45)
        box('nightstand', bx0, bx0 + 0.55, ny - 0.3, ny + 0.3, 0.0, 0.62, wood, 1.0, 0.01)
        box('nightstand drawer', bx0 + 0.55, bx0 + 0.57, ny - 0.25, ny + 0.25, 0.35, 0.55, trim, 1.0, 0.005)
        lamp(bx0 + 0.27, ny, 0.62, brass, shade_m, 0.45, 55); candles_cluster(bx0 + 0.3, ny + s * 0.18, 0.62, wax, 1, 0.8)
    model('potted_plant_02', (bx0 + 0.3, BY - BW / 2 - 1.3, 0), 0.2, height=0.85)
    oy0, oy1 = BY - 0.85, BY + 0.85; ox = bx0 + BL + 0.55
    box('ottoman base', ox - 0.32, ox + 0.32, oy0, oy1, 0.12, 0.3, wood, 1.0, 0.01)
    for (x, y) in ((ox - 0.27, oy0 + 0.05), (ox + 0.27, oy0 + 0.05), (ox - 0.27, oy1 - 0.05), (ox + 0.27, oy1 - 0.05)): cyl('ottoman leg', 0.035, 0.14, (x, y, 0.07), (0, 0, 0), wood, 12)
    pillow(ox, BY, 0.42, 0.66, oy1 - oy0 + 0.04, 0.22, leather)
    for k in range(6):
        for j in range(2): cyl('tuft', 0.012, 0.01, (ox - 0.15 + j * 0.3, oy0 + 0.15 + k * 0.28, 0.53), (0, 0, 0), brass, 8)
    # left wall above the bed: pictures, a shelf with plants and candles, lanterns
    model('fancy_picture_frame_01', (-HW + 0.05, BY, 2.1), math.pi / 2, width=1.2)
    shelf(-HW, -HW + 0.28, BY - 2.6, BY - 1.75, 1.75, trim); shelf(-HW, -HW + 0.28, BY + 1.75, BY + 2.6, 1.75, trim)
    for y in (BY - 2.2, BY + 2.2): model('potted_plant_04', (-HW + 0.14, y, 1.75), 0.3, height=0.3); leaf_cluster(ivy, -HW + 0.15, y, 1.95, 10, 0.25, 0.5)
    for y in (BY - 3.3, BY + 3.3): box('sconce arm', -HW, -HW + 0.25, y - 0.015, y + 0.015, 2.05, 2.08, iron, 1.0); lantern(-HW + 0.25, y, 1.72, 0.9, 2.06, iron, lglass, 45)
    # ------------------------------------------------------------ the right side: sectional sofa, coffee table, ottoman with throw, armchair
    SY = -7.7                                  # back of the long sofa
    def sofa_run(x0, x1, y0, y1, facing):
        box('sofa base', x0, x1, y0, y1, 0.0, 0.42, sofa_m, 1.0, 0.04)
        if facing == '-y': box('sofa back', x0, x1, y1 - 0.25, y1, 0.42, 0.85, sofa_m, 1.0, 0.06)
        else: box('sofa back', x1 - 0.25, x1, y0, y1, 0.42, 0.85, sofa_m, 1.0, 0.06)
        n = max(1, round(((x1 - x0) if facing == '-y' else (y1 - y0)) / 0.8))
        for i in range(n):
            if facing == '-y':
                c = x0 + (i + 0.5) * (x1 - x0) / n; pillow(c, (y0 + y1) / 2 - 0.1, 0.5, (x1 - x0) / n - 0.03, (y1 - y0) - 0.3, 0.14, sofa_m)
                pillow(c, y1 - 0.38, 0.75, (x1 - x0) / n - 0.1, 0.18, 0.42, rnd.choice((p1, p2, p3))).rotation_euler = (math.radians(14), 0, 0)
            else:
                c = y0 + (i + 0.5) * (y1 - y0) / n; pillow((x0 + x1) / 2 - 0.1, c, 0.5, (x1 - x0) - 0.3, (y1 - y0) / n - 0.03, 0.14, sofa_m)
                pillow(x1 - 0.38, c, 0.75, 0.18, (y1 - y0) / n - 0.1, 0.42, rnd.choice((p1, p2, p3))).rotation_euler = (0, math.radians(-14), 0)
    sofa_run(0.25, 4.85, SY - 1.1, SY, '-y'); sofa_run(4.85, 5.75, SY - 3.6, SY, '+x')
    box('sofa arm', 0.0, 0.25, SY - 1.1, SY, 0.0, 0.62, sofa_m, 1.0, 0.06)
    throw(4.9, 5.65, SY - 1.0, SY - 0.2, 0.58, knit, 0.25)
    CT = (2.5, -10.0)
    cyl('coffee table top', 0.75, 0.08, (CT[0], CT[1], 0.46), (0, 0, 0), wood, 48).scale = (1.15, 0.85, 1)
    for k in range(4): a_ = k * math.pi / 2 + math.pi / 4; box('coffee table leg', CT[0] + math.cos(a_) * 0.55 - 0.05, CT[0] + math.cos(a_) * 0.55 + 0.05, CT[1] + math.sin(a_) * 0.4 - 0.05, CT[1] + math.sin(a_) * 0.4 + 0.05, 0.0, 0.42, wood, 1.0)
    box('coffee table shelf', CT[0] - 0.6, CT[0] + 0.6, CT[1] - 0.35, CT[1] + 0.35, 0.1, 0.14, wood, 1.0)
    candles_cluster(CT[0] - 0.2, CT[1], 0.5, wax, 3, 1.0); model('tea_set_01', (CT[0] + 0.3, CT[1] + 0.05, 0.5), 0, width=0.45) if os.path.exists(A('assets', 'models', 'tea_set_01.glb')) else model('wooden_bowl_01', (CT[0] + 0.3, CT[1], 0.5), 0, width=0.35)
    model('decorative_book_set_01', (CT[0], CT[1] - 0.25, 0.5), 0.2, width=0.3) if os.path.exists(A('assets', 'models', 'decorative_book_set_01.glb')) else None
    OT = (2.5, -11.75)
    box('ottoman base', OT[0] - 0.6, OT[0] + 0.6, OT[1] - 0.45, OT[1] + 0.45, 0.1, 0.3, wood, 1.0, 0.01)
    pillow(OT[0], OT[1], 0.42, 1.24, 0.94, 0.24, sofa_m)
    throw(OT[0] - 0.5, OT[0] + 0.45, OT[1] - 0.47, OT[1] + 0.47, 0.55, knit, 0.4)
    model('ArmChair_01', (0.15, -10.3, 0), math.radians(-90), width=0.85); model('side_table_01', (0.1, -11.3, 0), 0, height=0.55); candles_cluster(0.1, -11.3, 0.55, wax, 2, 0.8)
    lamp(-0.15, -7.75, 0.0, brass, shade_m, 1.45, 60)                                         # floor lamp by the armchair
    model('potted_plant_01', (5.4, -11.9, 0), 1.2, height=1.5)
    # ------------------------------------------------------------ the great arched window in the right wall, the window seat, drapes, the view
    wy, ww, wrh, wz = BIGW
    cut(shell, arch_cutter_x(wy, ww, wrh, wz, HW - 0.6, HW + 0.6))
    gx = group((HW - 0.05, wy, wz), math.pi / 2)
    t = 0.09
    for x0, x1, z0, z1 in ((-ww / 2, -ww / 2 + t, 0, wrh), (ww / 2 - t, ww / 2, 0, wrh), (-ww / 2, ww / 2, 0, t)): kid(box('win frame', x0, x1, -0.05, 0.05, z0, z1, frame, 1.0), gx)
    bpy.ops.mesh.primitive_torus_add(major_radius=ww / 2 - t / 2, minor_radius=t / 2, major_segments=64, minor_segments=8, location=(0, 0, wrh), rotation=(math.pi / 2, 0, 0))
    o = bpy.context.active_object; o.data.materials.append(frame); kid(o, gx)
    bm2 = bmesh.new(); bm2.from_mesh(o.data); bmesh.ops.delete(bm2, geom=[v for v in bm2.verts if v.co.y < -t * 0.4], context='VERTS'); bm2.to_mesh(o.data); bm2.free()
    for x in (-ww / 6, ww / 6): kid(box('mullion', x - 0.03, x + 0.03, -0.035, 0.035, t, wrh + math.sqrt(max(0, (ww / 2) ** 2 - x * x)) - 0.08, frame, 1.0), gx)
    kid(box('transom', -ww / 2 + t, ww / 2 - t, -0.035, 0.035, wrh - 0.03, wrh + 0.03, frame, 1.0), gx)
    bm = bmesh.new(); vs = [bm.verts.new((-ww / 2 + t, 0, 0.05)), bm.verts.new((ww / 2 - t, 0, 0.05))]
    for i in range(41): a_ = i / 40 * math.pi; vs.append(bm.verts.new((math.cos(a_) * (ww / 2 - t), 0, wrh + math.sin(a_) * (ww / 2 - t))))
    bm.faces.new(vs); kid(obj_from_bm('glass', bm, glass), gx)
    g2 = group((HW - 0.15, wy, wz), math.pi / 2); stone_arch(g2, ww, wrh, 0.3, trim, 0.2, half=True)
    a = light((HW + 1.8, wy, wz + 1.3), 1300, (0.85, 0.92, 1.0), kind='AREA'); a.data.size = ww; a.rotation_euler = (0, math.radians(-90), 0)
    box('window seat', HW - 0.7, HW, wy - ww / 2 - 0.4, wy + ww / 2 + 0.4, 0.0, 0.5, wood, 1.0, 0.01)
    pillow(HW - 0.36, wy, 0.56, 0.62, ww + 0.7, 0.12, p1)
    for k, m in enumerate((p2, p3, p1, p2)): pillow(HW - 0.14, wy - 1.1 + k * 0.7, 0.82, 0.14, 0.45, 0.4, m).rotation_euler = (0, math.radians(-12), 0)
    model('wooden_bowl_01', (HW - 0.35, wy + 1.2, 0.62), 0, width=0.3)
    for s in (-1, 1):
        curtain('curtain', [(HW - 0.25, wy + s * (ww / 2 + 0.15)), (HW - 0.3, wy + s * (ww / 2 + 0.6))], 0.0, wz + wrh + ww / 2 + 0.3, drape, 0.06, 8)
        curtain('sheer', [(HW - 0.18, wy + s * (ww / 2 - 0.1)), (HW - 0.2, wy + s * (ww / 2 + 0.2))], 0.5, wz + wrh + ww / 2 + 0.3, sheer, 0.04, 6)
    box('curtain rod', HW - 0.3, HW - 0.26, wy - ww / 2 - 0.8, wy + ww / 2 + 0.8, wz + wrh + ww / 2 + 0.3, wz + wrh + ww / 2 + 0.34, brass, 1.0)
    for y in (wy - ww / 2 - 0.9, wy + ww / 2 + 0.9): box('sconce arm', HW - 0.25, HW, y - 0.015, y + 0.015, 2.1, 2.13, iron, 1.0); lantern(HW - 0.25, y, 1.78, 0.9, 2.11, iron, lglass, 45)
    for k in range(10): leaf_cluster(ivy, HW - 0.2, wy - ww / 2 - 0.4 + k * (ww + 0.8) / 9, WALL_H + 0.3, 9, 0.25, 0.6 if k % 2 else 0.2)
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1); bmesh.ops.scale(bm, vec=(40, 17.3, 1), verts=bm.verts)
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 4, 'X'))
    view = obj_from_bm('valley view', bm, image_mat('view', A('assets', 'rooms', 'master', 'view.jpg'), 1.25)); uvl = view.data.uv_layers.new()
    for i, l in enumerate(uvl.data): co = view.data.vertices[view.data.loops[i].vertex_index].co; l.uv = (co.x / 40 + 0.5, co.z / 17.3 + 0.5)
    view.rotation_euler = (0, 0, -math.pi / 2); view.location = (HW + 14, wy, 2.2)
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1); bmesh.ops.scale(bm, vec=(30, 13, 1), verts=bm.verts)
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 4, 'X')); bmesh.ops.translate(bm, vec=(acx, AD + 11, 1.7), verts=bm.verts)
    v2 = obj_from_bm('valley view', bm, image_mat('view', A('assets', 'rooms', 'master', 'view.jpg'), 1.25)); uvl = v2.data.uv_layers.new()
    for i, l in enumerate(uvl.data): co = v2.data.vertices[v2.data.loops[i].vertex_index].co; l.uv = ((co.x - acx) / 30 + 0.3, (co.z - 1.7) / 13 + 0.5)
    # ------------------------------------------------------------ the big rug, the iron candle chandelier, the door
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5); uvl = bm.loops.layers.uv.new()
    for f in bm.faces:
        for l in f.loops: l[uvl].uv = (l.vert.co.x + 0.5, l.vert.co.y + 0.5)
    o = obj_from_bm('rug', bm, rug); o.scale = (7.6, 12.5, 1); o.location = (0.0, -7.6, 0.007); o.rotation_euler = (0, 0, math.radians(-4))
    candle_chandelier(0.0, -7.8, 2.75, vault_z(0.0) - 0.15, iron, 0.75, 10)
    candle_chandelier(0.0, -3.2, 2.85, vault_z(0.0) - 0.15, iron, 0.55, 8); candle_chandelier(0.0, -12.6, 2.85, vault_z(0.0) - 0.15, iron, 0.55, 8)
    cut(front, arch_cutter_y(-1.2, 1.3, 1.7, 0.0, -L - 1, -L + 1)); box_uv(front, 2.0)
    g = group((-1.2, -L, 0.0)); stone_arch(g, 1.3, 1.7, 0.5, trim, 0.2, half=True)
    box('door', -1.85, -0.55, -L - 0.25, -L - 0.18, 0.0, 2.4, trim, 0.8)
    for x in (-4.5, 4.5): model('potted_plant_01', (x, -L + 0.5, 0), rnd.uniform(0, 6), height=1.4)
    for x in (-4.0, 1.0, 4.0): box('sconce arm', x - 0.015, x + 0.015, -L, -L + 0.25, 2.1, 2.13, iron, 1.0); lantern(x, -L + 0.25, 1.78, 0.9, 2.11, iron, lglass, 40)
    model('ArmChair_01', (-0.6, -2.6, 0), math.radians(160), width=0.85)
    for (x, y, h) in ((-5.4, -14.0, 1.3), (5.4, -14.5, 1.5), (5.4, -6.5, 1.2)): model('potted_plant_01' if h > 1 else 'potted_plant_02', (x, y, 0), rnd.uniform(0, 6), height=h)
    model('vintage_cabinet_01', (-HW + 0.35, -3.6, 0), math.pi / 2, width=1.3); lamp(-HW + 0.35, -3.3, 1.05, brass, shade_m, 0.4, 40); model('ceramic_vase_04', (-HW + 0.35, -3.95, 1.05), 0, height=0.25)
    model('fancy_picture_frame_01', (-HW + 0.05, -3.6, 2.05), math.pi / 2, width=0.8)
    model('painted_wooden_bench', (-4.7, -0.55, 0), 0, width=1.4) if False else None
    for x in (-2.0, 1.4): candles_cluster(x + (-0.6 if x < 0 else 0.6), -0.9, 0.0, wax, 3, 1.1)
    # more furniture, like the image: a daybed at the back, a rocking chair by the window seat, a commode, consoles, a reading corner
    model('vintage_day_bed', (-3.7, -2.45, 0), 0, width=2.0); pillow(-3.3, -2.3, 0.62, 0.5, 0.16, 0.42, p1).rotation_euler = (math.radians(70), 0, 0)
    throw(-4.3, -3.6, -2.95, -1.95, 0.55, knit, 0.3)
    model('Rockingchair_01', (4.3, -3.1, 0), math.radians(-120), height=1.05); model('side_table_01', (4.3, -2.1, 0), 0, height=0.55); lamp(4.3, -2.1, 0.55, brass, shade_m, 0.4, 35)
    model('GothicCommode_01', (HW - 0.32, -6.75, 0), -math.pi / 2, width=1.2); candles_cluster(HW - 0.3, -6.5, 1.21, wax, 3, 0.9); model('ceramic_vase_02', (HW - 0.3, -7.05, 1.21), 0, height=0.22); bouquet(HW - 0.3, -7.05, 1.4, petals, ivy, 14, 0.13)
    model('hanging_picture_frame_02', (HW - 0.05, -6.75, 2.0), -math.pi / 2, width=0.75)
    model('ClassicConsole_01', (-3.4, -L + 0.35, 0), 0, width=1.5); lamp(-3.8, -L + 0.35, 0.95, brass, shade_m, 0.4, 40); model('brass_vase_02', (-3.0, -L + 0.35, 0.95), 0, height=0.3)
    model('ClassicConsole_01', (3.2, -L + 0.35, 0), 0, width=1.5); candles_cluster(3.2, -L + 0.35, 0.95, wax, 3, 1.0); model('fancy_picture_frame_01', (3.2, -L + 0.06, 1.9), math.pi, width=0.75)
    model('ArmChair_01', (-HW + 0.7, -13.4, 0), math.radians(-40), width=0.8); model('side_table_01', (-HW + 0.5, -14.4, 0), 0, height=0.55); lamp(-HW + 0.5, -14.4, 0.55, brass, shade_m, 0.4, 35)
    model('wooden_bookshelf_worn', (HW - 0.3, -14.2, 0), -math.pi / 2, height=2.1)
    model('treasure_chest', (-HW + 0.55, -6.15, 0), math.pi / 2, width=0.85) if False else None
    blocks('books', BOOKS, bookm)
    w = bpy.data.worlds.new('w'); bpy.context.scene.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0.45, 0.5, 0.6, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.08
    for (x, y) in ((-3, -3.0), (3, -3.0), (-3, -8.0), (3, -8.0), (-3, -13.0), (3, -13.0)):
        f = light((x, y, WALL_H), 45, (1.0, 0.72, 0.45), kind='AREA'); f.data.size = 3.0; f.rotation_euler = (math.pi, 0, 0)

def walk_rects():
    R = [(-2.3, 0.0, -L + 0.4, -1.55),                      # the long aisle down the middle to the hearth
         (-HW + 0.6, HW - 1.0, -L + 0.9, -12.35),            # the front, past the foot of the bed and the sitting area
         (-0.4, 4.2, -7.5, -1.55),                           # the back right, between the sofa and the alcove
         (1.7, 4.2, -1.6, -0.05), (AX0 + 0.3, AX1 - 0.3, -0.1, AD - 0.75),   # into the alcove
         (-HW + 0.6, -2.3, -6.6, -3.1)]                      # behind the bed
    return [[x0, x1, -y1, -y0] for x0, x1, y0, y1 in R]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--render', default=''); ap.add_argument('--samples', type=int, default=96); ap.add_argument('--res', default='1600x900')
    ap.add_argument('--glb', default=''); ap.add_argument('--cam', default='main')
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
    bpy.ops.wm.read_factory_settings(use_empty=True); build()
    for o in bpy.context.scene.objects:
        if o.type == 'LIGHT' and hasattr(o, 'visible_camera'): o.visible_camera = False
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = a.samples; sc.cycles.use_denoising = True; sc.cycles.max_bounces = 8
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'; sc.view_settings.exposure = 0.0
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
    cfg.update(name="Parents' Bedroom", glb='assets/rooms/bedroom/bedroom.glb', spawn=dict(x=0.0, z=L - 0.6, yaw=0), walk=walk_rects(), probe=[0.0, 1.5, 5.0], tints=tints, floor='wood_floor_worn')
    cfg.setdefault('lights', [{'x': HW - 0.5, 'y': 1.6, 'z': 4.6, 'color': '#ffe8d0', 'power': 12, 'range': 7}, {'x': -0.8, 'y': 0.6, 'z': 1.3, 'color': '#ff7a2e', 'power': 10, 'range': 6},
                              {'x': 0.4, 'y': 2.6, 'z': 4.6, 'color': '#ffb877', 'power': 10, 'range': 8}, {'x': -4.0, 'y': 2.2, 'z': 4.6, 'color': '#ffb877', 'power': 8, 'range': 6}])
    cfg.setdefault('exposure', 0.85); cfg.setdefault('version', 1); cfg.setdefault('wallBoost', 1.0); cfg.setdefault('maxFlameLights', 30); cfg.setdefault('flameColor', '#ffb877')
    json.dump(cfg, open(cfgp, 'w'), indent=1)
    if a.render: sc.render.filepath = os.path.abspath(a.render); bpy.ops.render.render(write_still=True)
    if a.glb:
        keep = ('plaster', 'planks', 'rough_wood', 'wood_floor', 'wood_cabinet', 'stone', 'view', 'ivy', 'rug')
        for im in bpy.data.images:
            if im.size[0] > 512 and not any(k in im.name for k in keep): im.scale(512, 512)
        bpy.ops.object.select_all(action='DESELECT')
        for o in list(sc.objects):
            if o.type == 'EMPTY' and o.instance_type == 'COLLECTION': o.select_set(True)
        if any(o.select_get() for o in sc.objects): bpy.ops.object.duplicates_make_real()
        bpy.ops.export_scene.gltf(filepath=os.path.abspath(a.glb), export_format='GLB', export_lights=False, export_cameras=False, export_apply=True, export_image_format='AUTO')

if __name__ == '__main__':
    main()
