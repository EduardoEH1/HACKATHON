"""Live mode: camera -> liquid finder -> recipe queue -> anomaly score -> verdict.

1. Calibrate once per camera setup (vial under the nozzle):
    PYTHONPATH=src python -m vialsense.live_cli calibrate --camera 0

2. Run with the recipe queue the machine will execute, in order:
    PYTHONPATH=src python -m vialsense.live_cli run --camera 0 --recipes "7x3,8x3"

Replay a recorded video as if it were live (for testing and demos):
    PYTHONPATH=src python -m vialsense.live_cli run \
        --video data/raw/dataset2/vial_fill/videos/vial_fill_video_5.mp4 \
        --recipes "5x3,6x3,7x3,8x3,9x3,10x3,11x3,12x3,13x3,14x3" --realtime

Keys in the window: q quit, p pause, n skip one recipe in the queue (a vial
went by unseen), b step the queue back (a vial was counted twice).
"""

from __future__ import annotations

import argparse
import json
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from .anomaly import load_model
from .corrected_pipeline import score_salah_reading
from .liquid_finder import draw, find_liquid
from .live_calibration import Calibration, calibrate, calibration_preview, prepare
from .live_tracker import VialTracker, parse_queue

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "results/corrected/phase2/provisional_model.json"
FILL_TABLE = ROOT / "inputs/color_check/video5_vial_recipes.csv"
CALIBRATION = ROOT / "results/live/calibration.json"

VERDICT_COLORS = {"PASS": (60, 200, 60), "FLAG": (40, 40, 230), "NO DATA": (0, 180, 255),
                  "NO RECIPE": (0, 180, 255), "FILLING": (230, 230, 230)}


# --------------------------------------------------------------------------- sources
class FrameSource:
    """Camera index, stream URL, or video file. Yields (time_s, frame)."""

    def __init__(self, camera: int | None, stream: str | None, video: Path | None,
                 fps: float, realtime: bool, start_s: float = 0.0, max_s: float | None = None):
        self.is_file = video is not None
        target = str(video) if video else (stream if stream else camera)
        self.cap = cv2.VideoCapture(target)
        if not self.cap.isOpened():
            raise SystemExit(f"Cannot open source: {target}. For cameras, try --camera 1 or 2.")
        if camera is not None:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.fps = fps
        self.realtime = realtime
        self.max_s = max_s
        self.video_fps = self.cap.get(cv2.CAP_PROP_FPS) if self.is_file else None
        if self.is_file and start_s > 0:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, int(start_s * self.video_fps))
        self.start_s = start_s

    def __iter__(self):
        if self.is_file:
            step = max(1, int(round(self.video_fps / self.fps)))
            index = int(round(self.start_s * self.video_fps))
            wall0 = time.monotonic()
            while True:
                ok, frame = self.cap.read()
                if not ok:
                    return
                t = index / self.video_fps
                if self.max_s is not None and t - self.start_s > self.max_s:
                    return
                if self.realtime:
                    delay = (t - self.start_s) - (time.monotonic() - wall0)
                    if delay > 0:
                        time.sleep(delay)
                yield t, frame
                for _ in range(step - 1):
                    if not self.cap.grab():
                        return
                index += step
        else:
            t0 = time.monotonic()
            next_t = 0.0
            while True:
                ok, frame = self.cap.read()
                if not ok:
                    raise SystemExit("Camera stopped sending frames")
                t = time.monotonic() - t0
                if self.max_s is not None and t > self.max_s:
                    return
                if t >= next_t:
                    next_t = t + 1.0 / self.fps
                    yield t, frame

    def first_frame(self) -> np.ndarray:
        for _ in range(5):          # cameras often send dark frames first
            ok, frame = self.cap.read()
        if not ok:
            raise SystemExit("Could not read a frame from the source")
        return frame

    def release(self) -> None:
        self.cap.release()


def open_window(name: str) -> bool:
    import os
    import sys
    # Linux servers (Brev, judges' machines) have no screen; OpenCV's GUI aborts there.
    if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        print("No display found. Running without a window (use --record to save the screen as video).")
        return False
    try:
        cv2.namedWindow(name, cv2.WINDOW_NORMAL)
        return True
    except cv2.error:
        print("No window available (opencv-python-headless is installed). Running without a window.\n"
              "For the live window: pip uninstall -y opencv-python-headless && pip install opencv-python")
        return False


