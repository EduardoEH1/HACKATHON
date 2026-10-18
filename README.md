# VialSense

VialSense is a small Python prototype for measuring visible liquid color in vial images. It uses OpenCV, NumPy, and pandas. The current work covers preliminary manual-ROI measurements for Recipes 6, 7, and 8.

> **Status:** Every measurement in this repository is preliminary. The CSV summaries describe the sampled images only. They are not validated color references, acceptance limits, or contamination thresholds.

## Project layout

```text
src/vialsense/
  manual_roi.py                  Shared RGB/HSV measurement and ROI annotation functions
  dataset.py                     Loads recipe-labeled image rows and checks image paths
  color.py                       Experimental color-column heuristic and pixel filtering
  recipes/
    recipe6_manual.py            Recipe 6 sample selection and result generation
    recipe7_manual.py            Recipe 7 sample selection and result generation
    recipe8_manual.py            Recipe 8 sample selection and result generation
results/
  recipe_6/
    recipe_6_preliminary_measurements.csv
    recipe_6_preliminary_summary_by_vial.csv
    recipe_6_preliminary_summary_overall.csv
    roi_examples/                Annotated Recipe 6 images and vial montages
  recipe_7/
    recipe_7_manual_roi_measurements.csv
    recipe_7_preliminary_summary_by_vial.csv
    recipe_7_excluded_frames.csv
    annotated_images/             Annotated Recipe 7 images
    recipe_7_roi_montage_vial_*.jpg
  recipe_8/
    recipe_8_manual_roi_measurements.csv
    recipe_8_preliminary_summary_by_vial.csv
    recipe_8_excluded_frames.csv
    annotated_images/             Annotated Recipe 8 images
    recipe_8_roi_montage_vial_*.jpg
requirements.txt
```

`data/raw/` is reserved for local dataset files and is excluded from Git. Dataset ZIP archives, videos, and full collections of unannotated source images are not part of this project.

## Set up the environment

From the repository root, create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
. .venv/bin/activate             # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
```

In VS Code, select `.venv/bin/python` as the interpreter (on Windows, `.venv\Scripts\python.exe`).

## Run the recipe analyses

Place the original video 5 label CSV and vial-fill images at:

```text
data/raw/vial_fill/labels_video5_frame_labels.csv
data/raw/vial_fill/images/
```

Then run Recipe 6:

```bash
PYTHONPATH=src python -m vialsense.recipes.recipe6_manual
```

The script selects the existing sample of 18 frames: 5 each from Vials 4 and 5, and 8 from Vial 6. It writes the measurement and summary CSV files and annotated examples under `results/recipe_6/`.

For Recipe 7, place its 36 images and frame labels at:

```text
data/raw/recipe7/images/
data/raw/recipe7/labels_video5_frame_labels.csv
```

Then run:

```bash
PYTHONPATH=src python -m vialsense.recipes.recipe7_manual
```

The script keeps 17 manually selected samples (8 from Vial 7, 8 from Vial 8, and 1 from Vial 9). The other 19 frames and their exclusion notes are in `results/recipe_7/recipe_7_excluded_frames.csv`.

### Preliminary Results: Recipe 8

The labels describe Recipe 8 as an even triple of 20 ml from each tank (60 ml total, dispense order `T200>T400>T100`). The uploaded ZIP contained 55 images. All 55 filenames matched the Recipe 8 in-fill rows in the label CSV, with 19 images for Vial 10, 18 for Vial 11, and 18 for Vial 12. All images were readable at 640×480. The analysis uses the same fixed manual ROI as Recipes 6 and 7 and retains frames where visible colored liquid is inside that ROI: 3 from Vial 10, 8 from Vial 11, and 13 from Vial 12. The other 31 frames and their exclusion notes are listed in `results/recipe_8/recipe_8_excluded_frames.csv`.

Run the analysis with:

```bash
PYTHONPATH=src python -m vialsense.recipes.recipe8_manual \
  --labels data/raw/recipe7/labels_video5_frame_labels.csv \
  --images data/raw/recipe8/images \
  --output-dir results/recipe_8
```

The preliminary per-vial means are:

| Vial | Samples | Mean RGB | Mean HSV (OpenCV) |
|---|---:|---|---|
| 10 | 3 | (5.90, 38.31, 54.79) | (100.21, 229.31, 54.79) |
| 11 | 8 | (7.72, 41.14, 58.49) | (100.27, 222.55, 58.49) |
| 12 | 13 | (7.57, 43.93, 62.71) | (98.49, 216.83, 63.13) |

The selected regions look blue across the three vials. Vials 10 and 11 have similar sampled averages. Vial 12 is more variable: its first 10 selected frames average RGB (6.20, 47.38, 71.39), while its last 3 selected frames average (12.00, 32.26, 33.70) and look darker and more teal/green. Fill stage, liquid motion or mixing, glass/reflections, and ROI optics could affect this change; these images do not establish its cause. These measurements remain preliminary and are not validated reference colors or contamination thresholds.

All three commands accept path overrides. Run a command with `--help` to see its options. Outputs are saved in their recipe-specific result folders by default.

## Reusable functions for integration

The shared function `vialsense.manual_roi.measure_roi` takes an image path and a rectangle `(x1, y1, x2, y2)` in pixel coordinates. It returns mean RGB and OpenCV HSV values. Example:

```python
from pathlib import Path
from vialsense.manual_roi import measure_roi

# This is the prototype ROI for the current 640x480 camera view.
roi = (304, 384, 328, 400)
values = measure_roi(Path("frame.jpg"), roi)
rgb = (values["r_mean"], values["g_mean"], values["b_mean"])
hsv_opencv = (
    values["h_mean_opencv"],
    values["s_mean_opencv"],
    values["v_mean_opencv"],
)
```

If an integrated detection system already locates the vial and liquid, it can provide the corresponding image and ROI to this function, or reuse the RGB/HSV calculation with its own detected region. The Recipe 6 and Recipe 7 CSV files can also be loaded with pandas to inspect sampled measurements. The `dataset.load_labeled_frames` function is available for matching one recipe's label rows to local images.

The current ROI coordinates are tied to the existing 640x480 camera framing. They must be adapted or replaced by a validated vial/liquid region from the integrated system if the camera, resolution, position, or framing changes. `color.py` contains an experimental heuristic based on orange/brown pixels; it is not a general-purpose detector and should not be treated as validated for Recipe 7 or production use.

## Reading the measurements

The measurement CSVs contain one row per selected image, including its filename, recipe/vial labels, ROI coordinates, and channel averages. The summary CSVs report descriptive per-vial or combined statistics for those selected images.

RGB channels use the usual 0–255 scale. OpenCV HSV uses H from 0–179 and S/V from 0–255. These are camera pixel values, so lighting, camera exposure/white balance, vial glass, reflections, liquid depth, and fill stage can change them.

Recipe 6 includes 18 samples from three vials. Recipe 7 includes 17 samples, with only one usable measurement from Vial 9. Recipe 7's label says “pale blue”, while the selected images from Vials 7 and 8 appear orange/brown and the one selected Vial 9 frame appears blue. The reason for this difference has not been established. The results must not be used to claim contamination or define a pass/fail threshold.

Before using these measurements for detection, collect and review more representative images at comparable fill stages and under controlled camera/lighting conditions. The project team can then establish a validated recipe reference and decision logic. No thresholds are defined by this prototype.

## Development branch

Continue recipe work on the existing project branch, `color-analysis`. Each recipe has a separate result folder within the same project; no per-recipe branches are needed.
