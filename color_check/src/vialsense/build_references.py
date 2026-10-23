"""Build the expected color for each recipe from Eduardo's saved measurements.

Rule used (first version)
-------------------------
The LAST vial of each recipe is the reference. Reason: carryover hits the first
vials after a recipe switch. By the last vial, the pipes have flushed, so its
color is the best available guess of the clean recipe color.

This is an assumption, not ground truth. Replace these references with
known-good vials from the organizers once available.

Run from the repo root:
    PYTHONPATH=src python -m vialsense.build_references
"""

from __future__ import annotations

import argparse
import glob
from pathlib import Path

import pandas as pd

from vialsense.colorcheck import rgb_to_lab

DEFAULT_OUTPUT = Path("references/recipe_colors.csv")


def load_all_measurements(results_dir: Path = Path("results")) -> pd.DataFrame:
    """Load every per-frame measurement CSV for Recipes 5-14 into one table."""
    files = sorted(glob.glob(str(results_dir / "recipe_*" / "recipe_*_manual_roi_measurements.csv")))
    files += glob.glob(str(results_dir / "recipe_6" / "recipe_6_preliminary_measurements.csv"))
    if not files:
        raise FileNotFoundError(f"No measurement CSVs under {results_dir}")
    data = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    data["recipe_id"] = data["recipe_id"].astype(int)
    data["vial"] = data["vial"].astype(int)
    return data


def build_references(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    recipe_order = sorted(data["recipe_id"].unique())
    for i, recipe_id in enumerate(recipe_order):
        recipe = data[data["recipe_id"] == recipe_id]
        last_vial = recipe["vial"].max()
        ref = recipe[recipe["vial"] == last_vial]
        # Median resists single odd frames better than the mean.
        r, g, b = ref[["r_mean", "g_mean", "b_mean"]].median()
        l, a, b_lab = rgb_to_lab((r, g, b))
        first = recipe.iloc[0]
        rows.append({
            "recipe_id": recipe_id,
            "previous_recipe": recipe_order[i - 1] if i > 0 else "",
            "ref_r": round(r, 2), "ref_g": round(g, 2), "ref_b": round(b, 2),
            "ref_L": round(l, 2), "ref_a": round(a, 2), "ref_b_lab": round(b_lab, 2),
            "reference_vial": last_vial,
            "reference_frames": len(ref),
            "confidence": "low" if len(ref) < 3 else "ok",
            "t100_ml": first.get("t100_ml"), "t200_ml": first.get("t200_ml"),
            "t400_ml": first.get("t400_ml"), "dispense_order": first.get("dispense_order"),
            "description": first.get("color_purpose") if pd.notna(first.get("color_purpose")) else "",
            "method": "median of last vial (assumed flushed); not validated",
        })
    return pd.DataFrame(rows)


def load_references(path: Path = DEFAULT_OUTPUT) -> dict:
    """Read references CSV into the dict format check_color() expects."""
    table = pd.read_csv(path)
    refs = {}
    for _, row in table.iterrows():
        prev = row["previous_recipe"]
        refs[int(row["recipe_id"])] = {
            "rgb": (row["ref_r"], row["ref_g"], row["ref_b"]),
            "previous_recipe": int(prev) if pd.notna(prev) and prev != "" else None,
            "confidence": row["confidence"],
        }
    return refs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", type=Path, default=Path("results"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    table = build_references(load_all_measurements(args.results))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.output, index=False)
    print(f"Saved {len(table)} recipe references to {args.output}")
    print(table[["recipe_id", "ref_r", "ref_g", "ref_b", "reference_vial",
                 "reference_frames", "confidence"]].to_string(index=False))


if __name__ == "__main__":
    main()
