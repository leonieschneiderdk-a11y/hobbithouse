"""Main entrance of the hobbit house, rebuilt as a real 3D room from the 'Entrance (inside)' image.

    python blender/rooms/entrance.py --render docs/rooms/entrance.png --samples 128 --res 1600x900 --glb assets/rooms/entrance/entrance.glb

Blender axes: the garden doors are in the front wall at y = 0, the hall runs back to y = -L, x is left/right, z is up.
"""
import argparse, math, os, sys, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bpy, bmesh
from mathutils import Vector, Matrix
from hero_room import A, pbr, flat, image_mat, obj_from_bm, box_uv, box, cyl, torus, cut, model, light, candle

W, L, H = 13.0, 14.0, 5.0           # width, length, wall height
HX = W / 2; CY = -L / 2             # half width, centre of the hall
OCU_R, OCU_TOP = 2.3, 7.4           # skylight opening radius and height
ALC = 3.0                           # depth of the side alcoves behind the arcades
ARCHES = (-3.5, -7.0, -10.5)        # arcade arch centres along each side wall
rnd = random.Random(11)

def mat_alpha(name, img_path, tint=(1, 1, 1), rough=0.6):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; b = nt.nodes['Principled BSDF']
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(img_path); mix = nt.nodes.new('ShaderNodeMixRGB'); mix.blend_type = 'MULTIPLY'; mix.inputs[0].default_value = 1
    mix.inputs[2].default_value = (*tint, 1); nt.links.new(t.outputs['Color'], mix.inputs[1]); nt.links.new(mix.outputs[0], b.inputs['Base Color']); nt.links.new(t.outputs['Alpha'], b.inputs['Alpha'])
    b.inputs['Roughness'].default_value = rough
    for attr, val in (('blend_method', 'CLIP'), ('surface_render_method', 'DITHERED')):
        if hasattr(m, attr):
            try: setattr(m, attr, val)
            except Exception: pass
    return m

def arch_cutter(cx, cy, along_x, w, rect_h, z0=0.0, depth=2.0):
    """Box plus half-cylinder that punches an arched opening through a wall."""
    sx, sy = (w, depth) if along_x else (depth, w)
    b = box('c', cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, z0 - 0.05, z0 + rect_h, flat('cut', (1, 1, 1)))
    c = cyl('c', w / 2, depth, (cx, cy, z0 + rect_h), (math.pi / 2, 0, 0) if along_x else (0, math.pi / 2, 0), flat('cut', (1, 1, 1)), 40)
    return [b, c]

def arch_trim(cx, cy, along_x, w, rect_h, z0, mat, t=0.16, d=0.5):
    """Stone or timber surround for an arched opening: two jambs and a half ring."""
    rot = (math.pi / 2, 0, 0) if along_x else (0, math.pi / 2, 0)
    bpy.ops.mesh.primitive_torus_add(major_radius=w / 2 + t / 2, minor_radius=t / 2, major_segments=48, minor_segments=8, location=(cx, cy, z0 + rect_h), rotation=rot)
    o = bpy.context.active_object; o.scale = (1, 1, d / t) if along_x else (d / t, 1, 1); o.data.materials.append(mat)
    for p in o.data.polygons: p.use_smooth = True
    for s in (-1, 1):
        if along_x: box('jamb', cx + s * (w / 2 + t / 2) - t / 2, cx + s * (w / 2 + t / 2) + t / 2, cy - d / 2, cy + d / 2, z0, z0 + rect_h, mat, 1.2)
        else: box('jamb', cx - d / 2, cx + d / 2, cy + s * (w / 2 + t / 2) - t / 2, cy + s * (w / 2 + t / 2) + t / 2, z0, z0 + rect_h, mat, 1.2)

