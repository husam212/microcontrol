# MicroControl

A small GTK control panel for Wayland window managers, Sway and Hyperland.

## Features

- **Audio**: choose the output and input device, set speaker and microphone volume, control each app's volume and output device, and switch device profiles.
- **Wi-Fi**: turn Wi-Fi on or off, scan for networks, connect or disconnect a network, forget saved networks, and share the current network as a QR code.
- **Bluetooth**: turn Bluetooth on or off, scan for devices, connect or disconnect a device, forget devices, and see their battery level.
- **Battery**: see the charge level and time remaining, and switch between power modes.
- **Display**: set brightness, blue light and scale, and arrange multiple displays (join, mirror or single display).

## Installation

On Arch Linux, install [microcontrol-git](https://aur.archlinux.org/packages/microcontrol-git) from the AUR with an AUR helper such as yay:

```bash
yay -S microcontrol-git
```

Or build it yourself without an AUR helper:

```bash
git clone https://aur.archlinux.org/microcontrol-git.git
cd microcontrol-git
makepkg -si
```

## Usage

Start the app from the command line:

```bash
microcontrol
```

To see all the options, such as opening a specific tab:

```bash
microcontrol --help
```

## Compatibility

Some features depend on system services running: NetworkManager for Wi-Fi, BlueZ for Bluetooth, and power-profiles-daemon for power modes. To enable them:

```bash
sudo systemctl enable --now NetworkManager bluetooth power-profiles-daemon
```

MicroControl depends on a background daemon for D-Bus events, it starts automatically on MicroControl first run. To have it running from login, so your display settings are applied right away, enable its SystemD service:

```bash
systemctl --user enable microcontrol.service
```

This works in sessions that start `graphical-session.target` (e.g. Hyprland with uwsm). On Sway, which usually doesn't, add this line to your Sway config instead:

```
exec systemctl --user start microcontrol.service
```

## License

MicroControl is a fork of [Better Control](https://github.com/better-ecosystem/better-control). It's a modified version of it and, like it, is licensed under the [GNU General Public License v3.0](LICENSE).
