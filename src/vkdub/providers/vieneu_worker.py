"""Isolated SDK worker. Executed by the dedicated VieNeu Python environment."""

import contextlib
import io
import json
import sys
import traceback
from pathlib import Path
from typing import Any, cast


def main() -> None:
    cast(io.TextIOWrapper, sys.stdin).reconfigure(encoding="utf-8")
    cast(io.TextIOWrapper, sys.stdout).reconfigure(encoding="utf-8")
    engine: Any = None
    for line in sys.stdin:
        try:
            request = json.loads(line)
            with contextlib.redirect_stdout(sys.stderr):
                if engine is None:
                    from vieneu import Vieneu

                    engine = Vieneu(backend="onnx", precision="fp32")
                operation = request["operation"]
                if operation == "catalog":
                    result = {"voices": engine.list_preset_voices()}
                elif operation == "synthesize":
                    voice = request["voice"]
                    if voice["custom"]:
                        import numpy as np

                        profile = json.loads(Path(voice["profile"]).read_text(encoding="utf-8"))
                        profile["speaker_emb"] = np.asarray(
                            profile["speaker_emb"], dtype=np.float32
                        )
                        if profile["codes"] is not None:
                            profile["codes"] = np.asarray(profile["codes"], dtype=np.int64)
                        kwargs = {"voice": profile}
                    else:
                        kwargs = {"voice": voice["upstream_id"]}
                    audio = engine.infer(request["text"], **kwargs)
                    output = Path(request["output"])
                    engine.save(audio, str(output))
                    result = {"output": str(output), "samples": len(audio)}
                elif operation == "register":
                    # Exercise the backend's actual voice enrollment before accepting it.
                    engine.add_voice(request["name"], request["reference"], denoise=False)
                    profile = engine.get_preset_voice(request["name"])
                    saved = {
                        key: value.tolist() if hasattr(value, "tolist") else value
                        for key, value in profile.items()
                    }
                    Path(request["profile"]).write_text(json.dumps(saved), encoding="utf-8")
                    result = {"registered": True}
                else:
                    raise ValueError("Unsupported worker operation")
            reply = {"ok": True, "result": result}
        except Exception:
            traceback.print_exc(file=sys.stderr)
            reply = {
                "ok": False,
                "error": "VieNeu chưa hoàn thành. Kiểm tra model hoặc mẫu giọng, "
                "rồi thử lại. Chi tiết được lưu trong log Voice.",
            }
        print("VKDUB_RESULT " + json.dumps(reply, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
