"""Dialogs drawn inside the main window, like libadwaita's: a card centered
over the window's content, which is dimmed behind it, instead of a separate
window (which the compositor may give a titlebar, or tile).

The main window wraps its content in an InlineDialogHost. A dialog is built,
then shown with present(on_response); on_response(response) is called once,
with the response of the button clicked, or Gtk.ResponseType.CANCEL for
Escape. Widgets in the content area can still be read in on_response.
"""

from typing import Callable, Dict, Optional

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk  # type: ignore


class InlineDialogHost(Gtk.Overlay):
    """Holds the window's content, with dialogs overlaid on top of it"""

    def __init__(self, child: Gtk.Widget):
        super().__init__()
        self.add(child)


def _find_host(widget: Gtk.Widget) -> Optional[InlineDialogHost]:
    return getattr(widget.get_toplevel(), "dialog_host", None)


def _first_entry(widget: Gtk.Widget) -> Optional[Gtk.Entry]:
    if isinstance(widget, Gtk.Entry):
        return widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            found = _first_entry(child)
            if found is not None:
                return found
    return None


class InlineDialog(Gtk.EventBox):
    def __init__(self, parent: Gtk.Widget, title: Optional[str] = None, text: Optional[str] = None):
        """parent: any widget in the window to show the dialog in"""
        super().__init__()
        self._parent = parent
        self._buttons: Dict[int, Gtk.Button] = {}
        self._default: Optional[int] = None
        self._on_response: Optional[Callable[[int], None]] = None
        self._key_handler = None
        self._window: Optional[Gtk.Window] = None
        self._done = False

        # Swallow clicks on the dimmed backdrop
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", lambda *_: True)

        backdrop = Gtk.Box()
        backdrop.get_style_context().add_class("inline-dialog-backdrop")
        backdrop.get_style_context().add_class("fade-in")
        self.add(backdrop)

        self.card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.card.get_style_context().add_class("inline-dialog")
        self.card.set_halign(Gtk.Align.CENTER)
        self.card.set_valign(Gtk.Align.CENTER)
        self.card.set_margin_start(16)
        self.card.set_margin_end(16)
        self.card.set_size_request(300, -1)
        backdrop.pack_start(self.card, True, False, 0)

        if title:
            title_label = Gtk.Label(label=title)
            title_label.get_style_context().add_class("inline-dialog-title")
            title_label.set_line_wrap(True)
            title_label.set_max_width_chars(36)
            title_label.set_justify(Gtk.Justification.CENTER)
            self.card.pack_start(title_label, False, False, 0)
        if text:
            text_label = Gtk.Label(label=text)
            text_label.set_line_wrap(True)
            text_label.set_max_width_chars(36)
            text_label.set_justify(Gtk.Justification.CENTER)
            self.card.pack_start(text_label, False, False, 0)

        self.content_area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.card.pack_start(self.content_area, False, False, 0)

        self.button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, homogeneous=True)
        self.button_box.set_margin_top(6)
        self.card.pack_start(self.button_box, False, False, 0)

    def get_content_area(self) -> Gtk.Box:
        return self.content_area

    def add_button(self, label: str, response: int, style: Optional[str] = None) -> Gtk.Button:
        """style: e.g. "suggested-action" or "destructive-action" """
        button = Gtk.Button(label=label)
        button.set_can_default(True)
        if style:
            button.get_style_context().add_class(style)
        button.connect("clicked", lambda _: self.respond(response))
        self.button_box.pack_start(button, True, True, 0)
        self._buttons[response] = button
        return button

    def set_default_response(self, response: int) -> None:
        """The button activated by Enter in an entry (with activates-default)"""
        self._default = response

    def present(self, on_response: Optional[Callable[[int], None]] = None) -> None:
        self._on_response = on_response
        host = _find_host(self._parent)
        if host is None:
            raise RuntimeError("No InlineDialogHost in this window")
        host.add_overlay(self)
        self.show_all()

        # Keep input in the dialog while it's open
        self.grab_add()
        self._window = host.get_toplevel()
        self._key_handler = self._window.connect("key-press-event", self._on_key)
        default = self._buttons.get(self._default)
        if default is not None:
            self._window.set_default(default)
        focus = _first_entry(self.content_area) or default
        if focus is not None:
            focus.grab_focus()

    def respond(self, response: int) -> None:
        if self._done:
            return
        self._done = True
        self.grab_remove()
        if self._window is not None:
            if self._key_handler is not None:
                self._window.disconnect(self._key_handler)
            if self._window.get_default_widget() in self._buttons.values():
                self._window.set_default(None)
        parent = self.get_parent()
        if parent is not None:
            parent.remove(self)
        try:
            if self._on_response is not None:
                self._on_response(response)
        finally:
            self.destroy()

    def _on_key(self, _window, event) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self.respond(Gtk.ResponseType.CANCEL)
            return True
        return False


def show_message(parent: Gtk.Widget, title: str, text: Optional[str] = None,
                 on_close: Optional[Callable[[], None]] = None) -> None:
    """An inline dialog with a message and an OK button"""
    dialog = InlineDialog(parent, title, text)
    dialog.add_button("OK", Gtk.ResponseType.OK, "suggested-action")
    dialog.present(lambda _: on_close() if on_close else None)


def ask(parent: Gtk.Widget, title: str, text: Optional[str], confirm_label: str,
        on_confirm: Callable[[], None], cancel_label: str = "Cancel", destructive: bool = False) -> None:
    """An inline dialog asking to confirm an action"""
    dialog = InlineDialog(parent, title, text)
    dialog.add_button(cancel_label, Gtk.ResponseType.CANCEL)
    dialog.add_button(confirm_label, Gtk.ResponseType.OK,
                      "destructive-action" if destructive else "suggested-action")
    dialog.present(lambda response: on_confirm() if response == Gtk.ResponseType.OK else None)
