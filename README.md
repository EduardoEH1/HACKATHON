# VialSense

VialSense is a small Python prototype for measuring visible liquid color in vial images. It uses OpenCV, NumPy, and pandas. The current work covers preliminary manual-ROI measurements for Recipes 6, 7, 8, 9, 10, 11, 12, and 13.

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
    recipe9_manual.py            Recipe 9 sample selection and result generation
    recipe10_manual.py           Recipe 10 sample selection and result generation
    recipe11_manual.py           Recipe 11 sample selection and result generation
    recipe12_manual.py           Recipe 12 sample selection and result generation
    recipe13_manual.py           Recipe 13 sample selection and result generation
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
  recipe_9/
    recipe_9_manual_roi_measurements.csv
    recipe_9_preliminary_summary_by_vial.csv
    recipe_9_excluded_frames.csv
    annotated_images/             Annotated Recipe 9 images
    recipe_9_roi_montage_vial_*.jpg
  recipe_10/
    recipe_10_manual_roi_measurements.csv
    recipe_10_preliminary_summary_by_vial.csv
    recipe_10_excluded_frames.csv
    annotated_images/             Annotated Recipe 10 images
    recipe_10_roi_montage_vial_*.jpg
  recipe_11/
    recipe_11_manual_roi_measurements.csv
    recipe_11_preliminary_summary_by_vial.csv
    recipe_11_excluded_frames.csv
    recipe_11_missing_frames.csv
    annotated_images/             Annotated Recipe 11 images
    recipe_11_roi_montage_vial_*.jpg
  recipe_12/
    recipe_12_manual_roi_measurements.csv
    recipe_12_preliminary_summary_by_vial.csv
    recipe_12_excluded_frames.csv
    recipe_12_missing_frames.csv
    annotated_images/             Annotated Recipe 12 images
    recipe_12_roi_montage_vial_*.jpg
  recipe_13/
    recipe_13_manual_roi_measurements.csv
    recipe_13_preliminary_summary_by_vial.csv
    recipe_13_excluded_frames.csv
    recipe_13_missing_frames.csv
    annotated_images/             Annotated Recipe 13 images
    recipe_13_roi_montage_vial_*.jpg
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

### Preliminary Results: Recipe 9

The labels describe Recipe 9 as an 80 ml triple mixture (10 ml T100, 35 ml T200, and 35 ml T400; dispense order `T200>T400>T100`) with the purpose “dark saturated (low clear)”. The uploaded ZIP contained 70 images. All 70 filenames matched the Recipe 9 in-fill rows in the label CSV, and all were readable at 640×480. Using the same fixed manual ROI, the analysis retains 59 frames with visible liquid: 17 from Vial 13, 18 from Vial 14, and all 24 from Vial 15. The remaining 11 frames show Vials 13 or 14 moving away from the fixed ROI and are listed with reasons in `results/recipe_9/recipe_9_excluded_frames.csv`.

Run the analysis with:

```bash
PYTHONPATH=src python -m vialsense.recipes.recipe9_manual \
  --labels data/raw/recipe7/labels_video5_frame_labels.csv \
  --images data/raw/recipe9/images \
  --output-dir results/recipe_9
```

The preliminary per-vial means are:

| Vial | Samples | Mean RGB | Mean HSV (OpenCV) |
|---|---:|---|---|
| 13 | 17 | (15.95, 27.66, 23.46) | (79.57, 111.85, 27.67) |
| 14 | 18 | (15.87, 25.14, 21.37) | (80.64, 99.78, 25.44) |
| 15 | 24 | (15.46, 24.31, 19.97) | (74.78, 99.50, 24.33) |

The sampled liquid is very dark and greenish across all three vials. Vials 13 and 14 have similar averages. Vial 15 shifts toward a darker olive/yellow-green appearance in its last 8 frames: their mean RGB is (17.65, 23.51, 17.83), compared with (14.36, 24.70, 21.04) across its first 16 frames. The mean OpenCV V value is only about 24–28, so small reflections, glass, and image noise can have a noticeable effect on hue and saturation. Fill stage or optical effects may contribute; the images do not establish the cause. These measurements are preliminary, not validated color references or contamination thresholds.

### Preliminary Results: Recipe 10

The labels describe Recipe 10 as a 75 ml triple mixture (45 ml T100, 15 ml T200, and 15 ml T400; dispense order `T200>T400>T100`) with the purpose “pale wash (high clear)”. The uploaded ZIP contained 57 images. All 57 filenames matched the Recipe 10 in-fill rows in the label CSV, and all were readable at 640×480. Using the same fixed manual ROI, the analysis retains 38 frames with visible liquid: 14 from Vial 16, 5 from Vial 17, and 19 from Vial 18. The other 19 frames and their exclusion reasons are listed in `results/recipe_10/recipe_10_excluded_frames.csv`.

Run the analysis with:

```bash
PYTHONPATH=src python -m vialsense.recipes.recipe10_manual \
  --labels data/raw/recipe7/labels_video5_frame_labels.csv \
  --images data/raw/recipe10/images \
  --output-dir results/recipe_10
```

The preliminary per-vial means are:

| Vial | Samples | Mean RGB | Mean HSV (OpenCV) |
|---|---:|---|---|
| 16 | 14 | (24.08, 36.09, 30.84) | (79.11, 104.29, 36.14) |
| 17 | 5 | (16.49, 23.40, 19.35) | (73.56, 81.15, 23.40) |
| 18 | 19 | (13.68, 22.30, 19.85) | (81.99, 102.13, 22.40) |

