"""Red room textures: deep red damask wallpaper and a red-and-gold patterned rug."""
import cv2, numpy as np, os, math
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'rooms', 'redroom'); os.makedirs(D, exist_ok=True)
rng = np.random.default_rng(3); S = 512
yy, xx = np.mgrid[0:S, 0:S].astype(np.float32) / S
# damask: a mirrored flame/medallion motif in two diagonal offsets
def motif(u, v):
    u = np.abs(u); r = np.hypot(u * 1.4, v); a = np.arctan2(v, u)
    petal = (np.abs(np.sin(a * 3 + r * 6)) > 0.55) & (r < 0.42)
    core = (np.abs(r - 0.2) < 0.025) | ((u < 0.04) & (np.abs(v) < 0.45))
    return petal | core
m = np.zeros((S, S), bool)
for cx, cy in ((0.25, 0.25), (0.75, 0.75), (0.75, 0.25 - 1), (0.25, 1.25), (-0.25, 0.75), (1.25, 0.25)):
    m |= motif((xx - cx) * 2, (yy - cy) * 2)
base = np.array([0.08, 0.06, 0.42], np.float32)        # BGR deep red
hi = np.array([0.1, 0.08, 0.5], np.float32)
img = np.where(m[..., None], hi, base)
img *= 1 + 0.06 * cv2.GaussianBlur(rng.normal(0, 1, (S, S)).astype(np.float32), (0, 0), 1.5)[..., None]
cv2.imwrite(os.path.join(D, 'damask_diff.jpg'), (np.clip(img, 0, 1) * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 92])
rough = np.where(m, 0.35, 0.7).astype(np.float32); cv2.imwrite(os.path.join(D, 'damask_rough.jpg'), (rough * 255).astype(np.uint8))
# rug
W, H = 1024, 1536; yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
def c(r, g, b): return np.array([b, g, r], np.float32) / 255
red, deep, gold, cream, navy = c(120, 20, 22), c(60, 10, 14), c(176, 120, 52), c(200, 170, 130), c(30, 22, 36)
img = np.ones((H, W, 3), np.float32) * red
bx = np.minimum(np.minimum(xx, W - 1 - xx), np.minimum(yy, H - 1 - yy))
for a, b, col in ((0, 18, deep), (18, 24, gold), (24, 90, deep), (90, 96, gold), (96, 110, red)): img[(bx >= a) & (bx < b)] = col
canvas = img.copy()
for i in range(6000):
    x, y, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(5, 13); col = [gold, deep, cream * 0.8, navy, deep][rng.integers(0, 5)]
    for k in range(5):
        a = k / 5 * 6.28; cv2.ellipse(canvas, (int(x + math.cos(a) * r * 0.6), int(y + math.sin(a) * r * 0.6)), (int(r * 0.5), int(r * 0.28)), math.degrees(a), 0, 360, tuple(map(float, col)), -1)
img = np.where((bx >= 110)[..., None], canvas, img)
for k in range(0, max(W, H), 50):
    for px, py in ((k + 25, 57), (k + 25, H - 57), (57, k + 25), (W - 57, k + 25)):
        if px < W and py < H: cv2.circle(img, (int(px), int(py)), 18, tuple(map(float, gold)), -1); cv2.circle(img, (int(px), int(py)), 9, tuple(map(float, red)), -1)
d = np.abs(xx - W / 2) / 280 + np.abs(yy - H / 2) / 420
img[(d < 1) & (d > 0.9)] = gold; img[(d < 0.35)] = deep; img[(d < 0.2)] = gold * 0.9; img[(d < 0.1)] = red
img = np.clip(img * (1 + 0.1 * cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 1.2)[..., None]), 0, 1)
cv2.imwrite(os.path.join(D, 'rug_diff.jpg'), (img * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 92]); print('ok')
