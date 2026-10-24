"""
Automated unit tests for engine.custom_gestures:
CustomGesture model, CustomGestureRegistry persistence, atomic disk writes,
corrupted file recovery, and dynamic integration with decide().
"""
import os
import sys
import shutil
import tempfile
import unittest
import numpy as np

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from engine.custom_gestures import (
    CustomGesture,
    CustomGestureRegistry,
    DEFAULT_BUILTIN_GESTURES,
)
from engine.gesture_matcher import (
    HandSignature,
    extract_hand_signature,
    is_gesture_matched,
    FINGER_EXTENDED,
    FINGER_CURLED,
    ANCHOR_FREE,
)
from engine.decision import decide, POSES


def _generate_synthetic_hand(pose_type: str = "peace") -> np.ndarray:
    """Generates a synthetic 21-point hand skeleton."""
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
        self.thumb = pts[4]
        self.index = pts[8]
        self.middle = pts[12]
        self.ring = pts[16]
        self.pinky = pts[20]
        self.open = False
        self.horizontal = False
        self.vertical = True


class MockFace:
    def __init__(self, nose=(300.0, 200.0), fw=120.0):
        self.nose = np.array(nose, dtype=np.float32)
        self.w = fw
        self.h = fw * 1.3
        self.mouth = np.array([nose[0], nose[1] + 35.0], dtype=np.float32)
        self.chin = np.array([nose[0], nose[1] + 70.0], dtype=np.float32)
        self.eye_y = nose[1] - 30.0


