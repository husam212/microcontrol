#!/usr/bin/env python3
"""Turn the connected displays back on when none of them is; run by the
catch-all kanshi profile MicroControl writes (see tools/kanshi.py).

    display_fallback.py sway|hyprland
"""

import os
import sys

# Import the project's modules from src/, not from tools/ (this script's directory)
sys.path[0] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from utils.arg_parser import ArgParse
from utils.logger import Logger
from tools.multi_display import BACKENDS


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in BACKENDS:
        print(f"usage: {sys.argv[0]} {'|'.join(BACKENDS)}", file=sys.stderr)
        return 2
    logging = Logger(ArgParse(["display_fallback", "--log", "2"]))
    return 0 if BACKENDS[sys.argv[1]](logging).fallback() else 1


if __name__ == "__main__":
    sys.exit(main())
