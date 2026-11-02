"""Hobbit-house dining room, rebuilt as a real 3D room from the 'Dining room' image.

    python blender/rooms/dining.py --render docs/rooms/dining.png --samples 128 --res 1600x900 --glb assets/rooms/dining/dining.glb

Blender axes: the back wall with the three arched windows is at y = 0, the room runs toward the camera to y = -L,
x is left/right, z is up. Writes assets/rooms/dining/room.json for the walkable page.
"""
import argparse, json, math, os, sys, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
from hero_room import A, pbr, flat, image_mat, obj_from_bm, box_uv, box, cyl, torus, cut, sweep_profile, model, light, candle
from kitchen import (lantern, cabinet_run, shelf, plates_row, jars_row, leaf_cluster, bouquet, arch_window, stone_arch, group, kid,
                     tex_mat, mat_alpha, arch_cutter_x, arch_cutter_y)

W, L = 7.6, 11.0
HW = W / 2
WALL_H, APEX = 2.5, 4.1
BA, BD = 1.75, 2.35             # bay: half width of the straight back wall, depth of the corner cut
INNER = 0.42                      # thickness of the plastered inner wall layer that holds the arched niches
rnd = random.Random(31)
LIGHTS = []

def K(*p): return A('assets', 'rooms', 'dining', *p)

def vault_z(x, inset=0.0):
    t = max(-1.0, min(1.0, x / (HW - inset)))
    return WALL_H + math.sqrt(max(0.0, 1 - t * t)) * (APEX - WALL_H - inset)

def vault_x(z):
    """Half width of the vault at height z (for beams that cross it)."""
    if z <= WALL_H: return HW
    t = (z - WALL_H) / (APEX - WALL_H); return HW * math.sqrt(max(0.0, 1 - t * t))

def profile(n=40, inset=0.0):
    pts = [(-HW + inset, 0.0)]
    for i in range(n + 1):
        a = math.pi - i / n * math.pi
        pts.append((math.cos(a) * (HW - inset), WALL_H + math.sin(a) * (APEX - WALL_H - inset)))
    pts.append((HW - inset, 0.0)); return pts

def rod(name, p, q, r, mat, seg=8):
    p, q = Vector(p), Vector(q); d = q - p; o = cyl(name, r, d.length, (p + q) / 2, (0, 0, 0), mat, seg)
    o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized()); return o

def spindle_chair(x, y, rot, wood, seat_h=0.47, back_h=1.02):
    """Dark spindle-back dining chair; faces local -y (backrest at +y)."""
    g = group((x, y, 0), rot); w, d = 0.46, 0.44
    kid(box('chair seat', -w / 2, w / 2, -d / 2, d / 2, seat_h - 0.05, seat_h, wood, 1.0, 0.012), g)
    for sx in (-1, 1):
        for sy in (-1, 1):
            top = Vector((sx * (w / 2 - 0.05), sy * (d / 2 - 0.05), seat_h - 0.05)); bot = Vector((sx * (w / 2 - 0.02), sy * (d / 2 - 0.02), 0))
            kid(rod('chair leg', bot, top, 0.019, wood, 10), g)
        kid(rod('stretcher', (sx * (w / 2 - 0.035), -d / 2 + 0.04, 0.2), (sx * (w / 2 - 0.035), d / 2 - 0.04, 0.2), 0.011, wood), g)
    kid(rod('stretcher', (-w / 2 + 0.04, 0, 0.18), (w / 2 - 0.04, 0, 0.18), 0.011, wood), g)
    for sx in (-1, 1): kid(rod('back post', (sx * (w / 2 - 0.04), d / 2 - 0.04, seat_h - 0.02), (sx * (w / 2 - 0.02), d / 2 + 0.03, back_h), 0.021, wood, 10), g)
    # curved top rail and a lower rail, spindles between
    for zz, hh in ((back_h - 0.06, 0.08), (seat_h + 0.2, 0.04)):
        bm = bmesh.new(); n = 12; vs = []
        for i in range(n + 1):
            t = i / n - 0.5; xx = t * (w - 0.02); yy = d / 2 + 0.03 - 0.05 * (1 - (2 * t) ** 2) * -1
            vs.append((xx, yy))
        for i in range(n):
            (x0, y0), (x1, y1) = vs[i], vs[i + 1]
            v = [bm.verts.new((x0, y0 - 0.015, zz)), bm.verts.new((x1, y1 - 0.015, zz)), bm.verts.new((x1, y1 + 0.015, zz)), bm.verts.new((x0, y0 + 0.015, zz))]
            v2 = [bm.verts.new((a.co.x, a.co.y, zz + hh)) for a in v]
            for f in ((v[0], v[1], v[2], v[3]), (v2[3], v2[2], v2[1], v2[0]), (v[0], v2[0], v2[1], v[1]), (v[2], v2[2], v2[3], v[3])): bm.faces.new(f)
        o = obj_from_bm('top rail', bm, wood); box_uv(o, 1.0); kid(o, g)
    for i in range(5):
        t = (i + 1) / 6 - 0.5; xx = t * (w - 0.08); yy = d / 2 + 0.03 + 0.05 * (1 - (2 * t) ** 2)
        kid(rod('spindle', (xx, yy - 0.02, seat_h + 0.22), (xx, yy, back_h - 0.06), 0.009, wood, 8), g)
    return g

