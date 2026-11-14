#!/usr/bin/env python3
"""kanshi integration: kanshi is the source of truth for display layouts.

Changing the display configuration in MicroControl writes a kanshi profile
for the set of currently connected displays to ~/.config/kanshi/config, then
reloads kanshi, which applies it. kanshi then re-applies the same layout
whenever that set of displays is connected again (hotplug, login, ...).

The profiles MicroControl writes live in a marked block at the top of the
config (kanshi uses the first matching profile, so they take precedence);
anything outside that block is left untouched.

A catch-all profile at the end of the config matches whenever no other
profile does, and runs MicroControl's fallback (see KanshiBackend.fallback),
which turns the displays back on if none of them is, e.g. after unplugging
the only display that was on.
"""

import hashlib
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from utils.logger import LogLevel, Logger

SERVICE = "microcontrol-kanshi.service"

PROFILE_PREFIX = "microcontrol-"
BLOCK_BEGIN = "# >>> microcontrol: display profiles managed by MicroControl (edits in this block are overwritten) >>>"
BLOCK_END = "# <<< microcontrol <<<"
FALLBACK_BEGIN = "# >>> microcontrol: fallback when no other profile matches (edits in this block are overwritten) >>>"
FALLBACK_END = "# <<< microcontrol fallback <<<"
FALLBACK_PROFILE = PROFILE_PREFIX + "fallback"

# Hyprland transform numbers -> kanshi transform names (sway already uses these names)
TRANSFORM_NAMES = {
    "0": "normal", "1": "90", "2": "180", "3": "270",
    "4": "flipped", "5": "flipped-90", "6": "flipped-180", "7": "flipped-270",
}


def config_path() -> str:
    base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(base, "kanshi", "config")


def available() -> bool:
    return shutil.which("kanshi") is not None and shutil.which("kanshictl") is not None


@dataclass
class OutputPlan:
    """How one display should be configured in a profile"""
    criteria: str                      # "Make Model Serial" (or the output name)
    enabled: bool = True
    mode: Optional[str] = None         # "WxH@RHz"; None = preferred mode
    position: Tuple[int, int] = (0, 0)
    scale: float = 1.0
    transform: str = "normal"


@dataclass
class Profile:
    outputs: List[OutputPlan]
    execs: List[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        key = "\n".join(sorted(o.criteria for o in self.outputs))
        return PROFILE_PREFIX + hashlib.sha1(key.encode()).hexdigest()[:8]

    def render(self) -> str:
        lines = [f"profile {self.name} {{"]
        for o in sorted(self.outputs, key=lambda o: o.criteria):
            crit = '"' + o.criteria.replace('"', '') + '"'
            if not o.enabled:
                lines.append(f"\toutput {crit} disable")
                continue
            parts = [f"\toutput {crit} enable", f"mode {o.mode}" if o.mode else "mode preferred",
                     f"position {o.position[0]},{o.position[1]}", f"scale {o.scale:g}",
                     f"transform {o.transform}"]
            lines.append(" ".join(parts))
        for cmd in self.execs:
            lines.append(f"\texec {cmd}")
        lines.append("}")
        return "\n".join(lines) + "\n"


def output_criteria(make: str, model: str, serial: str, name: str) -> str:
    """kanshi identifies displays by "make model serial" ("Unknown" for a
    missing part), which stays the same when the display is plugged into
    another port. Fall back to the output name if nothing is known."""
    parts = [p.strip() if p and p.strip() else "Unknown" for p in (make, model, serial)]
    if parts[0] == "Unknown" and parts[1] == "Unknown":
        return name
    return " ".join(parts)


# --- config file -------------------------------------------------------------

_PROFILE_RE = re.compile(r"(?ms)^profile (\S+) \{\n.*?^\}\n")


def _remove_block(text: str, begin: str, end: str) -> str:
    if begin not in text or end not in text:
        return text
    head, rest = text.split(begin, 1)
    tail = rest.split(end, 1)[1].lstrip("\n")
    return head.rstrip("\n") + "\n" + tail if head.strip() else tail


def _split_config(text: str) -> Tuple[str, Dict[str, str], str]:
    """Split the config into (text before the managed block, managed profiles
    by name, text after it), leaving out the fallback block. Without a
    managed block, everything counts as 'after'."""
    text = _remove_block(text, FALLBACK_BEGIN, FALLBACK_END)
    if BLOCK_BEGIN in text and BLOCK_END in text:
        before, rest = text.split(BLOCK_BEGIN, 1)
        block, after = rest.split(BLOCK_END, 1)
        profiles = {m.group(1): m.group(0) for m in _PROFILE_RE.finditer(block)}
        return before, profiles, after
    return "", {}, text


def read_config() -> str:
    try:
        with open(config_path(), "r") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def write_config(text: str) -> None:
    path = config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def render_fallback(fallback_exec: str) -> str:
    """The catch-all profile: matches any set of displays, so it goes last,
    after the user's own profiles too"""
    return (f"{FALLBACK_BEGIN}\nprofile {FALLBACK_PROFILE} {{\n\t...output *\n"
            f"\texec {fallback_exec}\n}}\n{FALLBACK_END}\n")


def save_profile(profile: Profile, fallback_exec: Optional[str] = None) -> None:
    """Add or replace the managed profile for this set of displays, and the
    catch-all profile running fallback_exec (removed if None)"""
    before, profiles, after = _split_config(read_config())
    profiles[profile.name] = profile.render()
    block = BLOCK_BEGIN + "\n" + "\n".join(profiles[k] for k in sorted(profiles)) + BLOCK_END
    after = after.lstrip("\n")
    text = before + block + ("\n\n" + after if after else "\n")
    if fallback_exec:
        text = text.rstrip("\n") + "\n\n" + render_fallback(fallback_exec)
    write_config(text)


# --- the kanshi daemon ---------------------------------------------------------

def _kanshictl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["kanshictl", *args], capture_output=True, text=True, timeout=10)


