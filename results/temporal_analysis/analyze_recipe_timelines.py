#!/usr/bin/env python3
"""Build descriptive timelines from existing VialSense measurements and labels.

No image pixels are re-measured. Unmeasured frames remain blank and are tagged
from the existing exclusion/missing lists, or explicitly marked unclassified.
Recipe 8 is read only and included in the consolidated comparison.
"""
from __future__ import annotations

from pathlib import Path
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "temporal_analysis"
LABELS = ROOT / "data/raw/recipe7/labels_video5_frame_labels.csv"
RECIPES = [5, 6, 7, 9, 10, 11, 12, 13, 14]
CHANNELS = ["r_mean", "g_mean", "b_mean", "h_mean_opencv", "s_mean_opencv", "v_mean_opencv"]


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def source_measurement_path(recipe: int) -> Path:
    d = ROOT / f"results/recipe_{recipe}"
    options = [d / f"recipe_{recipe}_manual_roi_measurements.csv",
               d / f"recipe_{recipe}_preliminary_measurements.csv"]
    for p in options:
        if p.exists():
            return p
    raise FileNotFoundError(f"No measurement CSV for Recipe {recipe}: {options}")


def clean_names(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["filename"] = df.filename.astype(str).map(lambda x: Path(x.replace("\\", "/")).name)
    return df


def summarize_vial(rows: pd.DataFrame, recipe: int, vial: int) -> dict:
    m = rows[rows.status == "measured"].sort_values("video_s")
    result = {"recipe_id": recipe, "vial": vial,
              "labeled_in_fill_frames": len(rows), "measured_frames": len(m),
              "excluded_frames": int((rows.status == "excluded_roi").sum()),
              "missing_images": int((rows.status == "missing_image").sum()),
              "unclassified_unmeasured": int((rows.status == "unclassified_unmeasured").sum()),
              "fill_label_start_video_s": rows.video_s.min() if len(rows) else np.nan,
              "fill_label_end_video_s": rows.video_s.max() if len(rows) else np.nan,
              "labeled_duration_s": rows.video_s.max() - rows.video_s.min() if len(rows) else np.nan,
              "measured_start_elapsed_s": m.elapsed_fill_s.min() if len(m) else np.nan,
              "measured_end_elapsed_s": m.elapsed_fill_s.max() if len(m) else np.nan,
              "measurement_coverage_pct": 100 * len(m) / len(rows) if len(rows) else np.nan}
    for c in CHANNELS:
        x = pd.to_numeric(m[c], errors="coerce").dropna() if c in m else pd.Series(dtype=float)
        result[f"{c}_mean"] = x.mean() if len(x) else np.nan
        result[f"{c}_range"] = x.max() - x.min() if len(x) else np.nan
        result[f"{c}_first_to_last_delta"] = (x.iloc[-1] - x.iloc[0]) if len(x) > 1 else np.nan
    if len(m) > 1:
        rgb = m[["r_mean", "g_mean", "b_mean"]].to_numpy(float)
        result["median_adjacent_rgb_distance"] = float(np.median(np.linalg.norm(np.diff(rgb, axis=0), axis=1)))
        n = max(1, len(m) // 2)
        first = m.iloc[:n][["r_mean", "g_mean", "b_mean"]].mean().to_numpy(float)
        last = m.iloc[-n:][["r_mean", "g_mean", "b_mean"]].mean().to_numpy(float)
        result["first_vs_last_half_rgb_distance"] = float(np.linalg.norm(last - first))
    else:
        result["median_adjacent_rgb_distance"] = np.nan
        result["first_vs_last_half_rgb_distance"] = np.nan
    return result


def plot_channels(timeline: pd.DataFrame, recipe: int, names: list[int],
                  cols: list[str], labels: list[str], out_path: Path) -> None:
    fig, axes = plt.subplots(len(cols), 1, figsize=(10, 2.35 * len(cols)), sharex=True)
    colors = plt.get_cmap("tab10")
    for ax, col, label in zip(axes, cols, labels):
        for i, vial in enumerate(names):
            all_vial = timeline[timeline.vial == vial].sort_values("video_s")
            d = all_vial[all_vial.status == "measured"]
            if len(d):
                # Draw lines only between adjacent labeled frames; leave a visible
                # gap whenever excluded/missing labels interrupt measurement.
                groups = d.groupby(d.frame_index_in_vial.diff().fillna(1).ne(1).cumsum())
                for j, (_, part) in enumerate(groups):
                    ax.plot(part.elapsed_fill_s, part[col], marker="o", ms=3.5, lw=1.1,
                            color=colors(i % 10), label=f"Vial {vial}" if j == 0 else None)
        ax.set_ylabel(label)
        ax.grid(alpha=.25)
    axes[-1].set_xlabel("Seconds since first frame labeled in_fill=1 for this vial")
    if any((timeline.status == "measured").any() for _ in [0]):
        axes[0].legend(ncol=min(3, max(1, len(names))), fontsize=8)
    fig.suptitle(f"Recipe {recipe}: existing measured color over labeled fill time")
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def plot_coverage(timeline: pd.DataFrame, recipe: int, names: list[int], out_path: Path) -> None:
    yvals = {"measured": 3, "excluded_roi": 2, "missing_image": 1, "unclassified_unmeasured": 0}
    colors = {"measured": "#238b45", "excluded_roi": "#de8f05", "missing_image": "#c43c39", "unclassified_unmeasured": "#777777"}
    fig, ax = plt.subplots(figsize=(10, max(2.5, .65 * len(names))))
    for y, vial in enumerate(names):
        d = timeline[timeline.vial == vial]
        for status, yy in yvals.items():
            s = d[d.status == status]
            if len(s):
                ax.scatter(s.elapsed_fill_s, np.full(len(s), y), marker="|", s=110, linewidths=2.2,
                           color=colors[status], label=status.replace("_", " "))
    handles, labs = ax.get_legend_handles_labels()
    by = dict(zip(labs, handles))
    ax.legend(by.values(), by.keys(), ncol=4, fontsize=8, loc="upper center", bbox_to_anchor=(.5, 1.22))
    ax.set_yticks(range(len(names)), [f"Vial {v}" for v in names])
    ax.set_xlabel("Seconds since first frame labeled in_fill=1 for this vial")
    ax.set_title(f"Recipe {recipe}: measurement coverage across labeled frames")
    ax.grid(axis="x", alpha=.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def concise_findings(summary: pd.DataFrame) -> str:
    lines = []
    for _, r in summary.iterrows():
        v = int(r.vial)
        n = int(r.measured_frames)
        if n == 0:
            lines.append(f"- Vial {v}: no retained color measurements; timeline coverage is unavailable.")
            continue
        coverage = f"{n}/{int(r.labeled_in_fill_frames)} frames ({r.measurement_coverage_pct:.1f}%)"
        if n < 3:
            lines.append(f"- Vial {v}: {coverage}; too few samples to describe a time trend reliably.")
            continue
        rgb_delta = r.first_vs_last_half_rgb_distance
        adj = r.median_adjacent_rgb_distance
        lines.append(f"- Vial {v}: {coverage}; first-half vs last-half mean RGB distance {rgb_delta:.1f}; median adjacent RGB step {adj:.1f}. These describe recorded ROI variation, not a process threshold.")
    return "\n".join(lines)


def recipe_comparison(summary: pd.DataFrame) -> str:
    usable = summary[summary.measured_frames > 0].copy()
    if usable.empty:
        return "No vial has an existing color measurement."
    usable["first_vs_last_half_rgb_distance"] = pd.to_numeric(usable.first_vs_last_half_rgb_distance, errors="coerce")
    usable["median_adjacent_rgb_distance"] = pd.to_numeric(usable.median_adjacent_rgb_distance, errors="coerce")
    enough = usable[usable.measured_frames >= 3]
    parts = []
    if len(enough):
        highest = enough.loc[enough.first_vs_last_half_rgb_distance.idxmax()]
        lowest = enough.loc[enough.first_vs_last_half_rgb_distance.idxmin()]
        parts.append(f"Among vials with at least three measurements, Vial {int(highest.vial)} has the largest first-half/last-half mean RGB separation ({highest.first_vs_last_half_rgb_distance:.1f}); Vial {int(lowest.vial)} has the smallest ({lowest.first_vs_last_half_rgb_distance:.1f}). This is a descriptive time comparison, not a validated definition of a color change.")
        most_step = enough.loc[enough.median_adjacent_rgb_distance.idxmin()]
        parts.append(f"Vial {int(most_step.vial)} has the smallest median step between adjacent measured RGB samples ({most_step.median_adjacent_rgb_distance:.1f}), so its retained measurements are comparatively close together over time. This does not show what happened in gaps between retained frames.")
    vial_rgb = usable[["vial", "r_mean_mean", "g_mean_mean", "b_mean_mean"]].dropna()
    if len(vial_rgb) > 1:
        pair_dist = []
        vals = vial_rgb.set_index("vial")[["r_mean_mean", "g_mean_mean", "b_mean_mean"]]
        for i, va in enumerate(vals.index):
            for vb in vals.index[i+1:]:
                pair_dist.append((np.linalg.norm(vals.loc[va].to_numpy(float) - vals.loc[vb].to_numpy(float)), int(va), int(vb)))
        dist, va, vb = max(pair_dist)
        parts.append(f"The farthest pair of measured per-vial mean RGB values is Vials {va} and {vb} (distance {dist:.1f}). Differences can reflect ROI, illumination, fill stage, or the product itself; the data do not determine which explanation applies.")
    return "\n\n".join(parts)


def run_recipe(recipe: int, labels_all: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    dest = OUT / f"recipe_{recipe}"
    dest.mkdir(parents=True, exist_ok=True)
    labels = labels_all[(labels_all.recipe_id == recipe) & (labels_all.in_fill == 1)].copy()
    if labels.empty:
        raise ValueError(f"No in_fill labels for Recipe {recipe}")
    mpath = source_measurement_path(recipe)
    measured = clean_names(read_csv(mpath))
    measured = measured.drop_duplicates("filename", keep="last")
    d = ROOT / f"results/recipe_{recipe}"
    excluded_path = d / f"recipe_{recipe}_excluded_frames.csv"
    missing_path = d / f"recipe_{recipe}_missing_frames.csv"
    excluded = clean_names(read_csv(excluded_path))
    missing = clean_names(read_csv(missing_path))
    labels = clean_names(labels)
    label_names = set(labels.filename)
    measured_names = set(measured.filename)
    excluded_names = set(excluded.filename) if "filename" in excluded else set()
    missing_names = set(missing.filename) if "filename" in missing else set()
    outside = (measured_names | excluded_names | missing_names) - label_names
    if outside:
        raise ValueError(f"Recipe {recipe}: source filenames absent from the labels: {sorted(outside)[:5]}")
    if measured_names & excluded_names or measured_names & missing_names or excluded_names & missing_names:
        raise ValueError(f"Recipe {recipe}: measurement/excluded/missing source lists overlap")
    cols = ["filename", "timestamp", "video_s", "in_fill", "vial", "recipe_id", "type", "t100_ml", "t200_ml", "t400_ml", "total_ml", "dispense_order", "color_purpose"]
    cols = [c for c in cols if c in labels.columns]
    timeline = labels[cols].copy()
    timeline["vial"] = pd.to_numeric(timeline.vial, errors="coerce").astype("Int64")
    timeline["video_s"] = pd.to_numeric(timeline.video_s, errors="coerce")
    timeline["recipe_id"] = pd.to_numeric(timeline.recipe_id, errors="coerce").astype("Int64")
    start = timeline.groupby("vial").video_s.transform("min")
    timeline["elapsed_fill_s"] = timeline.video_s - start
    timeline["frame_index_in_vial"] = timeline.groupby("vial").cumcount()
    timeline["status"] = "unclassified_unmeasured"
    ex_names = excluded_names
    miss_names = missing_names
    timeline.loc[timeline.filename.isin(ex_names), "status"] = "excluded_roi"
    timeline.loc[timeline.filename.isin(miss_names), "status"] = "missing_image"
    mcols = [c for c in CHANNELS + ["measurement_status", "measurement_note", "roi_x1", "roi_y1", "roi_x2", "roi_y2"] if c in measured]
    m = measured[["filename"] + mcols].copy()
    timeline = timeline.merge(m, on="filename", how="left", validate="one_to_one")
    if "reason" in excluded:
        timeline = timeline.merge(excluded[["filename", "reason"]].rename(columns={"reason": "exclusion_reason"}), on="filename", how="left", validate="one_to_one")
    if "status" in missing:
        timeline = timeline.merge(missing[["filename", "status"]].rename(columns={"status": "missing_status"}), on="filename", how="left", validate="one_to_one")
    timeline.loc[timeline[CHANNELS].notna().any(axis=1), "status"] = "measured"
    # Preserve original timestamps and labels; color columns remain blank when not measured.
    timeline = timeline.sort_values(["vial", "video_s"]).reset_index(drop=True)
    timeline.to_csv(dest / f"recipe_{recipe}_labeled_timeline.csv", index=False)
    vials = sorted(int(x) for x in timeline.vial.dropna().unique())
    summaries = pd.DataFrame([summarize_vial(timeline[timeline.vial == v], recipe, v) for v in vials])
    summaries.to_csv(dest / f"recipe_{recipe}_vial_summary.csv", index=False)
    plot_channels(timeline, recipe, vials, CHANNELS[:3], ["Red mean (0–255)", "Green mean (0–255)", "Blue mean (0–255)"], dest / f"recipe_{recipe}_rgb_over_fill_time.png")
    plot_channels(timeline, recipe, vials, CHANNELS[3:], ["Hue (OpenCV 0–179)", "Saturation (0–255)", "Value (0–255)"], dest / f"recipe_{recipe}_hsv_over_fill_time.png")
    plot_coverage(timeline, recipe, vials, dest / f"recipe_{recipe}_frame_coverage.png")
    statuses = timeline.status.value_counts().to_dict()
    expected = len(timeline)
    report = f"""# Recipe {recipe} labeled temporal analysis

## Source and method

This analysis joins the existing preliminary ROI measurement CSV to the original
video5 frame labels by exact image filename. It does not inspect or re-measure
image pixels. Each vial's time axis starts at its earliest frame labeled
`in_fill=1`; it is elapsed time from that **label**, not a verified instant of
liquid dispensing. All {expected} labeled in-fill frames are retained in the
timeline. No color value is filled in for an excluded, missing, or unclassified
frame.

Measurement source: `{mpath.relative_to(ROOT)}`  
Labels: `data/raw/recipe7/labels_video5_frame_labels.csv`  
Frames: {statuses.get('measured', 0)} measured; {statuses.get('excluded_roi', 0)} explicitly excluded by prior ROI review; {statuses.get('missing_image', 0)} listed missing; {statuses.get('unclassified_unmeasured', 0)} have no matching measurement/exclusion/missing record. Coverage is {statuses.get('measured', 0)}/{expected} ({100*statuses.get('measured', 0)/expected:.1f}%).

## Per-vial observations

{concise_findings(summaries)}

## Time and vial comparison

{recipe_comparison(summaries)}

The summary CSV provides means, ranges, first-to-last changes, and descriptive
within-sequence changes for all RGB and OpenCV HSV channels. Large changes only
describe the measured ROI values. They do not establish contamination, recipe
failure, or cause.

## Outputs

- `recipe_{recipe}_labeled_timeline.csv`: every labeled in-fill frame with original timestamp, vial-relative elapsed seconds, status, and existing color measurements where available.
- `recipe_{recipe}_vial_summary.csv`: coverage and descriptive per-vial statistics.
- `recipe_{recipe}_rgb_over_fill_time.png` and `recipe_{recipe}_hsv_over_fill_time.png`: existing measurements plotted against label-derived fill time; gaps are left unconnected.
- `recipe_{recipe}_frame_coverage.png`: measured, excluded, missing, and unclassified frames along the label timeline.

## Limitations

`in_fill` is a binary label, not a liquid-level or dispense-phase annotation.
The first in-fill frame may occur after filling has begun. Frames were sampled
sparsely and unevenly. The measurements retain the prior ROI choices, including
their sensitivity to vial movement, lighting, reflections, glass, and support.
The CSV's exclusion reasons describe why the old analysis withheld a frame;
they are not a pixel-level new review. Recipes with low coverage or few points
cannot support strong statements about stable periods or trends. Results are
preliminary observations and are not validated references or thresholds.
"""
    (dest / "README.md").write_text(report, encoding="utf-8")
    return timeline, summaries


def include_recipe8(summary_rows: list[dict]) -> None:
    # Read only the latest already-produced Recipe 8 timeline. Do not rewrite it.
    p = OUT / "recipe_8_original_image_review/recipe_8_temporal_measurements_updated.csv"
    d = clean_names(read_csv(p))
    if d.empty:
        p = OUT / "recipe_8_fill_timeline/recipe_8_labeled_fill_timeline.csv"
        d = clean_names(read_csv(p))
    if d.empty:
        raise FileNotFoundError("Recipe 8 temporal analysis CSV is unavailable")
    d["status"] = d.get("measurement_status", pd.Series(index=d.index, dtype=str)).fillna("unclassified_unmeasured")
    d.loc[d.status.astype(str).str.contains("exclude", case=False), "status"] = "excluded_roi"
    d.loc[d[CHANNELS].notna().any(axis=1), "status"] = "measured"
    elapsed_col = next((c for c in ["elapsed_since_first_labeled_in_fill_s", "seconds_since_first_labeled_in_fill_frame", "elapsed_s"] if c in d), None)
    d["elapsed_fill_s"] = pd.to_numeric(d[elapsed_col], errors="coerce") if elapsed_col else np.nan
    for vial, rows in d.groupby("vial"):
        # Reuse the same metrics while mapping Recipe 8's existing labeled timeline.
        if "video_s" not in rows:
            continue
        summary_rows.append(summarize_vial(rows, 8, int(vial)))


def main() -> None:
    (OUT / "consolidated").mkdir(parents=True, exist_ok=True)
    labels = clean_names(pd.read_csv(LABELS))
    labels["recipe_id"] = pd.to_numeric(labels.recipe_id, errors="coerce")
    labels["in_fill"] = pd.to_numeric(labels.in_fill, errors="coerce").fillna(0).astype(int)
    all_summaries: list[pd.DataFrame] = []
    consolidated_rows: list[dict] = []
    availability = []
    for recipe in RECIPES:
        measurement = source_measurement_path(recipe)
        d = ROOT / f"results/recipe_{recipe}"
        label_count = int(((labels.recipe_id == recipe) & (labels.in_fill == 1)).sum())
        m = clean_names(read_csv(measurement))
        e = clean_names(read_csv(d / f"recipe_{recipe}_excluded_frames.csv"))
        miss = clean_names(read_csv(d / f"recipe_{recipe}_missing_frames.csv"))
        availability.append({"recipe_id": recipe, "label_frames": label_count,
                             "measurement_rows": len(m), "excluded_rows": len(e),
                             "missing_rows": len(miss), "measurement_csv": str(measurement.relative_to(ROOT)),
                             "measurement_filenames_match_labels": set(m.filename).issubset(set(labels[(labels.recipe_id == recipe) & (labels.in_fill == 1)].filename)),
                             "excluded_csv_present": (d / f"recipe_{recipe}_excluded_frames.csv").exists(),
                             "missing_csv_present": (d / f"recipe_{recipe}_missing_frames.csv").exists()})
        _, s = run_recipe(recipe, labels)
        all_summaries.append(s)
        consolidated_rows.extend(s.to_dict("records"))
    include_recipe8(consolidated_rows)
    pd.DataFrame(availability).to_csv(OUT / "consolidated/input_availability.csv", index=False)
    summary = pd.concat(all_summaries, ignore_index=True)
    by_recipe = summary.groupby("recipe_id", as_index=False).agg(
        labeled_in_fill_frames=("labeled_in_fill_frames", "sum"), measured_frames=("measured_frames", "sum"),
        excluded_frames=("excluded_frames", "sum"), missing_images=("missing_images", "sum"),
        unclassified_unmeasured=("unclassified_unmeasured", "sum"),
        mean_vial_coverage_pct=("measurement_coverage_pct", "mean"))
    # Recipe 8 is included using its existing per-vial results above.
    r8 = pd.DataFrame([r for r in consolidated_rows if int(r["recipe_id"]) == 8])
    if len(r8):
        summary = pd.concat([summary, r8], ignore_index=True)
        r8sum = r8.groupby("recipe_id", as_index=False).agg(
            labeled_in_fill_frames=("labeled_in_fill_frames", "sum"), measured_frames=("measured_frames", "sum"),
            excluded_frames=("excluded_frames", "sum"), missing_images=("missing_images", "sum"),
            unclassified_unmeasured=("unclassified_unmeasured", "sum"), mean_vial_coverage_pct=("measurement_coverage_pct", "mean"))
        by_recipe = pd.concat([by_recipe, r8sum], ignore_index=True).sort_values("recipe_id")
    summary.to_csv(OUT / "consolidated/temporal_summary_recipes_5_14.csv", index=False)
    by_recipe.to_csv(OUT / "consolidated/recipe_coverage_comparison.csv", index=False)
    lines = ["# Consolidated temporal comparison: Recipes 5–14", "",
             "This report combines the nine new label-derived analyses with Recipe 8's existing updated temporal results. Recipe 8 files were read only. All color values are pre-existing ROI measurements; no omitted frame was assigned a value.", "",
             "## Coverage", "",
             "See `recipe_coverage_comparison.csv` for frame totals and coverage. Recipe-level totals are summed across each recipe's vials; the mean-vial coverage column is an unweighted average across vials.", "",
             "## Patterns and data quality", "",
             "- Recipes 9 and 13 have comparatively strong measurement coverage across all three vials (59/70 and 42/55 frames respectively). Recipe 9's measurements were previously described as the most consistent cross-vial color cluster, but that is a descriptive comparison of these ROIs.",
             "- Recipes 5, 6, 7, 10, 11, 12, and 14 have sparse or uneven per-vial coverage. In particular, Recipe 14 has no measurements for Vial 28; Recipe 11 has 10 frames documented as missing from the uploaded image set; Recipe 6 has no exclusion ledger, so its unmeasured labels are marked unclassified.",
             "- Previously observed cross-vial color differences include Recipe 6 (Vial 6 brighter/oranger than 4–5), Recipe 7 (Vials 7–8 orange/brown while Vial 9 has only one blue measurement), Recipe 11 (Vial 19 differs from lightly sampled 20–21), Recipe 12 (strongly differing sparse vial samples), Recipe 13 (Vial 27 differs from 25–26), and Recipe 14 (Vial 30 brighter than 29; Vial 28 unmeasured). These are recorded ROI differences and do not identify a cause.",
             "- Recipe 8's existing review noted mostly blue samples, with a late turquoise shift in Vial 12. The updated analysis adds one cautious moving-vial sample for Vial 10 and retains 30 excluded frames; this comparison uses those already-published results without editing them.",
             "- Sparse frames, unequal sampling windows, fixed/manual ROI effects, motion, illumination, glass and reflections can all produce apparent change. The binary `in_fill` label does not give fill height, liquid volume, dispense phase, or true physical start/end. No recipe has validated normal limits or an outcome label proving contamination.",
             "", "## Reusable analysis", "",
             "Run from the repository root with the project environment: `python results/temporal_analysis/analyze_recipe_timelines.py`. It regenerates folders for Recipes 5, 6, 7, 9, 10, 11, 12, 13, and 14, plus consolidated CSVs. Recipe 8 is only read for the combined comparison.", "",
             "Each recipe folder contains its full labeled timeline, per-vial descriptive summary, RGB and HSV plots, frame-coverage plot, and README. Color columns are blank for frames without an existing measurement."]
    lines.extend(["", "## Recipe-by-recipe temporal observations", ""])
    for r in [5, 6, 7, 8, 9, 10, 11, 12, 13, 14]:
        rs = summary[summary.recipe_id == r]
        if r == 8:
            lines.append("- **Recipe 8:** existing analysis describes Vials 10–11 as broadly blue across their short measured spans; Vial 12 shifts toward turquoise in its last three samples around 20–24 seconds. Vial 10 has only four samples including the cautious moving-vial ROI, and 30 frames remain excluded.")
        else:
            lines.append(f"- **Recipe {r}:** {recipe_comparison(rs).replace(chr(10), ' ')}")
    (OUT / "consolidated/README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Generated {len(RECIPES)} new recipe timelines and consolidated comparison in {OUT}")


if __name__ == "__main__":
    main()
