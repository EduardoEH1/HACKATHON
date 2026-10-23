"""Provisional, stage-aware comparison of measured vial color with recipe data.

This module consumes color measurements. It does not locate liquid in an image
or decide whether a vial is contaminated.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

CHANNELS = ("r_mean", "g_mean", "b_mean", "h_mean_opencv", "s_mean_opencv", "v_mean_opencv")
STAGES = ("early", "middle", "late")
MIN_STAGE_SAMPLES = 4
MIN_STAGE_VIALS = 2
MIN_DISTANCE_PERCENT = 2.0  # Numerical guard; not a product acceptance limit.
REVIEW_SCORE = 100.0  # Exploratory score boundary, not a contamination threshold.


def stage_for(progress: float) -> str:
    """Divide the label-derived fill window into three equal time bands."""
    if not np.isfinite(progress) or not 0 <= progress <= 1:
        raise ValueError("fill_progress must be a finite number from 0 to 1")
    if progress < 1 / 3:
        return "early"
    if progress < 2 / 3:
        return "middle"
    return "late"


def _hue_center(values: np.ndarray) -> float:
    angles = values * (2 * np.pi / 180)
    return float(np.arctan2(np.sin(angles).mean(), np.cos(angles).mean()) % (2 * np.pi) * 180 / (2 * np.pi))


def _center(matrix: np.ndarray) -> np.ndarray:
    center = np.median(matrix, axis=0)
    center[3] = _hue_center(matrix[:, 3])
    return center


def color_distance(sample: np.ndarray, center: np.ndarray) -> float:
    """RMS difference as percent of RGB/HSV channel range, with circular hue."""
    differences = np.abs(sample - center).astype(float)
    differences[:3] *= 100 / 255
    hue_gap = abs(float(sample[3]) - float(center[3]))
    differences[3] = min(hue_gap, 180 - hue_gap) * 100 / 90
    differences[4:] *= 100 / 255
    # OpenCV hue is unstable when a measurement is nearly gray.
    if min(float(sample[4]), float(center[4])) < 30:
        differences = np.delete(differences, 3)
    return float(np.sqrt(np.mean(differences**2)))


def fit_model(
    measurements: pd.DataFrame, *, min_stage_samples: int = MIN_STAGE_SAMPLES,
    min_stage_vials: int = MIN_STAGE_VIALS,
    min_distance_percent: float = MIN_DISTANCE_PERCENT,
) -> dict[str, Any]:
    """Fit one provisional three-stage profile for each recipe in a data frame.

    Required columns: recipe_id, vial, fill_progress, and CHANNELS. Only
    caller-approved, reliable measurements should be passed here.
    """
    if min_stage_samples < 1 or min_stage_vials < 1 or min_distance_percent <= 0:
        raise ValueError("reference requirements and distance floor must be positive")
    required = {"recipe_id", "vial", "fill_progress", *CHANNELS}
    missing = required - set(measurements.columns)
    if missing:
        raise ValueError(f"missing training columns: {sorted(missing)}")
    data = measurements.copy()
    for column in ("recipe_id", "vial", "fill_progress", *CHANNELS):
        data[column] = pd.to_numeric(data[column], errors="raise")
    if data[list(CHANNELS) + ["fill_progress"]].isna().any().any():
        raise ValueError("training measurements contain missing values")
    if not np.isfinite(data[list(CHANNELS) + ["fill_progress"]].to_numpy(float)).all():
        raise ValueError("training measurements contain non-finite values")
    if not data.fill_progress.between(0, 1).all():
        raise ValueError("training progress must be between 0 and 1")
    if not data[list(CHANNELS[:3]) + list(CHANNELS[4:])].ge(0).all().all() or not data[list(CHANNELS[:3]) + list(CHANNELS[4:])].le(255).all().all():
        raise ValueError("RGB and S/V training channels must be between 0 and 255")
    if not data[CHANNELS[3]].between(0, 179).all():
        raise ValueError("OpenCV hue training channel must be between 0 and 179")
    data["stage"] = data.fill_progress.map(stage_for)
    recipes: dict[str, Any] = {}
    for recipe_id, recipe_rows in data.groupby("recipe_id"):
        stages: dict[str, Any] = {}
        for stage in STAGES:
            rows = recipe_rows.loc[recipe_rows.stage == stage]
            n_vials = int(rows.vial.nunique())
            entry: dict[str, Any] = {
                "samples": int(len(rows)), "vials": n_vials,
                "vial_ids": sorted(int(v) for v in rows.vial.unique()),
                "available": len(rows) >= min_stage_samples and n_vials >= min_stage_vials,
            }
            if entry["available"]:
                matrix = rows[list(CHANNELS)].to_numpy(float)
                center = _center(matrix)
                distances = np.array([color_distance(sample, center) for sample in matrix])
                # Each vial is compared with the other training vials. This
                # captures between-vial variation that an in-sample median
                # would otherwise hide. No held-out evaluation vial is used.
                cross_vial = []
                if n_vials > 1:
                    for vial in rows.vial.unique():
                        others = rows.loc[rows.vial != vial, list(CHANNELS)].to_numpy(float)
                        own = rows.loc[rows.vial == vial, list(CHANNELS)].to_numpy(float)
                        other_center = _center(others)
                        cross_vial.extend(color_distance(sample, other_center) for sample in own)
                within_q95 = float(np.quantile(distances, 0.95))
                cross_vial_q95 = float(np.quantile(cross_vial, 0.95)) if cross_vial else None
                entry["center"] = [float(value) for value in center]
                entry["within_q95"] = within_q95
                entry["cross_vial_q95"] = cross_vial_q95
                entry["reference_limit"] = float(max(within_q95, cross_vial_q95 or 0, min_distance_percent))
            stages[stage] = entry
        recipes[str(int(recipe_id))] = stages
    return {
        "model_version": 1,
        "method": ("three equal label-time stages; RGB/HSV channel distance; training and cross-vial 95th percentiles"
                   if min_stage_vials > 1 else
                   "three equal video-time stages; RGB/HSV channel distance; single-reference-vial 95th percentile"),
        "min_stage_samples": min_stage_samples,
        "min_stage_vials": min_stage_vials,
        "min_distance_percent": min_distance_percent,
        "review_score": REVIEW_SCORE,
        "recipes": recipes,
    }


def save_model(model: dict[str, Any], path: str | Path) -> None:
    Path(path).write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")


def load_model(path: str | Path) -> dict[str, Any]:
    model = json.loads(Path(path).read_text(encoding="utf-8"))
    if model.get("model_version") != 1:
        raise ValueError("unsupported model version")
    return model


def score_measurement(
    model: dict[str, Any], *, recipe_id: int, rgb: tuple[float, float, float] | None,
    hsv: tuple[float, float, float] | None, fill_progress: float | None,
    timestamp: str | None = None, liquid_visible: bool = True,
    measurement_reliable: bool = True,
) -> dict[str, Any]:
    """Score a supplied color measurement; never infer liquid visibility.

    A score of 100 is the provisional training-stage boundary; values may exceed
    100. The status `review_unusual` requests human review, not an automatic
    contamination or product-failure decision.
    """
    result: dict[str, Any] = {
        "recipe_id": recipe_id, "timestamp": timestamp, "fill_progress": fill_progress,
        "stage": None, "anomaly_score": None, "status": None, "reason": None,
        "distance_percent": None, "reference_limit_percent": None,
        "reference_samples": 0, "reference_vials": 0,
        "reference_vial_id": None, "reference_status": None,
    }
    if not liquid_visible or not measurement_reliable:
        result.update(status="unreliable_measurement", reason="liquid not visible or ROI/measurement not reliable")
        return result
    if rgb is None or hsv is None:
        result.update(status="missing_measurement", reason="RGB or HSV measurement missing")
        return result
    try:
        values = np.asarray((*rgb, *hsv), dtype=float)
        progress = float(fill_progress)
        if values.shape != (6,) or not np.isfinite(values).all():
            raise ValueError("RGB and HSV must each contain three finite values")
        if np.any(values[[0, 1, 2, 4, 5]] < 0) or np.any(values[[0, 1, 2, 4, 5]] > 255) or not 0 <= values[3] <= 179:
            raise ValueError("RGB/S/V must be 0–255 and OpenCV H must be 0–179")
        stage = stage_for(progress)
    except (TypeError, ValueError) as exc:
        result.update(status="invalid_input", reason=str(exc))
        return result
    result["stage"] = stage
    recipe = model["recipes"].get(str(recipe_id))
    if recipe is None:
        result.update(status="unknown_recipe", reason="recipe has no saved profile")
        return result
    reference_vials = model.get("reference_vials", {})
    reference_vial_id = reference_vials.get(str(recipe_id))
    if reference_vial_id is not None:
        result.update(reference_vial_id=int(reference_vial_id),
                      reference_status="provisional; not confirmed normal")
    entry = recipe[stage]
    result["reference_samples"] = entry["samples"]
    result["reference_vials"] = entry["vials"]
    if not entry["available"]:
        min_samples = model["min_stage_samples"]
        min_vials = model["min_stage_vials"]
        reason = ("stage needs at least four samples from two vials"
                  if (min_samples, min_vials) == (4, 2)
                  else f"stage needs at least {min_samples} samples from {min_vials} vial(s)")
        result.update(status="insufficient_reference",
                      reason=reason)
        return result
    distance = color_distance(values, np.asarray(entry["center"], dtype=float))
    score = 100 * distance / entry["reference_limit"]
    result.update(
        anomaly_score=round(score, 2),
        status="review_unusual" if score >= REVIEW_SCORE else "within_provisional_pattern",
        reason="exploratory comparison only",
        distance_percent=round(distance, 3),
        reference_limit_percent=round(entry["reference_limit"], 3),
    )
    return result
