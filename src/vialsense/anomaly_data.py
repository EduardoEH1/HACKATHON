"""Read existing Phase 1 timelines and evaluate the provisional detector by vial."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .anomaly import CHANNELS, STAGES, fit_model, score_measurement

RECIPES = tuple(range(5, 15))


def load_phase1_timelines(root: Path) -> pd.DataFrame:
    """Use checked-in temporal CSVs only; no raw images or invented labels."""
    frames = []
    for recipe_id in RECIPES:
        if recipe_id == 8:
            path = root / "results/temporal_analysis/recipe_8_original_image_review/recipe_8_temporal_measurements_updated.csv"
            elapsed_column = "elapsed_since_first_labeled_in_fill_s"
        else:
            path = root / f"results/temporal_analysis/recipe_{recipe_id}/recipe_{recipe_id}_labeled_timeline.csv"
            elapsed_column = "elapsed_fill_s"
        source = pd.read_csv(path)
        required = {"filename", "timestamp", "vial", "recipe_id", elapsed_column, *CHANNELS}
        if missing := required - set(source.columns):
            raise ValueError(f"{path}: missing columns {sorted(missing)}")
        if not source.recipe_id.eq(recipe_id).all() or not source.in_fill.eq(1).all():
            raise ValueError(f"{path}: rows do not match Recipe {recipe_id} in-fill labels")
        if source.filename.duplicated().any():
            raise ValueError(f"{path}: duplicate filenames")
        if "measurement_status" not in source:
            # The older Recipe 6 timeline records this in `status` alone.
            source["measurement_status"] = source["status"]
        source["phase1_status"] = source["measurement_status"] if recipe_id == 8 else source["status"]
        source["elapsed_fill_s"] = pd.to_numeric(source[elapsed_column], errors="coerce")
        duration = source.groupby("vial").elapsed_fill_s.transform("max")
        source["fill_progress"] = source.elapsed_fill_s / duration
        if source.fill_progress.isna().any() or not source.fill_progress.between(0, 1).all():
            raise ValueError(f"{path}: cannot derive labeled fill progress")
        # Recipe 8 has one relocated ROI explicitly marked cautious. Leave it
        # visible in coverage, but keep it out of model fitting and scoring.
        if recipe_id == 8:
            source["usable_measurement"] = source.measurement_status.eq("measured")
        else:
            source["usable_measurement"] = source.status.eq("measured")
        source["usable_measurement"] &= source[list(CHANNELS)].notna().all(axis=1)
        source["source_timeline"] = str(path.relative_to(root))
        frames.append(source[["recipe_id", "vial", "filename", "timestamp", "elapsed_fill_s",
                              "fill_progress", "measurement_status", "phase1_status", "source_timeline",
                              "usable_measurement", *CHANNELS]])
    data = pd.concat(frames, ignore_index=True)
    if data[list(CHANNELS)].notna().any(axis=1).sum() < data.usable_measurement.sum():
        raise ValueError("measurement coverage accounting failed")
    return data


def _score_row(model: dict, row: pd.Series) -> dict:
    usable = bool(row.usable_measurement)
    result = score_measurement(
        model,
        recipe_id=int(row.recipe_id),
        rgb=tuple(float(row[c]) for c in CHANNELS[:3]) if usable else None,
        hsv=tuple(float(row[c]) for c in CHANNELS[3:]) if usable else None,
        fill_progress=float(row.fill_progress),
        timestamp=str(row.timestamp),
        measurement_reliable=bool(row.phase1_status not in ("excluded_roi", "remain_excluded", "measured_with_caution")),
    )
    return {
        "recipe_id": int(row.recipe_id), "vial": int(row.vial), "filename": row.filename,
        "timestamp": row.timestamp, "elapsed_fill_s": row.elapsed_fill_s,
        "fill_progress": row.fill_progress,
        "phase1_measurement_status": row.measurement_status,
        "phase1_status": row.phase1_status,
        "usable_measurement": usable,
        **{key: value for key, value in result.items() if key not in ("recipe_id", "timestamp", "fill_progress")},
    }


def evaluate_leave_one_vial_out(data: pd.DataFrame) -> pd.DataFrame:
    """Score each vial using a profile fitted only on other vials of its recipe."""
    predictions = []
    for recipe_id, recipe_rows in data.groupby("recipe_id"):
        for vial, held_out in recipe_rows.groupby("vial"):
            training = recipe_rows[(recipe_rows.vial != vial) & recipe_rows.usable_measurement]
            model = fit_model(training)
            # A recipe with one measured vial has no profile; use an empty one.
            if str(int(recipe_id)) not in model["recipes"]:
                model["recipes"][str(int(recipe_id))] = {
                    stage: {"samples": 0, "vials": 0, "vial_ids": [], "available": False}
                    for stage in STAGES
                }
            predictions.extend(_score_row(model, row) for _, row in held_out.iterrows())
    return pd.DataFrame(predictions).sort_values(["recipe_id", "vial", "elapsed_fill_s"]).reset_index(drop=True)


def summarize_evaluation(predictions: pd.DataFrame) -> pd.DataFrame:
    summaries = []
    for (recipe_id, vial), rows in predictions.groupby(["recipe_id", "vial"]):
        scored = rows[rows.anomaly_score.notna()]
        flagged = rows[rows.status == "review_unusual"]
        summaries.append({
            "recipe_id": int(recipe_id), "vial": int(vial),
            "labeled_frames": int(len(rows)), "usable_measurements": int(rows.usable_measurement.sum()),
            "scored_frames": int(len(scored)), "review_unusual_frames": int(len(flagged)),
            "insufficient_reference_frames": int((rows.status == "insufficient_reference").sum()),
            "unreliable_or_missing_frames": int(rows.status.isin(("unreliable_measurement", "missing_measurement")).sum()),
            "first_scored_elapsed_s": float(scored.elapsed_fill_s.min()) if len(scored) else np.nan,
            "first_review_elapsed_s": float(flagged.elapsed_fill_s.min()) if len(flagged) else np.nan,
            "max_anomaly_score": float(scored.anomaly_score.max()) if len(scored) else np.nan,
        })
    return pd.DataFrame(summaries)


def summarize_profiles(model: dict) -> pd.DataFrame:
    rows = []
    for recipe_id, stages in model["recipes"].items():
        for stage, entry in stages.items():
            row = {"recipe_id": int(recipe_id), "stage": stage, "reference_available": entry["available"],
                   "samples": entry["samples"], "vials": entry["vials"],
                   "vial_ids": ",".join(map(str, entry["vial_ids"])),
                   "within_q95_percent": entry.get("within_q95", np.nan),
                   "cross_vial_q95_percent": entry.get("cross_vial_q95", np.nan),
                   "reference_limit_percent": entry.get("reference_limit", np.nan)}
            row.update({name: value for name, value in zip(CHANNELS, entry.get("center", []))})
            rows.append(row)
    return pd.DataFrame(rows)
