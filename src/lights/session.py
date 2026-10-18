import ctypes
import logging
import threading
from ctypes import wintypes

from . import shutdown
from .pause import SESSION

log = logging.getLogger(__name__)

WM_QUERYENDSESSION = 0x0011
WM_ENDSESSION = 0x0016
WM_POWERBROADCAST = 0x0218
WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK, WTS_SESSION_UNLOCK = 0x7, 0x8
PBT_APMSUSPEND, PBT_APMRESUMEAUTOMATIC = 0x4, 0x12
NOTIFY_FOR_THIS_SESSION = 0
HWND_MESSAGE = wintypes.HWND(-3)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


class SessionWatcher:
    """Fenêtre message cachée : verrouillage/veille -> pause, déconnexion/arrêt du PC -> arrêt propre.

    on_suspend est appelé tout de suite à la mise en veille (le réseau coupe vite, on n'attend pas la boucle).
    """

    def __init__(self, pause, auto_pause=True, on_suspend=None):
        self.pause = pause
        self.on_suspend = on_suspend
        self.locked = False
        self.auto_pause = auto_pause
        self._proc = WNDPROC(self._wndproc)  # référence gardée : sinon le callback est libéré
        threading.Thread(target=self._loop, daemon=True).start()

    @property
    def auto_pause(self):
        return self._auto_pause

    @auto_pause.setter
    def auto_pause(self, on):
        self._auto_pause = on
        if not on:  # désactivé à chaud pendant un verrouillage : ne pas rester en pause indéfiniment
            self.pause.set(SESSION, False)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        user32 = ctypes.windll.user32
        if msg == WM_WTSSESSION_CHANGE and self.auto_pause:
            if wparam == WTS_SESSION_LOCK:
                self.locked = True
                log.info("Session verrouillée : pause.")
                self.pause.set(SESSION, True)
            elif wparam == WTS_SESSION_UNLOCK:
                self.locked = False
                log.info("Session déverrouillée.")
                self.pause.set(SESSION, False)
        elif msg == WM_POWERBROADCAST and self.auto_pause:
            if wparam == PBT_APMSUSPEND:
                log.info("Mise en veille : pause.")
                self.pause.set(SESSION, True)
                if self.on_suspend:
                    self.on_suspend()
            # PBT_APMRESUMEAUTOMATIC est envoyé à chaque sortie de veille (PBT_APMRESUMESUSPEND seulement
            # si un utilisateur est présent) : il suffit
            elif wparam == PBT_APMRESUMEAUTOMATIC and not self.locked:
                log.info("Sortie de veille.")
                self.pause.set(SESSION, False)
            return 1
        elif msg == WM_QUERYENDSESSION:
            return 1
        elif msg == WM_ENDSESSION and wparam:
            log.info("Fermeture de session : arrêt.")
            shutdown.stop.set()
            shutdown.done.wait(4)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _loop(self):
        user32 = ctypes.windll.user32
        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.DefWindowProcW.restype = LRESULT
        user32.CreateWindowExW.restype = wintypes.HWND
        hinst = ctypes.windll.kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW(lpfnWndProc=self._proc, hInstance=hinst, lpszClassName="TastyWizzySession")
        user32.RegisterClassW(ctypes.byref(wc))
        # fenêtre de premier niveau invisible : les fenêtres message-only ne reçoivent pas WM_ENDSESSION
        hwnd = user32.CreateWindowExW(0, wc.lpszClassName, "TastyWizzy", 0, 0, 0, 0, 0, None, None, hinst, None)
        if not hwnd:
            log.warning("Surveillance verrouillage/veille indisponible.")
            return
        if not ctypes.windll.wtsapi32.WTSRegisterSessionNotification(hwnd, NOTIFY_FOR_THIS_SESSION):
            log.warning("Notification de verrouillage indisponible.")
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
