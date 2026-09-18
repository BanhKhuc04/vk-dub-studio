import base64
from pathlib import Path
repo_root = Path(r"D:\Work\Project_AI\ToolVideo")
frontend_dir = repo_root / "frontend"
logo_path = frontend_dir / "logo.png"
logo_base64 = "data:image/png;base64," + base64.b64encode(logo_path.read_bytes()).decode("utf-8")
