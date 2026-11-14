#!/usr/bin/env python3

import traceback
import gi # type: ignore
import threading
from utils.logger import LogLevel, Logger
import subprocess

from utils.translations import Translation

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk  # type: ignore
from tools.globals import get_wifi_css

from tools.wifi import (
    get_wifi_status,
    set_wifi_power,
    get_wifi_networks,
    connect_network,
    disconnect_network,
    forget_network,
    get_connection_info,
    generate_wifi_qrcode,
    wifi_supported,
)

class WiFiTab(Gtk.Box):
    """WiFi settings tab"""

    def __init__(self, logging: Logger, txt: Translation):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        get_wifi_css()
        self.txt = txt
        self.logging = logging
        self.logging.log(LogLevel.Debug, "WiFi tab: Starting initialization")
        
        # Debug container visibility
        self._debug_containers = []
        self.set_margin_start(15)
        self.set_margin_end(15)
        self.set_margin_top(15)
        self.set_margin_bottom(15)
        self.set_hexpand(True)
        self.set_vexpand(True)

        # Track tab visibility status
        self.tab_visible = False
        # True once the list shows networks; refreshes then swap rows in place
        # instead of clearing to a spinner (which made the list flicker)
        self._has_network_rows = False

        if not wifi_supported:
            self.logging.log(LogLevel.Warn, "WiFi is not supported on this machine")

        # Add refresh button with expandable animation
        self.refresh_button = Gtk.Button()
        self.refresh_button.set_valign(Gtk.Align.CENTER)
        self.refresh_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.refresh_icon = Gtk.Image.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        self.refresh_label = Gtk.Label(label="Refresh")
        self.refresh_label.set_margin_start(5)
        self.refresh_btn_box.pack_start(self.refresh_icon, False, False, 0)
        # Shown in place of the icon while a rescan runs
        self.refresh_spinner = Gtk.Spinner()
        self.refresh_spinner.set_no_show_all(True)
        self.refresh_btn_box.pack_start(self.refresh_spinner, False, False, 0)
        self._scanning = False
        
        # Animation controller
        self.refresh_revealer = Gtk.Revealer()
        self.refresh_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_RIGHT)
        self.refresh_revealer.set_transition_duration(150)
        self.refresh_revealer.add(self.refresh_label)
        self.refresh_revealer.set_reveal_child(False)
        self.refresh_btn_box.pack_start(self.refresh_revealer, False, False, 0)
        
        self.refresh_button.add(self.refresh_btn_box)
        refresh_tooltip = getattr(self.txt, "wifi_refresh_tooltip", "Refresh WiFi List")
        self.refresh_button.set_tooltip_text(refresh_tooltip)
        self.refresh_button.connect("clicked", self.on_refresh_clicked)
        
        # Hover behavior
        self.refresh_button.set_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.refresh_button.connect("enter-notify-event", self.on_refresh_enter)
        self.refresh_button.connect("leave-notify-event", self.on_refresh_leave)

        # Disable refresh button if WiFi is not supported
        if not wifi_supported:
            self.refresh_button.set_sensitive(False)

        # WiFi power switch, next to the refresh button
        wifi_power_text = getattr(self.txt, "wifi_power", "WiFi Power")
        self.power_switch = Gtk.Switch()
        self.power_switch.set_valign(Gtk.Align.CENTER)
        self.power_switch.set_tooltip_text(wifi_power_text)

        if wifi_supported:
            self.power_switch.set_active(get_wifi_status(self.logging))
            self.power_switch.connect("notify::active", self.on_power_switched)
        else:
            self.power_switch.set_sensitive(False)


        # Create main content box (the header row stays put; only the list scrolls)
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content_box.set_margin_top(10)
        content_box.set_margin_bottom(10)
        content_box.set_margin_start(10)
        content_box.set_margin_end(10)

        # Network list section
        networks_label = Gtk.Label()
        wifi_available_text = getattr(self.txt, "wifi_available", "Available Networks")
        networks_label.set_markup(f"<b>{wifi_available_text}</b>")
        networks_label.set_halign(Gtk.Align.START)
        networks_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        networks_header.pack_start(networks_label, False, False, 0)
        networks_header.pack_end(self.power_switch, False, False, 0)
        networks_header.pack_end(self.refresh_button, False, False, 0)
        content_box.pack_start(networks_header, False, True, 0)

        # Network list
        networks_frame = Gtk.ScrolledWindow()
        networks_frame.set_shadow_type(Gtk.ShadowType.IN)
        self.networks_box = Gtk.ListBox()
        # Clicking a network connects to it, or disconnects if already connected
        self.networks_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.networks_box.set_activate_on_single_click(True)
        self.networks_box.connect("row-activated", self.on_network_row_activated)
        # Only the list scrolls; the scrolled window's border replaces the frame
        networks_frame.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        networks_frame.set_vexpand(True)
        networks_frame.add(self.networks_box)
        networks_frame.get_child().set_shadow_type(Gtk.ShadowType.NONE)  # viewport: no second border
        content_box.pack_start(networks_frame, True, True, 0)

        self.pack_start(content_box, True, True, 0)

        # Initial network list population is now deferred
        # self.update_network_list()  <- This line is removed

        
        # Connect signals for tab visibility tracking
        self.connect("map", self.on_tab_shown)
        self.connect("unmap", self.on_tab_hidden)

    def on_tab_shown(self, widget):
        """Handle tab becoming visible"""
        self.logging.log(LogLevel.Debug, "WiFi tab: on_tab_shown triggered")
        self.tab_visible = True
        
        # Debug container visibility
        def check_visibility():
            self.logging.log(LogLevel.Debug, f"WiFi tab visible: {self.get_visible()}")
            for child in self.get_children():
                self.logging.log(LogLevel.Debug, f"Child {type(child).__name__} visible: {child.get_visible()}")
            return False
            
        GLib.idle_add(check_visibility)
        
        self.update_network_list()

        return False

    def on_tab_hidden(self, widget):
        """Handle tab becoming hidden"""
        self.logging.log(LogLevel.Info, "WiFi tab became hidden")
        self.tab_visible = False

        return False

    def load_networks(self):
        """Load WiFi networks list - to be called after all tabs are loaded"""
        self.logging.log(LogLevel.Info, "Loading WiFi networks after tabs initialization")

        # Only load networks if the tab is visible
        if not self.tab_visible:
            self.logging.log(LogLevel.Info, "WiFi tab not visible, skipping initial network loading")
            return

        # Add a loading indicator
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)

        spinner = Gtk.Spinner()
        spinner.start()
        box.pack_start(spinner, False, False, 0)

        label = Gtk.Label(label="Loading networks...")
        label.set_halign(Gtk.Align.START)
        box.pack_start(label, True, True, 0)

        row.add(box)
        self.networks_box.add(row)
        self.networks_box.show_all()

        # Start network scan in background thread
        thread = threading.Thread(target=self._load_networks_thread)
        thread.daemon = True
        thread.start()

    def _load_networks_thread(self, rescan=False):
        """Background thread to load WiFi networks"""
        try:
            # Get networks
            networks = get_wifi_networks(self.logging, rescan=rescan)
            self.logging.log(LogLevel.Info, f"Found {len(networks)} WiFi networks")
            # Update UI in main thread
            GLib.idle_add(self._update_networks_in_ui, networks)
        except Exception as e:
            self.logging.log(LogLevel.Error, f"Failed loading WiFi networks: {e}")
            # Show error in UI
            GLib.idle_add(self._show_network_error, str(e))
        finally:
            if rescan:
                GLib.idle_add(self._set_scanning, False)

    def _update_networks_in_ui(self, networks):
        """Update UI with networks (called in main thread)"""
        try:
            # Fade rows in only when they first appear, not on every refresh
            animate = not self._has_network_rows

            # Clear existing networks
            for child in self.networks_box.get_children():
                self.networks_box.remove(child)

            if not networks:
                self._has_network_rows = False
                self._show_no_networks_info()
                return False

            sorted_networks = self._sort_networks(networks)

            for network in sorted_networks:
                self._add_network_row(network, animate)

            self.networks_box.show_all()
            self._has_network_rows = True

        except Exception as e:
            self.logging.log(LogLevel.Error, f"Failed updating networks in UI: {e}")
            self._show_network_error(str(e))

        return False  # required for GLib.idle_add

    def _show_no_networks_info(self):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)

        result = subprocess.run(["nmcli", "-t", "-f", "DEVICE,TYPE", "device"], capture_output=True, text=True)
        wifi_interfaces = [line for line in result.stdout.split('\n') if "wifi" in line]

        if not wifi_interfaces:
            error_icon = Gtk.Image.new_from_icon_name("dialog-error-symbolic", Gtk.IconSize.MENU)
            box.pack_start(error_icon, False, False, 0)
            label = Gtk.Label(label="WiFi is not supported on this machine")
        else:
            label = Gtk.Label(label="No networks found")

        label.set_halign(Gtk.Align.START)
        box.pack_start(label, True, True, 0)

        row.add(box)
        self.networks_box.add(row)

        row.get_style_context().add_class("fade-in")

        def remove_animation_class(row_widget):
            if row_widget and row_widget.get_parent() is not None:
                row_widget.get_style_context().remove_class("fade-in")
            return False

        GLib.timeout_add(350, remove_animation_class, row)

        self.networks_box.show_all()

    def _sort_networks(self, networks):
        def get_sort_key(network):
            try:
                if network["in_use"]:
                    return -9999
                else:
                    return -int(network["signal"])
            except (ValueError, TypeError):
                return 0
        return sorted(networks, key=get_sort_key)

    def _add_network_row(self, network, animate=False):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(6)
        box.set_margin_bottom(6)

        # Add signal icon
        signal_icon = self._create_signal_icon(network)
        box.pack_start(signal_icon, False, False, 0)

        info_box = self._create_network_info_box(network)
        box.pack_start(info_box, True, True, 0)

        # Connected indicator + QR button
        if network["in_use"]:
            self._add_connected_qr_widgets(box)

        # Forget button for saved networks (like the Bluetooth list)
        if network.get("saved"):
            forget_button = Gtk.Button()
            forget_button.set_relief(Gtk.ReliefStyle.NONE)
            forget_button.set_valign(Gtk.Align.CENTER)
            forget_button.set_image(
                Gtk.Image.new_from_icon_name("user-trash-symbolic", Gtk.IconSize.MENU)
            )
            forget_button.set_tooltip_text(getattr(self.txt, "wifi_forget", "Forget"))
            forget_button.connect("clicked", self.on_forget_clicked, row)
            box.pack_end(forget_button, False, False, 0)

        row.add(box)
        row.network = network
        self.networks_box.add(row)

        if animate:
            # Add the class before the row is first drawn; adding it later made
            # an already visible row jump to transparent and fade back in
            row.get_style_context().add_class("fade-in")

            def remove_animation_class():
                if row.get_parent() is not None:
                    row.get_style_context().remove_class("fade-in")
                return False

            GLib.timeout_add(350, remove_animation_class)

    def _create_signal_icon(self, network):
        try:
            signal_strength = int(network.get("signal", 0))
        except (ValueError, TypeError):
            signal_strength = 0
        if signal_strength >= 80:
            icon_name = "network-wireless-signal-excellent-symbolic"
        elif signal_strength >= 60:
            icon_name = "network-wireless-signal-good-symbolic"
        elif signal_strength >= 40:
            icon_name = "network-wireless-signal-ok-symbolic"
        elif signal_strength > 0:
            icon_name = "network-wireless-signal-weak-symbolic"
        else:
            icon_name = "network-wireless-signal-none-symbolic"
        signal_icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
        return signal_icon

    def _create_network_info_box(self, network):
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)

        name_label = Gtk.Label()
        name_label.set_halign(Gtk.Align.START)
        if network["in_use"]:
            name_label.set_markup(f"<b>{GLib.markup_escape_text(network['ssid'])}</b>")
        else:
            name_label.set_text(network["ssid"])
        info_box.pack_start(name_label, False, True, 0)

        security_text = network.get("security", "")
        if security_text.lower() == "none":
            security_text_disp = "Open"
        else:
            security_text_disp = security_text
        details_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        details_label = Gtk.Label()
        details_label.set_markup(f'<small>{GLib.markup_escape_text(security_text_disp)}</small>')
        details_label.set_halign(Gtk.Align.START)
        # Same dimmed color as the device type under each Bluetooth device
        details_label.get_style_context().add_class("dim-label")
        details_box.pack_start(details_label, False, True, 0)
        info_box.pack_start(details_box, False, True, 0)

        return info_box

    def _add_connected_qr_widgets(self, container_box):
        connected_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic", Gtk.IconSize.MENU)
        connected_text = getattr(self.txt, "connected", "Connected")
        connected_label = Gtk.Label(label=connected_text)
        connected_label.get_style_context().add_class("dim-label")
        connected_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        connected_box.pack_start(connected_icon, False, False, 0)
        connected_box.pack_start(connected_label, False, False, 0)
        container_box.pack_start(connected_box, False, True, 0)

        qr_button = Gtk.Button()
        qr_button.set_tooltip_text("Show Qr code")
        qr_button.get_style_context().add_class("qr-button")
        qr_button.connect("clicked", self.show_qr_dialog)
        qr_icon = Gtk.Image.new_from_icon_name("qrscanner-symbolic", Gtk.IconSize.MENU)
        qr_button.set_image(qr_icon)
        container_box.pack_start(qr_button, False, False, 0)

    def _show_network_error(self, error_message):
        """Show an error message in the networks list"""
        self._has_network_rows = False
        # Clear existing networks
        for child in self.networks_box.get_children():
            self.networks_box.remove(child)
        # Add error message
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)

        error_icon = Gtk.Image.new_from_icon_name("dialog-error-symbolic", Gtk.IconSize.MENU)
        box.pack_start(error_icon, False, False, 0)

        label = Gtk.Label(label=f"Failed loading networks: {error_message}")
        label.set_halign(Gtk.Align.START)
        box.pack_start(label, True, True, 0)

        row.add(box)
        self.networks_box.add(row)
        self.networks_box.show_all()

        return False  # Required for GLib.idle_add

    def update_network_list(self, rescan=False):
        """Update the list of WiFi networks

        Args:
            rescan (bool): trigger a NetworkManager rescan instead of using its
                cached scan results
        """
        self.logging.log(LogLevel.Info, "Refreshing WiFi networks list")

        # Don't refresh if tab is not visible
        if not self.tab_visible:
            self.logging.log(LogLevel.Info, "WiFi tab not visible, skipping network refresh")
            if rescan:
                self._set_scanning(False)
            return

        # Keep the current list on screen while refreshing; it's replaced in one
        # go when the scan finishes. Only show the spinner for an empty list.
        if self._has_network_rows:
            thread = threading.Thread(target=self._load_networks_thread, args=(rescan,))
            thread.daemon = True
            thread.start()
            return

        # Clear existing networks
        for child in self.networks_box.get_children():
            self.networks_box.remove(child)

        # Add loading indicator
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)

        spinner = Gtk.Spinner()
        spinner.start()
        box.pack_start(spinner, False, False, 0)

        loading_networks_text = getattr(self.txt, "wifi_loading_networks", "Loading networks...")
        label = Gtk.Label(label=loading_networks_text)
        label.set_halign(Gtk.Align.START)
        box.pack_start(label, True, True, 0)

        row.add(box)
        self.networks_box.add(row)
        self.networks_box.show_all()

        # Start network scan in background thread
        thread = threading.Thread(target=self._load_networks_thread, args=(rescan,))
        thread.daemon = True
        thread.start()

    def on_power_switched(self, switch, gparam):
        """Handle WiFi power switch toggle"""
        state = switch.get_active()
        self.logging.log(LogLevel.Info, f"Setting WiFi power: {'ON' if state else 'OFF'}")
        # Run power toggle in a background thread to avoid UI freezing
        def power_toggle_thread():
            try:
                set_wifi_power(state, self.logging)
                if state and self.tab_visible:
                    # Only refresh network list if tab is visible
                    GLib.idle_add(self.update_network_list)
            except Exception as e:
                self.logging.log(LogLevel.Error, f"Failed setting WiFi power: {e}")
        # Start thread
        thread = threading.Thread(target=power_toggle_thread)
        thread.daemon = True
        thread.start()

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

    def on_refresh_clicked(self, button):
        """Handle refresh button click"""
        self.logging.log(LogLevel.Info, "Manual refresh of WiFi networks requested")
        self.rescan_networks()

    def rescan_networks(self):
        """Ask NetworkManager for a fresh Wi-Fi scan, then update the list"""
        if self._scanning or not self.power_switch.get_active():
            return
        self._set_scanning(True)
        self.update_network_list(rescan=True)

    def _set_scanning(self, scanning):
        """Show a spinner on the refresh button while a rescan runs"""
        self._scanning = scanning
        self.refresh_button.set_sensitive(not scanning)
        self.refresh_icon.set_visible(not scanning)
        self.refresh_spinner.set_visible(scanning)
        if scanning:
            self.refresh_spinner.start()
        else:
            self.refresh_spinner.stop()
        return False

    def on_network_row_activated(self, listbox, row):
        """Connect to the clicked network, or disconnect if it is the active one"""
        network = getattr(row, "network", None)
        if network is None or getattr(row, "busy", False):
            return  # loading/error rows, or a connect/disconnect already running
        row.busy = True
        if network.get("in_use"):
            self.on_disconnect_clicked(None, row)
        else:
            self.on_connect_clicked(None, row)

    def on_connect_clicked(self, button, row=None):
        """Connect to the given (or selected) network row"""
        row = row or self.networks_box.get_selected_row()
        if row is None:
            return

        box = row.get_child()
        info_box = box.get_children()[1]
        name_label = info_box.get_children()[0]
        ssid = name_label.get_text()
        # If network name is formatted with markup, strip the markup
        if not ssid:
            ssid = name_label.get_label()
            ssid = ssid.replace("<b>", "").replace("</b>", "")

        self.logging.log(LogLevel.Info, f"Connecting to WiFi network: {ssid}")

        # Show connecting indicator in list
        for child in self.networks_box.get_children():
            if child == row:
                # Update the selected row to show connecting status
                old_box = child.get_child()
                child.remove(old_box)
                new_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                new_box.set_margin_start(10)
                new_box.set_margin_end(10)
                new_box.set_margin_top(6)
                new_box.set_margin_bottom(6)
                # Add spinner
                spinner = Gtk.Spinner()
                spinner.start()
                new_box.pack_start(spinner, False, False, 0)
                # Add label
                connecting_label = Gtk.Label(label=f"Connecting to {ssid}...")
                connecting_label.set_halign(Gtk.Align.START)
                new_box.pack_start(connecting_label, True, True, 0)

                child.add(new_box)
                child.show_all()
                break

        # Try connecting in background thread
        def connect_thread():
            try:
                # First try to connect with saved credentials
                if connect_network(ssid, self.logging):
                    GLib.idle_add(self.update_network_list)
                    return

                # If that fails, check if network requires password
                networks = get_wifi_networks(self.logging)
                network = next((n for n in networks if n["ssid"] == ssid), None)

                if network and network["security"].lower() != "none":
                    # Network requires password and saved credentials failed, show password dialog
                    GLib.idle_add(self._show_password_dialog, ssid)
                else:
                    # Failed to connect but no password needed, just refresh UI
                    GLib.idle_add(self.update_network_list)
            except Exception as e:
                self.logging.log(LogLevel.Error, f"Failed connecting to network: {e}")
                GLib.idle_add(self.update_network_list)

        thread = threading.Thread(target=connect_thread)
        thread.daemon = True
        thread.start()

    def _show_password_dialog(self, ssid):
        """Show password dialog for secured networks"""
        networks = get_wifi_networks(self.logging)
        network = next((n for n in networks if n["ssid"] == ssid), None)
        if network and network["security"].lower() != "none":
            dialog = Gtk.Dialog(
                title=f"Connect to {ssid}",
                parent=self.get_toplevel(),
                flags=0,
                buttons=(
                    Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_OK, Gtk.ResponseType.OK
                )
            )

            box = dialog.get_content_area()
            box.set_spacing(10)
            box.set_margin_start(10)
            box.set_margin_end(10)
            box.set_margin_top(10)
            box.set_margin_bottom(10)

            password_label = Gtk.Label(label="Password:")
            box.add(password_label)

            password_entry = Gtk.Entry()
            password_entry.set_visibility(False)
            password_entry.set_invisible_char("●")
            box.add(password_entry)

            remember_check = Gtk.CheckButton(label="Remember this network")
            remember_check.set_active(True)
            box.add(remember_check)

            dialog.show_all()
            response = dialog.run()

            if response == Gtk.ResponseType.OK:
                password = password_entry.get_text()
                remember = remember_check.get_active()
                dialog.destroy()
                # Connect with password in background thread
                def connect_with_password_thread():
                    try:
                        if connect_network(ssid, self.logging, password, remember):
                            GLib.idle_add(self.update_network_list)
                        else:
                            # Show error dialog
                            error_dialog = Gtk.MessageDialog(
                                transient_for=self.get_toplevel(),
                                flags=0,
                                message_type=Gtk.MessageType.ERROR,
                                buttons=Gtk.ButtonsType.OK,
                                text="Failed to connect"
                            )
                            error_dialog.format_secondary_text(
                                "Please check your password and try again."
                            )
                            error_dialog.run()
                            error_dialog.destroy()
                            # Refresh UI to clear status
                            GLib.idle_add(self.update_network_list)
                    except Exception as e:
                        self.logging.log(LogLevel.Error, f"Failed connecting to network with password: {e}")
                        GLib.idle_add(self.update_network_list)
                thread = threading.Thread(target=connect_with_password_thread)
                thread.daemon = True
                thread.start()
            else:
                dialog.destroy()
                # User cancelled, refresh UI to clear status
                self.update_network_list()
        else:
            # No security or network not found, just refresh UI
            self.update_network_list()
        return False  # Required for GLib.idle_add

    def on_disconnect_clicked(self, button, row=None):
        """Disconnect from the given (or selected) network row"""
        row = row or self.networks_box.get_selected_row()
        if row is None:
            return

        box = row.get_child()
        info_box = box.get_children()[1]
        name_label = info_box.get_children()[0]
        ssid = name_label.get_text()
        # If network name is formatted with markup, strip the markup
        if not ssid:
            ssid = name_label.get_label()
            ssid = ssid.replace("<b>", "").replace("</b>", "")

        self.logging.log(LogLevel.Info, f"Disconnecting from WiFi network: {ssid}")

        # Show disconnecting indicator
        for child in self.networks_box.get_children():
            if child == row:
                # Update the selected row to show disconnecting status
                old_box = child.get_child()
                child.remove(old_box)
                new_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                new_box.set_margin_start(10)
                new_box.set_margin_end(10)
                new_box.set_margin_top(6)
                new_box.set_margin_bottom(6)
                # Add spinner
                spinner = Gtk.Spinner()
                spinner.start()
                new_box.pack_start(spinner, False, False, 0)
                # Add label
                disconnecting_label = Gtk.Label(label=f"Disconnecting from {ssid}...")
                disconnecting_label.set_halign(Gtk.Align.START)
                new_box.pack_start(disconnecting_label, True, True, 0)

                child.add(new_box)
                child.show_all()
                break

        # Run disconnect in separate thread
        thread = threading.Thread(target=self._disconnect_thread, args=(ssid,))
        thread.daemon = True
        thread.start()

    def on_forget_clicked(self, button, row):
        """Forget the saved network on the given row, after confirmation"""
        network = getattr(row, "network", None)
        if network is None or getattr(row, "busy", False):
            return
        ssid = network["ssid"]
        self.logging.log(LogLevel.Info, f"Forgetting WiFi network: {ssid}")

        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Forget network {ssid}?"
        )
        dialog.format_secondary_text(
            "This will remove all saved settings for this network."
        )

        response = dialog.run()
        dialog.destroy()

        if response == Gtk.ResponseType.YES:
            row.busy = True
            # Show forgetting indicator
            for child in self.networks_box.get_children():
                if child == row:
                    # Update the selected row to show forgetting status
                    old_box = child.get_child()
                    child.remove(old_box)
                    new_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                    new_box.set_margin_start(10)
                    new_box.set_margin_end(10)
                    new_box.set_margin_top(6)
                    new_box.set_margin_bottom(6)
                    # Add spinner
                    spinner = Gtk.Spinner()
                    spinner.start()
                    new_box.pack_start(spinner, False, False, 0)
                    # Add label
                    forgetting_label = Gtk.Label(label=f"Forgetting {ssid}...")
                    forgetting_label.set_halign(Gtk.Align.START)
                    new_box.pack_start(forgetting_label, True, True, 0)

                    child.add(new_box)
                    child.show_all()
                    break

            # Run forget in background thread
            def forget_thread():
                try:
                    if forget_network(ssid, self.logging):
                        GLib.idle_add(self.update_network_list)
                    else:
                        # Failed to forget, just refresh UI
                        GLib.idle_add(self.update_network_list)
                except Exception as e:
                    self.logging.log(LogLevel.Error, f"Failed forgetting network: {e}")
                    GLib.idle_add(self.update_network_list)
            thread = threading.Thread(target=forget_thread)
            thread.daemon = True
            thread.start()

    def _disconnect_thread(self, ssid):
        """Thread function to disconnect from a WiFi network"""
        try:
            if disconnect_network(ssid, self.logging):
                GLib.idle_add(self.update_network_list)
                self.logging.log(LogLevel.Info, f"Successfully disconnected from {ssid}")
            else:
                self.logging.log(LogLevel.Error, f"Failed to disconnect from {ssid}")
                GLib.idle_add(self.update_network_list)
        except Exception as e:
            self.logging.log(LogLevel.Error, f"Failed disconnecting from network: {e}")
            GLib.idle_add(self.update_network_list)


    def get_current_network(self):
        """Get the currently connected network"""
        try:
            networks = get_wifi_networks(self.logging)
            current_network = next((network for network in networks if network["in_use"]), None)
            return current_network
        except Exception as e:
            self.logging.log(LogLevel.Error, f"Failed to get current network: {e}")
            return None

    def show_qr_dialog(self, button):
            """Show a qr code dialog for current network"""
            # Get current network
            current_network = self.get_current_network()
            if current_network:
                # create a dialog
                try:
                    connection_info = get_connection_info(current_network["ssid"], self.logging)

                    # generate qr code for wifi
                    qr_path = generate_wifi_qrcode(
                        current_network["ssid"],
                        connection_info.get("password", ""),
                        current_network["security"],
                        self.logging
                    )

                    # use hardcoded fallback title text to avoid missing translation attribute diagnostics
                    dialog_title = getattr(self.txt, "wifi_share_title", "Share WiFi")

                    qr_dialog = Gtk.Dialog(
                        title=dialog_title,
                        parent=self.get_toplevel(),
                        flags=Gtk.DialogFlags.MODAL,
                    )
                    qr_dialog.set_default_size(0,0)
                    qr_dialog.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)

                    # header
                    header_bar = Gtk.HeaderBar()
                    header_bar.set_show_close_button(True)
                    header_bar.set_title(dialog_title)
                    qr_dialog.set_titlebar(header_bar)

                    # content area
                    content_area = qr_dialog.get_content_area()
                    content_area.set_spacing(10)
                    content_area.set_margin_top(10)
                    content_area.set_margin_bottom(10)
                    content_area.set_margin_start(10)
                    content_area.set_margin_end(10)

                    # for qr code image
                    top_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
                    top_box.set_margin_bottom(20)

                    # image holder
                    qr_button = Gtk.Button()
                    qr_button.set_size_request(124,124)
                    qr_button.set_relief(Gtk.ReliefStyle.NONE)
                    qr_button.get_style_context().add_class("qr_image_holder")
                    top_box.pack_start(qr_button, False, False, 0)

                    # fallback for wifi_share_scan
                    scan_text = getattr(self.txt, "wifi_share_scan", "Scan this QR code to join")
                    scan_label = Gtk.Label(label=scan_text)
                    scan_label.get_style_context().add_class("scan_label")
                    top_box.pack_start(scan_label, False, False, 0)

                    if qr_path and not qr_path.endswith("error.png"):
                        qr_image = Gtk.Image()
                        qr_image.set_size_request(120, 120)
                        qr_image.set_margin_top(8)
                        qr_image.set_margin_bottom(8)
                        qr_image.set_from_file(qr_path)
                        qr_button.add(qr_image)
                    else:
                        error_label = Gtk.Label(label="You need to install python-qrencode for this feature to work.")
                        error_label.set_line_wrap(True)
                        error_label.set_max_width_chars(30)
                        qr_button.add(error_label)

                    content_area.pack_start(top_box, False, True, 0)

                    # network details
                    bottom_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
                    bottom_box.set_margin_top(1)

                    # network name
                    ssid_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                    ssid_box.set_size_request(320, 50)
                    ssid_box.get_style_context().add_class("ssid-box")

                    ssid_label_text = getattr(self.txt, "wifi_network_name", "Network name")
                    ssid_label = Gtk.Label(label=ssid_label_text)
                    ssid_label.get_style_context().add_class("dimmed-label")
                    ssid_label.set_markup(f"<b>{ssid_label_text}</b>")
                    ssid_label.set_halign(Gtk.Align.START)

                    ssid_name = Gtk.Label(label=current_network["ssid"])
                    ssid_name.get_style_context().add_class("dimmed-label")
                    ssid_name.set_halign(Gtk.Align.START)
                    ssid_box.pack_start(ssid_label, False, False, 0)
                    ssid_box.pack_start(ssid_name, False, False, 0)

                    # network password
                    security_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                    security_box.set_size_request(320, 50)
                    security_box.get_style_context().add_class("secrity-box")

                    wifi_password_text = getattr(self.txt, "wifi_password", "Password")
                    security_label = Gtk.Label(label=wifi_password_text)
                    security_label.get_style_context().add_class("dimmed-label")
                    security_label.set_markup(f"<b>{wifi_password_text}</b>")
                    security_label.set_halign(Gtk.Align.START)

                    passwd = Gtk.Label(label=connection_info.get("password", "Hidden"))
                    passwd.get_style_context().add_class("dimmed-label")
                    passwd.set_halign(Gtk.Align.START)
                    security_box.pack_start(security_label, False, False, 0)
                    security_box.pack_start(passwd, False, False, 0)

                    # add to bottom box
                    bottom_box.pack_start(ssid_box, False, False, 0)
                    bottom_box.pack_start(security_box, False, False, 0)

                    content_area.pack_start(bottom_box, False, True, 0)

                    qr_dialog.show_all()
                    qr_dialog.run()
                    qr_dialog.destroy()

                except Exception as e:
                    self.logging.log(LogLevel.Error, f"failed to open qr code dialog: {e}")
                    traceback.print_exc()
