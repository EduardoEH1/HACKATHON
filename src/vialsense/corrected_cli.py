"""Build versioned corrected results or score Salah's liquid-finder JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from .anomaly import CHANNELS, load_model
from .corrected_pipeline import (
    INPUT_NAMES, SOURCE_COMMIT, build_label_audit, evaluate_corrected,
    fit_corrected_model, load_inputs, prepare_video_timeline, reference_summary,
    relabel_saved_stills, save_reference_model, score_salah_reading,
    summarize_video,
)

ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = ROOT / "inputs/color_check"
OUTPUT_DIR = ROOT / "results/corrected"


def plot_channels(group: pd.DataFrame, columns: tuple[str, ...], title: str, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(3, 1, figsize=(8, 7), sharex=True)
    for vial, rows in group[group.usable_measurement].groupby("vial"):
        rows = rows.sort_values("fill_progress")
        for ax, column in zip(axes, columns):
            ax.plot(rows.fill_progress, rows[column], ".-", linewidth=1, markersize=3,
                    label=f"Vial {int(vial)}")
    for ax, column in zip(axes, columns):
        ax.set_ylabel(column)
        ax.grid(alpha=0.2)
        ax.axvline(1 / 3, color="gray", linestyle=":", linewidth=1)
        ax.axvline(2 / 3, color="gray", linestyle=":", linewidth=1)
    axes[0].legend(loc="best", fontsize=8)
    axes[-1].set_xlabel("Progress through labeled video fill window (0–1)")
    axes[-1].set_xlim(0, 1)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def build(repo_root: Path, input_dir: Path, output_dir: Path) -> None:
    data = load_inputs(input_dir)
    audit = build_label_audit(data["old"], data["corrected"], data["vials"])
    stills = relabel_saved_stills(repo_root, audit)
    fill = prepare_video_timeline(data["video"], data["vials"])
    vial_summary, recipe_summary = summarize_video(fill)
    model = fit_corrected_model(fill, data["vials"])
    predictions, evaluation_summary = evaluate_corrected(fill, model)

    phase1 = output_dir / "phase1"
    phase2 = output_dir / "phase2"
    phase1.mkdir(parents=True, exist_ok=True)
    phase2.mkdir(parents=True, exist_ok=True)
    audit.to_csv(output_dir / "label_audit.csv", index=False)
    stills.to_csv(output_dir / "legacy_stills_relabelled.csv", index=False)
    vial_summary.to_csv(phase1 / "vial_summary.csv", index=False)
    recipe_summary.to_csv(phase1 / "recipe_summary.csv", index=False)
    for recipe, rows in fill.groupby("recipe_id"):
        folder = phase1 / f"recipe_{int(recipe)}"
        folder.mkdir(parents=True, exist_ok=True)
        rows.to_csv(folder / "timeline.csv", index=False)
        vial_summary[vial_summary.recipe_id.eq(recipe)].to_csv(folder / "vial_summary.csv", index=False)
        plot_channels(rows, CHANNELS[:3], f"Recipe {int(recipe)}: corrected video RGB", folder / "rgb_over_fill.png")
        plot_channels(rows, CHANNELS[3:], f"Recipe {int(recipe)}: corrected video HSV", folder / "hsv_over_fill.png")
    save_reference_model(model, phase2 / "provisional_model.json")
    reference_summary(model).to_csv(phase2 / "reference_stage_summary.csv", index=False)
    predictions.to_csv(phase2 / "frame_predictions.csv", index=False)
    evaluation_summary.to_csv(phase2 / "vial_evaluation_summary.csv", index=False)
    hashes = {name: hashlib.sha256((input_dir / name).read_bytes()).hexdigest()
              for name in INPUT_NAMES.values()}
    (output_dir / "input_hashes.json").write_text(
        json.dumps({"color_check_commit": SOURCE_COMMIT, "sha256": hashes}, indent=2) + "\n",
        encoding="utf-8",
    )
    scored = predictions[(predictions.split == "evaluation") & predictions.anomaly_score.notna()]
    flagged = scored[scored.status.eq("review_unusual")]
    print(f"Still labels: {len(audit)}; uncertain boundary/clock rows: {audit.boundary_review.sum()}.")
    print(f"Original measured stills relabeled for audit: {len(stills)}; they were not used for new references.")
    print(f"Video fill frames: {len(fill)}; high-confidence colors: {fill.usable_measurement.sum()}.")
    print(f"Independent evaluation frames scored: {len(scored)}; provisional review flags: {len(flagged)}.")
    print(f"Saved versioned results under {output_dir}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build", help="rebuild corrected results from checked-in CSV snapshots")
    build_parser.add_argument("--repo-root", type=Path, default=ROOT)
    build_parser.add_argument("--input-dir", type=Path, default=INPUT_DIR)
    build_parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    score_parser = sub.add_parser("score", help="score one liquid-finder JSON reading from a file or stdin")
    score_parser.add_argument("--model", type=Path, default=OUTPUT_DIR / "phase2/provisional_model.json")
    score_parser.add_argument("--reading-file", type=Path, help="JSON from Salah's find_color command; stdin if omitted")
    score_parser.add_argument("--recipe-id", type=int, help="current machine recipe, required for live readings")
    score_parser.add_argument("--progress", type=float, help="current fill progress 0–1, required for live readings")
    score_parser.add_argument("--timestamp", help="source timestamp for tracing the observation")
    args = parser.parse_args()
    if args.command == "build":
        build(args.repo_root.resolve(), args.input_dir.resolve(), args.output_dir.resolve())
        return
    reading = json.loads(args.reading_file.read_text(encoding="utf-8") if args.reading_file else sys.stdin.read())
    result = score_salah_reading(load_model(args.model), reading, recipe_id=args.recipe_id,
                                 fill_progress=args.progress, timestamp=args.timestamp)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
