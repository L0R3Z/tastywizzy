import json
import socket

PORT = 38899


class Bulb:
    def __init__(self, name, ip):
        self.name, self.ip = name, ip
        self.saved = None

    def __repr__(self):
        return f"{self.name}({self.ip})"


class Wiz:
    def __init__(self, bulbs):
        self.bulbs = [Bulb(n, ip) for n, ip in bulbs.items()]
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def _send(self, bulb, method, params):
        self.sock.sendto(json.dumps({"method": method, "params": params}).encode(), (bulb.ip, PORT))

    def save_state(self):
        self.sock.settimeout(1.0)
        for b in self.bulbs:
            self._send(b, "getPilot", {})
            try:
                b.saved = json.loads(self.sock.recvfrom(2048)[0])["result"]
            except (socket.timeout, KeyError, ValueError):
                b.saved = None
        self.sock.settimeout(None)

    def restore_state(self):
        for b in self.bulbs:
            s = b.saved
            if not s:
                continue
            p = {"state": s["state"], "dimming": s.get("dimming", 100)}
            if s.get("sceneId"):
                p["sceneId"] = s["sceneId"]
            elif "temp" in s:
                p["temp"] = s["temp"]
            self._send(b, "setPilot", p)

    def set_color(self, rgb, dimming):
        r, g, b = rgb
        p = {"state": True, "r": r, "g": g, "b": b, "dimming": dimming}
        for bulb in self.bulbs:
            self._send(bulb, "setPilot", p)  # sans attente de réponse

    def set_temp(self, kelvin, dimming):
        p = {"state": True, "temp": kelvin, "dimming": dimming}
        for bulb in self.bulbs:
            self._send(bulb, "setPilot", p)
