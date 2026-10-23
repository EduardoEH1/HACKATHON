"""Review the previously excluded Recipe 8 frames and recover one ROI sample."""

from __future__ import annotations

import argparse
from pathlib import Path, PureWindowsPath
import os
import tempfile
from zipfile import ZipFile

cache_root = Path(tempfile.gettempdir()) / "vialsense-matplotlib"
cache_root.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(cache_root / "mpl"))
os.environ.setdefault("XDG_CACHE_HOME", str(cache_root / "xdg"))
Path(os.environ["XDG_CACHE_HOME"]).mkdir(parents=True, exist_ok=True)

import cv2
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


VIALS = (10, 11, 12)
FIXED_ROI = (304, 384, 328, 400)
# Manually reviewed central liquid area in the moving Vial 10 frame at 442.034 s.
RECOVERED_FRAME = "vial_fill_20260923_195432_034496.jpg"
RECOVERED_ROI = (80, 290, 104, 306)
CHANNELS = {
    "RGB": ["r_mean", "g_mean", "b_mean"],
    "HSV": ["h_mean_opencv", "s_mean_opencv", "v_mean_opencv"],
}
VIAL_COLORS = {10: "#1976d2", 11: "#ef6c00", 12: "#2e7d32"}
CHANNEL_LABELS = {
    "r_mean": "Red (0–255)",
    "g_mean": "Green (0–255)",
    "b_mean": "Blue (0–255)",
    "h_mean_opencv": "Hue (OpenCV 0–179)",
    "s_mean_opencv": "Saturation (0–255)",
    "v_mean_opencv": "Value / brightness (0–255)",
}


def read_image(archive: ZipFile, member: str) -> np.ndarray:
    encoded = np.frombuffer(archive.read(member), dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"OpenCV could not decode image {member}")
    return image


def measure(image: np.ndarray, roi: tuple[int, int, int, int]) -> dict[str, float | int]:
    x1, y1, x2, y2 = roi
    if not (0 <= x1 < x2 <= image.shape[1] and 0 <= y1 < y2 <= image.shape[0]):
        raise ValueError(f"ROI is outside image bounds: {roi}")
    crop = image[y1:y2, x1:x2]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    b, g, r = crop.astype(np.float64).mean(axis=(0, 1))
    h, s, v = hsv.astype(np.float64).mean(axis=(0, 1))
    return {
        "roi_x1": x1,
        "roi_y1": y1,
        "roi_x2": x2,
        "roi_y2": y2,
        "roi_pixels": int(crop.shape[0] * crop.shape[1]),
        "r_mean": float(r),
        "g_mean": float(g),
        "b_mean": float(b),
        "h_mean_opencv": float(h),
        "s_mean_opencv": float(s),
        "v_mean_opencv": float(v),
    }


def decision(vial: int, filename: str) -> tuple[str, str]:
    if vial == 10 and filename == RECOVERED_FRAME:
        return (
            "measured_with_caution",
            "Blue liquid is visibly inside the moving vial. A small ROI lies within the colored liquid, but motion blur may affect the value.",
        )
    if vial == 10:
        return (
            "remain_excluded",
            "The vial has left the stable measurement position. The remaining visible tube/fixture area does not provide a confidently identifiable colored-liquid ROI.",
        )
    if vial == 11:
        return (
            "remain_excluded",
            "The vessels have shifted relative to the fixed ROI; no distinct colored-liquid area can be separated confidently from clear glass, holder, and reflections.",
        )
    return (
        "remain_excluded",
        "The late-frame vial area is shifted and appears clear or reflective; no confidently colored liquid region can be isolated from the holder and reflections.",
    )


