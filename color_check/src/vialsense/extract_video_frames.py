"""Pull correctly labeled frames for every vial straight from the video.

The video and the vial fill windows share one clock, so frames taken from the
video by time always carry the right vial and recipe. This also covers
Vials 25-30, which have no matching stills.

For each vial, saves one frame every --step seconds inside its fill window,
plus a few frames after the fill ends (before the vial leaves), which show
the finished color.

Run from the repo root:
    PYTHONPATH=src python -m vialsense.extract_video_frames --data data/raw/dataset2/vial_fill
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


def extract(data: Path, out_dir: Path, step: float, after: float) -> pd.DataFrame:
    vials = pd.read_csv(data / "labels" / "video5_vial_recipes.csv")
    cap = cv2.VideoCapture(str(data / "videos" / "vial_fill_video_5.mp4"))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    img_dir = out_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for _, v in vials.iterrows():
        times = np.append(np.arange(v.start_s, v.end_s, step), [v.end_s])
        times = np.append(times, np.arange(v.end_s + 1, v.end_s + after + 0.01, 1.0))
        for t in times:
            index = min(int(round(t * fps)), total - 1)
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = cap.read()
            if not ok:
                continue
            name = f"v5_vial{int(v.vial):02d}_t{t:07.1f}.jpg"
            cv2.imwrite(str(img_dir / name), frame)
            phase = "fill" if t <= v.end_s else "after_fill"
            rows.append({"filename": name, "video_s": round(index / fps, 3), "frame": index,
                         "vial": int(v.vial), "recipe_id": int(v.recipe_id), "phase": phase,
                         "fill_progress": round(min((t - v.start_s) / v.duration_s, 1.0), 3),
                         "t100_ml": v.t100_ml, "t200_ml": v.t200_ml, "t400_ml": v.t400_ml,
                         "total_ml": v.total_ml, "dispense_order": v.dispense_order})
    table = pd.DataFrame(rows)
    table.to_csv(out_dir / "frame_labels.csv", index=False)
    return table


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=Path("data/raw/dataset2/vial_fill"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/derived/video5_frames"))
    parser.add_argument("--step", type=float, default=1.0, help="seconds between frames inside a fill")
    parser.add_argument("--after", type=float, default=2.0, help="seconds to keep after fill end")
    args = parser.parse_args()
    table = extract(args.data, args.output_dir, args.step, args.after)
    print(f"Saved {len(table)} frames for {table.vial.nunique()} vials to {args.output_dir}")


if __name__ == "__main__":
    main()
