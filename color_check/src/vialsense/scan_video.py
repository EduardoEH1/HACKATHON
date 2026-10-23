"""Run the liquid finder over a whole video, labeled or not.

Use it on videos 1-4 (no labels), new footage from the line, or digital twin
renders. Saves one reading per --step seconds and a review sheet.

Run from the repo root:
    PYTHONPATH=src python -m vialsense.scan_video --video data/raw/dataset2/vial_fill/videos/vial_fill_video_1.mp4

Outputs (default results/liquid_finder/scan_<video name>/):
  readings.csv       one row per sampled frame
  review_sheet.jpg   evenly spaced frames that contain liquid, with boxes drawn
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from vialsense.find_color import reading
from vialsense.liquid_finder import draw, find_liquid


def scan(video: Path, step: float) -> tuple[pd.DataFrame, list]:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise SystemExit(f"Cannot open video: {video}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    rows, frames = [], []
    for index in range(0, total, max(1, int(round(step * fps)))):
        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = cap.read()
        if not ok:
            break
        rows.append({"video_s": round(index / fps, 2), **reading(frame)})
        frames.append(index)
    return pd.DataFrame(rows), frames


def review_sheet(video: Path, table: pd.DataFrame, output: Path, count: int = 24) -> None:
    liquid = table[table.found_liquid]
    if liquid.empty:
        return
    picks = liquid.iloc[np.linspace(0, len(liquid) - 1, min(count, len(liquid))).astype(int)]
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    tiles = []
    for _, row in picks.iterrows():
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(row.video_s * fps))
        ok, frame = cap.read()
        if not ok:
            continue
        tile = cv2.resize(draw(frame, find_liquid(frame))[30:480, 160:480], (160, 225))
        color = (0, 200, 0) if row.confidence == "high" else (0, 165, 255)
        cv2.rectangle(tile, (0, 0), (160, 22), (0, 0, 0), -1)
        cv2.putText(tile, f"{row.video_s:.0f}s {row.confidence}", (5, 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        tiles.append(tile)
    while len(tiles) % 8:
        tiles.append(np.zeros_like(tiles[0]))
    cv2.imwrite(str(output), cv2.vconcat([cv2.hconcat(tiles[i:i + 8]) for i in range(0, len(tiles), 8)]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--step", type=float, default=1.0, help="seconds between readings")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    out = args.output_dir or Path("results/liquid_finder") / f"scan_{args.video.stem}"
    out.mkdir(parents=True, exist_ok=True)
    table, _ = scan(args.video, args.step)
    table.to_csv(out / "readings.csv", index=False)
    review_sheet(args.video, table, out / "review_sheet.jpg")
    liquid = table[table.found_liquid]
    print(f"{args.video.name}: {len(table)} frames, vial at fill position {table.found_vial.sum()}, "
          f"liquid {len(liquid)} (high {int((liquid.confidence == 'high').sum())}, "
          f"low {int((liquid.confidence == 'low').sum())}). Saved to {out}")


if __name__ == "__main__":
    main()
