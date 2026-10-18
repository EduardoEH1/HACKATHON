"""Analyze reviewed sample frames from Recipe 6 with a manual ROI."""

from pathlib import Path

import pandas as pd
import cv2

from vialsense.dataset import load_labeled_frames
from vialsense.manual_roi import measure_roi, save_roi_example


# Manually selected from the visible lower liquid body in the inspected frames.
# Coordinates are x1, y1, x2, y2 in the original 640x480 images.
ROI = (304, 384, 328, 400)
SAMPLES_PER_VIAL = {4: (0, 1, 2, 3, 4), 5: (0, 2, 4, 6, 8), 6: tuple(range(8))}


def analyze(labels: Path, images: Path, output: Path, examples: Path) -> pd.DataFrame:
    labeled = load_labeled_frames(labels, images, recipe_id=6)
    groups = []
    for vial, positions in SAMPLES_PER_VIAL.items():
        group = labeled.loc[labeled["vial"] == vial].reset_index(drop=True)
        if max(positions) >= len(group):
            raise ValueError(f"Not enough labeled frames for vial {vial}")
        groups.append(group.iloc[list(positions)])
    frames = pd.concat(groups, ignore_index=True)
    records = []
    reviewed_images = {vial: [] for vial in SAMPLES_PER_VIAL}
    for row in frames.itertuples(index=False):
        path = Path(row.image_path)
        values = measure_roi(path, ROI)
        annotated_path = examples / path.name
        save_roi_example(path, ROI, annotated_path)
        reviewed_images[int(row.vial)].append(annotated_path)
        records.append({**row._asdict(), "roi_x1": ROI[0], "roi_y1": ROI[1],
                        "roi_x2": ROI[2], "roi_y2": ROI[3], **values,
                        "measurement_note": "manual ROI; visible liquid; visually reviewed"})
    result = pd.DataFrame(records)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False)
    metrics = ["r_mean", "g_mean", "b_mean", "h_mean_opencv", "s_mean_opencv", "v_mean_opencv"]
    summary_rows = []
    for vial, group in result.groupby("vial"):
        for metric in metrics:
            values = group[metric]
            summary_rows.append({"recipe_id": 6, "vial": int(vial), "channel": metric,
                                 "sample_count": len(values), "mean": values.mean(),
                                 "std": values.std(ddof=1), "min": values.min(), "max": values.max()})
    pd.DataFrame(summary_rows).to_csv(output.with_name("recipe_6_preliminary_summary_by_vial.csv"), index=False)
    overall_rows = []
    for metric in metrics:
        values = result[metric]
        overall_rows.append({"recipe_id": 6, "channel": metric, "sample_count": len(values),
                             "mean": values.mean(), "std": values.std(ddof=1),
                             "min": values.min(), "max": values.max(),
                             "status": "observed sample envelope; not an acceptance threshold"})
    pd.DataFrame(overall_rows).to_csv(output.with_name("recipe_6_preliminary_summary_overall.csv"), index=False)
    for vial, paths in reviewed_images.items():
        thumbs = [cv2.resize(cv2.imread(str(path)), (320, 240)) for path in paths]
        while len(thumbs) % 4:
            thumbs.append(thumbs[-1] * 0)
        montage = cv2.vconcat([cv2.hconcat(thumbs[i:i + 4]) for i in range(0, len(thumbs), 4)])
        cv2.imwrite(str(examples / f"montage_vial_{vial}.jpg"), montage)
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, default=Path("data/raw/vial_fill/labels_video5_frame_labels.csv"))
    parser.add_argument("--images", type=Path, default=Path("data/raw/vial_fill/images"))
    parser.add_argument("--output", type=Path, default=Path("results/recipe_6/recipe_6_preliminary_measurements.csv"))
    parser.add_argument("--examples", type=Path, default=Path("results/recipe_6/roi_examples"))
    args = parser.parse_args()
    result = analyze(args.labels, args.images, args.output, args.examples)
    print(f"Saved {len(result)} measurements to {args.output}")
    print(result.groupby("vial")[["r_mean", "g_mean", "b_mean", "h_mean_opencv", "s_mean_opencv", "v_mean_opencv"]].mean().round(2).to_string())
