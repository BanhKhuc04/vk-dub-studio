import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent / "src"
if src_dir.is_dir() and str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))


def _run() -> int:
    args = sys.argv[1:]
    if args and args[0] == "--vkdub-smoke-test":
        return 0
    if len(args) == 3 and args[0] == "--vkdub-transcription-worker":
        from vkdub.services.transcription_runner import main as run_transcription_worker

        sys.argv = ["vkdub.services.transcription_runner", args[1], args[2]]
        return run_transcription_worker()
    if args and args[0] == "--native-host":
        from vkdub.bridge.native_host import main as run_native_host

        run_native_host()
        return 0

    from vkdub.app import main

    return main()


if __name__ == "__main__":
    raise SystemExit(_run())
