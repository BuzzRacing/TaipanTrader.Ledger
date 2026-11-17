"""Whose turn it is to speak.

Every screen (the player window, the harbor board, a second player window...)
keeps its own list of lines to read aloud. Screens that share the same
speakers must not talk over each other, so before a screen plays a line it asks
the server for the turn ("the floor"). The server hands the turn to one screen
at a time per device, in the order the screens asked, and the others wait.

    take   ask for the turn (or keep it); waiting screens line up first come, first served
    renew  still talking, keep the turn
    free   finished (or muted, or closed); the next screen in line may speak

A screen that stops renewing (closed, crashed, lost the network) loses the turn
after LEASE seconds, so one dead window can never silence the rest.

News headlines are read by several screens at once (player and board). When a
line marked "once" was just read on this device by another screen, the second
screen is told to skip it instead of reading the same headline twice.

Screens on the same computer share one turn. Each other device (an iPad, a
laptop) has its own speakers and gets its own turn. Set SCOPE = "house" to make
every screen in the house wait for every other.
"""
import socket
import threading
import time

LEASE = 6.0          # seconds a turn is held without a renewal
STALE = 3.0          # a waiting screen that stopped asking leaves the line
HEARD = 90.0         # a "once" line read by one screen is not read again by another screen
WAIT = 0.35          # how long a waiting screen should pause before asking again
SCOPE = "device"     # "device": one turn per computer/tablet; "house": one turn for everyone

_LOCAL = {"127.0.0.1", "::1", "localhost"}


def _own_addresses():
    found = set(_LOCAL)
    try:
        found.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    return found


class Floor:
    def __init__(self):
        self.lock = threading.Lock()
        self.rooms = {}
        self.own = _own_addresses()

    def add_own(self, address):
        """Teach the floor another address of the server's own computer (its LAN address)."""
        if address:
            self.own.add(address)

    def room_for(self, address):
        if SCOPE == "house":
            return "house"
        a = str(address or "")
        if a.startswith("::ffff:"):
            a = a[7:]
        return "local" if a in self.own else a

    def _room(self, key):
        r = self.rooms.get(key)
        if r is None:
            r = self.rooms[key] = {"holder": None, "until": 0.0, "line": [], "heard": {}}
        return r

    @staticmethod
    def _tidy(r, now):
        if r["holder"] and r["until"] < now:
            r["holder"] = None
        r["line"] = [w for w in r["line"] if now - w[1] <= STALE]
        if len(r["heard"]) > 200:
            r["heard"] = {k: v for k, v in r["heard"].items() if now - v[1] <= HEARD}

    def ask(self, address, sid, op, clip="", now=None):
        """Answer one screen. Returns {"granted": bool, "skip": bool, "wait": seconds}."""
        now = time.monotonic() if now is None else now
        sid = str(sid or "")[:64]
        clip = str(clip or "")[:64]
        if not sid:
            return {"granted": True, "skip": False, "wait": 0}
        with self.lock:
            r = self._room(self.room_for(address))
            self._tidy(r, now)
            if op == "free":
                if r["holder"] == sid:
                    r["holder"] = None
                r["line"] = [w for w in r["line"] if w[0] != sid]
                return {"granted": False, "skip": False, "wait": 0}
            if op == "renew":
                if r["holder"] == sid:
                    r["until"] = now + LEASE
                    return {"granted": True, "skip": False, "wait": 0}
                return {"granted": False, "skip": False, "wait": WAIT}
            # take
            if r["holder"] == sid:
                r["until"] = now + LEASE
                if clip:
                    r["heard"][clip] = (sid, now)
                return {"granted": True, "skip": False, "wait": 0}
            if clip:
                h = r["heard"].get(clip)
                if h and h[0] != sid and now - h[1] <= HEARD:
                    r["line"] = [w for w in r["line"] if w[0] != sid]
                    return {"granted": False, "skip": True, "wait": 0}
            first = r["line"][0][0] if r["line"] else None
            if r["holder"] is None and (first is None or first == sid):
                r["holder"], r["until"] = sid, now + LEASE
                r["line"] = [w for w in r["line"] if w[0] != sid]
                if clip:
                    r["heard"][clip] = (sid, now)
                return {"granted": True, "skip": False, "wait": 0}
            for w in r["line"]:
                if w[0] == sid:
                    w[1] = now
                    break
            else:
                r["line"].append([sid, now])
            return {"granted": False, "skip": False, "wait": WAIT}

    def status(self):
        now = time.monotonic()
        with self.lock:
            out = {}
            for key, r in self.rooms.items():
                self._tidy(r, now)
                out[key] = {"speaking": r["holder"], "waiting": [w[0] for w in r["line"]]}
            return out


FLOOR = Floor()
