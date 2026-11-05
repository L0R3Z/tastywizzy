import logging
import time
from dataclasses import dataclass
from pathlib import Path

from mss.exception import ScreenShotError

from . import audio, color, config, shutdown
from .audio import AudioListener
from .capture import MssCapture
from .hotkey import PauseHotkey
from .pause import SESSION, PauseState
from .session import SessionWatcher
from .smoothing import Smoother
from .wiz import Wiz

DIMMING_MIN, DIMMING_MAX = 10, 100  # plage acceptée par les ampoules WiZ
CAPTURE_RETRY_S = 1.0  # attente quand l'écran n'est pas capturable (session verrouillée, UAC)

log = logging.getLogger(__name__)


def compute_state(cfg, h, s, k, v):
    """Couleur lissée de l'écran -> (rgb, dimming, white) à envoyer aux ampoules."""
    kk = color.neutral_factor(k, cfg["neutral_low"], cfg["neutral_high"])
    hue_rgb = color.hs_to_rgb(h, s, cfg["color_gamma"])
    # couleur pleine si l'image est colorée, sinon RGB neutre (config), en continu
    rgb = tuple(round(x + (y - x) * kk) for x, y in zip(cfg["neutral_rgb"], hue_rgb))
    # LED blanche : simple appoint sur les images neutres, dosé par dimming_max_white (%).
    # Elle ne remplace plus le RGB : seule, elle reste éblouissante même au dimming minimum.
    white = round(255 * (1 - kk) * cfg["dimming_max_white"] / 100) if cfg["use_white_led"] else 0
    lo = cfg["dimming_min_by_mode"][cfg["brightness_mode"]]
    if cfg["dynamic_brightness"]:
        level = min(1.0, v * cfg["brightness_gain"]) ** cfg["brightness_gamma"]
        scale = cfg["brightness_scales"][cfg["brightness_mode"]]
        dimming = max(lo, scale * (lo + (cfg["dimming_max"] - lo) * level))
    else:
        dimming = cfg["fixed_brightness"]
    return rgb, min(DIMMING_MAX, max(DIMMING_MIN, round(dimming))), white


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
        forced = config.changed.is_set()  # enregistré par la fenêtre de réglages : effet immédiat
        if self.mtime is None or (now < self.next_check and not forced):
            return None
        config.changed.clear()
        self.next_check = now + 1.0
        m = self._stat()
        if m is None or (m == self.mtime and not forced):  # horloge de fichier trop grossière pour un save rapide
            return None
        self.mtime = m
        new = config.load(self.path)
        config.validate(new)
        return new


def _restore(wiz):
    wiz.restore_state()
    time.sleep(0.2)
    wiz.restore_state()  # UDP sans accusé : on double l'envoi par sécurité


@dataclass
class Runtime:
    """Dépendances de la boucle principale."""
    wiz: Wiz
    cap: MssCapture
    pause: PauseState
    session: SessionWatcher
    config_path: Path = None
    duration: float = None
    on_color: object = None  # on_color(rgb) ou None
    audio: AudioListener = None


def apply_pause(cfg, pause, wiz, restored):
    """En pause : restaure l'état d'origine une seule fois si besoin. Renvoie le nouveau `restored`.

    Verrouillage/veille : toujours l'état d'origine ; pause manuelle : selon pause_mode.
    """
    if not restored and (cfg["pause_mode"] == "restore" or pause.has(SESSION)):
        wiz.restore_state()
        return True
    return restored


def run(cfg, duration=None, config_path=None, pause=None, on_color=None):
    """Boucle principale. pause : PauseState partagé (tray) ; on_color(rgb) : appelé à chaque envoi."""
    pause = pause or PauseState()
    save = (lambda b: config.save_bulbs(config_path, b)) if config_path else None
    shutdown.install()
    cap = wiz = None
    listener = AudioListener()
    try:
        config.validate(cfg)
        wiz = Wiz(cfg["bulbs"], save, cfg["bulb_retry_s"], shutdown.stop)
        cap = MssCapture(cfg["monitor"])
        wiz.connect()
        log.info("État sauvegardé : %s", {b.name: bool(b.saved) for b in wiz.bulbs})
        session = SessionWatcher(pause, cfg["auto_pause_session"], on_suspend=lambda: _restore(wiz))
        listener.set_enabled(cfg["audio_mode"] != "off")
        _loop(cfg, Runtime(wiz, cap, pause, session, config_path, duration, on_color, listener))
    finally:
        listener.close()
        if cap:
            cap.close()
        if wiz and cfg["restore_on_exit"]:
            _restore(wiz)
            log.info("État des ampoules restauré.")
        shutdown.done.set()


