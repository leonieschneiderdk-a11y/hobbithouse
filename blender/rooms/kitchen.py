"""Hobbit-house kitchen, rebuilt as a real 3D room from the 'Indoor kitchen' image.

    python blender/rooms/kitchen.py --render docs/rooms/kitchen.png --samples 128 --res 1600x900 --glb assets/rooms/kitchen/kitchen.glb

Blender axes: the back wall with the two arched windows is at y = 0, the room runs toward the camera to y = -L,
x is left/right (range cooker and hearth on the left wall, dining table on the right), z is up.
The script also writes assets/rooms/kitchen/room.json for the walkable page (spawn, walkable areas, lights).
"""
import argparse, json, math, os, sys, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bpy, bmesh
from mathutils import Vector, Matrix
from hero_room import A, pbr, flat, image_mat, obj_from_bm, box_uv, box, cyl, torus, cut, sweep_profile, model, light, candle

W, L = 10.0, 13.0                     # width, length
HW = W / 2
WALL_H, APEX = 2.7, 4.7               # where the vault starts to curve, and its crown
CTR = 0.92                            # counter height
rnd = random.Random(21)
LIGHTS = []                           # extra point lights for the walkable page (three.js coords)
KDIR = os.path.join('rooms', 'kitchen')

def K(*p): return A('assets', 'rooms', 'kitchen', *p)

def vault_z(x, inset=0.0):
    t = max(-1.0, min(1.0, x / (HW - inset)))
    return WALL_H + math.sqrt(max(0.0, 1 - t * t)) * (APEX - WALL_H - inset)

def profile(n=40, inset=0.0):
    pts = [(-HW + inset, 0.0)]
    for i in range(n + 1):
        a = math.pi - i / n * math.pi
        pts.append((math.cos(a) * (HW - inset), WALL_H + math.sin(a) * (APEX - WALL_H - inset)))
    pts.append((HW - inset, 0.0)); return pts

def mat_alpha(name, img_path, rough=0.6):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; b = nt.nodes['Principled BSDF']
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(img_path)
    nt.links.new(t.outputs['Color'], b.inputs['Base Color']); nt.links.new(t.outputs['Alpha'], b.inputs['Alpha']); b.inputs['Roughness'].default_value = rough
    for attr, val in (('blend_method', 'CLIP'), ('surface_render_method', 'DITHERED')):
        try: setattr(m, attr, val)
        except Exception: pass
    return m

def tex_mat(name, diff, rough_img=None, rough=0.5, tint=(1, 1, 1)):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; b = nt.nodes['Principled BSDF']
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(diff)
    mix = nt.nodes.new('ShaderNodeMixRGB'); mix.blend_type = 'MULTIPLY'; mix.inputs[0].default_value = 1; mix.inputs[2].default_value = (*tint, 1)
    nt.links.new(t.outputs[0], mix.inputs[1]); nt.links.new(mix.outputs[0], b.inputs['Base Color'])
    if rough_img:
        r = nt.nodes.new('ShaderNodeTexImage'); r.image = bpy.data.images.load(rough_img); r.image.colorspace_settings.name = 'Non-Color'; nt.links.new(r.outputs[0], b.inputs['Roughness'])
    else: b.inputs['Roughness'].default_value = rough
    return m

def group(loc=(0, 0, 0), rot=0.0):
    g = bpy.data.objects.new('group', None); bpy.context.scene.collection.objects.link(g); g.location = loc; g.rotation_euler = (0, 0, rot); return g

def kid(o, g): o.parent = g; return o

def arch_cutter_y(cx, w, rect_h, z0, y0=-1.0, y1=1.0):
    """Arched opening through a wall that faces along y (box + half cylinder)."""
    b = box('c', cx - w / 2, cx + w / 2, y0, y1, z0, z0 + rect_h, flat('cut', (1, 1, 1)))
    c = cyl('c', w / 2, y1 - y0, (cx, (y0 + y1) / 2, z0 + rect_h), (math.pi / 2, 0, 0), flat('cut', (1, 1, 1)), 48)
    return [b, c]

def arch_cutter_x(cy, w, rect_h, z0, x0, x1):
    b = box('c', x0, x1, cy - w / 2, cy + w / 2, z0, z0 + rect_h, flat('cut', (1, 1, 1)))
    c = cyl('c', w / 2, x1 - x0, ((x0 + x1) / 2, cy, z0 + rect_h), (0, math.pi / 2, 0), flat('cut', (1, 1, 1)), 48)
    return [b, c]

def arch_window(g, w, rect_h, cols, rows, frame, glass, fan=5):
    """Arched window in local space: x across, z up, glass in the plane y = 0. Frame, glazing bars and a fan of bars in the arch."""
    t = 0.08
    for x0, x1, z0, z1 in ((-w / 2, -w / 2 + t, 0, rect_h), (w / 2 - t, w / 2, 0, rect_h), (-w / 2, w / 2, 0, t)):
        kid(box('win frame', x0, x1, -0.05, 0.05, z0, z1, frame, 1.0), g)
    bpy.ops.mesh.primitive_torus_add(major_radius=w / 2 - t / 2, minor_radius=t / 2, major_segments=48, minor_segments=8, location=(0, 0, rect_h), rotation=(math.pi / 2, 0, 0))
    o = bpy.context.active_object; o.scale = (1, 1, 1.25); o.data.materials.append(frame); kid(o, g)
    for i in range(1, cols): x = -w / 2 + i * w / cols; kid(box('bar', x - 0.018, x + 0.018, -0.03, 0.03, t, rect_h + math.sqrt(max(0, (w / 2) ** 2 - x * x)) - 0.05, frame, 1.0), g)
    for k in range(1, rows + 1): z = k * rect_h / (rows + 0.0001) if k < rows + 1 else rect_h; kid(box('bar', -w / 2 + t, w / 2 - t, -0.03, 0.03, min(z, rect_h) - 0.018, min(z, rect_h) + 0.018, frame, 1.0), g)
    bpy.ops.mesh.primitive_torus_add(major_radius=w / 4, minor_radius=0.018, major_segments=36, minor_segments=6, location=(0, 0, rect_h), rotation=(math.pi / 2, 0, 0))
    o = bpy.context.active_object; o.data.materials.append(frame); kid(o, g)
    for k in range(fan):
        a = (k + 1) / (fan + 1) * math.pi; bb = kid(box('fan bar', -0.016, 0.016, -0.03, 0.03, 0, w / 2 - 0.06, frame, 1.0), g); bb.location = (0, 0, rect_h); bb.rotation_euler = (0, a - math.pi / 2, 0)
    bm = bmesh.new(); vs = [bm.verts.new((-w / 2 + t, 0, 0.05)), bm.verts.new((w / 2 - t, 0, 0.05))]
    for i in range(33): a = i / 32 * math.pi; vs.append(bm.verts.new((math.cos(a) * (w / 2 - t), 0, rect_h + math.sin(a) * (w / 2 - t))))
    bm.faces.new([vs[0], vs[1]] + vs[2:]); kid(obj_from_bm('glass', bm, glass), g)

def stone_arch(g, w, rect_h, depth, mat, t=0.22):
    """Stone surround (jambs and voussoir ring) around an arched opening, local space like arch_window."""
    bpy.ops.mesh.primitive_torus_add(major_radius=w / 2 + t / 2, minor_radius=t / 2, major_segments=48, minor_segments=8, location=(0, 0, rect_h), rotation=(math.pi / 2, 0, 0))
    o = bpy.context.active_object; o.scale = (1, 1, depth / t); o.data.materials.append(mat); kid(o, g)
    for s in (-1, 1): kid(box('jamb', s * (w / 2 + t / 2) - t / 2, s * (w / 2 + t / 2) + t / 2, -depth / 2, depth / 2, 0, rect_h, mat, 0.9), g)

