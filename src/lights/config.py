import json
from pathlib import Path

DEFAULTS = {
    "bulbs": {"plafonnier": "192.168.1.29", "bureau": "192.168.1.33"},
    "send_hz": 10,
    "capture_hz": 30,
    "tau": 0.1,
    "min_change": 2,  # écart RGB max (0-255) sous lequel on n'envoie pas
    "monitor": "primary",  # "primary" ou "all"
    "crop_black_bars": True,
    "restore_on_exit": True,
    "pause_hotkey": "ctrl+alt+l",  # "" pour désactiver
    "pause_mode": "restore",  # "restore" : remet l'état d'origine ; "freeze" : garde la dernière couleur
    "neutral_low": 0.06,  # colorfulness sous laquelle l image est neutre (blanc chaud)
    "neutral_high": 0.14,  # colorfulness à partir de laquelle la couleur est pleine
    "neutral_rgb": [255, 255, 255],  # couleur des images neutres (ex. [255,169,87] pour un blanc chaud)
    "dimming_min_by_mode": {"night": 10, "day": 25},
    "dimming_max": 100,
    "dimming_max_white": 60,  # plafond spécifique aux LED blanches (plus lumineuses)
    "brightness_mode": "night",  # "night" ou "day"
    "brightness_scales": {"night": 0.8, "day": 1.0},
    "dynamic_brightness": True,  # False : luminosité fixe (fixed_brightness)
    "fixed_brightness": 80,  # % (10-100), utilisé si dynamic_brightness est False
    "brightness_gamma": 1.5,  # >1 : les scènes sombres restent plus sombres
    "brightness_gain": 2.0,  # multiplie la luminosité moyenne de l image
}


def load(path="config.json"):
    cfg = dict(DEFAULTS)
    p = Path(path)
    if p.exists():
        cfg.update(json.loads(p.read_text(encoding="utf-8")))
    return cfg


def validate(cfg):
    """Lève une exception si la config est inutilisable (utilisé au rechargement à chaud)."""
    mode = cfg["brightness_mode"]
    cfg["brightness_scales"][mode], cfg["dimming_min_by_mode"][mode]
    float(cfg["tau"]), float(cfg["send_hz"]), float(cfg["capture_hz"])
    if len(cfg["neutral_rgb"]) != 3:
        raise ValueError("neutral_rgb doit avoir 3 valeurs")
