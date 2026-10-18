import ctypes
import logging
import logging.handlers
import os
import shutil
import sys
import threading
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)  # lancé depuis l'exe PyInstaller
if not FROZEN:
    sys.path.insert(0, str(Path(__file__).parent / "src"))

from lights import app, config, shutdown  # noqa: E402
from lights.pause import PauseState  # noqa: E402

APP_DIR = Path(sys.executable).parent if FROZEN else Path(__file__).parent  # config.json à côté de l'exe
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))  # fichiers embarqués (config.example.json)
LOG_PATH = Path(os.environ.get("LOCALAPPDATA", APP_DIR)) / "TastyWizzy" / "lights.log"
ERROR_ALREADY_EXISTS = 183


def has_console():
    return bool(ctypes.windll.kernel32.GetConsoleWindow())


def fail(msg):
    """Erreur fatale : texte en console, boîte de dialogue sinon."""
    logging.getLogger("lights").error(msg)
    if not has_console():
        ctypes.windll.user32.MessageBoxW(None, msg, "TastyWizzy", 0x10)
    sys.exit(msg)


def setup_logging(console):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"))
    handlers = [file_handler]
    if console:
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(level=logging.INFO, handlers=handlers)


def main():
    args = [a for a in sys.argv[1:] if a != "--console"]
    console = "--console" in sys.argv[1:]
    setup_logging(console and has_console())
    # une seule instance : démarrage auto + lancement manuel se battraient pour les ampoules
    # handle gardé ouvert jusqu'à la fin du process (le libérer lèverait le verrou)
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "TastyWizzy-single-instance")
    if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        fail("TastyWizzy est déjà lancé (icône dans la zone de notification).")
    # Argument optionnel : durée en secondes (sinon tourne jusqu'à l'arrêt)
    try:
        duration = float(args[0]) if args else None
    except ValueError:
        fail(f"Durée invalide : {args[0]!r} (attendu : un nombre de secondes)")
    path = APP_DIR / "config.json"
    if not path.exists():  # config.json est local (ignoré par git) : on part du modèle
        shutil.copy(BUNDLE_DIR / "config.example.json", path)
        logging.getLogger("lights").info("config.json créé depuis config.example.json.")
    try:
        cfg = config.load(path)
        config.validate(cfg)
    except (ValueError, KeyError, TypeError) as e:
        fail(f"Config invalide : {e}")

    try:
        from lights.tray import Tray
    except ImportError:  # pystray/Pillow absents : mode console seul
        Tray = None
        if not console:  # lancé sans console (pythonw, démarrage auto) : sans icône, impossible de quitter
            fail("pystray/Pillow manquants : réinstalle les dépendances (pip install -r requirements.txt).")
    if console:
        app.run(cfg, duration, path)
        return
    pause = PauseState()
    tray = Tray(pause, LOG_PATH, path)

    def worker():
        try:
            app.run(cfg, duration, path, pause, tray.set_color)
        except Exception:
            logging.getLogger("lights").exception("Arrêt sur erreur")
        finally:
            tray.stop()

    t = threading.Thread(target=worker, daemon=True)  # ne bloque pas la sortie si app.run reste coincé
    t.start()
    tray.run()  # bloque jusqu'à tray.stop() (Quitter -> shutdown.stop -> fin de app.run)
    shutdown.stop.set()
    t.join(10)


if __name__ == "__main__":
    main()