def glazed_leaf(parent, w, h, frame, glass, panes=(2, 5)):
    """A glazed door or window leaf in its own local space (hinge at x = 0, opening toward +x)."""
    t = 0.07
    for x0, x1, z0, z1 in ((0, t, 0, h), (w - t, w, 0, h), (0, w, 0, t * 1.4), (0, w, h - t, h)):
        o = box('leaf', x0, x1, -0.03, 0.03, z0, z1, frame, 1.0); o.parent = parent
    nx, nz = panes
    for i in range(1, nx): o = box('bar', i * w / nx - 0.015, i * w / nx + 0.015, -0.025, 0.025, t, h - t, frame, 1.0); o.parent = parent
    for k in range(1, nz): o = box('bar', t, w - t, -0.025, 0.025, k * h / nz - 0.015, k * h / nz + 0.015, frame, 1.0); o.parent = parent
    g = box('glass', t, w - t, -0.006, 0.006, t, h - t, glass, 1.0); g.parent = parent

def ivy_cluster(mat, x, y, z, n=14, spread=0.35, hang=0.0):
    """Leaf cards scattered around a point, optionally trailing downward."""
    bm = bmesh.new(); uv = bm.loops.layers.uv.new()
    for i in range(n):
        s = rnd.uniform(0.25, 0.45); p = Vector((x + rnd.uniform(-spread, spread), y + rnd.uniform(-spread, spread), z + rnd.uniform(-spread * 0.4, spread * 0.4) - (rnd.uniform(0, hang) if hang else 0)))
        rot = Matrix.Rotation(rnd.uniform(0, 6.28), 3, 'Z') @ Matrix.Rotation(rnd.uniform(-1.2, 1.2), 3, 'X')
        vs = [bm.verts.new(p + rot @ Vector((dx * s, 0, dz * s))) for dx, dz in ((-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5))]
        f = bm.faces.new(vs)
        for l, (u, v) in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))): l[uv].uv = (u, v)
    o = obj_from_bm('ivy', bm, mat); return o

def half_disc(name, r, cx, cy, cz, mat, seg=32):
    bm = bmesh.new(); vs = [bm.verts.new((cx + math.cos(i / seg * math.pi) * r, cy, cz + math.sin(i / seg * math.pi) * r)) for i in range(seg + 1)]
    bm.faces.new(vs); return obj_from_bm(name, bm, mat)

