"""Hobbit-house living room, rebuilt as a real 3D room from the 'Living Room & Fireplace' image: a tall timber barrel
vault with close-set arched ribs strung with fairy lights, two iron candle chandeliers, a big stone fireplace with a raised
hearth and a heavy mantel dressed with candles and ivy, a huge L-shaped sectional heaped with throws and patterned cushions,
an octagonal coffee table on a Persian rug, and - where the image has a dining table - a second sitting area with a sofa,
armchairs and a long cushioned window seat under three arched windows. Seats well over twelve people.

Blender axes: the window wall is at y = 0, the room runs toward the camera to y = -L, x is left/right.

    python blender/rooms/living.py --render docs/rooms/living.png --samples 96 --glb assets/rooms/living/living.glb
"""
import argparse, json, math, os, sys, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
from hero_room import A, pbr, flat, image_mat, obj_from_bm, box_uv, box, cyl, torus, cut, sweep_profile, model, light, candle
from kitchen import leaf_cluster, group, kid, tex_mat, mat_alpha, arch_cutter_y, stone_arch, bouquet
from hallway import pillow, blocks
from spa import candles_cluster
from cellar import candle_chandelier
from bedroom import lamp, throw
from dining import rod
import office

W, L = 11.0, 17.0
HW = W / 2
WALL_H, APEX = 2.6, 4.7
rnd = random.Random(171)
CAMS = {'main': (1.7, -16.55, 1.65, 85, 9, 14), 'fire': (-1.2, -14.6, 1.6, 84, -38, 16), 'back': (0.3, -8.9, 1.6, 86, 4, 15)}
FY = -10.4                                                 # fireplace centre along the right wall

def K(*p): return A('assets', 'rooms', 'living', *p)

def vault_z(x, inset=0.0):
    t = max(-1.0, min(1.0, x / (HW - inset)))
    return WALL_H + math.sqrt(max(0.0, 1 - t * t)) * (APEX - WALL_H - inset)

def profile(n=48, inset=0.0):
    pts = [(-HW + inset, 0.0)]
    for i in range(n + 1):
        a = math.pi - i / n * math.pi
        pts.append((math.cos(a) * (HW - inset), WALL_H + math.sin(a) * (APEX - WALL_H - inset)))
    pts.append((HW - inset, 0.0)); return pts

def tint_model(lib_name, cloth, wood=(0.25, 0.14, 0.08)):
    """Multiply a Poly Haven model's colours, so its upholstery matches the room."""
    for o in bpy.data.collections[lib_name].all_objects:
        for slot in getattr(o, 'material_slots', []):
            m = slot.material
            if not m or not m.use_nodes or m.get('tinted'): continue
            b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if not b: continue
            inp = b.inputs['Base Color']; mix = m.node_tree.nodes.new('ShaderNodeMixRGB'); mix.blend_type = 'MULTIPLY'; mix.inputs[0].default_value = 1
            if inp.is_linked: m.node_tree.links.new(inp.links[0].from_socket, mix.inputs[1])
            else: mix.inputs[1].default_value = inp.default_value
            w = 'leg' in m.name.lower() or 'wood' in m.name.lower()
            mix.inputs[2].default_value = (*(wood if w else cloth), 1); m.node_tree.links.new(mix.outputs[0], inp); m['tinted'] = 1

def face_rot(dx, dy):
    """Group rotation so that local -y (the way a seat faces) points along (dx, dy)."""
    return math.atan2(dx, -dy)

