"""
Gesture evaluation, sigma scoring against Baseline, and hysteresis debouncing.
"""
import cv2
import numpy as np
from .detector import dist

POSES = ["time_out", "heart", "cover_nose", "crashing_out", "dance", "nose_closed", "flirty", "hand_up",
         "tongue_out", "open_mouth", "disgusted", "talking_to_wall", "suspicious", "spin"]
TEST_KEYS = "1234567890-=[]"

FACE_SCALE = 2.0
HOLD_FRAMES = 10
ARM = {
    "spin": 15, "suspicious": 8, "talking_to_wall": 6, "dance": 6, "crashing_out": 4,
    "open_mouth": 4, "tongue_out": 5, "disgusted": 5,
}

Z = dict(
    jaw_open=6.0,
    scream_jaw=3.5,
    tongue_jaw=3.5,
    sneer=4.5,
    disgust=14.0,
    squint=4.0,
)
Z_CAP = 8.0
FLOOR = dict(
    jaw_open=0.30,
    scream_jaw=0.18,
    tongue_jaw=0.18,
    sneer=0.06,
    squint=0.18,
)
T = dict(
    tongue=0.5,
    head_turn=0.15,
    gesture=0.035,
)


class Motion:
    """Smoothed hand speed across frames, in face-widths per frame."""

    def __init__(self):
        self.prev, self.energy, self.fw = [], 0.0, 200.0

    def update(self, hands, face):
        if face is not None:
            self.fw = max(face.w, 1.0)
        cur = [h.palm for h in hands]
        speed = 0.0
        if cur and self.prev:
            moved = [min(dist(c, p) for p in self.prev) for c in cur]
            moved = [m for m in moved if m < self.fw]
            if moved:
                speed = max(moved) / self.fw
        self.energy = 0.8 * self.energy + 0.2 * speed
        self.prev = cur
        return self.energy


def measure(face, base):
    """Every expression channel, raw and in sigma above your own neutral."""
    zpair = lambda n: (base.z(n + "Left", face.b(n + "Left")) + base.z(n + "Right", face.b(n + "Right"))) / 2
    pair = lambda n: (face.b(n + "Left") + face.b(n + "Right")) / 2
    m = {
        "jaw": face.b("jawOpen"), "z_jaw": base.z("jawOpen", face.b("jawOpen")),
        "sneer": pair("noseSneer"), "z_sneer": zpair("noseSneer"),
        "z_brow": zpair("browDown"), "z_frown": zpair("mouthFrown"), "z_lip": zpair("mouthUpperUp"),
        "squint": max(pair("eyeSquint"), pair("eyeBlink")),
        "z_squint": max(zpair("eyeSquint"), zpair("eyeBlink")),
        "turn": abs(face.turn_signed - base.neutral_turn),
    }
    cap = lambda v: min(v, Z_CAP)
    m["z_disgust"] = 2 * cap(m["z_sneer"]) + cap(m["z_brow"]) + cap(m["z_frown"]) + cap(m["z_lip"])
    return m


def over(key, m, zkey, rawkey):
    """Sigma above your neutral AND a raw floor, so a tiny sigma can't become a hair trigger."""
    return m[zkey] >= Z[key] and m[rawkey] >= FLOOR[key]


