"""
Automated integration test for app.py and MainWindow startup lifecycle.
"""
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from engine import VisionWorker
from ui import MainWindow, DARK_THEME_QSS

def test_app_integration():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME_QSS)

    worker = VisionWorker(camera_index=0, enable_vcam=False)
    window = MainWindow(worker=worker)
    window.show()

    # Validate window and child components
    assert window.isVisible(), "MainWindow should be visible"
    assert window.video_widget is not None, "VideoWidget must be initialized"
    assert window.asset_grid is not None, "AssetGrid must be initialized"
    assert len(window.asset_grid.cards) == 14, "All 14 reaction cards must be in grid"
    assert window.vcam_badge is not None, "Virtual Camera status badge must exist"
    assert window.cam_combo.count() >= 3, "Camera selector must list at least 3 cameras"
    print("[OK] MainWindow component validation passed")

    def on_timeout():
        print("[OK] Timeout reached, testing clean application shutdown...")
        window.exit_application()
        app.quit()

    QTimer.singleShot(1500, on_timeout)
    app.exec()

    print("[OK] Full App Integration Test PASSED cleanly!")

if __name__ == "__main__":
    test_app_integration()
