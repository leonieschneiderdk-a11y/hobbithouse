"""Builds the hobbit house in Blender from the floor plan in index.html, with Poly Haven
models and materials, real sun + sky lighting, and renders it with Cycles.

Run with Blender as a Python module (pip install bpy==4.2.0, Python 3.11):
    python blender/build_scene.py --rooms entrance,living --render out.png
"""
import argparse, math, os, re, sys
import bpy, bmesh
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = lambda *p: os.path.join(ROOT, *p)
PXS, OX, OY = 0.12, 845, 895          # 1 plan pixel = 0.12 m, origin at the entrance hall (same as the web game)
WT, H = 0.24, 3.4                     # wall thickness, room height

def plan_xy(px, py):                  # game x -> Blender x, game z (south) -> Blender -y
    return ((px - OX) * PXS, -(py - OY) * PXS)

# ---------------------------------------------------------------- floor plan, read straight from the game
def read_plan():
    src = open(A('index.html'), encoding='utf8').read()
    rooms = []
    for m in re.finditer(r"room\(\{name:(['\"])(.*?)\1,type:'(\w+)'.*?floor:'(\w+)',px:\[(\d+),(\d+),(\d+),(\d+)\](.*?)\}\);", src):
        name, typ, floor = m.group(2), m.group(3), m.group(4)
        a, b, c, d = map(int, m.group(5, 6, 7, 8))
        rest = m.group(9)
        doors = [dict(side=s, at=float(at), w=float(w) if w else 1.5, flat=bool(f))
                 for s, at, w, f in re.findall(r"\{side:'(\w)',at:([\d.]+)(?:,w:([\d.]+))?(,flat:true)?", rest)]
        nowalls = re.findall(r"noWalls:\[([^\]]*)\]", rest)
        rooms.append(dict(name=name, type=typ, floor=floor, px=(a, b, c, d), doors=doors,
                          nowalls=re.findall(r"'(\w)'", nowalls[0]) if nowalls else []))
    rooms.append(dict(name='Main Entrance', type='entrance', floor='stone', px=(768, 798, 915, 987), h=5.0,
                      doors=[dict(side='W', at=874, w=12.6, flat=True), dict(side='W', at=962, w=1.5, flat=False),
                             dict(side='E', at=894, w=12.4, flat=True), dict(side='N', at=842, w=3.2, flat=False),
                             dict(side='S', at=805, w=2.4, flat=False)], nowalls=[]))
    return rooms

# ---------------------------------------------------------------- materials (Poly Haven scans)
_mats = {}
def pbr(name, tile=2.5, tint=(1, 1, 1)):
    key = (name, tint)
    if key in _mats: return _mats[key]
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; bsdf = nt.nodes['Principled BSDF']
    def img(kind, colour):
        p = A('assets', 'materials', f'{name}_{kind}.jpg')
        if not os.path.exists(p): return None
        n = nt.nodes.new('ShaderNodeTexImage'); n.image = bpy.data.images.load(p, check_existing=True)
        n.image.colorspace_settings.name = 'sRGB' if colour else 'Non-Color'; return n
    d, r, nm = img('diff', True), img('rough', False), img('nor', False)
    if d:
        mix = nt.nodes.new('ShaderNodeMixRGB'); mix.blend_type = 'MULTIPLY'; mix.inputs[0].default_value = 1
        nt.links.new(d.outputs[0], mix.inputs[1]); mix.inputs[2].default_value = (*tint, 1)
        nt.links.new(mix.outputs[0], bsdf.inputs['Base Color'])
    if r: nt.links.new(r.outputs[0], bsdf.inputs['Roughness'])
    if nm:
        nmap = nt.nodes.new('ShaderNodeNormalMap'); nt.links.new(nm.outputs[0], nmap.inputs['Color']); nt.links.new(nmap.outputs[0], bsdf.inputs['Normal'])
    _mats[key] = m; return m

def box_uv(obj, tile=2.5):
    """World-space box projection so scans tile at real size on every face."""
    bm = bmesh.new(); bm.from_mesh(obj.data); uv = bm.loops.layers.uv.verify(); mw = obj.matrix_world
    for f in bm.faces:
        n = f.normal; ax = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            w = mw @ l.vert.co
            u, v = ((w.y, w.z) if ax == 0 else (w.x, w.z) if ax == 1 else (w.x, w.y))
            l[uv].uv = (u / tile, v / tile)
    bm.to_mesh(obj.data); bm.free()

