"""Builds the round-door hall (the reference render the user sent) as a real 3D room in Blender, then renders it
and exports a .glb for the walkable web version.

    python blender/hero_room.py --render docs/hero.png --samples 128 --res 1600x900 --glb assets/hero/hall.glb --blend hall.blend

Layout (metres, Blender axes): the front wall with the round door is at y = 0, the room runs back to y = -D,
x is left/right, z is up. The camera in the reference stands near the back, looking at the door.
"""
import argparse, math, os, sys, random
import bpy, bmesh
from mathutils import Vector, Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = lambda *p: os.path.join(ROOT, *p)
HW, D, WALL_H, APEX = 4.2, 8.0, 1.25, 3.9        # half width, depth, height where the walls start to curve, ceiling apex
DOOR_R, DOOR_C = 1.18, 1.32                      # round door radius and centre height
rnd = random.Random(4)

def profile(n=36, inset=0.0):
    """Cross-section of the vault: vertical walls, then an elliptical arch to the apex."""
    pts = [(-HW + inset, 0.0)]
    for i in range(n + 1):
        a = math.pi - i / n * math.pi
        pts.append((math.cos(a) * (HW - inset), WALL_H + math.sin(a) * (APEX - WALL_H - inset)))
    pts.append((HW - inset, 0.0)); return pts

# ---------------------------------------------------------------- materials
_m = {}
def pbr(name, folder, tile_tint=(1, 1, 1), rough_mul=1.0, normal=1.0):
    key = (name, tile_tint, rough_mul)
    if key in _m: return _m[key]
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; b = nt.nodes['Principled BSDF']
    def img(kind, colour):
        p = A('assets', folder, f'{name}_{kind}.jpg')
        if not os.path.exists(p): return None
        n = nt.nodes.new('ShaderNodeTexImage'); n.image = bpy.data.images.load(p, check_existing=True); n.image.colorspace_settings.name = 'sRGB' if colour else 'Non-Color'; return n
    d, r, nm = img('diff', True), img('rough', False), img('nor', False)
    if d:
        mix = nt.nodes.new('ShaderNodeMixRGB'); mix.blend_type = 'MULTIPLY'; mix.inputs[0].default_value = 1; mix.inputs[2].default_value = (*tile_tint, 1)
        nt.links.new(d.outputs[0], mix.inputs[1]); nt.links.new(mix.outputs[0], b.inputs['Base Color'])
    if r:
        mr = nt.nodes.new('ShaderNodeMath'); mr.operation = 'MULTIPLY'; mr.inputs[1].default_value = rough_mul; nt.links.new(r.outputs[0], mr.inputs[0]); nt.links.new(mr.outputs[0], b.inputs['Roughness'])
    if nm:
        nn = nt.nodes.new('ShaderNodeNormalMap'); nn.inputs['Strength'].default_value = normal; nt.links.new(nm.outputs[0], nn.inputs['Color']); nt.links.new(nn.outputs[0], b.inputs['Normal'])
    _m[key] = m; return m

def flat(name, rgb, rough=0.5, metal=0.0, emit=None, strength=0.0, transmission=0.0):
    if name in _m: return _m[name]
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1); b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    if emit: b.inputs['Emission Color'].default_value = (*emit, 1); b.inputs['Emission Strength'].default_value = strength
    if transmission: b.inputs['Transmission Weight'].default_value = transmission
    _m[name] = m; return m

def image_mat(name, path, strength=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(path); e = nt.nodes.new('ShaderNodeEmission'); e.inputs['Strength'].default_value = strength
    o = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(t.outputs[0], e.inputs[0]); nt.links.new(e.outputs[0], o.inputs[0]); return m

# ---------------------------------------------------------------- mesh helpers
def obj_from_bm(name, bm, mat=None, smooth=False):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o)
    if mat: me.materials.append(mat)
    if smooth:
        for p in me.polygons: p.use_smooth = True
    return o

