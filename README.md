# VialSense: RGB/HSV Color Analysis and Anomaly Detection

VialSense is a Python prototype for comparing liquid color measurements with
the expected color pattern for a programmed recipe. It is organized as two
phases: **Phase 1 measures and summarizes color over filling progress**, and
**Phase 2 compares a measurement with a recipe-specific provisional profile**.

This is a hackathon prototype. Its references and review flags are exploratory;
they are not validated product limits or proof of contamination.

## Phase 1: RGB/HSV Color Analysis

The current analysis uses saved measurements from Salah's automatic liquid
finder. For Dataset 2 Video 5, it covers 30 vials across Recipes 5–14 and
1,067 unique labeled fill frames. The finder supplied high-confidence liquid
colors for 879 frames; other frames remain in the timelines without color
values. Each usable measurement contains mean RGB and OpenCV HSV values,
timestamp, recipe, vial, and progress through the labeled fill window.

The RGB/HSV values describe pixels selected by the liquid finder. They are not
calibrated physical color readings. `fill_progress` is a time-based position
from 0 to 1 within a labeled fill window, not measured liquid volume.

- [Phase 1 results, recipe timelines, and plots](results/corrected/README.md)
- [Combined recipe summary](results/corrected/phase1/recipe_summary.csv)
- [Per-vial summary](results/corrected/phase1/vial_summary.csv)
- [Consolidated temporal comparison](results/temporal_analysis/consolidated/README.md)
- [Earlier manual-ROI recipe measurements](#additional-exploratory-results)

## Phase 2: Anomaly Detection

Phase 2 compares RGB/HSV input with the recipe's early, middle, or late filling
pattern. It returns an `anomaly_score` and status, or abstains when the color,
confidence, recipe-stage reference, or process context is unavailable. It does
not locate a vial or liquid in a camera frame; that measurement is supplied by
the upstream detector.

The current profiles use one candidate reference vial per recipe. These
references are **provisional and not confirmed normal**. A `review_unusual`
result requests review; it does not diagnose contamination. Evaluation held
out the other two vials per recipe: 577 high-confidence measurements received
scores and 255 were marked for review. There are no confirmed good/bad labels,
so these counts do not measure accuracy, false-alarm rate, or contamination.

- [Phase 2 methodology, results, and integration instructions](results/corrected/phase2/README.md)
- [Stage reference table](results/corrected/phase2/reference_stage_summary.csv)
- [Frame-level scores](results/corrected/phase2/frame_predictions.csv)
- [Per-vial evaluation summary](results/corrected/phase2/vial_evaluation_summary.csv)

The scoring interface accepts a recipe ID, RGB, OpenCV HSV, fill progress, and
optional timestamp. `score_salah_reading` also accepts the dictionary returned
by Salah's liquid-finder `Detection.to_dict()` or a saved measurement row. Live
use requires the machine or digital twin to provide current recipe and fill
progress.

## Integrated detector run

The [integration guide](results/integration/README.md) shows how to replay
Dataset 2 Video 5 through Phase 1 and Phase 2, or run Salah's `find_liquid()`
on a local copy of the Video 5 MP4. Saved replay is executable without raw
video. For a new video without recipe/fill timing, the runner saves color
readings and leaves anomaly scores blank until that context is provided.

## Live mode

[LIVE_MODE.md](LIVE_MODE.md) runs the full check on a live camera. The camera
supplies the timing (vial arrival, fill start, departure), and the operator
types the recipe queue before the run. A one-time calibration maps any camera
view onto the view the liquid finder was tuned on. Each flagged vial gets a
cause: for example, "Likely carryover from Recipe 6". Replaying video 5 as live
with labels hidden: 30 of 30 vials tracked, 9 of 10 carryover vials flagged,
1 false alarm in 10 clean vials.

```bash
PYTHONPATH=src python -m vialsense.live_cli calibrate --camera 0
PYTHONPATH=src python -m vialsense.live_cli run --camera 0 --recipes "7x3,8x3" --previous-recipe 6
```

## Setup and run

Use Python 3.10 or newer. From the repository root:

```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Rebuild the current Phase 1 summaries and Phase 2 model from checked-in CSV
snapshots, then run the integration and analysis checks:

```bash
PYTHONPATH=src python -m vialsense.corrected_cli build
PYTHONPATH=src python -m pytest -q tests
```

The build writes under `results/corrected/`. It needs no raw images or video;
the saved inputs are in [`inputs/color_check/`](inputs/color_check/README.md).
Repeat pixel extraction from source images/video only when the corresponding
raw media and liquid-finder code are available.

To score a single liquid-finder JSON reading, supply the model, current recipe,
and filling progress:

```bash
PYTHONPATH=src python -m vialsense.corrected_cli score \
  --recipe-id 9 --progress 0.40 < reading.json
```

The input JSON must include `r_mean`, `g_mean`, `b_mean`, `h_mean_opencv`,
`s_mean_opencv`, `v_mean_opencv`, `found_vial`, `found_liquid`, and
`confidence`. See the [Phase 2 guide](results/corrected/phase2/README.md) for
the Python interface and returned fields.

## Repository guide

```text
src/vialsense/                 Reusable color, timeline, and anomaly functions
inputs/color_check/            Saved label and liquid-finder CSV inputs
results/corrected/phase1/      Current RGB/HSV timelines, summaries, plots
results/corrected/phase2/      Current provisional model and scores
results/integration/           Detector-to-score runs and instructions
results/temporal_analysis/      Earlier temporal comparisons and reports
results/recipe_5 ... recipe_14/ Earlier manual-ROI samples and annotations
tests/                          Checks for Phase 2 and saved integration data
```

### Additional exploratory results

The repository also retains selected manual-ROI RGB/HSV samples and temporal
analyses for Recipes 5–14. Those files provide exploratory examples and
historical measurements; the current Phase 1 and Phase 2 workflow described
above uses the saved automatic liquid-finder measurements under
`inputs/color_check/` and `results/corrected/`.

## Method and limitations

- Phase 1 retains only colors with a detected vial, detected liquid, and high
  finder confidence. The confidence signal is algorithmic and does not verify
  every pixel in the selected region as liquid.
- Lighting, reflections, glass, liquid depth, camera settings, or vial motion
  may affect RGB/HSV values. The measurement setup is not color-calibrated.
- Each recipe reference comes from its final vial, chosen as a candidate for a
  well-flushed sample. Dataset 2 does not confirm that this vial is normal.
- Some recipe-stage references have too few usable measurements. The detector
  returns `insufficient_reference` for unsupported stages.
- The review boundary is a prototype setting based on observed reference-vial
  variation. Dataset 2 has no verified contamination labels, so it cannot
  establish detector accuracy or validated alert thresholds.
- A live camera-to-score demo requires Salah's running liquid detector plus
  machine or digital-twin context for recipe and fill progress. The checked-in
  integration tests replay saved detector measurements.

Use the results to explore color behavior and demonstrate the data flow. Do
not use review flags alone to classify product or trigger an industrial
decision.
