# VialSense

VialSense is a small Python prototype for measuring visible liquid color in vial images. It uses OpenCV, NumPy, and pandas. The current work covers preliminary manual-ROI measurements for Recipes 6 and 7.

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

Both commands accept path overrides. Run a command with `--help` to see its options. Outputs are saved in their recipe-specific result folders by default.

## Reusable functions for Salah

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

If Salah's detection system already locates the vial and liquid, it can provide the corresponding image and ROI to this function, or reuse the RGB/HSV calculation with its own detected region. The Recipe 6 and Recipe 7 CSV files can also be loaded with pandas to inspect sampled measurements. The `dataset.load_labeled_frames` function is available for matching one recipe's label rows to local images.

The current ROI coordinates are tied to the existing 640x480 camera framing. They must be adapted or replaced by a validated vial/liquid region from the integrated system if the camera, resolution, position, or framing changes. `color.py` contains an experimental heuristic based on orange/brown pixels; it is not a general-purpose detector and should not be treated as validated for Recipe 7 or production use.

## Reading the measurements

The measurement CSVs contain one row per selected image, including its filename, recipe/vial labels, ROI coordinates, and channel averages. The summary CSVs report descriptive per-vial or combined statistics for those selected images.

RGB channels use the usual 0–255 scale. OpenCV HSV uses H from 0–179 and S/V from 0–255. These are camera pixel values, so lighting, camera exposure/white balance, vial glass, reflections, liquid depth, and fill stage can change them.

Recipe 6 includes 18 samples from three vials. Recipe 7 includes 17 samples, with only one usable measurement from Vial 9. Recipe 7's label says “pale blue”, while the selected images from Vials 7 and 8 appear orange/brown and the one selected Vial 9 frame appears blue. The reason for this difference has not been established. The results must not be used to claim contamination or define a pass/fail threshold.

Before using these measurements for detection, collect and review more representative images at comparable fill stages and under controlled camera/lighting conditions. Then Salah can establish a validated recipe reference and decision logic with the team. No thresholds are defined by this prototype.

## Development branch

Continue recipe work on the existing project branch, `vialsense-recipe6-prototype`. Recipes 6 and 7 are organized as separate result folders within the same project; no per-recipe branches are needed.
