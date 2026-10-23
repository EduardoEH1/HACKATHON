"""Tests for the liquid finder on a drawn test frame. Run: PYTHONPATH=src python -m pytest tests"""

import numpy as np

from vialsense.liquid_finder import find_liquid, rate_confidence


def make_frame(liquid_bgr=None, liquid_top=330, block_x=258):
    """Gray background, black holder block, gray tube, optional liquid column."""
    frame = np.full((480, 640, 3), (150, 150, 150), np.uint8)
    frame[200:265, block_x:block_x + 118] = (20, 20, 20)            # holder block
    if liquid_bgr is not None:
        frame[liquid_top:400, block_x + 33:block_x + 66] = liquid_bgr  # liquid in tube
    return frame


def test_finds_block_and_liquid_color():
    det = find_liquid(make_frame((200, 120, 20), liquid_top=300))  # blue liquid
    assert det.found_vial and det.found_liquid
    assert det.block[3] == 265
    assert (det.r_mean, det.g_mean, det.b_mean) == (20, 120, 200)
    assert 90 <= det.liquid_height_px <= 110


def test_empty_vial_has_no_liquid():
    det = find_liquid(make_frame())
    assert det.found_vial and not det.found_liquid


def test_vial_away_from_nozzle_is_skipped():
    det = find_liquid(make_frame((20, 100, 220), block_x=360))
    assert not det.found_vial
    assert "moving" in det.reason


def test_tilted_vial_is_skipped():
    frame = np.full((480, 640, 3), (150, 150, 150), np.uint8)
    frame[160:222, 258:376] = (20, 20, 20)            # block sits too high: vial tilted
    frame[230:380, 291:324] = (200, 120, 20)
    det = find_liquid(frame)
    assert not det.found_vial and "moving" in det.reason


def test_pale_liquid_is_flagged_low():
    # Real pale readings from videos 1, 3, 4 (RGB).
    for rgb in [(110, 110, 82), (122, 124, 93), (87, 90, 64)]:
        confidence, note = rate_confidence(120, rgb)
        assert confidence == "low" and "pale" in note
    # Real colored readings from video 5 stay high: blue, orange, teal, dark green.
    for rgb in [(6, 48, 69), (65, 30, 12), (42, 69, 61), (15, 28, 22)]:
        assert rate_confidence(120, rgb)[0] == "high"


def test_colored_liquid_is_high_confidence():
    det = find_liquid(make_frame((200, 120, 20), liquid_top=300))
    assert det.confidence == "high"
