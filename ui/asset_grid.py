"""
Meme reaction card grid and asset manager with drag-and-drop replacement,
corrupted file guard, automated original backup, dynamic custom reaction creation,
and interactive gesture re-binding.
"""
import os
import shutil
import time
from typing import Optional, Dict
from PIL import Image

from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QPixmap, QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QGridLayout, QFrame, QMessageBox
)

from engine.paths import ROOT_DIR, APP_DATA_DIR
from engine.compositor import find_asset_file
from engine.custom_gestures import CustomGesture, CustomGestureRegistry

FACTORY_ASSETS_DIR = os.path.join(ROOT_DIR, "assets")
USER_ASSETS_DIR = os.path.join(APP_DATA_DIR, "assets")
BACKUPS_DIR = os.path.join(APP_DATA_DIR, "backups")

POSE_DESCRIPTIONS = {
    "time_out": "Referee's T with hands",
    "heart": "Two hands forming heart",
    "cover_nose": "Hands covering mouth & nose",
    "crashing_out": "Hands on head + jaw open",
    "dance": "Hands up behind head",
    "nose_closed": "Pinch your nose shut",
    "flirty": "Index fingertip on lips",
    "hand_up": "Open palm raised beside head",
    "tongue_out": "Tongue extended",
    "open_mouth": "Dramatic gasp / jaw drop",
    "disgusted": "Scrunch nose or frown",
    "talking_to_wall": "Gesturing away from lens",
    "suspicious": "Turn head and squint",
    "spin": "Leave frame completely",
}


def validate_image_file(filepath: str) -> bool:
    """Verifies that the file exists and is a valid decodable image or animated GIF."""
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


class AddReactionCard(QFrame):
    """
    Dashed-border call-to-action card triggering the Add Reaction wizard.
    """
    add_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AddReactionCard")
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setMinimumSize(180, 160)
        self.setMaximumSize(240, 190)
        self.setStyleSheet(
            "QFrame#AddReactionCard {"
            "  background-color: #12121c;"
            "  border: 2px dashed #4f46e5;"
            "  border-radius: 10px;"
            "}"
            "QFrame#AddReactionCard:hover {"
            "  background-color: #1a1a2e;"
            "  border-color: #818cf8;"
            "}"
        )

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)

        plus_icon = QLabel("＋")
        plus_icon.setAlignment(Qt.AlignCenter)
        plus_icon.setStyleSheet("font-size: 28px; color: #818cf8; font-weight: bold;")
        layout.addWidget(plus_icon)

        title = QLabel("Add Reaction")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-weight: 700; color: #f8fafc; font-size: 13px;")
        layout.addWidget(title)

        subtitle = QLabel("Custom meme & gesture")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(subtitle)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.add_clicked.emit()
        super().mousePressEvent(event)


