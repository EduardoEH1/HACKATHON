"""Tests use the checked-in Phase 1 data, with no invented anomaly labels."""

import tempfile
import unittest
from pathlib import Path

import numpy as np

from vialsense.anomaly import (CHANNELS, color_distance, fit_model, load_model,
                               save_model, score_measurement)
from vialsense.anomaly_data import evaluate_leave_one_vial_out, load_phase1_timelines

ROOT = Path(__file__).resolve().parents[1]


class Phase2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_phase1_timelines(ROOT)
        cls.model = fit_model(cls.data[cls.data.usable_measurement])

    def test_data_sources_and_cautious_roi(self):
        self.assertEqual(len(self.data), 509)
        self.assertEqual(int(self.data.usable_measurement.sum()), 271)
        recipe8 = self.data[self.data.recipe_id == 8]
        self.assertEqual(len(recipe8), 55)
        self.assertEqual(int(recipe8.usable_measurement.sum()), 24)
        cautious = recipe8[recipe8.measurement_status == "measured_with_caution"]
        self.assertEqual(len(cautious), 1)
        self.assertFalse(bool(cautious.iloc[0].usable_measurement))

    def test_circular_hue(self):
        sample = np.array([10, 30, 50, 179, 100, 50], dtype=float)
        reference = np.array([10, 30, 50, 1, 100, 50], dtype=float)
        self.assertLess(color_distance(sample, reference), 2)

    def test_unreliable_and_missing_context_abstain(self):
        args = dict(recipe_id=9, rgb=(15, 26, 24), hsv=(84, 109, 26), fill_progress=0.1)
        self.assertEqual(score_measurement(self.model, **args, liquid_visible=False)["status"], "unreliable_measurement")
        self.assertIsNone(score_measurement(self.model, **args, liquid_visible=False)["anomaly_score"])
        self.assertEqual(score_measurement(self.model, **(args | {"fill_progress": None}))["status"], "invalid_input")
        self.assertEqual(score_measurement(self.model, **(args | {"rgb": None}))["status"], "missing_measurement")
        self.assertEqual(score_measurement(self.model, **(args | {"recipe_id": 99}))["status"], "unknown_recipe")

    def test_sparse_stage_abstains(self):
        # Recipe 12 has saved colors only in the early third of its label window.
        row = self.data[(self.data.recipe_id == 12) & self.data.usable_measurement].iloc[0]
        result = score_measurement(
            self.model, recipe_id=12, rgb=tuple(row[c] for c in CHANNELS[:3]),
            hsv=tuple(row[c] for c in CHANNELS[3:]), fill_progress=0.8,
        )
        self.assertEqual(result["status"], "insufficient_reference")
        self.assertIsNone(result["anomaly_score"])

    def test_same_color_uses_different_time_stage(self):
        row = self.data[(self.data.recipe_id == 9) & self.data.usable_measurement].iloc[0]
        args = dict(recipe_id=9, rgb=tuple(row[c] for c in CHANNELS[:3]),
                    hsv=tuple(row[c] for c in CHANNELS[3:]))
        early = score_measurement(self.model, **args, fill_progress=0.1)
        late = score_measurement(self.model, **args, fill_progress=0.9)
        self.assertEqual(early["stage"], "early")
        self.assertEqual(late["stage"], "late")
        self.assertNotEqual(early["anomaly_score"], late["anomaly_score"])

    def test_held_out_vial_is_not_in_reference(self):
        recipe9 = self.data[self.data.recipe_id == 9]
        train = recipe9[(recipe9.vial != 13) & recipe9.usable_measurement]
        model = fit_model(train)
        self.assertNotIn(13, model["recipes"]["9"]["early"]["vial_ids"])
        row = recipe9[(recipe9.vial == 13) & recipe9.usable_measurement].iloc[0]
        expected = score_measurement(
            model, recipe_id=9, rgb=tuple(row[c] for c in CHANNELS[:3]),
            hsv=tuple(row[c] for c in CHANNELS[3:]), fill_progress=row.fill_progress,
        )
        predictions = evaluate_leave_one_vial_out(recipe9)
        actual = predictions[predictions.filename == row.filename].iloc[0]
        self.assertEqual(expected["anomaly_score"], actual.anomaly_score)
        self.assertEqual(expected["status"], actual.status)

    def test_model_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.json"
            save_model(self.model, path)
            self.assertEqual(load_model(path), self.model)


if __name__ == "__main__":
    unittest.main()
