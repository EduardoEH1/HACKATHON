"""Preliminary manual-ROI color analysis for the available Recipe 11 frames."""

from pathlib import Path

import cv2
import pandas as pd

from vialsense.manual_roi import measure_roi, save_roi_example


# Shared 640x480 lower-vial ROI used for the earlier recipe prototypes.
ROI = (304, 384, 328, 400)
EXPECTED_COUNTS = {19: 20, 20: 21, 21: 21}
EXPECTED_TOTAL = sum(EXPECTED_COUNTS.values())
# Positions are zero-based within each vial's CSV rows, in CSV order.
# Vial 19's visible dark liquid begins at position 5; only the final three
# available Vial 20 frames show a measurable pool in this ROI; Vial 21 has two
# usable early frames. Other positions are empty or the vial has moved away.
SAMPLE_POSITIONS = {19: set(range(5, 19)), 20: {16, 17, 18}, 21: {0, 1}}


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
    """Compare Recipe 11 CSV rows to local images and measure reviewed ROIs."""
    labels = pd.read_csv(labels_path)
    required = {"filename", "recipe_id", "in_fill", "vial"}
    missing_columns = required - set(labels.columns)
    if missing_columns:
        raise ValueError(f"Label CSV is missing columns: {sorted(missing_columns)}")

    recipe = labels.loc[(labels.recipe_id == 11) & (labels.in_fill == 1)].copy()
    if len(recipe) != EXPECTED_TOTAL or recipe.filename.nunique() != EXPECTED_TOTAL:
        raise ValueError(
            f"Expected {EXPECTED_TOTAL} unique labeled Recipe 11 frames; "
            f"found {len(recipe)} rows / {recipe.filename.nunique()} unique names"
        )
    for vial, expected in EXPECTED_COUNTS.items():
        actual = int((recipe.vial == vial).sum())
        if actual != expected:
            raise ValueError(f"Expected {expected} Recipe 11 frames for vial {vial}; found {actual}")

    actual_names = {path.name for path in images_dir.glob("*") if path.is_file()}
    expected_names = set(recipe.filename)
    unexpected_names = actual_names - expected_names
    if unexpected_names:
        raise ValueError(f"Images not labeled as Recipe 11: {sorted(unexpected_names)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    examples_dir = output_dir / "annotated_images"
    measurements = []
    exclusions = []
    absent = []
    selected_paths: dict[int, list[Path]] = {vial: [] for vial in EXPECTED_COUNTS}

    for vial, group in recipe.groupby("vial", sort=True):
        vial = int(vial)
        group = group.reset_index(drop=True)
        for position, row in group.iterrows():
            image_path = images_dir / row.filename
            if not image_path.is_file():
                absent.append(
                    {
                        "recipe_id": 11,
                        "vial": vial,
                        "position_in_vial": position,
                        "filename": row.filename,
                        "status": "missing from uploaded ZIP",
                    }
                )
                continue

            if position not in SAMPLE_POSITIONS[vial]:
                if vial == 19:
                    reason = "positions 0-4: ROI has no clearly visible colored liquid"
                elif vial == 20:
                    reason = "positions 0-8: ROI has no clearly visible colored liquid"
                else:
                    reason = "positions 2 onward: vial/liquid is no longer visible in ROI"
                exclusions.append(
                    {"recipe_id": 11, "vial": vial, "filename": row.filename, "reason": reason}
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

    if len(actual_names) != 52:
        raise ValueError(f"Expected 52 uploaded images; found {len(actual_names)}")

    results = pd.DataFrame(measurements)
    results.to_csv(output_dir / "recipe_11_manual_roi_measurements.csv", index=False)
    pd.DataFrame(exclusions).to_csv(output_dir / "recipe_11_excluded_frames.csv", index=False)
    pd.DataFrame(absent).to_csv(output_dir / "recipe_11_missing_frames.csv", index=False)

    metrics = [
        "r_mean", "g_mean", "b_mean", "h_mean_opencv", "s_mean_opencv", "v_mean_opencv"
    ]
    summary = []
    for vial, group in results.groupby("vial"):
        for metric in metrics:
            values = group[metric]
            summary.append(
                {
                    "recipe_id": 11,
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
        output_dir / "recipe_11_preliminary_summary_by_vial.csv", index=False
    )
    for vial, paths in selected_paths.items():
        _montage(paths, output_dir / f"recipe_11_roi_montage_vial_{vial}.jpg")
    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--labels", type=Path, default=Path("data/raw/recipe7/labels_video5_frame_labels.csv")
    )
    parser.add_argument("--images", type=Path, default=Path("data/raw/recipe11/images"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/recipe_11"))
    args = parser.parse_args()
    result = analyze(args.labels, args.images, args.output_dir)
    print(f"Saved {len(result)} preliminary measurements under {args.output_dir}")
    print(result.groupby("vial")[["r_mean", "g_mean", "b_mean", "h_mean_opencv", "s_mean_opencv", "v_mean_opencv"]].mean().round(2).to_string())
