"""
CleoStream — Vision & Compositing Engine Core
"""
from .detector import (
    Clock, Face, Hand, Body, ensure_models, preflight, build_detectors,
    near, tongue_score, dist, INNER_LIPS, MODELS
)
from .decision import (
    decide, POSES, TEST_KEYS, ARM, HOLD_FRAMES, Z, Z_CAP, FLOOR, T,
    FACE_SCALE, Motion, measure, over, draw_hud
)
from .compositor import (
    Asset, load_asset, overlay, placeholder, to_bgra, find_asset_file
)
from .calibration import (
    Baseline, Collector, calibration_warnings, draw_calibration,
    CALIB_FILE, CALIB_SECONDS, CALIB_WARMUP, CALIB_MIN_SAMPLES,
    SIGMA_FLOOR, SIGMA_CEIL, CALIB_VERSION, GENERIC_SIGMA, GENERIC_MEAN
)
from .gesture_matcher import (
    HandSignature, extract_hand_signature, compute_gesture_similarity,
    is_gesture_matched, classify_finger_states, classify_anchor,
    aggregate_signatures, ANCHOR_FREE, ANCHOR_NEAR_HEAD, ANCHOR_OVER_MOUTH,
    ANCHOR_UNDER_CHIN, ANCHOR_PINCHING_NOSE, FINGER_EXTENDED, FINGER_CURLED, FINGER_HALF
)
from .worker import VisionWorker

__all__ = [
    "Clock", "Face", "Hand", "Body", "ensure_models", "preflight", "build_detectors",
    "near", "tongue_score", "dist", "INNER_LIPS", "MODELS",
    "decide", "POSES", "TEST_KEYS", "ARM", "HOLD_FRAMES", "Z", "Z_CAP", "FLOOR", "T",
    "FACE_SCALE", "Motion", "measure", "over", "draw_hud",
    "Asset", "load_asset", "overlay", "placeholder", "to_bgra", "find_asset_file",
    "Baseline", "Collector", "calibration_warnings", "draw_calibration",
    "CALIB_FILE", "CALIB_SECONDS", "CALIB_WARMUP", "CALIB_MIN_SAMPLES",
    "SIGMA_FLOOR", "SIGMA_CEIL", "CALIB_VERSION", "GENERIC_SIGMA", "GENERIC_MEAN",
    "HandSignature", "extract_hand_signature", "compute_gesture_similarity",
    "is_gesture_matched", "classify_finger_states", "classify_anchor",
    "aggregate_signatures", "ANCHOR_FREE", "ANCHOR_NEAR_HEAD", "ANCHOR_OVER_MOUTH",
    "ANCHOR_UNDER_CHIN", "ANCHOR_PINCHING_NOSE", "FINGER_EXTENDED", "FINGER_CURLED", "FINGER_HALF",
    "VisionWorker",
]
