"""Closet runner: a dark kilim with rows of diamonds (charcoal, rust, tan) and banded borders."""
import cv2, numpy as np, os
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'rooms', 'closet'); os.makedirs(D, exist_ok=True)
rng = np.random.default_rng(12); W, H = 512, 1536
def c(r, g, b): return np.array([b, g, r], np.float32) / 255
dark, char, rust, tan, cream = c(42, 32, 28), c(70, 56, 48), c(120, 62, 40), c(150, 112, 78), c(186, 160, 126)
img = np.ones((H, W, 3), np.float32) * dark
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
bx = np.minimum(np.minimum(xx, W - 1 - xx), np.minimum(yy, H - 1 - yy))
for a, b, col in ((0, 14, char), (14, 20, tan), (20, 44, rust), (44, 50, tan), (50, 58, char)): img[(bx >= a) & (bx < b)] = col
f = bx >= 58
u = (xx - W / 2) / 70; v = (yy % 160 - 80) / 70; d = np.abs(u) + np.abs(v)
for lo, hi, col in ((0.0, 0.25, cream), (0.25, 0.45, rust), (0.45, 0.6, tan), (0.6, 0.8, char), (0.8, 0.9, rust)): img[f & (d >= lo) & (d < hi)] = col
for s in (-1, 1):
    u2 = (xx - W / 2 - s * 150) / 40; v2 = ((yy + 80) % 160 - 80) / 40; d2 = np.abs(u2) + np.abs(v2)
    img[f & (d2 < 0.5)] = tan; img[f & (d2 < 0.25)] = rust
zig = (np.abs(((yy % 40) - 20)) / 20 * 30 + 60).astype(int)
noise = 1 + 0.12 * cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 1.5)[..., None]
img = np.clip(img * noise, 0, 1)
cv2.imwrite(os.path.join(D, 'runner_diff.jpg'), (img * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 92]); print('ok')
