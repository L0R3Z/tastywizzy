import ctypes
import threading

stop = threading.Event()  # posé quand la fenêtre se ferme, Ctrl+C/Break, déconnexion ou arrêt
done = threading.Event()  # à poser une fois la restauration terminée

_HANDLER = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)
CTRL_C_EVENT = 0


def _on_event(event):
    # 0 Ctrl+C, 1 Ctrl+Break, 2 fermeture de la fenêtre, 5 déconnexion, 6 arrêt
    stop.set()
    if event != CTRL_C_EVENT:
        done.wait(4)  # Windows tue le processus ~5 s après le retour du gestionnaire
    return 1  # géré : pas de KeyboardInterrupt, la boucle principale voit `stop`


_keep = _HANDLER(_on_event)


def install():
    ctypes.windll.kernel32.SetConsoleCtrlHandler(_keep, 1)
