"""SeaTrader game engine.

Pure game rules with no networking or file access. All state lives in one
JSON-serialisable dict (Game.s) so saving and loading is trivial.

One turn is one month. Every player does port business at the same time, then
picks a destination (or stays). When everyone has set sail the world advances:
voyages resolve, interest accrues, markets move and the weather changes.

Everything that happens is also reported through Game.on_event, one small dict
per event (an action, a dice roll with its odds, a battle round, a month-end
snapshot). The engine does nothing with them itself; the server writes them to
the game journal (journal.py). Events marked with "do" are enough to play a
turn again exactly (replay.py).

Nothing is hard-coded here: the tables, numbers and wording all come from
config.py and strings.py through configure(), which the Admin page calls
again whenever settings are saved.
"""
import copy
import math
import random
import secrets
import time

import config as _config
import strings as _strings

# Filled in by configure(). Kept as module tables so tests and tools can read them.
GOODS, PORTS, SHIPS, REGIONS = {}, {}, {}, {}
R = {}        # rules, grouped: R["market"]["impact"] and so on
MULT = {}     # the current difficulty level's multipliers
TEXT = {}     # wording, key -> template
TOKENS = {}   # names available in every template
CFG = {}
HOME = "hongkong"


class GameError(Exception):
    """A rule was broken; the message is shown to the player."""


