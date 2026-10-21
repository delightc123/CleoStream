"""
Meme reaction card grid and asset manager with drag-and-drop replacement,
corrupted file guard, and automated original backup.
"""
import os
import shutil
import time
from PIL import Image

from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QPixmap, QImageReader
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QGridLayout, QFrame, QMessageBox
)

from engine.decision import POSES
from engine.compositor import find_asset_file

from engine.paths import ROOT_DIR, APP_DATA_DIR
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
    if not os.path.isfile(filepath):
        return False
    try:
        with Image.open(filepath) as img:
            img.verify()
        # Verify first frame can be read
        with Image.open(filepath) as img:
            img.load()
        return True
    except Exception:
        return False


class ReactionCard(QFrame):
    """
    Card widget representing one meme reaction with thumbnail,
    test trigger button, and drag-and-drop asset replacement.
    """
    asset_replaced = Signal(str)  # pose name
    test_requested = Signal(str)  # pose name

    def __init__(self, pose: str, parent=None):
        super().__init__(parent)
        self.pose = pose
        self.setObjectName("ReactionCard")
        self.setProperty("class", "Card")
        self.setAcceptDrops(True)
        self.setMinimumSize(180, 150)
        self.setMaximumSize(240, 180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Header: Name and test trigger
        top_row = QHBoxLayout()
        self.name_label = QLabel(pose.replace("_", " ").title())
        self.name_label.setStyleSheet("font-weight: 600; color: #f8fafc;")
        top_row.addWidget(self.name_label)

        self.test_btn = QPushButton("Test")
        self.test_btn.setObjectName("TestBtn")
        self.test_btn.setToolTip("Preview overlay for 2s")
        self.test_btn.clicked.connect(lambda: self.test_requested.emit(self.pose))
        top_row.addWidget(self.test_btn)
        layout.addLayout(top_row)

        # Thumbnail display / Drop Target
        self.thumb_label = QLabel()
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet(
            "background-color: #121217; border: 1px dashed #3a3a4c; border-radius: 6px;"
        )
        self.thumb_label.setMinimumHeight(80)
        layout.addWidget(self.thumb_label, 1)

        # Subtitle / Hint
        desc = POSE_DESCRIPTIONS.get(pose, "Gesture trigger")
        self.desc_label = QLabel(desc)
        self.desc_label.setStyleSheet("font-size: 11px; color: #94a3b8;")
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.desc_label)

        self.load_thumbnail()

    def load_thumbnail(self):
        """Finds current media file and loads scaled thumbnail."""
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

    # Drag and Drop handlers
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

        # Integrity Check: Ensure file is not corrupted
        if not validate_image_file(source_path):
            QMessageBox.warning(
                self,
                "Corrupted File",
                "The dropped file could not be decoded. Existing reaction meme has been preserved."
            )
            return

        # 1. Back up existing file to %APPDATA%/ReactInMeetings/backups/
        os.makedirs(USER_ASSETS_DIR, exist_ok=True)
        os.makedirs(BACKUPS_DIR, exist_ok=True)
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        user_file = find_asset_file(self.pose, USER_ASSETS_DIR)
        factory_file = find_asset_file(self.pose, FACTORY_ASSETS_DIR)

        if user_file and os.path.isfile(user_file):
            old_ext = os.path.splitext(user_file)[1]
            backup_name = f"{timestamp}_{self.pose}{old_ext}"
            backup_path = os.path.join(BACKUPS_DIR, backup_name)
            try:
                shutil.copy2(user_file, backup_path)
                os.remove(user_file)
            except Exception as e:
                print(f"Error backing up custom asset: {e}")
        elif factory_file and os.path.isfile(factory_file):
            old_ext = os.path.splitext(factory_file)[1]
            backup_name = f"{timestamp}_{self.pose}_factory{old_ext}"
            backup_path = os.path.join(BACKUPS_DIR, backup_name)
            try:
                shutil.copy2(factory_file, backup_path)
            except Exception as e:
                print(f"Error backing up factory asset: {e}")

        # 2. Copy new file into writable user assets directory
        dest_path = os.path.join(USER_ASSETS_DIR, f"{self.pose}{ext}")
        try:
            shutil.copy2(source_path, dest_path)
            self.load_thumbnail()
            self.asset_replaced.emit(self.pose)
        except Exception as e:
            QMessageBox.warning(self, "Asset Error", f"Could not save file: {e}")


class AssetGridWidget(QWidget):
    """
    Scrollable gallery containing ReactionCards for all 14 reactions.
    """
    trigger_force_reaction = Signal(str, float)
    reload_assets_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Header Title
        header_layout = QHBoxLayout()
        title = QLabel("Reaction Memes")
        title.setObjectName("SectionHeader")
        header_layout.addWidget(title)

        subtitle = QLabel("Drag & drop any GIF/PNG onto a card to replace")
        subtitle.setStyleSheet("color: #64748b; font-size: 11px;")
        header_layout.addWidget(subtitle, 1, Qt.AlignRight)
        main_layout.addLayout(header_layout)

        # Scrollable Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        self.grid = QGridLayout(container)
        self.grid.setContentsMargins(4, 4, 4, 4)
        self.grid.setSpacing(10)

        self.cards = {}
        cols = 2
        for idx, pose in enumerate(POSES):
            card = ReactionCard(pose)
            card.test_requested.connect(lambda p: self.trigger_force_reaction.emit(p, 2.0))
            card.asset_replaced.connect(lambda p: self.reload_assets_requested.emit())
            self.cards[pose] = card
            row = idx // cols
            col = idx % cols
            self.grid.addWidget(card, row, col)

        scroll.setWidget(container)
        main_layout.addWidget(scroll, 1)

    def refresh_cards(self):
        for card in self.cards.values():
            card.load_thumbnail()
