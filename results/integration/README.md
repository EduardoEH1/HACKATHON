# Detector → Phase 1 → Phase 2 integration

This branch combines Salah's `find_liquid(frame)` with the existing
`score_salah_reading()` adapter. The saved Dataset 2 Video 5 workflow is
executable from the checked-in CSVs. The same runner can measure frames from
an MP4 when the original video is available.
`liquid_finder.py` and `find_color.py` are copied unchanged from `color-check`
commit `f1c91958ffd6e91abf7f6e74014a78e9ed23f9fc`.

## Run the saved Video 5 workflow

From the repository root, install `requirements.txt`, then run:

```bash
PYTHONPATH=src python -m vialsense.integration_cli saved
```

The command reads `inputs/color_check/frame_colors.csv`,
`inputs/color_check/video5_vial_recipes.csv`, and the existing provisional
model. It uses `prepare_video_timeline()` for Phase 1 and
`evaluate_corrected()` / `score_salah_reading()` for Phase 2. It writes
[Video 5 outputs](video5_saved/) in this folder. The run reproduces 1,067
unique fill frames, 879 high-confidence liquid colors, 577 scored evaluation
frames, and 255 provisional review flags. These counts match the current
Phase 1 and Phase 2 outputs; the flags are not confirmed contamination.

## Run from the original Video 5 MP4

When the Dataset 2 Video 5 MP4 is available locally, run:

```bash
PYTHONPATH=src python -m vialsense.integration_cli video \
  --video data/raw/dataset2/vial_fill/videos/vial_fill_video_5.mp4 \
  --windows inputs/color_check/video5_vial_recipes.csv \
  --output-dir results/integration/video5_from_mp4
```

The runner samples each labeled fill window once per second, calls Salah's
`find_liquid(frame)` on each frame, and passes its RGB/HSV and quality fields
through the same Phase 1 and Phase 2 path. The video itself is not checked in,
so this command needs a local copy. The video command was exercised with a
small generated clip; the original MP4 still needs a full rerun and visual
ROI review.

For a new video without a recipe/fill-window table, omit `--windows`. The
runner will save detector colors but give each frame `invalid_input` and no
anomaly score. When a machine timeline becomes available, provide a CSV with
`vial`, `recipe_id`, `start_s`, `end_s`, and `duration_s`. The recipe must have
a profile in the current model (Recipes 5–14). `fill_progress` is computed as
elapsed video time divided by that vial's labeled fill duration. This is a
time proxy, not measured liquid volume.

## Output files

- `detector_readings.csv`: liquid finder fields, frame time, recipe, and fill
  progress when available.
- `phase1_timeline.csv`, `phase1_vial_summary.csv`,
  `phase1_recipe_summary.csv`: filtered RGB/HSV measurements and coverage.
- `phase2_predictions.csv`, `phase2_vial_summary.csv`: per-frame status/score
  and per-vial evaluation. The vial summary is generated for labeled runs.
- `run_summary.json`: counts and the provisional result status.

The saved workflow uses the checked-in detector CSV, so it checks the full
data-to-score connection but does not repeat pixel extraction. Running the
MP4 command repeats pixel extraction. Neither path validates detection
accuracy or contamination accuracy without reviewed ground truth.

## Tests

```bash
PYTHONPATH=src python -m pytest -q tests
```

The integration tests check saved Video 5 outputs against the existing
results, a generated video frame through `find_liquid` and Phase 1/2 scoring,
and abstention when a new video's recipe timeline is unavailable.
