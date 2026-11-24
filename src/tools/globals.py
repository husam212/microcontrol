#!/usr/bin/env python3
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk # type: ignore


# css for wifi_tab
def get_wifi_css():
    css_provider = Gtk.CssProvider()
    css_provider.load_from_data(b"""
        .qr_image_holder{
            border-radius: 12px;
        }
        .scan_label{
            font-size: 18px;
            font-weight: bold;
        }
        .ssid-box{
            background: @wm_button_unfocused_bg;
            border-radius: 6px;
            border-bottom-right-radius: 0px;
            border-bottom-left-radius: 0px;
            padding: 10px;
        }
        .dimmed-label{
            opacity: 0.5;
        }
        .secrity-box{
            background: @wm_button_unfocused_bg;
            border-radius: 6px;
            border-top-right-radius: 0px;
            border-top-left-radius: 0px;
            padding: 10px;
        }
    """)

    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_USER
    )