def decide(face, hands, body, tongue, gesture, m, custom_registry=None):
    """Return (pose or None, debug dict)."""
    d = {"hands": len(hands)}
    if face is None:
        gone = not hands and (body is None or not body.seen)
        return ("spin" if gone else None), d

    fw = face.w
    near = lambda a, b, k: dist(a, b) < k * fw
    elbows_up = bool(body and body.elbows_up)
    d.update(m, gesture=gesture, tongue=tongue, elbows_up=elbows_up)
    screaming = over("scream_jaw", m, "z_jaw", "jaw")

    # Priority 1: User-calibrated dynamic gestures evaluated first
    if custom_registry is not None and hands:
        try:
            calibrated = custom_registry.get_calibrated(enabled_only=True)
            if calibrated:
                from .gesture_matcher import extract_hand_signature, is_gesture_matched
                for cg in calibrated:
                    target_sig = cg.to_signature()
                    if not target_sig:
                        continue
                    for h in hands:
                        if hasattr(h, "pts") and h.pts is not None:
                            live_sig = extract_hand_signature(h.pts, face=face)
                            matched, score = is_gesture_matched(live_sig, target_sig, tolerance=cg.tolerance)
                            if matched:
                                d["custom_match"] = cg.id
                                d["custom_score"] = round(score, 4)
                                return cg.id, d
        except Exception as e:
            d["custom_error"] = str(e)

    if len(hands) >= 2:
        a, b = hands[0], hands[1]
        for top, under in ((a, b), (b, a)):
            if top.horizontal and under.vertical and top.palm[1] < under.palm[1] \
                    and near(under.middle, top.palm, 0.6):
                return "time_out", d
        if near(a.index, b.index, 0.3) and near(a.thumb, b.thumb, 0.3) \
                and (a.index[1] + b.index[1]) < (a.thumb[1] + b.thumb[1]):
            return "heart", d
        if near(a.palm, face.mouth, 0.6) and near(b.palm, face.mouth, 0.6):
            return "cover_nose", d
        on_head = lambda h: (h.palm[1] < face.eye_y and abs(h.palm[0] - face.nose[0]) < 1.1 * fw
                             and h.palm[1] > face.top[1] - 0.8 * face.h)
        if on_head(a) and on_head(b) and screaming:
            return "crashing_out", d

    near_head = lambda h: abs(h.palm[0] - face.nose[0]) < 1.3 * fw and h.palm[1] < face.eye_y + 0.3 * face.h
    if elbows_up and all(near_head(h) for h in hands):
        return ("crashing_out" if screaming else "dance"), d

    for h in hands:
        if near(h.thumb, face.nose, 0.35) and near(h.index, face.nose, 0.35) and near(h.thumb, h.index, 0.3):
            return "nose_closed", d
        if near(h.index, face.mouth, 0.22) and not near(h.palm, face.mouth, 0.3):
            return "flirty", d
        if h.open and h.palm[1] < face.nose[1] and abs(h.palm[0] - face.nose[0]) > 0.8 * fw:
            return "hand_up", d

    if tongue > T["tongue"]:
        return "tongue_out", d
    if over("jaw_open", m, "z_jaw", "jaw"):
        return "open_mouth", d
    if over("sneer", m, "z_sneer", "sneer") or m["z_disgust"] >= Z["disgust"]:
        return "disgusted", d
    if hands and gesture > T["gesture"]:
        return "talking_to_wall", d
    if m["turn"] > T["head_turn"] and over("squint", m, "z_squint", "squint"):
        return "suspicious", d
    return None, d


def draw_hud(img, shown, raw, d, face, hands, body, base):
    if face:
        x0, y0, x1, y1 = face.box
        cv2.rectangle(img, (x0, y0), (x1, y1), (0, 255, 0), 1)
    for h in hands:
        cv2.circle(img, (int(h.palm[0]), int(h.palm[1])), 6, (0, 200, 255), -1)
    if body and body.seen:
        for pt in np.vstack([body.shoulders, body.elbows]):
            cv2.circle(img, (int(pt[0]), int(pt[1])), 6, (255, 120, 0), -1)
    g = d.get
    lines = [
        (f"showing: {shown or '-'}   raw: {raw or '-'}   hands: {g('hands', 0)}"
         f"   elbows up: {'Y' if g('elbows_up') else 'n'}", (0, 255, 0)),
        (f"jaw {g('jaw', 0):.2f} = {g('z_jaw', 0):+.1f}s/{Z['jaw_open']:.0f}   "
         f"squint {g('squint', 0):.2f} = {g('z_squint', 0):+.1f}s/{Z['squint']:.0f}   "
         f"tongue {g('tongue', 0):.2f}   turn {g('turn', 0):.2f}   gesture {g('gesture', 0):.3f}", (0, 255, 0)),
        (f"disgust {g('z_disgust', 0):+.1f}s/{Z['disgust']:.0f} = 2x sneer {g('z_sneer', 0):+.1f} "
         f"+ brow {g('z_brow', 0):+.1f} + frown {g('z_frown', 0):+.1f} + lip {g('z_lip', 0):+.1f}", (0, 255, 0)),
        (("NOT CALIBRATED - generic baseline, everything is harder to trigger. press 'c'"
          if base.generic else
          f"calibrated {base.made} on {base.samples} frames   (s = sigma above your neutral)"),
         (0, 140, 255) if base.generic else (200, 200, 200)),
        ("keys: q quit  d hud  c recalibrate  1-9 0 - = [ ] test poses", (0, 255, 0)),
    ]
    for i, (t, colour) in enumerate(lines):
        y = 24 + 22 * i
        cv2.putText(img, t, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3)
        cv2.putText(img, t, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, colour, 1)
