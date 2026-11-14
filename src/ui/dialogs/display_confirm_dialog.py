import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib  # type: ignore


class DisplayConfirmDialog(Gtk.MessageDialog):
    """Ask to keep new display settings, reverting automatically after a countdown.

    Emits the standard "response" signal with Gtk.ResponseType.OK (keep) or
    Gtk.ResponseType.CANCEL (revert, also sent when the countdown runs out).
    """

    def __init__(self, parent, txt, countdown: int = 30):
        super().__init__(
            transient_for=parent,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text=txt.display_keep_changes,
        )
        self.txt = txt
        self.countdown = countdown

        self.add_button(txt.display_revert, Gtk.ResponseType.CANCEL)
        self.add_button(txt.display_keep, Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.CANCEL)

        self._update_text()
        self.timeout_id = GLib.timeout_add_seconds(1, self._tick)
        self.connect("response", self._on_response)

    def _update_text(self):
        self.format_secondary_text(self.txt.display_reverting_in.format(seconds=self.countdown))

    def _tick(self):
        self.countdown -= 1
        if self.countdown <= 0:
            self.timeout_id = None
            self.response(Gtk.ResponseType.CANCEL)
            return False
        self._update_text()
        return True

    def _on_response(self, dialog, response):
        if self.timeout_id is not None:
            GLib.source_remove(self.timeout_id)
            self.timeout_id = None
