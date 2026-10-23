"""Find the vial and the liquid in a vial_fill frame, then measure the liquid color.

This is Salah's part of the pipeline:
    frame -> find vial -> find liquid -> measure color -> send to Eduardo's check

How it works
------------
1. Find the vial holder. Each vial sits in a black plastic block. The block is
   the darkest large shape in the upper middle of the frame. When two vials are
   in view, pick the block closest to the fill nozzle.
2. Find the tube. The glass tube hangs below the block, near its center.
3. Find the liquid. Scan the tube row by row from the bottom up. A row counts
   as liquid when its pixels are colorful or dark. Empty glass shows the gray
   conveyor behind it, which is neither. The liquid is the run of liquid rows
   that touches the bottom of the tube.
4. Measure. Average the middle of the liquid column. Skip the top (meniscus,
   falling stream) and the bottom (holder base, reflections). Skip glare.

Output uses Eduardo's column names (r_mean, h_mean_opencv, ...) so his code
reads it directly.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import cv2
import numpy as np

NOZZLE_X = 315          # x pixel of the fill nozzle in the 640x480 view
SEARCH = (150, 140, 520, 330)  # x1, y1, x2, y2 area to look for holder blocks
MIN_BLOCK_AREA = 1200   # pixels; smaller dark shapes are not holder blocks
CHROMA_MIN = 14.0       # LAB chroma above this = colorful pixel
DARK_MAX = 70           # brightness (0-255) below this = dark liquid pixel
LIQUID_ROW_SHARE = 0.6  # share of a row's pixels that must look like liquid
MIN_LIQUID_ROWS = 6     # fewer rows than this = no liquid yet
BLOCK_BOTTOM_MAX = 295  # block bottom edge sits near y=264; lower shapes are conveyor
FILL_X_TOLERANCE = 25   # block center farther than this from NOZZLE_X = vial in motion
FILL_Y_RANGE = (252, 276)  # block bottom edge at the fill position (264 typical); outside = tilted or moving


@dataclass
class Detection:
    found_vial: bool
    found_liquid: bool
    block: tuple[int, int, int, int] | None = None   # x1, y1, x2, y2 of holder block
    tube: tuple[int, int, int, int] | None = None    # area searched for liquid
    liquid: tuple[int, int, int, int] | None = None  # full liquid column
    roi: tuple[int, int, int, int] | None = None     # area actually measured
    liquid_height_px: int = 0
    pixels_used: int = 0
    r_mean: float = float("nan")
    g_mean: float = float("nan")
    b_mean: float = float("nan")
    h_mean_opencv: float = float("nan")
    s_mean_opencv: float = float("nan")
    v_mean_opencv: float = float("nan")
    reason: str = ""
    # "high", or "low" when the reading needs care. confidence_note says why.
    confidence: str = ""
    confidence_note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def find_block(image: np.ndarray) -> tuple[int, int, int, int] | None:
    """Return the holder block closest to the nozzle, or None."""
    x1, y1, x2, y2 = SEARCH
    hsv = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    dark = ((hsv[:, :, 2] < 60) & (hsv[:, :, 1] < 120)).astype(np.uint8) * 255
    # Keep only wide horizontal dark runs. The block is about 120 px wide, the
    # tube under it about 45 px, so dark liquid in the tube gets removed here
    # and no longer merges with the block.
    dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((5, 71), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(dark)
    best, best_dist = None, 1e9
    for i in range(1, count):
        bx, by, bw, bh, area = stats[i]
        # Blocks are wide, short, and mostly solid.
        if area < MIN_BLOCK_AREA or bw < 1.3 * bh or area < 0.5 * bw * bh:
            continue
        # Blocks are 100-140 px wide and sit above the conveyor.
        if not 95 <= bw <= 150 or y1 + by + bh > BLOCK_BOTTOM_MAX:
            continue
        dist = abs(x1 + bx + bw / 2 - NOZZLE_X)
        if dist < best_dist:
            best, best_dist = (x1 + bx, y1 + by, x1 + bx + bw, y1 + by + bh), dist
    return best


def tube_from_block(block: tuple[int, int, int, int], shape) -> tuple[int, int, int, int]:
    """Tube area below the block. Proportions measured on Dataset 2 frames."""
    bx1, _, bx2, by2 = block
    width = bx2 - bx1
    center = bx1 + 0.42 * width
    half = 0.14 * width
    top = by2 + 4
    bottom = min(int(by2 + 1.15 * width), shape[0] - 1)
    return int(center - half), int(top), int(center + half), int(bottom)


def liquid_rows(tube_img: np.ndarray) -> np.ndarray:
    """Boolean per row: does this row look like liquid?"""
    lab = cv2.cvtColor(tube_img, cv2.COLOR_BGR2LAB).astype(np.float32)
    chroma = np.hypot(lab[:, :, 1] - 128, lab[:, :, 2] - 128)
    value = tube_img.max(axis=2)
    liquid_px = (chroma > CHROMA_MIN) | (value < DARK_MAX)
    return liquid_px.mean(axis=1) >= LIQUID_ROW_SHARE


def bottom_run(rows: np.ndarray, gap: int = 3) -> tuple[int, int] | None:
    """Longest run of liquid rows that reaches near the bottom. Allows small gaps."""
    n = len(rows)
    # Start from the lowest liquid row within the bottom quarter.
    candidates = np.where(rows[int(n * 0.75):])[0]
    if len(candidates) == 0:
        return None
    end = int(n * 0.75) + candidates[-1]
    start, misses = end, 0
    for y in range(end, -1, -1):
        if rows[y]:
            start, misses = y, 0
        else:
            misses += 1
            if misses > gap:
                break
    return start, end


def find_liquid(image: np.ndarray) -> Detection:
    block = find_block(image)
    if block is None:
        return Detection(False, False, reason="no holder block near the nozzle")
    if (abs((block[0] + block[2]) / 2 - NOZZLE_X) > FILL_X_TOLERANCE
            or not FILL_Y_RANGE[0] <= block[3] <= FILL_Y_RANGE[1]):
        return Detection(False, False, block, reason="vial moving, not at fill position")
    tube = tube_from_block(block, image.shape)
    tx1, ty1, tx2, ty2 = tube
    run = bottom_run(liquid_rows(image[ty1:ty2, tx1:tx2]))
    if run is None or run[1] - run[0] + 1 < MIN_LIQUID_ROWS:
        return Detection(True, False, block, tube, reason="no liquid column in the tube")

    top, bottom = ty1 + run[0], ty1 + run[1]
    height = bottom - top + 1
    # Measure the middle: drop the top 20% and the bottom 15% of the column.
    my1 = top + int(0.20 * height)
    my2 = bottom - int(0.15 * height)
    if my2 - my1 < 3:
        my1, my2 = top, bottom
    crop = image[my1:my2 + 1, tx1:tx2].reshape(-1, 3).astype(np.float32)
    glare = (crop.min(axis=1) > 200)
    keep = crop[~glare] if (~glare).sum() >= 20 else crop
    b, g, r = keep.mean(axis=0)
    hsv = cv2.cvtColor(keep.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.float32)
    h, s, v = hsv.mean(axis=0)
    confidence, note = rate_confidence(int(height), (r, g, b))
    return Detection(True, True, block, tube, (tx1, top, tx2, bottom), (tx1, my1, tx2, my2),
                     int(height), int(len(keep)), float(r), float(g), float(b),
                     float(h), float(s), float(v), confidence=confidence, confidence_note=note)


PALE_BRIGHT_MIN = 75    # pale readings are bright (max channel above this)
PALE_RG_GAP = 10        # ...with red and green nearly equal (yellowish gray)
SHORT_COLUMN_PX = 15    # a column this short is mostly the tube bottom


def rate_confidence(height: int, rgb) -> tuple[str, str]:
    """Flag readings that need care.

    Tested on videos 1-4: pale, mostly clear liquid looks almost like the empty
    tube with the conveyor behind it, a bright yellowish gray. The finder then
    sees only part of the column, so the liquid level is too low. The color is
    still the liquid's, but from a small area.
    """
    r, g, b = (float(c) for c in rgb)
    if max(r, g, b) > PALE_BRIGHT_MIN and abs(r - g) < PALE_RG_GAP and b < g:
        return "low", "pale liquid: looks like an empty tube, liquid level not reliable"
    if height < SHORT_COLUMN_PX:
        return "low", "short column: reading taken from the tube bottom"
    return "high", ""


def draw(image: np.ndarray, det: Detection, label: str = "") -> np.ndarray:
    """Copy of the frame with block (yellow), liquid (cyan), and measured area (red)."""
    out = image.copy()
    if det.block:
        cv2.rectangle(out, det.block[:2], det.block[2:], (0, 220, 255), 2)
    if det.liquid:
        cv2.rectangle(out, det.liquid[:2], det.liquid[2:], (255, 255, 0), 1)
    if det.roi:
        cv2.rectangle(out, det.roi[:2], det.roi[2:], (0, 0, 255), 2)
    text = label or (f"liquid {det.liquid_height_px}px" if det.found_liquid else det.reason)
    cv2.rectangle(out, (0, 0), (640, 28), (0, 0, 0), -1)
    cv2.putText(out, text, (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    if det.found_liquid:
        swatch = (int(det.b_mean), int(det.g_mean), int(det.r_mean))
        cv2.rectangle(out, (580, 2), (636, 26), swatch, -1)
    return out
