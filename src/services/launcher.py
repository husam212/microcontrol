#!/usr/bin/env python3
"""Finding and starting the daemon from the app (GTK-free)"""

import os
import shutil
import subprocess
import sys
import time

from gi.repository import Gio, GLib  # type: ignore

from utils.logger import LogLevel, Logger

BUS_NAME = "dev.husam.MicroControl.Daemon"
# The daemon's systemd user service (package/systemd/microcontrol.service)
DAEMON_SERVICE = "microcontrol.service"
# What the daemon needs from the session: the Wayland socket, and the
# compositor's IPC socket and name (for mirroring)
SESSION_ENV = ("WAYLAND_DISPLAY", "SWAYSOCK", "HYPRLAND_INSTANCE_SIGNATURE", "XDG_CURRENT_DESKTOP")


def is_running() -> bool:
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        reply = bus.call_sync(
            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "NameHasOwner",
            GLib.Variant("(s)", (BUS_NAME,)), GLib.VariantType("(b)"), Gio.DBusCallFlags.NONE, -1, None,
        )
        return bool(reply.unpack()[0])
    except GLib.Error:
        return False


def _start(logging: Logger) -> None:
    """Through the systemd user service when installed (the package ships
    it), otherwise as a detached process"""
    if shutil.which("systemctl"):
        unit = subprocess.run(["systemctl", "--user", "cat", DAEMON_SERVICE], capture_output=True, text=True)
        if unit.returncode == 0:
            # The user manager may not have the session's environment yet
            # (sessions that don't activate graphical-session.target)
            names = [n for n in SESSION_ENV if os.environ.get(n)]
            if names:
                subprocess.run(["systemctl", "--user", "import-environment", *names], capture_output=True)
            result = subprocess.run(["systemctl", "--user", "start", DAEMON_SERVICE],
                                    capture_output=True, text=True)
            if result.returncode == 0:
                logging.log(LogLevel.Info, f"Started {DAEMON_SERVICE}")
                return
            logging.log(LogLevel.Warn, f"Couldn't start {DAEMON_SERVICE}: {result.stderr.strip()}")

    logging.log(LogLevel.Info, "Starting the MicroControl daemon")
    entry = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "microcontrol.py")
    subprocess.Popen([sys.executable, entry, "--daemon"], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


def ensure_running(logging: Logger) -> bool:
    """Start the daemon if it isn't running"""
    if is_running():
        return True
    _start(logging)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if is_running():
            return True
        time.sleep(0.1)
    logging.log(LogLevel.Error, "The MicroControl daemon didn't start")
    return False
