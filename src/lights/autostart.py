import sys
import winreg
from pathlib import Path

KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "TastyWizzy"


def command():
    """Commande lancée à l'ouverture de session : l'exe si figé, sinon pythonw + main.py."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pyw = Path(sys.executable).with_name("pythonw.exe")
    main = Path(__file__).resolve().parents[2] / "main.py"
    return f'"{pyw}" "{main}"'


def is_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as k:
            winreg.QueryValueEx(k, NAME)
        return True
    except OSError:
        return False


def set_enabled(on):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(k, NAME)
            except FileNotFoundError:
                pass