def lantern(x, y, z, s=1.0, top=None, iron=None, glass=None, power=45):
    """Black iron lantern with glass panes and a lit candle; hangs on a chain up to z = top if given."""
    w, h = 0.2 * s, 0.3 * s
    for dx in (-1, 1):
        for dy in (-1, 1): box('lantern post', x + dx * w / 2 - 0.012 * s, x + dx * w / 2 + 0.012 * s, y + dy * w / 2 - 0.012 * s, y + dy * w / 2 + 0.012 * s, z, z + h, iron, 1.0)
    box('lantern base', x - w / 2 - 0.02 * s, x + w / 2 + 0.02 * s, y - w / 2 - 0.02 * s, y + w / 2 + 0.02 * s, z - 0.03 * s, z, iron, 1.0)
    box('lantern head', x - w / 2 - 0.015 * s, x + w / 2 + 0.015 * s, y - w / 2 - 0.015 * s, y + w / 2 + 0.015 * s, z + h, z + h + 0.025 * s, iron, 1.0)
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=4, radius1=w * 0.78, radius2=0.015 * s, depth=0.13 * s)
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.pi / 4, 3, 'Z')); o = obj_from_bm('lantern cap', bm, iron); o.location = (x, y, z + h + 0.09 * s)
    torus('lantern ring', 0.035 * s, 0.007 * s, (x, y, z + h + 0.19 * s), (math.pi / 2, 0, 0), iron)
    for dx, dy, sx, sy in ((0, -1, 1, 0), (0, 1, 1, 0), (-1, 0, 0, 1), (1, 0, 0, 1)):
        box('glass', x + dx * w / 2 - (w / 2 - 0.012 * s) * sx - 0.002, x + dx * w / 2 + (w / 2 - 0.012 * s) * sx + 0.002,
            y + dy * w / 2 - (w / 2 - 0.012 * s) * sy - 0.002, y + dy * w / 2 + (w / 2 - 0.012 * s) * sy + 0.002, z + 0.01, z + h - 0.01, glass, 1.0)
    candle((x, y, z), 0.12 * s, 0)
    cyl('lantern glow', 0.035 * s, 0.1 * s, (x, y, z + 0.2 * s), (0, 0, 0), flat('lanternglow', (1, 0.6, 0.3), 1, emit=(1.0, 0.5, 0.18), strength=3.5), 12)
    light((x, y, z + 0.18 * s), power, radius=0.05)
    if top: cyl('chain', 0.008, top - (z + h + 0.21 * s), (x, y, (top + z + h + 0.21 * s) / 2), (0, 0, 0), iron, 6)

def pan(x, y, z, r, rot, copper, iron):
    """Copper pan hanging by its handle from a hook at (x, y, z); the pan face points along the local y axis."""
    g = group((x, y, z), rot)
    kid(cyl('pan', r, 0.06, (0, 0, -0.24 - r), (math.pi / 2, 0, 0), copper, 32), g)
    t = torus('pan rim', r, 0.008, (0, 0, -0.24 - r), (math.pi / 2, 0, 0), copper); kid(t, g); t.location = (0, 0.03, -0.24 - r)
    kid(box('pan handle', -0.012, 0.012, -0.01, 0.01, -0.25, -0.01, iron, 1.0), g)
    kid(torus('hook', 0.018, 0.004, (0, 0, 0.0), (math.pi / 2, 0, 0), iron), g)

def pot(x, y, z, r, h, rot, copper, iron):
    g = group((x, y, z), rot)
    kid(cyl('pot', r, h, (0, 0, -0.3 - h / 2), (0, 0, 0), copper, 32), g); kid(torus('pot rim', r, 0.01, (0, 0, -0.3), (0, 0, 0), copper), g)
    for s in (-1, 1): kid(torus('pot ear', 0.03, 0.007, (s * (r + 0.02), 0, -0.33), (math.pi / 2, 0, 0), copper), g)
    kid(cyl('pot hanger', 0.004, 0.3, (0, 0, -0.15), (0, 0, 0), iron, 6), g)

def ladder_chair(x, y, rot, wood, rush, seat=0.74, back=1.1, w=0.42, d=0.4):
    """Ladder-back chair or bar stool with a woven rush seat; it faces local -y (backrest at +y)."""
    g = group((x, y, 0), rot); r = 0.02
    for sx in (-1, 1):
        kid(cyl('leg', r, seat, (sx * (w / 2 - r), -d / 2 + r, seat / 2), (0, 0, 0), wood, 10), g)
        kid(cyl('back post', r * 1.1, back, (sx * (w / 2 - r), d / 2 - r, back / 2), (0, 0, 0), wood, 10), g)
        for zz in (seat * 0.3, seat * 0.62): kid(cyl('rung', 0.011, d - 2 * r, (sx * (w / 2 - r), 0, zz), (math.pi / 2, 0, 0), wood, 8), g)
    for zz in (seat * 0.3, seat * 0.62):
        for sy in (-1, 1): kid(cyl('rung', 0.011, w - 2 * r, (0, sy * (d / 2 - r), zz + 0.04 * sy), (0, math.pi / 2, 0), wood, 8), g)
    kid(box('seat', -w / 2, w / 2, -d / 2, d / 2, seat - 0.04, seat, rush, 0.25), g)
    for sy in (-1, 1): kid(box('seat rail', -w / 2 - 0.005, w / 2 + 0.005, sy * d / 2 - 0.015, sy * d / 2 + 0.015, seat - 0.05, seat - 0.01, wood, 1.0), g)
    n = 3 if back - seat > 0.3 else 2
    for k in range(n):
        zz = seat + 0.12 + k * (back - seat - 0.2) / max(1, n - 1)
        kid(box('slat', -w / 2 + r, w / 2 - r, d / 2 - r - 0.012, d / 2 - r + 0.012, zz, zz + 0.06, wood, 1.0, 0.004), g)
    return g

def cabinet_run(x0, x1, y0, y1, face, wood, top_mat, knob, unit=0.6, h=CTR, worktop=True):
    """Base cabinets between x0..x1, y0..y1 with door and drawer fronts on the side 'face' ('+x', '-x', '+y', '-y')."""
    box('cabinet', x0, x1, y0, y1, 0.1, h - 0.05, wood, 1.0); box('plinth', x0 + 0.04, x1 - 0.04, y0 + 0.04, y1 - 0.04, 0.0, 0.1, wood, 1.0)
    if worktop:
        ov = 0.03; box('worktop', x0 - ov, x1 + ov, y0 - ov, y1 + ov, h - 0.05, h, top_mat, 1.2, 0.006)
    along_x = face in ('+y', '-y'); a0, a1 = (x0, x1) if along_x else (y0, y1); n = max(1, round((a1 - a0) / unit)); u = (a1 - a0) / n
    sgn = 1 if face[0] == '+' else -1; fixed = (y1 if sgn > 0 else y0) if along_x else (x1 if sgn > 0 else x0)
    for i in range(n):
        c = a0 + (i + 0.5) * u
        for z0, z1, drawer in ((0.14, h - 0.24, False), (h - 0.22, h - 0.07, True)):
            def panel(name, a_lo, a_hi, zl, zh, out, thick, mat):
                if along_x: return box(name, a_lo, a_hi, fixed + (0 if sgn > 0 else -out - thick) + (out if sgn > 0 else 0), fixed + (out + thick if sgn > 0 else -out), zl, zh, mat, 1.0, 0.004)
                return box(name, fixed + (out if sgn > 0 else -out - thick), fixed + (out + thick if sgn > 0 else -out), a_lo, a_hi, zl, zh, mat, 1.0, 0.004)
            panel('door', c - u / 2 + 0.02, c + u / 2 - 0.02, z0, z1, 0.0, 0.022, wood)
            if not drawer: panel('door panel', c - u / 2 + 0.09, c + u / 2 - 0.09, z0 + 0.08, z1 - 0.08, 0.022, 0.012, wood)
            kz = (z0 + z1) / 2 if drawer else z1 - 0.08; ka = c if drawer else c + (u / 2 - 0.08) * (1 if i % 2 else -1)
            kp = (ka, fixed + sgn * 0.05, kz) if along_x else (fixed + sgn * 0.05, ka, kz)
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.016, location=kp, segments=12, ring_count=8); bpy.context.active_object.data.materials.append(knob)

