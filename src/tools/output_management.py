#!/usr/bin/env python3
"""Reading and changing the display configuration through the
wlr-output-management Wayland protocol, which sway, Hyprland and other
wlroots-based compositors implement (the same protocol kanshi uses).

Each process has one connection (get_manager()). The app refreshes it when
it needs the current state; the daemon also watches it for changes (displays
plugged in or out), see services/display_service.py.

The protocol bindings in protocols/ are generated from the protocol's XML
with pywayland's scanner:

    python -m pywayland.scanner -i protocols/wlr-output-management-unstable-v1.xml -o protocols
"""

import atexit
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from pywayland.client import Display

from protocols.wlr_output_management_unstable_v1 import ZwlrOutputManagerV1

MANAGER_VERSION = 4

# wl_output.transform values <-> names
TRANSFORMS = ["normal", "90", "180", "270", "flipped", "flipped-90", "flipped-180", "flipped-270"]
ROTATED_TRANSFORMS = ("90", "270", "flipped-90", "flipped-270")


class OutputManagementError(Exception):
    pass


@dataclass
class Mode:
    width: int = 0
    height: int = 0
    refresh: int = 0          # mHz, 0 if unknown
    preferred: bool = False
    proxy: object = None


@dataclass
class Head:
    name: str = ""
    description: str = ""
    make: str = ""
    model: str = ""
    serial: str = ""
    enabled: bool = False
    modes: List[Mode] = field(default_factory=list)
    current_mode: Optional[Mode] = None
    x: int = 0
    y: int = 0
    transform: str = "normal"
    scale: float = 1.0
    proxy: object = None

    @property
    def criteria(self) -> str:
        return output_criteria(self.make, self.model, self.serial, self.name)

    @property
    def preferred_mode(self) -> Optional[Mode]:
        return next((m for m in self.modes if m.preferred), self.modes[0] if self.modes else None)


@dataclass
class OutputPlan:
    """How one display should be configured"""
    criteria: str                                  # see output_criteria()
    enabled: bool = True
    mode: Optional[Tuple[int, int, int]] = None    # (width, height, refresh mHz); None = preferred
    position: Tuple[int, int] = (0, 0)
    scale: float = 1.0
    transform: str = "normal"

    def to_dict(self) -> dict:
        return {"criteria": self.criteria, "enabled": self.enabled,
                "mode": list(self.mode) if self.mode else None, "position": list(self.position),
                "scale": self.scale, "transform": self.transform}

    @classmethod
    def from_dict(cls, d: dict) -> "OutputPlan":
        return cls(d["criteria"], bool(d.get("enabled", True)),
                   tuple(d["mode"]) if d.get("mode") else None,
                   tuple(d.get("position") or (0, 0)), float(d.get("scale", 1.0)),
                   d.get("transform", "normal"))


def output_criteria(make: str, model: str, serial: str, name: str) -> str:
    """Identifies a display by "make model serial" ("Unknown" for a missing
    part), which stays the same when it's plugged into another port. Falls
    back to the output name if nothing is known."""
    parts = [p.strip() if p and p.strip() else "Unknown" for p in (make, model, serial)]
    if parts[0] == "Unknown" and parts[1] == "Unknown":
        return name
    return " ".join(parts)


