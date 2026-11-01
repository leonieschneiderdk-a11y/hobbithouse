"""Builds the whole hobbit estate in Blender, with no manual work.

It reads the floor plan from index.html (the same data the web game uses), then:
  * builds every room and hallway: floors, ceilings, beams, walls with stone dados,
    doorways cut wherever either neighbouring room has a door, arched windows on outside walls;
  * furnishes each room with Poly Haven / Khronos scanned models, keeping doorways clear;
  * builds the thatched roofs, ground, lake, trees and rocks outside;
  * lights it all (sunset sky image, sun, room lights, lanterns, window glow) and renders with Cycles.

Run with Blender as a Python module (pip install bpy==4.2.0 on Python 3.11):
    python blender/build_scene.py --blend house.blend
    python blender/build_scene.py --shots all --samples 64 --res 1920x1080
"""
import argparse, math, os, re, sys
import bpy, bmesh
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = lambda *p: os.path.join(ROOT, *p)
PXS, OX, OY = 0.12, 845, 895          # 1 plan pixel = 0.12 m, origin at the entrance hall (same as the web game)
WT, H = 0.24, 3.4                     # wall thickness, room height

bx = lambda px: (px - OX) * PXS        # plan x -> Blender x
by = lambda py: -(py - OY) * PXS       # plan y (down = south) -> Blender y (north is +y)

# ---------------------------------------------------------------- floor plan, read straight from the game
def read_plan():
    src = open(A('index.html'), encoding='utf8').read()
    spaces = []
    for m in re.finditer(r"room\(\{name:(['\"])(.*?)\1,type:'(\w+)'(.*?)px:\[(\d+),(\d+),(\d+),(\d+)\](.*?)\}\);", src):
        name, typ, pre, rest = m.group(2), m.group(3), m.group(4), m.group(9)
        a, b, c, d = map(int, m.group(5, 6, 7, 8))
        floor = re.search(r"floor:'(\w+)'", pre + rest).group(1)
        kid = re.search(r"kid:(\d+)", pre + rest)
        doors = [dict(side=s, at=float(at), w=float(w) if w else 1.5, flat=bool(f), outside=bool(o))
                 for s, at, w, f, o in re.findall(r"\{side:'(\w)',at:([\d.]+)(?:,w:([\d.]+))?(,flat:true)?(?:,s:[\d.]+)?(,outside:true)?\}", rest)]
        nw = re.search(r"noWalls:\[([^\]]*)\]", rest)
        spaces.append(dict(name=name, type=typ, floor=floor, px=(a, b, c, d), doors=doors, kid=int(kid.group(1)) if kid else 0,
                           nowalls=re.findall(r"'(\w)'", nw.group(1)) if nw else [], inner='inner:true' in rest, h=H))
    have = {sp['name'] for sp in spaces}
    kids = [((1158, 793, 1206, 881), 'S', 0), ((1207, 793, 1256, 881), 'S', 1), ((1257, 793, 1306, 881), 'S', 2), ((1307, 793, 1356, 881), 'S', 3),
            ((1171, 914, 1219, 1002), 'N', 5), ((1221, 914, 1269, 1002), 'N', 6), ((1271, 914, 1319, 1002), 'N', 7), ((1354, 914, 1402, 1002), 'N', 8), ((1404, 914, 1452, 1002), 'N', 9)]
    for px, side, k in kids:                        # the kids' rooms are generated in a loop in the game code
        nm = f"Kids' Room {k + 1}"
        if nm in have: continue
        spaces.append(dict(name=nm, type='kid', floor='wood', px=px, kid=k, nowalls=[], inner=False, h=H,
                           doors=[dict(side=side, at=(px[0] + px[2]) / 2, w=1.5, flat=False, outside=False)]))
    for nm, px in (('West Hallway', (520, 900, 768, 928)), ("Kids' Hallway", (1077, 883, 1492, 912))):
        spaces.append(dict(name=nm, type='hall', floor='stone', px=px, doors=[], nowalls=list('NSWE'), inner=False, h=H, kid=0))
    spaces.append(dict(name='Main Entrance', type='entrance', floor='stone', px=(768, 798, 915, 987), h=5.0, inner=False, kid=0, nowalls=[],
                       doors=[dict(side='W', at=874, w=12.6, flat=True, outside=False), dict(side='W', at=962, w=1.5, flat=False, outside=False),
                              dict(side='E', at=894, w=12.4, flat=True, outside=False), dict(side='N', at=842, w=3.0, flat=False, outside=True),
                              dict(side='S', at=805, w=2.4, flat=False, outside=True)]))
    for s in spaces:
        a, b, c, d = s['px']; s['x0'], s['x1'], s['y0'], s['y1'] = bx(a), bx(c), by(d), by(b)
    return spaces

def side_line(s, side):
    """(lo, hi, line, horizontal, outward_sign) for one side of a space, in Blender coordinates."""
    return {'N': (s['x0'], s['x1'], s['y1'], True, 1), 'S': (s['x0'], s['x1'], s['y0'], True, -1),
            'W': (s['y0'], s['y1'], s['x0'], False, -1), 'E': (s['y0'], s['y1'], s['x1'], False, 1)}[side]

def all_doors(spaces):
    """Every door as (horizontal, line, centre, width, flat) in Blender coordinates, so a shared wall is cut from both sides."""
    out = []
    for s in spaces:
        for d in s['doors']:
            lo, hi, line, horiz, _ = side_line(s, d['side'])
            at = bx(d['at']) if horiz else by(d['at'])
            out.append((horiz, line, at, d['w'], d['flat']))
    return out

def point_inside(spaces, x, y):
    return any(s['x0'] - 0.01 < x < s['x1'] + 0.01 and s['y0'] - 0.01 < y < s['y1'] + 0.01 for s in spaces)