def is_running() -> bool:
    try:
        return _kanshictl("status").returncode == 0
    except Exception:
        return False


def ensure_running(logging: Logger) -> bool:
    """Start kanshi if it isn't running: through its systemd user service when
    installed (the package ships it), otherwise as a detached process."""
    if not available():
        logging.log(LogLevel.Error, "kanshi is not installed")
        return False
    if is_running():
        return True

    started = False
    if shutil.which("systemctl"):
        unit = subprocess.run(["systemctl", "--user", "cat", SERVICE], capture_output=True, text=True)
        if unit.returncode == 0:
            # The user manager may not know the compositor's sockets yet
            # (sessions that don't activate graphical-session.target); kanshi
            # needs the Wayland one, the profiles' exec commands the IPC one
            names = [n for n in ("WAYLAND_DISPLAY", "SWAYSOCK", "HYPRLAND_INSTANCE_SIGNATURE")
                     if os.environ.get(n)]
            if names:
                subprocess.run(["systemctl", "--user", "import-environment", *names],
                               capture_output=True)
            result = subprocess.run(["systemctl", "--user", "start", SERVICE], capture_output=True, text=True)
            if result.returncode == 0:
                logging.log(LogLevel.Info, f"Started {SERVICE}")
                started = True
            else:
                logging.log(LogLevel.Warn, f"Couldn't start {SERVICE}: {result.stderr.strip()}")
    if not started:
        logging.log(LogLevel.Info, "Starting kanshi")
        subprocess.Popen(["kanshi"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)

    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if is_running():
            return True
        time.sleep(0.1)
    logging.log(LogLevel.Error, "kanshi didn't start")
    return False


def apply_profile(profile: Profile, logging: Logger, fallback_exec: Optional[str] = None) -> bool:
    """Write the profile to the kanshi config first, then have kanshi apply it"""
    try:
        save_profile(profile, fallback_exec)
    except Exception as e:
        logging.log(LogLevel.Error, f"Failed writing {config_path()}: {e}")
        return False
    logging.log(LogLevel.Info, f"Saved kanshi profile {profile.name}")

    if not ensure_running(logging):
        return False
    result = _kanshictl("reload")
    if result.returncode != 0:
        logging.log(LogLevel.Error, f"kanshictl reload failed: {(result.stderr or result.stdout).strip()}")
        return False
    return True
