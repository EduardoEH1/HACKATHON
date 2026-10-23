# Recipe 8 timeline anchored to labeled in-fill frames

[Project overview](../../../README.md) · [Temporal analysis guide](../README.md) · [Original RGB/HSV measurements](../../recipe_8/recipe_8_manual_roi_measurements.csv)

This add-on uses the original video labels, the preliminary measurement CSV,
and the excluded-frame CSV to place measured colors within each vial's complete
**labeled in-fill interval**. It does not change the earlier temporal analysis
or any Recipe 8 results.

## Run it

From the repository root:

```bash
python results/temporal_analysis/recipe_8_fill_timeline/analyze_recipe_8_labeled_timeline.py
```

The script writes three plots and two CSVs in this folder. By default it reads
the video labels at `data/raw/recipe7/labels_video5_frame_labels.csv`, Recipe
8's measurement CSV, and Recipe 8's exclusion CSV. The label file's parent
folder is named `recipe7`, but its contents are the shared `video5` labels.

## What the timestamps establish

`video_s` and `timestamp` are present for all 55 labeled Recipe 8 in-fill
frames. The label rows form three complete segments: Vial 10 has 19 frames from
436.003 to 472.248 seconds in the video; Vial 11 has 18 from 492.356 to
526.559 seconds; Vial 12 has 18 from 550.702 to 584.894 seconds. For each
segment, the labels also contain a non-fill frame immediately before and after.
Thus, the data locate the labeled segments in the source video and bracket
their transitions at roughly the two-second sampling interval.

The plots use elapsed seconds since the first frame labeled `in_fill=1` for
each vial. This is a stronger process-time anchor than the first measured
frame, but it is still a **label-based proxy**, not a verified dispense-onset
time. `in_fill` is a binary frame label; the data do not record the instant
liquid first leaves the nozzle or a per-frame dispense phase or fill level.

## How to read the files

- `recipe_8_labeled_fill_timeline.csv` has one row per labeled in-fill frame,
  with timestamp, absolute video time, elapsed time from the first labeled
  frame, measured/excluded status, any exclusion reason, and RGB/HSV values
  when available. Excluded color values are blank, not zero.
- `recipe_8_fill_window_summary.csv` gives each labeled segment's time range,
  neighboring non-fill frame timestamps, transition brackets, and coverage.
- `recipe_8_rgb_vs_labeled_fill_time.png` and
  `recipe_8_hsv_vs_labeled_fill_time.png` show measured color values against
  the labeled timeline. A curve ending early means the fixed ROI stopped
  yielding measurements, not that the liquid or filling stopped.
- `recipe_8_frame_coverage.png` marks all 55 labeled frames: circles were
  measured, gray crosses were excluded from ROI measurement.
- `analyze_recipe_8_labeled_timeline.py` regenerates the outputs.

## What the expanded timeline suggests

The existing ROI measurements cover only the early portion of each labeled
segment: 3 of 19 frames for Vial 10, 8 of 18 for Vial 11, and 13 of 18 for
Vial 12. All 31 excluded frames occur later in their vial's segment because
the vial moved away from the fixed measurement ROI. The excluded CSV and
labels restore their timestamps and show where measurement coverage ends, but
they contain no color values for those frames.

Consequently, the pronounced green/turquoise shift in Vial 12's last measured
frames can be placed at about 20–24 seconds after the first labeled frame. It
cannot be confirmed whether that color persisted or changed again during the
five later excluded frames. Vials 10 and 11 likewise have no color data for
most of their labeled segments. No contamination or process cause can be
inferred from this timeline alone.

## Limitations and next useful data

The current workspace has the 55 extracted images under
`data/raw/recipe8/images/`, but `data/raw/` is excluded from Git, so a fresh clone
does not contain them. This timeline script reads the labels and existing CSVs,
not the images. To inspect the excluded frames or repeat the original-image
review, obtain the image files (and provide the ZIP to that review script).
For reliable process-time alignment, record a verified dispense-start/end
event or frame-level fill phase/volume label alongside the images. The
timestamps and current measurements remain preliminary and are not anomaly
thresholds.
