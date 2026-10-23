# Auditable input snapshots for corrected analysis

These CSVs preserve the inputs used to build `results/corrected/`. No original
images or videos are included.

| File | Source |
|---|---|
| `video5_frame_labels_original.csv` | Original Dataset 2 label file supplied with the project. |
| `video5_vial_recipes.csv` | Original Dataset 2 vial-to-recipe table and video fill windows. |
| `video5_frame_labels_corrected.csv` | `color_check/labels_corrected/` on GitHub branch `color-check`, commit `f1c91958ffd6e91abf7f6e74014a78e9ed23f9fc`. |
| `frame_colors.csv` | Salah's automatic liquid finder output from the same commit: `color_check/results/liquid_finder/frame_colors.csv`. |

The versioned copy of the original label CSV uses Unix line endings; its
records and field values are unchanged. The corrected-label and finder CSVs
match `color-check` byte for byte.

The corrected still labels include both the old `video_s` and
`video_s_corrected`. The old column is **photo-clock time**; code must use
`video_s_corrected` to compare a still with the vial fill windows. A few stills
are close to fill boundaries; the generated `label_audit.csv` records the
uncertainty and withholds those cases from reuse.

`frame_colors.csv` describes video frames taken directly on the fill-window
clock. Its RGB/HSV values come from Salah's `liquid_finder` ROI, which moves
with the detected liquid. These values are the sole color input for the new
summaries and Phase 2 profiles. The saved CSV makes the analysis reproducible
without the raw video. Repeating the *pixel extraction* requires the original
video and Salah's extraction and liquid-finder code from `color-check`.

The three duplicate video filenames in the source CSV are kept here for
provenance. The corrected analysis retains the last row per filename because
the later extracted image overwrote the earlier image at that path. Input file
SHA-256 hashes are recorded in `results/corrected/input_hashes.json`.

The [liquid ROI review sheet](examples/video5_liquid_roi_review_sheet.jpg)
and [end-of-fill montage](examples/video5_end_of_fill_all_vials.jpg) are
unchanged visual examples from the same `color-check` commit. They show one
selected frame per vial and cannot validate every frame's ROI.
