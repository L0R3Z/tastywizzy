import json
import os
import re
from pathlib import Path

DEFAULTS = {
    "bulbs": {"plafonnier": "192.168.1.101", "bureau": "192.168.1.102"},
    "bulb_retry_s": 30,  # délai entre deux recherches d une ampoule injoignable
    "send_hz": 10,
    "capture_hz": 30,
    "tau": 0.1,
    "min_change": 2,  # écart RGB max (0-255) sous lequel on n'envoie pas
    "monitor": "primary",  # "primary" ou "all"
    "crop_black_bars": True,
    "restore_on_exit": True,
    "pause_hotkey": "ctrl+alt+l",  # "" pour désactiver
    "auto_pause_session": True,  # pause (état d'origine) quand la session est verrouillée ou le PC en veille
    "pause_mode": "restore",  # "restore" : remet l'état d'origine ; "freeze" : garde la dernière couleur
    "neutral_low": 0.06,  # colorfulness sous laquelle l image est neutre (blanc chaud)
    "neutral_high": 0.14,  # colorfulness à partir de laquelle la couleur est pleine
    "neutral_rgb": [255, 255, 255],  # couleur des images neutres (ex. [255,169,87] pour un blanc chaud)
    "use_white_led": False,  # True : images neutres via la LED blanche chaude ; False : tout en RGB
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
        try:
            cfg.update(json.loads(p.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            raise ValueError(f"{p.name} n'est pas du JSON valide (ligne {e.lineno}) : {e.msg}") from e
    return cfg


def _check(cond, msg):
    if not cond:
        raise ValueError(msg)


def validate(cfg):
    """Lève ValueError si la config est inutilisable (au lancement et au rechargement à chaud)."""
    mode = cfg["brightness_mode"]
    _check(mode in cfg["brightness_scales"] and mode in cfg["dimming_min_by_mode"],
           f"brightness_mode '{mode}' absent de brightness_scales ou dimming_min_by_mode")
    _check(cfg["pause_mode"] in ("restore", "freeze"), "pause_mode doit valoir restore ou freeze")
    _check(isinstance(cfg["auto_pause_session"], bool), "auto_pause_session doit valoir true ou false")
    _check(cfg["monitor"] in ("primary", "all"), "monitor doit valoir primary ou all")
    for key in ("send_hz", "capture_hz", "bulb_retry_s"):
        _check(float(cfg[key]) > 0, f"{key} doit être > 0")
    _check(float(cfg["tau"]) >= 0, "tau doit être >= 0")
    _check(float(cfg["neutral_high"]) > float(cfg["neutral_low"]), "neutral_high doit être > neutral_low")
    _check(len(cfg["neutral_rgb"]) == 3 and all(0 <= int(x) <= 255 for x in cfg["neutral_rgb"]),
           "neutral_rgb doit avoir 3 valeurs entre 0 et 255")
    _check(isinstance(cfg["bulbs"], dict), "bulbs doit être un dictionnaire nom -> IP")


def save_bulbs(path, bulbs):
    """Réécrit uniquement la clé "bulbs" de config.json (IP/MAC apprises automatiquement)."""
    p = Path(path)
    text = p.read_text(encoding="utf-8") if p.exists() else "{}"
    data = json.loads(text)
    new = None
    m = re.search(r'"bulbs"\s*:\s*', text)
    if m:  # remplace exactement la valeur de "bulbs" pour garder la mise en forme du reste
        try:
            _, end = json.JSONDecoder().raw_decode(text, m.end())
            new = text[:m.end()] + json.dumps(bulbs, ensure_ascii=False) + text[end:]
            if {**data, "bulbs": bulbs} != json.loads(new):
                new = None
        except ValueError:
            new = None
    if new is None:  # format inattendu : réécriture complète
        data["bulbs"] = bulbs
        new = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(new, encoding="utf-8")
    os.replace(tmp, p)  # atomique : le rechargement à chaud ne lit jamais un fichier à moitié écrit
    return p.stat().st_mtime
