# React in Meetings

[![Latest Release](https://img.shields.io/github/v/release/delightc123/React-in-Meetings?label=Download%20Installer&style=for-the-badge&color=6366f1)](https://github.com/delightc123/React-in-Meetings/releases/latest)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-blue?style=for-the-badge)](https://github.com/delightc123/React-in-Meetings/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald?style=for-the-badge)](https://github.com/delightc123/React-in-Meetings/blob/main/LICENSE)

Pull a face at your webcam. It works out *which* face, and drops the matching meme over your head, scaled to follow you around the frame. You can extend and add more memes to your heart's desire.

Point Zoom, Google Meet, Microsoft Teams, or Discord at its virtual camera and the whole call sees it.

> 📥 **Downloads**:
> - 🪟 **[Download for Windows (ReactInMeetings_Setup.exe)](https://github.com/delightc123/React-in-Meetings/releases/latest)** *(Windows 10/11 Setup Wizard)*
> - 🍏 **[Download for macOS (ReactInMeetings_macOS.dmg)](https://github.com/delightc123/React-in-Meetings/releases/latest)** *(Apple Silicon M1/M2/M3/M4)*  
> *(No Python or command-line required. Built-in auto-updates on both platforms)*

---

## Quick Start — Desktop Application

Run the native PySide6 / Qt6 desktop app with a modern dark theme, live letterboxed preview, visual meme gallery, interactive 7-second calibration wizard, and Windows system tray streaming:

```bash
# Windows One-Click:
run_desktop.bat

# Or via Python:
python app.py
```

### Desktop App Features
- **Live Preview Canvas**: Smooth 30+ FPS preview with letterboxing, camera selector dropdown, and diagnostic HUD toggles.
- **Visual Meme Gallery**: Interactive cards for all 14 reactions with instant 2-second test buttons.
- **Drag-and-Drop Meme Customization**: Drag any `.png`, `.jpg`, or `.gif` straight from your file manager onto a card to replace it live. Original files are safely backed up to your user profile directory.
- **7-Second Calibration Wizard**: Interactive countdown modal with posture alignment guide and instant baseline feedback.
- **Background Meeting Streaming**: Closing `[X]` minimizes the app directly to your system tray so your meeting virtual camera stays active. Explicitly exit anytime via the tray menu.

### macOS (MacBook) Installation & Gatekeeper Note

Because React in Meetings is an independent open-source project without an annual Apple Developer certificate:
1. Open the downloaded `ReactInMeetings_macOS.dmg` and drag **React in Meetings** into `/Applications`.
2. When launching for the first time, if macOS displays *"cannot be opened because Apple cannot check it for malicious software"*:
   - **Right-click** (or Control-click) `ReactInMeetings.app` in `/Applications` → click **Open** → click **Open**, OR
   - Run this one-line command in Terminal:
     ```bash
     xattr -cr /Applications/ReactInMeetings.app
     ```
3. **Virtual Camera on Mac**: To stream composited meme reactions to Zoom, Google Meet, or Microsoft Teams, ensure [OBS Studio](https://obsproject.com/) (free) is installed to provide the macOS CoreMediaIO virtual camera plugin. (Preview mode works without OBS).

---

## CLI Mode

For headless setups, terminal lovers, or quick testing without the full GUI:

```bash
python react_in_meetings_v2.py              # Calibrated engine (preview + virtual camera)
python react_in_meetings_v2.py --no-vcam    # Local preview only
python react_in_meetings_v2.py --calibrate  # 7-second terminal calibration
python react_in_meetings.py                 # Fixed-threshold fallback engine
```

Fourteen reactions out of the box: **time out**, **heart hands**, **hands over face**, **crashing out**, **dancing**, **nose pinch**, **flirty**, **hand up**, **tongue out**, **gasp**, **disgust**, **talking to the wall**, **side-eye**, and **spinning**.

---

## Setup & Installation

```bash
# Create and activate virtual environment (Python 3.11 or 3.12)
python -m venv venv
venv\Scripts\activate              # Linux/macOS: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

> [!NOTE]
> Requires **Python 3.11** or **3.12**. Three MediaPipe task bundles (~15 MB) download automatically on first run into `models/`.

> [!WARNING]
> **Don't unpin the dependencies.** MediaPipe `0.10.30+` (including `1.0.x`) ships macOS wheels that abort the moment they open a detector, so it is pinned at `0.10.21`. That build requires NumPy 1.x, and OpenCV 5 requires NumPy 2 — while MediaPipe `0.10.21` asks for an *unpinned* `opencv-contrib-python`, which quietly drags OpenCV 5 and NumPy 2 back in. That is why the OpenCV pins exist. Unpin one and you have to unpin all three.

---

## Using It in Meetings

The virtual camera is enabled by default. Zoom, Google Meet, Microsoft Teams, Discord, and OBS all treat it as a standard webcam feed.

### 1. Install a Backend (Once)

| Operating System | Setup Step |
| :--- | :--- |
| **macOS** | Install [OBS Studio](https://obsproject.com), open it once to register the virtual device, then quit. |
| **Windows** | Install OBS Studio, or run its virtual camera installer utility. |
| **Linux** | Run `sudo apt install v4l2loopback-dkms` followed by `sudo modprobe v4l2loopback`. |

### 2. Launch the App

The header bar (or console) indicates the target device it publishes to:

```text
Virtual camera: 'OBS Virtual Camera'  <- select this camera in Zoom / Meet
```

### 3. Select the Device in Your Video App

- **Zoom**: `Settings` → `Video` → `Camera` → Select `OBS Virtual Camera`.
- **Google Meet / Teams / Discord**: Look under video device settings.

> [!IMPORTANT]
> **Start React in Meetings before launching your meeting app.** Most meeting clients scan for connected cameras once on launch and won't detect virtual devices registered afterwards.

---

## The 14 Out-of-the-Box Reactions

| Pose | Trigger Gesture |
| :--- | :--- |
| `time_out` | Referee's T — one hand flat horizontally on top, one vertical hand underneath |
| `heart` | Two hands forming a heart — index fingertips together, thumb tips together |
| `cover_nose` | Both hands covering your nose and mouth |
| `crashing_out` | Both hands clutching your head with mouth wide open |
| `dance` | Both hands up behind your head with mouth closed |
| `nose_closed` | Pinch your nose shut |
| `flirty` | One index fingertip resting on your lips |
| `hand_up` | One open palm raised beside your head |
| `tongue_out` | Tongue extended, mouth open |
| `open_mouth` | Dramatic jaw drop / gasp |
| `disgusted` | Scrunch your nose, or brows pulled down into a frown |
| `talking_to_wall` | Hands in frame, gesturing away from camera |
| `suspicious` | Turn your head sideways and squint |
| `spin` | Leave the webcam frame entirely |

Reaction media lives in `assets/`, named after the corresponding pose (e.g. `heart.jpeg`, `spin.gif`). Swap in your own simply by dragging files into the desktop app or dropping a file into `assets/`. JPEG, PNG, and animated GIFs all work seamlessly.

---

## Customizing & Extending

### Swapping a Meme in the Desktop App
1. Open the Desktop App (`run_desktop.bat` or `python app.py`).
2. Drag and drop any image or animated GIF directly from Windows Explorer onto the desired reaction card in the gallery.
3. The app automatically creates a timestamped backup of the original asset in `assets/backups/`, installs the new file, and live-reloads it immediately.

### Adding a New Pose (Developer Guide)

1. **Place Asset**: Save your image/GIF in `assets/` (e.g., `assets/thinking.png`).
2. **Register Pose**: Append the identifier to `POSES` in `engine/decision.py`. The list evaluates top-to-bottom, so place specific poses above generic ones.
3. **Add Detection Logic**: Insert a branch in `decide()` inside [`engine/decision.py`](file:///C:/Software/PROJ/React-in-Meetings/engine/decision.py):
   ```python
   for h in hands:
       if near(h.palm, face.chin, 0.5) and not h.open:
           return "thinking", d
   ```
   *Available features*:
   - `face`: `.nose`, `.chin`, `.mouth`, `.w`, `.h`, `.b("jawOpen")` for any of the 52 blendshapes.
   - `hands`: `.palm`, `.thumb`, `.index`, `.open`.
   - `body`: `.elbows_up`.
   - `m`: Normalized facial expressions measured in standard deviations (sigma).
   - `near(a, b, k)`: Evaluates whether distance is within `k` face-widths (maintains distance invariance).
4. **Tune Stability**: Assign an `ARM` count if the gesture is twitchy, then calibrate against the HUD.

---

## Architecture & How It Works

```text
webcam frame
     │
 1. MediaPipe Tasks    face: 478 landmarks + 52 blendshapes
                       hands: 2 × 21 points
                       body: shoulders, elbows, wrists
     │
 2. Feature Extraction face-relative geometry, tongue color, hand velocity
     │
 3. Baseline Normalization expressions converted to sigma (Z) above YOUR resting face
     │
 4. decide() Engine    ordered rules pass — first matching pose fires
     │
 5. Hysteresis (ARM)   persists N frames to activate, lingers 10 frames after
     │
 Composite Output      scaled to face bounding box, alpha-blended, streamed to vcam & Qt UI
```

### Why Sigma Calibration Wins Over Fixed Thresholds

MediaPipe blendshape values are **never zero when your face is at rest**, and resting baselines differ across individuals:
- Some faces idle at `jawOpen = 0.02`; others sit naturally at `0.19`.
- A resting smile can read `mouthSmile = 0.30` while thinking about nothing.

The engine computes the **mean ($\mu$) and standard deviation ($\sigma$)** across all 52 blendshape channels:

$$z = \frac{\text{reading} - \mu_{\text{neutral}}}{\sigma_{\text{neutral}}}$$

"6 sigma above your resting jaw" produces an identical, reliable trigger across any face.

---

## Project Structure

```text
React-in-Meetings/
├── app.py                      # Desktop application entrypoint (PySide6)
├── run_desktop.bat             # One-click Windows batch launcher
├── react_in_meetings_v2.py     # Calibrated CLI script entrypoint
├── react_in_meetings.py        # Fixed-threshold fallback CLI script
├── calibration.json            # Personalized neutral baseline
├── requirements.txt            # Pinned dependencies (MediaPipe, OpenCV, PySide6)
├── assets/                     # Reaction media library (images & animated GIFs)
│   └── backups/                # Automatic backups from drag-and-drop replacements
├── models/                     # MediaPipe .task bundles (auto-downloaded)
├── engine/                     # Decoupled core vision & detection pipeline
│   ├── detector.py             # MediaPipe task models & scale-invariant geometry
│   ├── decision.py             # Gesture priority rules & sigma thresholds
│   ├── compositor.py           # GIF timing, alpha blending & procedural fallbacks
│   ├── calibration.py          # Baseline metrics collection & posture warnings
│   └── worker.py               # High-performance QThread capture & inference loop
├── ui/                         # Modern PySide6 presentation components
│   ├── styles.py               # Notion/Linear dark theme design tokens & QSS
│   ├── video_widget.py         # QPainter video canvas with letterboxing & HUD
│   ├── asset_grid.py           # 14-card gallery with test keys & drag-and-drop
│   ├── calibration_dialog.py   # 7-second calibration wizard modal dialog
│   ├── tray.py                 # System tray controller & context menu
│   └── main_window.py          # Master window layout & header/footer controls
├── tests/                      # Automated unit & integration test suites
│   ├── test_worker.py          # Worker thread latency & signals
│   ├── test_ui_components.py   # UI widgets & rendering
│   ├── test_app_integration.py # App lifecycle & graceful shutdown
│   └── test_hardening.py       # Malformed asset rejection & camera resilience
├── .rules/                     # Subsystem architecture rules
└── .memory/                    # Progressive disclosure decision & session logs
```

---

## Acknowledgments & Attribution

- Built upon the computer-vision facial reaction prototype [`itsgiving`](https://github.com/gazijarin) by **Gazi Jarin**.
- Modularized, hardened, and transformed into a native desktop application with PySide6 / Qt6, automated installer packaging, drag-and-drop customization, and background meeting stream retention by **Delight Chukwu**.

---

## Author & Maintainer

**Delight Chukwu**  
*React in Meetings Engine*
