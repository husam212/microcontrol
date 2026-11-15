#!/usr/bin/env python3
"""Saved display layouts, one per set of connected displays.

When the display configuration is changed in MicroControl, the layout is
saved for the displays connected at the time; the daemon applies it again
whenever the same set of displays is connected (hotplug, login, ...).
Displays are identified by "make model serial" (see output_criteria), so a
layout still applies when a display is plugged into another port.

Stored in ~/.config/microcontrol/displays.json:

    {"profiles": {"<criteria>|<criteria>": {
        "outputs": [{"criteria": ..., "enabled": ..., "mode": [w, h, mHz],
                     "position": [x, y], "scale": ..., "transform": ...}],
        "mirror": {"source": <criteria>, "targets": [<criteria>, ...]} or null}},
     "primary": <criteria>}

The primary display (see tools/multi_display.py) is stored by criteria too,
so it stays the primary one whichever port it's plugged into.
"""

import json
import os
import threading
from dataclasses import dataclass
from typing import Iterable, List, Optional

from tools.output_management import OutputPlan
from utils.settings import CONFIG_PATH

PROFILES_FILE = os.path.join(CONFIG_PATH, "displays.json")

_lock = threading.Lock()


@dataclass
class Mirror:
    source: str            # criteria
    targets: List[str]


@dataclass
class Profile:
    outputs: List[OutputPlan]
    mirror: Optional[Mirror] = None

    @property
    def key(self) -> str:
        return profile_key(o.criteria for o in self.outputs)


def profile_key(criteria: Iterable[str]) -> str:
    return "|".join(sorted(criteria))


def _read() -> dict:
    try:
        with open(PROFILES_FILE, "r") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write(data: dict) -> None:
    os.makedirs(CONFIG_PATH, exist_ok=True)
    tmp = PROFILES_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, PROFILES_FILE)


def load_profile(criteria: Iterable[str]) -> Optional[Profile]:
    """The saved layout for exactly this set of displays, if any"""
    with _lock:
        entry = _read().get("profiles", {}).get(profile_key(criteria))
    if not entry:
        return None
    try:
        mirror = entry.get("mirror")
        return Profile([OutputPlan.from_dict(o) for o in entry["outputs"]],
                       Mirror(mirror["source"], list(mirror["targets"])) if mirror else None)
    except (KeyError, TypeError, ValueError):
        return None


def save_profile(profile: Profile) -> None:
    with _lock:
        data = _read()
        data.setdefault("profiles", {})[profile.key] = {
            "outputs": [o.to_dict() for o in profile.outputs],
            "mirror": ({"source": profile.mirror.source, "targets": profile.mirror.targets}
                       if profile.mirror else None),
        }
        _write(data)


def load_primary() -> Optional[str]:
    """The primary display's criteria, if one was chosen"""
    with _lock:
        primary = _read().get("primary")
    return primary if isinstance(primary, str) else None


def save_primary(criteria: str) -> None:
    with _lock:
        data = _read()
        if data.get("primary") != criteria:
            data["primary"] = criteria
            _write(data)
