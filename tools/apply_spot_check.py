"""Adds Port Authority spot checks to engine.py and config.py (strings.py already has the lines).

A house that would pay no tax at a landing (its home port, or a port where its shares cut the tax
to nothing) is now and then stopped anyway and declares at the port's full rate, that landing only.
Admin > Pirates & Customs: "Spot check at home" and "Spot check where shares make a port free".

Safe to run twice: each edit is skipped if it is already in place.
Run from the project folder:  python tools/apply_spot_check.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ENGINE = [
    ('''    def _drift_tax_rates(self):''',
     '''    def _spot_check(self, p, port):
        """A house that would pay no tax here (its home port, or a port where its shares cut the tax
        to nothing) is now and then stopped anyway: a spot check at the port's full rate for this
        one landing, waiver and shares set aside (Pirates & Customs > Spot check). Returns "home",
        "shares" or None. Drawn from its own seed, never the game's dice, so the same landing
        always comes out the same."""
        c = R["customs"]
        if self.tax_rate(port) <= 0 or self.tax_rate_for(p, port) > 0:
            return None                          # a free port has nothing to check; a taxed house is checked anyway
        kind = "home" if self.home_free(p, port) else "shares"
        chance = float(c.get("spot_home" if kind == "home" else "spot_shares", 0.0) or 0.0)
        if chance <= 0:
            return None
        roll = random.Random("spot:{}:{}:{}:{}".format(self.s.get("game_id", ""), p.get("id", p.get("name", "")),
                                                       self.s["turn"], port)).random()
        return kind if roll < chance else None

    def _drift_tax_rates(self):''', "def _spot_check("),
    ('''                          "appetite": round(app, 4)})
        status = "declare" if rate > 0 and lines else "welcome"''',
     '''                          "appetite": round(app, 4)})
        spot = self._spot_check(p, port) if lines else None
        if spot:                                 # stopped anyway: the port's full rate, this landing only
            rate, at_home = self.tax_rate(port), False
        status = "declare" if rate > 0 and lines else "welcome"''', "spot = self._spot_check(p, port)"),
    ('''                        "free": rate <= 0, "home_free": at_home, "lines": lines, "cx": cx, "box": box, "result": None}
        if status == "declare":
            p["customs"]["say"] = self._pa_greeting(p, p["customs"]["officer"])''',
     '''                        "free": rate <= 0, "home_free": at_home, "spot": spot, "lines": lines, "cx": cx, "box": box,
                        "result": None}
        if spot:
            p["customs"]["say"] = "l.customs_spot_" + spot
        elif status == "declare":
            p["customs"]["say"] = self._pa_greeting(p, p["customs"]["officer"])''', '"l.customs_spot_" + spot'),
    ('''            "waves the house in (its home port, no tax)" if at_home else''',
     '''            "stops the house for a spot check at the full rate of {} ({})".format(
                pct(rate), "its home port" if spot == "home" else "its shares make the port free") if spot else
            "waves the house in (its home port, no tax)" if at_home else''', "stops the house for a spot check"),
    ('''            p, port=port, rate=rate, lines=lines, cx=cx, box=box, status=status)''',
     '''            p, port=port, rate=rate, lines=lines, cx=cx, box=box, status=status, spot=spot)''', "status=status, spot=spot)"),
    ('''        out["home_free"] = bool(cu.get("home_free"))
        out["tip"] = cu.get("tip")''',
     '''        out["home_free"] = bool(cu.get("home_free"))
        out["spot"] = cu.get("spot")             # "home" / "shares" when a free house was stopped anyway
        out["tip"] = cu.get("tip")''', 'out["spot"] = cu.get("spot")'),
]

CONFIG = [
    ('''"customs": {"enabled": True, "home_free": True, "bond": True,''',
     '''"customs": {"enabled": True, "home_free": True, "spot_home": 0.05, "spot_shares": 0.05, "bond": True,''',
     '"spot_home": 0.05'),
    ('''               "Each player's home port (where they started) waves them in free, whatever its rate for others."),''',
     '''               "Each player's home port (where they started) waves them in free, whatever its rate for others."),
             _pct("rules.customs.spot_home", "Spot check at home: chance a house is stopped anyway",
                  "Now and then a house coming home with cargo is stopped and declares at the port's full rate, "
                  "for that one landing only. Lies, buyouts and audits work as in any port. 0: never.", 0, 1),
             _pct("rules.customs.spot_shares", "Spot check where shares make a port free",
                  "The same, in a port where the house's shares cut its tax to nothing: the shares are set aside "
                  "for that landing and it declares at the full rate. 0: never.", 0, 1),''',
     '"rules.customs.spot_home"'),
]


def patch(name, edits, dry):
    path = os.path.join(ROOT, name)
    with open(path, encoding="utf-8") as f:
        s = f.read()
    for old, new, done in edits:
        if done in s:
            continue
        if s.count(old) != 1:
            sys.exit("{}: could not find the place for this edit (the file has moved on): {!r}".format(name, old[:60]))
        s = s.replace(old, new)
    if not dry:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(s)
    print("{}: {}".format(name, "would patch cleanly" if dry else "patched"))


if __name__ == "__main__":
    dry = "--check" in sys.argv
    patch("engine.py", ENGINE, dry)
    patch("config.py", CONFIG, dry)
