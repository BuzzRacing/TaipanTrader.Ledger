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
import re
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
        out = tpl.format_map(values)
    except (ValueError, IndexError, KeyError, AttributeError, TypeError):
        out = tpl
    if key.startswith("n."):                    # remember which headline this wording came from (news heat)
        if len(_NEWS_KEYS) > 600:
            _NEWS_KEYS.clear()
        _NEWS_KEYS[out] = key
    return out


# ---- News heat: how hot each kind of headline burns on the Port screen's News board (0 = never hot,
# 3 = front-page). A headline is hottest the month it appears and cools over NEWS_FADE months.
_NEWS_KEYS = {}
NEWS_HEAT = {
    "n.crash": 3, "n.boom": 3, "n.wrecked": 3, "n.game_over": 3,
    "n.caught": 2, "n.customs_caught": 2, "n.slip_caught": 2, "n.wh_robbed": 2, "n.ban": 2,
    "n.fight_plundered": 2, "n.fight_won": 2, "n.fight_retreated": 2,
    "n.fight_broke_off": 1, "n.fight_away": 1, "n.fight_paid": 1,
    "n.scarce": 1, "n.glut": 1, "n.ban_lifted": 1,
    "n.opening": 1, "n.start_one": 1, "n.start_many": 1,
    "admin": 2,                                 # news the host posts from the Admin page
}
NEWS_FADE = [1.0, 0.55, 0.22]                   # this month, next month, the month after; then cold


def home_of(p):
    """A house's own home port: where it started, and where its bank, lender, warehouse and
    protection are. Houses from saves made before homes were personal use the game's home port."""
    h = p.get("home")
    return h if h in PORTS else HOME


def port_has(p, port, what):
    """Is there a bank ("bank"), a warehouse ("warehouse") or a shipyard ("shipyard") for this house in
    port? Its own home port always has all three; other ports only where Admin > Ports ticks the box."""
    return port in PORTS and (port == home_of(p) or bool(PORTS[port].get(what)))


def depots_of(p):
    """The house's warehouses away from home: {port: {"goods": {good: qty}, "level": expansions}}."""
    d = p.get("depots")
    if not isinstance(d, dict):
        d = p["depots"] = {}
    return d


def depot_cap(level):
    f = R["fleet"]
    return int(f.get("depot_cap", 1000)) + int(level) * int(f.get("depot_expand_cap", 1000))


def stored(p, g=None):
    """Units ashore in every warehouse the house owns (home and away), for one cargo or all."""
    stores = [p["wh"]] + [d.get("goods", {}) for d in depots_of(p).values()]
    if g is None:
        return sum(sum(w.values()) for w in stores)
    return sum(w.get(g, 0) for w in stores)


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
    R["battle"] = dict(BATTLE_DEFAULTS, **(cfg["rules"].get("battle") or {}))   # settings saved before the sea battle
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


HIST_MONTHS = 12      # months of prices in the market keepers' book (Market tab pulse chart)


def seed_firm(p):
    """The House name the seat's dice were seeded with: its first name, kept when the House is renamed."""
    return p.get("seed_firm") or p.get("firm", "")


def rename_in(obj, old, new, skip=("token", "seed_firm")):
    """Swap one House name for another in every piece of text inside obj (lists and dicts, in place).
    Only the whole name, between word edges, so a name inside a longer word is left alone. Returns obj."""
    pat = re.compile(r"(?<![\w]){}(?![\w])".format(re.escape(old)))
    def fix(v):
        if isinstance(v, str):
            return pat.sub(lambda _m: new, v) if old in v else v
        if isinstance(v, list):
            for i, x in enumerate(v):
                v[i] = fix(x)
            return v
        if isinstance(v, dict):
            for k in list(v):
                if k not in skip:
                    v[k] = fix(v[k])
            return v
        return v
    return fix(obj)


