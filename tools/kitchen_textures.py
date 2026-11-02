"""Textures for the kitchen: the alpine view outside the windows, the grey-brown marble island top, the Persian runner,
the rush weave for the stool seats, and leaf cards for trailing plants."""
import cv2, numpy as np, os, math
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'rooms', 'kitchen'); os.makedirs(D, exist_ok=True)
rng = np.random.default_rng(3)

def fbm1d(n, octaves=8, rough=0.55, seed=0):
    r = np.random.default_rng(seed); out = np.zeros(n); amp = 1.0; f = 2
    for _ in range(octaves):
        pts = r.uniform(-1, 1, f + 1); out += amp * np.interp(np.linspace(0, f, n), np.arange(f + 1), pts); amp *= rough; f *= 2
    return out

def noise2(h, w, scale, seed):
    r = np.random.default_rng(seed); s = r.normal(0, 1, (max(2, h // scale), max(2, w // scale))).astype(np.float32)
    return cv2.resize(s, (w, h), interpolation=cv2.INTER_CUBIC)

def fbm2(h, w, base=256, oct=6, seed=0):
    out = np.zeros((h, w), np.float32); a = 1.0; s = base
    for i in range(oct): out += a * noise2(h, w, max(2, s), seed + i); a *= 0.5; s //= 2
    return out / 2

# ---------------------------------------------------------------- alpine view
W, H = 3000, 1300
y = np.linspace(0, 1, H)[:, None]; x = np.linspace(0, 1, W)[None, :]
sky_top, sky_hor = np.array([0.42, 0.58, 0.80]), np.array([0.86, 0.90, 0.95])
img = (sky_top * (1 - y[..., None] / 0.55) + sky_hor * (y[..., None] / 0.55)).clip(0, 1) * np.ones((H, W, 3))
cl = fbm2(H, W, 400, 6, 50); cl = np.clip((cl - 0.25) * 2.2, 0, 1) * np.clip(1 - y / 0.45, 0, 1)
img = img * (1 - cl[..., None] * 0.6) + np.array([0.98, 0.96, 0.94]) * cl[..., None] * 0.6
def layer(img, ridge, colour, haze, snow=None, tex_seed=1, tex_amp=0.08):
    m = (np.arange(H)[:, None] >= ridge[None, :] * H)
    depth = (np.arange(H)[:, None] - ridge[None, :] * H) / H
    t = fbm2(H, W, 16, 4, tex_seed); col = np.array(colour)[None, None, :] * (1 + tex_amp * t[..., None])
    if snow is not None:
        rock = fbm2(H, W, 24, 5, tex_seed + 9)
        sn = np.clip((snow - depth * 9.0 + rock * 0.9 - 0.15) * 2.5, 0, 1) * np.clip(1 - depth * 6, 0, 1)
        gx = np.gradient(rock, axis=1); shade = np.clip(0.85 + gx * 25, 0.55, 1.15)
        col = col * (1 - sn[..., None]) + np.array([0.95, 0.96, 0.99]) * shade[..., None] * sn[..., None]
    col = col * (1 - haze) + sky_hor * haze
    img[m] = col[m]; return img
peaks = 0.36 - 0.17 * np.abs(fbm1d(W, 9, 0.52, 4)) - 0.10 * np.exp(-((np.linspace(0, 1, W) - 0.3) / 0.12) ** 2) - 0.08 * np.exp(-((np.linspace(0, 1, W) - 0.74) / 0.1) ** 2)
img = layer(img, peaks, (0.36, 0.42, 0.52), 0.30, snow=0.85, tex_seed=10, tex_amp=0.25)
img = layer(img, 0.47 - 0.07 * np.abs(fbm1d(W, 8, 0.5, 7)), (0.24, 0.32, 0.30), 0.35, snow=0.15, tex_seed=20, tex_amp=0.2)
img = layer(img, 0.55 - 0.05 * fbm1d(W, 8, 0.55, 9), (0.16, 0.26, 0.15), 0.2, tex_seed=30, tex_amp=0.35)       # forested hills
img = layer(img, 0.63 - 0.025 * fbm1d(W, 6, 0.5, 11), (0.30, 0.44, 0.17), 0.08, tex_seed=40, tex_amp=0.12)      # meadow
# a few dark conifers on the meadow edge
for i in range(260):
    cx = rng.integers(0, W); base = int((0.63 - 0.025 * 0) * H + rng.integers(-10, 120)); hgt = int(rng.uniform(18, 70) * (1 + (base - 0.63 * H) / 300))
    pts = np.array([[cx, base - hgt], [cx - hgt // 4, base], [cx + hgt // 4, base]], np.int32)
    cv2.fillPoly(img, [pts], tuple(float(c) for c in np.array([0.08, 0.16, 0.09]) * rng.uniform(0.8, 1.3)))
img = np.clip(img, 0, 1); cv2.imwrite(os.path.join(D, 'view.jpg'), cv2.cvtColor((img * 255).astype(np.uint8), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])

# ---------------------------------------------------------------- marble island top (grey-brown, soft veins)
S = 1024
t = fbm2(S, S, 256, 7, 70); u = np.linspace(0, 1, S)[None, :] * 6 + np.linspace(0, 1, S)[:, None] * 2.5
veins = np.abs(np.sin((u + t * 3.2) * math.pi)) ** 0.25
fine = np.abs(np.sin((u * 3 + fbm2(S, S, 128, 6, 80) * 5) * math.pi)) ** 0.15
base = np.array([0.50, 0.46, 0.41]) * (1 + 0.12 * fbm2(S, S, 128, 5, 90))[..., None]
m = base * (0.80 + 0.20 * veins[..., None]) * (0.97 + 0.03 * fine[..., None])
m += np.array([0.12, 0.11, 0.10]) * np.clip(1 - veins, 0, 1)[..., None] ** 6
cv2.imwrite(os.path.join(D, 'marble_diff.jpg'), cv2.cvtColor((np.clip(m, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
cv2.imwrite(os.path.join(D, 'marble_rough.jpg'), (np.clip(0.12 + 0.08 * (1 - veins), 0, 1) * 255).astype(np.uint8))

# ---------------------------------------------------------------- Persian runner (red-brown field, medallions, borders)
RW, RH = 512, 1536
yy, xx = np.mgrid[0:RH, 0:RW].astype(np.float32); u = xx / RW; v = yy / RH
red, dred, navy, cream, gold, brown = [np.array(c) / 255 for c in ((140, 38, 30), (92, 24, 22), (40, 36, 52), (214, 190, 150), (186, 128, 62), (70, 40, 28))]
rug = np.ones((RH, RW, 3)) * red
bx = np.minimum(np.minimum(xx, RW - 1 - xx), np.minimum(yy, RH - 1 - yy))
def band(a, b): return (bx >= a) & (bx < b)
rug[band(0, 14)] = dred; rug[band(14, 20)] = cream; rug[band(20, 60)] = navy; rug[band(60, 66)] = cream; rug[band(66, 74)] = dred
# border motifs: repeating rosettes in the navy band
for k in range(0, RH, 46):
    for cx in (40, RW - 40): cv2.circle(rug, (cx, k + 23), 12, tuple(gold), -1); cv2.circle(rug, (cx, k + 23), 6, tuple(red), -1)
for k in range(0, RW, 46):
    for cy in (40, RH - 40): cv2.circle(rug, (k + 23, cy), 12, tuple(gold), -1); cv2.circle(rug, (k + 23, cy), 6, tuple(red), -1)
# field: lattice of small diamonds and flowers
field = bx >= 74
lat = (np.abs(((xx - 74) % 56) - 28) + np.abs(((yy - 74) % 56) - 28)) < 6
rug[field & lat] = dred
for cy in range(110, RH - 100, 56):
    for cx in range(102, RW - 90, 56): cv2.circle(rug, (cx, cy), 5, tuple(cream * 0.9), -1)
# three medallions down the length
for cy in (RH * 0.22, RH * 0.5, RH * 0.78):
    d = np.abs(xx - RW / 2) / 150 + np.abs(yy - cy) / 210
    rug[(d < 1.0)] = navy; rug[(d < 0.86)] = dred; rug[(d < 0.7) & (d > 0.62)] = gold; rug[(d < 0.45)] = red; rug[(d < 0.2)] = gold; rug[(d < 0.1)] = navy
    ang = np.arctan2(yy - cy, xx - RW / 2); petals = (np.abs(np.sin(ang * 6)) > 0.75) & (d < 0.6) & (d > 0.48)
    rug[petals] = cream
wool = 1 + 0.10 * fbm2(RH, RW, 8, 3, 101)[..., None] + 0.05 * rng.normal(0, 1, (RH, RW, 1)); wear = 1 - 0.12 * np.clip(fbm2(RH, RW, 128, 4, 102), 0, 1)[..., None]
rug = np.clip(rug * wool * wear, 0, 1)
cv2.imwrite(os.path.join(D, 'runner_diff.jpg'), cv2.cvtColor((rug * 255).astype(np.uint8), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])

# ---------------------------------------------------------------- rush seat weave
S = 512; yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
a = (np.sin(xx / S * 2 * math.pi * 24) * 0.5 + 0.5); b = (np.sin(yy / S * 2 * math.pi * 24) * 0.5 + 0.5)
chk = (((xx // (S / 12)) + (yy // (S / 12))) % 2).astype(bool)
strand = np.where(chk, a, b) ** 0.6
col = np.array([0.55, 0.40, 0.22]) * (0.55 + 0.45 * strand[..., None]) * (1 + 0.08 * fbm2(S, S, 16, 3, 120)[..., None])
cv2.imwrite(os.path.join(D, 'rush_diff.jpg'), cv2.cvtColor((np.clip(col, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
print('textures ok')
