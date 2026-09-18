# Wrapper package to expose src/vkdub as top-level package
import os
from pathlib import Path
# Extend __path__ to include the actual source directory
_src_path = Path(__file__).resolve().parent.parent / "src" / "vkdub"
if _src_path.is_dir():
    __path__.append(str(_src_path))
else:
    raise ImportError(f"Source package not found at {_src_path}")
