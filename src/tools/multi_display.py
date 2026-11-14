#!/usr/bin/env python3
"""Multi-display arrangement (join / mirror / single) and primary display.

Mirrors the GNOME Settings "Display Mode" options on the compositors
MicroControl supports:

* Sway, Hyprland - every change is written as a kanshi profile for the
              connected displays and applied by kanshi (see tools/kanshi.py),
              so it is re-applied whenever those displays are connected again.
              Sway has no native mirroring, so the profile runs ``wl-mirror``;
              on Hyprland it sets a ``mirror`` monitor rule.

Wayland compositors have no notion of a "primary" output, so the primary
display is the anchor of the arrangement: it is placed first (at the origin)
when joining, it is the mirror source, and it is the display kept on in
single mode. The choice is persisted in MicroControl's settings.
"""

import json
import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from utils.logger import LogLevel, Logger
from utils.settings import load_settings, save_settings
from tools.globals import get_current_session
from tools import kanshi

MODE_JOIN = "join"
MODE_MIRROR = "mirror"
MODE_SINGLE = "single"

PRIMARY_SETTING_KEY = "primary_display"

BUILTIN_PREFIXES = ("eDP", "LVDS", "DSI")


@dataclass
class OutputInfo:
    name: str
    description: str = ""
    enabled: bool = False
    # Size of the output in layout coordinates (scale/rotation applied)
    logical_width: int = 0
    logical_height: int = 0
    x: int = 0
    y: int = 0
    # Backend specific mode/scale/transform values, used for restoring
    mode: Optional[str] = None
    rate: Optional[str] = None
    scale: float = 1.0
    transform: str = "normal"
    mirror_of: Optional[str] = None
    # kanshi "make model serial" identifier (Wayland backends)
    criteria: str = ""
    # Pixel size of the preferred mode, to lay out displays that are off
    preferred_size: Optional[Tuple[int, int]] = None

    @property
    def is_builtin(self) -> bool:
        return self.name.startswith(BUILTIN_PREFIXES)


def detect_mode(outputs: List[OutputInfo]) -> str:
    """Infer the current display mode from the output states"""
    enabled = [o for o in outputs if o.enabled]
    if any(o.mirror_of for o in enabled):
        return MODE_MIRROR
    if len(outputs) > 1 and len(enabled) == 1:
        return MODE_SINGLE
    return MODE_JOIN


class DisplayBackend:
    """Base class, subclasses implement the compositor specific parts"""

    name = "none"

    def __init__(self, logging: Logger):
        self.logging = logging

    def list_outputs(self) -> List[OutputInfo]:
        raise NotImplementedError

    def supports_mirror(self) -> bool:
        return True

    def mirror_unavailable_reason(self) -> Optional[str]:
        return None

    def get_primary(self, outputs: List[OutputInfo]) -> Optional[str]:
        names = [o.name for o in outputs]
        if not names:
            return None
        # Single display mode: the display that's on is the primary one, even
        # if another was saved (e.g. the laptop panel turned off elsewhere)
        if detect_mode(outputs) == MODE_SINGLE:
            return next(o.name for o in outputs if o.enabled)
        saved = load_settings(self.logging).get(PRIMARY_SETTING_KEY)
        if saved in names:
            return saved
        enabled = [o for o in outputs if o.enabled and not o.mirror_of]
        if enabled:
            return min(enabled, key=lambda o: (o.x, o.y)).name
        return names[0]

    def save_primary(self, primary: str) -> None:
        settings = load_settings(self.logging)
        if settings.get(PRIMARY_SETTING_KEY) != primary:
            settings[PRIMARY_SETTING_KEY] = primary
            save_settings(settings, self.logging)


# ---------------------------------------------------------------------------
# Wayland compositors: kanshi is the source of truth
# ---------------------------------------------------------------------------

ROTATED_TRANSFORMS = ("90", "270", "flipped-90", "flipped-270")


