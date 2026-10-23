"""Fix the Dataset 2 still-image labels by matching each still to the video.

The problem
-----------
video5_frame_labels.csv assigns each still to a vial using the still's own
timestamp. The vial fill windows (video5_vial_recipes.csv) are in VIDEO time.
The two clocks drift: video time = 0.8225 x still time. By the end of the
video the stills are off by about 5 minutes, so most stills carry the wrong
vial and recipe. Example: stills labeled "Vial 7" show the Recipe 6 vial.

The fix
-------
1. Shrink every video frame and every still to 80x60 grayscale.
2. For each still, find the video frame that looks most similar.
3. Fit one straight line (video time vs still time) through all matches,
   ignoring outliers. Use the line, not single matches, so near-identical
   idle frames do not cause wrong jumps.
4. Re-label each still with the vial whose video window contains its
   corrected time.

Run from the repo root:
    PYTHONPATH=src python -m vialsense.sync_labels --data data/raw/dataset2/vial_fill
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

SIZE = (80, 60)


def _normalize(gray: np.ndarray) -> np.ndarray:
    v = gray.astype(np.float32).ravel()
    v -= v.mean()
    return v / (np.linalg.norm(v) + 1e-6)


def video_fingerprints(video: Path) -> tuple[np.ndarray, float]:
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    rows = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rows.append(_normalize(cv2.resize(gray, SIZE, interpolation=cv2.INTER_AREA)))
    if not rows:
        raise ValueError(f"Cannot read video: {video}")
    return np.stack(rows), fps


def match_stills(labels: pd.DataFrame, images_dir: Path, prints: np.ndarray, fps: float) -> pd.DataFrame:
    out = labels.copy()
    matched, score = [], []
    for name in out["filename"]:
        gray = cv2.imread(str(images_dir / name), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            raise FileNotFoundError(images_dir / name)
        sims = prints @ _normalize(cv2.resize(gray, SIZE, interpolation=cv2.INTER_AREA))
        best = int(sims.argmax())
        matched.append(best / fps)
        score.append(float(sims[best]))
    out["matched_video_s"] = matched
    out["match_score"] = score
    return out


def fit_clock(still_s: np.ndarray, video_s: np.ndarray, max_resid: float = 3.0) -> tuple[float, float, np.ndarray]:
    slope, offset = np.polyfit(still_s, video_s, 1)
    keep = np.abs(video_s - (slope * still_s + offset)) < max_resid
    slope, offset = np.polyfit(still_s[keep], video_s[keep], 1)
    return float(slope), float(offset), keep


def relabel(frames: pd.DataFrame, vials: pd.DataFrame) -> pd.DataFrame:
    meta_cols = ["recipe_id", "type", "t100_ml", "t200_ml", "t400_ml", "total_ml",
                 "dispense_order", "color_purpose"]
    out = frames.drop(columns=[c for c in meta_cols + ["vial", "in_fill"] if c in frames], errors="ignore")
    out["in_fill"] = 0
    out["vial"] = pd.NA
    out["fill_progress"] = np.nan  # 0 = fill start, 1 = fill end
    for _, v in vials.iterrows():
        inside = (out["video_s_corrected"] >= v.start_s) & (out["video_s_corrected"] <= v.end_s)
        out.loc[inside, "in_fill"] = 1
        out.loc[inside, "vial"] = int(v.vial)
        out.loc[inside, "fill_progress"] = (out.loc[inside, "video_s_corrected"] - v.start_s) / v.duration_s
    out = out.merge(vials[["vial"] + meta_cols], on="vial", how="left")
    out["type"] = out["type"].fillna("between_fills")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=Path("data/raw/dataset2/vial_fill"),
                        help="vial_fill folder with images/, videos/, labels/")
    parser.add_argument("--video-id", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path("labels_corrected/video5_frame_labels_corrected.csv"))
    args = parser.parse_args()

    labels = pd.read_csv(args.data / "labels" / "video5_frame_labels.csv")
    vials = pd.read_csv(args.data / "labels" / "video5_vial_recipes.csv")
    prints, fps = video_fingerprints(args.data / "videos" / f"vial_fill_video_{args.video_id}.mp4")
    print(f"Video: {len(prints)} frames at {fps:.0f} fps ({len(prints) / fps:.0f} s)")

    frames = match_stills(labels, args.data / "images", prints, fps)
    slope, offset, keep = fit_clock(frames["video_s"].to_numpy(), frames["matched_video_s"].to_numpy())
    frames["video_s_corrected"] = slope * frames["video_s"] + offset
    frames["clock_fit_outlier"] = ~keep
    print(f"Clock fit: video_s = {slope:.5f} x still_s + {offset:.3f}  "
          f"({(~keep).sum()} outliers, lowest match score {frames.match_score.min():.3f})")

    fixed = relabel(frames, vials)
    old = labels.set_index("filename")["vial"]
    changed = (fixed.set_index("filename")["vial"].astype("Float64") != old.astype("Float64")).sum()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fixed.to_csv(args.output, index=False)

    last = fixed["video_s_corrected"].max()
    covered = sorted(int(v) for v in fixed.loc[fixed.in_fill == 1, "vial"].dropna().unique())
    print(f"Stills cover video 0-{last:.0f} s. Vials with in-fill stills: {covered}")
    print(f"{changed} of {len(fixed)} stills changed vial assignment. Saved {args.output}")


if __name__ == "__main__":
    main()
