#!/usr/bin/env python3
"""Master build automation script for VK Dub Studio Windows Production Release.

Workflow:
1. Load version from single source of truth (src/vkdub/version.py)
2. Ensure bundled tools (ffmpeg, ffprobe) are staged in tools/
3. Run PyInstaller to produce dist/VK Dub Studio/ onedir bundle
4. Run Inno Setup Compiler (ISCC) to build VKDubStudio-Setup-X.Y.Z.exe
5. Calculate SHA-256 hash and update packaging/latest.json
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

# Add src to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from vkdub.version import APP_BRANDING, __version__  # noqa: E402


def verify_version_sync() -> None:
    """Fail the build when package, runtime, and installer versions drift."""
    package_data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_version = str(package_data["project"]["version"])
    installer_text = (ROOT / "installer" / "VK-Dub-Studio.iss").read_text(encoding="utf-8")
    match = re.search(r'#define MyAppVersion "([^"]+)"', installer_text)
    installer_version = match.group(1) if match else ""
    versions = {
        "runtime": __version__,
        "package": package_version,
        "installer": installer_version,
    }
    if len(set(versions.values())) != 1:
        details = ", ".join(f"{name}={value or '<missing>'}" for name, value in versions.items())
        raise RuntimeError(f"Release version mismatch: {details}")


def find_iscc() -> Path | None:
    """Locate Inno Setup compiler executable (ISCC.exe)."""
    if found := shutil.which("iscc"):
        return Path(found)
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"))
        / "Inno Setup 6"
        / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Inno Setup 6" / "ISCC.exe",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def calculate_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


def stage_tools() -> None:
    tools_dir = ROOT / "tools"
    tools_dir.mkdir(exist_ok=True)
    for tool_name in ("ffmpeg", "ffprobe"):
        dest = tools_dir / f"{tool_name}.exe"
        if dest.is_file() and dest.stat().st_size > 1000:
            continue
        found = shutil.which(tool_name)
        if found and Path(found).is_file():
            print(f"Copying {tool_name} from {found} to {dest}...")
            shutil.copy2(found, dest)
        else:
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            if local_appdata:
                pkg_dir = Path(local_appdata) / "Microsoft" / "WinGet" / "Packages"
                matches = list(pkg_dir.glob(f"**/{tool_name}.exe"))
                if matches and matches[0].is_file():
                    print(f"Copying {tool_name} from {matches[0]} to {dest}...")
                    shutil.copy2(matches[0], dest)


def build_pyinstaller() -> Path:
    print("\n=======================================================")
    print(f" 1. BUILDING PYINSTALLER ONEDIR BUNDLE (v{__version__})")
    print("=======================================================")
    spec_file = ROOT / "packaging" / "vkdub.spec"
    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "-y", str(spec_file)]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(ROOT), check=True)

    dist_dir = ROOT / "dist" / "VK Dub Studio"
    exe_file = dist_dir / "VK Dub Studio.exe"
    if not exe_file.is_file():
        raise FileNotFoundError(f"PyInstaller build failed to produce {exe_file}")

    print(f"✓ PyInstaller bundle created successfully at:\n  {dist_dir}")
    return dist_dir


def build_installer(iscc_path: Path) -> Path:
    print("\n=======================================================")
    print(f" 2. COMPILING INNO SETUP INSTALLER (v{__version__})")
    print("=======================================================")
    iss_file = ROOT / "installer" / "VK-Dub-Studio.iss"
    cmd = [
        str(iscc_path),
        f"/DMyAppVersion={__version__}",
        str(iss_file),
    ]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(ROOT / "installer"), check=True)

    installer_file = ROOT / "dist" / f"VKDubStudio-Setup-{__version__}.exe"
    if not installer_file.is_file():
        alt = ROOT / "dist" / "VK-Dub-Studio-Setup-x64.exe"
        if alt.is_file():
            alt.rename(installer_file)

    if not installer_file.is_file():
        raise FileNotFoundError(f"Inno Setup failed to produce {installer_file}")

    print(f"✓ Installer created successfully at:\n  {installer_file}")
    return installer_file


def update_manifest(installer_path: Path) -> Path:
    print("\n=======================================================")
    print(" 3. GENERATING UPDATE MANIFEST (latest.json)")
    print("=======================================================")
    sha256 = calculate_sha256(installer_path)
    file_size = installer_path.stat().st_size
    now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    manifest = {
        "version": __version__,
        "published_at": now_iso,
        "installer_url": f"https://github.com/BanhKhuc04/vk-dub-studio/releases/download/v{__version__}/{installer_path.name}",
        "sha256": sha256,
        "file_size_bytes": file_size,
        "changelog": [
            f"VK Dub Studio v{__version__} — Bản cập nhật vá lỗi và cải tiến trải nghiệm",
            "Bổ sung quy trình Vbee thủ công: Tải file SRT tiếng Việt về máy và "
            "Nhập file audio Vbee để tự động cắt ghép, đồng bộ",
            "Vá triệt để lỗi kết nối CapCut Voice: Tích hợp sẵn bộ SDK và chuyển sang "
            "thực thi trực tiếp in-process (không cần subprocess)",
            "Vá triệt để lỗi kết nối VieNeu: Tự động dò tìm Python hệ thống, không còn "
            "lỗi khi gọi từ bản đóng gói .exe",
            "Cập nhật an toàn bằng bộ cài đầy đủ qua HTTPS, xác thực SHA-256 trước khi chạy",
            "Bảo toàn toàn bộ dự án, cấu hình và phiên đăng nhập qua các lần cập nhật",
        ],
    }

    manifest_file = ROOT / "packaging" / "latest.json"
    content = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    manifest_file.write_text(content, encoding="utf-8")
    (ROOT / "latest.json").write_text(content, encoding="utf-8")
    print(f"✓ Manifest updated at {manifest_file} and {ROOT / 'latest.json'}:")
    print(f"  • Version:     v{__version__}")
    print(f"  • Installer:   {file_size / (1024 * 1024):.2f} MB")
    return manifest_file


def main() -> None:
    print("*******************************************************")
    print(f" {APP_BRANDING}")
    print(f" Production Packaging & Installer Pipeline (v{__version__})")
    print("*******************************************************")

    verify_version_sync()
    iscc = find_iscc()
    if not iscc:
        print("ERROR: Inno Setup Compiler (ISCC.exe) not found on system.", file=sys.stderr)
        sys.exit(1)
    print(f"Found Inno Setup Compiler: {iscc}")

    stage_tools()
    dist_dir = build_pyinstaller()
    installer = build_installer(iscc)
    manifest = update_manifest(installer)

    print("\n=======================================================")
    print(" SUCCESSFUL PRODUCTION BUILD SUMMARY")
    print("=======================================================")
    print(f" 1. Application Bundle:  {dist_dir}")
    print(f" 2. Windows Installer:   {installer}")
    print(f" 3. Update Manifest:     {manifest}")
    print("=======================================================\n")


if __name__ == "__main__":
    main()
