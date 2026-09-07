import hashlib
import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

DEFAULT_UPDATE_FEED_STABLE = (
    "https://raw.githubusercontent.com/BanhKhuc04/vk-dub-studio/main/latest.json"
)
DEFAULT_UPDATE_FEED_BETA = (
    "https://raw.githubusercontent.com/BanhKhuc04/vk-dub-studio/main/latest-beta.json"
)
MAX_INSTALLER_BYTES = 1024 * 1024 * 1024
SEMVER_PATTERN = re.compile(
    r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


def _is_trusted_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return bool(
        parsed.scheme == "https"
        and parsed.hostname
        and not parsed.username
        and not parsed.password
        and not parsed.fragment
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
    patch_url: str = ""
    patch_sha256: str = ""
    patch_size_bytes: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not SEMVER_PATTERN.fullmatch(self.version):
            raise ValueError("Phiên bản cập nhật không hợp lệ.")
        if not isinstance(self.installer_url, str) or not _is_trusted_https_url(self.installer_url):
            raise ValueError("Đường dẫn tải bản cài đặt không hợp lệ.")
        cleaned_sha = self.sha256.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", cleaned_sha):
            raise ValueError("Mã băm SHA-256 của bản cập nhật không hợp lệ.")
        if not isinstance(self.changelog, tuple):
            raise ValueError("Nhật ký thay đổi không đúng cấu trúc.")
        if not 0 <= self.file_size_bytes <= MAX_INSTALLER_BYTES:
            raise ValueError("Kích thước bản cập nhật không hợp lệ.")

    @property
    def has_patch(self) -> bool:
        """Hot patches are intentionally disabled until updates can be transactional."""
        return False

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
        patch_url = str(data.get("patch_url", "")).strip()
        patch_sha256 = str(data.get("patch_sha256", "")).strip()
        patch_size_bytes = int(data.get("patch_size_bytes", 0))

        return cls(
            version=version,
            published_at=published_at,
            installer_url=installer_url,
            sha256=sha256,
            changelog=changelog,
            file_size_bytes=file_size_bytes,
            patch_url=patch_url,
            patch_sha256=patch_sha256,
            patch_size_bytes=patch_size_bytes,
        )


def fetch_update_info(
    feed_url: str = DEFAULT_UPDATE_FEED_STABLE,
    timeout_sec: float = 8.0,
) -> UpdateInfo | None:
    """Fetch and parse update information from the remote feed URL."""
    if not _is_trusted_https_url(feed_url):
        return None
    try:
        with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
            resp = client.get(feed_url)
            if resp.status_code != 200 or not _is_trusted_https_url(str(resp.url)):
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
    """Download an HTTPS installer atomically and verify its size, type, and hash."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_target = target_path.with_suffix(f"{target_path.suffix}.part")

    if not _is_trusted_https_url(url):
        return False
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256.strip()):
        return False

    try:
        temp_target.unlink(missing_ok=True)
        with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
            with client.stream("GET", url) as response:
                if response.status_code != 200:
                    return False
                final_url = str(getattr(response, "url", url))
                if not _is_trusted_https_url(final_url):
                    return False
                total = int(response.headers.get("content-length", 0) or 0)
                if total < 0 or total > MAX_INSTALLER_BYTES:
                    return False
                downloaded = 0
                header = b""
                with open(temp_target, "xb") as f:
                    for chunk in response.iter_bytes(chunk_size=32768):
                        if is_cancelled and is_cancelled():
                            temp_target.unlink(missing_ok=True)
                            return False
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        header = (header + chunk)[:2]
                        if downloaded > MAX_INSTALLER_BYTES:
                            temp_target.unlink(missing_ok=True)
                            return False
                        if progress_callback:
                            progress_callback(downloaded, total)
                    f.flush()
                    os.fsync(f.fileno())

        if total and downloaded != total:
            temp_target.unlink(missing_ok=True)
            return False
        if header != b"MZ":
            temp_target.unlink(missing_ok=True)
            return False

        # Verify checksum before promoting file
        if not verify_sha256(temp_target, expected_sha256):
            temp_target.unlink(missing_ok=True)
            return False

        os.replace(temp_target, target_path)
        return True
    except Exception:
        temp_target.unlink(missing_ok=True)
        return False


def apply_update_and_restart(
    installer_path: Path,
    expected_sha256: str,
    silent: bool = False,
) -> None:
    """Reverify and launch the full installer without invoking a command shell."""
    if not installer_path.is_file():
        raise FileNotFoundError(f"Tệp cài đặt không tồn tại: {installer_path}")
    with open(installer_path, "rb") as installer:
        if installer.read(2) != b"MZ":
            raise ValueError("Tệp cập nhật không phải bộ cài Windows hợp lệ.")
    if not verify_sha256(installer_path, expected_sha256):
        raise ValueError("Bộ cài đã thay đổi sau khi tải; từ chối cập nhật.")

    args = [str(installer_path.resolve()), "/CLOSEAPPLICATIONS"]
    if silent:
        args.extend(["/SILENT", "/SUPPRESSMSGBOXES"])

    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    subprocess.Popen(
        args,
        creationflags=creation_flags,
        close_fds=True,
    )


def apply_patch_and_restart(patch_zip: Path) -> None:
    """Reject legacy in-place patches, which cannot guarantee rollback safety."""
    raise RuntimeError(
        "Bản vá trực tiếp đã bị vô hiệu hóa để bảo vệ dữ liệu. "
        "Vui lòng cập nhật bằng bộ cài đầy đủ đã xác thực."
    )
