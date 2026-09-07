"""Entrypoint for running vkdub via `python -m vkdub`."""

import sys
from vkdub.app import main

if __name__ == "__main__":
    sys.exit(main())
