import mss
import numpy as np

SUBSAMPLE = 8  # un pixel sur 8 dans chaque direction : largement assez pour une couleur moyenne
MONITORS = ("primary", "all")


class Capture:
    """Interface : grab() -> tableau RGB (H, W, 3) uint8. Branchable pour dxcam plus tard."""

    def grab(self):
        raise NotImplementedError

    def close(self):
        pass


class MssCapture(Capture):
    def __init__(self, monitor="primary"):
        if monitor not in MONITORS:
            raise ValueError(f"monitor doit valoir {' ou '.join(MONITORS)}")
        self._sct = mss.mss()
        mons = self._sct.monitors  # [0]=bureau virtuel, [1]=principal
        self._mon = mons[0] if monitor == "all" else mons[1]

    def grab(self):
        """Lève mss.exception.ScreenShotError si l'écran n'est pas capturable (session verrouillée, UAC)."""
        shot = self._sct.grab(self._mon)
        bgra = np.frombuffer(shot.bgra, dtype=np.uint8).reshape(shot.height, shot.width, 4)
        return bgra[::SUBSAMPLE, ::SUBSAMPLE, 2::-1]  # sous-échantillonné, BGRA -> RGB

    def close(self):
        self._sct.close()
