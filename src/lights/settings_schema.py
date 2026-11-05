"""Description of the settings window: what is shown, in which order. No UI code here.

Sections are ordered by how often a setting is useful; rarely touched ones live in ADVANCED.
"""
import copy
from dataclasses import dataclass


@dataclass(frozen=True)
class Field:
    path: tuple  # key in config.json, then nested key if any
    label: str
    help: str = ""
    kind: str = "slider"  # slider, switch, choice, color, hotkey
    lo: float = 0
    hi: float = 100
    step: float = 1
    unit: str = ""
    options: tuple = ()  # choice: (value, label) pairs
    visible: object = None  # visible(cfg) -> bool; None = always shown


def _dynamic(cfg):
    return cfg["dynamic_brightness"]


def _mode_is(mode):
    return lambda cfg: cfg["dynamic_brightness"] and cfg["brightness_mode"] == mode


SECTIONS = (
    ("Brightness", (
        Field(("brightness_mode",), "Mode", "Night is dimmer, day is brighter.", "choice",
              options=(("night", "Night"), ("day", "Day")), visible=_dynamic),
        Field(("dynamic_brightness",), "Follow the screen", "Off: the bulbs keep a fixed brightness.", "switch"),
        Field(("dimming_max",), "Maximum brightness", "The brightest the bulbs can get.",
              lo=10, unit="%", visible=_dynamic),
        Field(("dimming_min_by_mode", "night"), "Minimum brightness", "Level reached on a black screen.",
              lo=10, unit="%", visible=_mode_is("night")),
        Field(("dimming_min_by_mode", "day"), "Minimum brightness", "Level reached on a black screen.",
              lo=10, unit="%", visible=_mode_is("day")),
        Field(("fixed_brightness",), "Brightness", "Used while the bulbs don't follow the screen.",
              lo=10, unit="%", visible=lambda cfg: not cfg["dynamic_brightness"]),
    )),
    ("Colour", (
        Field(("neutral_rgb",), "Neutral colour", "Used on black, grey and white scenes.", "color"),
        Field(("color_gamma",), "Colour correction", "Higher gives more saturated colours; 1 means no correction.",
              lo=1, hi=3, step=0.1),
        Field(("use_white_led",), "Use the white LED", "Adds the warm white LED on neutral scenes.", "switch"),
        Field(("dimming_max_white",), "White LED intensity", "Very bright: keep it low in a dark room.",
              unit="%", visible=lambda cfg: cfg["use_white_led"]),
    )),
    ("Responsiveness", (
        Field(("tau",), "Smoothing", "Low is reactive but jittery, high is soft but delayed.",
              hi=1, step=0.01, unit=" s"),
        Field(("send_hz",), "Updates per second", "Higher is smoother, but slow bulbs may lag behind.",
              lo=2, hi=20, unit=" Hz"),
    )),
    ("Screen", (
        Field(("monitor",), "Captured screen", "", "choice", options=(("primary", "Main"), ("all", "All"))),
        Field(("crop_black_bars",), "Ignore black bars", "Keeps movie bars from darkening the colour.", "switch"),
    )),
    ("Pause and exit", (
        Field(("pause_hotkey",), "Pause shortcut", "For example ctrl+alt+l. Leave empty to disable.", "hotkey"),
        Field(("pause_mode",), "During a pause", "", "choice",
              options=(("restore", "Restore bulbs"), ("freeze", "Keep colour"))),
        Field(("auto_pause_session",), "Pause on lock and sleep", "Resumes when you unlock the PC.", "switch"),
        Field(("restore_on_exit",), "Restore bulbs on exit", "Otherwise they keep the last colour.", "switch"),
    )),
)

ADVANCED = (
    ("Brightness response", (
        Field(("brightness_gain",), "Gain", "Amplifies the brightness measured on screen.",
              lo=1, hi=4, step=0.1, visible=_dynamic),
        Field(("brightness_gamma",), "Curve", "Above 1, dark scenes stay dark.",
              lo=0.5, hi=3, step=0.1, visible=_dynamic),
        Field(("brightness_scales", "night"), "Night scale", "Multiplies all brightness in night mode.",
              lo=0.1, hi=1, step=0.05, visible=_dynamic),
        Field(("brightness_scales", "day"), "Day scale", "Multiplies all brightness in day mode.",
              lo=0.1, hi=1, step=0.05, visible=_dynamic),
    )),
    ("Neutral scene detection", (
        Field(("neutral_low",), "Neutral below", "Below this colour level, the neutral colour is used.",
              hi=0.3, step=0.01),
        Field(("neutral_high",), "Full colour above", "Above this level, the screen's hue is used fully.",
              lo=0.05, hi=0.5, step=0.01),
    )),
    ("Performance", (
        Field(("capture_hz",), "Captures per second", "Higher reacts faster but uses more CPU.",
              lo=10, hi=60, unit=" Hz"),
        Field(("min_change",), "Change threshold", "Ignores variations smaller than this.", hi=10),
        Field(("bulb_retry_s",), "Bulb search delay", "How often an unreachable bulb is searched for.",
              lo=5, hi=120, step=5, unit=" s"),
    )),
)

COLOR_PRESETS = (("Warm", [255, 169, 87]), ("Soft", [255, 200, 130]), ("White", [255, 255, 255]))


def get_value(cfg, path):
    value = cfg
    for key in path:
        value = value[key]
    return value


def with_value(cfg, path, value):
    """Returns a copy of cfg with this setting changed."""
    new = copy.deepcopy(cfg)
    target = new
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return new


def snap(value, field):
    """Rounds a slider position to the field's step (an int when the step is whole)."""
    steps = round((value - field.lo) / field.step)
    result = min(field.hi, field.lo + steps * field.step)
    return round(result) if float(field.step).is_integer() and float(field.lo).is_integer() else round(result, 2)


def format_value(value, field):
    text = str(value) if isinstance(value, int) else f"{value:.2f}".rstrip("0").rstrip(".")
    return text + field.unit
