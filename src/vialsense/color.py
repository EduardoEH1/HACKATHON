"""Conservative color measurement helpers for vial-fill frames."""

import cv2
import numpy as np


def locate_vial_column(image: np.ndarray) -> tuple[int, int] | None:
    """Locate the active vial by finding the strongest liquid-colored column.

    Dataset 2 Recipe 6 liquid appears orange/brown in the visible lower vial.
    Search the two observed vial lanes only; require a compact region of colored
    pixels. This is a simple heuristic and returns None when evidence is weak.
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # Orange/brown pixels: broad color range accommodates the darker first vial.
    mask = cv2.inRange(hsv, np.array([5, 45, 25]), np.array([32, 255, 230]))
    h, w = image.shape[:2]
    best = None
    for x1, x2 in ((int(w * .43), int(w * .56)), (int(w * .69), int(w * .83))):
        # Restrict to lower vial body, below its label and above the holder.
        roi = mask[int(h * .48):int(h * .84), x1:x2]
        count = cv2.countNonZero(roi)
        if best is None or count > best[0]:
            best = (count, (x1, x2))
    if best is None or best[0] < 80:
        return None
    return best[1]


def measure_frame(image_path: str) -> dict[str, float]:
    """Measure mean RGB/HSV only on liquid-colored pixels in the detected vial."""
    image = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"OpenCV could not read image: {image_path}")
    column = locate_vial_column(image)
    if column is None:
        raise ValueError(f"No sufficiently visible liquid found: {image_path}")
    x1, x2 = column
    y1, y2 = int(image.shape[0] * .48), int(image.shape[0] * .84)
    roi = image[y1:y2, x1:x2]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    # Keep saturated, non-extreme-brightness pixels so clear plastic/background
    # and strong highlights do not dominate the color average.
    valid = (hsv[:, :, 1] >= 45) & (hsv[:, :, 2] >= 25) & (hsv[:, :, 2] <= 230)
    if not np.any(valid):
        raise ValueError(f"No usable pixels in central ROI: {image_path}")
    bgr = roi[valid].astype(np.float32)
    hsv_values = hsv[valid].astype(np.float32)
    b, g, r = bgr.mean(axis=0)
    h, s, v = hsv_values.mean(axis=0)
    return {"pixels_used": int(valid.sum()), "roi_pixels": int(valid.size),
            "roi_x1": x1, "roi_x2": x2, "roi_y1": y1, "roi_y2": y2,
            "r_mean": float(r), "g_mean": float(g), "b_mean": float(b),
            "h_mean_opencv": float(h), "s_mean_opencv": float(s), "v_mean_opencv": float(v)}
