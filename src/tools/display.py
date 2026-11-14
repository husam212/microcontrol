#!/usr/bin/env python3

import subprocess
from utils.logger import LogLevel, Logger

def get_brightness(logging: Logger) -> int:
    """Get the current brightness level

    Returns:
        int: current brightness percentage
    """
    try:
        output = subprocess.getoutput("brightnessctl g")
        max_brightness = int(subprocess.getoutput("brightnessctl m"))
        current_brightness = int(output)
        return int((current_brightness / max_brightness) * 100)
    except Exception as e:
        logging.log(LogLevel.Error, f"Failed getting brightness: {e}")
        return 0


def set_brightness(value: int, logging: Logger) -> None:
    """Set the brightness level

    Args:
        value (int): brightness percentage to set
    """
    try:
        subprocess.run(["brightnessctl", "s", f"{value}%"], check=True, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        logging.log(LogLevel.Error, f"Failed setting brightness: {e}")
