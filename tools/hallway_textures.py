"""Hallway textures: a traditional runner (beige field, brown and grey-blue florals, dark borders)."""
import cv2, numpy as np, os, math
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'rooms', 'hallway'); os.makedirs(D, exist_ok=True)
rng = np.random.default_rng(9)
def noise2(h, w, scale, seed):
    r = np.random.default_rng(seed); s = r.normal(0, 1, (max(2, h // scale), max(2, w // scale))).astype(np.float32)
    return cv2.resize(s, (w, h), interpolation=cv2.INTER_CUBIC)
def rgb(*c): return np.array(c[::-1], np.float32) / 255           # BGR for OpenCV
W, H = 512, 1536
field, deep, rose, brown, navy, cream, olive = rgb(150, 128, 100), rgb(64, 48, 38), rgb(120, 82, 64), rgb(96, 68, 48), rgb(66, 76, 92), rgb(204, 186, 154), rgb(118, 106, 80)
img = np.ones((H, W, 3), np.float32) * field
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
bx = np.minimum(np.minimum(xx, W - 1 - xx), np.minimum(yy, H - 1 - yy))
def band(a, b, col): img[(bx >= a) & (bx < b)] = col
canvas = img.copy()
# dense field of rosettes, palmettes and vines
for i in range(5000):
    cx, cy = rng.uniform(0, W), rng.uniform(0, H); r = rng.uniform(5, 15)
    col = [rose, brown, navy, deep, cream * 0.8, olive][rng.integers(0, 6)]
    if rng.random() < 0.5:
        for k in range(6):
            a = k / 6 * 2 * math.pi; cv2.ellipse(canvas, (int(cx + math.cos(a) * r * 0.6), int(cy + math.sin(a) * r * 0.6)), (int(r * 0.5), int(r * 0.28)), math.degrees(a), 0, 360, tuple(map(float, col)), -1)
        cv2.circle(canvas, (int(cx), int(cy)), int(r * 0.3) + 1, tuple(map(float, deep if col is not deep else cream * 0.7)), -1)
    else:
        cv2.ellipse(canvas, (int(cx), int(cy)), (int(r), int(r * 0.4)), rng.uniform(0, 180), 0, 360, tuple(map(float, col)), -1)
for i in range(400):
    pts = []; x, y, a = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0, 6.28)
    for k in range(16): a += rng.uniform(-0.5, 0.5); x += math.cos(a) * 11; y += math.sin(a) * 11; pts.append((int(x), int(y)))
    cv2.polylines(canvas, [np.array(pts, np.int32)], False, tuple(map(float, brown)), 2)
img = np.where((bx >= 92)[..., None], canvas, img)
# central medallion
d = np.abs(xx - W / 2) / 150 + np.abs(yy - H / 2) / 300
img[(d < 1.0) & (d > 0.9)] = deep; img[(d < 0.9) & (d > 0.86)] = cream * 0.75; img[(d < 0.35)] = navy; img[(d < 0.22)] = rose; img[(d < 0.1)] = deep
# borders
band(0, 16, deep); band(16, 22, cream * 0.7); band(22, 70, brown); band(70, 76, cream * 0.8); band(76, 92, deep)
bmask = (bx >= 22) & (bx < 92)
for k in range(0, max(W, H), 54):
    for cx, cy in [(k + 27, 46), (k + 27, H - 46), (46, k + 27), (W - 46, k + 27)]:
        if 0 <= cx < W and 0 <= cy < H:
            cv2.circle(img, (int(cx), int(cy)), 16, tuple(map(float, cream * 0.8)), -1); cv2.circle(img, (int(cx), int(cy)), 9, tuple(map(float, navy)), -1); cv2.circle(img, (int(cx), int(cy)), 4, tuple(map(float, cream * 0.7)), -1)
wool = 1 + 0.10 * noise2(H, W, 3, 1)[..., None] + 0.05 * rng.normal(0, 1, (H, W, 1)); wear = 1 - 0.18 * np.clip(noise2(H, W, 200, 2), 0, 1)[..., None]
img = np.clip(img * wool * wear, 0, 1)
cv2.imwrite(os.path.join(D, 'rug_diff.jpg'), (img * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 92])
print('ok')
