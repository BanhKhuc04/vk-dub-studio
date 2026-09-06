import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    spec_file = root / "packaging" / "vkdub.spec"

    print("==================================================")
    print("VK Dub Studio — Build Standalone Windows App")
    print("==================================================")
    print(f"Project root: {root}")
    print(f"Spec file:    {spec_file}")

    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "-y", str(spec_file)]
    print(f"Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(root))
    if result.returncode != 0:
        print("Build failed!", file=sys.stderr)
        sys.exit(result.returncode)

    dist_dir = root / "dist" / "VK Dub Studio"
    exe_file = dist_dir / "VK Dub Studio.exe"
    if exe_file.is_file():
        print("--------------------------------------------------")
        print(f"BUILD SUCCESSFUL: {exe_file}")
        print(f"Output directory ready for Inno Setup: {dist_dir}")
        print("--------------------------------------------------")
    else:
        print("Build completed but executable was not found!", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