def cube(name, x0, x1, y0, y1, z0, z1, mat, tile=2.5):
    bpy.ops.mesh.primitive_cube_add(size=1, location=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    o = bpy.context.active_object; o.name = name; o.scale = (abs(x1 - x0), abs(y1 - y0), abs(z1 - z0))
    bpy.ops.object.transform_apply(scale=True); o.data.materials.append(mat); box_uv(o, tile); return o

def cut_openings(wall, cutters):
    for c in cutters:
        mod = wall.modifiers.new('cut', 'BOOLEAN'); mod.object = c; mod.operation = 'DIFFERENCE'; mod.solver = 'EXACT'
        bpy.context.view_layer.objects.active = wall; bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(c, do_unlink=True)
    box_uv(wall)

def opening_cutter(cx, cy, horiz, w, h, arched, z0=0.0):
    """A box (plus a half-cylinder on top for arches) that punches a doorway through a wall."""
    depth = 1.0
    sx, sy = (w, depth) if horiz else (depth, w)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, z0 + h / 2)); b = bpy.context.active_object; b.scale = (sx, sy, h)
    bpy.ops.object.transform_apply(scale=True)
    if arched:
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=w / 2, depth=depth, location=(cx, cy, z0 + h))
        cyl = bpy.context.active_object; cyl.rotation_euler = (math.pi / 2, 0, 0 if horiz else math.pi / 2)
        bpy.ops.object.select_all(action='DESELECT'); b.select_set(True); cyl.select_set(True); bpy.context.view_layer.objects.active = b; bpy.ops.object.join()
    return b

# ---------------------------------------------------------------- rooms
def build_room(r, mats):
    a, b, c, d = r['px']; (x0, y1), (x1, y0) = plan_xy(a, b), plan_xy(c, d)
    hgt = r.get('h', H); floor = {'wood': mats['floor_wood'], 'stone': mats['floor_stone'], 'dark': mats['floor_dark']}[r['floor']]
    cube(r['name'] + ' floor', x0, x1, y0, y1, -0.1, 0.0, floor)
    ceil = cube(r['name'] + ' ceiling', x0, x1, y0, y1, hgt, hgt + 0.1, mats['ceiling'])
    if r['type'] == 'entrance':                                  # round skylight over the rug, as in the plan
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=2.4, depth=1, location=((x0 + x1) / 2, (y0 + y1) / 2, hgt)); cut_openings(ceil, [bpy.context.active_object])
        sky = bpy.data.lights.new('skylight', 'AREA'); sky.shape = 'DISK'; sky.size = 4.6; sky.energy = 3500; sky.color = (0.85, 0.9, 1.0)
        so = bpy.data.objects.new('skylight', sky); so.location = ((x0 + x1) / 2, (y0 + y1) / 2, hgt + 0.05); bpy.context.scene.collection.objects.link(so)
    n = max(1, int((x1 - x0) / 1.8))
    for i in range(1, n):                                       # ceiling beams
        x = x0 + i * (x1 - x0) / n; cube(r['name'] + ' beam', x - 0.11, x + 0.11, y0 + 0.2, y1 - 0.2, hgt - 0.28, hgt, mats['beam'], 1.2)
    sides = {'N': (x0, x1, y1, True), 'S': (x0, x1, y0, True), 'W': (y0, y1, x0, False), 'E': (y0, y1, x1, False)}
    for s, (lo, hi, line, horiz) in sides.items():
        if s in r['nowalls']: continue
        inset = -WT / 2 if s in 'NE' else WT / 2
        if horiz: w = cube(f"{r['name']} wall {s}", lo, hi, line + inset - WT / 2, line + inset + WT / 2, 0, hgt, mats['wall'])
        else:     w = cube(f"{r['name']} wall {s}", line + inset - WT / 2, line + inset + WT / 2, lo, hi, 0, hgt, mats['wall'])
        cutters = []
        for dr in r['doors']:
            if dr['side'] != s: continue
            at = (dr['at'] - OX) * PXS if horiz else -(dr['at'] - OY) * PXS
            dw = min(dr['w'], (hi - lo) - 0.2)
            cx, cy = (at, line + inset) if horiz else (line + inset, at)
            cutters.append(opening_cutter(cx, cy, horiz, dw, 2.7 if dr['flat'] else 1.95, not dr['flat']))
        if r['type'] == 'entrance' and s in 'NS':                 # tall arched windows either side of the garden and front doors
            door_at = (842 if s == 'N' else 805 - 0) ; dx = (door_at - OX) * PXS
            for off in (-4.4, 4.4):
                cutters.append(opening_cutter(dx + off, line + inset, True, 1.4, 1.8, True, z0=1.0))
                win = bpy.data.lights.new('window', 'AREA'); win.size = 1.4; win.size_y = 2.4; win.shape = 'RECTANGLE'; win.energy = 900; win.color = (1.0, 0.82, 0.62)
                wo = bpy.data.objects.new('window', win); wo.location = (dx + off, line + inset + (0.3 if s == 'N' else -0.3), 2.3)
                wo.rotation_euler = (math.radians(90 if s == 'N' else -90), 0, 0); bpy.context.scene.collection.objects.link(wo)
        if cutters: cut_openings(w, cutters)
        # stone dado along the bottom of the wall
        if horiz: cube(f"{r['name']} dado {s}", lo + 0.02, hi - 0.02, line + inset - WT / 2 - 0.03, line + inset + WT / 2 + 0.03, 0, 0.9, mats['stone'], 1.5)
        else:     cube(f"{r['name']} dado {s}", line + inset - WT / 2 - 0.03, line + inset + WT / 2 + 0.03, lo + 0.02, hi - 0.02, 0, 0.9, mats['stone'], 1.5)
        if cutters:   # re-cut the dado through the same doorways
            dado = bpy.context.active_object; cs = []
            for dr in r['doors']:
                if dr['side'] != s: continue
                at = (dr['at'] - OX) * PXS if horiz else -(dr['at'] - OY) * PXS
                cx, cy = (at, line + inset) if horiz else (line + inset, at)
                cs.append(opening_cutter(cx, cy, horiz, min(dr['w'], (hi - lo) - 0.2), 2.7, False))
            cut_openings(dado, cs)
    # wall lanterns: one per long wall, kept clear of doorways
    for s, (lo, hi, line, horiz) in sides.items():
        if s in r['nowalls']: continue
        doors = [((dr['at'] - OX) * PXS if horiz else -(dr['at'] - OY) * PXS, dr['w']) for dr in r['doors'] if dr['side'] == s]
        for at in ((lo + hi) / 2, lo + (hi - lo) * 0.2, lo + (hi - lo) * 0.8):
            if any(abs(at - da) < dw / 2 + 0.7 for da, dw in doors): continue
            off = -0.35 if s in 'NE' else 0.35
            loc = (at, line + off, 2.1) if horiz else (line + off, at, 2.1)
            model('wooden_lantern_01', (loc[0], loc[1], 1.85), fit=(None, None, 0.45)); warm_light(loc, 120, 0.12)
            break
    return (x0, x1, y0, y1, hgt)

