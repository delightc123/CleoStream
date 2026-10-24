"""
CleoStream — Mathematical Hand Gesture Feature Extraction & Matching Engine
Provides scale-invariant coordinate normalization, discrete finger state classification,
face-relative spatial anchoring, and cosine similarity scoring.
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Union
import math
import numpy as np


# Discrete Finger States
FINGER_EXTENDED = "extended"
FINGER_CURLED = "curled"
FINGER_HALF = "half_curled"

# Spatial Anchors relative to Face
ANCHOR_FREE = "FREE_FLOATING"
ANCHOR_NEAR_HEAD = "NEAR_HEAD"
ANCHOR_OVER_MOUTH = "OVER_MOUTH"
ANCHOR_UNDER_CHIN = "UNDER_CHIN"
ANCHOR_PINCHING_NOSE = "PINCHING_NOSE"

FINGER_NAMES = ("thumb", "index", "middle", "ring", "pinky")

# Landmark indices for fingers
# (MCP, PIP, DIP, TIP)
FINGER_LANDMARK_MAP = {
    "thumb": (2, 3, 4),        # MCP, IP, TIP
    "index": (5, 6, 7, 8),     # MCP, PIP, DIP, TIP
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}


def _euclidean_dist(a: np.ndarray, b: np.ndarray) -> float:
    """Calculates 2D Euclidean distance between two points."""
    return float(np.linalg.norm(np.asarray(a) - np.asarray(b)))


@dataclass
class HandSignature:
    """
    Scale-invariant, translation-invariant mathematical signature of a hand pose.
    Serialized into custom_gestures.json for dynamic gesture evaluation.
    """
    vector: List[float] = field(default_factory=list)
    finger_states: Dict[str, str] = field(default_factory=dict)
    anchor: str = ANCHOR_FREE
    hands_count: int = 1
    relative_to_face: Optional[List[float]] = None
    tolerance: float = 0.85

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "HandSignature":
        return cls(
            vector=[float(v) for v in data.get("vector", [])],
            finger_states=dict(data.get("finger_states", {})),
            anchor=str(data.get("anchor", ANCHOR_FREE)),
            hands_count=int(data.get("hands_count", 1)),
            relative_to_face=data.get("relative_to_face"),
            tolerance=float(data.get("tolerance", 0.85)),
        )


def normalize_hand_landmarks(pts: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    Normalizes 21 2D landmarks:
    1. Origin translation: Centers all points at Wrist (landmark 0).
    2. Scale normalization: Divides by Euclidean distance from Wrist (0) to Middle MCP (9).
    Returns (normalized_points, scale_factor).
    """
    if pts.shape[0] < 21:
        raise ValueError(f"Expected at least 21 hand landmarks, received {pts.shape[0]}")

    wrist = pts[0]
    translated = pts - wrist

    # Scale by distance from wrist (0) to middle MCP (9)
    scale = float(np.linalg.norm(translated[9]))
    if scale < 1e-4:
        scale = 1.0

    normalized = translated / scale
    return normalized, scale


def classify_finger_states(pts: np.ndarray) -> Dict[str, str]:
    """
    Classifies extension state (extended, curled, half_curled) for all 5 fingers.
    Uses distance ratios from Wrist (0) to Tips vs PIPs.
    """
    states = {}
    wrist = pts[0]

    # 1. Four main fingers (Index, Middle, Ring, Pinky)
    for name in ("index", "middle", "ring", "pinky"):
        mcp_idx, pip_idx, _, tip_idx = FINGER_LANDMARK_MAP[name]
        d_tip = _euclidean_dist(pts[tip_idx], wrist)
        d_pip = _euclidean_dist(pts[pip_idx], wrist)

        ratio = d_tip / max(d_pip, 1e-4)
        if ratio > 1.25:
            states[name] = FINGER_EXTENDED
        elif ratio < 0.95:
            states[name] = FINGER_CURLED
        else:
            states[name] = FINGER_HALF

    # 2. Thumb articulation (compared to Pinky MCP 17)
    # When thumb is extended away from palm, distance to pinky knuckle is large
    d_thumb_tip_pinky = _euclidean_dist(pts[4], pts[17])
    d_thumb_mcp_pinky = _euclidean_dist(pts[2], pts[17])
    d_thumb_tip_index = _euclidean_dist(pts[4], pts[5])

    thumb_ratio = d_thumb_tip_pinky / max(d_thumb_mcp_pinky, 1e-4)
    if thumb_ratio > 1.15 and d_thumb_tip_index > 0.4 * d_thumb_mcp_pinky:
        states["thumb"] = FINGER_EXTENDED
    elif thumb_ratio < 0.95 or d_thumb_tip_index < 0.25 * d_thumb_mcp_pinky:
        states["thumb"] = FINGER_CURLED
    else:
        states["thumb"] = FINGER_HALF

    return states


