#!/usr/bin/env python3

import gi  # type: ignore
import subprocess

from utils.logger import LogLevel, Logger
from utils.translations import Translation

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib  # type: ignore

from utils.settings import load_settings, save_settings
from tools.display import get_brightness, set_brightness
from tools.globals import get_current_session
from tools.multi_display import (
    MODE_JOIN, MODE_MIRROR, MODE_SINGLE, detect_mode, get_display_backend,
)
from ui.dialogs.display_confirm_dialog import DisplayConfirmDialog

class DisplayTab(Gtk.Box):
    """Display settings tab"""

    def __init__(self, logging: Logger, txt: Translation):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.txt = txt
        self.logging = logging
        self.update_timeout_id = None
        self.update_interval = 500  # milliseconds
        self.multi_display_timeout_id = None
        self.multi_display_interval = 3000  # milliseconds, catches hotplugged displays
        self.is_visible = False
        self.session = get_current_session()

        self.set_margin_start(15)
        self.set_margin_end(15)
        self.set_margin_top(15)
        self.set_margin_bottom(15)
        self.set_hexpand(True)
        self.set_vexpand(True)

        # Create scrollable content
        scroll_window = Gtk.ScrolledWindow()
        scroll_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll_window.set_vexpand(True)

        # Create main content box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        content_box.set_margin_top(10)
        content_box.set_margin_bottom(10)
        content_box.set_margin_start(10)
        content_box.set_margin_end(10)
        
        # Brightness
        self.brightness_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 100, 1
        )
        self.brightness_scale.set_value(get_brightness(self.logging))
        self.brightness_scale.connect("value-changed", self.on_brightness_changed)
        content_box.pack_start(
            self._slider_card(self.txt.display_brightness, self.brightness_scale), False, True, 0
        )

        # Blue light
        self.bluelight_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 100, 1
        )
        settings = load_settings(self.logging)
        saved_gamma = settings.get("gamma", 6500)
        # Convert temperature to percentage
        percentage = (saved_gamma - 2500) / 40  # (6500-2500)/100 = 40
        self.bluelight_scale.set_value(percentage)
        self.bluelight_scale.connect("value-changed", self.on_bluelight_changed)
        content_box.pack_start(
            self._slider_card(self.txt.display_blue_light, self.bluelight_scale), False, True, 0
        )

        # Multiple displays section (only shown with 2+ connected displays)
        self.display_backend = get_display_backend(self.logging)

        # Display scale
        self.scale_card = self._build_scale_section()
        content_box.pack_start(self.scale_card, False, True, 0)
        self.refresh_scale()
        self._md_syncing = False
        self._md_dialog = None
        self._md_output_labels = None
        self._md_current = None
        self.multi_display_box = self._build_multi_display_section()
        content_box.pack_start(self.multi_display_box, False, True, 0)
        self.refresh_multi_display()

        scroll_window.add(content_box)
        self.pack_start(scroll_window, True, True, 0)

        # Connect destroy signal to cleanup
        self.connect("destroy", self.on_destroy)

        # Connect visibility signals
        self.connect("map", self.on_mapped)
        self.connect("unmap", self.on_unmapped)

        # Only start auto-refresh when the tab becomes visible
        if self.get_mapped():
            self.is_visible = True
            self.start_auto_update()
        
        self.previous_orientation = "normal"
    
    def _slider_card(self, title, scale, extra=None):
        """A framed card with a bold title above a slider, like the Volume tab's
        (an optional extra widget goes between the title and the slider)"""
        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.IN)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)

        title_label = Gtk.Label()
        title_label.set_markup(f"<b>{GLib.markup_escape_text(title)}</b>")
        title_label.set_halign(Gtk.Align.START)
        box.pack_start(title_label, False, True, 0)
        if extra is not None:
            box.pack_start(extra, False, True, 0)

        # Same slider settings as the Volume tab
        scale.set_draw_value(True)
        scale.set_value_pos(Gtk.PositionType.RIGHT)
        scale.set_increments(1, 5)
        scale.set_hexpand(True)
        box.pack_start(scale, True, True, 0)

        frame.add(box)
        return frame

    SCALE_MIN, SCALE_MAX, SCALE_STEP = 100, 300, 25  # percent

    def _build_scale_section(self):
        """Card with a display scale slider (100%-300% in 25% steps)"""
        self._scale_syncing = False
        self._scale_apply_id = None
        self._scale_output_names = None

        # Display picker, only shown when more than one display is active
        self.scale_display_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.scale_display_row.pack_start(Gtk.Label(label=f"{self.txt.msg_tab_display}:"), False, True, 0)
        self.scale_display_combo = Gtk.ComboBoxText()
        self.scale_display_combo.set_hexpand(True)
        self.scale_display_combo.connect("changed", self.on_scale_display_changed)
        self.scale_display_row.pack_start(self.scale_display_combo, True, True, 0)
        for child in self.scale_display_row.get_children():
            child.show_all()
        self.scale_display_row.set_no_show_all(True)  # shown by refresh_scale

        self.scale_slider = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, self.SCALE_MIN, self.SCALE_MAX, self.SCALE_STEP
        )
        card = self._slider_card(self.txt.display_scale, self.scale_slider, self.scale_display_row)
        self.scale_slider.set_increments(self.SCALE_STEP, self.SCALE_STEP)
        self.scale_slider.set_digits(0)
        self.scale_slider.connect("format-value", lambda _s, v: f"{int(round(v))}%")
        self.scale_slider.connect("change-value", self.on_scale_change_value)
        self.scale_slider.connect("value-changed", self.on_scale_value_changed)

        card.set_no_show_all(True)  # visibility driven by refresh_scale
        card.get_child().show_all()
        return card

    def _scale_target(self):
        """Name of the display the scale slider controls"""
        return self.scale_display_combo.get_active_id()

    def refresh_scale(self):
        """Show the scale card (when there's an active display) and sync it"""
        backend = self.display_backend
        outputs = []
        if backend is not None:
            outputs = [o for o in backend.list_outputs() if o.enabled]
        self.scale_card.set_visible(bool(outputs))
        if not outputs or self._scale_apply_id is not None:
            return  # nothing to show, or the user is still choosing a value

        self._scale_syncing = True
        try:
            names = [(o.name, self._md_output_label(o)) for o in outputs]
            if names != self._scale_output_names:
                current = self._scale_target()
                self.scale_display_combo.remove_all()
                for name, label in names:
                    self.scale_display_combo.append(name, label)
                self._scale_output_names = names
                ids = [n for n, _ in names]
                if current not in ids:
                    current = backend.get_primary(outputs)
                    current = current if current in ids else ids[0]
                self.scale_display_combo.set_active_id(current)
            self.scale_display_row.set_visible(len(outputs) > 1)

            target = next(o for o in outputs if o.name == self._scale_target())
            self.scale_slider.set_value(round(target.scale * 100))
        finally:
            self._scale_syncing = False

    def on_scale_display_changed(self, combo):
        if not self._scale_syncing:
            self.refresh_scale()

    def on_scale_change_value(self, scale, scroll, value):
        """Snap to 25% steps"""
        step = self.SCALE_STEP
        snapped = min(self.SCALE_MAX, max(self.SCALE_MIN, round(value / step) * step))
        if snapped != scale.get_value():
            scale.set_value(snapped)
        return True

    def on_scale_value_changed(self, scale):
        """Apply once the slider has stopped moving, not at every step"""
        if self._scale_syncing:
            return
        if self._scale_apply_id is not None:
            GLib.source_remove(self._scale_apply_id)
        self._scale_apply_id = GLib.timeout_add(500, self._apply_scale)

    def _apply_scale(self):
        self._scale_apply_id = None
        name = self._scale_target()
        value = self.scale_slider.get_value() / 100
        if name and self.display_backend is not None:
            self.display_backend.set_scale(name, value)
        # Read back what the compositor settled on (Hyprland may round it)
        GLib.timeout_add(300, lambda: self.refresh_scale() and False)
        return False

    def _build_multi_display_section(self):
        """Build the GNOME-like Join / Mirror / Single display mode controls"""
        section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Card like the slider cards above: title inside, 12px padding
        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.IN)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)

        title = Gtk.Label()
        title.set_markup(f"<b>{self.txt.display_multi_title}</b>")
        title.set_halign(Gtk.Align.START)
        box.pack_start(title, False, True, 0)

        # Display mode toggle buttons
        mode_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        mode_box.get_style_context().add_class("linked")
        self.md_mode_buttons = {}
        group = None
        for mode, label in (
            (MODE_JOIN, self.txt.display_mode_join),
            (MODE_MIRROR, self.txt.display_mode_mirror),
            (MODE_SINGLE, self.txt.display_mode_single),
        ):
            button = Gtk.RadioButton.new_with_label_from_widget(group, label)
            button.set_mode(False)  # render as a toggle button
            group = group or button
            button.connect("toggled", self.on_md_mode_toggled, mode)
            mode_box.pack_start(button, True, True, 0)
            self.md_mode_buttons[mode] = button
        box.pack_start(mode_box, False, False, 0)

        # Primary display selector
        primary_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.md_primary_label = Gtk.Label(label=self.txt.display_primary)
        self.md_primary_label.set_halign(Gtk.Align.START)
        primary_row.pack_start(self.md_primary_label, False, False, 0)
        self.md_primary_combo = Gtk.ComboBoxText()
        self.md_primary_combo.set_hexpand(True)
        self.md_primary_combo.connect("changed", self.on_md_primary_changed)
        primary_row.pack_start(self.md_primary_combo, True, True, 0)
        box.pack_start(primary_row, False, False, 0)

        frame.add(box)
        section.pack_start(frame, False, True, 0)

        # Visibility is driven by refresh_multi_display, not by show_all()
        frame.show_all()
        section.set_no_show_all(True)
        return section

    def _md_output_label(self, output):
        if output.is_builtin:
            return f"{self.txt.display_builtin} ({output.name})"
        if output.description:
            return f"{output.name} — {output.description}"
        return output.name

    def _md_active_mode(self):
        for mode, button in self.md_mode_buttons.items():
            if button.get_active():
                return mode
        return MODE_JOIN

    def _md_update_labels(self, mode):
        self.md_primary_label.set_text(
            self.txt.display_active if mode == MODE_SINGLE else self.txt.display_primary
        )

    def refresh_multi_display(self, *args):
        """Sync the multi-display controls with the current output state"""
        self.refresh_scale()
        if self.display_backend is None:
            self.multi_display_box.set_visible(False)
            return True
        if self._md_dialog is not None:
            return True  # don't fight the user while they confirm a change

        outputs = self.display_backend.list_outputs()
        visible = len(outputs) >= 2
        self.multi_display_box.set_visible(visible)
        if not visible:
            self._md_current = None
            return True

        mode = detect_mode(outputs)
        primary = self.display_backend.get_primary(outputs)
        self._md_syncing = True
        try:
            labels = [(o.name, self._md_output_label(o)) for o in outputs]
            if labels != self._md_output_labels:
                self.md_primary_combo.remove_all()
                for name, label in labels:
                    self.md_primary_combo.append(name, label)
                self._md_output_labels = labels
            self.md_primary_combo.set_active_id(primary)
            self.md_mode_buttons[mode].set_active(True)

            mirror_button = self.md_mode_buttons[MODE_MIRROR]
            mirror_ok = self.display_backend.supports_mirror()
            mirror_button.set_sensitive(mirror_ok or mode == MODE_MIRROR)
            if mirror_ok:
                tooltip = None
            elif self.display_backend.mirror_unavailable_reason() == "wl-mirror":
                tooltip = self.txt.display_mirror_unavailable
            else:
                tooltip = getattr(self.txt, "display_mirror_unsupported",
                                  "Mirroring isn't supported on this compositor yet.")
            mirror_button.set_tooltip_text(tooltip)
            self._md_update_labels(mode)
        finally:
            self._md_syncing = False
        self._md_current = (mode, primary)
        return True

    def on_md_mode_toggled(self, button, mode):
        if self._md_syncing or not button.get_active():
            return
        self._md_update_labels(mode)
        self._md_request(mode, self.md_primary_combo.get_active_id())

    def on_md_primary_changed(self, combo):
        if self._md_syncing:
            return
        self._md_request(self._md_active_mode(), combo.get_active_id())

    def _md_request(self, mode, primary):
        """Apply a display mode, then ask to keep it or revert"""
        if not primary or self._md_dialog is not None or (mode, primary) == self._md_current:
            return
        backend = self.display_backend
        snapshot = backend.list_outputs()
        previous_primary = backend.get_primary(snapshot)

        def revert():
            self.logging.log(LogLevel.Info, "Reverting display configuration")
            backend.restore(snapshot)
            backend.save_primary(previous_primary)

        if not backend.apply(mode, primary):
            self.logging.log(LogLevel.Error, f"Failed to apply display mode '{mode}'")
            revert()
            self.refresh_multi_display()
            return

        self.multi_display_box.set_sensitive(False)
        parent = self.get_toplevel()
        dialog = DisplayConfirmDialog(parent if isinstance(parent, Gtk.Window) else None, self.txt)
        self._md_dialog = dialog

        def on_response(dlg, response):
            dlg.destroy()
            if response != Gtk.ResponseType.OK:
                revert()
            self._md_dialog = None
            self.multi_display_box.set_sensitive(True)
            self.refresh_multi_display()

        dialog.connect("response", on_response)
        dialog.show_all()

    def on_brightness_changed(self, scale):
        """Handle brightness scale changes"""
        value = int(scale.get_value())
        set_brightness(value, self.logging)

    def set_bluelight(self, temperature):
        """Set blue light level"""
        temperature = int(temperature)
        settings = load_settings(self.logging)
        settings["gamma"] = temperature
        save_settings(settings, self.logging)

        # Kill any existing gammastep process
        subprocess.run(
            ["pkill", "-f", "gammastep"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Start new gammastep process with new temperature
        subprocess.Popen(
            ["gammastep", "-O", str(temperature)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def on_bluelight_changed(self, scale):
        """Handle blue light scale changes"""
        percentage = int(scale.get_value())
        temperature = int(2500 + (percentage * 40))
        self.set_bluelight(temperature)

    def refresh_display_settings(self, *args):
        """Refresh display settings"""
        self.logging.log(LogLevel.Info, "Refreshing display settings")

        # Block the value-changed signal before updating the brightness slider
        self.brightness_scale.disconnect_by_func(self.on_brightness_changed)

        # Update brightness slider with current value
        current_brightness = get_brightness(self.logging)
        self.brightness_scale.set_value(current_brightness)

        # Reconnect the value-changed signal
        self.brightness_scale.connect("value-changed", self.on_brightness_changed)

        # Reload settings from file
        settings = load_settings(self.logging)
        saved_gamma = settings.get("gamma", 6500)
        # Convert temperature to percentage (non-inverted: 2500K = 0%, 6500K = 100%)
        percentage = (saved_gamma - 2500) / 40  # (6500-2500)/100 = 40

        # Block the value-changed signal before updating the blue light filter slider
        self.bluelight_scale.disconnect_by_func(self.on_bluelight_changed)

        # Update blue light filter slider with saved value
        self.bluelight_scale.set_value(percentage)

        # Reconnect the value-changed signal
        self.bluelight_scale.connect("value-changed", self.on_bluelight_changed)

        # Return True to keep the timer running if this was called by the timer
        return True

    def on_mapped(self, widget):
        """Called when the widget becomes visible"""
        self.is_visible = True
        self.start_auto_update()
        self.logging.log(LogLevel.Info, "Display tab became visible, starting auto-update")

    def on_unmapped(self, widget):
        """Called when the widget is hidden"""
        self.is_visible = False
        self.stop_auto_update()
        self.logging.log(LogLevel.Info, "Display tab hidden, stopping auto-update")

    def start_auto_update(self):
        """Start auto-updating display settings"""
        if self.update_timeout_id is None and self.is_visible:
            self.update_timeout_id = GLib.timeout_add(
                self.update_interval, self.refresh_display_settings
            )
            if self.display_backend is not None:
                self.refresh_multi_display()
                self.multi_display_timeout_id = GLib.timeout_add(
                    self.multi_display_interval, self.refresh_multi_display
                )
            self.logging.log(LogLevel.Info, f"Auto-update started with {self.update_interval}ms interval")

    def stop_auto_update(self):
        """Stop auto-updating display settings"""
        if self.multi_display_timeout_id is not None:
            GLib.source_remove(self.multi_display_timeout_id)
            self.multi_display_timeout_id = None
        if self.update_timeout_id is not None:
            GLib.source_remove(self.update_timeout_id)
            self.update_timeout_id = None
            self.logging.log(LogLevel.Info, "Auto-update stopped")

    def on_destroy(self, widget):
        """Clean up resources when widget is destroyed"""
        self.stop_auto_update()
