#!/usr/bin/env python3

import os
import subprocess
from typing import Any
import gi  # type: ignore
import sys
from setproctitle import setproctitle
import signal
import threading
from utils.arg_parser import ArgParse
from utils.logger import LogLevel, Logger
from utils.settings import ensure_config_dir
from utils.translations import get_translations

# Initialize GTK before imports
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, GLib  # type: ignore

from ui.main_window import MicroControl
from tools.bluetooth import restore_last_sink
from tools.hyprland import set_floating_rule


def signal_handler(sig, frame):
    """Immediately kill the process on signal"""
    import os

    os._exit(0)


def parse_arguments():
    arg_parser = ArgParse(sys.argv)

    if arg_parser.find_arg(("-h", "--help")):
        arg_parser.print_help_msg(sys.stdout)
        sys.exit(0)

    return arg_parser


def setup_logging(arg_parser):
    logger = Logger(arg_parser)
    logger.log(LogLevel.Info, "Starting MicroControl")
    return logger


def setup_temp_directory(logger):
    ensure_config_dir(logger)
    try:
        temp_dir = os.path.join("/tmp", "microcontrol")
        os.makedirs(temp_dir, exist_ok=True)
        logger.log(LogLevel.Info, f"Created temporary directory at {temp_dir}")
    except Exception as e:
        logger.log(LogLevel.Error, f"Error creating temporary directory: {e}")


def process_language(arg_parser, logger):
    """Translations for -L/--lang, or the system language ($LANG) by default"""
    available_languages = ["en", "es", "pt", "fr", "id", "it", "tr", "de", "ru"]
    lang = "default"

    if arg_parser.find_arg(("-L", "--lang")):
        requested = arg_parser.option_arg(("-L", "--lang"))
        if requested in available_languages:
            lang = requested
        else:
            print(f"\033[1;31mError: Invalid language code '{requested}'\033[0m")
            print(f"Available languages: {', '.join(available_languages)}")
            print("Using the system language instead")
            logger.log(
                LogLevel.Warn,
                f"Invalid language code '{requested}'. Using the system language",
            )

    logger.log(LogLevel.Info, f"Language: {lang}")
    return get_translations(logger, lang)


def apply_environment_variables():
    # Initialize environment variables
    os.environ['PYTHONUNBUFFERED'] = '1'
    os.environ['DBUS_FATAL_WARNINGS'] = '0'
    os.environ['GST_GL_XINITTHREADS'] = '1'
    os.environ['G_SLICE'] = 'always-malloc'
    os.environ['MALLOC_CHECK_'] = '2'
    os.environ['MALLOC_PERTURB_'] = '0'


def launch_main_window(arg_parser, logger, txt):
    logger.log(LogLevel.Info, "Creating main window")
    win = MicroControl(txt, arg_parser, logger)
    logger.log(LogLevel.Info, "Main window created successfully")

    setproctitle("microcontrol")

    def run_audio_operation():
        restore_last_sink(logger)

    GLib.idle_add(run_audio_operation)

    option: Any = []
    if arg_parser.find_arg(("-s", "--size")):
        optarg = arg_parser.option_arg(("-s", "--size"))
        if optarg is None or 'x' not in optarg:
            logger.log(LogLevel.Error, "Invalid window size")
            sys.exit(1)
        else:
            option = optarg.split('x')
    else:
        option = [700, 600]

    win.set_default_size(int(option[0]), int(option[1]))
    win.resize(int(option[0]), int(option[1]))
    win.connect("destroy", Gtk.main_quit)
    win.show_all()

    xdg = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    sway_sock = os.environ.get("SWAYSOCK", "").lower()

    if "hyprland" in xdg:
        set_floating_rule(logger)
    elif "sway" in sway_sock:
        try:
            subprocess.run(
                [
                    "swaymsg",
                    "for_window",
                    '[app_id="^microcontrol$"]',
                    "floating",
                    "enable",
                ],
                check=False,
            )
        except Exception as e:
            logger.log(
                LogLevel.Warn, f"Failed to set sway window rule: {e}"
            )

    try:
        Gtk.main()
    except KeyboardInterrupt:
        logger.log(LogLevel.Info, "Keyboard interrupt detected, exiting...")
        Gtk.main_quit()
        sys.exit(0)
    except Exception as e:
        logger.log(LogLevel.Error, f"Error in GTK main loop: {e}")
        sys.exit(1)


def initialize_and_start():
    # Register signals again to be safe
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Window/app ID ("microcontrol") for compositor window rules, and the
    # app's display name; must be set before GTK connects to the display
    GLib.set_prgname("microcontrol")
    GLib.set_application_name("MicroControl")

    # GTK must be initialized before any IconTheme/Window use.
    # (main() does this via Gtk.init_check; this entry point did not,
    # so fresh launches crashed in icon preloading.)
    Gtk.init_check()
    if not Gtk.init_check()[0]:
        sys.stderr.write("Failed to initialize GTK\n")
        sys.exit(1)

    apply_environment_variables()

    arg_parser = parse_arguments()

    logger = setup_logging(arg_parser)

    setup_temp_directory(logger)

    txt = process_language(arg_parser, logger)

    # Make sure kanshi runs on Wayland compositors: it applies the display
    # layouts set in the Display tab (and re-applies them on hotplug)
    def ensure_kanshi():
        try:
            from tools.multi_display import KanshiBackend, get_display_backend
            from tools import kanshi
            if isinstance(get_display_backend(logger), KanshiBackend):
                kanshi.ensure_running(logger)
        except Exception as e:
            logger.log(LogLevel.Error, f"Failed to start kanshi: {e}")

    threading.Thread(target=ensure_kanshi, daemon=True).start()

    try:
        launch_main_window(arg_parser, logger, txt)
    except Exception as e:
        logger.log(LogLevel.Error, f"Fatal error starting application: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    initialize_and_start()
