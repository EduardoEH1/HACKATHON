"""Run the detector-to-Phase-1/Phase-2 connection on saved data or a video."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .anomaly import load_model
from .integration import measure_video, save_labeled_results, save_unlabeled_results

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "results/corrected/phase2/provisional_model.json"
WINDOWS = ROOT / "inputs/color_check/video5_vial_recipes.csv"
READINGS = ROOT / "inputs/color_check/frame_colors.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    saved = modes.add_parser("saved", help="replay saved Video 5 detector readings")
    saved.add_argument("--readings", type=Path, default=READINGS)
    saved.add_argument("--windows", type=Path, default=WINDOWS)
    saved.add_argument("--output-dir", type=Path,
                       default=ROOT / "results/integration/video5_saved")
    video = modes.add_parser("video", help="run Salah's liquid finder on an MP4")
    video.add_argument("--video", type=Path, required=True)
    video.add_argument("--windows", type=Path,
                       help="vial/recipe fill windows; omit for color-only output")
    video.add_argument("--step", type=float, default=1.0, help="seconds between frames")
    video.add_argument("--output-dir", type=Path,
                       default=ROOT / "results/integration/video")
    for mode in (saved, video):
        mode.add_argument("--model", type=Path, default=MODEL)
    args = parser.parse_args()
    model = load_model(args.model)
    if args.mode == "saved":
        summary = save_labeled_results(pd.read_csv(args.readings), pd.read_csv(args.windows),
                                       model, args.output_dir)
    else:
        windows = pd.read_csv(args.windows) if args.windows else None
        readings = measure_video(args.video, step_s=args.step, windows=windows)
        summary = (save_labeled_results(readings, windows, model, args.output_dir)
                   if windows is not None else
                   save_unlabeled_results(readings, model, args.output_dir))
    print(json.dumps(summary, indent=2))
    print(f"Saved integration outputs to {args.output_dir}")


if __name__ == "__main__":
    main()