def sofa(cx, cy, length, depth, rot, mat, cush, throws, arms=(True, True), legs=None):
    """A deep upholstered sofa in local space (seat faces -y, back along +y), rotated into place. Seat and back cushions,
    patterned scatter cushions, a throw or two over the back."""
    g = group((cx, cy, 0), rot); l2, d2 = length / 2, depth / 2; aw = 0.26
    kid(box('sofa base', -l2, l2, -d2, d2, 0.1, 0.42, mat, 1.0, 0.05), g)
    kid(box('sofa back', -l2, l2, d2 - 0.3, d2, 0.42, 0.98, mat, 1.0, 0.09), g)
    x0 = -l2 + (aw if arms[0] else 0.0); x1 = l2 - (aw if arms[1] else 0.0)
    for s, on in ((-1, arms[0]), (1, arms[1])):
        if on:
            a0, a1 = (-l2, -l2 + aw) if s < 0 else (l2 - aw, l2)
            kid(box('sofa arm', a0, a1, -d2, d2, 0.1, 0.72, mat, 1.0, 0.1), g)
            kid(pillow((a0 + a1) / 2, 0.0, 0.72, aw + 0.04, depth - 0.02, 0.12, mat), g)
    for (x, y) in ((-l2 + 0.08, -d2 + 0.08), (l2 - 0.08, -d2 + 0.08), (-l2 + 0.08, d2 - 0.08), (l2 - 0.08, d2 - 0.08)):
        kid(cyl('sofa foot', 0.035, 0.1, (x, y, 0.05), (0, 0, 0), legs, 10), g)
    n = max(1, round((x1 - x0) / 0.85)); w = (x1 - x0) / n
    for i in range(n):
        c = x0 + (i + 0.5) * w
        kid(pillow(c, -0.12, 0.5, w - 0.03, depth - 0.4, 0.17, mat), g)
        bc = kid(pillow(c, d2 - 0.45, 0.8, w - 0.06, 0.24, 0.48, mat), g); bc.rotation_euler = (math.radians(-12), 0, 0)
        for k in range(rnd.choice((1, 1, 2))):
            sc = kid(pillow(c + rnd.uniform(-0.18, 0.18), d2 - 0.62 - k * 0.1, 0.84, 0.46, 0.14, 0.44, rnd.choice(cush)), g)
            sc.rotation_euler = (math.radians(-14), rnd.uniform(-0.15, 0.15), rnd.uniform(-0.25, 0.25))
    for k in range(len(throws)):
        u = rnd.uniform(x0 + 0.2, x1 - 1.0); kid(throw(u, u + rnd.uniform(0.7, 1.0), d2 - 0.35, d2 + 0.02, 1.0, throws[k], 0.45), g)
    return g