def shelf(x0, x1, y0, y1, z, wood, brackets=True):
    box('shelf', x0, x1, y0, y1, z - 0.035, z, wood, 1.0, 0.004)

def plates_row(x0, x1, y, z, along_x, n, ceramic, r=0.12):
    for i in range(n):
        p = x0 + (i + 0.5) * (x1 - x0) / n
        loc = (p, y, z + r) if along_x else (y, p, z + r)
        o = cyl('plate', r, 0.018, loc, (math.radians(78), 0, 0) if along_x else (math.radians(78), 0, math.pi / 2), ceramic, 28)

def jars_row(x0, x1, y, z, along_x, n, glass_mat, fills, lid):
    for i in range(n):
        p = x0 + (i + 0.5) * (x1 - x0) / n; r = rnd.uniform(0.045, 0.07); h = rnd.uniform(0.14, 0.26)
        loc = (p, y) if along_x else (y, p)
        cyl('jar', r, h, (loc[0], loc[1], z + h / 2), (0, 0, 0), glass_mat, 20)
        cyl('jar fill', r * 0.9, h * rnd.uniform(0.5, 0.85), (loc[0], loc[1], z + h * 0.35), (0, 0, 0), rnd.choice(fills), 20)
        cyl('jar lid', r * 1.03, 0.025, (loc[0], loc[1], z + h + 0.012), (0, 0, 0), lid, 20)

def leaf_cluster(mat, x, y, z, n=14, spread=0.35, hang=0.0, size=(0.22, 0.4)):
    bm = bmesh.new(); uv = bm.loops.layers.uv.new()
    for i in range(n):
        s = rnd.uniform(*size); p = Vector((x + rnd.uniform(-spread, spread), y + rnd.uniform(-spread, spread), z + rnd.uniform(-spread * 0.3, spread * 0.3) - (rnd.uniform(0, hang) if hang else 0)))
        rot = Matrix.Rotation(rnd.uniform(0, 6.28), 3, 'Z') @ Matrix.Rotation(rnd.uniform(-1.2, 1.2), 3, 'X')
        vs = [bm.verts.new(p + rot @ Vector((dx * s, 0, dz * s))) for dx, dz in ((-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5))]
        f = bm.faces.new(vs)
        for l, (u, v) in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))): l[uv].uv = (u, v)
    return obj_from_bm('ivy', bm, mat)

def bouquet(x, y, z, petals, ivy, n=26, r=0.22):
    for i in range(n):
        a = rnd.uniform(0, 6.28); d = rnd.uniform(0, r); h = rnd.uniform(0.12, 0.3)
        bpy.ops.mesh.primitive_ico_sphere_add(radius=rnd.uniform(0.035, 0.06), subdivisions=2, location=(x + math.cos(a) * d, y + math.sin(a) * d, z + h))
        o = bpy.context.active_object; o.scale = (1, 1, 0.7); o.data.materials.append(rnd.choice(petals))
    leaf_cluster(ivy, x, y, z + 0.12, 12, r * 0.9, 0.0, (0.12, 0.2))

def fruit_bowl(x, y, z, kinds):
    model('wooden_bowl_01', (x, y, z), rnd.uniform(0, 6), width=0.42)
    for i, (name, hgt) in enumerate(kinds):
        a = i / len(kinds) * 6.28; d = 0.0 if i == 0 else 0.1
        model(name, (x + math.cos(a) * d, y + math.sin(a) * d, z + 0.05 + (0.04 if i == 0 else 0)), rnd.uniform(0, 6), height=hgt)

