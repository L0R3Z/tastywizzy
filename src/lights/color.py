import colorsys

import numpy as np


def crop_black_bars(img, threshold=16):
    """Retire les bords quasi noirs (bandes de film). Garde l'image si tout est noir."""
    lum = img.max(axis=2)
    rows = np.where(lum.max(axis=1) > threshold)[0]
    cols = np.where(lum.max(axis=0) > threshold)[0]
    if rows.size == 0 or cols.size == 0:
        return img
    return img[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]


def analyze(img):
    """Retourne (h, s, colorfulness, v), tous dans [0,1].
    h : teinte moyenne circulaire pondérée saturation×valeur (None si aucune couleur).
    s : saturation moyenne pondérée. colorfulness : moyenne de saturation×valeur
    (0 = image neutre noir/gris). v : valeur moyenne (luminosité perçue de l'image)."""
    f = img.reshape(-1, 3).astype(np.float32) / 255.0
    mx, mn = f.max(axis=1), f.min(axis=1)
    d = mx - mn
    s = np.where(mx > 0, d / np.maximum(mx, 1e-6), 0)
    r, g, b = f[:, 0], f[:, 1], f[:, 2]
    dd = np.maximum(d, 1e-6)
    h = np.where(mx == r, ((g - b) / dd) % 6, np.where(mx == g, (b - r) / dd + 2, (r - g) / dd + 4)) / 6
    w = s * mx
    total = float(w.sum())
    v = float(mx.mean())
    colorfulness = total / len(w)
    ang = h * 2 * np.pi
    x, y = (w * np.cos(ang)).sum(), (w * np.sin(ang)).sum()
    if total < 1e-6 or x * x + y * y < 1e-12:
        return None, 0.0, colorfulness, v
    return (float(np.arctan2(y, x)) / (2 * np.pi)) % 1.0, float(min(1.0, (w * s).sum() / total)), colorfulness, v


def neutral_factor(colorfulness, low, high):
    """0 = image neutre (blanc chaud), 1 = assez colorée ; progressif entre low et high."""
    return float(min(1.0, max(0.0, (colorfulness - low) / max(high - low, 1e-6))))


def hs_to_rgb(h, s):
    return tuple(round(c * 255) for c in colorsys.hsv_to_rgb(h % 1.0, s, 1.0))