class TestCustomGestures(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.json_path = os.path.join(self.test_dir, "test_custom_gestures.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_default_seeding(self):
        """Verifies default registry seeds all 14 built-in gestures."""
        registry = CustomGestureRegistry(filepath=self.json_path)
        all_gestures = registry.get_all()
        self.assertEqual(len(all_gestures), len(DEFAULT_BUILTIN_GESTURES))
        self.assertEqual(len(all_gestures), len(POSES))

        for pose_id in POSES:
            g = registry.get(pose_id)
            self.assertIsNotNone(g, f"Built-in pose {pose_id} missing from registry")
            self.assertTrue(g.is_builtin)
            self.assertTrue(g.enabled)
            self.assertFalse(g.has_calibration())

        # Disk file must exist
        self.assertTrue(os.path.exists(self.json_path))

    def test_add_and_update_custom_gesture(self):
        """Verifies adding a custom gesture and updating its attributes."""
        registry = CustomGestureRegistry(filepath=self.json_path)

        synthetic_hand = _generate_synthetic_hand("peace")
        sig = extract_hand_signature(synthetic_hand)

        custom = CustomGesture(
            id="custom_peace",
            display_name="Victory Sign",
            asset_file="peace.png",
            hands_count=1,
            arm_frames=3,
            hold_frames=12,
        )
        custom.set_signature(sig)
        registry.add_or_update(custom)

        # Retrieve and verify
        retrieved = registry.get("custom_peace")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.display_name, "Victory Sign")
        self.assertTrue(retrieved.has_calibration())
        self.assertEqual(len(retrieved.feature_vector), 42)

        # Update tolerance
        retrieved.tolerance = 0.92
        registry.add_or_update(retrieved)
        self.assertEqual(registry.get("custom_peace").tolerance, 0.92)

    def test_disk_persistence_roundtrip(self):
        """Verifies that saved custom gestures survive process reload from disk."""
        registry1 = CustomGestureRegistry(filepath=self.json_path)
        sig = extract_hand_signature(_generate_synthetic_hand("peace"))
        cg = CustomGesture(id="magic_wand", display_name="Magic Wand")
        cg.set_signature(sig)
        registry1.add_or_update(cg)

        # Load fresh registry instance pointing to same file
        registry2 = CustomGestureRegistry(filepath=self.json_path)
        loaded = registry2.get("magic_wand")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.display_name, "Magic Wand")
        self.assertTrue(loaded.has_calibration())
        self.assertEqual(loaded.feature_vector, cg.feature_vector)

    def test_corrupt_file_recovery(self):
        """Verifies that corrupted JSON is backed up and factory defaults restored without crashing."""
        # Write corrupted JSON
        with open(self.json_path, "w", encoding="utf-8") as f:
            f.write("{ invalid json [ 123, broken")

        registry = CustomGestureRegistry(filepath=self.json_path)
        # Should gracefully recover with all 14 defaults
        self.assertEqual(len(registry.get_all()), 14)

        # Backup file must have been created in directory
        files = os.listdir(self.test_dir)
        corrupt_backups = [fn for fn in files if "corrupt" in fn]
        self.assertTrue(len(corrupt_backups) >= 1, "Expected corrupt backup file to be created")

    def test_delete_gesture(self):
        """Verifies deleting custom gesture removes it, while deleting built-in clears calibration."""
        registry = CustomGestureRegistry(filepath=self.json_path)

        # 1. Add and delete custom gesture
        cg = CustomGesture(id="temp_reaction", display_name="Temp")
        registry.add_or_update(cg)
        self.assertIn("temp_reaction", registry.get_all_ids())
        self.assertTrue(registry.delete("temp_reaction"))
        self.assertNotIn("temp_reaction", registry.get_all_ids())

        # 2. Calibrate and delete built-in gesture
        heart = registry.get("heart")
        heart.set_signature(extract_hand_signature(_generate_synthetic_hand("peace")))
        registry.add_or_update(heart)
        self.assertTrue(registry.get("heart").has_calibration())

        self.assertTrue(registry.delete("heart"))
        # Built-in is retained in registry, but calibration cleared
        self.assertIn("heart", registry.get_all_ids())
        self.assertFalse(registry.get("heart").has_calibration())

    def test_decide_integration_with_custom_registry(self):
        """Verifies decide() prioritizes calibrated custom gestures over default rules."""
        registry = CustomGestureRegistry(filepath=self.json_path)

        peace_hand_pts = _generate_synthetic_hand("peace")
        fist_hand_pts = _generate_synthetic_hand("fist")

        mock_face = MockFace()
        mock_hand_peace = MockHand(peace_hand_pts)
        mock_hand_fist = MockHand(fist_hand_pts)

        # Register custom gesture with peace signature
        sig_peace = extract_hand_signature(peace_hand_pts, face=mock_face)
        custom = CustomGesture(id="victory_dance", display_name="Victory Dance", hands_count=1)
        custom.set_signature(sig_peace)
        registry.add_or_update(custom)

        # 1. Test when peace hand is present: custom gesture triggers!
        pose, dbg = decide(
            face=mock_face,
            hands=[mock_hand_peace],
            body=None,
            tongue=0.0,
            gesture=0.0,
            m={"turn": 0.0, "z_jaw": 0.0, "jaw": 0.0, "z_disgust": 0.0, "z_sneer": 0.0, "sneer": 0.0, "z_squint": 0.0, "squint": 0.0},
            custom_registry=registry,
        )
        self.assertEqual(pose, "victory_dance")
        self.assertEqual(dbg.get("custom_match"), "victory_dance")
        self.assertGreaterEqual(dbg.get("custom_score", 0), 0.85)

        # 2. Test when fist hand is present: custom gesture does NOT trigger
        pose_fist, dbg_fist = decide(
            face=mock_face,
            hands=[mock_hand_fist],
            body=None,
            tongue=0.0,
            gesture=0.0,
            m={"turn": 0.0, "z_jaw": 0.0, "jaw": 0.0, "z_disgust": 0.0, "z_sneer": 0.0, "sneer": 0.0, "z_squint": 0.0, "squint": 0.0},
            custom_registry=registry,
        )
        self.assertNotEqual(pose_fist, "victory_dance")


if __name__ == "__main__":
    unittest.main()
