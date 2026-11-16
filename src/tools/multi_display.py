#!/usr/bin/env python3
"""Multi-display arrangement (join / mirror / single) and primary display.

Mirrors the GNOME Settings "Display Mode" options. Displays are read and
configured through the wlr-output-management protocol (tools/
output_management.py), so this works on any compositor implementing it
(sway, Hyprland, and other wlroots-based ones). Each change is also saved as
the layout for the connected displays (tools/display_profiles.py), which
the daemon re-applies whenever they're connected again.

The protocol has no mirroring, so that part is compositor specific: sway
shows the source on the targets with ``wl-mirror``, Hyprland uses a
``mirror`` monitor rule; other compositors don't support it yet.

Wayland compositors have no notion of a "primary" output, so the primary
display is the anchor of the arrangement: it is placed first (at the origin)
when joining, it is the mirror source, and it is the display kept on in
single mode. The choice is saved with the display layouts.
"""

import json
import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from utils.logger import LogLevel, Logger
from tools import output_management as om
from tools import display_profiles
from tools.display_profiles import Mirror, Profile, load_profile, save_profile
from tools.session import get_current_session

MODE_JOIN = "join"
MODE_MIRROR = "mirror"
MODE_SINGLE = "single"

BUILTIN_PREFIXES = ("eDP", "LVDS", "DSI")


@dataclass
class OutputInfo:
    name: str
    description: str = ""
    enabled: bool = False
    x: int = 0
    y: int = 0
    # Current mode as (width, height, refresh mHz)
    mode: Optional[Tuple[int, int, int]] = None
    scale: float = 1.0
    transform: str = "normal"
    mirror_of: Optional[str] = None
    # "make model serial" identifier, see output_management.output_criteria
    criteria: str = ""
    # Pixel size of the preferred mode, to lay out displays that are off
    preferred_size: Optional[Tuple[int, int]] = None
    # The display's modes, (width, height, refresh mHz), without duplicates
    modes: List[Tuple[int, int, int]] = field(default_factory=list)

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


def _run_commands(cmds: List[str], wait: bool) -> None:
    for cmd in cmds:
        if wait:
            subprocess.run(cmd, shell=True, capture_output=True, timeout=10)
        else:
            subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)