def create_review_montages(
    archive: ZipFile,
    member_by_name: dict[str, str],
    exclusions: pd.DataFrame,
    labels: pd.DataFrame,
    output_dir: Path,
) -> None:
    for vial, excluded_group in exclusions.merge(
        labels[["filename", "video_s"]], on="filename", validate="one_to_one"
    ).groupby("vial", sort=True):
        excluded_group = excluded_group.sort_values("video_s")
        tiles = []
        for _, row in excluded_group.iterrows():
            image = read_image(archive, member_by_name[row.filename])
            cv2.rectangle(image, FIXED_ROI[:2], FIXED_ROI[2:], (0, 0, 255), 2)
            status, _ = decision(int(vial), row.filename)
            if status == "measured_with_caution":
                cv2.rectangle(image, RECOVERED_ROI[:2], RECOVERED_ROI[2:], (0, 255, 0), 3)
                caption = "MANUAL ROI CANDIDATE"
            else:
                caption = "REMAIN EXCLUDED"
            header = f"Vial {int(vial)} | {row.video_s:.1f}s | {caption}"
            cv2.rectangle(image, (0, 0), (640, 28), (0, 0, 0), -1)
            cv2.putText(image, header, (7, 20), cv2.FONT_HERSHEY_SIMPLEX,
                        0.47, (255, 255, 255), 1, cv2.LINE_AA)
            tiles.append(cv2.resize(image, (320, 240)))

        columns = 4
        rows = (len(tiles) + columns - 1) // columns
        blank = np.zeros((240, 320, 3), dtype=np.uint8)
        tiles.extend(blank.copy() for _ in range(rows * columns - len(tiles)))
        sheet = cv2.vconcat(
            [cv2.hconcat(tiles[i * columns:(i + 1) * columns]) for i in range(rows)]
        )
        path = output_dir / f"recipe_8_vial_{int(vial)}_excluded_review.jpg"
        if not cv2.imwrite(str(path), sheet):
            raise OSError(f"Could not write review montage {path}")


def plot_color(measurements: pd.DataFrame, labels: pd.DataFrame, family: str, output: Path) -> None:
    channels = CHANNELS[family]
    fig, axes = plt.subplots(len(channels), 1, figsize=(11, 9), sharex=True)
    for ax, channel in zip(axes, channels):
        for vial in VIALS:
            group = measurements.loc[measurements.vial == vial].sort_values("video_s")
            same_roi = group.loc[group.measurement_status == "measured"]
            ax.plot(
                same_roi["elapsed_since_first_labeled_in_fill_s"], same_roi[channel],
                color=VIAL_COLORS[vial], marker="o", markersize=4, linewidth=1.7,
                label=f"Vial {vial} original ROI (n={len(same_roi)})",
            )
            recovered = group.loc[group.measurement_status == "measured_with_caution"]
            if len(recovered):
                ax.scatter(
                    recovered["elapsed_since_first_labeled_in_fill_s"],
                    recovered[channel], marker="s", s=65, facecolors="none",
                    edgecolors="#111111", linewidths=1.5, zorder=5,
                    label="Recovered moving-frame sample",
                )
        ax.set_ylabel(CHANNEL_LABELS[channel])
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best", frameon=False)
    max_elapsed = (
        labels.groupby("vial")["video_s"].agg(lambda x: x.max() - x.min()).max()
    )
    axes[-1].set_xlim(-0.5, max_elapsed + 1)
    axes[-1].set_xlabel(
        "Seconds since the first frame labeled in_fill=1 for each vial"
    )
    fig.suptitle(f"Recipe 8 preliminary {family} after original-frame review")
    fig.text(
        0.5, 0.01,
        "Only measured frames are plotted; hollow square marks the motion-blurred manual ROI sample.",
        ha="center", fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.97))
    fig.savefig(output, dpi=160, bbox_inches="tight")
    plt.close(fig)


def plot_coverage(timeline: pd.DataFrame, output: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 3.4))
    y_position = {10: 2, 11: 1, 12: 0}
    for vial in VIALS:
        group = timeline.loc[timeline.vial == vial]
        x = group["elapsed_since_first_labeled_in_fill_s"]
        measured = group["measurement_status"].isin(
            ["measured", "measured_with_caution"]
        )
        y = y_position[vial]
        ax.scatter(x[measured], [y] * int(measured.sum()), marker="o", s=38,
                   color=VIAL_COLORS[vial], label="Color measured" if vial == 10 else None)
        ax.scatter(x[~measured], [y] * int((~measured).sum()), marker="x", s=38,
                   color="#777777", label="No reliable ROI color" if vial == 10 else None)
    ax.set_yticks([2, 1, 0], ["Vial 10", "Vial 11", "Vial 12"])
    ax.set_xlabel("Seconds since first frame labeled in_fill=1")
    ax.set_title("Recipe 8 color measurement coverage after reviewing original frames")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(loc="upper right", frameon=False)
    fig.tight_layout()
    fig.savefig(output, dpi=160, bbox_inches="tight")
    plt.close(fig)


