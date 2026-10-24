# Phase 2: Anomaly Detection

Phase 2 compares an RGB/HSV measurement with the expected color pattern for
its recipe and filling stage. It returns a numeric `anomaly_score` and status,
or abstains if the input is unreliable or that recipe-stage profile is
unavailable. The detector consumes color measurements; it does not find or
track vials in camera images.

## Inputs and outputs

The scoring interface accepts:

- `recipe_id`: active recipe, 5–14 in the saved Dataset 2 model.
- `r_mean`, `g_mean`, `b_mean`: mean RGB values, each on a 0–255 scale.
- `h_mean_opencv`, `s_mean_opencv`, `v_mean_opencv`: OpenCV HSV values
  (`H` 0–179; `S` and `V` 0–255).
- `fill_progress`: progress from 0 to 1 through the labeled filling window.
- Optional timestamp, plus upstream `found_vial`, `found_liquid`, and
  `confidence` fields when using `score_salah_reading`.

Outputs include `anomaly_score`, `status`, `stage`, `reason`, reference sample
count, `reference_vial_id`, and `reference_status`. A high-confidence liquid
measurement is required. Missing recipe/progress, unreliable detection,
invalid color values, unknown recipes, and unsupported recipe stages return a
status without a score.

## Reference profiles and score

Each recipe has early, middle, and late stages based on equal thirds of its
labeled fill progress. For each available stage, the profile center uses the
median RGB/S/V and a circular hue center. Recipe 11 has no supported early
stage; Recipe 14 has no supported early or middle stage because there are not
enough high-confidence measurements.

The current model uses the last vial of each recipe as a **candidate reference**
on the assumption it may be most flushed. Dataset 2 does not establish that
these vials are normal. The selected vial IDs are recorded in the model,
reference table, frame predictions, and score response, with the status
`provisional; not confirmed normal`.

The score is `100 × color_distance / stage_limit`. The limit is at least the
95th-percentile within-stage variation from that recipe's reference vial and a
shared variation floor estimated from reference-vial measurements only
(9.71% of the scaled channel range in this model). A score at or above 100
returns `review_unusual`. That boundary is an exploratory review setting, not
a validated acceptance or contamination threshold.

## Current evaluation

Evaluation holds each recipe's reference vial out of the comparison set and
scores the other two vials. Of 577 high-confidence measurements with supported
stages, 255 were marked `review_unusual`; 17 of the 20 evaluation vials had at
least one such measurement. This measures difference from one candidate
reference, not detector accuracy. Lighting, ROI variation, fill depth, normal
process variation, or actual fluid differences may contribute. There are no
confirmed good/bad labels to establish precision, recall, or false-alarm rate.

## Run and integrate

From the repository root, use the installed dependencies to rebuild the
current outputs and run the tests:

```bash
PYTHONPATH=src python -m vialsense.corrected_cli build
PYTHONPATH=src python -m unittest discover -s tests -v
```

The build uses the saved measurement inputs and writes under
`results/corrected/`. To score one JSON reading produced by the liquid finder:

```bash
PYTHONPATH=src python -m vialsense.corrected_cli score \
  --recipe-id 9 --progress 0.40 < reading.json
```

`reading.json` must contain the six color fields and detection status fields.
The machine or digital twin supplies the active recipe and fill progress. In
Python, the adapter accepts the dictionary from Salah's
`Detection.to_dict()`:

```python
from vialsense.anomaly import load_model
from vialsense.corrected_pipeline import score_salah_reading

model = load_model("results/corrected/phase2/provisional_model.json")
result = score_salah_reading(
    model,
    detection.to_dict(),
    recipe_id=current_recipe,
    fill_progress=current_fill_progress,
)
```

The tests replay saved high-confidence liquid-finder measurements through the
adapter and CLI, including abstention behavior. A live camera demo also needs
Salah's running detector and a live source for recipe and fill progress; the
checked-in data does not include a camera feed.

## Files

- [Model](provisional_model.json): recipe-stage centers, limits, and reference
  vial IDs.
- [Stage reference table](reference_stage_summary.csv): center values,
  reference counts, vial ID, and per-stage availability.
- [Frame predictions](frame_predictions.csv): measurement status, progress,
  score, status, and reference vial for every saved fill frame.
- [Per-vial evaluation](vial_evaluation_summary.csv): coverage and review
  counts by evaluation vial.

For Phase 1 timelines and color summaries, see the
[RGB/HSV analysis guide](../README.md).