# ---------------------------------------------------------------- models
_lib = {}
def model(name, loc, rot_z=0.0, fit=None, scale=None):
    """Imports a Poly Haven / Khronos glb once, then links a scaled copy at loc (Blender coords)."""
    path = next((p for p in (A('assets', 'models', name + '.glb'), A('assets', 'khronos', name + '.glb')) if os.path.exists(p)), None)
    if not path: print('missing model', name); return None
    if name not in _lib:
        before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=path)
        objs = [o for o in bpy.data.objects if o not in before]; root = bpy.data.objects.new(name + '_src', None); bpy.context.scene.collection.objects.link(root)
        for o in objs:
            if o.type == 'LIGHT': bpy.data.objects.remove(o, do_unlink=True); continue
            if o.parent is None: o.parent = root
        lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
        bpy.context.view_layer.update()
        for o in root.children_recursive:
            if o.type == 'MESH':
                for v in o.bound_box:
                    w = o.matrix_world @ Vector(v); lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
        coll = bpy.data.collections.new(name); 
        for o in [root] + list(root.children_recursive):
            for uc in list(o.users_collection): uc.objects.unlink(o)
            coll.objects.link(o)
        root.location = (-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z)
        _lib[name] = (coll, hi - lo)
    coll, size = _lib[name]
    inst = bpy.data.objects.new(name, None); inst.instance_type = 'COLLECTION'; inst.instance_collection = coll
    bpy.context.scene.collection.objects.link(inst)
    s = scale or 1.0
    if fit: s = min(fit[i] / size[i] for i in range(3) if fit[i])
    inst.scale = (s, s, s); inst.location = loc; inst.rotation_euler = (0, 0, rot_z); return inst

def warm_light(loc, power=60, radius=0.15, colour=(1.0, 0.72, 0.42)):
    l = bpy.data.lights.new('lamp', 'POINT'); l.energy = power; l.color = colour; l.shadow_soft_size = radius
    o = bpy.data.objects.new('lamp', l); o.location = loc; bpy.context.scene.collection.objects.link(o); return o