class DisplayBackend:
    """Displays through wlr-output-management; subclasses add mirroring for
    their compositor"""

    name = "wlroots"

    def __init__(self, logging: Logger):
        self.logging = logging

    # --- compositor specific --------------------------------------------------
    def supports_mirror(self) -> bool:
        return False

    def mirror_unavailable_reason(self) -> Optional[str]:
        """Why mirroring is unavailable: "wl-mirror" (not installed), or None
        if it isn't supported at all or is available"""
        return None

    def _mirror_commands(self, source: str, targets: List[str]) -> List[str]:
        """Shell commands showing output source on the target outputs"""
        return []

    def _unmirror_commands(self) -> List[str]:
        """Shell commands making sure nothing is mirrored"""
        return []

    def _mirror_sources(self) -> Dict[str, str]:
        """{target output: source output} for the current mirrors"""
        return {}

    # --- reading --------------------------------------------------------------
    def list_outputs(self) -> List[OutputInfo]:
        try:
            heads = om.get_manager().refresh()
        except om.OutputManagementError as e:
            self.logging.log(LogLevel.Error, f"Failed to read the displays: {e}")
            return []
        mirrors = self._mirror_sources()
        outputs = []
        for h in heads:
            preferred = h.preferred_mode
            description = " ".join(p for p in (h.make, h.model) if p and p != "Unknown")
            outputs.append(OutputInfo(
                name=h.name,
                description=description or h.description,
                enabled=h.enabled,
                x=h.x,
                y=h.y,
                mode=(h.current_mode.width, h.current_mode.height, h.current_mode.refresh)
                if h.enabled and h.current_mode else None,
                scale=h.scale if h.scale > 0 else 1.0,
                transform=h.transform,
                mirror_of=mirrors.get(h.name) if h.enabled else None,
                criteria=h.criteria,
                preferred_size=(preferred.width, preferred.height) if preferred else None,
                modes=sorted({(m.width, m.height, m.refresh) for m in h.modes if m.width and m.height},
                             reverse=True),
            ))
        return outputs

    def get_primary(self, outputs: List[OutputInfo]) -> Optional[str]:
        names = [o.name for o in outputs]
        if not names:
            return None
        # Single display mode: the display that's on is the primary one, even
        # if another was saved (e.g. the laptop panel turned off elsewhere)
        if detect_mode(outputs) == MODE_SINGLE:
            return next(o.name for o in outputs if o.enabled)
        saved = self._saved_primary(outputs)
        if saved:
            return saved
        enabled = [o for o in outputs if o.enabled and not o.mirror_of]
        if enabled:
            return min(enabled, key=lambda o: (o.x, o.y)).name
        return names[0]

    def _saved_primary(self, outputs: List[OutputInfo]) -> Optional[str]:
        """The saved primary display's output name, if it's connected"""
        saved = display_profiles.load_primary()
        return next((o.name for o in outputs if o.criteria == saved), None) if saved else None

    def save_primary(self, primary: str, outputs: Optional[List[OutputInfo]] = None) -> None:
        """Save the output named primary as the primary display"""
        outputs = outputs if outputs is not None else self.list_outputs()
        criteria = next((o.criteria for o in outputs if o.name == primary), None)
        if criteria is None:
            return
        try:
            display_profiles.save_primary(criteria)
        except Exception as e:
            self.logging.log(LogLevel.Error, f"Failed to save the primary display: {e}")

    # --- planning -------------------------------------------------------------
    def _pixel_size(self, o: OutputInfo) -> Tuple[int, int]:
        if o.enabled and o.mode:
            return o.mode[0], o.mode[1]
        return o.preferred_size or (1920, 1080)

    def _logical_width(self, o: OutputInfo, scale: float) -> int:
        w, h = self._pixel_size(o)
        if o.enabled and o.transform in om.ROTATED_TRANSFORMS:
            w = h
        return max(1, round(w / scale))

    def _plan(self, o: OutputInfo, enabled: bool = True, position: Tuple[int, int] = (0, 0),
              scale: Optional[float] = None) -> om.OutputPlan:
        if not enabled:
            return om.OutputPlan(o.criteria, enabled=False)
        if scale is None:
            scale = o.scale if o.enabled else 1.0
        # Displays that are off now get their preferred mode
        return om.OutputPlan(o.criteria, True, o.mode if o.enabled else None, position, scale,
                             o.transform if o.enabled else "normal")

    def _join_plans(self, outputs: List[OutputInfo], primary: str,
                    scales: Optional[Dict[str, float]] = None) -> List[om.OutputPlan]:
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

    def _commit(self, outputs: List[OutputInfo], plans: List[om.OutputPlan],
                mirror: Optional[Tuple[str, List[str]]] = None) -> bool:
        """Save plans (with mirror = (source, targets) output names) as the
        layout for the connected displays, then apply them"""
        criteria = {o.name: o.criteria for o in outputs}
        saved_mirror = Mirror(criteria[mirror[0]], [criteria[t] for t in mirror[1]]) if mirror else None
        try:
            save_profile(Profile(plans, saved_mirror))
        except Exception as e:
            self.logging.log(LogLevel.Error, f"Failed to save the display layout: {e}")
        return self._apply(plans, mirror)

    def _apply(self, plans: List[om.OutputPlan], mirror: Optional[Tuple[str, List[str]]]) -> bool:
        _run_commands(self._unmirror_commands(), wait=True)
        try:
            ok = om.get_manager().apply(plans)
        except om.OutputManagementError as e:
            self.logging.log(LogLevel.Error, f"Failed to configure the displays: {e}")
            return False
        if not ok:
            self.logging.log(LogLevel.Error, "The compositor rejected the display configuration")
            return False
        if mirror:
            _run_commands(self._mirror_commands(*mirror), wait=False)
        return True

    # --- operations -----------------------------------------------------------
    def apply(self, mode: str, primary: str) -> bool:
        outputs = self.list_outputs()
        if primary not in [o.name for o in outputs]:
            self.logging.log(LogLevel.Error, f"Display '{primary}' is not connected")
            return False
        self.save_primary(primary, outputs)
        self.logging.log(LogLevel.Info, f"Applying display mode '{mode}' with primary '{primary}'")

        if mode == MODE_JOIN:
            return self._commit(outputs, self._join_plans(outputs, primary))
        if mode == MODE_MIRROR:
            if not self.supports_mirror():
                self.logging.log(LogLevel.Error, "Mirroring is not supported on this session")
                return False
            targets = [o.name for o in outputs if o.name != primary]
            return self._commit(outputs, self._join_plans(outputs, primary), (primary, targets))
        if mode == MODE_SINGLE:
            plans = [self._plan(o, True, (0, 0)) if o.name == primary else self._plan(o, False)
                     for o in outputs]
            return self._commit(outputs, plans)
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
        return self._commit(outputs, plans, self._current_mirror(outputs))

    def set_mode(self, name: str, mode: Tuple[int, int, int]) -> bool:
        """Set a display's resolution and refresh rate"""
        outputs = self.list_outputs()
        target = next((o for o in outputs if o.name == name and o.enabled), None)
        if target is None:
            self.logging.log(LogLevel.Error, f"Display '{name}' is not active")
            return False
        self.logging.log(LogLevel.Info, f"Setting mode of {name} to {mode[0]}x{mode[1]}@{mode[2] / 1000:g}Hz")
        target.mode = tuple(mode)
        if detect_mode(outputs) == MODE_JOIN and sum(o.enabled for o in outputs) > 1:
            # Re-lay out: the display's width changes with its resolution
            plans = self._join_plans(outputs, self.get_primary(outputs))
        else:
            plans = [self._plan(o, o.enabled, (o.x, o.y)) for o in outputs]
        return self._commit(outputs, plans, self._current_mirror(outputs))

    def restore(self, snapshot: List[OutputInfo]) -> bool:
        plans = [self._plan(o, o.enabled, (o.x, o.y)) for o in snapshot]
        return self._commit(snapshot, plans, self._current_mirror(snapshot))

    def _current_mirror(self, outputs: List[OutputInfo]) -> Optional[Tuple[str, List[str]]]:
        mirrored = [o for o in outputs if o.enabled and o.mirror_of]
        return (mirrored[0].mirror_of, [o.name for o in mirrored]) if mirrored else None

    def apply_saved_layout(self) -> bool:
        """Apply the saved layout for the connected displays (run by the
        daemon when they change). Without one, if none of the displays is on
        (e.g. the only display that was on got unplugged), turn them all on,
        joined, and save that as their layout."""
        outputs = self.list_outputs()
        if not outputs:
            return True
        profile = load_profile(o.criteria for o in outputs)
        if profile is None:
            if any(o.enabled for o in outputs):
                return True
            names = [o.name for o in outputs]
            primary = (self._saved_primary(outputs)
                       or min(outputs, key=lambda o: (not o.is_builtin, o.name)).name)
            self.logging.log(LogLevel.Info, f"No display is on, turning on {', '.join(names)}")
            # The saved primary is left as is, so it's kept for when it's reconnected
            return self._commit(outputs, self._join_plans(outputs, primary))

        names = {o.criteria: o.name for o in outputs}
        mirror = None
        if profile.mirror and profile.mirror.source in names and self.supports_mirror():
            targets = [names[t] for t in profile.mirror.targets if t in names]
            mirror = (names[profile.mirror.source], targets) if targets else None
        heads = {h.criteria: h for h in om.get_manager().refresh()}
        current_mirrors = self._mirror_sources()
        wanted_mirrors = {t: mirror[0] for t in mirror[1]} if mirror else {}
        if (all(om.plan_matches(heads[p.criteria], p) for p in profile.outputs if p.criteria in heads)
                and current_mirrors == wanted_mirrors):
            return True
        self.logging.log(LogLevel.Info, "Applying the saved layout for the connected displays")
        return self._apply(profile.outputs, mirror)


