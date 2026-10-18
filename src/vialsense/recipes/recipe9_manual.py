"""Analyze visibly colored Recipe 9 frames with the shared manual ROI."""

from pathlib import Path

import cv2
import pandas as pd

from vialsense.manual_roi import measure_roi, save_roi_example


# Same 640x480 fixed-camera ROI used for the preliminary Recipe 6-8 work.
ROI = (304, 384, 328, 400)
# Frames were reviewed against the ROI. Keep samples while visible liquid is
# inside the box; omit frames after Vials 13 and 14 move away from the camera ROI.
SAMPLE_POSITIONS = {
    13: tuple(range(17)),
    14: tuple(range(18)),
    15: tuple(range(24)),
}
EXCLUSION_REASONS = {
    13: "frames 17-22: vial moves out of the fixed ROI; colored liquid is no longer visible in the box",
    14: "frames 18-22: vial moves out of the fixed ROI; colored liquid is no longer visible in the box",
}
EXPECTED_COUNTS = {13: 23, 14: 23, 15: 24}


def _montage(paths: list[Path], output: Path) -> None:
    thumbs = [cv2.resize(cv2.imread(str(path)), (320, 240)) for path in paths]
    while len(thumbs) % 4:
        thumbs.append(thumbs[-1] * 0)
    canvas = cv2.vconcat(
        [cv2.hconcat(thumbs[i : i + 4]) for i in range(0, len(thumbs), 4)]
    )
    cv2.imwrite(str(output), canvas)


def analyze(labels_path: Path, images_dir: Path, output_dir: Path) -> pd.DataFrame:
    labels = pd.read_csv(labels_path)
    required = {"filename", "recipe_id", "in_fill", "vial"}
    missing = required - set(labels.columns)
    if missing:
        raise ValueError(f"Label CSV is missing columns: {sorted(missing)}")

    recipe = labels.loc[(labels.recipe_id == 9) & (labels.in_fill == 1)].copy()
    if len(recipe) != 70 or recipe.filename.nunique() != 70:
        raise ValueError(
            f"Expected 70 unique labeled Recipe 9 frames; found {len(recipe)}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    examples_dir = output_dir / "annotated_images"
    measurement_rows = []
    exclusion_rows = []
    selected_paths: dict[int, list[Path]] = {13: [], 14: [], 15: []}

    for vial, positions in SAMPLE_POSITIONS.items():
        group = recipe.loc[recipe.vial == vial].reset_index(drop=True)
        if len(group) != EXPECTED_COUNTS[vial]:
            raise ValueError(
                f"Expected {EXPECTED_COUNTS[vial]} labeled frames for vial {vial}; "
                f"found {len(group)}"
            )
        for position, row in group.iterrows():
            image_path = images_dir / row.filename
            if not image_path.is_file():
                raise FileNotFoundError(f"Missing labeled image: {image_path}")
            if position not in positions:
                exclusion_rows.append(
                    {
                        "recipe_id": 9,
                        "vial": vial,
                        "filename": row.filename,
                        "reason": EXCLUSION_REASONS[vial],
                    }
                )
                continue

            values = measure_roi(image_path, ROI)
            annotated = examples_dir / row.filename
            save_roi_example(image_path, ROI, annotated)
            selected_paths[vial].append(annotated)
            measurement_rows.append(
                {
                    **row.to_dict(),
                    "roi_x1": ROI[0],
                    "roi_y1": ROI[1],
                    "roi_x2": ROI[2],
                    "roi_y2": ROI[3],
                    **values,
                    "measurement_status": (
                        "preliminary; manual ROI; visibly colored liquid reviewed"
                    ),
                }
            )

    results = pd.DataFrame(measurement_rows)
    results.to_csv(output_dir / "recipe_9_manual_roi_measurements.csv", index=False)
    pd.DataFrame(exclusion_rows).to_csv(
        output_dir / "recipe_9_excluded_frames.csv", index=False
    )

    metrics = [
        "r_mean",
        "g_mean",
        "b_mean",
        "h_mean_opencv",
        "s_mean_opencv",
        "v_mean_opencv",
    ]
    summary = []
    for vial, group in results.groupby("vial"):
        for metric in metrics:
            values = group[metric]
            summary.append(
                {
                    "recipe_id": 9,
                    "vial": int(vial),
                    "channel": metric,
                    "sample_count": len(values),
                    "mean": values.mean(),
                    "std": values.std(ddof=1),
                    "min": values.min(),
                    "max": values.max(),
                    "status": "preliminary; not a validated reference or threshold",
                }
            )
    pd.DataFrame(summary).to_csv(
        output_dir / "recipe_9_preliminary_summary_by_vial.csv", index=False
    )

    for vial, paths in selected_paths.items():
        _montage(paths, output_dir / f"recipe_9_roi_montage_vial_{vial}.jpg")
    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--labels",
        type=Path,
        default=Path("data/raw/recipe7/labels_video5_frame_labels.csv"),
    )
    parser.add_argument(
        "--images", type=Path, default=Path("data/raw/recipe9/images")
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("results/recipe_9")
    )
    args = parser.parse_args()
    result = analyze(args.labels, args.images, args.output_dir)
    print(f"Saved {len(result)} preliminary measurements under {args.output_dir}")
    print(
        result.groupby("vial")[[
            "r_mean",
            "g_mean",
            "b_mean",
            "h_mean_opencv",
            "s_mean_opencv",
            "v_mean_opencv",
        ]]
        .mean()
        .round(2)
        .to_string()
    )
