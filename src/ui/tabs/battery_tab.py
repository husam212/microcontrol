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


class BatteryTab(Gtk.Box):
    def __init__(self, logging: Logger, txt: English|Spanish, parent=None):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.txt = txt
        self.logging = logging

        self.last_refresh_time = datetime.now()

        self.__load_gui(parent)

        self.power_mode_dropdown = Gtk.ComboBoxText()
        self.power_modes = {
            self.txt.battery_power_saving: "power-saver",
            self.txt.battery_balanced: "balanced",
            self.txt.battery_performance: "performance",
        }

        for mode in self.power_modes.keys():
            self.power_mode_dropdown.append_text(mode)

        # Get saved mode from settings
        saved_mode = ''
        try:
            # Get current power plan using powerprofilesctl
            result = subprocess.run(
                "powerprofilesctl get", shell=True, capture_output=True, text=True
            )
            if result.returncode == 0:
                current_plan = result.stdout.strip()

                plan_mapping = {
                    "power-saver": "Power Saving",
                    "balanced": "Balanced",
                    "performance": "Performance",
                }
                if current_plan in plan_mapping:
                    saved_mode = current_plan
        except Exception as e:
            self.logging.log(LogLevel.Error, f"Failed to get current power plan: {e}")

        matching_label = next(
            (label for label, value in self.power_modes.items() if value == saved_mode),
            self.txt.battery_balanced,
        )
        if matching_label:
            self.power_mode_dropdown.set_active(
                list(self.power_modes.keys()).index(matching_label)
            )
        else:
            self.logging.log(
                LogLevel.Warn,
                f"Unknown power mode '{saved_mode}', defaulting to Balanced",
            )
            self.power_mode_dropdown.set_active(
                list(self.power_modes.keys()).index("Balanced")
            )

        # Add dropdown to the UI
        self.dropdown_box.pack_start(self.power_mode_dropdown, True, True, 0)
        self.power_mode_box.pack_start(self.dropdown_box, False, False, 0)

        self.scroll_window.add(self.content_box)
        self.pack_start(self.scroll_window, True, True, 0)

        self.power_mode_dropdown.connect("changed", self.set_power_mode)
        

        self.refresh_battery_info()
        GLib.timeout_add_seconds(10, self.refresh_battery_info)
        
    def set_power_mode(self, widget):
        """Handle power mode change using powerprofilesctl."""
        selected_mode = widget.get_active_text()
        if selected_mode in self.power_modes:
            mode_value = self.power_modes[selected_mode]

            # Disable dropdown while processing
            self.power_mode_dropdown.set_sensitive(False)

            # Create and start thread for async operation
            def run_power_change():
                try:
                    command = f"powerprofilesctl set {mode_value}"
                    result = subprocess.run(
                        command, shell=True, capture_output=True, text=True
                    )

                    # Use GLib.idle_add to update UI from the main thread
                    def update_ui():
                        self.power_mode_dropdown.set_sensitive(True)

                        if result.returncode != 0:
                            error_message = "powerprofilesctl is missing. Please check our GitHub page to see all dependencies and install them."
                            self.logging.log(LogLevel.Error, error_message)
                            if self.parent:
                                self.parent.show_error_dialog(error_message)
                        else:
                            self.logging.log(
                                LogLevel.Info,
                                f"Power mode changed to: {selected_mode} ({mode_value})",
                            )
                            # Refresh the UI to update button styles
                            self.refresh_battery_info()
                        return False

                    GLib.idle_add(update_ui)

                except Exception as e:
                    def handle_error(e=e):  # Capture the exception in the closure
                        self.power_mode_dropdown.set_sensitive(True)
                        error_message = f"Failed to set power mode: {e}"
                        self.logging.log(LogLevel.Error, error_message)
                        if self.parent:
                            self.parent.show_error_dialog(error_message)
                        return False

                    GLib.idle_add(handle_error)

            # Start the thread
            thread = threading.Thread(target=run_power_change, daemon=True)
            thread.start()

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
        level_bar.add_offset_value("low", 20.0)
        level_bar.add_offset_value("high", 50.0)
        level_bar.add_offset_value("full", 90.0)
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

        # Power mode selector below the charge
        mode_selector = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        mode_selector.set_homogeneous(True)  # Make all buttons equal width
        mode_selector.set_margin_top(10)

        mode_icons = {
            self.txt.battery_power_saving: "power-profile-power-saver-symbolic",
            self.txt.battery_balanced: "power-profile-balanced-symbolic",
            self.txt.battery_performance: "power-profile-performance-symbolic"
        }

        # Get current active mode
        active_mode = self.power_mode_dropdown.get_active_text()

        for mode, profile in self.power_modes.items():
            mode_button = Gtk.Button()

            button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            button_box.set_margin_top(8)
            button_box.set_margin_bottom(8)

            icon = Gtk.Image.new_from_icon_name(mode_icons.get(mode, "dialog-question-symbolic"), Gtk.IconSize.BUTTON)
            button_box.pack_start(icon, False, False, 0)

            label = Gtk.Label(mode)
            button_box.pack_start(label, True, False, 0)

            mode_button.add(button_box)
            mode_button.connect("clicked", self.on_power_mode_button_clicked, mode)

            if mode == active_mode:
                mode_button.get_style_context().add_class("suggested-action")

            mode_selector.pack_start(mode_button, True, True, 0)

        self.content_box.pack_start(mode_selector, False, False, 0)

        # Show all widgets
        self.content_box.show_all()        # Show all widgets
        self.content_box.show_all()

        # Update refresh time
        self.last_refresh_time = datetime.now()

        return True

    def on_power_mode_button_clicked(self, button, mode):
        """Handle click on power mode button."""
        # Disable all mode buttons while processing
        for child in button.get_parent().get_children():
            child.set_sensitive(False)

        # Find index of the selected mode
        if mode in self.power_modes:
            index = list(self.power_modes.keys()).index(mode)
            # Set the dropdown to this index (will trigger the "changed" signal)
            self.power_mode_dropdown.set_active(index)

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
        self.content_box.set_margin_top(10)
        self.content_box.set_margin_bottom(10)
        self.content_box.set_margin_start(10)
        self.content_box.set_margin_end(10)
        self.content_box.set_hexpand(True)
        self.content_box.set_vexpand(True)

        # Power mode section (hidden as we'll create this dynamically)
        self.power_mode_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.power_mode_label = Gtk.Label(label="Select Power Mode:")
        self.power_mode_label.set_halign(Gtk.Align.START)
        self.power_mode_label.set_markup("<b>Select Power Mode:</b>")
        self.power_mode_box.pack_start(self.power_mode_label, False, False, 0)

        # Mode selection dropdown (hidden but functional for logic)
        self.dropdown_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.dropdown_box.set_margin_top(5)
        # Note: The dropdown is not visible but set active in code to trigger mode change
