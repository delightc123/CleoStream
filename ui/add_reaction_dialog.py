"""
Add Reaction Dialog Modal Wizard.
Enables users to name a new reaction, select/drag an image or animated GIF asset,
and calibrate a 3-second hand gesture trigger using GestureRecorderDialog.
"""
import os
import re
import shutil
from typing import Optional
from PIL import Image

from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QFileDialog, QMessageBox, QWidget
)

from engine.paths import APP_DATA_DIR, ROOT_DIR
from engine.custom_gestures import CustomGesture, CustomGestureRegistry
from engine.gesture_matcher import HandSignature
from ui.gesture_recorder_dialog import GestureRecorderDialog

USER_ASSETS_DIR = os.path.join(APP_DATA_DIR, "assets")


def slugify_reaction_id(name: str) -> str:
    """Converts a display name into a clean alphanumeric snake_case ID."""
    clean = re.sub(r"[^\w\s-]", "", name.lower()).strip()
    slug = re.sub(r"[\s-]+", "_", clean)
    return slug or "custom_reaction"


def validate_asset_file(filepath: str) -> bool:
    """Verifies that the file exists and is a valid decodable image or GIF."""
    if not filepath or not os.path.isfile(filepath):
        return False
    try:
        with Image.open(filepath) as img:
            img.verify()
        with Image.open(filepath) as img:
            img.load()
        return True
    except Exception:
        return False


