#!/usr/bin/env python3
"""
CleoStream — Modern Desktop Application
PySide6 (Qt6) Entrypoint with real-time MediaPipe vision worker,
OBS virtual camera streaming, drag-and-drop meme gallery, and system tray.
"""
import argparse
import signal
import sys
import os

# Ensure repository root is on sys.path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

from engine import ensure_models, preflight, VisionWorker
from ui import MainWindow, DARK_THEME_QSS, create_tray_icon


def parse_args():
    parser = argparse.ArgumentParser(description="CleoStream — Desktop Application")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--no-vcam", action="store_true", help="Disable virtual camera broadcast")
    parser.add_argument("--size", default="1280x720", help="Resolution: 1280x720 or 640x480")
    parser.add_argument("--no-flip", action="store_true", help="Do not mirror preview/broadcast")
    return parser.parse_args()


def main():
    # 1. Enable modern High-DPI attributes
    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    app = QApplication(sys.argv)
    app.setApplicationName("CleoStream")
    app.setApplicationDisplayName("CleoStream")
    app.setOrganizationName("CleoStream")
    app.setWindowIcon(create_tray_icon())
    app.setStyleSheet(DARK_THEME_QSS)

    args = parse_args()

    # Parse resolution dimensions
    w, h = 1280, 720
    if "x" in args.size.lower():
        try:
            parts = args.size.lower().split("x")
            w, h = int(parts[0]), int(parts[1])
        except Exception:
            w, h = 1280, 720

    # 2. Run detector preflight check once on startup
    print("Preflight: verifying MediaPipe task models...")
    model_paths = ensure_models()
    preflight(model_paths["face_landmarker.task"])
    print("Preflight OK!")

    # 3. Create Vision Engine Worker Thread
    worker = VisionWorker(
        camera_index=args.camera,
        resolution=(w, h),
        flip=not args.no_flip,
        enable_vcam=not args.no_vcam,
    )

    # 4. Create Main Application Window
    window = MainWindow(worker=worker)
    window.show()

    # 5. Start Vision Worker Thread
    worker.start()

    # Clean shutdown handling
    def on_about_to_quit():
        print("Application shutting down, stopping vision worker...")
        worker.stop()
        print("Shutdown complete.")

    app.aboutToQuit.connect(on_about_to_quit)

    # Periodic timer to allow Python signal handler (Ctrl+C) to process
    sig_timer = QTimer()
    sig_timer.start(500)
    sig_timer.timeout.connect(lambda: None)

    signal.signal(signal.SIGINT, lambda sig, frame: app.quit())

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
