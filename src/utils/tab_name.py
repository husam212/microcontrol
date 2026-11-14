import os
from pathlib import Path
from utils.arg_parser import ArgParse

# Tabs in the order they appear
TAB_ORDER = ["Audio", "Wi-Fi", "Bluetooth", "Battery", "Display"]


def tab_name_from_arguments(arg_parser: ArgParse):
    active_tab = None

    if arg_parser.find_arg(("-a", "--audio")):
        active_tab = "Audio"
    elif arg_parser.find_arg(("-w", "--wifi")):
        active_tab = "Wi-Fi"
    elif arg_parser.find_arg(("-b", "--bluetooth")):
        active_tab = "Bluetooth"
    elif arg_parser.find_arg(("-B", "--battery")):
        active_tab = "Battery"
    elif arg_parser.find_arg(("-d", "--display")):
        active_tab = "Display"

    return active_tab

def read_tab_from_file():
    temp_dir = Path("/tmp/microcontrol")
    tab_file_path = temp_dir / "tab.txt"

    if os.path.exists(tab_file_path):
        with open(tab_file_path, 'r', encoding='utf-8') as file:
            arg_parser = ArgParse(["microcontrol"] + file.read().split(" "))
            return tab_name_from_arguments(arg_parser)