class ReactionCard(QFrame):
    """
    Card widget representing one meme reaction with thumbnail,
    calibration badge, test trigger, re-bind gesture button, and drag-and-drop asset replacement.
    """
    asset_replaced = Signal(str)    # pose/gesture id
    test_requested = Signal(str)    # pose/gesture id
    rebind_requested = Signal(str)  # pose/gesture id
    delete_requested = Signal(str)  # pose/gesture id

    def __init__(self, gesture_or_id, parent=None):
        super().__init__(parent)
        if isinstance(gesture_or_id, CustomGesture):
            self.gesture = gesture_or_id
            self.pose = gesture_or_id.id
            self.display_name = gesture_or_id.display_name
            self.is_builtin = gesture_or_id.is_builtin
            self.is_calibrated = gesture_or_id.has_calibration()
        else:
            self.pose = str(gesture_or_id)
            self.display_name = self.pose.replace("_", " ").title()
            self.is_builtin = True
            self.is_calibrated = False
            self.gesture = None

        self.setObjectName("ReactionCard")
        self.setProperty("class", "Card")
        self.setAcceptDrops(True)
        self.setMinimumSize(180, 160)
        self.setMaximumSize(240, 190)

        self._build_ui()
        self.load_thumbnail()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # 1. Header: Name, Calibration Badge, Action Buttons
        top_row = QHBoxLayout()
        top_row.setSpacing(4)

        self.name_label = QLabel(self.display_name)
        self.name_label.setStyleSheet("font-weight: 600; color: #f8fafc; font-size: 12px;")
        top_row.addWidget(self.name_label, 1)

        # Calibration badge
        self.badge_label = QLabel()
        if self.is_calibrated:
            self.badge_label.setText("✨")
            self.badge_label.setToolTip("Custom Calibrated Gesture")
            self.badge_label.setStyleSheet("color: #34d399; font-size: 11px;")
        top_row.addWidget(self.badge_label)

        # Re-bind Gesture Button
        self.rebind_btn = QPushButton("⚙️")
        self.rebind_btn.setToolTip("Re-bind hand gesture trigger")
        self.rebind_btn.setFixedSize(26, 24)
        self.rebind_btn.setStyleSheet(
            "QPushButton { background-color: #27273a; color: #cbd5e1; border-radius: 4px; font-size: 11px; padding: 0; }"
            "QPushButton:hover { background-color: #3b3b55; color: white; }"
        )
        self.rebind_btn.clicked.connect(lambda: self.rebind_requested.emit(self.pose))
        top_row.addWidget(self.rebind_btn)

        # Test Button
        self.test_btn = QPushButton("Test")
        self.test_btn.setObjectName("TestBtn")
        self.test_btn.setToolTip("Preview overlay for 2s")
        self.test_btn.setFixedHeight(24)
        self.test_btn.clicked.connect(lambda: self.test_requested.emit(self.pose))
        top_row.addWidget(self.test_btn)

        # Delete Button (for custom reactions only)
        if not self.is_builtin:
            self.delete_btn = QPushButton("✕")
            self.delete_btn.setToolTip("Delete custom reaction")
            self.delete_btn.setFixedSize(22, 24)
            self.delete_btn.setStyleSheet(
                "QPushButton { background-color: transparent; color: #ef4444; border: none; font-size: 12px; font-weight: bold; }"
                "QPushButton:hover { background-color: #ef4444; color: white; border-radius: 4px; }"
            )
            self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.pose))
            top_row.addWidget(self.delete_btn)

        layout.addLayout(top_row)

        # 2. Thumbnail Display / Drop Target
        self.thumb_label = QLabel()
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet(
            "background-color: #121217; border: 1px dashed #3a3a4c; border-radius: 6px;"
        )
        self.thumb_label.setMinimumHeight(75)
        layout.addWidget(self.thumb_label, 1)

        # 3. Subtitle / Gesture Description
        if self.is_calibrated:
            desc = "Calibrated hand gesture"
        elif self.gesture and not self.is_builtin:
            desc = "Custom gesture"
        else:
            desc = POSE_DESCRIPTIONS.get(self.pose, "Gesture trigger")

        self.desc_label = QLabel(desc)
        self.desc_label.setStyleSheet("font-size: 11px; color: #94a3b8;")
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.desc_label)

    def update_gesture_state(self, is_calibrated: bool):
        """Updates calibration badge and subtitle without re-creating card."""
        self.is_calibrated = is_calibrated
        if is_calibrated:
            self.badge_label.setText("✨")
            self.badge_label.setToolTip("Custom Calibrated Gesture")
            self.desc_label.setText("Calibrated hand gesture")
        else:
            self.badge_label.setText("")
            desc = POSE_DESCRIPTIONS.get(self.pose, "Standard trigger")
            self.desc_label.setText(desc)

    def load_thumbnail(self):
        """Finds current media file and loads scaled thumbnail."""
        filepath = None
        if self.gesture and self.gesture.asset_file:
            filepath = find_asset_file(self.gesture.asset_file)
        if not filepath:
            filepath = find_asset_file(self.pose)

        if filepath and os.path.isfile(filepath):
            pixmap = QPixmap(filepath)
            if not pixmap.isNull():
                scaled = pixmap.scaled(QSize(100, 75), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.thumb_label.setPixmap(scaled)
                return

        self.thumb_label.setText("Drop Image/GIF")
        self.thumb_label.setStyleSheet(
            "background-color: #16161d; border: 1px dashed #4b4b60; color: #64748b; font-size: 11px;"
        )

    # Drag and Drop Handlers
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                ext = os.path.splitext(path)[1].lower()
                if ext in (".png", ".jpg", ".jpeg", ".gif"):
                    self.setStyleSheet("border: 2px solid #6366f1; background-color: #242436;")
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")
        self.setProperty("class", "Card")

    def dropEvent(self, event):
        self.setStyleSheet("")
        self.setProperty("class", "Card")
        urls = event.mimeData().urls()
        if not urls:
            return

        source_file = urls[0].toLocalFile()
        if not os.path.isfile(source_file):
            return

        self.replace_asset_with_file(source_file)
        event.acceptProposedAction()

    def replace_asset_with_file(self, source_path: str):
        """Validates file integrity, backs up existing asset, and updates reaction."""
        ext = os.path.splitext(source_path)[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".gif"):
            QMessageBox.warning(self, "Invalid Format", "Supported formats: PNG, JPEG, JPG, GIF.")
            return

        if not validate_image_file(source_path):
            QMessageBox.warning(
                self,
                "Corrupted File",
                "The dropped file could not be decoded. Existing reaction meme has been preserved."
            )
            return

        os.makedirs(USER_ASSETS_DIR, exist_ok=True)
        os.makedirs(BACKUPS_DIR, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        user_file = find_asset_file(self.pose, USER_ASSETS_DIR)
        factory_file = find_asset_file(self.pose, FACTORY_ASSETS_DIR)

        if user_file and os.path.isfile(user_file):
            old_ext = os.path.splitext(user_file)[1]
            backup_name = f"{timestamp}_{self.pose}{old_ext}"
            try:
                shutil.copy2(user_file, os.path.join(BACKUPS_DIR, backup_name))
                os.remove(user_file)
            except Exception as e:
                print(f"Error backing up custom asset: {e}")
        elif factory_file and os.path.isfile(factory_file):
            old_ext = os.path.splitext(factory_file)[1]
            backup_name = f"{timestamp}_{self.pose}_factory{old_ext}"
            try:
                shutil.copy2(factory_file, os.path.join(BACKUPS_DIR, backup_name))
            except Exception as e:
                print(f"Error backing up factory asset: {e}")

        dest_path = os.path.join(USER_ASSETS_DIR, f"{self.pose}{ext}")
        try:
            shutil.copy2(source_path, dest_path)
            self.load_thumbnail()
            self.asset_replaced.emit(self.pose)
        except Exception as e:
            QMessageBox.warning(self, "Asset Error", f"Could not save file: {e}")


class AssetGridWidget(QWidget):
    """
    Scrollable gallery containing ReactionCards for all registered reactions
    and the + Add Reaction call-to-action.
    """
    trigger_force_reaction = Signal(str, float)
    reload_assets_requested = Signal()
    add_reaction_requested = Signal()
    rebind_gesture_requested = Signal(str)
    delete_reaction_requested = Signal(str)

    def __init__(self, registry: Optional[CustomGestureRegistry] = None, parent=None):
        super().__init__(parent)
        self.registry = registry or CustomGestureRegistry()
        self.cards: Dict[str, ReactionCard] = {}

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        # Header Title with "+ Add Reaction" Button
        header_layout = QHBoxLayout()
        title = QLabel("Reaction Memes")
        title.setObjectName("SectionHeader")
        header_layout.addWidget(title)

        header_layout.addStretch(1)

        self.add_btn = QPushButton("＋ Add Reaction")
        self.add_btn.setStyleSheet(
            "QPushButton { background-color: #4338ca; color: white; font-weight: 600; font-size: 11px; padding: 5px 12px; border-radius: 6px; }"
            "QPushButton:hover { background-color: #4f46e5; }"
        )
        self.add_btn.clicked.connect(self.add_reaction_requested.emit)
        header_layout.addWidget(self.add_btn)
        main_layout.addLayout(header_layout)

        # Scrollable Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setContentsMargins(4, 4, 4, 4)
        self.grid.setSpacing(10)

        scroll.setWidget(self.container)
        main_layout.addWidget(scroll, 1)

        self.reload_grid()

    def reload_grid(self):
        """Clears and re-populates all reaction cards from the gesture registry."""
        # Clear existing layout items
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.cards.clear()

        cols = 2
        # Card 0: Add Reaction CTA Card
        add_card = AddReactionCard()
        add_card.add_clicked.connect(self.add_reaction_requested.emit)
        self.grid.addWidget(add_card, 0, 0)

        # Registered Reactions (Built-in + Custom)
        all_gestures = self.registry.get_all()
        for idx, gesture in enumerate(all_gestures, start=1):
            card = ReactionCard(gesture)
            card.test_requested.connect(lambda p: self.trigger_force_reaction.emit(p, 2.0))
            card.rebind_requested.connect(self.rebind_gesture_requested.emit)
            card.delete_requested.connect(self.delete_reaction_requested.emit)
            card.asset_replaced.connect(lambda p: self.reload_assets_requested.emit())

            self.cards[gesture.id] = card
            row = idx // cols
            col = idx % cols
            self.grid.addWidget(card, row, col)

    def refresh_cards(self):
        """Refreshes thumbnail and calibration state for all existing cards."""
        for pose_id, card in self.cards.items():
            g = self.registry.get(pose_id)
            if g:
                card.gesture = g
                card.update_gesture_state(g.has_calibration())
            card.load_thumbnail()
