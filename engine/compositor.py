"""
Reaction asset management, alpha compositing, and animated GIF decoding.
Robust error handling for corrupted, truncated, or unsupported media files.
"""
import os
import cv2
import numpy as np

from .paths import ROOT_DIR, APP_DATA_DIR


class Asset:
    """One reaction: a list of BGRA frames plus per-frame durations (ms) for GIFs."""

    def __init__(self, frames, durations):
        if not frames:
            img = np.zeros((300, 300, 4), np.uint8)
            cv2.circle(img, (150, 150), 140, (0, 0, 255, 220), -1)
            frames = [img]
            durations = [100]

        self.frames = frames
        self.durations = durations
        self.cum = np.cumsum(durations)
        self.total = max(int(self.cum[-1]), 1)
        h, w = frames[0].shape[:2]
        self.aspect = max(w / max(h, 1), 0.1)
        self._cache = {}

    def frame_at(self, ms):
        if len(self.frames) <= 1:
            return 0
        return int(np.searchsorted(self.cum, ms % self.total, side="right")) % len(self.frames)

    def scaled(self, idx, height):
        idx = idx % len(self.frames)
        key = (idx, height)
        if key not in self._cache:
            if len(self._cache) > 64:
                self._cache.clear()
            w = max(1, int(round(height * self.aspect)))
            try:
                self._cache[key] = cv2.resize(self.frames[idx], (w, height), interpolation=cv2.INTER_AREA)
            except Exception:
                self._cache[key] = self.frames[idx]
        return self._cache[key]


def to_bgra(img):
    if img is None:
        return np.zeros((100, 100, 4), np.uint8)
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    if img.shape[2] == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    return img


def placeholder(label):
    img = np.zeros((300, 300, 4), np.uint8)
    cv2.circle(img, (150, 150), 140, (0, 0, 255, 220), -1)
    cv2.putText(img, label, (12, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255, 255), 2)
    return Asset([img], [100])


def find_asset_file(pose, assets_dir=None):
    """
    Finds the media file for a reaction pose.
    If assets_dir is not explicitly specified, checks the user customizations
    directory (APP_DATA_DIR/assets) first, falling back to factory assets (ROOT_DIR/assets).
    """
    # Direct absolute or relative file existence check
    if isinstance(pose, str) and os.path.isfile(pose):
        return os.path.abspath(pose)

    candidate_dirs = []
    if assets_dir:
        candidate_dirs.append(assets_dir)
    else:
        user_assets = os.path.join(APP_DATA_DIR, "assets")
        factory_assets = os.path.join(ROOT_DIR, "assets")
        if os.path.abspath(user_assets) != os.path.abspath(factory_assets):
            candidate_dirs.append(user_assets)
        candidate_dirs.append(factory_assets)

    exts = (".gif", ".png", ".jpg", ".jpeg")
    for adir in candidate_dirs:
        if not os.path.isdir(adir):
            continue
        # Check if pose matches an exact filename in candidate directory
        if isinstance(pose, str):
            direct_path = os.path.join(adir, pose)
            if os.path.isfile(direct_path):
                return direct_path
        try:
            for fn in sorted(os.listdir(adir)):
                stem, ext = os.path.splitext(fn)
                if ext.lower() in exts and (stem == pose or stem.endswith("_" + pose)):
                    return os.path.join(adir, fn)
        except Exception:
            continue
    return None


def load_asset(pose, assets_dir=None):
    """Loads and decodes image or animated GIF with fallback to placeholder."""
    path = find_asset_file(pose, assets_dir)
    if path is None:
        return placeholder(pose)

    frames, durations = [], []
    try:
        if path.lower().endswith(".gif"):
            from PIL import Image, ImageSequence
            with Image.open(path) as im:
                for f in ImageSequence.Iterator(im):
                    try:
                        rgba = np.array(f.convert("RGBA"))
                        frames.append(cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA))
                        durations.append(max(20, int(f.info.get("duration", 100))))
                    except Exception:
                        continue
        else:
            img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
            if img is not None:
                frames, durations = [to_bgra(img)], [100]
    except Exception as e:
        print(f"Warning: Could not decode asset for '{pose}' from {path}: {e}")
        return placeholder(pose)

    if not frames:
        return placeholder(pose)
    return Asset(frames, durations)


def overlay(frame, sprite, x, y):
    """Alpha-composite BGRA sprite onto BGR frame at top-left (x, y), safely clipped."""
    if frame is None or sprite is None:
        return frame

    H, W = frame.shape[:2]
    h, w = sprite.shape[:2]
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x0 >= x1 or y0 >= y1:
        return frame

    try:
        s = sprite[y0 - y:y1 - y, x0 - x:x1 - x]
        if s.shape[2] == 4:
            a = s[:, :, 3:4].astype(np.float32) / 255.0
            roi = frame[y0:y1, x0:x1].astype(np.float32)
            frame[y0:y1, x0:x1] = (a * s[:, :, :3] + (1 - a) * roi).astype(np.uint8)
        else:
            frame[y0:y1, x0:x1] = s[:, :, :3]
    except Exception as e:
        print(f"Overlay exception suppressed: {e}")
    return frame