# --------------------------------------------------------------------------- display
def render(frame: np.ndarray, detection, view: dict, tracker: VialTracker, events: deque) -> np.ndarray:
    top = draw(frame, detection, " ")
    w = top.shape[1]
    cv2.rectangle(top, (0, 0), (w, 30), (0, 0, 0), -1)
    if view["vial"] is None:
        head = f"WAITING FOR VIAL   next recipe: {tracker.next_recipe if tracker.next_recipe is not None else 'queue empty'}"
    else:
        progress = "" if view["progress"] is None else f"  fill {view['progress'] * 100:.0f}%"
        score = "" if view["anomaly_score"] is None else f"  score {view['anomaly_score']:.0f}"
        head = f"Vial {view['vial']}  Recipe {view['recipe_id']}  {view['state']}{progress}{score}"
    color = (40, 40, 230) if view.get("status") == "review_unusual" else (255, 255, 255)
    cv2.putText(top, head, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.58, color, 1)

    panel = np.zeros((150, w, 3), np.uint8)
    y = 24
    if tracker.finished:
        last = tracker.finished[-1]
        text = f"Last: Vial {last.number}  Recipe {last.recipe_id}  {last.verdict}"
        if last.median_score is not None:
            text += f"  (score {last.median_score:.0f}, {last.flagged_share * 100:.0f}% frames flagged)"
        cv2.putText(panel, text, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, VERDICT_COLORS.get(last.verdict, (255, 255, 255)), 2)
        y += 22
        for line in wrap(last.explanation, 78)[:2]:
            cv2.putText(panel, line, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)
            y += 18
    y = max(y, 88)
    for line in list(events)[-2:]:
        cv2.putText(panel, wrap(line, 84)[0], (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 200, 255), 1)
        y += 18
    upcoming = tracker.queue[tracker.position:tracker.position + 12]
    cv2.putText(panel, "Queue: " + (" ".join(map(str, upcoming)) if upcoming else "empty"),
                (8, 142), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (160, 160, 160), 1)
    return cv2.vconcat([top, panel])


def wrap(text: str, width: int) -> list[str]:
    words, lines, line = text.split(), [], ""
    for word in words:
        if len(line) + len(word) + 1 > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(line)
    return lines or [""]


# --------------------------------------------------------------------------- commands
def fill_seconds_table(path: Path) -> dict[int, float]:
    table = pd.read_csv(path)
    return table.groupby("recipe_id").duration_s.mean().round(2).to_dict()


