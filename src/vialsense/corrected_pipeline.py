"""Rebuild separate Phase 1/2 results from corrected timing and video colors.

The input snapshots are from Dataset 2 and Salah's color-check branch. No
original result is overwritten. The new color references use only the same
automatic liquid finder that supplies measurements to the detector.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .anomaly import CHANNELS, color_distance, fit_model, score_measurement, stage_for
from .anomaly_data import load_phase1_timelines, summarize_profiles

INPUT_NAMES = {
    "old": "video5_frame_labels_original.csv",
    "corrected": "video5_frame_labels_corrected.csv",
    "vials": "video5_vial_recipes.csv",
    "video": "frame_colors.csv",
}
SOURCE_COMMIT = "f1c91958ffd6e91abf7f6e74014a78e9ed23f9fc"
BOUNDARY_REVIEW_S = 1.0


def load_inputs(input_dir: Path) -> dict[str, pd.DataFrame]:
    data = {key: pd.read_csv(input_dir / name) for key, name in INPUT_NAMES.items()}
    old, corrected, vials, video = (data[key] for key in INPUT_NAMES)
    if len(old) != len(corrected) or set(old.filename) != set(corrected.filename):
        raise ValueError("original and corrected still-label filenames differ")
    if old.filename.duplicated().any() or corrected.filename.duplicated().any():
        raise ValueError("still labels contain duplicate filenames")
    if vials.vial.duplicated().any() or set(vials.recipe_id.astype(int)) != set(range(5, 15)):
        raise ValueError("vial recipe table is missing recipes or has duplicate vials")
    if not video.phase.isin(("fill", "after_fill")).all():
        raise ValueError("unknown video phase")
    return data


def vial_at_time(times: pd.Series, vials: pd.DataFrame) -> pd.Series:
    """Assign video-time points to nonoverlapping vial fill windows."""
    assigned = pd.Series(pd.NA, index=times.index, dtype="Int64")
    for vial in vials.itertuples(index=False):
        inside = times.between(vial.start_s, vial.end_s, inclusive="both")
        if assigned[inside].notna().any():
            raise ValueError("overlapping vial fill windows")
        assigned.loc[inside] = int(vial.vial)
    return assigned


def build_label_audit(old: pd.DataFrame, corrected: pd.DataFrame, vials: pd.DataFrame) -> pd.DataFrame:
    """Check corrected labels against fill windows and mark uncertain stills."""
    old = old[["filename", "video_s", "in_fill", "vial", "recipe_id"]].rename(columns={
        "video_s": "old_video_s", "in_fill": "old_in_fill", "vial": "old_vial",
        "recipe_id": "old_recipe_id",
    })
    fixed = corrected[["filename", "matched_video_s", "match_score", "video_s_corrected",
                       "clock_fit_outlier", "in_fill", "vial", "recipe_id", "fill_progress"]].rename(columns={
        "in_fill": "corrected_in_fill", "vial": "corrected_vial",
        "recipe_id": "corrected_recipe_id", "fill_progress": "corrected_fill_progress",
    })
    audit = old.merge(fixed, on="filename", validate="one_to_one")
    expected = vial_at_time(audit.video_s_corrected, vials)
    same = expected.eq(audit.corrected_vial.astype("Int64")).fillna(False)
    both_empty = expected.isna() & audit.corrected_vial.isna()
    if not (same | both_empty).all() or not (audit.corrected_in_fill.eq(expected.notna().astype(int))).all():
        raise ValueError("corrected still labels disagree with the vial fill windows")
    audit["matched_video_vial"] = vial_at_time(audit.matched_video_s, vials)
    direct_same = audit.matched_video_vial.eq(expected).fillna(False)
    audit["direct_match_disagrees"] = ~(direct_same | (audit.matched_video_vial.isna() & expected.isna()))
    boundaries = np.r_[vials.start_s.to_numpy(float), vials.end_s.to_numpy(float)]
    audit["nearest_fill_boundary_s"] = np.min(
        np.abs(audit.video_s_corrected.to_numpy(float)[:, None] - boundaries[None, :]), axis=1,
    )
    audit["boundary_review"] = (
        audit.clock_fit_outlier.astype(bool)
        | audit.direct_match_disagrees
        | audit.nearest_fill_boundary_s.lt(BOUNDARY_REVIEW_S)
    )
    audit["review_reason"] = audit.apply(
        lambda row: "; ".join(reason for test, reason in (
            (row.clock_fit_outlier, "clock_fit_outlier"),
            (row.direct_match_disagrees, "direct_match_disagrees"),
            (row.nearest_fill_boundary_s < BOUNDARY_REVIEW_S, "within_1s_of_boundary"),
        ) if test), axis=1,
    )
    audit["still_use_status"] = np.select(
        [audit.corrected_in_fill.eq(0), audit.boundary_review],
        ["between_fills", "review_boundary"], default="candidate_in_fill",
    )
    return audit.sort_values("old_video_s").reset_index(drop=True)


def relabel_saved_stills(repo_root: Path, audit: pd.DataFrame) -> pd.DataFrame:
    """Join old pixel values by filename; keep them separate from video colors."""
    old = load_phase1_timelines(repo_root)
    measured = old[old.usable_measurement].copy().rename(columns={
        "vial": "original_vial", "recipe_id": "original_recipe_id",
        "fill_progress": "original_fill_progress",
    })
    keep = ["filename", "corrected_vial", "corrected_recipe_id", "corrected_in_fill",
            "corrected_fill_progress", "video_s_corrected", "boundary_review", "review_reason"]
    out = measured.merge(audit[keep], on="filename", validate="one_to_one")
    out["reuse_status"] = np.select(
        [out.corrected_in_fill.eq(0), out.boundary_review],
        ["outside_corrected_fill", "boundary_review"],
        default="pixel_value_requires_roi_review",
    )
    columns = ["filename", "original_recipe_id", "original_vial", "original_fill_progress",
               "corrected_recipe_id", "corrected_vial", "corrected_in_fill",
               "corrected_fill_progress", "video_s_corrected", "reuse_status", "review_reason",
               *CHANNELS]
    return out[columns].sort_values("filename").reset_index(drop=True)


def prepare_video_timeline(video: pd.DataFrame, vials: pd.DataFrame) -> pd.DataFrame:
    """Keep each saved video image once and retain only reliable fill colors."""
    # The extraction script rounded three pairs of filenames to the same 0.1 s.
    # The later image overwrote the earlier file, so keep its later label row.
    video = video.drop_duplicates("filename", keep="last")
    fill = video[video.phase.eq("fill")].copy()
    fill = fill.merge(vials[["vial", "recipe_id", "start_s", "end_s", "duration_s"]],
                      on="vial", how="left", suffixes=("", "_table"), validate="many_to_one")
    if fill.start_s.isna().any() or not fill.recipe_id.eq(fill.recipe_id_table).all():
        raise ValueError("video frame recipe and vial mapping disagree with the vial table")
    if not (fill.video_s - fill.start_s).ge(-0.05).all() or not (fill.video_s - fill.end_s).le(0.05).all():
        raise ValueError("video frame timestamp lies outside its fill window")
    if not ((fill.video_s - fill.start_s) / fill.duration_s - fill.fill_progress).abs().le(0.01).all():
        raise ValueError("video fill progress disagrees with its fill window")
    good_values = fill[list(CHANNELS)].notna().all(axis=1)
    for name in (*CHANNELS[:3], *CHANNELS[4:]):
        good_values &= fill[name].between(0, 255)
    good_values &= fill[CHANNELS[3]].between(0, 179)
    fill["measurement_status"] = np.select(
        [~fill.found_vial, ~fill.found_liquid, fill.confidence.ne("high"), ~good_values],
        ["excluded_no_vial", "excluded_no_liquid", "excluded_low_confidence", "excluded_invalid_color"],
        default="measured_high",
    )
    fill["usable_measurement"] = fill.measurement_status.eq("measured_high")
    fill["elapsed_fill_s"] = fill.video_s - fill.start_s
    fill["stage"] = fill.fill_progress.map(stage_for)
    # Preserve exclusion status; blank unusable color columns in analysis files.
    fill.loc[~fill.usable_measurement, list(CHANNELS)] = np.nan
    return fill.drop(columns=["recipe_id_table"]).sort_values(["recipe_id", "vial", "video_s"]).reset_index(drop=True)


def score_salah_reading(
    model: dict[str, Any], reading: Mapping[str, Any], *, recipe_id: int | None = None,
    fill_progress: float | None = None, timestamp: str | None = None,
) -> dict[str, Any]:
    """Adapter for `liquid_finder.Detection.to_dict()` or `frame_colors.csv` rows.

    Live Detection output has no recipe or progress; machine context supplies
    those two fields. A low-confidence/no-liquid reading always abstains.
    """
    if timestamp is None:
        if reading.get("time") is not None:
            timestamp = str(reading["time"])
        elif reading.get("video_s") is not None:
            timestamp = f"video5:{float(reading['video_s']):.3f}s"
    recipe = recipe_id if recipe_id is not None else reading.get("recipe_id")
    progress = fill_progress if fill_progress is not None else reading.get("fill_progress")
    try:
        if pd.isna(recipe) or pd.isna(progress):
            raise ValueError("missing machine context")
        recipe_number, progress_number = int(recipe), float(progress)
    except (TypeError, ValueError):
        return {"recipe_id": recipe, "fill_progress": progress, "timestamp": timestamp,
                "anomaly_score": None, "status": "invalid_input",
                "reason": "recipe_id and fill_progress are required from the machine timeline"}
    reliable = reading.get("found_vial") == True and reading.get("confidence") == "high"
    visible = reading.get("found_liquid") == True
    rgb = tuple(reading.get(c) for c in CHANNELS[:3])
    hsv = tuple(reading.get(c) for c in CHANNELS[3:])
    return score_measurement(
        model, recipe_id=recipe_number, rgb=rgb, hsv=hsv,
        fill_progress=progress_number, timestamp=timestamp,
        liquid_visible=bool(visible), measurement_reliable=bool(reliable),
    )


def fit_corrected_model(fill: pd.DataFrame, vials: pd.DataFrame) -> dict[str, Any]:
    """Train on each recipe's last vial only, a provisional flushed candidate."""
    last_vials = vials.groupby("recipe_id").vial.max().astype(int).to_dict()
    reliable = fill[fill.usable_measurement].copy()
    training = reliable[reliable.apply(lambda row: int(row.vial) == last_vials[int(row.recipe_id)], axis=1)]
    initial = fit_model(training, min_stage_samples=4, min_stage_vials=1)
    # A near-static reference stage can produce an unrealistically tiny limit.
    # Derive a common measurement-variation floor from reference vials only;
    # never tune it on the other two vials used for evaluation.
    residuals = []
    for row in training.itertuples(index=False):
        entry = initial["recipes"][str(int(row.recipe_id))][stage_for(float(row.fill_progress))]
        if entry["available"]:
            observed = np.array([getattr(row, column) for column in CHANNELS], dtype=float)
            residuals.append(color_distance(observed, np.array(entry["center"], dtype=float)))
    shared_floor = max(2.0, float(np.quantile(residuals, 0.95)))
    model = fit_model(training, min_stage_samples=4, min_stage_vials=1,
                      min_distance_percent=shared_floor)
    if set(model["recipes"]) != {str(r) for r in range(5, 15)}:
        raise ValueError("at least one recipe lacks a final-vial reference")
    model["reference_selection"] = "last vial per recipe; assumed most flushed, not confirmed good"
    model["reference_status"] = "provisional; not confirmed normal"
    model["measurement_method"] = "Salah liquid_finder high-confidence video ROI"
    model["time_method"] = "video_s and vial fill windows; fill_progress 0..1"
    model["source_color_check_commit"] = SOURCE_COMMIT
    model["reference_vials"] = {str(k): int(v) for k, v in last_vials.items()}
    model["reference_only_variation_floor_percent"] = shared_floor
    return model