class OutputManager:
    """A Wayland connection with the wlr-output-management manager bound.
    Not thread safe on its own: callers hold self.lock."""

    def __init__(self):
        self.lock = threading.RLock()
        self.display = Display()
        try:
            self.display.connect()
        except Exception as e:
            raise OutputManagementError(f"Can't connect to the Wayland display: {e}")

        globals_: Dict[str, Tuple[int, int]] = {}
        self.registry = self.display.get_registry()
        self.registry.dispatcher["global"] = lambda _r, name, iface, ver: globals_.__setitem__(iface, (name, ver))
        self.display.roundtrip()
        if ZwlrOutputManagerV1.name not in globals_:
            self.display.disconnect()
            raise OutputManagementError("The compositor doesn't support wlr-output-management")

        name, version = globals_[ZwlrOutputManagerV1.name]
        self.manager = self.registry.bind(name, ZwlrOutputManagerV1, min(version, MANAGER_VERSION))
        self.heads: List[Head] = []
        self.serial = 0
        self.finished = False
        # Called after the compositor sends a complete, changed state
        self.on_done: Optional[Callable[[], None]] = None

        self.manager.dispatcher["head"] = self._on_head
        self.manager.dispatcher["done"] = self._on_done
        self.manager.dispatcher["finished"] = self._on_finished
        # Heads and their properties arrive after the bind; done ends them
        self.display.roundtrip()
        self.display.roundtrip()

    # --- events ---------------------------------------------------------------
    def _on_head(self, _manager, proxy) -> None:
        head = Head(proxy=proxy)
        self.heads.append(head)

        def setter(attr, convert=lambda v: v):
            def handler(_proxy, value):
                setattr(head, attr, convert(value))
            return handler

        def on_mode(_proxy, mode_proxy):
            mode = Mode(proxy=mode_proxy)
            head.modes.append(mode)
            mode_proxy.mc_mode = mode
            def on_size(_p, w, h):
                mode.width, mode.height = w, h

            mode_proxy.dispatcher["size"] = on_size
            mode_proxy.dispatcher["refresh"] = lambda _p, r: setattr(mode, "refresh", r)
            mode_proxy.dispatcher["preferred"] = lambda _p: setattr(mode, "preferred", True)
            mode_proxy.dispatcher["finished"] = lambda _p: head.modes.remove(mode) if mode in head.modes else None

        def on_finished(_proxy):
            if head in self.heads:
                self.heads.remove(head)

        def on_position(_proxy, x, y):
            head.x, head.y = x, y

        # (handlers must return None: pywayland passes the result back to C)
        d = proxy.dispatcher
        d["name"] = setter("name")
        d["description"] = setter("description")
        d["make"] = setter("make")
        d["model"] = setter("model")
        d["serial_number"] = setter("serial")
        d["enabled"] = setter("enabled", bool)
        d["position"] = on_position
        d["transform"] = setter("transform", lambda t: TRANSFORMS[t] if 0 <= t < len(TRANSFORMS) else "normal")
        d["scale"] = setter("scale", float)
        d["mode"] = on_mode
        d["current_mode"] = lambda _p, m: setattr(head, "current_mode", getattr(m, "mc_mode", None))
        d["finished"] = on_finished

    def _on_done(self, _manager, serial: int) -> None:
        self.serial = serial
        if self.on_done is not None:
            self.on_done()

    def _on_finished(self, _manager) -> None:
        self.finished = True

    def close(self) -> None:
        """Release the Wayland objects, then disconnect. Needed before the
        process exits: otherwise the garbage collector may free the heads
        and modes after the connection, and libwayland crashes on them."""
        with self.lock:
            if self.display is None:
                return
            for head in self.heads:
                for mode in head.modes:
                    mode.proxy.destroy()
                head.proxy.destroy()
            self.heads = []
            self.manager.destroy()
            self.registry.destroy()
            self.display.disconnect()
            self.display = None
            self.finished = True

    # --- use ------------------------------------------------------------------
    def refresh(self) -> List[Head]:
        """Process pending changes and return the connected displays"""
        with self.lock:
            if self.display.roundtrip() < 0:
                raise OutputManagementError("Lost the connection to the Wayland display")
            return [h for h in self.heads if h.name]

    def apply(self, plans: List[OutputPlan], retries: int = 2) -> bool:
        """Apply the configuration; displays without a plan keep their state.
        Retried if the configuration changed meanwhile (e.g. hotplug)."""
        with self.lock:
            for _ in range(retries + 1):
                heads = self.refresh()
                result = self._apply_once(heads, plans)
                if result != "cancelled":
                    return result == "succeeded"
            return False

    def _apply_once(self, heads: List[Head], plans: List[OutputPlan]) -> str:
        by_criteria = {p.criteria: p for p in plans}
        config = self.manager.create_configuration(self.serial)
        result: List[str] = []
        config.dispatcher["succeeded"] = lambda _c: result.append("succeeded")
        config.dispatcher["failed"] = lambda _c: result.append("failed")
        config.dispatcher["cancelled"] = lambda _c: result.append("cancelled")

        for head in heads:
            plan = by_criteria.get(head.criteria) or by_criteria.get(head.name)
            if plan is None:
                plan = OutputPlan(head.criteria, head.enabled, _mode_key(head.current_mode),
                                  (head.x, head.y), head.scale, head.transform)
            if not plan.enabled:
                config.disable_head(head.proxy)
                continue
            config_head = config.enable_head(head.proxy)
            mode = _find_mode(head, plan.mode)
            if mode is not None:
                config_head.set_mode(mode.proxy)
            config_head.set_position(*plan.position)
            config_head.set_transform(TRANSFORMS.index(plan.transform) if plan.transform in TRANSFORMS else 0)
            config_head.set_scale(plan.scale)

        config.apply()
        while not result:
            if self.display.dispatch(block=True) < 0:
                raise OutputManagementError("Lost the connection to the Wayland display")
        config.destroy()
        return result[0]


def _mode_key(mode: Optional[Mode]) -> Optional[Tuple[int, int, int]]:
    return (mode.width, mode.height, mode.refresh) if mode else None


def _find_mode(head: Head, wanted: Optional[Tuple[int, int, int]]) -> Optional[Mode]:
    """The head's mode matching wanted (closest refresh rate), or its
    preferred mode"""
    if wanted:
        same_size = [m for m in head.modes if (m.width, m.height) == tuple(wanted[:2])]
        if same_size:
            return min(same_size, key=lambda m: abs(m.refresh - wanted[2]))
    return head.preferred_mode


def plan_matches(head: Head, plan: OutputPlan) -> bool:
    """Whether the display is already configured as planned"""
    if head.enabled != plan.enabled:
        return False
    if not plan.enabled:
        return True
    mode = _find_mode(head, plan.mode)
    return (mode is head.current_mode and (head.x, head.y) == tuple(plan.position)
            and abs(head.scale - plan.scale) < 0.01 and head.transform == plan.transform)


_manager: Optional[OutputManager] = None
_manager_lock = threading.Lock()


def get_manager() -> OutputManager:
    """This process' connection, made on first use (raises
    OutputManagementError if it can't be made)"""
    global _manager
    with _manager_lock:
        if _manager is None or _manager.finished:
            if _manager is not None:
                _manager.close()
            _manager = OutputManager()
            atexit.register(_manager.close)
        return _manager
