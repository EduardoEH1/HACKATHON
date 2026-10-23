"""Run the liquid finder on every extracted video frame and save the colors.

Input:  data/derived/video5_frames/ (from extract_video_frames.py)
Output: results/liquid_finder/
  frame_colors.csv   one row per frame, Eduardo's column names (r_mean, h_mean_opencv, ...)
  vial_colors.csv    finished color per vial: median of the last 3 s of the fill
  review_sheet.jpg   end-of-fill frame of all 30 vials with the measured box

Run from the repo root:
    PYTHONPATH=src python -m vialsense.measure_frames
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from vialsense.liquid_finder import draw, find_liquid

COLOR_COLS = ["r_mean", "g_mean", "b_mean", "h_mean_opencv", "s_mean_opencv", "v_mean_opencv"]


def measure_all(frames_dir: Path) -> pd.DataFrame:
    labels = pd.read_csv(frames_dir / "frame_labels.csv")
    rows = []
    for _, row in labels.iterrows():
        det = find_liquid(cv2.imread(str(frames_dir / "images" / row.filename)))
        d = det.to_dict()
        for key in ("block", "tube", "liquid", "roi"):
            box = d.pop(key)
            if key == "roi":
                d.update(dict(zip(["roi_x1", "roi_y1", "roi_x2", "roi_y2"], box or [None] * 4)))
        rows.append({**row.to_dict(), **d})
    return pd.DataFrame(rows)


def vial_colors(frames: pd.DataFrame, last_seconds: float = 3.0) -> pd.DataFrame:
    """Finished color per vial: median over the last few seconds of the fill."""
    out = []
    for vial, g in frames[frames.phase == "fill"].groupby("vial"):
        end = g.video_s.max()
        tail = g[(g.video_s >= end - last_seconds) & g.found_liquid]
        rec = {"vial": vial, "recipe_id": g.recipe_id.iloc[0], "frames_used": len(tail),
               "liquid_height_px": tail.liquid_height_px.median() if len(tail) else np.nan}
        for c in COLOR_COLS:
            rec[c] = round(tail[c].median(), 2) if len(tail) else np.nan
        out.append(rec)
    return pd.DataFrame(out)


def review_sheet(frames: pd.DataFrame, frames_dir: Path, output: Path) -> None:
    tiles = []
    for vial, g in frames[(frames.phase == "fill") & frames.found_liquid].groupby("vial"):
        row = g.iloc[-1]
        image = cv2.imread(str(frames_dir / "images" / row.filename))
        det = find_liquid(image)
        tile = cv2.resize(draw(image, det)[30:480, 160:480], (160, 225))
        cv2.rectangle(tile, (0, 0), (160, 22), (0, 0, 0), -1)
        cv2.putText(tile, f"Vial {vial}  R{row.recipe_id}", (5, 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        tiles.append(tile)
    while len(tiles) % 10:
        tiles.append(np.zeros_like(tiles[0]))
    sheet = cv2.vconcat([cv2.hconcat(tiles[i:i + 10]) for i in range(0, len(tiles), 10)])
    cv2.imwrite(str(output), sheet)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--frames", type=Path, default=Path("data/derived/video5_frames"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/liquid_finder"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    frames = measure_all(args.frames)
    frames.to_csv(args.output_dir / "frame_colors.csv", index=False)
    vials = vial_colors(frames)
    vials.to_csv(args.output_dir / "vial_colors.csv", index=False)
    review_sheet(frames, args.frames, args.output_dir / "review_sheet.jpg")

    fill = frames[frames.phase == "fill"]
    print(f"{len(frames)} frames. Fill frames: vial found {fill.found_vial.sum()}/{len(fill)}, "
          f"liquid found {fill.found_liquid.sum()}/{len(fill)}")
    print(vials[["vial", "recipe_id", "frames_used", "r_mean", "g_mean", "b_mean"]].to_string(index=False))


if __name__ == "__main__":
    main()