def build():
    floor = pbr('wood_floor_worn', 'materials', (0.42, 0.29, 0.2), 0.75, 1.0)
    plaster = pbr('clay_plaster', 'materials', (0.62, 0.47, 0.33), 1.0, 1.4)
    boards = pbr('weathered_brown_planks', 'materials', (0.42, 0.29, 0.19), 0.9)
    beam = pbr('rough_wood', 'materials', (0.24, 0.15, 0.09), 0.9)
    stone = pbr('rustic_stone_wall', 'materials', (0.6, 0.54, 0.46), 1.0, 1.4)
    wood = pbr('wood_cabinet_worn_long', 'materials', (0.42, 0.28, 0.17), 0.75)
    trim = pbr('dark_wooden_planks', 'materials', (0.4, 0.27, 0.17), 0.9)
    rug = tex_mat('rug', A('assets', 'rooms', 'bedroom', 'rug_diff.jpg'), rough=0.95, tint=(0.95, 0.85, 0.8))
    rug2 = tex_mat('rug back', A('assets', 'rooms', 'redroom', 'rug_diff.jpg'), rough=0.95)
    velvet = flat('sofa velvet', (0.085, 0.075, 0.042), 0.85); rust = flat('rust velvet', (0.11, 0.035, 0.017), 0.8)
    kilim = [tex_mat('kilim cushion ' + r, A('assets', 'rooms', r, 'rug_diff.jpg'), rough=0.9) for r in ('cellar', 'hallway', 'redroom', 'bedroom')]
    cush = kilim + [flat('cushion rust', (0.3, 0.08, 0.035), 0.9), flat('cushion mustard', (0.42, 0.26, 0.06), 0.9), flat('cushion moss', (0.12, 0.14, 0.06), 0.9),
                    flat('cushion oat', (0.48, 0.4, 0.3), 0.9)]
    throws = [flat('throw wine', (0.2, 0.03, 0.025), 0.95), flat('throw knit', (0.42, 0.35, 0.26), 1.0), flat('throw mustard', (0.33, 0.19, 0.05), 0.95), kilim[0], kilim[2]]
    brass = flat('brass', (0.78, 0.55, 0.26), 0.3, 1.0); iron = flat('iron', (0.03, 0.028, 0.026), 0.55, 0.35); office.BRASS = brass
    shade_m = flat('lamp shade', (0.95, 0.78, 0.55), 0.8, emit=(1.0, 0.7, 0.4), strength=3)
    frame = flat('window frame', (0.2, 0.11, 0.05), 0.55); glass = flat('glass', (0.95, 0.97, 0.98), 0.02, transmission=1.0)
    wax = flat('wax', (0.92, 0.88, 0.78), 0.45); log = flat('living log', (0.03, 0.018, 0.01), 0.95); soot = flat('soot', (0.012, 0.01, 0.008), 0.95)
    flame = flat('flame', (1, 0.35, 0.05), 1, emit=(1.0, 0.24, 0.02), strength=0.45)
    fairy = flat('fairy bulb', (1, 0.8, 0.5), 1, emit=(1.0, 0.72, 0.38), strength=25)
    ivy = mat_alpha('ivy', A('assets', 'rooms', 'kitchen', 'ivy.png'))
    petals = [flat('petal white', (0.95, 0.92, 0.88), 0.6), flat('petal cream', (0.95, 0.85, 0.65), 0.6), flat('petal rust', (0.7, 0.3, 0.15), 0.6), flat('petal pink', (0.85, 0.45, 0.5), 0.6)]
    bookm = [flat('book ' + n, c, 0.6) for n, c in (('red', (0.3, 0.05, 0.03)), ('brown', (0.22, 0.12, 0.06)), ('green', (0.08, 0.14, 0.07)), ('tan', (0.45, 0.32, 0.18)),
                                                  ('navy', (0.05, 0.07, 0.14)), ('maroon', (0.2, 0.04, 0.05)), ('cream', (0.55, 0.48, 0.36)), ('black', (0.03, 0.03, 0.03)))]
    # ------------------------------------------------------------ shell: wide boards, plaster walls, the tall timber barrel vault
    box('floor', -HW - 0.3, HW + 0.3, -L - 0.3, 0.3, -0.12, 0.0, floor, 2.4)
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
    # close-set arched ribs, purlins, wall plates and posts; fairy lights strung along every other rib
    rp = profile(48, 0.03)[1:-1]
    RIBS = [-0.7 - k * 1.3 for k in range(13)]
    fb = bmesh.new()
    for k, y in enumerate(RIBS):
        sweep_profile('rib', rp, y, 0.26, 0.3, beam)
        if k % 2 == 0:
            for (x, z) in rp[2:-2:2]:
                n_ = Vector((x, 0, (z - WALL_H) * (HW / (APEX - WALL_H)))).normalized()
                p = Vector((x, y - 0.16, z)) - n_ * 0.05
                bmesh.ops.create_icosphere(fb, subdivisions=1, radius=0.016, matrix=Matrix.Translation(p))
    for x in (-3.6, -1.8, 0.0, 1.8, 3.6):
        box('purlin', x - 0.12, x + 0.12, -L, 0.0, vault_z(x, 0.3) - 0.26, vault_z(x, 0.3), beam, 1.2)
        for k in range(0, int(L / 0.45)):                                   # fairy lights along the ridge purlins
            if x in (-1.8, 1.8): bmesh.ops.create_icosphere(fb, subdivisions=1, radius=0.016, matrix=Matrix.Translation((x + 0.14 * math.sin(k * 1.7), -0.3 - k * 0.45, vault_z(x, 0.3) - 0.3 - 0.06 * abs(math.sin(k * 0.9)))))
    obj_from_bm('fairy lights', fb, fairy, True)
    for x in (-1.8, 1.8):
        for y in (-3.0, -7.5, -12.0, -15.5): light((x, y, vault_z(x, 0.3) - 0.45), 18, (1.0, 0.72, 0.4), radius=0.3)
    for s in (-1, 1): box('wall plate', s * HW - (0.15 if s > 0 else -0.15) - 0.15, s * HW - (0.15 if s > 0 else -0.15) + 0.15, -L, 0.0, WALL_H - 0.15, WALL_H + 0.1, beam, 1.2)
    for y in RIBS:
        for s in (-1, 1):
            if -7.5 < y < -0.4: continue                                   # bookcases there
            if s > 0 and FY - 2.0 < y < FY + 2.0: continue                 # fireplace
            x = s * (HW - 0.12); box('wall post', x - 0.12, x + 0.12, y - 0.13, y + 0.13, 0.0, WALL_H, beam, 1.2)
    # ------------------------------------------------------------ the great stone fireplace in the right wall
    def fx(name, d0, d1, u0, u1, z0, z1, mat, bev=0.0): return box(name, HW - d1, HW - d0, FY + u0, FY + u1, z0, z1, mat, 1.0, bev)
    br = fx('chimney breast', 0.0, 0.62, -1.6, 1.6, 0.0, vault_z(HW - 0.62) + 0.4, stone)
    cut(br, [box('c', HW - 0.7, HW - 0.3, FY - 0.8, FY + 0.8, 0.45, 1.35, stone)]); box_uv(br, 1.0)
    sr = fx('firebox surround', 0.6, 0.98, -1.5, 1.5, 0.0, 1.7, stone, 0.02)
    cut(sr, [box('c', HW - 1.2, HW - 0.3, FY - 0.8, FY + 0.8, 0.45, 1.35, stone)])
    sa = cyl('firebox arch', 0.8, 0.38, (HW - 0.79, FY, 1.35), (0, math.pi / 2, 0), stone, 32); sa.scale = (0.45, 1, 1)
    cut(sa, [cyl('c', 0.8, 0.6, (HW - 0.79, FY, 1.35), (0, math.pi / 2, 0), stone, 32), box('c', HW - 2, HW, FY - 2, FY + 2, 1.35, 3, stone)])
    bpy.data.objects.remove(sa, do_unlink=True)
    fx('firebox back', 0.24, 0.31, -0.82, 0.82, 0.43, 1.37, soot); fx('firebox floor', 0.3, 0.99, -0.81, 0.81, 0.43, 0.46, soot)
    for su in (-1, 1): fx('firebox side', 0.3, 0.98, su * 0.8 - 0.01 * (1 - su), su * 0.8 + 0.01 * (1 + su), 0.45, 1.35, soot)
    fx('firebox top', 0.3, 0.98, -0.8, 0.8, 1.34, 1.36, soot)
    fx('raised hearth', 0.6, 1.55, -2.0, 2.0, 0.0, 0.45, stone, 0.02)
    fx('mantel', 0.5, 1.2, -2.0, 2.0, 1.7, 1.92, beam, 0.015)
    for k in range(4): cyl('log', 0.07, 0.95, (HW - 0.62 + (k % 2) * 0.1, FY + (k - 1.5) * 0.03, 0.53 + (k // 2) * 0.12), (math.pi / 2, 0, (k - 1.5) * 0.25), log, 12)
    for dy, hh in ((-0.42, 0.45), (-0.3, 0.6), (-0.18, 0.75), (-0.05, 0.95), (0.08, 1.0), (0.2, 0.8), (0.32, 0.6), (0.44, 0.4)):
        b_ = bmesh.new(); bmesh.ops.create_cone(b_, cap_ends=True, segments=10, radius1=0.1, radius2=0.0, depth=0.36); f = obj_from_bm('flame', b_, flame, True)
        hh *= rnd.uniform(0.75, 1.15); f.location = (HW - 0.6 + rnd.uniform(-0.05, 0.05), FY + dy, 0.6 + 0.22 * hh); f.scale = (0.55, 1.0, hh * 1.35); f.rotation_euler = (rnd.uniform(-0.25, 0.25), rnd.uniform(-0.1, 0.1), 0)
    fx('ember bed', 0.45, 0.8, -0.55, 0.55, 0.46, 0.49, flat('embers', (0.15, 0.03, 0.01), 0.9, emit=(0.9, 0.12, 0.01), strength=0.25))
    light((HW - 2.0, FY, 1.0), 110, (1.0, 0.45, 0.15), radius=0.35); light((HW - 2.6, FY, 0.4), 40, (1.0, 0.5, 0.2), radius=0.3)
    for du in (-1.0, 1.0): fx('firedog', 1.0, 1.25, du * 0.6 - 0.03, du * 0.6 + 0.03, 0.45, 0.8, iron)
    model('fancy_picture_frame_01', (HW - 0.64, FY, 2.75), -math.pi / 2, width=1.3)
    for du in (-1.75, -1.5, 1.45, 1.75): candles_cluster(HW - 0.85, FY + du, 1.92, wax, 2, 1.2)
    model('brass_vase_02', (HW - 0.85, FY - 1.0, 1.92), 0, height=0.32); model('mantel_clock_01', (HW - 0.85, FY + 0.95, 1.92), -math.pi / 2, height=0.3)
    model('brass_candleholders', (HW - 0.85, FY + 0.3, 1.92), -math.pi / 2, height=0.3) if os.path.exists(A('assets', 'models', 'brass_candleholders.glb')) else None
    for k in range(9): leaf_cluster(ivy, HW - 0.88, FY - 1.9 + k * 0.47, 1.95, 9, 0.24, 0.6 if k in (0, 1, 7, 8) else 0.2)
    model('wicker_basket_01', (HW - 1.0, FY - 2.45, 0.0), 0, height=0.4); model('wooden_lantern_01', (HW - 1.1, FY + 1.75, 0.45), 0, height=0.45); light((HW - 1.1, FY + 1.75, 0.7), 15)
    # ------------------------------------------------------------ the main sitting area: a huge L-sectional facing the fire, armchairs by the hearth
    legs = flat('sofa feet', (0.08, 0.045, 0.025), 0.5)
    sofa(-3.55, -10.5, 4.9, 1.1, face_rot(1, 0), velvet, cush, throws[:3], arms=(False, True), legs=legs)       # long run, faces the fire
    sofa(-2.55, -13.5, 3.1, 1.1, face_rot(0, 1), velvet, cush, throws[2:4], arms=(True, False), legs=legs)       # the return across the front
    throw(-4.1, -3.0, -12.95, -12.6, 0.55, throws[0], 0.4)                                                        # a blanket spilling over the corner seat
    throw(-2.3, -1.45, -14.05, -12.92, 0.62, throws[4], 0.45); throw(-4.06, -3.04, -8.3, -8.02, 0.8, throws[1], 0.5)
    throw(-4.06, -3.04, -10.9, -10.2, 0.62, throws[3], 0.42)
    for (x, y, fx_, fy_) in ((3.3, -13.15, -0.8, 0.9), (3.3, -7.75, -0.8, -0.9)):
        model('ArmChair_01', (x, y, 0), face_rot(fx_, fy_), width=0.9)
    tint_model('lib_ArmChair_01', (0.13, 0.065, 0.032))
    for (x, y) in ((3.7, -14.25), (3.7, -6.6)): model('side_table_01', (x, y, 0), 0, height=0.55); candles_cluster(x, y, 0.55, wax, 2, 0.9)
    model('Ottoman_01', (1.6, -10.4, 0), 0, height=0.42); tint_model('lib_Ottoman_01', (0.3, 0.16, 0.08))
    throw(1.3, 1.9, -10.75, -10.05, 0.45, throws[2], 0.3)
    # the octagonal coffee table with flowers, a lantern, candles and books
    CX, CY = -1.0, -10.5
    cyl('coffee table top', 0.85, 0.08, (CX, CY, 0.46), (0, 0, math.pi / 8), wood, 8)
    cyl('coffee table apron', 0.78, 0.1, (CX, CY, 0.37), (0, 0, math.pi / 8), trim, 8)
    cyl('coffee table shelf', 0.7, 0.05, (CX, CY, 0.1), (0, 0, math.pi / 8), trim, 8)
    for k in range(4):
        a_ = k * math.pi / 2 + math.pi / 4; lx, ly = CX + math.cos(a_) * 0.55, CY + math.sin(a_) * 0.55
        box('coffee table leg', lx - 0.06, lx + 0.06, ly - 0.06, ly + 0.06, 0.0, 0.42, trim, 1.0, 0.01)
    T = 0.5
    model('ceramic_vase_02', (CX, CY, T), 0, height=0.22); bouquet(CX, CY, T + 0.22, petals, ivy, 22, 0.2)
    model('wooden_lantern_01', (CX + 0.45, CY - 0.3, T), 0, height=0.32); light((CX + 0.45, CY - 0.3, T + 0.16), 12)
    candles_cluster(CX - 0.4, CY + 0.35, T, wax, 3, 1.0); candles_cluster(CX + 0.4, CY + 0.4, T, wax, 2, 0.8)
    for k in range(3): office.BOOKS.append((CX - 0.45, CY - 0.3, T + 0.022 + k * 0.045, 0.3, 0.22, 0.042, [0, 3, 5][k]))
    model('tea_set_01', (CX + 0.05, CY - 0.5, T), 0.4, width=0.4)
    for k in range(2): office.BOOKS.append((CX + 0.3, CY + 0.1, 0.15 + k * 0.05, 0.3, 0.22, 0.045, [1, 2][k]))
    # behind the long sofa, against the left wall: a console with lamps, pictures above
    box('console', -HW + 0.05, -HW + 0.5, -12.6, -8.4, 0.78, 0.83, wood, 1.0, 0.01)
    for y in (-12.5, -8.5):
        for x in (-HW + 0.1, -HW + 0.45): box('console leg', x - 0.03, x + 0.03, y - 0.03, y + 0.03, 0.0, 0.78, wood, 1.0)
    lamp(-HW + 0.27, -12.0, 0.83, brass, shade_m, 0.45, 50); lamp(-HW + 0.27, -9.0, 0.83, brass, shade_m, 0.45, 50)
    model('potted_plant_02', (-HW + 0.27, -10.5, 0.83), 0.3, height=0.5); model('ceramic_vase_04', (-HW + 0.27, -11.2, 0.83), 0, height=0.25)
    model('fancy_picture_frame_01', (-HW + 0.03, -10.5, 1.95), math.pi / 2, width=1.1)
    model('hanging_picture_frame_02', (-HW + 0.03, -12.3, 1.9), math.pi / 2, width=0.55); model('hanging_picture_frame_01', (-HW + 0.03, -8.7, 1.9), math.pi / 2, width=0.55)
    # ------------------------------------------------------------ the back sitting area (instead of the dining table): sofa, armchairs, round table
    sofa(0.0, -5.6, 3.3, 1.05, face_rot(0, 1), rust, cush, throws[3:], arms=(True, True), legs=legs)
    for (x, y, d) in ((-2.25, -3.9, (1, 0)), (2.25, -3.9, (-1, 0))):
        model('chinese_sofa', (x, y, 0), face_rot(*d), width=1.5) if False else model('ArmChair_01', (x, y, 0), face_rot(*d), width=0.9)
    cyl('round table top', 0.65, 0.06, (0, -3.9, 0.46), (0, 0, 0), wood, 48); cyl('round table pedestal', 0.09, 0.4, (0, -3.9, 0.23), (0, 0, 0), trim, 16)
    cyl('round table foot', 0.35, 0.05, (0, -3.9, 0.025), (0, 0, 0), trim, 24)
    candles_cluster(0.1, -3.9, 0.49, wax, 3, 1.0); model('wooden_bowl_01', (-0.3, -3.75, 0.49), 0, width=0.3); bouquet(0.2, -4.15, 0.62, petals, ivy, 10, 0.12)
    model('ceramic_vase_04', (0.2, -4.15, 0.49), 0, height=0.15)
    model('Ottoman_01', (0.0, -2.4, 0), 0, height=0.42) if os.path.exists(A('assets', 'models', 'Ottoman_01.glb')) else None
    # ------------------------------------------------------------ the window wall: three arched windows, a long cushioned window seat
    WX = (-3.2, 0.0, 3.2); WW, WRH, WZ = 1.5, 1.35, 0.75; t = 0.08
    for wx in WX:
        cut(back, arch_cutter_y(wx, WW, WRH, WZ, -0.2, 0.8))
        g = group((wx, 0.22, WZ))
        for x0, x1, z0, z1 in ((-WW / 2, -WW / 2 + t, 0, WRH), (WW / 2 - t, WW / 2, 0, WRH), (-WW / 2, WW / 2, 0, t)): kid(box('win frame', x0, x1, -0.05, 0.05, z0, z1, frame, 1.0), g)
        bpy.ops.mesh.primitive_torus_add(major_radius=WW / 2 - t / 2, minor_radius=t / 2, major_segments=48, minor_segments=8, location=(0, 0, WRH), rotation=(math.pi / 2, 0, 0))
        o = bpy.context.active_object; o.data.materials.append(frame)
        b2 = bmesh.new(); b2.from_mesh(o.data); bmesh.ops.delete(b2, geom=[v for v in b2.verts if v.co.y < -t * 0.4], context='VERTS'); b2.to_mesh(o.data); b2.free(); kid(o, g)
        for x in (-WW / 4, 0.0, WW / 4): kid(box('mullion', x - 0.022, x + 0.022, -0.035, 0.035, t, WRH + math.sqrt(max(0, (WW / 2) ** 2 - x * x)) - 0.07, frame, 1.0), g)
        for z in (WRH * 0.5, WRH): kid(box('transom', -WW / 2 + t, WW / 2 - t, -0.035, 0.035, z - 0.02, z + 0.02, frame, 1.0), g)
        bm = bmesh.new(); vs = [bm.verts.new((-WW / 2 + t, 0, 0.05)), bm.verts.new((WW / 2 - t, 0, 0.05))]
        for i in range(33): a_ = i / 32 * math.pi; vs.append(bm.verts.new((math.cos(a_) * (WW / 2 - t), 0, WRH + math.sin(a_) * (WW / 2 - t))))
        bm.faces.new(vs); kid(obj_from_bm('glass', bm, glass), g)
        g2 = group((wx, 0.0, WZ)); stone_arch(g2, WW, WRH, 0.35, beam, 0.16, half=True)
        a = light((wx, 1.6, WZ + 1.1), 600, (0.9, 0.94, 1.0), kind='AREA'); a.data.size = WW; a.rotation_euler = (math.radians(-90), 0, 0)
        model('potted_plant_04', (wx - 0.45, -0.15, WZ), 0, height=0.3)
    box_uv(back, 2.0)
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1); bmesh.ops.scale(bm, vec=(25, 9, 1), verts=bm.verts)
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 4, 'X')); bmesh.ops.translate(bm, vec=(0, 14, 2.6), verts=bm.verts)
    view = obj_from_bm('valley view', bm, image_mat('view', A('assets', 'rooms', 'kitchen', 'view.jpg'), 1.15)); uvl = view.data.uv_layers.new()
    for i, l in enumerate(uvl.data): co = view.data.vertices[view.data.loops[i].vertex_index].co; l.uv = (co.x / 50 + 0.5, (co.z - 2.6) / 18 + 0.5)
    box('window seat', -4.4, 4.4, -0.62, 0.0, 0.0, 0.46, wood, 1.0, 0.01)
    for k in range(4): x = -3.3 + k * 2.2; box('seat panel', x - 0.9, x + 0.9, -0.64, -0.62, 0.08, 0.38, trim, 1.0)
    pillow(0.0, -0.31, 0.53, 8.7, 0.6, 0.13, flat('seat cushion', (0.3, 0.2, 0.12), 0.9))
    for k in range(10):
        p = pillow(-4.0 + k * 0.89, -0.12, 0.8, 0.46, 0.14, 0.42, rnd.choice(cush)); p.rotation_euler = (math.radians(12), 0, rnd.uniform(-0.1, 0.1))
    # ------------------------------------------------------------ bookcases along both side walls at the back, with plants and lamps
    for s in (-1, 1):
        office.bookcase_run(-7.3, -0.75, s * HW, -s, False, wood, top=2.4)
        model('potted_plant_01', (s * (HW - 0.45), -8.0, 0), 0.6 * s, height=1.6)
        for k in range(6): leaf_cluster(ivy, s * (HW - 0.3), -7.0 + k * 1.15, 2.55, 8, 0.25, 0.5)
    lamp(-HW + 0.95, -1.0, 0.0, brass, shade_m, 1.5, 55); lamp(HW - 0.95, -1.0, 0.0, brass, shade_m, 1.5, 55)
    # ------------------------------------------------------------ rugs, chandeliers, the front door
    for (mat, sx, sy, x, y, r) in ((rug, 6.2, 7.6, -1.0, -10.5, -2), (rug2, 5.0, 4.4, 0.0, -4.3, 1)):
        bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5); uvl = bm.loops.layers.uv.new()
        for f in bm.faces:
            for l in f.loops: l[uvl].uv = (l.vert.co.x + 0.5, l.vert.co.y + 0.5)
        o = obj_from_bm('rug', bm, mat); o.scale = (sx, sy, 1); o.location = (x, y, 0.007); o.rotation_euler = (0, 0, math.radians(r))
    top = vault_z(0.0) - 0.15
    candle_chandelier(-0.6, -10.4, 2.75, top, iron, 1.0, 14); candle_chandelier(-0.6, -10.4, 2.2, 2.6, iron, 0.55, 8)
    candle_chandelier(0.0, -4.2, 2.95, top, iron, 0.75, 10)
    DX0 = 2.6
    cut(front, arch_cutter_y(DX0, 1.3, 1.7, 0.0, -L - 1, -L + 1)); box_uv(front, 2.0)
    g = group((DX0, -L, 0.0)); stone_arch(g, 1.3, 1.7, 0.5, beam, 0.2, half=True)
    box('door', DX0 - 0.7, DX0 + 0.7, -L - 0.25, -L - 0.18, 0.0, 2.45, trim, 0.8)
    for k in range(4): box('door batten', DX0 - 0.62, DX0 + 0.62, -L - 0.18, -L - 0.16, 0.3 + k * 0.55, 0.38 + k * 0.55, beam, 1.0)
    model('potted_plant_01', (DX0 - 1.25, -L + 0.45, 0), 0.4, height=1.4); model('vintage_grandfather_clock_01', (-HW + 0.4, -L + 0.4, 0), math.pi / 2, height=2.1)
    model('wooden_display_shelves_01', (-1.0, -L + 0.3, 0), math.pi, height=1.9) if os.path.exists(A('assets', 'models', 'wooden_display_shelves_01.glb')) else None
    blocks('books', office.BOOKS, bookm)
    w = bpy.data.worlds.new('w'); bpy.context.scene.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0.4, 0.42, 0.45, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 0.05
    for y in (-3.0, -8.0, -13.0):
        f = light((0, y, vault_z(0) - 0.6), 80, (1.0, 0.7, 0.42), kind='AREA'); f.data.size = 4.0

