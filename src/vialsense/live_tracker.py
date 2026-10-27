"""Follow vials through the fill station and score each one live.

No machine signals are used. The tracker works out timing from the camera,
and the recipe from a queue the operator types in before the run.

Timing rules, measured on Dataset 2 video 5 (all 30 vials found):
- A vial ARRIVES when a holder block appears at the fill position.
- A vial LEAVES when the holder is gone for ARRIVAL_GAP_S or longer. The
  conveyor swaps vials in about 0.67 s. Brief detection blips inside one
  vial last about 0.13 s, so a 0.4 s rule separates the two.
- FILL START (live estimate): the liquid column reaches MIN_FILL_PX for
  START_CONFIRM samples in a row, and RISE_PX above the empty vial's
  baseline. Empty vials often show a thin 6-17 px strip (residue, reflection). Usually 0.5 to 4 s after the dispense
  starts, later for pale liquids.
- FILL END: about END_LAG_S before the vial leaves (2.0 +/- 1.0 s on video 5).

Two progress estimates:
- live: seconds since the detected fill start / expected fill seconds.
  Used for the running on-screen score.
- final: anchored on the departure, which is the more reliable signal.
  Used for the vial's verdict.

Recipe source: the operator's queue. Each arriving vial takes the next recipe.
The tracker never guesses the recipe from the vial's color, since a check
that adjusts its expectation to what it sees would pass any contaminated vial.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

ARRIVAL_GAP_S = 0.4
MIN_DWELL_S = 3.0
MIN_FILL_PX = 10
START_CONFIRM = 3
SETTLE_S = 3.0          # first seconds after arrival: measure the empty vial's baseline
RISE_PX = 8             # liquid must rise this far above the empty baseline
END_LAG_S = 2.0
FLAG_SHARE = 0.5
MIN_SCORED = 3


def parse_queue(text: str) -> list[int]:
    """'7,7,7,8,8,8' or '7x3, 8x3' -> [7, 7, 7, 8, 8, 8]."""
    out: list[int] = []
    for part in text.replace(";", ",").replace(" ", "").split(","):
        if not part:
            continue
        if "x" in part.lower():
            recipe, count = part.lower().split("x", 1)
            out.extend([int(recipe)] * int(count))
        else:
            out.append(int(part))
    if not out:
        raise ValueError("Recipe queue is empty")
    return out


@dataclass
class VialRecord:
    number: int                      # 1, 2, 3 ... in order of arrival
    recipe_id: int | None            # from the operator queue; None when the queue ran out
    previous_recipe: int | None      # recipe of the vial before, for the carryover check
    arrived_s: float
    expected_fill_s: float
    readings: list[dict[str, Any]] = field(default_factory=list)
    fill_start_s: float | None = None
    left_s: float | None = None
    verdict: str = "FILLING"         # FILLING, PASS, FLAG, NO DATA, NO RECIPE
    flagged_share: float | None = None
    scored_frames: int = 0
    median_score: float | None = None
    explanation: str = ""
    _run: int = 0
    _run_start: float = 0.0
    _settle_heights: list = field(default_factory=list)
    _baseline: float | None = None

    @property
    def recipe_change(self) -> bool:
        return (self.recipe_id is not None and self.previous_recipe is not None
                and self.recipe_id != self.previous_recipe)

    def live_progress(self, t: float) -> float | None:
        if self.fill_start_s is None:
            return None
        return float(np.clip((t - self.fill_start_s) / self.expected_fill_s, 0.0, 1.0))

    def summary(self) -> dict[str, Any]:
        return {
            "vial": self.number, "recipe_id": self.recipe_id, "previous_recipe": self.previous_recipe,
            "recipe_change": self.recipe_change, "arrived_s": round(self.arrived_s, 2),
            "fill_start_detected_s": None if self.fill_start_s is None else round(self.fill_start_s, 2),
            "left_s": None if self.left_s is None else round(self.left_s, 2),
            "est_fill_start_s": None if self.left_s is None else round(self.left_s - END_LAG_S - self.expected_fill_s, 2),
            "est_fill_end_s": None if self.left_s is None else round(self.left_s - END_LAG_S, 2),
            "scored_frames": self.scored_frames,
            "flagged_share": None if self.flagged_share is None else round(self.flagged_share, 3),
            "median_score": None if self.median_score is None else round(self.median_score, 1),
            "verdict": self.verdict, "explanation": self.explanation,
        }


class VialTracker:
    """Feed it (time, detection) pairs. It reports arrivals, live scores, and verdicts.

    score_fn(reading, recipe_id, progress) -> dict with 'anomaly_score' and 'status'
    (Eduardo's score_salah_reading with the model bound in).
    fill_seconds: expected fill duration per recipe; default_fill_s when missing.
    """

    def __init__(self, queue: list[int], score_fn: Callable[[dict, int, float], dict],
                 fill_seconds: dict[int, float], default_fill_s: float = 35.0,
                 previous_recipe: int | None = None):
        self.queue = list(queue)
        self.position = 0
        self.score_fn = score_fn
        self.fill_seconds = fill_seconds
        self.default_fill_s = default_fill_s
        self.last_recipe = previous_recipe
        self.current: VialRecord | None = None
        self.finished: list[VialRecord] = []
        self.last_seen_s: float | None = None
        self.events: list[str] = []

    # ---- operator controls -------------------------------------------------
    def skip(self) -> None:
        """Operator: a vial went by unseen. Move the queue forward one."""
        if self.position < len(self.queue):
            self.position += 1
            self.events.append(f"Operator skipped queue to position {self.position + 1}")

    def back(self) -> None:
        """Operator: a vial was counted twice. Move the queue back one."""
        if self.position > 0:
            self.position -= 1
            self.events.append(f"Operator moved queue back to position {self.position + 1}")

    @property
    def next_recipe(self) -> int | None:
        return self.queue[self.position] if self.position < len(self.queue) else None

    # ---- main loop ---------------------------------------------------------
    def update(self, t: float, detection: dict[str, Any]) -> dict[str, Any]:
        """Process one frame. Returns what to show for this frame."""
        present = bool(detection.get("found_vial"))
        if present:
            if self.current is None:
                self._arrive(t)
            self.last_seen_s = t
        elif self.current is not None and self.last_seen_s is not None and t - self.last_seen_s >= ARRIVAL_GAP_S:
            self._leave()

        frame_view: dict[str, Any] = {"t": t, "vial": None, "recipe_id": None, "state": "WAITING",
                                      "progress": None, "anomaly_score": None, "status": None}
        vial = self.current
        if vial is None or not present:
            if vial is not None:
                frame_view.update(vial=vial.number, recipe_id=vial.recipe_id, state="VIAL BLINK")
            return frame_view

        reading = dict(detection)
        reading["t"] = t
        self._update_fill_start(vial, t, detection)
        progress = vial.live_progress(t)
        reading["live_progress"] = progress
        state = "WAITING FOR FILL" if progress is None else "FILLING"
        score = None
        if progress is not None and vial.recipe_id is not None:
            score = self.score_fn(detection, vial.recipe_id, progress)
            reading["live_score"] = score.get("anomaly_score")
            reading["live_status"] = score.get("status")
        vial.readings.append(reading)
        frame_view.update(vial=vial.number, recipe_id=vial.recipe_id, state=state, progress=progress,
                          anomaly_score=None if score is None else score.get("anomaly_score"),
                          status=None if score is None else score.get("status"))
        return frame_view

    def finish(self) -> None:
        """End of stream: close the vial in progress."""
        if self.current is not None:
            self._leave()

    # ---- internals ---------------------------------------------------------
    def _arrive(self, t: float) -> None:
        recipe = self.next_recipe
        if recipe is not None:
            self.position += 1
        number = len(self.finished) + 1
        expected = self.fill_seconds.get(recipe, self.default_fill_s) if recipe is not None else self.default_fill_s
        self.current = VialRecord(number, recipe, self.last_recipe, t, float(expected))
        if recipe is None:
            self.events.append(f"Vial {number} arrived: recipe queue is empty, color only")
        elif self.current.recipe_change:
            self.events.append(f"Vial {number} arrived: Recipe {self.last_recipe} -> {recipe}. "
                               f"Carryover risk on this vial")
        else:
            self.events.append(f"Vial {number} arrived: Recipe {recipe}")

    def _update_fill_start(self, vial: VialRecord, t: float, detection: dict[str, Any]) -> None:
        if vial.fill_start_s is not None:
            return
        height = float(detection.get("liquid_height_px") or 0) if detection.get("found_liquid") else 0.0
        if t - vial.arrived_s < SETTLE_S:
            vial._settle_heights.append(height)   # empty vial: residue or reflection at the bottom
            return
        if vial._baseline is None:
            vial._baseline = float(np.median(vial._settle_heights)) if vial._settle_heights else 0.0
        tall = height >= max(MIN_FILL_PX, vial._baseline + RISE_PX)
        if tall:
            vial._run += 1
            if vial._run == 1:
                vial._run_start = t
            if vial._run >= START_CONFIRM:
                vial.fill_start_s = vial._run_start
        else:
            vial._run = 0

    def _leave(self) -> None:
        vial = self.current
        assert vial is not None and self.last_seen_s is not None
        self.current = None
        vial.left_s = self.last_seen_s
        if vial.left_s - vial.arrived_s < MIN_DWELL_S:
            # Too short to be a real vial (a hand, a flicker). Give the recipe back.
            if vial.recipe_id is not None:
                self.position -= 1
            self.events.append(f"Ignored a {vial.left_s - vial.arrived_s:.1f} s detection")
            return
        self._decide(vial)
        self.finished.append(vial)
        if vial.recipe_id is not None:
            self.last_recipe = vial.recipe_id
        self.events.append(f"Vial {vial.number} done: {vial.verdict}"
                           + (f". {vial.explanation}" if vial.explanation else ""))

    def final_progress(self, vial: VialRecord, t: float) -> float | None:
        end = vial.left_s - END_LAG_S  # type: ignore[operator]
        start = end - vial.expected_fill_s
        if t < start or t > end:
            return None
        return float((t - start) / vial.expected_fill_s)

    def _decide(self, vial: VialRecord) -> None:
        if vial.recipe_id is None:
            vial.verdict, vial.explanation = "NO RECIPE", "Recipe queue was empty; color recorded only"
            return
        own, prev = [], []
        for r in vial.readings:
            progress = self.final_progress(vial, r["t"])
            if progress is None or not r.get("found_liquid") or r.get("confidence") != "high":
                continue
            result = self.score_fn(r, vial.recipe_id, progress)
            if result.get("anomaly_score") is None:
                continue
            own.append((result["anomaly_score"], result["status"] == "review_unusual"))
            if vial.previous_recipe is not None and vial.previous_recipe != vial.recipe_id:
                other = self.score_fn(r, vial.previous_recipe, progress)
                if other.get("anomaly_score") is not None:
                    prev.append(other["anomaly_score"])
        vial.scored_frames = len(own)
        if len(own) < MIN_SCORED:
            vial.verdict = "NO DATA"
            vial.explanation = ("Too few clear readings to judge "
                                "(pale liquid, short column, or no reference for this fill stage)")
            return
        scores = np.array([s for s, _ in own], dtype=float)
        vial.flagged_share = float(np.mean([f for _, f in own]))
        vial.median_score = float(np.median(scores))
        vial.verdict = "FLAG" if vial.flagged_share > FLAG_SHARE else "PASS"
        vial.explanation = explain(vial, float(np.median(prev)) if prev else None)


def explain(vial: VialRecord, previous_score: float | None) -> str:
    """Why a vial was flagged, using the recipe that ran before it."""
    if vial.verdict == "PASS":
        if vial.recipe_change:
            return f"First vial after Recipe {vial.previous_recipe} -> {vial.recipe_id}. No carryover seen"
        return ""
    if vial.verdict != "FLAG":
        return vial.explanation
    if vial.previous_recipe is None:
        return "Color off for this recipe. Previous recipe unknown (first vial of the run)"
    if vial.previous_recipe == vial.recipe_id:
        return (f"Color off, but the vial before also ran Recipe {vial.recipe_id}, so this is not "
                "recipe-change carryover. Check lighting, the vial, or the dispensed volume")
    if previous_score is not None and previous_score < (vial.median_score or np.inf):
        return (f"Likely carryover from Recipe {vial.previous_recipe}: color sits closer to Recipe "
                f"{vial.previous_recipe} (score {previous_score:.0f}) than to Recipe {vial.recipe_id} "
                f"(score {vial.median_score:.0f}). First vial after a recipe change")
    return (f"Possible carryover: first vial after Recipe {vial.previous_recipe} -> {vial.recipe_id}. "
            f"Color is off but does not match Recipe {vial.previous_recipe} either; "
            "leftover may have mixed with the new liquid")