def classify_anchor(
    pts: np.ndarray,
    palm: np.ndarray,
    face=None
) -> Tuple[str, Optional[List[float]]]:
    """
    Determines whether hand is situated in a specific face-relative spatial zone.
    Returns (anchor_zone, relative_offset).
    """
    if face is None:
        return ANCHOR_FREE, None

    fw = max(getattr(face, "w", 100.0), 1.0)
    rel_x = float((palm[0] - face.nose[0]) / fw)
    rel_y = float((palm[1] - face.nose[1]) / fw)
    rel_offset = [round(rel_x, 3), round(rel_y, 3)]

    # Distances to key facial landmarks
    d_nose = _euclidean_dist(palm, face.nose)
    d_mouth = _euclidean_dist(palm, face.mouth)
    d_chin = _euclidean_dist(palm, face.chin)

    # 1. Pinching nose check (index tip and thumb tip both near nose)
    d_index_nose = _euclidean_dist(pts[8], face.nose)
    d_thumb_nose = _euclidean_dist(pts[4], face.nose)
    d_fingers = _euclidean_dist(pts[8], pts[4])

    if d_index_nose < 0.38 * fw and d_thumb_nose < 0.38 * fw and d_fingers < 0.32 * fw:
        return ANCHOR_PINCHING_NOSE, rel_offset

    # 2. Under chin check (evaluated if palm is at or below the chin plane)
    if d_chin < 0.60 * fw and palm[1] >= face.chin[1] - 0.15 * fw:
        return ANCHOR_UNDER_CHIN, rel_offset

    # 3. Covering mouth check (centered over mouth, above lower chin)
    if d_mouth < 0.50 * fw and palm[1] < face.chin[1]:
        return ANCHOR_OVER_MOUTH, rel_offset

    # 4. Near head check (beside ears or temples)
    eye_y = getattr(face, "eye_y", face.nose[1] - 0.2 * fw)
    face_h = getattr(face, "h", fw)
    if abs(palm[0] - face.nose[0]) < 1.35 * fw and palm[1] < eye_y + 0.35 * face_h:
        return ANCHOR_NEAR_HEAD, rel_offset

    return ANCHOR_FREE, rel_offset


def extract_hand_signature(
    hand_input: Union[np.ndarray, any],
    W: int = 1280,
    H: int = 720,
    face=None,
    hands_count: int = 1
) -> HandSignature:
    """
    Extracts a complete HandSignature from either:
    1. A Hand object from engine.detector (having .pts and .palm)
    2. A numpy array of shape (21, 2) or (21, 3)
    3. A list of MediaPipe landmark objects (with .x and .y)
    """
    if hasattr(hand_input, "pts"):
        pts = hand_input.pts
        palm = hand_input.palm
    elif isinstance(hand_input, np.ndarray):
        pts = hand_input[:, :2].astype(np.float32)
        palm = pts[[0, 5, 9, 13, 17]].mean(0)
    elif isinstance(hand_input, (list, tuple)):
        # List of MediaPipe landmarks
        pts = np.array([[l.x * W, l.y * H] for l in hand_input], dtype=np.float32)
        palm = pts[[0, 5, 9, 13, 17]].mean(0)
    else:
        raise TypeError(f"Unsupported hand input type: {type(hand_input)}")

    # 1. Scale-invariant normalized vector (42 dimensions: 21 (x, y) coordinates)
    norm_pts, _ = normalize_hand_landmarks(pts)
    vector = norm_pts.flatten().tolist()

    # 2. Discrete finger extension states
    finger_states = classify_finger_states(pts)

    # 3. Spatial anchoring
    anchor, rel_offset = classify_anchor(pts, palm, face)

    return HandSignature(
        vector=[round(v, 4) for v in vector],
        finger_states=finger_states,
        anchor=anchor,
        hands_count=hands_count,
        relative_to_face=rel_offset,
        tolerance=0.85,
    )