# ---------------------------------------------------------------- materials (Poly Haven scans)
_mats = {}
def pbr(name, tint=(1, 1, 1), rough_mul=1.0):
    key = (name, tint)
    if key in _mats: return _mats[key]
    m = bpy.data.materials.new(f'{name}{"" if tint == (1, 1, 1) else "_tint"}'); m.use_nodes = True
    nt = m.node_tree; bsdf = nt.nodes['Principled BSDF']
    def img(kind, colour):
        p = A('assets', 'materials', f'{name}_{kind}.jpg')
        if not os.path.exists(p): return None
        n = nt.nodes.new('ShaderNodeTexImage'); n.image = bpy.data.images.load(p, check_existing=True)
        n.image.colorspace_settings.name = 'sRGB' if colour else 'Non-Color'; return n
    d, r, nm = img('diff', True), img('rough', False), img('nor', False)
    if d:
        mix = nt.nodes.new('ShaderNodeMixRGB'); mix.blend_type = 'MULTIPLY'; mix.inputs[0].default_value = 1
        nt.links.new(d.outputs[0], mix.inputs[1]); mix.inputs[2].default_value = (*tint, 1); nt.links.new(mix.outputs[0], bsdf.inputs['Base Color'])
    if r:
        mr = nt.nodes.new('ShaderNodeMath'); mr.operation = 'MULTIPLY'; mr.inputs[1].default_value = rough_mul
        nt.links.new(r.outputs[0], mr.inputs[0]); nt.links.new(mr.outputs[0], bsdf.inputs['Roughness'])
    if nm:
        nmap = nt.nodes.new('ShaderNodeNormalMap'); nt.links.new(nm.outputs[0], nmap.inputs['Color']); nt.links.new(nmap.outputs[0], bsdf.inputs['Normal'])
    _mats[key] = m; return m

def flat(name, rgb, rough=0.5, metal=0.0, emit=None, strength=0.0, alpha=1.0, transmission=0.0):
    if name in _mats: return _mats[name]
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1); b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    if emit: b.inputs['Emission Color'].default_value = (*emit, 1); b.inputs['Emission Strength'].default_value = strength
    if transmission: b.inputs['Transmission Weight'].default_value = transmission
    _mats[name] = m; return m

def box_uv(obj, tile=2.5):
    """World-space box projection so the scans tile at real-world size on every face."""
    bm = bmesh.new(); bm.from_mesh(obj.data); uv = bm.loops.layers.uv.verify(); mw = obj.matrix_world
    for f in bm.faces:
        n = f.normal; ax = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            w = mw @ l.vert.co
            u, v = ((w.y, w.z) if ax == 0 else (w.x, w.z) if ax == 1 else (w.x, w.y))
            l[uv].uv = (u / tile, v / tile)
    bm.to_mesh(obj.data); bm.free()

COL = {}
def coll(name):
    if name not in COL:
        c = bpy.data.collections.new(name); bpy.context.scene.collection.children.link(c); COL[name] = c
    return COL[name]

def link(o, c):
    for uc in list(o.users_collection): uc.objects.unlink(o)
    coll(c).objects.link(o)

def cube(name, x0, x1, y0, y1, z0, z1, mat, tile=2.5, c='house'):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1); bmesh.ops.scale(bm, vec=(abs(x1 - x0), abs(y1 - y0), abs(z1 - z0)), verts=bm.verts)
    bmesh.ops.translate(bm, vec=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), verts=bm.verts); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); coll(c).objects.link(o); me.materials.append(mat); box_uv(o, tile); return o

def cutter_box(cx, cy, horiz, w, h, arched, z0=0.0):
    """Mesh that punches a doorway or window through a wall (box, plus a half-cylinder on top if arched)."""
    me = bpy.data.meshes.new('cut'); bm = bmesh.new(); depth = 1.2
    sx, sy = (w, depth) if horiz else (depth, w)
    bmesh.ops.create_cube(bm, size=1); bmesh.ops.scale(bm, vec=(sx, sy, h), verts=bm.verts); bmesh.ops.translate(bm, vec=(cx, cy, z0 + h / 2), verts=bm.verts)
    if arched:
        r = bmesh.ops.create_cone(bm, cap_ends=True, segments=28, radius1=w / 2, radius2=w / 2, depth=depth)
        rot = __import__('mathutils').Matrix.Rotation(math.pi / 2, 4, 'X' if horiz else 'Y')
        bmesh.ops.rotate(bm, verts=r['verts'], matrix=rot); bmesh.ops.translate(bm, vec=(cx, cy, z0 + h), verts=r['verts'])
    bm.to_mesh(me); bm.free(); o = bpy.data.objects.new('cut', me); bpy.context.scene.collection.objects.link(o); return o

def apply_cuts(obj, cutters):
    if not cutters: return
    for c in cutters:
        mod = obj.modifiers.new('cut', 'BOOLEAN'); mod.object = c; mod.operation = 'DIFFERENCE'; mod.solver = 'EXACT'; mod.use_self = True; mod.use_hole_tolerant = True
    bpy.context.view_layer.objects.active = obj
    for mod in list(obj.modifiers): bpy.ops.object.modifier_apply(modifier=mod.name)
    for c in cutters: bpy.data.objects.remove(c, do_unlink=True)
    box_uv(obj)

# ---------------------------------------------------------------- models
_lib = {}
def model(name, loc, rot_z=0.0, fit=None, scale=None, c='furniture'):
    """Imports a scanned .glb once, then places a scaled instance. fit=(x,y,z) target size in metres (None = ignore)."""
    path = next((p for p in (A('assets', 'models', name + '.glb'), A('assets', 'khronos', name + '.glb')) if os.path.exists(p)), None)
    if not path: print('missing model', name); return None
    if name not in _lib:
        before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=path)
        objs = [o for o in bpy.data.objects if o not in before]
        root = bpy.data.objects.new(name + '_src', None); bpy.context.scene.collection.objects.link(root)
        for o in objs:
            if o.type == 'LIGHT': bpy.data.objects.remove(o, do_unlink=True); continue
            if o.parent is None: o.parent = root
        bpy.context.view_layer.update(); lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
        for o in root.children_recursive:
            if o.type == 'MESH':
                for v in o.bound_box:
                    w = o.matrix_world @ Vector(v); lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
        lib = bpy.data.collections.new('lib_' + name)
        for o in [root] + list(root.children_recursive):
            for uc in list(o.users_collection): uc.objects.unlink(o)
            lib.objects.link(o)
        root.location = (-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z)
        _lib[name] = (lib, hi - lo)
    lib, size = _lib[name]
    inst = bpy.data.objects.new(name, None); inst.instance_type = 'COLLECTION'; inst.instance_collection = lib; coll(c).objects.link(inst)
    sx = sy = sz = scale or 1.0
    if fit:
        ks = [fit[i] / size[i] for i in range(3) if fit[i]]; sx = sy = sz = min(ks)
    inst.scale = (sx, sy, sz); inst.location = loc; inst.rotation_euler = (0, 0, rot_z)
    return inst

def model_size(name):
    if name not in _lib: model(name, (0, 0, -100)); bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True) if name in bpy.data.objects else None
    return _lib[name][1] if name in _lib else Vector((1, 1, 1))

