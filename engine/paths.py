"""
React in Meetings — Path & Resource Resolver
Supports standard Python source trees and frozen PyInstaller bundles.
"""
import os
import sys


def get_root_dir() -> str:
    """Returns directory containing application resources (models, assets)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_app_data_dir() -> str:
    """Returns writable directory for user settings and backups."""
    if getattr(sys, "frozen", False):
        # When installed in Program Files, write user settings to %APPDATA%\ReactInMeetings
        appdata = os.environ.get("APPDATA")
        if appdata:
            path = os.path.join(appdata, "ReactInMeetings")
            os.makedirs(path, exist_ok=True)
            return path
        return os.path.dirname(sys.executable)
    return get_root_dir()


ROOT_DIR = get_root_dir()
APP_DATA_DIR = get_app_data_dir()