def stadium(name, length, width, z0, z1, mat, seg=24):
    """Long table top with rounded ends, length along y."""
    r = width / 2; half = length / 2 - r; pts = []
    for i in range(seg + 1): a = i / seg * math.pi; pts.append((math.cos(a) * r, half + math.sin(a) * r))
    for i in range(seg + 1): a = math.pi + i / seg * math.pi; pts.append((math.cos(a) * r, -half + math.sin(a) * r))
    bm = bmesh.new(); b = [bm.verts.new((x, y, z0)) for x, y in pts]; t = [bm.verts.new((x, y, z1)) for x, y in pts]
    bm.faces.new(t); bm.faces.new(list(reversed(b)))
    for i in range(len(pts)): j = (i + 1) % len(pts); bm.faces.new((b[i], b[j], t[j], t[i]))
    o = obj_from_bm(name, bm, mat); box_uv(o, 1.4); bv = o.modifiers.new('bevel', 'BEVEL'); bv.width = 0.015; bv.segments = 3; return o

def pedestal(x, y, wood, h):
    cyl('pedestal column', 0.11, h - 0.2, (x, y, 0.1 + (h - 0.2) / 2), (0, 0, 0), wood, 24)
    for z, rr in ((0.22, 0.15), (h - 0.18, 0.14), (0.5, 0.13)): torus('pedestal ring', rr, 0.03, (x, y, z), (0, 0, 0), wood)
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2; dx, dy = math.cos(a), math.sin(a)
        # a curved foot: three short segments sweeping down and out
        p0 = Vector((x, y, 0.24)); p1 = Vector((x + dx * 0.22, y + dy * 0.22, 0.14)); p2 = Vector((x + dx * 0.42, y + dy * 0.42, 0.05)); p3 = Vector((x + dx * 0.5, y + dy * 0.5, 0.03))
        for a_, b_, r in ((p0, p1, 0.05), (p1, p2, 0.042), (p2, p3, 0.036)): rod('foot', a_, b_, r, wood, 12)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.04, location=(p3.x, p3.y, 0.03), segments=12, ring_count=8); bpy.context.active_object.data.materials.append(wood)
    box('pedestal head', x - 0.45, x + 0.45, y - 0.06, y + 0.06, h - 0.2, h - 0.08, wood, 1.0, 0.01)

def chandelier(cx, cy, top, z, iron, lglass, r1=0.95, n1=8, r2=0.5, n2=5, s=1.0):
    cyl('chandelier chain', 0.012, top - (z + 0.9), (cx, cy, (top + z + 0.9) / 2), (0, 0, 0), iron, 6)
    cyl('chandelier column', 0.035, 0.95, (cx, cy, z + 0.42), (0, 0, 0), iron, 12)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.08, location=(cx, cy, z - 0.05)); bpy.context.active_object.data.materials.append(iron)
    torus('chandelier ring', r1, 0.022, (cx, cy, z), (0, 0, 0), iron); torus('chandelier ring', r2, 0.018, (cx, cy, z + 0.42), (0, 0, 0), iron)
    for k in range(n1):
        a = k / n1 * 2 * math.pi; ex, ey = cx + math.cos(a) * r1, cy + math.sin(a) * r1
        rod('chandelier arm', (cx, cy, z + 0.12), (ex, ey, z), 0.014, iron); rod('chandelier strut', (cx, cy, z + 0.6), (ex, ey, z + 0.02), 0.01, iron)
        # little iron scroll under each arm
        torus('scroll', 0.06, 0.008, ((cx + ex) / 2, (cy + ey) / 2, z - 0.06), (math.pi / 2, 0, a + math.pi / 2), iron)
        lantern(ex, ey, z + 0.02, 0.95 * s, None, iron, lglass, 50)
    for k in range(n2):
        a = (k + 0.5) / n2 * 2 * math.pi; ex, ey = cx + math.cos(a) * r2, cy + math.sin(a) * r2
        rod('chandelier arm', (cx, cy, z + 0.55), (ex, ey, z + 0.42), 0.012, iron)
        lantern(ex, ey, z + 0.44, 0.8 * s, None, iron, lglass, 40)
    lantern(cx, cy, z - 0.42, 0.9 * s, z - 0.12, iron, lglass, 45)

