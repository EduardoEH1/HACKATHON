"""Measured color from manually reviewed regions of interest (ROI)."""

from pathlib import Path

import cv2
import numpy as np


def measure_roi(image_path: Path, roi: tuple[int, int, int, int]) -> dict[str, float]:
    """Return RGB and OpenCV HSV means for rectangle (x1, y1, x2, y2)."""
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot read image: {image_path}")
    x1, y1, x2, y2 = roi
    if not (0 <= x1 < x2 <= image.shape[1] and 0 <= y1 < y2 <= image.shape[0]):
        raise ValueError(f"ROI outside image bounds: {roi}")
    crop = image[y1:y2, x1:x2]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    b, g, r = crop.astype(np.float64).mean(axis=(0, 1))
    h, s, v = hsv.astype(np.float64).mean(axis=(0, 1))
    return {"r_mean": r, "g_mean": g, "b_mean": b,
            "h_mean_opencv": h, "s_mean_opencv": s, "v_mean_opencv": v,
            "roi_pixels": int(crop.shape[0] * crop.shape[1])}


def save_roi_example(image_path: Path, roi: tuple[int, int, int, int], output: Path) -> None:
    """Save a review image with the exact measured rectangle drawn in red."""
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot read image: {image_path}")
    x1, y1, x2, y2 = roi
    cv2.rectangle(image, (x1, y1), (x2, y2), (0, 0, 255), 2)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), image):
        raise OSError(f"Could not write ROI example: {output}")