def light(loc, power, radius=0.15, colour=(1.0, 0.72, 0.42), kind='POINT', c='lights'):
    l = bpy.data.lights.new('lamp', kind); l.energy = power; l.color = colour
    if kind == 'POINT': l.shadow_soft_size = radius
    o = bpy.data.objects.new('lamp', l); o.location = loc; coll(c).objects.link(o); return o

# ---------------------------------------------------------------- building the house
def build_space(s, spaces, doors, M):
    x0, x1, y0, y1, hgt = s['x0'], s['x1'], s['y0'], s['y1'], s['h']; lift = 0.004 if s['inner'] else 0.0
    floor = {'wood': M['floor_wood'], 'stone': M['floor_stone'], 'dark': M['floor_dark']}[s['floor']]
    cube(s['name'] + ' floor', x0, x1, y0, y1, -0.12 + lift, lift, floor, 2.0)
    ceil = cube(s['name'] + ' ceiling', x0, x1, y0, y1, hgt - lift, hgt + 0.12, M['ceiling'])
    if s['type'] == 'entrance':      # round skylight over the rug, as on the plan
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        c = cutter_box(cx, cy, True, 0.01, 0.01, False); bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=2.4, radius2=2.4, depth=1)
        bmesh.ops.translate(bm, vec=(cx, cy, hgt), verts=bm.verts); bm.to_mesh(c.data); bm.free(); apply_cuts(ceil, [c])
        sky = light((cx, cy, hgt + 0.05), 2600, kind='AREA', colour=(0.9, 0.92, 1.0)); sky.data.shape = 'DISK'; sky.data.size = 4.6
    long_x = (x1 - x0) >= (y1 - y0); n = max(1, int(((x1 - x0) if long_x else (y1 - y0)) / 1.8))
    for i in range(1, n):            # ceiling beams across the short span
        if long_x: x = x0 + i * (x1 - x0) / n; cube('beam', x - 0.11, x + 0.11, y0 + 0.15, y1 - 0.15, hgt - 0.28, hgt - lift, M['beam'], 1.2)
        else:      y = y0 + i * (y1 - y0) / n; cube('beam', x0 + 0.15, x1 - 0.15, y - 0.11, y + 0.11, hgt - 0.28, hgt - lift, M['beam'], 1.2)
    s['windows'] = {}
    for side in 'NSWE':
        if side in s['nowalls']: continue
        lo, hi, line, horiz, out = side_line(s, side); mid = line - out * WT / 2
        exterior = not s['inner'] and not point_inside(spaces, *(((lo + hi) / 2, line + out * 0.7) if horiz else (line + out * 0.7, (lo + hi) / 2)))
        mat = M['wall_ext'] if exterior else M['wall']
        w = cube(f"{s['name']} wall {side}", *((lo, hi, mid - WT / 2, mid + WT / 2) if horiz else (mid - WT / 2, mid + WT / 2, lo, hi)), 0, hgt, mat)
        dado = cube(f"{s['name']} dado {side}", *((lo + 0.02, hi - 0.02, mid - WT / 2 - 0.03, mid + WT / 2 + 0.03) if horiz else (mid - WT / 2 - 0.03, mid + WT / 2 + 0.03, lo + 0.02, hi - 0.02)), 0, 0.9, M['stone'], 1.5)
        wc, dc, gaps = [], [], []
        for (h2, l2, at, dw, fl) in doors:                     # any door on this wall line, from this room or its neighbour
            if h2 != horiz or abs(l2 - line) > 0.6 or not (lo - 0.1 < at < hi + 0.1): continue
            dw = min(dw, (hi - lo) - 0.2); cx, cy = (at, mid) if horiz else (mid, at); hh = 2.7 if fl else 1.95
            wc.append(cutter_box(cx, cy, horiz, dw, hh, not fl)); dc.append(cutter_box(cx, cy, horiz, dw, 2.7, False)); gaps.append((at - dw / 2 - 0.6, at + dw / 2 + 0.6))
        if exterior and s['type'] not in ('wine', 'winefood', 'pantry', 'hall'):   # arched windows on outside walls
            L = hi - lo; k = max(1, int(L / 3.4))
            for i in range(k):
                at = lo + L * (i + 0.5) / k
                if any(a < at < b for a, b in gaps): continue
                cx, cy = (at, mid) if horiz else (mid, at)
                wc.append(cutter_box(cx, cy, horiz, 1.2, 1.3, True, z0=0.95)); s['windows'].setdefault(side, []).append(at)
                glass = cube('glass', *((at - 0.6, at + 0.6, mid - 0.01, mid + 0.01) if horiz else (mid - 0.01, mid + 0.01, at - 0.6, at + 0.6)), 0.95, 2.85, M['glass'], c='glass')
                pn = light(((at, line + out * 0.4, 1.8) if horiz else (line + out * 0.4, at, 1.8)), 500, kind='AREA', colour=(1.0, 0.85, 0.66))
                pn.data.size = 1.2; pn.data.shape = 'RECTANGLE'; pn.data.size_y = 1.9
                pn.rotation_euler = ((math.radians(-90 * out), 0, 0) if horiz else (0, math.radians(90 * out), 0))
                gaps.append((at - 1.2, at + 1.2))
        apply_cuts(w, wc); apply_cuts(dado, dc); s.setdefault('gaps', {})[side] = gaps

def dome(px, Hd, axis, M, ov=1.7, y0=3.45):
    a, b, c, d = px; cx, cy = (bx(a) + bx(c)) / 2, (by(b) + by(d)) / 2; hx, hy = (bx(c) - bx(a)) / 2 + ov, (by(b) - by(d)) / 2 + ov
    NU, NV = 56, 40; me = bpy.data.meshes.new('thatch'); bm = bmesh.new(); vs = []
    for j in range(NV + 1):
        row = []
        for i in range(NU + 1):
            u, v = (i / NU * 2 - 1) * 1.06, (j / NV * 2 - 1) * 1.06; au, av = min(abs(u), 0.999), min(abs(v), 0.999)
            p, q = (au, av) if axis == 'x' else (av, au)
            z = y0 + Hd * (1 - q ** 2.2) ** 0.55 * (1 - p ** 6) ** 0.4
            ex = max(abs(u) - 1, abs(v) - 1, 0); z -= math.sqrt(ex / 0.06) * 0.55
            row.append(bm.verts.new((cx + u * hx, cy + v * hy, z)))
        vs.append(row)
    for j in range(NV):
        for i in range(NU): bm.faces.new((vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]))
    bm.to_mesh(me); bm.free(); o = bpy.data.objects.new('thatch', me); coll('roof').objects.link(o); me.materials.append(M['thatch'])
    for f in me.polygons: f.use_smooth = True
    sol = o.modifiers.new('thickness', 'SOLIDIFY'); sol.thickness = 0.45; sol.offset = 1.0; box_uv(o, 2.2)
    return o

