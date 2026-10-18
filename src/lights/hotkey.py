import ctypes
import threading
from ctypes import wintypes

WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000
VK_F1 = 0x70
MODS = {"alt": 0x0001, "ctrl": 0x0002, "shift": 0x0004, "win": 0x0008}


def parse(combo):
    """'ctrl+alt+l' -> (modificateurs, code de touche virtuelle). Touches : lettre, chiffre, f1-f24."""
    parts = [p.strip().lower() for p in combo.split("+")]
    mods = 0
    for p in parts[:-1]:
        if p not in MODS:
            raise ValueError(f"Modificateur non supporté : {p}")
        mods |= MODS[p]
    key = parts[-1]
    if len(key) == 1 and key.isalnum():
        vk = ord(key.upper())
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = VK_F1 + int(key[1:]) - 1
    else:
        raise ValueError(f"Touche non supportée : {key}")
    return mods, vk


class PauseHotkey:
    """Raccourci global (RegisterHotKey) : chaque appui appelle on_press (dans le thread du raccourci)."""

    def __init__(self, combo, on_press=lambda: None):
        self.combo = combo
        self.on_press = on_press
        self.error = None
        try:
            self._keys = parse(combo)
        except ValueError as e:
            self.error = f"Raccourci {combo} invalide : {e}"
            return
        self._ok = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        if not self._ok.wait(2):
            self.error = f"Raccourci {combo} : enregistrement sans réponse"

    def _loop(self):
        mods, vk = self._keys
        user32 = ctypes.windll.user32
        if not user32.RegisterHotKey(None, 1, mods | MOD_NOREPEAT, vk):
            self.error = f"Raccourci {self.combo} déjà pris"
            self._ok.set()
            return
        self._ok.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                self.on_press()
