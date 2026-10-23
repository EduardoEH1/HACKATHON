# Recipe 14 labeled temporal analysis

[Project overview](../../../README.md) · [Consolidated comparison](../consolidated/README.md) · [Original RGB/HSV measurements](../../recipe_14/recipe_14_manual_roi_measurements.csv)

## Source and method

This analysis joins the existing preliminary ROI measurement CSV to the original
video5 frame labels by exact image filename. It does not inspect or re-measure
image pixels. Each vial's time axis starts at its earliest frame labeled
`in_fill=1`; it is elapsed time from that **label**, not a verified instant of
liquid dispensing. All 32 labeled in-fill frames are retained in the
timeline. No color value is filled in for an excluded, missing, or unclassified
frame.

Measurement source: `results/recipe_14/recipe_14_manual_roi_measurements.csv`  
Labels: `data/raw/recipe7/labels_video5_frame_labels.csv`  
Frames: 14 measured; 18 explicitly excluded by prior ROI review; 0 listed missing; 0 have no matching measurement/exclusion/missing record. Coverage is 14/32 (43.8%).

## Per-vial observations

- Vial 28: no retained color measurements; timeline coverage is unavailable.
- Vial 29: 10/10 frames (100.0%); first-half vs last-half mean RGB distance 0.9; median adjacent RGB step 0.6. These describe recorded ROI variation, not a process threshold.
- Vial 30: 4/11 frames (36.4%); first-half vs last-half mean RGB distance 59.0; median adjacent RGB step 33.8. These describe recorded ROI variation, not a process threshold.

## Time and vial comparison

Among vials with at least three measurements, Vial 30 has the largest first-half/last-half mean RGB separation (59.0); Vial 29 has the smallest (0.9). This is a descriptive time comparison, not a validated definition of a color change.

Vial 29 has the smallest median step between adjacent measured RGB samples (0.6), so its retained measurements are comparatively close together over time. This does not show what happened in gaps between retained frames.

The farthest pair of measured per-vial mean RGB values is Vials 29 and 30 (distance 56.8). Differences can reflect ROI, illumination, fill stage, or the product itself; the data do not determine which explanation applies.

The summary CSV provides means, ranges, first-to-last changes, and descriptive
within-sequence changes for all RGB and OpenCV HSV channels. Large changes only
describe the measured ROI values. They do not establish contamination, recipe
failure, or cause.

## Outputs

- [Labeled timeline CSV](recipe_14_labeled_timeline.csv): every labeled in-fill frame with its timestamp, vial-relative elapsed time, status, and existing color values where available.
- [Per-vial summary CSV](recipe_14_vial_summary.csv): coverage and descriptive statistics.
- [RGB plot](recipe_14_rgb_over_fill_time.png) and [HSV plot](recipe_14_hsv_over_fill_time.png): measured samples over the label-derived timeline; gaps remain unconnected.
- [Frame coverage plot](recipe_14_frame_coverage.png): measured, excluded, missing, and unclassified frame positions.

## Limitations

`in_fill` is a binary label, not a liquid-level or dispense-phase annotation.
The first in-fill frame may occur after filling has begun. Frames were sampled
sparsely and unevenly. The measurements retain the prior ROI choices, including
their sensitivity to vial movement, lighting, reflections, glass, and support.
The CSV's exclusion reasons describe why the old analysis withheld a frame;
they are not a pixel-level new review. Recipes with low coverage or few points
cannot support strong statements about stable periods or trends. Results are
preliminary observations and are not validated references or thresholds.
