from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import threading
import time
from collections import deque
from html import escape
from pathlib import Path

import av
import cv2
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_webrtc import VideoProcessorBase, webrtc_streamer

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

INPUT_DIR = ROOT / "inputs" / "color_check"
RESULT_DIR = ROOT / "results" / "corrected"
TIMELINE_DIR = RESULT_DIR / "phase1"
PREDICTIONS_PATH = RESULT_DIR / "phase2" / "frame_predictions.csv"
DEFAULT_MODEL_PATH = RESULT_DIR / "phase2" / "provisional_model.json"
TRAINED_MODEL_PATH = ROOT / "results" / "training_runs" / "active_model.json"
TRAINING_ROWS_PATH = ROOT / "results" / "training_runs" / "approved_training_rows.csv"
TRAINING_MANIFEST_PATH = ROOT / "results" / "training_runs" / "training_manifest.json"
MODEL_PATH = TRAINED_MODEL_PATH if TRAINED_MODEL_PATH.exists() else DEFAULT_MODEL_PATH
LABELS_PATH = INPUT_DIR / "video5_vial_recipes.csv"
DATA_PATH = INPUT_DIR / "frame_colors.csv"
CHANNELS = ("r_mean", "g_mean", "b_mean", "h_mean_opencv", "s_mean_opencv", "v_mean_opencv")

