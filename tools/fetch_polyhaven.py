"""Download Poly Haven models (1k glTF) and pack each into assets/models/<id>.glb.
Run with the Blender Python:  python tools/fetch_polyhaven.py <work_dir> id1 id2 ..."""
import sys, os, json, urllib.request, bpy
UA = {'User-Agent': 'Mozilla/5.0 hobbithouse'}
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'); OUT = os.path.join(ROOT, 'assets', 'models')
work = sys.argv[1]
def get(url, path=None):
    data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
    if path: os.makedirs(os.path.dirname(path), exist_ok=True); open(path, 'wb').write(data)
    return data
cat_p = os.path.join(OUT, 'catalog.json'); cat = json.load(open(cat_p))
for mid in sys.argv[2:]:
    dst = os.path.join(OUT, mid + '.glb')
    if os.path.exists(dst): print('have', mid); continue
    try:
        f = json.loads(get(f'https://api.polyhaven.com/files/{mid}'))['gltf']['1k']['gltf']
        d = os.path.join(work, mid); g = os.path.join(d, os.path.basename(f['url'])); get(f['url'], g)
        for rel, inc in f['include'].items(): get(inc['url'], os.path.join(d, rel))
        bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=g)
        bpy.ops.export_scene.gltf(filepath=dst, export_format='GLB', export_image_format='JPEG', export_jpeg_quality=85)
        lo = [min(v[i] for o in bpy.context.scene.objects if o.type == 'MESH' for v in [o.matrix_world @ __import__('mathutils').Vector(c) for c in o.bound_box]) for i in range(3)]
        hi = [max(v[i] for o in bpy.context.scene.objects if o.type == 'MESH' for v in [o.matrix_world @ __import__('mathutils').Vector(c) for c in o.bound_box]) for i in range(3)]
        cat[mid] = {'size': [round(hi[0] - lo[0], 3), round(hi[2] - lo[2], 3), round(hi[1] - lo[1], 3)], 'bytes': os.path.getsize(dst)}
        print('ok', mid, cat[mid]['size'], cat[mid]['bytes'] // 1024, 'KB', flush=True)
    except Exception as e: print('FAIL', mid, e, flush=True)
json.dump(cat, open(cat_p, 'w'), indent=1)
