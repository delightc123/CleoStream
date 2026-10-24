"""
System Tray controller with Windows notification and background meeting streaming.
"""
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PySide6.QtWidgets import QSystemTrayIcon, QMenu


def create_tray_icon():
    """Generates a crisp programmatic 64x64 tray icon."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Indigo rounded badge
    painter.setBrush(QColor(79, 70, 229))
    painter.setPen(QColor(129, 140, 248))
    painter.drawRoundedRect(4, 4, 56, 56, 14, 14)

    # Smiley / Camera icon text
    painter.setFont(QFont("Segoe UI Emoji", 28))
    painter.setPen(QColor(255, 255, 255))
    painter.drawText(pixmap.rect(), 0x0084, "⚡")
    painter.end()
    return QIcon(pixmap)


class TrayController(QObject):
    """
    Manages system tray lifecycle, context menu, and minimize-to-tray notifications.
    """
    show_window_requested = Signal()
    quit_requested = Signal()
    recalibrate_requested = Signal()
    check_updates_requested = Signal()
    pause_toggled = Signal(bool)
    vcam_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._notified_minimize = False

        self.tray_icon = QSystemTrayIcon(create_tray_icon(), parent)
        self.tray_icon.setToolTip("CleoStream — Meme Reaction Camera")

        # Context Menu
        self.menu = QMenu()
        self.menu.setStyleSheet("""
            QMenu {
                background-color: #1a1a24;
                color: #f1f5f9;
                border: 1px solid #333348;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #4f46e5;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #2e2e40;
                margin: 4px 8px;
            }
        """)

        self.show_action = self.menu.addAction("Show CleoStream")
        self.show_action.triggered.connect(self.show_window_requested.emit)

        self.menu.addSeparator()

        self.pause_action = self.menu.addAction("Pause Reactions")
        self.pause_action.setCheckable(True)
        self.pause_action.toggled.connect(self.pause_toggled.emit)

        self.vcam_action = self.menu.addAction("OBS Virtual Camera Active")
        self.vcam_action.setCheckable(True)
        self.vcam_action.setChecked(True)
        self.vcam_action.toggled.connect(self.vcam_toggled.emit)

        self.calib_action = self.menu.addAction("Recalibrate Face...")
        self.calib_action.triggered.connect(self.recalibrate_requested.emit)

        self.update_action = self.menu.addAction("Check for Updates...")
        self.update_action.triggered.connect(self.check_updates_requested.emit)

        self.menu.addSeparator()

        self.quit_action = self.menu.addAction("Quit")
        self.quit_action.triggered.connect(self.quit_requested.emit)

        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.show_window_requested.emit()

    def notify_minimized(self):
        """Displays a one-time balloon tip when minimized to tray."""
        if not self._notified_minimize and self.tray_icon.isSystemTrayAvailable():
            self.tray_icon.showMessage(
                "CleoStream",
                "App minimized to tray. Your video stream is still active in your meeting.",
                QSystemTrayIcon.Information,
                3000
            )
            self._notified_minimize = True

    @Slot(bool, str)
    def update_vcam_status(self, active: bool, device_name: str):
        self.vcam_action.setChecked(active)
        self.vcam_action.setText(f"Virtual Camera: {'Active' if active else 'Offline'}")
