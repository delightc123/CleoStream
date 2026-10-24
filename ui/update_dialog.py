"""
CleoStream — Modern Update Modal Dialog
Displays available release notes, download progress, and triggers installer.
"""
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QFrame,
    QMessageBox,
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices

from engine.updater import UpdateDownloadWorker, launch_installer_and_exit
from engine.version import __version__


class UpdateDialog(QDialog):
    """
    Modal dialog informing the user of an available update,
    displaying release notes, and handling installer download.
    """

    def __init__(self, update_info: dict, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.download_worker = None
        self.downloaded_installer_path = None

        self.setWindowTitle("Update Available — CleoStream")
        self.setFixedSize(540, 480)
        self.setModal(True)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header card
        header_card = QFrame()
        header_card.setObjectName("headerCard")
        header_card.setStyleSheet("""
            QFrame#headerCard {
                background-color: #222227;
                border: 1px solid #2f2f36;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        h_layout = QVBoxLayout(header_card)
        h_layout.setContentsMargins(12, 12, 12, 12)
        h_layout.setSpacing(6)

        title = QLabel(f"🚀 New Version Available: {self.update_info.get('remote_version', 'Latest')}")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #f4f4f5;")
        h_layout.addWidget(title)

        subtitle = QLabel(
            f"You are currently running <b>v{self.update_info.get('current_version', __version__)}</b>."
        )
        subtitle.setStyleSheet("font-size: 13px; color: #a1a1aa;")
        h_layout.addWidget(subtitle)

        layout.addWidget(header_card)

        # Release Notes label
        notes_label = QLabel("What's New:")
        notes_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #e4e4e7;")
        layout.addWidget(notes_label)

        # Release Notes text edit
        self.notes_view = QTextEdit()
        self.notes_view.setReadOnly(True)
        notes = self.update_info.get("notes", "").strip() or "General improvements and bug fixes."
        self.notes_view.setPlainText(notes)
        self.notes_view.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1e;
                color: #d4d4d8;
                border: 1px solid #2f2f36;
                border-radius: 6px;
                padding: 8px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.notes_view)

        # Progress bar (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #222227;
                border: 1px solid #2f2f36;
                border-radius: 4px;
                text-align: center;
                color: #ffffff;
                height: 18px;
            }
            QProgressBar::chunk {
                background-color: #6366f1;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Status text
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("font-size: 11px; color: #a1a1aa;")
        self.status_lbl.setVisible(False)
        layout.addWidget(self.status_lbl)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        # Link to GitHub releases web page
        self.btn_web = QPushButton("View on GitHub")
        self.btn_web.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #818cf8;
                border: none;
                font-size: 12px;
                text-decoration: underline;
                padding: 6px;
            }
            QPushButton:hover {
                color: #a5b4fc;
            }
        """)
        self.btn_web.clicked.connect(self._open_github)
        btn_layout.addWidget(self.btn_web)

        btn_layout.addStretch()

        self.btn_later = QPushButton("Remind Me Later")
        self.btn_later.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                color: #d4d4d8;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3f3f46;
            }
        """)
        self.btn_later.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_later)

        self.btn_update = QPushButton("Download & Update Now")
        self.btn_update.setStyleSheet("""
            QPushButton {
                background-color: #6366f1;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #4f46e5;
            }
            QPushButton:disabled {
                background-color: #3730a3;
                color: #818cf8;
            }
        """)
        self.btn_update.clicked.connect(self._on_update_clicked)
        btn_layout.addWidget(self.btn_update)

        layout.addLayout(btn_layout)

    def _open_github(self):
        url = self.update_info.get("html_url") or "https://github.com/delightc123/CleoStream/releases"
        QDesktopServices.openUrl(QUrl(url))

    def _on_update_clicked(self):
        if self.downloaded_installer_path:
            # Already downloaded, launch it!
            launch_installer_and_exit(self.downloaded_installer_path)
            return

        installer_url = self.update_info.get("installer_url")
        if not installer_url:
            # Fallback to browser if no direct .exe asset attached yet
            self._open_github()
            self.accept()
            return

        # Start download
        self.btn_update.setEnabled(False)
        self.btn_later.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_lbl.setVisible(True)
        self.status_lbl.setText("Connecting to download server...")

        installer_name = self.update_info.get("installer_name") or "CleoStream_Setup.exe"
        self.download_worker = UpdateDownloadWorker(installer_url, filename=installer_name, parent=self)
        self.download_worker.progress.connect(self._on_progress)
        self.download_worker.download_finished.connect(self._on_finished)
        self.download_worker.download_failed.connect(self._on_failed)
        self.download_worker.start()

    def _on_progress(self, downloaded: int, total: int):
        if total > 0:
            pct = int((downloaded / total) * 100)
            self.progress_bar.setValue(pct)
            mb_down = downloaded / (1024 * 1024)
            mb_tot = total / (1024 * 1024)
            self.status_lbl.setText(f"Downloading update: {mb_down:.1f} MB / {mb_tot:.1f} MB ({pct}%)")
        else:
            self.progress_bar.setRange(0, 0)  # indeterminate
            mb_down = downloaded / (1024 * 1024)
            self.status_lbl.setText(f"Downloading update: {mb_down:.1f} MB...")

    def _on_finished(self, local_path: str):
        self.downloaded_installer_path = local_path
        self.progress_bar.setValue(100)
        self.status_lbl.setText("Download complete! Ready to install.")
        self.btn_update.setText("Install & Restart Now")
        self.btn_update.setEnabled(True)
        self.btn_later.setEnabled(True)

    def _on_failed(self, error_msg: str):
        self.status_lbl.setText(f"Error: {error_msg}")
        self.btn_update.setText("Retry Download")
        self.btn_update.setEnabled(True)
        self.btn_later.setEnabled(True)
        QMessageBox.warning(self, "Download Failed", f"Could not download update installer:\n{error_msg}")
