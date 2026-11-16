#!/usr/bin/env python3

import gi

from utils.translations import English, Spanish  # type: ignore
gi.require_version('Gtk', '3.0')
import subprocess
import os
import threading
from datetime import datetime
from gi.repository import Gtk, GLib,Gdk  # type: ignore
from utils.logger import LogLevel, Logger
from tools import power


class BatteryTab(Gtk.Box):
    def __init__(self, logging: Logger, txt: English|Spanish, parent=None):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.txt = txt
        self.logging = logging

        self.last_refresh_time = datetime.now()

        self.__load_gui(parent)

        # Power profile names
        self.profile_names = {
            "power-saver": self.txt.battery_power_saving,
            "balanced": self.txt.battery_balanced,
            "performance": self.txt.battery_performance,
        }

        self.scroll_window.add(self.content_box)
        self.pack_start(self.scroll_window, True, True, 0)

        self.refresh_battery_info()
        GLib.timeout_add_seconds(10, self.refresh_battery_info)

    def _profile_card(self, source, title, is_current, selected, profiles):
        """Card choosing the power profile for a power source (AC or battery)"""
        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.IN)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)

        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_label = Gtk.Label(xalign=0)
        title_label.set_markup(f"<b>{GLib.markup_escape_text(title)}</b>")
        title_row.pack_start(title_label, False, False, 0)
        if is_current:
            now_label = Gtk.Label(label=getattr(self.txt, "power_now", "Now"))
            now_label.get_style_context().add_class("dim-label")
            title_row.pack_start(now_label, False, False, 0)
        box.pack_start(title_row, False, True, 0)

        # Linked toggle buttons, like the Display tab's Layout card
        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        buttons.get_style_context().add_class("linked")
        group = None
        for profile in profiles:
            button = Gtk.RadioButton.new_with_label_from_widget(group, self.profile_names[profile])
            button.set_mode(False)  # render as a toggle button
            group = group or button
            button.set_active(profile == selected)
            button.connect("toggled", self.on_profile_chosen, source, profile, is_current)
            buttons.pack_start(button, True, True, 0)
        if selected not in profiles and group is not None:
            # Unknown active profile: show none selected
            group.set_inconsistent(True)
        box.pack_start(buttons, False, False, 0)

        frame.add(box)
        return frame

    def on_profile_chosen(self, button, source, profile, is_current):
        """Save the profile for the power source; apply it now if the system
        runs on that source (the daemon applies it when the source changes)"""
        if not button.get_active():
            return
        power.save_profile(source, profile, self.logging)
        if not is_current or profile == power.get_profile():
            self.refresh_battery_info()
            return

        for sibling in button.get_parent().get_children():
            sibling.set_sensitive(False)

        def apply():
            power.set_profile(profile, self.logging)
            GLib.idle_add(lambda: self.refresh_battery_info() and False)

        threading.Thread(target=apply, daemon=True).start()

    def get_battery_devices(self):
        """Get list of battery devices from UPower."""
        devices = []
        try:
            # List all UPower devices
            result = subprocess.run(
                "upower -e", shell=True, capture_output=True, text=True
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    # Only include battery devices
                    if "battery" in line.lower():
                        devices.append(line)
            return devices
        except Exception as e:
            self.logging.log(LogLevel.Error, f"Failed to get UPower devices: {e}")
            return []

    def get_laptop_batteries(self):
        """Return parsed UPower info for batteries that power the system"""
        batteries = []
        for device_path in self.get_battery_devices():
            try:
                result = subprocess.run(
                    ["upower", "-i", device_path], capture_output=True, text=True
                )
                if result.returncode != 0:
                    continue
                info = self.parse_upower_output(result.stdout)
                if info.get("Power supply", "yes").lower() == "yes":
                    batteries.append(info)
            except Exception as e:
                self.logging.log(LogLevel.Error, f"Error reading battery {device_path}: {e}")
        return batteries

    def parse_upower_output(self, output):
        """Parse the output of upower -i command into a dict."""
        info = {}

        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue

            # Check if this is a main property line (contains a colon)
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()

                # Skip empty values
                if not value:
                    continue

                # Map UPower keys to more user-friendly labels
                key_mapping = {
                    "vendor": "Manufacturer",
                    "model": "Model",
                    "state": "State",
                    "warning-level": "Warning Level",
                    "energy": "Energy",
                    "energy-empty": "Energy Empty",
                    "energy-full": "Energy Full",
                    "energy-full-design": "Energy Full Design",
                    "energy-rate": "Energy Rate",
                    "voltage": "Voltage",
                    "time to empty": "Time to Empty",
                    "time to full": "Time to Full",
                    "percentage": "Charge",
                    "capacity": "Capacity",
                    "technology": "Technology",
                }

                display_key = key_mapping.get(key, key.capitalize())
                info[display_key] = value

        return info

    def create_battery_charge_box(self, battery_info):
        """Charge readout for a laptop battery: percentage, state, time and level bar"""
        charge_percentage = self._get_charge_percentage(battery_info)
        state = battery_info.get("State", "unknown").lower()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        charge_label = Gtk.Label()
        charge_label.set_markup(f"<span size='x-large'><b>{charge_percentage}%</b></span>")
        charge_label.set_valign(Gtk.Align.BASELINE)
        status_box.pack_start(charge_label, False, False, 0)

        # Right next to the percentage, on the same text baseline
        state_label = Gtk.Label()
        state_label.set_markup(f"<span size='large'>{state.capitalize()}</span>")
        state_label.set_valign(Gtk.Align.BASELINE)
        status_box.pack_start(state_label, False, False, 0)

        # Time estimates
        if state == "discharging" and "Time to Empty" in battery_info:
            time_label = Gtk.Label(xalign=0)
            time_label.set_markup(f"Empty in {battery_info['Time to Empty']}")
            time_label.set_valign(Gtk.Align.BASELINE)
            status_box.pack_end(time_label, False, False, 0)
        elif state == "charging" and "Time to Full" in battery_info:
            time_label = Gtk.Label(xalign=0)
            time_label.set_markup(f"Full in {battery_info['Time to Full']}")
            time_label.set_valign(Gtk.Align.BASELINE)
            status_box.pack_end(time_label, False, False, 0)

        box.pack_start(status_box, False, False, 0)

        level_bar = Gtk.LevelBar()
        level_bar.set_min_value(0.0)
        level_bar.set_max_value(100.0)
        level_bar.set_value(charge_percentage)
        level_bar.set_size_request(-1, 15)
        level_bar.set_hexpand(True)
        # The bar takes the color of the first offset at or above the charge:
        # red up to 10%, orange up to 20%, blue up to 80%, then green (the
        # colors are set in animations.css)
        level_bar.add_offset_value("critical", 10.0)
        level_bar.add_offset_value("low", 20.0)
        level_bar.add_offset_value("high", 80.0)
        level_bar.add_offset_value("full", 100.0)
        box.pack_start(level_bar, False, False, 0)

        return box

    def _get_charge_percentage(self, battery_info):
        """Extract charge percentage from battery info."""
        if "Charge" in battery_info:
            try:
                charge_text = battery_info["Charge"]
                return int(charge_text.split("%")[0])
            except (ValueError, IndexError):
                pass
        return 0

    def refresh_battery_info(self, button=None):
        """Refresh battery information using UPower with improved visual representation."""
        if button:
            self.logging.log(
                LogLevel.Info, "Manual refresh of battery information requested"
            )

        for child in self.content_box.get_children():
            self.content_box.remove(child)

        # Laptop battery charge at the top
        batteries = self.get_laptop_batteries()
        if not batteries:
            no_battery_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            no_battery_box.set_halign(Gtk.Align.CENTER)
            no_battery_box.set_margin_top(20)
            no_battery_box.set_margin_bottom(20)

            no_battery_icon = Gtk.Image.new_from_icon_name(
                "battery-missing-symbolic", Gtk.IconSize.DIALOG
            )
            no_battery_box.pack_start(no_battery_icon, False, False, 0)

            no_battery_label = Gtk.Label()
            no_battery_label.set_markup(f"<span size='large'>{self.txt.battery_no_batteries}</span>")
            no_battery_box.pack_start(no_battery_label, False, False, 10)

            self.content_box.pack_start(no_battery_box, False, False, 0)
        else:
            for battery_info in batteries:
                self.content_box.pack_start(self.create_battery_charge_box(battery_info), False, False, 0)

        # Power profile for each power source, below the charge. Sources
        # without a chosen profile show the active one (nothing switches)
        if power.available():
            source = power.current_source()
            active = power.get_profile()
            profiles = power.available_profiles() or list(power.PROFILES)
            for card_source, title in (
                (power.SOURCE_AC, getattr(self.txt, "power_plugged_in", "Plugged In")),
                (power.SOURCE_BATTERY, getattr(self.txt, "power_on_battery", "On Battery")),
            ):
                selected = power.saved_profile(card_source, self.logging) or active
                self.content_box.pack_start(
                    self._profile_card(card_source, title, card_source == source, selected, profiles),
                    False, True, 0,
                )

        # Show all widgets
        self.content_box.show_all()

        # Update refresh time
        self.last_refresh_time = datetime.now()

        return True

    def __load_gui(self, parent):
        self.set_margin_top(15)
        self.set_margin_bottom(15)
        self.set_margin_start(15)
        self.set_margin_end(15)
        self.set_hexpand(True)
        self.set_vexpand(True)

        self.parent = parent



        # Create scrollable content
        self.scroll_window = Gtk.ScrolledWindow()
        self.scroll_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll_window.set_vexpand(True)

        # Create main content box - store as instance variable to update later
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        self.content_box.set_hexpand(True)
        self.content_box.set_vexpand(True)
