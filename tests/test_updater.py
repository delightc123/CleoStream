"""
Unit and integration test for engine.updater and UpdateDialog
"""
import sys
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from engine.updater import parse_version, is_newer_version, check_for_updates_sync
from engine.version import __version__
from ui.update_dialog import UpdateDialog
from PySide6.QtWidgets import QApplication

def test_version_parsing():
    print("Testing semantic version parsing...")
    assert parse_version("1.0.0") == (1, 0, 0)
    assert parse_version("v1.2.3") == (1, 2, 3)
    assert parse_version("v2.0.0-beta.1") == (2, 0, 0, 1)

    assert is_newer_version("v1.0.1", "1.0.0") is True
    assert is_newer_version("v1.0.0", "1.0.0") is False
    assert is_newer_version("v0.9.9", "1.0.0") is False
    assert is_newer_version("v2.0.0", "1.9.9") is True
    print("[OK] Version comparison logic PASSED")

def test_update_dialog_instantiation():
    print("Testing UpdateDialog UI instantiation...")
    app = QApplication.instance() or QApplication(sys.argv)
    dummy_info = {
        "has_update": True,
        "current_version": "1.0.0",
        "remote_version": "v1.0.1",
        "notes": "### New Features\n- Added cool meme reactions\n- Faster startup",
        "html_url": "https://github.com/delightc123/React-in-Meetings/releases/tag/v1.0.1",
        "installer_url": "",
    }
    dialog = UpdateDialog(dummy_info)
    assert dialog.windowTitle().startswith("Update Available")
    assert "Added cool meme reactions" in dialog.notes_view.toPlainText()
    assert dialog.btn_update.text() == "Download & Update Now"
    print("[OK] UpdateDialog instantiated successfully")

def test_updater_network_graceful_handling():
    print("Testing update check on repository (graceful 404/fallback)...")
    res = check_for_updates_sync()
    print(f"[OK] check_for_updates_sync returned safely: has_update={res.get('has_update')}, error={res.get('error')}")

if __name__ == "__main__":
    test_version_parsing()
    test_update_dialog_instantiation()
    test_updater_network_graceful_handling()
    print("\nAll Updater Unit Tests PASSED successfully!")
