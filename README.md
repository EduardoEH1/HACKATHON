# VialSense

VialSense is a Python prototype designed to measure the visible liquid color in `vial_fill` images using OpenCV, NumPy, and pandas. This first version only covers labeled samples from Recipe 6, Vials 4, 5, and 6.

## Available Data and Labels

The original Dataset 2 README explains that `vial_fill/labels/video5_frame_labels.csv` links each sampled image to its corresponding `vial`, `recipe_id`, and `in_fill` values. Video 5 contains the only recipe labels, covering Recipes 5 through 14. Recipe 6 was selected for the initial analysis, although the script can be adapted to another individual recipe.

The original dataset files are not included in this GitHub-ready project. The results CSV contains the image filenames and the labels used during the analysis. To reproduce the measurements, `video5_frame_labels.csv` and the original `vial_fill` images must be placed in the following locations:

```
data/raw/vial_fill/images/
data/raw/vial_fill/labels_video5_frame_labels.csv
```

The results and annotated examples included in `outputs/` are small derived files. ZIP archives, videos, and complete collections of original images are not included.

## Environment Setup

Open this project folder in VS Code and select the `.venv/bin/python` interpreter. Then run the following commands in the terminal:

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
```

### Preliminary Results: Recipe 6

The current sample contains 5 images from Vial 4, 5 from Vial 5, and 8 from Vial 6. Each region of interest (ROI) was individually reviewed at an enlarged scale, with the red boxes positioned over visible liquid near the bottom of each vial.

Run:

```bash
PYTHONPATH=src python -m vialsense.analyze_recipe6_manual
```

The script requires the image and label files in the locations specified above. The label CSV connects each frame to its corresponding recipe and vial, while the script processes a fixed selection of Recipe 6 samples. It measures the average RGB and HSV values within a manually selected ROI. It does not perform automatic vial detection, contamination detection, or threshold classification.

Running the script generates `outputs/recipe_6_preliminary_measurements.csv`, 18 annotated images under `outputs/recipe_6_roi_examples/`, image montages for each vial, and descriptive CSV summaries for individual vials and the combined samples.

The manually selected rectangle is defined by `(x1=304, y1=384, x2=328, y2=400)` for 640×480 camera images. Measurements are calculated as direct averages of RGB and HSV values using all pixels inside the rectangle. OpenCV represents H on a scale of 0–179 and S/V on a scale of 0–255.

The ROI is intentionally small to avoid the cap, label, background, and vial support. However, glass surfaces, reflections, low image resolution, lighting conditions, and filling stages can still affect the measured values.

The 18 frames are repeated samples from only three vials, which is not enough to statistically establish the normal color variation for the entire recipe.

The observed average RGB values were:

| Vial | Mean RGB |
|---|---|
| Vial 4 | (21.65, 26.18, 19.27) |
| Vial 5 | (35.80, 41.31, 28.61) |
| Vial 6 | (85.55, 60.99, 26.67) |

The observed average HSV values in OpenCV format were:

| Vial | Mean HSV |
|---|---|
| Vial 4 | (56.03, 70.74, 26.20) |
| Vial 5 | (45.87, 80.73, 41.31) |
| Vial 6 | (17.51, 176.37, 85.55) |

These differences are observations that require further investigation. They are not interpreted as evidence of either contamination or normal conditions. The combined summary is descriptive and should not be considered a validated reference color or an acceptance threshold.

Some blurry frames or images showing empty vials were excluded. Other images from Vial 5 were not selected because of the sampling limit, not because they failed an acceptance criterion.

For future integration, the `measure_roi` function accepts an image and ROI coordinates. Another system could replace the manually selected coordinates with a validated automatic detection method.

## Project Structure

```
src/vialsense/      Label loading, color measurement, and analysis commands
data/raw/           Expected local dataset location; excluded from Git
outputs/            Generated CSV results
requirements.txt    Python dependencies
```

### Separate preliminary exploration: Recipe 7

Recipe 7 inputs and outputs are kept separate from Recipe 6 under `data/raw/recipe7/` and `outputs/recipe_7/`. The manual analysis uses the same fixed ROI and the 36 label-matched frames. It retains frames where colored liquid is visible in the ROI: 8 samples from Vial 7, 8 from Vial 8, and 1 from Vial 9. The other 19 frames are listed in `recipe_7_excluded_frames.csv` with the visual reason for exclusion.

```bash
PYTHONPATH=src python -m vialsense.analyze_recipe7_manual \
  --labels data/raw/recipe7/labels_video5_frame_labels.csv \
  --images data/raw/recipe7/images \
  --output-dir outputs/recipe_7
```

These results are preliminary. The label description for Recipe 7 says “pale blue”, while the selected frames from Vials 7 and 8 look orange/brown and the single usable frame from Vial 9 looks blue. This visual difference is recorded without inferring its cause. One sample from Vial 9 cannot establish its color variation. Lighting, reflections, glass, and filling stage can affect all measurements. This is not a validated color reference or a contamination threshold.