def date_label(turn):
    return "{} {}".format(tx("mon.{}".format(turn % 12)), R["game"]["start_year"] + turn // 12)


def distance(a, b):
    pa, pb = PORTS[a], PORTS[b]
    return math.hypot(pa["x"] - pb["x"], pa["y"] - pb["y"])


def rank_index(worth):
    return next((i for i in range(len(CFG["ranks"]) - 1, -1, -1)
                 if worth >= CFG["ranks"][i]["worth"]), 0)


def rank_for(worth):
    return CFG["ranks"][rank_index(worth)]["title"] if CFG["ranks"] else ""


def loan_rate():
    return R["bank"]["loan_rate"] * MULT["interest"]


def pct(x):
    return "{:g}%".format(round(x * 100, 2))


# Cannons (rules.fleet): bought for cannon_cost guns' price, fire like cannon_power guns, take cannon_slots mounts.
def cannon_price():
    f = R["fleet"]
    return int(round(f["gun_price"] * f.get("cannon_cost", 7.5)))


def cannon_power():
    return max(1, int(R["fleet"].get("cannon_power", 2)))


def cannon_slots():
    return max(1, int(R["fleet"].get("cannon_slots", 2)))


# The three classes of ship (Admin > Ships > Class). Merchantmen carry cargo and guns and make up the
# first line of a fleet (rules.fleet.max_fleet of them); escorts carry guns only and sail in the van;
# cargo ships carry cargo only and sail in the rear. Each class has its own limit.
ROLES = ("escort", "trader", "cargo")


def role_of(kind):
    spec = SHIPS.get(kind) or {}
    r = spec.get("role", "trader")
    return r if r in ROLES else "trader"


def role_limit(role):
    f = R["fleet"]
    return int(f["max_fleet"] if role == "trader" else f.get("max_escorts" if role == "escort" else "max_cargo", 5))


def role_unlock(role):
    """Merchantmen a house must have before a shipyard sells it this class (0 for merchantmen)."""
    if role == "trader":
        return 0
    return int(R["fleet"].get("escort_unlock" if role == "escort" else "cargo_unlock", 5))


# The sea battle played on screen (rules.battle). Used whole when the settings predate it.
BATTLE_DEFAULTS = {"interactive": True, "parley": True, "parley_per_junk": 60, "parley_cargo": 0.05,
                   "retreat_min": 0.15, "retreat_max": 0.30, "retreat_floor": 5,
                   "round_secs": 10, "first_extra": 10, "voice_grace": 0,
                   "gun_loss": 0.25, "gun_loss_two": 0.25,
                   "cargo_hit": 0.2, "cargo_hit_min": 0.1, "cargo_hit_max": 0.3, "foe_voice": True}
BATTLE_DEFAULTS.update({
    "match": True, "match_rounds_min": 2.5, "match_rounds_max": 4.5, "match_base": 0.55, "match_cargo": 0.3,
    "match_fame": 0.2, "match_standing": 0.1, "match_spread": 0.1, "match_min": 0.3, "match_max": 1.5,
    "match_lord": 0.15, "match_escort_share": 0.5, "match_cargo_ref": 100000, "match_ships_min": 2, "match_ships_max": 12,
    "match_lord_ships_max": 16, "match_hp_min": 4, "match_hp_max": 12, "match_flag": 2.0,
    "allure_base": 0.6, "allure_cargo": 0.6, "allure_fame": 0.3, "match_booty": 0.8,
    "fame_win": 1.0, "fame_broke_off": 0.5, "fame_decay": 0.1, "fame_ref": 10,
    "focus": 0.3, "van_weight": 4, "line_weight": 3, "rear_weight": 3, "rear_cover": 0.85, "cargo_spill": 1.0,
    "lowball": True, "lowball_chance": 0.15, "lowball_dense": 1.0, "lowball_fame": 0.7,
    "lowball_min": 0.1, "lowball_max": 0.3, "lowball_goods": ["gold", "opium"]})

# Which heading of the captain's report each player action belongs under.
ACTION_CAT = {"buy": "trade", "sell": "trade", "warehouse": "trade", "depot": "trade",
              "bank": "finance", "loan": "finance", "protection": "finance",
              "buy_ship": "fleet", "sell_ship": "fleet", "trade_down": "fleet", "buy_gun": "fleet", "repair": "fleet",
              "sell_gun": "fleet", "buy_cannon": "fleet", "sell_cannon": "fleet",
              "sail": "orders", "unsail": "orders", "sea": "orders",
              "customs_declare": "finance", "customs_buyback": "finance", "customs_done": "finance",
              "gift": "finance", "house": "players",
              "settings": "host", "start": "host", "force": "host"}


class Game:
    def __init__(self, state=None, seed=None):
        self.on_event = None      # set by the server: called with one dict per event
        self._hold = None         # events queued while an action is being applied
        self._detail = None       # extra facts an action handler wants in its event
        self._say_from, self._said = 0, 0   # which of the bosun's lines comes next (see _frame)
        self._foe_who, self._foe_n = "", 0  # who speaks for the enemy, and which of her lines comes next
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

    def _store_view(self, p):
        """What the player screen needs about banks and warehouses where the house is now."""
        port, f = p["port"], R["fleet"]
        store = self._store_here(p)
        offered = port_has(p, port, "warehouse")
        away = {k: {"goods": dict(d.get("goods", {})), "cap": depot_cap(d.get("level", 0))}
                for k, d in depots_of(p).items()}
        return {"wh": dict(store["goods"]) if store else {}, "wh_cap": store["cap"] if store else 0,
                "wh_here": "home" if store and store["home"] else "open" if store else "closed" if offered else "none",
                "bank_here": port_has(p, port, "bank"),
                "wh_home": dict(p["wh"]), "wh_away": away, "stored": {g: stored(p, g) for g in GOODS if stored(p, g)},
                "depot_rules": {"open": int(f.get("depot_open_cost", 10000)), "cap": depot_cap(0),
                                "expand": int(f.get("depot_expand_cost", 100000)), "add": int(f.get("depot_expand_cap", 1000))}}

    def firms(self):
        """Every house's position, for snapshots."""
        out = []
        for p in (self.s["players"][i] for i in self.s["order"]):
            out.append({"id": p["id"], "name": p["name"], "firm": p["firm"], "port": p["port"],
                        "cash": int(p["cash"]), "bank": int(p["bank"]), "debt": int(math.ceil(p["debt"])),
                        "worth": int(self.worth(p)), "rank": self.commissioned_rank(p)["title"],
                        "protect": p["protect"], "wrecks": p["wrecks"],
                        "hold": self.capacity(p), "used": self.used(p), "guns": self.guns(p),
                        "cannons": self.cannons(p),
                        "cargo": dict(p["cargo"]), "wh": dict(p["wh"]),
                        "depots": {k: dict(d["goods"]) for k, d in depots_of(p).items()},
                        "ships": [{"type": sh["type"], "name": sh["name"], "hull": sh["hull"], "guns": sh["guns"],
                                   "cannons": sh.get("cannons", 0)} for sh in p["ships"]],
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
                 weather=dict(s["weather"]), crackdown=dict(s["crackdown"]), ban_goods=copy.deepcopy(s.get("ban_goods", {})), shocks=copy.deepcopy(s["shocks"]), windfalls=copy.deepcopy(s.get("windfalls", [])),
                 state=state)

    # ------------------------------------------------------------ setup --
    def _new_state(self):
        s = {"phase": "lobby", "turn": 0, "years": R["game"]["default_years"], "players": {}, "order": [],
             "prices": {}, "shocks": [], "windfalls": [], "crackdown": {}, "ban_goods": {}, "weather": {}, "news": [], "news_meta": {},
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
        w = self._windfall(port, good)
        if w:
            t *= w["mult"]
        if port in self.s["crackdown"] and good in self.banned(port):
            t *= R["events"]["ban_price_mult"]
        return t

    def _windfall(self, port, good):
        """The crash or boom running on this cargo in this port, or None."""
        for w in self.s.get("windfalls", ()):
            if w["port"] == port and w["good"] == good:
                return w
        return None

    def _roll_windfalls(self, news):
        """Now and then the bottom falls out of one cargo in one port, or it goes through the roof:
        a lottery win for whoever is standing there with the silver or the cargo. Usually one or
        the other; rarely a crash and a boom land in the same month."""
        ev, rng, s = R["events"], self.rng, self.s
        if not self._chance(ev.get("windfall_chance", 0.0), "windfall", "A crash or a boom this month"):
            return
        kinds = [rng.choice(("crash", "boom"))]
        if self._chance(ev.get("windfall_pair_chance", 0.0), "windfall_pair", "A crash and a boom in the same month"):
            kinds.append("boom" if kinds[0] == "crash" else "crash")
        used_ports = set(w["port"] for w in s["windfalls"])
        for kind in kinds:
            ports = [k for k in PORTS if k not in used_ports] or list(PORTS)
            port, good = rng.choice(ports), rng.choice(list(GOODS))
            used_ports.add(port)
            lo, hi = (ev["crash_min"], ev["crash_max"]) if kind == "crash" else (ev["boom_min"], ev["boom_max"])
            lo, hi = min(lo, hi), max(lo, hi)
            mult = math.exp(rng.uniform(math.log(lo), math.log(hi)))      # spread evenly on a log scale
            turns = rng.randint(min(ev["windfall_min_turns"], ev["windfall_max_turns"]),
                                max(ev["windfall_min_turns"], ev["windfall_max_turns"]))
            s["shocks"] = [sh for sh in s["shocks"] if not (sh["port"] == port and sh["good"] == good)]
            s["windfalls"] = [w for w in s["windfalls"] if not (w["port"] == port and w["good"] == good)]
            s["windfalls"].append({"port": port, "good": good, "kind": kind, "mult": round(mult, 4), "turns": turns})
            before = s["prices"][port][good]
            s["prices"][port][good] = max(1.0, self._target(port, good))
            self._ev("market", "windfall", "{}: {} in {} x{:.3g} of normal for {} month(s) ({:,.0f} -> {:,.0f})".format(
                "Crash" if kind == "crash" else "Boom", GOODS[good]["name"], PORTS[port]["name"], mult, turns,
                before, s["prices"][port][good]), port=port, good=good, sort=kind, mult=round(mult, 4), turns=turns,
                price=[round(before, 2), round(s["prices"][port][good], 2)])
            news.append(tx("n.crash" if kind == "crash" else "n.boom", good=GOODS[good]["name"],
                           good_lower=GOODS[good]["name"].lower(), port=PORTS[port]["name"]))

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
        if s.get("phase") == "sea" and not s.get("sea"):
            s["phase"] = "port"
        s.setdefault("shocks", [])
        s.setdefault("windfalls", [])
        s.setdefault("forecasts", [])
        s.setdefault("crackdown", {})
        s.setdefault("news", [])
        s.setdefault("price_hist", [])          # the keepers' price book: month-start prices, newest last
        if "news_meta" not in s:                # games saved before news heat: old headlines start cold
            s["news_meta"] = {n: {"turn": s.get("turn", 0), "heat": 0} for n in s["news"]}
        s["prices"] = {port: {g: (s["prices"].get(port, {}).get(g) or self._opening_safe(port, g)) for g in GOODS}
                       for port in PORTS}
        s["shocks"] = [sh for sh in s["shocks"] if sh["port"] in PORTS and sh["good"] in GOODS]
        s["windfalls"] = [w for w in s["windfalls"] if w["port"] in PORTS and w["good"] in GOODS]
        if s.get("phase") != "lobby":
            self._note_history()
        s["forecasts"] = [f for f in s["forecasts"] if f["port"] in PORTS and f["good"] in GOODS]
        s["crackdown"] = {k: v for k, v in s["crackdown"].items() if k in PORTS}
        extra = sometimes_contraband()
        s["ban_goods"] = {k: [g for g in v if g in extra] for k, v in (s.get("ban_goods") or {}).items()
                          if k in s["crackdown"]}
        s["weather"] = {r: int(s.get("weather", {}).get(r, 1)) for r in REGIONS}
        rates = s.get("tax_rates") if isinstance(s.get("tax_rates"), dict) else {}
        # A port that charges a rate never sits at 0: a save made while it was a free port (or a port
        # just given a rate in Admin > Ports) picks up the base rate at once instead of next month.
        s["tax_rates"] = {}
        for port in PORTS:
            base = float(PORTS[port].get("tax_rate", 0.0) or 0.0)
            was = float(rates.get(port, 0.0) or 0.0)
            s["tax_rates"][port] = (was if was > 0 else base) if base > 0 else 0.0
        fallback = R["wreck"]["ship"]
        for p in s["players"].values():
            seen = set()                          # older saves could give two ships one name
            for sh in p.get("ships", []):
                base, k = sh["name"], 2
                while sh["name"] in seen:
                    sh["name"] = "{} {}".format(base, k)
                    k += 1
                seen.add(sh["name"])
            p["fame"] = max(0.0, float(p.get("fame", 0) or 0))
            p["home"] = home_of(p)
            if p["port"] not in PORTS:
                p["port"] = p["home"]
            if p.get("dest") not in PORTS:
                p["dest"] = None
            p["rep"] = {port: float(p["rep"].get(port, R["start"]["rep"])) for port in PORTS}
            p["cargo"] = {g: q for g, q in p["cargo"].items() if g in GOODS and q > 0}
            p["wh"] = {g: q for g, q in p["wh"].items() if g in GOODS and q > 0}
            p["depots"] = {port: {"goods": {g: int(q) for g, q in (d.get("goods") or {}).items() if g in GOODS and q > 0},
                                  "level": max(0, int(d.get("level", 0) or 0))}
                           for port, d in depots_of(p).items() if port in PORTS and isinstance(d, dict)}
            p["known"] = {k: v for k, v in p.get("known", {}).items() if k in PORTS}
            tab = p.get("tab") if isinstance(p.get("tab"), dict) else {}
            p["tab"] = {k: float(tab.get(k, 0) or 0) for k in self._new_tab()}
            net = p.get("net") if isinstance(p.get("net"), dict) else {}
            p["net"] = {g: [int(v[0]), max(0, int(v[1]))] for g, v in net.items()
                        if g in GOODS and isinstance(v, (list, tuple)) and len(v) == 2}
            p["slip"] = bool(p.get("slip", False))
            gr = p.get("gift_rep") if isinstance(p.get("gift_rep"), dict) else {}
            p["gift_rep"] = {k: min(float(v or 0), p["rep"][k]) for k, v in gr.items() if k in PORTS and float(v or 0) > 0}
            self._books(p)
            p.pop("declare", None)
            bond = p.get("bond")
            if not isinstance(bond, dict) or bond.get("port") != p["port"]:
                p["bond"] = None
            cu = p.get("customs")
            if not isinstance(cu, dict) or cu.get("port") != p["port"]:
                p["customs"] = None
            else:
                cu["lines"] = [ln for ln in cu.get("lines", []) if ln.get("good") in GOODS]
            # What each cargo cost on average. Saves from before this was kept count what is held at today's price.
            basis = p.get("basis") if isinstance(p.get("basis"), dict) else {}
            held = set(p["cargo"]) | set(p["wh"]) | {g for d in p["depots"].values() for g in d["goods"]}
            p["basis"] = {g: float(basis.get(g, self.s["prices"].get(p["port"], {}).get(g, GOODS[g]["base"])))
                          for g in held if g in GOODS}

            for sh in p["ships"]:
                if sh["type"] not in SHIPS:
                    sh["type"] = fallback
                spec = SHIPS[sh["type"]]
                sh["hull"] = max(1, min(sh["hull"], spec["hull"]))
                cs = cannon_slots()
                sh["cannons"] = max(0, min(int(sh.get("cannons", 0)), spec["slots"] // cs)) if spec.get("cannons") else 0
                sh["guns"] = max(0, min(sh["guns"], spec["slots"] - cs * sh["cannons"]))
            over = self.used(p) - self.capacity(p)
            for g in sorted(p["cargo"], key=lambda k: GOODS[k]["base"]):
                if over <= 0:
                    break
                drop = min(over, p["cargo"][g])       # overflow goes ashore to the warehouse
                p["cargo"][g] -= drop
                p["wh"][g] = p["wh"].get(g, 0) + drop
                over -= drop
            p["cargo"] = {g: q for g, q in p["cargo"].items() if q > 0}
            if "rank_id" not in p:
                p["rank_id"] = CFG["ranks"][rank_index(int(self.worth(p)))]["id"]

    def _opening_safe(self, port, good):
        return GOODS[good]["base"] * PORTS[port]["mods"].get(good, 1.0)

    # ---------------------------------------------------------- players --
    def join(self, name, firm, present=(), via=None, captain=None):
        """Join the game, or take back your seat by name from a new device or address.
        captain is the saved Captain's id (captains.py) when the player came in with a profile and PIN;
        a seat taken by a Captain can only be taken back by that Captain."""
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
                if p.get("captain") and p["captain"] != captain:
                    raise GameError(tx("e.captain_seat", name=p["name"]))
                # A seat claimed by name alone is refused while one of its screens is still open, so nobody
                # can take another player's seat. A Captain who has just given the right PIN has proved who
                # they are (a different Captain was turned away just above), so they may take the seat back
                # even if an old screen - a sleeping iPad, a forgotten tab - still looks connected.
                if p["id"] in present and not captain:
                    raise GameError(tx("e.elsewhere", name=p["name"]))
                if captain and not p.get("captain"):
                    p["captain"] = captain
                self._ev("players", "seat_reclaim", "{} took their seat back ({})".format(p["name"], p["firm"]),
                         p, via=via, captain=captain or p.get("captain"))
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
        port = self._start_port()
        p = {"id": pid, "name": name, "firm": firm, "token": secrets.token_urlsafe(16),
             "color": color, "port": port,
             "cash": cash, "bank": 0.0, "debt": float(st["debt"]),
             "cargo": {}, "wh": {}, "depots": {},
             "ships": [self._new_ship(st["ship"], guns=min(st["guns"], SHIPS[st["ship"]]["slots"]))],
             "rep": {port: float(st["rep"]) for port in PORTS},
             "protect": 0, "ready": False, "dest": None, "orders": "fight",
             "log": [tx("l.arrive", home=PORTS[port]["name"], ship=SHIPS[st["ship"]]["name"].lower(), cash=money(cash), debt=money(st["debt"]))],
             "known": {}, "wrecks": 0, "tab": self._new_tab(), "slip": False, "basis": {}, "customs": None,
             "gift_rep": {}}
        if captain:
            p["captain"] = captain
        p["rep"][port] = float(st["home_rep"])
        p["start_port"] = p["home"] = port
        p["rank_id"] = CFG["ranks"][rank_index(int(self.worth(p)))]["id"]
        p["books"] = self._new_books(p)
        s["players"][pid] = p
        s["order"].append(pid)
        self._note_prices(p)
        ship = p["ships"][0]
        self._ev("players", "seat_new", "{} joined as {} in {} with {} silver, {} debt and the {} {}".format(
            name, firm, PORTS[port]["name"], money(cash), money(st["debt"]), SHIPS[ship["type"]]["name"].lower(),
            ship["name"]), p, do="join", start_port=port, name=str(raw_name or "")[:60], firm=str(raw_firm or "")[:60], via=via,
            captain=captain)
        return p["token"]

    def _start_port(self):
        """Where a new player sets out from: the home port, or (Game Setup > Where players
        start) a random port that no other house started in, while there are any left."""
        if R["start"].get("where", "home") != "random":
            return HOME
        taken = {q.get("start_port", q["port"]) for q in self.s["players"].values()}
        free = [port for port in PORTS if port not in taken] or list(PORTS)
        return self.rng.choice(sorted(free))

    def _new_ship(self, kind, guns=0, hull=None):
        # Each class has its own name list (Ships > Ship names); merchantmen use ship_names.
        role = SHIPS[kind].get("role", "trader")
        own = CFG.get({"escort": "escort_names", "cargo": "cargo_names"}.get(role, "ship_names")) or []
        used = {sh["name"] for p in self.s["players"].values() for sh in p["ships"]}
        names = own or CFG["ship_names"]
        free = [n for n in names if n not in used]
        if not free and own and own is not CFG["ship_names"]:
            # The class's own list is all at sea: borrow a free Merchantman name before numbering.
            free = [n for n in CFG["ship_names"] if n not in used]
        if not free:
            # Every name is at sea: a second ship of a name is "II", then "III" (names are how a fight
            # tells the ships apart, so no two may share one).
            free = next(f for f in ([n + " " + r for n in names if n + " " + r not in used]
                                    for r in ("II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")) if f) \
                if names else ["Ship {}".format(len(used) + 1)]
        return {"type": kind, "name": self.rng.choice(free),
                "hull": SHIPS[kind]["hull"] if hull is None else min(hull, SHIPS[kind]["hull"]), "guns": guns,
                "cannons": 0}

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

    @staticmethod
    def class_count(p, role):
        return sum(1 for sh in p["ships"] if role_of(sh["type"]) == role)

    def fleet_classes(self, p):
        """Each class of the fleet for the screens: how many, the limit, and whether a shipyard sells it yet."""
        traders = self.class_count(p, "trader")
        return {r: {"n": self.class_count(p, r), "max": role_limit(r), "unlock": role_unlock(r),
                    "open": traders >= role_unlock(r)} for r in ROLES}

    def cannons(self, p):
        return sum(sh.get("cannons", 0) for sh in p["ships"])

    def firepower(self, p):
        """Shots the fleet fires each round: one per gun, rules.fleet.cannon_power per cannon."""
        return self.guns(p) + cannon_power() * self.cannons(p)

    @staticmethod
    def mounts_free(sh):
        """Gun mounts still empty on a ship. A cannon takes rules.fleet.cannon_slots of them."""
        return SHIPS[sh["type"]]["slots"] - sh["guns"] - cannon_slots() * sh.get("cannons", 0)

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
                + (sh["guns"] * f["gun_price"] + sh.get("cannons", 0) * cannon_price()) * f["gun_resale"])

    def worth(self, p):
        hk = self.s["prices"][HOME]
        goods = sum(q * hk[g] for g, q in p["cargo"].items())
        goods += sum(q * hk[g] for g, q in p["wh"].items())
        goods += sum(q * hk[g] for d in depots_of(p).values() for g, q in d.get("goods", {}).items())
        ships = sum(self.ship_value(sh) for sh in p["ships"])
        return p["cash"] + p["bank"] - p["debt"] + R["market"]["worth_cargo"] * goods + ships

    def commissioned_rank(self, p):
        return next((rank for rank in CFG["ranks"] if rank["id"] == p.get("rank_id")), CFG["ranks"][0])

    def _check_promotions(self):
        if self.s["phase"] == "port":
            for captain in self.s["players"].values():
                self._promote(captain)

    def _promote(self, p):
        if self.s["phase"] != "port" or p["port"] != home_of(p) or p.get("voy") or self._customs_pending(p):
            return
        ranks = CFG["ranks"]
        current = ranks.index(self.commissioned_rank(p))
        qualified = rank_index(int(self.worth(p)))
        if qualified <= current:
            return
        rank = ranks[qualified]
        previous = ranks[current]
        following = ranks[qualified + 1] if qualified + 1 < len(ranks) else None
        record = {"worth": int(self.worth(p)), "ships": len(p["ships"]), "date": date_label(self.s["turn"]),
                  "turn": self.s["turn"], "name": p["name"], "firm": p["firm"],
                  "previous": {"id": previous["id"], "title": previous["title"]},
                  "next": dict(following) if following else None,
                  "ranks": [{"id": r["id"], "title": r["title"]} for r in ranks]}
        serial = p.get("promotion_serial", 0) + 1
        p["rank_id"], p["promotion_serial"] = rank["id"], serial
        # The Mayor's words (m.promote.N), one of a bank drawn from this house's own deck.
        say = self._draw(p, "m.promote")
        p.setdefault("promotions", []).append(
            {"id": serial, "rank_id": rank["id"], "title": rank["title"], "port": p["port"],
             "record": record,
             "text": tx(say, name=p["name"], rank=rank["title"], firm=p["firm"],
                        port=PORTS[p["port"]]["name"] if p["port"] in PORTS else "") if say else ""})
        self._ev("players", "promotion", "{} was commissioned as {} in {}".format(
            p["name"], rank["title"], PORTS[p["port"]]["name"]), p, rank=rank["title"], port=p["port"],
                 promotion_id=serial)

    def _rank_view(self, p, worth):
        ranks = CFG["ranks"]
        current = self.commissioned_rank(p)
        following = ranks.index(current) + 1
        qualified = rank_index(worth)
        return {"rank": current["title"], "rank_id": current["id"],
                "next_rank": ranks[following] if following < len(ranks) else None,
                "qualified_rank": ranks[qualified]["title"] if qualified >= following else None,
                "promotion": next(iter(p.get("promotions", [])), None)}

    def loan_limit(self, p):
        b = R["bank"]
        assets = p["cash"] + p["bank"] + sum(self.ship_value(sh) for sh in p["ships"])
        return b["loan_base"] + b["loan_per_rep"] * self.earned_rep(p, home_of(p)) + b["loan_asset_share"] * max(assets, 0)

    def collectors_line(self, p):
        """The debt the collectors tolerate. It is built like the loan limit but leaves out silver and
        bank, so every dollar repaid brings the debt closer to the line (counting silver, paying it
        over to the lender lowered the line faster than the debt)."""
        b = R["bank"]
        ships = sum(self.ship_value(sh) for sh in p["ships"])
        return b["debt_warn_mult"] * (b["loan_base"] + b["loan_per_rep"] * self.earned_rep(p, home_of(p))
                                      + b["loan_asset_share"] * max(ships, 0))

    def collectors(self, p):
        """The debt clock shown on the player screen: the line the collectors watch, and how many
        month-ends until they next call if nothing changes (1 = the end of this month). None when
        there is no debt. Mirrors the count kept in resolve()."""
        b = R["bank"]
        if p["debt"] <= 0:
            return None
        line = self.collectors_line(p)
        grace = max(0, int(b.get("debt_grace_months", 0)))
        every = max(1, int(b.get("debt_call_every", 1)))
        calls_in = None
        # Repaid now, this much leaves the debt on the line after this month's interest.
        to_clear = min(p["debt"], max(0.0, p["debt"] - line / (1 + loan_rate())))
        if p["debt"] * (1 + loan_rate()) > line:
            n = int(p.get("debt_over", 0)) + 1      # the count at the end of this month
            calls_in = 1
            while not (n > grace and (n - grace - 1) % every == 0):
                n += 1
                calls_in += 1
        return {"line": int(line), "over": p["debt"] > line, "months_over": int(p.get("debt_over", 0)),
                "calls_in": calls_in, "penalty": b["debt_rep_penalty"], "grace": grace, "every": every,
                "to_clear": int(math.ceil(to_clear)) if calls_in else 0}

    def repair_rate(self, p, sh):
        f = R["fleet"]
        rate = f["repair_base"] + SHIPS[sh["type"]]["price"] / float(f["repair_price_div"])
        if not port_has(p, p["port"], "shipyard"):
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
            for g in [g for g in b if not p["cargo"].get(g) and not stored(p, g)]:
                del b[g]

    @staticmethod
    def _new_tab():
        return {"repair": 0.0, "yard": 0.0, "bank": 0.0, "loan": 0.0, "wh": 0.0, "profit": 0.0, "sales": 0.0,
                "gift": 0.0}     # gift: the purse given to the Mayor this visit (0 = she can still be called on)

    def _tally(self, p, key, amount):
        tab = p.setdefault("tab", self._new_tab())
        tab[key] = tab.get(key, 0.0) + max(0.0, float(amount))

    # ----------------------------------------------------- account book --
    # Each house keeps a profit and loss book (p["books"]) for the Port screen. "cur" fills up from one
    # landing to the next: trades in port, the Mayor's dues, the voyage and the month's interest. When the
    # month is resolved it is closed into "last", the statement shown on arrival; the Port Authority's
    # tax on that arrival is added to "last" too. "year" and "game" add up every line.
    # Ships and guns bought are not losses (the house still owns them), so they are left out.
    BOOK_LOG = 12        # earlier captain's log entries kept for the Port screen

    def _new_books(self, p):
        return {"cur": {}, "last": None, "year": {}, "year_no": self.s["turn"] // 12, "game": {},
                "start": {"turn": self.s["turn"], "port": p["port"], "worth": int(self.worth(p))}, "logbook": []}

    def _books(self, p):
        bk = p.get("books")
        if not isinstance(bk, dict):
            bk = p["books"] = self._new_books(p)
        for k, v in (("cur", {}), ("year", {}), ("game", {}), ("logbook", [])):
            if not isinstance(bk.get(k), type(v)):
                bk[k] = v
        bk.setdefault("last", None)
        bk.setdefault("year_no", self.s["turn"] // 12)
        if not isinstance(bk.get("start"), dict):
            bk["start"] = {"turn": self.s["turn"], "port": p["port"], "worth": int(self.worth(p))}
        return bk

    def _book(self, p, key, amount, arrival=False):
        """Write one amount (+ income, - cost) into the house's books. arrival=True puts it on the
        statement of the landing just made (the Port Authority) instead of the one now filling up."""
        amount = round(float(amount), 2)
        if not amount:
            return
        if p.get("battle") is not None:
            p["battle"]["net"] = round(p["battle"].get("net", 0.0) + amount, 2)
        bk = self._books(p)
        year = self.s["turn"] // 12
        if bk["year_no"] != year:
            bk["year"], bk["year_no"] = {}, year
        here = bk["last"]["lines"] if arrival and bk.get("last") else bk["cur"]
        for t in (here, bk["year"], bk["game"]):
            t[key] = round(t.get(key, 0.0) + amount, 2)

    def _rob_warehouses(self, p, news, b, rng):
        """Month end: thieves may break into any warehouse the house keeps (home or away) that has cargo
        in it, wherever the house itself is. Standing in that port shifts the odds as for street robbery.
        A share of every cargo stored there is carried off; the house reads it in its log and in the news
        on landing at the next port."""
        chance = float(b.get("whrob_chance", 0.0))
        if chance <= 0:
            return
        stores = [(home_of(p), p["wh"])] + [(k, d.get("goods", {})) for k, d in sorted(depots_of(p).items())]
        for port, goods in stores:
            if port not in PORTS or not sum(goods.values()):
                continue
            st = float(p["rep"].get(port, 50.0))
            odds = chance * max(0.0, 1 + float(b.get("whrob_rep", 0.0)) * (50.0 - st) / 50.0)
            if not self._chance(odds, "wh_robbery", "{}: warehouse in {} broken into (standing {:.0f})".format(
                    p["name"], PORTS[port]["name"], st), p, port=port):
                continue
            share = rng.uniform(float(b.get("whrob_min", 0.1)), float(b.get("whrob_max", 0.3)))
            lost = {}
            for g in sorted(goods):
                q = goods[g]
                take = min(q, max(1, int(round(q * share))))
                if take > 0:
                    lost[g] = take
                    goods[g] = q - take
                    if not goods[g]:
                        del goods[g]
            if not lost:
                continue
            cost = self._cost_of(p, lost)
            self._book(p, "wh_robbed", -cost)
            qty = sum(lost.values())
            what = ", ".join("{} {}".format(q, GOODS[g]["name"]) for g, q in lost.items())
            p["log"].append(tx("l.wh_robbed", port=PORTS[port]["name"], goods=what, pct=int(round(share * 100))))
            news.append(tx("n.wh_robbed", name=p["name"], firm=p["firm"], port=PORTS[port]["name"], qty=qty))
            self._ev("finance", "wh_robbed", "{}: thieves took {} of the stock ({}) from the warehouse in {}".format(
                p["name"], pct(share), what, PORTS[port]["name"]), p, port=port, lost=lost,
                share=round(share, 4), value=round(cost, 2))

    def _cost_of(self, p, goods):
        """What a set of cargo {good: qty} cost the house, at its average price paid."""
        basis = p.get("basis") or {}
        return sum(float(basis.get(g, 0.0)) * q for g, q in goods.items() if q)

    def _close_books(self, p, origin, sailed):
        """End of the month: the filling statement becomes the arrival statement."""
        bk, turn = self._books(p), self.s["turn"]
        st = bk["start"]
        worth = int(self.worth(p))
        pending = self._customs_pending(p)
        bk["last"] = {"lines": bk["cur"], "from": st.get("port") or origin, "to": p["port"], "turn": turn,
                      "date": date_label(turn), "sailed": bool(sailed), "wrecked": "wreck" in bk["cur"],
                      "worth": [st.get("worth") if st.get("worth") is not None else worth, worth], "open": pending,
                      "log": list(p["log"])}
        bk["cur"] = {}
        # While the Port Authority's desk is open the new period's starting worth waits for her verdict.
        bk["start"] = {"turn": turn + 1, "port": p["port"], "worth": None if pending else worth}
        entry = {"date": date_label(turn), "from": origin, "to": p["port"], "lines": list(p["log"])}
        bk["logbook"] = ([entry] + bk["logbook"])[:self.BOOK_LOG]

    def _settle_books(self, p):
        """The Port Authority is done with the house: finish the arrival statement's worth."""
        bk = p.get("books")
        if not isinstance(bk, dict) or not isinstance(bk.get("start"), dict) or bk["start"].get("worth") is not None:
            return
        worth = int(self.worth(p))
        bk["start"]["worth"] = worth
        if bk.get("last"):
            bk["last"]["worth"][1] = worth
            bk["last"]["open"] = False

    def books_view(self, p):
        """The account book for the Port screen."""
        bk = self._books(p)
        return {"last": bk["last"], "year": bk["year"], "game": bk["game"], "cur": bk["cur"],
                "year_no": bk["year_no"], "logbook": bk["logbook"][1:]}

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
        # Debtor's relief: a house carrying debt pays less, in proportion to how near the debt is to the
        # collectors' line, never more than debt_relief off. Measured against the line (not a flat cut) so
        # borrowing just before sailing is never worth it for the discount alone.
        relief = 0
        cap = float(d.get("debt_relief", 0.0) or 0.0)
        debt = float(p.get("debt", 0.0) or 0.0)
        after = max(0, sub + adjust)
        if cap > 0 and debt > 0 and after > 0:
            line = self.collectors_line(p)
            frac = cap if line <= 0 else min(cap, cap * debt / line)
            relief = -int(round(after * frac))
            if relief:
                lines.append({"key": "debt", "basis": int(round(debt)), "rate": round(frac, 4), "amount": relief})
        return {"lines": lines, "total": max(0, after + relief), "level": level, "rep": int(round(rep))}

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

    def home_free(self, p, port):
        """True when this port is the house's own home port and homes are tax-free
        (Pirates & Customs > A house pays no cargo tax in its own home port)."""
        return bool(R["customs"].get("home_free", True)) and port == home_of(p)

    def tax_rate_for(self, p, port):
        """The rate this house is charged in a port: nothing at home, the port's rate elsewhere."""
        return 0.0 if self.home_free(p, port) else self.tax_rate(port)

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
                # Standing also cools her appetite for a house's cargo: a trusted house is rarely bought out.
                "rep_buy": round(max(0.1, 1 + c.get("rep_buy", 0.0) * (50.0 - rep) / 50.0), 4),
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
        k = cx["greed"] * cx["mood"] * line["appetite"] * cx.get("rep_buy", 1.0)
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
        p["bond"] = None                         # a new arrival: nothing is sealed yet
        if not c["enabled"]:
            p["customs"] = None
            return
        rate = self.tax_rate_for(p, port)
        at_home = self.home_free(p, port)
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
        officer = "taxlady" if self.registrar_here(p, port) else self.officer_of(port)
        p["customs"] = {"port": port, "turn": self.s["turn"], "status": status, "officer": officer,
                        "rate": round(rate, 4), "base": float(PORTS[port].get("tax_rate", 0.0) or 0.0),
                        "free": rate <= 0, "home_free": at_home, "lines": lines, "cx": cx, "box": box, "result": None}
        if status == "declare":
            p["customs"]["say"] = self._pa_greeting(p, p["customs"]["officer"])
        elif officer == "taxlady" and port == home_of(p):
            p["customs"]["say"] = self._draw(p, "l.registrar_home")   # her welcome home (None: the stock line)
        if not (at_home and officer != "taxlady"):     # a port's own officer at home says nothing aloud anyway
            p["customs"]["aloud"] = self._greet_aloud(p)
        # At home the Registrar gives a tip; in any other port its own officer may give a hot tip (_hot_tip).
        tip = self._registrar_tip(p) if self.registrar_here(p, port) else self._hot_tip(p, officer)
        if tip:
            p["customs"]["tip"] = tip
        self._ev("finance", "customs_open", "{}: the Port Authority of {} ({}) {}".format(
            p["name"], PORTS[port]["name"], officer,
            "waves the house in (its home port, no tax)" if at_home else
            "waves the house in (free port)" if rate <= 0 else "has nothing to tax (empty hold)" if not lines else
            "asks for a declaration at {}: {}; strongbox {}, mood x{}".format(
                pct(rate), ", ".join("{} {} worth {}".format(ln["qty"], GOODS[ln["good"]]["name"], money(ln["value"]))
                                     for ln in lines), money(box), cx["mood"])),
            p, port=port, rate=rate, lines=lines, cx=cx, box=box, status=status)

    # ------------------------------------------------------ the Registrar --
    # Mrs. Evelyn Marlowe (cast key "taxlady") keeps the register of every merchant house. She is
    # found only in a captain's own home port: she meets the house on the wharf when it comes home
    # (in place of that port's officer) and gives it one fresh price from her book: this month's
    # price of one cargo in one other port, written into the Price Book and read aloud.
    def registrar_here(self, p, port=None):
        """True when this house is in its own home port, where the Registrar keeps its desk."""
        r = R.get("registrar") or {}
        return bool(r.get("enabled", True)) and (port or p["port"]) == home_of(p) and \
            "taxlady" in (CFG.get("characters") or {})

    def _registrar_tip(self, p):
        """Pick, record and log this arrival's price tip, or None. She favours a cargo the house holds
        and a port it has not seen for a while. Drawn from its own seed, never the game's dice, so
        replays of old journals come out the same."""
        r = R.get("registrar") or {}
        here = p["port"]
        if not self.registrar_here(p, here) or len(PORTS) < 2:
            return None
        hot = self._hot_tip(p, "taxlady")
        if hot:
            return hot
        turn, stale = self.s["turn"], max(0, int(r.get("stale_months", 2)))
        known = p.get("known") or {}
        tips = p.setdefault("tips", {})

        def age(port, g):
            seen = [known[port]["turn"]] if port in known else []
            t = (tips.get(port) or {}).get(g)
            if isinstance(t, dict):
                seen.append(int(t.get("turn", -10 ** 6)))
            return turn - max(seen) if seen else None

        ports = [k for k in PORTS if k != here]
        held = [g for g in GOODS if p["cargo"].get(g, 0) > 0] if r.get("held_first", True) else []
        pool = []
        for goods in ([held] if held else []) + [list(GOODS)]:
            pool = [(port, g) for port in ports for g in goods if age(port, g) is None or age(port, g) >= stale]
            if pool:
                break
        if not pool:                              # every price is fresh: the oldest one she has
            oldest = max((age(port, g) or 0) for port in ports for g in (held or list(GOODS)))
            pool = [(port, g) for port in ports for g in (held or list(GOODS)) if (age(port, g) or 0) == oldest]
        pool.sort()
        rng = random.Random("registrar:{}:{}:{}:{}".format(self.s.get("game_id", ""), p.get("name", ""), seed_firm(p), turn))
        port, g = rng.choice(pool)
        was = age(port, g)
        price = int(round(self.s["prices"][port][g]))
        tips.setdefault(port, {})[g] = {"turn": turn, "price": price}
        key = self._draw(p, "l.registrar_tip") or "l.registrar_tip"
        words = {"goods": GOODS[g]["name"], "where": PORTS[port]["name"], "price": money(price), "port": PORTS[here]["name"]}
        p["log"].append(tx("l.registrar_logged", **words))
        self._ev("market", "registrar_tip", "{}: the Registrar, home in {}, tipped {} at {} in {} (the house's last price for it: {})".format(
            p["name"], PORTS[here]["name"], GOODS[g]["name"], money(price), PORTS[port]["name"],
            "none" if was is None else "{} months old".format(was)),
            p, port=here, where=port, good=g, price=price, was=was)
        return {"good": g, "port": port, "price": price, "turn": turn, "key": key,
                "text": tx(key, **words)}

    def _hot_live(self, p):
        """True while this house still holds a hot tip that is to come or still running: one at a time."""
        turn = self.s["turn"]
        return any(int(t.get("ends", -1)) >= turn and (t.get("over") is None or int(t["over"]) > turn)
                   for t in (p.get("hot_tips") or ()))

    def _hot_tip(self, p, officer):
        """A hot tip, or None: a boom the giver knows is coming. One cargo, cheap in this port just now,
        is about to go through the roof in one other port. Given by the Registrar when the house comes
        home (rules.registrar.hot_home_chance, 50%) or by the port's own officer anywhere else
        (hot_away_chance, 20%). Never two at once: while a house holds a tip still to come or still
        running, nobody gives it another. The boom is real: it is booked into s["forecasts"] and lands
        in _move_markets, so a house that buys here and sails straight there arrives in the middle of
        it. Drawn from its own seeds, never the game's dice."""
        r = R.get("registrar") or {}
        s, here = self.s, p["port"]
        if not r.get("hot_enabled", True) or len(PORTS) < 2 or not officer:
            return None
        home = self.registrar_here(p, here)
        turn = s["turn"]
        if self._hot_live(p):
            return None
        last = p.get("hot_last")
        if last is not None and turn - int(last) < max(1, int(r.get("hot_every", 3))):
            return None
        who = "game:{}:{}:{}:{}".format(s.get("game_id", ""), p.get("name", ""), seed_firm(p), turn)
        chance = float(r.get("hot_home_chance" if home else "hot_away_chance", 0.5 if home else 0.2))
        if random.Random("hot_odds:{}:{}".format(who, here)).random() >= chance:
            return None
        # The Registrar's pick keeps its seed from before the odds, so her tips come out as they did.
        rng = random.Random("registrar_hot:{}:{}:{}:{}".format(s.get("game_id", ""), p.get("name", ""), seed_firm(p), turn)
                            if home else "port_hot:{}:{}".format(who, here))
        lead = max(1, int(r.get("hot_lead", 1)))
        # How long the boom lasts is drawn now and kept secret: the tip names when it lands, never how
        # long it runs. The tip's "ends" is the latest it could run (one-at-a-time and the on-screen pin).
        m_lo, m_hi = self._hot_span()
        months = rng.randint(m_lo, m_hi)
        lo, hi = float(r.get("hot_min", 3.0)), float(r.get("hot_max", 6.0))
        lo, hi = max(1.0, min(lo, hi)), max(1.0, lo, hi)
        busy = set((w["port"], w["good"]) for w in s.get("windfalls", ())) | \
            set((f["port"], f["good"]) for f in s.get("forecasts", ()))
        home_bans = set(self.banned(here))
        # Cheap here: this month's price against its normal price here; the cheaper half of the cargoes.
        normal = {g: GOODS[g]["base"] * PORTS[here]["mods"].get(g, 1.0) for g in GOODS}
        goods = sorted((g for g in GOODS if g not in home_bans),
                       key=lambda g: (s["prices"][here][g] / max(0.01, normal[g]), g))
        goods = goods[:max(1, (len(goods) + 1) // 2)]
        pairs = sorted((port, g) for port in PORTS if port != here for g in goods
                       if (port, g) not in busy and g not in self.banned(port))
        if not pairs:
            return None
        port, g = rng.choice(pairs)
        mult = round(math.exp(rng.uniform(math.log(lo), math.log(hi))), 4)
        fire = turn + lead                        # booked in the month turn of that month (see _move_markets)
        lands, ends = fire + 1, fire + m_hi       # the boom shows from lands; at the latest it ends by ends
        s.setdefault("forecasts", []).append({"pid": p["id"], "port": port, "good": g, "fire": fire,
                                              "mult": mult, "turns": months, "lands": lands})
        p["hot_last"] = turn
        name = ((CFG.get("characters") or {}).get(officer) or {}).get("name", "")
        when = tx("l.when.next") if lead == 1 else tx("l.when.months", n=lead)
        words = {"goods": GOODS[g]["name"], "where": PORTS[port]["name"], "home": PORTS[here]["name"],
                 "port": PORTS[here]["name"], "when": when, "months": months, "officer": name}
        bank = "l.registrar_hot" if home else "l.officer_hot"
        key = self._draw(p, bank) or bank
        tip = {"hot": True, "good": g, "port": port, "home": here, "turn": turn, "lands": lands, "ends": ends,
               "by": "registrar" if home else "officer", "officer": officer, "who": name,
               "price": int(round(s["prices"][here][g])), "key": key, "text": tx(key, **words)}
        p.setdefault("hot_tips", []).append(tip)
        p["hot_tips"] = p["hot_tips"][-6:]
        p["log"].append(tx(bank + "_logged", **words))
        self._ev("market", "registrar_hot" if home else "port_hot",
                 "{}: {}, in {}, tipped a boom in {} at {} (x{:.3g} of normal for {} month(s), from {}); {} costs {} here".format(
                     p["name"], "the Registrar" if home else "the Port Authority ({})".format(name or officer),
                     PORTS[here]["name"], GOODS[g]["name"], PORTS[port]["name"], mult, months,
                     date_label(lands), GOODS[g]["name"], money(tip["price"])) + " (kept from the house: {}-{} possible)".format(m_lo, m_hi),
                 p, port=here, where=port, good=g, mult=mult, fire=fire, lands=lands, ends=ends, by=tip["by"])
        return tip

    @staticmethod
    def _hot_span():
        """Shortest and longest a hot-tip boom can run (rules.registrar.hot_months_min / _max)."""
        r = R.get("registrar") or {}
        lo = max(1, int(r.get("hot_months_min", 1)))
        hi = max(lo, int(r.get("hot_months_max", r.get("hot_months", 3))))
        return lo, hi

    def _hot_over(self, w):
        """A foretold boom has just run out: the price falls back to about normal at once (a late house
        finds the party over), and the tip is marked so its pin says the boom was missed."""
        s, r = self.s, R.get("registrar") or {}
        port, g = w["port"], w["good"]
        base = GOODS[g]["base"] * PORTS[port]["mods"].get(g, 1.0)
        top = max(1.0, float(r.get("hot_after_max", 1.5)))
        before = s["prices"][port][g]
        s["prices"][port][g] = base * random.Random("hot_over:{}:{}:{}:{}".format(
            s.get("game_id", ""), port, g, s["turn"])).uniform(1.0, top)
        for q in s["players"].values():
            for tp in q.get("hot_tips") or ():
                if tp.get("port") == port and tp.get("good") == g and tp.get("over") is None \
                        and int(tp.get("lands", 0)) <= s["turn"] + 1 <= int(tp.get("ends", -1)) + 1:
                    tp["over"] = s["turn"] + 1           # the first month it is gone
        self._ev("market", "hot_over", "The foretold boom in {} in {} is over ({:,.0f} -> {:,.0f})".format(
            GOODS[g]["name"], PORTS[port]["name"], before, s["prices"][port][g]),
            port=port, good=g, price=[round(before, 2), round(s["prices"][port][g], 2)])

    def _land_forecasts(self, news):
        """The booms the Registrar foretold that are due this month turn: each becomes a windfall boom."""
        s, ev = self.s, R["events"]
        due = [f for f in s.get("forecasts", ()) if int(f["fire"]) <= s["turn"]]
        s["forecasts"] = [f for f in s.get("forecasts", ()) if int(f["fire"]) > s["turn"]]
        for f in due:
            port, good = f["port"], f["good"]
            if port not in PORTS or good not in GOODS:
                continue
            s["shocks"] = [sh for sh in s["shocks"] if not (sh["port"] == port and sh["good"] == good)]
            s["windfalls"] = [w for w in s["windfalls"] if not (w["port"] == port and w["good"] == good)]
            s["windfalls"].append({"port": port, "good": good, "kind": "boom", "mult": f["mult"],
                                   "turns": int(f["turns"]), "foretold": True})
            before = s["prices"][port][good]
            s["prices"][port][good] = max(1.0, self._target(port, good))
            self._ev("market", "windfall", "Boom (foretold by the Registrar): {} in {} x{:.3g} of normal for {} month(s) "
                     "({:,.0f} -> {:,.0f})".format(GOODS[good]["name"], PORTS[port]["name"], f["mult"], f["turns"],
                                                   before, s["prices"][port][good]),
                     port=port, good=good, sort="boom", mult=f["mult"], turns=f["turns"], foretold=True,
                     price=[round(before, 2), round(s["prices"][port][good], 2)])
            news.append(tx("n.boom", good=GOODS[good]["name"], good_lower=GOODS[good]["name"].lower(),
                           port=PORTS[port]["name"]))

    def sealed(self, p, g=None):
        """Cargo this house left sealed in bond at the Port Authority's desk in the port it is in:
        untaxed, and not for sale there until it has sailed. One cargo's units, or all of them."""
        bond = p.get("bond") or {}
        goods = bond.get("goods") or {} if bond.get("port") == p["port"] else {}
        goods = {k: min(int(q), int(p["cargo"].get(k, 0))) for k, q in goods.items() if p["cargo"].get(k, 0) > 0}
        return goods if g is None else goods.get(g, 0)

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
        seal = a.get("sealed") if isinstance(a.get("sealed"), (list, tuple)) else []
        seal = {ln["good"] for ln in cu["lines"] if ln["good"] in seal} if c.get("bond", True) else set()
        open_lines = [ln for ln in cu["lines"] if ln["good"] not in seal]
        declared = {}
        for ln in open_lines:
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
                self._book(p, "pa_bribe", -cost, arrival=True)
                bribe_mult, bribe = 1 - c["bribe_cut"], {"cost": cost, "taken": True}
        box = int(cu.get("box", 0))
        out, tax_total, paid_in, fine_total, caught = [], 0, 0, 0, False
        for ln in sorted(open_lines, key=lambda x: -x["appetite"]):
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
                    self._book(p, "pa_sold", paid, arrival=True)
                    self._book(p, "cost", -res["cost"] * units, arrival=True)
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
        for ln in cu["lines"]:
            if ln["good"] in seal:
                out.append({"good": ln["good"], "qty": ln["qty"], "value": ln["value"], "declared": 0, "buy": 0.0, "audit": 0.0,
                            "roll": None, "outcome": "sealed", "units": 0, "paid": 0, "tax": 0, "fine": 0, "back": False})
        if seal:
            p["bond"] = {"port": port, "goods": {ln["good"]: ln["qty"] for ln in cu["lines"] if ln["good"] in seal}}
        p["cargo"] = {k: v for k, v in p["cargo"].items() if v > 0}
        owed = self._collect(p, tax_total + fine_total)
        self._book(p, "pa_tax", -tax_total, arrival=True)
        self._book(p, "pa_fine", -fine_total, arrival=True)
        rep_change = 0.0
        value_total = sum(ln["value"] for ln in open_lines)
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
        if seal:
            p["log"].append(tx("l.customs_sealed", port=name, goods=names_of(sorted(seal)).lower()))
        if not caught and open_lines:
            p["log"].append(tx("l.customs_paid", port=name, declared=money(total_declared), value=money(value_total),
                               tax=money(tax_total)))
        self._detail = {"port": port, "rate": rate, "declared": declared, "value": value_total, "tax": tax_total,
                        "fine": fine_total, "paid": paid_in, "owed": owed, "bribe": bribe, "rep": round(rep_change, 2),
                        "lines": out,
                        "sealed": sorted(seal),
                        "note": "declared {} of {} at {}: tax {}{}{}{}{}".format(
                            money(total_declared), money(value_total), pct(rate), money(tax_total),
                            ", {} kept sealed in bond (worth {})".format(
                                names_of(sorted(seal)), money(sum(ln["value"] for ln in cu["lines"] if ln["good"] in seal)))
                            if seal else "",
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

    def _stamp_news(self, admin=False):
        """Give every headline not yet stamped its month and heat (from the headline it was worded from),
        and forget stamps for headlines that have dropped off the board."""
        s = self.s
        meta = s.setdefault("news_meta", {})
        for line in s["news"]:
            if line in meta:
                continue
            at = line.find(": ")
            body = line[at + 2:] if 0 < at < 20 else line
            key = _NEWS_KEYS.get(body) or _NEWS_KEYS.get(line) or ("admin" if admin else "")
            meta[line] = {"turn": s.get("turn", 0), "heat": NEWS_HEAT.get(key, 0)}
        keep = set(s["news"])
        for line in [k for k in meta if k not in keep]:
            del meta[line]

    def news_heat(self, line):
        """0..1: how hot a headline is now: its kind's heat, cooled by how many months old it is."""
        m = (self.s.get("news_meta") or {}).get(line)
        if not m or not m.get("heat"):
            return 0
        age = max(0, self.s.get("turn", 0) - m.get("turn", 0))
        if age >= len(NEWS_FADE):
            return 0
        return round(m["heat"] / 3.0 * NEWS_FADE[age], 3)

    def _news_later(self, p, line):
        """News the house makes in port goes out with the month's news."""
        self.s.setdefault("pending_news", []).append(line)

    def buyback_cost(self, res):
        """Getting a line back from the Port Authority: her price plus her premium, but never less than
        what those goods are worth on the market. A lowball she took at its word (even $0) can't be
        undone for less than the cargo is worth."""
        units, qty = int(res.get("units", 0) or 0), int(res.get("qty", 0) or 0)
        worth = float(res.get("value", 0) or 0) * units / float(qty) if qty > 0 else 0.0
        premium = res["paid"] * (1 + R["customs"]["buyback_premium"])
        return int(math.ceil(max(premium, worth) - 1e-9))

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
        held = p["cargo"].get(g, 0) + stored(p, g)
        basis = p.setdefault("basis", {})
        # What the cargo cost the house stays what it cost before she bought it.
        was = float(res.get("cost", self.s["prices"][p["port"]][g]))
        basis[g] = (basis.get(g, was) * held + was * res["units"]) / float(held + res["units"])
        p["cargo"][g] = p["cargo"].get(g, 0) + res["units"]
        res["back"], res["back_cost"] = True, cost
        # The sale is undone; what she charged above her price is the cost of getting it back.
        self._book(p, "pa_sold", -res["paid"], arrival=True)
        self._book(p, "cost", was * res["units"], arrival=True)
        self._book(p, "pa_premium", -(cost - res["paid"]), arrival=True)
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
        self._settle_books(p)

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

    def _greet_aloud(self, p):
        """Whether the desk's greeting is read aloud on this landing. She reads it, then stays quiet for
        the next few landings (rules.customs.greet_aloud_min..max apart, per house). Its own dice, so the
        game's dice are untouched; the text is always on her desk either way."""
        c = R["customs"]
        lo = max(1, int(c.get("greet_aloud_min", 1) or 1))
        hi = max(lo, int(c.get("greet_aloud_max", lo) or lo))
        wait = int(p.get("greet_wait", 0) or 0)
        if wait > 0:
            p["greet_wait"] = wait - 1
            return False
        rng = random.Random("greet:{}:{}:{}".format(self.s.get("game_id", ""), p.get("id", p.get("name", "")), self.s["turn"]))
        p["greet_wait"] = rng.randint(lo, hi) - 1
        return True

    def _pa_greeting(self, p, officer):
        """Which greeting the officer gives on this visit (a key), or None: drawn from a deck of the
        30 shared greetings (l.customs_welcome.N) and her own (l.customs_welcome.<officer>.N),
        shuffled per house and per officer (engine _draw_keys), so none repeats until all are heard."""
        keys = ["l.customs_welcome.{}".format(i) for i in self._bank("l.customs_welcome")]
        keys += ["l.customs_welcome.{}.{}".format(officer, i) for i in self._bank("l.customs_welcome." + officer)]
        return self._draw_keys(p, "pa:" + officer, keys)

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
        out["bond"] = bool(c.get("bond", True))
        out["rules"] = {k: c[k] for k in ("buy_base", "buy_k", "buy_exp", "audit_base", "audit_k", "buy_cap", "audit_cap",
                                          "fine_mult", "caught_rep", "max_declare", "bribe_min", "bribe_share",
                                          "bribe_cut", "bribe_refused_mult", "bribe_rep", "buyback_premium", "over_rep",
                                          "tell_curious", "tell_hungry")}
        if cu["status"] == "verdict":
            for r in out["result"]["lines"]:
                r["back_price"] = self.buyback_cost(r) if r["units"] and not r["back"] else 0
        name = PORTS[cu["port"]]["name"]
        out["home_free"] = bool(cu.get("home_free"))
        out["tip"] = cu.get("tip")
        out["aloud"] = bool(cu.get("aloud", True))    # saves from before this rule: always read
        if out["home_free"]:
            say = cu.get("say") if isinstance(cu.get("say"), str) else None
            if not say or not str(TEXT.get(say, "")).strip():
                say = "l.customs_home"
            out["welcome"] = tx(say, line=out["line"], port=name)
        elif cu["free"]:
            out["welcome"] = tx("l.customs_free", line=out["line"], port=name)
        elif not cu["lines"]:
            out["welcome"] = tx("l.customs_empty", port=name)
        else:
            say = cu.get("say")                  # a key; a number in saves from before the officers' own lines
            key = say if isinstance(say, str) else "l.customs_welcome.{}".format(say) if say is not None else "l.customs_welcome"
            if not str(TEXT.get(key, "")).strip():
                key = "l.customs_welcome"
            out["welcome"] = tx(key, line=out["line"], port=name, rate=pct(cu["rate"]))
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
        self._book(p, "dues", -total)
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
        # Standing bought from the Mayor never exceeds the standing itself. A loss lowers the standing and
        # leaves the bought share alone, so standing and earned standing drop by the same amount.
        gr = p.get("gift_rep")
        if isinstance(gr, dict) and gr.get(port, 0) > p["rep"][port]:
            gr[port] = p["rep"][port]

    def earned_rep(self, p, port):
        """Standing in a port without what was bought from its Mayor. The moneylender and her collectors
        read this one for the home port, so gifts never buy more borrowing (Mayor's Parlour, decision 5)."""
        gr = p.get("gift_rep") if isinstance(p.get("gift_rep"), dict) else {}
        return max(0.0, p["rep"][port] - float(gr.get(port, 0.0)))

    # ------------------------------------------------- the Mayor's Parlour --
    # Once per visit a house may give the port's Mayor a purse of silver for standing in that port.
    # Standing gained = cap x (1 - e^(-gift / appetite)) x headroom: each dollar buys less than the one
    # before, appetite is the base appetite x the port's harbour dues level, and headroom is 1 up to
    # soft_from, falling in a straight line to 0 at standing 100. web/player.js mirrors gift_gain.
    GIFT_TIERS = ("cool", "gracious", "warm", "delighted")

    def gift_appetite(self, port):
        g = R["gift"]
        return max(1.0, float(g["appetite"]) * float(PORTS.get(port, {}).get("dues", 1.0) or 1.0))

    def gift_gain(self, port, rep, amount):
        g = R["gift"]
        soft = min(99.0, max(0.0, float(g["soft_from"])))
        headroom = 1.0 if rep <= soft else max(0.0, (100.0 - rep) / (100.0 - soft))
        return float(g["cap"]) * (1 - math.exp(-max(0.0, amount) / self.gift_appetite(port))) * headroom

    def gift_tier(self, gain):
        g = R["gift"]
        if gain >= g["delighted_at"]:
            return "delighted"
        if gain >= g["warm_at"]:
            return "warm"
        if gain >= g["gracious_at"]:
            return "gracious"
        return "cool"

    def _bank(self, prefix):
        """The numbered lines of a bank (prefix.0, prefix.1, ...) that are not blanked in Language & Text."""
        n = 0
        while "{}.{}".format(prefix, n) in TEXT:
            n += 1
        return [i for i in range(n) if str(TEXT.get("{}.{}".format(prefix, i), "")).strip()]

    def _draw(self, p, prefix):
        """The next line of a numbered bank (prefix.0, prefix.1, ...) for this house; see _draw_keys."""
        return self._draw_keys(p, prefix, ["{}.{}".format(prefix, i) for i in self._bank(prefix)])

    def _draw_keys(self, p, deck, keys):
        """The next of these wording keys for this house: each house has its own shuffled deck
        (p["decks"][deck]), so no line comes round again until all have been heard, and never twice
        running across a reshuffle. Shuffled from the house's name and deck count, never the game's
        dice, so replays match. None when there are no keys."""
        if not keys:
            return None
        decks = p.setdefault("decks", {})
        d = decks.get(deck) if isinstance(decks.get(deck), dict) else {}
        left = [k for k in (d.get("left") or []) if isinstance(k, str) and k in keys]
        last, n = d.get("last"), int(d.get("n", 0))
        if not left:
            left = list(keys)
            random.Random("{}:{}:{}:{}".format(deck, p.get("name", ""), seed_firm(p), n)).shuffle(left)
            n += 1
            if len(left) > 1 and left[-1] == last:      # drawn from the end
                left[0], left[-1] = left[-1], left[0]
        pick = left.pop()
        decks[deck] = {"left": left, "last": pick, "n": n}
        return pick

    def mayor_mood(self, p, port):
        """How the Mayor regards a house, for her greeting: cold, neutral or warm."""
        g, rep = R["gift"], float(p["rep"].get(port, 50.0))
        if rep < float(g.get("greet_cold_below", 40)):
            return "cold"
        return "warm" if rep >= float(g.get("greet_warm_from", 70)) else "neutral"

    def _mayor_greeting(self, p):
        """Picks the Mayor's greeting for this visit, on anchoring, so it stays put while the house is here."""
        port = p["port"]
        key = self._draw(p, "port.mayor.greet." + self.mayor_mood(p, port))
        p["mayor_greet"] = {"port": port, "key": key or "port.mayor.greet"}

    def gift_view(self, p):
        """What the Parlour on the Port tab needs: the rule's numbers (the slider works them out live),
        whether she has been called on this visit, and the thanks if she has."""
        g, port = R["gift"], p["port"]
        appetite = self.gift_appetite(port)
        top = int(max(0.0, min(p["cash"], appetite * float(g["max_x"]))))
        step = max(1, int(g["step"]))
        last = p.get("gift_last") if isinstance(p.get("gift_last"), dict) else None
        given = (p.get("tab") or {}).get("gift", 0) > 0
        c, m, d = R["customs"], R["market"], R["dues"]
        mg = p.get("mayor_greet") if isinstance(p.get("mayor_greet"), dict) else {}
        greet = mg.get("key") if mg.get("port") == port and str(TEXT.get(mg.get("key") or "", "")).strip() else "port.mayor.greet"
        return {"enabled": bool(g["enabled"]), "given": given, "thanks": last if given and last and last.get("port") == port else None,
                "greet": greet,
                "appetite": round(appetite, 2), "cap": float(g["cap"]), "soft_from": float(g["soft_from"]),
                "min": int(g["min_gift"]), "max": top - top % step if top >= g["min_gift"] else 0, "step": step,
                "tiers": [float(g["gracious_at"]), float(g["warm_at"]), float(g["delighted_at"])],
                "rep": round(p["rep"][port], 2), "earned": round(self.earned_rep(p, port), 2), "home": port == home_of(p),
                "rules": {"rep_discount": d["rep_discount"], "rep_audit": c["rep_audit"], "rep_buy": c.get("rep_buy", 0.0),
                          "spread_base": m["spread_base"], "spread_swing": m["spread_swing"]}}

    def _act_gift(self, p, a):
        g, port = R["gift"], p["port"]
        if not g["enabled"]:
            raise GameError(tx("e.gift_off"))
        if (p.get("tab") or {}).get("gift", 0) > 0:
            raise GameError(tx("e.gift_again", port=PORTS[port]["name"]))
        try:
            amount = int(a.get("amount", 0))
        except (TypeError, ValueError):
            raise GameError(tx("e.whole_number"))
        if amount < int(g["min_gift"]):
            raise GameError(tx("e.gift_small", amount=money(g["min_gift"])))
        top = self.gift_appetite(port) * float(g["max_x"])
        if amount > top:
            raise GameError(tx("e.gift_big", amount=money(top)))
        if amount > p["cash"]:
            raise GameError(tx("e.cost"))
        before = p["rep"][port]
        gain = self.gift_gain(port, before, amount)
        tier = self.gift_tier(gain)
        p["cash"] -= amount
        self._gain_rep(p, port, gain)
        got = p["rep"][port] - before
        gr = p.setdefault("gift_rep", {})
        gr[port] = min(p["rep"][port], gr.get(port, 0.0) + got)
        self._tally(p, "gift", amount)
        self._book(p, "gift", -amount)
        name = PORTS[port]["name"]
        key = self._draw(p, "m.gift." + tier) or "m.gift." + tier
        p["gift_last"] = {"port": port, "turn": self.s["turn"], "amount": amount, "tier": tier, "key": key,
                          "from": int(round(before)), "to": int(round(p["rep"][port])), "gain": round(got, 2)}
        p["log"].append(tx("l.gift", port=name, amount=money(amount), gain=int(round(got))))
        self._ev("finance", "gift", "{} gave the Mayor of {} {}: standing {} -> {} ({}, she is {})".format(
            p["name"], name, money(amount), int(round(before)), int(round(p["rep"][port])),
            "+{:.1f}".format(got), tier), p, port=port, amount=amount, gain=round(got, 2), tier=tier)
        return tx(key, port=name, amount=money(amount), gain=int(round(got)))

    def _note_history(self):
        """The market keepers' price book: every port's prices at the start of each month (newest last,
        kept for HIST_MONTHS + 1 months). The Market tab's pulse chart reads its own port's rows."""
        s = self.s
        hist = s.setdefault("price_hist", [])
        row = {"turn": s["turn"], "prices": {port: {g: round(v, 2) for g, v in r.items()} for port, r in s["prices"].items()}}
        if hist and hist[-1].get("turn") == s["turn"]:
            return
        hist.append(row)
        del hist[:-(HIST_MONTHS + 1)]

    def _note_best_sale(self, p, g, q, gain, unit):
        """Keep this house's most profitable single sale in this port (Market tab's plaque)."""
        profit = int(round(gain - unit * q))
        if profit <= 0:
            return
        best = p.setdefault("best_sale", {})
        old = best.get(p["port"])
        if old and old.get("profit", 0) >= profit:
            return
        best[p["port"]] = {"profit": profit, "good": g, "qty": int(q), "turn": self.s["turn"]}

    def market_view(self, p):
        """The pulse panel under the market keeper: this port's price book, her running windfalls,
        and the house's best sale here."""
        s, port = self.s, p["port"]
        rows = [{"turn": r["turn"], "date": date_label(r["turn"]), "prices": r["prices"].get(port, {})}
                for r in s.get("price_hist", []) if port in r.get("prices", {})]
        best = (p.get("best_sale") or {}).get(port)
        return {"hist": rows[-HIST_MONTHS:],
                "windfalls": {w["good"]: w["kind"] for w in s.get("windfalls", []) if w["port"] == port},
                "best": dict(best, date=date_label(best.get("turn", 0))) if best else None}

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
        if pid in self.s["players"]:
            self._tidy_basis(p)
        self._check_promotions()
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

    def _rename_house(self, p, a):
        """A Captain renames their House (Options). The House is the seat; the name is only its label,
        so the new name shows everywhere at once, past log lines and news included."""
        name = " ".join(str(a.get("name") or "").split())[:28]
        if not name:
            raise GameError(tx("e.house_name"))
        old = p["firm"]
        if name == old:
            return tx("m.house_same", firm=name)
        for q in self.s["players"].values():
            if q is not p and q["firm"].lower() == name.lower():
                raise GameError(tx("e.house_taken", firm=name))
        others = {q["id"]: q["firm"] for q in self.s["players"].values() if q is not p}
        p.setdefault("seed_firm", old)
        p["firm"] = name
        rename_in(self.s, old, name)
        for q in self.s["players"].values():     # another House's own name is never touched
            if q["id"] in others:
                q["firm"] = others[q["id"]]
        self._detail = {"old": old, "firm": name}
        return tx("m.house_renamed", old=old, firm=name)

    def _act(self, pid, a, present=()):
        s = self.s
        p = s["players"].get(pid)
        if p is None:
            raise GameError(tx("e.not_in_game"))
        kind = a.get("type")
        is_host = pid == self.host_id(set(present) | {pid})

        if kind == "house":
            return self._rename_house(p, a)
        if kind == "promotion_ack":
            queue = p.get("promotions", [])
            ack = a.get("id")
            if type(ack) is int and queue and queue[0]["id"] == ack:
                queue.pop(0)
            return tx("m.promotion_ack")
        if kind == "free_play":
            return self._free_play(p)
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
            if not is_host or s["phase"] not in ("port", "sea"):
                raise GameError(tx("e.host_force"))
            if s["phase"] == "sea":
                self._sea_force()            # every open fight is finished on standing orders
            else:
                self.resolve("host", present)
            return tx("m.forced")

        if s["phase"] == "sea":
            if kind != "sea":
                raise GameError(tx("e.at_sea"))
            return self._act_sea(p, a)
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
        s.pop("start_at", None)
        s["phase"] = "port"
        s["price_hist"] = []
        self._note_history()
        n = len(s["players"])
        for q in s["players"].values():
            self._mayor_greeting(q)             # the first port's Parlour greeting
        self._ev("turn", "game_started", "The game has started: {} player{}, {} years".format(
            n, "" if n == 1 else "s", s["years"]), players=[q["name"] for q in s["players"].values()], years=s["years"])
        s["news"].insert(0, "{}: {}".format(date_label(0), tx("n.start_one" if n == 1 else "n.start_many", n=n)))
        self._stamp_news()
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

    def _trade_rep(self, p, value, g, moved):
        """Standing earned by a trade. Each cargo keeps [net units dealt this visit (+ bought, - sold),
        units already credited]; only units that take the net past what was credited earn standing.
        So selling a lot and buying it back, or the reverse, earns nothing however often it is done:
        the dealers know a churned lot when they see one. p["net"] starts again on arrival."""
        m = R["market"]
        acct = p.setdefault("net", {}).setdefault(g, [0, 0])
        acct[0] += moved
        fresh = abs(acct[0]) - acct[1]
        if fresh <= 0:
            return
        acct[1] += fresh
        value *= min(1.0, fresh / float(abs(moved)))
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
        held = p["cargo"].get(g, 0) + stored(p, g)
        basis = p.setdefault("basis", {})
        basis[g] = (basis.get(g, 0.0) * held + cost) / float(held + q)   # average price paid per unit
        p["cargo"][g] = p["cargo"].get(g, 0) + q
        self.s["prices"][p["port"]][g] = end
        self._trade_rep(p, cost, g, q)
        return tx("m.bought", qty=q, good=GOODS[g]["name"], cost=money(cost))

    def _act_sell(self, p, a):
        if a.get("src") in ("wh", "all"):
            return self._sell_store(p, a)
        g, q = self._good(a), self._qty(a)
        if p["cargo"].get(g, 0) < q:
            raise GameError(tx("e.only_have", qty=p["cargo"].get(g, 0), good=GOODS[g]["name"]))
        held = self.sealed(p, g)
        if held and p["cargo"][g] - held < q:
            raise GameError(tx("e.sealed", qty=held, good=GOODS[g]["name"], left=p["cargo"][g] - held))
        gain, end = self.quote(p, g, q, "sell")
        self._trade_detail(p, g, q, gain, end)
        p["cash"] += gain
        unit = p.setdefault("basis", {}).get(g, gain / float(q))      # unknown cost counts as no profit
        self._tally(p, "sales", gain)
        p["tab"]["profit"] = p["tab"].get("profit", 0.0) + (gain - unit * q)   # a loss offsets profit this visit
        self._book(p, "sales", gain)
        self._book(p, "cost", -unit * q)
        self._note_best_sale(p, g, q, gain, unit)
        p["cargo"][g] -= q
        if not p["cargo"][g]:
            del p["cargo"][g]
        self.s["prices"][p["port"]][g] = end
        self._trade_rep(p, gain, g, -q)
        return tx("m.sold", qty=q, good=GOODS[g]["name"], gain=money(gain))

    def _sell_store(self, p, a):
        """Sell straight out of this port's warehouse (src "wh"), or everything of one cargo held here,
        hold and warehouse together (src "all", sealed cargo stays aboard), as one lot at the market."""
        g = self._good(a)
        store = self._store_here(p)
        if store is None:
            raise GameError(tx("e.no_warehouse_here", port=PORTS[p["port"]]["name"]))
        goods = store["goods"]
        in_wh = goods.get(g, 0)
        aboard = 0
        if a.get("src") == "all":
            aboard = max(0, p["cargo"].get(g, 0) - self.sealed(p, g))
            q = in_wh + aboard
        else:
            q = min(self._qty(a), in_wh)
        if q <= 0:
            raise GameError(tx("e.nothing_to_sell", good=GOODS[g]["name"]))
        gain, end = self.quote(p, g, q, "sell")
        self._trade_detail(p, g, q, gain, end)
        p["cash"] += gain
        unit = p.setdefault("basis", {}).get(g, gain / float(q))
        self._tally(p, "sales", gain)
        p["tab"]["profit"] = p["tab"].get("profit", 0.0) + (gain - unit * q)
        self._book(p, "sales", gain)
        self._book(p, "cost", -unit * q)
        self._note_best_sale(p, g, q, gain, unit)
        from_wh = min(in_wh, q)
        goods[g] = in_wh - from_wh
        if not goods[g]:
            del goods[g]
        if aboard:
            p["cargo"][g] -= q - from_wh
            if not p["cargo"][g]:
                del p["cargo"][g]
        self.s["prices"][p["port"]][g] = end
        self._trade_rep(p, gain, g, -q)
        return tx("m.sold_store", qty=q, good=GOODS[g]["name"], gain=money(gain))

    def _store_here(self, p):
        """This port's warehouse for the house as {"goods", "cap", "home"}, or None when it has none
        open here (home always has one; elsewhere it must be ticked in Admin and opened)."""
        port = p["port"]
        if port == home_of(p):
            return {"goods": p["wh"], "cap": int(R["fleet"]["warehouse_cap"]), "home": True}
        if not port_has(p, port, "warehouse"):
            return None
        d = depots_of(p).get(port)
        if d is None:
            return None
        d.setdefault("goods", {})
        return {"goods": d["goods"], "cap": depot_cap(d.get("level", 0)), "home": False, "depot": d}

    def _act_depot(self, p, a):
        """Open a warehouse in this port (op "open") or enlarge it (op "expand"). Home's is free."""
        port, f = p["port"], R["fleet"]
        name = PORTS[port]["name"]
        if port == home_of(p):
            raise GameError(tx("e.depot_home"))
        if not port_has(p, port, "warehouse"):
            raise GameError(tx("e.no_warehouse_port", port=name))
        deps = depots_of(p)
        if a.get("op") == "expand":
            d = deps.get(port)
            if d is None:
                raise GameError(tx("e.depot_not_open", port=name))
            cost, add = int(f.get("depot_expand_cost", 100000)), int(f.get("depot_expand_cap", 1000))
            if cost > p["cash"]:
                raise GameError(tx("e.cost", cost=money(cost), cash=money(p["cash"])))
            p["cash"] -= cost
            d["level"] = int(d.get("level", 0)) + 1
            self._book(p, "depot", -cost)
            return tx("m.depot_expanded", port=name, qty="{:,}".format(add),
                      cap="{:,}".format(depot_cap(d["level"])), cost=money(cost))
        if port in deps:
            raise GameError(tx("e.depot_open_already", port=name))
        cost = int(f.get("depot_open_cost", 10000))
        if cost > p["cash"]:
            raise GameError(tx("e.cost", cost=money(cost), cash=money(p["cash"])))
        p["cash"] -= cost
        deps[port] = {"goods": {}, "level": 0}
        self._book(p, "depot", -cost)
        return tx("m.depot_opened", port=name, cap="{:,}".format(depot_cap(0)), cost=money(cost))

    def _home_only(self, p, what):
        if p["port"] != home_of(p):
            raise GameError(tx("e.home_only", what=what, home=PORTS[home_of(p)]["name"]))

    def _act_bank(self, p, a):
        if not port_has(p, p["port"], "bank"):
            raise GameError(tx("e.no_bank_here", port=PORTS[p["port"]]["name"], home=PORTS[home_of(p)]["name"]))
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
            rate = "{:g}".format(round(loan_rate() * 100, 2))
            c = self.collectors(p)
            share = float(R["bank"].get("wu_easy_share", 0.25))
            tier = "danger" if c and c["calls_in"] else \
                "careful" if c and p["debt"] >= share * c["line"] else "easy"
            return self._wu(p, "m.borrowed", tier, amount=money(q), rate=rate)
        q = min(q, int(math.ceil(p["debt"])), int(p["cash"]))
        if q <= 0:
            raise GameError(tx("e.nothing_to_repay"))
        before = self.collectors(p)
        p["debt"] = max(0.0, p["debt"] - q)
        p["cash"] -= q
        if p["debt"] < 1:
            p["debt"] = 0.0
        self._tally(p, "loan", q)
        after = self.collectors(p)
        if p["debt"] <= 0:
            tier = "clear"
        elif after and after["calls_in"]:
            tier = "still"
        elif before and before["calls_in"]:
            tier = "under"
        else:
            tier = "part"
        return self._wu(p, "m.repaid", tier, amount=money(q),
                        suggest=money(after["to_clear"]) if after and after["calls_in"] else "")

    def _wu(self, p, key, tier, **kw):
        """Madam Wu's word on a loan or a repayment: the receipt and her advice for how close the debt is
        to the collectors' line. tier: easy / careful / danger (borrowing), part / still / under / clear
        (repaying; "still" means still headed for a call, with {suggest} the amount that stops it).
        She takes each tier's lines in turn (p["wu_said"]), so no dice are rolled and replays match.
        Off (Admin > Economy > Bank and moneylender), or with a tier's lines all deleted: the plain receipt."""
        if R["bank"].get("wu_advice", True):
            count = 0
            while "{}.{}.{}".format(key, tier, count) in TEXT:
                count += 1
            if count:
                n = int(p.get("wu_said", 0))
                p["wu_said"] = n + 1
                return tx("{}.{}.{}".format(key, tier, n % count), home=PORTS[home_of(p)]["name"], **kw)
        return tx(key, **kw)

    def _act_warehouse(self, p, a):
        store = self._store_here(p)
        if store is None:
            if port_has(p, p["port"], "warehouse"):
                raise GameError(tx("e.depot_not_open", port=PORTS[p["port"]]["name"]))
            raise GameError(tx("e.no_warehouse_here", port=PORTS[p["port"]]["name"]))
        wh = store["goods"]
        g, q = self._good(a), self._qty(a)
        if a.get("op") == "store":
            q = min(q, p["cargo"].get(g, 0) - self.sealed(p, g), store["cap"] - sum(wh.values()))
            if q <= 0:
                raise GameError(tx("e.nothing_to_store"))
            p["cargo"][g] -= q
            if not p["cargo"][g]:
                del p["cargo"][g]
            wh[g] = wh.get(g, 0) + q
            self._tally(p, "wh", q)
            return tx("m.stored", qty=q, good=GOODS[g]["name"])
        q = min(q, wh.get(g, 0), self.capacity(p) - self.used(p))
        if q <= 0:
            raise GameError(tx("e.nothing_to_load"))
        wh[g] -= q
        if not wh[g]:
            del wh[g]
        p["cargo"][g] = p["cargo"].get(g, 0) + q
        self._tally(p, "wh", q)
        return tx("m.loaded", qty=q, good=GOODS[g]["name"])

    def _act_buy_ship(self, p, a):
        kind = a.get("ship")
        if kind not in SHIPS:
            raise GameError(tx("e.unknown_ship"))
        if not port_has(p, p["port"], "shipyard"):
            raise GameError(tx("e.no_shipyard", port=PORTS[p["port"]]["name"]))
        role = role_of(kind)
        limit, have = role_limit(role), self.class_count(p, role)
        if have >= limit:
            raise GameError(tx("e.fleet_limit", n=limit) if role == "trader"
                            else tx("e.class_limit." + role, n=limit))
        need = role_unlock(role)
        if role != "trader" and self.class_count(p, "trader") < need:
            raise GameError(tx("e.class_locked." + role, n=need, have=self.class_count(p, "trader")))
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
        if not port_has(p, p["port"], "shipyard"):
            raise GameError(tx("e.no_shipyard", port=PORTS[p["port"]]["name"]))
        if len(p["ships"]) <= 1:
            raise GameError(tx("e.last_ship"))
        if R["fleet"].get("keep_trader", True) and role_of(sh["type"]) == "trader" \
                and self.class_count(p, "trader") <= 1:
            raise GameError(tx("e.last_trader"))
        if self.capacity(p) - SHIPS[sh["type"]]["hold"] < self.used(p):
            raise GameError(tx("e.unload_first"))
        value = int(self.ship_value(sh))
        p["ships"].remove(sh)
        p["cash"] += value
        self._detail = {"ship": sh["type"], "name": sh["name"], "value": value}
        return tx("m.ship_sold", name=sh["name"], value=money(value))

    def trade_down_offer(self, p):
        """A house down to its last ship may swap her at a shipyard for a sound junk (the wreck
        replacement: Admin > Rules > Shipwreck) and take the difference in silver. This is the way back
        for a house with no silver that Madam Wu will not lend to. None when it does not apply."""
        wk = R["wreck"]
        kind = wk["ship"] if wk.get("ship") in SHIPS else min(SHIPS, key=lambda k: SHIPS[k]["price"])
        if len(p["ships"]) != 1 or p["ships"][0]["type"] == kind:
            return None
        spec = SHIPS[kind]
        guns = max(0, min(int(wk.get("guns", 2)), spec["slots"]))
        value = int(self.ship_value(p["ships"][0]) - spec["price"] - guns * R["fleet"]["gun_price"])
        if value <= 0:
            return None
        return {"kind": kind, "guns": guns, "value": value, "hold": spec["hold"], "name": p["ships"][0]["name"],
                "junk": spec["name"]}

    def _act_trade_down(self, p, a):
        if not port_has(p, p["port"], "shipyard"):
            raise GameError(tx("e.no_shipyard", port=PORTS[p["port"]]["name"]))
        if len(p["ships"]) != 1:
            raise GameError(tx("e.trade_down_fleet"))
        offer = self.trade_down_offer(p)
        if offer is None:
            wk = R["wreck"].get("ship")
            raise GameError(tx("e.trade_down_none", name=p["ships"][0]["name"],
                               junk=SHIPS[wk]["name"] if wk in SHIPS else "junk"))
        if self.used(p) > offer["hold"]:
            raise GameError(tx("e.trade_down_cargo", junk=offer["junk"], hold=offer["hold"]))
        old = p["ships"][0]
        new = {"type": offer["kind"], "name": old["name"], "hull": SHIPS[offer["kind"]]["hull"], "guns": offer["guns"],
               "cannons": 0}
        p["ships"] = [new]
        p["cash"] += offer["value"]
        self._detail = {"ship": old["type"], "name": old["name"], "to": offer["kind"], "value": offer["value"],
                        "note": "traded down {} -> {} with {} guns".format(old["type"], offer["kind"], offer["guns"])}
        return tx("m.traded_down", old=SHIPS[old["type"]]["name"], name=old["name"], junk=offer["junk"],
                  guns=offer["guns"], value=money(offer["value"]))

    def _act_buy_gun(self, p, a):
        sh = self._ship(p, a)
        price = R["fleet"]["gun_price"]
        if self.mounts_free(sh) < 1:
            raise GameError(tx("e.no_more_guns", name=sh["name"]))
        if price > p["cash"]:
            raise GameError(tx("e.gun_cost", price=money(price)))
        p["cash"] -= price
        self._tally(p, "yard", price)
        sh["guns"] += 1
        return tx("m.gun_mounted", name=sh["name"])

    def _act_buy_cannon(self, p, a):
        """Only ships marked for cannons (the barque and the East Indiaman as shipped) take them. A cannon
        fires like rules.fleet.cannon_power guns but takes rules.fleet.cannon_slots mounts, so a full
        deck has to sell guns to make room."""
        sh = self._ship(p, a)
        spec, price, cs = SHIPS[sh["type"]], cannon_price(), cannon_slots()
        if not spec.get("cannons"):
            raise GameError(tx("e.no_cannons", name=sh["name"], ship=spec["name"]))
        if self.mounts_free(sh) < cs:
            raise GameError(tx("e.no_cannon_room", name=sh["name"], n=cs))
        if price > p["cash"]:
            raise GameError(tx("e.cannon_cost", price=money(price)))
        p["cash"] -= price
        self._tally(p, "yard", price)
        sh["cannons"] = sh.get("cannons", 0) + 1
        self._detail = {"name": sh["name"], "price": price}
        return tx("m.cannon_mounted", name=sh["name"])

    def _act_sell_gun(self, p, a):
        sh = self._ship(p, a)
        if sh["guns"] < 1:
            raise GameError(tx("e.no_gun_to_sell", name=sh["name"]))
        value = int(R["fleet"]["gun_price"] * R["fleet"]["gun_resale"])
        sh["guns"] -= 1
        p["cash"] += value
        self._detail = {"name": sh["name"], "value": value}
        return tx("m.gun_sold", name=sh["name"], value=money(value))

    def _act_sell_cannon(self, p, a):
        sh = self._ship(p, a)
        if sh.get("cannons", 0) < 1:
            raise GameError(tx("e.no_cannon_to_sell", name=sh["name"]))
        value = int(cannon_price() * R["fleet"]["gun_resale"])
        sh["cannons"] -= 1
        p["cash"] += value
        self._detail = {"name": sh["name"], "value": value}
        return tx("m.cannon_sold", name=sh["name"], value=money(value))

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
        self._book(p, "repairs", -spent)
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
        self._book(p, "protection", -cost)
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
        self._check_promotions()
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
            if s["phase"] == "sea":
                self._sea_force()
                return "Every fight was finished on standing orders and the turn ended."
            if s["phase"] != "port":
                raise GameError("The game is not in progress.")
            self.resolve("admin", a.get("present") if isinstance(a.get("present"), list) else None)
            return "Turn ended."
        if s["phase"] == "sea" and op in ("finish", "kick", "adjust", "years"):
            self._sea_force()                # finish the month before the game is changed under it
        if op == "years":
            s["years"] = int(number("years", 1, 100))
            if s["phase"] == "ended" and s["turn"] < s["years"] * 12:
                s["phase"] = "port"
            elif s["phase"] == "port" and s["turn"] >= s["years"] * 12 and not s.get("free_play"):
                self._finish()
            return "Game length set to {} years.".format(s["years"])
        if op == "finish":
            if s["phase"] != "port":
                raise GameError("The game is not in progress.")
            if s.get("free_play"):
                # The real ending already happened; closing free play keeps the final standings as they were.
                s["phase"] = "ended"
                s.pop("free_play", None)
                self._ev("turn", "free_play_closed", "Free play was closed from the Admin page")
                return "Free play has been closed. The final standings are unchanged."
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
            self._stamp_news(admin=True)
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
        """Turn the month. Voyages are sailed first; a house that meets pirates while its captain is
        at a screen fights on that screen, and the month waits "at sea" (nobody lands) until every
        fight is over. Then _resolve_finish does the rest."""
        s, rng = self.s, self.rng
        if s.get("sea"):                     # already at sea: finish the open fights on standing orders
            self._sea_force()
            return
        news = []
        label = date_label(s["turn"])
        b = R["bank"]
        why = {"all_ready": "everyone present has given orders", "host": "the host ended the month",
               "admin": "the admin ended the month"}.get(cause, cause)
        orders = {q["id"]: {"name": q["name"], "ready": q["ready"], "dest": q["dest"], "orders": q["orders"],
                            "present": None if present is None else q["id"] in present}
                  for q in (s["players"][i] for i in s["order"])}
        self._ev("turn", "turn_resolve", "Resolving {} ({})".format(label, why), do="resolve", cause=cause,
                 date=label, orders=orders, present=None if present is None else sorted(present))
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
            p.pop("fights", None)
            self._settle_customs(p)
        self._drift_tax_rates()          # the new month's rates, quoted to every ship that arrives
        origins = {p["id"]: [p["port"], bool(p["ready"] and p["dest"])] for p in players}
        s["sea"] = {"cause": cause, "label": label, "actual": actual, "news": news, "origins": origins,
                    "order": [p["id"] for p in players], "present": None if present is None else sorted(present)}
        for p in players:
            if p["ready"] and p["dest"]:
                self._depart(p, news)
                p["voy"] = {"stage": 0, "origin": p["port"], "dest": p["dest"]}
                self._voyage_step(p)
            else:
                p["log"].append(tx("l.anchor", port=PORTS[p["port"]]["name"]))
                self._ev("voyage", "anchor", "{} stayed at anchor in {}{}".format(
                    p["name"], PORTS[p["port"]]["name"], "" if p["ready"] else " (gave no orders)"), p,
                    port=p["port"], gave_orders=p["ready"])
            p["ready"], p["dest"], p["slip"] = False, None, False
        self._sea_check()

    def _sea_check(self):
        """Still at sea while any house is in a fight; otherwise the month is finished."""
        s = self.s
        if not s.get("sea"):
            return
        fighting = [p for p in s["players"].values() if p.get("battle") is not None]
        if fighting:
            if s["phase"] == "port":
                s["phase"] = "sea"
                self._ev("turn", "at_sea", "The month waits at sea: {} in a fight".format(
                    ", ".join(p["name"] for p in fighting)), fighting=[p["id"] for p in fighting])
            return
        self._resolve_finish()

    def _sea_force(self):
        """Finish every open fight on standing orders (the host or the admin ended the month)."""
        s = self.s
        if not s.get("sea"):
            return
        for pid in s["sea"]["order"]:
            p = s["players"].get(pid)
            if p is not None and p.get("battle") is not None:
                p["battle"]["auto"] = True
                self._voyage_step(p)
        self._sea_check()

    def _resolve_finish(self):
        s, rng = self.s, self.rng
        sea = s.pop("sea")
        if s["phase"] == "sea":
            s["phase"] = "port"
        news, label, origins, b = sea["news"], sea["label"], sea["origins"], R["bank"]
        players = [s["players"][pid] for pid in sea["order"] if pid in s["players"]]
        for p in players:
            p.pop("voy", None)
            p.pop("battle", None)
        for p in players:
            bank0, debt0 = p["bank"], p["debt"]
            if p["bank"] > 0:
                p["bank"] *= 1 + b["bank_rate"]
            if p["debt"] > 0:
                p["debt"] *= 1 + loan_rate()
                # Collectors: a grace period after debt first passes the line, then a call every few months.
                # "debt_over" counts the months in a row spent over the line (old saves start at 0).
                if p["debt"] > self.collectors_line(p):
                    p["debt_over"] = int(p.get("debt_over", 0)) + 1
                    grace = max(0, int(b.get("debt_grace_months", 0)))
                    every = max(1, int(b.get("debt_call_every", 1)))
                    if p["debt_over"] > grace and (p["debt_over"] - grace - 1) % every == 0:
                        self._gain_rep(p, home_of(p), -b["debt_rep_penalty"])
                        p["log"].append(tx("l.collectors", home=PORTS[home_of(p)]["name"]))
                        self._ev("finance", "collectors", "{}: debt {} is over the collectors' line {} (month {} over "
                                 "the line; grace {}, then every {}); standing in {} fell by {}".format(
                                     p["name"], money(p["debt"]), money(self.collectors_line(p)),
                                     p["debt_over"], grace, every, PORTS[home_of(p)]["name"], b["debt_rep_penalty"]), p)
                    elif p["debt_over"] == 1:
                        # First month over the line: a warning only, no standing lost.
                        p["log"].append(tx("l.collectors_warn", months=grace, s="" if grace == 1 else "s",
                                           home=PORTS[home_of(p)]["name"]))
                        self._ev("finance", "collectors_warn", "{}: debt {} is over the collectors' line {}; warned, "
                                 "no penalty. The collectors first call after {} month(s) of grace".format(
                                     p["name"], money(p["debt"]), money(self.collectors_line(p)), grace), p)
                else:
                    p["debt_over"] = 0
            self._book(p, "bank_interest", p["bank"] - bank0)
            self._book(p, "interest", -(p["debt"] - debt0))
            if bank0 > 0 or debt0 > 0:
                self._ev("finance", "interest", "{}: bank interest +{} at {}, loan interest +{} at {}".format(
                    p["name"], money(p["bank"] - bank0), pct(b["bank_rate"]), money(p["debt"] - debt0), pct(loan_rate())),
                    p, bank=[round(bank0, 2), round(p["bank"], 2)], debt=[round(debt0, 2), round(p["debt"], 2)])
            if p.get("fame"):
                p["fame"] = round(float(p["fame"]) * (1 - float(R["battle"].get("fame_decay", 0.1))), 3)
                if p["fame"] < 0.05:
                    p["fame"] = 0.0
            if p["protect"] > 0:
                p["protect"] -= 1
                if p["protect"] == 0:
                    p["log"].append(tx("l.protect_lapsed"))
                    self._ev("finance", "protect_lapsed", "{}: protection has run out".format(p["name"]), p)
                elif p["protect"] == R["liyuen"]["renew_at"]:
                    p["log"].append(tx("l.protect_low", months=p["protect"], s="" if p["protect"] == 1 else "s",
                                       home=PORTS[home_of(p)]["name"]))
                    self._ev("finance", "protect_low", "{}: protection runs out in {} month(s); warned".format(
                        p["name"], p["protect"]), p)
            # Standing in the port where the house is ashore: 50 gives the base chance, 100 cuts it by
            # mug_rep, 0 raises it by the same amount.
            mug_st = float(p["rep"].get(p["port"], 50.0))
            mug_odds = b["mug_chance"] * max(0.0, 1 + b.get("mug_rep", 0.0) * (50.0 - mug_st) / 50.0)
            if p["cash"] > b["mug_threshold"] and self._chance(mug_odds, "robbery", "{}: robbed ashore (carrying over {}, standing {:.0f})".format(
                    p["name"], money(b["mug_threshold"]), mug_st), p):
                lost = int(p["cash"] * rng.uniform(b["mug_min"], b["mug_max"]))
                p["cash"] -= lost
                self._book(p, "robbed", -lost)
                p["log"].append(tx("l.robbed", lost=money(lost)))
                self._ev("finance", "robbed", "{} was robbed of {}".format(p["name"], money(lost)), p, lost=lost)
            self._rob_warehouses(p, news, b, rng)

        self._move_markets(news)
        for p in players:
            self._close_books(p, *origins[p["id"]])
            self._tidy_basis(p)
        s["turn"] += 1
        self._note_history()
        self._roll_weather()
        for p in players:
            self._note_prices(p)
            self._promote(p)
        for n in news:
            self._ev("news", "news", "News: " + n, turn=s["turn"] - 1)
        s["news"] = ["{}: {}".format(label, n) for n in news] + s["news"]
        s["news"] = s["news"][:40]
        self._stamp_news()
        if s["turn"] >= s["years"] * 12 and not s.get("free_play"):
            self._finish()
        self._reseed()
        self.checkpoint("turn_begin")

    def _finish(self):
        s = self.s
        s["phase"] = "ended"
        s["ended_at"] = time.time()
        s.pop("free_play", None)
        ranked = sorted(s["players"].values(), key=self.worth, reverse=True)
        s["final_winner"] = ranked[0]["id"] if ranked else None
        if ranked:
            s["news"].insert(0, "{}: {}".format(date_label(s["turn"]), tx(
                "n.game_over", name=ranked[0]["name"], firm=ranked[0]["firm"], worth=money(self.worth(ranked[0])))))
            self._stamp_news()
        self._ev("turn", "game_over", "The game is over. " + ("Final standings: " + "; ".join(
            "{}. {} ({}) {}".format(i + 1, q["name"], q["firm"], money(self.worth(q))) for i, q in enumerate(ranked))
            if ranked else "Nobody was playing."),
            standings=[{"id": q["id"], "name": q["name"], "firm": q["firm"], "worth": int(self.worth(q)),
                        "rank": self.commissioned_rank(q)["title"]} for q in ranked])

    def _free_play(self, p):
        """After the last month (or the Admin's Finish), any captain can carry the world on: the
        final standings and the winner stay as they were, and trading and sailing go on with no end date."""
        s = self.s
        if s.get("free_play") and s["phase"] in ("port", "sea"):
            return tx("m.free_play_on")
        if s["phase"] != "ended":
            raise GameError(tx("e.free_play"))
        s["phase"] = "port"
        s["free_play"] = True
        s.setdefault("free_play_from", s["turn"])
        for q in s["players"].values():
            q["ready"], q["dest"], q["slip"] = False, None, False
        s["news"].insert(0, "{}: {}".format(date_label(s["turn"]), tx("n.free_play", name=p["name"], firm=p["firm"])))
        s["news"] = s["news"][:40]
        self._stamp_news()
        self._ev("turn", "free_play", "{} ({}) opened free play: the final standings stand and trading carries on".format(
            p["name"], p["firm"]), p)
        return tx("m.free_play")

    def voyage_story(self):
        players = self.s["players"]
        if not players:
            return None
        winner = players.get(self.s.get("final_winner")) \
            or max((players[pid] for pid in self.s["order"]), key=self.worth)
        log = (winner.get("books") or {}).get("logbook", [])
        route = next((entry for entry in log if entry.get("from") in PORTS
                      and entry.get("to") in PORTS and entry["from"] != entry["to"]), None)
        return {"id": winner["id"], "name": winner["name"], "firm": winner["firm"], "port": winner["port"],
                "ships": len(winner["ships"]), "route": route and {
                    "date": route["date"], "from": route["from"], "to": route["to"]}}

    def _move_markets(self, news):
        s, rng, ev, m = self.s, self.rng, R["events"], R["market"]
        s["shocks"] = [dict(sh, turns=sh["turns"] - 1) for sh in s["shocks"] if sh["turns"] > 1]
        ending = [w for w in s.get("windfalls", []) if w["turns"] <= 1 and w.get("foretold") and w.get("kind") == "boom"]
        s["windfalls"] = [dict(w, turns=w["turns"] - 1) for w in s.get("windfalls", []) if w["turns"] > 1]
        for w in ending:
            if w["port"] in PORTS and w["good"] in GOODS:
                self._hot_over(w)
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
        self._roll_windfalls(news)
        self._land_forecasts(news)
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
        hot_hold = bool((R.get("registrar") or {}).get("hot_hold", True))
        for port in PORTS:
            for g, spec in GOODS.items():
                base = spec["base"] * PORTS[port]["mods"].get(g, 1.0)
                price = s["prices"][port][g]
                price += m["reversion"] * (self._target(port, g) - price)
                price *= math.exp(rng.gauss(0, spec["vol"] * m["vol_mult"]))
                w = self._windfall(port, g)
                if w:                                       # a crash or boom runs past the usual limits
                    price = max(1.0, price)
                    # A boom from a hot tip holds: the month's swing can lift it but never take it below
                    # the level that was foretold (rules.registrar.hot_hold). Selling into it still moves
                    # the price, and it comes back up to that level next month while the boom runs.
                    if w.get("foretold") and w.get("kind") == "boom" and hot_hold:
                        price = max(price, base * float(w.get("mult", 1.0)))
                    s["prices"][port][g] = price
                else:
                    s["prices"][port][g] = max(m["floor"] * base, min(m["ceiling"] * base, price))
        moves = sorted(((s["prices"][port][g] / before[port][g] - 1, port, g) for port in PORTS for g in GOODS
                        if before[port].get(g)), key=lambda t: -abs(t[0]))[:6]
        self._ev("market", "prices", "Markets moved. Biggest changes: " + "; ".join(
            "{} in {} {:+.0%} ({:,.0f} -> {:,.0f})".format(GOODS[g]["name"], PORTS[port]["name"], ch, before[port][g],
                                                           s["prices"][port][g]) for ch, port, g in moves),
            movers=[{"port": port, "good": g, "change": round(ch, 4), "from": round(before[port][g], 2),
                     "to": round(s["prices"][port][g], 2)} for ch, port, g in moves])

    # ---------------------------------------------------------- voyages --
    def _voyage_step(self, p):
        """Sail a voyage as far as it will go: to the end, or until a fight needs the captain.
        Stages: 0 put to sea (storms), 1 pirates, 2 the pirate lord's fleet, 3 landfall."""
        v = p.get("voy")
        if not v:
            return
        rng, log = self.rng, p["log"]
        sea = self.s["sea"]
        actual, news = sea["actual"], sea["news"]
        w, pi, ly, cb = R["weather"], R["pirates"], R["liyuen"], R["contraband"]
        who = p["name"]
        while True:
            if p.get("battle") is not None:
                if self._battle_live(p):
                    return                      # the captain is choosing; the month waits
                self._battle_step(p, "auto")
                continue
            origin, dest = v["origin"], v["dest"]
            if v["stage"] == 0:
                v["stage"] = 1
                risk = max(w["risk_min"], min(w["risk_max"], distance(origin, dest) / float(w["risk_div"])))
                level = max(actual[PORTS[origin]["region"]], actual[PORTS[dest]["region"]])
                v["risk"], v["level"] = risk, level
                log.append(tx("l.sailed", origin=PORTS[origin]["name"], dest=PORTS[dest]["name"],
                              weather=tx("l.sea.{}".format(level))))
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
                        dest = v["dest"] = rng.choice(others)
                        log.append(tx("l.offcourse", port=PORTS[dest]["name"]))
                        self._ev("voyage", "offcourse", "{} was blown off course to {}".format(who, PORTS[dest]["name"]), p, dest=dest)
            elif v["stage"] == 1:
                v["stage"] = 2
                risk = v["risk"]
                allure = self._allure(p) if R["battle"].get("match") else 1.0
                if p["ships"] and self._chance(pi["chance"] * risk * MULT["pirates"] * allure, "pirates",
                                               "{}: pirate attack{}".format(who, " (their appetite x{:.2f})".format(allure)
                                                                            if allure != 1.0 else ""), p):
                    muster = None
                    if R["battle"].get("match"):
                        muster = self._muster(p, "pirates", dest)
                        n = muster["n"]
                    else:
                        top = max(pi["fleet_min"], pi["fleet_base"] + self.capacity(p) // pi["fleet_per_hold"])
                        n = int(rng.randint(pi["fleet_min"], top) * risk)
                        n = max(1, min(n, pi["fleet_max"]))
                    if p["protect"] > 0 and self._chance(ly["protect_save"], "protection",
                                                         "{}: {}'s fleet drives off {} pirate junks".format(who, TOKENS["pirate"], n), p):
                        log.append(tx("l.driven_off", n=n))
                    else:
                        self._battle_open(p, n, "pirates", muster)
            elif v["stage"] == 2:
                v["stage"] = 3
                risk = v["risk"]
                if p["ships"] and p["protect"] <= 0 and self._chance(ly["chance"] * risk * MULT["pirates"], "pirate_lord",
                                                                      "{}: found by {}'s fleet (no protection)".format(who, TOKENS["pirate"]), p):
                    muster = self._muster(p, "lord", dest) if R["battle"].get("match") else None
                    n = muster["n"] if muster else min(ly["fleet_max"], ly["fleet_base"] + self.capacity(p) // ly["fleet_per_hold"])
                    log.append(tx("l.lord_found"))
                    self._battle_open(p, n, "lord", muster)
            else:
                p.pop("voy", None)
                if not p["ships"]:
                    self._shipwreck(p, news)
                    return
                p["port"] = dest
                p["tab"] = self._new_tab()
                p["net"] = {}
                self._mayor_greeting(p)
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
                        self._book(p, "seized", -self._cost_of(p, {g: p["cargo"].get(g, 0) for g in risky}))
                        self._book(p, "fines", -fine)
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
                return

    # ------------------------------------------------------- sea battles --
    # A fight is a small state on the house (p["battle"]) played one step at a time. A captain at a
    # screen chooses each round (fight, run, retreat; or pays the pirates' price before the first
    # shot); a house with nobody at the helm plays every round on its standing orders, exactly as
    # battles were always settled. A fight played on screen rolls its own dice from its own seed,
    # so it comes out the same whatever else is going on around it.
    SEA_CHOICES = ("fight", "run", "retreat", "pay", "auto", "skip")

    def _battle_live(self, p):
        """Is this fight being played by its captain (rather than on standing orders)?"""
        b = p.get("battle")
        return bool(b) and b.get("seed") is not None and not b.get("auto")

    # The enemy's voice (the right-hand seat): Admiral Li Yue speaks for her own war junks, Madam Shek
    # Yu-lan for the ordinary pirate junks. She speaks at the key moments only, after the bosun, from her
    # own pool of lines (battle.foe.<cast key>.<pool>.<n>). Each pool has the mood her picture shows.
    FOE_MOOD = {"sighting": "speaking", "price": "speaking", "lowball": "sly", "reprice": "angry", "paid": "happy",
                "lost_junk": "angry", "sank_ours": "happy", "hit_us": "happy", "noguns": "happy", "got_away": "angry",
                "broke_off": "angry", "retreat": "happy", "defeated": "angry", "victory": "happy", "plunder": "happy"}

    def _foe_start(self, b):
        """Called when a step of a fight starts: who speaks for this enemy."""
        self._foe_who = "pirate" if b.get("kind") == "lord" else "agent"
        self._foe_n = 0

    def _frame(self, moment, cap, say=None, foe=None, **kw):
        """One picture-and-caption of a fight. say: the pool of the bosun's spoken lines to draw from;
        foe: the pool of the enemy's answering line, if she speaks on this picture."""
        f = {"moment": moment, "cap": tx("battle.cap." + cap, **kw)}
        if say:
            count = 0
            while "battle.say.{}.{}".format(say, count) in TEXT:
                count += 1
            if count:
                self._said = getattr(self, "_said", 0) + 1
                f["say"] = tx("battle.say.{}.{}".format(say, (self._say_from + self._said) % count))
        who = getattr(self, "_foe_who", "")
        if foe and who and R["battle"].get("foe_voice", True):
            base = "battle.foe.{}.{}.".format(who, foe)
            count = 0
            while base + str(count) in TEXT:
                count += 1
            if count:
                self._foe_n = getattr(self, "_foe_n", 0) + 1
                f["foe"] = tx(base + str((self._say_from * 7 + self._foe_n) % count))
                f["foe_by"] = who
                f["foe_mood"] = self.FOE_MOOD.get(foe, "speaking")
        return f

    # ---- matched fights (rules.battle.match) --------------------------------------------------
    # Pirates come out to fight a fleet they think they can take. The fleet they put to sea is sized
    # from the house's own strength: its firepower sets how much hull the enemy brings (enough to
    # last match_rounds of our fire), its hull sets how hard they hit back. The match ratio says how
    # close the fight is (1 = an even fight: they would sink us as fast as we sink them). It grows
    # with the cargo aboard (a rich hold draws hungrier hunters), with the house's fame at sea (every
    # win makes a name worth taking), and falls with the house's standing in the port it is making for.
    def temptation(self, p):
        """0 to 1: how much the cargo aboard is worth to a pirate (half way at rules.battle.match_cargo_ref)."""
        value = sum(q * GOODS[g]["base"] for g, q in p["cargo"].items() if g in GOODS)
        ref = max(1.0, float(R["battle"].get("match_cargo_ref", 100000)))
        return value / (value + ref)

    def fame_share(self, p):
        return min(1.0, float(p.get("fame", 0) or 0) / max(0.1, float(R["battle"].get("fame_ref", 10))))

    def _allure(self, p):
        """How keen the pirates are on this fleet: an empty hold and no name draws fewer of them."""
        bt = R["battle"]
        return max(0.0, bt["allure_base"] + bt["allure_cargo"] * self.temptation(p) + bt["allure_fame"] * self.fame_share(p))

    def _muster(self, p, kind, dest=None):
        """The enemy fleet for a matched fight: how many junks, each one's hull (shots to sink her) and guns."""
        rng, bt, pi = self.rng, R["battle"], R["pirates"]
        src = pi if kind == "pirates" else R["liyuen"]
        lord = kind == "lord"
        fire = max(1.0, self.firepower(p) * pi["gun_hit"])          # enemy hull we strip each round
        # Their guns are sized from the hull they mean to take: the merchantmen and cargo ships in full, the
        # escorts only in part (match_escort_share), so escorts soak up fire meant for the line and the rear.
        es = float(bt.get("match_escort_share", 0.5))
        hull = max(1, sum(max(0, sh["hull"]) * (es if role_of(sh["type"]) == "escort" else 1.0) for sh in p["ships"]))
        tempt, fame = self.temptation(p), self.fame_share(p)
        standing = (float(p["rep"].get(dest, 50.0)) - 50.0) / 50.0 if dest in PORTS else 0.0
        lo, hi = sorted((float(bt["match_rounds_min"]), float(bt["match_rounds_max"])))
        rounds = max(1.0, rng.uniform(lo, hi))
        noise = rng.gauss(0, float(bt["match_spread"]))
        m = (bt["match_base"] + bt["match_cargo"] * tempt + bt["match_fame"] * fame
             - bt["match_standing"] * standing + noise + (bt["match_lord"] if lord else 0.0))
        m = max(float(bt["match_min"]), min(float(bt["match_max"]), m)) * MULT.get("pirates", 1.0) ** 0.35
        their_hull = fire * rounds                                  # sum of the junks' hit points
        per_shot = src["hit"] * (src["dmg_min"] + src["dmg_max"]) / 2.0
        their_fire = hull * m / rounds                              # our hull they would take off each round
        size = rng.uniform(float(bt["match_hp_min"]), float(bt["match_hp_max"])) * (1.5 if lord else 1.0)
        top = int(bt["match_lord_ships_max"] if lord else bt["match_ships_max"])
        n = max(int(bt["match_ships_min"]), min(top, int(round(their_hull / max(1.0, size)))))
        weights = [float(bt.get("match_flag", 2.0))] + [rng.uniform(0.7, 1.3) for _ in range(n - 1)]
        total = sum(weights)
        hp = [max(1, int(round(their_hull * w / total))) for w in weights]
        guns_all = max(n, int(round(their_fire / max(0.1, per_shot))))
        raw = [guns_all * w / total for w in weights]
        guns = [max(1, int(r)) for r in raw]
        for i in sorted(range(n), key=lambda i: -(raw[i] - int(raw[i])))[:max(0, guns_all - sum(guns))]:
            guns[i] += 1
        return {"n": n, "hp": hp, "guns": guns, "match": round(m, 3), "rounds": round(rounds, 2),
                "temptation": round(tempt, 3), "fame": round(fame, 3), "standing": round(standing, 3),
                "worth_n": their_hull / max(1.0, float(pi["hp"]))}

    # ---- where the enemy's fire lands (the fleet's formation) ----------------------------------
    # Escorts sail in the van and take the fire; merchantmen sail in the line; cargo ships in the rear,
    # screened by the escorts (and half as well by merchantmen) in front of them. With focus, each enemy
    # junk lays its whole broadside on the weakest ship of the front rank, so the van is ground down
    # one ship at a time and the rear grows more exposed as it goes.
    def _formation_weight(self, sh, ships):
        bt, r = R["battle"], role_of(sh["type"])
        if r == "escort":
            return float(bt["van_weight"])
        if r == "trader":
            return float(bt["line_weight"])
        alive = [x for x in ships if x["hull"] > 0]
        rear = sum(1 for x in alive if role_of(x["type"]) == "cargo")
        cover = sum(1.0 if role_of(x["type"]) == "escort" else 0.5 if role_of(x["type"]) == "trader" else 0.0
                    for x in alive)
        screen = min(1.0, cover / max(1, rear))
        return float(bt["rear_weight"]) * max(0.05, 1.0 - float(bt["rear_cover"]) * screen)

    def _pick_target(self, b, ships):
        rng = self.rng
        alive = [sh for sh in ships if sh["hull"] > 0]
        if not alive:
            return None
        if b.get("focus") and rng.random() < b["focus"]:
            for rank in ROLES:                                  # van, then line, then rear
                front = [sh for sh in alive if role_of(sh["type"]) == rank]
                if front:
                    return min(front, key=lambda sh: (sh["hull"] / float(SHIPS[sh["type"]]["hull"] or 1), sh["name"]))
        weights = [self._formation_weight(sh, ships) for sh in alive]
        return rng.choices(alive, weights=weights)[0]

    def _battle_open(self, p, n, kind, muster=None):
        rng, log, pi, bt = self.rng, p["log"], R["pirates"], R["battle"]
        src = pi if kind == "pirates" else R["liyuen"]
        label = tx("w.pirate_junks" if kind == "pirates" else "w.war_junks")
        hit, dmg = src["hit"], [src["dmg_min"], src["dmg_max"]]
        sea = self.s.get("sea") or {}
        live = bool(bt["interactive"] and sea.get("present") is not None and p["id"] in sea["present"])
        orders = p["orders"]
        noguns = orders == "fight" and self.firepower(p) == 0
        if noguns:
            orders = "run"
        dest = (p.get("voy") or {}).get("dest")
        b = {"kind": kind, "label": label, "n": n, "hp": [pi["hp"]] * n, "hit": hit, "dmg": dmg,
             "round": 0, "step": 0, "stage": "fight", "orders": orders, "runs": 0, "seed": None, "auto": not live,
             "fast": all(SHIPS[sh["type"]]["fast"] for sh in p["ships"]),
             "hull0": sum(sh["hull"] for sh in p["ships"]),
             "ships0": [{"name": sh["name"], "type": sh["type"], "hull": sh["hull"], "guns": sh["guns"],
                         "cannons": sh.get("cannons", 0)} for sh in p["ships"]],
             "cargo0": dict(p["cargo"]), "net": 0.0, "booty": 0, "paid": 0, "price": 0, "dest": dest, "beat": None}
        for sh in b["ships0"]:
            sh["role"] = role_of(sh["type"])
        if muster:
            b.update({"hp": list(muster["hp"]), "hpmax": list(muster["hp"]), "eg": list(muster["guns"]),
                      "enemy_hull": sum(muster["hp"]), "enemy_guns": sum(muster["guns"]),
                      "focus": float(bt.get("focus", 0.0)), "formation": True, "worth_n": muster["worth_n"],
                      "match": {k: muster[k] for k in ("match", "rounds", "temptation", "fame", "standing")}})
        else:
            b.update({"hpmax": list(b["hp"]), "eg": [1] * n, "worth_n": n,
                      "formation": any(role_of(sh["type"]) != "trader" for sh in p["ships"])})
        if live:
            b["seed"] = rng.getrandbits(48)
            own = random.Random("{}:open".format(b["seed"]))
            b["dump"] = round(own.uniform(bt["retreat_min"], bt["retreat_max"]), 4)
            if kind == "pirates" and bt["parley"]:
                value = sum(q * GOODS[g]["base"] for g, q in p["cargo"].items() if g in GOODS)
                b["price"] = int(max(1, b["worth_n"] * bt["parley_per_junk"] + bt["parley_cargo"] * value))
                b["stage"] = "parley"
                self._lowball(p, b, value, own)
            log.append(tx("l.attack_met", n=n, enemy=label))
        elif kind == "lord" and R["liyuen"].get("tribute", True):
            pass                                    # nobody at a screen: she is paid or she attacks, logged then
        elif noguns:
            log.append(tx("l.attack_noguns", n=n, enemy=label))
        else:
            log.append(tx("l.attack", n=n, enemy=label, orders=tx("w.fight" if orders == "fight" else "w.run")))
        if kind == "lord" and R["liyuen"].get("tribute", True):
            # She names her price before the first shot: dearer than the tribute at home, and it buys the same months.
            b["price"] = int(max(1, round(R["liyuen"].get("tribute_mult", 2.0) * self.protection_cost(p))))
            b["stage"] = "parley"
        p["battle"] = b
        self._say_from, self._said = (b["seed"] or 0) % 9973, 0
        self._foe_start(b)
        who = p["name"]
        mt = b.get("match")
        self._ev("battle", "battle", "{} attacked by {} {}: orders {}{}, {} guns, hull {}; enemy hits {} per gun per "
                 "round for {}-{}{}{}".format(who, n, label, orders, " (no guns, so running)" if orders != p["orders"] else "",
                                            self.guns(p), "/".join(str(sh["hull"]) for sh in p["ships"]), pct(hit), dmg[0], dmg[1],
                                            ("; matched x{} (cargo {}, fame {}, standing {:+}), {} enemy hull, {} enemy guns, "
                                             "about {} rounds of our fire".format(mt["match"], mt["temptation"], mt["fame"],
                                                                                  mt["standing"], sum(b["hp"]), sum(b["eg"]),
                                                                                  mt["rounds"]) if mt else ""),
                                            ("; fought on screen" if live else "") + ("; they ask {} to let the fleet pass".format(
                                                money(b["price"])) if b["price"] else "")),
                 p, enemy=label, count=n, orders=orders, guns=self.guns(p), hit=hit, dmg=list(dmg),
                 **({"match": mt, "enemy_hp": list(b["hp"]), "enemy_guns": list(b["eg"])} if mt else {}),
                 **({"live": True} if live else {}), **({"parley": b["price"]} if live or b["price"] else {}))
        where = PORTS[dest]["name"] if dest in PORTS else ""
        frames = [self._frame("sighting", "sighting", "sighting", foe="sighting", n=n, enemy=label, port=where)]
        if b["stage"] == "parley":
            talk = "tribute" if kind == "lord" else "lowball" if b.get("lowball") else "parley"
            fr = self._frame("sighting", talk, talk, foe="lowball" if talk == "lowball" else "price", price=money(b["price"]))
            if talk == "lowball":
                fr["mood"] = "sly"
            frames.append(fr)
        b["beat"] = {"id": 0, "frames": frames}

    def _lowball(self, p, b, value, own):
        """They misjudge the hold (rules.battle.lowball): now and then the pirates take a rich fleet for a
        poor coaster and name a price on a fraction of what is really aboard. Small, dear cargo (gold,
        opium: rules.battle.lowball_goods) fools them more often; a famous house fools them seldom.
        Rolled on the fight's own dice, so nothing else in the month changes."""
        bt = R["battle"]
        if not bt.get("lowball", True) or value <= 0:
            return
        dense = set(bt.get("lowball_goods") or ())
        share = sum(q * GOODS[g]["base"] for g, q in p["cargo"].items() if g in dense and g in GOODS) / value
        chance = float(bt["lowball_chance"]) * (1 + float(bt["lowball_dense"]) * share) \
            * max(0.0, 1 - float(bt["lowball_fame"]) * self.fame_share(p))
        if own.random() >= chance:
            return
        lo, hi = sorted((float(bt["lowball_min"]), float(bt["lowball_max"])))
        think = own.uniform(lo, hi)
        full = b["price"]
        b["price"] = int(max(1, b["worth_n"] * bt["parley_per_junk"] + bt["parley_cargo"] * value * think))
        b["lowball"] = {"think": round(think, 3), "full": full, "value": int(value), "chance": round(chance, 3)}
        self._ev("battle", "lowball", "{}: the pirates misjudge the hold ({:.0%} chance): they think it is worth {:.0%} of "
                 "{} and ask {} instead of {}".format(p["name"], chance, think, money(value), money(b["price"]), money(full)),
                 p, chance=round(chance, 4), think=round(think, 4), price=b["price"], full=full)

    def _battle_step(self, p, choice):
        """Play one step of a fight: one round, or the answer to the pirates' price."""
        b = p["battle"]
        keep = self.rng
        if b["seed"] is not None:
            self.rng = random.Random("{}:{}".format(b["seed"], b["step"]))
        try:
            self._battle_round(p, b, choice)
        finally:
            self.rng = keep
        b["step"] += 1

    def _retreat_dump(self, p, b):
        """What goes over the side to break away: a share of the hold, cheapest cargo first."""
        over = int(self.used(p) * b.get("dump", 0.0))
        gone = {}
        for g in sorted(p["cargo"], key=lambda k: GOODS[k]["base"]):
            if over <= 0:
                break
            drop = min(over, p["cargo"][g])
            if drop > 0:
                gone[g] = drop
                over -= drop
        return gone

    def _battle_round(self, p, b, choice):
        rng, log, pi, bt = self.rng, p["log"], R["pirates"], R["battle"]
        who, n, pirates, hit, dmg = p["name"], b["n"], b["hp"], b["hit"], b["dmg"]
        frames = []
        self._say_from, self._said = (b["seed"] or 0) % 9973 + b["step"] * 5, 0
        self._foe_start(b)
        lord = b["kind"] == "lord"
        if choice == "auto":
            # Standing orders say nothing of tribute: with no captain to choose, the house pays her if it can.
            choice = "pay" if lord and b["stage"] == "parley" and p["cash"] >= b["price"] else b["orders"]
        if choice == "fight" and self.firepower(p) == 0:
            choice = "run"                      # every gun dismounted: standing orders to fight become a run for it
        if b["stage"] == "parley":
            if choice == "pay":
                price = b["price"]
                p["cash"] -= price
                b["paid"] = price
                if lord:
                    self._book(p, "protection", -price)
                    p["protect"] = R["liyuen"]["protect_months"]
                    log.append(tx("l.tribute_paid", cost=money(price), months=p["protect"]))
                    self._ev("battle", "paid", "{} paid {} {} {} in tribute at sea; protected for {} months".format(
                        who, n, b["label"], money(price), p["protect"]), p, price=price, tribute=True)
                    frames.append(self._frame("got_away", "tribute_paid", "paid", foe="paid", price=money(price)))
                else:
                    self._book(p, "parley", -price)
                    log.append(tx("l.parley_paid", n=n, enemy=b["label"], cost=money(price)))
                    self._ev("battle", "paid", "{} paid {} {} {} to pass".format(who, n, b["label"], money(price)), p, price=price)
                    frames.append(self._frame("got_away", "paid", "paid", foe="paid", price=money(price)))
                return self._battle_close(p, b, "paid", frames)
            lb = b.get("lowball")
            if lb and not lb.get("seen"):
                # They misjudged the hold; refusing their bargain shows them what is really aboard. They
                # name the true price, and the captain has one more chance to pay before the first shot.
                lb["seen"] = True
                cheap, b["price"] = b["price"], int(lb["full"])
                self._ev("battle", "lowball_refused", "{} refused the bargain of {}; they saw the hold and now ask {}".format(
                    who, money(cheap), money(b["price"])), p, price=b["price"], bargain=cheap)
                fr = self._frame("sighting", "reprice", "reprice", foe="reprice", price=money(b["price"]))
                fr["mood"] = "angry"
                frames.append(fr)
                b["beat"] = {"id": b["step"] + 1, "frames": frames}
                return
            b["stage"] = "fight"
            self._ev("battle", "parley_refused", "{} {} {}".format(
                who, "could not pay" if p["cash"] < b["price"] else "refused to pay", money(b["price"])), p, price=b["price"])
            if lord and b.get("seed") is None:
                # nobody at a screen and no tribute paid: the log line the fight would have opened with
                if b["orders"] != p["orders"]:
                    log.append(tx("l.attack_noguns", n=n, enemy=b["label"]))
                else:
                    log.append(tx("l.attack", n=n, enemy=b["label"], orders=tx("w.fight" if b["orders"] == "fight" else "w.run")))
        rnd = b["round"] + 1
        s = "" if rnd == 1 else "s"

        if choice == "retreat":
            gone = self._retreat_dump(p, b)
            if gone:
                self._book(p, "overboard", -self._cost_of(p, gone))
                for g, q in gone.items():
                    p["cargo"][g] -= q
                p["cargo"] = {g: q for g, q in p["cargo"].items() if q > 0}
            taken_round = self._enemy_fire(p, b, pirates)       # every junk afloat fires as the fleet turns away
            if p["ships"] and all(sh["hull"] <= 0 for sh in p["ships"]):
                last = max(p["ships"], key=lambda sh: sh["hull"])   # a retreat never takes the last ship
                last["hull"] = max(1, min(int(bt["retreat_floor"]), SHIPS[last["type"]]["hull"]))
            qty = sum(gone.values())
            log.append(tx("l.retreated", qty=qty))
            self._ev("battle", "retreat", "{} round {}: broke away from {} of {} {}; {} units over the side ({}); {} parting "
                     "shots, {} hit{}".format(who, rnd, len(pirates), n, b["label"], qty,
                                              ", ".join("{} {}".format(q, GOODS[g]["name"]) for g, q in gone.items()) or "nothing",
                                              len(pirates), len(taken_round), ": " + ", ".join(
                                                  self._hit_text(h) for h in taken_round)
                                              if taken_round else ""),
                     p, round=rnd, lost=gone, hits=taken_round, enemy_left=len(pirates))
            names = [sh["name"] for sh in p["ships"]]
            self._check_sunk(p, tx("l.how_sunk"))
            b["round"] = rnd
            frames.append(self._frame("retreat", "retreat", "retreat", foe="retreat", qty=qty))
            self._hit_frames(p, b, frames, taken_round, names, say=False)
            return self._battle_close(p, b, "retreated", frames)

        if choice == "fight":
            shots = hits = 0
            left0 = len(pirates)
            for _ in range(self.firepower(p)):
                if pirates:
                    shots += 1
                if pirates and rng.random() < pi["gun_hit"]:
                    hits += 1
                    pirates[-1] -= 1
                    if pirates[-1] <= 0:
                        pirates.pop()
                        for key in ("eg", "hpmax"):
                            if len(b.get(key) or []) > len(pirates):
                                b[key].pop()
            self._ev("battle", "round", "{} round {}: {} shots at {} each, {} hit, {} of {} enemy left".format(
                who, rnd, shots, pct(pi["gun_hit"]), hits, len(pirates), n), p, round=rnd, shots=shots, hits=hits,
                enemy_left=len(pirates))
            sunk = left0 - len(pirates)
            if not pirates:
                booty = int(b.get("worth_n", n) * rng.randint(pi["booty_min"], pi["booty_max"])
                            * (1 + self.s["turn"] / float(pi["booty_growth"]))
                            * (float(bt.get("match_booty", 1.0)) if b.get("match") else 1.0))
                p["cash"] += booty
                self._book(p, "booty", booty)
                b["booty"] = booty
                log.append(tx("l.sank_all", n=n, rounds=rnd, s=s, booty=money(booty)))
                self._ev("battle", "won", "{} sank all {} in {} round{} and took {} in booty".format(
                    who, n, rnd, s, money(booty)), p, rounds=rnd, booty=booty)
                b["round"] = rnd
                frames.append(self._frame("victory", "victory", "victory", foe="defeated", n=n, booty=money(booty)))
                self._battle_prize(p, b, frames)
                return self._battle_close(p, b, "won", frames)
            if sunk:
                frames.append(self._frame("enemy_hit", "sunk", "enemy_hit", foe="lost_junk", sunk=sunk, left=len(pirates), n=n))
            elif hits:
                frames.append(self._frame("broadside", "broadside", "broadside", hits=hits, shots=shots, left=len(pirates), n=n))
            else:
                frames.append(self._frame("broadside", "miss" if shots else "noguns", "miss",
                                          foe=None if shots else "noguns", left=len(pirates), n=n))
        elif self._chance(pi["run_base"] + (pi["run_fast"] if b["fast"] else 0) + pi["run_round"] * rnd, "escape",
                          "{} round {}: outrun them{}".format(who, rnd, " (every ship is fast)" if b["fast"] else ""), p, round=rnd):
            log.append(tx("l.outran", rounds=rnd, s=s))
            b["round"] = rnd
            frames.append(self._frame("got_away", "got_away", "got_away", foe="got_away"))
            return self._battle_close(p, b, "away", frames)
        else:
            b["runs"] += 1
            frames.append(self._frame("sighting", "run_fail", "run_fail", left=len(pirates)))
        taken_round = self._enemy_fire(p, b, pirates)
        if pirates:
            self._ev("battle", "enemy_fire", "{} round {}: {} enemy fired, {} hit{}".format(
                who, rnd, len(pirates), len(taken_round), ": " + ", ".join(
                    self._hit_text(h) for h in taken_round) if taken_round else ""),
                p, round=rnd, enemy=len(pirates), hits=taken_round)
        names = [sh["name"] for sh in p["ships"]]
        self._check_sunk(p, tx("l.how_sunk"))
        b["round"] = rnd
        self._hit_frames(p, b, frames, taken_round, names)
        if not p["ships"]:
            frames.append(self._frame("defeat", "defeat", "defeat", foe="victory"))
            return self._battle_close(p, b, "wrecked", frames)
        if rnd >= pi["rounds"]:
            if b["runs"] == 0:
                log.append(tx("l.long_fight", n=n - len(pirates)))
                self._ev("battle", "broke_off", "{}: enemy broke off after {} rounds; {} of {} sunk".format(
                    who, pi["rounds"], n - len(pirates), n), p, sunk=n - len(pirates))
                frames.append(self._frame("got_away", "broke_off", "broke_off", foe="broke_off", sunk=n - len(pirates), n=n))
                return self._battle_close(p, b, "broke_off", frames)
            # Every round spent running and failing lets them close: the cargo they carry off is in
            # proportion (all of it when the fleet only ever ran, as before).
            share = b["runs"] / float(rnd)
            lost = {g: int(q * rng.uniform(pi["plunder_min"], pi["plunder_max"]) * share) for g, q in p["cargo"].items()}
            self._book(p, "plundered", -self._cost_of(p, lost))
            for g, q in lost.items():
                p["cargo"][g] -= q
            p["cargo"] = {g: q for g, q in p["cargo"].items() if q > 0}
            log.append(tx("l.plundered", qty=sum(lost.values())))
            self._ev("battle", "plundered", "{} could not get away in {} rounds and was plundered of {} units: {}".format(
                who, pi["rounds"], sum(lost.values()),
                ", ".join("{} {}".format(q, GOODS[g]["name"]) for g, q in lost.items() if q) or "nothing"),
                p, lost={g: q for g, q in lost.items() if q})
            frames.append(self._frame("boarding", "plundered", "plundered", foe="plunder", qty=sum(lost.values())))
            return self._battle_close(p, b, "plundered", frames)
        b["beat"] = {"id": b["step"] + 1, "frames": frames}

    PRIZE_TIERS = ("scraps", "modest", "rich", "haul")

    def _battle_prize(self, p, b, frames):
        """A won fight: the sunk junks' holds give up whatever they had stolen from someone else.
        A tier is drawn first (rules.battle.prize_tiers): mostly scraps (three bags of tea), now and
        then a hold full of everything. Its own dice, so every other roll of the month is unchanged."""
        bt = R["battle"]
        if not bt.get("prize", True):
            return
        table = bt.get("prize_tiers") or {}
        order = [k for k in self.PRIZE_TIERS if k in table] + sorted(k for k in table if k not in self.PRIZE_TIERS)
        tiers = [dict(table[k], key=k) for k in order if float(table[k].get("weight", 0)) > 0]
        if not tiers:
            return
        own = random.Random("{}:{}:{}:{}:{}:prize".format(self.s.get("game_id", ""), self.s["turn"], p["id"],
                                                          b["kind"], b["seed"] if b["seed"] is not None else b["n"]))
        roll, pick = own.random() * sum(float(t["weight"]) for t in tiers), 0
        for i, t in enumerate(tiers):
            roll -= float(t["weight"])
            if roll < 0:
                pick = i
                break
        if b["kind"] == "lord":                          # the queen's war junks carry the richer plunder
            pick = min(len(tiers) - 1, pick + int(bt.get("prize_lord_step", 1)))
        tier = tiers[pick]
        names = [g for g in GOODS]
        pool = {g: float(GOODS[g].get("depth", 100)) for g in names}      # plentiful goods turn up most
        kinds = min(len(pool), own.randint(int(tier.get("goods_min", 1)), int(tier.get("goods_max", 1))))
        chosen = []
        for _ in range(kinds):
            r = own.random() * sum(pool.values())
            for g in sorted(pool):
                r -= pool[g]
                if r < 0:
                    chosen.append(g)
                    del pool[g]
                    break
        haul = {}
        if tier.get("units_max"):                        # scraps: a few units of one or two cheap goods
            for g in chosen:
                haul[g] = own.randint(int(tier.get("units_min", 1)), int(tier["units_max"]))
        else:
            grow = 1 + self.s["turn"] / float(R["pirates"]["booty_growth"])
            value = b.get("worth_n", b["n"]) * own.uniform(float(tier["value_min"]), float(tier["value_max"])) * grow
            shares = [own.uniform(0.3, 1.0) for _ in chosen]
            for g, sh in zip(chosen, shares):
                haul[g] = max(1, int(round(value * sh / sum(shares) / GOODS[g]["base"])))
        free = max(0, self.capacity(p) - self.used(p))
        took, left = {}, 0
        for g in sorted(haul, key=lambda k: -GOODS[k]["base"]):   # the dearest goods are carried across first
            q = min(haul[g], free)
            if q > 0:
                took[g] = q
                free -= q
            left += haul[g] - q
        basis = p.setdefault("basis", {})
        for g, q in took.items():
            held = p["cargo"].get(g, 0) + stored(p, g)
            # Plunder costs the house nothing: it lowers the average paid for what is already aboard.
            basis[g] = (float(basis.get(g, 0.0)) * held) / float(held + q)
            p["cargo"][g] = p["cargo"].get(g, 0) + q
        worth = int(sum(q * GOODS[g]["base"] for g, q in took.items()))
        what = self._goods_text(took)
        mark = tx("battle.prize.mark.{}".format(own.randrange(self._count("battle.prize.mark."))))
        b["prize"] = {"tier": tier.get("key", str(pick)), "goods": took, "left": left, "worth": worth}
        if took:
            p["log"].append(tx("l.prize", goods=what, mark=mark))
        if left:
            p["log"].append(tx("l.prize_left", qty=left))
        self._ev("battle", "prize", "{} took {} from the {} {} ({} tier, about {} at usual prices){}".format(
            p["name"], what or "nothing", b["n"], b["label"], tier.get("key", pick), money(worth),
            "; no room for {} more units".format(left) if left else ""), p,
            tier=tier.get("key", pick), goods=took, left=left, worth=worth)
        key = tier.get("key", "scraps")
        if took:
            frames.append(self._frame("victory", "prize_" + key, "prize_" + key, goods=what, mark=mark))
        elif left:
            frames.append(self._frame("victory", "prize_full", "prize_full", qty=left))

    @staticmethod
    def _count(prefix):
        n = 0
        while "{}{}".format(prefix, n) in TEXT:
            n += 1
        return max(1, n)

    @staticmethod
    def _goods_text(goods):
        parts = ["{} {}".format(q, GOODS[g]["name"]) for g, q in sorted(goods.items(), key=lambda kv: -kv[1])]
        if len(parts) > 1:
            return tx("w.list_and", most=", ".join(parts[:-1]), last=parts[-1])
        return parts[0] if parts else ""

    def _enemy_fire(self, p, b, pirates):
        """Every junk afloat fires once. A hit lands in one of three places:
        - the guns (rules.battle.gun_loss): one gun dismounted, sometimes two; a cannon is as likely
          to be struck as the mounts she fills, and one goes at a time. A ship with no guns can't be.
        - the hold (rules.battle.cargo_hit, of the hits that miss the guns): one kind of goods aboard,
          every kind as likely as the next (so the gold is no safer than the rice), loses
          cargo_hit_min to cargo_hit_max of its units over the side, at least one.
        - the hull: everything else."""
        rng, bt = self.rng, R["battle"]
        if b.get("formation"):
            return self._enemy_fire_formed(p, b, pirates)
        out = []
        for _ in pirates:
            if not p["ships"] or rng.random() >= b["hit"]:
                continue
            target = rng.choice(p["ships"])
            armed = target["guns"] + cannon_slots() * target.get("cannons", 0)
            if armed > 0 and rng.random() < bt.get("gun_loss", 0.0):
                if target.get("cannons", 0) and rng.random() * armed >= target["guns"]:
                    target["cannons"] -= 1
                    self._book(p, "ships_lost", -cannon_price() * R["fleet"]["gun_resale"])
                    out.append({"name": target["name"], "damage": 0, "guns": 0, "cannons": 1, "hull": target["hull"],
                                "guns_left": target["guns"], "cannons_left": target["cannons"]})
                    continue
                k = min(target["guns"], 2 if rng.random() < bt.get("gun_loss_two", 0.0) else 1)
                target["guns"] -= k
                self._book(p, "ships_lost", -k * R["fleet"]["gun_price"] * R["fleet"]["gun_resale"])
                out.append({"name": target["name"], "damage": 0, "guns": k, "hull": target["hull"],
                            "guns_left": target["guns"]})
                continue
            aboard = sorted(g for g, q in p["cargo"].items() if q > 0)
            if aboard and rng.random() < bt.get("cargo_hit", 0.0):
                g = rng.choice(aboard)
                lo, hi = sorted((float(bt.get("cargo_hit_min", 0.1)), float(bt.get("cargo_hit_max", 0.3))))
                q = min(p["cargo"][g], max(1, int(round(p["cargo"][g] * rng.uniform(lo, hi)))))
                self._book(p, "overboard", -self._cost_of(p, {g: q}))
                p["cargo"][g] -= q
                if p["cargo"][g] <= 0:
                    del p["cargo"][g]
                shot = b.setdefault("shot", {})
                shot[g] = shot.get(g, 0) + q
                out.append({"name": target["name"], "damage": 0, "guns": 0, "hull": target["hull"], "cargo": {g: q}})
                continue
            points = rng.randint(*b["dmg"])
            target["hull"] -= points
            out.append({"name": target["name"], "damage": points, "guns": 0, "hull": target["hull"]})
        return out

    def _enemy_fire_formed(self, p, b, pirates):
        """The fleet in formation (escorts in the van, merchantmen in the line, cargo ships in the rear).
        Each enemy junk fires all her guns (rules: b["eg"]) at one ship (see _pick_target). A hit on
        - an escort: smashes guns (rules.battle.gun_loss) or holes the hull. She carries no cargo.
        - a merchantman: guns, the hold (rules.battle.cargo_hit) or the hull, as always.
        - a cargo ship: always the hull, and always cargo: the share of her hold that the damage is of
          her hull goes over the side (rules.battle.cargo_spill), from the goods aboard by weight."""
        rng, bt = self.rng, R["battle"]
        out = []
        guns_each = b.get("eg") or [1] * len(pirates)
        for i in range(len(pirates)):
            target = self._pick_target(b, p["ships"])
            if target is None:
                break
            role = role_of(target["type"])
            for _ in range(guns_each[i] if i < len(guns_each) else 1):
                if target["hull"] <= 0:
                    break                                   # she is going down; the rest of the broadside is wasted
                if rng.random() >= b["hit"]:
                    continue
                if role != "cargo":
                    armed = target["guns"] + cannon_slots() * target.get("cannons", 0)
                    if armed > 0 and rng.random() < bt.get("gun_loss", 0.0):
                        if target.get("cannons", 0) and rng.random() * armed >= target["guns"]:
                            target["cannons"] -= 1
                            self._book(p, "ships_lost", -cannon_price() * R["fleet"]["gun_resale"])
                            out.append({"name": target["name"], "damage": 0, "guns": 0, "cannons": 1, "hull": target["hull"],
                                        "guns_left": target["guns"], "cannons_left": target["cannons"], "role": role})
                            continue
                        k = min(target["guns"], 2 if rng.random() < bt.get("gun_loss_two", 0.0) else 1)
                        target["guns"] -= k
                        self._book(p, "ships_lost", -k * R["fleet"]["gun_price"] * R["fleet"]["gun_resale"])
                        out.append({"name": target["name"], "damage": 0, "guns": k, "hull": target["hull"],
                                    "guns_left": target["guns"], "role": role})
                        continue
                if role == "trader":
                    aboard = sorted(g for g, q in p["cargo"].items() if q > 0)
                    if aboard and rng.random() < bt.get("cargo_hit", 0.0):
                        # One kind of goods (gold as likely as rice), as much of it as the shot's share
                        # of her hull is of her hold (the cargo-ship rule), at least one unit.
                        g = rng.choice(aboard)
                        spec = SHIPS[target["type"]]
                        fill = self.used(p) / float(max(1, self.capacity(p)))
                        share = rng.randint(*b["dmg"]) / float(max(1, spec["hull"])) * spec["hold"] * fill \
                            * float(bt.get("cargo_spill", 1.0))
                        q = min(p["cargo"][g], max(1, int(round(share))))
                        self._spill(p, b, {g: q})
                        out.append({"name": target["name"], "damage": 0, "guns": 0, "hull": target["hull"],
                                    "cargo": {g: q}, "role": role})
                        continue
                points = rng.randint(*b["dmg"])
                target["hull"] -= points
                hit = {"name": target["name"], "damage": points, "guns": 0, "hull": target["hull"], "role": role}
                if role == "cargo" and self.used(p) > 0:
                    spec = SHIPS[target["type"]]
                    fill = self.used(p) / float(max(1, self.capacity(p)))
                    units = int(round(points / float(max(1, spec["hull"])) * spec["hold"] * fill
                                      * float(bt.get("cargo_spill", 1.0))))
                    lost = {}
                    for _k in range(min(max(1, units), self.used(p))):
                        pool = [(g, q - lost.get(g, 0)) for g, q in p["cargo"].items() if q - lost.get(g, 0) > 0]
                        if not pool:
                            break
                        g = rng.choices([x[0] for x in pool], weights=[x[1] for x in pool])[0] if len(pool) > 1 else pool[0][0]
                        lost[g] = lost.get(g, 0) + 1
                    if lost:
                        self._spill(p, b, lost)
                        hit["cargo"] = lost
                out.append(hit)
        return out

    def _spill(self, p, b, goods):
        """Cargo shot out of the fleet: booked at cost, counted for the reckoning."""
        self._book(p, "overboard", -self._cost_of(p, goods))
        shot = b.setdefault("shot", {})
        for g, q in goods.items():
            p["cargo"][g] -= q
            if p["cargo"][g] <= 0:
                del p["cargo"][g]
            shot[g] = shot.get(g, 0) + q

    @staticmethod
    def _hit_text(h):
        if h.get("cargo") and h.get("damage"):
            return "{} -{} (hull {}), {} lost with her hold".format(h["name"], h["damage"], h["hull"], ", ".join(
                "{} {}".format(q, GOODS[g]["name"] if g in GOODS else g) for g, q in h["cargo"].items()))
        if h.get("cargo"):
            return "{} hit in the hold: {} lost".format(h["name"], ", ".join(
                "{} {}".format(q, GOODS[g]["name"] if g in GOODS else g) for g, q in h["cargo"].items()))
        if h.get("cannons"):
            return "{} lost a cannon ({} left)".format(h["name"], h.get("cannons_left", 0))
        if h.get("guns"):
            return "{} lost {} gun{} ({} left)".format(h["name"], h["guns"], "" if h["guns"] == 1 else "s", h.get("guns_left", 0))
        return "{} -{} (hull {})".format(h["name"], h["damage"], h["hull"])

    def _hit_frames(self, p, b, frames, taken_round, names, say=True):
        """Pictures for the enemy's fire: the damage, then any ship that went down."""
        holed = [h for h in taken_round if h["damage"]]
        dismounted = sum(h.get("guns", 0) for h in taken_round)
        cannons = sum(h.get("cannons", 0) for h in taken_round)
        gloat = [bool(say)]     # the enemy crows once a round, on the first hit picture the bosun leaves silent

        def foe_if(pool):
            if pool is None and gloat[0]:
                gloat[0] = False
                return "hit_us"
            return None
        if holed:
            frames.append(self._frame("we_are_hit", "we_are_hit", "we_are_hit" if say else None,
                                      points=sum(h["damage"] for h in holed), n=len(holed)))
        if dismounted:
            left = self.guns(p)
            pool = "guns_lost" if say and not holed else None
            frames.append(self._frame("we_are_hit", "guns_lost" if left else "guns_gone", pool, foe=foe_if(pool),
                                      guns=dismounted, s="" if dismounted == 1 else "s", left=left))
        if cannons:
            left = self.firepower(p)
            pool = "guns_lost" if say and not holed and not dismounted else None
            frames.append(self._frame("we_are_hit", "cannon_lost" if left else "guns_gone", pool, foe=foe_if(pool),
                                      guns=cannons, n=cannons, s="" if cannons == 1 else "s",
                                      left=self.cannons(p)))
        spilled = {}
        for h in taken_round:
            for g, q in (h.get("cargo") or {}).items():
                spilled[g] = spilled.get(g, 0) + q
        if spilled:
            gold = "gold" in spilled
            spoke = holed or dismounted or cannons
            rear = any(h.get("role") == "cargo" and h.get("cargo") for h in taken_round)
            pool = ("cargo_gold" if gold else "cargo_hit") if say and (gold or not spoke) else None
            frames.append(self._frame("we_are_hit", "cargo_gold" if gold else "rear_hit" if rear else "cargo_hit",
                                      pool, foe=foe_if(pool),
                                      goods=self._goods_text(spilled), qty=sum(spilled.values())))
        afloat = {sh["name"] for sh in p["ships"]}
        for sh in b["ships0"]:
            if sh["name"] in names and sh["name"] not in afloat:
                r = sh.get("role") or role_of(sh["type"])
                frames.append(self._frame("ship_lost", "escort_lost" if r == "escort" else "cargo_sunk" if r == "cargo"
                                          else "ship_lost", "ship_lost", foe="sank_ours",
                                          ship=SHIPS[sh["type"]]["name"] if sh["type"] in SHIPS else sh["type"], name=sh["name"]))

    def _battle_close(self, p, b, outcome, frames):
        """The fight is over: the damage line for the log, and the reckoning for the screen."""
        bt = R["battle"]
        gain = float(bt.get("fame_win", 1.0)) if outcome == "won" else float(bt.get("fame_broke_off", 0.5)) \
            if outcome == "broke_off" else 0.0
        if gain:
            p["fame"] = round(float(p.get("fame", 0) or 0) + gain, 3)
        taken = b["hull0"] - sum(sh["hull"] for sh in p["ships"])
        if taken > 0 and p["ships"]:
            p["log"].append(tx("l.damage", points=taken))
        now = {sh["name"]: sh for sh in p["ships"]}
        guns_lost = sum(max(0, sh.get("guns", 0) - now[sh["name"]]["guns"]) for sh in b["ships0"] if sh["name"] in now)
        if guns_lost > 0:
            p["log"].append(tx("l.guns_lost", guns=guns_lost, s="" if guns_lost == 1 else "s"))
        cannons_lost = sum(max(0, sh.get("cannons", 0) - now[sh["name"]].get("cannons", 0))
                           for sh in b["ships0"] if sh["name"] in now)
        if cannons_lost > 0:
            p["log"].append(tx("l.cannons_lost", n=cannons_lost, s="" if cannons_lost == 1 else "s"))
        if b.get("shot") and p["ships"]:
            p["log"].append(tx("l.cargo_shot", goods=self._goods_text(b["shot"]), qty=sum(b["shot"].values())))
        if b["seed"] is not None:
            ships = [{"name": sh["name"], "type": sh["type"], "hull0": sh["hull"],
                      "guns0": sh.get("guns", 0), "guns1": now[sh["name"]]["guns"] if sh["name"] in now else 0,
                      "cannons0": sh.get("cannons", 0),
                      "cannons1": now[sh["name"]].get("cannons", 0) if sh["name"] in now else 0,
                      "hull1": now[sh["name"]]["hull"] if sh["name"] in now else 0,
                      "max": SHIPS[sh["type"]]["hull"] if sh["type"] in SHIPS else sh["hull"],
                      "role": sh.get("role") or role_of(sh["type"]),
                      "lost": sh["name"] not in now} for sh in b["ships0"]]
            # What left the hold: start against now, leaving out any prize cargo carried aboard after.
            won = (b.get("prize") or {}).get("goods", {})
            lost = {g: q - (p["cargo"].get(g, 0) - won.get(g, 0)) for g, q in b["cargo0"].items()
                    if q - (p["cargo"].get(g, 0) - won.get(g, 0)) > 0}
            cargo = [{"good": g, "qty": q, "cost": int(round(self._cost_of(p, {g: q})))} for g, q in lost.items()]
            dest = b.get("dest")
            if outcome != "wrecked" and self.s.get("sea"):       # a shipwreck makes its own headline
                self.s["sea"]["news"].append(tx("n.fight_" + outcome, name=p["name"], firm=p["firm"], n=b["n"], enemy=b["label"],
                                                port=PORTS[dest]["name"] if dest in PORTS else ""))
            p.setdefault("fights", []).append({
                "id": "{}:{}-{}".format(self.s.get("game_id", ""), self.s["turn"], len(p.get("fights") or [])), "outcome": outcome, "kind": b["kind"],
                "enemy": b["label"], "n": b["n"], "sunk": b["n"] - len(b["hp"]),
                "rounds": b["round"], "ships": ships, "cargo": cargo, "booty": b["booty"], "paid": b["paid"],
                "prize": [{"good": g, "qty": q, "worth": int(q * GOODS[g]["base"])}
                          for g, q in sorted((b.get("prize") or {}).get("goods", {}).items(), key=lambda kv: -kv[1])],
                "prize_tier": (b.get("prize") or {}).get("tier"), "prize_left": (b.get("prize") or {}).get("left", 0),
                "prize_worth": (b.get("prize") or {}).get("worth", 0),
                "net": int(round(b.get("net", 0.0))), "where": PORTS[dest]["name"] if dest in PORTS else "",
                "match": b.get("match"), "enemy_hull": b.get("enemy_hull"), "enemy_guns": b.get("enemy_guns"),
                "beat": {"id": b["step"] + 1, "frames": frames}})
        p.pop("battle", None)

    def _act_sea(self, p, a):
        """A captain's choice in a fight: pay, fight, run, retreat; auto (this round on standing
        orders: the round timer ran out) or skip (the rest of the fight on standing orders)."""
        b = p.get("battle")
        if b is None:
            raise GameError(tx("e.no_battle"))
        choice = str(a.get("choice"))
        if choice not in self.SEA_CHOICES:
            raise GameError(tx("e.unknown_action"))
        if choice == "pay":
            if b["stage"] != "parley":
                raise GameError(tx("e.no_parley"))
            if p["cash"] < b["price"]:
                raise GameError(tx("e.parley_cost", cost=money(b["price"]), cash=money(p["cash"])))
        if choice == "fight" and self.firepower(p) == 0:
            raise GameError(tx("e.no_guns"))
        rnd, left = b["round"] + 1, len(b["hp"])
        if choice == "skip":
            b["auto"] = True
        else:
            self._battle_step(p, choice)
        self._voyage_step(p)                 # sails on: to port, to the next fight, or (skip) through this one
        fights = p.get("fights") or []
        note = "round {}, {} of {} {} afloat: {}".format(rnd, left, b["n"], b["label"], choice)
        if p.get("battle") is not b and fights:
            note += "; " + fights[-1]["outcome"]
        self._detail = {"choice": choice, "round": rnd, "note": note}
        self._sea_check()
        return tx("battle.ack." + ("skip" if choice == "skip" else "auto" if choice == "auto" else choice))

    def fight_out(self, present=(), pick=None):
        """Play every open fight to its end, as a captain at a screen would (for bots and tests).
        pick(view) names each choice; without it the choices are drawn from the fight's own seed."""
        steps = 0
        while self.s["phase"] == "sea":
            for pid in list(self.s["order"]):
                p = self.s["players"].get(pid)
                if p is None or p.get("battle") is None:
                    continue
                b, v = p["battle"], self.battle_view(p)
                if pick is not None:
                    choice = pick(v)
                else:
                    own = random.Random("{}:bot:{}".format(b["seed"], b["step"]))
                    choice = own.choice(["run", "retreat"] + (["fight"] * 4 if v["can_fight"] else [])
                                        + (["pay"] if v["can_pay"] else []))
                self.act(pid, {"type": "sea", "choice": choice}, present)
                steps += 1
        return steps

    def battle_view(self, p):
        """What the battle screen shows a captain in a fight (None when there is none)."""
        b = p.get("battle")
        if b is None or b.get("seed") is None:
            return None
        pi = R["pirates"]
        view = MULT.get("battle_view") or MULT.get("customs_view", "bar")
        left, guns = len(b["hp"]), self.firepower(p)
        hull = sum(max(0, sh["hull"]) for sh in p["ships"])
        rnd = b["round"] + 1
        run = max(0.0, min(1.0, pi["run_base"] + (pi["run_fast"] if b["fast"] else 0) + pi["run_round"] * rnd))
        avg = (b["dmg"][0] + b["dmg"][1]) / 2.0
        eg = (b.get("eg") or [1] * left)[:left]
        per_round = sum(eg) * b["hit"] * avg                    # hull the enemy takes off the fleet each round
        to_sink = (sum(b["hp"]) / (guns * pi["gun_hit"])) if guns and pi["gun_hit"] > 0 else 99.0
        rounds_left = max(1, pi["rounds"] - b["round"])
        danger = per_round * min(to_sink, rounds_left) / max(1.0, hull)

        def mood(x, calm, worried):
            return "calm" if x < calm else "worried" if x < worried else "grim"
        moods = {"fight": mood(danger, 0.25, 0.6) if guns else "grim",
                 "run": mood(1 - run, 0.4, 0.6),
                 "retreat": mood(per_round / max(1.0, hull), 0.15, 0.4)}
        overall = moods["fight"] if guns else moods["run"]      # her manner speaks to standing and fighting, or to getting away
        tells = 0
        while "battle.tell.{}.{}".format(overall, tells) in TEXT:
            tells += 1
        gone = self._retreat_dump(p, b)
        dest = b.get("dest")
        out = {"kind": b["kind"], "enemy": b["label"], "n": b["n"], "left": left, "round": rnd, "rounds": pi["rounds"],
               "stage": b["stage"], "orders": b["orders"], "guns": guns, "can_fight": guns > 0, "step": b["step"],
               "gun_count": self.guns(p), "cannons": self.cannons(p),
               "where": PORTS[dest]["name"] if dest in PORTS else "", "view": view, "moods": moods, "mood": overall,
               "tell": tx("battle.tell.{}.{}".format(overall, (b["seed"] + b["step"]) % tells)) if tells else "",
               "price": b["price"] if b["stage"] == "parley" else 0,
               "can_pay": b["stage"] == "parley" and p["cash"] >= b["price"],
               "bargain": ({"share": round(b["price"] / float(max(1, b["lowball"]["value"])), 4),
                            "full": b["lowball"]["full"]}
                           if b.get("lowball") and not b["lowball"].get("seen") and b["stage"] == "parley" else None),
               "repriced": bool(b.get("lowball") and b["lowball"].get("seen") and b["stage"] == "parley"),
               "dump": gone, "dump_qty": sum(gone.values()), "beat": b["beat"], "hull": hull,
               "auto": bool(b.get("auto")),
               "enemy_ships": [{"hp": max(0, h), "max": (b.get("hpmax") or [])[i] if i < len(b.get("hpmax") or []) else h,
                                "guns": eg[i] if i < len(eg) else 1} for i, h in enumerate(b["hp"])],
               "enemy_guns": sum(eg), "matched": bool(b.get("match"))}
        if out["bargain"]:
            k = 0
            while "battle.tell.bargain.{}".format(k) in TEXT:
                k += 1
            if k:
                out["tell"] = tx("battle.tell.bargain.{}".format((b["seed"] + b["step"]) % k))
                out["mood"] = "bargain"
        if view in ("exact", "bar"):
            out["odds"] = {"run": round(run, 3), "hit": round(b["hit"], 3), "gun_hit": round(pi["gun_hit"], 3),
                           "retreat": [0, int(round(min(per_round, hull))), int(min(per_round * 1.6 if b.get("match") else left * b["dmg"][1], hull))],
                           "enemy_round": int(round(per_round)), "danger": round(min(1.0, danger), 3)}
        return out

    def sea_view(self):
        """Who is in a fight right now, for the harbor board and the houses that are waiting."""
        out = []
        for p in (self.s["players"][i] for i in self.s["order"]):
            b = p.get("battle")
            if b is None:
                continue
            dest = b.get("dest")
            out.append({"id": p["id"], "name": p["name"], "firm": p["firm"], "color": p["color"], "kind": b["kind"],
                        "enemy": b["label"], "n": b["n"], "left": len(b["hp"]), "round": b["round"] + 1,
                        "rounds": R["pirates"]["rounds"], "stage": b["stage"],
                        "where": PORTS[dest]["name"] if dest in PORTS else ""})
        return out

    def _check_sunk(self, p, how):
        for sh in [sh for sh in p["ships"] if sh["hull"] <= 0]:
            # What she would have fetched in good repair, less the wreck's own value (which is nothing).
            self._book(p, "ships_lost", -SHIPS[sh["type"]]["price"] * R["fleet"]["ship_resale"]
                       - (sh["guns"] * R["fleet"]["gun_price"] + sh.get("cannons", 0) * cannon_price())
                       * R["fleet"]["gun_resale"])
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
                self._book(p, "overboard", -self._cost_of(p, {g: drop}))
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
                 "back in {} with a {}".format(p["name"], self.used(p), money(lost), money(wk["debt"]), PORTS[home_of(p)]["name"],
                                               SHIPS[wk["ship"]]["name"].lower()), p, lost=lost, debt=wk["debt"],
                 cargo=dict(p["cargo"]))
        self._book(p, "wreck_cargo", -self._cost_of(p, p["cargo"]))
        self._book(p, "wreck", -(lost + wk["debt"]))
        p["cargo"] = {}
        p["cash"] -= lost
        p["debt"] += wk["debt"]
        p["port"] = home_of(p)
        p["tab"] = self._new_tab()
        p["net"] = {}
        self._mayor_greeting(p)
        p["wrecks"] += 1
        kind = SHIPS[wk["ship"]]
        p["ships"] = [self._new_ship(wk["ship"], guns=max(0, min(int(wk.get("guns", 2)), kind["slots"])),
                                     hull=min(wk["hull"], kind["hull"]))]
        p["log"].append(tx("l.wrecked", home=PORTS[home_of(p)]["name"], lost=money(lost), debt=money(wk["debt"]),
                           ship=SHIPS[wk["ship"]]["name"].lower()))
        news.append(tx("n.wrecked", name=p["name"], firm=p["firm"], home=PORTS[home_of(p)]["name"]))

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
                              "worth": worth, "rank": self.commissioned_rank(q)["title"], "ships": len(q["ships"]),
                              "host": q["id"] == host})
        out = {
            "phase": s["phase"], "turn": s["turn"], "date": date_label(s["turn"]),
            "years": s["years"], "turns_left": max(0, s["years"] * 12 - s["turn"]),
            "free_play": bool(s.get("free_play")),
            "players": standings, "news": s["news"][:14],
            "news_heat": [self.news_heat(n) for n in s["news"][:14]],
            "weather": s["weather"], "crackdown": sorted(s["crackdown"]),
            "bans": {k: self.banned(k) for k in sorted(s["crackdown"])},
            "waiting": [q["name"] for q in standings if q["present"] and not q["ready"]],
            "sea": self.sea_view() if s["phase"] == "sea" else [],
            "me": None,
        }
        p = s["players"].get(pid)
        if p:
            port = p["port"]
            sp = self.spread(p, port)
            worth = int(self.worth(p))
            out["me"] = {
                "id": p["id"], "name": p["name"], "firm": p["firm"], "color": p["color"],
                "captain": p.get("captain") or "", "hid": p.get("hid") or "",
                "host": p["id"] == host, "port": port, "home": home_of(p),
                "home_free": self.home_free(p, home_of(p)),
                "cash": int(p["cash"]), "bank": int(p["bank"]), "debt": int(math.ceil(p["debt"])),
                "worth": worth, **self._rank_view(p, worth),
                "cargo": p["cargo"], **self._store_view(p),
                "capacity": self.capacity(p), "used": self.used(p),
                "ships": [{"type": sh["type"], "name": sh["name"], "hull": sh["hull"], "guns": sh["guns"],
                           "cannons": sh.get("cannons", 0), "free": self.mounts_free(sh), "role": role_of(sh["type"]),
                           "value": int(self.ship_value(sh)),
                           "repair": int(math.ceil((SHIPS[sh["type"]]["hull"] - sh["hull"])
                                                   * self.repair_rate(p, sh)))}
                          for sh in p["ships"]],
                "classes": self.fleet_classes(p), "fame": round(float(p.get("fame", 0) or 0), 2),
                "trade_down": self.trade_down_offer(p),
                "rep": {k: int(round(v)) for k, v in p["rep"].items()},
                "protect": p["protect"], "protect_cost": self.protection_cost(p),
                "loan_room": max(0, int(self.loan_limit(p) - p["debt"])),
                "collectors": self.collectors(p),
                "ready": p["ready"], "dest": p["dest"], "orders": p["orders"],
                "log": p["log"], "known": p["known"],
                "tips": p.get("tips") or {},                 # the Registrar's prices: {port: {good: {turn, price}}}
                # The Registrar's hot tips still to come or still running (shown under Port > Arrival and the Price Book).
                "hot_tips": [t for t in (p.get("hot_tips") or []) if int(t.get("ends", -1)) >= s["turn"]],
                "prices": {g: round(v, 2) for g, v in s["prices"][port].items()},
                "basis": {g: round(v, 2) for g, v in (p.get("basis") or {}).items()},   # average paid per unit
                "spread": round(sp, 4),
                "dues": self.dues(p), "slip": bool(p.get("slip")),
                "customs": self.customs_view(p), "bond": self.sealed(p),
                "battle": self.battle_view(p), "fights": p.get("fights") or [],
                "books": self.books_view(p),
                "gift": self.gift_view(p),
                "market": self.market_view(p),
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
                            "debt": int(math.ceil(p["debt"])), "worth": worth, "rank": self.commissioned_rank(p)["title"],
                            "protect": p["protect"], "wrecks": p["wrecks"],
                            "cargo": p["cargo"], "wh": p["wh"], "hold": self.capacity(p), "used": self.used(p),
                            "ships": [{"type": sh["type"], "name": sh["name"], "hull": sh["hull"],
                                       "guns": sh["guns"], "cannons": sh.get("cannons", 0)} for sh in p["ships"]],
                            "log": p["log"]})
        return {"phase": s["phase"], "turn": s["turn"], "date": date_label(s["turn"]), "years": s["years"],
                "turns_left": max(0, s["years"] * 12 - s["turn"]), "players": players,
                "prices": {port: {g: round(v, 1) for g, v in row.items()} for port, row in s["prices"].items()},
                "weather": s["weather"], "crackdown": s["crackdown"], "ban_goods": s.get("ban_goods", {}),
                "bans": {k: self.banned(k) for k in s["crackdown"]}, "shocks": s["shocks"],
                "windfalls": s.get("windfalls", []), "news": s["news"],
                "news_heat": [self.news_heat(n) for n in s["news"]]}


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
            "market": {"reversion": R["market"]["reversion"], "spread_base": R["market"]["spread_base"],
                       "spread_swing": R["market"]["spread_swing"]},
            "gun_price": f["gun_price"], "max_fleet": f["max_fleet"],
            "fleet_rules": {r: {"max": role_limit(r), "unlock": role_unlock(r)} for r in ROLES},
            "keep_trader": bool(f.get("keep_trader", True)),
            "gun_resale": f["gun_resale"], "cannon_price": cannon_price(), "cannon_power": cannon_power(),
            "cannon_slots": cannon_slots(),
            "loan_rate": loan_rate(), "bank_rate": R["bank"]["bank_rate"], "home": HOME,
            "impact": R["market"]["impact"], "lengths": R["game"]["lengths"],
            "start_year": R["game"]["start_year"], "renew_at": R["liyuen"]["renew_at"],
            "ban_price_mult": R["events"]["ban_price_mult"],
            "dues_rules": {k: R["dues"][k] for k in ("slip_caught", "slip_mult", "slip_rep")},
            "forecast_accuracy": R["weather"]["forecast_accuracy"],
            "brand": b, "graphics": CFG["graphics"], "colors": CFG["theme"]["player_colors"],
            "ranks": CFG["ranks"], "promotion_styles": _config.promotion_styles(),
            "rating": CFG["content"]["rating"],
            "difficulty": MULT.get("name", ""), "yards": [p["name"] for p in PORTS.values() if p["shipyard"]],
            "tokens": TOKENS, "text": TEXT, "lang": CFG["language"]["active"]}


configure()
