#!/usr/bin/env python3
"""Which compositor the app runs in; GTK-free, so the daemon can use it too"""

import os


def get_current_session():
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if "hyprland" in desktop:
        return "Hyprland"
    elif "sway" in desktop:
        return "sway"
    else:
        return False
