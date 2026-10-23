"""Checks against the saved Dataset 2/auto-finder CSV snapshots."""

import unittest
import json
import os
import subprocess
import sys
from pathlib import Path

from vialsense.anomaly import CHANNELS, score_measurement
from vialsense.corrected_pipeline import (
    build_label_audit, evaluate_corrected, fit_corrected_model, load_inputs,
    prepare_video_timeline, relabel_saved_stills, score_salah_reading,
)

ROOT = Path(__file__).resolve().parents[1]


class CorrectedPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = load_inputs(ROOT / "inputs/color_check")
        cls.audit = build_label_audit(cls.inputs["old"], cls.inputs["corrected"], cls.inputs["vials"])
        cls.fill = prepare_video_timeline(cls.inputs["video"], cls.inputs["vials"])
        cls.model = fit_corrected_model(cls.fill, cls.inputs["vials"])

    def test_corrected_photo_labels_match_windows_and_old_disagreements(self):
        self.assertEqual(len(self.audit), 845)
        self.assertEqual(int(self.audit.old_in_fill.sum()), 509)
        self.assertEqual(int(self.audit.corrected_in_fill.sum()), 516)
        old_fill = self.audit[self.audit.old_in_fill.eq(1)]
        self.assertEqual(int((old_fill.old_vial == old_fill.corrected_vial).sum()), 26)
        self.assertEqual(int(old_fill.corrected_vial.isna().sum()), 195)
        self.assertEqual(int((old_fill.old_vial.ne(old_fill.corrected_vial)
                              & old_fill.corrected_vial.notna()).sum()), 288)
        self.assertEqual(int(self.audit.direct_match_disagrees.sum()), 7)
        self.assertEqual(int(self.audit.clock_fit_outlier.sum()), 30)
        self.assertTrue(self.audit.loc[self.audit.direct_match_disagrees, "boundary_review"].all())

    def test_old_pixel_values_are_audited_but_not_training_data(self):
        stills = relabel_saved_stills(ROOT, self.audit)
        self.assertEqual(len(stills), 271)
        self.assertEqual(int((stills.original_vial == stills.corrected_vial).sum()), 25)
        self.assertEqual(int(stills.corrected_vial.isna().sum()), 17)
        self.assertEqual(int((stills.original_vial.ne(stills.corrected_vial)
                              & stills.corrected_vial.notna()).sum()), 229)
        self.assertEqual(int((stills.reuse_status == "outside_corrected_fill").sum()), 17)

    def test_video_timeline_has_unique_frames_and_consistent_labels(self):
        self.assertEqual(len(self.inputs["video"]), 1130)
        self.assertEqual(len(self.fill), 1067)  # 1070 fill rows minus three duplicate filenames
        self.assertFalse(self.fill.filename.duplicated().any())
        self.assertEqual(int(self.fill.usable_measurement.sum()), 879)
        self.assertEqual(self.fill.vial.nunique(), 30)
        self.assertTrue(self.fill.loc[~self.fill.usable_measurement, list(CHANNELS)].isna().all().all())

    def test_reference_vials_and_missing_stages(self):
        for recipe, stages in self.model["recipes"].items():
            expected_vial = int(self.inputs["vials"].loc[
                self.inputs["vials"].recipe_id.eq(int(recipe)), "vial"].max())
            self.assertEqual(self.model["reference_vials"][recipe], expected_vial)
            for entry in stages.values():
                if entry["available"]:
                    self.assertEqual(entry["vial_ids"], [expected_vial])
        self.assertFalse(self.model["recipes"]["11"]["early"]["available"])
        self.assertFalse(self.model["recipes"]["14"]["early"]["available"])
        self.assertFalse(self.model["recipes"]["14"]["middle"]["available"])

    def test_evaluation_vials_do_not_change_reference(self):
        changed = self.fill.copy()
        nonreference = changed.apply(
            lambda row: int(row.vial) != self.model["reference_vials"][str(int(row.recipe_id))], axis=1)
        changed.loc[nonreference & changed.usable_measurement, "r_mean"] = 250.0
        other = fit_corrected_model(changed, self.inputs["vials"])
        self.assertEqual(other, self.model)

    def test_salah_record_and_live_dict_use_same_interface(self):
        row = self.fill[(self.fill.recipe_id == 9) & self.fill.usable_measurement].iloc[0]
        reading = row.to_dict()
        adapted = score_salah_reading(self.model, reading)
        direct = score_measurement(
            self.model, recipe_id=int(row.recipe_id),
            rgb=tuple(float(row[c]) for c in CHANNELS[:3]),
            hsv=tuple(float(row[c]) for c in CHANNELS[3:]),
            fill_progress=float(row.fill_progress),
        )
        self.assertEqual(adapted["anomaly_score"], direct["anomaly_score"])
        self.assertEqual(adapted["status"], direct["status"])
        live = {c: reading[c] for c in CHANNELS}
        live.update(found_vial=True, found_liquid=True, confidence="high", time=123.45)
        self.assertEqual(score_salah_reading(self.model, live)["status"], "invalid_input")
        live_result = score_salah_reading(self.model, live, recipe_id=9,
                                          fill_progress=float(row.fill_progress))
        self.assertEqual(live_result["status"], direct["status"])
        self.assertEqual(live_result["timestamp"], "123.45")
        self.assertEqual(live_result["reference_vial_id"], self.model["reference_vials"]["9"])
        self.assertEqual(live_result["reference_status"], "provisional; not confirmed normal")
        live["confidence"] = "low"
        self.assertEqual(score_salah_reading(self.model, live, recipe_id=9,
                                             fill_progress=0.5)["status"], "unreliable_measurement")

    def test_cli_scores_saved_liquid_finder_output_end_to_end(self):
        row = self.fill[(self.fill.recipe_id == 9) & self.fill.usable_measurement].iloc[0]
        reading = {key: (row[key].item() if hasattr(row[key], "item") else row[key]) for key in (
            *CHANNELS, "found_vial", "found_liquid", "confidence", "video_s",
        )}
        expected = score_salah_reading(
            self.model, reading, recipe_id=9, fill_progress=float(row.fill_progress),
            timestamp=f"video5:{float(row.video_s):.3f}s",
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        completed = subprocess.run(
            [sys.executable, "-m", "vialsense.corrected_cli", "score",
             "--model", str(ROOT / "results/corrected/phase2/provisional_model.json"),
             "--recipe-id", "9", "--progress", str(float(row.fill_progress)),
             "--timestamp", f"video5:{float(row.video_s):.3f}s"],
            input=json.dumps(reading), text=True, capture_output=True,
            cwd=ROOT, env=env, check=True,
        )
        actual = json.loads(completed.stdout)
        self.assertEqual(actual["anomaly_score"], expected["anomaly_score"])
        self.assertEqual(actual["status"], expected["status"])
        self.assertEqual(actual["reference_vial_id"], self.model["reference_vials"]["9"])
        self.assertEqual(actual["reference_status"], "provisional; not confirmed normal")

    def test_evaluation_scores_only_reliable_rows(self):
        predictions, summary = evaluate_corrected(self.fill, self.model)
        self.assertEqual(len(predictions), len(self.fill))
        self.assertEqual(len(summary), 30)
        self.assertTrue(predictions.loc[predictions.measurement_status.ne("measured_high"),
                                        "anomaly_score"].isna().all())
        self.assertEqual(int(predictions.loc[predictions.split.eq("evaluation"),
                                              "anomaly_score"].notna().sum()), 577)
        self.assertEqual(int(predictions.loc[predictions.split.eq("evaluation"),
                                              "status"].eq("review_unusual").sum()), 255)


if __name__ == "__main__":
    unittest.main()
