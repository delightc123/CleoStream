"""
Primary desktop application window combining live video preview,
reaction gallery, controls toolbar, non-blocking notification banners,
system tray lifecycle, and GitHub auto-updates.
"""
from PySide6.QtCore import Qt, QSize, Slot, QTimer
from PySide6.QtGui import QIcon, QCloseEvent, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QFrame, QSplitter, QMessageBox,
    QApplication, QLineEdit, QTextEdit
)

from .video_widget import VideoWidget
from .asset_grid import AssetGridWidget
from .calibration_dialog import CalibrationDialog
from .tray import TrayController, create_tray_icon
from .update_dialog import UpdateDialog
from engine.updater import UpdateCheckWorker
from engine.version import __version__


class MainWindow(QMainWindow):
    """
    Main Application Window for CleoStream Desktop.
    """
    def __init__(self, worker, parent=None):
        super().__init__(parent)
        self.worker = worker
        self._is_quitting = False
        self._update_worker = None

        self.setWindowTitle(f"CleoStream v{__version__} — Meme Reaction Camera")
        self.setWindowIcon(create_tray_icon())
        self.resize(1180, 720)
        self.setMinimumSize(900, 560)

        # Initialize System Tray Controller
        self.tray = TrayController(self)
        self._bind_tray_signals()

        # Bind Global Keyboard Shortcuts (Ctrl+Shift+M, Space)
        self._setup_shortcuts()

        # Build UI layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_vbox = QVBoxLayout(central_widget)
        main_vbox.setContentsMargins(0, 0, 0, 0)
        main_vbox.setSpacing(0)

        # 1. Header Frame
        header = self._build_header()
        main_vbox.addWidget(header)

        # Non-blocking Warning Banner (Hidden by default)
        self.vcam_banner = QLabel()
        self.vcam_banner.setStyleSheet(
            "background-color: #3b2005; color: #fde68a; border-bottom: 1px solid #78350f; "
            "padding: 6px 16px; font-size: 12px; font-weight: 500;"
        )
        self.vcam_banner.hide()
        main_vbox.addWidget(self.vcam_banner)

        # 2. Central Split Content Area
        splitter = QSplitter(Qt.Horizontal)
        splitter.setContentsMargins(16, 16, 16, 16)
        splitter.setHandleWidth(8)

        # Left Column: Video Preview + Quick Controls Toolbar
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        self.video_widget = VideoWidget()
        left_layout.addWidget(self.video_widget, 1)

        left_toolbar = self._build_left_toolbar()
        left_layout.addLayout(left_toolbar)
        splitter.addWidget(left_container)

        # Right Column: Reaction Memes Grid
        self.asset_grid = AssetGridWidget()
        splitter.addWidget(self.asset_grid)

        # Proportions: 60% preview, 40% memes
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 4)
        main_vbox.addWidget(splitter, 1)

        # 3. Footer Frame
        footer = self._build_footer()
        main_vbox.addWidget(footer)

        # Calibration Dialog Instance
        self.calib_dialog = CalibrationDialog(self)
        self._bind_calibration_signals()

        # Connect Worker Signals to UI
        self._bind_worker_signals()

        # Check for updates silently 2.5 seconds after startup
        QTimer.singleShot(2500, self.check_for_updates_silent)

    def _build_header(self):
        header_frame = QFrame()
        header_frame.setObjectName("HeaderFrame")
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(16, 10, 16, 10)
        h_layout.setSpacing(14)

        # App Logo & Title
        logo_label = QLabel("⚡ CleoStream")
        logo_label.setObjectName("AppTitle")
        h_layout.addWidget(logo_label)

        h_layout.addStretch(1)

        # Camera Selector
        cam_label = QLabel("Camera:")
        cam_label.setStyleSheet("color: #94a3b8; font-weight: 500;")
        h_layout.addWidget(cam_label)

        self.cam_combo = QComboBox()
        self.cam_combo.addItems(["Camera 0 (Default)", "Camera 1", "Camera 2"])
        self.cam_combo.currentIndexChanged.connect(self._on_camera_changed)
        h_layout.addWidget(self.cam_combo)

        # Resolution Selector
        res_label = QLabel("Resolution:")
        res_label.setStyleSheet("color: #94a3b8; font-weight: 500;")
        h_layout.addWidget(res_label)

        self.res_combo = QComboBox()
        self.res_combo.addItems(["1280x720 (HD)", "640x480 (Fast)"])
        self.res_combo.currentIndexChanged.connect(self._on_resolution_changed)
        h_layout.addWidget(self.res_combo)

        # Virtual Camera Status Badge & Toggle
        self.vcam_badge = QLabel("V-CAM BROADCASTING")
        self.vcam_badge.setObjectName("BadgeActive")
        h_layout.addWidget(self.vcam_badge)

        self.vcam_btn = QPushButton("Stop V-Cam")
        self.vcam_btn.setCheckable(True)
        self.vcam_btn.setChecked(True)
        self.vcam_btn.clicked.connect(self._on_vcam_toggle_clicked)
        h_layout.addWidget(self.vcam_btn)

        # Check Updates Button
        self.update_btn = QPushButton("Updates")
        self.update_btn.setToolTip("Check GitHub for new updates")
        self.update_btn.setStyleSheet("""
            QPushButton {
                background-color: #222227;
                color: #a1a1aa;
                border: 1px solid #2f2f36;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #2e2e38;
                color: #f4f4f5;
                border-color: #4f46e5;
            }
        """)
        self.update_btn.clicked.connect(lambda: self.check_for_updates(silent=False))
        h_layout.addWidget(self.update_btn)

        return header_frame

    def _build_left_toolbar(self):
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.mirror_btn = QPushButton("Mirror Video")
        self.mirror_btn.setCheckable(True)
        self.mirror_btn.setChecked(True)
        self.mirror_btn.clicked.connect(self._on_mirror_toggled)
        toolbar.addWidget(self.mirror_btn)

        self.hud_btn = QPushButton("Diagnostic HUD")
        self.hud_btn.setCheckable(True)
        self.hud_btn.setChecked(False)
        self.hud_btn.clicked.connect(self._on_hud_toggled)
        toolbar.addWidget(self.hud_btn)

        self.pause_btn = QPushButton("⏸ Pause Reactions (Space)")
        self.pause_btn.setObjectName("PauseBtn")
        self.pause_btn.setToolTip("Mute/unmute meme reactions during calls (Shortcut: Space or Ctrl+Shift+M)")
        self.pause_btn.setCheckable(True)
        self.pause_btn.setChecked(False)
        self.pause_btn.clicked.connect(self._on_pause_toggled)
        toolbar.addWidget(self.pause_btn)

        toolbar.addStretch(1)
        return toolbar

    def _build_footer(self):
        footer_frame = QFrame()
        footer_frame.setObjectName("FooterFrame")
        f_layout = QHBoxLayout(footer_frame)
        f_layout.setContentsMargins(16, 10, 16, 10)
        f_layout.setSpacing(16)

        # Telemetry / Status indicator
        self.status_label = QLabel("Ready • Initializing vision models...")
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 500;")
        f_layout.addWidget(self.status_label)

        f_layout.addStretch(1)

        # Primary Calibration Trigger Button
        self.calibrate_btn = QPushButton("🎯 Calibrate Neutral Face (7s)")
        self.calibrate_btn.setStyleSheet("""
            QPushButton {
                background-color: #4f46e5;
                color: #ffffff;
                font-weight: 600;
                font-size: 12px;
                padding: 6px 16px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #4338ca;
            }
        """)
        self.calibrate_btn.clicked.connect(self._open_calibration_modal)
        f_layout.addWidget(self.calibrate_btn)

        return footer_frame

    def _bind_worker_signals(self):
        # 1. Video frame rendering
        self.worker.frame_ready.connect(self.video_widget.update_frame)

        # 2. Real-time telemetry
        self.worker.telemetry_updated.connect(self._on_telemetry_updated)

        # 3. Virtual Camera state
        self.worker.vcam_status_changed.connect(self._on_vcam_status_changed)

        # 4. Camera hardware state
        self.worker.camera_status_changed.connect(self._on_camera_status_changed)

        # 5. Reaction test button and asset reload from meme cards
        self.asset_grid.trigger_force_reaction.connect(self.worker.force_reaction)
        self.asset_grid.reload_assets_requested.connect(self.worker.reload_assets)

    def _bind_tray_signals(self):
        self.tray.show_window_requested.connect(self._restore_from_tray)
        self.tray.recalibrate_requested.connect(self._open_calibration_modal)
        self.tray.pause_toggled.connect(self._on_tray_pause_toggled)
        self.tray.vcam_toggled.connect(self.worker.set_vcam_enabled)
        self.tray.check_updates_requested.connect(lambda: self.check_for_updates(silent=False))
        self.tray.quit_requested.connect(self.exit_application)

    def _bind_calibration_signals(self):
        self.calib_dialog.recalibrate_requested.connect(self.worker.start_calibration)
        self.worker.calibration_progress.connect(self.calib_dialog.update_progress)
        self.worker.calibration_finished.connect(self.calib_dialog.on_finished)

    # -------------------------------------------------------------------------
    # Auto-Update Checks
    # -------------------------------------------------------------------------
    def check_for_updates_silent(self):
        """Silently queries GitHub for updates in the background on startup."""
        self.check_for_updates(silent=True)

    def check_for_updates(self, silent: bool = False):
        """Spawns background update check worker."""
        if not silent:
            self.update_btn.setEnabled(False)
            self.update_btn.setText("Checking...")

        self._update_worker = UpdateCheckWorker(parent=self)
        self._update_worker.check_finished.connect(
            lambda result: self._on_update_check_finished(result, silent)
        )
        self._update_worker.start()

    def _on_update_check_finished(self, result: dict, silent: bool):
        self.update_btn.setEnabled(True)
        self.update_btn.setText("Updates")

        if result.get("has_update"):
            dialog = UpdateDialog(result, parent=self)
            dialog.exec()
        elif not silent:
            error = result.get("error")
            if error:
                QMessageBox.warning(
                    self,
                    "Update Check",
                    f"Could not check for updates:\n{error}\n\nPlease check your internet connection or GitHub."
                )
            else:
                QMessageBox.information(
                    self,
                    "Up to Date",
                    f"You are running the latest version of CleoStream (v{__version__}).\nNo new updates available."
                )

    # -------------------------------------------------------------------------
    # UI Control Slots
    # -------------------------------------------------------------------------
    @Slot(int)
    def _on_camera_changed(self, index: int):
        self.worker.set_camera_index(index)

    @Slot(int)
    def _on_resolution_changed(self, index: int):
        if index == 0:
            self.worker.set_resolution(1280, 720)
        else:
            self.worker.set_resolution(640, 480)

    @Slot()
    def _on_vcam_toggle_clicked(self):
        enable = self.vcam_btn.isChecked()
        self.worker.set_vcam_enabled(enable)

    @Slot()
    def _on_mirror_toggled(self):
        flip = self.mirror_btn.isChecked()
        self.worker.set_flip(flip)

    def _setup_shortcuts(self):
        """Binds global window shortcuts for instant reaction muting during calls."""
        self.mute_shortcut = QShortcut(QKeySequence("Ctrl+Shift+M"), self)
        self.mute_shortcut.activated.connect(self._toggle_pause_shortcut)

        self.space_shortcut = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.space_shortcut.activated.connect(self._toggle_pause_shortcut)

    @Slot()
    def _toggle_pause_shortcut(self):
        """Toggles pause/mute state via keyboard shortcut unless a text field is focused."""
        focused = QApplication.focusWidget()
        if isinstance(focused, (QLineEdit, QTextEdit)):
            return
        self.pause_btn.setChecked(not self.pause_btn.isChecked())
        self._on_pause_toggled()

    @Slot()
    def _on_hud_toggled(self):
        hud = self.hud_btn.isChecked()
        self.worker.set_show_hud(hud)

    @Slot()
    def _on_pause_toggled(self):
        paused = self.pause_btn.isChecked()
        self.worker.set_paused(paused)
        self.tray.pause_action.setChecked(paused)
        self.video_widget.set_paused(paused)

        # Update button text, icon, and dynamic style
        if paused:
            self.pause_btn.setText("▶ Resume Reactions (Space)")
            self.pause_btn.setObjectName("PauseBtnActive")
        else:
            self.pause_btn.setText("⏸ Pause Reactions (Space)")
            self.pause_btn.setObjectName("PauseBtn")

        self.pause_btn.style().unpolish(self.pause_btn)
        self.pause_btn.style().polish(self.pause_btn)

        # If window is minimized or hidden, show tray toast notification
        if not self.isVisible() or self.isMinimized():
            self.tray.notify_mute_state(paused)

    @Slot(str)
    def _on_test_reaction_requested(self, pose: str):
        self.worker.trigger_force_reaction(pose, duration=2.0)

    @Slot(dict)
    def _on_telemetry_updated(self, telemetry: dict):
        fps = telemetry.get("fps", 0.0)
        reaction = telemetry.get("reaction") or telemetry.get("shown")
        face_detected = telemetry.get("face_detected", False)
        calibrated = telemetry.get("calibrated", False)

        calib_str = "Calibrated" if calibrated else "Generic Baseline"
        face_str = "Face Tracked" if face_detected else "No Face"
        active_str = f" • Active: {reaction}" if reaction else ""

        self.status_label.setText(f"{face_str} • {calib_str} • {fps:.1f} FPS{active_str}")
        self.video_widget.set_fps(fps)
        self.video_widget.set_active_reaction(reaction)

    @Slot(bool, str)
    def _on_vcam_status_changed(self, active: bool, device_or_err: str):
        self.tray.update_vcam_status(active, device_or_err)
        if active:
            self.vcam_banner.hide()
            self.vcam_badge.setText("V-CAM BROADCASTING")
            self.vcam_badge.setStyleSheet(
                "background-color: #064e3b; color: #34d399; border: 1px solid #059669; "
                "font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 12px;"
            )
            self.vcam_btn.setText("Stop V-Cam")
            self.vcam_btn.setChecked(True)
        else:
            self.vcam_badge.setText("V-CAM OFFLINE")
            self.vcam_badge.setStyleSheet(
                "background-color: #451a03; color: #fbbf24; border: 1px solid #d97706; "
                "font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 12px;"
            )
            self.vcam_btn.setText("Start V-Cam")
            self.vcam_btn.setChecked(False)

            if device_or_err and not device_or_err.startswith("User disabled"):
                self.vcam_banner.setText(f"⚠️ {device_or_err}. Running in local preview mode.")
                self.vcam_banner.show()

    @Slot(bool, str)
    def _on_camera_status_changed(self, connected: bool, message: str):
        if not connected:
            self.status_label.setText(f"Camera Error: {message}")
            self.status_label.setStyleSheet("color: #f87171; font-weight: 600;")
        else:
            self.status_label.setStyleSheet("color: #94a3b8; font-weight: 500;")

    @Slot(bool)
    def _on_tray_pause_toggled(self, paused: bool):
        self.pause_btn.setChecked(paused)
        self._on_pause_toggled()

    @Slot()
    def _open_calibration_modal(self):
        self.calib_dialog.action_btn.setText("Start 7s Calibration")
        self.calib_dialog.progress_bar.setValue(0)
        self.calib_dialog.status_label.setText("Ready to calibrate")
        self.calib_dialog.status_label.setStyleSheet("font-weight: 600; color: #f8fafc;")
        self.calib_dialog.show()
        self.calib_dialog.raise_()
        self.calib_dialog.activateWindow()

    @Slot()
    def _restore_from_tray(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event: QCloseEvent):
        """Intercepts window close to minimize to system tray if streaming."""
        if not self._is_quitting and self.tray.tray_icon.isSystemTrayAvailable():
            event.ignore()
            self.hide()
            self.tray.notify_minimized()
        else:
            event.accept()

    def exit_application(self):
        """Full clean application shutdown."""
        self._is_quitting = True
        self.status_label.setText("Shutting down engine...")
        if self._update_worker and self._update_worker.isRunning():
            self._update_worker.quit()
            self._update_worker.wait(1000)
        self.worker.stop()
        self.close()