class AddReactionDialog(QDialog):
    """
    Modal wizard to create and register a new custom reaction.
    """
    reaction_created = Signal(object)  # Emits CustomGesture

    def __init__(self, registry: Optional[CustomGestureRegistry] = None, worker=None, parent=None):
        super().__init__(parent)
        self.registry = registry or CustomGestureRegistry()
        self.worker = worker
        self.selected_asset_path: Optional[str] = None
        self.recorded_signature: Optional[HandSignature] = None

        self.setWindowTitle("Create New Reaction")
        self.setFixedSize(520, 560)
        self.setModal(True)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        # Header Title
        title = QLabel("✨ Add Custom Reaction")
        title.setObjectName("AppTitle")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #f8fafc;")
        layout.addWidget(title)

        subtitle = QLabel("Create a meme reaction and bind it to your unique hand gesture.")
        subtitle.setStyleSheet("color: #94a3b8; font-size: 12px; margin-bottom: 2px;")
        layout.addWidget(subtitle)

        # 1. Reaction Name Input
        name_box = QVBoxLayout()
        name_box.setSpacing(4)
        name_label = QLabel("Reaction Name")
        name_label.setStyleSheet("font-weight: 600; color: #cbd5e1; font-size: 12px;")
        name_box.addWidget(name_label)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Victory Sign, Facepalm, Wow")
        self.name_input.textChanged.connect(self._validate_inputs)
        name_box.addWidget(self.name_input)
        layout.addLayout(name_box)

        # 2. Asset Picker & Drop Target
        asset_box = QVBoxLayout()
        asset_box.setSpacing(4)
        asset_label = QLabel("Reaction Image or GIF Asset")
        asset_label.setStyleSheet("font-weight: 600; color: #cbd5e1; font-size: 12px;")
        asset_box.addWidget(asset_label)

        # Thumbnail / Drop Frame
        self.thumb_frame = QFrame()
        self.thumb_frame.setStyleSheet(
            "background-color: #14141e; border: 1px dashed #3a3a52; border-radius: 8px;"
        )
        self.thumb_frame.setMinimumHeight(110)
        self.thumb_frame.setAcceptDrops(True)

        thumb_layout = QHBoxLayout(self.thumb_frame)
        self.thumb_preview = QLabel("Drop GIF or PNG here\nor click Browse")
        self.thumb_preview.setAlignment(Qt.AlignCenter)
        self.thumb_preview.setStyleSheet("color: #64748b; font-size: 11px;")
        thumb_layout.addWidget(self.thumb_preview, 1)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._on_browse_clicked)
        thumb_layout.addWidget(self.browse_btn)

        asset_box.addWidget(self.thumb_frame)
        layout.addLayout(asset_box)

        # 3. Gesture Calibration Card
        gesture_box = QVBoxLayout()
        gesture_box.setSpacing(6)

        g_header = QLabel("Hand Gesture Trigger")
        g_header.setStyleSheet("font-weight: 600; color: #cbd5e1; font-size: 12px;")
        gesture_box.addWidget(g_header)

        self.gesture_card = QFrame()
        self.gesture_card.setStyleSheet(
            "background-color: #161622; border: 1px solid #28283c; border-radius: 8px; padding: 10px;"
        )
        g_card_layout = QHBoxLayout(self.gesture_card)
        g_card_layout.setContentsMargins(12, 10, 12, 10)

        self.gesture_status_label = QLabel("⚠️ No gesture recorded yet")
        self.gesture_status_label.setStyleSheet("color: #f59e0b; font-weight: 500; font-size: 12px;")
        g_card_layout.addWidget(self.gesture_status_label, 1)

        self.record_btn = QPushButton("✋ Record Gesture (3s)...")
        self.record_btn.setStyleSheet(
            "QPushButton { background-color: #4f46e5; color: white; font-weight: 600; padding: 6px 14px; border-radius: 6px; }"
            "QPushButton:hover { background-color: #6366f1; }"
        )
        self.record_btn.clicked.connect(self._on_record_clicked)
        g_card_layout.addWidget(self.record_btn)

        gesture_box.addWidget(self.gesture_card)
        layout.addLayout(gesture_box)

        layout.addStretch(1)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        btn_layout.addStretch(1)

        self.create_btn = QPushButton("Create Reaction")
        self.create_btn.setObjectName("PrimaryBtn")
        self.create_btn.setEnabled(False)
        self.create_btn.clicked.connect(self._on_create_clicked)
        btn_layout.addWidget(self.create_btn)

        layout.addLayout(btn_layout)

    def _on_browse_clicked(self):
        """Opens file dialog for user to select reaction media."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Reaction Meme Asset",
            "",
            "Media Files (*.gif *.png *.jpg *.jpeg)"
        )
        if path:
            self._set_asset_path(path)

    def _set_asset_path(self, path: str):
        if not validate_asset_file(path):
            QMessageBox.warning(self, "Invalid File", "The selected file is not a valid image or GIF.")
            return

        self.selected_asset_path = os.path.abspath(path)
        pix = QPixmap(self.selected_asset_path)
        if not pix.isNull():
            scaled = pix.scaled(QSize(100, 80), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.thumb_preview.setPixmap(scaled)
        else:
            self.thumb_preview.setText(os.path.basename(path))

        self._validate_inputs()

    def _on_record_clicked(self):
        """Launches GestureRecorderDialog wired to live camera worker if present."""
        gesture_name = self.name_input.text().strip() or "Custom Gesture"
        recorder = GestureRecorderDialog(gesture_name=gesture_name, parent=self)

        # Connect live worker signals if available
        if self.worker is not None:
            self.worker.frame_ready.connect(recorder.update_frame)
            self.worker.hand_tracking_updated.connect(recorder.update_tracking)

        recorder.gesture_recorded.connect(self._on_gesture_calibrated)
        recorder.exec()

        if self.worker is not None:
            try:
                self.worker.frame_ready.disconnect(recorder.update_frame)
                self.worker.hand_tracking_updated.disconnect(recorder.update_tracking)
            except Exception:
                pass

    @Slot(object)
    def _on_gesture_calibrated(self, sig: HandSignature):
        """Receives calibrated signature from recorder modal."""
        self.recorded_signature = sig
        self.gesture_status_label.setText("✓ Gesture Calibrated (30 frames)")
        self.gesture_status_label.setStyleSheet("color: #10b981; font-weight: 600; font-size: 12px;")
        self.record_btn.setText("Re-record")
        self._validate_inputs()

    def set_recorded_signature_for_test(self, sig: HandSignature):
        """Direct test setter."""
        self._on_gesture_calibrated(sig)

    def _validate_inputs(self):
        """Ensures all 3 required elements are provided before allowing creation."""
        has_name = bool(self.name_input.text().strip())
        has_asset = bool(self.selected_asset_path and os.path.isfile(self.selected_asset_path))
        has_gesture = self.recorded_signature is not None

        self.create_btn.setEnabled(has_name and has_asset and has_gesture)

    def _on_create_clicked(self):
        """Creates and registers the custom gesture and copies the asset."""
        display_name = self.name_input.text().strip()
        base_slug = slugify_reaction_id(display_name)

        # Ensure unique ID in registry
        slug = base_slug
        idx = 2
        while self.registry.get(slug) is not None:
            slug = f"{base_slug}_{idx}"
            idx += 1

        # Copy asset into APP_DATA_DIR/assets/
        os.makedirs(USER_ASSETS_DIR, exist_ok=True)
        ext = os.path.splitext(self.selected_asset_path)[1].lower()
        dest_filename = f"{slug}{ext}"
        dest_path = os.path.join(USER_ASSETS_DIR, dest_filename)

        try:
            shutil.copy2(self.selected_asset_path, dest_path)
        except Exception as e:
            QMessageBox.critical(self, "File Error", f"Could not copy asset: {e}")
            return

        # Construct and persist CustomGesture
        custom_gesture = CustomGesture(
            id=slug,
            display_name=display_name,
            asset_file=dest_filename,
            is_builtin=False,
            enabled=True,
        )
        if self.recorded_signature is not None:
            custom_gesture.set_signature(self.recorded_signature)

        self.registry.add_or_update(custom_gesture)
        self.reaction_created.emit(custom_gesture)
        self.accept()
