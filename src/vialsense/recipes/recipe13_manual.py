"""Preliminary manual-ROI color analysis for Recipe 13."""

from pathlib import Path

import cv2
import pandas as pd

from vialsense.manual_roi import measure_roi, save_roi_example


# Shared 640x480 lower-vial ROI used for the earlier recipe prototypes.
ROI = (304, 384, 328, 400)
EXPECTED_COUNTS = {25: 19, 26: 18, 27: 18}
EXPECTED_TOTAL = sum(EXPECTED_COUNTS.values())
# Visually reviewed chronological positions where the ROI contains liquid.
SAMPLE_POSITIONS = {
    25: set(range(10)),
    26: set(range(18)),
    27: set(range(4, 18)),
}


def _montage(paths: list[Path], output: Path) -> None:
    thumbs = []
    for path in paths:
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Cannot read annotated image: {path}")
        thumbs.append(cv2.resize(image, (320, 240)))
    if not thumbs:
        return
    while len(thumbs) % 3:
        thumbs.append(thumbs[-1] * 0)
    canvas = cv2.vconcat(
        [cv2.hconcat(thumbs[i : i + 3]) for i in range(0, len(thumbs), 3)]
    )
    if not cv2.imwrite(str(output), canvas):
        raise OSError(f"Could not write montage: {output}")


def analyze(labels_path: Path, images_dir: Path, output_dir: Path) -> pd.DataFrame:
    """Match Recipe 13 labels to local files and measure reviewed ROIs."""
    labels = pd.read_csv(labels_path)
    required = {"filename", "recipe_id", "in_fill", "vial"}
    missing_columns = required - set(labels.columns)
    if missing_columns:
        raise ValueError(f"Label CSV is missing columns: {sorted(missing_columns)}")

    recipe = labels.loc[(labels.recipe_id == 13) & (labels.in_fill == 1)].copy()
    if len(recipe) != EXPECTED_TOTAL or recipe.filename.nunique() != EXPECTED_TOTAL:
        raise ValueError(
            f"Expected {EXPECTED_TOTAL} unique labeled Recipe 13 frames; "
            f"found {len(recipe)} rows / {recipe.filename.nunique()} unique names"
        )
    for vial, expected in EXPECTED_COUNTS.items():
        actual = int((recipe.vial == vial).sum())
        if actual != expected:
            raise ValueError(f"Expected {expected} Recipe 13 frames for vial {vial}; found {actual}")

    actual_names = {path.name for path in images_dir.glob("*") if path.is_file()}
    expected_names = set(recipe.filename)
    if actual_names != expected_names:
        raise ValueError(
            f"Image folder differs from Recipe 13 labels: "
            f"{len(expected_names - actual_names)} missing, "
            f"{len(actual_names - expected_names)} unexpected"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    examples_dir = output_dir / "annotated_images"
    measurements = []
    exclusions = []
    selected_paths: dict[int, list[Path]] = {vial: [] for vial in EXPECTED_COUNTS}

    for vial, group in recipe.groupby("vial", sort=True):
        vial = int(vial)
        group = group.reset_index(drop=True)
        for position, row in group.iterrows():
            image_path = images_dir / row.filename
            if position not in SAMPLE_POSITIONS[vial]:
                reason = (
                    "positions 10 onward: vial moved or ROI no longer contains visible liquid"
                    if vial == 25
                    else "positions 0-3: not enough visible liquid in the ROI"
                )
                exclusions.append(
                    {
                        "recipe_id": 13,
                        "vial": vial,
                        "filename": row.filename,
                        "reason": reason,
                    }
                )
                continue

            values = measure_roi(image_path, ROI)
            annotated_path = examples_dir / row.filename
            save_roi_example(image_path, ROI, annotated_path)
            selected_paths[vial].append(annotated_path)
            measurements.append(
                {
                    **row.to_dict(),
                    "roi_x1": ROI[0],
                    "roi_y1": ROI[1],
                    "roi_x2": ROI[2],
                    "roi_y2": ROI[3],
                    **values,
                    "measurement_status": "preliminary; manual ROI; visible liquid reviewed",
                }
            )

    results = pd.DataFrame(measurements)
    results.to_csv(output_dir / "recipe_13_manual_roi_measurements.csv", index=False)
    pd.DataFrame(exclusions).to_csv(
        output_dir / "recipe_13_excluded_frames.csv", index=False
    )
    pd.DataFrame(
        columns=["recipe_id", "vial", "filename", "status"]
    ).to_csv(output_dir / "recipe_13_missing_frames.csv", index=False)

    metrics = [
        "r_mean", "g_mean", "b_mean", "h_mean_opencv", "s_mean_opencv", "v_mean_opencv"
    ]
    summary = []
    for vial, group in results.groupby("vial"):
        for metric in metrics:
            values = group[metric]
            summary.append(
                {
                    "recipe_id": 13,
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
        output_dir / "recipe_13_preliminary_summary_by_vial.csv", index=False
    )
    for vial, paths in selected_paths.items():
        _montage(paths, output_dir / f"recipe_13_roi_montage_vial_{vial}.jpg")
    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--labels", type=Path, default=Path("data/raw/recipe7/labels_video5_frame_labels.csv")
    )
    parser.add_argument("--images", type=Path, default=Path("data/raw/recipe13/images"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/recipe_13"))
    args = parser.parse_args()
    result = analyze(args.labels, args.images, args.output_dir)
    print(f"Saved {len(result)} preliminary measurements under {args.output_dir}")
    print(
        result.groupby("vial")[
            ["r_mean", "g_mean", "b_mean", "h_mean_opencv", "s_mean_opencv", "v_mean_opencv"]
        ]
        .mean()
        .round(2)
        .to_string()
    )