def build():
    floor = pbr('wood_floor_worn', 'materials', (0.6, 0.47, 0.35), 0.55, 1.0)
    plaster = pbr('clay_plaster', 'materials', (0.92, 0.8, 0.64), 1.0, 1.6)
    wall = pbr('plastered_stone_wall', 'materials', (1.35, 1.1, 0.8), 1.0, 1.1)
    boards = pbr('weathered_brown_planks', 'materials', (0.44, 0.33, 0.23), 0.9)
    beam = pbr('rough_wood', 'materials', (0.31, 0.23, 0.16), 0.9)
    timber = pbr('dark_wooden_planks', 'materials', (0.3, 0.21, 0.14), 0.9)
    cab = pbr('wood_cabinet_worn_long', 'materials', (0.46, 0.36, 0.27), 0.8)
    table_wood = pbr('wood_table_worn', 'materials', (0.66, 0.52, 0.38), 0.6)
    chair_wood = flat('chair wood', (0.13, 0.085, 0.055), 0.62)
    frame = flat('window frame', (0.45, 0.27, 0.14), 0.55)
    wtrim = pbr('oak_wood_planks', 'materials', (0.6, 0.37, 0.19), 0.9)      # light brown wood round the windows
    ptrim = pbr('oak_wood_planks', 'materials', (0.56, 0.34, 0.17), 0.9)              # light brown posts up the walls
    glass = flat('glass', (0.95, 0.97, 0.98), 0.02, transmission=1.0); lglass = flat('lantern glass', (1.0, 0.86, 0.66), 0.08, transmission=0.85)
    iron = flat('iron', (0.03, 0.028, 0.026), 0.55, 0.35)
    brass = flat('brass', (0.78, 0.55, 0.26), 0.3, 1.0)
    ceramic = flat('ceramic', (0.88, 0.84, 0.76), 0.25); ceramic2 = flat('ceramic blue', (0.42, 0.48, 0.55), 0.3); ceramic3 = flat('ceramic terracotta', (0.62, 0.32, 0.18), 0.5)
    jar_glass = flat('jar glass', (0.9, 0.93, 0.9), 0.05, transmission=0.9)
    fills = [flat('fill grain', (0.78, 0.62, 0.38), 0.8), flat('fill beans', (0.35, 0.16, 0.08), 0.6), flat('fill preserve', (0.55, 0.12, 0.08), 0.3), flat('fill herbs', (0.24, 0.3, 0.12), 0.8)]
    ivy = mat_alpha('ivy', A('assets', 'rooms', 'kitchen', 'ivy.png'))
    rug = mat_alpha('rug', K('rug_diff.png'), 0.95)
    petals = [flat('petal pink', (0.92, 0.45, 0.58), 0.6), flat('petal red', (0.62, 0.06, 0.1), 0.6), flat('petal white', (0.95, 0.92, 0.88), 0.6),
              flat('petal purple', (0.45, 0.2, 0.45), 0.6), flat('petal magenta', (0.8, 0.2, 0.45), 0.6)]
    wax = flat('wax', (0.92, 0.88, 0.78), 0.45)

    # ------------------------------------------------------------ shell: plank floor, arched plank ceiling, end walls
    box('floor', -HW - 0.3, HW + 0.3, -L - 0.3, 0.3, -0.12, 0.0, floor, 2.4)
    prof = profile()
    # the vault is built in short sections so the pieces behind the bay's diagonal walls can simply be left out
    ys = [0.0] + [-0.15 * k for k in range(1, int(BD / 0.15) + 3)] + [-L]
    bm = bmesh.new(); rings = [[bm.verts.new((x, y, z)) for x, z in prof] for y in ys]
    for j in range(len(ys) - 1):
        ym = (ys[j] + ys[j + 1]) / 2
        for i in range(len(prof) - 1):
            xm = (prof[i][0] + prof[i + 1][0]) / 2
            if ym > -BD and abs(xm) > BA + (-ym) * (HW - BA) / BD + 0.05: continue
            bm.faces.new((rings[j][i + 1], rings[j][i], rings[j + 1][i], rings[j + 1][i + 1]))
    shell = obj_from_bm('vault', bm, boards, True); shell.data.materials.append(plaster)
    for p in shell.data.polygons: p.material_index = 1 if p.center.z < WALL_H - 0.01 else 0
    box_uv(shell, 2.0); sol = shell.modifiers.new('s', 'SOLIDIFY'); sol.thickness = 0.3; sol.offset = 1
    def end_wall(name, y, thick):
        bm = bmesh.new(); vs = [bm.verts.new((x, y, z)) for x, z in prof]; bm.faces.new(vs); w = obj_from_bm(name, bm, plaster)
        s = w.modifiers.new('s', 'SOLIDIFY'); s.thickness = thick; s.offset = 1.0 if y > -1 else -1.0
        bpy.context.view_layer.objects.active = w; bpy.ops.object.modifier_apply(modifier='s'); return w
    back = end_wall('back wall', 0.0, 0.45); front = end_wall('front wall', -L, 0.45)
    # heavy arched ribs, straight tie beams, longitudinal purlins and a ridge, all rough timber
    rib = profile(40, 0.02)[1:-1]; RIBS = [-0.35 - k * 1.6 for k in range(7)]
    BAY_TRIM = []
    for y in RIBS[1:]: (BAY_TRIM.append if y > -2.6 else (lambda o: None))(sweep_profile('rib', [(prof[1][0] + 0.03, 0.0)] + rib + [(prof[-2][0] - 0.03, 0.0)], y, 0.3, 0.32, beam))
    for y in RIBS[1:-1:2]:
        zt = WALL_H + 0.55; hx = vault_x(zt) - 0.05; tb = box('tie beam', -hx, hx, y - 0.17, y + 0.17, zt - 0.3, zt, beam, 1.2)
        if y > -2.6: BAY_TRIM.append(tb)
        for s in (-1, 1): rod('brace', (s * (HW - INNER), y, WALL_H - 0.4), (s * (hx - 0.6), y, zt - 0.3), 0.08, beam, 8)
    box('ridge', -0.16, 0.16, -L, 0.0, APEX - 0.34, APEX - 0.02, beam, 1.2)
    for s in (-1, 1):
        xp = s * 2.1; box('purlin', xp - 0.13, xp + 0.13, -L, -0.5, vault_z(xp, 0.25) - 0.26, vault_z(xp, 0.25), beam, 1.2)
        box('wall plate', s * (HW - INNER) - 0.14, s * (HW - INNER) + 0.14, -L, -1.9, WALL_H - 0.12, WALL_H + 0.12, beam, 1.2)
    # inner plaster wall layer with arched niches, and timber posts at every other rib
    NICHES = {-1: (-3.55, -6.75), 1: (-3.55, -9.15)}; INNER_WALLS = []
    for s in (-1, 1):
        x0, x1 = (s * HW - INNER, s * HW) if s > 0 else (s * HW, s * HW + INNER)
        iw = box('inner wall', x0, x1, -L, 0.0, 0.0, WALL_H - 0.1, plaster, 2.0); INNER_WALLS.append(iw)
        cuts = []
        for ny in NICHES[s]: cuts += arch_cutter_x(ny, 1.1, 1.25, 0.85, (x1 - 0.3) if s < 0 else (x0 - 0.2), (x1 + 0.2) if s < 0 else (x0 + 0.3))
        cut(iw, cuts); box_uv(iw, 2.0)
        for ny in NICHES[s]:
            xi = x1 if s < 0 else x0; xb = xi - s * 0.28
            g = group((xi + s * -0.02, ny, 0.85), math.pi / 2); stone_arch(g, 1.1, 1.25, 0.08, timber, 0.12)
            for z in (1.3, 1.75): shelf(min(xi, xb), max(xi, xb), ny - 0.52, ny + 0.52, z, timber)
            box('niche sill', min(xi, xb) - 0.02, max(xi, xb) + 0.06, ny - 0.62, ny + 0.62, 0.8, 0.86, timber, 1.0)
            xc = (xi + xb) / 2
            model('ceramic_vase_04', (xc, ny - 0.3, 0.86), 0, height=0.3); model('brass_vase_02', (xc, ny + 0.3, 0.86), 0, height=0.34); candle((xc, ny, 0.86), 0.16, 6)
            plates_row(ny - 0.45, ny + 0.45, xc, 1.3, False, 3, rnd.choice([ceramic, ceramic2]))
            jars_row(ny - 0.45, ny + 0.45, xc, 1.75, False, 4, jar_glass, fills, brass)
            model('ceramic_vase_03', (xc, ny, 2.2 - 0.05), 0, height=0.22) if False else None
            light((xc + s * -0.15, ny, 1.95), 45, radius=0.15); light((xc, ny, 1.05), 25, radius=0.1)
        for y in RIBS[1::2] + [RIBS[-1]]:
            xp = (x0 - 0.12) if s > 0 else (x1 + 0.12); box('wall post', xp - 0.14, xp + 0.14, y - 0.15, y + 0.15, 0.0, WALL_H, ptrim, 1.2)
        for y in RIBS[1::2]:
            xp = (x0 - 0.3) if s > 0 else (x1 + 0.3); lantern(xp, y, 1.75, 1.0, None, iron, lglass, 80)
            box('sconce arm', min(xp, xp + s * 0.2), max(xp, xp + s * 0.2), y - 0.015, y + 0.015, 2.12, 2.15, iron, 1.0); cyl('sconce drop', 0.008, 0.07, (xp, y, 2.1), (0, 0, 0), iron, 6)
    # ------------------------------------------------------------ the bay at the far end: a short straight back wall with two arched windows
    # and a diagonal wall in each corner with one more window each (four windows, like the image)
    WZ = 0.85; WW, WRH = 1.15, 1.75
    cut(back, sum((arch_cutter_y(wx, WW, WRH, WZ, -0.2, 0.8) for wx in (-0.95, 0.95)), []))
    box_uv(back, 2.0)
    for wx in (-0.95, 0.95):
        g = group((wx, 0.22, WZ)); arch_window(g, WW, WRH, 3, 3, frame, glass, 5, ring=False)
        g2 = group((wx, 0.0, WZ)); stone_arch(g2, WW, WRH, 0.14, wtrim, 0.15)
        box('sill', wx - WW / 2 - 0.1, wx + WW / 2 + 0.1, -0.12, 0.25, WZ - 0.06, WZ, wtrim, 1.0)
        a = light((wx, 1.5, WZ + 1.1), 520, (0.85, 0.95, 0.85), kind='AREA'); a.data.size = WW; a.rotation_euler = (math.radians(90), 0, 0)
    DW, DRH = 1.15, 1.5
    for sgn in (-1, 1):
        p0 = Vector((sgn * BA, 0.0)); p1 = Vector((sgn * HW, -BD)); d = (p1 - p0); ln = d.length; u = d / ln
        ang = math.atan2(u.y, u.x) if sgn > 0 else math.atan2(-u.y, -u.x)            # local x along the wall
        nrm = Vector((-math.sin(ang), math.cos(ang)))                                  # local +y, pointing out of the room
        # the wall: bottom along the floor, top following the vault, thickened outward
        bm = bmesh.new(); n = 24; bot = [bm.verts.new((p0.x + d.x * t, p0.y + d.y * t, 0.0)) for t in (0.0, 1.0)]
        top = [bm.verts.new((p0.x + d.x * (k / n), p0.y + d.y * (k / n), vault_z(p0.x + d.x * (k / n)) + 0.15)) for k in range(n + 1)]
        bm.faces.new([bot[0], bot[1]] + list(reversed(top)))
        dw = obj_from_bm('bay wall', bm, plaster); sl = dw.modifiers.new('s', 'SOLIDIFY'); sl.thickness = 0.42
        bpy.context.view_layer.objects.active = dw; bpy.ops.object.modifier_apply(modifier='s')
        # make sure the thickness went outward: if the wall centre moved inward, flip it
        c = sum((v.co for v in dw.data.vertices), Vector()) / len(dw.data.vertices); mid = (p0 + p1) / 2
        if (Vector((c.x, c.y)) - mid).dot(nrm) < 0: dw.location = (nrm.x * 0.42, nrm.y * 0.42, 0)
        mid3 = Vector((mid.x, mid.y, 0))
        cutters = arch_cutter_y(0.0, DW, DRH, WZ, -0.8, 0.8)
        for cobj in cutters:
            cobj.rotation_euler = (cobj.rotation_euler.x, cobj.rotation_euler.y, ang); cobj.location = (mid.x + cobj.location.x * math.cos(ang), mid.y + cobj.location.x * math.sin(ang), cobj.location.z)
        bpy.context.view_layer.update(); cut(dw, cutters); box_uv(dw, 2.0)
        g = group((mid.x + nrm.x * 0.22, mid.y + nrm.y * 0.22, WZ), ang); arch_window(g, DW, DRH, 3, 3, frame, glass, 5, ring=False)
        g2 = group((mid.x, mid.y, WZ), ang); stone_arch(g2, DW, DRH, 0.14, wtrim, 0.15)
        g3 = group((mid.x, mid.y, WZ), ang); kid(box('sill', -DW / 2 - 0.1, DW / 2 + 0.1, -0.12, 0.25, -0.06, 0.0, wtrim, 1.0), g3)
        a = light((mid.x + nrm.x * 1.5, mid.y + nrm.y * 1.5, WZ + 1.0), 450, (0.85, 0.95, 0.85), kind='AREA'); a.data.size = DW; a.rotation_euler = (math.radians(90), 0, ang)
        # clear out everything behind the diagonal wall so its window looks out onto the garden
        def corner_cutter():
            cb = box('c', -5, 5, 0.5, 9, -1, 7, flat('cut', (1, 1, 1))); cb.rotation_euler = (0, 0, ang); cb.location = (mid.x, mid.y, 0); return cb
        for tgt in [back] + INNER_WALLS + BAY_TRIM:
            bpy.context.view_layer.update(); cut(tgt, [corner_cutter()])
        # its own garden backdrop, facing the window
        bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1); bmesh.ops.scale(bm, vec=(60, 39, 1), verts=bm.verts)
        bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 4, 'X'))
        vw = obj_from_bm('garden view', bm, image_mat('view', K('view.jpg'), 1.0)); uvl = vw.data.uv_layers.new()
        for i_, l_ in enumerate(uvl.data): co = vw.data.vertices[vw.data.loops[i_].vertex_index].co; l_.uv = (co.x / 60 + 0.5 + 0.25 * sgn, co.z / 39 + 0.5)
        vw.rotation_euler = (0, 0, ang); vw.location = (mid.x + nrm.x * 20, mid.y + nrm.y * 20, 7.0)
        # timber post in each corner of the bay, where the walls meet
        for q in (p0, p1): box('bay post', q.x - 0.13, q.x + 0.13, q.y - 0.13, q.y + 0.13, 0.0, vault_z(q.x) - 0.05, ptrim, 1.2)
        # a low cabinet under each diagonal window with candles and flowers, a spare chair beside it
        g4 = group((mid.x - nrm.x * 0.3, mid.y - nrm.y * 0.3, 0.0), ang)
        for o in (box('bay cabinet', -0.7, 0.7, -0.24, 0.24, 0.1, 0.74, cab, 1.0, 0.01), box('bay cabinet top', -0.74, 0.74, -0.27, 0.27, 0.74, 0.79, table_wood, 1.0, 0.01),
                  box('bay plinth', -0.66, 0.66, -0.2, 0.2, 0.0, 0.1, cab, 1.0)): kid(o, g4)
        for k in range(2): kid(box('bay door', -0.66 + k * 0.67, -0.02 + k * 0.67, -0.27, -0.245, 0.16, 0.68, cab, 1.0, 0.005), g4)
        cpos = mid - nrm * 0.3
        model('brass_candleholders', (cpos.x - u.x * 0.4 * sgn, cpos.y - u.y * 0.4 * sgn, 0.79), ang, width=0.3)
        model('ceramic_vase_02', (cpos.x + u.x * 0.4 * sgn, cpos.y + u.y * 0.4 * sgn, 0.79), 0, height=0.22); bouquet(cpos.x + u.x * 0.4 * sgn, cpos.y + u.y * 0.4 * sgn, 0.99, petals, ivy, 12, 0.12)
    # a wall clock above and a lantern between the two back windows, plants either side
    model('wall_clock', (0.0, -0.06, 3.05), 0, width=0.4).rotation_euler = (math.radians(90), 0, 0)
    box('sconce arm', -0.015, 0.015, -0.25, 0.0, 2.55, 2.58, iron, 1.0); lantern(0.0, -0.25, 2.2, 0.85, 2.56, iron, lglass, 40)
    for sx in (-1, 1): model('potted_plant_02', (sx * 1.65, -0.5, 0), sx, height=0.8)

    # ------------------------------------------------------------ the long table, chairs, rug, centrepiece and candles
    TL, TWD, TH, TC = 6.3, 1.35, 0.78, -6.1
    stadium('table top', TL, TWD, TH - 0.08, TH, table_wood).location.y = TC
    stadium('table apron', TL - 0.35, TWD - 0.3, TH - 0.18, TH - 0.08, table_wood).location.y = TC
    for dy in (-2.0, 0.0, 2.0): pedestal(0, TC + dy, table_wood, TH - 0.08)
    box('table stretcher', -0.05, 0.05, TC - 2.0, TC + 2.0, 0.3, 0.38, table_wood, 1.0)
    n = 8; span = TL - 1.6
    for i in range(n):
        y = TC - span / 2 + i * span / (n - 1)
        spindle_chair(-TWD / 2 - 0.12, y + rnd.uniform(-0.04, 0.04), math.pi / 2 + rnd.uniform(-0.08, 0.08), chair_wood)
        spindle_chair(TWD / 2 + 0.12, y + rnd.uniform(-0.04, 0.04), -math.pi / 2 + rnd.uniform(-0.08, 0.08), chair_wood)
    spindle_chair(0, TC - TL / 2 - 0.25, 0.0 + math.pi, chair_wood); spindle_chair(0, TC + TL / 2 + 0.25, 0.0, chair_wood)
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5); uvl = bm.loops.layers.uv.new()
    for f in bm.faces:
        for l in f.loops: l[uvl].uv = (l.vert.co.y + 0.5, l.vert.co.x + 0.5)
    o = obj_from_bm('rug', bm, rug); o.scale = (3.9, 8.2, 1); o.location = (0, TC, 0.007)
    # centrepiece: a low bowl overflowing with flowers, a pillar candle in a glass hurricane, candlesticks
    model('wooden_bowl_01', (0, TC + 0.1, TH), 0, width=0.5); bouquet(0, TC + 0.1, TH + 0.08, petals, ivy, 46, 0.32)
    leaf_cluster(ivy, 0, TC + 0.1, TH + 0.1, 16, 0.42, 0.0, (0.12, 0.22))
    cyl('pillar candle', 0.055, 0.22, (0.05, TC - 0.75, TH + 0.11), (0, 0, 0), wax, 24); candle((0.05, TC - 0.75, TH + 0.215), 0.01, 18)
    cyl('hurricane', 0.1, 0.32, (0.05, TC - 0.75, TH + 0.16), (0, 0, 0), glass, 32); cyl('hurricane base', 0.11, 0.02, (0.05, TC - 0.75, TH + 0.01), (0, 0, 0), brass, 32)
    for dy in (-2.1, 1.0, 2.1):
        model('wooden_candlestick', (0, TC + dy, TH), 0, height=0.22); candle((0, TC + dy, TH + 0.2), 0.18, 10)
    # ------------------------------------------------------------ left wall front: built-in hutch with plates; right wall: sideboard, armchair
    LX = -HW + INNER
    cabinet_run(LX, LX + 0.55, -9.85, -8.45, '+x', cab, table_wood, brass, 0.5, 0.9)
    box('hutch back', LX, LX + 0.06, -9.85, -8.45, 0.9, WALL_H - 0.15, cab, 1.0)
    for z in (1.35, 1.8, 2.2): shelf(LX, LX + 0.34, -9.85, -8.45, z, cab)
    for yy in (-9.85, -8.45): box('hutch side', LX, LX + 0.36, yy - 0.03, yy + 0.03, 0.9, WALL_H - 0.15, cab, 1.0)
    box('hutch crown', LX, LX + 0.42, -9.9, -8.4, WALL_H - 0.18, WALL_H - 0.08, cab, 1.0, 0.01)
    plates_row(-9.75, -8.55, LX + 0.17, 1.35, False, 7, ceramic); plates_row(-9.75, -8.55, LX + 0.17, 1.8, False, 6, ceramic2); jars_row(-9.75, -8.55, LX + 0.18, 2.2, False, 6, jar_glass, fills, brass)
    model('brass_candleholders', (LX + 0.3, -9.15, 0.9), math.pi / 2, width=0.4); light((LX + 0.5, -9.15, 2.0), 40, radius=0.2)
    RX = HW - INNER
    cabinet_run(RX - 0.55, RX, -7.45, -5.95, '-x', cab, table_wood, brass, 0.53, 0.86)
    model('fancy_picture_frame_01', (RX - 0.05, -6.7, 1.35), -math.pi / 2, width=0.75)
    shelf(RX - 0.3, RX, -8.2, -4.4, 2.05, cab); plates_row(-8.1, -4.5, RX - 0.15, 2.05, False, 10, ceramic)
    shelf(RX - 0.3, RX, -8.2, -4.4, 1.85 - 0.0, cab) if False else None
    jars_row(-8.1, -4.5, RX - 0.16, 2.05, False, 0, jar_glass, fills, brass) if False else None
    model('ceramic_pot', (RX - 0.3, -7.2, 0.86), 0, width=0.32); model('brass_candleholders', (RX - 0.3, -6.3, 0.86), math.pi / 2, width=0.34)
    model('ArmChair_01', (RX - 0.75, -2.75, 0), -math.pi / 2 - 0.35, width=0.82); model('WoodenTable_02', (RX - 0.4, -3.0 + 0.0, 0), 0, height=0.6) if False else model('WoodenTable_02', (RX - 0.35, -2.05, 0), 0, height=0.6)
    candle((RX - 0.35, -2.05, 0.62), 0.14, 6); model('potted_plant_01', (-RX + 0.45, -2.0, 0), 0.3, height=1.3)
    model('vintage_cabinet_01', (-RX + 0.3, -1.2 - 1.3, 0), math.pi / 2, width=1.0) if False else None
    model('potted_plant_01', (RX - 0.45, -L + 0.5, 0), 1.0, height=1.4); model('potted_plant_01', (-RX + 0.45, -L + 0.55, 0), 2.0, height=1.3)
    # ------------------------------------------------------------ fuller room: cabinets under the niches, place settings, spare chairs, greenery
    for s in (-1, 1):
        xi = (-HW + INNER) if s < 0 else (HW - INNER)
        for ny in NICHES[s]:
            cabinet_run(min(xi, xi - s * 0.45), max(xi, xi - s * 0.45), ny - 0.62, ny + 0.62, '+x' if s < 0 else '-x', cab, table_wood, brass, 0.62, 0.78)
            model('wooden_bowl_02', (xi - s * 0.22, ny - 0.35, 0.78), 0, width=0.2); model('ceramic_vase_04', (xi - s * 0.22, ny + 0.35, 0.78), 0, height=0.26)
            candle((xi - s * 0.22, ny, 0.78), 0.2, 6)
    goblet_glass = flat('goblet glass', (0.95, 0.9, 0.85), 0.05, transmission=0.9)
    for i in range(n):
        y = TC - span / 2 + i * span / (n - 1)
        for s in (-1, 1):
            cyl('plate', 0.13, 0.015, (s * (TWD / 2 - 0.22), y, TH + 0.008), (0, 0, 0), ceramic, 32)
            cyl('plate rim', 0.1, 0.017, (s * (TWD / 2 - 0.22), y, TH + 0.01), (0, 0, 0), flat('plate centre', (0.82, 0.76, 0.66), 0.25), 32)
            gx, gy = s * (TWD / 2 - 0.4), y + 0.17
            cyl('goblet base', 0.035, 0.008, (gx, gy, TH + 0.004), (0, 0, 0), brass, 16); cyl('goblet stem', 0.007, 0.09, (gx, gy, TH + 0.05), (0, 0, 0), brass, 8)
            bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=False, segments=16, radius1=0.022, radius2=0.042, depth=0.09); gob = obj_from_bm('goblet', bm, goblet_glass, True); gob.location = (gx, gy, TH + 0.14)
    for dy in (-1.55, 1.55): fruit = model('wooden_bowl_01', (0.0, TC + dy, TH), 0, width=0.36)
    for dy in (-1.55, 1.55):
        for k, (nm, hh) in enumerate((('food_apple_01', 0.08), ('food_pomegranate_01', 0.09), ('lemon', 0.08), ('food_pears_asian_01', 0.09), ('food_apple_01', 0.08))):
            a_ = k / 5 * 6.28; model(nm, (0.08 * math.cos(a_), TC + dy + 0.08 * math.sin(a_), TH + 0.05), k, height=hh)
    model('brass_candleholders', (0, TC + 2.6, TH), math.pi / 2, width=0.4); model('brass_candleholders', (0, TC - 2.6, TH), math.pi / 2, width=0.4)
    for x, y, r in ((-2.95, -2.6, 1.3), (2.6, -9.9, 2.5)): spindle_chair(x, y, r, chair_wood)
    for y in RIBS[1:-1:2]:
        for k in range(5): leaf_cluster(ivy, -1.6 + k * 0.8, y, WALL_H + 0.6, 7, 0.22, 0.45 if k % 2 else 0.15)
    for s in (-1, 1):
        for y in RIBS[1::2]: leaf_cluster(ivy, s * (HW - INNER - 0.15), y, WALL_H + 0.05, 10, 0.25, 0.8)
    # ------------------------------------------------------------ chandeliers
    chandelier(0, TC + 0.4, APEX - 0.3, 2.55, iron, lglass)
    chandelier(0, -1.6, APEX - 0.3, 2.75, iron, lglass, 0.55, 5, 0.3, 0, 0.85)
    # ------------------------------------------------------------ front wall with the doorway to the rest of the house
    cut(front, arch_cutter_y(2.4, 1.4, 1.6, 0.0, -L - 1, -L + 1)); box_uv(front, 2.0)
    g = group((2.4, -L, 0.0)); stone_arch(g, 1.4, 1.6, 0.6, timber, 0.18)
    box('passage floor', 1.5, 3.3, -L - 2.5, -L, -0.12, 0.0, floor, 2.4); box('passage end', 1.4, 3.4, -L - 2.6, -L - 2.4, 0.0, 2.6, plaster, 2.0)
    for x0, x1 in ((1.35, 1.6), (3.2, 3.45)): box('passage wall', x0, x1, -L - 2.6, -L - 0.2, 0.0, 2.6, plaster, 2.0)
    box('passage ceiling', 1.35, 3.45, -L - 2.6, -L - 0.2, 2.45, 2.65, timber, 1.2); light((2.4, -L - 1.3, 2.0), 50)
    cabinet_run(-3.6, -0.6, -L + 0.02, -L + 0.55, '+y', cab, table_wood, brass, 0.6, 0.86)
    for z in (1.45, 1.9): shelf(-3.6, -0.6, -L + 0.02, -L + 0.3, z, cab)
    plates_row(-3.5, -0.7, -L + 0.15, 1.45, True, 9, ceramic); jars_row(-3.5, -0.7, -L + 0.16, 1.9, True, 8, jar_glass, fills, brass)
    lantern(-2.1, -L + 0.3, 2.2, 1.0, 2.6, iron, lglass, 40)
    # ------------------------------------------------------------ outside: the garden behind the windows
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1); bmesh.ops.scale(bm, vec=(60, 39, 1), verts=bm.verts)
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 4, 'X')); bmesh.ops.translate(bm, vec=(0, 22, 7.0), verts=bm.verts)
    view = obj_from_bm('garden view', bm, image_mat('view', K('view.jpg'), 1.0)); uvl = view.data.uv_layers.new()
    for i, l in enumerate(uvl.data): co = view.data.vertices[view.data.loops[i].vertex_index].co; l.uv = (co.x / 60 + 0.5, (co.z - 7.0) / 39 + 0.5)
    w = bpy.data.worlds.new('w'); bpy.context.scene.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0.6, 0.68, 0.6, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.3
    for y in (-3.5, -8.5):
        f = light((0, y, APEX - 0.9), 90, (1.0, 0.72, 0.45), kind='AREA'); f.data.size = 3.0

