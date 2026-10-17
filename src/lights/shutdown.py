import ctypes
import threading

stop = threading.Event()  # posé quand la fenêtre se ferme, Ctrl+C/Break, déconnexion ou arrêt
done = threading.Event()  # à poser une fois la restauration terminée

_HANDLER = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)


def _on_event(event):
    # 0 Ctrl+C, 1 Ctrl+Break, 2 fermeture de la fenêtre, 5 déconnexion, 6 arrêt
    stop.set()
    if event >= 1:
        done.wait(4)  # Windows tue le processus ~5 s après le retour du gestionnaire
        return 1
    return 1


_keep = _HANDLER(_on_event)


def install():
    ctypes.windll.kernel32.SetConsoleCtrlHandler(_keep, 1)
