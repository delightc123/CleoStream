"""
Interactive 7-second facial calibration wizard modal.
"""
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QFrame
)


class CalibrationDialog(QDialog):
    """
    Modal wizard guiding user through 7-second resting face calibration.
    """
    recalibrate_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resting Face Calibration")
        self.setFixedSize(460, 380)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header Title
        title = QLabel("Neutral Baseline Calibration")
        title.setObjectName("AppTitle")
        layout.addWidget(title)

        # Instructions
        desc = QLabel(
            "Sit how you normally sit, look directly at the webcam, and hold a bored, "
            "neutral resting face for 7 seconds.\n\n"
            "• Blinking is fine.\n"
            "• Do not talk, smile, or raise your eyebrows."
        )
        desc.setStyleSheet("color: #94a3b8; line-height: 1.4;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Status Pill Box
        self.status_frame = QFrame()
        self.status_frame.setObjectName("StatusFrame")
        self.status_frame.setStyleSheet(
            "background-color: #1a1a24; border: 1px solid #2e2e42; border-radius: 8px; padding: 12px;"
        )
        status_layout = QVBoxLayout(self.status_frame)
        status_layout.setSpacing(8)

        self.status_label = QLabel("Ready to calibrate")
        self.status_label.setStyleSheet("font-weight: 600; color: #f8fafc;")
        status_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        status_layout.addWidget(self.progress_bar)

        self.samples_label = QLabel("0 samples captured")
        self.samples_label.setStyleSheet("color: #64748b; font-size: 11px;")
        status_layout.addWidget(self.samples_label)

        layout.addWidget(self.status_frame)

        # Warnings / Results Box (Hidden initially)
        self.results_label = QLabel()
        self.results_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        self.results_label.setWordWrap(True)
        self.results_label.hide()
        layout.addWidget(self.results_label)

        layout.addStretch(1)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.action_btn = QPushButton("Start 7s Calibration")
        self.action_btn.setObjectName("PrimaryBtn")
        self.action_btn.clicked.connect(self._on_action_clicked)
        btn_layout.addWidget(self.action_btn)

        layout.addLayout(btn_layout)

    def _on_action_clicked(self):
        if self.action_btn.text() == "Start 7s Calibration" or self.action_btn.text() == "Retry":
            self.action_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)
            self.status_label.setText("Calibrating... Hold a bored face")
            self.status_label.setStyleSheet("font-weight: 600; color: #34d399;")
            self.results_label.hide()
            self.recalibrate_requested.emit()
        else:
            self.accept()

    @Slot(float, int, bool)
    def update_progress(self, progress: float, samples: int, face_seen: bool):
        pct = int(progress * 100)
        self.progress_bar.setValue(pct)
        status_face = "Face Detected" if face_seen else "NO FACE DETECTED"
        color = "#34d399" if face_seen else "#f59e0b"
        self.status_label.setText(f"Calibrating... ({status_face})")
        self.status_label.setStyleSheet(f"font-weight: 600; color: {color};")
        self.samples_label.setText(f"{samples} neutral frames captured")

    @Slot(object, list)
    def on_finished(self, baseline, warnings: list):
        self.cancel_btn.setEnabled(True)
        self.action_btn.setEnabled(True)
        self.progress_bar.setValue(100)

        if baseline is not None:
            self.status_label.setText("✓ Calibration Complete!")
            self.status_label.setStyleSheet("font-weight: 700; color: #34d399;")
            self.action_btn.setText("Done")

            report = [f"Successfully calibrated on {baseline.samples} frames."]
            if warnings:
                report.append("\n⚠️ Notes:")
                for w in warnings:
                    report.append(f"• {w}")
            else:
                report.append("\nNeutral baseline stored in calibration.json.")

            self.results_label.setText("\n".join(report))
            self.results_label.show()
        else:
            self.status_label.setText("Calibration Incomplete")
            self.status_label.setStyleSheet("font-weight: 700; color: #ef4444;")
            self.action_btn.setText("Retry")
            self.results_label.setText("Could not detect enough face frames. Please adjust lighting and retry.")
            self.results_label.show()
