"""
Automated unit tests for engine.gesture_matcher:
Scale/translation invariance, finger state classification, spatial anchoring,
cosine similarity scoring, and multi-frame signature aggregation.
"""
import os
import sys
import numpy as np

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from engine.gesture_matcher import (
    HandSignature,
    normalize_hand_landmarks,
    classify_finger_states,
    classify_anchor,
    extract_hand_signature,
    compute_gesture_similarity,
    is_gesture_matched,
    aggregate_signatures,
    FINGER_EXTENDED,
    FINGER_CURLED,
    ANCHOR_FREE,
    ANCHOR_PINCHING_NOSE,
    ANCHOR_OVER_MOUTH,
    ANCHOR_UNDER_CHIN,
)


def _generate_synthetic_hand(pose_type: str = "peace") -> np.ndarray:
    """Generates a realistic 21-point 2D hand landmark skeleton."""
    pts = np.zeros((21, 2), dtype=np.float32)

    # 0: Wrist
    pts[0] = [100.0, 200.0]

    # Thumb: 1, 2, 3, 4
    pts[1] = [80.0, 180.0]
    pts[2] = [65.0, 160.0]
    pts[3] = [55.0, 140.0]
    pts[4] = [45.0, 120.0] if pose_type in ("open", "peace") else [80.0, 170.0]

    # Index: 5, 6, 7, 8
    pts[5] = [90.0, 140.0]
    pts[6] = [88.0, 110.0]
    pts[7] = [86.0, 80.0]
    pts[8] = [84.0, 50.0] if pose_type in ("open", "peace", "point") else [90.0, 145.0]

    # Middle: 9, 10, 11, 12
    pts[9] = [105.0, 138.0]
    pts[10] = [106.0, 105.0]
    pts[11] = [107.0, 75.0]
    pts[12] = [108.0, 45.0] if pose_type in ("open", "peace") else [105.0, 145.0]

    # Ring: 13, 14, 15, 16
    pts[13] = [120.0, 142.0]
    pts[14] = [122.0, 115.0]
    pts[15] = [124.0, 90.0]
    pts[16] = [126.0, 65.0] if pose_type == "open" else [120.0, 148.0]

    # Pinky: 17, 18, 19, 20
    pts[17] = [135.0, 150.0]
    pts[18] = [138.0, 130.0]
    pts[19] = [140.0, 110.0]
    pts[20] = [142.0, 90.0] if pose_type == "open" else [135.0, 155.0]

    return pts


class MockFace:
    """Mock Face object for testing spatial anchoring."""
    def __init__(self, nose=(300.0, 200.0), fw=120.0):
        self.nose = np.array(nose, dtype=np.float32)
        self.w = fw
        self.h = fw * 1.3
        self.mouth = np.array([nose[0], nose[1] + 35.0], dtype=np.float32)
        self.chin = np.array([nose[0], nose[1] + 70.0], dtype=np.float32)
        self.eye_y = nose[1] - 30.0


def test_scale_and_translation_invariance():
    print("Testing Scale & Translation Invariance...")
    base_hand = _generate_synthetic_hand("peace")

    # Shift hand by +450px X, +200px Y, and scale up by 3.5x
    transformed_hand = (base_hand - base_hand[0]) * 3.5 + np.array([650.0, 400.0], dtype=np.float32)

    sig_base = extract_hand_signature(base_hand)
    sig_trans = extract_hand_signature(transformed_hand)

    # Cosine similarity must be practically 1.0 (invariant to scale and position)
    similarity = compute_gesture_similarity(sig_base, sig_trans)
    assert similarity >= 0.99, f"Expected similarity >= 0.99 across transformations, got {similarity}"

    # Finger states must remain identical
    assert sig_base.finger_states == sig_trans.finger_states
    print(f"[OK] Invariance confirmed: similarity = {similarity:.4f}")


def test_discrete_finger_states():
    print("Testing Discrete Finger States...")
    peace_hand = _generate_synthetic_hand("peace")
    states_peace = classify_finger_states(peace_hand)
    assert states_peace["index"] == FINGER_EXTENDED
    assert states_peace["middle"] == FINGER_EXTENDED
    assert states_peace["ring"] == FINGER_CURLED
    assert states_peace["pinky"] == FINGER_CURLED

    fist_hand = _generate_synthetic_hand("fist")
    states_fist = classify_finger_states(fist_hand)
    assert states_fist["index"] == FINGER_CURLED
    assert states_fist["middle"] == FINGER_CURLED
    assert states_fist["ring"] == FINGER_CURLED
    assert states_fist["pinky"] == FINGER_CURLED

    open_hand = _generate_synthetic_hand("open")
    states_open = classify_finger_states(open_hand)
    assert states_open["index"] == FINGER_EXTENDED
    assert states_open["middle"] == FINGER_EXTENDED
    assert states_open["ring"] == FINGER_EXTENDED
    assert states_open["pinky"] == FINGER_EXTENDED
    print("[OK] Finger state classifications verified (Peace, Fist, Open Hand)")


