#!/usr/bin/env python3
"""The MicroControl daemon (``microcontrol --daemon``): runs in the
background for features that react to events, without any UI.

It never imports GTK. Only one instance runs per session: it owns the
session bus name BUS_NAME, and exits if another instance already does.
Window options (-w, --size, ...) are ignored; --log works as in the app.

Features:
* applying the saved display layout when displays are plugged in or out
  (services/display_service.py)
"""

import signal
import sys
from typing import List, Optional

from gi.repository import Gio, GLib  # type: ignore
from setproctitle import setproctitle

from services.launcher import BUS_NAME
from tools.multi_display import get_display_backend
from utils.arg_parser import ArgParse
from utils.logger import LogLevel, Logger

# org.freedesktop.DBus.RequestName flags and replies
_DO_NOT_QUEUE = 4
_PRIMARY_OWNER = 1


def _own_bus_name(logging: Logger) -> Optional[Gio.DBusConnection]:
    """Claim BUS_NAME; None if another daemon already has it. The name is
    held as long as the returned connection is kept (GLib closes the shared
    bus connection once nothing references it), and released when the
    process exits, however it exits."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        reply = bus.call_sync(
            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "RequestName",
            GLib.Variant("(su)", (BUS_NAME, _DO_NOT_QUEUE)), GLib.VariantType("(u)"),
            Gio.DBusCallFlags.NONE, -1, None,
        )
    except GLib.Error as e:
        logging.log(LogLevel.Error, f"Can't connect to the session bus: {e.message}")
        return None
    return bus if reply.unpack()[0] == _PRIMARY_OWNER else None


def main(argv: List[str]) -> int:
    logging = Logger(ArgParse(argv))
    setproctitle("microcontrol-daemon")

    bus = _own_bus_name(logging)  # kept until the daemon exits
    if bus is None:
        # Printed directly: the logger doesn't print errors unless logging to a file
        print("The MicroControl daemon is already running", file=sys.stderr)
        return 1
    logging.log(LogLevel.Info, "MicroControl daemon started")

    loop = GLib.MainLoop()
    services = []
    exit_code = 0

    def lost_session() -> None:
        # The compositor is gone (or restarting): exit, so the service
        # restarts the daemon in the new session
        nonlocal exit_code
        exit_code = 1
        loop.quit()

    backend = get_display_backend(logging)
    if backend is not None:
        from services.display_service import DisplayService
        services.append(DisplayService(logging, backend, lost_session))
    else:
        logging.log(LogLevel.Info, "Not managing displays (the compositor doesn't support wlr-output-management)")

    def quit_loop() -> bool:
        logging.log(LogLevel.Info, "MicroControl daemon stopping")
        loop.quit()
        return GLib.SOURCE_REMOVE

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, quit_loop)

    for service in services:
        service.start()
    try:
        loop.run()
    finally:
        for service in services:
            service.stop()
    return exit_code