def build():
    # ------------------------------------------------------------ materials
    floor = pbr('monastery_stone_floor', 'materials', (0.72, 0.54, 0.4), 0.38, 1.2)
    wall = pbr('plastered_stone_wall', 'materials', (1.12, 0.96, 0.78), 1.0, 1.2)
    stone = pbr('yellow_stone_wall', 'materials', (0.78, 0.63, 0.48), 1.0, 1.4)
    old_stone = pbr('old_stone_wall', 'materials', (0.9, 0.78, 0.64), 1.0, 1.2)
    ceil = pbr('sandstone_blocks_08', 'materials', (0.72, 0.58, 0.44), 1.0, 1.4)
    beam = pbr('dark_wooden_planks', 'materials', (0.46, 0.30, 0.19), 0.9)
    cab = pbr('wood_cabinet_worn_long', 'materials', (0.78, 0.6, 0.45), 0.8)
    island_wood = pbr('wood_cabinet_worn_long', 'materials', (0.62, 0.46, 0.34), 0.75)
    table_wood = pbr('wood_table_worn', 'materials', (0.95, 0.78, 0.6), 0.8)
    chair_wood = flat('chair wood', (0.17, 0.09, 0.05), 0.45)
    marble = tex_mat('marble', K('marble_diff.jpg'), K('marble_rough.jpg'), tint=(0.78, 0.74, 0.7))
    rush = tex_mat('rush', K('rush_diff.jpg'), rough=0.85)
    runner = tex_mat('runner', K('runner_diff.jpg'), rough=0.95, tint=(0.78, 0.64, 0.56))
    frame = flat('window frame', (0.16, 0.10, 0.06), 0.55)
    glass = flat('glass', (0.95, 0.97, 0.98), 0.02, transmission=1.0); lglass = flat('lantern glass', (1.0, 0.86, 0.66), 0.08, transmission=0.85)
    iron = flat('iron', (0.03, 0.028, 0.026), 0.55, 0.35)
    enamel = flat('stove enamel', (0.025, 0.025, 0.028), 0.28, 0.2)
    chrome = flat('chrome', (0.8, 0.78, 0.74), 0.18, 1.0)
    brass = flat('brass', (0.78, 0.55, 0.26), 0.3, 1.0)
    copper = flat('copper', (0.86, 0.45, 0.30), 0.22, 1.0)
    ceramic = flat('ceramic', (0.88, 0.84, 0.76), 0.25)
    ceramic2 = flat('ceramic blue', (0.42, 0.48, 0.55), 0.3)
    ceramic3 = flat('ceramic terracotta', (0.62, 0.32, 0.18), 0.5)
    sink_mat = flat('sink', (0.93, 0.92, 0.88), 0.12)
    jar_glass = flat('jar glass', (0.9, 0.93, 0.9), 0.05, transmission=0.9)
    fills = [flat('fill grain', (0.78, 0.62, 0.38), 0.8), flat('fill beans', (0.35, 0.16, 0.08), 0.6), flat('fill flour', (0.92, 0.9, 0.84), 0.9),
             flat('fill pasta', (0.86, 0.7, 0.36), 0.7), flat('fill herbs', (0.24, 0.3, 0.12), 0.8), flat('fill preserve', (0.55, 0.12, 0.08), 0.3)]
    ivy = mat_alpha('ivy', K('ivy.png'))
    petals = [flat('petal pink', (0.9, 0.45, 0.55), 0.6), flat('petal white', (0.95, 0.92, 0.88), 0.6), flat('petal red', (0.7, 0.1, 0.12), 0.6), flat('petal peach', (0.95, 0.65, 0.45), 0.6)]
    bread = flat('bread', (0.62, 0.36, 0.15), 0.7)
    log = flat('log', (0.22, 0.13, 0.07), 0.9); ember = flat('ember', (1, 0.4, 0.1), 1, emit=(1.0, 0.38, 0.08), strength=30)

    # ------------------------------------------------------------ shell: flagstone floor, barrel vault, end walls
    box('floor', -HW - 0.3, HW + 0.3, -L - 0.3, 0.3, -0.12, 0.0, floor, 2.6)
    prof = profile()
    bm = bmesh.new(); r0 = [bm.verts.new((x, 0.0, z)) for x, z in prof]; r1 = [bm.verts.new((x, -L, z)) for x, z in prof]
    for i in range(len(prof) - 1): bm.faces.new((r0[i + 1], r0[i], r1[i], r1[i + 1]))
    shell = obj_from_bm('vault', bm, ceil, True)
    # walls get plaster, the curved ceiling the sandstone blocks: split by material per face height
    shell.data.materials.append(wall)
    for p in shell.data.polygons: p.material_index = 1 if p.center.z < WALL_H - 0.01 else 0
    box_uv(shell, 1.4); sol = shell.modifiers.new('s', 'SOLIDIFY'); sol.thickness = 0.3; sol.offset = 1
    def end_wall(name, y, thick):
        bm = bmesh.new(); vs = [bm.verts.new((x, y, z)) for x, z in prof]; bm.faces.new(vs); w = obj_from_bm(name, bm, wall)
        s = w.modifiers.new('s', 'SOLIDIFY'); s.thickness = thick; s.offset = 1.0 if y > -1 else -1.0
        bpy.context.view_layer.objects.active = w; bpy.ops.object.modifier_apply(modifier='s'); return w
    back = end_wall('back wall', 0.0, 0.45); front = end_wall('front wall', -L, 0.45)
    # curved timber ribs across the vault, a ridge beam and wall plates
    rib = profile(40, 0.02)[1:-1]
    for y in [-0.3 - k * 1.55 for k in range(int(L / 1.55) + 1)]:
        sweep_profile('rib', [(prof[1][0] + 0.03, 0.0)] + rib + [(prof[-2][0] - 0.03, 0.0)], y, 0.26, 0.3, beam)
    for s in (-1, 1): box('wall plate', s * HW - (0.18 if s > 0 else -0.18) - 0.1, s * HW - (0.18 if s > 0 else -0.18) + 0.1, -L, 0, WALL_H - 0.1, WALL_H + 0.12, beam, 1.2)
    sweep_profile('ridge', [(0, 0.0), (0, -L)], 0, 0, 0, beam) if False else box('ridge', -0.14, 0.14, -L, 0.0, APEX - 0.3, APEX - 0.02, beam, 1.2)
    for s in (-1, 1):
        xp = s * 3.2; box('purlin', xp - 0.11, xp + 0.11, -L, 0.0, vault_z(xp, 0.25) - 0.22, vault_z(xp, 0.25), beam, 1.2)

    # ------------------------------------------------------------ back wall: big arched window over the sink, smaller arched window right
    WX1, WW1, WRH1, WZ = -1.55, 2.3, 2.0, 0.98
    WX2, WW2, WRH2 = 2.85, 1.45, 1.85
    cut(back, arch_cutter_y(WX1, WW1, WRH1, WZ, -0.2, 0.8) + arch_cutter_y(WX2, WW2, WRH2, WZ, -0.2, 0.8))
    for wx, ww, wrh, cols, rows in ((WX1, WW1, WRH1, 5, 4), (WX2, WW2, WRH2, 3, 4)):
        g = group((wx, 0.22, WZ)); arch_window(g, ww, wrh, cols, rows, frame, glass)
        g2 = group((wx, 0.0, WZ)); stone_arch(g2, ww, wrh, 0.12, stone, 0.2)
        box('sill', wx - ww / 2 - 0.1, wx + ww / 2 + 0.1, -0.1, 0.25, WZ - 0.06, WZ, stone, 1.0)
        a = light((wx, 1.4, WZ + 1.1), 900, (0.78, 0.86, 1.0), kind='AREA'); a.data.size = ww; a.rotation_euler = (math.radians(90), 0, 0)
    # arched stone niche between the windows with open shelves
    NX = 0.75
    for z in (1.25, 1.65, 2.05): shelf(NX - 0.55, NX + 0.55, -0.3, 0.0, z, beam)
    g = group((NX, -0.02, 1.0)); stone_arch(g, 1.15, 1.25, 0.08, stone, 0.18)
    jars_row(NX - 0.5, NX + 0.5, -0.15, 1.25, True, 6, jar_glass, fills, brass); jars_row(NX - 0.5, NX + 0.5, -0.15, 1.65, True, 5, jar_glass, fills, brass)
    plates_row(NX - 0.5, NX + 0.5, -0.12, 2.05, True, 5, ceramic)
    # back counters, farmhouse sink under the big window, tap
    cabinet_run(-HW + 0.7, WX1 - 0.48, -0.65, -0.02, '-y', cab, marble, brass)
    cabinet_run(WX1 + 0.48, NX + 0.55, -0.65, -0.02, '-y', cab, marble, brass)
    cabinet_run(NX + 0.55, HW - 0.3, -0.65, -0.02, '-y', cab, marble, brass)
    box('sink', WX1 - 0.48, WX1 + 0.48, -0.7, -0.05, 0.6, CTR - 0.02, sink_mat, 1.0, 0.02)
    box('sink basin', WX1 - 0.42, WX1 + 0.42, -0.62, -0.12, 0.66, CTR, flat('sink inside', (0.8, 0.79, 0.76), 0.2), 1.0)
    box('sink cupboard', WX1 - 0.48, WX1 + 0.48, -0.6, -0.02, 0.1, 0.6, cab, 1.0)
    cyl('tap', 0.018, 0.32, (WX1, -0.08, CTR + 0.16), (0, 0, 0), brass, 12); cyl('spout', 0.015, 0.22, (WX1, -0.18, CTR + 0.31), (math.pi / 2, 0, 0), brass, 12)
    for s in (-1, 1): cyl('tap handle', 0.025, 0.04, (WX1 + s * 0.1, -0.08, CTR + 0.06), (0, 0, 0), brass, 12)
    # things on the back counters and window sills
    model('potted_plant_04', (WX1 - 0.8, -0.12, WZ), 0, height=0.32); model('potted_plant_04', (WX1 + 0.8, -0.12, WZ), 1, height=0.3)
    model('planter_pot_clay', (WX2 - 0.45, -0.12, WZ), 0, height=0.18); leaf_cluster(ivy, WX2 - 0.45, -0.12, WZ + 0.3, 10, 0.15, 0.0, (0.12, 0.22))
    model('ceramic_pot', (-3.6, -0.35, CTR), 0.3, width=0.4); model('jug_01', (-2.95, -0.3, CTR), 0.2, height=0.2)
    model('wooden_cutting_board', (-3.2, -0.08, CTR + 0.22), 0, width=0.45).rotation_euler = (math.radians(80), 0, 0)
    model('wicker_basket_02', (0.25, -0.35, CTR), 0.4, width=0.38)
    for i in range(5): model('yellow_onion', (0.15 + (i % 3) * 0.09, -0.33 + (i // 3) * 0.08, CTR + 0.07), rnd.uniform(0, 6), height=0.07)
    model('metal_jug', (1.6, -0.3, CTR), 0, height=0.26); model('wine_bottles_01', (2.0, -0.25, CTR), 0, width=0.5)
    model('potted_plant_02', (4.25, -0.35, CTR), 0.5, height=0.6)
    # shelves on the back wall either side of the windows with crockery
    for x0, x1 in ((-HW + 0.75, -3.05), (3.75, HW - 0.35)):
        for z in (1.45, 1.9, 2.35): shelf(x0, x1, -0.32, -0.02, z, beam)
        plates_row(x0 + 0.05, x1 - 0.05, -0.14, 1.45, True, 6, rnd.choice([ceramic, ceramic2]))
        jars_row(x0 + 0.05, x1 - 0.05, -0.16, 1.9, True, 5, jar_glass, fills, brass)
        for i in range(4): xx = x0 + (i + 0.5) * (x1 - x0) / 4; model('ceramic_vase_03' if i % 2 else 'ceramic_vase_02', (xx, -0.17, 2.35), 0, height=0.28 if i % 2 else 0.2)
        light(((x0 + x1) / 2, -0.4, 2.2), 30, radius=0.2)

    # ------------------------------------------------------------ left wall: range cooker, cabinets, stone hearth, shelves, trailing plants
    LX = -HW
    # range cooker
    RY0, RY1 = -10.8, -9.5
    box('range body', LX + 0.02, LX + 0.72, RY0, RY1, 0.08, CTR, enamel, 1.0, 0.015)
    box('range top', LX + 0.0, LX + 0.75, RY0 - 0.02, RY1 + 0.02, CTR, CTR + 0.03, enamel, 1.0, 0.01)
    for i, (y0, y1) in enumerate(((RY0 + 0.05, (RY0 + RY1) / 2 - 0.02), ((RY0 + RY1) / 2 + 0.02, RY1 - 0.05))):
        box('oven door', LX + 0.72, LX + 0.75, y0, y1, 0.16, 0.66, enamel, 1.0, 0.01)
        box('oven window', LX + 0.75, LX + 0.755, y0 + 0.08, y1 - 0.08, 0.3, 0.55, flat('oven glass', (0.02, 0.02, 0.02), 0.05), 1.0)
        cyl('oven handle', 0.012, y1 - y0 - 0.12, (LX + 0.8, (y0 + y1) / 2, 0.62), (math.pi / 2, 0, 0), chrome, 12)
        for k in range(2): cyl('knob', 0.025, 0.03, (LX + 0.76, y0 + 0.15 + k * 0.25, 0.79), (0, math.pi / 2, 0), chrome, 16)
        box('drawer', LX + 0.72, LX + 0.75, y0, y1, 0.69, 0.74, enamel, 1.0)
    box('range trim', LX + 0.74, LX + 0.76, RY0, RY1, 0.66, 0.68, chrome, 1.0)
    for dy in (-0.33, 0.33):
        for dx in (0.2, 0.5): torus('burner', 0.09, 0.012, (LX + dx, (RY0 + RY1) / 2 + dy, CTR + 0.04), (0, 0, 0), iron)
    model('pot_enamel_01', (LX + 0.5, (RY0 + RY1) / 2 - 0.33, CTR + 0.03), 0.4, height=0.2)
    model('brass_pot_01', (LX + 0.22, (RY0 + RY1) / 2 + 0.33, CTR + 0.03), 0.9, height=0.2)
    # stone surround and hood over the range with a shelf of copper pans
    box('range splash', LX, LX + 0.06, RY0 - 0.25, RY1 + 0.25, CTR, 2.2, old_stone, 0.9)
    box('hood', LX, LX + 0.6, RY0 - 0.15, RY1 + 0.15, 1.75, 2.15, stone, 0.9); box('hood beam', LX + 0.55, LX + 0.68, RY0 - 0.25, RY1 + 0.25, 1.68, 1.82, beam, 1.0)
    for i in range(4): pan(LX + 0.62, RY0 + 0.15 + i * 0.33, 1.65, 0.1 + 0.02 * (i % 2), math.pi / 2, copper, iron)
    # cabinets either side of the range and the hearth
    cabinet_run(LX + 0.02, LX + 0.66, -12.3, RY0 - 0.02, '+x', cab, marble, brass)
    cabinet_run(LX + 0.02, LX + 0.66, RY1 + 0.02, -7.25, '+x', cab, marble, brass)
    cabinet_run(LX + 0.02, LX + 0.66, -4.65, -0.67, '+x', cab, marble, brass)
    # the stone hearth with its arched oven/fire opening
    HY0, HY1 = -7.2, -4.7; HC = (HY0 + HY1) / 2
    hearth = box('hearth', LX, LX + 0.75, HY0, HY1, 0.0, WALL_H + 0.1, stone, 0.9)
    cut(hearth, arch_cutter_x(HC, 1.15, 0.65, 0.35, LX + 0.15, LX + 1.0))
    box('hearth slab', LX + 0.1, LX + 0.95, HY0 - 0.05, HY1 + 0.05, 0.0, 0.35, old_stone, 0.9, 0.01)
    box('mantel', LX + 0.6, LX + 0.9, HY0 - 0.15, HY1 + 0.15, 1.62, 1.75, beam, 1.0, 0.01)
    for i in range(3): cyl('log', 0.07, 0.75, (LX + 0.45 + (i % 2) * 0.05, HC + (i - 1) * 0.05, 0.43 + (i // 2) * 0.12), (math.pi / 2, 0, (i - 1) * 0.3), log, 12)
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.28); o = obj_from_bm('fire', bm, ember, True); o.location = (LX + 0.45, HC, 0.52); o.scale = (0.6, 1.3, 0.55)
    light((LX + 0.6, HC, 0.6), 220, (1.0, 0.45, 0.15), radius=0.3); LIGHTS.append(dict(x=LX + 0.9, y=0.7, z=-HC, color='#ff7a2e', power=9, range=6))
    model('brass_pot_02', (LX + 0.8, HC + 0.95, 0.35), 0.6, width=0.34)
    for k, dy in enumerate((-0.9, -0.45, 0.45, 0.9)): candle((LX + 0.72, HC + dy, 1.75), 0.12 + 0.06 * (k % 2), 8)
    for dy in (-0.25, 0.25): model('carved_wooden_plate', (LX + 0.68, HC + dy, 1.75 + 0.14), math.pi / 2, width=0.26).rotation_euler = (math.radians(80), 0, math.pi / 2)
    # crockery shelves above the counters along the left wall
    for y0, y1 in ((-12.2, RY0 - 0.3), (RY1 + 0.3, -7.35), (-4.55, -0.8)):
        for z in (1.5, 1.95): shelf(LX + 0.02, LX + 0.34, y0, y1, z, beam)
        plates_row(y0 + 0.05, y1 - 0.05, LX + 0.17, 1.5, False, max(2, int((y1 - y0) / 0.28)), rnd.choice([ceramic, ceramic2, ceramic3]))
        jars_row(y0 + 0.05, y1 - 0.05, LX + 0.17, 1.95, False, max(2, int((y1 - y0) / 0.3)), jar_glass, fills, brass)
        light((LX + 0.5, (y0 + y1) / 2, 2.3), 35, radius=0.2)
    # a high ledge with pots and trailing greenery all along the left wall (the image's top-left)
    box('ledge', LX + 0.0, LX + 0.4, -L + 0.4, -0.3, WALL_H - 0.12, WALL_H - 0.05, beam, 1.0)
    for i in range(14):
        y = -L + 0.9 + i * (L - 1.6) / 13
        leaf_cluster(ivy, LX + 0.25, y, WALL_H + 0.05, 14, 0.32, 0.0); leaf_cluster(ivy, LX + 0.3, y + 0.2, WALL_H - 0.3, 9, 0.18, 0.9)
        if i % 3 == 0: model('planter_pot_clay', (LX + 0.22, y, WALL_H - 0.05), rnd.uniform(0, 6), height=0.2)
    # a counter by the front with bread and a bowl of produce
    model('wooden_cutting_board', (LX + 0.35, -11.6, CTR), math.pi / 2, width=0.45)
    for i in range(2):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.1, location=(LX + 0.35, -11.75 + i * 0.25, CTR + 0.08)); o = bpy.context.active_object; o.scale = (0.8, 1.4, 0.65); o.data.materials.append(bread)
        for p in o.data.polygons: p.use_smooth = True
    model('wicker_basket_01', (LX + 0.35, -8.0, CTR), math.pi / 2, width=0.4); [model('food_apple_01', (LX + 0.3 + 0.08 * (i % 2), -8.08 + 0.08 * (i // 2), CTR + 0.06), rnd.uniform(0, 6), height=0.08) for i in range(4)]
    model('ceramic_pot', (LX + 0.35, -3.6, CTR), 0.0, width=0.36); model('potted_plant_02', (LX + 0.35, -1.3, CTR), 0.2, height=0.55)

    # ------------------------------------------------------------ the long island with a marble top, stools, the pot rack and lanterns over it
    IX0, IX1, IY0, IY1 = -1.3, -0.1, -9.6, -3.9
    box('island', IX0, IX1, IY0, IY1, 0.12, CTR - 0.06, island_wood, 1.0); box('island plinth', IX0 + 0.05, IX1 - 0.05, IY0 + 0.05, IY1 - 0.05, 0.0, 0.12, island_wood, 1.0)
    box('island top', IX0 - 0.06, IX1 + 0.32, IY0 - 0.08, IY1 + 0.08, CTR - 0.06, CTR + 0.02, marble, 1.6, 0.012)
    box('island moulding', IX0 - 0.02, IX1 + 0.02, IY0 - 0.02, IY1 + 0.02, CTR - 0.13, CTR - 0.06, island_wood, 1.0, 0.01)
    # raised panels on all four sides
    n = 7; u = (IY1 - IY0) / n
    for i in range(n):
        c = IY0 + (i + 0.5) * u
        for xf, sgn in ((IX0, -1), (IX1, 1)):
            box('island frame', xf + (0 if sgn > 0 else -0.025), xf + (0.025 if sgn > 0 else 0), c - u / 2 + 0.03, c + u / 2 - 0.03, 0.18, CTR - 0.18, island_wood, 1.0, 0.004)
            box('island panel', xf + (0.025 if sgn > 0 else -0.04), xf + (0.04 if sgn > 0 else -0.025), c - u / 2 + 0.1, c + u / 2 - 0.1, 0.26, CTR - 0.26, island_wood, 1.0, 0.006)
    for yf, sgn in ((IY0, -1), (IY1, 1)):
        for k in range(2):
            c = IX0 + (k + 0.5) * (IX1 - IX0) / 2
            box('island frame', c - 0.27, c + 0.27, yf + (0 if sgn > 0 else -0.025), yf + (0.025 if sgn > 0 else 0), 0.18, CTR - 0.18, island_wood, 1.0, 0.004)
            box('island panel', c - 0.19, c + 0.19, yf + (0.025 if sgn > 0 else -0.04), yf + (0.04 if sgn > 0 else -0.025), 0.26, CTR - 0.26, island_wood, 1.0, 0.006)
    for yy in (IY0, IY1):
        for xx in (IX0, IX1): box('island post', xx - 0.05, xx + 0.05, yy - 0.05, yy + 0.05, 0.0, CTR - 0.06, island_wood, 1.0, 0.01)
    # on the island: flowers in the middle, bowls of fruit, bread on a board, a plate of pastries
    IC = (IX0 + IX1) / 2 + 0.05; T = CTR + 0.02
    model('ceramic_vase_02', (IC, -6.6, T), 0, height=0.24); bouquet(IC, -6.6, T + 0.22, petals, ivy, 30, 0.24)
    fruit_bowl(IC - 0.05, -5.3, T, [('food_pomegranate_01', 0.11), ('food_apple_01', 0.09), ('food_apple_01', 0.09), ('food_pomegranate_01', 0.1), ('lemon', 0.09), ('food_apple_01', 0.09)])
    fruit_bowl(IC, -8.1, T, [('lemon', 0.09), ('food_pears_asian_01', 0.1), ('lemon', 0.09), ('food_apple_01', 0.09), ('food_pears_asian_01', 0.1)])
    model('carved_wooden_plate', (IC + 0.05, -7.25, T), 0.3, width=0.34); [model('croissant', (IC + 0.02 + 0.07 * (i % 2), -7.32 + 0.09 * i, T + 0.03), rnd.uniform(0, 6), width=0.14) for i in range(3)]
    model('wooden_cutting_board', (IC, -4.55, T), 0.1, width=0.45)
    for i in range(2):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.11, location=(IC - 0.05 + i * 0.12, -4.55 + i * 0.05, T + 0.1)); o = bpy.context.active_object; o.scale = (0.75, 1.35, 0.62); o.data.materials.append(bread)
        for p in o.data.polygons: p.use_smooth = True
    model('brass_candleholders', (IC, -9.25, T), math.pi / 2, width=0.4)
    model('bananas', (IC + 0.05, -5.95, T), 0.5, width=0.28)
    # ladder-back rush-seat bar stools along the island
    for i in range(6): ladder_chair(IX1 + 0.62, IY0 + 0.45 + i * (IY1 - IY0 - 0.9) / 5, -math.pi / 2 + rnd.uniform(-0.06, 0.06), chair_wood, rush, 0.74, 1.12, 0.4, 0.38)
    # iron pot rack hung from the vault, with copper pans, pots and lanterns
    PZ = 2.62; px0, px1, py0, py1 = IX0 - 0.1, IX1 + 0.1, -8.6, -4.9
    for x in (px0, px1): box('rack rail', x - 0.02, x + 0.02, py0, py1, PZ - 0.02, PZ + 0.02, iron, 1.0)
    for y in (py0, (py0 + py1) / 2, py1): box('rack rail', px0, px1, y - 0.02, y + 0.02, PZ - 0.02, PZ + 0.02, iron, 1.0)
    for y in (py0 + 0.6, py1 - 0.6): box('rack bar', px0, px1, y - 0.015, y + 0.015, PZ + 0.35, PZ + 0.38, iron, 1.0)
    for x in (px0, px1):
        for y in (py0, py1): cyl('rack chain', 0.01, vault_z(x) - PZ, (x, y, (vault_z(x) + PZ) / 2), (0, 0, 0), iron, 6)
    k = 0
    for side_x in (px0, px1):
        for j in range(9):
            y = py0 + 0.2 + j * (py1 - py0 - 0.4) / 8
            if j % 2 == 0: pan(side_x, y, PZ - 0.02, rnd.uniform(0.1, 0.15), math.pi / 2 + rnd.uniform(-0.25, 0.25), copper, iron)
            else: pot(side_x, y, PZ - 0.02, rnd.uniform(0.09, 0.12), rnd.uniform(0.1, 0.16), rnd.uniform(0, 3), copper, iron)
    for j, (y, z) in enumerate(((-8.3, 2.25), (-7.4, 2.05), (-6.5, 2.3), (-5.6, 2.1), (-4.9, 2.3))):
        lantern(IC + (0.18 if j % 2 else -0.18), y, z, 1.0, PZ, iron, lglass, 55)
    # more lanterns hanging from the vault around the room, like the image
    for x, y, z in ((-3.2, -2.2, 2.45), (-3.0, -10.2, 2.45), (2.3, -2.0, 2.6), (3.3, -7.8, 2.35), (3.4, -5.2, 2.4), (3.2, -10.3, 2.4), (0.8, -11.0, 2.7), (-0.9, -2.0, 2.75)):
        lantern(x, y, z, 1.15, vault_z(x, 0.25), iron, lglass, 60)
    # wall lanterns
    for x, y, rot in ((LX + 0.25, -3.0, 0), (LX + 0.25, -8.6, 0), (HW - 0.25, -4.4, 0), (HW - 0.25, -9.6, 0)):
        box('sconce arm', x - 0.2 if x > 0 else x, x if x > 0 else x + 0.2, y - 0.015, y + 0.015, 2.08, 2.11, iron, 1.0)
        lantern(x + (-0.15 if x > 0 else 0.15), y, 1.75, 1.0, 2.1, iron, lglass, 45)

    # ------------------------------------------------------------ the Persian runner and the long dining table on the right
    rx0, rx1, ry0, ry1 = 0.85, 2.3, -11.3, -3.4
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5); uvl = bm.loops.layers.uv.new()
    for f in bm.faces:
        for l in f.loops: l[uvl].uv = (l.vert.co.x + 0.5, l.vert.co.y + 0.5)
    o = obj_from_bm('runner', bm, runner); o.scale = (rx1 - rx0, ry1 - ry0, 1); o.location = ((rx0 + rx1) / 2, (ry0 + ry1) / 2, 0.008)
    TX, TW, TY0, TY1, TH = 3.65, 1.05, -10.9, -5.2, 0.78
    box('table top', TX - TW / 2, TX + TW / 2, TY0, TY1, TH - 0.07, TH, table_wood, 1.3, 0.012)
    box('table apron', TX - TW / 2 + 0.08, TX + TW / 2 - 0.08, TY0 + 0.1, TY1 - 0.1, TH - 0.17, TH - 0.07, table_wood, 1.0)
    for yy in (TY0 + 0.12, (TY0 + TY1) / 2, TY1 - 0.12):
        for s in (-1, 1): box('table leg', TX + s * (TW / 2 - 0.14) - 0.06, TX + s * (TW / 2 - 0.14) + 0.06, yy - 0.06, yy + 0.06, 0.0, TH - 0.07, table_wood, 1.0, 0.01)
    box('table stretcher', TX - 0.04, TX + 0.04, TY0 + 0.12, TY1 - 0.12, 0.18, 0.26, table_wood, 1.0)
    for i in range(5):
        y = TY0 + 0.6 + i * (TY1 - TY0 - 1.2) / 4
        ladder_chair(TX - TW / 2 - 0.25, y, math.pi / 2 + rnd.uniform(-0.1, 0.1), chair_wood, rush, 0.46, 1.02, 0.44, 0.42)
        ladder_chair(TX + TW / 2 + 0.25, y, -math.pi / 2 + rnd.uniform(-0.1, 0.1), chair_wood, rush, 0.46, 1.02, 0.44, 0.42)
    for i, y in enumerate((-10.3, -8.9, -7.2, -5.8)):
        model('brass_candleholders', (TX, y, TH), 0, width=0.32) if i % 2 else None
        for dx, h in ((0.0, 0.26), (0.09, 0.18)):
            cyl('pillar candle', 0.04, h, (TX + dx - 0.04, y, TH + h / 2), (0, 0, 0), flat('wax', (0.92, 0.88, 0.78), 0.45), 20)
            candle((TX + dx - 0.04, y, TH + h - 0.005), 0.01, 14)
    for y in (-9.6, -8.0, -6.5): model('carved_wooden_plate', (TX - 0.3, y, TH), 0, width=0.24); model('carved_wooden_plate', (TX + 0.3, y, TH), 0, width=0.24)
    model('wooden_bowl_02', (TX, -8.0, TH), 0, width=0.16); model('brass_goblets', (TX + 0.15, -6.5, TH), 0, width=0.3)
    model('ceramic_vase_02', (TX, -6.0, TH), 0, height=0.2); bouquet(TX, -6.0, TH + 0.18, petals, ivy, 16, 0.15)

    # ------------------------------------------------------------ right wall: window at the back, dresser shelves of jars, plants
    RX = HW
    cut(shell, arch_cutter_x(-2.0, 1.25, 1.2, 1.0, RX - 0.6, RX + 0.6))
    g = group((RX - 0.05, -2.0, 1.0), math.pi / 2); arch_window(g, 1.25, 1.2, 3, 2, frame, glass)
    a = light((RX + 1.2, -2.0, 2.0), 500, (0.78, 0.86, 1.0), kind='AREA'); a.data.size = 1.2; a.rotation_euler = (0, math.radians(-90), 0)
    box('right sill', RX - 0.3, RX, -2.75, -1.25, 0.94, 1.0, stone, 1.0)
    model('potted_plant_04', (RX - 0.15, -2.4, 1.0), 0, height=0.3); model('potted_plant_04', (RX - 0.15, -1.6, 1.0), 2, height=0.28)
    cabinet_run(RX - 0.62, RX - 0.02, -3.85, -2.85, '-x', cab, marble, brass)
    for y0, y1 in ((-4.6, -2.85), (-10.6, -5.4)):
        for z in (1.45, 1.9, 2.35): shelf(RX - 0.34, RX - 0.02, y0, y1, z, beam)
        jars_row(y0 + 0.05, y1 - 0.05, RX - 0.17, 1.45, False, int((y1 - y0) / 0.2), jar_glass, fills, brass)
        jars_row(y0 + 0.05, y1 - 0.05, RX - 0.17, 1.9, False, int((y1 - y0) / 0.24), jar_glass, fills, brass)
        plates_row(y0 + 0.05, y1 - 0.05, RX - 0.17, 2.35, False, int((y1 - y0) / 0.3), ceramic)
        for k in range(int((y1 - y0) / 1.2)): leaf_cluster(ivy, RX - 0.2, y0 + 0.5 + k * 1.2, 2.55, 10, 0.25, 0.7)
        light((RX - 0.5, (y0 + y1) / 2, 2.25), 40, radius=0.2)
    model('potted_plant_01', (RX - 0.55, -11.9, 0), 0.4, height=1.55); model('potted_plant_01', (RX - 0.5, -4.9, 0), 1.3, height=1.35)
    model('potted_plant_02', (RX - 0.45, -1.0, 0), 0.8, height=0.9); model('potted_plant_02', (2.0, -12.4, 0), 2.0, height=0.85)
    model('wooden_barrels_01', (-3.6, -12.4, 0), 0.3, height=0.8) if False else None
    # the doorway in the front wall leading back to the rest of the house
    cut(front, arch_cutter_y(-2.6, 1.5, 1.6, 0.0, -L - 1, -L + 1)); box_uv(front, 2.2); box_uv(back, 2.2)
    # front wall: a long dresser with shelves of plates and jars, a clock and lanterns
    FY = -L
    cabinet_run(0.3, HW - 0.4, FY + 0.02, FY + 0.6, '+y', cab, marble, brass)
    for z in (1.5, 1.95, 2.4): shelf(0.3, HW - 0.4, FY + 0.02, FY + 0.32, z, beam)
    plates_row(0.4, HW - 0.5, FY + 0.15, 1.5, True, 12, ceramic); jars_row(0.4, HW - 0.5, FY + 0.17, 1.95, True, 11, jar_glass, fills, brass)
    plates_row(0.4, HW - 0.5, FY + 0.15, 2.4, True, 10, ceramic2)
    for i in range(4): leaf_cluster(ivy, 0.9 + i * 1.1, FY + 0.2, 2.62, 10, 0.25, 0.8)
    model('ceramic_pot', (1.2, FY + 0.32, CTR), 0.2, width=0.4); model('wicker_basket_02', (2.4, FY + 0.32, CTR), 0.1, width=0.36); model('jug_01', (3.3, FY + 0.3, CTR), 0.4, height=0.22)
    bouquet(4.1, FY + 0.3, CTR + 0.2, petals, ivy, 14, 0.14); model('ceramic_vase_02', (4.1, FY + 0.3, CTR), 0, height=0.22)
    cabinet_run(-HW + 0.7, -3.6, FY + 0.02, FY + 0.6, '+y', cab, marble, brass)
    for z in (1.5, 1.95): shelf(-HW + 0.7, -3.6, FY + 0.02, FY + 0.32, z, beam)
    jars_row(-HW + 0.8, -3.7, FY + 0.17, 1.5, True, 4, jar_glass, fills, brass); plates_row(-HW + 0.8, -3.7, FY + 0.15, 1.95, True, 3, ceramic3)
    model('vintage_grandfather_clock_01', (-0.6, FY + 0.3, 0), 0, height=2.1)
    for x in (-3.9, 0.0, 2.6): box('sconce arm', x - 0.015, x + 0.015, FY, FY + 0.22, 2.08, 2.11, iron, 1.0); lantern(x, FY + 0.22, 1.75, 1.0, 2.1, iron, lglass, 45)
    model('hanging_picture_frame_02', (-1.4, FY + 0.06, 2.3), 0, width=0.7)
    g = group((-2.6, -L, 0.0)); stone_arch(g, 1.5, 1.6, 0.6, stone, 0.2)
    box('passage floor', -3.5, -1.7, -L - 2.5, -L, -0.12, 0.0, floor, 2.6); box('passage end', -3.6, -1.6, -L - 2.6, -L - 2.4, 0.0, 2.6, wall, 2.2)
    for x0, x1 in ((-3.75, -3.5), (-1.7, -1.45)): box('passage wall', x0, x1, -L - 2.6, -L - 0.2, 0.0, 2.6, wall, 2.2)
    box('passage ceiling', -3.75, -1.45, -L - 2.6, -L - 0.2, 2.45, 2.65, beam, 1.2)
    light((-2.6, -L - 1.4, 2.0), 60)
    # outside: the alpine valley behind the windows
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1); bmesh.ops.scale(bm, vec=(90, 39, 1), verts=bm.verts)
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 4, 'X')); bmesh.ops.translate(bm, vec=(0, 32, 2.0), verts=bm.verts)
    view = obj_from_bm('valley view', bm, image_mat('view', K('view.jpg'), 1.15)); uvl = view.data.uv_layers.new()
    for i, l in enumerate(uvl.data): co = view.data.vertices[view.data.loops[i].vertex_index].co; l.uv = (co.x / 90 + 0.5, (co.z - 2.0) / 39 + 0.5)
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1); bmesh.ops.scale(bm, vec=(39, 90, 1), verts=bm.verts)
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(-90), 4, 'Y')); bmesh.ops.translate(bm, vec=(28, -6, 2.0), verts=bm.verts)
    v2 = obj_from_bm('valley view', bm, image_mat('view', K('view.jpg'), 1.15)); uvl = v2.data.uv_layers.new()
    for i, l in enumerate(uvl.data): co = v2.data.vertices[v2.data.loops[i].vertex_index].co; l.uv = (-co.y / 90 + 0.5, (co.z - 2.0) / 39 + 0.5)
    w = bpy.data.worlds.new('w'); bpy.context.scene.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0.55, 0.65, 0.8, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.35
    # a soft warm fill so the far corners are not black (stands in for all the bounced candle light)
    for y in (-3.0, -7.0, -11.0):
        f = light((0.5, y, APEX - 0.9), 110, (1.0, 0.72, 0.45), kind='AREA'); f.data.size = 3.0; f.rotation_euler = (0, 0, 0)

