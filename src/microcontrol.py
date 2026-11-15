#!/usr/bin/env python3
"""MicroControl entry point.

    microcontrol [options]      open the control panel window
    microcontrol --daemon       run the background daemon (re-applies display
                                layouts on hotplug, and other event-driven
                                features); window options are ignored

The mode is picked before anything else is imported, so the daemon never
loads GTK.
"""

import sys

from utils.arg_parser import ArgParse


def main() -> None:
    if ArgParse(sys.argv).find_arg(("", "--daemon")):
        from services.daemon import main as daemon_main
        sys.exit(daemon_main(sys.argv))

    from ui.app import initialize_and_start
    initialize_and_start()


if __name__ == "__main__":
    main()
