"""Build Phase 2 profiles/evaluation or score one external measurement."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .anomaly import fit_model, load_model, save_model, score_measurement
from .anomaly_data import (evaluate_leave_one_vial_out, load_phase1_timelines,
                           summarize_evaluation, summarize_profiles)

ROOT = Path(__file__).resolve().parents[2]


def build(root: Path, output_dir: Path) -> None:
    data = load_phase1_timelines(root)
    output_dir.mkdir(parents=True, exist_ok=True)
    usable = data[data.usable_measurement]
    model = fit_model(usable)
    predictions = evaluate_leave_one_vial_out(data)
    save_model(model, output_dir / "provisional_model.json")
    summarize_profiles(model).to_csv(output_dir / "reference_stage_summary.csv", index=False)
    predictions.to_csv(output_dir / "held_out_vial_predictions.csv", index=False)
    summary = summarize_evaluation(predictions)
    summary.to_csv(output_dir / "held_out_vial_summary.csv", index=False)
    print(f"Read {len(data)} labeled frames; {len(usable)} usable color measurements.")
    print(f"Held-out frames with scores: {predictions.anomaly_score.notna().sum()}.")
    print(f"Provisional review flags: {(predictions.status == 'review_unusual').sum()}.")
    print(f"Saved model, stage summary, and held-out evaluation to {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build", help="Fit from checked-in CSVs and evaluate on held-out vials")
    build_parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    build_parser.add_argument("--output-dir", type=Path, default=ROOT / "results/anomaly_detection")
    score_parser = sub.add_parser("score", help="score one RGB/HSV observation")
    score_parser.add_argument("--model", type=Path, default=ROOT / "results/anomaly_detection/provisional_model.json")
    score_parser.add_argument("--recipe-id", type=int, required=True)
    score_parser.add_argument("--rgb", type=float, nargs=3, metavar=("R", "G", "B"))
    score_parser.add_argument("--hsv", type=float, nargs=3, metavar=("H", "S", "V"))
    score_parser.add_argument("--progress", type=float, required=True, help="0 to 1 across the labeled filling window")
    score_parser.add_argument("--timestamp", help="camera/source timestamp for tracing the observation")
    score_parser.add_argument("--liquid-not-visible", action="store_true")
    score_parser.add_argument("--unreliable", action="store_true", help="ROI or color value is unreliable")
    args = parser.parse_args()
    if args.command == "build":
        build(args.root.resolve(), args.output_dir.resolve())
    else:
        result = score_measurement(
            load_model(args.model), recipe_id=args.recipe_id, rgb=tuple(args.rgb) if args.rgb else None,
            hsv=tuple(args.hsv) if args.hsv else None, fill_progress=args.progress,
            timestamp=args.timestamp, liquid_visible=not args.liquid_not_visible,
            measurement_reliable=not args.unreliable,
        )
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
