"""
Automated unit and integration tests for Sprint 5:
AddReactionDialog, AddReactionCard, dynamic ReactionCard revamps,
slug generation, asset copying, and gesture re-binding persistence.
"""
import os
import sys
import shutil
import tempfile
import unittest
import numpy as np
from PIL import Image

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPointF, QEvent
from PySide6.QtGui import QMouseEvent

from ui.add_reaction_dialog import (
    AddReactionDialog,
    slugify_reaction_id,
    validate_asset_file,
)
from ui.asset_grid import (
    AssetGridWidget,
    ReactionCard,
    AddReactionCard,
)
from engine.custom_gestures import CustomGesture, CustomGestureRegistry
from engine.gesture_matcher import (
    HandSignature,
    extract_hand_signature,
    FINGER_EXTENDED,
    FINGER_CURLED,
)


def _generate_synthetic_hand() -> np.ndarray:
    pts = np.zeros((21, 2), dtype=np.float32)
    pts[0] = [100.0, 200.0]
    for i in range(1, 21):
        pts[i] = [100.0 + i * 2, 200.0 - i * 5]
    return pts


class TestAddReactionAndGrid(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.json_path = os.path.join(self.test_dir, "gestures.json")
        self.registry = CustomGestureRegistry(filepath=self.json_path)

        # Create dummy PNG image asset
        self.sample_img_path = os.path.join(self.test_dir, "sample.png")
        img = Image.new("RGBA", (120, 120), (255, 0, 0, 255))
        img.save(self.sample_img_path)

        self.synthetic_sig = extract_hand_signature(_generate_synthetic_hand())

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        # Clean up any test asset file copied to project assets during dev test
        dev_asset = os.path.join(ROOT_DIR, "assets", "victory_dance.png")
        if os.path.isfile(dev_asset):
            try:
                os.remove(dev_asset)
            except Exception:
                pass

    def test_slugify_and_validator(self):
        """Verifies slugify_reaction_id and validate_asset_file helpers."""
        self.assertEqual(slugify_reaction_id("Cool Sunglasses"), "cool_sunglasses")
        self.assertEqual(slugify_reaction_id("  Party--Time!!  "), "party_time")
        self.assertEqual(slugify_reaction_id(""), "custom_reaction")

        self.assertTrue(validate_asset_file(self.sample_img_path))
        self.assertFalse(validate_asset_file("nonexistent.png"))

        # Corrupted file test
        corrupt_path = os.path.join(self.test_dir, "corrupt.png")
        with open(corrupt_path, "wb") as f:
            f.write(b"not an image")
        self.assertFalse(validate_asset_file(corrupt_path))

    def test_add_reaction_card_click(self):
        """Verifies AddReactionCard emits add_clicked on click."""
        card = AddReactionCard()
        signals = []
        card.add_clicked.connect(lambda: signals.append(True))

        press_event = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(20.0, 20.0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        card.mousePressEvent(press_event)
        self.assertEqual(len(signals), 1)

    def test_add_reaction_dialog_validation_and_creation(self):
        """Verifies AddReactionDialog inputs validation and reaction creation."""
        dialog = AddReactionDialog(registry=self.registry)
        self.assertFalse(dialog.create_btn.isEnabled())

        # 1. Provide name only -> still disabled
        dialog.name_input.setText("Victory Dance")
        self.assertFalse(dialog.create_btn.isEnabled())

        # 2. Provide asset -> still disabled (no gesture)
        dialog._set_asset_path(self.sample_img_path)
        self.assertFalse(dialog.create_btn.isEnabled())

        # 3. Provide gesture signature -> enabled!
        dialog.set_recorded_signature_for_test(self.synthetic_sig)
        self.assertTrue(dialog.create_btn.isEnabled())

        # 4. Create reaction
        emitted = []
        dialog.reaction_created.connect(lambda g: emitted.append(g))
        dialog._on_create_clicked()

        self.assertEqual(len(emitted), 1)
        created_gesture = emitted[0]
        self.assertEqual(created_gesture.id, "victory_dance")
        self.assertEqual(created_gesture.display_name, "Victory Dance")
        self.assertTrue(created_gesture.has_calibration())

        # Verify persisted in registry
        in_reg = self.registry.get("victory_dance")
        self.assertIsNotNone(in_reg)
        self.assertEqual(in_reg.display_name, "Victory Dance")
        self.assertFalse(in_reg.is_builtin)

    def test_asset_grid_dynamic_cards_and_deletion(self):
        """Verifies AssetGridWidget populates built-ins, custom cards, and handles deletion."""
        grid_widget = AssetGridWidget(registry=self.registry)

        # Initially 14 built-in cards
        self.assertEqual(len(grid_widget.cards), 14)
        self.assertIn("heart", grid_widget.cards)
        self.assertNotIn("delete_btn", dir(grid_widget.cards["heart"]))

        # Add custom reaction to registry and reload
        custom = CustomGesture(id="facepalm", display_name="Facepalm", is_builtin=False)
        custom.set_signature(self.synthetic_sig)
        self.registry.add_or_update(custom)
        grid_widget.reload_grid()

        # Now 15 cards
        self.assertEqual(len(grid_widget.cards), 15)
        self.assertIn("facepalm", grid_widget.cards)
        custom_card = grid_widget.cards["facepalm"]
        self.assertTrue(hasattr(custom_card, "delete_btn"))
        self.assertTrue(custom_card.is_calibrated)

        # Delete custom reaction
        self.registry.delete("facepalm")
        grid_widget.reload_grid()
        self.assertEqual(len(grid_widget.cards), 14)
        self.assertNotIn("facepalm", grid_widget.cards)

    def test_rebind_gesture_on_builtin_card(self):
        """Verifies re-binding a built-in card updates its badge and state."""
        grid_widget = AssetGridWidget(registry=self.registry)
        heart_card = grid_widget.cards["heart"]
        self.assertFalse(heart_card.is_calibrated)

        # Calibrate heart in registry
        heart_gesture = self.registry.get("heart")
        heart_gesture.set_signature(self.synthetic_sig)
        self.registry.add_or_update(heart_gesture)

        # Refresh cards
        grid_widget.refresh_cards()
        self.assertTrue(heart_card.is_calibrated)
        self.assertEqual(heart_card.badge_label.text(), "✨")


if __name__ == "__main__":
    unittest.main()
