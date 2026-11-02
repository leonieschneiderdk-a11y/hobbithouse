"""Nursery textures: a fluffy white sheepskin (irregular outline with alpha, soft fur noise)."""
import cv2, numpy as np, os, math
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'rooms', 'nursery'); os.makedirs(D, exist_ok=True)
rng = np.random.default_rng(4); S = 1024
yy, xx = np.mgrid[0:S, 0:S].astype(np.float32) / S - 0.5
ang = np.arctan2(yy, xx); rad = np.hypot(xx * 1.0, yy * 1.35)
edge = 0.42 + 0.03 * np.sin(ang * 5 + 0.5) + 0.02 * np.sin(ang * 11) + 0.04 * np.cos(ang * 2)
for k in range(4):                                          # four 'legs' of the hide
    a = k * math.pi / 2 + math.pi / 4; edge += 0.06 * np.exp(-((np.angle(np.exp(1j * (ang - a)))) / 0.18) ** 2)
fur = cv2.GaussianBlur(rng.normal(0, 1, (S, S)).astype(np.float32), (0, 0), 1.2)
tufts = cv2.GaussianBlur(rng.normal(0, 1, (S, S)).astype(np.float32), (0, 0), 6)
edge_n = edge + 0.012 * fur + 0.01 * tufts
alpha = np.clip((edge_n - rad) * 90, 0, 1)
shade = 0.88 + 0.06 * fur / (np.abs(fur).max() + 1e-6) + 0.08 * tufts / (np.abs(tufts).max() + 1e-6)
col = np.dstack([0.86 * shade, 0.9 * shade, 0.93 * shade])            # BGR warm white
cv2.imwrite(os.path.join(D, 'sheepskin.png'), np.dstack([(np.clip(col, 0, 1) * 255).astype(np.uint8), (alpha * 255).astype(np.uint8)]))
print('ok')
