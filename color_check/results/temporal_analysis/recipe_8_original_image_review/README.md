# Recipe 8 original-frame review

[Project overview](../../../README.md) · [Temporal analysis guide](../README.md) · [Consolidated comparison](../consolidated/README.md) · [Original RGB/HSV measurements](../../recipe_8/recipe_8_manual_roi_measurements.csv)

This separate review checks the uploaded original image ZIP against the 55
Recipe 8 `in_fill` labels and re-examines the 31 frames previously excluded
from the fixed-ROI measurements. Earlier Recipe 8 results and plots remain
unchanged.

## ZIP verification

The uploaded archive contains exactly 55 unique JPG filenames. All 55 match
the Recipe 8 filenames in the video label CSV, all decode successfully, and
all are 640×480 pixels. The ZIP uses Windows-style `Recipe_8\\filename.jpg`
paths; the analysis compares the image basenames with the label filenames.

## Review outcome

The old fixed ROI is `(304, 384, 328, 400)`. In later frames the vial moves
relative to this pixel location, so the box can cover a support or an empty
area. I reviewed all 31 previously excluded frames against their full images.

One frame still shows identifiable blue liquid while Vial 10 is moving out of
the original measurement position: `vial_fill_20260923_195432_034496.jpg`, at
video time 442.034 s (6.031 s after the first frame labeled `in_fill=1`). A
small manually moved 24×16-pixel ROI at `(80, 290, 104, 306)` lies inside the
visible blue liquid. This provides one additional **cautious preliminary**
sample. The vial is moving and the image is blurred; the ROI is also at a
different vertical position than the previous fixed ROI, so it is not a
perfect like-for-like comparison.

The recovered ROI mean is RGB `(3.26, 52.40, 75.91)` and OpenCV HSV
`(99.69, 243.28, 75.91)`. The pixels are strongly blue/cyan, but the motion
blur and changed ROI position mean this point should be interpreted only as
evidence that visible blue liquid remains in the vial during that transition.

The other 30 frames remain excluded:

- Vial 10: 15 frames after the moving-vial candidate. The colored vial is no
  longer visible in a stable, identifiable region; the old box falls on the
  support/empty path.
- Vial 11: all 10 later frames show a shifted arrangement of mostly clear
  tubes. The visible regions near the holder and bottom are not confidently
  separable from glass, support, and reflections as colored liquid.
- Vial 12: all 5 later frames likewise lack a reliably isolated colored
  liquid region. A moving ROI would risk sampling clear glass, support, or
  reflections rather than liquid.

No additional values were forced from those frames. The original ZIP and raw
images are not copied into this repository.

## Outputs

- `recipe_8_excluded_frame_review.csv`: timestamped review decision for each
  of the 31 formerly excluded frames.
- `recipe_8_recovered_measurement.csv`: the one manually relocated ROI result
  with its timestamp, ROI coordinates, and motion-blur caveat.
- `recipe_8_temporal_measurements_updated.csv`: the 55-frame labeled timeline
  with 25 color measurements (24 original plus the cautious Vial 10 sample).
  The 30 still-excluded rows have blank color values.
- `recipe_8_temporal_summary_updated.csv`: per-vial/channel descriptive
  statistics for the updated measurements. These are not color references or
  thresholds.
- `recipe_8_rgb_over_time_updated.png` and
  `recipe_8_hsv_over_time_updated.png`: updated time plots. The recovered
  moving-frame value is shown as a hollow square and is not connected to the
  original-ROI line.
- `recipe_8_measurement_coverage_updated.png`: all 55 labeled frames marked
  as measured or still excluded.
- `recipe_8_vial10_442_roi_example.jpg`: old fixed ROI in red and the
  recovered liquid ROI in green.
- `recipe_8_vial_10_excluded_review.jpg`,
  `recipe_8_vial_11_excluded_review.jpg`, and
  `recipe_8_vial_12_excluded_review.jpg`: contact sheets of the excluded
  frames with the fixed ROI marked in red and the recovered ROI, where
  applicable, marked in green.
- `analyze_recipe_8_original_frames.py`: reproducible verification, review,\
  measurement, and plotting script.

## Re-run

The ZIP archive is not included in Git, and `data/raw/` is excluded from Git.
The current workspace has the extracted images under `data/raw/recipe8/images/`,
but the archive-review script requires the original ZIP. From the repository
root, provide the archive path and use the existing label, measurement, and
exclusion CSVs:

```bash
PYTHONPATH=src python results/temporal_analysis/recipe_8_original_image_review/analyze_recipe_8_original_frames.py \
  --zip /path/to/Recipe_8.zip
```

Replace `/path/to/Recipe_8.zip` with the local archive path. The source ZIP and
raw images are not committed.

The 55 labels span about 34–36 seconds per vial, but only 4.0 seconds of Vial
10, 14.1 seconds of Vial 11, and 24.1 seconds of Vial 12 currently have
measurements. This review improves Vial 10 coverage by only one frame, to 6.0
seconds. It does not recover color over the later part of any vial's fill.
The available `in_fill` labels are binary, and no frame-level liquid level,
dispense phase, exact dispense onset, or known-good/known-deviation outcome is
provided. The additional sample is not evidence of contamination or a process
fault.
