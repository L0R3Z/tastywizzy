import time

from pathlib import Path

from . import color, config, shutdown
from .capture import MssCapture
from .hotkey import PauseHotkey
from .smoothing import Smoother
from .wiz import Wiz


def run(cfg, duration=None, config_path=None):
    wiz = Wiz(cfg["bulbs"])
    cap = MssCapture(cfg["monitor"])
    smoother = Smoother(cfg["tau"])
    shutdown.install()
    wiz.save_state()
    print("État sauvegardé :", {b.name: bool(b.saved) for b in wiz.bulbs})
    last_sent, last_send_t, prev_t = None, 0.0, time.monotonic()
    t_end = prev_t + duration if duration else None
    cfg_file = Path(config_path) if config_path else None
    cfg_mtime = cfg_file.stat().st_mtime if cfg_file and cfg_file.exists() else None
    next_check = 0.0
    hk = PauseHotkey(cfg["pause_hotkey"]) if cfg["pause_hotkey"] else None
    if hk and hk.error:
        print("Attention :", hk.error)
        hk = None
    elif hk:
        print(f"Pause : {cfg['pause_hotkey']} (mode {cfg['pause_mode']})")
    try:
        while not shutdown.stop.is_set():
            if hk and hk.paused.is_set():
                if hk.toggled.is_set():
                    hk.toggled.clear()
                    if cfg["pause_mode"] == "restore":
                        wiz.restore_state()
                    print("Pause.")
                time.sleep(0.1)
                prev_t = time.monotonic()
                continue
            if hk and hk.toggled.is_set():  # reprise
                hk.toggled.clear()
                smoother, last_sent = Smoother(cfg["tau"]), None
                print("Reprise.")
            if cfg_mtime is not None and time.monotonic() >= next_check:
                next_check = time.monotonic() + 1.0
                try:
                    m = cfg_file.stat().st_mtime
                    if m != cfg_mtime:
                        cfg_mtime = m
                        new = config.load(cfg_file)
                        config.validate(new)
                        cfg.update(new)
                        smoother.tau = cfg["tau"]
                        last_sent = None
                        print("Config rechargée.")
                except Exception as e:  # ancienne config conservée
                    print("Config invalide, ancienne conservée :", e)
            img = cap.grab()
            if cfg["crop_black_bars"]:
                img = color.crop_black_bars(img)
            h, s, c, v = color.analyze(img)
            now = time.monotonic()
            h, s, k, v = smoother.update(h, s, c, v, now - prev_t)
            # couleur pleine si l'image est colorée, sinon RGB neutre (config), en continu
            kk = color.neutral_factor(k, cfg["neutral_low"], cfg["neutral_high"])
            rgb = tuple(round(x + (y - x) * kk) for x, y in zip(cfg["neutral_rgb"], color.hs_to_rgb(h, s)))
            lo = cfg["dimming_min_by_mode"][cfg["brightness_mode"]]
            if cfg["dynamic_brightness"]:
                cap_max = cfg["dimming_max_white"] + (cfg["dimming_max"] - cfg["dimming_max_white"]) * kk
                level = min(1.0, v * cfg["brightness_gain"]) ** cfg["brightness_gamma"]
                scale = cfg["brightness_scales"][cfg["brightness_mode"]]
                dimming = max(lo, round(scale * (lo + (cap_max - lo) * level)))
            else:
                dimming = min(100, max(10, round(cfg["fixed_brightness"])))
            state = (*rgb, dimming)
            due = now - last_send_t >= 1 / cfg["send_hz"]
            changed = last_sent is None or max(abs(x - y) for x, y in zip(state, last_sent)) >= cfg["min_change"]
            if due and changed:
                wiz.set_color(rgb, dimming)
                last_sent, last_send_t = state, now
            prev_t = now
            if t_end and now >= t_end:
                break
            shutdown.stop.wait(1 / cfg["capture_hz"])
    except KeyboardInterrupt:
        pass
    finally:
        cap.close()
        if cfg["restore_on_exit"]:
            wiz.restore_state()
            time.sleep(0.2)
            wiz.restore_state()  # UDP sans accusé : on double l'envoi par sécurité
            print("État des ampoules restauré.")
        shutdown.done.set()
