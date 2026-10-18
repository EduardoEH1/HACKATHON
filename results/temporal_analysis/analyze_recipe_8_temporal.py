"""Plot preliminary Recipe 8 RGB/HSV measurements over relative time per vial."""

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
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


CHANNELS = {
    "RGB": ["r_mean", "g_mean", "b_mean"],
    "HSV": ["h_mean_opencv", "s_mean_opencv", "v_mean_opencv"],
}
VIALS = (10, 11, 12)
COLORS = {10: "#1976d2", 11: "#ef6c00", 12: "#2e7d32"}


def add_relative_time(measurements: pd.DataFrame) -> pd.DataFrame:
    """Sort rows and calculate seconds since each vial's first sampled frame."""
    required = {
        "recipe_id",
        "vial",
        "filename",
        "timestamp",
        "video_s",
        *CHANNELS["RGB"],
        *CHANNELS["HSV"],
    }
    missing = required - set(measurements.columns)
    if missing:
        raise ValueError(f"Measurement CSV is missing columns: {sorted(missing)}")

    frame = measurements.copy()
    frame = frame.loc[frame["recipe_id"] == 8].copy()
    frame["vial"] = pd.to_numeric(frame["vial"], errors="raise").astype(int)
    frame = frame.loc[frame["vial"].isin(VIALS)].copy()
    if set(frame["vial"].unique()) != set(VIALS):
        raise ValueError("Expected measurements for Vials 10, 11, and 12")
    frame["video_s"] = pd.to_numeric(frame["video_s"], errors="raise")
    frame = frame.sort_values(["vial", "video_s", "filename"]).reset_index(drop=True)
    first_time = frame.groupby("vial")["video_s"].transform("min")
    frame["elapsed_s"] = frame["video_s"] - first_time
    frame["sample_index"] = frame.groupby("vial").cumcount()
    return frame


def summarize(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for vial, group in frame.groupby("vial", sort=True):
        x = group["elapsed_s"].to_numpy(dtype=float)
        for family, channels in CHANNELS.items():
            for channel in channels:
                values = group[channel].to_numpy(dtype=float)
                slope = float("nan")
                if len(values) > 1 and x.max() > x.min():
                    slope = float(np.polyfit(x, values, 1)[0])
                rows.append(
                    {
                        "recipe_id": 8,
                        "vial": int(vial),
                        "color_space": family,
                        "channel": channel,
                        "sample_count": len(values),
                        "elapsed_start_s": float(x.min()),
                        "elapsed_end_s": float(x.max()),
                        "mean": float(values.mean()),
                        "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
                        "min": float(values.min()),
                        "max": float(values.max()),
                        "first": float(values[0]),
                        "last": float(values[-1]),
                        "last_minus_first": float(values[-1] - values[0]),
                        "linear_slope_per_s": slope,
                        "status": "preliminary temporal description; not a threshold",
                    }
                )
    return pd.DataFrame(rows)


def plot_family(frame: pd.DataFrame, family: str, output: Path) -> None:
    channels = CHANNELS[family]
    labels = {
        "r_mean": "Red (0–255)",
        "g_mean": "Green (0–255)",
        "b_mean": "Blue (0–255)",
        "h_mean_opencv": "Hue (OpenCV 0–179)",
        "s_mean_opencv": "Saturation (0–255)",
        "v_mean_opencv": "Value / brightness (0–255)",
    }
    fig, axes = plt.subplots(len(channels), 1, figsize=(10, 9), sharex=True)
    for ax, channel in zip(axes, channels):
        for vial, group in frame.groupby("vial", sort=True):
            ax.plot(
                group["elapsed_s"],
                group[channel],
                color=COLORS[int(vial)],
                marker="o",
                linewidth=1.8,
                markersize=4,
                label=f"Vial {int(vial)} (n={len(group)})",
            )
        ax.set_ylabel(labels[channel])
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best", frameon=False)
    axes[-1].set_xlabel(
        "Seconds since the first retained measurement for each vial"
    )
    fig.suptitle(f"Recipe 8 preliminary {family} measurements over time")
    fig.text(
        0.5,
        0.01,
        "Each vial's clock starts at its first selected frame; curves are not aligned to fill start.",
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.97))
    fig.savefig(output, dpi=160, bbox_inches="tight")
    plt.close(fig)


def analyze(input_csv: Path, output_dir: Path) -> pd.DataFrame:
    original = pd.read_csv(input_csv)
    frame = add_relative_time(original)
    output_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_dir / "recipe_8_temporal_measurements.csv", index=False)
    summarize(frame).to_csv(output_dir / "recipe_8_temporal_summary.csv", index=False)
    plot_family(frame, "RGB", output_dir / "recipe_8_rgb_over_time.png")
    plot_family(frame, "HSV", output_dir / "recipe_8_hsv_over_time.png")
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("results/recipe_8/recipe_8_manual_roi_measurements.csv"),
        help="Existing preliminary Recipe 8 measurement CSV",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("results/temporal_analysis")
    )
    args = parser.parse_args()
    result = analyze(args.input, args.output_dir)
    print(f"Saved temporal results for {len(result)} samples to {args.output_dir}")
    print(
        result.groupby("vial").agg(
            samples=("filename", "count"),
            duration_s=("elapsed_s", "max"),
        ).round(2)
    )


if __name__ == "__main__":
    main()
