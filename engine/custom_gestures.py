"""
Dynamic Hand Gesture Registry & Storage Architecture.
Provides persistent, versioned JSON storage for custom reactions and gesture re-bindings.
Guarantees atomic file updates and automatic recovery from corrupted configurations.
"""
import os
import json
import time
import shutil
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any

from .paths import APP_DATA_DIR, ROOT_DIR
from .gesture_matcher import (
    HandSignature,
    ANCHOR_FREE,
    ANCHOR_PINCHING_NOSE,
    ANCHOR_OVER_MOUTH,
    ANCHOR_UNDER_CHIN,
    ANCHOR_NEAR_HEAD,
)

REGISTRY_VERSION = "1.0"
DEFAULT_TOLERANCE = 0.85
DEFAULT_ARM_FRAMES = 4
DEFAULT_HOLD_FRAMES = 10

# Default built-in reactions aligned with engine.decision.POSES
DEFAULT_BUILTIN_GESTURES = [
    {
        "id": "time_out",
        "display_name": "Time Out",
        "asset_file": "01_time_out.png",
        "hands_count": 2,
        "anchor": ANCHOR_FREE,
        "arm_frames": 4,
        "hold_frames": 10,
        "is_builtin": True,
        "enabled": True,
    },
    {
        "id": "heart",
        "display_name": "Heart Hands",
        "asset_file": "02_heart.png",
        "hands_count": 2,
        "anchor": ANCHOR_FREE,
        "arm_frames": 4,
        "hold_frames": 10,
        "is_builtin": True,
        "enabled": True,
    },
    {
        "id": "cover_nose",
        "display_name": "Cover Nose/Mouth",
        "asset_file": "03_cover_nose.png",
        "hands_count": 2,
        "anchor": ANCHOR_OVER_MOUTH,
        "arm_frames": 4,
        "hold_frames": 10,
        "is_builtin": True,
        "enabled": True,
    },
    {
        "id": "crashing_out",
        "display_name": "Crashing Out",
        "asset_file": "04_crashing_out.png",
        "hands_count": 2,
        "anchor": ANCHOR_NEAR_HEAD,
        "arm_frames": 4,
        "hold_frames": 10,
        "is_builtin": True,
        "enabled": True,
    },
    {
        "id": "dance",
        "display_name": "Dance",
        "asset_file": "05_dance.gif",
        "hands_count": 2,
        "anchor": ANCHOR_NEAR_HEAD,
        "arm_frames": 6,
        "hold_frames": 10,
        "is_builtin": True,
        "enabled": True,
    },
    {
        "id": "nose_closed",
        "display_name": "Hold Nose",
        "asset_file": "06_nose_closed.png",
        "hands_count": 1,
        "anchor": ANCHOR_PINCHING_NOSE,
        "arm_frames": 4,
        "hold_frames": 10,
        "is_builtin": True,
        "enabled": True,
    },
    {
        "id": "flirty",
        "display_name": "Flirty / Thinking",
        "asset_file": "07_flirty.png",
        "hands_count": 1,
        "anchor": ANCHOR_UNDER_CHIN,
        "arm_frames": 4,
        "hold_frames": 10,
        "is_builtin": True,
        "enabled": True,
    },
    {
        "id": "hand_up",
        "display_name": "Hand Up / Stop",
        "asset_file": "08_hand_up.png",
        "hands_count": 1,
        "anchor": ANCHOR_FREE,
        "arm_frames": 4,
        "hold_frames": 10,
        "is_builtin": True,
        "enabled": True,
    },
    {
        "id": "tongue_out",
        "display_name": "Tongue Out",
        "asset_file": "09_tongue_out.png",
        "hands_count": 0,
        "anchor": ANCHOR_FREE,
        "arm_frames": 5,
        "hold_frames": 10,
        "is_builtin": True,
        "enabled": True,
    },
    {
        "id": "open_mouth",
        "display_name": "Open Mouth / Gasp",
        "asset_file": "10_open_mouth.png",
        "hands_count": 0,
        "anchor": ANCHOR_FREE,
        "arm_frames": 4,
        "hold_frames": 10,
        "is_builtin": True,
        "enabled": True,
    },
    {
        "id": "disgusted",
        "display_name": "Disgusted",
        "asset_file": "11_disgusted.png",
        "hands_count": 0,
        "anchor": ANCHOR_FREE,
        "arm_frames": 5,
        "hold_frames": 10,
        "is_builtin": True,
        "enabled": True,
    },
    {
        "id": "talking_to_wall",
        "display_name": "Talking To Wall",
        "asset_file": "12_talking_to_wall.png",
        "hands_count": 1,
        "anchor": ANCHOR_FREE,
        "arm_frames": 6,
        "hold_frames": 10,
        "is_builtin": True,
        "enabled": True,
    },
    {
        "id": "suspicious",
        "display_name": "Suspicious Eye",
        "asset_file": "13_suspicious.png",
        "hands_count": 0,
        "anchor": ANCHOR_FREE,
        "arm_frames": 8,
        "hold_frames": 10,
        "is_builtin": True,
        "enabled": True,
    },
    {
        "id": "spin",
        "display_name": "Spin Away",
        "asset_file": "14_spin.gif",
        "hands_count": 0,
        "anchor": ANCHOR_FREE,
        "arm_frames": 15,
        "hold_frames": 10,
        "is_builtin": True,
        "enabled": True,
    },
]


