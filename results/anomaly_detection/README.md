# Phase 2: provisional color comparison

This is a runnable hackathon prototype. It takes a recipe ID, a measured mean
RGB and OpenCV HSV color, and estimated filling progress, then returns an
`anomaly_score` and a status. It does not inspect images or locate liquid. The
camera/ROI component must supply a **visible, reliable liquid measurement**.
No measured vial in this dataset is confirmed contaminated or confirmed good.
`review_unusual` means only that a measurement differs from this provisional
recipe-stage profile; it is **not** a contamination decision or a validated
product threshold.

## Files

- [provisional_model.json](provisional_model.json): machine-readable profiles for
  Recipes 5–14, split into early, middle, and late thirds of each vial's
  label-derived filling window.
- [reference_stage_summary.csv](reference_stage_summary.csv): stage coverage,
  sample/vial counts, RGB/S/V medians and circular hue center, and provisional distance limit.
  An unavailable stage has no center or limit.
- [held_out_vial_predictions.csv](held_out_vial_predictions.csv): every labeled
  frame with its measurement status and a prediction where one was possible.
  Each vial is scored against a model fitted on **other vials only**.
- [held_out_vial_summary.csv](held_out_vial_summary.csv): measured and scored
  counts, review flags, and the first scored/flagged time for each vial.
- Code: [model and scoring](../../src/vialsense/anomaly.py),
  [timeline loading and evaluation](../../src/vialsense/anomaly_data.py), and
  [command line interface](../../src/vialsense/anomaly_cli.py).

## How progress and the score work

The Phase 1 timeline CSVs have one row per frame labeled `in_fill=1`. For each
vial, progress is elapsed seconds divided by the seconds between its first and
last such labeled frames: 0 at the first, 1 at the last. This is a **time
proxy**, not verified dispenser progress or liquid volume. A source timestamp
is retained in output for traceability but cannot establish progress by
itself. The future camera integration must supply progress from the process
timeline (or an equivalent estimate) to `score_measurement`.

Each recipe-stage profile needs at least four usable measurements from at
least two vials. The center is the median of RGB/S/V and a circular hue center.
The distance averages differences in the six scaled channels; hue wraps around
OpenCV's 0–179 circle and is ignored when saturation is below 30. RGB and HSV
are derived from the same pixels, so their contributions are correlated.

The stage limit is the larger of: the 95th percentile distance of training
measurements from the stage center; the 95th percentile distance when each
training vial is compared with the other training vials; and a 2% numerical
floor. `anomaly_score = 100 × distance / stage limit`. A score of 100 is the
provisional **review** boundary; scores can exceed 100. The 95th percentile,
2% floor, three stage bands, and minimum sample count are demonstration
choices, **not measured contamination thresholds**. If a stage is unsupported,
or a measurement/ROI/progress is missing or unreliable, the score is blank and
the status explains why. The detector does not infer liquid visibility.

## Rebuild and run

From the repository root, with the dependencies in `requirements.txt`
installed, run:

```bash
PYTHONPATH=src python -m vialsense.anomaly_cli build
PYTHONPATH=src python -m unittest discover -s tests -v
```

`build` uses **only the checked-in Phase 1 timeline CSVs**; raw images, label
files under `data/raw/`, and OpenCV are not required for this step. The command
rebuilds only the files in this Phase 2 folder. To write elsewhere, add
`--output-dir /some/path`.

Score an existing Recipe 9 measurement from the saved timeline:

```bash
PYTHONPATH=src python -m vialsense.anomaly_cli score \
  --recipe-id 9 --rgb 15.6796875 26.4583333 24.375 \
  --hsv 84.5703125 109.6067708 26.4583333 --progress 0 \
  --timestamp '2026-09-23 19:57:21.070470'
```

This returns a score near 34.9 and `within_provisional_pattern` for the
all-vial model. Pass `--liquid-not-visible` or `--unreliable` to abstain when
the upstream ROI/measurement is not trustworthy. For Python integration:

```python
from vialsense.anomaly import load_model, score_measurement

model = load_model("results/anomaly_detection/provisional_model.json")
result = score_measurement(
    model,
    recipe_id=9,
    rgb=(15.68, 26.46, 24.38),
    hsv=(84.57, 109.61, 26.46),  # OpenCV scales: H 0–179, S/V 0–255
    fill_progress=0.0,
    timestamp="2026-09-23 19:57:21.070470",
    liquid_visible=True,
    measurement_reliable=True,
)
```

Output fields include `anomaly_score`, `status`, `stage`, `reason`,
`reference_samples`, and `reference_vials`. Statuses are
`within_provisional_pattern`, `review_unusual`, `insufficient_reference`,
`unreliable_measurement`, `missing_measurement`, `invalid_input`, and
`unknown_recipe`.

## Held-out evaluation on existing data

The evaluation holds out one whole vial at a time, trains that recipe's
profile on the remaining vials, and then scores only the held-out vial's saved
measurements. Frames close in time from the same vial never appear in both its
training and evaluation sets. It checks whether this provisional profile
generalizes to another recorded vial; **it cannot measure contamination
recall, precision, or false-alarm rate**, because none of these vials has a
confirmed good/bad label.

| Recipe | Usable measurements | Held-out scores | Review flags | Main coverage issue |
|---:|---:|---:|---:|---|
| 5 | 25 | 14 | 4 | Early stage has one measured vial. |
| 6 | 18 | 13 | 8 | Late stage has one measurement. |
| 7 | 17 | 0 | 0 | Held-out stage references do not have two other measured vials. |
| 8 | 24 | 15 | 6 | Late stage has one usable measurement; one cautious ROI was excluded. |
| 9 | 59 | 59 | 13 | Best measured coverage, yet the simple comparison still flags natural differences. |
| 10 | 38 | 12 | 1 | Stage coverage between vials is uneven. |
| 11 | 19 | 0 | 0 | Sparse stages and ten missing images. |
| 12 | 15 | 15 | 2 | All usable samples occur in the early time band. |
| 13 | 42 | 30 | 8 | Vial 27 differs substantially from 25 and 26. |
| 14 | 14 | 0 | 0 | Vial 28 has no measurement; other stages are sparse. |
| **Total** | **271** | **158** | **42** | **509** labeled frames; 238 have no comparable usable measurement. |

The per-vial summary shows the first time a score or review flag was possible.
Some occur at 0 seconds, the **first labeled in-fill image**, which may already
be after dispensing began. Recipe 13 Vial 27 is a clear example of a measured
cross-vial difference (first flagged at about 8 seconds on its label timeline).
Recipe 9, despite comparatively similar sampled colors, receives 13 review
flags. This demonstrates that this profile and boundary are not ready for an
automatic product alert. A wide or contradictory provisional profile can
also hide a real problem; an unflagged measurement does not prove correctness.

## What is still needed

For a reliable detector: a camera/ROI component that returns liquid-only color
and an explicit quality/visibility signal; a trustworthy process progress
signal or calibrated timing; repeated known-good vials under varied lighting;
and labeled controlled abnormal runs for selecting and validating thresholds.
Until then, treat the output as a human-review aid. The code and checked-in
results do not identify contamination, cause, or product disposition.