def analyze(zip_path: Path, labels_path: Path, measurements_path: Path,
            exclusions_path: Path, output_dir: Path):
    labels_all = pd.read_csv(labels_path)
    recipe_labels = labels_all.loc[
        (labels_all.recipe_id == 8) & (labels_all.in_fill == 1)
    ].copy()
    recipe_labels["vial"] = recipe_labels.vial.astype(int)
    recipe_labels = recipe_labels.sort_values(["vial", "video_s", "filename"])
    measurements = pd.read_csv(measurements_path)
    exclusions = pd.read_csv(exclusions_path)

    with ZipFile(zip_path) as archive:
        members = [name for name in archive.namelist() if not name.endswith("/")]
        member_by_name: dict[str, str] = {}
        for member in members:
            basename = PureWindowsPath(member).name
            if basename in member_by_name:
                raise ValueError(f"Duplicate image basename in ZIP: {basename}")
            member_by_name[basename] = member
        expected = set(recipe_labels.filename)
        actual = set(member_by_name)
        if len(members) != 55 or expected != actual or len(actual) != 55:
            raise ValueError(
                f"ZIP/labels mismatch: archive={len(actual)}, expected={len(expected)}, "
                f"missing={len(expected-actual)}, extra={len(actual-expected)}"
            )

        # Verify all image files decode before making review outputs.
        for name, member in member_by_name.items():
            image = read_image(archive, member)
            if image.shape[:2] != (480, 640):
                raise ValueError(f"Unexpected image size for {name}: {image.shape[:2]}")

        excluded_names = set(exclusions.filename)
        if set(measurements.filename) & excluded_names:
            raise ValueError("A filename is present in both measurements and exclusions")
        if set(measurements.filename) | excluded_names != expected:
            raise ValueError("Measurements/exclusions do not partition the 55 labels")

        label_index = recipe_labels.set_index("filename")
        review_rows = []
        recovered_rows = []
        for row in exclusions.itertuples(index=False):
            label = label_index.loc[row.filename]
            vial = int(label.vial)
            status, note = decision(vial, row.filename)
            review_rows.append(
                {
                    "recipe_id": 8,
                    "vial": vial,
                    "filename": row.filename,
                    "timestamp": label.timestamp,
                    "video_s": float(label.video_s),
                    "elapsed_since_first_labeled_in_fill_s": float(
                        label.video_s - recipe_labels.loc[
                            recipe_labels.vial == vial, "video_s"
                        ].min()
                    ),
                    "original_exclusion_reason": row.reason,
                    "review_decision": status,
                    "review_note": note,
                }
            )
            if status == "measured_with_caution":
                image = read_image(archive, member_by_name[row.filename])
                values = measure(image, RECOVERED_ROI)
                recovered_rows.append(
                    {
                        **label.to_dict(),
                        "filename": row.filename,
                        **values,
                        "measurement_status": "preliminary; manually relocated ROI; motion blur caveat",
                        "review_note": note,
                    }
                )
                annotated = image.copy()
                cv2.rectangle(annotated, FIXED_ROI[:2], FIXED_ROI[2:], (0, 0, 255), 2)
                cv2.rectangle(annotated, RECOVERED_ROI[:2], RECOVERED_ROI[2:], (0, 255, 0), 3)
                cv2.putText(annotated, "Old fixed ROI", (FIXED_ROI[0], FIXED_ROI[1] - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1, cv2.LINE_AA)
                cv2.putText(annotated, "Recovered liquid ROI", (RECOVERED_ROI[0], RECOVERED_ROI[1] - 7),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)
                output_dir.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(output_dir / "recipe_8_vial10_442_roi_example.jpg"), annotated)

        recovered = pd.DataFrame(recovered_rows)
        if len(recovered) != 1 or recovered.iloc[0]["filename"] != RECOVERED_FRAME:
            raise ValueError("Expected exactly the manually reviewed Vial 10 candidate")

        review = pd.DataFrame(review_rows).sort_values(["vial", "video_s"])
        review.to_csv(output_dir / "recipe_8_excluded_frame_review.csv", index=False)
        recovered.to_csv(output_dir / "recipe_8_recovered_measurement.csv", index=False)
        create_review_montages(archive, member_by_name, exclusions, recipe_labels, output_dir)

    timeline = recipe_labels.copy()
    roi_columns = ["roi_x1", "roi_y1", "roi_x2", "roi_y2"]
    timeline = timeline.merge(
        measurements[["filename", *roi_columns, *CHANNELS["RGB"], *CHANNELS["HSV"]]],
        on="filename", how="left", validate="one_to_one",
    )
    timeline = timeline.merge(
        recovered[["filename", *roi_columns, *CHANNELS["RGB"], *CHANNELS["HSV"]]].rename(
            columns={c: f"{c}_recovered" for c in [*roi_columns, *CHANNELS["RGB"], *CHANNELS["HSV"]]}
        ),
        on="filename", how="left", validate="one_to_one",
    )
    for column in [*roi_columns, *CHANNELS["RGB"], *CHANNELS["HSV"]]:
        timeline[column] = timeline[column].combine_first(timeline[f"{column}_recovered"])
        timeline.drop(columns=[f"{column}_recovered"], inplace=True)
    status_by_name = {name: "measured" for name in measurements.filename}
    status_by_name.update({name: "remain_excluded" for name in exclusions.filename})
    status_by_name[RECOVERED_FRAME] = "measured_with_caution"
    timeline["measurement_status"] = timeline.filename.map(status_by_name)
    timeline["roi_method"] = timeline.measurement_status.map(
        {
            "measured": "original fixed ROI",
            "measured_with_caution": "manually relocated ROI; motion blur caveat",
            "remain_excluded": "no reliable color ROI identified",
        }
    )
    timeline["elapsed_since_first_labeled_in_fill_s"] = timeline.video_s - timeline.groupby(
        "vial"
    ).video_s.transform("min")
    timeline.to_csv(output_dir / "recipe_8_temporal_measurements_updated.csv", index=False)

    summaries = []
    for vial, group in timeline.groupby("vial", sort=True):
        measured = group.loc[group.measurement_status.isin(["measured", "measured_with_caution"])]
        for family, channels in CHANNELS.items():
            for channel in channels:
                values = measured[channel].astype(float)
                summaries.append(
                    {
                        "recipe_id": 8, "vial": int(vial), "color_space": family,
                        "channel": channel, "sample_count": len(values),
                        "mean": values.mean(), "std": values.std(ddof=1),
                        "min": values.min(), "max": values.max(),
                        "first": values.iloc[0], "last": values.iloc[-1],
                        "status": "preliminary; one manually recovered moving-frame sample included",
                    }
                )
    pd.DataFrame(summaries).to_csv(
        output_dir / "recipe_8_temporal_summary_updated.csv", index=False
    )
    plot_color(
        timeline.loc[timeline.measurement_status.isin(["measured", "measured_with_caution"])],
        recipe_labels, "RGB", output_dir / "recipe_8_rgb_over_time_updated.png",
    )
    plot_color(
        timeline.loc[timeline.measurement_status.isin(["measured", "measured_with_caution"])],
        recipe_labels, "HSV", output_dir / "recipe_8_hsv_over_time_updated.png",
    )
    plot_coverage(timeline, output_dir / "recipe_8_measurement_coverage_updated.png")
    return timeline, review, recovered


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, default=Path("data/raw/recipe8/Recipe_8.zip"))
    parser.add_argument("--labels", type=Path, default=Path("data/raw/recipe7/labels_video5_frame_labels.csv"))
    parser.add_argument("--measurements", type=Path, default=Path("results/recipe_8/recipe_8_manual_roi_measurements.csv"))
    parser.add_argument("--exclusions", type=Path, default=Path("results/recipe_8/recipe_8_excluded_frames.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/temporal_analysis/recipe_8_original_image_review"))
    args = parser.parse_args()
    timeline, review, recovered = analyze(
        args.zip, args.labels, args.measurements, args.exclusions, args.output_dir
    )
    print(f"Verified {len(timeline)} labeled frames; reviewed {len(review)} exclusions")
    print(f"Added {len(recovered)} cautious sample; remaining excluded: {(review.review_decision == 'remain_excluded').sum()}")
    print(timeline.groupby("vial").measurement_status.value_counts().to_string())


if __name__ == "__main__":
    main()