def walk_rects():
    R = [(-2.75, 2.75, -10.6, -9.95),          # front strip
         (-2.75, -1.5, -10.6, -1.6),            # left aisle
         (1.5, 2.75, -10.6, -1.6),              # right aisle
         (-2.25, 2.25, -2.45, -0.8),            # back strip by the windows
         (1.85, 2.95, -L - 2.2, -11.4)]         # doorway passage
    return [[x0, x1, -y1, -y0] for x0, x1, y0, y1 in R]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--render', default=''); ap.add_argument('--samples', type=int, default=96); ap.add_argument('--res', default='1280x720')
    ap.add_argument('--glb', default=''); ap.add_argument('--blend', default=''); ap.add_argument('--cam', default=f'0,{-L + 0.55},1.62,88,0,17')
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
    bpy.ops.wm.read_factory_settings(use_empty=True); build()
    for l in bpy.data.lights:
        if tuple(round(c, 2) for c in l.color) == (1.0, 0.68, 0.38): l.color = (1.0, 0.76, 0.52)
    for o in bpy.context.scene.objects:
        if o.type == 'LIGHT' and hasattr(o, 'visible_camera'): o.visible_camera = False
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = a.samples; sc.cycles.use_denoising = True; sc.cycles.max_bounces = 8
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'; sc.view_settings.exposure = 0.95
    w, h = map(int, a.res.split('x')); sc.render.resolution_x, sc.render.resolution_y = w, h
    x, y, z, tilt, head, lens = map(float, a.cam.split(',')); cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera')); sc.collection.objects.link(cam); sc.camera = cam
    cam.location = (x, y, z); cam.rotation_euler = (math.radians(tilt), 0, math.radians(head)); cam.data.lens = lens
    cfgp = K('room.json'); cfg = json.load(open(cfgp)) if os.path.exists(cfgp) else {}
    tints = {}
    for m in bpy.data.materials:
        if m.use_nodes:
            for n in m.node_tree.nodes:
                if n.type == 'MIX_RGB' and n.blend_type == 'MULTIPLY': tints[m.name] = [round(v, 3) for v in n.inputs[2].default_value[:3]]
    cfg.update(name='Dining Room', glb='assets/rooms/dining/dining.glb', spawn=dict(x=0, z=L - 0.65, yaw=0), walk=walk_rects(), lights=LIGHTS, probe=[0, 1.4, 6.1], tints=tints, floor='wood_floor_worn')
    cfg.setdefault('exposure', 1.0); cfg.setdefault('version', 1); cfg.setdefault('wallBoost', 1.25); cfg.setdefault('maxFlameLights', 34)
    json.dump(cfg, open(cfgp, 'w'), indent=1)
    if a.blend: bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.blend))
    if a.render: sc.render.filepath = os.path.abspath(a.render); bpy.ops.render.render(write_still=True)
    if a.glb:
        keep = ('stone', 'plaster', 'planks', 'wood_floor', 'rough_wood', 'wood_cabinet', 'wood_table', 'view', 'rug', 'ivy')
        for im in bpy.data.images:
            if im.size[0] > 512 and not any(k in im.name for k in keep): im.scale(512, 512)
        bpy.ops.object.select_all(action='DESELECT')
        for o in list(sc.objects):
            if o.type == 'EMPTY' and o.instance_type == 'COLLECTION': o.select_set(True)
        if any(o.select_get() for o in sc.objects): bpy.ops.object.duplicates_make_real()
        bpy.ops.export_scene.gltf(filepath=os.path.abspath(a.glb), export_format='GLB', export_lights=False, export_cameras=False, export_apply=True, export_image_format='JPEG', export_jpeg_quality=82)

if __name__ == '__main__':
    main()
