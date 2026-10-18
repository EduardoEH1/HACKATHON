# Recipe 13 labeled temporal analysis

[Project overview](../../../README.md) · [Consolidated comparison](../consolidated/README.md) · [Original RGB/HSV measurements](../../recipe_13/recipe_13_manual_roi_measurements.csv)

## Source and method

This analysis joins the existing preliminary ROI measurement CSV to the original
video5 frame labels by exact image filename. It does not inspect or re-measure
image pixels. Each vial's time axis starts at its earliest frame labeled
`in_fill=1`; it is elapsed time from that **label**, not a verified instant of
liquid dispensing. All 55 labeled in-fill frames are retained in the
timeline. No color value is filled in for an excluded, missing, or unclassified
frame.

Measurement source: `results/recipe_13/recipe_13_manual_roi_measurements.csv`  
Labels: `data/raw/recipe7/labels_video5_frame_labels.csv`  
Frames: 42 measured; 13 explicitly excluded by prior ROI review; 0 listed missing; 0 have no matching measurement/exclusion/missing record. Coverage is 42/55 (76.4%).

## Per-vial observations

- Vial 25: 10/19 frames (52.6%); first-half vs last-half mean RGB distance 0.5; median adjacent RGB step 0.6. These describe recorded ROI variation, not a process threshold.
- Vial 26: 18/18 frames (100.0%); first-half vs last-half mean RGB distance 3.1; median adjacent RGB step 0.8. These describe recorded ROI variation, not a process threshold.
- Vial 27: 14/18 frames (77.8%); first-half vs last-half mean RGB distance 0.8; median adjacent RGB step 0.9. These describe recorded ROI variation, not a process threshold.

## Time and vial comparison

Among vials with at least three measurements, Vial 26 has the largest first-half/last-half mean RGB separation (3.1); Vial 25 has the smallest (0.5). This is a descriptive time comparison, not a validated definition of a color change.

Vial 25 has the smallest median step between adjacent measured RGB samples (0.6), so its retained measurements are comparatively close together over time. This does not show what happened in gaps between retained frames.

The farthest pair of measured per-vial mean RGB values is Vials 25 and 27 (distance 28.3). Differences can reflect ROI, illumination, fill stage, or the product itself; the data do not determine which explanation applies.

The summary CSV provides means, ranges, first-to-last changes, and descriptive
within-sequence changes for all RGB and OpenCV HSV channels. Large changes only
describe the measured ROI values. They do not establish contamination, recipe
failure, or cause.

## Outputs

- [Labeled timeline CSV](recipe_13_labeled_timeline.csv): every labeled in-fill frame with its timestamp, vial-relative elapsed time, status, and existing color values where available.
- [Per-vial summary CSV](recipe_13_vial_summary.csv): coverage and descriptive statistics.
- [RGB plot](recipe_13_rgb_over_fill_time.png) and [HSV plot](recipe_13_hsv_over_fill_time.png): measured samples over the label-derived timeline; gaps remain unconnected.
- [Frame coverage plot](recipe_13_frame_coverage.png): measured, excluded, missing, and unclassified frame positions.

## Limitations

`in_fill` is a binary label, not a liquid-level or dispense-phase annotation.
The first in-fill frame may occur after filling has begun. Frames were sampled
sparsely and unevenly. The measurements retain the prior ROI choices, including
their sensitivity to vial movement, lighting, reflections, glass, and support.
The CSV's exclusion reasons describe why the old analysis withheld a frame;
they are not a pixel-level new review. Recipes with low coverage or few points
cannot support strong statements about stable periods or trends. Results are
preliminary observations and are not validated references or thresholds.