def compute_gesture_similarity(live: HandSignature, target: HandSignature) -> float:
    """
    Computes a composite similarity score [0.0, 1.0] between a live signature and a target.
    Combines:
    1. Landmark coordinate vector Cosine Similarity (70% weight)
    2. Discrete Finger State match percentage (30% weight)
    3. Spatial Anchor requirement gate
    """
    if not live.vector or not target.vector:
        return 0.0

    # 1. Hands count requirement
    if target.hands_count > 1 and live.hands_count < target.hands_count:
        return 0.0

    # 2. Vector Cosine Similarity
    v1 = np.asarray(live.vector, dtype=np.float32)
    v2 = np.asarray(target.vector, dtype=np.float32)

    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 < 1e-6 or norm2 < 1e-6:
        return 0.0

    cos_sim = float(np.dot(v1, v2) / (norm1 * norm2))
    cos_sim = max(0.0, min(1.0, cos_sim))

    # 3. Discrete Finger States Match Score
    matched_fingers = 0.0
    for finger in FINGER_NAMES:
        target_st = target.finger_states.get(finger)
        live_st = live.finger_states.get(finger)

        if not target_st or not live_st:
            matched_fingers += 0.5
            continue

        if live_st == target_st:
            matched_fingers += 1.0
        elif live_st == FINGER_HALF or target_st == FINGER_HALF:
            matched_fingers += 0.6
        else:
            # Complete mismatch (e.g. extended vs curled)
            matched_fingers += 0.0

    finger_score = matched_fingers / len(FINGER_NAMES)

    # 4. Anchor Zone Compatibility
    anchor_multiplier = 1.0
    if target.anchor != ANCHOR_FREE:
        if live.anchor == target.anchor:
            anchor_multiplier = 1.0
        else:
            # Penalize mismatch if specific anchor was required
            anchor_multiplier = 0.45

    # Multiplicative confidence: geometric alignment gated by finger states
    confidence = (cos_sim * finger_score) * anchor_multiplier
    return float(round(confidence, 4))


def is_gesture_matched(live: HandSignature, target: HandSignature) -> Tuple[bool, float]:
    """
    Evaluates whether live hand signature matches target signature above tolerance.
    Returns (is_match: bool, confidence: float).
    """
    confidence = compute_gesture_similarity(live, target)
    matched = confidence >= target.tolerance
    return matched, confidence


def aggregate_signatures(signatures: List[HandSignature]) -> Tuple[HandSignature, float]:
    """
    Averages multiple signatures collected during a 3-second hold to produce a
    clean, noise-reduced calibrated gesture signature.
    Also returns variance metric (stability score, where lower = more stable).
    """
    if not signatures:
        raise ValueError("Cannot aggregate empty list of signatures")

    # 1. Compute mean vector
    vectors = np.array([s.vector for s in signatures], dtype=np.float32)
    mean_vec = vectors.mean(axis=0)
    variance = float(vectors.var(axis=0).mean())

    # 2. Majority vote for finger states
    aggregated_states = {}
    for finger in FINGER_NAMES:
        counts = {}
        for s in signatures:
            st = s.finger_states.get(finger, FINGER_HALF)
            counts[st] = counts.get(st, 0) + 1
        majority_state = max(counts.items(), key=lambda item: item[1])[0]
        aggregated_states[finger] = majority_state

    # 3. Majority vote for anchor
    anchor_counts = {}
    for s in signatures:
        anchor_counts[s.anchor] = anchor_counts.get(s.anchor, 0) + 1
    majority_anchor = max(anchor_counts.items(), key=lambda item: item[1])[0]

    # Average face relative offset if present
    offsets = [s.relative_to_face for s in signatures if s.relative_to_face is not None]
    avg_offset = np.array(offsets).mean(axis=0).round(3).tolist() if offsets else None

    calibrated_sig = HandSignature(
        vector=[round(float(v), 4) for v in mean_vec],
        finger_states=aggregated_states,
        anchor=majority_anchor,
        hands_count=signatures[0].hands_count,
        relative_to_face=avg_offset,
        tolerance=signatures[0].tolerance,
    )

    return calibrated_sig, variance
