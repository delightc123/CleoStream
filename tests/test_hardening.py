"""
Automated hardening test suite verifying failure recovery, corrupted asset guards,
camera disconnect resilience, and clean shutdown.
"""
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from engine.compositor import load_asset, placeholder, overlay
from ui.asset_grid import validate_image_file
from engine import VisionWorker
from ui import MainWindow, DARK_THEME_QSS


def test_corrupted_asset_guard():
    print("Testing corrupted asset guard...")
    # Create corrupted dummy file
    corrupt_file = os.path.join(ROOT_DIR, "tests", "corrupt.png")
    with open(corrupt_file, "wb") as f:
        f.write(b"NOT_A_VALID_PNG_FILE_DATA_CORRUPTED")

    try:
        # 1. validate_image_file must reject it
        assert not validate_image_file(corrupt_file), "validate_image_file must reject corrupted bytes"
        print("[OK] validate_image_file successfully rejected corrupted file")

        # 2. load_asset must fallback to placeholder without crashing
        fake_asset = load_asset("non_existent_pose_12345")
        assert fake_asset is not None
        assert len(fake_asset.frames) >= 1
        print("[OK] Missing asset safely returned placeholder Asset")

        # 3. overlay must handle None safely
        result = overlay(None, None, 0, 0)
        assert result is None
        print("[OK] overlay handled None arguments safely")
    finally:
        if os.path.isfile(corrupt_file):
            os.remove(corrupt_file)


def test_invalid_camera_resilience():
    print("\nTesting camera resilience with invalid camera index 99...")
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME_QSS)

    # Use invalid camera index 99
    worker = VisionWorker(camera_index=99, enable_vcam=False)
    camera_errors = []
    worker.camera_status_changed.connect(lambda connected, msg: camera_errors.append((connected, msg)))

    window = MainWindow(worker=worker)
    worker.set_camera_index(99)
    window.show()

    def on_timeout():
        print(f"[OK] Camera status events captured: {len(camera_errors)}")
        # Check that error was captured
        has_error = any(not conn for conn, _ in camera_errors)
        assert has_error, "Expected camera error for invalid camera index 99"
        print("[OK] Invalid camera index was caught and non-fatal")
        window.exit_application()
        app.quit()

    worker.start()
    QTimer.singleShot(2000, on_timeout)
    app.exec()
    print("[OK] Camera resilience test PASSED cleanly!")


def test_dual_layer_asset_resolution():
    print("\nTesting dual-layer asset resolution...")
    from engine.compositor import find_asset_file
    from engine.paths import ROOT_DIR, APP_DATA_DIR

    # 1. Factory fallback works
    factory_heart = find_asset_file("heart")
    assert factory_heart is not None and os.path.isfile(factory_heart), "Factory asset must resolve"
    print(f"[OK] Resolved factory asset: {os.path.basename(factory_heart)}")

    # 2. User directory override takes precedence
    user_assets_dir = os.path.join(APP_DATA_DIR, "assets")
    os.makedirs(user_assets_dir, exist_ok=True)
    custom_override = os.path.join(user_assets_dir, "test_custom_pose.png")
    try:
        with open(custom_override, "wb") as f:
            f.write(b"CUSTOM_PNG")
        resolved = find_asset_file("test_custom_pose")
        assert resolved == custom_override, f"Expected {custom_override}, got {resolved}"
        print("[OK] User override in APP_DATA_DIR/assets successfully takes precedence")
    finally:
        if os.path.isfile(custom_override):
            os.remove(custom_override)


def run_all_hardening_tests():
    test_corrupted_asset_guard()
    test_dual_layer_asset_resolution()
    test_invalid_camera_resilience()
    print("\nAll Phase 5 Hardening & Resilience tests PASSED successfully!")


if __name__ == "__main__":
    run_all_hardening_tests()
