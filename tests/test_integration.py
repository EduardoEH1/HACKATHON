"""Exercise saved Video 5 replay and frame-to-score integration."""

import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from vialsense.anomaly import load_model
from vialsense.corrected_pipeline import score_salah_reading
from vialsense.integration import measure_video, save_labeled_results, save_unlabeled_results
from vialsense.liquid_finder import find_liquid

ROOT = Path(__file__).resolve().parents[1]


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = load_model(ROOT / "results/corrected/phase2/provisional_model.json")

    @staticmethod
    def frame():
        frame = np.full((480, 640, 3), 150, dtype=np.uint8)
        frame[200:265, 258:376] = (20, 20, 20)
        frame[300:400, 291:324] = (200, 120, 20)
        return frame

    def test_saved_video5_matches_existing_phase1_and_phase2(self):
        readings = pd.read_csv(ROOT / "inputs/color_check/frame_colors.csv")
        windows = pd.read_csv(ROOT / "inputs/color_check/video5_vial_recipes.csv")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            summary = save_labeled_results(readings, windows, self.model, out)
            self.assertEqual((summary["unique_fill_frames"],
                              summary["high_confidence_colors"],
                              summary["evaluation_frames_scored"],
                              summary["evaluation_review_flags"]), (1067, 879, 577, 255))
            pd.testing.assert_frame_equal(
                pd.read_csv(out / "phase1_recipe_summary.csv"),
                pd.read_csv(ROOT / "results/corrected/phase1/recipe_summary.csv"),
            )
            pd.testing.assert_frame_equal(
                pd.read_csv(out / "phase2_predictions.csv"),
                pd.read_csv(ROOT / "results/corrected/phase2/frame_predictions.csv"),
            )

    def test_detector_output_flows_to_phase1_and_phase2(self):
        frame = self.frame()
        detection = find_liquid(frame)
        self.assertTrue(detection.found_liquid)
        self.assertEqual(detection.confidence, "high")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.avi"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"),
                                     10.0, (640, 480))
            self.assertTrue(writer.isOpened())
            for _ in range(30):
                writer.write(frame)
            writer.release()
            windows = pd.DataFrame([{"vial": 13, "recipe_id": 9, "start_s": 0.0,
                                     "end_s": 2.0, "duration_s": 2.0}])
            readings = measure_video(path, windows=windows)
            self.assertEqual(len(readings), 3)
            self.assertTrue(readings.found_liquid.all())
            out = Path(tmp) / "labeled"
            summary = save_labeled_results(readings, windows, self.model, out)
            self.assertEqual(summary["high_confidence_colors"], 3)
            predictions = pd.read_csv(out / "phase2_predictions.csv")
            self.assertTrue(predictions.anomaly_score.notna().all())
            direct = score_salah_reading(self.model, readings.iloc[0].to_dict())
            self.assertEqual(predictions.iloc[0].anomaly_score, direct["anomaly_score"])
            self.assertEqual(predictions.iloc[0].reference_vial_id, 15)

    def test_missing_video_context_abstains_and_keeps_colors(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.avi"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"),
                                     10.0, (640, 480))
            self.assertTrue(writer.isOpened())
            writer.write(self.frame())
            writer.release()
            readings = measure_video(path, windows=None)
            out = Path(tmp) / "unlabeled"
            summary = save_unlabeled_results(readings, self.model, out)
            self.assertEqual(summary["scored_frames"], 0)
            self.assertTrue(readings.found_liquid.all())
            self.assertTrue(pd.read_csv(out / "phase2_predictions.csv")
                            .status.eq("invalid_input").all())
            self.assertEqual(json.loads((out / "run_summary.json").read_text())["input_rows"], 1)


if __name__ == "__main__":
    unittest.main()
