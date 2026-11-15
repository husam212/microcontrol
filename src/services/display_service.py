#!/usr/bin/env python3
"""Daemon service: applies the saved display layout whenever the set of
connected displays changes (and once at startup, for login), by watching
the wlr-output-management connection from the daemon's main loop.

Only a change in which displays are connected triggers it, not other
changes (the app applying a new layout, a scale change, ...), so it never
fights changes made outside of it.
"""

import select
from typing import FrozenSet, Optional

from gi.repository import GLib  # type: ignore

from tools import output_management as om
from tools.multi_display import DisplayBackend
from utils.logger import LogLevel, Logger

# Hotplug sends several updates in a row; act once they settle
SETTLE_MS = 500


class DisplayService:
    def __init__(self, logging: Logger, backend: DisplayBackend, on_lost: callable):
        self.logging = logging
        self.backend = backend
        self.on_lost = on_lost          # called if the Wayland connection is lost
        self.manager = om.get_manager()
        self.connected: Optional[FrozenSet[str]] = None
        self.watch_id = 0
        self.timer_id = 0

    def start(self) -> None:
        self.manager.on_done = self._on_done
        self.watch_id = GLib.io_add_watch(
            self.manager.display.get_fd(), GLib.PRIORITY_DEFAULT,
            GLib.IOCondition.IN | GLib.IOCondition.HUP | GLib.IOCondition.ERR, self._on_readable,
        )
        self._on_done()  # apply for the displays connected now

    def stop(self) -> None:
        for source in (self.watch_id, self.timer_id):
            if source:
                GLib.source_remove(source)
        self.watch_id = self.timer_id = 0
        self.manager.on_done = None

    def _on_readable(self, _fd, condition) -> bool:
        if condition & (GLib.IOCondition.HUP | GLib.IOCondition.ERR):
            return self._lost()
        with self.manager.lock:
            display = self.manager.display
            # Another call (a roundtrip while applying) may have read the
            # events already; a blocking dispatch would then wait for more
            readable = select.select([display.get_fd()], [], [], 0)[0]
            if display.dispatch(block=bool(readable)) < 0:
                return self._lost()
            display.flush()
        return True

    def _lost(self) -> bool:
        self.watch_id = 0
        self.logging.log(LogLevel.Error, "Lost the connection to the Wayland display")
        self.on_lost()
        return False

    def _on_done(self) -> None:
        connected = frozenset(h.criteria for h in self.manager.heads if h.name)
        if connected == self.connected:
            return
        self.connected = connected
        if self.timer_id:
            GLib.source_remove(self.timer_id)
        self.timer_id = GLib.timeout_add(SETTLE_MS, self._apply)

    def _apply(self) -> bool:
        self.timer_id = 0
        try:
            self.backend.apply_saved_layout()
        except Exception as e:
            self.logging.log(LogLevel.Error, f"Failed to apply the display layout: {e}")
        return False