@dataclass
class CustomGesture:
    """Represents a registered gesture configuration and its optional calibrated signature."""
    id: str
    display_name: str
    asset_file: str = ""
    hands_count: int = 1
    finger_states: Dict[str, str] = field(default_factory=dict)
    anchor: str = ANCHOR_FREE
    feature_vector: List[float] = field(default_factory=list)
    tolerance: float = DEFAULT_TOLERANCE
    arm_frames: int = DEFAULT_ARM_FRAMES
    hold_frames: int = DEFAULT_HOLD_FRAMES
    is_builtin: bool = False
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def has_calibration(self) -> bool:
        """Returns True if this gesture has an active calibrated feature vector."""
        return bool(self.feature_vector and len(self.feature_vector) == 42)

    def to_signature(self) -> Optional[HandSignature]:
        """Converts calibrated feature vector into a HandSignature for live matching."""
        if not self.has_calibration():
            return None
        return HandSignature(
            vector=list(self.feature_vector),
            finger_states=dict(self.finger_states),
            anchor=self.anchor,
            hands_count=self.hands_count,
            tolerance=self.tolerance,
        )

    def set_signature(self, sig: HandSignature):
        """Sets calibrated signature values on this gesture."""
        self.feature_vector = [float(v) for v in sig.vector]
        self.finger_states = dict(sig.finger_states)
        self.anchor = sig.anchor
        self.hands_count = sig.hands_count
        self.tolerance = sig.tolerance

    def clear_calibration(self):
        """Clears calibration vector and reverts to default algorithmic detection."""
        self.feature_vector = []
        self.finger_states = {}
        self.anchor = ANCHOR_FREE

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CustomGesture":
        return cls(
            id=d["id"],
            display_name=d.get("display_name", d["id"].replace("_", " ").title()),
            asset_file=d.get("asset_file", ""),
            hands_count=d.get("hands_count", 1),
            finger_states=d.get("finger_states", {}),
            anchor=d.get("anchor", ANCHOR_FREE),
            feature_vector=d.get("feature_vector", []),
            tolerance=float(d.get("tolerance", DEFAULT_TOLERANCE)),
            arm_frames=int(d.get("arm_frames", DEFAULT_ARM_FRAMES)),
            hold_frames=int(d.get("hold_frames", DEFAULT_HOLD_FRAMES)),
            is_builtin=bool(d.get("is_builtin", False)),
            enabled=bool(d.get("enabled", True)),
            created_at=d.get("created_at", datetime.utcnow().isoformat() + "Z"),
        )


