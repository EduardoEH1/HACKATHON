"""Place Recipe 8 color samples on the CSV's labeled in-fill timeline."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import tempfile

cache_root = Path(tempfile.gettempdir()) / "vialsense-matplotlib"
cache_root.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(cache_root / "mpl"))
os.environ.setdefault("XDG_CACHE_HOME", str(cache_root / "xdg"))
Path(os.environ["XDG_CACHE_HOME"]).mkdir(parents=True, exist_ok=True)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


VIALS = (10, 11, 12)
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


def build_timeline(labels_path: Path, measurements_path: Path, exclusions_path: Path):
    labels = pd.read_csv(labels_path)
    measurements = pd.read_csv(measurements_path)
    exclusions = pd.read_csv(exclusions_path)
    required_labels = {"filename", "timestamp", "video_s", "in_fill", "vial", "recipe_id"}
    if missing := required_labels - set(labels.columns):
        raise ValueError(f"Label CSV is missing columns: {sorted(missing)}")

    active = labels.loc[(labels.recipe_id == 8) & (labels.in_fill == 1)].copy()
    active["vial"] = pd.to_numeric(active["vial"], errors="raise").astype(int)
    active = active.loc[active.vial.isin(VIALS)].copy()
    active["video_s"] = pd.to_numeric(active["video_s"], errors="raise")
    active = active.sort_values(["vial", "video_s", "filename"])

    if set(active.vial.unique()) != set(VIALS):
        raise ValueError("Expected labeled in-fill rows for Vials 10, 11, and 12")
    if active.filename.duplicated().any():
        raise ValueError("Recipe 8 label filenames must be unique")

    measured_by_file = measurements.set_index("filename")
    excluded_by_file = exclusions.set_index("filename")
    measured_names = set(measured_by_file.index)
    excluded_names = set(excluded_by_file.index)
    label_names = set(active.filename)
    if measured_names & excluded_names:
        raise ValueError("A frame cannot be both measured and excluded")
    if measured_names | excluded_names != label_names:
        raise ValueError(
            "Measured and excluded frames do not cover the Recipe 8 in-fill labels"
        )

    frame = active.copy()
    frame["measurement_status"] = frame.filename.map(
        lambda filename: "measured" if filename in measured_names else "excluded_roi"
    )
    frame["exclusion_reason"] = frame.filename.map(
        lambda filename: excluded_by_file.loc[filename, "reason"]
        if filename in excluded_names
        else ""
    )
    for channel in CHANNELS["RGB"] + CHANNELS["HSV"]:
        frame[channel] = frame.filename.map(
            lambda filename: measured_by_file.loc[filename, channel]
            if filename in measured_names
            else float("nan")
        )
    frame["sample_index_in_fill"] = frame.groupby("vial").cumcount()
    frame["seconds_since_first_labeled_in_fill_frame"] = frame.video_s - frame.groupby(
        "vial"
    ).video_s.transform("min")

    # Bound the labeled segment using the nearest non-fill frame on either side.
    full_labels = labels.sort_values("video_s")
    summaries = []
    for vial, group in frame.groupby("vial", sort=True):
        first = group.iloc[0]
        last = group.iloc[-1]
        preceding = full_labels.loc[
            (full_labels.video_s < first.video_s) & (full_labels.in_fill == 0)
        ].tail(1)
        following = full_labels.loc[
            (full_labels.video_s > last.video_s) & (full_labels.in_fill == 0)
        ].head(1)
        before = preceding.iloc[0] if len(preceding) else None
        after = following.iloc[0] if len(following) else None
        measured = group.loc[group.measurement_status == "measured"]
        summaries.append(
            {
                "recipe_id": 8,
                "vial": int(vial),
                "labeled_in_fill_frame_count": len(group),
                "first_labeled_in_fill_timestamp": first.timestamp,
                "first_labeled_in_fill_video_s": float(first.video_s),
                "previous_non_fill_timestamp": before.timestamp if before is not None else "",
                "previous_non_fill_video_s": float(before.video_s) if before is not None else float("nan"),
                "start_boundary_sample_gap_s": float(first.video_s - before.video_s) if before is not None else float("nan"),
                "last_labeled_in_fill_timestamp": last.timestamp,
                "last_labeled_in_fill_video_s": float(last.video_s),
                "next_non_fill_timestamp": after.timestamp if after is not None else "",
                "next_non_fill_video_s": float(after.video_s) if after is not None else float("nan"),
                "end_boundary_sample_gap_s": float(after.video_s - last.video_s) if after is not None else float("nan"),
                "first_to_last_labeled_frame_span_s": float(last.video_s - first.video_s),
                "measured_frame_count": len(measured),
                "excluded_roi_frame_count": int((group.measurement_status == "excluded_roi").sum()),
                "last_measured_elapsed_s": float(measured.seconds_since_first_labeled_in_fill_frame.max()),
                "status": "labeled frame interval; exact liquid dispense onset/end not established",
            }
        )

    return frame, pd.DataFrame(summaries)


def plot_channels(frame: pd.DataFrame, family: str, output_path: Path) -> None:
    channels = CHANNELS[family]
    fig, axes = plt.subplots(len(channels), 1, figsize=(11, 9), sharex=True)
    for ax, channel in zip(axes, channels):
        for vial in VIALS:
            group = frame.loc[
                (frame.vial == vial) & (frame.measurement_status == "measured")
            ]
            ax.plot(
                group.seconds_since_first_labeled_in_fill_frame,
                group[channel],
                marker="o",
                markersize=4,
                linewidth=1.7,
                color=VIAL_COLORS[vial],
                label=f"Vial {vial} ({len(group)} measured)",
            )
        ax.set_ylabel(CHANNEL_LABELS[channel])
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best", frameon=False)
    max_elapsed = frame.seconds_since_first_labeled_in_fill_frame.max()
    axes[-1].set_xlim(-0.5, max_elapsed + 1)
    axes[-1].set_xlabel(
        "Seconds since the first frame labeled in_fill=1 for this vial"
    )
    fig.suptitle(f"Recipe 8 preliminary {family} values on labeled fill timeline")
    fig.text(
        0.5,
        0.01,
        "Color points stop where ROI measurements stop; later labeled frames have no color value.",
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.97))
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def plot_coverage(frame: pd.DataFrame, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 3.5))
    y_positions = {10: 2, 11: 1, 12: 0}
    for vial in VIALS:
        group = frame.loc[frame.vial == vial]
        elapsed = group.seconds_since_first_labeled_in_fill_frame
        measured = group.measurement_status == "measured"
        y = y_positions[vial]
        ax.scatter(elapsed[measured], [y] * int(measured.sum()),
                   marker="o", s=38, color=VIAL_COLORS[vial],
                   label="Measured ROI" if vial == 10 else None)
        ax.scatter(elapsed[~measured], [y] * int((~measured).sum()),
                   marker="x", s=38, color="#777777",
                   label="Excluded from ROI measurement" if vial == 10 else None)
    ax.set_yticks([2, 1, 0], ["Vial 10", "Vial 11", "Vial 12"])
    ax.set_xlabel("Seconds since first frame labeled in_fill=1 for that vial")
    ax.set_title("Recipe 8 frame coverage across each labeled in-fill segment")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(loc="upper right", frameon=False)
    fig.text(
        0.5,
        0.01,
        "Gray crosses have timestamps and labels, but no usable color measurement.",
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def analyze(labels_path: Path, measurements_path: Path, exclusions_path: Path, output_dir: Path):
    frame, summary = build_timeline(labels_path, measurements_path, exclusions_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_dir / "recipe_8_labeled_fill_timeline.csv", index=False)
    summary.to_csv(output_dir / "recipe_8_fill_window_summary.csv", index=False)
    plot_channels(frame, "RGB", output_dir / "recipe_8_rgb_vs_labeled_fill_time.png")
    plot_channels(frame, "HSV", output_dir / "recipe_8_hsv_vs_labeled_fill_time.png")
    plot_coverage(frame, output_dir / "recipe_8_frame_coverage.png")
    return frame, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--labels",
        type=Path,
        default=Path("data/raw/recipe7/labels_video5_frame_labels.csv"),
    )
    parser.add_argument(
        "--measurements",
        type=Path,
        default=Path("results/recipe_8/recipe_8_manual_roi_measurements.csv"),
    )
    parser.add_argument(
        "--exclusions",
        type=Path,
        default=Path("results/recipe_8/recipe_8_excluded_frames.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/temporal_analysis/recipe_8_fill_timeline"),
    )
    args = parser.parse_args()
    frame, summary = analyze(args.labels, args.measurements, args.exclusions, args.output_dir)
    print(f"Saved {len(frame)} labeled frames and {len(summary)} fill windows")
    print(summary[[
        "vial", "labeled_in_fill_frame_count", "first_to_last_labeled_frame_span_s",
        "measured_frame_count", "excluded_roi_frame_count", "last_measured_elapsed_s",
    ]].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
