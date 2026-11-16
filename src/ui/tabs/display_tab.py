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

LAYOUT_SINGLE = "single"
LAYOUT_MULTI = "multi"


class _ScaleControl:
    """Scale card for one display: a 100%-300% slider in 25% steps, applied
    once it stops moving"""

    MIN, MAX, STEP = 100, 300, 25  # percent

    def __init__(self, tab: "DisplayTab", name: str):
        self.tab = tab
        self.name = name
        self.syncing = False
        self.apply_id = None

        self.slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, self.MIN, self.MAX, self.STEP)
        self.card = tab._slider_card(tab.txt.display_scale, self.slider)
        self.slider.set_increments(self.STEP, self.STEP)
        self.slider.set_digits(0)
        self.slider.connect("format-value", lambda _s, v: f"{int(round(v))}%")
        self.slider.connect("change-value", self._on_change_value)
        self.slider.connect("value-changed", self._on_value_changed)
        self.card.connect("destroy", lambda _w: self.cancel())

    def sync(self, scale: float) -> None:
        """Show the display's current scale, unless the user is choosing one"""
        if self.apply_id is not None:
            return
        self.syncing = True
        try:
            self.slider.set_value(round(scale * 100))
        finally:
            self.syncing = False

    def cancel(self) -> None:
        if self.apply_id is not None:
            GLib.source_remove(self.apply_id)
            self.apply_id = None

    def _on_change_value(self, scale, _scroll, value):
        """Snap to 25% steps"""
        snapped = min(self.MAX, max(self.MIN, round(value / self.STEP) * self.STEP))
        if snapped != scale.get_value():
            scale.set_value(snapped)
        return True

    def _on_value_changed(self, _scale):
        if self.syncing:
            return
        self.cancel()
        self.apply_id = GLib.timeout_add(500, self._apply)

    def _apply(self):
        self.apply_id = None
        backend = self.tab.display_backend
        if backend is not None:
            backend.set_scale(self.name, self.slider.get_value() / 100)
        # Read back what the compositor settled on (Hyprland may round it)
        GLib.timeout_add(300, lambda: self.tab.refresh_multi_display() and False)
        return False


