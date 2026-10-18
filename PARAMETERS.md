# config.json parameters

Reference for every setting. This file is the source for the UI tooltips (V2). A French version is available in [PARAMETRES.md](PARAMETRES.md).

**Entry format** (designed to be parsed by a script):
- the `### key` heading is the exact key in `config.json`;
- **Label**: short name shown in the UI;
- **Tooltip**: short text (one or two sentences) shown on hover;
- **Type / Default / Range**: kind of control to provide in the UI;
- **Applied**: "live" (applied as soon as saved) or "on restart";
- **Details**: long explanation, for a "learn more" link.

Defaults listed are those in the code (`src/lights/config.py`). The current `config.json` may differ.

---

## Bulbs and capture

### bulbs
- **Label**: Bulbs
- **Tooltip**: Names and IP addresses of the WiZ bulbs to control. All of them receive the same color.
- **Type**: dictionary name → IP address, or name → `{"ip": ..., "mac": ...}`
- **Default**: `{"plafonnier": "192.168.1.101", "bureau": "192.168.1.102"}`
- **Applied**: on restart
- **Details**: the IPs are reserved on the SFR Box (DHCP reservation: ceiling light .101, desk lamp .102). At startup, the app reads each bulb's MAC address and saves it here automatically; if a bulb no longer answers at its IP, it is searched for by MAC on the local network and `config.json` is corrected on its own. A bulb that cannot be found is skipped and searched for again every `bulb_retry_s` seconds.

### bulb_retry_s
- **Label**: Retry delay
- **Tooltip**: How often, in seconds, the app searches for an unreachable bulb.
- **Type**: number (seconds)
- **Default**: `30`
- **Applied**: on restart
- **Details**: the search runs in the background, without slowing down sync for the other bulbs.

### monitor
- **Label**: Captured screen
- **Tooltip**: "primary" captures the main screen, "all" captures all screens together.
- **Type**: choice (`primary` or `all`)
- **Default**: `primary`
- **Applied**: on restart
- **Details**: with `all`, the screens are merged into a single image (virtual desktop), and the color is the average of all of them.

### crop_black_bars
- **Label**: Ignore black bars
- **Tooltip**: Detects and ignores black bars around the image (21:9 movies, etc.) so they don't darken the average.
- **Type**: boolean
- **Default**: `true`
- **Applied**: live
- **Details**: detection is automatic, on the image edges. If the whole screen is black, the image is kept as is. The taskbar is not handled separately (it is hidden on this machine).

### capture_hz
- **Label**: Capture rate
- **Tooltip**: Number of screen captures per second. Higher means snappier reactions, but more CPU work.
- **Type**: number (Hz)
- **Default**: `30`
- **Recommended range**: 10 to 60
- **Applied**: live
- **Details**: independent of `send_hz`. There is no point in capturing much faster than sending.

---

## Sending to bulbs and smoothing

### send_hz
- **Label**: Sends per second
- **Tooltip**: Maximum number of commands sent to the bulbs per second. Higher is smoother, but slow bulbs may lag behind.
- **Type**: number (Hz)
- **Default**: `10`
- **Recommended range**: 2 to 10 (2 is choppy, 5 is smooth, 10 is smoother still)
- **Applied**: live
- **Details**: sending uses UDP, without waiting for a reply. The desk lamp responds slowly (up to 1 s) and may lag behind the ceiling light.

### tau
- **Label**: Smoothing (τ)
- **Tooltip**: Duration of color change smoothing, in seconds. Small = responsive but jittery, large = soft but delayed.
- **Type**: number (seconds)
- **Default**: `0.1`
- **Recommended range**: 0 to 1 (0 disables smoothing)
- **Applied**: live
- **Details**: adds to the bulbs' internal fade (about 0.5 to 1 s). The smoothed hue always takes the shortest path around the color wheel.

### min_change
- **Label**: Change threshold
- **Tooltip**: Minimum color or brightness difference before sending a new command. Avoids flooding the bulbs with invisible variations.
- **Type**: integer (0 to 255 scale for colors, 0 to 100 for brightness)
- **Default**: `2`
- **Recommended range**: 0 to 10
- **Applied**: live
- **Details**: the comparison uses the largest difference among red, green, blue and brightness. A threshold that is too high produces visible steps.

---

## Neutral colors (black, gray, white)

### neutral_low
- **Label**: "Neutral image" threshold
- **Tooltip**: Below this color level in the image, the bulbs use the neutral color instead of the average hue.
- **Type**: number
- **Default**: `0.06`
- **Recommended range**: 0 to 0.3 (must stay below `neutral_high`)
- **Applied**: live
- **Details**: the color level is the average of saturation × brightness over the pixels. The higher the value, the more dark or desaturated images are treated as neutral, which avoids stray color casts (for example a blue or pink tint on a gray scene).

### neutral_high
- **Label**: "Full color" threshold
- **Tooltip**: From this color level upward, the bulbs fully take on the screen's average hue.
- **Type**: number
- **Default**: `0.14`
- **Recommended range**: 0.05 to 0.5 (must stay above `neutral_low`)
- **Applied**: live
- **Details**: between `neutral_low` and `neutral_high`, the neutral color and the average hue are blended progressively.

### neutral_rgb
- **Label**: Neutral color
- **Tooltip**: Color used when the image is black, gray or white. Pick a warm white or a pure white.
- **Type**: color (3 values red, green, blue from 0 to 255)
- **Default**: `[255, 255, 255]`
- **Applied**: live
- **Details**: a pure white may look bluish or pinkish depending on the bulb. A warm white (for example `[255, 200, 130]`) is often more pleasant. The bulbs produce this white with their color LEDs, hence possible hue differences.

### use_white_led
- **Label**: Use the white LED
- **Tooltip**: On: neutral images are rendered by the bulb's warm white LED. Off: everything is done with the RGB LEDs.
- **Type**: boolean
- **Default**: `false`
- **Applied**: live
- **Details**: when on, the warm white LED (`w` channel) replaces the neutral color, and `neutral_rgb` is no longer used. Between neutral and colorful images, the RGB LEDs and the white LED are blended progressively. Requires a WiZ RGBW bulb (color + white).

---

## Brightness

### dynamic_brightness
- **Label**: Dynamic brightness
- **Tooltip**: On: brightness follows the screen. Off: fixed brightness (see "Fixed brightness").
- **Type**: boolean
- **Default**: `true`
- **Applied**: live
- **Details**: when off, only color and hue follow the screen. The day/night mode, gamma, gain and cap settings no longer apply.

### fixed_brightness
- **Label**: Fixed brightness
- **Tooltip**: Brightness used when dynamic brightness is off, as a percentage.
- **Type**: slider (%)
- **Default**: `80`
- **Range**: 10 to 100 (10 is the WiZ bulbs' minimum)
- **Applied**: live
- **Details**: has no effect while `dynamic_brightness` is on.

### brightness_mode
- **Label**: Day / night mode
- **Tooltip**: "night" is dimmer, "day" is brighter. Switches between two brightness profiles.
- **Type**: choice (`night` or `day`)
- **Default**: `night`
- **Applied**: live
- **Details**: the mode selects both the minimum (`dimming_min_by_mode`) and the global scale (`brightness_scales`). A mode key missing from either of these settings makes the configuration invalid.

### brightness_scales
- **Label**: Global scale per mode
- **Tooltip**: Multiplies all dynamic brightness. 0.8 reduces by 20%, 1 leaves it unchanged.
- **Type**: dictionary mode → number
- **Default**: `{"night": 0.8, "day": 1.0}`
- **Recommended range**: 0.1 to 1 per mode
- **Applied**: live
- **Details**: applied before the minimum, which is always respected. No effect if dynamic brightness is off.

### dimming_min_by_mode
- **Label**: Minimum brightness per mode
- **Tooltip**: Floor brightness of the bulbs, per mode, as a percentage. This is the level reached on an all-black screen.
- **Type**: dictionary mode → percentage
- **Default**: `{"night": 10, "day": 25}`
- **Range**: 10 to 100 per mode (10 is the WiZ bulbs' hardware minimum)
- **Applied**: live
- **Details**: a higher minimum in day mode keeps the room lit even on a black scene. No effect if dynamic brightness is off.

### dimming_max
- **Label**: Maximum brightness (colors)
- **Tooltip**: Brightness cap for colorful scenes, as a percentage.
- **Type**: slider (%)
- **Default**: `100`
- **Range**: 10 to 100
- **Applied**: live
- **Details**: general cap. With `use_white_led`, it applies to colorful images and the cap moves progressively from `dimming_max_white` (neutral image) to `dimming_max` (colorful image). Without `use_white_led`, it applies to all images.

### dimming_max_white
- **Label**: Maximum brightness (whites)
- **Tooltip**: Brightness cap for white or gray scenes, as a percentage. Whites are more dazzling than colors.
- **Type**: slider (%)
- **Default**: `60`
- **Range**: 10 to 100
- **Applied**: live
- **Details**: at the same percentage, white looks much brighter than a color, because it lights all the LEDs. Lowering this cap softens bright scenes and white menus. Raising it gives more range on neutral screens. Only used if `use_white_led` is on.

### brightness_gain
- **Label**: Brightness gain
- **Tooltip**: Amplifies the brightness measured on screen. Higher means the bulbs ramp up faster, even on fairly dark scenes.
- **Type**: number
- **Default**: `2.0`
- **Recommended range**: 1 to 4
- **Applied**: live
- **Details**: the average brightness of a typical scene is low (often around 0.3), hence a gain above 1. A gain that is too high quickly saturates at the cap. No effect if dynamic brightness is off.

### brightness_gamma
- **Label**: Brightness curve
- **Tooltip**: Above 1, dark scenes stay dark. Below 1, they brighten faster.
- **Type**: number
- **Default**: `1.5`
- **Recommended range**: 0.5 to 3
- **Applied**: live
- **Details**: 1 gives a linear response. Useful to prevent a small bright area on a dark background (for example text on a gray bar) from pushing the bulbs up sharply. No effect if dynamic brightness is off.

---

## Pause and exit

### pause_hotkey
- **Label**: Pause hotkey
- **Tooltip**: Global keyboard shortcut that pauses and resumes sync, even from inside a game.
- **Type**: keyboard shortcut (string)
- **Default**: `ctrl+alt+l`
- **Applied**: on restart
- **Details**: available modifiers: `ctrl`, `alt`, `shift`, `win`, followed by a letter, a digit or a key `f1` to `f24` (example: `ctrl+shift+f9`). An empty string disables the hotkey. If the combination is already used by another program, a warning is shown at startup and hotkey pause is unavailable.

### pause_mode
- **Label**: Pause behavior
- **Tooltip**: "restore" returns the bulbs to their original state during the pause. "freeze" keeps the last color.
- **Type**: choice (`restore` or `freeze`)
- **Default**: `restore`
- **Applied**: live
- **Details**: with `restore`, the restored state is the one saved when the program started. On resume, sync starts fresh, with no inherited smoothing.

### auto_pause_session
- **Label**: Pause on lock and sleep
- **Tooltip**: Pauses sync and returns the bulbs to their original state when the session is locked (Win+L) or the PC goes to sleep. Resumes automatically on unlock.
- **Type**: boolean
- **Default**: `true`
- **Applied**: live
- **Details**: the original state is always restored, regardless of `pause_mode`. A manual pause (hotkey or tray icon) stays active after unlocking. When going to sleep, the restore is sent immediately, before the network shuts down.

### restore_on_exit
- **Label**: Restore on exit
- **Tooltip**: When the program closes (window closed, Ctrl+C, Windows shutdown), returns the bulbs to their original state.
- **Type**: boolean
- **Default**: `true`
- **Applied**: live
- **Details**: the original state (scene, temperature, brightness, on/off) is read with `getPilot` at startup. If a bulb does not respond at that moment, it is not restored. The command is sent twice for safety, since UDP sending has no acknowledgment. When off, the bulbs keep their last color.
