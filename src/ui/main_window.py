#!/usr/bin/env python3

import gi  # type: ignore
import threading
import sys
import json
import os
from datetime import datetime
import signal

from utils.arg_parser import ArgParse
from utils.tab_name import TAB_ORDER, read_tab_from_file, tab_name_from_arguments

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk  # type: ignore

from ui.tabs.battery_tab import BatteryTab
from ui.tabs.bluetooth_tab import BluetoothTab
from ui.tabs.display_tab import DisplayTab
from ui.tabs.volume_tab import VolumeTab
from ui.tabs.wifi_tab import WiFiTab
from utils.logger import LogLevel, Logger
from ui.css.animations import load_animations_css
from ui.dialogs.inline_dialog import InlineDialogHost
from utils.translations import Translation

TAB_CLASSES = {
    "Volume": VolumeTab,
    "Wi-Fi": WiFiTab,
    "Bluetooth": BluetoothTab,
    "Battery": BatteryTab,
    "Display": DisplayTab,
}

TAB_ICONS = {
    "Volume": "audio-volume-high-symbolic",
    "Wi-Fi": "network-wireless-symbolic",
    "Bluetooth": "bluetooth-symbolic",
    "Battery": "battery-good-symbolic",
    "Display": "video-display-symbolic",
}


class MicroControl(Gtk.Window):

    def __init__(self, txt: Translation, arg_parser: ArgParse, logging: Logger) -> None:
        # Initialize cache directory
        self.cache_dir = os.path.expanduser("~/.cache/microcontrol")
        os.makedirs(self.cache_dir, exist_ok=True)

        # Initialize thread safety mechanisms
        self._initialized = False
        self._is_destroyed = False
        self._init_lock = threading.Lock()
        self._destroy_lock = threading.Lock()

        # Safe GTK initialization
        with self._init_lock:
            try:
                # Initialize GTK window
                super().__init__(title="MicroControl")
                self._initialized = True
                # Show window immediately for faster perceived startup
                self.show_all()
            except Exception as e:
                logging.log(LogLevel.Error, f"Window initialization failed: {e}")
                raise

        self.logging = logging
        self.txt = txt
        self.arg_parser = arg_parser
        self.set_default_size(600, 400)
        self.logging.log(LogLevel.Info, "Initializing application")

        # Initialize important instance variables to prevent segfaults
        self.tabs = {}
        self.tab_pages = {}
        self._pending_tabs = set()  # tabs with a lazy creation already scheduled

        # Command line options
        self.minimal_mode = arg_parser.find_arg(("-m", "--minimal"))
        if self.minimal_mode:
            self.logging.log(LogLevel.Info, "Minimal mode enabled")
        self.vertical_tabs = arg_parser.find_arg(("-t", "--vertical-tabs"))

        # Apply custom CSS to remove button focus/selection outline
        css_provider = Gtk.CssProvider()
        css = b"""
            button {
                outline: none;
                -gtk-outline-radius: 0;
                border: none;
            }
            button:focus, button:hover, button:active {
                outline: none;
                box-shadow: none;
                border: none;
            }
            notebook tab {
                outline: none;
            }
            notebook tab:focus {
                outline: none;
            }
            /* Make selections invisible */
            selection {
                background-color: transparent;
                color: inherit;
            }
            *:selected {
                background-color: transparent;
                color: inherit;
            }
            textview text selection {
                background-color: transparent;
            }
            entry selection {
                background-color: transparent;
            }
            label selection {
                background-color: transparent;
            }
            treeview:selected {
                background-color: transparent;
            }
            menuitem:selected {
                background-color: transparent;
            }
            listbox row:selected {
                background-color: transparent;
            }
        """
        css_provider.load_from_data(css)
        screen = Gdk.Screen.get_default()
        style_context = Gtk.StyleContext()
        style_context.add_provider_for_screen(
            screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Load animations CSS
        self.animations_css_provider = load_animations_css()

        self.notebook = Gtk.Notebook()
        # Dialogs are shown inside the window, over the notebook
        self.dialog_host = InlineDialogHost(self.notebook)
        self.add(self.dialog_host)

        if self.vertical_tabs:
            self.notebook.set_tab_pos(Gtk.PositionType.LEFT)
        else:
            self.notebook.set_tab_pos(Gtk.PositionType.TOP)

        # Hide tab bar in minimal mode
        if self.minimal_mode:
            self.notebook.set_show_tabs(False)

        # Connect key-press-event to disable tab selection with Tab key
        self.notebook.connect("key-press-event", self.on_notebook_key_press)
        # Also connect key-press-event to the main window to catch all tab presses
        self.connect("key-press-event", self.on_key_press)

        self.create_lazy_tabs()

        self.connect("destroy", self.on_destroy)
        self.notebook.connect("switch-page", self.on_tab_switched)

        signal.signal(signal.SIGUSR1, self.signal_handler)

    def create_lazy_tabs(self):
        """Add all tabs as empty placeholders; only the active one is built now"""
        self.logging.log(LogLevel.Info, "Initializing lazy tab loading")

        # Map tab names to translated labels
        self.tab_name_mapping = {
            "Volume": self.txt.msg_tab_volume,
            "Wi-Fi": self.txt.msg_tab_wifi,
            "Bluetooth": self.txt.msg_tab_bluetooth,
            "Battery": self.txt.msg_tab_battery,
            "Display": self.txt.msg_tab_display,
        }

        self.tabs = {}
        self.tab_pages = {}

        # Active tab: command line argument, else the first tab
        active_tab = tab_name_from_arguments(self.arg_parser) or TAB_ORDER[0]

        for tab_name in TAB_ORDER:
            # Create empty placeholder
            placeholder = Gtk.Box()
            placeholder.show_all()

            # Add tab with label but empty content
            page_num = self.notebook.append_page(
                placeholder,
                self.create_tab_label(tab_name, self.get_icon_for_tab(tab_name))
            )
            self.tabs[tab_name] = placeholder
            self.tab_pages[tab_name] = page_num

            # Load active tab content immediately
            if tab_name == active_tab:
                tab_instance = TAB_CLASSES[tab_name](self.logging, self.txt)
                tab_instance.show_all()
                self.notebook.remove_page(page_num)
                page_num = self.notebook.insert_page(
                    tab_instance,
                    self.create_tab_label(tab_name, self.get_icon_for_tab(tab_name)),
                    page_num
                )
                self.tabs[tab_name] = tab_instance
                self.tab_pages[tab_name] = page_num

        page_num = self.tab_pages[active_tab]
        self.notebook.set_current_page(page_num)
        GLib.idle_add(lambda: self.lazy_load_tab(self.notebook, None, page_num))

        # Other tabs are built on first switch (lazy_load_tab). Preloading them
        # all right after startup ran their constructors (which shell out to
        # nmcli, upower, pactl, ...) on the main loop and froze the window.
        self.notebook.connect("switch-page", self.lazy_load_tab)

        # Show all widgets
        self.show_all()

    def get_cache_file(self, tab_name):
        """Get cache file path for a tab"""
        return os.path.join(self.cache_dir, f"{tab_name}.json")

    def load_from_cache(self, tab_name):
        """Load tab data from cache if valid"""
        cache_file = self.get_cache_file(tab_name)
        if not os.path.exists(cache_file):
            return None

        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
                # Check if cache is expired (1 hour)
                cache_time = datetime.fromisoformat(data['timestamp'])
                if (datetime.now() - cache_time).total_seconds() > 3600:
                    return None
                return data['state']
        except Exception:
            return None

    def save_to_cache(self, tab_name, state):
        """Save tab state to cache"""
        try:
            cache_file = self.get_cache_file(tab_name)
            with open(cache_file, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'state': state
                }, f)
        except Exception as e:
            self.logging.log(LogLevel.Warn, f"Failed to cache {tab_name} state: {e}")

    def lazy_load_tab(self, notebook, page, page_num):
        """Instantiate tab on first switch if not yet created, using cache if available"""
        # Determine tab name by page_num
        tab_name = None
        for name, num in self.tab_pages.items():
            if num == page_num:
                tab_name = name
                break
        if not tab_name:
            return

        # If already created (not a placeholder), do nothing
        current_widget = self.tabs.get(tab_name)
        if isinstance(current_widget, tuple(TAB_CLASSES.values())) or tab_name in self._pending_tabs:
            return
        self._pending_tabs.add(tab_name)

        # Defer real tab creation to avoid segfault during switch-page
        def replace_placeholder():
            # Removing the current page makes the notebook switch pages; don't
            # let that lazily build the neighbouring tab as a side effect.
            self.notebook.handler_block_by_func(self.lazy_load_tab)
            try:
                tab_class = TAB_CLASSES.get(tab_name)
                if not tab_class:
                    return False
                # Try loading from cache first
                cached_state = self.load_from_cache(tab_name)
                tab_instance = tab_class(self.logging, self.txt)

                if cached_state and hasattr(tab_instance, 'load_state'):
                    try:
                        tab_instance.load_state(cached_state)
                    except Exception as e:
                        self.logging.log(LogLevel.Warn, f"Failed to load {tab_name} from cache: {e}")

                tab_instance.show_all()
                self.notebook.remove_page(page_num)
                new_page_num = self.notebook.insert_page(
                    tab_instance,
                    self.create_tab_label(tab_name, self.get_icon_for_tab(tab_name)),
                    page_num
                )
                self.tabs[tab_name] = tab_instance
                self.tab_pages[tab_name] = new_page_num
                # Save to cache if tab supports it
                if hasattr(tab_instance, 'get_state'):
                    try:
                        self.save_to_cache(tab_name, tab_instance.get_state())
                    except Exception as e:
                        self.logging.log(LogLevel.Warn, f"Failed to cache {tab_name} state: {e}")

                self.logging.log(LogLevel.Info, f"Lazily created tab: {tab_name}")
                self.show_all()
                # Activate the newly created tab immediately
                self.notebook.set_current_page(new_page_num)
            except Exception as e:
                self.logging.log(LogLevel.Error, f"Failed to lazily create tab {tab_name}: {e}")
            finally:
                self._pending_tabs.discard(tab_name)
                self.notebook.handler_unblock_by_func(self.lazy_load_tab)
            return False  # Only run once

        GLib.idle_add(replace_placeholder)

    def get_icon_for_tab(self, tab_name):
        """Get icon name for a tab"""
        return TAB_ICONS.get(tab_name, "application-x-executable-symbolic")

    def create_tab_label(self, text: str, icon_name: str) -> Gtk.Box:
        """Create a tab label with an icon and the translated tab name

        Args:
            text (str): Tab label text (internal name)
            icon_name (str): Icon name

        Returns:
            Gtk.Box: Box containing icon and label
        """
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
        box.pack_start(icon, False, False, 0)

        translated_text = self.tab_name_mapping.get(text, text) if hasattr(self, 'tab_name_mapping') else text
        label = Gtk.Label(label=translated_text)
        box.pack_start(label, False, False, 0)

        box.show_all()
        return box

    def on_tab_switched(self, notebook, page, page_num):
        """Handle tab switching"""

        # Apply animation to the new tab
        current_page = notebook.get_nth_page(page_num)
        if current_page:
            # Add fade-in animation class
            current_page.get_style_context().add_class("fade-in")

            # Remove the animation class after it completes
            def remove_animation_class():
                if current_page and not current_page.get_parent() is None:
                    current_page.get_style_context().remove_class("fade-in")
                return False

            # Schedule class removal after animation duration
            GLib.timeout_add(350, remove_animation_class)

        # Update tab visibility status
        for tab_name, tab in self.tabs.items():
            # Check if this tab is at the current page number
            is_visible = self.tab_pages.get(tab_name) == page_num

            # If tab has tab_visible property (WiFi tab), update it
            if hasattr(tab, 'tab_visible'):
                tab.tab_visible = is_visible

            # Update window title in minimal mode
            if is_visible and self.minimal_mode:
                # Use translated tab name in window title
                translated_tab_name = self.tab_name_mapping.get(tab_name, tab_name) if hasattr(self, 'tab_name_mapping') else tab_name
                self.set_title(f"MicroControl - {translated_tab_name}")

    def on_notebook_key_press(self, widget, event):
        """Prevent tab selection with Tab key"""
        # Prevent Tab key (65289) and Shift+Tab (65056)
        if event.keyval in (65289, 65056):
            return True  # Event handled, don't propagate
        return False  # Let other handlers process the event

    def on_key_press(self, widget, event):
        """Prevent tab selection globally, and close the app on Escape"""
        if event.keyval in (65289, 65056):  # Tab and Shift+Tab
            return True  # Stop propagation
        if event.keyval == Gdk.KEY_Escape:
            # An open dialog (overlaid on the notebook) handles Escape itself
            if len(self.dialog_host.get_children()) > 1:
                return False
            self.close()
            return True
        return False  # Let other handlers process the event

    def signal_handler(self, sig, frame):
        """Handle SIGUSR1 signal - toggle window visibility on main thread"""

        def toggle_window_visibility():
            requested = read_tab_from_file()
            requested_page = self.tab_pages.get(requested) if requested else None
            current_page = self.notebook.get_current_page()
            if self.get_visible() and (requested_page is None or requested_page == current_page):
                # Already open on the requested tab (or no tab requested): toggle closed.
                self.hide()
            else:
                # Hidden, or a different tab was requested: show and switch.
                if requested_page is not None:
                    self.notebook.set_current_page(requested_page)
                    GLib.idle_add(lambda: self.lazy_load_tab(self.notebook, None, requested_page))
                self.present()
            return False  # Only run once

        GLib.idle_add(toggle_window_visibility)

    def on_destroy(self, window):
        """Thread-safe window destruction with initialization check"""
        if self._is_destroyed or not hasattr(self, '_initialized') or not self._initialized:
            return

        with self._destroy_lock:
            self._is_destroyed = True
            self.logging.log(LogLevel.Info, "Application shutting down")

            # Clean up children
            try:
                for child in self.get_children():
                    try:
                        child.destroy()
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                if Gtk.main_level() > 0:
                    GLib.idle_add(Gtk.main_quit)
            except Exception:
                pass

        # Signal all tabs to clean up their resources
        for tab_name, tab in self.tabs.items():
            if hasattr(tab, 'on_destroy'):
                try:
                    tab.on_destroy(None)
                except Exception as e:
                    self.logging.log(LogLevel.Error, f"Error destroying {tab_name} tab: {e}")

        self.logging.log(LogLevel.Info, "Application shutdown complete")

        # Use try/except to avoid errors during shutdown
        try:
            sys.stdout = open('/dev/null', 'w')
            sys.stderr = open('/dev/null', 'w')
        except Exception:
            pass

        # Let GTK know we're quitting
        Gtk.main_quit()
