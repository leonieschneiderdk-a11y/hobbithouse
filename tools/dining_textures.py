"""Dining room textures: the big oval rug (cream field, grey-blue and brown florals, dark border bands)."""
import cv2, numpy as np, os, math
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'rooms', 'dining'); os.makedirs(D, exist_ok=True)
rng = np.random.default_rng(5)
def noise2(h, w, scale, seed):
    r = np.random.default_rng(seed); s = r.normal(0, 1, (max(2, h // scale), max(2, w // scale))).astype(np.float32)
    return cv2.resize(s, (w, h), interpolation=cv2.INTER_CUBIC)
W, H = 2048, 1024
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
e = np.sqrt(((xx - W / 2) / (W / 2 - 4)) ** 2 + ((yy - H / 2) / (H / 2 - 4)) ** 2)       # 0 centre .. 1 edge
cream, beige, greyblue, slate, brown, dbrown, rust = [np.array(c[::-1], np.float32) / 255 for c in
    ((206, 190, 162), (178, 160, 130), (122, 124, 128), (62, 62, 66), (120, 86, 60), (66, 46, 34), (142, 84, 58))]
img = np.ones((H, W, 3), np.float32) * cream
def ring(a, b, col): img[(e >= a) & (e < b)] = col
# field: dense little flowers and leaves
canvas = img.copy()
for i in range(9000):
    cx, cy = rng.uniform(0, W), rng.uniform(0, H); r = rng.uniform(5, 13)
    col = [greyblue, slate, slate, dbrown, brown, rust, beige][rng.integers(0, 7)]
    if rng.random() < 0.55:
        for k in range(5):
            a = k / 5 * 2 * math.pi + rng.uniform(0, 1); cv2.ellipse(canvas, (int(cx + math.cos(a) * r * 0.7), int(cy + math.sin(a) * r * 0.7)), (int(r * 0.55), int(r * 0.3)), math.degrees(a), 0, 360, tuple(map(float, col)), -1)
        cv2.circle(canvas, (int(cx), int(cy)), int(r * 0.3) + 1, tuple(map(float, dbrown if rng.random() < 0.5 else cream)), -1)
    else:
        a = rng.uniform(0, 180); cv2.ellipse(canvas, (int(cx), int(cy)), (int(r * 1.1), int(r * 0.35)), a, 0, 360, tuple(map(float, [greyblue, brown, slate][rng.integers(0, 3)])), -1)
# a few vine curves
for i in range(220):
    pts = []; x, y, a = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0, 6.28)
    for k in range(18): a += rng.uniform(-0.4, 0.4); x += math.cos(a) * 12; y += math.sin(a) * 12; pts.append((int(x), int(y)))
    cv2.polylines(canvas, [np.array(pts, np.int32)], False, tuple(map(float, brown)), 2)
img = np.where((e < 0.74)[..., None], canvas, img)
# central medallion
md = np.sqrt(((xx - W / 2) / 260) ** 2 + ((yy - H / 2) / 150) ** 2)
img[(md < 1.0) & (md > 0.9)] = dbrown; img[(md < 0.9) & (md > 0.84)] = beige
# borders
ring(0.74, 0.76, dbrown); ring(0.76, 0.86, beige); ring(0.86, 0.875, dbrown); ring(0.875, 0.96, dbrown * 1.4); ring(0.96, 1.0, dbrown)
band = (e >= 0.76) & (e < 0.86); ang = np.arctan2((yy - H / 2) / H, (xx - W / 2) / W)
motif = (np.abs(np.sin(ang * 60)) > 0.6) & (np.abs(e - 0.81) < 0.03); img[band & motif] = brown
band2 = (e >= 0.875) & (e < 0.96); motif2 = (np.abs(np.sin(ang * 90 + e * 40)) > 0.75); img[band2 & motif2] = greyblue
wool = 1 + 0.08 * noise2(H, W, 4, 1)[..., None] + 0.05 * rng.normal(0, 1, (H, W, 1)); wear = 1 - 0.12 * np.clip(noise2(H, W, 160, 2), 0, 1)[..., None]
img = np.clip(img * wool * wear, 0, 1)
alpha = (e < 1.0).astype(np.float32) * 255
out = np.dstack([(img * 255).astype(np.uint8), alpha.astype(np.uint8)])
cv2.imwrite(os.path.join(D, 'rug_diff.png'), out)
print('ok')
