#!/usr/bin/env python3

import gi

from utils.translations import English, Spanish # type: ignore

gi.require_version("Gtk", "3.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gtk, GLib, Pango # type: ignore

class BluetoothDeviceRow(Gtk.ListBoxRow):
    """A device in the Bluetooth list.

    Activating (clicking) the row is handled by the tab: it connects, or
    disconnects when the device is already connected. ``busy_text`` shows a
    spinner with that text while such an action is running.
    """

    def __init__(self, device, txt:English|Spanish, busy_text=None):
        super().__init__()
        self.txt = txt
        self.busy = busy_text is not None

        # Store device info
        self.device_path = device['path']
        self.mac_address = device['mac']
        self.device_name = device['name']
        self.is_connected = device['connected']
        self.is_paired = device['paired']
        self.device_type = device['icon'] if device['icon'] else 'unknown'
        self.battery_percentage = device.get('battery', None)

        # Main container for the row (margins inside the row so the whole
        # row highlights on hover, like the Wi-Fi list)
        container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        container.set_margin_top(6)
        container.set_margin_bottom(6)
        container.set_margin_start(10)
        container.set_margin_end(10)
        self.add(container)

        # Device icon based on type
        # Same icon size as the Wi-Fi list's signal icons
        device_icon = Gtk.Image.new_from_icon_name(self.get_icon_name_for_device(), Gtk.IconSize.MENU)
        container.pack_start(device_icon, False, False, 0)

        # Left side with device name and type
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)

        name_label = Gtk.Label(xalign=0)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        if self.is_connected:
            name_label.set_markup(f"<b>{GLib.markup_escape_text(self.device_name)}</b>")
        else:
            name_label.set_text(self.device_name)
        left_box.pack_start(name_label, False, False, 0)

        # Details line: device type, plus battery level when reported
        details_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        # Small dimmed text, same as the security type under Wi-Fi networks
        type_label = Gtk.Label()
        type_label.set_markup(f"<small>{GLib.markup_escape_text(self.get_friendly_device_type())}</small>")
        type_label.set_halign(Gtk.Align.START)
        type_label.get_style_context().add_class("dim-label")
        details_box.pack_start(type_label, False, False, 0)

        if self.battery_percentage is not None:
            battery_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
            battery_box.set_tooltip_text(f"Battery {self.battery_percentage}%")
            battery_icon = Gtk.Image.new_from_icon_name(self.get_battery_icon_name(), Gtk.IconSize.MENU)
            battery_icon.get_style_context().add_class("dim-label")
            battery_box.pack_start(battery_icon, False, False, 0)
            battery_label = Gtk.Label()
            battery_label.set_markup(f"<small>{self.battery_percentage}%</small>")
            battery_label.get_style_context().add_class("dim-label")
            battery_box.pack_start(battery_label, False, False, 0)
            details_box.pack_start(battery_box, False, False, 10)

        left_box.pack_start(details_box, False, False, 0)

        container.pack_start(left_box, True, True, 0)

        # Right side, like the Wi-Fi list: status, then the forget button
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        status_box.set_valign(Gtk.Align.CENTER)
        if busy_text is not None:
            spinner = Gtk.Spinner()
            spinner.start()
            status_box.pack_start(spinner, False, False, 0)
            busy_label = Gtk.Label(label=busy_text)
            busy_label.get_style_context().add_class("dim-label")
            status_box.pack_start(busy_label, False, False, 0)
        elif self.is_connected:
            status_box.pack_start(
                Gtk.Image.new_from_icon_name("emblem-ok-symbolic", Gtk.IconSize.MENU), False, False, 0
            )
            connected_label = Gtk.Label(label=self.txt.connected)
            connected_label.get_style_context().add_class("dim-label")
            status_box.pack_start(connected_label, False, False, 0)

        # Forget: small flat icon button, like the Wi-Fi QR code button
        self.forget_button = Gtk.Button()
        self.forget_button.set_relief(Gtk.ReliefStyle.NONE)
        self.forget_button.set_valign(Gtk.Align.CENTER)
        self.forget_button.set_image(
            Gtk.Image.new_from_icon_name("user-trash-symbolic", Gtk.IconSize.MENU)
        )
        self.forget_button.set_tooltip_text(getattr(self.txt, "forget", "Forget"))
        self.forget_button.set_sensitive(not self.busy)
        container.pack_end(self.forget_button, False, False, 0)
        container.pack_end(status_box, False, False, 0)

    def get_icon_name_for_device(self):
        """Return appropriate icon based on device type"""
        if self.device_type == "audio-headset" or self.device_type == "audio-headphones":
            return "audio-headset-symbolic"
        elif self.device_type == "audio-card":
            return "audio-speakers-symbolic"
        elif self.device_type == "input-keyboard":
            return "input-keyboard-symbolic"
        elif self.device_type == "input-mouse":
            return "input-mouse-symbolic"
        elif self.device_type == "input-gaming":
            return "input-gaming-symbolic"
        elif self.device_type == "phone":
            return "phone-symbolic"
        else:
            return "bluetooth-symbolic"

    def get_friendly_device_type(self):
        """Return user-friendly device type name"""
        type_names = {
            "audio-headset": "Headset",
            "audio-headphones": "Headphones",
            "audio-card": "Speaker",
            "input-keyboard": "Keyboard",
            "input-mouse": "Mouse",
            "input-gaming": "Game Controller",
            "phone": "Phone",
            "unknown": "Device",
        }
        return type_names.get(self.device_type, "Bluetooth Device")

    def get_battery_icon_name(self):
        """Symbolic battery icon for the device's battery level"""
        level = self.battery_percentage or 0
        if level >= 80:
            return "battery-full-symbolic"
        if level >= 50:
            return "battery-good-symbolic"
        if level >= 20:
            return "battery-low-symbolic"
        if level >= 5:
            return "battery-caution-symbolic"
        return "battery-empty-symbolic"

    def get_battery_level_icon(self):
        """Return battery level icon suffix based on percentage"""
        if not self.battery_percentage:
            return "missing"
        if self.battery_percentage >= 90:
            return "100"
        elif self.battery_percentage >= 70:
            return "080"
        elif self.battery_percentage >= 50:
            return "060"
        elif self.battery_percentage >= 30:
            return "040"
        elif self.battery_percentage >= 10:
            return "020"
        else:
            return "000"

    def get_mac_address(self):
        return self.mac_address

    def get_device_name(self):
        return self.device_name

    def get_is_connected(self):
        return self.is_connected