def build():
    wall = pbr('plastered_stone_wall', 'materials', (1.0, 0.93, 0.82), 1.0, 1.2)
    stone = pbr('rustic_stone_wall', 'materials', (0.95, 0.88, 0.78), 1.0, 1.2)
    timber = pbr('dark_wooden_planks', 'materials', (0.5, 0.34, 0.22), 0.9)
    ceil_boards = pbr('dark_wooden_planks', 'materials', (0.42, 0.3, 0.2), 0.9)
    floor = pbr('stonetile', os.path.join('rooms', 'entrance'), (1, 1, 1), 1.0, 0.5)
    frame = pbr('dark_wooden_planks', 'materials', (0.36, 0.23, 0.15), 0.8)
    glass = flat('glass', (0.95, 0.97, 0.98), 0.02, transmission=1.0)
    iron = flat('iron', (0.06, 0.055, 0.05), 0.45, 0.85)
    ivy = mat_alpha('ivy', A('assets', 'rooms', 'entrance', 'ivy.png'))
    rug = mat_alpha('rug', A('assets', 'rooms', 'entrance', 'rug_diff.png'), rough=0.95)
    # ---- floor, ceiling with the round skylight, walls
    box('floor', -HX - ALC - 0.3, HX + ALC + 0.3, -L - 0.3, 0.3, -0.12, 0.0, floor, 2.4)
    ceil = box('ceiling', -HX, HX, -L, 0.0, H, H + 0.25, ceil_boards, 2.0)
    cut(ceil, [cyl('c', OCU_R, 2, (0, CY, H), (0, 0, 0), wall, 64)])
    shaft = cyl('skylight shaft', OCU_R + 0.25, OCU_TOP - H, (0, CY, (H + OCU_TOP) / 2), (0, 0, 0), wall, 64)
    cut(shaft, [cyl('c', OCU_R, OCU_TOP - H + 1, (0, CY, (H + OCU_TOP) / 2), (0, 0, 0), wall, 64)]); box_uv(shaft, 2.0)
    for z in (H + 0.95, OCU_TOP - 0.1): torus('skylight ring', OCU_R - 0.05, 0.09, (0, CY, z), (0, 0, 0), timber)
    for i in range(24):                                                       # balustrade round the skylight
        a = i / 24 * 2 * math.pi; cyl('baluster', 0.05, 0.9, (math.cos(a) * (OCU_R - 0.05), CY + math.sin(a) * (OCU_R - 0.05), H + 0.5), (0, 0, 0), timber, 10)
    sky = light((0, CY, OCU_TOP + 0.3), 4500, (0.85, 0.82, 0.95), kind='AREA'); sky.data.shape = 'DISK'; sky.data.size = OCU_R * 2; sky.rotation_euler = (math.pi, 0, 0)
    # radial beams from the skylight ring out to the walls, plus a ring beam
    for i in range(16):
        a = i / 16 * 2 * math.pi; dx, dy = math.cos(a), math.sin(a)
        reach = min(HX / max(1e-3, abs(dx)), (L / 2) / max(1e-3, abs(dy))) - 0.2; mid = (OCU_R + reach) / 2
        bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1); bmesh.ops.scale(bm, vec=(reach - OCU_R, 0.26, 0.34), verts=bm.verts)
        bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(a, 3, 'Z')); bmesh.ops.translate(bm, vec=(dx * mid, CY + dy * mid, H - 0.17), verts=bm.verts)
        b = obj_from_bm('beam', bm, timber); box_uv(b, 1.2)
        for k in range(4): ivy_cluster(ivy, dx * (OCU_R + (k + 0.5) * (reach - OCU_R) / 4), CY + dy * (OCU_R + (k + 0.5) * (reach - OCU_R) / 4), H - 0.4, 10, 0.3, 0.5 if k % 2 else 0)
    torus('ring beam', OCU_R + 0.1, 0.17, (0, CY, H - 0.17), (0, 0, 0), timber)
    for i in range(30): a = i / 30 * 2 * math.pi; ivy_cluster(ivy, math.cos(a) * (OCU_R + 0.15), CY + math.sin(a) * (OCU_R + 0.15), H - 0.35, 8, 0.25, 0.9 if i % 3 == 0 else 0)
    T = 0.45
    front = box('front wall', -HX - T, HX + T, 0.0, T, 0.0, H, wall, 2.2)
    back = box('back wall', -HX - T, HX + T, -L - T, -L, 0.0, H, wall, 2.2)
    side = {s: box('side wall', s * HX - (T if s < 0 else 0), s * HX + (T if s > 0 else 0), -L, 0.0, 0.0, H, wall, 2.2) for s in (-1, 1)}
    # front: the arched garden doors and two tall arched windows
    DW, DRH = 3.1, 2.75; WW, WRH, WZ = 1.45, 1.85, 0.85
    cut(front, arch_cutter(0, T / 2, True, DW, DRH) + sum((arch_cutter(s * 3.7, T / 2, True, WW, WRH, WZ) for s in (-1, 1)), []))
    arch_trim(0, T / 2, True, DW, DRH, 0.0, stone, 0.24, T + 0.12)
    for s in (-1, 1):
        arch_trim(s * 3.7, T / 2, True, WW, WRH, WZ, stone, 0.16, T + 0.08)
        win = bpy.data.objects.new('window', None); bpy.context.scene.collection.objects.link(win); win.location = (s * 3.7 - WW / 2, T / 2, WZ); glazed_leaf(win, WW, WRH, frame, glass, (3, 4))
        half = half_disc('window top glass', WW / 2 - 0.05, s * 3.7, T / 2, WZ + WRH, glass)
        for k in range(3): a = (k + 1) / 4 * math.pi; bb = box('fan bar', -0.015, 0.015, -0.02, 0.02, 0, WW / 2 - 0.05, frame, 1.0); bb.location = (s * 3.7, T / 2, WZ + WRH); bb.rotation_euler = (0, a - math.pi / 2, 0)
        box('sill', s * 3.7 - WW / 2 - 0.15, s * 3.7 + WW / 2 + 0.15, -0.25, T / 2, WZ - 0.08, WZ, stone, 1.2)
        glow = light((s * 3.7, 1.2, WZ + 1.2), 700, (1.0, 0.72, 0.45), kind='AREA'); glow.data.size = 1.5; glow.rotation_euler = (math.radians(90), 0, 0)
        # door leaves standing open into the hall
        hinge = bpy.data.objects.new('door hinge', None); bpy.context.scene.collection.objects.link(hinge)
        hinge.location = (s * DW / 2, -0.02, 0.0); hinge.rotation_euler = (0, 0, math.radians(-75 if s < 0 else 75) + (0 if s < 0 else math.pi))
        glazed_leaf(hinge, DW / 2 - 0.03, DRH + 0.05, frame, glass, (2, 6))
    transom = half_disc('door top glass', DW / 2 - 0.08, 0, T / 2, DRH + 0.05, glass)
    box('door head', -DW / 2, DW / 2, T / 2 - 0.05, T / 2 + 0.05, DRH, DRH + 0.08, frame, 1.0)
    for k in range(5): a = (k + 1) / 6 * math.pi; bb = box('fan bar', -0.02, 0.02, -0.03, 0.03, 0, DW / 2 - 0.1, frame, 1.0); bb.location = (0, T / 2, DRH + 0.05); bb.rotation_euler = (0, a - math.pi / 2, 0)
    # side arcades opening into alcoves; the left alcove holds a little sitting room, the right one a console and paintings
    AW, ARH = 2.5, 2.55
    for s in (-1, 1):
        cut(side[s], sum((arch_cutter(s * (HX + T / 2), y, False, AW, ARH) for y in ARCHES), []))
        for y in ARCHES:
            arch_trim(s * (HX + T / 2), y, False, AW, ARH, 0.0, stone, 0.18, T + 0.1)
            for k in range(6): ivy_cluster(ivy, s * (HX - 0.05), y + math.cos(k / 5 * math.pi) * (AW / 2 + 0.1), ARH + math.sin(k / 5 * math.pi) * (AW / 2 + 0.1), 6, 0.2, 0.3)
        ax0 = s * (HX + T); ax1 = s * (HX + T + ALC)
        box('alcove ceiling', min(ax0, ax1), max(ax0, ax1), -L, 0.0, 3.6, 3.8, ceil_boards, 2.0)
        box('alcove back', min(ax1, ax1 + s * 0.3), max(ax1, ax1 + s * 0.3), -L, 0.0, 0.0, 3.8, wall, 2.2)
        box('alcove front', min(ax0, ax1), max(ax0, ax1), 0.0, T, 0.0, 3.8, wall, 2.2); box('alcove end', min(ax0, ax1), max(ax0, ax1), -L - T, -L, 0.0, 3.8, wall, 2.2)
        box('alcove wall above', min(ax0, ax1), max(ax0, ax1), -L, 0.0, 3.8, H, wall, 2.2)
        for y in ARCHES:
            ex = s * (HX + T + ALC - 0.1); light((s * (HX + T + 1.4), y, 2.8), 380, radius=0.3)
            model('fancy_picture_frame_01' if y != ARCHES[1] else 'hanging_picture_frame_02', (ex, y, 1.5), -s * math.pi / 2, width=1.0)
        if s < 0:
            model('dining_table', (ax0 - 1.4, ARCHES[0], 0), math.pi / 2, width=1.6); [model('dining_chair_02', (ax0 - 1.4 + dx, ARCHES[0] + dy, 0), r, height=0.95) for dx, dy, r in ((0.55, 0.0, -math.pi / 2), (-0.55, 0.0, math.pi / 2))]
            model('ArmChair_01', (ax0 - 1.3, ARCHES[1], 0), math.pi / 2, width=0.9); model('potted_plant_01', (ax0 - 2.3, ARCHES[2], 0), height=1.5); model('wooden_bookshelf_worn', (ax1 + 0.35, ARCHES[2], 0), math.pi / 2, height=2.2)
            candle((ax0 - 1.4, ARCHES[0], 0.78), 0.2, 10)
        else:
            model('WoodenTable_01', (ax1 - 0.45, ARCHES[1], 0), math.pi / 2, width=1.7); candle((ax1 - 0.45, ARCHES[1] - 0.4, 0.55), 0.22, 10); model('brass_vase_01', (ax1 - 0.45, ARCHES[1] + 0.4, 0.55), height=0.4)
            model('potted_plant_02', (ax0 + 1.2, ARCHES[0], 0), height=1.1); model('vintage_cabinet_01', (ax1 - 0.4, ARCHES[2], 0), -math.pi / 2, width=1.7)
    # stone pilasters between the arches, with wall lanterns
    for s in (-1, 1):
        for y in (0 - 1.3, -5.25, -8.75, -L + 1.3):
            box('pilaster', s * HX - (0.3 if s > 0 else -0.3) - 0.22, s * HX - (0.3 if s > 0 else -0.3) + 0.22, y - 0.35, y + 0.35, 0.0, H, stone, 1.2)
            model('wooden_lantern_01', (s * (HX - 0.62), y, 2.2), -s * math.pi / 2, height=0.42); light((s * (HX - 0.8), y, 2.45), 70)
            ivy_cluster(ivy, s * (HX - 0.5), y, 3.6, 10, 0.25, 1.5)
    # the big round rug
    bm = bmesh.new(); bmesh.ops.create_circle(bm, cap_ends=True, segments=96, radius=3.3); uv = bm.loops.layers.uv.new()
    for f in bm.faces:
        for l in f.loops: l[uv].uv = (l.vert.co.x / 6.6 + 0.5, l.vert.co.y / 6.6 + 0.5)
    r = obj_from_bm('rug', bm, rug); r.location = (0, CY - 0.4, 0.006)
    # the iron cage lantern hanging in the skylight
    cz = H - 1.0; ch = 1.25; cr = 0.6
    for z in (cz, cz + ch / 2, cz + ch): torus('cage ring', cr, 0.025, (0, CY, z), (0, 0, 0), iron)
    for i in range(14): a = i / 14 * 2 * math.pi; cyl('cage bar', 0.015, ch, (math.cos(a) * cr, CY + math.sin(a) * cr, cz + ch / 2), (0, 0, 0), iron, 8)
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=cr + 0.05, radius2=0.08, depth=0.45); o = obj_from_bm('cage top', bm, iron, True); o.location = (0, CY, cz + ch + 0.22)
    cyl('chain', 0.02, OCU_TOP - (cz + ch + 0.45), (0, CY, (OCU_TOP + cz + ch + 0.45) / 2), (0, 0, 0), iron, 8)
    for dx, dy, hh in ((0, 0, 0.3), (0.22, 0.1, 0.2), (-0.2, 0.15, 0.22), (0.05, -0.22, 0.25), (-0.12, -0.12, 0.18)): candle((dx, CY + dy, cz + 0.1), hh, 30)
    light((0, CY, cz + 0.5), 260, radius=0.4)
    # console tables, plants and floor lanterns along the front wall and the hall, like the image
    for s in (-1, 1):
        model('WoodenTable_01', (s * 2.25, -0.75, 0), 0.0, width=1.3); candle((s * 2.0, -0.75, 0.55), 0.2, 8)
        model('potted_plant_01', (s * 5.2, -0.9, 0), height=1.7); model('potted_plant_02', (s * 1.85, -0.5, 0), height=1.0)
        for y in (-2.3, -12.2): model('potted_plant_01', (s * (HX - 1.0), y, 0), height=1.6)
        for y in (-1.6, -6.0, -9.5): model('wooden_lantern_01', (s * (HX - 1.2), y, 0), 0, height=0.5); light((s * (HX - 1.2), y, 0.35), 25)
        model('hanging_picture_frame_01', (s * 5.0, -L + 0.08, 2.4), 0, width=1.2)
    model('vintage_grandfather_clock_01', (0, -L + 0.35, 0), 0, height=2.3)
    # outside: stone terrace, wooden railing and the lake at sunset
    box('terrace', -8, 8, T, 4.0, -0.12, 0.0, stone, 1.4)
    for x in [i * 0.9 - 6.3 for i in range(15)]:
        if abs(x) > 0.2: box('rail post', x - 0.06, x + 0.06, 3.6, 3.72, 0.0, 1.0, frame, 1.0)
    box('rail', -6.4, 6.4, 3.6, 3.72, 0.95, 1.05, frame, 1.0); box('rail low', -6.4, 6.4, 3.6, 3.72, 0.45, 0.52, frame, 1.0)
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1); bmesh.ops.scale(bm, vec=(80, 22, 1), verts=bm.verts)
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 4, 'X')); bmesh.ops.translate(bm, vec=(0, 45, 2.0), verts=bm.verts)
    view = obj_from_bm('lake view', bm, image_mat('view', A('assets', 'hero', 'view.jpg'), 1.3)); uvl = view.data.uv_layers.new()
    for i, l in enumerate(uvl.data): co = view.data.vertices[view.data.loops[i].vertex_index].co; l.uv = (co.x / 80 + 0.5, (co.z - 2.0) / 22 + 0.5)
    for x, y in ((-5.5, 3.0), (5.8, 2.9), (-2.4, 3.2), (2.6, 3.1)): model('potted_plant_02', (x, y, 0), height=1.2)
    # sunset light coming in through the garden doors
    sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 3.0; sun.color = (1.0, 0.7, 0.45); sun.angle = math.radians(2.5)
    so = bpy.data.objects.new('sun', sun); bpy.context.scene.collection.objects.link(so); so.rotation_euler = (math.radians(-75), 0, math.radians(10))
    dl = light((0, 1.0, 2.2), 2400, (1.0, 0.78, 0.55), kind='AREA'); dl.data.size = 3.0; dl.rotation_euler = (math.radians(90), 0, 0)
    w = bpy.data.worlds.new('w'); bpy.context.scene.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0.75, 0.55, 0.5, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.5

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--render', default=''); ap.add_argument('--samples', type=int, default=96); ap.add_argument('--res', default='1280x720')
    ap.add_argument('--glb', default=''); ap.add_argument('--blend', default=''); ap.add_argument('--cam', default=f'0,{-L + 0.6},1.6,87,0,17')
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
    bpy.ops.wm.read_factory_settings(use_empty=True); build()
    for o in bpy.context.scene.objects:
        if o.type == 'LIGHT' and hasattr(o, 'visible_camera'): o.visible_camera = False
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = a.samples; sc.cycles.use_denoising = True; sc.cycles.max_bounces = 8
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'; sc.view_settings.exposure = 0.6
    w, h = map(int, a.res.split('x')); sc.render.resolution_x, sc.render.resolution_y = w, h
    x, y, z, tilt, head, lens = map(float, a.cam.split(',')); cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera')); sc.collection.objects.link(cam); sc.camera = cam
    cam.location = (x, y, z); cam.rotation_euler = (math.radians(tilt), 0, math.radians(head)); cam.data.lens = lens
    if a.blend: bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.blend))
    if a.glb:
        bpy.ops.object.select_all(action='DESELECT')
        for o in list(sc.objects):
            if o.type == 'EMPTY' and o.instance_type == 'COLLECTION': o.select_set(True)
        if any(o.select_get() for o in sc.objects): bpy.ops.object.duplicates_make_real()
        bpy.ops.export_scene.gltf(filepath=os.path.abspath(a.glb), export_format='GLB', export_lights=False, export_cameras=False, export_apply=True, export_image_format='AUTO')
    if a.render: sc.render.filepath = os.path.abspath(a.render); bpy.ops.render.render(write_still=True)

if __name__ == '__main__':
    main()