st.set_page_config(page_title="VialSense", page_icon="🧪", layout="wide")
st.markdown(
    """
    <style>
    .stApp { background:#f4f7fa; color:#183047; }
    [data-testid="stSidebar"] { background:#10263b; }
    [data-testid="stSidebar"] * { color:#edf5fa !important; }
    .hero { padding:1rem 1.35rem; border-radius:16px; color:white;
            background:linear-gradient(115deg,#102b46,#176b70); margin-bottom:.8rem; }
    .hero h1 { margin:0; font-size:1.8rem; }
    .hero p { margin:.3rem 0 0; opacity:.86; }
    .notice { background:#fff7df; border:1px solid #f3d477; padding:.72rem .9rem;
              border-radius:10px; color:#5b4712; margin:.4rem 0 .9rem; }
    .metric-card { background:#ffffff; border:2px solid #718096;
                   border-radius:12px; padding:.8rem .9rem; min-height:88px;
                   box-shadow:0 3px 10px rgba(16,43,70,.12); margin-bottom:.5rem; }
    .metric-card-label { color:#26384a !important; -webkit-text-fill-color:#26384a !important;
                         opacity:1 !important; font-size:.95rem; font-weight:700; line-height:1.25; }
    .metric-card-value { color:#102b46 !important; -webkit-text-fill-color:#102b46 !important;
                         opacity:1 !important; font-size:1.5rem; font-weight:800;
                         line-height:1.2; white-space:normal; overflow-wrap:anywhere; }
    section.main div[data-testid="stCaptionContainer"],
    section.main div[data-testid="stCaptionContainer"] * { color:#34465a !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_saved_data():
    timeline_files = sorted(TIMELINE_DIR.glob("recipe_*/timeline.csv"))
    if not timeline_files:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    timeline = pd.concat([pd.read_csv(path) for path in timeline_files], ignore_index=True)
    predictions = pd.read_csv(PREDICTIONS_PATH) if PREDICTIONS_PATH.exists() else pd.DataFrame()
    profiles_path = RESULT_DIR / "phase2" / "reference_stage_summary.csv"
    profiles = pd.read_csv(profiles_path) if profiles_path.exists() else pd.DataFrame()
    labels = pd.read_csv(LABELS_PATH) if LABELS_PATH.exists() else pd.DataFrame()
    color_data = pd.read_csv(DATA_PATH) if DATA_PATH.exists() else pd.DataFrame()
    if not predictions.empty:
        keys = ["filename", "recipe_id", "vial"]
        extra = [c for c in ("anomaly_score", "status", "split", "reference_vial_id",
                             "reference_status") if c in predictions]
        timeline = timeline.merge(predictions[keys + extra], on=keys, how="left")
    return timeline, predictions, profiles, labels, color_data


def fill_stage(progress: float) -> str:
    if progress < 1 / 3:
        return "Early fill"
    if progress < 2 / 3:
        return "Middle fill"
    return "Late fill"


def status_label(score, threshold: float) -> str:
    if pd.isna(score):
        return "Not scored"
    return "Review needed" if float(score) >= threshold else "Within reference"


def metric_card(label, value):
    """Render a high-contrast metric tile without Streamlit's pale label styling."""
    st.markdown(
        '<div class="metric-card">'
        '<div class="metric-card-label">{}</div>'
        '<div class="metric-card-value">{}</div>'
        '</div>'.format(escape(str(label)), escape(str(value))),
        unsafe_allow_html=True,
    )


def score_rows(rows: pd.DataFrame, threshold: float) -> pd.DataFrame:
    if rows.empty or not MODEL_PATH.exists():
        return rows
    from vialsense.anomaly import load_model
    from vialsense.corrected_pipeline import score_salah_reading

    model = load_model(MODEL_PATH)
    output = rows.copy()
    scores = []
    statuses = []
    for row in output.to_dict("records"):
        result = score_salah_reading(model, row)
        score = result.get("anomaly_score")
        scores.append(score)
        statuses.append(
            status_label(score, threshold)
            if result.get("status") in ("review_unusual", "within_provisional_pattern")
            else result.get("status", "Not scored")
        )
    output["anomaly_score"] = scores
    output["status"] = statuses
    return output


def prepare_training_rows(readings: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    from vialsense.anomaly import CHANNELS

    missing = sorted(set(CHANNELS) - set(readings.columns))
    if missing:
        raise ValueError("Training readings are missing color columns: " + ", ".join(missing))
    data = readings.copy()
    if "vial" not in data:
        raise ValueError("Training readings need a vial column.")

    window_columns = {"vial", "recipe_id", "start_s", "end_s", "duration_s"}
    if "video_s" in data and window_columns.issubset(labels.columns):
        windows = labels[list(window_columns)].copy()
        if windows.vial.duplicated().any():
            raise ValueError("Fill-window labels must contain only one row per vial.")
        for column in ("vial", "recipe_id", "start_s", "end_s", "duration_s"):
            windows[column] = pd.to_numeric(windows[column], errors="raise")
        data = data.drop(columns=["recipe_id", "fill_progress"], errors="ignore")
        data["video_s"] = pd.to_numeric(data["video_s"], errors="coerce")
        data = data.merge(windows, on="vial", how="inner", validate="many_to_one")
        data = data[
            data.video_s.between(data.start_s, data.end_s, inclusive="both")
            & data.duration_s.gt(0)
        ].copy()
        data["fill_progress"] = ((data.video_s - data.start_s) / data.duration_s).clip(lower=0.0, upper=1.0)
    elif {"recipe_id", "fill_progress"}.issubset(data.columns):
        data["recipe_id"] = pd.to_numeric(data.recipe_id, errors="coerce")
        data["fill_progress"] = pd.to_numeric(data.fill_progress, errors="coerce")
    else:
        raise ValueError(
            "Provide video_s plus vial fill-window labels, or include recipe_id and fill_progress in the training CSV."
        )

    data["vial"] = pd.to_numeric(data.vial, errors="coerce")
    for column in CHANNELS:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    usable = data[list(CHANNELS)].notna().all(axis=1)
    usable &= data[["recipe_id", "vial", "fill_progress"]].notna().all(axis=1)
    if "found_vial" in data:
        usable &= data.found_vial.astype(str).str.strip().str.lower().isin(("true", "1", "yes"))
    if "found_liquid" in data:
        usable &= data.found_liquid.astype(str).str.strip().str.lower().isin(("true", "1", "yes"))
    if "confidence" in data:
        usable &= data.confidence.astype(str).str.strip().str.lower().eq("high")
    if "phase" in data:
        usable &= data.phase.astype(str).str.lower().eq("fill")
    training = data.loc[usable, ["recipe_id", "vial", "fill_progress", *CHANNELS]].copy()
    training["recipe_id"] = training.recipe_id.astype(int)
    training["vial"] = training.vial.astype(int)
    if training.empty:
        raise ValueError("No usable high-confidence readings matched the labels.")
    return training


def color_chart(rows: pd.DataFrame, title: str = "Detected RGB") -> go.Figure:
    fig = go.Figure()
    for column, label, color in (
        ("r_mean", "Red", "#d1495b"),
        ("g_mean", "Green", "#27976b"),
        ("b_mean", "Blue", "#3973ac"),
    ):
        if column in rows and rows[column].notna().any():
            fig.add_trace(go.Scatter(
                x=rows.fill_progress, y=rows[column], mode="lines+markers", name=label,
                line={"color": color, "width": 2},
                customdata=rows[["filename"]].to_numpy() if "filename" in rows else None,
                hovertemplate="%{fullData.name}: %{y:.1f}<br>Fill: %{x:.0%}<extra></extra>",
            ))
    fig.add_vline(x=1 / 3, line_dash="dot", line_color="#aab6c2")
    fig.add_vline(x=2 / 3, line_dash="dot", line_color="#aab6c2")
    fig.update_layout(
        title=title, height=300, margin={"l": 8, "r": 8, "t": 45, "b": 12},
        paper_bgcolor="white", plot_bgcolor="white",
        xaxis={"title": "Current vial fill progress", "tickformat": ".0%", "range": [0, 1]},
        yaxis={"title": "RGB channel value", "range": [0, 255]},
        legend={"orientation": "h", "y": 1.12},
    )
    return fig


def anomaly_chart(rows: pd.DataFrame, threshold: float) -> go.Figure:
    fig = go.Figure()
    if not rows.empty and "anomaly_score" in rows:
        fig.add_trace(go.Scatter(
            x=rows.fill_progress, y=rows.anomaly_score, mode="lines+markers",
            name="Anomaly prediction", line={"color": "#7654a5", "width": 2},
            marker={"color": [
                "#e89b2c" if pd.notna(score) and float(score) >= threshold else "#7654a5"
                for score in rows.anomaly_score
            ]},
            hovertemplate="Score: %{y:.1f}<br>Fill: %{x:.0%}<extra></extra>",
        ))
    fig.add_hline(y=threshold, line_dash="dash", line_color="#e89b2c",
                  annotation_text="Review threshold")
    fig.add_vline(x=1 / 3, line_dash="dot", line_color="#aab6c2")
    fig.add_vline(x=2 / 3, line_dash="dot", line_color="#aab6c2")
    fig.update_layout(
        title="Anomaly prediction", height=300, margin={"l": 8, "r": 8, "t": 45, "b": 12},
        paper_bgcolor="white", plot_bgcolor="white",
        xaxis={"title": "Current vial fill progress", "tickformat": ".0%", "range": [0, 1]},
        yaxis={"title": "Relative score"},
    )
    return fig


class CameraProcessor(VideoProcessorBase):
    """Live camera detector with a small thread-safe stream of recent readings."""

    def __init__(self):
        self.lock = threading.Lock()
        self.context = {"recipe_id": 5, "vial": 1, "progress": 0.0,
                        "threshold": 100.0, "mode": "training"}
        self.latest = {}
        self.history = deque(maxlen=180)
        self.last_sample = 0.0

    def set_context(self, recipe_id: int, vial: int, progress: float,
                    threshold: float, mode: str):
        with self.lock:
            self.context = {"recipe_id": recipe_id, "vial": vial, "progress": progress,
                            "threshold": threshold, "mode": mode}

    def snapshot(self):
        with self.lock:
            return dict(self.latest), list(self.history)

    def recv(self, frame):
        from vialsense.liquid_finder import draw, find_liquid

        image = frame.to_ndarray(format="bgr24")
        detection = find_liquid(image)
        now = time.time()
        with self.lock:
            context = dict(self.context)
        reading = detection.to_dict()
        reading.update(
            timestamp=now, recipe_id=context["recipe_id"], vial=context["vial"],
            fill_progress=context["progress"], stage=fill_stage(context["progress"]),
        )
        if context["mode"] == "prediction":
            try:
                from vialsense.anomaly import load_model
                from vialsense.corrected_pipeline import score_salah_reading

                result = score_salah_reading(
                    load_model(MODEL_PATH), reading,
                    recipe_id=context["recipe_id"], fill_progress=context["progress"],
                    timestamp=time.strftime("%H:%M:%S", time.localtime(now)),
                )
                reading["anomaly_score"] = result.get("anomaly_score")
                reading["status"] = status_label(reading["anomaly_score"], context["threshold"])
            except Exception as exc:
                reading["anomaly_score"] = None
                reading["status"] = "Scoring unavailable: {}".format(exc)
        else:
            reading["status"] = "Data capture" if detection.found_liquid else "Waiting for liquid"

        with self.lock:
            self.latest = reading
            if now - self.last_sample >= 0.75:
                self.history.append(reading.copy())
                self.last_sample = now
        annotated = draw(image, detection)
        return av.VideoFrame.from_ndarray(annotated, format="bgr24")


def camera_panel(mode: str, recipe_id: int, vial: int, progress: float,
                 threshold: float, key: str):
    st.subheader("Camera stream")
    st.caption("Allow camera access in your browser. Detection updates as frames arrive.")
    ctx = webrtc_streamer(
        key=key,
        video_processor_factory=CameraProcessor,
        media_stream_constraints={"video": True, "audio": False},
        rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
    )
    if ctx.video_processor:
        ctx.video_processor.set_context(recipe_id, vial, progress, threshold, mode)
        processor = ctx.video_processor

        @st.fragment(run_every=1)
        def live_status():
            latest, history = processor.snapshot()
            if not latest:
                st.info("Waiting for the first camera frame.")
                return
            score = latest.get("anomaly_score")
            current_status = latest.get("status", "Not scored")
            a, b, c, d = st.columns(4)
            with a:
                metric_card("Prediction", current_status)
            with b:
                metric_card("Anomaly score", "{:.1f}".format(score) if pd.notna(score) else "—")
            with c:
                metric_card("Fill label", latest.get("stage", "—"))
            rgb = latest
            with d:
                metric_card(
                    "RGB detected",
                    "{:.0f}, {:.0f}, {:.0f}".format(
                        rgb.get("r_mean", 0), rgb.get("g_mean", 0), rgb.get("b_mean", 0)
                    ) if latest.get("found_liquid") else "No liquid",
                )
            if history:
                stream = pd.DataFrame(history)
                if "r_mean" not in stream:
                    stream["r_mean"] = None
                stream["fill_progress"] = stream.fill_progress.astype(float)
                plots = st.columns(2)
                with plots[0]:
                    st.plotly_chart(anomaly_chart(stream, threshold), use_container_width=True)
                with plots[1]:
                    st.plotly_chart(color_chart(stream), use_container_width=True)
                st.dataframe(
                    stream[["timestamp", "stage", "found_liquid", "confidence",
                            "r_mean", "g_mean", "b_mean", "anomaly_score", "status"]],
                    use_container_width=True, hide_index=True,
                )
                st.download_button(
                    "Download recent stream data",
                    stream.to_csv(index=False).encode("utf-8"),
                    file_name="vialsense_camera_stream.csv",
                    mime="text/csv",
                )

        live_status()


def video_frame_for_reading(video_path: Path, timestamp_s: float, reading=None):
    """Return the source frame for a measurement, outlining its measured color ROI."""
    cap = cv2.VideoCapture(str(video_path))
    try:
        if not cap.isOpened():
            return None
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        frame_index = max(0, int(round(float(timestamp_s) * fps))) if fps > 0 else 0
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = cap.read()
        if not ok:
            return None
        if reading is not None:
            names = ("roi_x1", "roi_y1", "roi_x2", "roi_y2")
            coords = [reading.get(name) for name in names]
            if all(value is not None and pd.notna(value) for value in coords):
                x1, y1, x2, y2 = (int(round(float(value))) for value in coords)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(frame, "Measured color ROI", (max(0, x1), max(20, y1 - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
        return frame
    finally:
        cap.release()


def render_saved_main(timeline: pd.DataFrame, threshold: float):
    recipes = sorted(int(x) for x in timeline.recipe_id.dropna().unique())
    c1, c2, c3 = st.columns([1, 1, 1.6])
    with c1:
        recipe = st.selectbox("Recipe", recipes, key="saved_recipe")
    recipe_rows = timeline[timeline.recipe_id.eq(recipe)]
    vials = sorted(int(x) for x in recipe_rows.vial.dropna().unique())
    with c2:
        vial = st.selectbox("Vial", vials, key="saved_vial")
    selected = recipe_rows[recipe_rows.vial.eq(vial)].sort_values("video_s").reset_index(drop=True)
    selected = score_rows(selected, threshold)
    with c3:
        index = st.slider("Played frame / status", 0, max(0, len(selected) - 1), 0,
                          key="saved_frame")
    row = selected.iloc[index]
    progress = float(row.fill_progress) if pd.notna(row.fill_progress) else 0.0
    stage = fill_stage(progress)
    score = row.get("anomaly_score", None)
    status = status_label(score, threshold) if pd.notna(score) else row.get("status", "Not scored")

    video_col, status_col = st.columns([1.25, 1])
    with video_col:
        st.subheader("Main · Frame currently selected")
        source_video = st.file_uploader(
            "Source video for this saved frame",
            type=["mp4", "mov", "avi", "mkv"],
            key="saved_frame_source_video",
        )
        if source_video is None:
            st.info(
                "The saved data contains measurements, not the original video. Upload its source "
                "video to show the frame at {:.1f}s.".format(float(row.video_s))
            )
        else:
            suffix = Path(source_video.name).suffix or ".mp4"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
                temp.write(source_video.getvalue())
                video_path = Path(temp.name)
            try:
                frame = video_frame_for_reading(video_path, float(row.video_s), row)
            finally:
                video_path.unlink(missing_ok=True)
            if frame is None:
                st.warning("Could not read the selected frame from this video.")
            else:
                st.image(frame, channels="BGR", use_container_width=True,
                         caption="Selected source frame · measured color area outlined in red when available")
        st.caption("Selected reading: {} · {:.1f}s".format(row.filename, float(row.video_s)))
    with status_col:
        st.subheader("Current vial status")
        a, b = st.columns(2)
        with a:
            metric_card("Anomaly prediction", status)
        with b:
            metric_card("Score", "{:.1f}".format(score) if pd.notna(score) else "—")
        a, b, c = st.columns(3)
        with a:
            metric_card("Label", stage)
        with b:
            metric_card("Fill progress", "{:.0%}".format(progress))
        with c:
            metric_card("Vial / recipe", "{} / {}".format(vial, recipe))
        st.caption("Frame: {} · confidence: {}".format(
            row.filename, row.get("confidence", "not recorded")
        ))

    rows = selected.copy()
    if "anomaly_score" in rows:
        rows["anomaly_score"] = pd.to_numeric(rows.anomaly_score, errors="coerce")
    p1, p2 = st.columns(2)
    with p1:
        st.plotly_chart(anomaly_chart(rows, threshold), use_container_width=True)
    with p2:
        st.plotly_chart(color_chart(rows), use_container_width=True)
    st.subheader("Current RGB reading")
    if all(pd.notna(row.get(c)) for c in ("r_mean", "g_mean", "b_mean")):
        r, g, b = st.columns(3)
        with r:
            metric_card("Red", "{:.1f}".format(row.r_mean))
        with g:
            metric_card("Green", "{:.1f}".format(row.g_mean))
        with b:
            metric_card("Blue", "{:.1f}".format(row.b_mean))
    else:
        st.info("This frame has no usable color reading.")
    st.dataframe(
        selected[["video_s", "fill_progress", "stage", "measurement_status",
                  "confidence", "r_mean", "g_mean", "b_mean", "anomaly_score", "status"]]
        .tail(12).sort_values("video_s", ascending=False),
        use_container_width=True, hide_index=True,
    )


def render_uploaded_video(uploaded, labels: pd.DataFrame, step_s: float, threshold: float):
    st.subheader("Main · Video replay")
    st.video(uploaded.getvalue())
    st.caption("The uploaded clip is played here. Choose a vial below to use its saved fill-window label.")
    if labels.empty or not {"vial", "recipe_id", "start_s", "end_s", "duration_s"}.issubset(labels.columns):
        st.error("Fill-window labels must contain vial, recipe_id, start_s, end_s, and duration_s.")
        return
    vial_options = labels[["vial", "recipe_id"]].drop_duplicates().sort_values(["recipe_id", "vial"])
    choices = ["Recipe {} · Vial {}".format(int(r.recipe_id), int(r.vial))
               for r in vial_options.itertuples(index=False)]
    choice = st.selectbox("Current vial label", choices)
    selected_map = vial_options.iloc[choices.index(choice)]
    window = labels[(labels.vial.eq(selected_map.vial))
                    & (labels.recipe_id.eq(selected_map.recipe_id))]
    selection_key = (
        hashlib.sha256(uploaded.getvalue()).hexdigest(),
        int(selected_map.recipe_id),
        int(selected_map.vial),
        float(window.iloc[0].start_s),
        float(window.iloc[0].end_s),
        float(step_s),
    )
    if st.session_state.get("uploaded_selection_key") != selection_key:
        st.session_state.pop("uploaded_results", None)
        st.session_state.pop("uploaded_preview_bgr", None)
        st.session_state["uploaded_selection_key"] = selection_key
    if st.button("Analyze selected fill window", type="primary"):
        try:
            from vialsense.integration import measure_video
            from vialsense.anomaly import load_model
            from vialsense.corrected_pipeline import score_salah_reading

            suffix = Path(uploaded.name).suffix or ".mp4"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
                temp.write(uploaded.getvalue())
                video_path = Path(temp.name)
            try:
                measurements = measure_video(video_path, step_s=step_s, windows=window)
                preview_bgr = None
                if not measurements.empty:
                    latest_measurement = measurements.iloc[-1]
                    preview_bgr = video_frame_for_reading(
                        video_path, float(latest_measurement.video_s), latest_measurement
                    )
            finally:
                video_path.unlink(missing_ok=True)
            model = load_model(MODEL_PATH)
            scored = []
            for item in measurements.to_dict("records"):
                result = score_salah_reading(model, item)
                item["anomaly_score"] = result.get("anomaly_score")
                item["status"] = status_label(item["anomaly_score"], threshold)
                item["stage"] = result.get("stage")
                scored.append(item)
            st.session_state["uploaded_results"] = pd.DataFrame(scored)
            st.session_state["uploaded_preview_bgr"] = preview_bgr
            st.success("Video sampled and scored using the selected recipe and fill window.")
        except Exception as exc:
            st.error("Could not analyze this video: {}".format(exc))
    result = st.session_state.get("uploaded_results", pd.DataFrame())
    if not result.empty:
        last = result.iloc[-1]
        preview_bgr = st.session_state.get("uploaded_preview_bgr")
        if preview_bgr is not None:
            st.subheader("Frame used for the latest prediction")
            st.image(preview_bgr, channels="BGR", use_container_width=True,
                     caption="Latest analyzed frame · measured color area outlined in red when available")
        else:
            st.info("The analyzed frame preview is unavailable for this clip.")
        a, b, c, d = st.columns(4)
        with a:
            metric_card("Prediction", last.status)
        with b:
            metric_card("Score", "{:.1f}".format(last.anomaly_score)
                        if pd.notna(last.anomaly_score) else "—")
        with c:
            metric_card("Fill label", last.get("stage", "—"))
        with d:
            metric_card("RGB", "{:.0f}, {:.0f}, {:.0f}".format(
                last.r_mean, last.g_mean, last.b_mean
            ) if pd.notna(last.r_mean) else "—")
        p1, p2 = st.columns(2)
        with p1:
            st.plotly_chart(anomaly_chart(result, threshold), use_container_width=True)
        with p2:
            st.plotly_chart(color_chart(result), use_container_width=True)
        st.dataframe(result, use_container_width=True, hide_index=True)
        st.download_button("Download analyzed readings", result.to_csv(index=False).encode("utf-8"),
                           file_name="vialsense_video_predictions.csv", mime="text/csv")


timeline, predictions, profiles, default_labels, default_colors = load_saved_data()

st.sidebar.markdown("## VialSense")
st.sidebar.caption("Video color monitoring")
page = st.sidebar.radio("View", ["Main", "Review queue", "Reference profiles"], index=0)
st.sidebar.markdown("---")
st.sidebar.markdown("### Configuration")
mode = st.sidebar.radio("Mode", ["Realtime Prediction", "Data Training"])
threshold = st.sidebar.slider("Review threshold", 50, 200, 100, 5)
step_s = st.sidebar.slider("Video sample step (seconds)", 0.5, 5.0, 1.0, 0.5)
st.sidebar.caption("Threshold changes the UI flag boundary; it does not retrain the model.")

if mode == "Realtime Prediction":
    source = st.sidebar.radio(
        "Video source", ["Saved folder data", "Upload / play video", "Camera stream"], index=0
    )
else:
    source = "Camera stream"

training_source = "Use folder defaults"
training_readings_upload = None
training_labels_upload = None
if mode == "Data Training":
    training_source = st.sidebar.radio(
        "Training files",
        ["Use folder defaults", "Upload training files"],
        index=0,
        key="training_source",
    )
    st.sidebar.caption("Defaults: frame_colors.csv + video5_vial_recipes.csv")
    if training_source == "Upload training files":
        training_readings_upload = st.sidebar.file_uploader(
            "Training readings CSV", type=["csv"], key="training_readings_upload"
        )
        training_labels_upload = st.sidebar.file_uploader(
            "Optional fill-window labels CSV", type=["csv"], key="training_labels_upload"
        )
    min_stage_samples = st.sidebar.number_input(
        "Minimum samples per stage", min_value=1, max_value=100, value=4, step=1
    )
    min_stage_vials = st.sidebar.number_input(
        "Minimum distinct vials per stage", min_value=1, max_value=30, value=2, step=1
    )
    min_distance = st.sidebar.slider(
        "Minimum reference distance (%)", min_value=1.0, max_value=25.0,
        value=2.0, step=0.5,
    )
else:
    min_stage_samples, min_stage_vials, min_distance = 4, 2, 2.0

st.sidebar.markdown("**Default data**")
st.sidebar.caption("inputs/color_check/frame_colors.csv")
st.sidebar.caption("Default fill labels: inputs/color_check/video5_vial_recipes.csv")
uploaded_video = None
custom_labels = None
if page == "Main" and mode == "Realtime Prediction" and source == "Upload / play video":
    uploaded_video = st.sidebar.file_uploader("Video file", type=["mp4", "avi", "mov", "mkv"])
    custom_labels = st.sidebar.file_uploader("Optional fill-window labels CSV", type=["csv"])
    st.sidebar.caption("No raw Video 5 clip is checked into the repository.")
if custom_labels is not None:
    try:
        labels = pd.read_csv(custom_labels)
    except Exception:
        labels = default_labels
else:
    labels = default_labels

st.markdown(
    '<div class="hero"><h1>VialSense</h1>'
    '<p>Main monitor · video, current vial status, and live color signals</p></div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="notice"><b>Prototype notice:</b> a review flag means a reading differs '
    'from a provisional reference. It does not confirm contamination.</div>',
    unsafe_allow_html=True,
)

if page == "Main":
    if mode == "Data Training":
        st.subheader("Data Training mode")
        st.caption(
            "Choose the folder defaults or upload readings and optional fill-window labels, "
            "then train a new provisional reference model."
        )
        if st.button("Train model", type="primary", key="train_model"):
            try:
                from vialsense.anomaly import fit_model, save_model
                from vialsense.anomaly_data import summarize_profiles

                if training_source == "Use folder defaults":
                    readings_bytes = DATA_PATH.read_bytes()
                    labels_bytes = LABELS_PATH.read_bytes()
                    readings = pd.read_csv(io.BytesIO(readings_bytes))
                    train_labels = pd.read_csv(io.BytesIO(labels_bytes))
                    source_name = "Repository defaults"
                else:
                    if training_readings_upload is None:
                        raise ValueError("Upload a training readings CSV first.")
                    readings_bytes = training_readings_upload.getvalue()
                    readings = pd.read_csv(io.BytesIO(readings_bytes))
                    if training_labels_upload is not None:
                        labels_bytes = training_labels_upload.getvalue()
                        train_labels = pd.read_csv(io.BytesIO(labels_bytes))
                    else:
                        labels_bytes = LABELS_PATH.read_bytes()
                        train_labels = pd.read_csv(io.BytesIO(labels_bytes))
                    source_name = training_readings_upload.name

                dataset_id = hashlib.sha256(readings_bytes + b"\0" + labels_bytes).hexdigest()
                new_rows = prepare_training_rows(readings, train_labels)
                new_rows["batch_id"] = dataset_id

                TRAINED_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
                if TRAINING_ROWS_PATH.exists():
                    accumulated = pd.read_csv(TRAINING_ROWS_PATH)
                else:
                    accumulated = pd.DataFrame()
                if TRAINING_MANIFEST_PATH.exists():
                    manifest = json.loads(TRAINING_MANIFEST_PATH.read_text(encoding="utf-8"))
                else:
                    manifest = {"dataset_ids": [], "sources": {}}

                if dataset_id not in manifest["dataset_ids"]:
                    training = pd.concat([accumulated, new_rows], ignore_index=True)
                    manifest["dataset_ids"].append(dataset_id)
                    manifest["sources"][dataset_id] = source_name
                else:
                    training = accumulated
                if training.empty:
                    raise ValueError("No accumulated training readings are available.")

                model = fit_model(
                    training,
                    min_stage_samples=int(min_stage_samples),
                    min_stage_vials=int(min_stage_vials),
                    min_distance_percent=float(min_distance),
                    review_score=float(threshold),
                )
                profile = summarize_profiles(model)
                if not profile.reference_available.any():
                    raise ValueError(
                        "No recipe stage has enough data for a reference. Add more usable readings or lower the stage requirements."
                    )
                model["training_source"] = "Cumulative uploaded and repository datasets"
                model["training_datasets"] = list(manifest["sources"].values())
                model["trained_measurements"] = int(len(training))
                save_model(model, TRAINED_MODEL_PATH)
                training.to_csv(TRAINING_ROWS_PATH, index=False)
                TRAINING_MANIFEST_PATH.write_text(
                    json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
                )
                st.session_state["last_training_summary"] = {
                    "source": source_name,
                    "rows": int(len(training)),
                    "datasets": len(manifest["dataset_ids"]),
                    "recipes": int(training.recipe_id.nunique()),
                    "available_stages": int(profile.reference_available.sum()),
                    "path": str(TRAINED_MODEL_PATH),
                }
                st.success("Training finished. The new model is now active for predictions.")
                st.rerun()
            except Exception as exc:
                st.error("Training could not be completed: {}".format(exc))

        summary = st.session_state.get("last_training_summary")
        if summary:
            st.success(
                "Active model rebuilt from {} dataset(s) · {:,} usable readings · {} recipes · "
                "{} recipe stages have enough reference data.".format(
                    summary.get("datasets", 1), summary["rows"], summary["recipes"],
                    summary["available_stages"],
                )
            )
            st.caption("Saved separately at {}".format(summary["path"]))
        st.markdown(
            "Training settings: **{} samples/stage**, **{} vial(s)/stage**, "
            "**{:.1f}% minimum distance**, **{:.0f} review score**.".format(
                int(min_stage_samples), int(min_stage_vials), float(min_distance),
                float(threshold),
            )
        )
        st.caption(
            "The model is saved separately from the checked-in provisional model. "
            "Training on these readings does not establish detector accuracy."
        )

        if timeline.empty:
            recipe_options, vial_options = [5], [1]
            chosen_recipe = st.sidebar.selectbox("Current recipe label", recipe_options)
        else:
            recipe_options = sorted(int(x) for x in timeline.recipe_id.dropna().unique())
            chosen_recipe = st.sidebar.selectbox("Current recipe label", recipe_options)
            vial_options = sorted(int(x) for x in timeline.loc[
                timeline.recipe_id.eq(chosen_recipe), "vial"
            ].dropna().unique())
        chosen_vial = st.sidebar.selectbox("Current vial label", vial_options)
        progress = st.sidebar.slider("Current fill progress", 0.0, 1.0, 0.0, 0.01)
        camera_panel("training", chosen_recipe, chosen_vial, progress, threshold, "training-camera")
    elif source == "Camera stream":
        st.subheader("Realtime Prediction mode")
        st.caption("Camera frames are analyzed live. Set the current process label in Configuration.")
        if timeline.empty:
            recipe_options, vial_options = [5], [1]
        else:
            recipe_options = sorted(int(x) for x in timeline.recipe_id.dropna().unique())
        chosen_recipe = st.sidebar.selectbox("Current recipe label", recipe_options)
        if timeline.empty:
            vial_options = [1]
        else:
            vial_options = sorted(int(x) for x in timeline.loc[
                timeline.recipe_id.eq(chosen_recipe), "vial"
            ].dropna().unique())
        chosen_vial = st.sidebar.selectbox("Current vial label", vial_options)
        progress = st.sidebar.slider("Current fill progress", 0.0, 1.0, 0.0, 0.01)
        camera_panel("prediction", chosen_recipe, chosen_vial, progress, threshold, "prediction-camera")
    elif source == "Upload / play video":
        if uploaded_video is None:
            st.info("Choose a video in Configuration. The default Video 5 measurements and labels remain loaded.")
            if not timeline.empty:
                render_saved_main(timeline, threshold)
        else:
            render_uploaded_video(uploaded_video, labels, step_s, threshold)
    else:
        st.subheader("Realtime Prediction mode · saved folder data")
        if timeline.empty:
            st.error("Saved corrected timelines were not found.")
        else:
            render_saved_main(timeline, threshold)

elif page == "Review queue":
    st.subheader("Review queue")
    if predictions.empty or "status" not in predictions:
        st.info("No saved prediction records are available.")
    else:
        queue = predictions[predictions.status.eq("review_unusual")].copy()
        recipes = sorted(int(x) for x in predictions.recipe_id.dropna().unique())
        chosen = st.multiselect("Recipes", recipes, default=recipes)
        queue = queue[queue.recipe_id.isin(chosen)]
        st.caption("{} saved readings are flagged for human review.".format(len(queue)))
        columns = [c for c in (
            "recipe_id", "vial", "video_s", "fill_progress", "stage", "anomaly_score",
            "confidence", "filename", "reference_vial_id", "reference_status",
        ) if c in queue]
        st.dataframe(queue[columns].sort_values(["recipe_id", "vial", "video_s"]),
                     use_container_width=True, hide_index=True)

else:
    st.subheader("Reference profiles")
    if profiles.empty:
        st.info("No reference profile summary is available.")
    else:
        recipe_options = sorted(int(x) for x in profiles.recipe_id.dropna().unique())
        recipe = st.selectbox("Recipe", recipe_options)
        view = profiles[profiles.recipe_id.eq(recipe)].copy()
        view["Stage coverage"] = view.reference_available.map(
            {True: "Available", False: "Not enough reference data"}
        )
        columns = [c for c in (
            "stage", "Stage coverage", "samples", "vials", "vial_ids",
            "reference_vial_id", "reference_status", "reference_limit_percent",
        ) if c in view]
        st.dataframe(view[columns], use_container_width=True, hide_index=True)
        st.caption("Reference vials are provisional and have not been confirmed normal.")

st.markdown("---")
st.caption(
    "Default numeric data and fill-window labels come from this repository. "
    "The raw Video 5 clip is not included; upload a clip or use the camera stream."
)