Most retained frames look very dark green, which differs from the label description “pale wash”. Vials 17 and 18 have similarly dark averages. Vial 16's first retained frame is a lighter, low-saturation transition (RGB 93.13, 101.46, 77.47; OpenCV HSV 40.37, 60.56, 101.46); its remaining 13 frames average RGB (18.77, 31.06, 27.25) and look dark green. That visible transition frame raises Vial 16's overall mean. Fill stage, mixing, reflections, and the glass can affect these measurements. The images do not establish the cause or show contamination. Results remain preliminary, not validated reference colors or thresholds.

### Preliminary Results: Recipe 11

The label CSV contains 62 in-fill images: 20 for Vial 19, 21 for Vial 20, and 21 for Vial 21. The uploaded ZIP contains 52 readable images at 640×480. All 52 filenames match Recipe 11 labels and there are no extra filenames from other recipes. Ten labeled images were absent; their exact names are in `results/recipe_11/recipe_11_missing_frames.csv`. The reviewed shared manual ROI retains 19 images (14 from Vial 19, 3 from Vial 20, and 2 from Vial 21); 33 available images without visible liquid in that region or after the vial moved are documented in `recipe_11_excluded_frames.csv`.

Run the analysis with:

```bash
PYTHONPATH=src python -m vialsense.recipes.recipe11_manual \
  --labels data/raw/recipe7/labels_video5_frame_labels.csv \
  --images data/raw/recipe11/images \
  --output-dir results/recipe_11
```

The preliminary per-vial means are:

| Vial | Samples | Mean RGB | Mean HSV (OpenCV) |
|---|---:|---|---|
| 19 | 14 | (17.86, 28.22, 26.23) | (84.95, 102.35, 28.56) |
| 20 | 3 | (43.79, 43.48, 22.05) | (29.75, 128.57, 44.24) |
| 21 | 2 | (59.90, 63.43, 47.40) | (38.17, 77.79, 63.43) |

The measured regions vary visibly: Vial 19 appears darker and greener/teal, while the few retained images from Vials 20 and 21 appear brighter and more olive/yellow. The label CSV does not provide a color-purpose description. Vials 20 and 21 have only three and two measurements, respectively, so their means are especially tentative. The ROI is close to the vial base and support, where glass and reflections can affect pixel values; the images do not establish why the samples differ and do not show that contamination occurred. These measurements are preliminary, not validated color references or thresholds.

### Preliminary Results: Recipe 12

The label CSV describes Recipe 12 as a 70 ml triple mixture (10 ml T100, 50 ml T200, and 10 ml T400; dispense order `T200>T400>T100`). The uploaded ZIP contains 65 images: 21 for Vial 22, 22 for Vial 23, and 22 for Vial 24. All filenames match the Recipe 12 in-fill labels, with no missing images or extra files from another recipe. All images were readable at 640×480. Visual review of the shared manual ROI retained 15 images: 2 from Vial 22, 6 from Vial 23, and 7 from Vial 24. The other 50 frames and their exclusion notes are in `results/recipe_12/recipe_12_excluded_frames.csv`.

Run the analysis with:

```bash
PYTHONPATH=src python -m vialsense.recipes.recipe12_manual \
  --labels data/raw/recipe7/labels_video5_frame_labels.csv \
  --images data/raw/recipe12/images \
  --output-dir results/recipe_12
```

The preliminary per-vial means are:

| Vial | Samples | Mean RGB | Mean HSV (OpenCV) |
|---|---:|---|---|
| 22 | 2 | (31.10, 33.82, 20.38) | (36.56, 98.84, 33.82) |
| 23 | 6 | (24.33, 38.96, 27.12) | (65.41, 102.23, 38.96) |
| 24 | 7 | (14.26, 27.15, 26.82) | (89.50, 125.42, 27.40) |

The selected regions look olive/yellow-green in Vial 22, greener in Vial 23, and more cyan/teal in Vial 24. Vial 22 has only two retained frames, so its mean is especially uncertain. Fill stage, illumination, liquid motion, reflections, and the vial glass can affect these pixels; the measurements do not establish why the vials differ or indicate contamination. They remain preliminary and are not validated color references or thresholds.

### Preliminary Results: Recipe 13

The label CSV describes Recipe 13 as a 70 ml pair of T200 (50 ml) and T400 (20 ml), dispensed in `T200>T400` order. The ZIP contains all 55 labeled images: 19 from Vial 25, 18 from Vial 26, and 18 from Vial 27. There are no missing or extra filenames, and all images decode at 640×480. Visual review of the shared manual ROI retained 42 images: 10 from Vial 25, all 18 from Vial 26, and 14 from Vial 27. The other 13 frames and their exclusion notes are in `results/recipe_13/recipe_13_excluded_frames.csv`.

Run the analysis with:

```bash
PYTHONPATH=src python -m vialsense.recipes.recipe13_manual \
  --labels data/raw/recipe7/labels_video5_frame_labels.csv \
  --images data/raw/recipe13/images \
  --output-dir results/recipe_13
```

The preliminary per-vial means are:

| Vial | Samples | Mean RGB | Mean HSV (OpenCV) |
|---|---:|---|---|
| 25 | 10 | (12.62, 27.74, 27.25) | (89.28, 142.24, 27.96) |
| 26 | 18 | (14.21, 24.64, 21.96) | (82.28, 109.57, 24.65) |
| 27 | 14 | (38.62, 24.37, 16.49) | (10.33, 144.88, 38.62) |

Vials 25 and 26 look dark teal/green in the selected regions. Vial 27 looks orange/brown and has a much higher red channel, an unusual difference for samples with the same recipe label. The images do not establish why they differ or indicate contamination. Lighting, fill stage, liquid motion, reflections, glass, and the small samples can affect the measurements. Results are preliminary, not validated reference colors or thresholds.

All recipe commands accept path overrides. Run a command with `--help` to see the options. Outputs are saved in their recipe-specific result folders by default.

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
