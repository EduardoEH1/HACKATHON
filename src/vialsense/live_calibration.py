"""Map any camera view onto the view the liquid finder was tuned on.

The liquid finder expects Dataset 2's vial_fill camera: 640x480, with the
holder block of the vial under the nozzle centered near x=316 and its bottom
edge near y=264. A different resolution, zoom, or camera position breaks those
fixed pixel positions.

Calibration finds the holder block in one frame from the new camera and
computes a scale and shift that moves it to the reference position. Every
live frame then goes through the same transform before the finder sees it.

    PYTHONPATH=src python -m vialsense.live_cli calibrate --camera 0

Check the saved calibration image before trusting it. If the wrong block was
picked, pass the block yourself with --holder CENTER_X BOTTOM_Y WIDTH (pixels
in the 640x480-resized frame).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

FRAME_SIZE = (640, 480)
REF_CENTER_X = 316.0   # holder block center x in the reference view
REF_BOTTOM_Y = 264.0   # holder block bottom edge y in the reference view
REF_WIDTH = 116.0      # holder block width in the reference view


@dataclass
class Calibration:
    scale: float = 1.0
    shift_x: float = 0.0
    shift_y: float = 0.0
    source_size: tuple[int, int] | None = None   # (width, height) of the camera frames
    holder: tuple[float, float, float] | None = None  # center_x, bottom_y, width found in the resized frame

    def matrix(self) -> np.ndarray:
        return np.array([[self.scale, 0.0, self.shift_x],
                         [0.0, self.scale, self.shift_y]], dtype=np.float32)

    def is_identity(self) -> bool:
        return abs(self.scale - 1) < 1e-6 and abs(self.shift_x) < 1e-6 and abs(self.shift_y) < 1e-6

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Calibration":
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in ("source_size", "holder"):
            if data.get(key) is not None:
                data[key] = tuple(data[key])
        return cls(**data)


def to_frame_size(frame: np.ndarray) -> np.ndarray:
    """Resize any camera frame to 640x480, the size the finder was tuned on."""
    if frame.shape[1] == FRAME_SIZE[0] and frame.shape[0] == FRAME_SIZE[1]:
        return frame
    return cv2.resize(frame, FRAME_SIZE, interpolation=cv2.INTER_AREA)


def prepare(frame: np.ndarray, calibration: Calibration | None) -> np.ndarray:
    """Resize, then apply the calibration transform."""
    frame = to_frame_size(frame)
    if calibration is None or calibration.is_identity():
        return frame
    return cv2.warpAffine(frame, calibration.matrix(), FRAME_SIZE,
                          flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def find_holder_candidates(frame: np.ndarray) -> list[tuple[float, float, float, float]]:
    """Dark, wide, solid shapes anywhere in the frame: (center_x, bottom_y, width, area)."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    dark = ((hsv[:, :, 2] < 60) & (hsv[:, :, 1] < 120)).astype(np.uint8) * 255
    dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((5, 41), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(dark)
    out = []
    for i in range(1, count):
        x, y, w, h, area = stats[i]
        if area < 600 or w < 40 or w > 320 or w < 1.3 * h or area < 0.5 * w * h:
            continue
        if y + h > 0.85 * frame.shape[0]:   # conveyor and machine base, not a holder
            continue
        out.append((x + w / 2, float(y + h), float(w), float(area)))
    return out


def calibrate(frame: np.ndarray, holder: tuple[float, float, float] | None = None) -> Calibration:
    """Compute the transform that moves the fill-position holder to the reference spot.

    holder: (center_x, bottom_y, width) in the 640x480-resized frame, to skip auto-detection.
    Auto-detection picks the holder closest to the reference position.
    """
    source_size = (int(frame.shape[1]), int(frame.shape[0]))
    small = to_frame_size(frame)
    if holder is None:
        candidates = find_holder_candidates(small)
        if not candidates:
            raise ValueError("No holder block found. Put a vial under the nozzle, or pass --holder.")
        holder = min(candidates, key=lambda c: np.hypot(c[0] - REF_CENTER_X, c[1] - REF_BOTTOM_Y))[:3]
    center_x, bottom_y, width = (float(v) for v in holder)
    scale = REF_WIDTH / width
    # Same camera as Dataset 2: leave frames untouched.
    if abs(scale - 1) < 0.04 and abs(center_x - REF_CENTER_X) < 8 and abs(bottom_y - REF_BOTTOM_Y) < 8:
        return Calibration(source_size=source_size, holder=(center_x, bottom_y, width))
    return Calibration(scale=round(scale, 5),
                       shift_x=round(REF_CENTER_X - scale * center_x, 3),
                       shift_y=round(REF_BOTTOM_Y - scale * bottom_y, 3),
                       source_size=source_size, holder=(center_x, bottom_y, width))


def calibration_preview(frame: np.ndarray, calibration: Calibration) -> np.ndarray:
    """Side by side: camera view with the chosen holder, and the corrected view."""
    small = to_frame_size(frame).copy()
    if calibration.holder:
        cx, by, w = calibration.holder
        cv2.rectangle(small, (int(cx - w / 2), int(by - 0.55 * w)), (int(cx + w / 2), int(by)), (0, 220, 255), 2)
    fixed = prepare(frame, calibration).copy()
    cv2.rectangle(fixed, (int(REF_CENTER_X - REF_WIDTH / 2), int(REF_BOTTOM_Y - 0.55 * REF_WIDTH)),
                  (int(REF_CENTER_X + REF_WIDTH / 2), int(REF_BOTTOM_Y)), (0, 220, 255), 2)
    for image, text in ((small, "Camera: holder picked (yellow)"), (fixed, "Corrected: holder must sit in yellow box")):
        cv2.rectangle(image, (0, 0), (640, 28), (0, 0, 0), -1)
        cv2.putText(image, text, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    return cv2.hconcat([small, fixed])
