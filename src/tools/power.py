#!/usr/bin/env python3
"""Power source (UPower) and power profiles (power-profiles-daemon), and the
profile chosen for each power source. GTK-free: the daemon uses it too
(services/power_service.py) to switch profiles when AC power is plugged in
or out.
"""

import shutil
import subprocess
from typing import List, Optional

from gi.repository import Gio, GLib  # type: ignore

from utils.logger import LogLevel, Logger
from utils.settings import load_settings, save_settings

PROFILES = ("power-saver", "balanced", "performance")

SOURCE_AC = "ac"
SOURCE_BATTERY = "battery"
# Settings keys for the profile chosen for each source (unset: no switching)
SETTING_KEYS = {SOURCE_AC: "power_profile_ac", SOURCE_BATTERY: "power_profile_battery"}

UPOWER_NAME = "org.freedesktop.UPower"
UPOWER_PATH = "/org/freedesktop/UPower"


def on_battery() -> Optional[bool]:
    """Whether the system runs on battery, None if UPower can't tell"""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        reply = bus.call_sync(
            UPOWER_NAME, UPOWER_PATH, "org.freedesktop.DBus.Properties", "Get",
            GLib.Variant("(ss)", (UPOWER_NAME, "OnBattery")), GLib.VariantType("(v)"),
            Gio.DBusCallFlags.NONE, 2000, None,
        )
        return bool(reply.unpack()[0])
    except GLib.Error:
        return None


def current_source() -> Optional[str]:
    state = on_battery()
    return None if state is None else (SOURCE_BATTERY if state else SOURCE_AC)


def available() -> bool:
    return shutil.which("powerprofilesctl") is not None


def _powerprofilesctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["powerprofilesctl", *args], capture_output=True, text=True, timeout=5)


def get_profile() -> Optional[str]:
    try:
        result = _powerprofilesctl("get")
    except (OSError, subprocess.TimeoutExpired):
        return None
    profile = result.stdout.strip()
    return profile if result.returncode == 0 and profile in PROFILES else None


def available_profiles() -> List[str]:
    """The profiles this machine supports (performance isn't always there)"""
    try:
        result = _powerprofilesctl("list")
    except (OSError, subprocess.TimeoutExpired):
        return []
    listed = {line.strip(" *:") for line in result.stdout.splitlines() if line.rstrip().endswith(":")}
    return [p for p in PROFILES if p in listed]


def set_profile(profile: str, logging: Logger) -> bool:
    try:
        result = _powerprofilesctl("set", profile)
    except (OSError, subprocess.TimeoutExpired) as e:
        logging.log(LogLevel.Error, f"Failed to set the power profile: {e}")
        return False
    if result.returncode != 0:
        logging.log(LogLevel.Error, f"Failed to set the power profile: {result.stderr.strip()}")
        return False
    logging.log(LogLevel.Info, f"Power profile set to {profile}")
    return True


def saved_profile(source: str, logging: Logger) -> Optional[str]:
    """The profile chosen for a power source, if any"""
    profile = load_settings(logging).get(SETTING_KEYS[source])
    return profile if profile in PROFILES else None


def save_profile(source: str, profile: str, logging: Logger) -> None:
    settings = load_settings(logging)
    settings[SETTING_KEYS[source]] = profile
    save_settings(settings, logging)