# ---------------------------------------------------------------- furnishing
def free_spots(s, side, width, margin=0.35):
    """Centres along a wall where an object of this width fits without touching a doorway or window."""
    lo, hi, line, horiz, out = side_line(s, side); gaps = s.get('gaps', {}).get(side, [])
    spots, t = [], lo + WT + margin + width / 2
    while t + width / 2 < hi - WT - margin:
        if not any(t + width / 2 > a and t - width / 2 < b for a, b in gaps): spots.append(t)
        t += 0.25
    return spots

FACE = {'N': 0.0, 'S': math.pi, 'W': math.pi / 2, 'E': -math.pi / 2}   # rotation so a model's front faces into the room
def against(s, side, at, depth):
    lo, hi, line, horiz, out = side_line(s, side); off = line - out * (WT + depth / 2 + 0.05)
    return ((at, off, 0) if horiz else (off, at, 0)), FACE[side]

BOOK_LEVELS = (0.06, 0.255, 0.45, 0.645, 0.84)     # shelf heights as a fraction of the bookshelf's height
def stock_books(shelf, side):
    sz = _lib['wooden_bookshelf_worn'][1] * shelf.scale[0]; hgt, wid = sz.z, sz.x
    for i, f in enumerate(BOOK_LEVELS):
        for k in (-1, 1):
            if (i + k) % 3 == 0: continue
            off = Vector((k * wid * 0.24, 0.02, hgt * f)); off.rotate(shelf.rotation_euler)
            model('book_encyclopedia_set_01', shelf.location + off, shelf.rotation_euler.z + (math.pi if (i + k) % 2 else 0), fit=(wid * 0.42, None, hgt * 0.16), c='decor')

def place_on_wall(s, side, name, w, d, h=None, prefer=0.5, gap_after=0.4, used=None):
    spots = free_spots(s, side, w)
    if used: spots = [t for t in spots if all(abs(t - u) > (w + uw) / 2 + 0.2 for u, uw in used)]
    if not spots: return None
    lo, hi, *_ = side_line(s, side); target = lo + (hi - lo) * prefer; at = min(spots, key=lambda t: abs(t - target))
    loc, rot = against(s, side, at, d); inst = model(name, loc, rot, fit=(w, None, h))
    if name == 'wooden_bookshelf_worn' and inst: stock_books(inst, side)
    if used is not None: used.append((at, w))
    return at

def walls_by_length(s):
    sides = [sd for sd in 'NSWE' if sd not in s['nowalls']]
    return sorted(sides, key=lambda sd: -(side_line(s, sd)[1] - side_line(s, sd)[0]) + 2.0 * sum(b - a for a, b in s.get('gaps', {}).get(sd, [])) / max(1, (side_line(s, sd)[1] - side_line(s, sd)[0])))

def hang(s, side, at, name, w, z=1.75):
    lo, hi, line, horiz, out = side_line(s, side); off = line - out * (WT + 0.03)
    model(name, ((at, off, z) if horiz else (off, at, z)), FACE[side], fit=(w, None, None), c='decor')

def fill_room(s, used):
    t = s['type']; x0, x1, y0, y1 = s['x0'], s['x1'], s['y0'], s['y1']; area = (x1 - x0) * (y1 - y0)
    if t in ('hall', 'pantry', 'wine', 'winefood', 'closet', 'linen', 'laundry', 'spa') or area < 8: return
    frames = ['hanging_picture_frame_01', 'hanging_picture_frame_02', 'fancy_picture_frame_01']
    pieces = (['GothicCabinet_01', 1.6, 0.9], ['wooden_bookshelf_worn', 1.4, 0.6], ['painted_wooden_bench', 1.3, 0.5], ['vintage_cabinet_01', 1.8, 0.6], ['potted_plant_01', 0.6, 0.6]) if area > 25 else (['painted_wooden_nightstand', 0.5, 0.5], ['potted_plant_02', 0.6, 0.6], ['painted_wooden_shelves', 0.6, 0.45])
    k = 0
    for sd in [q for q in 'NSWE' if q not in s['nowalls']]:
        lo, hi, line, horiz, out = side_line(s, sd)
        # pictures every ~2.6 m of clear wall, above any furniture
        for at in free_spots(s, sd, 0.9)[::11]:
            hang(s, sd, at, frames[k % 3], 0.75 if area > 25 else 0.55, 1.85); k += 1
        # furniture in the gaps left along the wall
        for at in free_spots(s, sd, 1.9)[::9]:
            if any(abs(at - u) < (uw + 1.9) / 2 + 0.3 for u, uw in used[sd]): continue
            name, w, d = pieces[k % len(pieces)]; k += 1
            loc, rot = against(s, sd, at, d); inst = model(name, loc, rot, fit=(w, None, 2.2 if 'shelf' in name or 'cabinet' in name else None)); used[sd].append((at, w))
            if name == 'wooden_bookshelf_worn' and inst: stock_books(inst, sd)
            if name in ('painted_wooden_nightstand', 'GothicCabinet_01'):
                top = 0.62 if 'night' in name else 0.92
                model(['brass_vase_01', 'antique_ceramic_vase_01', 'mantel_clock_01'][k % 3], (loc[0], loc[1], top), rot, fit=(None, None, 0.35))
    if area > 60:      # a second seating group in large rooms
        gx, gy = (x0 + (x1 - x0) * 0.25, (y0 + y1) / 2) if (x1 - x0) > (y1 - y0) else ((x0 + x1) / 2, y0 + (y1 - y0) * 0.25)
        cube('rug border', gx - 1.7, gx + 1.7, gy - 1.3, gy + 1.3, 0.001, 0.009, MATS['rug_border'], 0.45, c='furniture'); cube('rug', gx - 1.56, gx + 1.56, gy - 1.16, gy + 1.16, 0.002, 0.011, MATS['rug'], 0.45, c='furniture')
        model('ArmChair_01', (gx - 0.9, gy + 0.6, 0), math.pi + 0.5, fit=(0.85, None, None)); model('ArmChair_01', (gx + 0.9, gy + 0.6, 0), math.pi - 0.5, fit=(0.85, None, None))
        model('coffee_table_round_01', (gx, gy - 0.2, 0), fit=(0.9, None, None)); model('tea_set_01', (gx, gy - 0.2, 0.43), fit=(0.5, None, None))
        model('Rockingchair_01', (gx, gy - 1.3, 0), 0.0, fit=(0.75, None, None))

