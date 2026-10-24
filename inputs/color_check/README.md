# Saved Dataset 2 analysis inputs

This folder contains the CSV snapshots used to reproduce the current Phase 1
RGB/HSV summaries and Phase 2 profiles. Raw video and source images are not
included.

| File | Use and source |
|---|---|
| `video5_vial_recipes.csv` | Dataset 2 vial-to-recipe map and video-time fill windows. |
| `video5_frame_labels_original.csv` | Original still-image labels, retained for audit and traceability. |
| `video5_frame_labels_corrected.csv` | Still-image label alignment data from `color-check`, commit `f1c91958ffd6e91abf7f6e74014a78e9ed23f9fc`. |
| `frame_colors.csv` | Saved RGB/HSV measurements and quality fields from Salah's liquid finder on Video 5. |

The current color timelines and detector profiles use `frame_colors.csv`,
video timestamps, and the vial fill windows. Values enter the analysis only
when the finder reports a vial and liquid with high confidence. The still-image
label files support alignment auditing and do not supply the current Phase 1
color values.

The saved frame colors make the numeric analysis reproducible without raw
media. Repeating pixel extraction requires the original Video 5 file and the
liquid-finder implementation. The generated `results/corrected/input_hashes.json`
records hashes for the input CSV snapshots.