def walk_rects():
    R = [(-5.0, 5.0, -16.6, -14.35),            # just inside the door, behind the sofa return
         (0.25, 2.65, -14.35, -6.4),            # between the coffee table and the armchairs
         (-2.85, -1.95, -12.75, -8.3),          # inside the L, between the sectional and the table
         (-2.85, 0.25, -12.75, -11.45),
         (2.65, 4.05, -12.55, -8.35),           # in front of the hearth
         (-4.85, 4.85, -7.25, -6.35),           # across the room between the two sitting areas
         (-4.85, -2.8, -7.25, -0.75), (2.8, 4.85, -7.25, -0.75),   # the back aisles by the bookcases
         (-4.85, 4.85, -2.95, -0.75)]           # in front of the window seat
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
    cfg.update(name='Living Room', glb='assets/rooms/living/living.glb', spawn=dict(x=2.6, z=L - 0.6, yaw=0.12), walk=walk_rects(), probe=False, tints=tints, floor='wood_floor_worn')
    cfg.setdefault('lights', [{'x': HW - 1.5, 'y': 1.0, 'z': -FY, 'color': '#ff8a3a', 'power': 14, 'range': 8}, {'x': -0.6, 'y': 2.7, 'z': 10.4, 'color': '#ffb877', 'power': 12, 'range': 9},
                              {'x': 0.0, 'y': 2.9, 'z': 4.2, 'color': '#ffb877', 'power': 10, 'range': 8}, {'x': 0.0, 'y': 2.0, 'z': 0.8, 'color': '#ffe8d0', 'power': 8, 'range': 7},
                              {'x': -HW + 0.3, 'y': 1.4, 'z': 10.5, 'color': '#ffb877', 'power': 5, 'range': 5}, {'x': 0.0, 'y': 3.8, 'z': 14.0, 'color': '#ffb877', 'power': 6, 'range': 7}])
    cfg.setdefault('exposure', 0.9); cfg.setdefault('version', 1); cfg.setdefault('wallBoost', 1.0); cfg.setdefault('maxFlameLights', 30); cfg.setdefault('flameColor', '#ffb877')
    json.dump(cfg, open(cfgp, 'w'), indent=1)
    if a.render: sc.render.filepath = os.path.abspath(a.render); bpy.ops.render.render(write_still=True)
    if a.glb:
        keep = ('plaster', 'planks', 'rough_wood', 'wood_floor', 'rustic_stone', 'view', 'ivy', 'rug')
        for im in bpy.data.images:
            if im.size[0] > 512 and not any(k in im.name for k in keep): im.scale(512, 512)
        bpy.ops.object.select_all(action='DESELECT')
        for o in list(sc.objects):
            if o.type == 'EMPTY' and o.instance_type == 'COLLECTION': o.select_set(True)
        if any(o.select_get() for o in sc.objects): bpy.ops.object.duplicates_make_real()
        bpy.ops.export_scene.gltf(filepath=os.path.abspath(a.glb), export_format='GLB', export_lights=False, export_cameras=False, export_apply=True, export_image_format='AUTO')

if __name__ == '__main__':
    main()
