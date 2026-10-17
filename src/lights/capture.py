import mss
import numpy as np


class Capture:
    """Interface : grab() -> tableau RGB (H, W, 3) uint8. Branchable pour dxcam plus tard."""

    def grab(self):
        raise NotImplementedError

    def close(self):
        pass


class MssCapture(Capture):
    def __init__(self, monitor="primary"):
        self._sct = mss.mss()
        mons = self._sct.monitors  # [0]=bureau virtuel, [1]=principal
        self._mon = mons[0] if monitor == "all" else mons[1]

    def grab(self):
        shot = self._sct.grab(self._mon)
        bgra = np.frombuffer(shot.bgra, dtype=np.uint8).reshape(shot.height, shot.width, 4)
        return bgra[::8, ::8, 2::-1]  # sous-échantillonné, BGRA -> RGB

    def close(self):
        self._sct.close()
