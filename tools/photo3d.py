"""Turns each room image into a layered 3D scene for the web game.

For every image it writes, into assets/photo3d/:
  <name>.jpg      the picture (foreground colours)
  <name>_bg.jpg   the picture with foreground objects removed and the background filled in (AI inpainting)
  <name>_d.png    depth: R,G = 16-bit foreground depth, B = 8-bit background depth (0 = near, 1 = far)
The game turns these into two meshes: the foreground, torn apart wherever depth jumps (so objects stand
free of the wall behind them), and the filled-in background behind it.

Usage:  python tools/photo3d.py <image folder> [names...]
Needs:  onnxruntime, opencv-python-headless, numpy, pillow, and depth_anything_v2_vitl.onnx (DA2_MODEL env var).
"""
import os, sys, glob, numpy as np, cv2, onnxruntime as ort

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'assets', 'photo3d'); os.makedirs(OUT, exist_ok=True)
MODEL = os.environ.get('DA2_MODEL', 'depth_anything_v2_vitl.onnx')
sess = ort.InferenceSession(MODEL, providers=['CPUExecutionProvider']); INP = sess.get_inputs()[0].name
MEAN, STD = np.array([0.485, 0.456, 0.406]), np.array([0.229, 0.224, 0.225])

def disparity(rgb):
    """Depth Anything V2 (large), averaged with its mirror image for stable edges. Returns relative disparity (bigger = nearer)."""
    x = cv2.resize(rgb, (518, 518), interpolation=cv2.INTER_CUBIC).astype(np.float32) / 255.0
    x = ((x - MEAN) / STD).transpose(2, 0, 1)[None].astype(np.float32)
    d1 = sess.run(None, {INP: x})[0][0]; d2 = sess.run(None, {INP: x[..., ::-1].copy()})[0][0][:, ::-1]
    return (d1 + d2) / 2

def guided(I, p, r, eps):
    """Edge-aware upsampling: makes depth edges snap to the edges in the photo."""
    mean = lambda a: cv2.boxFilter(a, -1, (2 * r + 1, 2 * r + 1))
    mI, mp = mean(I), mean(p); cov = mean(I * p) - mI * mp; var = mean(I * I) - mI * mI
    a = cov / (var + eps); b = mp - a * mI; return mean(a) * I + mean(b)

def process(path, name):
    bgr = cv2.imread(path); h0, w0 = bgr.shape[:2]
    W = min(1600, w0); H = round(h0 * W / w0); bgr = cv2.resize(bgr, (W, H), interpolation=cv2.INTER_AREA)
    # remove the caption printed in the bottom-left corner of the board images (white capitals)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV); cap = np.zeros((H, W), np.uint8); y0, x1 = int(H * 0.86), int(W * 0.5)
    reg = (hsv[y0:, :x1, 2] > 140) & (hsv[y0:, :x1, 1] < 95); cap[y0:, :x1] = reg.astype(np.uint8) * 255
    if cap.sum() > 0: bgr = cv2.inpaint(bgr, cv2.dilate(cap, np.ones((9, 9), np.uint8)), 7, cv2.INPAINT_TELEA)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    d = disparity(rgb)
    # depth grid used by the game: 384 px wide, edge-aware upsampled from the 518x518 network output
    gw = 384; gh = round(H * gw / W); gray = cv2.cvtColor(cv2.resize(bgr, (gw, gh), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    dd = cv2.resize(d, (gw, gh), interpolation=cv2.INTER_CUBIC); lo, hi = np.percentile(dd, 7), np.percentile(dd, 99.8)   # the far 7% (windows, sky) sits on the back wall; dd = np.clip((dd - lo) / (hi - lo), 0, 1).astype(np.float32)
    dd = np.clip(guided(gray, dd, 4, 1e-3), 0, 1)
    # disparity (1 = near) -> depth fraction (0 = near, 1 = far) with a 1:12 near/far range, typical for a room
    near = 1 / 12.0; z = 1.0 / (dd * (1 / near - 1) + 1); zf = (z - near) / (1 - near)
    # background layer: push every pixel back to the farthest depth around it, then smooth
    k = max(5, gw // 24) | 1
    zb = cv2.dilate(zf, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))); zb = cv2.GaussianBlur(zb, (0, 0), k / 3); zb = np.maximum(zb, zf)
    # what is foreground: clearly nearer than the background around it
    zfull = cv2.resize(zf, (W, H)); zbfull = cv2.resize(zb, (W, H))
    # only the strip just behind each depth edge gets revealed when you walk sideways, so only fill that strip in
    gx = cv2.Sobel(zfull, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(zfull, cv2.CV_32F, 0, 1, ksize=3); edge = (np.hypot(gx, gy) > 0.06).astype(np.uint8)
    band = cv2.dilate(edge, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(W * 0.035) | 1,) * 2))
    occl = (((zbfull - zfull) > 0.05) & (band > 0)).astype(np.uint8) * 255
    # fill in behind the foreground (inpainted at reduced size, then upscaled; detail matters less behind objects)
    s = 640 / W; small = cv2.resize(bgr, (640, round(H * s)), interpolation=cv2.INTER_AREA); m = cv2.resize(occl, (small.shape[1], small.shape[0]), interpolation=cv2.INTER_NEAREST)
    fill = cv2.inpaint(small, m, 5, cv2.INPAINT_NS); fill = cv2.resize(fill, (W, H), interpolation=cv2.INTER_CUBIC)
    bg = np.where(occl[..., None] > 0, fill, bgr)
    cv2.imwrite(os.path.join(OUT, name + '.jpg'), bgr, [cv2.IMWRITE_JPEG_QUALITY, 88, cv2.IMWRITE_JPEG_PROGRESSIVE, 1])
    cv2.imwrite(os.path.join(OUT, name + '_bg.jpg'), cv2.resize(bg, (W // 2, H // 2), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 80])
    q = np.round(zf * 65535).astype(np.uint16)
    png = np.dstack([(q >> 8).astype(np.uint8), (q & 255).astype(np.uint8), np.round(zb * 255).astype(np.uint8)])
    cv2.imwrite(os.path.join(OUT, name + '_d.png'), cv2.cvtColor(png, cv2.COLOR_RGB2BGR))
    print('ok', name, f'{W}x{H}', flush=True)

if __name__ == '__main__':
    src = sys.argv[1]; names = sys.argv[2:] or [os.path.splitext(os.path.basename(f))[0] for f in sorted(glob.glob(os.path.join(src, '*.jpg')))]
    for n in names: process(os.path.join(src, n + '.jpg'), n)
