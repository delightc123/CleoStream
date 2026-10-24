"""
Interactive 3-Second Hand Gesture Calibration Wizard Modal.
Visualizes live hand skeletal landmarks, manages countdown and multi-frame sampling,
verifies gesture stability (variance threshold), and produces an aggregated HandSignature.
"""
from typing import List, Optional
import numpy as np

from PySide6.QtCore import Qt, Signal, Slot, QRect, QTimer
from PySide6.QtGui import QPainter, QImage, QColor, QFont, QPen, QBrush
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QFrame, QWidget
)

from engine.gesture_matcher import (
    HandSignature,
    extract_hand_signature,
    aggregate_signatures,
    FINGER_EXTENDED,
    FINGER_CURLED,
    FINGER_HALF,
    ANCHOR_FREE,
    ANCHOR_PINCHING_NOSE,
    ANCHOR_OVER_MOUTH,
    ANCHOR_UNDER_CHIN,
    ANCHOR_NEAR_HEAD,
)

# Standard MediaPipe 21-point Hand Skeleton Topology
HAND_CONNECTIONS = [
    # Thumb
    (0, 1), (1, 2), (2, 3), (3, 4),
    # Index
    (0, 5), (5, 6), (6, 7), (7, 8),
    # Middle
    (5, 9), (9, 10), (10, 11), (11, 12),
    # Ring
    (9, 13), (13, 14), (14, 15), (15, 16),
    # Pinky
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
]

STATE_IDLE = "IDLE"
STATE_COUNTDOWN = "COUNTDOWN"
STATE_SAMPLING = "SAMPLING"
STATE_CONFIRMED = "CONFIRMED"
STATE_FAILED = "FAILED"

TOTAL_SAMPLES_NEEDED = 30
MAX_STABILITY_VARIANCE = 0.05


