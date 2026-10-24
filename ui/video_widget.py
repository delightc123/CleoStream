"""
High-performance video canvas widget for rendering real-time camera frames
with aspect ratio preservation and letterboxing.
"""
from PySide6.QtCore import Qt, QRect, Slot
from PySide6.QtGui import QPainter, QImage, QColor, QFont
from PySide6.QtWidgets import QWidget


class VideoWidget(QWidget):
    """
    Renders incoming QImages via QPainter with zero memory thrashing,
    proper letterboxing, and high frame-rate stability.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setMinimumSize(480, 270)
        self._current_frame = None
        self._fps = 0.0
        self._active_reaction = None
        self._paused = False
        self._status_text = "Initializing Camera..."

    @Slot(QImage)
    def update_frame(self, image: QImage):
        """Receives new video frame from VisionWorker."""
        self._current_frame = image
        self.update()

    @Slot(dict)
    def update_telemetry(self, telemetry: dict):
        """Receives metrics update from VisionWorker."""
        self._fps = float(telemetry.get("fps", 0.0))
        self._active_reaction = telemetry.get("reaction") or telemetry.get("shown")
        self._paused = bool(telemetry.get("paused", False))
        if not telemetry.get("face_detected"):
            self._status_text = "Searching for face..."
        elif self._paused:
            self._status_text = "Reactions Paused"
        else:
            self._status_text = "Active"
        self.update()

    @Slot(float)
    def set_fps(self, fps: float):
        """Sets the FPS display and triggers repaint."""
        self._fps = float(fps)
        self.update()

    @Slot(str)
    def set_active_reaction(self, reaction: str):
        """Sets the active reaction banner and triggers repaint."""
        self._active_reaction = reaction if reaction else None
        self.update()

    @Slot(bool)
    def set_paused(self, paused: bool):
        """Sets paused state and triggers repaint."""
        self._paused = bool(paused)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Clear background to dark surface
        painter.fillRect(self.rect(), QColor(14, 14, 18))

        if self._current_frame and not self._current_frame.isNull():
            # Calculate aspect-ratio preserving dimensions (letterboxing)
            img_w = self._current_frame.width()
            img_h = self._current_frame.height()
            widget_w = self.width()
            widget_h = self.height()

            scale = min(widget_w / img_w, widget_h / img_h)
            target_w = int(img_w * scale)
            target_h = int(img_h * scale)
            target_x = (widget_w - target_w) // 2
            target_y = (widget_h - target_h) // 2

            dest_rect = QRect(target_x, target_y, target_w, target_h)
            painter.drawImage(dest_rect, self._current_frame)

            # Draw upper-left live telemetry pill
            pill_rect = QRect(target_x + 12, target_y + 12, 130, 28)
            painter.setBrush(QColor(18, 18, 24, 210))
            painter.setPen(QColor(45, 45, 60))
            painter.drawRoundedRect(pill_rect, 6, 6)

            painter.setPen(QColor(52, 211, 153))
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            painter.drawText(target_x + 22, target_y + 30, f"{self._fps:0.1f} FPS")

            # Draw upper-right status pill (Muted vs Active Reaction)
            if self._paused:
                label_text = "⏸ REACTIONS MUTED (CLEAN CAM)"
                pill_w = len(label_text) * 7 + 22
                react_rect = QRect(target_x + target_w - pill_w - 12, target_y + 12, pill_w, 28)
                painter.setBrush(QColor(180, 83, 9, 235))
                painter.setPen(QColor(245, 158, 11))
                painter.drawRoundedRect(react_rect, 6, 6)
                painter.setPen(QColor(255, 255, 255))
                painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
                painter.drawText(react_rect, Qt.AlignCenter, label_text)
            elif self._active_reaction:
                label_text = f"🔥 {self._active_reaction.upper()}"
                pill_w = len(label_text) * 9 + 20
                react_rect = QRect(target_x + target_w - pill_w - 12, target_y + 12, pill_w, 28)
                painter.setBrush(QColor(79, 70, 229, 230))
                painter.setPen(QColor(129, 140, 248))
                painter.drawRoundedRect(react_rect, 6, 6)
                painter.setPen(QColor(255, 255, 255))
                painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
                painter.drawText(react_rect, Qt.AlignCenter, label_text)
        else:
            # Standby screen when camera is idle/initializing
            painter.setPen(QColor(148, 163, 184))
            painter.setFont(QFont("Segoe UI", 13, QFont.Medium))
            painter.drawText(self.rect(), Qt.AlignCenter, self._status_text)