def _start_hotkey(cfg, pause):
    hk = PauseHotkey(cfg["pause_hotkey"], pause.toggle_manual) if cfg["pause_hotkey"] else None
    if hk and hk.error:
        log.warning(hk.error)
        return None
    if hk:
        log.info("Pause : %s (mode %s)", cfg["pause_hotkey"], cfg["pause_mode"])
    return hk


def _loop(cfg, rt):
    wiz, cap, pause = rt.wiz, rt.cap, rt.pause
    smoother = Smoother(cfg["tau"])
    watcher = ConfigWatcher(rt.config_path)
    last_sent, last_send_t, prev_t = None, 0.0, time.monotonic()
    t_end = prev_t + rt.duration if rt.duration is not None else None
    capture_lost = restored = False
    hk = _start_hotkey(cfg, pause)
    while not shutdown.stop.is_set():
        try:  # aussi en pause : les réglages changés pendant une pause s'appliquent tout de suite
            new = watcher.poll(time.monotonic())
            if new:
                old_monitor, old_hotkey = cfg["monitor"], cfg["pause_hotkey"]
                cfg.update(new)
                wiz.reconfigure(cfg["bulbs"], cfg["bulb_retry_s"])
                smoother.tau = cfg["tau"]
                rt.session.auto_pause = cfg["auto_pause_session"]
                rt.audio.set_enabled(cfg["audio_mode"] != "off")
                if cfg["monitor"] != old_monitor:
                    cap.set_monitor(cfg["monitor"])
                if cfg["pause_hotkey"] != old_hotkey:
                    if hk:
                        hk.close()
                    hk = _start_hotkey(cfg, pause)
                last_sent = None
                log.info("Config rechargée.")
        except Exception as e:  # ancienne config conservée
            log.warning("Config invalide, ancienne conservée : %s", e)
        if pause.changed.is_set():
            pause.changed.clear()
            if pause.paused:
                log.info("Pause.")
            else:
                if restored:  # l'utilisateur a pu régler les ampoules pendant la pause : nouvel état d'origine
                    wiz.resave_states()
                smoother, last_sent, restored = Smoother(cfg["tau"]), None, False
                log.info("Reprise.")
        if pause.paused:
            restored = apply_pause(cfg, pause, wiz, restored)
            shutdown.stop.wait(0.1)
            prev_t = time.monotonic()
            continue
        try:
            img = cap.grab()
        except ScreenShotError:
            if not capture_lost:
                log.info("Écran non capturable (session verrouillée ?), en attente.")
                capture_lost = True
            shutdown.stop.wait(CAPTURE_RETRY_S)
            prev_t = time.monotonic()
            continue
        if capture_lost:
            log.info("Capture reprise.")
            capture_lost = False
        if cfg["crop_black_bars"]:
            img = color.crop_black_bars(img)
        h, s, c, v = color.analyze(img)
        now = time.monotonic()
        h, s, k, v = smoother.update(h, s, c, v, now - prev_t)
        rgb, dimming, white = compute_state(cfg, h, s, k, v)
        rgb, dimming, white = audio.apply_effect(cfg, rgb, dimming, white, rt.audio.state())
        state = (*rgb, dimming, white)
        due = now - last_send_t >= 1 / cfg["send_hz"]
        changed = last_sent is None or max(abs(x - y) for x, y in zip(state, last_sent)) >= cfg["min_change"]
        if due and changed:
            wiz.set_color(rgb, dimming, white)
            if rt.on_color:
                rt.on_color(rgb)
            last_sent, last_send_t = state, now
        prev_t = now
        if t_end is not None and now >= t_end:
            break
        shutdown.stop.wait(1 / cfg["capture_hz"])
