# VialSense color analysis

VialSense is a Python prototype for describing the visible color of liquids in
vials from images recorded at a fluid mixing station. The work supports a
future camera-based check that a vial's observed color is consistent with its
assigned recipe.

> **Project status:** This repository contains preliminary color
> characterization and temporal analysis. It is **not a validated contamination
> detector**. Measurements are not validated recipe references, acceptance
> limits, or contamination thresholds.

## Current progress

- Preliminary RGB and OpenCV HSV measurements are available for Recipes 5–14.
- Temporal plots and labeled-frame coverage summaries are available for all ten
  recipes. The Recipe 8 temporal work includes an additional cautious sample
  from a manually moved ROI; see its [review notes](results/temporal_analysis/recipe_8_original_image_review/README.md).
- Analyses use selected frames and manually reviewed fixed regions of interest
  (ROIs). They describe the recorded pixels; they do not determine why vials or
  time points differ.
- The checked-in branch is `color-analysis`.

## Start here

| I want to… | Start with |
|---|---|
| See the overall temporal comparison and coverage | [Consolidated comparison](results/temporal_analysis/consolidated/README.md) |
| Find a recipe's timeline, plots, and per-vial summary | [Recipe temporal results](#temporal-results) |
| Understand the original per-recipe RGB/HSV measurements | [Recipe result folders](#rgbhsv-results) |
| Recreate temporal plots from the existing CSVs | [Temporal analysis instructions](results/temporal_analysis/README.md) |
| Re-measure image pixels | [Setup and image analysis instructions](#setup-and-reproduce) |

## Method

The original RGB/HSV scripts use OpenCV and pandas to join each recipe's image
labels to selected image files and calculate mean color values. Most recipe
analyses use the shared 24×16-pixel ROI `(304, 384, 328, 400)` in the 640×480
camera view. The samples were selected for visible liquid, and annotated images
show the measured region. Recipe 8's original-image review adds one cautious
measurement using a relocated ROI; that result is kept separate in its temporal
review files.

RGB channels use a 0–255 scale. OpenCV HSV uses hue from 0–179 and saturation
and value from 0–255. These are image pixel values, not calibrated physical
color measurements.

The temporal analyses reuse the saved RGB/HSV values and original frame
timestamps. For Recipes 5–7 and 9–14, elapsed time starts at the first frame
labeled `in_fill=1` for each vial. Recipe 8 has both an earlier measurement-
anchored timeline and a later label-anchored review. `in_fill` is a binary label:
it does not provide exact dispense onset, fill height, liquid volume, or dispense
phase. Frames without a stored measurement stay blank in the timelines.

## Main findings

- Recipe 9 has the strongest measurement coverage (59 of 70 labeled in-fill
  frames) and comparatively similar sampled colors across its three vials.
  Recipe 13 also has relatively high coverage (42 of 55 frames), though Vial 27
  differs visibly from Vials 25 and 26.
- Coverage is uneven. Recipe 12 has 15 measurements for 65 labeled frames;
  Recipe 11 has 19 measurements for 62 labels and 10 image files missing from
  the available set. Recipe 7 has only one measurement for Vial 9. Recipe 14
  has no measurement for Vial 28.
- Other cross-vial or temporal differences appear in Recipes 6, 7, 8, 10, 11,
  12, and 14. Examples include the later turquoise shift in Recipe 8 Vial 12
  and the orange/brown measurements for Recipe 7 Vials 7–8 despite a pale-blue
  recipe description.
- These are differences in selected ROI values. Lighting, reflections, vial
  movement, fill stage, liquid depth, and ROI placement may affect them. The
  current data do not establish contamination or its cause.

The [consolidated comparison](results/temporal_analysis/consolidated/README.md)
includes all ten recipes, per-recipe coverage, and links to the temporal files.

## Repository map

```text
src/vialsense/
  manual_roi.py                 RGB/HSV measurement and ROI annotation
  dataset.py                    Label-to-image matching
  color.py                      Experimental color-based locator; limited scope
  analyze_recipe.py             Experimental single-image analysis entry point
  recipes/                      Recipe-specific manual frame selection/scripts
results/
  recipe_5/ ... recipe_14/      Original RGB/HSV measurements and annotated examples
  temporal_analysis/
    recipe_5/ ... recipe_14/    Timelines, coverage plots, summaries, notes
    recipe_8_*/                 Recipe 8 timeline and original-frame reviews
    consolidated/               Comparison and input-coverage tables
data/raw/                       Local labels and images; excluded from Git
requirements.txt                Python dependencies
```

### RGB/HSV results

Use this table to open the saved measurement CSV or the recipe's temporal page:

| Recipe | RGB/HSV measurements | Temporal results |
|---:|---|---|
| 5 | [Measurement CSV](results/recipe_5/recipe_5_manual_roi_measurements.csv) | [Timeline and plots](results/temporal_analysis/recipe_5/README.md) |
| 6 | [Measurement CSV](results/recipe_6/recipe_6_preliminary_measurements.csv) | [Timeline and plots](results/temporal_analysis/recipe_6/README.md) |
| 7 | [Measurement CSV](results/recipe_7/recipe_7_manual_roi_measurements.csv) | [Timeline and plots](results/temporal_analysis/recipe_7/README.md) |
| 8 | [Measurement CSV](results/recipe_8/recipe_8_manual_roi_measurements.csv) | [Timeline and plots](results/temporal_analysis/recipe_8_fill_timeline/README.md) · [Updated image review](results/temporal_analysis/recipe_8_original_image_review/README.md) |
| 9 | [Measurement CSV](results/recipe_9/recipe_9_manual_roi_measurements.csv) | [Timeline and plots](results/temporal_analysis/recipe_9/README.md) |
| 10 | [Measurement CSV](results/recipe_10/recipe_10_manual_roi_measurements.csv) | [Timeline and plots](results/temporal_analysis/recipe_10/README.md) |
| 11 | [Measurement CSV](results/recipe_11/recipe_11_manual_roi_measurements.csv) | [Timeline and plots](results/temporal_analysis/recipe_11/README.md) |
| 12 | [Measurement CSV](results/recipe_12/recipe_12_manual_roi_measurements.csv) | [Timeline and plots](results/temporal_analysis/recipe_12/README.md) |
| 13 | [Measurement CSV](results/recipe_13/recipe_13_manual_roi_measurements.csv) | [Timeline and plots](results/temporal_analysis/recipe_13/README.md) |
| 14 | [Measurement CSV](results/recipe_14/recipe_14_manual_roi_measurements.csv) | [Timeline and plots](results/temporal_analysis/recipe_14/README.md) |

Each linked `results/recipe_N/` folder also contains summaries and selected
annotated examples. Recipe folders commonly include:

- `recipe_N_manual_roi_measurements.csv` (Recipe 6 uses
  `recipe_6_preliminary_measurements.csv`): per-frame RGB/HSV values, labels,
  timestamps, and ROI coordinates.
- `recipe_N_preliminary_summary_by_vial.csv`: descriptive per-vial channel
  statistics.
- `recipe_N_excluded_frames.csv` and `recipe_N_missing_frames.csv`, when
  present: frames withheld from measurement or absent from the available files.
- `annotated_images/`, `roi_examples/`, or `recipe_N_roi_montage_vial_*.jpg`:
  visual records of selected ROIs.

Some older recipe analyses store their summary and annotated examples under
slightly different names. The files are listed in each [recipe result folder](results/).

### Temporal results

Each linked temporal page contains a labeled timeline CSV, per-vial summary,
RGB and HSV plots, frame-coverage plot, and recipe-specific notes. Recipe 8 has
separate pages because its timeline was extended in stages; the updated image
review is the latest summary of its 25 available values.

## Setup and reproduce

Use Python 3.10 or newer. From the repository root, create an environment and
install the dependencies:

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell instead:
# .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

In VS Code, select `.venv/bin/python` (macOS/Linux) or
`.venv\Scripts\python.exe` (Windows) as the interpreter.

### Data files

Raw datasets are not stored in Git. Obtain the Dataset 2 labels and images
separately. The shared video 5 label file is expected at
`data/raw/recipe7/labels_video5_frame_labels.csv`; despite that directory name,
it contains labels for Recipes 5–14. Image files are expected in
`data/raw/recipeN/images/` for each recipe.

The current checkout has the original images for Recipes 5 and 7–14. Recipe 11
has 52 of 62 labeled images; ten are documented as missing. Recipe 6's 36
original images are not present in this checkout. A clean Git clone contains
none of the ignored `data/raw/` files, so image-level analyses require the local
data files to be provided first.

### Re-run temporal analysis

This uses existing measurements; it does not re-read or measure image pixels.
From the repository root:

```bash
python results/temporal_analysis/analyze_recipe_timelines.py
```

It reads the shared labels and saved per-recipe measurement/exclusion/missing
CSV files, then regenerates temporal outputs for Recipes 5–7 and 9–14 plus the
consolidated comparison. Recipe 8 is read from its existing updated timeline;
its result files are not regenerated by this script. See
[temporal analysis details](results/temporal_analysis/README.md).

### Re-run RGB/HSV image measurements

The recipe modules use the shared labels and local raw images. For example,
Recipe 5 can be run without replacing the checked-in results by directing output
to a temporary folder:

```bash
PYTHONPATH=src python -m vialsense.recipes.recipe5_manual \
  --labels data/raw/recipe7/labels_video5_frame_labels.csv \
  --images data/raw/recipe5/images \
  --output-dir /tmp/vialsense-recipe5
```

On Windows PowerShell, set the import path first:

```powershell
$env:PYTHONPATH = "src"
python -m vialsense.recipes.recipe5_manual `
  --labels data/raw/recipe7/labels_video5_frame_labels.csv `
  --images data/raw/recipe5/images `
  --output-dir "$env:TEMP\vialsense-recipe5"
```

Recipes 5 and 7–14 accept `--labels`, `--images`, and `--output-dir`; inspect a
module's `--help` for its defaults and checks. Recipe 6 has a different command
interface (`--labels`, `--images`, `--output`, `--examples`) and cannot be
rerun from this checkout until its original images are restored. Recipe 11's
script permits the documented missing images and checks the available set.
Directing output to a temporary folder avoids replacing the published results.

After restoring the Recipe 6 images under `data/raw/recipe6/images/`, its
command is:

```bash
PYTHONPATH=src python -m vialsense.recipes.recipe6_manual \
  --labels data/raw/recipe7/labels_video5_frame_labels.csv \
  --images data/raw/recipe6/images \
  --output /tmp/vialsense-recipe6/recipe_6_preliminary_measurements.csv \
  --examples /tmp/vialsense-recipe6/examples
```

Recipe 8's `recipe8_manual` module reproduces its original 24 fixed-ROI values.
The later 25-value temporal CSV also contains one cautious relocated-ROI
measurement; it is documented separately and is not generated by that module.

## Limitations and appropriate use

- The camera framing and ROI are not automatically adapted to a moving vial.
- ROI pixels can include glass, reflections, supports, or changing amounts of
  liquid. Sample coverage and time spacing vary by vial.
- Recipe 8 has one extra relocated-ROI measurement marked cautious; it is not
  directly comparable to its fixed-ROI samples.
- Lighting and camera settings are not calibrated. Recipe labels and
  `color_purpose` descriptions do not verify that a vial was a known-good
  product.
- The repository has no confirmed contamination labels, controlled
  good/bad-run dataset, or validated acceptance limits.

The results are useful for learning, visual review, and planning a future
detector. Do not use them alone to label a vial contaminated or make a
production decision. A validated detector would need controlled imaging,
repeated known-good runs, known deviations with ground truth, and an evaluated
liquid/vial localization method.