def run(args) -> dict:
    model = load_model(args.model)
    queue = parse_queue(Path(args.recipes_file).read_text() if args.recipes_file else args.recipes)
    calibration = None
    if args.calibration and Path(args.calibration).is_file():
        calibration = Calibration.load(Path(args.calibration))
        print(f"Using calibration {args.calibration}: scale {calibration.scale}, "
              f"shift ({calibration.shift_x}, {calibration.shift_y})")
    elif args.camera is not None or args.stream:
        print("No calibration file. Frames are only resized to 640x480. "
              "Run 'calibrate' first if the camera view differs from Dataset 2.")

    def score_fn(reading: dict, recipe_id: int, progress: float) -> dict:
        return score_salah_reading(model, reading, recipe_id=recipe_id, fill_progress=progress)

    tracker = VialTracker(queue, score_fn, fill_seconds_table(args.fill_table),
                          default_fill_s=args.default_fill_s, previous_recipe=args.previous_recipe)
    source = FrameSource(args.camera, args.stream, args.video, args.fps, args.realtime, args.start_s, args.max_seconds)
    out_dir = args.output_dir or ROOT / "results/live" / datetime.now().strftime("run_%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    window = "VialSense live" if (not args.no_window and open_window("VialSense live")) else None
    writer = None
    events: deque = deque(maxlen=6)
    frame_rows = []
    seen_events = 0
    paused = False
    try:
        for t, raw in source:
            frame = prepare(raw, calibration)
            detection = find_liquid(frame)
            view = tracker.update(t, detection.to_dict())
            for event in tracker.events[seen_events:]:
                stamp = f"[{t:7.1f}s] {event}"
                events.append(stamp)
                print(stamp, flush=True)
            seen_events = len(tracker.events)
            frame_rows.append({**{k: v for k, v in view.items()},
                               "found_vial": detection.found_vial, "found_liquid": detection.found_liquid,
                               "confidence": detection.confidence, "liquid_height_px": detection.liquid_height_px,
                               "r_mean": detection.r_mean, "g_mean": detection.g_mean, "b_mean": detection.b_mean})
            if window or args.record:
                screen = render(frame, detection, view, tracker, events)
                if args.record:
                    if writer is None:
                        writer = cv2.VideoWriter(str(args.record), cv2.VideoWriter_fourcc(*"mp4v"),
                                                 args.fps, (screen.shape[1], screen.shape[0]))
                    writer.write(screen)
                if window:
                    cv2.imshow(window, screen)
                    key = cv2.waitKey(1) & 0xFF
                    while True:
                        if key == ord("q"):
                            raise KeyboardInterrupt
                        if key == ord("n"):
                            tracker.skip()
                        if key == ord("b"):
                            tracker.back()
                        if key == ord("p"):
                            paused = not paused
                        if not paused:
                            break
                        key = cv2.waitKey(50) & 0xFF
    except KeyboardInterrupt:
        print("Stopped by operator")
    finally:
        tracker.finish()
        for event in tracker.events[seen_events:]:
            print(event)
        source.release()
        if writer is not None:
            writer.release()
        if window:
            cv2.destroyAllWindows()

    vials = pd.DataFrame([v.summary() for v in tracker.finished])
    vials.to_csv(out_dir / "vials.csv", index=False)
    pd.DataFrame(frame_rows).to_csv(out_dir / "frames.csv", index=False)
    (out_dir / "events.log").write_text("\n".join(tracker.events) + "\n", encoding="utf-8")
    summary = {
        "vials": len(vials),
        "verdicts": vials.verdict.value_counts().to_dict() if len(vials) else {},
        "queue_used": tracker.position, "queue_length": len(queue),
        "calibration": None if calibration is None else str(args.calibration),
        "status": "provisional; not validated contamination detection",
    }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    print(f"Saved to {out_dir}")
    return summary


def do_calibrate(args) -> None:
    source = FrameSource(args.camera, args.stream, args.video, 5, False, args.start_s)
    frame = source.first_frame()
    source.release()
    calibration = calibrate(frame, tuple(args.holder) if args.holder else None)
    calibration.save(args.output)
    preview = args.output.with_suffix(".jpg")
    cv2.imwrite(str(preview), calibration_preview(frame, calibration))
    check = find_liquid(prepare(frame, calibration))
    print(json.dumps({"calibration": str(args.output), "scale": calibration.scale,
                      "shift": [calibration.shift_x, calibration.shift_y],
                      "camera_size": calibration.source_size, "holder_found": calibration.holder,
                      "finder_after_calibration": {"found_vial": check.found_vial,
                                                   "found_liquid": check.found_liquid,
                                                   "reason": check.reason}}, indent=2))
    print(f"Check the preview before running: {preview}")
    if not check.found_vial:
        print("WARNING: the finder still does not see the vial. Look at the preview, then pass "
              "--holder CENTER_X BOTTOM_Y WIDTH for the holder under the nozzle.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    def add_source(p):
        group = p.add_mutually_exclusive_group(required=True)
        group.add_argument("--camera", type=int, help="camera index: 0, 1, 2...")
        group.add_argument("--stream", help="camera stream URL (RTSP or HTTP)")
        group.add_argument("--video", type=Path, help="video file, replayed as live")
        p.add_argument("--start-s", type=float, default=0.0, help="video only: start at this second")

    cal = commands.add_parser("calibrate", help="map this camera's view onto the finder's reference view")
    add_source(cal)
    cal.add_argument("--holder", type=float, nargs=3, metavar=("CENTER_X", "BOTTOM_Y", "WIDTH"),
                     help="holder block under the nozzle, in the 640x480-resized frame")
    cal.add_argument("--output", type=Path, default=CALIBRATION)

    live = commands.add_parser("run", help="run live mode")
    add_source(live)
    queue = live.add_mutually_exclusive_group(required=True)
    queue.add_argument("--recipes", help='recipe queue in run order, e.g. "7,7,7,8,8,8" or "7x3,8x3"')
    queue.add_argument("--recipes-file", help="text file holding the same")
    live.add_argument("--previous-recipe", type=int, help="recipe that ran just before this run")
    live.add_argument("--calibration", default=str(CALIBRATION))
    live.add_argument("--fps", type=float, default=5.0, help="frames analysed per second")
    live.add_argument("--realtime", action="store_true", help="video only: play at real speed")
    live.add_argument("--max-seconds", type=float)
    live.add_argument("--model", type=Path, default=MODEL)
    live.add_argument("--fill-table", type=Path, default=FILL_TABLE,
                      help="CSV with recipe_id and duration_s; expected fill time per recipe")
    live.add_argument("--default-fill-s", type=float, default=35.0)
    live.add_argument("--no-window", action="store_true")
    live.add_argument("--record", type=Path, help="save the annotated screen as an MP4")
    live.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.command == "calibrate":
        do_calibrate(args)
    else:
        if args.realtime and args.video is None:
            parser.error("--realtime is for --video")
        run(args)


if __name__ == "__main__":
    main()
