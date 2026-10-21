"""
Automated unit test for VisionWorker QThread lifecycle, signal emission, and clean shutdown.
"""
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from PySide6.QtCore import QCoreApplication, QTimer
from engine import VisionWorker

def test_worker():
    app = QCoreApplication(sys.argv)
    worker = VisionWorker(camera_index=0, enable_vcam=False)
    frames_received = []
    telemetry_received = []

    worker.frame_ready.connect(lambda img: frames_received.append((img.width(), img.height())))
    worker.telemetry_updated.connect(lambda d: telemetry_received.append(d))

    def on_timeout():
        print(f"Stopping worker... Frames received: {len(frames_received)}, Telemetry: {len(telemetry_received)}")
        worker.stop()
        assert not worker.isRunning(), "Worker should not be running after stop()"
        assert len(frames_received) > 0, "Expected at least 1 frame"
        assert len(telemetry_received) > 0, "Expected telemetry updates"
        print(f"Frame sample: {frames_received[0]}")
        print(f"Latest telemetry: {telemetry_received[-1]}")
        app.quit()

    worker.start()
    QTimer.singleShot(8000, on_timeout)
    app.exec()

    print("Test passed cleanly! All worker assertions succeeded.")

if __name__ == "__main__":
    test_worker()
