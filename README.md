# Vial Color Check

Flags vials whose liquid color does not match the recipe. Catches fluid carryover between runs before a bad sample moves down the line.

Built for the Rockwell and NVIDIA Physical AI Hackathon, Fall 2026.

## How It Works

1. The camera captures an image of the vial.
2. The script crops the region that holds the liquid.
3. It measures the average color of that region.
4. It compares that color to the expected color for the recipe.
5. If the difference passes the threshold, it flags the vial as a mismatch.

## Folder Structure

```
color_check/
├── README.md
├── [main_script].py      # Runs the color check
├── [config_file]         # Recipe colors and threshold
└── [samples]/            # Test images
```

## Requirements

- Python [version]
- OpenCV
- NumPy
- [other libraries]

Install them:

```
pip install -r requirements.txt
```

## Usage

Run the check on a single image:

```
python [main_script].py --image [path/to/image.jpg] --recipe [recipe_name]
```

Run it on a live camera feed:

```
python [main_script].py --camera 0 --recipe [recipe_name]
```

## Configuration

Set each recipe's expected color and the mismatch threshold in `[config_file]`.

| Setting | Meaning |
|---|---|
| recipe color | Expected liquid color for each recipe |
| threshold | How far the measured color drifts before a flag |

## Output

- PASS: the liquid color matches the recipe.
- FAIL: the liquid color does not match. The vial needs review.

## Status

Work in progress on the `color-check` branch. Next step: connect with the `color-analysis` code.

## Author

Salah ([Salahalrayess1](https://github.com/Salahalrayess1))