class GestureCanvas(QWidget):
    """
    Renders camera video frame with high-visibility neon green hand skeleton wireframes
    and countdown overlays.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setMinimumSize(480, 270)
        self._frame: Optional[QImage] = None
        self._hands: list = []
        self._countdown_text: str = ""
        self._status_text: str = ""

    def set_frame(self, image: QImage):
        self._frame = image
        self.update()

    def set_hands(self, hands: list):
        self._hands = hands
        self.update()

    def set_countdown(self, text: str):
        self._countdown_text = text
        self.update()

    def set_status_overlay(self, text: str):
        self._status_text = text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # 1. Dark canvas backdrop
        painter.fillRect(self.rect(), QColor(14, 14, 20))

        if not self._frame or self._frame.isNull():
            painter.setPen(QColor(100, 116, 139))
            painter.setFont(QFont("Segoe UI", 12))
            painter.drawText(self.rect(), Qt.AlignCenter, "Waiting for Camera Feed...")
            return

        # 2. Letterbox calculations
        img_w = self._frame.width()
        img_h = self._frame.height()
        widget_w = self.width()
        widget_h = self.height()

        scale = min(widget_w / img_w, widget_h / img_h)
        target_w = int(img_w * scale)
        target_h = int(img_h * scale)
        target_x = (widget_w - target_w) // 2
        target_y = (widget_h - target_h) // 2

        dest_rect = QRect(target_x, target_y, target_w, target_h)
        painter.drawImage(dest_rect, self._frame)

        # 3. Draw Hand Landmark Skeleton Wireframes
        if self._hands:
            bone_pen = QPen(QColor(0, 230, 118, 220), 3)
            bone_pen.setCapStyle(Qt.RoundCap)
            bone_pen.setJoinStyle(Qt.RoundJoin)

            joint_brush = QBrush(QColor(0, 255, 127))
            joint_pen = QPen(QColor(5, 46, 22), 1.5)

            for h in self._hands:
                pts = getattr(h, "pts", None)
                if pts is None or len(pts) < 21:
                    continue

                # Map points to screen letterbox coordinates
                screen_pts = []
                for p in pts:
                    sx = target_x + p[0] * scale
                    sy = target_y + p[1] * scale
                    screen_pts.append((sx, sy))

                # Draw Bones
                painter.setPen(bone_pen)
                for i1, i2 in HAND_CONNECTIONS:
                    p1 = screen_pts[i1]
                    p2 = screen_pts[i2]
                    painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))

                # Draw Joints
                painter.setPen(joint_pen)
                painter.setBrush(joint_brush)
                for pt in screen_pts:
                    painter.drawEllipse(int(pt[0] - 4), int(pt[1] - 4), 8, 8)

        # 4. Draw Radial Countdown Overlay
        if self._countdown_text:
            center_x = widget_w // 2
            center_y = widget_h // 2
            radius = 55

            # Circular glow pill
            painter.setPen(QPen(QColor(0, 230, 118, 240), 4))
            painter.setBrush(QBrush(QColor(15, 23, 42, 210)))
            painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

            # Text
            painter.setPen(QColor(248, 250, 252))
            font = QFont("Segoe UI", 32, QFont.Bold)
            painter.setFont(font)
            painter.drawText(
                QRect(center_x - radius, center_y - radius, radius * 2, radius * 2),
                Qt.AlignCenter,
                self._countdown_text
            )

        # 5. Upper Status Banner
        if self._status_text:
            banner_rect = QRect(target_x + 16, target_y + 16, 220, 30)
            painter.setBrush(QBrush(QColor(15, 23, 42, 210)))
            painter.setPen(QPen(QColor(51, 65, 85), 1))
            painter.drawRoundedRect(banner_rect, 6, 6)

            painter.setPen(QColor(52, 211, 153))
            painter.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
            painter.drawText(banner_rect, Qt.AlignCenter, self._status_text)


class GestureRecorderDialog(QDialog):
    """
    Modal wizard dialog guiding the user to record or calibrate a custom hand gesture.
    """
    gesture_recorded = Signal(object)  # Emits HandSignature upon saving

    def __init__(self, gesture_name: str = "New Gesture", parent=None):
        super().__init__(parent)
        self.gesture_name = gesture_name
        self.setWindowTitle(f"Calibrate Gesture — {gesture_name}")
        self.setFixedSize(680, 640)
        self.setModal(True)

        self.state = STATE_IDLE
        self.countdown_remaining = 3
        self.samples: List[HandSignature] = []
        self.latest_face = None
        self.latest_hands: list = []
        self.calibrated_signature: Optional[HandSignature] = None
        self.calibrated_variance: float = 0.0

        # Countdown Timer
        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(1000)
        self.countdown_timer.timeout.connect(self._on_countdown_tick)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header Title
        title_label = QLabel(f"✋ Calibrate Hand Gesture: {self.gesture_name}")
        title_label.setObjectName("AppTitle")
        title_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(title_label)

        # Instruction Subtitle
        desc = QLabel(
            "Hold your hand in the desired pose. When ready, click 'Start Capture' "
            "and hold your hand steady through the 3-second countdown."
        )
        desc.setStyleSheet("color: #94a3b8; font-size: 12px; margin-bottom: 4px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Video Canvas
        self.canvas = GestureCanvas(self)
        layout.addWidget(self.canvas, stretch=1)

        # Status & Telemetry Card
        self.status_frame = QFrame()
        self.status_frame.setStyleSheet(
            "background-color: #161622; border: 1px solid #28283c; border-radius: 8px; padding: 10px;"
        )
        status_layout = QVBoxLayout(self.status_frame)
        status_layout.setSpacing(6)

        header_row = QHBoxLayout()
        self.status_label = QLabel("Ready to capture")
        self.status_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #38bdf8;")
        header_row.addWidget(self.status_label)

        self.stability_label = QLabel("")
        self.stability_label.setStyleSheet("font-size: 11px; color: #94a3b8;")
        self.stability_label.setAlignment(Qt.AlignRight)
        header_row.addWidget(self.stability_label)
        status_layout.addLayout(header_row)

        # Sampling Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            "QProgressBar { background-color: #1e1e2d; border-radius: 4px; }"
            "QProgressBar::chunk { background-color: #10b981; border-radius: 4px; }"
        )
        status_layout.addWidget(self.progress_bar)

        # Finger State Summary Pill
        self.finger_summary_label = QLabel("Awaiting hand...")
        self.finger_summary_label.setStyleSheet("color: #cbd5e1; font-size: 11px; font-family: monospace;")
        status_layout.addWidget(self.finger_summary_label)

        layout.addWidget(self.status_frame)

        # Buttons Row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        btn_layout.addStretch(1)

        self.start_btn = QPushButton("Start 3s Capture")
        self.start_btn.setObjectName("PrimaryBtn")
        self.start_btn.clicked.connect(self._on_start_clicked)
        btn_layout.addWidget(self.start_btn)

        self.save_btn = QPushButton("Save Gesture")
        self.save_btn.setStyleSheet(
            "QPushButton { background-color: #059669; color: white; font-weight: 600; padding: 8px 18px; border-radius: 6px; }"
            "QPushButton:hover { background-color: #10b981; }"
            "QPushButton:disabled { background-color: #27273a; color: #64748b; }"
        )
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._on_save_clicked)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)

    @Slot(QImage)
    def update_frame(self, image: QImage):
        """Receives live video frame."""
        self.canvas.set_frame(image)

    @Slot(list, object)
    def update_tracking(self, hands: list, face: object):
        """Receives live MediaPipe hand and face landmark detections."""
        self.latest_hands = hands
        self.latest_face = face
        self.canvas.set_hands(hands)

        if not hands:
            if self.state == STATE_IDLE:
                self.canvas.set_status_overlay("NO HAND DETECTED")
                self.finger_summary_label.setText("No hand in view. Show hand to camera.")
            elif self.state == STATE_COUNTDOWN:
                self.canvas.set_status_overlay("HAND LOST!")
            return

        # Hand detected
        h0 = hands[0]
        pts = getattr(h0, "pts", None)
        if pts is None or len(pts) < 21:
            return

        live_sig = extract_hand_signature(pts, face=face)

        # Live feedback during IDLE or CONFIRMED
        if self.state in (STATE_IDLE, STATE_CONFIRMED):
            self.canvas.set_status_overlay(f"Hand Ready ({live_sig.anchor})")
            self._update_finger_states_label(live_sig.finger_states, live_sig.anchor)

        # Sampling Mode: collect frames
        elif self.state == STATE_SAMPLING:
            self.samples.append(live_sig)
            progress_pct = int((len(self.samples) / TOTAL_SAMPLES_NEEDED) * 100)
            self.progress_bar.setValue(progress_pct)
            self.status_label.setText(f"Sampling gesture ({len(self.samples)}/{TOTAL_SAMPLES_NEEDED})...")
            self._update_finger_states_label(live_sig.finger_states, live_sig.anchor)

            if len(self.samples) >= TOTAL_SAMPLES_NEEDED:
                self._finish_sampling()

    def _update_finger_states_label(self, states: dict, anchor: str):
        """Renders compact summary of finger articulacy and spatial anchor."""
        sym = {FINGER_EXTENDED: "UP", FINGER_CURLED: "DOWN", FINGER_HALF: "HALF"}
        fingers_text = " ".join([
            f"T:{sym.get(states.get('thumb'), '-')}",
            f"I:{sym.get(states.get('index'), '-')}",
            f"M:{sym.get(states.get('middle'), '-')}",
            f"R:{sym.get(states.get('ring'), '-')}",
            f"P:{sym.get(states.get('pinky'), '-')}",
        ])
        anchor_text = anchor.replace("ANCHOR_", "").replace("_", " ").title()
        self.finger_summary_label.setText(f"Fingers: {fingers_text} | Anchor: {anchor_text}")

    def _on_start_clicked(self):
        """Starts the 3-second countdown state machine."""
        self.state = STATE_COUNTDOWN
        self.countdown_remaining = 3
        self.samples.clear()
        self.progress_bar.setValue(0)
        self.save_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.stability_label.setText("")

        self.canvas.set_countdown(str(self.countdown_remaining))
        self.status_label.setText(f"Get ready... {self.countdown_remaining}s")
        self.status_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #fbbf24;")
        self.countdown_timer.start()

    def _on_countdown_tick(self):
        self.countdown_remaining -= 1
        if self.countdown_remaining > 0:
            self.canvas.set_countdown(str(self.countdown_remaining))
            self.status_label.setText(f"Get ready... {self.countdown_remaining}s")
        else:
            self.countdown_timer.stop()
            self.canvas.set_countdown("HOLD!")
            self.status_label.setText("Hold steady! Recording gesture...")
            self.status_label.setStyleSheet("font-weight: 700; font-size: 13px; color: #34d399;")
            self.state = STATE_SAMPLING

    def _finish_sampling(self):
        """Evaluates collected samples for stability and computes aggregated signature."""
        self.canvas.set_countdown("")
        self.start_btn.setEnabled(True)
        self.start_btn.setText("Re-record")

        try:
            aggregated, variance = aggregate_signatures(self.samples)
            self.calibrated_signature = aggregated
            self.calibrated_variance = variance

            if variance <= MAX_STABILITY_VARIANCE:
                # Stability Check: Passed!
                self.state = STATE_CONFIRMED
                self.status_label.setText("✓ Gesture Calibrated Successfully!")
                self.status_label.setStyleSheet("font-weight: 700; font-size: 13px; color: #34d399;")
                self.stability_label.setText(f"Stability: Excellent (Var: {variance:.5f})")
                self.save_btn.setEnabled(True)
            else:
                # Stability Check: Failed (hand was shaking/moving)
                self.state = STATE_FAILED
                self.status_label.setText("⚠️ Hand moved during capture")
                self.status_label.setStyleSheet("font-weight: 700; font-size: 13px; color: #ef4444;")
                self.stability_label.setText(f"Instability: {variance:.4f} > {MAX_STABILITY_VARIANCE}")
                self.start_btn.setText("Retry")
                self.save_btn.setEnabled(False)

        except Exception as e:
            self.state = STATE_FAILED
            self.status_label.setText(f"Analysis Error: {e}")
            self.status_label.setStyleSheet("font-weight: 700; font-size: 13px; color: #ef4444;")
            self.start_btn.setText("Retry")
            self.save_btn.setEnabled(False)

    def _on_save_clicked(self):
        """Emits calibrated signature and closes dialog with accepted code."""
        if self.calibrated_signature is not None:
            self.gesture_recorded.emit(self.calibrated_signature)
            self.accept()

    def closeEvent(self, event):
        self.countdown_timer.stop()
        super().closeEvent(event)
