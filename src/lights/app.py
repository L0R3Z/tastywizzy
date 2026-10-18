import time
from pathlib import Path

from mss.exception import ScreenShotError

from . import color, config, shutdown
from .capture import MssCapture
from .hotkey import PauseHotkey
from .smoothing import Smoother
from .wiz import Wiz

DIMMING_MIN, DIMMING_MAX = 10, 100  # plage acceptée par les ampoules WiZ
CAPTURE_RETRY_S = 1.0  # attente quand l'écran n'est pas capturable (session verrouillée, UAC)
RESTART_KEYS = ("monitor", "pause_hotkey")  # non rechargeables à chaud


def compute_state(cfg, h, s, k, v):
    """Couleur lissée de l'écran -> (rgb, dimming, white) à envoyer aux ampoules."""
    kk = color.neutral_factor(k, cfg["neutral_low"], cfg["neutral_high"])
    if cfg["use_white_led"]:
        # image neutre -> LED blanche chaude, image colorée -> LED RGB, mélange continu
        rgb = tuple(round(x * kk) for x in color.hs_to_rgb(h, s))
        white = round(255 * (1 - kk))
    else:
        # couleur pleine si l'image est colorée, sinon RGB neutre (config), en continu
        rgb = tuple(round(x + (y - x) * kk) for x, y in zip(cfg["neutral_rgb"], color.hs_to_rgb(h, s)))
        white = 0
    lo = cfg["dimming_min_by_mode"][cfg["brightness_mode"]]
    if cfg["dynamic_brightness"]:
        cap_max = cfg["dimming_max"]
        if cfg["use_white_led"]:  # plafond propre aux LED blanches, plus lumineuses
            cap_max = cfg["dimming_max_white"] + (cap_max - cfg["dimming_max_white"]) * kk
        level = min(1.0, v * cfg["brightness_gain"]) ** cfg["brightness_gamma"]
        scale = cfg["brightness_scales"][cfg["brightness_mode"]]
        dimming = max(lo, round(scale * (lo + (cap_max - lo) * level)))
    else:
        dimming = round(cfg["fixed_brightness"])
    return rgb, min(DIMMING_MAX, max(DIMMING_MIN, dimming)), white


class ConfigWatcher:
    """Détecte les modifications de config.json (vérification au plus une fois par seconde)."""

    def __init__(self, path):
        self.path = Path(path) if path else None
        self.mtime = self._stat()
        self.next_check = 0.0

    def _stat(self):
        return self.path.stat().st_mtime if self.path and self.path.exists() else None

    def poll(self, now):
        """Renvoie la nouvelle config si le fichier a changé, None sinon. Lève si elle est invalide."""
        if self.mtime is None or now < self.next_check:
            return None
        self.next_check = now + 1.0
        m = self._stat()
        if m is None or m == self.mtime:
            return None
        self.mtime = m
        new = config.load(self.path)
        config.validate(new)
        return new


def run(cfg, duration=None, config_path=None):
    save = (lambda b: config.save_bulbs(config_path, b)) if config_path else None
    shutdown.install()
    cap = wiz = None
    try:
        config.validate(cfg)
        wiz = Wiz(cfg["bulbs"], save, cfg["bulb_retry_s"], shutdown.stop)
        cap = MssCapture(cfg["monitor"])
        wiz.connect()
        print("État sauvegardé :", {b.name: bool(b.saved) for b in wiz.bulbs})
        _loop(cfg, wiz, cap, duration, config_path)
    finally:
        if cap:
            cap.close()
        if wiz and cfg["restore_on_exit"]:
            wiz.restore_state()
            time.sleep(0.2)
            wiz.restore_state()  # UDP sans accusé : on double l'envoi par sécurité
            print("État des ampoules restauré.")
        shutdown.done.set()


def _loop(cfg, wiz, cap, duration, config_path):
    smoother = Smoother(cfg["tau"])
    watcher = ConfigWatcher(config_path)
    last_sent, last_send_t, prev_t = None, 0.0, time.monotonic()
    t_end = prev_t + duration if duration is not None else None
    capture_lost = False
    hk = PauseHotkey(cfg["pause_hotkey"]) if cfg["pause_hotkey"] else None
    if hk and hk.error:
        print("Attention :", hk.error)
        hk = None
    elif hk:
        print(f"Pause : {cfg['pause_hotkey']} (mode {cfg['pause_mode']})")
    while not shutdown.stop.is_set():
        if hk and hk.paused.is_set():
            if hk.toggled.is_set():
                hk.toggled.clear()
                if cfg["pause_mode"] == "restore":
                    wiz.restore_state()
                print("Pause.")
            shutdown.stop.wait(0.1)
            prev_t = time.monotonic()
            continue
        if hk and hk.toggled.is_set():  # reprise
            hk.toggled.clear()
            smoother, last_sent = Smoother(cfg["tau"]), None
            print("Reprise.")
        try:
            new = watcher.poll(time.monotonic())
            if new:
                restart = [k for k in RESTART_KEYS if new[k] != cfg[k]]
                cfg.update(new)
                wiz.reconfigure(cfg["bulbs"], cfg["bulb_retry_s"])
                smoother.tau = cfg["tau"]
                last_sent = None
                print("Config rechargée.")
                if restart:
                    print(f"Redémarre l'appli pour appliquer : {', '.join(restart)}")
        except Exception as e:  # ancienne config conservée
            print("Config invalide, ancienne conservée :", e)
        try:
            img = cap.grab()
        except ScreenShotError:
            if not capture_lost:
                print("Écran non capturable (session verrouillée ?), en attente.")
                capture_lost = True
            shutdown.stop.wait(CAPTURE_RETRY_S)
            prev_t = time.monotonic()
            continue
        if capture_lost:
            print("Capture reprise.")
            capture_lost = False
        if cfg["crop_black_bars"]:
            img = color.crop_black_bars(img)
        h, s, c, v = color.analyze(img)
        now = time.monotonic()
        h, s, k, v = smoother.update(h, s, c, v, now - prev_t)
        rgb, dimming, white = compute_state(cfg, h, s, k, v)
        state = (*rgb, dimming, white)
        due = now - last_send_t >= 1 / cfg["send_hz"]
        changed = last_sent is None or max(abs(x - y) for x, y in zip(state, last_sent)) >= cfg["min_change"]
        if due and changed:
            wiz.set_color(rgb, dimming, white)
            last_sent, last_send_t = state, now
        prev_t = now
        if t_end is not None and now >= t_end:
            break
        shutdown.stop.wait(1 / cfg["capture_hz"])
