"""Make the entrance floor tiles (glossy beige-taupe) and warm up the round rug."""
import cv2, numpy as np, os
D = os.path.join(os.path.dirname(__file__), '..', 'assets', 'rooms', 'entrance')
rng = np.random.default_rng(7); S, N, G = 1024, 4, 5          # size, tiles per side, grout px
tile = S // N
base = np.array([196, 176, 148], np.float32)                 # sRGB beige-taupe (RGB)
diff = np.zeros((S, S, 3), np.float32); rough = np.zeros((S, S), np.float32); nor_h = np.zeros((S, S), np.float32)
yy, xx = np.mgrid[0:tile, 0:tile].astype(np.float32)
for i in range(N):
    for j in range(N):
        k = 1 + rng.uniform(-0.06, 0.06) + (0.035 if (i + j) % 2 else -0.035)   # soft checker + per-tile variation
        hue = np.array([1, 1 + rng.uniform(-0.015, 0.015), 1 + rng.uniform(-0.03, 0.02)])
        c = base * k * hue
        # gentle cloudy marbling inside each tile
        n = cv2.GaussianBlur(rng.normal(0, 1, (tile, tile)).astype(np.float32), (0, 0), 18); n /= np.abs(n).max() + 1e-6
        f = cv2.GaussianBlur(rng.normal(0, 1, (tile, tile)).astype(np.float32), (0, 0), 3); f /= np.abs(f).max() + 1e-6
        t = c[None, None, :] * (1 + 0.035 * n[..., None] + 0.012 * f[..., None])
        diff[i*tile:(i+1)*tile, j*tile:(j+1)*tile] = t
        rough[i*tile:(i+1)*tile, j*tile:(j+1)*tile] = 0.16 + 0.06 * (n * 0.5 + 0.5)
        nor_h[i*tile:(i+1)*tile, j*tile:(j+1)*tile] = 1 - 0.0 * xx
grout = np.zeros((S, S), bool)
for p in range(N + 1):
    for q in range(-G // 2 - 1, G // 2 + 1):
        grout[np.clip(p * tile + q, 0, S - 1), :] = True; grout[:, np.clip(p * tile + q, 0, S - 1)] = True
diff[grout] = [118, 100, 80]; rough[grout] = 0.85; nor_h[grout] = 0
diff = np.clip(diff, 0, 255).astype(np.uint8)
cv2.imwrite(os.path.join(D, 'stonetile_diff.jpg'), cv2.cvtColor(diff, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])
cv2.imwrite(os.path.join(D, 'stonetile_rough.jpg'), (rough * 255).astype(np.uint8))
# normal map from a height map with rounded tile edges
h = cv2.GaussianBlur(nor_h, (0, 0), 2.0)
gx = cv2.Sobel(h, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(h, cv2.CV_32F, 0, 1, ksize=3)
nz = np.ones_like(h); nrm = np.dstack([-gx * 2, gy * 2, nz]); nrm /= np.linalg.norm(nrm, axis=2, keepdims=True)
cv2.imwrite(os.path.join(D, 'stonetile_nor.jpg'), cv2.cvtColor(((nrm * 0.5 + 0.5) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))

# ---- rug: move the purple/mauve palette to warm browns, rust and cream
src = os.path.join(D, 'rug_diff_orig.png')
if not os.path.exists(src): os.rename(os.path.join(D, 'rug_diff.png'), src)
im = cv2.imread(src, cv2.IMREAD_UNCHANGED); bgr, a = im[..., :3], im[..., 3]
rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255
lum = rgb @ np.array([0.3, 0.55, 0.15], np.float32)
lo, hi = np.percentile(lum[a > 0], 2), np.percentile(lum[a > 0], 99.5); t = np.clip((lum - lo) / (hi - lo), 0, 1)
# warm palette from the rendered reference: dark chocolate -> rose-brown -> tan -> cream
stops = np.array([0, 0.32, 0.6, 1.0], np.float32)
cols = np.array([[46, 30, 24], [120, 74, 60], [176, 122, 100], [232, 210, 178]], np.float32) / 255
out = np.stack([np.interp(t, stops, cols[:, c]) for c in range(3)], -1)
hsv0 = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
rust = (hsv0[..., 1] > 120) & ((hsv0[..., 0] < 14) | (hsv0[..., 0] > 172))      # keep the rust rings, a little richer
out[rust] = np.clip(rgb[rust] * np.array([1.12, 0.95, 0.85]), 0, 1)
out = cv2.cvtColor((out * 255).astype(np.uint8), cv2.COLOR_RGB2BGR)
cv2.imwrite(os.path.join(D, 'rug_diff.png'), np.dstack([out, a]))
print('ok')
