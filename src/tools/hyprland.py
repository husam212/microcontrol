#!/usr/bin/env python3

import subprocess

from utils.logger import LogLevel

def set_floating_rule(logger=None):
    """Best-effort runtime float rule for the MicroControl window.

    Hyprland 0.55+ with the Lua config parser rejects `hyprctl keyword`
    with "keyword can't work with non-legacy parsers. Use eval.", so fall
    back to `hyprctl eval 'hl.window_rule(...)'` in that case.
    Output is captured so the message never leaks onto the terminal.
    """
    def _log(level, msg):
        if logger is not None:
            try:
                logger.log(level, msg)
            except Exception:
                pass

    try:
        result = subprocess.run(
            ["hyprctl", "keyword", "windowrule", "float on,match:class ^(microcontrol)$"],
            capture_output=True,
            text=True,
            check=False,
        )
        output = (result.stdout or "") + (result.stderr or "")
        if "non-legacy parsers" in output:
            _log(LogLevel.Info, "Lua Hyprland config detected, setting float rule via eval")
            subprocess.run(
                ["hyprctl", "eval", 'hl.window_rule({ match = { class = "microcontrol" }, float = true })'],
                capture_output=True,
                text=True,
                check=False,
            )
    except Exception as e:
        _log(LogLevel.Warn, f"Failed to set hyprland window rule: {e}")
