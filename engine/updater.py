"""
React in Meetings — Auto-Update Subsystem
Connects to GitHub Releases API to check for new releases and download installers.
"""
import os
import sys
import re
import json
import tempfile
import subprocess
import urllib.request
import urllib.error
from typing import Optional, Tuple, Dict, Any

from PySide6.QtCore import QThread, Signal

from .version import __version__, GITHUB_REPO


def parse_version(v_str: str) -> Tuple[int, ...]:
    """Parse version string into an integer tuple for comparison."""
    # Find all numeric components (e.g. 'v1.2.3' -> [1, 2, 3])
    digits = re.findall(r"\d+", v_str)
    if not digits:
        return (0, 0, 0)
    return tuple(int(d) for d in digits)


def is_newer_version(remote: str, current: str = __version__) -> bool:
    """Returns True if remote version is strictly newer than current version."""
    return parse_version(remote) > parse_version(current)


def check_for_updates_sync(repo: str = GITHUB_REPO, current: str = __version__) -> Dict[str, Any]:
    """
    Synchronously queries GitHub Releases API for the latest release.
    Returns dictionary with update info or error.
    """
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"ReactInMeetings/{current} (Windows; x64)",
            "Accept": "application/vnd.github.v3+json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status != 200:
                return {"has_update": False, "error": f"HTTP {response.status}"}
            payload = json.loads(response.read().decode("utf-8"))

        tag_name = payload.get("tag_name", "")
        release_name = payload.get("name", tag_name)
        release_notes = payload.get("body", "")
        html_url = payload.get("html_url", "")

        # Find .exe setup installer in release assets
        assets = payload.get("assets", [])
        installer_url = ""
        installer_name = ""
        installer_size = 0

        for asset in assets:
            name = asset.get("name", "").lower()
            if name.endswith(".exe"):
                installer_url = asset.get("browser_download_url", "")
                installer_name = asset.get("name", "")
                installer_size = asset.get("size", 0)
                if "setup" in name:
                    # Prefer dedicated setup installer
                    break

        newer = is_newer_version(tag_name, current)

        return {
            "has_update": newer,
            "current_version": current,
            "remote_version": tag_name,
            "release_name": release_name,
            "notes": release_notes,
            "html_url": html_url,
            "installer_url": installer_url,
            "installer_name": installer_name,
            "installer_size": installer_size,
        }
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # No releases published yet
            return {"has_update": False, "error": "No releases published yet on GitHub"}
        return {"has_update": False, "error": f"GitHub API error: {e.code}"}
    except Exception as e:
        return {"has_update": False, "error": str(e)}


class UpdateCheckWorker(QThread):
    """Background worker to check for updates without freezing the Qt main loop."""
    check_finished = Signal(dict)

    def __init__(self, repo: str = GITHUB_REPO, current: str = __version__, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current = current

    def run(self):
        result = check_for_updates_sync(self.repo, self.current)
        self.check_finished.emit(result)


class UpdateDownloadWorker(QThread):
    """Background worker to download the update installer with progress reporting."""
    progress = Signal(int, int)        # (bytes_downloaded, total_bytes)
    download_finished = Signal(str)   # local_file_path
    download_failed = Signal(str)     # error_message

    def __init__(self, download_url: str, filename: str = "ReactInMeetings_Setup.exe", parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self.filename = filename
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        if not self.download_url:
            self.download_failed.emit("No download URL provided for installer.")
            return

        try:
            temp_dir = tempfile.gettempdir()
            dest_path = os.path.join(temp_dir, self.filename)

            req = urllib.request.Request(
                self.download_url,
                headers={"User-Agent": "ReactInMeetings-Updater"},
            )

            with urllib.request.urlopen(req, timeout=15) as response:
                total_size = int(response.headers.get("content-length", 0))
                downloaded = 0
                chunk_size = 64 * 1024  # 64 KB chunks

                with open(dest_path, "wb") as f:
                    while True:
                        if self._is_cancelled:
                            self.download_failed.emit("Download cancelled by user.")
                            return

                        chunk = response.read(chunk_size)
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded += len(chunk)
                        self.progress.emit(downloaded, total_size)

            self.download_finished.emit(dest_path)
        except Exception as e:
            self.download_failed.emit(f"Download failed: {str(e)}")


def launch_installer_and_exit(installer_path: str):
    """
    Executes the downloaded Windows setup installer and shuts down the current process.
    Uses shell=False to safely handle paths containing spaces without cmd.exe mangling.
    """
    if not os.path.isfile(installer_path):
        raise FileNotFoundError(f"Installer not found at {installer_path}")

    # Launch installer detached so it continues after this app exits
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

    subprocess.Popen([installer_path], shell=False, creationflags=creation_flags)
    sys.exit(0)