MATS = {}
def furnish(s, M):
    t = s['type']; x0, x1, y0, y1, hgt = s['x0'], s['x1'], s['y0'], s['y1'], s['h']; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    area = (x1 - x0) * (y1 - y0); sides = walls_by_length(s); used = {sd: [] for sd in 'NSWE'}
    main = sides[0] if sides else None; other = sides[1] if len(sides) > 1 else None
    rug = None
    def P(side, name, w, d, h=None, prefer=0.5):
        return place_on_wall(s, side, name, w, d, h, prefer, used=used[side]) if side else None
    # room light: chandelier in the middle of bigger rooms, lanterns on walls
    if t not in ('hall',) and area > 14:
        ch = 'Chandelier_01' if area > 60 else ('lantern_chandelier_01' if t in ('kitchen2', 'dining2', 'wine', 'winefood', 'pantry') else 'Chandelier_02')
        model(ch, (cx, cy, hgt - 1.25 if hgt < 4 else hgt - 1.7), fit=(1.1 if area > 40 else 0.8, None, None))
    light((cx, cy, hgt - 0.9), 120 + area * 9, 0.35)
    for sd in sides[:2]:
        spots = free_spots(s, sd, 0.6)
        if spots:
            lo, hi, line, horiz, out = side_line(s, sd); at = min(spots, key=lambda q: abs(q - (lo + hi) / 2)); o2 = line - out * (WT + 0.18)
            loc = (at, o2, 1.85) if horiz else (o2, at, 1.85); model('wooden_lantern_01', loc, FACE[sd], fit=(None, None, 0.42), c='lamps')
            light((loc[0], loc[1], 2.1), 90, 0.1)
    def floor_rug(w, d, at=None):
        rx, ry = at or (cx, cy)
        cube('rug border', rx - w / 2, rx + w / 2, ry - d / 2, ry + d / 2, 0.001, 0.009, M['rug_border'], 0.45, c='furniture')
        cube('rug', rx - w / 2 + 0.14, rx + w / 2 - 0.14, ry - d / 2 + 0.14, ry + d / 2 - 0.14, 0.002, 0.011, M['rug'], 0.45, c='furniture')
    if t not in ('hall', 'entrance', 'bath', 'kidsbath', 'masterbath', 'spa', 'pantry', 'wine', 'winefood', 'laundry', 'linen', 'kitchen2', 'workshop') and area > 9:
        floor_rug(min(4.2, (x1 - x0) * 0.6), min(3.2, (y1 - y0) * 0.6))
    def plants(n=2):
        for (px, py) in [(x0 + 0.65, y0 + 0.65), (x1 - 0.65, y1 - 0.65), (x1 - 0.65, y0 + 0.65), (x0 + 0.65, y1 - 0.65)][:n]:
            if any(abs(px - a) < 1 or abs(py - b) < 1 for a, b in []): continue
            model('potted_plant_01' if (px + py) % 2 > 1 else 'potted_plant_02', (px, py, 0), fit=(None, None, 1.2))
    if t in ('bedroom2', 'guest', 'red', 'kid'):
        bw = 2.0 if t in ('bedroom2', 'red', 'guest') else 1.45
        at = P(main, 'GothicBed_01', bw, 2.6, prefer=0.5)
        if at is not None:
            for dsgn in (-1, 1):
                lo, hi, line, horiz, out = side_line(s, main); a2 = at + dsgn * (bw / 2 + 0.35)
                if lo + 0.5 < a2 < hi - 0.5:
                    loc, rot = against(s, main, a2, 0.42); model('ClassicNightstand_01', loc, rot, fit=(0.5, None, None))
                    light((loc[0], loc[1], 0.95), 25, 0.08)
        P(other, 'vintage_cabinet_01' if t == 'bedroom2' else 'painted_wooden_shelves', 1.6 if t == 'bedroom2' else 0.6, 0.6)
        if t == 'kid': P(other, 'treasure_chest', 0.9, 0.5, prefer=0.2)
        if t == 'bedroom2':
            P(sides[2] if len(sides) > 2 else None, 'scandinavian_masonry_heater', 1.2, 1.3); light((cx, cy - 1, 0.5), 120, 0.3, (1, 0.5, 0.2))
            model('ArmChair_01', (cx - 1.5, cy + 1.6, 0), math.pi + 0.4, fit=(0.9, None, None)); model('Ottoman_01', (cx - 0.5, cy + 1.6, 0), fit=(0.7, None, None))
        plants(1)
    elif t in ('living2', 'tv', 'childlounge', 'cat', 'reading', 'music', 'gaming', 'movie'):
        P(main, 'chinese_sofa' if t == 'living2' else 'sofa_02', 2.6 if area > 30 else 1.9, 1.0)
        if t == 'living2':
            P(other, 'scandinavian_masonry_heater', 1.3, 1.4); light((cx, cy, 0.6), 220, 0.4, (1, 0.5, 0.2))
            model('sofa_02', (cx - 2.6, cy, 0), math.pi / 2, fit=(2.2, None, None)); model('sofa_02', (cx + 2.6, cy, 0), -math.pi / 2, fit=(2.2, None, None))
            model('coffee_table_round_01', (cx, cy, 0), fit=(1.3, None, None)); model('brass_candleholders', (cx, cy, 0.48), fit=(0.6, None, None))
        else:
            model('coffee_table_round_01', (cx, cy, 0), fit=(1.0, None, None))
            model('ArmChair_01', (cx + 1.3, cy + 0.9, 0), math.pi * 0.75, fit=(0.85, None, None))
        if t in ('reading', 'tv', 'childlounge', 'living2'): P(other, 'wooden_bookshelf_worn', 1.4, 0.6, 2.2)
        for sd in sides[2:4]: P(sd, 'GothicCabinet_01' if area > 30 else 'painted_wooden_nightstand', 1.2 if area > 30 else 0.5, 0.6)
        model('WoodenTable_02', (cx + 1.6, cy - 0.9, 0), fit=(0.45, None, None)); model('vintage_oil_lamp', (cx + 1.6, cy - 0.9, 0.42), fit=(None, None, 0.4)); light((cx + 1.6, cy - 0.9, 0.75), 30, 0.06)
        if t == 'music': model('Rockingchair_01', (cx - 1.2, cy - 0.8, 0), 0.6, fit=(0.8, None, None))
        if t == 'cat': model('wicker_basket_01', (cx + 0.6, cy - 0.8, 0), fit=(0.5, None, None))
        plants(2)
    elif t in ('library', 'office2'):
        for sd in sides[:3]:
            for _ in range(4):
                if P(sd, 'wooden_bookshelf_worn', 1.4, 0.6, 2.2) is None: break
        model('WoodenTable_01' if t == 'office2' else 'dining_table', (cx, cy, 0), 0, fit=(1.8 if t == 'office2' else 2.0, None, 0.8))
        model('dining_chair_02', (cx, cy - 0.85, 0), math.pi, fit=(None, None, 0.95)); model('ArmChair_01', (cx + 1.4, cy + 1.2, 0), math.pi * 0.8, fit=(0.85, None, None))
        model('vintage_oil_lamp', (cx - 0.5, cy, 0.8), fit=(None, None, 0.45))
    elif t == 'dining2':
        model('dining_table', (cx, cy, 0), math.pi / 2, fit=(None, 3.0, 0.8))
        for i in range(3):
            for sg in (-1, 1): model('dining_chair_02', (cx + sg * 0.85, cy - 1.0 + i, 0), -sg * math.pi / 2, fit=(None, None, 0.95))
        model('brass_candleholders', (cx, cy, 0.78), math.pi / 2, fit=(None, 0.8, None)); P(main, 'vintage_cabinet_01', 1.8, 0.6); plants(2)
    elif t == 'kitchen2':
        for sd in sides[:2]:
            for sp in free_spots(s, sd, 1.0)[::5]:
                loc, rot = against(s, sd, sp, 0.65); cube('counter', loc[0] - 0.5, loc[0] + 0.5, loc[1] - 0.32, loc[1] + 0.32, 0, 0.88, M['wood_dark'], c='furniture')
                cube('worktop', loc[0] - 0.52, loc[0] + 0.52, loc[1] - 0.34, loc[1] + 0.34, 0.88, 0.93, M['marble'], c='furniture')
        cube('island', cx - 1.8, cx + 1.8, cy - 0.65, cy + 0.65, 0, 0.9, M['wood_dark'], c='furniture'); cube('island top', cx - 1.9, cx + 1.9, cy - 0.72, cy + 0.72, 0.9, 0.96, M['marble'], c='furniture')
        for i in range(4): model('Barrel_01' if i % 2 else 'wine_barrel_01', (x0 + 0.6 + i * 0.8, y1 - 0.6, 0), fit=(0.6, None, None))
        model('brass_candleholders', (cx, cy, 0.96), fit=(0.7, None, None))
    elif t in ('pantry', 'winefood', 'wine'):
        for sd in sides[:2]:
            for _ in range(3):
                if P(sd, 'painted_wooden_shelves' if t == 'pantry' else 'wooden_bookshelf_worn', 0.9, 0.5, 2.0) is None: break
        model('wooden_barrels_01' if t == 'wine' else 'wine_barrel_01', (cx, cy, 0), 0, fit=(min(2.6, x1 - x0 - 1.2), None, None))
    elif t in ('bath', 'kidsbath', 'masterbath'):
        L = 1.7 if t == 'masterbath' else 1.5
        loc, rot = against(s, main, (side_line(s, main)[0] + side_line(s, main)[1]) / 2, 0.8)
        tub = cube('bathtub', loc[0] - (L / 2 if rot in (0.0, math.pi) else 0.4), loc[0] + (L / 2 if rot in (0.0, math.pi) else 0.4), loc[1] - (0.4 if rot in (0.0, math.pi) else L / 2), loc[1] + (0.4 if rot in (0.0, math.pi) else L / 2), 0, 0.6, M['copper' if t == 'masterbath' else 'porcelain'], c='furniture')
        bev = tub.modifiers.new('bevel', 'BEVEL'); bev.width = 0.12; bev.segments = 6
        P(other, 'ornate_mirror_01', 0.5, 0.05); plants(1); light((cx, cy, 2.2), 120, 0.2)
    elif t in ('baby',):
        P(main, 'painted_wooden_shelves', 0.6, 0.5); model('Rockingchair_01', (cx, cy, 0), 0.5, fit=(0.8, None, None)); plants(1)
    elif t in ('closet', 'linen', 'laundry'):
        for sd in sides[:3]:
            for _ in range(4):
                if P(sd, 'vintage_cabinet_01' if t == 'closet' else 'painted_wooden_shelves', 1.6 if t == 'closet' else 0.6, 0.6) is None: break
        if t == 'closet': model('Ottoman_01', (cx, cy, 0), fit=(0.9, None, None))
    elif t in ('workshop', 'painting'):
        P(main, 'WoodenTable_01', 1.8, 0.7); P(other, 'painted_wooden_shelves', 0.6, 0.5); model('wooden_crate_01' if False else 'treasure_chest', (cx + 1, cy, 0), fit=(0.8, None, None)); plants(1)
    elif t == 'spa':
        cube('pool', cx - 2.2, cx + 2.2, cy - 1.4, cy + 1.4, -0.12, 0.02, M['pool_water'], c='furniture')
        for sx in (-2.35, 2.35): cube('pool edge', cx + sx - 0.15, cx + sx + 0.15, cy - 1.55, cy + 1.55, 0, 0.12, M['stone'], 1.5, c='furniture')
        for sy in (-1.55, 1.55): cube('pool edge', cx - 2.5, cx + 2.5, cy + sy - 0.15, cy + sy + 0.15, 0, 0.12, M['stone'], 1.5, c='furniture')
        light((cx, cy, 0.3), 150, 0.5, (0.5, 0.9, 1.0)); plants(3)
    elif t == 'entrance':
        model('Chandelier_01', (cx, cy, hgt - 1.7), fit=(1.6, None, None)); light((cx, cy, hgt - 1.4), 900, 0.4)
        for dx, dy in ((-7.2, 9.6), (7.2, 9.6), (-7.2, -9.8), (7.2, -9.8)): model('potted_plant_01', (cx + dx, cy + dy, 0), fit=(None, None, 1.6))
        model('vintage_grandfather_clock_01', (x0 + 0.55, cy - 6.0, 0), math.pi / 2, fit=(None, None, 2.2))
        model('painted_wooden_bench', (cx - 4.0, y0 + 0.55, 0), math.pi, fit=(1.6, None, None))
        for rad, z, mat in ((3.6, 0.006, 'rug_dark'), (3.35, 0.008, 'rug_border'), (3.1, 0.010, 'rug'), (1.6, 0.012, 'rug_border'), (1.35, 0.014, 'rug')):
            bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=rad, depth=0.004, location=(cx, cy, z)); r = bpy.context.active_object; link(r, 'furniture'); r.data.materials.append(M[mat]); box_uv(r, 0.45)
    elif t == 'hall':
        L = x1 - x0
        for i in range(int(L / 6)):
            x = x0 + 3 + i * 6; model('lantern_chandelier_01', (x, cy, hgt - 1.0), fit=(0.55, None, None), c='lamps'); light((x, cy, hgt - 0.9), 140, 0.15)
        r = cube('runner', x0 + 0.6, x1 - 0.6, cy - 0.7, cy + 0.7, 0.002, 0.012, M['rug'], 0.45, c='furniture')
    fill_room(s, used)

