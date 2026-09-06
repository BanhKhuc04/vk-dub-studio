import hashlib
import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

DEFAULT_UPDATE_FEED_STABLE = (
    "https://raw.githubusercontent.com/BanhKhuc04/vk-dub-studio/main/latest.json"
)
DEFAULT_UPDATE_FEED_BETA = (
    "https://raw.githubusercontent.com/BanhKhuc04/vk-dub-studio/main/latest-beta.json"
)


def parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a semantic version string into a comparable tuple of integers."""
    cleaned = version_str.strip().lstrip("vV")
    main_ver = cleaned.split("-")[0]
    parts = []
    for segment in main_ver.split("."):
        segment = re.sub(r"\D", "", segment)
        parts.append(int(segment) if segment else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer_version(remote: str, local: str) -> bool:
    """Return True if remote semantic version is strictly newer than local version."""
    try:
        return parse_version(remote) > parse_version(local)
    except Exception:
        return False


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    published_at: str
    installer_url: str
    sha256: str
    changelog: tuple[str, ...]
    file_size_bytes: int = 0

    def __post_init__(self) -> None:
        if not self.version or not isinstance(self.version, str):
            raise ValueError("Phiên bản cập nhật không hợp lệ.")
        if not self.installer_url or not isinstance(self.installer_url, str):
            raise ValueError("Đường dẫn tải bản cài đặt không hợp lệ.")
        cleaned_sha = self.sha256.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", cleaned_sha):
            raise ValueError("Mã băm SHA-256 của bản cập nhật không hợp lệ.")
        if not isinstance(self.changelog, tuple):
            raise ValueError("Nhật ký thay đổi không đúng cấu trúc.")

    @classmethod
    def from_dict(cls, data: dict) -> "UpdateInfo":
        version = str(data.get("version", "")).strip()
        published_at = str(data.get("published_at", "")).strip()
        installer_url = str(data.get("installer_url", "")).strip()
        sha256 = str(data.get("sha256", "")).strip()
        raw_changelog = data.get("changelog", [])
        if isinstance(raw_changelog, list):
            changelog = tuple(str(item).strip() for item in raw_changelog if str(item).strip())
        elif isinstance(raw_changelog, str):
            changelog = (raw_changelog.strip(),)
        else:
            changelog = ()
        file_size_bytes = int(data.get("file_size_bytes", 0))

        return cls(
            version=version,
            published_at=published_at,
            installer_url=installer_url,
            sha256=sha256,
            changelog=changelog,
            file_size_bytes=file_size_bytes,
        )


def fetch_update_info(
    feed_url: str = DEFAULT_UPDATE_FEED_STABLE,
    timeout_sec: float = 8.0,
) -> UpdateInfo | None:
    """Fetch and parse update information from the remote feed URL."""
    try:
        with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
            resp = client.get(feed_url)
            if resp.status_code != 200:
                return None
            data = resp.json()
            return UpdateInfo.from_dict(data)
    except Exception:
        return None


def verify_sha256(file_path: Path, expected_hash: str) -> bool:
    """Calculate and compare SHA-256 checksum of the specified file."""
    if not file_path.is_file():
        return False
    expected = expected_hash.strip().lower()
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest().lower() == expected


def download_installer(
    url: str,
    target_path: Path,
    expected_sha256: str,
    progress_callback: Callable[[int, int], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
    timeout_sec: float = 60.0,
) -> bool:
    """Stream download installer file and verify SHA-256 checksum."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_target = target_path.with_suffix(f"{target_path.suffix}.tmp")

    try:
        with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
            with client.stream("GET", url) as response:
                if response.status_code != 200:
                    return False
                total = int(response.headers.get("content-length", 0))
                downloaded = 0
                with open(temp_target, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=32768):
                        if is_cancelled and is_cancelled():
                            temp_target.unlink(missing_ok=True)
                            return False
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total)

        # Verify checksum before promoting file
        if not verify_sha256(temp_target, expected_sha256):
            temp_target.unlink(missing_ok=True)
            return False

        if target_path.exists():
            target_path.unlink()
        temp_target.rename(target_path)
        return True
    except Exception:
        temp_target.unlink(missing_ok=True)
        return False


def launch_installer(installer_path: Path) -> subprocess.Popen:
    """Launch the downloaded Windows installer executable."""
    if not installer_path.is_file():
        raise FileNotFoundError(f"Tệp cài đặt không tồn tại: {installer_path}")
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    return subprocess.Popen([str(installer_path)], creationflags=creation_flags)


def apply_update_and_restart(installer_path: Path, silent: bool = False) -> None:
    """Launch installer to upgrade the application, then relaunch VK Dub Studio.

    Writes a temporary .bat file to avoid cmd.exe escaping issues with
    backslash paths on Windows.
    """
    import sys
    import tempfile

    if not installer_path.is_file():
        raise FileNotFoundError(f"Tệp cài đặt không tồn tại: {installer_path}")

    # Resolve the app executable path
    exe_path = sys.executable if getattr(sys, "frozen", False) else ""
    target_exe = (
        Path(exe_path).resolve()
        if exe_path
        else Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "VK Dub Studio" / "VK Dub Studio.exe"
    )

    installer_abs = str(installer_path.resolve())
    target_abs = str(target_exe)
    args = "/SILENT /CLOSEAPPLICATIONS" if silent else "/CLOSEAPPLICATIONS"

    # Write a temporary .bat file — avoids backslash escaping issues when
    # passing long paths inline to cmd.exe /c "..."
    bat_lines = [
        "@echo off",
        "timeout /t 2 /nobreak >nul",
        f'start "" /wait "{installer_abs}" {args}',
        f'if exist "{target_abs}" start "" "{target_abs}"',
    ]
    bat_content = "\r\n".join(bat_lines) + "\r\n"

    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".bat",
        prefix="vkdub_update_",
        delete=False,
        encoding="utf-8",
    )
    tmp.write(bat_content)
    tmp.close()

    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    subprocess.Popen(
        ["cmd.exe", "/c", tmp.name],
        creationflags=creation_flags,
        close_fds=True,
    )
