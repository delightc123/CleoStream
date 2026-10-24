"""
High-Performance Vision Worker Thread (QThread) for MediaPipe inference,
compositing, and virtual camera streaming.
"""
import os
import sys
import time
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision

from PySide6.QtCore import QThread, Signal, Slot, QMutex, QMutexLocker
from PySide6.QtGui import QImage

from .detector import (
    Clock, Face, Hand, Body, ensure_models, build_detectors,
    tongue_score, dist
)
from .decision import (
    POSES, ARM, HOLD_FRAMES, FACE_SCALE, Motion, measure, over, decide, draw_hud
)
from .compositor import Asset, load_asset, overlay
from .calibration import (
    Baseline, Collector, calibration_warnings, CALIB_FILE,
    CALIB_SECONDS, CALIB_WARMUP, CALIB_MIN_SAMPLES
)
from .custom_gestures import CustomGestureRegistry

from .paths import ROOT_DIR, APP_DATA_DIR


class VisionWorker(QThread):
    """
    Dedicated QThread worker running OpenCV VideoCapture, MediaPipe tasks,
    decision engine, head-tracked compositing, and pyvirtualcam broadcast.
    """
    frame_ready = Signal(QImage)
    telemetry_updated = Signal(dict)
    vcam_status_changed = Signal(bool, str)
    camera_status_changed = Signal(bool, str)
    calibration_progress = Signal(float, int, bool)   # (progress 0.0-1.0, samples, face_seen)
    calibration_finished = Signal(object, list)       # (baseline, warnings)
    assets_reloaded = Signal(list)

    def __init__(self, camera_index=0, resolution=(1280, 720), flip=True, enable_vcam=True, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self.resolution = resolution
        self.flip = flip
        self.enable_vcam = enable_vcam

        self._running = True
        self._paused = False
        self._show_hud = False
        self._calibrating = False
        self._forced_pose = None
        self._forced_until = 0.0

        self._mutex = QMutex()
        self.assets = {}
        self.baseline = Baseline.load()
        self.custom_registry = CustomGestureRegistry()
        self.vcam = None
        self.cap = None

    def run(self):
        """Main worker execution loop off the Qt GUI thread."""
        model_paths = ensure_models()
        with QMutexLocker(self._mutex):
            if not self._running:
                return

        face_det, hand_det, pose_det = build_detectors(model_paths)
        clock = Clock()
        motion = Motion()

        self._load_all_assets()
        with QMutexLocker(self._mutex):
            if not self._running:
                face_det.close()
                hand_det.close()
                pose_det.close()
                return

        self._init_camera()
        if self.enable_vcam:
            self._init_vcam()

        shown, hold = None, 0
        arm = {p: 0 for p in self.custom_registry.get_all_ids()}
        shown_since = 0.0
        sm_center = np.array([self.resolution[0] / 2, self.resolution[1] / 2], np.float32)
        sm_h = float(self.resolution[1] * 0.45)

        calib_collector = None
        calib_start = 0.0
        calib_seen_face = 0

        fps_timer = time.monotonic()
        frame_counter = 0
        current_fps = 0.0
        target_frame_time = 1.0 / 30.0

        try:
            while True:
                with QMutexLocker(self._mutex):
                    if not self._running:
                        break
                    paused = self._paused
                    show_hud = self._show_hud
                    forced_pose = self._forced_pose
                    forced_until = self._forced_until
                    calibrating = self._calibrating
                    W, H = self.resolution
                    flip = self.flip

                loop_start = time.monotonic()

                if self.cap is None or not self.cap.isOpened():
                    self.camera_status_changed.emit(False, f"Camera {self.camera_index} not opened")
                    time.sleep(0.2)
                    with QMutexLocker(self._mutex):
                        if not self._running:
                            break
                    self._init_camera()
                    continue

                ok, frame = self.cap.read()
                if not ok or frame is None:
                    with QMutexLocker(self._mutex):
                        if not self._running:
                            break
                    self.camera_status_changed.emit(False, "Failed to read camera frame")
                    time.sleep(0.02)
                    continue

                if frame.shape[0] != H or frame.shape[1] != W:
                    frame = cv2.resize(frame, (W, H))
                if flip:
                    frame = cv2.flip(frame, 1)

                # Process Calibration Mode if active
                if calibrating:
                    if calib_collector is None:
                        calib_collector = Collector()
                        calib_start = time.monotonic()
                        calib_seen_face = 0

                    elapsed = time.monotonic() - calib_start
                    ts = clock.next()
                    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    fr = face_det.detect_for_video(mp_img, ts)
                    face = Face(fr.face_landmarks[0], fr.face_blendshapes[0] if fr.face_blendshapes else None, W, H) \
                        if fr.face_landmarks else None

                    if face is not None:
                        calib_seen_face += 1
                        if elapsed > CALIB_WARMUP and face.bs:
                            calib_collector.add(face)

                    progress = min(elapsed / CALIB_SECONDS, 1.0)
                    self.calibration_progress.emit(progress, calib_collector.n, face is not None)

                    if elapsed >= CALIB_SECONDS:
                        with QMutexLocker(self._mutex):
                            self._calibrating = False
                        if calib_collector.n >= CALIB_MIN_SAMPLES:
                            base = calib_collector.finish()
                            base.save()
                            self.baseline = base
                            warns = calibration_warnings(base)
                            self.calibration_finished.emit(base, warns)
                        else:
                            self.calibration_finished.emit(None, ["Insufficient face samples captured"])
                        calib_collector = None
                        calib_seen_face = 0

                    self._emit_frame(frame)
                    self._stream_vcam(frame)
                    continue

                # Standard Reaction Pipeline
                ts = clock.next()
                mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                fr = face_det.detect_for_video(mp_img, ts)
                hr = hand_det.detect_for_video(mp_img, ts)
                pr = pose_det.detect_for_video(mp_img, ts)

                face = Face(fr.face_landmarks[0], fr.face_blendshapes[0] if fr.face_blendshapes else None, W, H) \
                    if fr.face_landmarks else None
                hands = [Hand(h, W, H) for h in hr.hand_landmarks]
                body = Body(pr.pose_landmarks[0], W, H) if pr.pose_landmarks else None

                m = measure(face, self.baseline) if face is not None else {}
                tongue = tongue_score(frame, face, hands, over("tongue_jaw", m, "z_jaw", "jaw")) if face is not None else 0.0
                gesture = motion.update(hands, face)
                raw, dbg = decide(face, hands, body, tongue, gesture, m, custom_registry=self.custom_registry)

                fired = None
                if not paused:
                    all_ids = self.custom_registry.get_all_ids()
                    for p in all_ids:
                        if p not in arm:
                            arm[p] = 0
                        arm[p] = arm[p] + 1 if raw == p else 0
                        if raw == p and arm[p] >= self.custom_registry.get_arm_frames(p):
                            fired = p
                    now = time.monotonic()
                    if forced_pose and now < forced_until:
                        fired = forced_pose
                    if fired:
                        if fired != shown:
                            shown_since = now
                        shown, hold = fired, self.custom_registry.get_hold_frames(fired)
                    elif hold > 0:
                        hold -= 1
                    else:
                        shown = None
                else:
                    shown = None

                if face is not None:
                    sm_center = 0.7 * sm_center + 0.3 * np.array(face.center, np.float32)
                    sm_h = 0.7 * sm_h + 0.3 * face.h * FACE_SCALE

                # Composite reaction overlay
                if shown and shown in self.assets:
                    asset = self.assets[shown]
                    idx = asset.frame_at(int((time.monotonic() - shown_since) * 1000))
                    h = int(min(sm_h, H * 0.98, (W * 0.98) / asset.aspect)) // 8 * 8
                    sprite = asset.scaled(idx, max(h, 8))
                    sh, sw = sprite.shape[:2]
                    overlay(frame, sprite, int(sm_center[0] - sw / 2), int(sm_center[1] - sh / 2 - 0.05 * sh))

                # Virtual camera broadcast
                self._stream_vcam(frame)

                # Telemetry update
                frame_counter += 1
                now_mono = time.monotonic()
                if now_mono - fps_timer >= 1.0:
                    current_fps = frame_counter / (now_mono - fps_timer)
                    fps_timer = now_mono
                    frame_counter = 0

                telemetry = {
                    "fps": round(current_fps, 1),
                    "shown": shown,
                    "reaction": shown,
                    "calibrated": not getattr(self.baseline, "generic", False),
                    "raw": raw,
                    "hands": len(hands),
                    "face_detected": face is not None,
                    "paused": paused,
                    "vcam_active": self.vcam is not None,
                    "dbg": dbg,
                }
                self.telemetry_updated.emit(telemetry)

                # Optional local HUD overlay on preview
                preview = frame
                if show_hud:
                    preview = frame.copy()
                    draw_hud(preview, shown, raw, dbg, face, hands, body, self.baseline)

                self._emit_frame(preview)

                # Responsive frame rate pacing
                elapsed = time.monotonic() - loop_start
                sleep_time = target_frame_time - elapsed
                while sleep_time > 0:
                    with QMutexLocker(self._mutex):
                        if not self._running:
                            break
                    step = min(sleep_time, 0.005)
                    time.sleep(step)
                    sleep_time -= step

        finally:
            face_det.close()
            hand_det.close()
            pose_det.close()
            self._cleanup()

    def _init_camera(self):
        try:
            if self.cap is not None:
                self.cap.release()
            if sys.platform == "win32":
                backend = cv2.CAP_DSHOW
            elif sys.platform == "darwin":
                backend = cv2.CAP_AVFOUNDATION
            else:
                backend = cv2.CAP_ANY
            self.cap = cv2.VideoCapture(self.camera_index, backend)
            W, H = self.resolution
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
            ok, frame = self.cap.read()
            if ok and frame is not None:
                self.camera_status_changed.emit(True, f"Camera {self.camera_index} ({W}x{H})")
            else:
                self.camera_status_changed.emit(False, f"Cannot read from Camera {self.camera_index}")
        except Exception as e:
            self.camera_status_changed.emit(False, str(e))

    def _init_vcam(self):
        try:
            import pyvirtualcam
            W, H = self.resolution
            self.vcam = pyvirtualcam.Camera(width=W, height=H, fps=30, fmt=pyvirtualcam.PixelFormat.BGR)
            self.vcam_status_changed.emit(True, str(self.vcam.device))
        except Exception as e:
            self.vcam = None
            self.vcam_status_changed.emit(False, f"Virtual camera unavailable ({e})")

    def _stream_vcam(self, frame):
        if self.vcam is not None:
            try:
                self.vcam.send(frame)
                self.vcam.sleep_until_next_frame()
            except Exception as e:
                self.vcam = None
                self.vcam_status_changed.emit(False, f"Virtual camera error: {e}")

    def _emit_frame(self, frame):
        """Converts BGR numpy frame into QImage and emits."""
        H, W = frame.shape[:2]
        bytes_per_line = 3 * W
        q_img = QImage(frame.data, W, H, bytes_per_line, QImage.Format_BGR888).copy()
        self.frame_ready.emit(q_img)

    def _load_all_assets(self):
        with QMutexLocker(self._mutex):
            all_ids = self.custom_registry.get_all_ids()
            self.assets = {}
            for p in all_ids:
                cg = self.custom_registry.get(p)
                asset_ref = cg.asset_file if (cg and cg.asset_file) else p
                self.assets[p] = load_asset(asset_ref)
        self.assets_reloaded.emit(all_ids)

    def _cleanup(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        if self.vcam is not None:
            try:
                self.vcam.close()
            except Exception:
                pass
            self.vcam = None

    # Thread-Safe Slots
    @Slot(bool)
    def set_paused(self, paused: bool):
        with QMutexLocker(self._mutex):
            self._paused = paused

    @Slot(bool)
    def set_vcam_enabled(self, enabled: bool):
        with QMutexLocker(self._mutex):
            self.enable_vcam = enabled
        if enabled and self.vcam is None:
            self._init_vcam()
        elif not enabled and self.vcam is not None:
            try:
                self.vcam.close()
            except Exception:
                pass
            self.vcam = None
            self.vcam_status_changed.emit(False, "Virtual camera disabled")

    @Slot()
    def reload_gestures(self):
        """Reloads custom gestures and refreshes loaded reaction assets."""
        with QMutexLocker(self._mutex):
            self.custom_registry.load()
        self._load_all_assets()

    @Slot(int)
    def set_camera_index(self, index: int):
        with QMutexLocker(self._mutex):
            self.camera_index = index
        self._init_camera()

    @Slot(int, int)
    def set_resolution(self, width: int, height: int):
        with QMutexLocker(self._mutex):
            self.resolution = (width, height)
        self._init_camera()
        if self.vcam is not None:
            self._init_vcam()

    @Slot(bool)
    def set_flip(self, flip: bool):
        with QMutexLocker(self._mutex):
            self.flip = flip

    @Slot(bool)
    def set_show_hud(self, show: bool):
        with QMutexLocker(self._mutex):
            self._show_hud = show

    @Slot(str, float)
    def force_reaction(self, pose: str, duration: float = 2.0):
        with QMutexLocker(self._mutex):
            self._forced_pose = pose
            self._forced_until = time.monotonic() + duration

    @Slot()
    def start_calibration(self):
        with QMutexLocker(self._mutex):
            self._calibrating = True

    @Slot()
    def cancel_calibration(self):
        with QMutexLocker(self._mutex):
            self._calibrating = False

    @Slot()
    def reload_assets(self):
        self._load_all_assets()

    def stop(self):
        with QMutexLocker(self._mutex):
            self._running = False
        if self.isRunning():
            self.wait(5000)
