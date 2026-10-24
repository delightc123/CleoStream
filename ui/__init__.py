"""
CleoStream — Desktop UI Package
"""
from .styles import DARK_THEME_QSS
from .video_widget import VideoWidget
from .asset_grid import AssetGridWidget, ReactionCard, AddReactionCard
from .calibration_dialog import CalibrationDialog
from .gesture_recorder_dialog import GestureRecorderDialog
from .add_reaction_dialog import AddReactionDialog
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
    "AddReactionCard",
    "CalibrationDialog",
    "GestureRecorderDialog",
    "AddReactionDialog",
    "TrayController",
    "SystemTray",
    "create_tray_icon",
    "MainWindow",
    "UpdateDialog",
]