def test_face_relative_spatial_anchors():
    print("Testing Spatial Anchors...")
    mock_face = MockFace(nose=(400.0, 300.0), fw=150.0)

    # 1. Free floating hand far from face
    free_hand = _generate_synthetic_hand("open") + np.array([500.0, 200.0])
    sig_free = extract_hand_signature(free_hand, face=mock_face)
    assert sig_free.anchor == ANCHOR_FREE

    # 2. Hand covering mouth
    mouth_hand = _generate_synthetic_hand("open")
    mouth_palm = mouth_hand[[0, 5, 9, 13, 17]].mean(0)
    mouth_hand = mouth_hand - mouth_palm + mock_face.mouth
    sig_mouth = extract_hand_signature(mouth_hand, face=mock_face)
    assert sig_mouth.anchor == ANCHOR_OVER_MOUTH

    # 3. Hand under chin
    chin_hand = _generate_synthetic_hand("open")
    chin_palm = chin_hand[[0, 5, 9, 13, 17]].mean(0)
    chin_hand = chin_hand - chin_palm + mock_face.chin + np.array([0.0, 10.0])
    sig_chin = extract_hand_signature(chin_hand, face=mock_face)
    assert sig_chin.anchor == ANCHOR_UNDER_CHIN

    print("[OK] Spatial Anchors verified (Free, Mouth, Chin)")


def test_gesture_discrimination():
    print("Testing Gesture Discrimination & Tolerance matching...")
    peace_hand = _generate_synthetic_hand("peace")
    fist_hand = _generate_synthetic_hand("fist")

    sig_peace = extract_hand_signature(peace_hand)
    sig_fist = extract_hand_signature(fist_hand)

    # Matching same gesture
    matched, score = is_gesture_matched(sig_peace, sig_peace)
    assert matched is True
    assert score >= 0.99

    # Comparing peace against fist (must reject)
    matched_diff, score_diff = is_gesture_matched(sig_peace, sig_fist)
    assert matched_diff is False
    assert score_diff < 0.65, f"Expected low score for different gestures, got {score_diff}"
    print(f"[OK] Discrimination verified: same = {score:.4f}, different = {score_diff:.4f}")


def test_signature_aggregation():
    print("Testing Multi-Frame Calibration Aggregation...")
    base = _generate_synthetic_hand("peace")
    np.random.seed(42)

    # Simulate 30 frames with jitter noise (hand held steady)
    signatures = []
    for _ in range(30):
        noisy_hand = base + np.random.normal(0, 1.2, base.shape).astype(np.float32)
        signatures.append(extract_hand_signature(noisy_hand))

    aggregated_sig, variance = aggregate_signatures(signatures)
    assert len(aggregated_sig.vector) == 42
    assert aggregated_sig.finger_states["index"] == FINGER_EXTENDED
    assert aggregated_sig.finger_states["middle"] == FINGER_EXTENDED
    assert aggregated_sig.finger_states["pinky"] == FINGER_CURLED
    assert variance < 0.05, f"Expected low variance during stable hold, got {variance}"

    # Verify serialized dictionary roundtrip
    data = aggregated_sig.to_dict()
    restored = HandSignature.from_dict(data)
    assert restored.vector == aggregated_sig.vector
    assert restored.finger_states == aggregated_sig.finger_states
    print(f"[OK] Aggregation verified: 30 frames -> variance = {variance:.5f}")


import unittest


class TestGestureMatcher(unittest.TestCase):
    def test_scale_and_translation_invariance(self):
        test_scale_and_translation_invariance()

    def test_discrete_finger_states(self):
        test_discrete_finger_states()

    def test_face_relative_spatial_anchors(self):
        test_face_relative_spatial_anchors()

    def test_gesture_discrimination(self):
        test_gesture_discrimination()

    def test_signature_aggregation(self):
        test_signature_aggregation()


if __name__ == "__main__":
    test_scale_and_translation_invariance()
    test_discrete_finger_states()
    test_face_relative_spatial_anchors()
    test_gesture_discrimination()
    test_signature_aggregation()
    print("\nAll Gesture Matcher Unit Tests PASSED cleanly!")
