"""Minimal entry point for the GUI and frozen worker processes."""

import sys


def _run() -> int:
    args = sys.argv[1:]
    if args and args[0] == "--vkdub-smoke-test":
        return 0
    if len(args) == 3 and args[0] == "--vkdub-transcription-worker":
        from vkdub.services.transcription_runner import main as run_transcription_worker

        sys.argv = ["vkdub.services.transcription_runner", args[1], args[2]]
        return run_transcription_worker()

    from vkdub.app import main

    return main()


if __name__ == "__main__":
    raise SystemExit(_run())
