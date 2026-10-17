"""Load the documented video-5 labels and match them to vial-fill frames."""

from pathlib import Path

import pandas as pd


def load_labeled_frames(labels_csv: Path, images_dir: Path, recipe_id: int) -> pd.DataFrame:
    """Return labeled frame rows for one recipe, with validated image paths."""
    labels = pd.read_csv(labels_csv)
    required = {"filename", "in_fill", "vial", "recipe_id"}
    missing = required - set(labels.columns)
    if missing:
        raise ValueError(f"Label CSV is missing columns: {sorted(missing)}")

    selected = labels.loc[(labels["recipe_id"] == recipe_id) & (labels["in_fill"] == 1)].copy()
    if selected.empty:
        raise ValueError(f"No in-fill frames found for recipe {recipe_id}")
    selected["image_path"] = selected["filename"].map(lambda name: images_dir / name)
    missing_images = selected.loc[~selected["image_path"].map(Path.is_file), "filename"].tolist()
    if missing_images:
        raise FileNotFoundError(f"{len(missing_images)} labeled images are missing; first: {missing_images[0]}")
    return selected.reset_index(drop=True)
