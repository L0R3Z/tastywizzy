import ctypes
import threading
from ctypes import wintypes

WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000
MODS = {"alt": 0x0001, "ctrl": 0x0002, "shift": 0x0004, "win": 0x0008}


def parse(combo):
    """'ctrl+alt+l' -> (modificateurs, code de touche virtuelle). Touches : lettre, chiffre, f1-f24."""
    parts = [p.strip().lower() for p in combo.split("+")]
    mods = 0
    for p in parts[:-1]:
        mods |= MODS[p]
    key = parts[-1]
    if len(key) == 1 and key.isalnum():
        vk = ord(key.upper())
    elif key.startswith("f") and key[1:].isdigit():
        vk = 0x70 + int(key[1:]) - 1
    else:
        raise ValueError(f"Touche non supportée : {key}")
    return mods, vk


class PauseHotkey:
    """Raccourci global (RegisterHotKey) : chaque appui bascule `paused`."""

    def __init__(self, combo):
        self.combo = combo
        self.paused = threading.Event()
        self.toggled = threading.Event()  # posé à chaque appui, à effacer par le consommateur
        self._ok = threading.Event()
        self.error = None
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self._ok.wait(2)

    def _loop(self):
        mods, vk = parse(self.combo)
        user32 = ctypes.windll.user32
        if not user32.RegisterHotKey(None, 1, mods | MOD_NOREPEAT, vk):
            self.error = f"Raccourci {self.combo} déjà pris ou invalide"
            self._ok.set()
            return
        self._ok.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                if self.paused.is_set():
                    self.paused.clear()
                else:
                    self.paused.set()
                self.toggled.set()
