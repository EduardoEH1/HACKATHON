"""Connect saved or video liquid-finder readings to Phase 1 and Phase 2."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from .corrected_pipeline import (
    evaluate_corrected, prepare_video_timeline, score_salah_reading,
    summarize_video,
)
from .liquid_finder import find_liquid


def measure_video(video_path: Path, step_s: float = 1.0,
                  windows: pd.DataFrame | None = None) -> pd.DataFrame:
    """Sample a video and return detector readings with optional fill context.

    `windows` has Dataset 2-style vial, recipe_id, start_s, end_s, duration_s
    columns. Without it, colors can be measured but anomaly scoring abstains.
    """
    if step_s <= 0 or not np.isfinite(step_s):
        raise ValueError("step_s must be a positive finite number")
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0 or frame_count <= 0:
            raise ValueError("Video has no usable FPS or frames")
        requests: list[tuple[float, int | None, int | None, float | None, float | None]] = []
        if windows is None:
            requests = [(float(t), None, None, None, None)
                        for t in np.arange(0, frame_count / fps, step_s)]
        else:
            required = {"vial", "recipe_id", "start_s", "end_s", "duration_s"}
            if missing := required - set(windows.columns):
                raise ValueError(f"Fill-window table lacks {sorted(missing)}")
            for vial in windows.itertuples(index=False):
                if not (0 <= vial.start_s < vial.end_s <= frame_count / fps
                        and vial.duration_s > 0):
                    raise ValueError(f"Invalid fill window for vial {vial.vial}")
                times = [*np.arange(vial.start_s, vial.end_s, step_s), vial.end_s]
                requests.extend((float(t), int(vial.vial), int(vial.recipe_id),
                                 float(vial.start_s), float(vial.duration_s)) for t in times)
        rows = []
        seen: set[tuple[int | None, int]] = set()
        for requested_s, vial, recipe_id, start_s, duration_s in requests:
            frame_index = int(round(requested_s * fps))
            if frame_index >= frame_count:
                raise ValueError(f"Fill window exceeds video at {requested_s:.3f}s")
            key = (vial, frame_index)
            if key in seen:
                continue
            seen.add(key)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError(f"Cannot read frame {frame_index} from {video_path}")
            video_s = frame_index / fps
            detection = find_liquid(frame).to_dict()
            roi = detection.pop("roi")
            for box in ("block", "tube", "liquid"):
                detection.pop(box)
            detection.update(zip(("roi_x1", "roi_y1", "roi_x2", "roi_y2"),
                                 roi or (None, None, None, None)))
            rows.append({
                "filename": f"vial{vial:02d}_frame{frame_index:06d}"
                            if vial is not None else f"frame{frame_index:06d}",
                "video_s": round(video_s, 3), "frame": frame_index,
                "vial": vial, "recipe_id": recipe_id,
                "phase": "fill" if vial is not None else "unlabeled",
                "fill_progress": (min(1.0, max(0.0, (video_s - start_s) / duration_s))
                                  if start_s is not None else None),
                **detection,
            })
        return pd.DataFrame(rows)
    finally:
        cap.release()


def save_labeled_results(readings: pd.DataFrame, windows: pd.DataFrame,
                         model: dict, output_dir: Path) -> dict:
    """Reuse the existing Phase 1 summaries and Phase 2 evaluation path."""
    timeline = prepare_video_timeline(readings, windows)
    vial_summary, recipe_summary = summarize_video(timeline)
    predictions, evaluation_summary = evaluate_corrected(timeline, model)
    output_dir.mkdir(parents=True, exist_ok=True)
    readings.to_csv(output_dir / "detector_readings.csv", index=False)
    timeline.to_csv(output_dir / "phase1_timeline.csv", index=False)
    vial_summary.to_csv(output_dir / "phase1_vial_summary.csv", index=False)
    recipe_summary.to_csv(output_dir / "phase1_recipe_summary.csv", index=False)
    predictions.to_csv(output_dir / "phase2_predictions.csv", index=False)
    evaluation_summary.to_csv(output_dir / "phase2_vial_summary.csv", index=False)
    summary = {
        "input_rows": len(readings), "unique_fill_frames": len(timeline),
        "high_confidence_colors": int(timeline.usable_measurement.sum()),
        "evaluation_frames_scored": int(predictions.loc[
            predictions.split.eq("evaluation"), "anomaly_score"].notna().sum()),
        "evaluation_review_flags": int((predictions.split.eq("evaluation")
                                         & predictions.status.eq("review_unusual")).sum()),
        "status": "provisional; not validated contamination detection",
    }
    (output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def save_unlabeled_results(readings: pd.DataFrame, model: dict,
                           output_dir: Path) -> dict:
    """Keep colors from an unknown video; abstain until recipe/progress arrive."""
    predictions = []
    for row in readings.to_dict("records"):
        score = score_salah_reading(model, row,
                                    timestamp=f"video:{row['video_s']:.3f}s")
        predictions.append({"filename": row["filename"], "video_s": row["video_s"], **score})
    output_dir.mkdir(parents=True, exist_ok=True)
    readings.to_csv(output_dir / "detector_readings.csv", index=False)
    pd.DataFrame(predictions).to_csv(output_dir / "phase2_predictions.csv", index=False)
    summary = {"input_rows": len(readings), "scored_frames": 0,
               "status": "recipe_id and fill_progress unavailable; no anomaly scores"}
    (output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary
