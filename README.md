# TastyWizzy

Ambilight-style sync between a Windows PC screen and WiZ smart bulbs.

## Purpose

Make the room lighting follow what is on screen by setting the colour and brightness of WiZ bulbs from the average colour of the display, in real time.

## What it does today

A command-line script (V1) that:

- **Captures the screen** (primary monitor or all monitors) with `mss`, and optionally ignores black bars around the image.
- **Computes a dominant colour** (circular hue mean, saturation-weighted) and a brightness level, with time-based smoothing.
- **Handles neutral scenes** (black, grey, white) by blending to a configurable neutral colour instead of showing a stray tint.
- **Drives several WiZ bulbs** over UDP (port 38899), fire-and-forget, at a configurable rate (default 10 Hz). Bulbs are addressed by fixed IP (see `config.json`).
- **Adapts brightness to the screen**, with day/night modes, min/max limits, gain and gamma. It can also use a fixed brightness.
- **Saves and restores bulb state**: the original state is read at start and restored on exit (and on pause).
- **Global pause hotkey** (default `Ctrl+Alt+L`): restore the original state or freeze the current colour.
- **Hot-reloads `config.json`** while running.

All settings are documented in [PARAMETRES.md](PARAMETRES.md).

## Usage

Requires Python 3.12+ on Windows.

```
pip install -r requirements.txt
python main.py          # runs until Ctrl+C
python main.py 60       # runs for 60 seconds
```

On first run, `config.json` is created from `config.example.json`: set your bulbs' IP addresses in it. `lancer.bat` is a shortcut to launch the app.

## Roadmap

Planned changes:

- **Tray app and settings UI** (`pystray`, packaged with PyInstaller), with every setting as a toggle or slider.
- **Auto-pause** on lock, sleep or inactivity.
- **Profiles** (Film / Game / Work).
- **Per-bulb screen zones** (optional): each bulb follows its own part of the screen.
- **Warm-white fallback** for low-saturation scenes (optional).
- **`dxcam` capture**, for exclusive-fullscreen games.
- **Audio-reactive mode** (WASAPI loopback), once the hue sync is complete.
- **DHCP reservation** for the bulbs, so their IPs stay stable.
