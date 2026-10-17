"""Test du fondu interne des ampoules WiZ. Sauvegarde l'état, teste, restaure."""
import colorsys, json, socket, statistics, sys, time

BULBS = {"plafonnier": "192.168.1.29", "bureau": "192.168.1.33"}
PORT = 38899
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(1.0)


def call(ip, method, params=None, wait=True):
    sock.sendto(json.dumps({"method": method, "params": params or {}}).encode(), (ip, PORT))
    if not wait:
        return None
    try:
        return json.loads(sock.recvfrom(2048)[0])
    except socket.timeout:
        return None


def rgb(h):
    r, g, b = (round(c * 255) for c in colorsys.hsv_to_rgb(h % 1, 1, 1))
    return {"state": True, "r": r, "g": g, "b": b, "dimming": 100}


def all_set(p):
    for ip in BULBS.values():
        call(ip, "setPilot", p, wait=False)


def sweep(hz, secs, label):
    print(f"\n>>> {label} : balayage de teinte à {hz} Hz pendant {secs}s", flush=True)
    t0, n = time.time(), 0
    while time.time() - t0 < secs:
        all_set(rgb((time.time() - t0) / 8))  # 1 tour de teinte / 8 s
        n += 1
        time.sleep(1 / hz)
    print(f"    {n} envois", flush=True)


saved = {}
for name, ip in BULBS.items():
    r = call(ip, "getPilot")
    saved[name] = r["result"] if r else None
    print("sauvegardé", name, saved[name])

phase = sys.argv[1].upper() if len(sys.argv) > 1 else "A"
try:
    if phase == "A":
        print(">>> A : sauts rouge/bleu toutes les 2 s")
        rtts = {n: [] for n in BULBS}
        for i in range(6):
            p = rgb(0 if i % 2 == 0 else 2 / 3)
            for n, ip in BULBS.items():
                t = time.time()
                if call(ip, "setPilot", p):
                    rtts[n].append((time.time() - t) * 1000)
            time.sleep(2)
    elif phase == "B":
        sweep(2, 8, "B")
    elif phase == "C":
        sweep(5, 8, "C")
    elif phase == "D":
        sweep(10, 8, "D")
finally:
    for name, ip in BULBS.items():
        s = saved[name]
        if not s:
            continue
        p = {"state": s["state"], "dimming": s.get("dimming", 100)}
        if "sceneId" in s and s["sceneId"]:
            p["sceneId"] = s["sceneId"]
        elif "temp" in s:
            p["temp"] = s["temp"]
        call(ip, "setPilot", p)
    print("état restauré")
