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
    return [k for k, g in GOODS.items() if g.get("contraband")]


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
                 weather=dict(s["weather"]), crackdown=dict(s["crackdown"]), shocks=copy.deepcopy(s["shocks"]),
                 state=state)

    # ------------------------------------------------------------ setup --
    def _new_state(self):
        s = {"phase": "lobby", "turn": 0, "years": R["game"]["default_years"], "players": {}, "order": [],
             "prices": {}, "shocks": [], "crackdown": {}, "weather": {}, "news": [],
             "next_id": 1}
        self.s = s
        for port in PORTS:
            s["prices"][port] = {g: self._opening(port, g) for g in GOODS}
        self._roll_weather()
        s["news"] = [tx("n.opening")]
        return s

    def _opening(self, port, good):
        spread = R["market"]["start_spread"]
        return self._target(port, good) * self.rng.uniform(1 - spread, 1 + spread)

    def _target(self, port, good):
        t = GOODS[good]["base"] * PORTS[port]["mods"].get(good, 1.0)
        for sh in self.s["shocks"]:
            if sh["port"] == port and sh["good"] == good:
                t *= sh["mult"]
        if GOODS[good].get("contraband") and port in self.s["crackdown"]:
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
        s["weather"] = {r: int(s.get("weather", {}).get(r, 1)) for r in REGIONS}
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
             "known": {}, "wrecks": 0}
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
            p["ready"], p["dest"] = False, None
            return tx("m.unsail")
        if p["ready"]:
            raise GameError(tx("e.already_sailed"))

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
            return tx("m.deposited", amount=money(q))
        q = min(q, int(p["bank"]))
        if q <= 0:
            raise GameError(tx("e.account_empty"))
        p["bank"] -= q
        p["cash"] += q
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
            return tx("m.borrowed", amount=money(q), rate="{:g}".format(round(loan_rate() * 100, 2)))
        q = min(q, int(math.ceil(p["debt"])), int(p["cash"]))
        if q <= 0:
            raise GameError(tx("e.nothing_to_repay"))
        p["debt"] = max(0.0, p["debt"] - q)
        p["cash"] -= q
        if p["debt"] < 1:
            p["debt"] = 0.0
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
            return tx("m.stored", qty=q, good=GOODS[g]["name"])
        q = min(q, p["wh"].get(g, 0), self.capacity(p) - self.used(p))
        if q <= 0:
            raise GameError(tx("e.nothing_to_load"))
        p["wh"][g] -= q
        if not p["wh"][g]:
            del p["wh"][g]
        p["cargo"][g] = p["cargo"].get(g, 0) + q
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
        self._detail = {"dest": dest, "orders": orders, "note": "standing orders: " + orders}
        if dest:
            return tx("m.sail", port=PORTS[dest]["name"])
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
                s["crackdown"][a["port"]] = turns
            else:
                s["crackdown"].pop(a["port"], None)
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
        for p in players:
            p["log"] = []
            if p["ready"] and p["dest"]:
                self._voyage(p, actual, news)
            else:
                p["log"].append(tx("l.anchor", port=PORTS[p["port"]]["name"]))
                self._ev("voyage", "anchor", "{} stayed at anchor in {}{}".format(
                    p["name"], PORTS[p["port"]]["name"], "" if p["ready"] else " (gave no orders)"), p,
                    port=p["port"], gave_orders=p["ready"])
            p["ready"], p["dest"] = False, None

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
                del s["crackdown"][port]
                news.append(tx("n.ban_lifted", port=PORTS[port]["name"]))
                self._ev("market", "ban_lifted", "The contraband ban in {} has ended".format(PORTS[port]["name"]), port=port)
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
        if contraband() and self._chance(ev["ban_chance"], "ban", "A port bans contraband this month"):
            open_ports = [k for k in PORTS if not PORTS[k].get("no_ban") and k not in s["crackdown"]]
            if open_ports:
                port = rng.choice(open_ports)
                s["crackdown"][port] = rng.randint(ev["ban_min_turns"], ev["ban_max_turns"])
                news.append(tx("n.ban", port=PORTS[port]["name"]))
                self._ev("market", "ban", "{} bans contraband for {} months".format(
                    PORTS[port]["name"], s["crackdown"][port]), port=port, turns=s["crackdown"][port])
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
        log.append(tx("l.anchored", port=PORTS[dest]["name"]))
        self._ev("voyage", "arrived", "{} anchored in {}: {} ship{}, hull {}, hold {}/{}, silver {}".format(
            who, PORTS[dest]["name"], len(p["ships"]), "" if len(p["ships"]) == 1 else "s",
            "/".join(str(sh["hull"]) for sh in p["ships"]), self.used(p), self.capacity(p), money(p["cash"])),
            p, port=dest, cargo=dict(p["cargo"]), cash=int(p["cash"]))
        held = sum(p["cargo"].get(g, 0) for g in contraband())
        if held:
            banned = dest in self.s["crackdown"]
            chance = (cb["seize_banned"] - cb["seize_rep_relief"] * p["rep"][dest]) if banned else cb["seize_chance"]
            if self._chance(chance * MULT["seizure"], "seizure", "{}: customs search in {} ({} units of contraband, {}, standing {})".format(
                    who, PORTS[dest]["name"], held, "banned here" if banned else "no ban", int(round(p["rep"][dest]))), p):
                fine = int(min(p["cash"], held * cb["fine_per_unit"]))
                for g in contraband():
                    p["cargo"].pop(g, None)
                p["cash"] -= fine
                self._gain_rep(p, dest, -cb["rep_penalty"])
                log.append(tx("l.seized", qty=held, fine=money(fine)))
                news.append(tx("n.caught", name=p["name"], firm=p["firm"], port=PORTS[dest]["name"]))
                self._ev("voyage", "seized", "{}: customs in {} seized {} units and fined {}; standing -{}".format(
                    who, PORTS[dest]["name"], held, money(fine), cb["rep_penalty"]), p, qty=held, fine=fine, port=dest)

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
                "spread": round(sp, 4),
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
                "weather": s["weather"], "crackdown": s["crackdown"], "shocks": s["shocks"], "news": s["news"]}


def static_data():
    """Reference data the browser needs once (and again whenever settings change)."""
    f, b = R["fleet"], CFG["brand"]
    return {"goods": GOODS, "ports": PORTS, "ships": SHIPS, "regions": REGIONS,
            "weather": [tx("wx.{}".format(i)) for i in range(4)],
            "gun_price": f["gun_price"], "max_fleet": f["max_fleet"],
            "loan_rate": loan_rate(), "bank_rate": R["bank"]["bank_rate"], "home": HOME,
            "impact": R["market"]["impact"], "lengths": R["game"]["lengths"],
            "start_year": R["game"]["start_year"], "renew_at": R["liyuen"]["renew_at"],
            "ban_price_mult": R["events"]["ban_price_mult"],
            "forecast_accuracy": R["weather"]["forecast_accuracy"],
            "brand": b, "graphics": CFG["graphics"], "colors": CFG["theme"]["player_colors"],
            "rating": CFG["content"]["rating"],
            "difficulty": MULT.get("name", ""), "yards": [p["name"] for p in PORTS.values() if p["shipyard"]],
            "tokens": TOKENS, "text": TEXT, "lang": CFG["language"]["active"]}


configure()