def box_uv(o, tile=2.0):
    bm = bmesh.new(); bm.from_mesh(o.data); uv = bm.loops.layers.uv.verify(); mw = o.matrix_world
    for f in bm.faces:
        n = (mw.to_3x3() @ f.normal); ax = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            w = mw @ l.vert.co; u, v = ((w.y, w.z) if ax == 0 else (w.x, w.z) if ax == 1 else (w.x, w.y)); l[uv].uv = (u / tile, v / tile)
    bm.to_mesh(o.data); bm.free()

def box(name, x0, x1, y0, y1, z0, z1, mat, tile=1.5, bevel=0.0):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1); bmesh.ops.scale(bm, vec=(x1 - x0, y1 - y0, z1 - z0), verts=bm.verts)
    bmesh.ops.translate(bm, vec=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), verts=bm.verts); o = obj_from_bm(name, bm, mat); box_uv(o, tile)
    if bevel: b = o.modifiers.new('bevel', 'BEVEL'); b.width = bevel; b.segments = 3
    return o

def cyl(name, r, depth, loc, rot, mat, seg=48):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=depth); o = obj_from_bm(name, bm, mat, True)
    o.location = loc; o.rotation_euler = rot; return o

def torus(name, R, r, loc, rot, mat):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, major_segments=72, minor_segments=14, location=loc, rotation=rot)
    o = bpy.context.active_object; o.name = name; o.data.materials.append(mat)
    for p in o.data.polygons: p.use_smooth = True
    return o

def cut(target, cutters):
    for c in cutters:
        md = target.modifiers.new('cut', 'BOOLEAN'); md.object = c; md.operation = 'DIFFERENCE'; md.solver = 'EXACT'
        bpy.context.view_layer.objects.active = target; bpy.ops.object.modifier_apply(modifier=md.name); bpy.data.objects.remove(c, do_unlink=True)

def sweep_profile(name, pts, y, w, d, mat):
    """A timber rib: a rectangular section swept along the vault profile at depth y."""
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
    for i, (x, z) in enumerate(pts): sp.points[i].co = (x, y, z, 1)
    prof = bpy.data.curves.new(name + '_p', 'CURVE'); ps = prof.splines.new('POLY'); ps.points.add(3)
    for i, (a, b) in enumerate(((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2))): ps.points[i].co = (a, b, 0, 1)
    ps.use_cyclic_u = True; po = bpy.data.objects.new(name + '_p', prof); bpy.context.scene.collection.objects.link(po)
    cu.bevel_mode = 'OBJECT'; cu.bevel_object = po; cu.use_fill_caps = True
    o = bpy.data.objects.new(name, cu); bpy.context.scene.collection.objects.link(o); o.data.materials.append(mat)
    bpy.context.view_layer.objects.active = o; o.select_set(True); bpy.ops.object.convert(target='MESH'); o.select_set(False)
    bpy.data.objects.remove(po, do_unlink=True); box_uv(o, 1.2); return o

_lib = {}
def model(name, loc, rot_z=0.0, height=None, width=None):
    path = next((p for p in (A('assets', 'models', name + '.glb'), A('assets', 'khronos', name + '.glb')) if os.path.exists(p)), None)
    if not path: print('missing', name); return None
    if name not in _lib:
        before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=path); objs = [o for o in bpy.data.objects if o not in before]
        root = bpy.data.objects.new(name + '_src', None); bpy.context.scene.collection.objects.link(root)
        for o in objs:
            if o.type == 'LIGHT': bpy.data.objects.remove(o, do_unlink=True); continue
            if o.parent is None: o.parent = root
        bpy.context.view_layer.update(); lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
        for o in root.children_recursive:
            if o.type == 'MESH':
                for v in o.bound_box: w = o.matrix_world @ Vector(v); lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
        lib = bpy.data.collections.new('lib_' + name)
        for o in [root] + list(root.children_recursive):
            for uc in list(o.users_collection): uc.objects.unlink(o)
            lib.objects.link(o)
        root.location = (-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z); _lib[name] = (lib, hi - lo)
    lib, size = _lib[name]; inst = bpy.data.objects.new(name, None); inst.instance_type = 'COLLECTION'; inst.instance_collection = lib
    bpy.context.scene.collection.objects.link(inst); s = 1.0
    if height: s = height / size.z
    if width: s = width / max(size.x, size.y)
    inst.scale = (s, s, s); inst.location = loc; inst.rotation_euler = (0, 0, rot_z); return inst