class KanshiBackend(DisplayBackend):
    """Changes are written to the kanshi config first, then kanshi applies them"""

    # --- compositor specific ------------------------------------------------
    def _kanshi_transform(self, output: OutputInfo) -> str:
        return output.transform or "normal"

    def _mirror_execs(self, source: str, targets: List[str]) -> List[str]:
        """Commands the profile runs to mirror source onto targets"""
        return []

    def _unmirror_execs(self) -> List[str]:
        """Commands the profile runs to make sure nothing is mirrored"""
        return []

    # --- planning -----------------------------------------------------------
    def _pixel_size(self, o: OutputInfo) -> Tuple[int, int]:
        if o.enabled and o.mode and "x" in o.mode:
            w, h = o.mode.split("x", 1)
            return int(w), int(h)
        return o.preferred_size or (1920, 1080)

    def _logical_width(self, o: OutputInfo, scale: float) -> int:
        w, h = self._pixel_size(o)
        if o.enabled and self._kanshi_transform(o) in ROTATED_TRANSFORMS:
            w = h
        return max(1, round(w / scale))

    def _plan(self, o: OutputInfo, enabled: bool = True, position: Tuple[int, int] = (0, 0),
              scale: Optional[float] = None) -> kanshi.OutputPlan:
        if not enabled:
            return kanshi.OutputPlan(o.criteria, enabled=False)
        mode = None  # preferred mode, for displays that are off now
        if o.enabled and o.mode and o.mode != "0x0":
            mode = f"{o.mode}@{o.rate}Hz" if o.rate else o.mode
        if scale is None:
            scale = o.scale if o.enabled else 1.0
        transform = self._kanshi_transform(o) if o.enabled else "normal"
        return kanshi.OutputPlan(o.criteria, True, mode, position, scale, transform)

    def _join_plans(self, outputs: List[OutputInfo], primary: str,
                    scales: Optional[Dict[str, float]] = None) -> List[kanshi.OutputPlan]:
        """All displays on, the primary at the origin, the others to its right
        in their current left-to-right order"""
        scales = scales or {}
        first = next(o for o in outputs if o.name == primary)
        others = sorted((o for o in outputs if o.name != primary),
                        key=lambda o: (not o.enabled, o.x, o.y, o.name))
        plans, x = [], 0
        for o in [first] + others:
            scale = scales.get(o.name, o.scale if o.enabled else 1.0)
            plans.append(self._plan(o, True, (x, 0), scale))
            x += self._logical_width(o, scale)
        return plans

    def _commit(self, plans: List[kanshi.OutputPlan], execs: List[str]) -> bool:
        return kanshi.apply_profile(kanshi.Profile(plans, execs), self.logging)

    # --- operations -----------------------------------------------------------
    def apply(self, mode: str, primary: str) -> bool:
        outputs = self.list_outputs()
        if primary not in [o.name for o in outputs]:
            self.logging.log(LogLevel.Error, f"Display '{primary}' is not connected")
            return False
        self.save_primary(primary)
        self.logging.log(LogLevel.Info, f"Applying display mode '{mode}' with primary '{primary}'")

        if mode == MODE_JOIN:
            return self._commit(self._join_plans(outputs, primary), self._unmirror_execs())
        if mode == MODE_MIRROR:
            if not self.supports_mirror():
                self.logging.log(LogLevel.Error, "Mirroring is not supported on this session")
                return False
            targets = [o.name for o in outputs if o.name != primary]
            return self._commit(self._join_plans(outputs, primary), self._mirror_execs(primary, targets))
        if mode == MODE_SINGLE:
            plans = [self._plan(o, True, (0, 0)) if o.name == primary else self._plan(o, False)
                     for o in outputs]
            return self._commit(plans, self._unmirror_execs())
        self.logging.log(LogLevel.Error, f"Unknown display mode '{mode}'")
        return False

    def set_scale(self, name: str, scale: float) -> bool:
        outputs = self.list_outputs()
        if not any(o.name == name and o.enabled for o in outputs):
            self.logging.log(LogLevel.Error, f"Display '{name}' is not active")
            return False
        self.logging.log(LogLevel.Info, f"Setting scale of {name} to {scale:g}")
        mode = detect_mode(outputs)
        if mode == MODE_JOIN and sum(o.enabled for o in outputs) > 1:
            # Re-lay out so the resized display doesn't leave a gap or overlap
            plans = self._join_plans(outputs, self.get_primary(outputs), {name: scale})
        else:
            plans = [self._plan(o, o.enabled, (o.x, o.y), scale if o.name == name else None)
                     for o in outputs]
        return self._commit(plans, self._current_mirror_execs(outputs))

    def restore(self, snapshot: List[OutputInfo]) -> bool:
        plans = [self._plan(o, o.enabled, (o.x, o.y)) for o in snapshot]
        return self._commit(plans, self._current_mirror_execs(snapshot))

    def _current_mirror_execs(self, outputs: List[OutputInfo]) -> List[str]:
        mirrored = [o for o in outputs if o.enabled and o.mirror_of]
        if not mirrored:
            return self._unmirror_execs()
        return self._mirror_execs(mirrored[0].mirror_of, [o.name for o in mirrored])


