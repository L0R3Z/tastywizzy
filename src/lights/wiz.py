import json
import socket
import threading
import time

PORT = 38899
MAX_MISSES = 3  # échecs consécutifs avant de considérer une ampoule perdue
RESTORE_KEYS = ("r", "g", "b", "c", "w", "temp", "speed")  # champs d'état réappliqués à la restauration


class Bulb:
    def __init__(self, name, ip, mac=None):
        self.name, self.ip, self.mac = name, ip, mac
        self.saved = None
        self.online = False
        self.misses = 0

    def __repr__(self):
        return f"{self.name}({self.ip})"


def _parse(entry):
    """Accepte "ip" (ancien format) ou {"ip": ..., "mac": ...}."""
    if isinstance(entry, str):
        return entry, None
    return entry.get("ip"), (entry.get("mac") or "").lower() or None


def _ask(sock, ips, method, timeout, done=None):
    """Envoie method à chaque IP, renvoie {ip: result} des réponses à method reçues avant timeout.
    S'arrête plus tôt si toutes les IP ont répondu ou si done(out) est vrai."""
    ips = set(ips)
    msg = json.dumps({"method": method, "params": {}}).encode()
    for ip in ips:
        try:
            sock.sendto(msg, (ip, PORT))
        except OSError:
            pass
    out, end = {}, time.monotonic() + timeout
    while (left := end - time.monotonic()) > 0:
        sock.settimeout(left)
        try:
            data, (ip, _) = sock.recvfrom(2048)
            reply = json.loads(data)
            res = reply.get("result")
            # ignore les réponses tardives / dupliquées d'une autre requête
            if res and ip in ips and reply.get("method") == method:
                out[ip] = res
                if len(out) == len(ips) or (done and done(out)):
                    break
        except socket.timeout:
            break
        except (OSError, ValueError):
            continue
    return out


