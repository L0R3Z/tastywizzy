"""Test du fondu interne des ampoules WiZ. Sauvegarde l'état, teste, restaure.
Usage : python tools/fade_test.py [A|B|C|D]  (ampoules lues depuis config.json)"""
import colorsys
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from lights import config, wiz  # noqa: E402


def rgb(h):
    r, g, b = (round(c * 255) for c in colorsys.hsv_to_rgb(h % 1, 1, 1))
    return {"state": True, "r": r, "g": g, "b": b, "dimming": 100}


def sweep(w, hz, secs, label):
    print(f"\n>>> {label} : balayage de teinte à {hz} Hz pendant {secs}s", flush=True)
    t0, n = time.time(), 0
    while time.time() - t0 < secs:
        w._broadcast(rgb((time.time() - t0) / 8))  # 1 tour de teinte / 8 s
        n += 1
        time.sleep(1 / hz)
    print(f"    {n} envois", flush=True)


def jumps(w):
    print(">>> A : sauts rouge/bleu toutes les 2 s (avec temps de réponse)")
    rtts = {b.name: [] for b in w.bulbs}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for i in range(6):
            p = rgb(0 if i % 2 == 0 else 2 / 3)
            for b in w.bulbs:
                t = time.time()
                w._send(b, "setPilot", p)
                if wiz._ask(sock, [b.ip], "getPilot", 1.0):
                    rtts[b.name].append((time.time() - t) * 1000)
            time.sleep(2)
    for name, values in rtts.items():
        print(f"    {name} : {sum(values) / len(values):.0f} ms en moyenne" if values else f"    {name} : aucune réponse")


def main():
    w = wiz.Wiz(config.load(ROOT / "config.json")["bulbs"])
    w.connect()
    print("sauvegardé", {b.name: b.saved for b in w.bulbs})
    phase = sys.argv[1].upper() if len(sys.argv) > 1 else "A"
    try:
        if phase == "A":
            jumps(w)
        else:
            sweep(w, {"B": 2, "C": 5, "D": 10}[phase], 8, phase)
    finally:
        w.stop.set()
        w.restore_state()
        print("état restauré")


if __name__ == "__main__":
    main()