def evaluate_corrected(fill: pd.DataFrame, model: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Score all frames, but report independent evaluation on other vials."""
    rows = []
    for row in fill.itertuples(index=False):
        record = row._asdict()
        score = score_salah_reading(
            model, record, timestamp=f"video5:{record['video_s']:.3f}s",
        )
        rows.append({
            "filename": record["filename"], "recipe_id": int(record["recipe_id"]),
            "vial": int(record["vial"]), "video_s": record["video_s"],
            "elapsed_fill_s": record["elapsed_fill_s"], "fill_progress": record["fill_progress"],
            "measurement_status": record["measurement_status"],
            "confidence": record["confidence"],
            "split": ("reference" if int(record["vial"]) == model["reference_vials"][str(int(record["recipe_id"]))]
                      else "evaluation"),
            "anomaly_score": score["anomaly_score"], "status": score["status"],
            "reason": score["reason"], "stage": score.get("stage"),
            "reference_samples": score.get("reference_samples"),
            "reference_vials": score.get("reference_vials"),
            "reference_vial_id": score.get("reference_vial_id"),
            "reference_status": score.get("reference_status"),
        })
    predictions = pd.DataFrame(rows)
    summaries = []
    for (recipe, vial, split), group in predictions.groupby(["recipe_id", "vial", "split"]):
        scored = group[group.anomaly_score.notna()]
        flagged = group[group.status.eq("review_unusual")]
        summaries.append({
            "recipe_id": int(recipe), "vial": int(vial), "split": split,
            "labeled_fill_frames": len(group),
            "high_confidence_measurements": int(group.measurement_status.eq("measured_high").sum()),
            "scored_frames": len(scored), "review_unusual_frames": len(flagged),
            "first_scored_video_s": scored.video_s.min() if len(scored) else np.nan,
            "first_review_video_s": flagged.video_s.min() if len(flagged) else np.nan,
            "first_review_fill_progress": flagged.fill_progress.min() if len(flagged) else np.nan,
        })
    return predictions, pd.DataFrame(summaries)


def summarize_video(fill: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Coverage and descriptive RGB/HSV medians for each vial and recipe."""
    vial_rows = []
    for (recipe, vial), group in fill.groupby(["recipe_id", "vial"]):
        good = group[group.usable_measurement]
        row = {"recipe_id": int(recipe), "vial": int(vial),
               "labeled_fill_frames": len(group), "high_confidence_measurements": len(good),
               "low_confidence_frames": int(group.measurement_status.eq("excluded_low_confidence").sum()),
               "no_liquid_frames": int(group.measurement_status.eq("excluded_no_liquid").sum()),
               "first_measured_progress": good.fill_progress.min() if len(good) else np.nan,
               "last_measured_progress": good.fill_progress.max() if len(good) else np.nan}
        row.update({f"{col}_median": good[col].median() if len(good) else np.nan for col in CHANNELS})
        vial_rows.append(row)
    recipe_rows = []
    for recipe, group in fill.groupby("recipe_id"):
        good = group[group.usable_measurement]
        row = {"recipe_id": int(recipe), "vials": int(group.vial.nunique()),
               "labeled_fill_frames": len(group), "high_confidence_measurements": len(good),
               "excluded_frames": len(group) - len(good)}
        row.update({f"{col}_median": good[col].median() if len(good) else np.nan for col in CHANNELS})
        recipe_rows.append(row)
    return pd.DataFrame(vial_rows), pd.DataFrame(recipe_rows)


def save_reference_model(model: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")


def reference_summary(model: dict[str, Any]) -> pd.DataFrame:
    summary = summarize_profiles(model)
    summary["reference_vial_id"] = summary.recipe_id.map(
        {int(recipe): int(vial) for recipe, vial in model.get("reference_vials", {}).items()}
    )
    summary["reference_status"] = model.get(
        "reference_status", "provisional; not confirmed normal"
    )
    return summary
