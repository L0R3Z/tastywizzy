# TastyWizzy

Ambilight-style sync between a Windows PC screen and WiZ smart bulbs.

## Purpose

Make the room lighting follow what is on screen by setting the colour and brightness of WiZ bulbs from the average colour of the display, in real time.

## What it does today

A command-line script (V1) that:

- **Captures the screen** (primary monitor or all monitors) with `mss`, and optionally ignores black bars around the image.
- **Computes a dominant colour** (circular hue mean, saturation-weighted) and a brightness level, with time-based smoothing.
- **Handles neutral scenes** (black, grey, white) by blending to a configurable neutral colour instead of showing a stray tint.
- **Drives several WiZ bulbs** over UDP (port 38899), fire-and-forget, at a configurable rate (default 10 Hz). Bulbs are addressed by fixed IP (DHCP-reserved on the router, see `config.json`); if one stops answering, it is found again by MAC address on the local network and `config.json` is updated automatically.
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
python -m unittest discover tests   # unit tests
```

On first run, `config.json` is created from `config.example.json`: set your bulbs' IP addresses in it. `lancer.bat` launches the app in a console (`main.py --console`) (uses `.venv` if present, otherwise the `py` launcher).

**Background mode** — `lancer_fond.bat` (or `TastyWizzy.exe`) runs without a console, with an icon in the notification area: pause/resume, open the log, open the config, *Start with Windows* (checkbox), quit. The log is in `%LOCALAPPDATA%\TastyWizzy\lights.log`. Only one instance can run at a time.

**Auto-pause** — locking the session (Win+L) or putting the PC to sleep pauses the sync and restores the bulbs' original state; unlocking resumes it (`auto_pause_session`, on by default). A manual pause stays active after unlocking.

**Executable** — `build.bat` produces `dist\TastyWizzy.exe` (PyInstaller, single file). Put it in any folder: `config.json` is created next to it on first launch.

## Roadmap

Planned changes:

- **Tray app and settings UI** (`pystray`, packaged with PyInstaller), with every setting as a toggle or slider.
- **Auto-pause** on lock, sleep or inactivity.
- **Profiles** (Film / Game / Work).
- **Per-bulb screen zones** (optional): each bulb follows its own part of the screen.
- **Warm-white fallback** for low-saturation scenes (optional).
- **`dxcam` capture**, for exclusive-fullscreen games.
- **Audio-reactive mode** (WASAPI loopback), once the hue sync is complete.
