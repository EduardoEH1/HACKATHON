# Corrected provisional anomaly detector

The [model](provisional_model.json) compares a high-confidence liquid color to
its recipe's early, middle, or late **video fill stage**. It uses the same
automatic liquid-finder RGB/HSV method as the checked-in video measurements.
The earlier Phase 2 model under `results/anomaly_detection/` was trained with
incorrect still labels and should be treated as historical.

## Reference selection and score

For each recipe, only its **last vial** supplies a provisional color pattern.
The last vial is a candidate for the most flushed color, **not a confirmed
good product**. The first two vials of each recipe are kept out of reference
fitting and the review-boundary calculation. Each stage needs at least four
high-confidence measurements from that last vial. The RGB/S/V center is a
median and hue uses a circular center.

The reference table and each scored frame/CLI response now name the specific
`reference_vial_id` and label it `provisional; not confirmed normal`. In the
JSON model, `reference_vials` maps recipe IDs to the chosen vial IDs; the
per-stage `vial_ids` field also identifies the source. `reference_vials` in a
score response remains a count of contributing vials, so use
`reference_vial_id` to see which vial supplied the reference.

The detector uses the existing Phase 2 RGB/HSV distance formula. It divides
the distance by a provisional stage limit and multiplies by 100. The limit is
at least the 95th percentile of variation in that last vial's stage and a
shared measurement-variation floor derived from **reference-vial readings
only** (about 9.71% of scaled channel range here). `anomaly_score >= 100`
returns `review_unusual`. This boundary is for a hackathon review prototype;
it is **not a validated contamination or acceptance threshold**.

There are 27 usable recipe-stage references. Recipe 11 has no early reference;
Recipe 14 has no early or middle reference because its last vial has no
high-confidence liquid measurement at those times. These stages return
`insufficient_reference` with no score. Missing liquid, low confidence, and
invalid measurements also receive no score.

## Evaluation files

- [Stage references](reference_stage_summary.csv): available stages, sample
  counts, candidate vial, RGB/HSV center, and provisional limit.
- [Frame predictions](frame_predictions.csv): every labeled video fill frame,
  original quality status, split (`reference` or `evaluation`), score/status,
  and fill time. Low-quality frames retain blank scores.
- [Per-vial evaluation](vial_evaluation_summary.csv): coverage, number of
  review flags, and earliest possible score or flag.

Across the **20 evaluation vials**, 577 high-confidence frames had supported
stages; 255 were marked for review. Seventeen of those vials had at least one
flag. This is a measure of difference from a single candidate reference vial,
not detection accuracy. Some vials may differ due to carryover, lighting,
motion, liquid depth, or the finder ROI. There are no confirmed good/bad labels
for precision, recall, or a false-alarm rate. A first review flag can be used
for a demo timeline, but the actual start of contamination is unknown.

## Feed Salah's output to the detector

`score_salah_reading` in
[corrected_pipeline.py](../../../src/vialsense/corrected_pipeline.py)
accepts the dictionary returned by Salah's `Detection.to_dict()` or one row
from his `frame_colors.csv`. It passes RGB `(r_mean, g_mean, b_mean)` and
OpenCV HSV `(h_mean_opencv, s_mean_opencv, v_mean_opencv)` to the existing
`score_measurement` function. It checks `found_vial`, `found_liquid`, and
`confidence == "high"` before scoring. A live `Detection` has no recipe or
progress, so the machine/digital-twin integration must supply them:

```python
from vialsense.anomaly import load_model
from vialsense.corrected_pipeline import score_salah_reading

model = load_model("results/corrected/phase2/provisional_model.json")
# detection = find_liquid(frame)  # from Salah's liquid_finder on color-check
result = score_salah_reading(
    model, detection.to_dict(), recipe_id=current_recipe,
    fill_progress=current_fill_progress,
)
```

For a single JSON line emitted by Salah's `find_color` command, run:

```bash
PYTHONPATH=src python -m vialsense.corrected_cli score \
  --recipe-id 9 --progress 0.104 < reading.json
```

The `score` command returns JSON with `anomaly_score`, `status`, `stage`,
`reference_vial_id`, `reference_status`, reference sample count, and reason.
`reading.json` must contain the six color fields, `found_vial`, `found_liquid`,
and `confidence`. The `score` command also accepts `--reading-file`. The
machine recipe and fill progress are required; a camera timestamp alone cannot
supply them.

The integration check replays a high-confidence row from the saved
`frame_colors.csv` through the same adapter and CLI used for live readings.
It validates detector-output-to-score wiring and abstention behavior. A live
camera session still needs Salah's running capture/detection code and a source
of current recipe/fill progress; this workspace does not contain a live camera
feed or the original video file.

Do not compare these video-ROI measurements to the old fixed-ROI Phase 2
model. The color distributions and clock labels differ. To improve the model,
obtain known-good and deliberately abnormal runs, confirm reference-vial
quality, and measure performance before using an automatic product alert.
