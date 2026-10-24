# Phase 1: RGB/HSV Color Analysis

This folder contains the current Recipe 5–14 video-based color analysis. It
uses saved RGB and OpenCV HSV measurements from the automatic liquid finder,
grouped by the labeled recipe, vial, timestamp, and fill progress. The main
outputs are per-frame timelines, recipe and vial summaries, and plots.

## Coverage and results

The analysis includes 1,067 unique fill frames across 30 vials. High-confidence
liquid colors are available for 879 frames. Other frames remain visible in the
timelines with color columns blank, so exclusions are not turned into invented
measurements.

| Recipe | High-confidence / fill frames | Timeline | RGB plot | HSV plot |
|---:|---:|---|---|---|
| 5 | 81 / 87 | [CSV](phase1/recipe_5/timeline.csv) | [RGB](phase1/recipe_5/rgb_over_fill.png) | [HSV](phase1/recipe_5/hsv_over_fill.png) |
| 6 | 67 / 77 | [CSV](phase1/recipe_6/timeline.csv) | [RGB](phase1/recipe_6/rgb_over_fill.png) | [HSV](phase1/recipe_6/hsv_over_fill.png) |
| 7 | 67 / 75 | [CSV](phase1/recipe_7/timeline.csv) | [RGB](phase1/recipe_7/rgb_over_fill.png) | [HSV](phase1/recipe_7/hsv_over_fill.png) |
| 8 | 103 / 116 | [CSV](phase1/recipe_8/timeline.csv) | [RGB](phase1/recipe_8/rgb_over_fill.png) | [HSV](phase1/recipe_8/hsv_over_fill.png) |
| 9 | 131 / 145 | [CSV](phase1/recipe_9/timeline.csv) | [RGB](phase1/recipe_9/rgb_over_fill.png) | [HSV](phase1/recipe_9/hsv_over_fill.png) |
| 10 | 100 / 118 | [CSV](phase1/recipe_10/timeline.csv) | [RGB](phase1/recipe_10/rgb_over_fill.png) | [HSV](phase1/recipe_10/hsv_over_fill.png) |
| 11 | 63 / 130 | [CSV](phase1/recipe_11/timeline.csv) | [RGB](phase1/recipe_11/rgb_over_fill.png) | [HSV](phase1/recipe_11/hsv_over_fill.png) |
| 12 | 122 / 132 | [CSV](phase1/recipe_12/timeline.csv) | [RGB](phase1/recipe_12/rgb_over_fill.png) | [HSV](phase1/recipe_12/hsv_over_fill.png) |
| 13 | 111 / 117 | [CSV](phase1/recipe_13/timeline.csv) | [RGB](phase1/recipe_13/rgb_over_fill.png) | [HSV](phase1/recipe_13/hsv_over_fill.png) |
| 14 | 34 / 70 | [CSV](phase1/recipe_14/timeline.csv) | [RGB](phase1/recipe_14/rgb_over_fill.png) | [HSV](phase1/recipe_14/hsv_over_fill.png) |

Other useful files:

- [Recipe summary](phase1/recipe_summary.csv): coverage and descriptive
  recipe-level RGB/HSV statistics.
- [Vial summary](phase1/vial_summary.csv): measurement coverage and channel
  summaries for each vial.
- [Label alignment audit](label_audit.csv): frame-to-fill-window alignment
  and boundary-review metadata.
- [Previously measured stills](legacy_stills_relabelled.csv): saved manual-ROI
  measurements alongside their current label metadata; these are not used for
  the current color summaries or detector references.
- [Representative ROI review sheet](../../inputs/color_check/examples/video5_liquid_roi_review_sheet.jpg).

## Measurement method

The analysis reads the saved `frame_colors.csv` in
[`inputs/color_check/`](../../inputs/color_check/README.md). Each frame is
matched to its video-time vial fill window. `fill_progress` spans 0 to 1 over
that labeled window; it is a time proxy, not liquid volume. A color enters the
analysis only when the finder reports a vial and liquid and marks confidence
as `high`. RGB uses 0–255 channel values; OpenCV HSV uses hue 0–179 and
saturation/value 0–255.

High finder confidence does not establish a ground-truth liquid mask. The ROI
can still be affected by reflections, glass, motion, lighting, or liquid
depth. Source frame colors, label windows, and input hashes are retained so the
tabulated analysis can be rebuilt from the saved inputs. Re-extracting pixels
requires the original Video 5 media and the liquid-finder implementation.

## Rebuild the analysis

From the repository root, install `requirements.txt`, then run:

```bash
PYTHONPATH=src python -m vialsense.corrected_cli build
```

This rebuilds Phase 1 summaries, timelines and plots, and the Phase 2 model
under `results/corrected/`. Use `--output-dir` to write to another location.
The checked-in CSV snapshots are sufficient; raw images and videos are not
needed to reproduce these saved numerical outputs.

## Phase 2

The anomaly-scoring prototype that consumes these Phase 1 measurements is
documented separately in [Phase 2: Anomaly Detection](phase2/README.md). Its
recipe-stage references and alerts are provisional and are not validated
contamination thresholds.
