#!/usr/bin/env python3

import gi  # type: ignore

from utils.logger import LogLevel, Logger
from utils.translations import English, Spanish

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk # type: ignore

from tools.bluetooth import (
    get_bluetooth_status,
    set_bluetooth_power,
    get_devices,
    start_discovery,
    stop_discovery,
    connect_device_async,
    disconnect_device_async,
)
from ui.widgets.bluetooth_device_row import BluetoothDeviceRow


class BluetoothTab(Gtk.Box):
    """Bluetooth settings tab"""

    def __init__(self, logging: Logger, txt: English|Spanish):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.txt = txt
        self.logging = logging

        self.set_margin_start(15)
        self.set_margin_end(15)
        self.set_margin_top(15)
        self.set_margin_bottom(15)
        self.set_hexpand(True)
        self.set_vexpand(True)

        # State tracking
        self.is_discovering = False
        self.discovery_timeout_id = None
        self.discovery_check_id = None

        # Add combined refresh/scan button with expandable animation
        self.refresh_button = Gtk.Button()
        self.refresh_button.set_valign(Gtk.Align.CENTER)
        self.refresh_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.refresh_icon = Gtk.Image.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        self.refresh_label = Gtk.Label(label="Refresh")
        self.refresh_label.set_margin_start(5)
        self.refresh_btn_box.pack_start(self.refresh_icon, False, False, 0)
        
        # Animation controller
        self.refresh_revealer = Gtk.Revealer()
        self.refresh_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_RIGHT)
        self.refresh_revealer.set_transition_duration(150)
        self.refresh_revealer.add(self.refresh_label)
        self.refresh_revealer.set_reveal_child(False)
        self.refresh_btn_box.pack_start(self.refresh_revealer, False, False, 0)
        
        self.refresh_button.add(self.refresh_btn_box)
        refresh_tooltip = getattr(self.txt, "refresh_tooltip", "Refresh and Scan for Devices")
        self.refresh_button.set_tooltip_text(refresh_tooltip)
        self.refresh_button.connect("clicked", self.on_scan_clicked)
        
        # Hover behavior
        self.refresh_button.set_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.refresh_button.connect("enter-notify-event", self.on_refresh_enter)
        self.refresh_button.connect("leave-notify-event", self.on_refresh_leave)

        # Bluetooth power switch, next to the refresh button
        self.power_switch = Gtk.Switch()
        self.power_switch.set_valign(Gtk.Align.CENTER)
        self.power_switch.set_tooltip_text(self.txt.bluetooth_power)
        self.power_switch.set_active(get_bluetooth_status(self.logging))
        self.power_switch.connect("notify::active", self.on_power_switched)

        # Create main content box (the header row stays put; only the list scrolls)
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content_box.set_margin_top(10)
        content_box.set_margin_bottom(10)
        content_box.set_margin_start(10)
        content_box.set_margin_end(10)

        # Device list section
        devices_label = Gtk.Label()
        devices_label.set_markup(f"<b>{self.txt.bluetooth_available_devices}</b>")
        devices_label.set_halign(Gtk.Align.START)
        devices_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        devices_header.pack_start(devices_label, False, False, 0)
        devices_header.pack_end(self.power_switch, False, False, 0)
        devices_header.pack_end(self.refresh_button, False, False, 0)
        content_box.pack_start(devices_header, False, True, 0)

        # Device list
        devices_frame = Gtk.ScrolledWindow()
        devices_frame.set_shadow_type(Gtk.ShadowType.IN)
        # Clicking a device connects to it, or disconnects if already connected
        self.devices_box = Gtk.ListBox()
        self.devices_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.devices_box.set_activate_on_single_click(True)
        self.devices_box.connect("row-activated", self.on_device_row_activated)
        # device path -> text shown while a connect/disconnect/forget runs
        self._busy_devices = {}
        # Last rendered device state, to skip rebuilding an unchanged list
        self._device_list_signature = None

        # Only the list scrolls; the scrolled window's border replaces the frame
        devices_frame.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        devices_frame.set_vexpand(True)
        devices_frame.add(self.devices_box)
        devices_frame.get_child().set_shadow_type(Gtk.ShadowType.NONE)  # viewport: no second border
        content_box.pack_start(devices_frame, True, True, 0)

        self.pack_start(content_box, True, True, 0)

        # Check for connected Bluetooth devices and switch audio if necessary
        devices = get_devices(self.logging)
        for device in devices:
            if device['connected']:
                from tools.bluetooth import get_bluetooth_manager
                manager = get_bluetooth_manager(self.logging)
                manager._switch_to_bluetooth_audio(device['path'])
                break

        # Initial device list population
        self.update_device_list()
        

        # Set up periodic device list updates
        GLib.timeout_add(2000, self.periodic_update)


    def on_refresh_enter(self, widget, event):
        alloc = widget.get_allocation()
        if (0 <= event.x <= alloc.width and 
            0 <= event.y <= alloc.height):
            self.refresh_revealer.set_reveal_child(True)
        return False
    
    def on_refresh_leave(self, widget, event):
        alloc = widget.get_allocation()
        if not (0 <= event.x <= alloc.width and 
               0 <= event.y <= alloc.height):
            self.refresh_revealer.set_reveal_child(False) 
        return False
        
    def update_device_list(self, force=False):
        """Update the list of Bluetooth devices

        The list is polled every 2 seconds; it is only rebuilt when something
        changed, so rows aren't replaced under the cursor while clicking.
        """
        devices = []
        if get_bluetooth_status(self.logging):
            try:
                devices = get_devices(self.logging)
                for device in devices:
                    # Get battery info for connected devices
                    if device['connected']:
                        from tools.bluetooth import get_bluetooth_manager
                        manager = get_bluetooth_manager(self.logging)
                        battery = manager.get_device_battery(device['path'])
                        if battery is not None:
                            device['battery'] = battery
            except Exception as e:
                self.logging.log(LogLevel.Error, f"Error getting Bluetooth devices: {e}")
                devices = []

        signature = (
            tuple(
                (d['path'], d['name'], d['connected'], d['paired'], d['icon'], d.get('battery'))
                for d in devices
            ),
            tuple(sorted(self._busy_devices.items())),
        )
        if not force and signature == self._device_list_signature:
            return
        self._device_list_signature = signature

        # Clear existing devices
        try:
            for child in self.devices_box.get_children():
                self.devices_box.remove(child)
        except Exception as e:
            self.logging.log(LogLevel.Error, f"Error clearing device list: {e}")

        try:
            for device in devices:
                device_row = BluetoothDeviceRow(
                    device, self.txt, busy_text=self._busy_devices.get(device["path"])
                )
                device_row.forget_button.connect(
                    "clicked", self.on_forget_clicked, device["path"], device["name"]
                )
                self.devices_box.add(device_row)
        except Exception as e:
            self.logging.log(LogLevel.Error, f"Error populating device list: {e}")

        self.devices_box.show_all()

    def periodic_update(self):
        """Update the device list periodically"""
        try:
            # Skip update if tab is being destroyed
            if hasattr(self, 'is_being_destroyed') and self.is_being_destroyed:
                return False

            self.update_device_list()
            return True  # Keep the timer active
        except Exception as e:
            self.logging.log(LogLevel.Error, f"Error in periodic update: {e}")
            return True  # Keep trying

    def __del__(self):
        """Clean up resources when tab is destroyed"""
        try:
            self.cleanup_resources()
        except Exception:
            pass  # Can't log during __del__

    def on_destroy(self, widget):
        """Clean up resources when tab is destroyed"""
        self.is_being_destroyed = True
        self.cleanup_resources()

    def cleanup_resources(self):
        """Clean up all resources used by the tab"""
        # Stop discovery if active
        if self.is_discovering:
            try:
                stop_discovery(self.logging)
                self.is_discovering = False
            except Exception as e:
                self.logging.log(LogLevel.Error, f"Error stopping discovery: {e}")

        # Remove timers
        if self.discovery_timeout_id is not None:
            try:
                GLib.source_remove(self.discovery_timeout_id)
                self.discovery_timeout_id = None
            except Exception as e:
                self.logging.log(LogLevel.Error, f"Error removing discovery timeout: {e}")

        if self.discovery_check_id is not None:
            try:
                GLib.source_remove(self.discovery_check_id)
                self.discovery_check_id = None
            except Exception as e:
                self.logging.log(LogLevel.Error, f"Error removing discovery check: {e}")

        self.logging.log(LogLevel.Debug, "Bluetooth tab resources cleaned up")

    def on_power_switched(self, switch, gparam):
        """Handle Bluetooth power switch changes

        Args:
            switch (Gtk.Switch): The power switch widget
            gparam: GObject parameter
        """
        is_enabled = switch.get_active()
        set_bluetooth_power(is_enabled, self.logging)
        # Update UI based on Bluetooth state
        if is_enabled:
            # Bluetooth enabled - show scan button
            self.refresh_button.set_visible(True)
            # Update device list
            self.update_device_list()
        else:
            # Bluetooth disabled - hide scan button
            self.refresh_button.set_visible(False)
            # Clear all devices from the list
            for child in self.devices_box.get_children():
                self.devices_box.remove(child)
            self.devices_box.show_all()
            self._device_list_signature = None
            # If we're discovering, stop it
            if self.is_discovering:
                self.stop_scan(self.refresh_button)

    def on_scan_clicked(self, button):
        """Handle scan button clicks

        Args:
            button (Gtk.Button): The scan button widget
        """
        # If already scanning, stop the scan
        if self.is_discovering:
            self.stop_scan(button)
            return

        self.logging.log(LogLevel.Info, "Starting Bluetooth device scan")
        # Update button during scan
        button.set_sensitive(False)
        self.refresh_label.set_label(self.txt.bluetooth_scanning)
        self.refresh_revealer.set_reveal_child(True)

        # Start discovery
        try:
            start_discovery(self.logging)
            self.is_discovering = True
        except Exception as e:
            self.logging.log(
                LogLevel.Error, f"Failed to start Bluetooth discovery: {e}"
            )
            button.set_label(self.txt.bluetooth_scan_devices)
            button.set_sensitive(True)
            return

        # Store the start time
        self.scan_start_time = GLib.get_monotonic_time()

        # Schedule periodic checks
        def check_scan_status():
            if not self.is_discovering:
                return False

            current_time = GLib.get_monotonic_time()
            elapsed_seconds = (
                current_time - self.scan_start_time
            ) / 1000000  # Convert to seconds
            # If scan has been running for more than 30 seconds, force stop
            if elapsed_seconds > 30:
                self.logging.log(
                    LogLevel.Warn, "Bluetooth scan timeout reached. Forcing stop."
                )
                self.stop_scan(button)
                return False
            return True

        # Add periodic check every 5 seconds
        if self.discovery_check_id:
            GLib.source_remove(self.discovery_check_id)
        self.discovery_check_id = GLib.timeout_add_seconds(5, check_scan_status)

        # Schedule stopping discovery after 10 seconds
        def stop_scan():
            if self.is_discovering:
                self.stop_scan(button)
            return False

        if self.discovery_timeout_id:
            GLib.source_remove(self.discovery_timeout_id)
        self.discovery_timeout_id = GLib.timeout_add_seconds(10, stop_scan)

    def stop_scan(self, button):
        """Stop the Bluetooth discovery process

        Args:
            button (Gtk.Button): The scan button widget
        """
        self.logging.log(LogLevel.Info, "Stopping Bluetooth device scan")
        if not self.is_discovering:
            button.set_sensitive(True)
            button.set_label(self.txt.bluetooth_scan_devices)
            return

        try:
            stop_discovery(self.logging)
        except Exception as e:
            self.logging.log(LogLevel.Error, f"Failed to stop Bluetooth discovery: {e}")
        finally:
            self.is_discovering = False
            if self.discovery_timeout_id:
                GLib.source_remove(self.discovery_timeout_id)
                self.discovery_timeout_id = None
            if self.discovery_check_id:
                GLib.source_remove(self.discovery_check_id)
                self.discovery_check_id = None
            # Restore original button appearance with hover behavior
            button.set_sensitive(True)
            self.refresh_label.set_label("Refresh")
            self.refresh_revealer.set_reveal_child(False)
            # Force update the button appearance
            self.refresh_btn_box.queue_draw()
            self.update_device_list()

    def on_device_row_activated(self, listbox, row):
        """Connect to the clicked device, or disconnect if it's connected"""
        if not isinstance(row, BluetoothDeviceRow) or row.device_path in self._busy_devices:
            return
        if row.is_connected:
            self._run_device_action(
                row.device_path, self.txt.disconnecting, "disconnect",
                getattr(self.txt, "bluetooth_disconnect_failed", "Failed to disconnect device"),
            )
        else:
            self._run_device_action(
                row.device_path, self.txt.connecting, "connect",
                self.txt.bluetooth_connect_failed,
            )

    def on_forget_clicked(self, button, device_path, device_name):
        """Forget (unpair) a device after confirmation"""
        if device_path in self._busy_devices:
            return
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"{getattr(self.txt, 'forget', 'Forget')} {device_name}?",
        )
        dialog.format_secondary_text("You'll need to pair it again to use it.")
        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.YES:
            return
        self._run_device_action(
            device_path,
            getattr(self.txt, "forget_in_progress", "Forgetting..."),
            "forget",
            getattr(self.txt, "bluetooth_forget_failed", "Failed to forget device"),
        )

    def _run_device_action(self, device_path, busy_text, action, error_text):
        """Run connect/disconnect/forget for a device, showing progress on its row"""
        from tools.bluetooth import forget_device_async

        self._busy_devices[device_path] = busy_text
        self.update_device_list(force=True)

        def on_complete(success):
            def update_ui():
                self._busy_devices.pop(device_path, None)
                self.update_device_list(force=True)
                if not success:
                    dialog = Gtk.MessageDialog(
                        transient_for=self.get_toplevel(),
                        modal=True,
                        message_type=Gtk.MessageType.ERROR,
                        buttons=Gtk.ButtonsType.OK,
                        text=error_text,
                    )
                    dialog.format_secondary_text(
                        getattr(self.txt, "bluetooth_try_again", "Please try again")
                    )
                    dialog.run()
                    dialog.destroy()
                return False

            GLib.idle_add(update_ui)

        runner = {
            "connect": connect_device_async,
            "disconnect": disconnect_device_async,
            "forget": forget_device_async,
        }[action]
        try:
            runner(device_path, on_complete, self.logging)
        except Exception as e:
            self.logging.log(LogLevel.Error, f"Bluetooth {action} failed for {device_path}: {e}")
            on_complete(False)
