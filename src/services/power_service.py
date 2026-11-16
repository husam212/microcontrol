#!/usr/bin/env python3
"""Daemon service: switches to the power profile chosen for the power source
(in the Power tab) when AC power is plugged in or out, and once at startup,
for login. Sources without a chosen profile are left alone.

The choice is read from the settings when the source changes, so changes
made in the app need no notification.
"""

from typing import Optional

from gi.repository import Gio, GLib  # type: ignore

from tools import power
from utils.logger import LogLevel, Logger


class PowerService:
    def __init__(self, logging: Logger):
        self.logging = logging
        self.bus: Optional[Gio.DBusConnection] = None
        self.subscription = 0
        self.source: Optional[str] = None

    def start(self) -> None:
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        except GLib.Error as e:
            self.logging.log(LogLevel.Error, f"Can't connect to the system bus: {e.message}")
            return
        self.subscription = self.bus.signal_subscribe(
            power.UPOWER_NAME, "org.freedesktop.DBus.Properties", "PropertiesChanged",
            power.UPOWER_PATH, power.UPOWER_NAME, Gio.DBusSignalFlags.NONE, self._on_changed,
        )
        self._update(power.current_source())

    def stop(self) -> None:
        if self.bus is not None and self.subscription:
            self.bus.signal_unsubscribe(self.subscription)
        self.subscription = 0

    def _on_changed(self, _bus, _sender, _path, _iface, _signal, params) -> None:
        _interface, changed, _invalidated = params.unpack()
        if "OnBattery" in changed:
            self._update(power.SOURCE_BATTERY if changed["OnBattery"] else power.SOURCE_AC)

    def _update(self, source: Optional[str]) -> None:
        if source is None or source == self.source:
            return
        self.source = source
        profile = power.saved_profile(source, self.logging)
        if profile is None or profile == power.get_profile():
            return
        self.logging.log(LogLevel.Info, f"On {'battery' if source == power.SOURCE_BATTERY else 'AC power'}, "
                                        f"switching to the {profile} power profile")
        power.set_profile(profile, self.logging)
