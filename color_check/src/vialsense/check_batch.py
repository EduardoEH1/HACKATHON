"""Run the PASS/FLAG check on every measured frame for Recipes 5-14.

For each frame Eduardo measured:
  - if its photo is in results/recipe_N/annotated_images/, measure it from the photo
    (box shrunk by 3 px so his red outline is not counted)
  - otherwise use his saved RGB values (Recipe 6, whose photos are not in the repo)

Outputs (default folder results/color_check/):
  frame_checks.csv   one row per frame, the file Yen's screen reads
  vial_summary.csv   one row per vial, with the majority verdict

Run from the repo root:
    PYTHONPATH=src python -m vialsense.check_batch
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from vialsense.build_references import DEFAULT_OUTPUT, load_all_measurements, load_references
from vialsense.colorcheck import DEFAULT_THRESHOLD, check_color, load_image, measure_liquid

INSET = 3  # pixels trimmed off each side to skip the red box drawn on annotated photos


def frame_color(row: pd.Series, results_dir: Path) -> tuple[tuple[float, float, float], str]:
    photo = results_dir / f"recipe_{row.recipe_id}" / "annotated_images" / row.filename
    if photo.is_file():
        roi = (int(row.roi_x1) + INSET, int(row.roi_y1) + INSET,
               int(row.roi_x2) - INSET, int(row.roi_y2) - INSET)
        m = measure_liquid(load_image(photo), roi)
        return (m["r"], m["g"], m["b"]), "photo"
    return (row.r_mean, row.g_mean, row.b_mean), "saved_csv"


def run(results_dir: Path, references: dict, threshold: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = load_all_measurements(results_dir).sort_values(["recipe_id", "vial", "timestamp"])
    rows = []
    for _, row in data.iterrows():
        rgb, source = frame_color(row, results_dir)
        result = check_color(rgb, row.recipe_id, references, threshold)
        rows.append({
            "recipe_id": row.recipe_id, "vial": row.vial, "filename": row.filename,
            "timestamp": row.timestamp, "source": source,
            "seen_r": round(rgb[0], 1), "seen_g": round(rgb[1], 1), "seen_b": round(rgb[2], 1),
            "expected_r": round(result.expected_rgb[0], 1), "expected_g": round(result.expected_rgb[1], 1),
            "expected_b": round(result.expected_rgb[2], 1),
            "delta_e": round(result.delta_e, 2), "threshold": threshold,
            "status": result.status, "note": result.note,
            "reference_confidence": references[row.recipe_id]["confidence"],
        })
    frames = pd.DataFrame(rows)

    summary = []
    for (recipe_id, vial), g in frames.groupby(["recipe_id", "vial"]):
        flags = int((g.status == "FLAG").sum())
        carry = int(g.note.str.contains("carryover").sum())
        summary.append({
            "recipe_id": recipe_id, "vial": vial, "frames": len(g), "flagged_frames": flags,
            "median_delta_e": round(g.delta_e.median(), 2),
            "vial_status": "FLAG" if flags > len(g) / 2 else "PASS",
            "carryover_hint": "yes" if carry > len(g) / 2 else "",
        })
    return frames, pd.DataFrame(summary)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", type=Path, default=Path("results"))
    parser.add_argument("--references", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--output-dir", type=Path, default=Path("results/color_check"))
    args = parser.parse_args()

    frames, summary = run(args.results, load_references(args.references), args.threshold)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    frames.to_csv(args.output_dir / "frame_checks.csv", index=False)
    summary.to_csv(args.output_dir / "vial_summary.csv", index=False)
    print(f"Checked {len(frames)} frames ({(frames.source == 'photo').sum()} from photos). "
          f"Saved to {args.output_dir}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
