"""
React in Meetings — Desktop UI Package
"""
from .styles import DARK_THEME_QSS
from .video_widget import VideoWidget
from .asset_grid import AssetGridWidget, ReactionCard
from .calibration_dialog import CalibrationDialog
from .tray import TrayController, create_tray_icon
from .main_window import MainWindow
from .update_dialog import UpdateDialog

# Convenience alias
SystemTray = TrayController

__all__ = [
    "DARK_THEME_QSS",
    "VideoWidget",
    "AssetGridWidget",
    "ReactionCard",
    "CalibrationDialog",
    "TrayController",
    "SystemTray",
    "create_tray_icon",
    "MainWindow",
    "UpdateDialog",
]
