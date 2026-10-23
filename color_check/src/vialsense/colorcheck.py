"""Core color check: measure liquid color, compare to the recipe, decide PASS or FLAG.

Plain-language summary
----------------------
1. measure_liquid()  -> average color of the liquid pixels inside a box (ROI).
2. rgb_to_lab()      -> convert that color to LAB, a color space built to match
                        how people see color differences.
3. delta_e_2000()    -> one number for "how different are two colors".
                        About 1 = barely visible. Above 10 = clearly different.
4. check_color()     -> compare the measured color to the recipe's expected color
                        and return PASS or FLAG.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# Default ROI from Eduardo's work: (x1, y1, x2, y2) in the 640x480 camera view.
DEFAULT_ROI = (304, 384, 328, 400)

# Lighting and liquid depth change brightness more than hue. kL=2 makes
# brightness count half as much as hue and saturation in the score.
DEFAULT_KL = 2.0

# First-pass limit. Tuned on Dataset 2 in check_batch.py. Not a validated limit.
DEFAULT_THRESHOLD = 8.0


# ---------------------------------------------------------------------------
# 1. Color conversion
# ---------------------------------------------------------------------------
def rgb_to_lab(rgb: tuple[float, float, float] | np.ndarray) -> np.ndarray:
    """Convert sRGB (0-255) to CIE LAB (D65 white). Works on one color or many."""
    rgb = np.asarray(rgb, dtype=np.float64) / 255.0
    # Undo the sRGB gamma curve to get linear light.
    linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    # Linear RGB -> XYZ (standard sRGB matrix).
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = linear @ m.T
    xyz = xyz / np.array([0.95047, 1.0, 1.08883])  # divide by D65 white point
    eps, kappa = 216 / 24389, 24389 / 27
    f = np.where(xyz > eps, np.cbrt(xyz), (kappa * xyz + 16) / 116)
    l = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([l, a, b], axis=-1)


# ---------------------------------------------------------------------------
# 2. Color difference (CIEDE2000, the industry standard formula)
# ---------------------------------------------------------------------------
def delta_e_2000(lab1, lab2, k_l: float = 1.0, k_c: float = 1.0, k_h: float = 1.0) -> float:
    """Return the CIEDE2000 difference between two LAB colors."""
    l1, a1, b1 = (float(v) for v in lab1)
    l2, a2, b2 = (float(v) for v in lab2)

    c1, c2 = np.hypot(a1, b1), np.hypot(a2, b2)
    c_bar = (c1 + c2) / 2
    g = 0.5 * (1 - np.sqrt(c_bar**7 / (c_bar**7 + 25**7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360

    d_lp = l2 - l1
    d_cp = c2p - c1p
    if c1p * c2p == 0:
        d_hp = 0.0
    elif abs(h2p - h1p) <= 180:
        d_hp = h2p - h1p
    elif h2p - h1p > 180:
        d_hp = h2p - h1p - 360
    else:
        d_hp = h2p - h1p + 360
    d_hp_big = 2 * np.sqrt(c1p * c2p) * np.sin(np.radians(d_hp / 2))

    l_bar_p = (l1 + l2) / 2
    c_bar_p = (c1p + c2p) / 2
    if c1p * c2p == 0:
        h_bar_p = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        h_bar_p = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        h_bar_p = (h1p + h2p + 360) / 2
    else:
        h_bar_p = (h1p + h2p - 360) / 2

    t = (1 - 0.17 * np.cos(np.radians(h_bar_p - 30))
         + 0.24 * np.cos(np.radians(2 * h_bar_p))
         + 0.32 * np.cos(np.radians(3 * h_bar_p + 6))
         - 0.20 * np.cos(np.radians(4 * h_bar_p - 63)))
    d_theta = 30 * np.exp(-(((h_bar_p - 275) / 25) ** 2))
    r_c = 2 * np.sqrt(c_bar_p**7 / (c_bar_p**7 + 25**7))
    s_l = 1 + (0.015 * (l_bar_p - 50) ** 2) / np.sqrt(20 + (l_bar_p - 50) ** 2)
    s_c = 1 + 0.045 * c_bar_p
    s_h = 1 + 0.015 * c_bar_p * t
    r_t = -np.sin(np.radians(2 * d_theta)) * r_c

    return float(np.sqrt(
        (d_lp / (k_l * s_l)) ** 2
        + (d_cp / (k_c * s_c)) ** 2
        + (d_hp_big / (k_h * s_h)) ** 2
        + r_t * (d_cp / (k_c * s_c)) * (d_hp_big / (k_h * s_h))
    ))


# ---------------------------------------------------------------------------
# 3. Measure the liquid in a photo
# ---------------------------------------------------------------------------
def measure_liquid(image: np.ndarray, roi: tuple[int, int, int, int] = DEFAULT_ROI) -> dict:
    """Average RGB of usable liquid pixels inside the ROI.

    Skips glare (very bright, washed-out pixels) and near-black pixels, which
    carry no color. Falls back to all pixels if the filter removes too many.
    """
    x1, y1, x2, y2 = roi
    h, w = image.shape[:2]
    if not (0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h):
        raise ValueError(f"ROI {roi} is outside the {w}x{h} image")
    crop = image[y1:y2, x1:x2].reshape(-1, 3).astype(np.float64)  # BGR order
    brightest = crop.max(axis=1)
    darkest = crop.min(axis=1)
    glare = (brightest > 240) & (darkest > 200)
    black = brightest < 8
    keep = ~(glare | black)
    if keep.sum() < 0.25 * len(crop):
        keep = np.ones(len(crop), dtype=bool)
    b, g, r = crop[keep].mean(axis=0)
    return {"r": r, "g": g, "b": b, "pixels_used": int(keep.sum()), "roi_pixels": len(crop)}


def load_image(path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot read image: {path}")
    return image


# ---------------------------------------------------------------------------
# 4. Decide PASS or FLAG
# ---------------------------------------------------------------------------
@dataclass
class CheckResult:
    recipe_id: int
    measured_rgb: tuple[float, float, float]
    expected_rgb: tuple[float, float, float]
    delta_e: float
    threshold: float
    status: str                 # "PASS" or "FLAG"
    note: str = ""              # extra hint, e.g. "looks like previous recipe"

    def line(self, label: str = "") -> str:
        m = "/".join(f"{v:.0f}" for v in self.measured_rgb)
        e = "/".join(f"{v:.0f}" for v in self.expected_rgb)
        text = (f"Recipe {self.recipe_id}{' | ' + label if label else ''} | "
                f"Seen RGB {m} | Expected RGB {e} | Score {self.delta_e:.1f} "
                f"(limit {self.threshold:.0f}) | {self.status}")
        return text + (f" | {self.note}" if self.note else "")


def check_color(measured_rgb, recipe_id: int, references: dict,
                threshold: float = DEFAULT_THRESHOLD, k_l: float = DEFAULT_KL) -> CheckResult:
    """Compare a measured RGB color to the recipe's expected color.

    references: {recipe_id: {"rgb": (r, g, b), "previous_recipe": id or None}}
    """
    if recipe_id not in references:
        raise KeyError(f"No reference color for recipe {recipe_id}")
    ref = references[recipe_id]
    measured_lab = rgb_to_lab(measured_rgb)
    score = delta_e_2000(measured_lab, rgb_to_lab(ref["rgb"]), k_l=k_l)
    status = "PASS" if score <= threshold else "FLAG"

    note = ""
    prev = ref.get("previous_recipe")
    if status == "FLAG" and prev in references:
        prev_score = delta_e_2000(measured_lab, rgb_to_lab(references[prev]["rgb"]), k_l=k_l)
        if prev_score < score:
            note = f"closer to previous recipe {prev} (score {prev_score:.1f}): possible carryover"

    return CheckResult(recipe_id, tuple(float(v) for v in measured_rgb),
                       tuple(float(v) for v in ref["rgb"]), score, threshold, status, note)
