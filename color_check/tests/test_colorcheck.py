"""Tests for the color math. Run with:  PYTHONPATH=src python -m pytest tests"""

import numpy as np
import pytest

from vialsense.colorcheck import check_color, delta_e_2000, measure_liquid, rgb_to_lab

# Published test pairs from Sharma, Wu, Dalal (2005), the CIEDE2000 reference paper.
SHARMA_PAIRS = [
    ((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
    ((50.0, 3.1571, -77.2803), (50.0, 0.0, -82.7485), 2.8615),
    ((50.0, -1.3802, -84.2814), (50.0, 0.0, -82.7485), 1.0000),
    ((50.0, 2.5, 0.0), (50.0, 0.0, -2.5), 4.3065),
    ((50.0, 2.5, 0.0), (73.0, 25.0, -18.0), 27.1492),
    ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
    ((22.7233, 20.0904, -46.6940), (23.0331, 14.9730, -42.5619), 2.0373),
    ((90.8027, -2.0831, 1.4410), (91.1528, -1.6435, 0.0447), 1.4441),
    ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
]


@pytest.mark.parametrize("lab1, lab2, expected", SHARMA_PAIRS)
def test_delta_e_matches_published_values(lab1, lab2, expected):
    assert delta_e_2000(lab1, lab2) == pytest.approx(expected, abs=1e-4)


def test_rgb_to_lab_known_colors():
    assert rgb_to_lab((255, 255, 255)) == pytest.approx([100, 0, 0], abs=0.01)
    assert rgb_to_lab((0, 0, 0)) == pytest.approx([0, 0, 0], abs=0.01)
    assert rgb_to_lab((255, 0, 0)) == pytest.approx([53.24, 80.09, 67.20], abs=0.05)


def test_measure_liquid_skips_glare():
    image = np.zeros((20, 20, 3), dtype=np.uint8)
    image[:, :] = (20, 60, 120)          # orange-brown liquid in BGR
    image[0:4, :] = (255, 255, 255)      # glare stripe
    result = measure_liquid(image, (0, 0, 20, 20))
    assert (result["r"], result["g"], result["b"]) == pytest.approx((120, 60, 20))
    assert result["pixels_used"] == 16 * 20


def test_check_color_pass_flag_and_carryover_note():
    refs = {1: {"rgb": (110, 55, 20), "previous_recipe": None},     # orange
            2: {"rgb": (25, 90, 100), "previous_recipe": 1}}         # blue
    assert check_color((108, 56, 22), 1, refs).status == "PASS"
    flagged = check_color((105, 57, 22), 2, refs)                   # orange in a blue recipe
    assert flagged.status == "FLAG"
    assert "previous recipe 1" in flagged.note
