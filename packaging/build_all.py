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
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add src to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from vkdub.version import APP_BRANDING, __version__  # noqa: E402


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


def build_patch_zip(dist_dir: Path) -> Path:
    """Build lightweight update patch zip (~2-4 MB) excluding heavy offline models and tools."""
    import zipfile

    print("\n=======================================================")
    print(f" 2.5. BUILDING LIGHTWEIGHT PATCH PACKAGE (v{__version__})")
    print("=======================================================")
    patch_file = ROOT / "dist" / f"VKDubStudio-Patch-{__version__}.zip"
    if patch_file.exists():
        patch_file.unlink()

    # Unchanging static binary packages to exclude from lightweight patch
    exclude_dirs = {
        "models",
        "tools",
        "PySide6",
        "playwright",
        "ctranslate2",
        "onnxruntime",
        "numpy.libs",
        "av.libs",
        "numpy",
        "av",
        "shiboken6",
        "torch",
        "hf_xet",
        "tokenizers",
        "scipy",
        "sounddevice",
        "PIL",
    }

    with zipfile.ZipFile(patch_file, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root, _dirs, files in os.walk(dist_dir):
            rel_root = Path(root).relative_to(dist_dir)
            if any(part in exclude_dirs for part in rel_root.parts):
                continue
            for file in files:
                full_path = Path(root) / file
                arc_name = str(rel_root / file) if str(rel_root) != "." else file
                zf.write(full_path, arc_name)

    patch_size_mb = patch_file.stat().st_size / (1024 * 1024)
    print(f"✓ Lightweight patch created successfully at:\n  {patch_file} ({patch_size_mb:.2f} MB)")
    return patch_file


def update_manifest(installer_path: Path, patch_path: Path | None = None) -> Path:
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
            "Hỗ trợ Bản cập nhật siêu nhẹ (Hot-patch ~3MB): Tải nhanh trong 2 giây "
            "thay vì tải lại toàn bộ bộ cài 300MB",
            "Bảo toàn toàn bộ dự án, cấu hình và phiên đăng nhập qua các lần cập nhật",
        ],
    }

    if patch_path and patch_path.is_file():
        manifest["patch_url"] = (
            "https://github.com/BanhKhuc04/vk-dub-studio/releases/download/"
            f"v{__version__}/{patch_path.name}"
        )
        manifest["patch_sha256"] = calculate_sha256(patch_path)
        manifest["patch_size_bytes"] = patch_path.stat().st_size

    manifest_file = ROOT / "packaging" / "latest.json"
    content = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    manifest_file.write_text(content, encoding="utf-8")
    (ROOT / "latest.json").write_text(content, encoding="utf-8")
    print(f"✓ Manifest updated at {manifest_file} and {ROOT / 'latest.json'}:")
    print(f"  • Version:     v{__version__}")
    print(f"  • Installer:   {file_size / (1024 * 1024):.2f} MB")
    if patch_path and patch_path.is_file():
        print(
            "  • Patch Size:  "
            f"{patch_path.stat().st_size / (1024 * 1024):.2f} MB "
            "(Tiết kiệm 99% dung lượng!)"
        )
    return manifest_file


def main() -> None:
    print("*******************************************************")
    print(f" {APP_BRANDING}")
    print(f" Production Packaging & Installer Pipeline (v{__version__})")
    print("*******************************************************")

    iscc = find_iscc()
    if not iscc:
        print("ERROR: Inno Setup Compiler (ISCC.exe) not found on system.", file=sys.stderr)
        sys.exit(1)
    print(f"Found Inno Setup Compiler: {iscc}")

    stage_tools()
    dist_dir = build_pyinstaller()
    patch_file = build_patch_zip(dist_dir)
    installer = build_installer(iscc)
    manifest = update_manifest(installer, patch_file)

    print("\n=======================================================")
    print(" SUCCESSFUL PRODUCTION BUILD SUMMARY")
    print("=======================================================")
    print(f" 1. Application Bundle:  {dist_dir}")
    print(f" 2. Lightweight Patch:   {patch_file}")
    print(f" 3. Windows Installer:   {installer}")
    print(f" 4. Update Manifest:     {manifest}")
    print("=======================================================\n")


if __name__ == "__main__":
    main()
