"""One frame in, liquid color out. The entry point for live use.

Three ways to give it a frame:

    # a photo
    python -m vialsense.find_color --image path/to/frame.jpg

    # one moment of a video (seconds)
    python -m vialsense.find_color --video path/to/video.mp4 --time 309

    # a live camera (0 = first camera), one reading per second until Ctrl+C
    python -m vialsense.find_color --camera 0

Each reading prints one JSON line, for example:
    {"found_vial": true, "found_liquid": true, "r_mean": 15.3, "g_mean": 28.2,
     "b_mean": 22.1, "h_mean_opencv": ..., "confidence": "high", ...}

From Python (for Lorena's integration):
    import cv2
    from vialsense.liquid_finder import find_liquid
    frame = cv2.imread("frame.jpg")      # or a frame from cv2.VideoCapture
    result = find_liquid(frame)
    if result.found_liquid:
        print(result.r_mean, result.g_mean, result.b_mean, result.confidence)
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2

from vialsense.liquid_finder import draw, find_liquid


def reading(frame) -> dict:
    det = find_liquid(frame)
    out = det.to_dict()
    for key, value in out.items():
        if isinstance(value, float):
            out[key] = None if value != value else round(value, 2)  # NaN -> null
        elif isinstance(value, tuple):
            out[key] = [int(v) for v in value]
    return out


def read_video_frame(path: Path, seconds: float):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise SystemExit(f"Cannot open video: {path}")
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(seconds * cap.get(cv2.CAP_PROP_FPS)))
    ok, frame = cap.read()
    if not ok:
        raise SystemExit(f"No frame at {seconds} s in {path}")
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", type=Path)
    source.add_argument("--video", type=Path)
    source.add_argument("--camera", type=int)
    parser.add_argument("--time", type=float, default=0.0, help="seconds into --video")
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between --camera readings")
    parser.add_argument("--save-preview", type=Path, help="save the frame with boxes drawn (image/video only)")
    args = parser.parse_args()

    if args.camera is not None:
        cap = cv2.VideoCapture(args.camera)
        if not cap.isOpened():
            raise SystemExit(f"Cannot open camera {args.camera}")
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    raise SystemExit("Camera stopped sending frames")
                print(json.dumps({"time": round(time.time(), 2), **reading(frame)}), flush=True)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            return

    if args.image:
        frame = cv2.imread(str(args.image))
        if frame is None:
            raise SystemExit(f"Cannot read image: {args.image}")
    else:
        frame = read_video_frame(args.video, args.time)
    print(json.dumps(reading(frame)))
    if args.save_preview:
        args.save_preview.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(args.save_preview), draw(frame, find_liquid(frame)))


if __name__ == "__main__":
    main()