# ---------------------------------------------------------------------------
# Sway
# ---------------------------------------------------------------------------

class SwayBackend(DisplayBackend):
    name = "sway"

    def supports_mirror(self) -> bool:
        return shutil.which("wl-mirror") is not None

    def mirror_unavailable_reason(self) -> Optional[str]:
        return None if self.supports_mirror() else "wl-mirror"

    def _mirror_commands(self, source, targets):
        # Sway has no native mirroring: sway_mirror.py moves the targets'
        # workspaces to the source (so they aren't hidden behind the mirror)
        # and shows the source full screen on each target with wl-mirror
        helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sway_mirror.py")
        args = ["python3", helper, source] + list(targets)
        return [" ".join(shlex.quote(a) for a in args)]

    def _unmirror_commands(self):
        return ["pkill -x wl-mirror"] if shutil.which("wl-mirror") else []

    def _mirror_sources(self) -> Dict[str, str]:
        """{target: source} for the running wl-mirror processes"""
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


# ---------------------------------------------------------------------------
# Hyprland
# ---------------------------------------------------------------------------

class HyprlandBackend(DisplayBackend):
    name = "hyprland"

    def supports_mirror(self) -> bool:
        return True

    def _mirror_commands(self, source, targets):
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

    def _mirror_sources(self) -> Dict[str, str]:
        try:
            result = subprocess.run(["hyprctl", "-j", "monitors", "all"], capture_output=True, text=True)
            data = json.loads(result.stdout)
        except Exception:
            return {}
        mirrors = {}
        for m in data:
            source = m.get("mirrorOf")
            if source not in (None, "", "none"):
                mirrors[m["name"]] = source
        return mirrors


# ---------------------------------------------------------------------------

def get_display_backend(logging: Logger) -> Optional[DisplayBackend]:
    """Pick the multi-display backend for the running session, or None if the
    compositor doesn't support wlr-output-management"""
    try:
        om.get_manager()
    except om.OutputManagementError as e:
        logging.log(LogLevel.Warn, f"Multi-display settings are not supported on this session: {e}")
        return None
    session = get_current_session()
    if (os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") or session == "Hyprland") and shutil.which("hyprctl"):
        return HyprlandBackend(logging)
    if (os.environ.get("SWAYSOCK") or session == "sway") and shutil.which("swaymsg"):
        return SwayBackend(logging)
    return DisplayBackend(logging)
