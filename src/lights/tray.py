import logging
import os
import threading
import time

import pystray
from PIL import Image, ImageDraw

from . import autostart, shutdown
from .pause import MANUAL, SESSION

log = logging.getLogger(__name__)

GREY = (110, 110, 110)


def _image(rgb):
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((4, 4, 60, 60), fill=(*rgb, 255), outline=(255, 255, 255, 255), width=3)
    return img


class Tray:
    """Icône de la zone de notification. run() bloque (thread principal) jusqu'à stop()."""

    def __init__(self, pause, log_path, config_path):
        self.pause = pause
        self.rgb = (255, 160, 60)
        self._shown = None
        self._next_color = 0.0
        self._lock = threading.Lock()  # appelé depuis le worker, le raccourci et la fenêtre session
        menu = pystray.Menu(
            pystray.MenuItem(self._pause_label, pause.toggle_manual, checked=lambda _: pause.has(MANUAL),
                             default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Ouvrir le journal", lambda: os.startfile(log_path)),
            pystray.MenuItem("Ouvrir la config", lambda: os.startfile(config_path)),
            pystray.MenuItem("Démarrer avec Windows", self._toggle_autostart, checked=lambda _: autostart.is_enabled()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quitter", shutdown.stop.set),
        )
        self.icon = pystray.Icon("TastyWizzy", _image(self.rgb), "TastyWizzy", menu)
        pause.listeners.append(self.refresh)

    def _pause_label(self, _):
        if self.pause.has(SESSION) and not self.pause.has(MANUAL):
            return "En pause (verrouillé / veille)"
        return "Pause"

    def _toggle_autostart(self):
        try:
            autostart.set_enabled(not autostart.is_enabled())
        except OSError as e:
            log.warning("Démarrage avec Windows : %s", e)

    def set_color(self, rgb):
        """Appelé à chaque envoi aux ampoules : l'icône suit au plus une fois par seconde."""
        now = time.monotonic()
        with self._lock:
            if now < self._next_color:
                return
            self._next_color = now + 1.0
            self.rgb = rgb
        self.refresh()

    def refresh(self):
        """Met à jour l'icône (couleur, grisée en pause) et le menu ; sans effet si rien n'a changé."""
        with self._lock:
            paused = self.pause.paused
            shown = GREY if paused else self.rgb
            if shown != self._shown:
                self._shown = shown
                self.icon.icon = _image(shown)
                self.icon.title = "TastyWizzy (en pause)" if paused else "TastyWizzy"
        self.icon.update_menu()

    def run(self):
        self.icon.run()

    def stop(self):
        self.icon.stop()