def _local_ip():
    """IP de ce PC sur le réseau local (aucun paquet n'est envoyé), None si hors réseau."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except OSError:
            return None


def _mac(res):
    return (res.get("mac") or "").lower() or None


def _restore_params(saved):
    """Paramètres setPilot qui remettent l'ampoule dans l'état sauvegardé par getPilot."""
    p = {"state": saved.get("state", True), "dimming": saved.get("dimming", 100)}
    if saved.get("sceneId"):
        p["sceneId"] = saved["sceneId"]
        if "speed" in saved:
            p["speed"] = saved["speed"]
    else:
        p.update({k: saved[k] for k in RESTORE_KEYS if k in saved and k != "speed"})
    return p


class Wiz:
    def __init__(self, bulbs, on_change=None, retry_s=30, stop=None):
        self.bulbs = [Bulb(n, *_parse(e)) for n, e in bulbs.items()]
        self.retired = []  # ampoules retirées de la config à chaud : restaurées quand même à la sortie
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.on_change = on_change  # appelé avec {nom: {"ip", "mac"}} quand une IP/MAC est apprise
        self.retry_s = retry_s
        self.stop = stop or threading.Event()
        self._wake = threading.Event()  # réveille la recherche avant la fin du délai
        self._thread = None

    def reconfigure(self, bulbs, retry_s):
        """Applique une config rechargée à chaud (ampoules ajoutées / modifiées / retirées, délai de recherche)."""
        self.retry_s = retry_s
        old = {b.name: b for b in self.bulbs}
        new = []
        for n, e in bulbs.items():
            ip, mac = _parse(e)
            b = old.pop(n, None)
            if b and (ip != b.ip or (mac and mac != b.mac)):
                nb = Bulb(n, ip, mac)  # localisée au prochain passage (déclenché ci-dessous)
                if mac and b.mac and mac != b.mac:
                    self.retired.append(b)  # autre ampoule physique : l'ancienne garde son état d'origine
                else:
                    nb.saved, nb.mac = b.saved, mac or b.mac  # même ampoule, nouvelle IP
                b = nb
            new.append(b or Bulb(n, ip, mac))
        self.retired.extend(old.values())
        self.bulbs = new
        self._wake.set()

    def _send(self, bulb, method, params):
        self.sock.sendto(json.dumps({"method": method, "params": params}).encode(), (bulb.ip, PORT))

    def _locate_all(self, bulbs, sock):
        """Vérifie chaque ampoule à son IP, puis cherche les absentes sur le réseau local
        (par MAC si connue, sinon toute ampoule WiZ non attribuée). Renvoie les ampoules trouvées."""
        found, changed = set(), False
        at_ip = _ask(sock, [b.ip for b in bulbs if b.ip], "getSystemConfig", 1.0)
        for b in bulbs:
            res = at_ip.get(b.ip)
            if res and (not b.mac or _mac(res) == b.mac):
                if not b.mac and _mac(res):
                    b.mac, changed = _mac(res), True
                found.add(b)
        missing = [b for b in bulbs if b not in found]
        if missing:
            prefixes = {ip.rsplit(".", 1)[0] for ip in [_local_ip(), *(b.ip for b in missing)] if ip}
            ips = [f"{p}.{i}" for p in prefixes for i in range(1, 255)]
            macs = {b.mac for b in missing}
            done = (lambda out: macs <= {_mac(r) for r in out.values()}) if None not in macs else None
            scan = _ask(sock, ips, "getSystemConfig", 2.0, done)
            by_mac = {_mac(r): ip for ip, r in scan.items() if _mac(r)}
            claimed = {b.mac for b in self.bulbs if b.mac} | {b.ip for b in found}
            for b in missing:
                ip = by_mac.get(b.mac) if b.mac else next(
                    (ip for m, ip in by_mac.items() if m not in claimed and ip not in claimed), None)
                if ip:
                    adopted = not b.mac
                    b.ip, changed = ip, True
                    b.mac = b.mac or next(m for m, i in by_mac.items() if i == ip)
                    print(f"{b.name} {'attribuée à l ampoule' if adopted else 'retrouvée'} {b.mac} : {ip}")
                    claimed |= {b.mac, ip}
                    found.add(b)
        if changed:
            self._changed()
        return found

    def _changed(self):
        if self.on_change:
            try:
                self.on_change({b.name: {"ip": b.ip, "mac": b.mac} for b in self.bulbs})
            except Exception as e:
                print("Impossible de mettre à jour config.json :", e)

    def _save_states(self, bulbs, sock):
        bulbs = [b for b in bulbs if b.saved is None]  # ne pas écraser l'état d'origine par une couleur ambilight
        res = _ask(sock, [b.ip for b in bulbs], "getPilot", 1.0)
        for b in bulbs:
            b.saved = res.get(b.ip)

    def connect(self):
        """Localise les ampoules, sauvegarde leur état, puis relance la recherche des absentes en fond."""
        found = self._locate_all(self.bulbs, self.sock)
        self._save_states(found, self.sock)
        for b in self.bulbs:
            b.online = b in found
            if not b.online:
                print(f"Attention : {b.name} injoignable, nouvel essai toutes les {self.retry_s} s.")
        self.sock.settimeout(None)
        self._thread = threading.Thread(target=self._retry_loop, daemon=True)
        self._thread.start()

    def _retry_loop(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            while not self.stop.is_set():
                self._wake.wait(self.retry_s)
                self._wake.clear()
                if self.stop.is_set():
                    break
                try:
                    self._check(sock)
                except Exception as e:  # la recherche doit survivre à toute erreur ponctuelle
                    print("Erreur pendant la recherche des ampoules :", e)

    def _check(self, sock):
        bulbs = self.bulbs
        found = self._locate_all(bulbs, sock)  # revérifie aussi les ampoules en ligne
        self._save_states(found, sock)
        for b in bulbs:
            if b in found:
                if not b.online:
                    print(f"{b.name} de nouveau joignable ({b.ip}).")
                b.online, b.misses = True, 0
            elif b.online:
                b.misses += 1  # UDP : un paquet perdu ne suffit pas à déclarer l'ampoule perdue
                if b.misses >= MAX_MISSES:
                    b.online = False
                    print(f"Attention : {b.name} perdue, recherche en cours.")

    def restore_state(self):
        for b in [*self.bulbs, *self.retired]:
            if not b.saved or not b.ip:  # tentée même hors ligne : l'envoi est sans risque
                continue
            try:
                self._send(b, "setPilot", _restore_params(b.saved))
            except OSError:
                pass

    def _broadcast(self, p):
        for bulb in self.bulbs:
            if bulb.online:
                try:
                    self._send(bulb, "setPilot", p)  # sans attente de réponse
                except OSError:
                    pass  # réseau momentanément indisponible : la prochaine trame repassera

    def set_color(self, rgb, dimming, white=0):
        r, g, b = rgb
        self._broadcast({"state": True, "r": r, "g": g, "b": b, "c": 0, "w": white, "dimming": dimming})
