# Recipe 8 temporal RGB/HSV analysis

This is a descriptive follow-up to the existing preliminary Recipe 8 manual-ROI
measurements. It reuses the recorded RGB/HSV values and timestamps; it does not
re-measure pixels or change any Recipe 8 files.

## Re-run

From the repository root, install the listed dependencies if needed, then run:

```bash
python -m pip install -r requirements.txt
python results/temporal_analysis/analyze_recipe_8_temporal.py
```

The script reads `results/recipe_8/recipe_8_manual_roi_measurements.csv` and
writes its outputs in this folder. `elapsed_s` is measured from the earliest
retained sample for each vial, not from the true start of filling. The input
CSV, label file, and annotated images are unchanged.

## Outputs

- `recipe_8_temporal_measurements.csv`: the selected measurements in timestamp
  order, with a per-vial elapsed time and sample index.
- `recipe_8_temporal_summary.csv`: per-vial/channel means, spread, range,
  first-to-last change, and a descriptive linear slope.
- `recipe_8_rgb_over_time.png`: RGB channels plotted against per-vial elapsed
  time.
- `recipe_8_hsv_over_time.png`: OpenCV HSV channels plotted against per-vial
  elapsed time. OpenCV hue is on a 0–179 scale; saturation and value are 0–255.
- `analyze_recipe_8_temporal.py`: reusable script for regenerating these files.

## Findings in these samples

The 24 retained measurements cover 3 samples for Vial 10 over about 4 seconds,
8 for Vial 11 over about 14 seconds, and 13 for Vial 12 over about 24 seconds.
Vials 10 and 11 remain broadly blue and fairly steady in their short observed
windows. Vial 12 is also broadly blue for most of its measured window, with a
brief brighter point around 4 seconds. Its last three measurements, around
20–24 seconds, shift markedly toward lower blue and higher red, giving a more
green/turquoise appearance in the annotated frames. This is a real change in
the recorded ROI values and is visible in the annotated samples, but the data
do not establish its cause.

## Limits

- The label `in_fill` is only a yes/no flag. There is no per-frame fill level,
  dispense phase, liquid volume, or verified fill-start timestamp.
- Each vial's time axis starts at its first retained measurement. The first
  retained image may already be partway through filling, and the three vial
  timelines are not aligned to a common process start.
- Only the selected frames are represented: later frames were excluded when
  the vial moved away from the fixed ROI. Sampling is sparse (about one image
  every two seconds) and uneven across vials.
- The ROI is a fixed 24-by-16-pixel box near the bottom of the vial. It can be
  affected by movement, glass, support, reflections, and changing liquid depth.
- The existing measurements are preliminary and camera/lighting dependent.
  A color change does not by itself establish contamination or a faulty batch.
  Repeated runs, controlled imaging, verified fill-stage labels, and known-good
  and known-deviation examples are needed before defining normal ranges.