# ---------------------------------------------------------------------------
# Sway
# ---------------------------------------------------------------------------

class SwayBackend(KanshiBackend):
    name = "sway"

    def supports_mirror(self) -> bool:
        return shutil.which("wl-mirror") is not None

    def mirror_unavailable_reason(self) -> Optional[str]:
        return None if self.supports_mirror() else "wl-mirror"

    def _mirror_execs(self, source, targets):
        # Sway has no native mirroring: sway_mirror.py moves the targets'
        # workspaces to the source (so they aren't hidden behind the mirror)
        # and shows the source full screen on each target with wl-mirror
        helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sway_mirror.py")
        args = ["python3", helper, source] + list(targets)
        return [" ".join(shlex.quote(a) for a in args)]

    def _unmirror_execs(self):
        return ["pkill -x wl-mirror"] if shutil.which("wl-mirror") else []

    def _running_mirrors(self) -> Dict[str, str]:
        """Return {target_output: source_output} for running wl-mirror processes"""
        mirrors = {}
        try:
            result = subprocess.run(["pgrep", "-a", "-x", "wl-mirror"], capture_output=True, text=True)
        except Exception:
            return mirrors
        for line in result.stdout.splitlines():
            args = line.split()[2:]
            target = None
            positional = []
            i = 0
            while i < len(args):
                arg = args[i]
                if arg == "--fullscreen-output" and i + 1 < len(args):
                    target = args[i + 1]
                    i += 2
                    continue
                if arg.startswith("--fullscreen-output="):
                    target = arg.split("=", 1)[1]
                elif not arg.startswith("-"):
                    positional.append(arg)
                i += 1
            if target and positional:
                mirrors[target] = positional[-1]
        return mirrors

    def list_outputs(self) -> List[OutputInfo]:
        try:
            result = subprocess.run(["swaymsg", "-t", "get_outputs", "-r"], capture_output=True, text=True)
            data = json.loads(result.stdout)
        except Exception as e:
            self.logging.log(LogLevel.Error, f"Failed to query sway outputs: {e}")
            return []

        mirrors = self._running_mirrors()
        outputs = []
        for o in data:
            if o.get("non_desktop"):
                continue
            rect = o.get("rect") or {}
            mode = o.get("current_mode") or {}
            mode_str = rate = None
            if mode.get("width"):
                mode_str = f"{mode['width']}x{mode['height']}"
                rate = f"{mode.get('refresh', 0) / 1000:.3f}"
            modes = o.get("modes") or []
            preferred = (modes[0]["width"], modes[0]["height"]) if modes else None
            scale = o.get("scale") or 1.0
            description = " ".join(p for p in (o.get("make"), o.get("model")) if p and p != "Unknown")
            enabled = bool(o.get("active"))
            outputs.append(OutputInfo(
                name=o["name"],
                description=description,
                enabled=enabled,
                logical_width=rect.get("width", 0),
                logical_height=rect.get("height", 0),
                x=rect.get("x", 0),
                y=rect.get("y", 0),
                mode=mode_str,
                rate=rate,
                scale=scale if scale > 0 else 1.0,
                transform=o.get("transform") or "normal",
                mirror_of=mirrors.get(o["name"]) if enabled else None,
                criteria=kanshi.output_criteria(o.get("make", ""), o.get("model", ""),
                                                o.get("serial", ""), o["name"]),
                preferred_size=preferred,
            ))
        return outputs


