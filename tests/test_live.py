"""Tests for live mode: queue parsing, calibration, and the vial tracker."""

import numpy as np
import pytest

from vialsense.live_calibration import REF_BOTTOM_Y, REF_CENTER_X, calibrate, prepare
from vialsense.live_tracker import VialTracker, parse_queue
from vialsense.liquid_finder import find_liquid


def test_parse_queue_forms():
    assert parse_queue("7,7,7,8") == [7, 7, 7, 8]
    assert parse_queue("7x3, 8x2") == [7, 7, 7, 8, 8]
    assert parse_queue("5x1;6") == [5, 6]
    with pytest.raises(ValueError):
        parse_queue(" , ")


def frame_with_holder(center_x, bottom_y, width, size=(640, 480)):
    """Gray scene, black holder block, blue liquid column under it."""
    w, h = size
    frame = np.full((h, w, 3), 150, np.uint8)
    half, top = width / 2, bottom_y - 0.55 * width
    frame[int(top):int(bottom_y), int(center_x - half):int(center_x + half)] = 20
    tube_x1 = int(center_x - half + 0.28 * width)
    tube_x2 = int(center_x - half + 0.56 * width)
    frame[int(bottom_y + 0.3 * width):int(bottom_y + 1.1 * width), tube_x1:tube_x2] = (200, 120, 20)
    return frame


def test_calibration_leaves_reference_view_alone():
    cal = calibrate(frame_with_holder(REF_CENTER_X, REF_BOTTOM_Y, 116))
    assert cal.is_identity()


def test_calibration_recovers_moved_zoomed_camera():
    moved = frame_with_holder(400, 300, 150, size=(640, 480))
    assert not find_liquid(moved).found_vial          # the finder alone misses it
    cal = calibrate(moved)
    assert cal.scale == pytest.approx(116 / 150, rel=0.05)
    det = find_liquid(prepare(moved, cal))
    assert det.found_vial and det.found_liquid


def detection(vial=True, height=0, color=(20, 120, 200), confidence="high"):
    found = vial and height > 0
    return {"found_vial": vial, "found_liquid": found, "liquid_height_px": height,
            "confidence": confidence if found else "",
            "r_mean": color[0], "g_mean": color[1], "b_mean": color[2],
            "h_mean_opencv": 100.0, "s_mean_opencv": 200.0, "v_mean_opencv": 200.0}


def fake_score(reading, recipe_id, progress):
    """Recipe 7 expects blue, recipe 6 orange. Score 50 = match, 300 = mismatch."""
    blue = reading["b_mean"] > reading["r_mean"]
    match = blue == (recipe_id == 7)
    score = 50.0 if match else 300.0
    return {"anomaly_score": score, "status": "within_provisional_pattern" if match else "review_unusual"}


def run_vial(tracker, t0, color, fill_s=20, baseline=8, dropout_at=None):
    """Simulate one vial: 5 s empty, fill_s filling, 2 s full, then leaves. 5 samples/s."""
    t = t0
    for _ in range(25):
        tracker.update(t, detection(height=baseline, confidence="low")); t += 0.2
    for i in range(int(fill_s * 5)):
        vial = not (dropout_at is not None and abs(t - (t0 + dropout_at)) < 0.1)
        tracker.update(t, detection(vial=vial, height=baseline + 2 + i, color=color)); t += 0.2
    for _ in range(10):
        tracker.update(t, detection(height=120, color=color)); t += 0.2
    for _ in range(4):                       # 0.8 s gap: vial swap
        tracker.update(t, detection(vial=False)); t += 0.2
    return t


def test_tracker_counts_vials_and_follows_queue():
    tracker = VialTracker([6, 7, 7], fake_score, {6: 20, 7: 20}, previous_recipe=6)
    t = run_vial(tracker, 0, color=(200, 120, 20))          # orange, recipe 6
    t = run_vial(tracker, t, color=(150, 120, 60))          # orange-ish in a blue recipe: carryover
    t = run_vial(tracker, t, color=(20, 120, 200))          # blue, recipe 7
    tracker.finish()
    assert [v.recipe_id for v in tracker.finished] == [6, 7, 7]
    assert [v.verdict for v in tracker.finished] == ["PASS", "FLAG", "PASS"]
    flagged = tracker.finished[1]
    assert flagged.recipe_change and "carryover from Recipe 6" in flagged.explanation
    assert any("Carryover risk" in e for e in tracker.events)


def test_brief_dropout_does_not_split_a_vial():
    tracker = VialTracker([7], fake_score, {7: 20}, previous_recipe=7)
    run_vial(tracker, 0, color=(20, 120, 200), dropout_at=12.0)
    tracker.finish()
    assert len(tracker.finished) == 1 and tracker.finished[0].verdict == "PASS"


def test_fill_start_ignores_empty_vial_residue():
    tracker = VialTracker([7], fake_score, {7: 20})
    run_vial(tracker, 0, color=(20, 120, 200), baseline=14)
    tracker.finish()
    start = tracker.finished[0].fill_start_s
    assert start is not None and start >= 5.0     # fill begins at t=5 s, not on arrival


def test_short_flicker_is_ignored_and_queue_kept():
    tracker = VialTracker([7, 8], fake_score, {7: 20})
    for i in range(5):                            # 1 s of a false detection
        tracker.update(i * 0.2, detection())
    for i in range(5, 10):
        tracker.update(i * 0.2, detection(vial=False))
    assert tracker.finished == [] and tracker.next_recipe == 7


def test_same_recipe_flag_is_not_called_carryover():
    tracker = VialTracker([7, 7], fake_score, {7: 20})
    t = run_vial(tracker, 0, color=(20, 120, 200))
    run_vial(tracker, t, color=(200, 120, 20))
    tracker.finish()
    second = tracker.finished[1]
    assert second.verdict == "FLAG" and "not recipe-change carryover" in second.explanation


def test_empty_queue_records_color_only():
    tracker = VialTracker([], fake_score, {}, default_fill_s=20)
    run_vial(tracker, 0, color=(20, 120, 200))
    tracker.finish()
    assert tracker.finished[0].verdict == "NO RECIPE"


def test_operator_skip_and_back():
    tracker = VialTracker([5, 6, 7], fake_score, {})
    tracker.skip()
    assert tracker.next_recipe == 6
    tracker.back()
    assert tracker.next_recipe == 5