class DisplayTab(Gtk.Box):
    """Display settings tab.

    With one display connected: Brightness, Blue Light and Scale cards.
    With more: the shared Blue Light and the Layout card (Join / Mirror /
    Single) at the top, then a sub-tab per display with its own settings
    (the primary display toggle, Scale, and Brightness for the built-in
    panel, the one with a backlight).
    """

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

        # Main content box, filled by _build_layout
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        self.content_box.set_margin_top(10)
        self.content_box.set_margin_bottom(10)
        self.content_box.set_margin_start(10)
        self.content_box.set_margin_end(10)

        # Cards that move between the layouts (kept, not rebuilt)
        self.brightness_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 100, 1
        )
        self.brightness_scale.set_value(get_brightness(self.logging))
        self.brightness_scale.connect("value-changed", self.on_brightness_changed)
        self.brightness_card = self._slider_card(self.txt.display_brightness, self.brightness_scale)

        self.bluelight_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 100, 1
        )
        settings = load_settings(self.logging)
        saved_gamma = settings.get("gamma", 6500)
        # Convert temperature to percentage
        percentage = (saved_gamma - 2500) / 40  # (6500-2500)/100 = 40
        self.bluelight_scale.set_value(percentage)
        self.bluelight_scale.connect("value-changed", self.on_bluelight_changed)
        self.bluelight_card = self._slider_card(self.txt.display_blue_light, self.bluelight_scale)

        self.display_backend = get_display_backend(self.logging)
        self._md_syncing = False
        self._md_dialog = None
        self._md_current = None
        self.primary_toggles = {}  # output name -> (switch, label)
        self.multi_display_box = self._build_multi_display_section()

        # Current layout, its per-display sub-tabs and scale controls
        self._layout = None
        self.display_notebook = None
        self.scale_controls = {}
        self.refresh_multi_display()

        scroll_window.add(self.content_box)
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

    # --- layout -----------------------------------------------------------------
    def _layout_for(self, outputs):
        """The layout to show: (LAYOUT_SINGLE, active display name or None), or
        (LAYOUT_MULTI, the displays' sub-tab details)"""
        if self.display_backend is None or len(outputs) < 2:
            active = next((o.name for o in outputs if o.enabled), None)
            return (LAYOUT_SINGLE, active)
        return (LAYOUT_MULTI, tuple((o.name, self._md_output_label(o), o.enabled, o.is_builtin)
                                    for o in outputs))

    def _build_layout(self, layout, outputs):
        """Fill the content box for the layout, keeping the selected sub-tab"""
        selected = None
        if self.display_notebook is not None:
            page = self.display_notebook.get_nth_page(self.display_notebook.get_current_page())
            selected = getattr(page, "output_name", None)

        # Take the kept cards out before the old layout is destroyed
        for card in (self.brightness_card, self.bluelight_card, self.multi_display_box):
            parent = card.get_parent()
            if parent is not None:
                parent.remove(card)
        for child in self.content_box.get_children():
            child.destroy()
        self.display_notebook = None
        self.scale_controls = {}
        self.primary_toggles = {}

        kind, details = layout
        if kind == LAYOUT_SINGLE:
            self.content_box.pack_start(self.brightness_card, False, True, 0)
            self.content_box.pack_start(self.bluelight_card, False, True, 0)
            if details is not None:
                control = _ScaleControl(self, details)
                self.scale_controls[details] = control
                self.content_box.pack_start(control.card, False, True, 0)
        else:
            self.content_box.pack_start(self.bluelight_card, False, True, 0)
            self.content_box.pack_start(self.multi_display_box, False, True, 0)

            notebook = Gtk.Notebook()
            notebook.set_scrollable(True)
            selected_index = 0
            for name, label, enabled, builtin in details:
                page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
                page.set_margin_top(12)
                page.output_name = name
                page.pack_start(self._primary_toggle_card(name), False, True, 0)
                if enabled:
                    # brightnessctl controls the backlight: the built-in panel's
                    if builtin and self.brightness_card.get_parent() is None:
                        page.pack_start(self.brightness_card, False, True, 0)
                    control = _ScaleControl(self, name)
                    self.scale_controls[name] = control
                    page.pack_start(control.card, False, True, 0)
                else:
                    off = Gtk.Label(label=getattr(self.txt, "display_off", "This display is off."))
                    off.get_style_context().add_class("dim-label")
                    page.pack_start(off, False, True, 0)
                tab_label = Gtk.Label(label=self.txt.display_builtin if builtin else self._short_label(name, label))
                tab_label.set_tooltip_text(label)
                if name == selected:
                    selected_index = notebook.get_n_pages()
                notebook.append_page(page, tab_label)
            self.display_notebook = notebook
            self.content_box.pack_start(notebook, False, True, 0)
            self.content_box.show_all()
            notebook.set_current_page(selected_index)

        self.content_box.show_all()
        self._layout = layout

    def _primary_toggle_card(self, name):
        """Card with a switch making the display the primary one (in Single
        mode, the active one)"""
        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.IN)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.set_margin_start(12)
        row.set_margin_end(12)
        row.set_margin_top(12)
        row.set_margin_bottom(12)
        label = Gtk.Label(xalign=0)
        row.pack_start(label, True, True, 0)
        switch = Gtk.Switch()
        switch.set_valign(Gtk.Align.CENTER)
        switch.connect("notify::active", self.on_primary_toggled, name)
        row.pack_end(switch, False, False, 0)
        frame.add(row)
        self.primary_toggles[name] = (switch, label)
        return frame

    @staticmethod
    def _short_label(name, label):
        """Sub-tab title: the display's make and model, or its output name"""
        prefix = f"{name} — "
        return label[len(prefix):] if label.startswith(prefix) else name

    # --- multiple displays ------------------------------------------------------
    def _build_multi_display_section(self):
        """Build the GNOME-like Join / Mirror / Single display mode controls"""
        section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Card like the slider cards: title inside, 12px padding
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

        frame.add(box)
        section.pack_start(frame, False, True, 0)
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
        text = self.txt.display_active if mode == MODE_SINGLE else self.txt.display_primary
        for _switch, label in self.primary_toggles.values():
            label.set_text(text)

    def refresh_multi_display(self, *args):
        """Sync the layout and the controls with the current displays"""
        if self._md_dialog is not None:
            return True  # don't fight the user while they confirm a change

        outputs = self.display_backend.list_outputs() if self.display_backend is not None else []
        layout = self._layout_for(outputs)
        if layout != self._layout:
            self._build_layout(layout, outputs)

        for o in outputs:
            control = self.scale_controls.get(o.name)
            if control is not None and o.enabled:
                control.sync(o.scale)

        if layout[0] != LAYOUT_MULTI:
            self._md_current = None
            return True

        mode = detect_mode(outputs)
        primary = self.display_backend.get_primary(outputs)
        self._md_syncing = True
        try:
            for name, (switch, _label) in self.primary_toggles.items():
                switch.set_active(name == primary)
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
        self._md_request(mode, self._md_current[1] if self._md_current else None)

    def on_primary_toggled(self, switch, _param, name):
        if self._md_syncing:
            return
        if not switch.get_active():
            # The primary can't be switched off, only replaced by another.
            # Switched back on once this handler is done: GTK delays the
            # notification of a change made to the switch from its own handler
            if self._md_current and self._md_current[1] == name:
                GLib.idle_add(self._set_toggle_on, switch)
            return
        # Only one display is the primary: switch the others off right away
        self._md_syncing = True
        try:
            for other, (other_switch, _label) in self.primary_toggles.items():
                if other != name:
                    other_switch.set_active(False)
        finally:
            self._md_syncing = False
        self._md_request(self._md_active_mode(), name)
        if self._md_dialog is None:
            # Nothing was applied (or it failed): show the actual state again
            self.refresh_multi_display()

    def _set_toggle_on(self, switch):
        self._md_syncing = True
        try:
            switch.set_active(True)
        finally:
            self._md_syncing = False
        return False

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

    # --- brightness and blue light ---------------------------------------------
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

    # --- visibility and refresh --------------------------------------------------
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