# ---------------------------------------------------------------- outside
def build_outside(spaces, M):
    g = cube('ground', -260, 260, -220, 300, -0.6, -0.12, M['grass'], 3.0, c='ground')
    lcx, lcy, lrx, lry = bx(675), by(220), 51.5, 20.6
    bpy.ops.mesh.primitive_circle_add(vertices=128, radius=1, fill_type='NGON', location=(lcx, lcy, -0.08)); lake = bpy.context.active_object
    lake.scale = (lrx, lry, 1); link(lake, 'ground'); lake.data.materials.append(M['water'])
    # paths of cobbles from the front door and garden doors
    cube('front walk', bx(790), bx(820), by(1085), by(990), -0.12, -0.09, M['cobble'], 1.5, c='ground')
    cube('garden walk', bx(828), bx(856), by(700), by(800), -0.12, -0.09, M['cobble'], 1.5, c='ground')
    cube('driveway', bx(-40), bx(805), by(1100), by(1070), -0.12, -0.09, M['gravel'], 2.0, c='ground')
    import random; rnd = random.Random(7)
    def clear(x, y, m=3.0):
        if any(s['x0'] - m < x < s['x1'] + m and s['y0'] - m < y < s['y1'] + m for s in spaces): return False
        if ((x - lcx) / (lrx + 3)) ** 2 + ((y - lcy) / (lry + 3)) ** 2 < 1: return False
        return True
    n = 0
    while n < 160:
        a = rnd.uniform(0, 6.283); r = rnd.uniform(45, 140); x, y = bx(845) + 15 + math.cos(a) * r * 1.2, by(700) + math.sin(a) * r
        if not clear(x, y, 6): continue
        model('island_tree_01', (x, y, -0.12), rnd.uniform(0, 6.283), scale=rnd.uniform(0.9, 1.5), c='nature'); n += 1
    for i in range(40):
        a = rnd.uniform(0, 6.283); k = rnd.uniform(1.04, 1.15); x, y = lcx + math.cos(a) * lrx * k, lcy + math.sin(a) * lry * k
        if clear(x, y, 2): model('boulder_01', (x, y, -0.3), rnd.uniform(0, 6.283), scale=rnd.uniform(0.6, 1.6), c='nature')
    for i in range(120):
        x, y = rnd.uniform(bx(300), bx(1700)), rnd.uniform(by(1080), by(300))
        if clear(x, y, 1.5): model(rnd.choice(['shrub_02', 'shrub_04', 'shrub_01']), (x, y, -0.12), rnd.uniform(0, 6.283), scale=rnd.uniform(0.7, 1.3), c='nature')
    model('stone_fire_pit', (bx(777), by(477), -0.12), fit=(2.4, None, None), c='nature'); light((bx(777), by(477), 0.4), 400, 0.4, (1, 0.45, 0.15))
    for px, py in ((790, 1060), (825, 760), (825, 700), (640, 1070), (480, 1070)):
        model('Lantern', (bx(px), by(py), -0.12), 0, fit=(None, None, 2.9), c='nature'); light((bx(px), by(py), 2.4), 150, 0.15)

