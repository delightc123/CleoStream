"""
Automated unit tests for ui.gesture_recorder_dialog:
GestureRecorderDialog UI lifecycle, skeletal landmark wireframe rendering,
countdown state machine, 30-frame sampling, and variance stability verification.
"""
import os
import sys
import unittest
import numpy as np

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter
from PySide6.QtCore import Qt

from ui.gesture_recorder_dialog import (
    GestureRecorderDialog,
    GestureCanvas,
    STATE_IDLE,
    STATE_COUNTDOWN,
    STATE_SAMPLING,
    STATE_CONFIRMED,
    STATE_FAILED,
)
from engine.gesture_matcher import (
    HandSignature,
    FINGER_EXTENDED,
    FINGER_CURLED,
)


def _generate_synthetic_hand(pose_type: str = "peace") -> np.ndarray:
    pts = np.zeros((21, 2), dtype=np.float32)
    pts[0] = [100.0, 200.0]  # Wrist

    # Thumb: 1, 2, 3, 4
    pts[1] = [80.0, 180.0]
    pts[2] = [65.0, 160.0]
    pts[3] = [55.0, 140.0]
    pts[4] = [45.0, 120.0] if pose_type == "peace" else [80.0, 170.0]

    # Index: 5, 6, 7, 8
    pts[5] = [90.0, 140.0]
    pts[6] = [88.0, 110.0]
    pts[7] = [86.0, 80.0]
    pts[8] = [84.0, 50.0] if pose_type == "peace" else [90.0, 145.0]

    # Middle: 9, 10, 11, 12
    pts[9] = [105.0, 138.0]
    pts[10] = [106.0, 105.0]
    pts[11] = [107.0, 75.0]
    pts[12] = [108.0, 45.0] if pose_type == "peace" else [105.0, 145.0]

    # Ring: 13, 14, 15, 16
    pts[13] = [120.0, 142.0]
    pts[14] = [122.0, 115.0]
    pts[15] = [124.0, 90.0]
    pts[16] = [120.0, 148.0]

    # Pinky: 17, 18, 19, 20
    pts[17] = [135.0, 150.0]
    pts[18] = [138.0, 130.0]
    pts[19] = [140.0, 110.0]
    pts[20] = [135.0, 155.0]

    return pts


class MockHand:
    def __init__(self, pts):
        self.pts = pts
        self.palm = pts[[0, 5, 9, 13, 17]].mean(0)


class MockFace:
    def __init__(self, nose=(300.0, 200.0), fw=120.0):
        self.nose = np.array(nose, dtype=np.float32)
        self.w = fw
        self.h = fw * 1.3
        self.mouth = np.array([nose[0], nose[1] + 35.0], dtype=np.float32)
        self.chin = np.array([nose[0], nose[1] + 70.0], dtype=np.float32)
        self.eye_y = nose[1] - 30.0


class TestGestureRecorderDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.dialog = GestureRecorderDialog(gesture_name="Peace Sign")
        self.test_img = QImage(640, 480, QImage.Format_BGR888)
        self.test_img.fill(0)

    def tearDown(self):
        self.dialog.close()

    def test_initial_state_and_canvas_render(self):
        """Verifies initial UI hierarchy and smooth canvas painting with skeletal wireframe."""
        self.assertEqual(self.dialog.state, STATE_IDLE)
        self.assertFalse(self.dialog.save_btn.isEnabled())
        self.assertEqual(self.dialog.progress_bar.value(), 0)

        # Feed frame and mock hand
        mock_pts = _generate_synthetic_hand("peace")
        mock_hand = MockHand(mock_pts)
        mock_face = MockFace()

        self.dialog.update_frame(self.test_img)
        self.dialog.update_tracking([mock_hand], mock_face)

        # Trigger paint on canvas to ensure no rendering exceptions
        self.dialog.show()
        QApplication.processEvents()
        self.dialog.hide()

        # Check finger state label updated
        label_text = self.dialog.finger_summary_label.text()
        self.assertIn("Fingers:", label_text)
        self.assertIn("I:UP", label_text)
        self.assertIn("M:UP", label_text)
        self.assertIn("P:DOWN", label_text)

    def test_countdown_state_machine(self):
        """Verifies countdown state transitions: IDLE -> COUNTDOWN -> SAMPLING."""
        self.dialog._on_start_clicked()
        self.assertEqual(self.dialog.state, STATE_COUNTDOWN)
        self.assertEqual(self.dialog.countdown_remaining, 3)

        # Tick 1: 3 -> 2
        self.dialog._on_countdown_tick()
        self.assertEqual(self.dialog.countdown_remaining, 2)
        self.assertEqual(self.dialog.state, STATE_COUNTDOWN)

        # Tick 2: 2 -> 1
        self.dialog._on_countdown_tick()
        self.assertEqual(self.dialog.countdown_remaining, 1)
        self.assertEqual(self.dialog.state, STATE_COUNTDOWN)

        # Tick 3: 1 -> 0 (Transition to SAMPLING)
        self.dialog._on_countdown_tick()
        self.assertEqual(self.dialog.countdown_remaining, 0)
        self.assertEqual(self.dialog.state, STATE_SAMPLING)

    def test_successful_sampling_and_stability_verification(self):
        """Verifies collecting 30 stable frames results in STATE_CONFIRMED with valid signature."""
        self.dialog.state = STATE_SAMPLING
        self.dialog.samples.clear()

        base_pts = _generate_synthetic_hand("peace")
        mock_face = MockFace()

        # Feed 30 steady frames with subtle jitter
        np.random.seed(42)
        for _ in range(30):
            jitter_pts = base_pts + np.random.normal(0, 0.5, base_pts.shape).astype(np.float32)
            self.dialog.update_tracking([MockHand(jitter_pts)], mock_face)

        # Should finish sampling and transition to CONFIRMED
        self.assertEqual(self.dialog.state, STATE_CONFIRMED)
        self.assertEqual(len(self.dialog.samples), 30)
        self.assertIsNotNone(self.dialog.calibrated_signature)
        self.assertLessEqual(self.dialog.calibrated_variance, 0.05)
        self.assertTrue(self.dialog.save_btn.isEnabled())

        # Test save signal emission
        emitted_signals = []
        self.dialog.gesture_recorded.connect(lambda sig: emitted_signals.append(sig))
        self.dialog._on_save_clicked()

        self.assertEqual(len(emitted_signals), 1)
        sig = emitted_signals[0]
        self.assertIsInstance(sig, HandSignature)
        self.assertEqual(len(sig.vector), 42)
        self.assertEqual(sig.finger_states["index"], FINGER_EXTENDED)
        self.assertEqual(sig.finger_states["middle"], FINGER_EXTENDED)

    def test_instability_rejection(self):
        """Verifies collecting 30 erratic frames fails stability check and offers retry."""
        self.dialog.state = STATE_SAMPLING
        self.dialog.samples.clear()

        base_pts = _generate_synthetic_hand("peace")
        mock_face = MockFace()

        # Feed 30 wildly erratic frames (large variance simulating shaky/moving hand)
        np.random.seed(99)
        for i in range(30):
            wild_pts = base_pts + np.random.uniform(-40.0, 40.0, base_pts.shape).astype(np.float32)
            self.dialog.update_tracking([MockHand(wild_pts)], mock_face)

        # Should fail stability check
        self.assertEqual(self.dialog.state, STATE_FAILED)
        self.assertGreater(self.dialog.calibrated_variance, 0.05)
        self.assertFalse(self.dialog.save_btn.isEnabled())
        self.assertEqual(self.dialog.start_btn.text(), "Retry")


if __name__ == "__main__":
    unittest.main()