def furnish(r, box):
    x0, x1, y0, y1, hgt = box; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; t = r['type']
    if t == 'entrance':
        model('Chandelier_01', (cx, cy, hgt - 1.6), fit=(1.6, None, None)); warm_light((cx, cy, hgt - 1.3), 900, 0.4)
        for dx, dy in ((-6.2, 9), (6.2, 9), (-6.2, -9.5)): model('potted_plant_01', (cx + dx, cy + dy, 0), fit=(None, None, 1.6))
        model('vintage_grandfather_clock_01', (x0 + 0.6, cy - 5.5, 0), rot_z=-math.pi / 2, fit=(None, None, 2.2))
        model('painted_wooden_bench', (cx - 3, y0 + 0.6, 0), rot_z=0, fit=(1.6, None, None))
    elif t == 'living2':
        model('scandinavian_masonry_heater', (cx, y0 + 0.9, 0), rot_z=0, fit=(None, None, 2.4)); warm_light((cx, y0 + 1.1, 0.5), 700, 0.3, (1, 0.5, 0.2))
        model('chinese_sofa', (cx, cy + 1.2, 0), rot_z=math.pi, fit=(2.6, None, None))
        model('sofa_02', (cx - 3.0, cy - 1.0, 0), rot_z=-math.pi / 2, fit=(2.2, None, None)); model('sofa_02', (cx + 3.0, cy - 1.0, 0), rot_z=math.pi / 2, fit=(2.2, None, None))
        model('coffee_table_round_01', (cx, cy - 1.0, 0), fit=(1.3, None, None)); model('ArmChair_01', (cx - 6, cy + 2.6, 0), rot_z=math.pi + 0.5, fit=(0.9, None, None))
        model('Rockingchair_01', (cx + 6, cy + 2.6, 0), rot_z=math.pi - 0.5, fit=(0.8, None, None))
        model('wooden_bookshelf_worn', (x1 - 0.5, cy - 2, 0), rot_z=math.pi / 2, fit=(None, None, 2.4)); model('wooden_bookshelf_worn', (x1 - 0.5, cy + 1, 0), rot_z=math.pi / 2, fit=(None, None, 2.4))
        for dx in (-5.5, 5.5): model('potted_plant_02', (cx + dx, y0 + 0.6, 0), fit=(None, None, 1.1))
        model('Chandelier_02', (cx, cy, hgt - 1.1), fit=(1.2, None, None)); warm_light((cx, cy, hgt - 0.9), 700, 0.3)
        model('brass_candleholders', (cx, cy - 1.0, 0.49), fit=(0.6, None, None))

def setup_world(sun_elev=10, sun_az=210):
    w = bpy.context.scene.world or bpy.data.worlds.new('World'); bpy.context.scene.world = w; w.use_nodes = True
    nt = w.node_tree; env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(A('assets', 'hdri', 'venice_sunset_2k.hdr'))
    nt.links.new(env.outputs[0], nt.nodes['Background'].inputs[0]); nt.nodes['Background'].inputs[1].default_value = 0.8
    sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 3.0; sun.color = (1.0, 0.78, 0.55); sun.angle = math.radians(1.5)
    so = bpy.data.objects.new('sun', sun); bpy.context.scene.collection.objects.link(so)
    so.rotation_euler = (math.radians(90 - sun_elev), 0, math.radians(sun_az))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--rooms', default='entrance,living2'); ap.add_argument('--render', default='')
    ap.add_argument('--samples', type=int, default=64); ap.add_argument('--res', default='1280x720'); ap.add_argument('--cam', default='')
    ap.add_argument('--blend', default='')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mats = dict(wall=pbr('plastered_stone_wall'), stone=pbr('rustic_stone_wall', 1.5), floor_wood=pbr('oak_wood_planks', 2.0), floor_stone=pbr('brown_floor_tiles'),
                floor_dark=pbr('cobblestone_floor_01'), ceiling=pbr('dark_wooden_planks'), beam=pbr('dark_wooden_planks', 1.2, (0.6, 0.5, 0.42)))
    want = set(args.rooms.split(','))
    for r in read_plan():
        if 'all' in want or r['type'] in want:
            furnish(r, build_room(r, mats))
    setup_world()
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = args.samples; sc.cycles.use_denoising = True
    sc.view_settings.exposure = 0.6; sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
    w, h = map(int, args.res.split('x')); sc.render.resolution_x, sc.render.resolution_y = w, h
    cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera')); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 20
    cx, cy, cz, rx, rz = map(float, (args.cam or '-6,-8,1.65,88,-62').split(','))
    cam.location = (cx, cy, cz); cam.rotation_euler = (math.radians(rx), 0, math.radians(rz))
    if args.blend: bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.blend))
    if args.render: sc.render.filepath = os.path.abspath(args.render); bpy.ops.render.render(write_still=True)

if __name__ == '__main__':
    main()