def setup_world(sun_elev=9, sun_az=232):
    w = bpy.data.worlds.new('World'); bpy.context.scene.world = w; w.use_nodes = True
    nt = w.node_tree; env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(A('assets', 'hdri', 'venice_sunset_2k.hdr'))
    mapping = nt.nodes.new('ShaderNodeMapping'); tc = nt.nodes.new('ShaderNodeTexCoord'); nt.links.new(tc.outputs['Generated'], mapping.inputs[0]); nt.links.new(mapping.outputs[0], env.inputs[0])
    mapping.inputs['Rotation'].default_value[2] = math.radians(sun_az - 90)
    nt.links.new(env.outputs[0], nt.nodes['Background'].inputs[0]); nt.nodes['Background'].inputs[1].default_value = 1.0
    sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 4.0; sun.color = (1.0, 0.76, 0.52); sun.angle = math.radians(1.2)
    so = bpy.data.objects.new('sun', sun); coll('lights').objects.link(so); so.rotation_euler = (math.radians(90 - sun_elev), 0, math.radians(sun_az))

SHOTS = {   # name: (x, y, z, tilt_deg, heading_deg, lens_mm)   heading 0 = looking north (+y), -90 = east
    'entrance': (-6.5, 0.4, 1.65, 87, -90, 18),
    'living': (12.0, -4.0, 1.6, 86, -55, 18),
    'bedroom': (bx(500), by(960), 1.6, 86, 140, 18),
    'dining_kitchen': (bx(700), by(905), 1.6, 87, 20, 18),
    'kids_hall': (bx(1095), by(897), 1.65, 88, -90, 22),
    'library': (bx(930), by(1010), 1.6, 86, -40, 18),
    'garden_view': (bx(842), by(600), 3.5, 84, 180, 24),
    'aerial': (bx(842), by(560), 32, 58, 180, 28),
    'front': (bx(805), by(1120), 2.2, 86, 0, 22),
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--blend', default=''); ap.add_argument('--shots', default=''); ap.add_argument('--out', default=A('docs', 'renders'))
    ap.add_argument('--samples', type=int, default=48); ap.add_argument('--res', default='1280x720'); ap.add_argument('--only', default='')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    M = dict(wall=pbr('clay_plaster'), wall_ext=pbr('clay_plaster', (0.95, 0.9, 0.82)), stone=pbr('rustic_stone_wall'), floor_wood=pbr('oak_wood_planks', (1, 1, 1), 1.5), floor_stone=pbr('brown_floor_tiles', (1, 1, 1), 1.3),
             floor_dark=pbr('cobblestone_floor_01'), ceiling=pbr('dark_wooden_planks'), beam=pbr('dark_wooden_planks', (0.55, 0.45, 0.38)), wood_dark=pbr('dark_wooden_planks', (0.7, 0.6, 0.5)),
             thatch=pbr('thatch_roof_angled', (1.0, 0.82, 0.6)), grass=pbr('leafy_grass', (0.62, 0.8, 0.42)), cobble=pbr('cobblestone_floor_01'), gravel=pbr('gravel_floor'),
             marble=flat('marble', (0.82, 0.79, 0.74), 0.25), porcelain=flat('porcelain', (0.93, 0.92, 0.9), 0.15), copper=flat('copper', (0.75, 0.38, 0.22), 0.3, 1.0),
             glass=flat('glass', (0.9, 0.95, 0.95), 0.02, transmission=1.0), water=flat('water', (0.08, 0.16, 0.18), 0.04, transmission=0.6),
             pool_water=flat('pool water', (0.2, 0.55, 0.6), 0.03, emit=(0.1, 0.4, 0.45), strength=0.4), rug=pbr('quatrefoil_jacquard_fabric', (0.16, 0.04, 0.03), 1.6), rug_border=pbr('quatrefoil_jacquard_fabric', (0.3, 0.2, 0.07), 1.6), rug_dark=pbr('quatrefoil_jacquard_fabric', (0.06, 0.04, 0.03), 1.6))
    spaces = read_plan(); MATS.update(M)
    if args.only: spaces_build = [s for s in spaces if s['type'] in args.only.split(',')]
    else: spaces_build = spaces
    doors = all_doors(spaces)
    for i, s in enumerate(spaces_build):
        build_space(s, spaces, doors, M); furnish(s, M); print(f'built {i + 1}/{len(spaces_build)}: {s["name"]}', flush=True)
    if not args.only:
        for px, Hd, ax in (([405, 772, 768, 1013], 7.2, 'x'), ([353, 872, 407, 960], 4.6, 'y'), ([420, 980, 507, 1040], 4.8, 'x'), ([768, 798, 915, 987], 8.6, 'y'), ([915, 772, 1077, 1073], 7.6, 'y'),
                           ([1075, 773, 1156, 881], 6.0, 'x'), ([1077, 793, 1292, 1002], 7.0, 'x'), ([1278, 793, 1492, 1002], 6.6, 'x'), ([1492, 854, 1640, 941], 5.8, 'x')):
            o = dome(px, Hd, 'x' if ax == 'x' else 'y', M, y0=5.15 if px == [768, 798, 915, 987] else 3.45)
            if px != [768, 798, 915, 987]:      # keep lower roofs out of the tall entrance hall
                e = next(sp for sp in spaces if sp['type'] == 'entrance'); c = cube('cut', e['x0'] + 0.05, e['x1'] - 0.05, e['y0'] + 0.05, e['y1'] - 0.05, -1, 5.1, M['wall'])
                apply_cuts(o, [c])
        build_outside(spaces, M)
    setup_world()
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = args.samples; sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6; sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'; sc.view_settings.exposure = 0.4
    w, h = map(int, args.res.split('x')); sc.render.resolution_x, sc.render.resolution_y = w, h
    cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera')); sc.collection.objects.link(cam); sc.camera = cam
    if args.blend:
        e = next(sp for sp in spaces if sp['type'] == 'entrance')
        cam.location = (e['x0'] + 2.0, (e['y0'] + e['y1']) / 2, 1.65); cam.rotation_euler = (math.radians(88), 0, math.radians(-90)); cam.data.lens = 22
        sc.render.engine = 'BLENDER_EEVEE_NEXT'; ee = sc.eevee
        for attr, val in (('use_raytracing', True), ('use_shadows', True), ('shadow_ray_count', 2), ('use_gtao', True), ('taa_render_samples', 64), ('use_volumetric_shadows', True)):
            if hasattr(ee, attr): setattr(ee, attr, val)
        sc.use_nodes = True; nt = sc.node_tree; nt.nodes.clear()
        rl = nt.nodes.new('CompositorNodeRLayers'); gl = nt.nodes.new('CompositorNodeGlare'); gl.glare_type = 'FOG_GLOW'; gl.threshold = 1.0; gl.size = 7; gl.mix = 0.0
        st = nt.nodes.new('CompositorNodeGlare'); st.glare_type = 'STREAKS'; st.threshold = 3.0; st.streaks = 4; st.mix = -0.85
        out = nt.nodes.new('CompositorNodeComposite'); nt.links.new(rl.outputs[0], gl.inputs[0]); nt.links.new(gl.outputs[0], st.inputs[0]); nt.links.new(st.outputs[0], out.inputs[0])
        try:
            for scr in bpy.data.screens:
                for area in scr.areas:
                    if area.type == 'VIEW_3D':
                        for sp in area.spaces:
                            if sp.type == 'VIEW_3D': sp.shading.type = 'RENDERED'; sp.shading.use_compositor = 'ALWAYS'
        except Exception as ex: print('viewport setup skipped:', ex)
        blend = os.path.abspath(args.blend); bpy.ops.wm.save_as_mainfile(filepath=blend)
        try: bpy.ops.file.make_paths_relative(); bpy.ops.wm.save_mainfile()
        except Exception as ex: print('relative paths:', ex)
        sc.render.engine = 'CYCLES'; print('saved', blend, flush=True)
    def room_shot(typ):
        sp = next((q for q in spaces if q['type'] == typ), None)
        if not sp: return None
        best = None
        for (kx, ky) in ((0, 0), (1, 0), (0, 1), (1, 1)):
            px = sp['x0'] + 1.3 if kx == 0 else sp['x1'] - 1.3; py = sp['y0'] + 1.3 if ky == 0 else sp['y1'] - 1.3
            tx = sp['x1'] - 1 if kx == 0 else sp['x0'] + 1; ty = sp['y1'] - 1 if ky == 0 else sp['y0'] + 1
            d = math.hypot(tx - px, ty - py)
            if not best or d > best[0]: best = (d, px, py, tx, ty)
        _, px, py, tx, ty = best; head = math.degrees(math.atan2(-(tx - px), ty - py))
        return (px, py, 1.55, 84, head, 16)
    for nm, typ in (('bedroom', 'bedroom2'), ('dining_kitchen', 'dining2'), ('library', 'library'), ('living', 'living2'), ('kids_room', 'kid')):
        sh = room_shot(typ)
        if sh: SHOTS[nm] = sh
    if args.shots:
        os.makedirs(args.out, exist_ok=True)
        for name in (SHOTS if args.shots == 'all' else args.shots.split(',')):
            x, y, z, tilt, head, lens = SHOTS[name]; cam.location = (x, y, z); cam.rotation_euler = (math.radians(tilt), 0, math.radians(head)); cam.data.lens = lens
            sc.render.filepath = os.path.join(args.out, name + '.png'); bpy.ops.render.render(write_still=True); print('rendered', name, flush=True)

if __name__ == '__main__':
    main()
