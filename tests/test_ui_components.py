"""
Automated unit test for UI presentation components (VideoWidget, AssetGrid, CalibrationDialog, Tray).
"""
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage
from ui import VideoWidget, AssetGridWidget, CalibrationDialog, GestureRecorderDialog, TrayController, DARK_THEME_QSS
from engine.decision import POSES

def test_ui_components():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME_QSS)

    # 1. Test VideoWidget
    video = VideoWidget()
    test_img = QImage(640, 480, QImage.Format_BGR888)
    test_img.fill(0)
    video.update_frame(test_img)
    video.update_telemetry({"fps": 30.0, "shown": "heart", "face_detected": True})
    assert video._fps == 30.0
    assert video._active_reaction == "heart"

    # Test direct setters
    video.set_fps(45.5)
    assert video._fps == 45.5
    video.set_active_reaction("cheer")
    assert video._active_reaction == "cheer"
    video.set_active_reaction(None)
    assert video._active_reaction is None
    video.set_paused(True)
    assert video._paused is True
    video.set_paused(False)
    assert video._paused is False
    print("[OK] VideoWidget verified (telemetry + direct setters + paused state)")

    # 2. Test AssetGridWidget
    grid = AssetGridWidget()
    assert len(grid.cards) == len(POSES), f"Expected {len(POSES)} cards, got {len(grid.cards)}"
    assert "heart" in grid.cards
    assert "dance" in grid.cards
    print("[OK] AssetGridWidget verified with all 14 reaction cards")

    # 3. Test CalibrationDialog
    calib_dialog = CalibrationDialog()
    calib_dialog.update_progress(0.5, 15, True)
    assert calib_dialog.progress_bar.value() == 50
    print("[OK] CalibrationDialog verified")

    # 4. Test TrayController
    tray = TrayController()
    assert tray.tray_icon is not None
    assert len(tray.menu.actions()) >= 4
    print("[OK] TrayController verified")

    # 5. Test GestureRecorderDialog
    recorder = GestureRecorderDialog(gesture_name="Test Gesture")
    assert recorder.state == "IDLE"
    assert recorder.save_btn.isEnabled() is False
    print("[OK] GestureRecorderDialog verified")

    print("\nAll Phase 3 UI Component unit tests PASSED successfully!")

if __name__ == "__main__":
    test_ui_components()