class CustomGestureRegistry:
    """
    Manages persistent gesture profiles with atomic disk serialization and corruption recovery.
    Stored at %APPDATA%/CleoStream/custom_gestures.json (or custom path).
    """

    def __init__(self, filepath: Optional[str] = None):
        if filepath:
            self.filepath = filepath
        else:
            self.filepath = os.path.join(APP_DATA_DIR, "custom_gestures.json")
        self.gestures: Dict[str, CustomGesture] = {}
        self.load()

    def load(self):
        """Loads gestures from disk, seeding defaults if file is absent or recovering if corrupt."""
        self.gestures.clear()
        if not os.path.exists(self.filepath):
            self.reset_to_defaults()
            return

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            gestures_data = data.get("gestures", [])
            for gd in gestures_data:
                g = CustomGesture.from_dict(gd)
                self.gestures[g.id] = g

            # Ensure any missing builtin gestures are added
            for bg in DEFAULT_BUILTIN_GESTURES:
                if bg["id"] not in self.gestures:
                    self.gestures[bg["id"]] = CustomGesture.from_dict(bg)

        except Exception as e:
            # Corrupted file recovery: back up corrupt file and restore defaults
            print(f"Warning: Corrupt gesture registry at {self.filepath} ({e}). Creating backup.")
            backup_path = f"{self.filepath}.corrupt.{int(time.time())}"
            try:
                shutil.copyfile(self.filepath, backup_path)
            except Exception:
                pass
            self.reset_to_defaults()

    def save(self):
        """Atomically saves current registry to disk via temporary file rename."""
        os.makedirs(os.path.dirname(os.path.abspath(self.filepath)), exist_ok=True)
        tmp_path = f"{self.filepath}.tmp"

        payload = {
            "version": REGISTRY_VERSION,
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "gestures": [g.to_dict() for g in self.gestures.values()],
        }

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            # Atomic replace (supported on both Windows and POSIX in Python 3.3+)
            os.replace(tmp_path, self.filepath)
        except Exception as e:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            raise IOError(f"Failed to atomically write gesture registry to {self.filepath}: {e}")

    def reset_to_defaults(self):
        """Resets registry to the 14 standard built-in gestures and saves to disk."""
        self.gestures.clear()
        for bg in DEFAULT_BUILTIN_GESTURES:
            g = CustomGesture.from_dict(bg)
            self.gestures[g.id] = g
        try:
            self.save()
        except Exception as e:
            print(f"Notice: Could not immediately save defaults to disk: {e}")

    def get(self, gesture_id: str) -> Optional[CustomGesture]:
        """Retrieves a gesture by ID."""
        return self.gestures.get(gesture_id)

    def get_all(self, enabled_only: bool = False) -> List[CustomGesture]:
        """Returns all registered gestures."""
        if enabled_only:
            return [g for g in self.gestures.values() if g.enabled]
        return list(self.gestures.values())

    def get_calibrated(self, enabled_only: bool = True) -> List[CustomGesture]:
        """Returns gestures that have a calibrated feature vector."""
        res = [g for g in self.gestures.values() if g.has_calibration()]
        if enabled_only:
            res = [g for g in res if g.enabled]
        return res

    def get_all_ids(self) -> List[str]:
        """Returns list of all gesture IDs."""
        return list(self.gestures.keys())

    def add_or_update(self, gesture_or_dict: Any) -> CustomGesture:
        """Adds or updates a gesture in the registry and persists to disk."""
        if isinstance(gesture_or_dict, dict):
            gesture = CustomGesture.from_dict(gesture_or_dict)
        elif isinstance(gesture_or_dict, CustomGesture):
            gesture = gesture_or_dict
        else:
            raise TypeError("Expected CustomGesture or dict")

        self.gestures[gesture.id] = gesture
        self.save()
        return gesture

    def delete(self, gesture_id: str) -> bool:
        """
        Deletes a gesture.
        If it's a built-in gesture, resets its calibration and keeps it in registry.
        If it's a custom gesture, removes it completely.
        """
        if gesture_id not in self.gestures:
            return False

        g = self.gestures[gesture_id]
        if g.is_builtin:
            # Revert built-in to uncalibrated factory state
            g.clear_calibration()
            g.enabled = True
        else:
            del self.gestures[gesture_id]

        self.save()
        return True

    def get_arm_frames(self, gesture_id: str) -> int:
        """Returns ARM debounce frame requirement for gesture."""
        g = self.gestures.get(gesture_id)
        if g:
            return g.arm_frames
        return DEFAULT_ARM_FRAMES

    def get_hold_frames(self, gesture_id: str) -> int:
        """Returns hold frames for gesture."""
        g = self.gestures.get(gesture_id)
        if g:
            return g.hold_frames
        return DEFAULT_HOLD_FRAMES
