import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from lights import app, config

if __name__ == "__main__":
    # Argument optionnel : durée en secondes (sinon tourne jusqu'à Ctrl+C)
    try:
        duration = float(sys.argv[1]) if len(sys.argv) > 1 else None
    except ValueError:
        sys.exit(f"Durée invalide : {sys.argv[1]!r} (attendu : un nombre de secondes)")
    path = Path(__file__).parent / "config.json"
    if not path.exists():  # config.json est local (ignoré par git) : on part du modèle
        shutil.copy(path.with_name("config.example.json"), path)
        print("config.json créé depuis config.example.json : renseigne les IP de tes ampoules.")
    try:
        cfg = config.load(path)
        config.validate(cfg)
    except (ValueError, KeyError, TypeError) as e:
        sys.exit(f"Config invalide : {e}")
    app.run(cfg, duration, path)
