"""Analyze labeled sampled frames for one video-5 recipe."""

import argparse
from pathlib import Path

import pandas as pd

from vialsense.color import measure_frame
from vialsense.dataset import load_labeled_frames


def analyze(labels_csv: Path, images_dir: Path, recipe_id: int, output_csv: Path) -> pd.DataFrame:
    frames = load_labeled_frames(labels_csv, images_dir, recipe_id)
    measurements = [measure_frame(str(path)) for path in frames["image_path"]]
    result = pd.concat([frames, pd.DataFrame(measurements)], axis=1)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_csv, index=False)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, required=True, help="video5_frame_labels.csv")
    parser.add_argument("--images", type=Path, required=True, help="vial_fill/images directory")
    parser.add_argument("--recipe", type=int, default=6, help="single recipe_id to analyze")
    parser.add_argument("--output", type=Path, default=Path("outputs/recipe_color_measurements.csv"))
    args = parser.parse_args()
    result = analyze(args.labels, args.images, args.recipe, args.output)
    print(f"Saved {len(result)} frame measurements to {args.output}")
    print(result.groupby("vial")[["r_mean", "g_mean", "b_mean", "h_mean_opencv", "s_mean_opencv", "v_mean_opencv"]].mean().to_string())


if __name__ == "__main__":
    main()