def light(loc, power, colour=(1.0, 0.68, 0.38), radius=0.04, kind='POINT'):
    l = bpy.data.lights.new('l', kind); l.energy = power; l.color = colour
    if kind == 'POINT': l.shadow_soft_size = radius
    o = bpy.data.objects.new('l', l); o.location = loc; bpy.context.scene.collection.objects.link(o); return o

def candle(loc, h=0.16, power=6.0):
    wax, flame = flat('wax', (0.92, 0.88, 0.78), 0.45), flat('flame', (1, 0.6, 0.2), 1, emit=(1.0, 0.62, 0.25), strength=40)
    cyl('candle', 0.022, h, (loc[0], loc[1], loc[2] + h / 2), (0, 0, 0), wax, 16)
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.009, radius2=0.0, depth=0.035); f = obj_from_bm('flame', bm, flame, True)
    f.location = (loc[0], loc[1], loc[2] + h + 0.02); light((loc[0], loc[1], loc[2] + h + 0.05), power)

# ---------------------------------------------------------------- the room
def build():
    plaster = pbr('clay_plaster', 'materials', (0.98, 0.97, 0.9), 1.0, 1.6)
    wood = pbr('dark_wooden_planks', 'materials', (0.55, 0.36, 0.22), 0.9)
    wood_mid = pbr('oak_wood_planks', 'materials', (0.62, 0.42, 0.26), 0.8)
    tile = pbr('octotile', 'hero', (1, 1, 1), 1.0, 0.6)
    iron, brass = flat('iron', (0.08, 0.07, 0.06), 0.45, 0.8), flat('brass', (0.72, 0.5, 0.24), 0.3, 1.0)
    copper = flat('copper', (0.55, 0.28, 0.16), 0.35, 1.0)
    door_wood = pbr('dark_wooden_planks', 'materials', (0.34, 0.22, 0.15), 0.8)
    glass = flat('glass', (0.95, 0.97, 0.98), 0.02, transmission=1.0)
    prof = profile()
    # floor
    f = box('floor', -HW - 0.3, HW + 0.3, -D - 0.3, 0.3, -0.1, 0.0, tile, 1.9)
    # vault: extrude the profile along the depth of the room
    bm = bmesh.new(); ring0 = [bm.verts.new((x, 0.0, z)) for x, z in prof]; ring1 = [bm.verts.new((x, -D, z)) for x, z in prof]
    for i in range(len(prof) - 1): bm.faces.new((ring0[i], ring0[i + 1], ring1[i + 1], ring1[i]))
    vault = obj_from_bm('vault', bm, plaster, True); sol = vault.modifiers.new('s', 'SOLIDIFY'); sol.thickness = 0.25; box_uv(vault, 2.2)
    # timber ribs every 1.6 m plus a ridge beam and two side beams along the length
    rib_pts = profile(36, 0.02)[1:-1]
    for y in [-0.25] + [-1.6 * k for k in range(1, int(D / 1.6) + 1)]:
        sweep_profile('rib', [(prof[1][0] + 0.02, 0.0)] + rib_pts + [(prof[-2][0] - 0.02, 0.0)], y, 0.24, 0.22, wood)
    box('ridge', -0.16, 0.16, -D, 0.0, APEX - 0.32, APEX - 0.02, wood, 1.2)
    for s in (-1, 1):
        box('purlin', s * (HW * 0.72) - 0.12, s * (HW * 0.72) + 0.12, -D, 0.0, WALL_H + 1.55, WALL_H + 1.8, wood, 1.2)
        # wainscot panelling with a curved top rail along the side walls
        box('wainscot', s * HW - (0.06 if s > 0 else -0.06) - 0.04, s * HW - (0.06 if s > 0 else -0.06) + 0.04, -D, -0.3, 0.0, 0.92, wood_mid, 1.0)
        box('rail', s * HW - (0.1 if s > 0 else -0.1) - 0.06, s * HW - (0.1 if s > 0 else -0.1) + 0.06, -D, -0.3, 0.9, 0.97, wood, 1.0, 0.01)
        for k in range(int(D / 1.0)):
            y = -0.8 - k * 1.0; x = s * HW - (0.11 if s > 0 else -0.11)
            box('panel', x - 0.02, x + 0.02, y - 0.38, y + 0.38, 0.12, 0.8, wood, 1.0, 0.008)
    # front wall with the round door and two round windows
    def end_wall(name, y, thick, holes):
        bm = bmesh.new(); vs = [bm.verts.new((x, y, z)) for x, z in prof]; bm.faces.new(vs); w = obj_from_bm(name, bm, plaster)
        s = w.modifiers.new('s', 'SOLIDIFY'); s.thickness = thick; s.offset = 1.0 if y < -1 else -1.0
        bpy.context.view_layer.objects.active = w; bpy.ops.object.modifier_apply(modifier='s')
        cut(w, [cyl('c', r, 2, (x, y, z), (math.pi / 2, 0, 0), plaster) for x, z, r in holes]); box_uv(w, 2.2); return w
    end_wall('front', 0.0, 0.42, [(0, DOOR_C, DOOR_R), (-2.55, 2.0, 0.44), (2.55, 2.0, 0.44)])
    end_wall('back', -D, 0.3, [])
    # door frame, round open door with iron studs, threshold
    torus('door frame', DOOR_R + 0.07, 0.11, (0, 0.02, DOOR_C), (math.pi / 2, 0, 0), wood)
    torus('door frame outer', DOOR_R + 0.24, 0.06, (0, -0.1, DOOR_C), (math.pi / 2, 0, 0), wood)
    hinge = bpy.data.objects.new('door hinge', None); bpy.context.scene.collection.objects.link(hinge); hinge.location = (-DOOR_R + 0.04, -0.18, DOOR_C); hinge.rotation_euler = (0, 0, math.radians(-78))
    dr = cyl('door', DOOR_R - 0.04, 0.09, (DOOR_R - 0.04, 0, 0), (math.pi / 2, 0, 0), door_wood, 72); dr.parent = hinge; box_uv(dr, 1.0)
    for ring in range(1, 4):
        n = 8 * ring
        for i in range(n):
            a = i / n * 2 * math.pi; rr = (DOOR_R - 0.04) * ring / 3.6
            st = cyl('stud', 0.018, 0.02, (DOOR_R - 0.04 + math.cos(a) * rr, -0.055, math.sin(a) * rr), (math.pi / 2, 0, 0), iron, 10); st.parent = hinge
    kn = cyl('knob', 0.06, 0.06, (DOOR_R - 0.04, -0.09, 0), (math.pi / 2, 0, 0), brass, 24); kn.parent = hinge
    box('threshold', -1.0, 1.0, -0.25, 0.25, 0.0, 0.03, pbr('rustic_stone_wall', 'materials'), 1.0)
    for sx in (-2.55, 2.55):
        torus('win frame', 0.47, 0.06, (sx, -0.02, 2.0), (math.pi / 2, 0, 0), wood)
        box('mullion', sx - 0.02, sx + 0.02, -0.2, -0.16, 1.56, 2.44, wood, 1.0); box('transom', sx - 0.44, sx + 0.44, -0.2, -0.16, 1.98, 2.02, wood, 1.0)
        cyl('pane', 0.44, 0.01, (sx, -0.18, 2.0), (math.pi / 2, 0, 0), glass, 36)
        # shelf with a curved underside below each window
        box('shelf', sx - 1.0, sx + 1.0, -0.62, -0.21, 1.42, 1.48, wood, 1.0, 0.01)
        for bx_ in (sx - 0.8, sx + 0.8): box('bracket', bx_ - 0.03, bx_ + 0.03, -0.55, -0.21, 1.2, 1.42, wood, 1.0)
        model('book_encyclopedia_set_01', (sx - 0.45, -0.42, 1.48), 0, width=0.45); candle((sx + 0.15, -0.4, 1.48)); model('brass_vase_01', (sx + 0.55, -0.42, 1.48), height=0.22)
        light((sx, 0.6, 2.0), 500, (0.75, 0.85, 1.0), kind='POINT')
    # timber posts and carved panels flanking the door
    for sx in (-1.75, 1.75): box('post', sx - 0.11, sx + 0.11, -0.4, -0.18, 0.0, 3.2, wood, 1.0, 0.02)
    # archway in the right wall leading on into the house
    arch_y = -5.0; c1 = cyl('c', 0.85, 2, (HW, arch_y, 1.95), (0, math.pi / 2, 0), plaster); c2 = box('c', HW - 1, HW + 1, arch_y - 0.85, arch_y + 0.85, 0.0, 1.95, plaster)
    cut(vault, [c1, c2]); torus('arch frame', 0.95, 0.09, (HW - 0.12, arch_y, 1.95), (0, math.pi / 2, 0), wood)
    for dy in (-0.95, 0.95): box('arch post', HW - 0.24, HW, arch_y + dy - 0.09, arch_y + dy + 0.09, 0.0, 1.95, wood, 1.0)
    box('corridor', HW, HW + 3, arch_y - 1.1, arch_y + 1.1, -0.1, 0.0, tile, 1.9); box('corridor wall', HW + 2.6, HW + 2.8, arch_y - 1.2, arch_y + 1.2, 0.0, 3.0, plaster, 2.2)
    light((HW + 1.5, arch_y, 2.0), 40)
    # left side: long desk with a map, candle, pipe-rack style books; chest by the door; stool and fruit on the right
    box('desk top', -HW + 0.15, -HW + 0.85, -3.3, -1.0, 0.82, 0.88, wood_mid, 1.0, 0.01)
    for y in (-3.2, -1.1): box('desk leg', -HW + 0.2, -HW + 0.8, y - 0.05, y + 0.05, 0.0, 0.82, wood, 1.0)
    box('map', -HW + 0.3, -HW + 0.8, -2.4, -1.7, 0.88, 0.884, flat('parchment', (0.78, 0.66, 0.46), 0.8), 1.0)
    model('book_encyclopedia_set_01', (-HW + 0.5, -2.9, 0.88), math.pi / 2, width=0.4); candle((-HW + 0.45, -1.35, 0.88), 0.2, 8)
    model('treasure_chest', (-1.55, -0.85, 0.0), 0.0, width=0.95)
    model('WoodenTable_02', (2.3, -0.9, 0.0), 0, height=0.55)
    for i in range(4):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.06, location=(2.25 + (i % 2) * 0.12, -0.9 + (i // 2) * 0.1, 0.62)); o = bpy.context.active_object; o.data.materials.append(flat('orange', (0.85, 0.38, 0.08), 0.5))
    candle((-1.95, -0.5, 0.0), 1.15, 0)                       # tall candle stand by the chest
    cyl('stand', 0.025, 1.15, (-1.95, -0.5, 0.575), (0, 0, 0), iron, 12)
    # wrought-iron candle chandelier
    ch = (0.0, -2.2, 3.0); cyl('chain', 0.012, APEX - 0.3 - ch[2], (ch[0], ch[1], (APEX - 0.3 + ch[2]) / 2), (0, 0, 0), iron, 8)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=ch); o = bpy.context.active_object; o.data.materials.append(copper)
    for i in range(6):
        a = i / 6 * 2 * math.pi; ex, ey = ch[0] + math.cos(a) * 0.5, ch[1] + math.sin(a) * 0.5
        arm = cyl('arm', 0.015, 0.52, ((ch[0] + ex) / 2, (ch[1] + ey) / 2, ch[2] - 0.05), (0, math.pi / 2, a), iron, 8)
        cyl('cup', 0.05, 0.03, (ex, ey, ch[2] - 0.05), (0, 0, 0), copper, 16); candle((ex, ey, ch[2] - 0.035), 0.17, 18)
    light((ch[0], ch[1], ch[2] - 0.3), 120, radius=0.3)
    # outside: lawn, stone path and the lake view
    grass = pbr('leafy_grass', 'materials', (0.6, 0.85, 0.45)); box('lawn', -30, 30, 0.2, 9.0, -0.15, -0.05, grass, 2.5)
    box('path', -0.9, 0.9, 0.2, 5, -0.06, -0.02, pbr('cobblestone_floor_01', 'materials'), 1.2)
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1); bmesh.ops.scale(bm, vec=(56, 15, 1), verts=bm.verts)
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 4, 'X')); bmesh.ops.translate(bm, vec=(0, 30, 0.6), verts=bm.verts)
    view = obj_from_bm('lake view', bm, image_mat('view', A('assets', 'hero', 'view.jpg'), 1.4))
    uvl = view.data.uv_layers.new()
    for i, l in enumerate(uvl.data):
        co = view.data.vertices[view.data.loops[i].vertex_index].co; l.uv = (co.x / 56 + 0.5, (co.z - 0.6) / 15 + 0.5)
    for x, y in ((-2.6, 1.2), (2.4, 1.0), (-3.4, 2.4), (3.3, 2.2)): model('shrub_04' if x > 0 else 'potted_plant_02', (x, y, -0.05), rnd.uniform(0, 6), height=1.1)
    # daylight: sun shining in through the door, plus soft sky light from the doorway
    sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 3.5; sun.color = (1.0, 0.93, 0.84); sun.angle = math.radians(2)
    so = bpy.data.objects.new('sun', sun); bpy.context.scene.collection.objects.link(so); so.rotation_euler = (math.radians(-62), 0, math.radians(8))
    sky = light((0, 0.35, DOOR_C), 2200, (0.8, 0.88, 1.0), kind='AREA'); sky.data.shape = 'DISK'; sky.data.size = 2.2; sky.rotation_euler = (math.radians(90), 0, 0)
    w = bpy.data.worlds.new('w'); bpy.context.scene.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0.55, 0.62, 0.72, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.6

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--render', default=''); ap.add_argument('--samples', type=int, default=96); ap.add_argument('--res', default='1280x720')
    ap.add_argument('--glb', default=''); ap.add_argument('--blend', default=''); ap.add_argument('--cam', default='0,-7.4,1.55,86,0,22')
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
    bpy.ops.wm.read_factory_settings(use_empty=True); build()
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = a.samples; sc.cycles.use_denoising = True; sc.cycles.max_bounces = 8
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'; sc.view_settings.exposure = 0.75
    w, h = map(int, a.res.split('x')); sc.render.resolution_x, sc.render.resolution_y = w, h
    x, y, z, tilt, head, lens = map(float, a.cam.split(',')); cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera')); sc.collection.objects.link(cam); sc.camera = cam
    cam.location = (x, y, z); cam.rotation_euler = (math.radians(tilt), 0, math.radians(head)); cam.data.lens = lens
    if a.blend: bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.blend))
    if a.glb:
        bpy.ops.object.select_all(action='DESELECT')
        for o in list(sc.objects):
            if o.type == 'EMPTY' and o.instance_type == 'COLLECTION': o.select_set(True)
        if any(o.select_get() for o in sc.objects): bpy.ops.object.duplicates_make_real()
        bpy.ops.export_scene.gltf(filepath=os.path.abspath(a.glb), export_format='GLB', export_lights=True, export_cameras=False, export_apply=True, export_image_format='JPEG', export_jpeg_quality=85)
    if a.render: sc.render.filepath = os.path.abspath(a.render); bpy.ops.render.render(write_still=True)

if __name__ == '__main__':
    main()
