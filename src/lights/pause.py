import logging
import threading

log = logging.getLogger(__name__)

MANUAL = "manual"  # raccourci clavier ou menu tray
SESSION = "session"  # session verrouillée ou PC en veille


class PauseState:
    """Pause partagée entre plusieurs sources : en pause tant qu'au moins une raison est active."""

    def __init__(self):
        self._lock = threading.Lock()
        self._reasons = set()
        self.changed = threading.Event()  # posé à chaque passage pause <-> actif, à effacer par le consommateur
        self.listeners = []  # appelés (sans argument) à chaque changement, ex. rafraîchir le menu tray

    @property
    def paused(self):
        return bool(self._reasons)

    def has(self, reason):
        return reason in self._reasons

    def set(self, reason, on):
        with self._lock:
            if on == (reason in self._reasons):
                return  # rien ne change : pas de notification
            before = self.paused
            (self._reasons.add if on else self._reasons.discard)(reason)
            flipped = before != self.paused
        if flipped:
            self.changed.set()
        for f in self.listeners:
            try:  # un écouteur défaillant ne doit pas tuer le thread appelant (raccourci, fenêtre session)
                f()
            except Exception:
                log.exception("Écouteur de pause en erreur")

    def toggle_manual(self):
        self.set(MANUAL, not self.has(MANUAL))