def walk_rects():
    """Walkable rectangles in three.js coordinates (x, z = -y): aisles around the island, table and counters."""
    R = [(-4.15, 4.55, -12.2, -11.15),          # front strip in front of the island and the table
         (-4.15, -1.55, -12.2, -0.85),          # left aisle between the counters/hearth and the island
         (0.95, 2.3, -12.2, -0.85),             # aisle between the stools and the dining chairs
         (-4.15, 4.4, -3.6, -0.85),             # back strip by the sink and windows
         (-3.2, -2.0, -L - 2.2, -11.9)]         # through the doorway into the passage
    return [[x0, x1, -y1, -y0] for x0, x1, y0, y1 in R]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--render', default=''); ap.add_argument('--samples', type=int, default=96); ap.add_argument('--res', default='1280x720')
    ap.add_argument('--glb', default=''); ap.add_argument('--blend', default=''); ap.add_argument('--cam', default=f'0.75,{-L + 0.55},1.72,86,13,17')
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
    bpy.ops.wm.read_factory_settings(use_empty=True); build()
    for o in bpy.context.scene.objects:
        if o.type == 'LIGHT' and hasattr(o, 'visible_camera'): o.visible_camera = False
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = a.samples; sc.cycles.use_denoising = True; sc.cycles.max_bounces = 8
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'; sc.view_settings.exposure = 0.95
    w, h = map(int, a.res.split('x')); sc.render.resolution_x, sc.render.resolution_y = w, h
    x, y, z, tilt, head, lens = map(float, a.cam.split(',')); cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera')); sc.collection.objects.link(cam); sc.camera = cam
    cam.location = (x, y, z); cam.rotation_euler = (math.radians(tilt), 0, math.radians(head)); cam.data.lens = lens
    cfgp = K('room.json'); cfg = json.load(open(cfgp)) if os.path.exists(cfgp) else {}
    cfg.update(name='Kitchen', glb='assets/rooms/kitchen/kitchen.glb', spawn=dict(x=0.75, z=L - 1.0, yaw=0.22), walk=walk_rects(), lights=LIGHTS, probe=[0.4, 1.4, 7.0])
    tints = {}
    for m in bpy.data.materials:
        if m.use_nodes:
            for n in m.node_tree.nodes:
                if n.type == 'MIX_RGB' and n.blend_type == 'MULTIPLY': tints[m.name] = [round(v, 3) for v in n.inputs[2].default_value[:3]]
    cfg['tints'] = tints; cfg['floor'] = 'monastery_stone_floor'
    cfg.setdefault('exposure', 1.0); cfg.setdefault('version', 1); cfg.setdefault('wallBoost', 1.25); cfg.setdefault('maxFlameLights', 30)
    json.dump(cfg, open(cfgp, 'w'), indent=1)
    if a.blend: bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.blend))
    if a.render: sc.render.filepath = os.path.abspath(a.render); bpy.ops.render.render(write_still=True)
    if a.glb:
        # the walkable page does not need 1k textures on small props: shrink those to 512 px (room surfaces keep theirs)
        keep = ('stone', 'plaster', 'sandstone', 'wood_cabinet', 'wood_table', 'dark_wooden', 'marble', 'runner', 'view', 'rush', 'ivy')
        for im in bpy.data.images:
            if im.size[0] > 512 and not any(k in im.name for k in keep): im.scale(512, 512)
        bpy.ops.object.select_all(action='DESELECT')
        for o in list(sc.objects):
            if o.type == 'EMPTY' and o.instance_type == 'COLLECTION': o.select_set(True)
        if any(o.select_get() for o in sc.objects): bpy.ops.object.duplicates_make_real()
        bpy.ops.export_scene.gltf(filepath=os.path.abspath(a.glb), export_format='GLB', export_lights=False, export_cameras=False, export_apply=True, export_image_format='JPEG', export_jpeg_quality=82)

if __name__ == '__main__':
    main()