# ---------------------------------------------------------------------------
# Hyprland
# ---------------------------------------------------------------------------

class HyprlandBackend(KanshiBackend):
    name = "hyprland"

    def _kanshi_transform(self, output):
        return kanshi.TRANSFORM_NAMES.get(str(output.transform), "normal")

    def _mirror_execs(self, source, targets):
        # Hyprland mirrors natively through a monitor rule (the Lua API on
        # Hyprland 0.55+ Lua configs, which reject `hyprctl keyword`)
        cmds = []
        for t in targets:
            rule = f"{t},preferred,auto,1,mirror,{source}"
            lua = f'hl.monitor({{ output = "{t}", mode = "preferred", position = "auto", scale = 1, mirror = "{source}" }})'
            cmds.append(
                f"out=$(hyprctl keyword monitor '{rule}' 2>&1); "
                f"case \"$out\" in *non-legacy*) hyprctl eval '{lua}';; esac"
            )
        return ["; ".join(cmds)] if cmds else []

    def list_outputs(self) -> List[OutputInfo]:
        try:
            result = subprocess.run(["hyprctl", "-j", "monitors", "all"], capture_output=True, text=True)
            data = json.loads(result.stdout)
        except Exception as e:
            self.logging.log(LogLevel.Error, f"Failed to query Hyprland monitors: {e}")
            return []

        outputs = []
        for m in data:
            width, height = m.get("width", 0), m.get("height", 0)
            scale = m.get("scale") or 1.0
            transform = int(m.get("transform", 0) or 0)
            lw, lh = round(width / scale), round(height / scale)
            if transform % 2 == 1:
                lw, lh = lh, lw
            mirror_of = m.get("mirrorOf")
            if mirror_of in (None, "", "none"):
                mirror_of = None
            preferred = None
            available_modes = m.get("availableModes") or []
            if available_modes:
                res = re.match(r"(\d+)x(\d+)", available_modes[0])
                if res:
                    preferred = (int(res.group(1)), int(res.group(2)))
            description = " ".join(p for p in (m.get("make"), m.get("model")) if p) or m.get("description", "")
            outputs.append(OutputInfo(
                name=m["name"],
                description=description,
                enabled=not m.get("disabled", False),
                logical_width=lw,
                logical_height=lh,
                x=m.get("x", 0),
                y=m.get("y", 0),
                mode=f"{width}x{height}",
                rate=f"{m.get('refreshRate', 60):.2f}",
                scale=scale,
                transform=str(transform),
                mirror_of=mirror_of,
                criteria=kanshi.output_criteria(m.get("make", ""), m.get("model", ""),
                                                m.get("serial", ""), m["name"]),
                preferred_size=preferred,
            ))
        return outputs


# ---------------------------------------------------------------------------

def get_display_backend(logging: Logger) -> Optional[DisplayBackend]:
    """Pick the multi-display backend for the running session, or None if unsupported"""
    session = get_current_session()
    wayland_ok = kanshi.available()
    if (os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") or session == "Hyprland") and shutil.which("hyprctl") and wayland_ok:
        return HyprlandBackend(logging)
    if (os.environ.get("SWAYSOCK") or session == "sway") and shutil.which("swaymsg") and wayland_ok:
        return SwayBackend(logging)
    logging.log(LogLevel.Warn, "Multi-display settings are not supported on this session")
    return None