class _Safe(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def tx(key, **kw):
    """The wording for a key, with {names} filled in."""
    tpl = TEXT.get(key, key)
    values = _Safe(TOKENS)
    values.update(kw)
    try:
        return tpl.format_map(values)
    except (ValueError, IndexError, KeyError, AttributeError, TypeError):
        return tpl


def _project(lon, lat):
    """Chart projection shared with the browser (1000 x 600 chart)."""
    return (lon - 85.0) / 50.0 * 1000.0, (35.0 - lat) / 45.0 * 600.0


def configure(cfg=None, text=None):
    """Load settings into the engine. Safe to call while a game is running."""
    global CFG, HOME
    cfg = cfg or _config.defaults()
    CFG = cfg
    family = cfg["content"]["rating"] == "family"
    GOODS.clear()
    for key, g in cfg["goods"].items():
        d = dict(g)
        if family and g.get("family_name"):
            d["name"] = g["family_name"]
        GOODS[key] = d
    PORTS.clear()
    for key, p in cfg["ports"].items():
        d = dict(p)
        d["x"], d["y"] = [round(v, 1) for v in _project(p["lon"], p["lat"])]
        PORTS[key] = d
    SHIPS.clear()
    SHIPS.update({k: dict(v) for k, v in cfg["ships"].items()})
    REGIONS.clear()
    REGIONS.update({k: dict(v) for k, v in cfg["regions"].items()})
    R.clear()
    R.update(cfg["rules"])
    HOME = R["game"]["home"]
    MULT.clear()
    MULT.update(cfg["difficulty"]["presets"][cfg["difficulty"]["level"]])
    TEXT.clear()
    TEXT.update(text if text is not None else _strings.resolve(cfg))
    contra = [g["name"] for g in GOODS.values() if g.get("contraband")]
    joined = " & ".join(contra) if contra else tx("w.contraband")
    b = cfg["brand"]
    TOKENS.clear()
    TOKENS.update({"lender": b["lender"], "pirate": b["pirate"], "bank": b["bank"], "winner": b["winner"],
                   "title": b["title_a"] + b["title_b"], "home": PORTS[HOME]["name"],
                   "Contraband": joined, "contraband": joined.lower()})


def contraband():
    """Cargo that is always contraband (searched in every port, banned outright by a crackdown)."""
    return [k for k, g in GOODS.items() if g.get("contraband")]


def sometimes_contraband():
    """Cargo that is normally legal but a port's ban may also cover (e.g. gold), with that chance."""
    return {k: float(g.get("ban_odds") or 0) for k, g in GOODS.items()
            if not g.get("contraband") and float(g.get("ban_odds") or 0) > 0}


def names_of(goods):
    """'Opium & Gold' for a list of cargo keys (falls back to the generic word)."""
    names = [GOODS[g]["name"] for g in goods if g in GOODS]
    return " & ".join(names) if names else tx("w.contraband")


def money(n):
    n = int(round(n))
    return "{}{}{:,}".format("-" if n < 0 else "", CFG["brand"]["currency"], abs(n))


def date_label(turn):
    return "{} {}".format(tx("mon.{}".format(turn % 12)), R["game"]["start_year"] + turn // 12)


def distance(a, b):
    pa, pb = PORTS[a], PORTS[b]
    return math.hypot(pa["x"] - pb["x"], pa["y"] - pb["y"])


def rank_for(worth):
    title = ""
    for r in CFG["ranks"]:
        if worth >= r["worth"]:
            title = r["title"]
    return title or (CFG["ranks"][0]["title"] if CFG["ranks"] else "")


def loan_rate():
    return R["bank"]["loan_rate"] * MULT["interest"]


def pct(x):
    return "{:g}%".format(round(x * 100, 2))


# Which heading of the captain's report each player action belongs under.
ACTION_CAT = {"buy": "trade", "sell": "trade", "warehouse": "trade",
              "bank": "finance", "loan": "finance", "protection": "finance",
              "buy_ship": "fleet", "sell_ship": "fleet", "buy_gun": "fleet", "repair": "fleet",
              "sail": "orders", "unsail": "orders",
              "customs_declare": "finance", "customs_buyback": "finance", "customs_done": "finance",
              "settings": "host", "start": "host", "force": "host"}


class Game:
    def __init__(self, state=None, seed=None):
        self.on_event = None      # set by the server: called with one dict per event
        self._hold = None         # events queued while an action is being applied
        self._detail = None       # extra facts an action handler wants in its event
        if seed is None:
            seed = secrets.randbits(62)
        self.rng = random.Random(seed)
        if state:
            self.s = state
            self.reconcile()
            # A resumed game cannot know where the dice were, so it starts a fresh run of them.
            self.s["seed"] = seed
        else:
            self.s = self._new_state()
            self.s["seed0"] = seed
            self._reseed()
        if not self.s.get("game_id"):
            self.s["game_id"] = time.strftime("g%Y%m%d-%H%M%S-") + secrets.token_hex(2)

    # ---------------------------------------------------------- journal --
    def _ev(self, cat, kind, msg, p=None, **data):
        """Report something that happened (see the note at the top of this file)."""
        if self.on_event is None:
            return
        e = {"turn": self.s["turn"], "cat": cat, "type": kind, "msg": msg}
        if p is not None:
            e["pid"], e["who"] = p["id"], p["name"]
        e.update(data)
        if self._hold is not None:
            self._hold.append(e)
        else:
            self.on_event(e)

    def _chance(self, odds, kind, label, p=None, **data):
        """One roll of the dice against the given odds, reported with both numbers."""
        roll = self.rng.random()
        hit = roll < odds
        self._ev("dice", kind, "{}: chance {}, rolled {} - {}".format(label, pct(odds), pct(roll), "yes" if hit else "no"),
                 p, odds=round(odds, 5), roll=round(roll, 5), hit=hit, **data)
        return hit

    def _reseed(self, seed=None):
        """Start a fresh, recorded run of dice. Done at the start of every month so a
        month can be played again from its snapshot."""
        if seed is None:
            seed = self.rng.getrandbits(62)
        self.s["seed"] = seed
        self.rng = random.Random(seed)

    def firms(self):
        """Every house's position, for snapshots."""
        out = []
        for p in (self.s["players"][i] for i in self.s["order"]):
            out.append({"id": p["id"], "name": p["name"], "firm": p["firm"], "port": p["port"],
                        "cash": int(p["cash"]), "bank": int(p["bank"]), "debt": int(math.ceil(p["debt"])),
                        "worth": int(self.worth(p)), "protect": p["protect"], "wrecks": p["wrecks"],
                        "hold": self.capacity(p), "used": self.used(p), "guns": self.guns(p),
                        "cargo": dict(p["cargo"]), "wh": dict(p["wh"]),
                        "ships": [{"type": sh["type"], "name": sh["name"], "hull": sh["hull"], "guns": sh["guns"]}
                                  for sh in p["ships"]],
                        "rep": {k: int(round(v)) for k, v in p["rep"].items()}})
        return out

    def checkpoint(self, kind="checkpoint", note=""):
        """A full snapshot: every house and every price, plus the whole game state
        (without the players' seat tokens) so the month can be replayed from here."""
        if self.on_event is None:
            return
        s = self.s
        state = copy.deepcopy(s)
        for p in state["players"].values():
            p.pop("token", None)
        firms = self.firms()
        msg = "Snapshot at {}".format(date_label(s["turn"]))
        if firms:
            msg += ": " + "; ".join("{} {} in {}".format(f["name"], money(f["worth"]), PORTS[f["port"]]["name"])
                                    for f in firms)
        if note:
            msg += " ({})".format(note)
        self._ev("snapshot", kind, msg, date=date_label(s["turn"]), phase=s["phase"], seed=s["seed"],
                 firms=firms, prices={port: {g: round(v, 2) for g, v in row.items()} for port, row in s["prices"].items()},
                 weather=dict(s["weather"]), crackdown=dict(s["crackdown"]), ban_goods=copy.deepcopy(s.get("ban_goods", {})), shocks=copy.deepcopy(s["shocks"]),
                 state=state)

    # ------------------------------------------------------------ setup --
    def _new_state(self):
        s = {"phase": "lobby", "turn": 0, "years": R["game"]["default_years"], "players": {}, "order": [],
             "prices": {}, "shocks": [], "crackdown": {}, "ban_goods": {}, "weather": {}, "news": [],
             "next_id": 1, "tax_rates": {}}
        self.s = s
        s["tax_rates"] = {k: float(p.get("tax_rate", 0.0) or 0.0) for k, p in PORTS.items()}
        for port in PORTS:
            s["prices"][port] = {g: self._opening(port, g) for g in GOODS}
        self._roll_weather()
        s["news"] = [tx("n.opening")]
        return s

    def _opening(self, port, good):
        spread = R["market"]["start_spread"]
        return self._target(port, good) * self.rng.uniform(1 - spread, 1 + spread)

    def banned(self, port):
        """Cargo banned in a port right now: the always-contraband goods plus any
        sometimes-contraband goods (gold) this port's ban happens to cover. Empty with no ban."""
        if port not in self.s["crackdown"]:
            return []
        extra = self.s.get("ban_goods", {}).get(port, [])
        return contraband() + [g for g in extra if g in GOODS and g not in contraband()]

    def at_risk(self, port):
        """Cargo customs will seize if they search a ship arriving in this port."""
        return self.banned(port) if port in self.s["crackdown"] else contraband()

    def _roll_ban_goods(self, port):
        """Decide which sometimes-contraband goods a new ban in this port also covers."""
        extra = sometimes_contraband()
        picked = [g for g, odds in extra.items() if self.rng.random() < odds]
        if not picked and not contraband() and extra:
            # nothing is always contraband, so a ban must cover something
            picked = [self.rng.choice(sorted(extra))]
        self.s.setdefault("ban_goods", {})[port] = picked
        return picked

    def _target(self, port, good):
        t = GOODS[good]["base"] * PORTS[port]["mods"].get(good, 1.0)
        for sh in self.s["shocks"]:
            if sh["port"] == port and sh["good"] == good:
                t *= sh["mult"]
        if port in self.s["crackdown"] and good in self.banned(port):
            t *= R["events"]["ban_price_mult"]
        return t

    def _roll_region(self, region, month):
        """Weather level 0-3 for a region in a given month (0 = January)."""
        spec = REGIONS[region]
        typhoon, squalls = spec["typhoon"], spec["squalls"]
        for season in spec.get("seasons", ()):
            if month + 1 in season["months"]:
                typhoon, squalls = season["typhoon"], season["squalls"]
        r = self.rng.random()
        if r < typhoon:
            return 3
        if r < typhoon + squalls:
            return 2
        return 1 if self.rng.random() < 0.6 else 0

    def _roll_weather(self):
        month = self.s["turn"] % 12
        self.s["weather"] = {r: self._roll_region(r, month) for r in REGIONS}

    def reconcile(self):
        """Make a saved or running game fit the current settings (ports, cargoes
        or ship types may have been added or removed in the Admin page)."""
        s = self.s
        s.setdefault("shocks", [])
        s.setdefault("crackdown", {})
        s.setdefault("news", [])
        s["prices"] = {port: {g: (s["prices"].get(port, {}).get(g) or self._opening_safe(port, g)) for g in GOODS}
                       for port in PORTS}
        s["shocks"] = [sh for sh in s["shocks"] if sh["port"] in PORTS and sh["good"] in GOODS]
        s["crackdown"] = {k: v for k, v in s["crackdown"].items() if k in PORTS}
        extra = sometimes_contraband()
        s["ban_goods"] = {k: [g for g in v if g in extra] for k, v in (s.get("ban_goods") or {}).items()
                          if k in s["crackdown"]}
        s["weather"] = {r: int(s.get("weather", {}).get(r, 1)) for r in REGIONS}
        rates = s.get("tax_rates") if isinstance(s.get("tax_rates"), dict) else {}
        s["tax_rates"] = {port: (float(rates.get(port, PORTS[port].get("tax_rate", 0.0) or 0.0))
                                 if (PORTS[port].get("tax_rate", 0.0) or 0.0) > 0 else 0.0) for port in PORTS}
        fallback = R["wreck"]["ship"]
        for p in s["players"].values():
            if p["port"] not in PORTS:
                p["port"] = HOME
            if p.get("dest") not in PORTS:
                p["dest"] = None
            p["rep"] = {port: float(p["rep"].get(port, R["start"]["rep"])) for port in PORTS}
            p["cargo"] = {g: q for g, q in p["cargo"].items() if g in GOODS and q > 0}
            p["wh"] = {g: q for g, q in p["wh"].items() if g in GOODS and q > 0}
            p["known"] = {k: v for k, v in p.get("known", {}).items() if k in PORTS}
            tab = p.get("tab") if isinstance(p.get("tab"), dict) else {}
            p["tab"] = {k: float(tab.get(k, 0) or 0) for k in self._new_tab()}
            p["slip"] = bool(p.get("slip", False))
            p.pop("declare", None)
            cu = p.get("customs")
            if not isinstance(cu, dict) or cu.get("port") != p["port"]:
                p["customs"] = None
            else:
                cu["lines"] = [ln for ln in cu.get("lines", []) if ln.get("good") in GOODS]
            # What each cargo cost on average. Saves from before this was kept count what is held at today's price.
            basis = p.get("basis") if isinstance(p.get("basis"), dict) else {}
            held = set(p["cargo"]) | set(p["wh"])
            p["basis"] = {g: float(basis.get(g, self.s["prices"].get(p["port"], {}).get(g, GOODS[g]["base"])))
                          for g in held if g in GOODS}

            for sh in p["ships"]:
                if sh["type"] not in SHIPS:
                    sh["type"] = fallback
                spec = SHIPS[sh["type"]]
                sh["hull"] = max(1, min(sh["hull"], spec["hull"]))
                sh["guns"] = max(0, min(sh["guns"], spec["slots"]))
            over = self.used(p) - self.capacity(p)
            for g in sorted(p["cargo"], key=lambda k: GOODS[k]["base"]):
                if over <= 0:
                    break
                drop = min(over, p["cargo"][g])       # overflow goes ashore to the warehouse
                p["cargo"][g] -= drop
                p["wh"][g] = p["wh"].get(g, 0) + drop
                over -= drop
            p["cargo"] = {g: q for g, q in p["cargo"].items() if q > 0}

    def _opening_safe(self, port, good):
        return GOODS[good]["base"] * PORTS[port]["mods"].get(good, 1.0)

    # ---------------------------------------------------------- players --
    def join(self, name, firm, present=(), via=None):
        """Join the game, or take back your seat by name from a new device or address."""
        s = self.s
        raw_name, raw_firm = name, firm
        name = " ".join(str(name or "").split())[:20]
        firm = " ".join(str(firm or "").split())[:28]
        if not name:
            raise GameError(tx("e.name"))
        if not firm:
            firm = tx("w.default_firm", name=name)[:28]
        for p in s["players"].values():
            if p["name"].lower() == name.lower():
                if p["id"] in present:
                    raise GameError(tx("e.elsewhere", name=p["name"]))
                self._ev("players", "seat_reclaim", "{} took their seat back ({})".format(p["name"], p["firm"]),
                         p, via=via)
                return p["token"]
        if s["phase"] == "ended":
            raise GameError(tx("e.ended"))
        if len(s["players"]) >= R["game"]["max_players"]:
            raise GameError(tx("e.full", n=R["game"]["max_players"]))
        pid = "p{}".format(s["next_id"])
        s["next_id"] += 1
        st = R["start"]
        cash = float(int(st["cash"] * MULT["start_cash"]))
        used = {q["color"] for q in s["players"].values()}
        color = next((c for c in range(8) if c not in used), len(s["order"]) % 8)
        p = {"id": pid, "name": name, "firm": firm, "token": secrets.token_urlsafe(16),
             "color": color, "port": HOME,
             "cash": cash, "bank": 0.0, "debt": float(st["debt"]),
             "cargo": {}, "wh": {},
             "ships": [self._new_ship(st["ship"], guns=min(st["guns"], SHIPS[st["ship"]]["slots"]))],
             "rep": {port: float(st["rep"]) for port in PORTS},
             "protect": 0, "ready": False, "dest": None, "orders": "fight",
             "log": [tx("l.arrive", ship=SHIPS[st["ship"]]["name"].lower(), cash=money(cash), debt=money(st["debt"]))],
             "known": {}, "wrecks": 0, "tab": self._new_tab(), "slip": False, "basis": {}, "customs": None}
        p["rep"][HOME] = float(st["home_rep"])
        s["players"][pid] = p
        s["order"].append(pid)
        self._note_prices(p)
        ship = p["ships"][0]
        self._ev("players", "seat_new", "{} joined as {} with {} silver, {} debt and the {} {}".format(
            name, firm, money(cash), money(st["debt"]), SHIPS[ship["type"]]["name"].lower(), ship["name"]),
            p, do="join", name=str(raw_name or "")[:60], firm=str(raw_firm or "")[:60], via=via)
        return p["token"]

    def _new_ship(self, kind, guns=0, hull=None):
        names = CFG["ship_names"]
        used = {sh["name"] for p in self.s["players"].values() for sh in p["ships"]}
        free = [n for n in names if n not in used] or names
        return {"type": kind, "name": self.rng.choice(free),
                "hull": SHIPS[kind]["hull"] if hull is None else min(hull, SHIPS[kind]["hull"]), "guns": guns}

    def pid_for_token(self, token):
        for pid, p in self.s["players"].items():
            if p["token"] == token:
                return pid
        return None

    def host_id(self, present):
        """The first player in join order who is currently connected."""
        for pid in self.s["order"]:
            if pid in present:
                return pid
        return self.s["order"][0] if self.s["order"] else None

    # ---------------------------------------------------------- helpers --
    def capacity(self, p):
        return sum(SHIPS[sh["type"]]["hold"] for sh in p["ships"])

    def used(self, p):
        return sum(p["cargo"].values())

    def guns(self, p):
        return sum(sh["guns"] for sh in p["ships"])

    def spread(self, p, port):
        """Dealer's margin: wide for a stranger, narrow for a trusted house."""
        m = R["market"]
        return max(0.0, m["spread_base"] - m["spread_swing"] * (p["rep"][port] - 50.0) / 50.0)

    def quote(self, p, good, qty, side):
        """Total silver for buying or selling qty units where the player is."""
        port = p["port"]
        mid = self.s["prices"][port][good]
        k = R["market"]["impact"] * qty / GOODS[good]["depth"]
        if side == "buy":
            end = mid * (1 + k)
            return int(math.ceil(qty * (mid + end) / 2 * (1 + self.spread(p, port)))), end
        end = mid / (1 + k)
        return int(math.floor(qty * (mid + end) / 2 * (1 - self.spread(p, port)))), end

    def ship_value(self, sh):
        spec, f = SHIPS[sh["type"]], R["fleet"]
        return (f["ship_resale"] * spec["price"] * max(sh["hull"], 0) / spec["hull"]
                + sh["guns"] * f["gun_price"] * f["gun_resale"])

    def worth(self, p):
        hk = self.s["prices"][HOME]
        goods = sum(q * hk[g] for g, q in p["cargo"].items())
        goods += sum(q * hk[g] for g, q in p["wh"].items())
        ships = sum(self.ship_value(sh) for sh in p["ships"])
        return p["cash"] + p["bank"] - p["debt"] + R["market"]["worth_cargo"] * goods + ships

    def loan_limit(self, p):
        b = R["bank"]
        assets = p["cash"] + p["bank"] + sum(self.ship_value(sh) for sh in p["ships"])
        return b["loan_base"] + b["loan_per_rep"] * p["rep"][HOME] + b["loan_asset_share"] * max(assets, 0)

    def repair_rate(self, p, sh):
        f = R["fleet"]
        rate = f["repair_base"] + SHIPS[sh["type"]]["price"] / float(f["repair_price_div"])
        if not PORTS[p["port"]]["shipyard"]:
            rate *= f["repair_noyard"]
        return max(0.01, rate * (1 - f["repair_rep_discount"] * (p["rep"][p["port"]] - 50.0) / 50.0))

    def protection_cost(self, p):
        return int(max(R["liyuen"]["cost_min"], R["liyuen"]["cost_share"] * self.worth(p)))

    # ----------------------------------------------------- harbour dues --
    # The mayor of each port bills a house as it sails out: anchorage per ship, tonnage on the hold,
    # and a share of what the house spent in town this visit (shipyard, shipwright and chandler,
    # bank, moneylender, warehouse). Cargo bought and sold is not on her bill (the tax lady's, later).
    # The tally (p["tab"]) starts again each time the house drops anchor in a new port.
    @staticmethod
    def _tidy_basis(p):
        """Forget what a cargo cost once none is held, aboard or ashore. Done after every action and month,
        so a replayed game keeps exactly the same records as the live one."""
        b = p.get("basis")
        if isinstance(b, dict):
            for g in [g for g in b if not p["cargo"].get(g) and not p["wh"].get(g)]:
                del b[g]

    @staticmethod
    def _new_tab():
        return {"repair": 0.0, "yard": 0.0, "bank": 0.0, "loan": 0.0, "wh": 0.0, "profit": 0.0, "sales": 0.0}

    def _tally(self, p, key, amount):
        tab = p.setdefault("tab", self._new_tab())
        tab[key] = tab.get(key, 0.0) + max(0.0, float(amount))

    def dues(self, p):
        """The mayor's bill if the house sailed now: {"lines": [...], "total": n}."""
        d, tab = R["dues"], p.get("tab") or self._new_tab()
        ships, hold = len(p["ships"]), self.capacity(p)
        level = float(PORTS.get(p["port"], {}).get("dues", 1.0))   # this port's harbour dues level (Admin > Ports)
        lines = [
            {"key": "anchorage", "basis": ships, "rate": d["anchorage"], "amount": ships * d["anchorage"]},
            {"key": "tonnage", "basis": hold, "rate": d["tonnage"], "amount": hold / 100.0 * d["tonnage"]},
            {"key": "repair", "basis": tab["repair"], "rate": d["repair_share"], "amount": tab["repair"] * d["repair_share"]},
            {"key": "yard", "basis": tab["yard"], "rate": d["yard_share"], "amount": tab["yard"] * d["yard_share"]},
            {"key": "bank", "basis": tab["bank"], "rate": d["bank_share"], "amount": tab["bank"] * d["bank_share"]},
            {"key": "loan", "basis": tab["loan"], "rate": d["loan_share"], "amount": tab["loan"] * d["loan_share"]},
            {"key": "wh", "basis": tab["wh"], "rate": d["warehouse"], "amount": tab["wh"] / 100.0 * d["warehouse"]},
        ]
        for ln in lines:
            ln["basis"], ln["amount"] = int(round(ln["basis"])), int(math.ceil(ln["amount"] * level - 1e-9))
        lines = [ln for ln in lines if ln["amount"] > 0]
        # Standing in this port: 50 pays the full bill, 100 gets the full discount, 0 pays the same again as a surcharge.
        sub = sum(ln["amount"] for ln in lines)
        rep = float(p["rep"].get(p["port"], 50.0))
        share = d.get("rep_discount", 0.0) * (rep - 50.0) / 50.0     # + is a discount, - a surcharge
        adjust = -int(round(sub * share))
        if adjust:
            lines.append({"key": "standing", "basis": int(round(rep)), "rate": round(abs(share), 4), "amount": adjust})
        return {"lines": lines, "total": max(0, sub + adjust), "level": level, "rep": int(round(rep))}

    def _collect(self, p, amount):
        """Take money from silver; whatever is missing goes on the debt. Returns what went on the debt."""
        paid = int(min(amount, max(0.0, p["cash"])))
        p["cash"] -= paid
        if amount - paid:
            p["debt"] += amount - paid
        return amount - paid

    # ---------------------------------------------------- port authority --
    # Arriving in a port, a house declares what each line of its cargo is worth to the port's tax
    # officer (the Danish Sound Toll's rule). She then either takes her rate on the declared value,
    # buys the line outright at the declared value, or goes through the hold and finds the lie.
    # Each port has its own officer (Admin > Ports), and a rate that drifts a little every month.
    # Nothing else can be done in port until the declaration is made (see _act).
    CUSTOMS_ACTS = ("customs_declare", "customs_buyback", "customs_done")

    def tax_rate(self, port):
        """This month's rate in a port (0 in a free port)."""
        base = float(PORTS.get(port, {}).get("tax_rate", 0.0) or 0.0)
        if base <= 0:
            return 0.0
        return float((self.s.get("tax_rates") or {}).get(port, base))

    def _drift_tax_rates(self):
        """Every port's rate wanders a little each month, staying near its base."""
        c, rates = R["customs"], self.s.setdefault("tax_rates", {})
        for port in PORTS:
            base = float(PORTS[port].get("tax_rate", 0.0) or 0.0)
            if base <= 0:
                rates[port] = 0.0
                continue
            was = float(rates.get(port, base))
            lo, hi = max(c["min_rate"], base - c["range"]), min(c["max_rate"], base + c["range"])
            # Rounded to a quarter of a percent, so the officer quotes a rate a captain can remember.
            rates[port] = round(max(lo, min(hi, round((was + self.rng.uniform(-c["drift"], c["drift"])) * 400) / 400.0)), 4)
        self._ev("market", "tax_rates", "Port Authority rates this month: " + ", ".join(
            "{} {}".format(PORTS[k]["name"], pct(v)) for k, v in rates.items() if v > 0), rates=dict(rates))

    def officer_of(self, port):
        """The cast key of a port's tax officer (falls back to the Tax Collector)."""
        chars = CFG.get("characters") or {}
        cid = PORTS.get(port, {}).get("officer") or ""
        if cid in chars:
            return cid
        return "taxlady" if "taxlady" in chars else (next(iter(chars)) if chars else "")

    def _officer_ctx(self, p, port):
        """The numbers that shape this officer's odds on this visit."""
        c = R["customs"]
        st = ((CFG.get("characters") or {}).get(self.officer_of(port)) or {}).get("stats") or {}
        greed, cunning = float(st.get("greed", 5)), float(st.get("cunning", 5))
        rep = float(p["rep"].get(port, 50.0))
        swing = float(PORTS.get(port, {}).get("mood", c["mood_swing"]) or 0.0)
        return {"greed": round(max(0.2, 1 + (greed - 5) * c["greed_weight"]), 4),
                "cunning": round(max(0.2, 1 + (cunning - 5) * c["cunning_weight"]), 4),
                "rep": round(max(0.1, 1 + c["rep_audit"] * (50.0 - rep) / 50.0), 4),
                "diff": float(MULT.get("seizure", 1.0)),
                "mood": round(self.rng.uniform(1 - swing, 1 + swing), 4) if swing > 0 else 1.0,
                "greed_stat": greed}

    @staticmethod
    def customs_odds(cx, line, declared, bribe=1.0):
        """(chance she buys the line, chance she audits it) for a declared value. The player screen
        repeats this sum (player.js cxOdds) to show the odds while the sliders move."""
        c = R["customs"]
        value = max(1.0, float(line["value"]))
        r = float(declared) / value
        k = cx["greed"] * cx["mood"] * line["appetite"]
        if r > 1 + 1e-9:
            buy, audit = 0.0, 0.0                                   # over-declared: nobody buys dear
        elif r >= 1 - 1e-9:
            buy, audit = c["buy_base"] * k, 0.0                     # honest: she may still want it
        else:
            gap = 1 - r
            buy = (c["buy_base"] + c["buy_k"] * gap ** c["buy_exp"]) * k
            audit = (c["audit_base"] + c["audit_k"] * gap) * cx["cunning"] * cx["rep"] * cx["diff"] * cx["mood"] * bribe
        buy, audit = min(c["buy_cap"], max(0.0, buy)), min(c["audit_cap"], max(0.0, audit))
        if buy + audit > 0.95:
            f = 0.95 / (buy + audit)
            buy, audit = buy * f, audit * f
        return round(buy, 5), round(audit, 5)

    def _open_customs(self, p):
        """Set the Port Authority's desk for a house that has just dropped anchor."""
        port, c = p["port"], R["customs"]
        if not c["enabled"]:
            p["customs"] = None
            return
        rate = self.tax_rate(port)
        mids = self.s["prices"][port]
        lines = []
        for g in sorted(p["cargo"], key=lambda k: -p["cargo"][k] * mids[k]):
            q = int(p["cargo"][g])
            if q <= 0:
                continue
            app = max(0.3, min(3.0, float(PORTS[port]["mods"].get(g, 1.0)) ** c["appetite_power"]))
            lines.append({"good": g, "qty": q, "unit": round(mids[g], 2), "value": int(round(q * mids[g])),
                          "appetite": round(app, 4)})
        status = "declare" if rate > 0 and lines else "welcome"
        cx = self._officer_ctx(p, port)
        box = int(c["strongbox"] * self.rng.uniform(1 - c["strongbox_swing"], 1 + c["strongbox_swing"])) if status == "declare" else 0
        p["customs"] = {"port": port, "turn": self.s["turn"], "status": status, "officer": self.officer_of(port),
                        "rate": round(rate, 4), "base": float(PORTS[port].get("tax_rate", 0.0) or 0.0),
                        "free": rate <= 0, "lines": lines, "cx": cx, "box": box, "result": None}
        self._ev("finance", "customs_open", "{}: the Port Authority of {} ({}) {}".format(
            p["name"], PORTS[port]["name"], self.officer_of(port),
            "waves the house in (free port)" if rate <= 0 else "has nothing to tax (empty hold)" if not lines else
            "asks for a declaration at {}: {}; strongbox {}, mood x{}".format(
                pct(rate), ", ".join("{} {} worth {}".format(ln["qty"], GOODS[ln["good"]]["name"], money(ln["value"]))
                                     for ln in lines), money(box), cx["mood"])),
            p, port=port, rate=rate, lines=lines, cx=cx, box=box, status=status)

    def _customs_pending(self, p):
        cu = p.get("customs")
        return bool(cu) and cu.get("status") in ("declare", "verdict") and cu.get("port") == p["port"]

    def bribe_cost(self, p, declared_total):
        c, cu = R["customs"], p["customs"]
        return int(max(c["bribe_min"], math.ceil(c["bribe_share"] * cu["rate"] * declared_total)))

    def _act_customs_declare(self, p, a):
        cu, c = p.get("customs"), R["customs"]
        if not cu or cu.get("status") != "declare":
            raise GameError(tx("e.customs_none"))
        port, name, rate, cx = cu["port"], PORTS[cu["port"]]["name"], cu["rate"], cu["cx"]
        raw = a.get("values") if isinstance(a.get("values"), dict) else {}
        top = c["max_declare"]
        declared = {}
        for ln in cu["lines"]:
            try:
                v = int(round(float(raw.get(ln["good"], ln["value"]))))
            except (TypeError, ValueError):
                raise GameError(tx("e.whole_number"))
            declared[ln["good"]] = max(0, min(int(math.floor(ln["value"] * top)), v))
        total_declared = sum(declared.values())
        bribe_mult, bribe = 1.0, None
        if a.get("bribe"):
            cost = self.bribe_cost(p, total_declared)
            if cost > p["cash"]:
                raise GameError(tx("e.customs_bribe_cost", cost=money(cost)))
            honest = max(0.02, min(0.9, c["bribe_honest"] * (1 - (cx.get("greed_stat", 5) - 5) * 0.1)))
            if self._chance(honest, "customs_bribe_refused", "{}: the officer of {} refuses a sweetener of {}".format(
                    p["name"], name, money(cost)), p, cost=cost):
                bribe_mult, bribe = c["bribe_refused_mult"], {"cost": cost, "taken": False}
                self._gain_rep(p, port, -c["bribe_rep"])
            else:
                p["cash"] -= cost
                bribe_mult, bribe = 1 - c["bribe_cut"], {"cost": cost, "taken": True}
        box = int(cu.get("box", 0))
        out, tax_total, paid_in, fine_total, caught = [], 0, 0, 0, False
        for ln in sorted(cu["lines"], key=lambda x: -x["appetite"]):
            g, q, value, d = ln["good"], ln["qty"], ln["value"], declared[ln["good"]]
            buy, audit = self.customs_odds(cx, ln, d, bribe_mult)
            roll = self.rng.random()
            res = {"good": g, "qty": q, "value": value, "declared": d, "buy": buy, "audit": audit,
                   "roll": round(roll, 5), "outcome": "tax", "units": 0, "paid": 0, "tax": 0, "fine": 0, "back": False}
            if roll < buy:
                per = d / float(q)
                units = q if per <= 0 else min(q, int(box // per))
                if units > 0:
                    paid = int(round(per * units))
                    box -= paid
                    p["cash"] += paid
                    p["cargo"][g] = p["cargo"].get(g, 0) - units
                    res.update(outcome="buyout" if units == q else "partial", units=units, paid=paid,
                               cost=round(float((p.get("basis") or {}).get(g, ln["unit"])), 4))
                    paid_in += paid
                    res["tax"] = int(math.ceil(rate * per * (q - units) - 1e-9))
                else:
                    res.update(outcome="tax", empty=True)
                    res["tax"] = int(math.ceil(rate * d - 1e-9))
            elif roll < buy + audit:
                hidden = max(0, value - d)
                res["tax"] = int(math.ceil(rate * value - 1e-9))
                res["fine"] = int(math.ceil(c["fine_mult"] * rate * hidden - 1e-9))
                res["outcome"] = "caught"
                caught = True
            else:
                res["tax"] = int(math.ceil(rate * d - 1e-9))
            tax_total += res["tax"]
            fine_total += res["fine"]
            self._ev("dice", "customs_roll", "{}: {} {} worth {} declared at {} in {}: buy {}, audit {}, rolled {} - {}".format(
                p["name"], q, GOODS[g]["name"], money(value), money(d), name, pct(buy), pct(audit), pct(roll), res["outcome"]),
                p, odds=round(buy + audit, 5), roll=round(roll, 5), hit=round(roll, 5) < round(buy + audit, 5),
                buy=buy, audit=audit, **{k: res[k] for k in ("good", "outcome")})
            out.append(res)
        p["cargo"] = {k: v for k, v in p["cargo"].items() if v > 0}
        owed = self._collect(p, tax_total + fine_total)
        rep_change = 0.0
        value_total = sum(ln["value"] for ln in cu["lines"])
        if caught:
            rep_change = -c["caught_rep"]
        elif value_total and total_declared > value_total:
            over = total_declared / float(value_total) - 1
            rep_change = c["over_rep"] * min(1.0, over / max(0.01, top - 1))
        if rep_change:
            self._gain_rep(p, port, rep_change)
        cu["box"] = box
        cu["status"] = "verdict"
        cu["result"] = {"lines": out, "declared": total_declared, "value": value_total, "tax": tax_total,
                        "fine": fine_total, "paid": paid_in, "owed": owed, "caught": caught, "bribe": bribe,
                        "rep": round(rep_change, 2)}
        bought = [r for r in out if r["units"]]
        if caught:
            p["log"].append(tx("l.customs_caught", port=name, total=money(tax_total + fine_total), fine=money(fine_total)))
            self._news_later(p, tx("n.customs_caught", name=p["name"], firm=p["firm"], port=name))
        if bought:
            what = names_of([r["good"] for r in bought])
            p["log"].append(tx("l.customs_bought", port=name, goods=what.lower(), paid=money(paid_in)))
        if not caught:
            p["log"].append(tx("l.customs_paid", port=name, declared=money(total_declared), value=money(value_total),
                               tax=money(tax_total)))
        self._detail = {"port": port, "rate": rate, "declared": declared, "value": value_total, "tax": tax_total,
                        "fine": fine_total, "paid": paid_in, "owed": owed, "bribe": bribe, "rep": round(rep_change, 2),
                        "lines": out,
                        "note": "declared {} of {} at {}: tax {}{}{}{}".format(
                            money(total_declared), money(value_total), pct(rate), money(tax_total),
                            ", fine {}".format(money(fine_total)) if fine_total else "",
                            ", bought out for {}".format(money(paid_in)) if paid_in else "",
                            ", {} short, added to the debt".format(money(owed)) if owed else "")}
        if caught:
            return tx("m.customs_caught", total=money(tax_total + fine_total), fine=money(fine_total))
        if bribe and not bribe["taken"]:
            return tx("m.customs_bribe_refused")
        if bought:
            return tx("m.customs_bought", goods=names_of([r["good"] for r in bought]), paid=money(paid_in))
        if rep_change > 0:
            return tx("m.customs_over", tax=money(tax_total))
        return tx("m.customs_clean", tax=money(tax_total), declared=money(total_declared))

    def _news_later(self, p, line):
        """News the house makes in port goes out with the month's news."""
        self.s.setdefault("pending_news", []).append(line)

    def buyback_cost(self, res):
        return int(math.ceil(res["paid"] * (1 + R["customs"]["buyback_premium"]) - 1e-9))

    def _act_customs_buyback(self, p, a):
        cu = p.get("customs")
        if not cu or cu.get("status") != "verdict":
            raise GameError(tx("e.customs_none"))
        g = a.get("good")
        res = next((r for r in cu["result"]["lines"] if r["good"] == g and r["units"] and not r["back"]), None)
        if res is None:
            raise GameError(tx("e.customs_nothing_back"))
        cost = self.buyback_cost(res)
        if cost > p["cash"]:
            raise GameError(tx("e.cost", cost=money(cost), cash=money(p["cash"])))
        p["cash"] -= cost
        held = p["cargo"].get(g, 0) + p["wh"].get(g, 0)
        basis = p.setdefault("basis", {})
        # What the cargo cost the house stays what it cost before she bought it.
        was = float(res.get("cost", self.s["prices"][p["port"]][g]))
        basis[g] = (basis.get(g, was) * held + was * res["units"]) / float(held + res["units"])
        p["cargo"][g] = p["cargo"].get(g, 0) + res["units"]
        res["back"], res["back_cost"] = True, cost
        self._detail = {"good": g, "qty": res["units"], "cost": cost, "paid": res["paid"],
                        "note": "bought back {} {} for {} (she paid {})".format(res["units"], GOODS[g]["name"], money(cost), money(res["paid"]))}
        return tx("m.customs_buyback", goods=GOODS[g]["name"], cost=money(cost))

    def _act_customs_done(self, p, a):
        cu = p.get("customs")
        if not cu:
            raise GameError(tx("e.customs_none"))
        if cu.get("status") == "declare":
            raise GameError(tx("e.customs_first"))
        self._close_customs(p)
        return tx("m.customs_done", port=PORTS[p["port"]]["name"])

    def _close_customs(self, p):
        """She sends what she bought to market (prices fall for everyone there) and the desk is cleared."""
        cu = p.get("customs")
        if cu and cu.get("result") and cu.get("port") in PORTS:
            port, m = cu["port"], R["market"]
            for r in cu["result"]["lines"]:
                if r["units"] and not r["back"] and r["good"] in GOODS:
                    g = r["good"]
                    k = m["impact"] * r["units"] / GOODS[g]["depth"]
                    floor = GOODS[g]["base"] * PORTS[port]["mods"].get(g, 1.0) * m["floor"]
                    before = self.s["prices"][port][g]
                    self.s["prices"][port][g] = max(floor, before / (1 + k))
                    self._ev("market", "customs_dump", "The Port Authority of {} put {} {} on the market: {:,.2f} -> {:,.2f}".format(
                        PORTS[port]["name"], r["units"], GOODS[g]["name"], before, self.s["prices"][port][g]),
                        p, port=port, good=g, qty=r["units"], price=[round(before, 2), round(self.s["prices"][port][g], 2)])
            if p["port"] == port:
                self._note_prices(p)
        p["customs"] = None

    def _settle_customs(self, p):
        """At the month's end: a declaration nobody made is made honestly; a verdict is closed."""
        cu = p.get("customs")
        if not cu:
            return
        if cu.get("status") == "declare" and cu.get("port") == p["port"]:
            self._hold, self._detail = [], None
            cash0 = p["cash"]
            try:
                self._act_customs_declare(p, {"values": {ln["good"]: ln["value"] for ln in cu["lines"]}})
                detail = {k: v for k, v in (self._detail or {}).items() if k != "note"}
                detail["cash"] = [int(cash0), int(p["cash"])]
                held, self._hold = self._hold or [], None
                self._ev("finance", "customs_auto", "{} made no declaration in {}; it was filed honestly: {}".format(
                    p["name"], PORTS[p["port"]]["name"], (self._detail or {}).get("note", "")), p, **detail)
            finally:
                if self._hold is not None:
                    held, self._hold = self._hold, None
                for e in held:
                    if self.on_event is not None:
                        self.on_event(e)
        self._close_customs(p)

    def customs_view(self, p):
        """What the Port Authority desk shows this house (None when she is done with it)."""
        cu = p.get("customs")
        if not cu or cu.get("port") != p["port"]:
            return None
        c = R["customs"]
        ch = (CFG.get("characters") or {}).get(cu["officer"]) or {}
        out = {k: cu[k] for k in ("status", "port", "officer", "rate", "base", "free", "lines", "cx", "result")}
        out["name"], out["title"], out["line"] = ch.get("name", ""), ch.get("title", ""), ch.get("catchphrase", "")
        out["view"] = MULT.get("customs_view", "bar")
        out["rules"] = {k: c[k] for k in ("buy_base", "buy_k", "buy_exp", "audit_base", "audit_k", "buy_cap", "audit_cap",
                                          "fine_mult", "caught_rep", "max_declare", "bribe_min", "bribe_share",
                                          "bribe_cut", "bribe_refused_mult", "bribe_rep", "buyback_premium", "over_rep",
                                          "tell_curious", "tell_hungry")}
        if cu["status"] == "verdict":
            for r in out["result"]["lines"]:
                r["back_price"] = self.buyback_cost(r) if r["units"] and not r["back"] else 0
        name = PORTS[cu["port"]]["name"]
        if cu["free"]:
            out["welcome"] = tx("l.customs_free", line=out["line"], port=name)
        elif not cu["lines"]:
            out["welcome"] = tx("l.customs_empty", port=name)
        else:
            out["welcome"] = tx("l.customs_welcome", line=out["line"], port=name, rate=pct(cu["rate"]))
        return out

    def _depart(self, p, news):
        """Leaving port: pay the Mayor, or try to slip out at night without paying."""
        if not p.get("slip"):
            return self._pay_dues(p)
        d, port = R["dues"], p["port"]
        bill = self.dues(p)["total"]
        if bill <= 0:
            return self._pay_dues(p)
        if self._chance(d["slip_caught"], "slip_caught", "{}: slipping out of {} without paying {} in dues".format(
                p["name"], PORTS[port]["name"], money(bill)), p, bill=bill):
            self._gain_rep(p, port, -d["slip_rep"])
            p["log"].append(tx("l.slip_caught", port=PORTS[port]["name"]))
            news.append(tx("n.slip_caught", name=p["name"], firm=p["firm"], port=PORTS[port]["name"]))
            self._ev("finance", "slip_caught", "{} was caught slipping out of {}: pays {} times the bill, standing -{}".format(
                p["name"], PORTS[port]["name"], d["slip_mult"], d["slip_rep"]), p, port=port, bill=bill)
            return self._pay_dues(p, mult=d["slip_mult"])
        p["log"].append(tx("l.slip_away", port=PORTS[port]["name"], total=money(bill)))
        self._ev("finance", "slip_away", "{} slipped out of {} at night without paying {} in dues".format(
            p["name"], PORTS[port]["name"], money(bill)), p, port=port, bill=bill)

    def _pay_dues(self, p, mult=1.0):
        """Charge the mayor's bill as the house leaves port. Silver first; any shortfall goes on the debt."""
        bill = self.dues(p)
        total = int(math.ceil(bill["total"] * mult))
        if total <= 0:
            return
        paid = int(min(total, max(0.0, p["cash"])))
        owed = total - paid
        p["cash"] -= paid
        if owed:
            p["debt"] += owed
            p["log"].append(tx("l.dues_short", port=PORTS[p["port"]]["name"], paid=money(paid), owed=money(owed)))
        else:
            p["log"].append(tx("l.dues", port=PORTS[p["port"]]["name"], total=money(total)))
        self._ev("finance", "dues", "{}: paid the mayor of {} {} in harbour dues ({}){}".format(
            p["name"], PORTS[p["port"]]["name"], money(total),
            ", ".join("{} {}".format(ln["key"], ln["amount"]) for ln in bill["lines"]),
            "; {} short, added to the debt".format(money(owed)) if owed else ""),
            p, port=p["port"], total=total, paid=paid, owed=owed, lines=bill["lines"])

    def _gain_rep(self, p, port, amount):
        p["rep"][port] = max(0.0, min(100.0, p["rep"][port] + amount))

    def _note_prices(self, p):
        port = p["port"]
        p["known"][port] = {"turn": self.s["turn"],
                            "prices": {g: int(round(v)) for g, v in self.s["prices"][port].items()}}

    # ---------------------------------------------------------- actions --
    def act(self, pid, a, present=()):
        """Apply one player action. Returns a short confirmation message."""
        p = self.s["players"].get(pid)
        kind = str(a.get("type"))
        clean = {k: v for k, v in a.items() if k != "token"}
        port = p["port"] if p else None
        before = (p["cash"], p["bank"], p["debt"]) if p else None
        turn = self.s["turn"]
        self._hold, self._detail = [], None
        try:
            msg = self._act(pid, a, present)
        except GameError as e:
            self._hold = None
            self._ev("rejected", kind, "{} tried '{}' and was refused: {}".format(p["name"] if p else pid, kind, e),
                     p, a=clean, error=str(e))
            raise
        except Exception:
            self._hold = None
            raise
        held, self._hold = self._hold, None
        if pid in self.s["players"]:
            self._tidy_basis(p)
        data = {"do": "act", "a": clean, "present": sorted(present), "port": port, "result": msg}
        text = "{} in {}: {}".format(p["name"], PORTS[port]["name"] if port in PORTS else port, msg)
        if self._detail:
            data.update(self._detail)
            if "note" in self._detail:
                text += " [{}]".format(data.pop("note"))
        if pid in self.s["players"]:
            after = (p["cash"], p["bank"], p["debt"])
            for key, was, now in zip(("cash", "bank", "debt"), before, after):
                if int(was) != int(now):
                    data[key] = [int(was), int(now)]
                    text += " {} {} -> {}.".format({"cash": "Silver", "bank": "Bank", "debt": "Debt"}[key],
                                                    money(was), money(now))
        e = {"turn": turn, "cat": ACTION_CAT.get(kind, "orders"), "type": kind, "msg": text,
             "pid": p["id"], "who": p["name"]}
        e.update(data)
        if self.on_event is not None:
            self.on_event(e)
            for h in held:
                self.on_event(h)
        return msg

    def _act(self, pid, a, present=()):
        s = self.s
        p = s["players"].get(pid)
        if p is None:
            raise GameError(tx("e.not_in_game"))
        kind = a.get("type")
        is_host = pid == self.host_id(set(present) | {pid})

        if kind == "settings":
            if not is_host or s["phase"] != "lobby":
                raise GameError(tx("e.host_settings"))
            try:
                years = int(a.get("years", R["game"]["default_years"]))
            except (TypeError, ValueError):
                years = 0
            if years not in R["game"]["lengths"]:
                raise GameError(tx("e.years", list=", ".join(str(y) for y in R["game"]["lengths"])))
            s["years"] = years
            return tx("m.years", years=years)
        if kind == "start":
            if not is_host or s["phase"] != "lobby":
                raise GameError(tx("e.host_start"))
            return self._start()
        if kind == "force":
            if not is_host or s["phase"] != "port":
                raise GameError(tx("e.host_force"))
            self.resolve("host")
            return tx("m.forced")

        if s["phase"] != "port":
            raise GameError(tx("e.not_running"))
        if kind == "unsail":
            p["ready"], p["dest"], p["slip"] = False, None, False
            return tx("m.unsail")
        if p["ready"]:
            raise GameError(tx("e.already_sailed"))
        if kind not in self.CUSTOMS_ACTS and self._customs_pending(p):
            raise GameError(tx("e.customs_first"))

        handler = getattr(self, "_act_" + str(kind), None)
        if handler is None:
            raise GameError(tx("e.unknown_action"))
        return handler(p, a)

    def _start(self):
        s = self.s
        s["phase"] = "port"
        n = len(s["players"])
        self._ev("turn", "game_started", "The game has started: {} player{}, {} years".format(
            n, "" if n == 1 else "s", s["years"]), players=[q["name"] for q in s["players"].values()], years=s["years"])
        s["news"].insert(0, "{}: {}".format(date_label(0), tx("n.start_one" if n == 1 else "n.start_many", n=n)))
        return tx("m.begin")

    @staticmethod
    def _qty(a, key="qty"):
        try:
            q = int(a.get(key, 0))
        except (TypeError, ValueError):
            raise GameError(tx("e.whole_number"))
        if q <= 0 or q > 10_000_000:
            raise GameError(tx("e.quantity"))
        return q

    @staticmethod
    def _good(a):
        g = a.get("good")
        if g not in GOODS:
            raise GameError(tx("e.unknown_cargo"))
        return g

    def _trade_detail(self, p, g, q, total, end):
        mid, margin = self.s["prices"][p["port"]][g], self.spread(p, p["port"])
        self._detail = {"good": g, "qty": q, "total": total, "unit": round(total / float(q), 2),
                        "price": [round(mid, 2), round(end, 2)], "margin": round(margin, 4),
                        "note": "{:,.2f} each, dealer margin {}, market {:,.2f} -> {:,.2f}".format(
                            total / float(q), pct(margin), mid, end)}

    def _trade_rep(self, p, value):
        m = R["market"]
        self._gain_rep(p, p["port"], min(m["rep_trade_cap"], value / float(m["rep_per_value"])))

    def _act_buy(self, p, a):
        g, q = self._good(a), self._qty(a)
        if self.used(p) + q > self.capacity(p):
            raise GameError(tx("e.no_room", free=self.capacity(p) - self.used(p)))
        cost, end = self.quote(p, g, q, "buy")
        if cost > p["cash"]:
            raise GameError(tx("e.cost", cost=money(cost), cash=money(p["cash"])))
        self._trade_detail(p, g, q, cost, end)
        p["cash"] -= cost
        held = p["cargo"].get(g, 0) + p["wh"].get(g, 0)
        basis = p.setdefault("basis", {})
        basis[g] = (basis.get(g, 0.0) * held + cost) / float(held + q)   # average price paid per unit
        p["cargo"][g] = p["cargo"].get(g, 0) + q
        self.s["prices"][p["port"]][g] = end
        self._trade_rep(p, cost)
        return tx("m.bought", qty=q, good=GOODS[g]["name"], cost=money(cost))

    def _act_sell(self, p, a):
        g, q = self._good(a), self._qty(a)
        if p["cargo"].get(g, 0) < q:
            raise GameError(tx("e.only_have", qty=p["cargo"].get(g, 0), good=GOODS[g]["name"]))
        gain, end = self.quote(p, g, q, "sell")
        self._trade_detail(p, g, q, gain, end)
        p["cash"] += gain
        unit = p.setdefault("basis", {}).get(g, gain / float(q))      # unknown cost counts as no profit
        self._tally(p, "sales", gain)
        p["tab"]["profit"] = p["tab"].get("profit", 0.0) + (gain - unit * q)   # a loss offsets profit this visit
        p["cargo"][g] -= q
        if not p["cargo"][g]:
            del p["cargo"][g]
        self.s["prices"][p["port"]][g] = end
        self._trade_rep(p, gain)
        return tx("m.sold", qty=q, good=GOODS[g]["name"], gain=money(gain))

    def _home_only(self, p, what):
        if p["port"] != HOME:
            raise GameError(tx("e.home_only", what=what))

    def _act_bank(self, p, a):
        self._home_only(p, tx("w.the_bank"))
        q = self._qty(a, "amount")
        if a.get("op") == "deposit":
            q = min(q, int(p["cash"]))
            if q <= 0:
                raise GameError(tx("e.no_deposit"))
            p["cash"] -= q
            p["bank"] += q
            self._tally(p, "bank", q)
            return tx("m.deposited", amount=money(q))
        q = min(q, int(p["bank"]))
        if q <= 0:
            raise GameError(tx("e.account_empty"))
        p["bank"] -= q
        p["cash"] += q
        self._tally(p, "bank", q)
        return tx("m.withdrew", amount=money(q))

    def _act_loan(self, p, a):
        self._home_only(p, tx("w.the_lender"))
        q = self._qty(a, "amount")
        if a.get("op") == "borrow":
            room = int(self.loan_limit(p) - p["debt"])
            if room <= 0:
                raise GameError(tx("e.no_more_loans"))
            q = min(q, room)
            p["debt"] += q
            p["cash"] += q
            self._tally(p, "loan", q)
            return tx("m.borrowed", amount=money(q), rate="{:g}".format(round(loan_rate() * 100, 2)))
        q = min(q, int(math.ceil(p["debt"])), int(p["cash"]))
        if q <= 0:
            raise GameError(tx("e.nothing_to_repay"))
        p["debt"] = max(0.0, p["debt"] - q)
        p["cash"] -= q
        if p["debt"] < 1:
            p["debt"] = 0.0
        self._tally(p, "loan", q)
        return tx("m.repaid", amount=money(q))

    def _act_warehouse(self, p, a):
        self._home_only(p, tx("w.the_warehouse"))
        g, q = self._good(a), self._qty(a)
        if a.get("op") == "store":
            q = min(q, p["cargo"].get(g, 0), R["fleet"]["warehouse_cap"] - sum(p["wh"].values()))
            if q <= 0:
                raise GameError(tx("e.nothing_to_store"))
            p["cargo"][g] -= q
            if not p["cargo"][g]:
                del p["cargo"][g]
            p["wh"][g] = p["wh"].get(g, 0) + q
            self._tally(p, "wh", q)
            return tx("m.stored", qty=q, good=GOODS[g]["name"])
        q = min(q, p["wh"].get(g, 0), self.capacity(p) - self.used(p))
        if q <= 0:
            raise GameError(tx("e.nothing_to_load"))
        p["wh"][g] -= q
        if not p["wh"][g]:
            del p["wh"][g]
        p["cargo"][g] = p["cargo"].get(g, 0) + q
        self._tally(p, "wh", q)
        return tx("m.loaded", qty=q, good=GOODS[g]["name"])

    def _act_buy_ship(self, p, a):
        kind = a.get("ship")
        if kind not in SHIPS:
            raise GameError(tx("e.unknown_ship"))
        if not PORTS[p["port"]]["shipyard"]:
            raise GameError(tx("e.no_shipyard", port=PORTS[p["port"]]["name"]))
        if len(p["ships"]) >= R["fleet"]["max_fleet"]:
            raise GameError(tx("e.fleet_limit", n=R["fleet"]["max_fleet"]))
        price = SHIPS[kind]["price"]
        if price > p["cash"]:
            raise GameError(tx("e.ship_cost", ship=SHIPS[kind]["name"], price=money(price)))
        p["cash"] -= price
        self._tally(p, "yard", price)
        sh = self._new_ship(kind)
        p["ships"].append(sh)
        self._gain_rep(p, p["port"], R["fleet"]["ship_rep"])
        self._detail = {"ship": kind, "name": sh["name"], "price": price}
        return tx("m.ship_joined", ship=SHIPS[kind]["name"], name=sh["name"])

    def _ship(self, p, a):
        try:
            i = int(a.get("index"))
            if i < 0:
                raise IndexError
            return p["ships"][i]
        except (TypeError, ValueError, IndexError):
            raise GameError(tx("e.no_such_ship"))

    def _act_sell_ship(self, p, a):
        sh = self._ship(p, a)
        if not PORTS[p["port"]]["shipyard"]:
            raise GameError(tx("e.no_shipyard", port=PORTS[p["port"]]["name"]))
        if len(p["ships"]) <= 1:
            raise GameError(tx("e.last_ship"))
        if self.capacity(p) - SHIPS[sh["type"]]["hold"] < self.used(p):
            raise GameError(tx("e.unload_first"))
        value = int(self.ship_value(sh))
        p["ships"].remove(sh)
        p["cash"] += value
        self._detail = {"ship": sh["type"], "name": sh["name"], "value": value}
        return tx("m.ship_sold", name=sh["name"], value=money(value))

    def _act_buy_gun(self, p, a):
        sh = self._ship(p, a)
        price = R["fleet"]["gun_price"]
        if sh["guns"] >= SHIPS[sh["type"]]["slots"]:
            raise GameError(tx("e.no_more_guns", name=sh["name"]))
        if price > p["cash"]:
            raise GameError(tx("e.gun_cost", price=money(price)))
        p["cash"] -= price
        self._tally(p, "yard", price)
        sh["guns"] += 1
        return tx("m.gun_mounted", name=sh["name"])

    def _act_repair(self, p, a):
        ships = p["ships"] if a.get("index") in (None, "all") else [self._ship(p, a)]
        spent = fixed = 0
        for sh in ships:
            need = SHIPS[sh["type"]]["hull"] - sh["hull"]
            rate = self.repair_rate(p, sh)
            points = int(min(need, (p["cash"] - spent) // rate))
            if points > 0:
                spent += int(math.ceil(points * rate))
                sh["hull"] += points
                fixed += points
        if not fixed:
            raise GameError(tx("e.nothing_to_repair"))
        p["cash"] = max(0.0, p["cash"] - spent)
        self._tally(p, "repair", spent)
        self._detail = {"points": fixed, "cost": spent, "note": "{} hull points".format(fixed)}
        return tx("m.repaired", cost=money(spent))

    def _act_protection(self, p, a):
        self._home_only(p, tx("w.the_agent"))
        if p["protect"] > R["liyuen"]["renew_at"]:
            raise GameError(tx("e.protect_content", months=p["protect"]))
        cost = self.protection_cost(p)
        if cost > p["cash"]:
            raise GameError(tx("e.protect_cost", cost=money(cost)))
        p["cash"] -= cost
        p["protect"] = R["liyuen"]["protect_months"]
        return tx("m.protected", cost=money(cost), months=p["protect"])

    def _act_sail(self, p, a):
        dest = a.get("dest")
        if dest is not None and dest not in PORTS:
            raise GameError(tx("e.unknown_port"))
        if dest == p["port"]:
            dest = None
        orders = a.get("orders", p["orders"])
        if orders not in ("fight", "run"):
            raise GameError(tx("e.orders"))
        p["orders"], p["dest"], p["ready"] = orders, dest, True
        p["slip"] = bool(a.get("slip")) and dest is not None    # leave at night without paying the Mayor
        self._detail = {"dest": dest, "orders": orders, "slip": p["slip"],
                        "note": "standing orders: " + orders + (", slipping out without paying dues" if p["slip"] else "")}
        if dest:
            return tx("m.slip" if p["slip"] else "m.sail", port=PORTS[dest]["name"])
        return tx("m.stay")

    # ------------------------------------------------------------ admin --
    def admin(self, op, a):
        """Actions from the Admin page. They skip the usual host and phase checks."""
        s = self.s
        turn = s["turn"]
        target = s["players"].get(a.get("pid"))
        was = {}
        if target and op == "adjust":
            was = {"cash": int(target["cash"]), "bank": int(target["bank"]), "debt": int(math.ceil(target["debt"])),
                   "protect": target["protect"], "port": target["port"]}
        elif op == "price" and a.get("port") in PORTS and a.get("good") in GOODS:
            was = {"value": round(s["prices"][a["port"]][a["good"]], 2)}
        elif op == "weather":
            was = {"level": s["weather"].get(a.get("region"))}
        elif op == "ban":
            was = {"turns": s["crackdown"].get(a.get("port"), 0)}
        elif op == "years":
            was = {"years": s["years"]}
        self._hold = []
        try:
            msg = self._admin(op, a)
        except GameError as e:
            self._hold = None
            self._ev("rejected", "admin_" + str(op), "Admin tried '{}' and was refused: {}".format(op, e),
                     a=dict(a), error=str(e))
            raise
        except Exception:
            self._hold = None
            raise
        held, self._hold = self._hold, None
        clean = {k: v for k, v in a.items() if k != "op"}
        text = "Admin: {}".format(msg)
        detail = ", ".join("{} {}".format(k, v) for k, v in clean.items() if v not in (None, ""))
        if detail:
            text += " [{}]".format(detail)
        if was:
            text += " (was: {})".format(", ".join("{} {}".format(k, v) for k, v in was.items()))
        e = {"turn": turn, "cat": "admin", "type": "admin_" + str(op), "msg": text, "do": "admin",
             "op": op, "a": clean, "was": was, "result": msg}
        if target:
            e["pid"], e["who"] = target["id"], target["name"]
        if self.on_event is not None:
            self.on_event(e)
            for h in held:
                self.on_event(h)
        return msg

    def _admin(self, op, a):
        s = self.s

        def player():
            p = s["players"].get(a.get("pid"))
            if p is None:
                raise GameError("No such player.")
            return p

        def number(key, lo, hi):
            try:
                v = float(a.get(key))
            except (TypeError, ValueError):
                raise GameError("Enter a number.")
            if not lo <= v <= hi:
                raise GameError("That number is out of range.")
            return v

        if op == "start":
            if s["phase"] != "lobby":
                raise GameError("The game has already started.")
            if not s["players"]:
                raise GameError("Nobody has joined yet.")
            return self._start()
        if op == "force":
            if s["phase"] != "port":
                raise GameError("The game is not in progress.")
            self.resolve("admin")
            return "Turn ended."
        if op == "years":
            s["years"] = int(number("years", 1, 100))
            if s["phase"] == "ended" and s["turn"] < s["years"] * 12:
                s["phase"] = "port"
            elif s["phase"] == "port" and s["turn"] >= s["years"] * 12:
                self._finish()
            return "Game length set to {} years.".format(s["years"])
        if op == "finish":
            if s["phase"] != "port":
                raise GameError("The game is not in progress.")
            self._finish()
            return "The game has been ended."
        if op == "kick":
            p = player()
            del s["players"][p["id"]]
            s["order"].remove(p["id"])
            return "{} has been removed.".format(p["name"])
        if op == "adjust":
            p = player()
            for key in ("cash", "bank", "debt"):
                if a.get(key) not in (None, ""):
                    p[key] = number(key, 0, 1e12)
            if a.get("protect") not in (None, ""):
                p["protect"] = int(number("protect", 0, 600))
            if a.get("port") and a["port"] != p["port"]:
                if a["port"] not in PORTS:
                    raise GameError("No such port.")
                p["port"], p["ready"], p["dest"] = a["port"], False, None
                self._note_prices(p)
            return "{} updated.".format(p["name"])
        if op == "news":
            text = " ".join(str(a.get("text") or "").split())[:240]
            if not text:
                raise GameError("Write the news first.")
            s["news"].insert(0, "{}: {}".format(date_label(s["turn"]), text))
            s["news"] = s["news"][:40]
            return "News posted."
        if op == "price":
            if a.get("port") not in PORTS or a.get("good") not in GOODS:
                raise GameError("No such port or cargo.")
            s["prices"][a["port"]][a["good"]] = number("value", 0.01, 1e9)
            for p in s["players"].values():
                if p["port"] == a["port"]:
                    self._note_prices(p)
            return "Price set."
        if op == "weather":
            if a.get("region") not in REGIONS:
                raise GameError("No such sea.")
            s["weather"][a["region"]] = int(number("level", 0, 3))
            return "Forecast changed."
        if op == "ban":
            if a.get("port") not in PORTS:
                raise GameError("No such port.")
            turns = int(number("turns", 0, 120))
            if turns:
                if a["port"] not in s["crackdown"]:
                    self._roll_ban_goods(a["port"])
                s["crackdown"][a["port"]] = turns
            else:
                s["crackdown"].pop(a["port"], None)
                s.setdefault("ban_goods", {}).pop(a["port"], None)
            return "Ban set." if turns else "Ban lifted."
        raise GameError("Unknown admin action.")

    # ------------------------------------------------------ turn engine --
    def maybe_advance(self, present):
        """Advance when every connected player has given orders."""
        s = self.s
        if s["phase"] != "port":
            return False
        here = [s["players"][pid] for pid in s["order"] if pid in present]
        if here and all(p["ready"] for p in here):
            self.resolve("all_ready", present)
            return True
        return False

    def resolve(self, cause="all_ready", present=None):
        s, rng = self.s, self.rng
        news = []
        label = date_label(s["turn"])
        b = R["bank"]
        why = {"all_ready": "everyone present has given orders", "host": "the host ended the month",
               "admin": "the admin ended the month"}.get(cause, cause)
        orders = {q["id"]: {"name": q["name"], "ready": q["ready"], "dest": q["dest"], "orders": q["orders"],
                            "present": None if present is None else q["id"] in present}
                  for q in (s["players"][i] for i in s["order"])}
        self._ev("turn", "turn_resolve", "Resolving {} ({})".format(label, why), do="resolve", cause=cause,
                 date=label, orders=orders)
        # The forecast is only sometimes wrong.
        actual = dict(s["weather"])
        wx = [tx("wx.{}".format(i)) for i in range(4)]
        for region in actual:
            roll = rng.random()
            wrong = roll > R["weather"]["forecast_accuracy"]
            if wrong:
                actual[region] = self._roll_region(region, s["turn"] % 12)
            self._ev("weather", "weather", "{}: forecast {}, actual {} (forecast held if roll {} was at most {}{})".format(
                REGIONS[region].get("name", region), wx[s["weather"][region]], wx[actual[region]], pct(roll),
                pct(R["weather"]["forecast_accuracy"]), "; it did not, weather rolled again" if wrong else ""),
                region=region, forecast=s["weather"][region], actual=actual[region], roll=round(roll, 5),
                accuracy=R["weather"]["forecast_accuracy"], rerolled=wrong)
        players = [s["players"][pid] for pid in s["order"]]
        rng.shuffle(players)
        if players:
            self._ev("turn", "order", "Voyages resolve in this order: " + ", ".join(q["name"] for q in players),
                     order=[q["id"] for q in players])
        news.extend(s.pop("pending_news", None) or [])
        for p in players:
            p["log"] = []
            self._settle_customs(p)
        self._drift_tax_rates()          # the new month's rates, quoted to every ship that arrives
        for p in players:
            if p["ready"] and p["dest"]:
                self._depart(p, news)
                self._voyage(p, actual, news)
            else:
                p["log"].append(tx("l.anchor", port=PORTS[p["port"]]["name"]))
                self._ev("voyage", "anchor", "{} stayed at anchor in {}{}".format(
                    p["name"], PORTS[p["port"]]["name"], "" if p["ready"] else " (gave no orders)"), p,
                    port=p["port"], gave_orders=p["ready"])
            p["ready"], p["dest"], p["slip"] = False, None, False

        for p in players:
            bank0, debt0 = p["bank"], p["debt"]
            if p["bank"] > 0:
                p["bank"] *= 1 + b["bank_rate"]
            if p["debt"] > 0:
                p["debt"] *= 1 + loan_rate()
                if p["debt"] > self.loan_limit(p) * b["debt_warn_mult"]:
                    self._gain_rep(p, HOME, -b["debt_rep_penalty"])
                    p["log"].append(tx("l.collectors"))
                    self._ev("finance", "collectors", "{}: debt {} is over {} times the loan limit {}; standing in {} "
                             "fell by {}".format(p["name"], money(p["debt"]), b["debt_warn_mult"],
                                                 money(self.loan_limit(p)), PORTS[HOME]["name"], b["debt_rep_penalty"]), p)
            if bank0 > 0 or debt0 > 0:
                self._ev("finance", "interest", "{}: bank interest +{} at {}, loan interest +{} at {}".format(
                    p["name"], money(p["bank"] - bank0), pct(b["bank_rate"]), money(p["debt"] - debt0), pct(loan_rate())),
                    p, bank=[round(bank0, 2), round(p["bank"], 2)], debt=[round(debt0, 2), round(p["debt"], 2)])
            if p["protect"] > 0:
                p["protect"] -= 1
                if p["protect"] == 0:
                    p["log"].append(tx("l.protect_lapsed"))
                    self._ev("finance", "protect_lapsed", "{}: protection has run out".format(p["name"]), p)
            if p["cash"] > b["mug_threshold"] and self._chance(b["mug_chance"], "robbery", "{}: robbed ashore (carrying over {})".format(
                    p["name"], money(b["mug_threshold"])), p):
                lost = int(p["cash"] * rng.uniform(b["mug_min"], b["mug_max"]))
                p["cash"] -= lost
                p["log"].append(tx("l.robbed", lost=money(lost)))
                self._ev("finance", "robbed", "{} was robbed of {}".format(p["name"], money(lost)), p, lost=lost)

        self._move_markets(news)
        for p in players:
            self._tidy_basis(p)
        s["turn"] += 1
        self._roll_weather()
        for p in players:
            self._note_prices(p)
        for n in news:
            self._ev("news", "news", "News: " + n, turn=s["turn"] - 1)
        s["news"] = ["{}: {}".format(label, n) for n in news] + s["news"]
        s["news"] = s["news"][:40]
        if s["turn"] >= s["years"] * 12:
            self._finish()
        self._reseed()
        self.checkpoint("turn_begin")

    def _finish(self):
        s = self.s
        s["phase"] = "ended"
        ranked = sorted(s["players"].values(), key=self.worth, reverse=True)
        if ranked:
            s["news"].insert(0, "{}: {}".format(date_label(s["turn"]), tx(
                "n.game_over", name=ranked[0]["name"], firm=ranked[0]["firm"], worth=money(self.worth(ranked[0])))))
        self._ev("turn", "game_over", "The game is over. " + ("Final standings: " + "; ".join(
            "{}. {} ({}) {}".format(i + 1, q["name"], q["firm"], money(self.worth(q))) for i, q in enumerate(ranked))
            if ranked else "Nobody was playing."),
            standings=[{"id": q["id"], "name": q["name"], "firm": q["firm"], "worth": int(self.worth(q))} for q in ranked])

    def _move_markets(self, news):
        s, rng, ev, m = self.s, self.rng, R["events"], R["market"]
        s["shocks"] = [dict(sh, turns=sh["turns"] - 1) for sh in s["shocks"] if sh["turns"] > 1]
        for port in list(s["crackdown"]):
            s["crackdown"][port] -= 1
            if s["crackdown"][port] <= 0:
                goods = self.banned(port)
                del s["crackdown"][port]
                s.setdefault("ban_goods", {}).pop(port, None)
                what = names_of(goods)
                news.append(tx("n.ban_lifted", port=PORTS[port]["name"], contraband=what.lower(), Contraband=what))
                self._ev("market", "ban_lifted", "The ban on {} in {} has ended".format(what, PORTS[port]["name"]),
                         port=port, goods=goods)
        before = {port: dict(row) for port, row in s["prices"].items()}
        if self._chance(ev["shock_chance"], "shock", "Glut or shortage this month"):
            port, good = rng.choice(list(PORTS)), rng.choice(list(GOODS))
            mult = rng.choice(ev["shock_mults"])
            s["shocks"].append({"port": port, "good": good, "mult": mult,
                                "turns": rng.randint(ev["shock_min_turns"], ev["shock_max_turns"])})
            s["prices"][port][good] *= mult ** 0.7
            self._ev("market", "shock", "{} of {} in {}: target price x{} for {} months".format(
                "Shortage" if mult > 1 else "Glut", GOODS[good]["name"], PORTS[port]["name"], mult,
                s["shocks"][-1]["turns"]), port=port, good=good, mult=mult, turns=s["shocks"][-1]["turns"])
            news.append(tx("n.scarce" if mult > 1 else "n.glut", good=GOODS[good]["name"],
                           good_lower=GOODS[good]["name"].lower(), port=PORTS[port]["name"]))
        if (contraband() or sometimes_contraband()) and self._chance(ev["ban_chance"], "ban", "A port bans contraband this month"):
            open_ports = [k for k in PORTS if not PORTS[k].get("no_ban") and k not in s["crackdown"]]
            if open_ports:
                port = rng.choice(open_ports)
                s["crackdown"][port] = rng.randint(ev["ban_min_turns"], ev["ban_max_turns"])
                self._roll_ban_goods(port)
                goods = self.banned(port)
                what = names_of(goods)
                news.append(tx("n.ban", port=PORTS[port]["name"], contraband=what.lower(), Contraband=what))
                self._ev("market", "ban", "{} bans {} for {} months".format(
                    PORTS[port]["name"], what, s["crackdown"][port]), port=port, turns=s["crackdown"][port], goods=goods)
        for port in PORTS:
            for g, spec in GOODS.items():
                base = spec["base"] * PORTS[port]["mods"].get(g, 1.0)
                price = s["prices"][port][g]
                price += m["reversion"] * (self._target(port, g) - price)
                price *= math.exp(rng.gauss(0, spec["vol"] * m["vol_mult"]))
                s["prices"][port][g] = max(m["floor"] * base, min(m["ceiling"] * base, price))
        moves = sorted(((s["prices"][port][g] / before[port][g] - 1, port, g) for port in PORTS for g in GOODS
                        if before[port].get(g)), key=lambda t: -abs(t[0]))[:6]
        self._ev("market", "prices", "Markets moved. Biggest changes: " + "; ".join(
            "{} in {} {:+.0%} ({:,.0f} -> {:,.0f})".format(GOODS[g]["name"], PORTS[port]["name"], ch, before[port][g],
                                                           s["prices"][port][g]) for ch, port, g in moves),
            movers=[{"port": port, "good": g, "change": round(ch, 4), "from": round(before[port][g], 2),
                     "to": round(s["prices"][port][g], 2)} for ch, port, g in moves])

    # ---------------------------------------------------------- voyages --
    def _voyage(self, p, actual, news):
        rng, log = self.rng, p["log"]
        w, pi, ly, cb = R["weather"], R["pirates"], R["liyuen"], R["contraband"]
        origin, dest = p["port"], p["dest"]
        risk = max(w["risk_min"], min(w["risk_max"], distance(origin, dest) / float(w["risk_div"])))
        level = max(actual[PORTS[origin]["region"]], actual[PORTS[dest]["region"]])
        log.append(tx("l.sailed", origin=PORTS[origin]["name"], dest=PORTS[dest]["name"],
                      weather=tx("l.sea.{}".format(level))))
        who = p["name"]
        self._ev("voyage", "sailed", "{} sailed {} -> {}: {} ship{}, {} guns, hold {}/{}, orders {}, sea {}, "
                 "distance risk x{:.2f}{}".format(
                     who, PORTS[origin]["name"], PORTS[dest]["name"], len(p["ships"]), "" if len(p["ships"]) == 1 else "s",
                     self.guns(p), self.used(p), self.capacity(p), p["orders"], tx("wx.{}".format(level)), risk,
                     ", protected for {} more months".format(p["protect"]) if p["protect"] > 0 else ", no protection"),
                 p, origin=origin, dest=dest, sea=level, risk=round(risk, 4), orders=p["orders"], protect=p["protect"],
                 cargo=dict(p["cargo"]), cash=int(p["cash"]),
                 ships=[{"type": sh["type"], "name": sh["name"], "hull": sh["hull"], "guns": sh["guns"]} for sh in p["ships"]])

        storm = w["storm_chance"][level] * min(risk, 1.4) * MULT["storms"]
        if self._chance(storm, "storm", "{}: caught in a {}".format(who, "typhoon" if level == 3 else "storm"), p):
            lo, hi = (w["typhoon_dmg_min"], w["typhoon_dmg_max"]) if level == 3 else (w["storm_dmg_min"], w["storm_dmg_max"])
            hits = []
            for sh in p["ships"]:
                hit = rng.randint(lo, hi)
                took = int(hit * w["fast_dmg_mult"]) if SHIPS[sh["type"]]["fast"] else hit
                sh["hull"] -= took
                hits.append({"name": sh["name"], "damage": took, "hull": sh["hull"]})
            log.append(tx("l.typhoon" if level == 3 else "l.storm"))
            self._ev("voyage", "storm_damage", "{}: {} damage ({}-{} per ship): {}".format(
                who, "typhoon" if level == 3 else "storm", lo, hi,
                ", ".join("{} -{} (hull {})".format(h["name"], h["damage"], h["hull"]) for h in hits)), p, hits=hits)
            self._check_sunk(p, tx("l.how_foundered"))
            others = [k for k in PORTS if k not in (origin, dest)]
            if p["ships"] and level == 3 and others and self._chance(w["offcourse"], "offcourse",
                                                                    "{}: blown off course".format(who), p):
                dest = rng.choice(others)
                log.append(tx("l.offcourse", port=PORTS[dest]["name"]))
                self._ev("voyage", "offcourse", "{} was blown off course to {}".format(who, PORTS[dest]["name"]), p, dest=dest)

        if p["ships"] and self._chance(pi["chance"] * risk * MULT["pirates"], "pirates",
                                       "{}: pirate attack".format(who), p):
            top = max(pi["fleet_min"], pi["fleet_base"] + self.capacity(p) // pi["fleet_per_hold"])
            n = int(rng.randint(pi["fleet_min"], top) * risk)
            n = max(1, min(n, pi["fleet_max"]))
            if p["protect"] > 0 and self._chance(ly["protect_save"], "protection",
                                                 "{}: {}'s fleet drives off {} pirate junks".format(who, TOKENS["pirate"], n), p):
                log.append(tx("l.driven_off", n=n))
            else:
                self._battle(p, n, tx("w.pirate_junks"), pi["hit"], (pi["dmg_min"], pi["dmg_max"]))

        if p["ships"] and p["protect"] <= 0 and self._chance(ly["chance"] * risk * MULT["pirates"], "pirate_lord",
                                                              "{}: found by {}'s fleet (no protection)".format(who, TOKENS["pirate"]), p):
            n = min(ly["fleet_max"], ly["fleet_base"] + self.capacity(p) // ly["fleet_per_hold"])
            log.append(tx("l.lord_found"))
            self._battle(p, n, tx("w.war_junks"), ly["hit"], (ly["dmg_min"], ly["dmg_max"]))

        if not p["ships"]:
            self._shipwreck(p, news)
            return

        p["port"] = dest
        p["tab"] = self._new_tab()
        log.append(tx("l.anchored", port=PORTS[dest]["name"]))
        self._ev("voyage", "arrived", "{} anchored in {}: {} ship{}, hull {}, hold {}/{}, silver {}".format(
            who, PORTS[dest]["name"], len(p["ships"]), "" if len(p["ships"]) == 1 else "s",
            "/".join(str(sh["hull"]) for sh in p["ships"]), self.used(p), self.capacity(p), money(p["cash"])),
            p, port=dest, cargo=dict(p["cargo"]), cash=int(p["cash"]))
        risky = self.at_risk(dest)
        held = sum(p["cargo"].get(g, 0) for g in risky)
        if held:
            banned = dest in self.s["crackdown"]
            chance = (cb["seize_banned"] - cb["seize_rep_relief"] * p["rep"][dest]) if banned else cb["seize_chance"]
            if self._chance(chance * MULT["seizure"], "seizure", "{}: customs search in {} ({} units of contraband, {}, standing {})".format(
                    who, PORTS[dest]["name"], held, "banned here" if banned else "no ban", int(round(p["rep"][dest]))), p):
                fine = int(min(p["cash"], held * cb["fine_per_unit"]))
                taken = {g: p["cargo"].pop(g) for g in risky if p["cargo"].get(g)}
                what = names_of(list(taken))
                p["cash"] -= fine
                self._gain_rep(p, dest, -cb["rep_penalty"])
                log.append(tx("l.seized", qty=held, fine=money(fine), contraband=what.lower(), Contraband=what))
                news.append(tx("n.caught", name=p["name"], firm=p["firm"], port=PORTS[dest]["name"],
                               contraband=what.lower(), Contraband=what))
                self._ev("voyage", "seized", "{}: customs in {} seized {} units of {} and fined {}; standing -{}".format(
                    who, PORTS[dest]["name"], held, what, money(fine), cb["rep_penalty"]), p, qty=held, fine=fine,
                    port=dest, goods=taken)
        self._open_customs(p)

    def _battle(self, p, n, label, hit, dmg):
        rng, log, pi = self.rng, p["log"], R["pirates"]
        orders = p["orders"]
        if orders == "fight" and self.guns(p) == 0:
            orders = "run"
            log.append(tx("l.attack_noguns", n=n, enemy=label))
        else:
            log.append(tx("l.attack", n=n, enemy=label, orders=tx("w.fight" if orders == "fight" else "w.run")))
        pirates = [pi["hp"]] * n
        fast = all(SHIPS[sh["type"]]["fast"] for sh in p["ships"])
        hull_before = sum(sh["hull"] for sh in p["ships"])
        who = p["name"]
        self._ev("battle", "battle", "{} attacked by {} {}: orders {}{}, {} guns, hull {}; enemy hits {} per junk per "
                 "round for {}-{}".format(who, n, label, orders, " (no guns, so running)" if orders != p["orders"] else "",
                                          self.guns(p), "/".join(str(sh["hull"]) for sh in p["ships"]), pct(hit), dmg[0], dmg[1]),
                 p, enemy=label, count=n, orders=orders, guns=self.guns(p), hit=hit, dmg=list(dmg))
        for rnd in range(1, pi["rounds"] + 1):
            s = "" if rnd == 1 else "s"
            if orders == "fight":
                shots = hits = 0
                for _ in range(self.guns(p)):
                    if pirates:
                        shots += 1
                    if pirates and rng.random() < pi["gun_hit"]:
                        hits += 1
                        pirates[-1] -= 1
                        if pirates[-1] <= 0:
                            pirates.pop()
                self._ev("battle", "round", "{} round {}: {} shots at {} each, {} hit, {} of {} enemy left".format(
                    who, rnd, shots, pct(pi["gun_hit"]), hits, len(pirates), n), p, round=rnd, shots=shots, hits=hits,
                    enemy_left=len(pirates))
                if not pirates:
                    booty = int(n * rng.randint(pi["booty_min"], pi["booty_max"])
                                * (1 + self.s["turn"] / float(pi["booty_growth"])))
                    p["cash"] += booty
                    log.append(tx("l.sank_all", n=n, rounds=rnd, s=s, booty=money(booty)))
                    self._ev("battle", "won", "{} sank all {} in {} round{} and took {} in booty".format(
                        who, n, rnd, s, money(booty)), p, rounds=rnd, booty=booty)
                    break
            elif self._chance(pi["run_base"] + (pi["run_fast"] if fast else 0) + pi["run_round"] * rnd, "escape",
                              "{} round {}: outrun them{}".format(who, rnd, " (every ship is fast)" if fast else ""), p, round=rnd):
                log.append(tx("l.outran", rounds=rnd, s=s))
                pirates = []
                break
            taken_round = []
            for _ in pirates:
                if p["ships"] and rng.random() < hit:
                    target = rng.choice(p["ships"])
                    points = rng.randint(*dmg)
                    target["hull"] -= points
                    taken_round.append({"name": target["name"], "damage": points, "hull": target["hull"]})
            if pirates:
                self._ev("battle", "enemy_fire", "{} round {}: {} enemy fired, {} hit{}".format(
                    who, rnd, len(pirates), len(taken_round), ": " + ", ".join(
                        "{} -{} (hull {})".format(h["name"], h["damage"], h["hull"]) for h in taken_round) if taken_round else ""),
                    p, round=rnd, enemy=len(pirates), hits=taken_round)
            self._check_sunk(p, tx("l.how_sunk"))
            if not p["ships"]:
                return
        else:
            if orders == "fight":
                log.append(tx("l.long_fight", n=n - len(pirates)))
                self._ev("battle", "broke_off", "{}: enemy broke off after {} rounds; {} of {} sunk".format(
                    who, pi["rounds"], n - len(pirates), n), p, sunk=n - len(pirates))
            else:
                lost = {g: int(q * rng.uniform(pi["plunder_min"], pi["plunder_max"])) for g, q in p["cargo"].items()}
                for g, q in lost.items():
                    p["cargo"][g] -= q
                p["cargo"] = {g: q for g, q in p["cargo"].items() if q > 0}
                log.append(tx("l.plundered", qty=sum(lost.values())))
                self._ev("battle", "plundered", "{} could not get away in {} rounds and was plundered of {} units: {}".format(
                    who, pi["rounds"], sum(lost.values()),
                    ", ".join("{} {}".format(q, GOODS[g]["name"]) for g, q in lost.items() if q) or "nothing"),
                    p, lost={g: q for g, q in lost.items() if q})
        taken = hull_before - sum(sh["hull"] for sh in p["ships"])
        if taken > 0 and p["ships"]:
            log.append(tx("l.damage", points=taken))

    def _check_sunk(self, p, how):
        for sh in [sh for sh in p["ships"] if sh["hull"] <= 0]:
            p["ships"].remove(sh)
            p["log"].append(tx("l.ship_lost", ship=SHIPS[sh["type"]]["name"], name=sh["name"], how=how))
            self._ev("voyage", "ship_lost", "{} lost the {} {} ({} guns): {}".format(
                p["name"], SHIPS[sh["type"]]["name"].lower(), sh["name"], sh["guns"], how), p,
                ship=sh["type"], name=sh["name"], guns=sh["guns"])
        over = self.used(p) - self.capacity(p)
        if over > 0 and p["ships"]:
            # The crew saves the most valuable cargo first.
            gone = {}
            for g in sorted(p["cargo"], key=lambda k: GOODS[k]["base"]):
                drop = min(over, p["cargo"][g])
                p["cargo"][g] -= drop
                gone[g] = drop
                over -= drop
                if over <= 0:
                    break
            p["cargo"] = {g: q for g, q in p["cargo"].items() if q > 0}
            p["log"].append(tx("l.cargo_lost"))
            self._ev("voyage", "cargo_lost", "{} lost cargo that no longer fits: {}".format(
                p["name"], ", ".join("{} {}".format(q, GOODS[g]["name"]) for g, q in gone.items())), p, lost=gone)

    def _shipwreck(self, p, news):
        wk = R["wreck"]
        lost = int(p["cash"] * wk["cash_loss"])
        self._ev("voyage", "shipwreck", "{} lost the whole fleet: cargo gone ({} units), {} silver lost, {} debt added, "
                 "back in {} with a {}".format(p["name"], self.used(p), money(lost), money(wk["debt"]), PORTS[HOME]["name"],
                                               SHIPS[wk["ship"]]["name"].lower()), p, lost=lost, debt=wk["debt"],
                 cargo=dict(p["cargo"]))
        p["cargo"] = {}
        p["cash"] -= lost
        p["debt"] += wk["debt"]
        p["port"] = HOME
        p["tab"] = self._new_tab()
        p["wrecks"] += 1
        p["ships"] = [self._new_ship(wk["ship"], guns=0, hull=wk["hull"])]
        p["log"].append(tx("l.wrecked", lost=money(lost), debt=money(wk["debt"]),
                           ship=SHIPS[wk["ship"]]["name"].lower()))
        news.append(tx("n.wrecked", name=p["name"], firm=p["firm"]))

    # ------------------------------------------------------------- view --
    def view(self, pid, present=()):
        """Everything one screen needs. pid=None gives the public harbor board."""
        s = self.s
        present = set(present)
        host = self.host_id(present)
        standings = []
        for q in (s["players"][i] for i in s["order"]):
            worth = int(self.worth(q))
            standings.append({"id": q["id"], "name": q["name"], "firm": q["firm"], "color": q["color"],
                              "port": q["port"], "ready": q["ready"], "present": q["id"] in present,
                              "worth": worth, "rank": rank_for(worth), "ships": len(q["ships"]),
                              "host": q["id"] == host})
        out = {
            "phase": s["phase"], "turn": s["turn"], "date": date_label(s["turn"]),
            "years": s["years"], "turns_left": max(0, s["years"] * 12 - s["turn"]),
            "players": standings, "news": s["news"][:14],
            "weather": s["weather"], "crackdown": sorted(s["crackdown"]),
            "bans": {k: self.banned(k) for k in sorted(s["crackdown"])},
            "waiting": [q["name"] for q in standings if q["present"] and not q["ready"]],
            "me": None,
        }
        p = s["players"].get(pid)
        if p:
            port = p["port"]
            sp = self.spread(p, port)
            worth = int(self.worth(p))
            out["me"] = {
                "id": p["id"], "name": p["name"], "firm": p["firm"], "color": p["color"],
                "host": p["id"] == host, "port": port,
                "cash": int(p["cash"]), "bank": int(p["bank"]), "debt": int(math.ceil(p["debt"])),
                "worth": worth, "rank": rank_for(worth),
                "cargo": p["cargo"], "wh": p["wh"], "wh_cap": R["fleet"]["warehouse_cap"],
                "capacity": self.capacity(p), "used": self.used(p),
                "ships": [{"type": sh["type"], "name": sh["name"], "hull": sh["hull"], "guns": sh["guns"],
                           "value": int(self.ship_value(sh)),
                           "repair": int(math.ceil((SHIPS[sh["type"]]["hull"] - sh["hull"])
                                                   * self.repair_rate(p, sh)))}
                          for sh in p["ships"]],
                "rep": {k: int(round(v)) for k, v in p["rep"].items()},
                "protect": p["protect"], "protect_cost": self.protection_cost(p),
                "loan_room": max(0, int(self.loan_limit(p) - p["debt"])),
                "ready": p["ready"], "dest": p["dest"], "orders": p["orders"],
                "log": p["log"], "known": p["known"],
                "prices": {g: round(v, 2) for g, v in s["prices"][port].items()},
                "basis": {g: round(v, 2) for g, v in (p.get("basis") or {}).items()},   # average paid per unit
                "spread": round(sp, 4),
                "dues": self.dues(p), "slip": bool(p.get("slip")),
                "customs": self.customs_view(p),
            }
        return out

    def admin_view(self, present=()):
        """The whole game, for the Admin page."""
        s = self.s
        present = set(present)
        players = []
        for p in (s["players"][i] for i in s["order"]):
            worth = int(self.worth(p))
            players.append({"id": p["id"], "name": p["name"], "firm": p["firm"], "color": p["color"],
                            "port": p["port"], "dest": p["dest"], "ready": p["ready"], "orders": p["orders"],
                            "present": p["id"] in present, "cash": int(p["cash"]), "bank": int(p["bank"]),
                            "debt": int(math.ceil(p["debt"])), "worth": worth, "rank": rank_for(worth),
                            "protect": p["protect"], "wrecks": p["wrecks"],
                            "cargo": p["cargo"], "wh": p["wh"], "hold": self.capacity(p), "used": self.used(p),
                            "ships": [{"type": sh["type"], "name": sh["name"], "hull": sh["hull"],
                                       "guns": sh["guns"]} for sh in p["ships"]],
                            "log": p["log"]})
        return {"phase": s["phase"], "turn": s["turn"], "date": date_label(s["turn"]), "years": s["years"],
                "turns_left": max(0, s["years"] * 12 - s["turn"]), "players": players,
                "prices": {port: {g: round(v, 1) for g, v in row.items()} for port, row in s["prices"].items()},
                "weather": s["weather"], "crackdown": s["crackdown"], "ban_goods": s.get("ban_goods", {}),
                "bans": {k: self.banned(k) for k in s["crackdown"]}, "shocks": s["shocks"], "news": s["news"]}


def static_data():
    """Reference data the browser needs once (and again whenever settings change)."""
    f, b, w, pi, ly = R["fleet"], CFG["brand"], R["weather"], R["pirates"], R["liyuen"]
    return {"goods": GOODS, "ports": PORTS, "ships": SHIPS, "regions": REGIONS,
            "weather": [tx("wx.{}".format(i)) for i in range(4)],
            "voyage_risk": {"risk_min": w["risk_min"], "risk_max": w["risk_max"], "risk_div": w["risk_div"],
                            "storm_chance": [chance * MULT["storms"] for chance in w["storm_chance"]],
                            "pirate_chance": pi["chance"] * MULT["pirates"],
                            "lord_chance": ly["chance"] * MULT["pirates"],
                            "protect_save": ly["protect_save"]},
            "gun_price": f["gun_price"], "max_fleet": f["max_fleet"],
            "loan_rate": loan_rate(), "bank_rate": R["bank"]["bank_rate"], "home": HOME,
            "impact": R["market"]["impact"], "lengths": R["game"]["lengths"],
            "start_year": R["game"]["start_year"], "renew_at": R["liyuen"]["renew_at"],
            "ban_price_mult": R["events"]["ban_price_mult"],
            "dues_rules": {k: R["dues"][k] for k in ("slip_caught", "slip_mult", "slip_rep")},
            "forecast_accuracy": R["weather"]["forecast_accuracy"],
            "brand": b, "graphics": CFG["graphics"], "colors": CFG["theme"]["player_colors"],
            "rating": CFG["content"]["rating"],
            "difficulty": MULT.get("name", ""), "yards": [p["name"] for p in PORTS.values() if p["shipyard"]],
            "tokens": TOKENS, "text": TEXT, "lang": CFG["language"]["active"]}


configure()
