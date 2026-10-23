"""Check one vial photo: give it an image and a recipe number, get PASS or FLAG.

Example (from the repo root):
    PYTHONPATH=src python -m vialsense.check_vial \
        --image results/recipe_7/annotated_images/<file>.jpg --recipe 7

Optional:
    --roi 304 384 328 400     box to measure (x1 y1 x2 y2), default is Eduardo's box
    --threshold 8             score limit for PASS
    --save-preview out.jpg    save the photo with the box and verdict drawn on it
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from vialsense.build_references import DEFAULT_OUTPUT, load_references
from vialsense.colorcheck import DEFAULT_ROI, DEFAULT_THRESHOLD, check_color, load_image, measure_liquid


def check_image(image_path: Path, recipe_id: int, references: dict,
                roi=DEFAULT_ROI, threshold: float = DEFAULT_THRESHOLD):
    image = load_image(image_path)
    measured = measure_liquid(image, roi)
    result = check_color((measured["r"], measured["g"], measured["b"]), recipe_id, references, threshold)
    return image, measured, result


def save_preview(image, roi, result, output: Path) -> None:
    """Draw the measured box and the verdict on a copy of the photo."""
    x1, y1, x2, y2 = roi
    color = (0, 200, 0) if result.status == "PASS" else (0, 0, 255)  # BGR
    preview = image.copy()
    cv2.rectangle(preview, (x1, y1), (x2, y2), color, 2)
    cv2.rectangle(preview, (0, 0), (640, 34), (0, 0, 0), -1)
    cv2.putText(preview, f"Recipe {result.recipe_id}: {result.status}  score {result.delta_e:.1f}",
                (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output), preview)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--recipe", type=int, required=True)
    parser.add_argument("--roi", type=int, nargs=4, default=list(DEFAULT_ROI), metavar=("X1", "Y1", "X2", "Y2"))
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--references", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--save-preview", type=Path)
    args = parser.parse_args()

    roi = tuple(args.roi)
    image, _, result = check_image(args.image, args.recipe, load_references(args.references), roi, args.threshold)
    print(result.line(args.image.name))
    if args.save_preview:
        save_preview(image, roi, result, args.save_preview)
        print(f"Preview saved to {args.save_preview}")


if __name__ == "__main__":
    main()
