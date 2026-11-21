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

import counter
import jail
import rot
import legend
import storm
import trade_text

# Filled in by configure(). Kept as module tables so tests and tools can read them.
GOODS, PORTS, SHIPS, REGIONS = {}, {}, {}, {}
R = {}        # rules, grouped: R["market"]["impact"] and so on
MULT = {}     # the current difficulty level's multipliers
TEXT = {}     # wording, key -> template
TOKENS = {}   # names available in every template
CFG = {}
HOME = "hongkong"


MONEY_CAP = 10 ** 15                    # bank and lender amounts (cargo keeps its 10 million cap)


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


def depot_refund(level):
    """What a port pays to take an away warehouse back: half of what opening and enlarging it costs."""
    f = R["fleet"]
    return (int(f.get("depot_open_cost", 10000)) + int(level) * int(f.get("depot_expand_cost", 100000))) // 2


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
    # Late-game rules (19 Nov 2026), whole from the defaults when the settings predate them.
    _defaults_rules = _config.DEFAULTS["rules"]
    for _group in ("estates", "contracts"):
        R[_group] = dict(_defaults_rules[_group], **(cfg["rules"].get(_group) or {}))
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


def rank_thresholds(years=None):
    """The net worth each rank needs, in rank order. Ranks marked "scales" (the ones above Taipan,
    19 Nov 2026) are set for a game of rules.game.rank_years years and scale with the game's length:
    a 5-year game halves them. A scaled rank never falls to or below the rank beneath it."""
    base = max(1, int(R["game"].get("rank_years", 10) or 10))
    out, floor = [], None
    for rank in CFG["ranks"]:
        w = rank["worth"]
        if rank.get("scales") and years:
            w = int(round(w * float(years) / base))
            if floor is not None and w <= floor:
                w = floor + 1
        out.append(w)
        floor = w
    return out


def rank_worth(rank, years=None):
    """One rank's worth needed in a game of this many years (see rank_thresholds)."""
    ranks = CFG["ranks"]
    return rank_thresholds(years)[ranks.index(rank)] if rank in ranks else rank.get("worth", 0)


def rank_index(worth, years=None):
    th = rank_thresholds(years)
    return next((i for i in range(len(th) - 1, -1, -1) if worth >= th[i]), 0)


def rank_for(worth, years=None):
    return CFG["ranks"][rank_index(worth, years)]["title"] if CFG["ranks"] else ""


def loan_rate():
    return R["bank"]["loan_rate"] * MULT["interest"]


def pct(x):
    return "{:g}%".format(round(x * 100, 2))


# Cannons (rules.fleet): bought for cannon_cost guns' price, fire like cannon_power guns, take cannon_slots mounts.
def cannon_price():
    f = R["fleet"]
    return int(round(f["gun_price"] * f.get("cannon_cost", 7.5)))


def normal_price(good):
    """A cargo's normal price: its base times each port's own factor, averaged over every port. No
    booms, crashes, shocks or price moves from anyone's trades. Net worth counts cargo at this."""
    spec = GOODS.get(good)
    if not spec or not PORTS:
        return 0.0
    return sum(spec["base"] * PORTS[k]["mods"].get(good, 1.0) for k in PORTS) / float(len(PORTS))


# Wild cargoes (Game 4 review, 20 Nov 2026): Maijiuana (porcelain) runs in trends and swings far wider than
# the rest (rules.market.wild_*). These give each cargo's own swing, pull back, floor and ceiling.
def is_wild(good):
    return good in (R["market"].get("wild_goods") or ())


def price_limits(good):
    """Lowest and highest a cargo's everyday price may go, as multiples of its usual price there."""
    m = R["market"]
    if is_wild(good):
        return float(m.get("wild_floor", m["floor"])), float(m.get("wild_ceiling", m["ceiling"]))
    return float(m["floor"]), float(m["ceiling"])


def reversion_of(good):
    m = R["market"]
    return float(m.get("wild_reversion", m["reversion"])) if is_wild(good) else float(m["reversion"])


def vol_of(good):
    m, spec = R["market"], GOODS[good]
    return max(float(spec["vol"]), float(m.get("wild_vol", 0.0))) if is_wild(good) else float(spec["vol"])


def ship_value(sh):
    """What a ship would fetch sold: hull share of half her price, plus a third of her guns and cannons."""
    spec, f = SHIPS.get(sh.get("type")), R["fleet"]
    if not spec:
        return 0.0
    return (f["ship_resale"] * spec["price"] * max(sh.get("hull", 0), 0) / spec["hull"]
            + (sh.get("guns", 0) * f["gun_price"] + sh.get("cannons", 0) * cannon_price()) * f["gun_resale"])


def cargo_normal_value(f):
    """Every unit the house owns (hold, home warehouse, depots) at its normal price."""
    total = 0.0
    for src in [f.get("cargo") or {}, f.get("wh") or {}] + [(d or {}).get("goods") or {}
                                                           for d in (f.get("depots") or {}).values()]:
        total += sum(q * normal_price(g) for g, q in src.items() if g in GOODS)
    return total


def holdings_value(f):
    """Port shares and the great house, at what was paid for them (late game, 19 Nov 2026). A journal
    snapshot carries the sum as "holdings"; a live house has the paid amounts themselves."""
    if "holdings" in f:
        return float(f.get("holdings") or 0)
    paid = f.get("share_paid") if isinstance(f.get("share_paid"), dict) else {}
    return float(sum(float(v) for v in paid.values())) + float(f.get("estate_paid", 0) or 0)


def worth_of(f):
    """Net worth of a house, from the live player or a journal snapshot of it (same keys). A snapshot
    taken under the dealer rule (Game 4 review, 20 Nov 2026: cargo at what the dealers would pay) carries
    its own figure, which needs that month's dealers and is kept as recorded. Older snapshots and live
    houses without a game count cargo at its normal price, as before."""
    if f.get("worth_rule") == "dealer" and f.get("worth") is not None:
        return float(f["worth"])
    return (float(f.get("cash", 0)) + float(f.get("bank", 0)) - float(f.get("debt", 0))
            + R["market"]["worth_cargo"] * cargo_normal_value(f)
            + sum(ship_value(sh) for sh in f.get("ships") or ())
            + sum(ship_value(sh) for sh in f.get("laid_up") or ())
            + holdings_value(f))


def cannon_power():
    return max(1, int(R["fleet"].get("cannon_power", 2)))


def cannon_slots():
    return max(1, int(R["fleet"].get("cannon_slots", 2)))


# Weapons take cargo space (19 Nov 2026): each gun takes rules.fleet.gun_hold units of her hold and each
# cannon rules.fleet.cannon_hold, so a ship armed to the teeth carries less. A hold never goes below 0
# (an escort has none to lose).
def gun_hold():
    return max(0, int(R["fleet"].get("gun_hold", 5)))


def cannon_hold():
    return max(0, int(R["fleet"].get("cannon_hold", 10)))


def ship_hold(sh, guns=0, cannons=0):
    """Cargo a ship can carry with her guns and cannons mounted (plus guns/cannons more, if given)."""
    spec = SHIPS.get(sh.get("type"))
    if not spec:
        return 0
    return max(0, int(spec["hold"]) - gun_hold() * (int(sh.get("guns", 0)) + guns)
               - cannon_hold() * (int(sh.get("cannons", 0)) + cannons))


# The three classes of ship (Admin > Ships > Class). Merchantmen carry cargo and guns and make up the
# first line of a fleet (rules.fleet.max_fleet of them); escorts carry guns only and sail in the van;
# cargo ships carry cargo only and sail in the rear. Each class has its own limit.
ROLES = ("escort", "trader", "cargo")


# The flagship (late game, 19 Nov 2026) is a class of her own: one per house, outside the limits of the
# three classes above. In a fight she keeps to the line and always goes down last (_flag_floor).
FLAG = "flagship"


def role_of(kind):
    spec = SHIPS.get(kind) or {}
    r = spec.get("role", "trader")
    return r if r in ROLES or r == FLAG else "trader"


def role_limit(role):
    f = R["fleet"]
    if role == FLAG:
        return 1
    return int(f["max_fleet"] if role == "trader" else f.get("max_escorts" if role == "escort" else "max_cargo", 5))


def role_unlock(role):
    """Merchantmen a house must have before a shipyard sells it this class (0 for merchantmen)."""
    if role == "trader":
        return 0
    if role == FLAG:
        return int(R["fleet"].get("flagship_unlock", 0))
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
    "match_lord": 0.15, "match_escort_share": 0.5, "match_cargo_ref": 100000, "match_ships_min": 2, "match_ships_max": 24,
    "match_lord_ships_max": 30, "match_size_swing": 0.3, "wu_fee": 0.10, "match_hp_min": 4, "match_hp_max": 12, "match_flag": 2.0,
    "allure_base": 0.6, "allure_cargo": 0.6, "allure_fame": 0.3, "match_booty": 0.8,
    "fame_win": 1.0, "fame_broke_off": 0.5, "fame_decay": 0.1, "fame_ref": 10,
    "focus": 0.3, "van_weight": 4, "line_weight": 3, "rear_weight": 3, "rear_cover": 0.85, "cargo_spill": 1.0,
    "lowball": True, "lowball_chance": 0.15, "lowball_dense": 1.0, "lowball_fame": 0.7,
    "lowball_min": 0.1, "lowball_max": 0.3, "lowball_goods": ["gold", "opium"]})

# Which heading of the captain's report each player action belongs under.
ACTION_CAT = {"counter": "trade", "plea": "finance", "buy": "trade", "sell": "trade", "buy_lot": "trade", "warehouse": "trade", "depot": "trade",
              "shares": "finance", "estate": "finance", "contract": "orders",
              "bank": "finance", "loan": "finance", "protection": "finance",
              "buy_ship": "fleet", "sell_ship": "fleet", "lay_up": "fleet", "recall": "fleet", "trade_down": "fleet", "buy_gun": "fleet", "repair": "fleet",
              "sell_gun": "fleet", "buy_cannon": "fleet", "fill_cannons": "fleet", "sell_cannon": "fleet",
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
                                "expand": int(f.get("depot_expand_cost", 100000)), "add": int(f.get("depot_expand_cap", 1000)),
                                "sell": depot_refund(store["depot"].get("level", 0)) if store and not store["home"] else 0}}

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
                        "holdings": int(holdings_value(p)),
                        "ships": [{"type": sh["type"], "name": sh["name"], "hull": sh["hull"], "guns": sh["guns"],
                                   "cannons": sh.get("cannons", 0)} for sh in p["ships"]],
                        "laid_up": [{"type": sh["type"], "name": sh["name"], "hull": sh["hull"], "guns": sh["guns"],
                                     "cannons": sh.get("cannons", 0)} for sh in p.get("laid_up") or ()],
                        "worth_rule": "dealer", "goods_value": int(self.goods_value(p)),
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
        return GOODS[good]["base"] * PORTS[port]["mods"].get(good, 1.0) * self._lift(port, good)

    def _lift(self, port, good):
        """How far this month's shortages, gluts, crash or boom and ban push a cargo's usual price here.
        Game 3 review (19 Nov 2026): when several meet on one cargo in one port only the strongest counts
        (rules.events.stack_booms False), so a shortage, a boom and a hot-tip boom can't multiply into a
        34x price. With stack_booms True they multiply, as before."""
        effects = [float(sh["mult"]) for sh in self.s["shocks"] if sh["port"] == port and sh["good"] == good]
        w = self._windfall(port, good)
        if w:
            effects.append(float(w["mult"]))
        if port in self.s["crackdown"] and good in self.banned(port):
            effects.append(float(R["events"]["ban_price_mult"]))
        if not effects:
            return 1.0
        if R["events"].get("stack_booms", False):
            out = 1.0
            for m in effects:
                out *= m
            return out
        return max(effects, key=lambda m: abs(math.log(max(1e-9, m))))

    def _price_band(self, port, good):
        """Lowest and highest a cargo's price may sit here this month: the usual floor and ceiling, widened
        to the size of a crash or boom running now (never past its own size) unless booms stack."""
        m = R["market"]
        base = GOODS[good]["base"] * PORTS[port]["mods"].get(good, 1.0)
        lift = self._lift(port, good)
        floor, ceiling = price_limits(good)
        return base * min(floor, lift), base * max(ceiling, lift)

    def _clamp(self, port, good, price):
        lo, hi = self._price_band(port, good)
        return max(1.0, lo, min(hi, price))

    def _windfall(self, port, good):
        """The crash or boom running on this cargo in this port, or None."""
        for w in self.s.get("windfalls", ()):
            if w["port"] == port and w["good"] == good:
                return w
        return None

    @staticmethod
    def _windfall_price(kind, before, target):
        """Where a new boom or crash sets the price (19 Nov 2026): a boom never below the price already
        there, a crash never above it, so a boom landing on a price that is already high can't pull it down."""
        if kind == "boom":
            return max(1.0, before, target)
        return max(1.0, min(before, target))

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
            s["prices"][port][good] = self._windfall_price(kind, before, self._target(port, good))
            if not ev.get("stack_booms", False):
                s["prices"][port][good] = self._clamp(port, good, s["prices"][port][good])
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
        self._sync_ship_names()                   # clean or NSFW names, as the content rating calls for
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
            tg = tab.get("goods") if isinstance(tab.get("goods"), dict) else {}
            p["tab"] = {k: float(tab.get(k, 0) or 0) for k in self._new_tab() if k != "goods"}
            p["tab"]["goods"] = {g: [float(v[0]), float(v[1])] for g, v in tg.items()
                                 if g in GOODS and isinstance(v, (list, tuple)) and len(v) == 2}
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
                p["rank_id"] = CFG["ranks"][rank_index(int(self.worth(p)), self.s.get("years"))]["id"]
        for p in s["players"].values():
            self._fit_shares(p)

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
        p["rank_id"] = CFG["ranks"][rank_index(int(self.worth(p)), self.s.get("years"))]["id"]
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

    def _new_ship(self, kind, guns=0, hull=None, name=None):
        # Each class has its own name list (Ships > Ship names); merchantmen use ship_names.
        if name:                                       # a flagship named by her house
            return {"type": kind, "name": name, "guns": guns, "cannons": 0,
                    "hull": SHIPS[kind]["hull"] if hull is None else min(hull, SHIPS[kind]["hull"])}
        role = SHIPS[kind].get("role", "trader")
        used = self._ship_names_used()
        clean = self._pick_ship_name(role, used, nsfw=False, rng=self.rng)
        ship = {"type": kind, "name": clean,
                "hull": SHIPS[kind]["hull"] if hull is None else min(hull, SHIPS[kind]["hull"]), "guns": guns,
                "cannons": 0}
        self._give_nsfw_name(ship, role, used | {clean})
        return ship

    def _ship_names_used(self):
        """Every name at sea, clean and NSFW alike (names are how a fight tells the ships apart)."""
        used = set()
        for p in self.s["players"].values():
            for sh in p["ships"]:
                used.update(n for n in (sh.get("name"), sh.get("clean_name"), sh.get("nsfw_name")) if n)
        return used

    @staticmethod
    def _pick_ship_name(role, used, nsfw, rng):
        """A free name for a ship of this class from the clean (or NSFW) lists, or None for an NSFW
        name when the NSFW lists are empty or all at sea (the ship then keeps her clean name)."""
        pre = "nsfw_" if nsfw else ""
        main = CFG.get(pre + "ship_names") or []
        own = CFG.get(pre + {"escort": "escort_names", "cargo": "cargo_names"}.get(role, "ship_names")) or []
        names = own or main
        free = [n for n in names if n not in used]
        if not free and own and own is not main:
            # The class's own list is all at sea: borrow a free Merchantman name before numbering.
            free = [n for n in main if n not in used]
        if not free and nsfw:
            return None
        if not free:
            # Every name is at sea: a second ship of a name is "II", then "III" (names are how a fight
            # tells the ships apart, so no two may share one).
            free = next((f for f in ([n + " " + r for n in names if n + " " + r not in used]
                                     for r in ("II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")) if f), None) \
                if names else None
            free = free or ["Ship {}".format(len(used) + 1)]
        return rng.choice(free)

    def _give_nsfw_name(self, ship, role, used):
        """Pair a ship with an NSFW name (her clean name is kept for Family-friendly), and show the
        one the content rating calls for. Picked with its own dice so the game's luck is untouched."""
        if role == "flagship" or ship.get("nsfw_name") or not (CFG.get("nsfw_ship_names") or CFG.get(
                "nsfw_" + {"escort": "escort_names", "cargo": "cargo_names"}.get(role, "ship_names"))):
            return
        clean = ship.get("clean_name") or ship["name"]
        dice = random.Random("{}|{}|{}".format(clean, self.s.get("turn", 0), len(used)))
        rude = self._pick_ship_name(role, used, nsfw=True, rng=dice)
        if rude:
            ship["clean_name"], ship["nsfw_name"] = clean, rude
            ship["name"] = clean if CFG["content"]["rating"] == "family" else rude

    def _sync_ship_names(self):
        """Show each ship's clean or NSFW name as the content rating calls for (Admin > Ratings, or
        the Family-friendly switch in the Media Library). Ships from before NSFW names get one."""
        family = CFG["content"]["rating"] == "family"
        used = self._ship_names_used()
        for p in self.s["players"].values():
            for sh in p.get("ships", []):
                role = SHIPS.get(sh.get("type"), {}).get("role", "trader")
                if not sh.get("nsfw_name") and not family:
                    self._give_nsfw_name(sh, role, used)
                    used.update(n for n in (sh.get("name"), sh.get("nsfw_name")) if n)
                if sh.get("nsfw_name") and sh.get("clean_name"):
                    sh["name"] = sh["clean_name"] if family else sh["nsfw_name"]

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
        return sum(ship_hold(sh) for sh in p["ships"])

    def used(self, p):
        return sum(p["cargo"].values())

    def guns(self, p):
        return sum(sh["guns"] for sh in p["ships"])

    @staticmethod
    def class_count(p, role):
        """Ships of a class, counting those laid up at home (they still count against the limit)."""
        return sum(1 for sh in list(p["ships"]) + list(p.get("laid_up") or ()) if role_of(sh["type"]) == role)

    def fleet_classes(self, p):
        """Each class of the fleet for the screens: how many, the limit, and whether a shipyard sells it yet."""
        traders = self.class_count(p, "trader")
        roles = ROLES + ((FLAG,) if any(role_of(k) == FLAG for k in SHIPS) else ())
        return {r: {"n": self.class_count(p, r), "max": role_limit(r), "unlock": role_unlock(r),
                    "open": traders >= role_unlock(r)} for r in roles}

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
        return max(0.0, m["spread_base"] - m["spread_swing"] * (p["rep"][port] - 50.0) / 50.0) \
            + self.band_effects(p, port)["margin"]               # Hostile and Cool dealers gouge (decision 9)

    def quote(self, p, good, qty, side):
        """Total silver for buying or selling qty units where the player is."""
        port = p["port"]
        mid = self.s["prices"][port][good]
        k = R["market"]["impact"] * qty / GOODS[good]["depth"]
        if side == "buy":
            end = mid * (1 + k)
            return int(math.ceil(qty * (mid + end) / 2 * (1 + self.spread(p, port)))), end
        end = mid / (1 + k)
        total = int(math.floor(qty * (mid + end) / 2 * (1 - self.spread(p, port))))
        return self._purse_pay(port, good, total), end

    # ---- the dealers' purse (Game 3 review, 19 Nov 2026) ------------------------------------------
    # Each port's dealers have only so much silver a month for each cargo. The purse is
    # rules.market.purse_depths x the cargo's depth x its usual price there x the port's purse size, so a
    # boom (paid at boom prices) drains it fast. Whatever a sale would bring past what is left of it is
    # paid at rules.market.purse_over. Shared by every house; filled again each month (_move_markets).
    def purse_size(self, port, good):
        m = R["market"]
        if not m.get("purse_enabled", True):
            return None
        usual = GOODS[good]["base"] * PORTS[port]["mods"].get(good, 1.0)
        return float(m.get("purse_depths", 0.75)) * GOODS[good]["depth"] * usual * float(PORTS[port].get("purse", 1.0) or 1.0)

    def purse_left(self, port, good):
        """Silver this port's dealers still have this month for this cargo (None with no purse rule)."""
        size = self.purse_size(port, good)
        if size is None:
            return None
        paid = float(((self.s.get("purse") or {}).get(port) or {}).get(good, 0.0))
        return max(0.0, size - paid)

    def _purse_pay(self, port, good, total):
        """What a sale worth total at the dealers' prices really pays, once their purse runs short."""
        left = self.purse_left(port, good)
        if left is None or total <= left:
            return total
        over = max(0.0, min(1.0, float(R["market"].get("purse_over", 0.35))))
        return int(math.floor(left + (total - left) * over))

    def _purse_spend(self, port, good, paid):
        if self.purse_size(port, good) is None:
            return
        row = self.s.setdefault("purse", {}).setdefault(port, {})
        row[good] = round(float(row.get(good, 0.0)) + float(paid), 2)

    def purse_view(self, port):
        """{good: [left, size]} for the screen (None with no purse rule)."""
        if not R["market"].get("purse_enabled", True):
            return None
        return {g: [round(self.purse_left(port, g), 2), int(self.purse_size(port, g))] for g in GOODS}

    # ---- selling into a boom uses it up (Game 3 review, 19 Nov 2026) -------------------------------
    def _eat_boom(self, p, good, qty):
        """A sale into a boom or a shortage here eats it: qty / (rules.events.boom_eat_depths x depth) of
        it is gone (all of it at that size or more). The boom's size shrinks on a log scale, and that share
        of the sale's own price drop stays put instead of fading back next month, so a full hold sold into
        a boom mostly ends it while a small sale leaves most of it for later."""
        s, port, ev = self.s, p["port"], R["events"]
        eat = float(ev.get("boom_eat_depths", 3.0) or 0.0)
        if eat <= 0 or qty <= 0:
            return
        frac = min(1.0, qty / (eat * float(GOODS[good]["depth"])))
        hit = False
        for w in list(s.get("windfalls") or ()):
            if w["port"] != port or w["good"] != good or w.get("kind") != "boom":
                continue
            hit = True
            was = float(w["mult"])
            w["mult"] = round(math.exp(math.log(max(1.0, was)) * (1.0 - frac)), 4)
            if w["mult"] < 1.05:
                s["windfalls"].remove(w)
                if w.get("foretold"):
                    self._mark_tips_over(port, good)
                p["log"].append(tx("l.boom_spent", goods=GOODS[good]["name"], port=PORTS[port]["name"]))
            self._ev("market", "boom_eaten", "{} sold {} {} into the boom in {}: x{:.3g} -> x{:.3g}{}".format(
                p["name"], qty, GOODS[good]["name"], PORTS[port]["name"], was, w["mult"],
                " (spent)" if w["mult"] < 1.05 else ""), p, port=port, good=good, qty=qty,
                mult=[was, w["mult"]], spent=w["mult"] < 1.05)
        keep = []
        for sh in s.get("shocks") or ():
            if sh["port"] == port and sh["good"] == good and float(sh["mult"]) > 1.0:
                hit = True
                was = float(sh["mult"])
                sh["mult"] = round(math.exp(math.log(was) * (1.0 - frac)), 4)
                self._ev("market", "boom_eaten", "{} sold {} {} into the shortage in {}: x{:.3g} -> x{:.3g}".format(
                    p["name"], qty, GOODS[good]["name"], PORTS[port]["name"], was, sh["mult"]), p,
                    port=port, good=good, qty=qty, mult=[was, sh["mult"]], spent=sh["mult"] < 1.05, shortage=True)
                if sh["mult"] < 1.05:
                    continue
            keep.append(sh)
        s["shocks"] = keep
        if hit:
            row = (s.get("pushes") or {}).get(port, {}).get(good)
            if row and row[0] < 0:
                # The part of the sale's price drop that answered the boom stays: it no longer fades back.
                stay = row[0] * frac
                row[0] -= stay

    def _mark_tips_over(self, port, good):
        """Every hot tip for this boom shows it as over from next month (the pin says it was missed)."""
        s = self.s
        for q in s["players"].values():
            for tp in q.get("hot_tips") or ():
                if tp.get("port") == port and tp.get("good") == good and tp.get("over") is None \
                        and int(tp.get("lands", 0)) <= s["turn"] + 1 <= int(tp.get("ends", -1)) + 1:
                    tp["over"] = s["turn"] + 1

    def ship_value(self, sh):
        return ship_value(sh)

    def worth(self, p):
        """Net worth (Game 4 review, 20 Nov 2026): silver + bank - debt + the fleet (ships laid up at home too)
        + shares and the great house + every unit of cargo at what the dealers would pay for it today: the
        hold sold in the port the fleet is in, each warehouse sold in its own port, the price falling as it
        sells and the dealers' purse running short, as a real sale would. A full hold of silk is worth what
        it would really fetch, not a posted price nobody would pay for all of it."""
        total = float(p.get("cash", 0)) + float(p.get("bank", 0)) - float(p.get("debt", 0))
        total += sum(ship_value(sh) for sh in p.get("ships") or ())
        total += sum(ship_value(sh) for sh in p.get("laid_up") or ())
        total += holdings_value(p)
        return total + self.goods_value(p)

    def goods_value(self, p):
        """Every unit the house owns, aboard and ashore, at what the dealers would pay (see worth)."""
        stores = [(p.get("port"), p.get("cargo") or {})]
        if p.get("wh"):
            stores.append((home_of(p), p["wh"]))
        for port, d in (p.get("depots") or {}).items():
            if isinstance(d, dict) and d.get("goods"):
                stores.append((port, d["goods"]))
        return sum(self.dealer_value(p, port, g, q) for port, goods in stores for g, q in goods.items()
                   if g in GOODS and q > 0)

    def dealer_value(self, p, port, good, qty):
        """What qty units would fetch from the dealers in port today (as quote, for any port)."""
        if port not in PORTS or qty <= 0:
            return qty * normal_price(good)
        mid = self.s["prices"][port][good]
        k = R["market"]["impact"] * qty / GOODS[good]["depth"]
        end = mid / (1 + k)
        total = int(math.floor(qty * (mid + end) / 2 * (1 - self.spread(p, port))))
        return float(self._purse_pay(port, good, total))

    def commissioned_rank(self, p):
        return next((rank for rank in CFG["ranks"] if rank["id"] == p.get("rank_id")), CFG["ranks"][0])

    # ---- running costs (Game 3 review, 19 Nov 2026) ----------------------------------------------
    def upkeep(self, p):
        """This month's crew wages and ship upkeep: rules.fleet.upkeep_rate of each ship's price plus
        upkeep_gun for each gun and cannon, times (1 + upkeep_rank for each rank the house holds above
        upkeep_rank_from)."""
        f = R["fleet"]
        if not f.get("upkeep_enabled", True) or (not p.get("ships") and not p.get("laid_up")):
            return 0
        laid = float(f.get("laid_up_wage", 0.25))
        base = sum(self.ship_wage(sh) for sh in p["ships"]) + laid * sum(self.ship_wage(sh) for sh in p.get("laid_up") or ())
        return int(round(base * self.upkeep_rank_mult(p)))

    @staticmethod
    def ship_wage(sh):
        """One ship's monthly wage before the rank rise: upkeep_rate of her price plus upkeep_gun per gun and
        cannon. The flagship's is flat (rules.fleet.flagship_wage, Game 4 review), like a big merchantman's."""
        f = R["fleet"]
        if sh.get("type") not in SHIPS:
            return 0.0
        guns = float(f.get("upkeep_gun", 15)) * (sh.get("guns", 0) + sh.get("cannons", 0))
        if role_of(sh["type"]) == FLAG and f.get("flagship_wage") is not None:
            return float(f["flagship_wage"]) + guns
        return float(f.get("upkeep_rate", 0.02)) * float(SHIPS[sh["type"]]["price"]) + guns

    def idle_wages(self, p):
        """(silver, empty share): how much of this month's wages went on empty hold. The wages of every
        ship that carries cargo, times the share of the fleet's hold that is empty."""
        cap = self.capacity(p)
        if cap <= 0 or not R["fleet"].get("upkeep_enabled", True):
            return 0, 0.0
        empty = max(0.0, 1.0 - self.used(p) / float(cap))
        carriers = sum(self.ship_wage(sh) for sh in p["ships"] if ship_hold(sh) > 0)
        return int(round(carriers * empty * self.upkeep_rank_mult(p))), round(empty, 4)

    def fleet_ledger(self, p):
        """The Fleet tab's cost ledger (20 Nov 2026): what each class of ship costs a month, worked out the way
        upkeep() charges it, so the classes add up to the month's bill. Each class has crew and hull upkeep, guns and
        cannons, and the rank rise; `idle` is the part of it that carried empty hold (the ships with a hold, times the
        share of the fleet's hold that is empty, as idle_wages() works it out); `repair` is what her hulls owe the
        yard. `laid` is the ships resting at home: what they cost now and what they would cost at full wage."""
        f = R["fleet"]
        on = bool(f.get("upkeep_enabled", True))
        mult = self.upkeep_rank_mult(p)
        laid_rate = float(f.get("laid_up_wage", 0.25))
        gun_rate = float(f.get("upkeep_gun", 15))
        cap = self.capacity(p)
        empty = max(0.0, 1.0 - self.used(p) / float(cap)) if cap > 0 else 0.0
        raw = {}
        for sh in p["ships"]:
            if sh.get("type") not in SHIPS:
                continue
            c = raw.setdefault(role_of(sh["type"]), {"n": 0, "crew": 0.0, "guns": 0.0, "idle": 0.0, "hold": 0, "repair": 0})
            guns = gun_rate * (sh.get("guns", 0) + sh.get("cannons", 0))
            wage = self.ship_wage(sh)
            c["n"] += 1
            c["guns"] += guns
            c["crew"] += wage - guns
            c["hold"] += ship_hold(sh)
            c["repair"] += int(math.ceil((SHIPS[sh["type"]]["hull"] - sh["hull"]) * self.repair_rate(p, sh)))
            if ship_hold(sh) > 0:
                c["idle"] += wage
        classes = {}
        for role, c in raw.items():
            total = int(round((c["crew"] + c["guns"]) * mult)) if on else 0
            crew = int(round(c["crew"])) if on else 0
            guns = int(round(c["guns"])) if on else 0
            classes[role] = {"n": c["n"], "crew": crew, "guns": guns, "rank": total - crew - guns, "total": total,
                             "idle": int(round(c["idle"] * empty * mult)) if on else 0,
                             "hold": c["hold"], "repair": c["repair"]}
        # The classes' rounding can differ from the month's single rounded bill by a few silver: the largest class takes it.
        laid_ships = list(p.get("laid_up") or ())
        laid_full = int(round(sum(self.ship_wage(sh) for sh in laid_ships) * mult)) if on else 0
        laid_now = int(round(laid_full * laid_rate)) if on else 0
        bill = self.upkeep(p)
        gap = bill - laid_now - sum(c["total"] for c in classes.values())
        if gap and classes:
            big = max(classes.values(), key=lambda c: c["total"])
            big["total"] += gap
            big["rank"] += gap
        return {"on": on, "rank_mult": round(mult, 4), "empty": round(empty, 4), "bill": bill, "classes": classes,
                "laid": {"n": len(laid_ships), "now": laid_now, "full": laid_full}}

    def upkeep_rank_mult(self, p):
        f = R["fleet"]
        ids = [r["id"] for r in CFG["ranks"]]
        frm = f.get("upkeep_rank_from", "merchant")
        start = ids.index(frm) if frm in ids else 0
        mine = ids.index(p.get("rank_id")) if p.get("rank_id") in ids else 0
        return 1.0 + float(f.get("upkeep_rank", 0.25)) * max(0, mine - start)

    def yearly_upkeep(self, p):
        """December's bill for the great house (house_upkeep of what was paid for it) and each port where
        the house is Patron (patron_upkeep of what its shares there cost). [(line, port or None, amount)]."""
        e = R.get("estates") or {}
        out = []
        paid = float(p.get("estate_paid", 0) or 0)
        if paid > 0 and e.get("house_upkeep", 0):
            out.append(("house", None, int(round(paid * float(e["house_upkeep"])))))
        if e.get("patron_upkeep", 0):
            for port in PORTS:
                if (self.s.get("patrons") or {}).get(port) == p["id"]:
                    cost = float((p.get("share_paid") or {}).get(port, 0) or 0) * float(e["patron_upkeep"])
                    if cost >= 1:
                        out.append(("patron", port, int(round(cost))))
        return out

    def _charge(self, p, amount):
        """Take a running cost from silver, then the bank; whatever is left goes on the debt."""
        amount = max(0, int(amount))
        cash = int(min(amount, max(0.0, p["cash"])))
        p["cash"] -= cash
        bank = int(min(amount - cash, max(0.0, p["bank"])))
        p["bank"] -= bank
        owed = amount - cash - bank
        if owed:
            p["debt"] += owed
        return owed

    def _pay_running_costs(self, p):
        """Month end: wages and upkeep for the fleet; in December the great house and patronages too."""
        wages = self.upkeep(p)
        if wages:
            owed = self._charge(p, wages)
            self._book(p, "upkeep", -wages)
            self._ev("finance", "upkeep", "{}: crew wages and upkeep for {} ship(s) {} (rank x{:.2f}){}".format(
                p["name"], len(p["ships"]), money(wages), self.upkeep_rank_mult(p),
                "; {} went on the debt".format(money(owed)) if owed else ""), p, amount=wages, owed=owed)
            if owed:
                p["log"].append(tx("l.upkeep_debt", cost=money(wages), owed=money(owed)))
            idle, empty = self.idle_wages(p)
            book = p.setdefault("idle", {"last": 0, "share": 0.0, "year": 0, "game": 0, "year_no": self.s["turn"] // 12})
            if book.get("year_no") != self.s["turn"] // 12:
                book["year"], book["year_no"] = 0, self.s["turn"] // 12
            book["last"], book["share"] = idle, empty
            book["year"] = int(book.get("year", 0)) + idle
            book["game"] = int(book.get("game", 0)) + idle
            f = R["fleet"]
            if idle >= int(f.get("idle_note_min", 1000)) and empty >= float(f.get("idle_note_share", 0.25)):
                p["log"].append(tx("l.idle_wages", idle=money(idle), pct=int(round(empty * 100)), wages=money(wages)))
                self._ev("finance", "idle_wages", "{}: {} of the month's wages carried empty hold ({:.0%} empty)".format(
                    p["name"], money(idle), empty), p, idle=idle, empty=empty)
        if self.s["turn"] % 12 != 11:
            return
        bills = self.yearly_upkeep(p)
        if not bills:
            return
        total = sum(b[2] for b in bills)
        owed = self._charge(p, total)
        self._book(p, "estate_upkeep", -total)
        house = sum(b[2] for b in bills if b[0] == "house")
        patron = [b for b in bills if b[0] == "patron"]
        # Every port the house is Patron of counts, also those whose shares were earned (they cost nothing to
        # keep, so they have no bill): the line said "patronage of 0 ports" for a Patron of five.
        n_pat = sum(1 for k in PORTS if (self.s.get("patrons") or {}).get(k) == p["id"])
        p["log"].append(tx("l.yearly_upkeep", total=money(total), house=money(house),
                           patron=money(sum(b[2] for b in patron)), n=n_pat,
                           s="" if n_pat == 1 else "s"))
        self._ev("finance", "yearly_upkeep", "{}: the year's upkeep {} (great house {}, patronage of {} port(s) {}){}".format(
            p["name"], money(total), money(house), n_pat, money(sum(b[2] for b in patron)),
            "; {} went on the debt".format(money(owed)) if owed else ""), p, amount=total, house=house,
            patron={b[1]: b[2] for b in patron}, owed=owed)

    def _check_promotions(self):
        if self.s["phase"] == "port":
            for captain in self.s["players"].values():
                self._promote(captain)

    def _promote(self, p):
        if self.s["phase"] != "port" or p["port"] != home_of(p) or p.get("voy") or self._customs_pending(p):
            return
        ranks = CFG["ranks"]
        current = ranks.index(self.commissioned_rank(p))
        qualified = rank_index(int(self.worth(p)), self.s.get("years"))
        if qualified <= current:
            return
        rank = ranks[qualified]
        previous = ranks[current]
        following = ranks[qualified + 1] if qualified + 1 < len(ranks) else None
        if following:
            following = dict(following, worth=rank_worth(following, self.s.get("years")))
        record = {"worth": int(self.worth(p)), "ships": len(p["ships"]), "date": date_label(self.s["turn"]),
                  "turn": self.s["turn"], "name": p["name"], "firm": p["firm"],
                  "previous": {"id": previous["id"], "title": previous["title"]},
                  "next": dict(following) if following else None,
                  "ranks": [{"id": r["id"], "title": r["title"]} for r in ranks]}
        serial = p.get("promotion_serial", 0) + 1
        p["rank_id"], p["promotion_serial"] = rank["id"], serial
        # Each rank climbed above Clerk earns one free port share (rules.estates.shares_per_rank).
        earned = self._rank_shares(qualified) - self._rank_shares(current)
        if earned > 0:
            self.award_shares(p, earned, "promotion", rank=rank["title"])
        # The Mayor's words (m.promote.N), one of a bank drawn from this house's own deck.
        # The ranks above Taipan have their own, grander bank (m.promote_top.N, 19 Nov 2026).
        say = self._draw(p, "m.promote_top" if rank.get("scales") and self._bank("m.promote_top") else "m.promote")
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
        qualified = rank_index(worth, self.s.get("years"))
        nxt = ranks[following] if following < len(ranks) else None
        return {"rank": current["title"], "rank_id": current["id"],
                "next_rank": dict(nxt, worth=rank_worth(nxt, self.s.get("years"))) if nxt else None,
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

    # ------------------------------------------------- debt cap and bankruptcy (19 Nov 2026) --
    # Both are in Admin > Economy > Bank and moneylender. The cap stops a runaway debt growing for
    # ever; bankruptcy is the way back for a house worth less than nothing: after bankrupt_months in a
    # row under water, the moneylender takes everything, clears the books and sets the captain up again
    # at home with a sound junk and a small stake. Ranks are kept (they are for life).
    def debt_cap(self, p):
        mult = float(R["bank"].get("debt_cap_mult", 0) or 0)
        return mult * self.collectors_line(p) if mult > 0 else None

    def _debt_after_interest(self, p):
        grown = p["debt"] * (1 + loan_rate())
        cap = self.debt_cap(p)
        if cap is None or grown <= cap:
            p.pop("debt_capped", None)
            return grown
        new = max(p["debt"], cap)              # never adds past the cap; never forgives what is owed
        if not p.get("debt_capped"):
            p["debt_capped"] = True
            p["log"].append(tx("l.debt_capped", home=PORTS[home_of(p)]["name"]))
            self._ev("finance", "debt_capped", "{}: debt {} has reached the cap {} ({} x the collectors' line); "
                     "no more interest is added while it stays there".format(
                         p["name"], money(p["debt"]), money(cap), R["bank"].get("debt_cap_mult")), p)
        return new

    def bankruptcy(self, p):
        """For the debt clock: months under water so far, and month-ends until the books are closed
        (None when the house is not under water or bankruptcy is off)."""
        b = R["bank"]
        if not b.get("bankrupt_enabled", True) or self.worth(p) >= 0:
            return None
        need = max(1, int(b.get("bankrupt_months", 12)))
        under = int(p.get("under_water", 0))
        return {"months": under, "need": need, "in": max(1, need - under),
                "short": int(math.ceil(-self.worth(p)))}

    def _bankruptcy_month(self, p, news):
        b = R["bank"]
        if not b.get("bankrupt_enabled", True):
            p.pop("under_water", None)
            return
        if self.worth(p) >= 0:
            if p.get("under_water"):
                self._ev("finance", "above_water", "{}: net worth is back above zero".format(p["name"]), p)
            p.pop("under_water", None)
            return
        need = max(1, int(b.get("bankrupt_months", 12)))
        warn = max(0, int(b.get("bankrupt_warn", 3)))
        p["under_water"] = int(p.get("under_water", 0)) + 1
        left = need - p["under_water"]
        home = PORTS[home_of(p)]["name"]
        if left <= 0:
            self._bankrupt(p, news)
        elif p["under_water"] == 1 or left <= warn:
            p["log"].append(tx("l.bankrupt_warn", months=left, s="" if left == 1 else "s", home=home))
            self._ev("finance", "bankrupt_warn", "{}: worth {} is below zero ({} month(s) running); the books are "
                     "closed in {} month(s)".format(p["name"], money(self.worth(p)), p["under_water"], left), p)

    def _bankrupt(self, p, news):
        b, s = R["bank"], self.s
        home = home_of(p)
        worth0 = int(self.worth(p))
        seized = {"cash": int(p["cash"]), "bank": int(p["bank"]), "debt": int(p["debt"]),
                  "ships": [sh["name"] for sh in p["ships"]], "cargo": dict(p["cargo"]), "wh": dict(p["wh"]),
                  "depots": {k: dict((d or {}).get("goods") or {}) for k, d in (p.get("depots") or {}).items()},
                  "shares": {},
                  "estate": int(p.get("estate", 0) or 0)}
        # Port shares go back to each port's pool; the Patron is worked out again.
        for port, held in list((s.get("shares") or {}).items()):
            if isinstance(held, dict) and held.get(p["id"]):
                seized["shares"][port] = int(held.pop(p["id"]))
                self.patron_of(port)
        # The moneylender keeps them: shares seized are lost for good, not handed back to place again.
        p["share_earned"] = max(0, self.shares_earned(p) - sum(seized["shares"].values()))
        stake = float(int(b.get("bankrupt_stake", 2000)))
        # Before her clerks come aboard the crew squirrels away a share of the silver and cargo aboard
        # (rules.hide.bankrupt). It stays with the house; the cargo rides in the new ship, as much as fits.
        hid_cash = int(max(0.0, p["cash"]) * self._hide_share()) if self._hide_on("bankrupt") else 0
        hid = self._crew_hide(p, dict(p["cargo"]), "bankrupt", "finance")
        hid_basis = {g: (p.get("basis") or {}).get(g) for g in hid if (p.get("basis") or {}).get(g) is not None}
        seized["cash"] -= hid_cash
        seized["cargo"] = {g: q - hid.get(g, 0) for g, q in seized["cargo"].items() if q - hid.get(g, 0) > 0}
        p["cash"], p["bank"], p["debt"] = stake + hid_cash, 0.0, 0.0
        p["cargo"], p["wh"] = {}, {}
        for d in (p.get("depots") or {}).values():
            if isinstance(d, dict):
                d["goods"] = {}
        p["share_paid"] = {}
        p["estate"], p["estate_paid"] = 0, 0.0
        p.pop("estate_costs", None)
        p.pop("estate_rep", None)
        p["basis"] = {}
        p.pop("debt_over", None)
        p.pop("debt_capped", None)
        p.pop("under_water", None)
        p["port"] = home
        p["customs"], p["bond"] = None, None
        p["tab"] = self._new_tab()
        p["net"] = {}
        wk = R["wreck"]
        kind = SHIPS[wk["ship"]]
        p["ships"] = [self._new_ship(wk["ship"], guns=max(0, min(int(wk.get("guns", 2)), kind["slots"])),
                                     hull=kind["hull"])]
        p["laid_up"] = []                     # ships laid up at home go with the rest
        room = self.capacity(p)
        for g in sorted(hid, key=lambda k: -normal_price(k)):     # the dearest first, as much as the hold takes
            q = min(hid[g], room)
            hid[g] = q
            room -= q
        hid = {g: q for g, q in hid.items() if q > 0}
        p["cargo"] = dict(hid)
        p["basis"] = {g: v for g, v in hid_basis.items() if g in hid}
        if self.standing_on():
            st = R["standing"]
            for k in PORTS:
                self._standing(p, k, -float(st["bankrupt_home" if k == home else "bankrupt_away"]), "bankrupt")
        else:
            self._gain_rep(p, home, -float(b.get("bankrupt_rep", 10)))
        p["bankruptcies"] = int(p.get("bankruptcies", 0)) + 1
        self._book(p, "bankrupt", stake + hid_cash + self._cost_of(p, hid) - worth0)
        p["log"].append(tx("l.bankrupt", home=PORTS[home]["name"], stake=money(stake),
                           ship=kind["name"].lower()))
        if hid_cash or hid:
            bits = ([tx("w.hid_silver", cash=money(hid_cash))] if hid_cash else []) + ([self._goods_text(hid)] if hid else [])
            p["log"].append(tx("l.hid_bankrupt", what=" and ".join(bits)))
        news.append(tx("n.bankrupt", name=p["name"], firm=p["firm"], home=PORTS[home]["name"]))
        self._ev("finance", "bankrupt", "{} ({}) went bankrupt: worth {}; the moneylender took everything "
                 "and cleared the books; set up again in {} with a {} and {}".format(
                     p["name"], p["firm"], money(worth0), PORTS[home]["name"], kind["name"].lower(), money(stake)),
                 p, worth=worth0, seized=seized, stake=int(stake), hid_cash=hid_cash, hid=dict(hid))
        self._mayor_greeting(p)
        jail.on_bankrupt(self, p, news)             # debtors' prison at home before the fresh start

    def repair_rate(self, p, sh):
        f = R["fleet"]
        rate = f["repair_base"] + SHIPS[sh["type"]]["price"] / float(f["repair_price_div"])
        if not port_has(p, p["port"], "shipyard"):
            rate *= f["repair_noyard"]
        rate = max(0.01, rate * (1 - f["repair_rep_discount"] * (p["rep"][p["port"]] - 50.0) / 50.0) * self.yard_mult(p))
        if sh.get("crippled"):
            # A crippled escort (Game 4 review): mending her from 1 hull costs cripple_repair of a new one.
            full = max(1, int(SHIPS[sh["type"]]["hull"]) - 1)
            rate = max(rate, float(SHIPS[sh["type"]]["price"]) * float(f.get("cripple_repair", 0.333)) / full)
        return rate

    def repair_ceiling(self, p, sh):
        """Hull a ship can be mended to here: full at a shipyard; in a port without one only up to
        rules.storm.patch_max of her full hull (a patch, not a mend). Never below what she has."""
        full = int(SHIPS[sh["type"]]["hull"])
        if not storm.on() or port_has(p, p["port"], "shipyard"):
            return full
        share = float(storm.rules()["patch_max"])
        if share >= 1.0:
            return full
        return max(int(sh["hull"]), min(full, int(full * share)))

    def repair_need(self, p, sh):
        return max(0, self.repair_ceiling(p, sh) - int(sh["hull"]))

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
                "gift": 0.0,     # gift: the purse given to the Mayor this visit (0 = she can still be called on)
                "goods": {}}     # goods: {cargo: [sales, cost]} sold this visit, for the Mayor's share of profit

    def _tally_sale(self, p, g, gain, cost):
        """A sale in port: its takings, its profit (a loss offsets profit this visit) and the cargo's own
        sales and cost, which the Mayor's share of profit reads (Harbour dues > Share of profit)."""
        self._tally(p, "sales", gain)
        tab = p["tab"]
        tab["profit"] = tab.get("profit", 0.0) + (gain - cost)
        if not isinstance(tab.get("goods"), dict):
            tab["goods"] = {}
        row = tab["goods"].setdefault(g, [0.0, 0.0])
        row[0] += float(gain)
        row[1] += max(0.0, float(cost))

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

    # ---------------------------------------------------- the crew hides --
    def _hide_share(self, g=None):
        """One draw of the share the crew hides (rules.hide): min..max, dear goods dear_mult as well."""
        h = R.get("hide") or {}
        lo, hi = sorted((float(h.get("min", 0.1)), float(h.get("max", 0.3))))
        share = self.rng.uniform(lo, hi)
        if g is not None and g in set(h.get("dear_goods") or []):
            share *= float(h.get("dear_mult", 1.5))
        return max(0.0, min(1.0, share))

    def _hide_on(self, what):
        h = R.get("hide") or {}
        return bool(h.get("enabled", True)) and bool(h.get(what, True))

    def _crew_hide(self, p, goods, what, cat):
        """Before customs, the Port Authority, pirates or the moneylender take cargo (owner's decision,
        19 Nov 2026), the crew always gets a share of it out of sight. goods: {good: units about to be
        taken}. Each cargo keeps its own random share (_hide_share); a fraction of a unit is kept or not
        by chance, so even a small lot can be saved. Returns {good: units hidden}; the rest is taken."""
        if not self._hide_on(what):
            return {}
        hid = {}
        for g in sorted(goods):
            q = int(goods[g] or 0)
            if q <= 0:
                continue
            want = q * self._hide_share(g)
            k = int(want) + (1 if self.rng.random() < want - int(want) else 0)
            k = min(q, k)
            if k > 0:
                hid[g] = k
        if hid:
            self._ev(cat, "crew_hid", "{}: the crew hid {} from {}".format(
                p["name"], self._goods_text(hid), {"customs": "customs", "desk": "the Port Authority",
                                                    "pirates": "the pirates", "bankrupt": "the moneylender"}.get(what, what)),
                p, hid=dict(hid), what=what)
        return hid

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
        # The Mayor's share of profit: its own standing and shares rule, outside the courtesy and the relief above.
        cut = self.profit_share(p, level, rep)
        if cut["amount"] > 0:
            lines.append(cut)
        return {"lines": lines, "total": max(0, after + relief) + cut["amount"], "level": level, "rep": int(round(rep)),
                "profit_rate": cut["month"]}

    # The Mayor's share of profit (Harbour dues > Share of profit). Only profit made selling cargo in her port
    # this visit is counted. The first `profit_free` is never charged, so small loads (a few rice or tea sales)
    # pay nothing; a loss on one cargo offsets a gain on another. Each cargo is charged by its margin
    # (profit / cost): nothing at or below profit_margin_floor, rising to the month's rate at
    # profit_margin_full and up to profit_top_mult x the rate at profit_margin_top. The rate is drawn for each
    # port each month between profit_rate_min and profit_rate_max from its own seed (never the game's dice), and
    # multiplied by the port's dues level. Standing 100 takes profit_rep_cut off (0 adds as much), and each share
    # held in the port takes the same cut as it does from the Port Authority tax (all 10 = nothing to pay).
    def profit_rate(self, port):
        """This month's share-of-profit rate in a port, before its dues level, standing and shares."""
        d = R["dues"]
        lo = max(0.0, float(d.get("profit_rate_min", 0.0) or 0.0))
        hi = max(lo, float(d.get("profit_rate_max", lo) or 0.0))
        if hi <= 0:
            return 0.0
        roll = random.Random("profit_share:{}:{}:{}".format(self.s.get("game_id", ""), self.s["turn"], port)).random()
        return round(lo + (hi - lo) * roll, 6)

    @staticmethod
    def profit_margin_factor(margin):
        """How much of the month's rate a cargo sold at this margin pays (0 up to the floor, 1 at full)."""
        d = R["dues"]
        floor = float(d.get("profit_margin_floor", 0.25))
        full = max(floor + 1e-6, float(d.get("profit_margin_full", 1.0)))
        top = max(full + 1e-6, float(d.get("profit_margin_top", 2.0)))
        top_mult = max(1.0, float(d.get("profit_top_mult", 1.5)))
        if margin <= floor:
            return 0.0
        if margin <= full:
            return (margin - floor) / (full - floor)
        return 1.0 + (top_mult - 1.0) * min(1.0, (margin - full) / (top - full))

    def profit_share(self, p, level=None, rep=None):
        """The share-of-profit line on the Mayor's bill (amount 0 when nothing is due)."""
        d, port = R["dues"], p["port"]
        month = self.profit_rate(port)
        out = {"key": "profit", "basis": 0, "rate": 0.0, "amount": 0, "month": month, "free": 0}
        if not d.get("profit_enabled", True) or month <= 0:
            return out
        level = float(PORTS.get(port, {}).get("dues", 1.0)) if level is None else level
        rep = float(p["rep"].get(port, 50.0)) if rep is None else rep
        free = max(0.0, float(d.get("profit_free", 0.0) or 0.0))
        out["free"] = int(free)
        goods = (p.get("tab") or {}).get("goods") or {}
        rows = [(float(v[0]) - float(v[1]), float(v[1])) for v in goods.values()
                if isinstance(v, (list, tuple)) and len(v) == 2]
        net = sum(pr for pr, _ in rows)
        gains = sum(pr for pr, _ in rows if pr > 0)
        if net <= free or gains <= 0:
            return out
        keep = min(1.0, (net - free) / gains)     # losses and the free allowance come off every gain alike
        weighted = sum(pr * keep * self.profit_margin_factor(pr / cost if cost > 0 else float("inf"))
                       for pr, cost in rows if pr > 0)
        rep_f = max(0.0, 1.0 - float(d.get("profit_rep_cut", 0.5)) * (rep - 50.0) / 50.0)
        share_f = max(0.0, 1.0 - self.share_cut(p, port))
        amount = int(round(weighted * month * level * rep_f * share_f))
        basis = net - free
        out.update(basis=int(round(basis)), amount=max(0, amount),
                   rate=round(amount / basis, 4) if basis > 0 else 0.0,
                   rep_f=round(rep_f, 4), share_cut=round(1.0 - share_f, 4))
        return out

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
        """The rate this house is charged in a port: nothing at home, the port's rate elsewhere,
        less share_cut for each share the house holds in that port."""
        if self.home_free(p, port):
            return 0.0
        cut = self.band_effects(p, port)["tax_cut"]          # Warm and Favoured houses pay less (decision 10)
        return round(self.tax_rate(port) * max(0.0, 1.0 - self.share_cut(p, port)) * max(0.0, 1.0 - cut), 6)

    def _spot_check(self, p, port):
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
                # A Hostile or Cool house is searched more often still (rules.standing, decision 9).
                "rep": round(max(0.1, 1 + c["rep_audit"] * (50.0 - rep) / 50.0) * self.band_effects(p, port)["audit"], 4),
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
        spot = self._spot_check(p, port) if lines else None
        if spot:                                 # stopped anyway: the port's full rate, this landing only
            rate, at_home = self.tax_rate(port), False
        status = "declare" if rate > 0 and lines else "welcome"
        cx = self._officer_ctx(p, port)
        box = int(c["strongbox"] * self.rng.uniform(1 - c["strongbox_swing"], 1 + c["strongbox_swing"])) if status == "declare" else 0
        officer = "taxlady" if self.registrar_here(p, port) else self.officer_of(port)
        p["customs"] = {"port": port, "turn": self.s["turn"], "status": status, "officer": officer,
                        "rate": round(rate, 4), "base": float(PORTS[port].get("tax_rate", 0.0) or 0.0),
                        "free": rate <= 0, "home_free": at_home, "spot": spot, "lines": lines, "cx": cx, "box": box,
                        "result": None}
        if spot:
            p["customs"]["say"] = "l.customs_spot_" + spot
        elif status == "declare":
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
            "stops the house for a spot check at the full rate of {} ({})".format(
                pct(rate), "its home port" if spot == "home" else "its shares make the port free") if spot else
            "waves the house in (its home port, no tax)" if at_home else
            "waves the house in (free port)" if rate <= 0 else "has nothing to tax (empty hold)" if not lines else
            "asks for a declaration at {}: {}; strongbox {}, mood x{}".format(
                pct(rate), ", ".join("{} {} worth {}".format(ln["qty"], GOODS[ln["good"]]["name"], money(ln["value"]))
                                     for ln in lines), money(box), cx["mood"])),
            p, port=port, rate=rate, lines=lines, cx=cx, box=box, status=status, spot=spot)

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
            s["prices"][port][good] = self._windfall_price("boom", before, self._target(port, good))
            if not ev.get("stack_booms", False):
                s["prices"][port][good] = self._clamp(port, good, s["prices"][port][good])
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

    def _caught_fine(self, p, port, out):
        """The fine for a caught lie (rules.standing, decision 2), set by the band the house is now in: the
        larger of fine_hidden x the hidden value found x the band's loss roll, or the house's net worth x a
        roll between the band's floor_lo and floor_hi. Shared over the caught lines by what each hid."""
        st = R["standing"]
        caught = [r for r in out if r["outcome"] == "caught"]
        hidden = {id(r): max(0, r["value"] - r["declared"]) for r in caught}
        found = sum(hidden.values())
        band = self.BANDS[self.band_here(p, port)]
        by_value = float(st.get("fine_hidden", 0.5)) * found * self.band_roll(p, port, "pen", "fine")
        lo, hi = sorted((float(st.get(band + "_floor_lo", 0)), float(st.get(band + "_floor_hi", 0))))
        by_worth = max(0.0, self.worth(p)) * self._band_rng(p, "fine_floor").uniform(lo, hi)
        total = int(math.ceil(max(by_value, by_worth) - 1e-9))
        left = total
        for i, r in enumerate(caught):
            part = left if i == len(caught) - 1 else int(round(total * (hidden[id(r)] / float(found) if found
                                                                          else 1.0 / len(caught))))
            r["fine"] = max(0, min(left, part))
            left -= r["fine"]
        self._ev("customs", "caught_fine", "{}: caught in {} ({}), hidden {}: fine {} (hidden x roll {}, net worth floor {})".format(
            p["name"], PORTS[port]["name"], band, money(found), money(total), money(by_value), money(by_worth)),
            p, port=port, band=band, hidden=found, fine=total)
        return sum(r["fine"] for r in caught)

    PAY_DESK = ("nothing", "less", "correct", "more")

    def pay_share(self, p, cu, good, choice):
        """The share of a line's true worth each pay button declares. Pay Less is drawn per cargo line
        between pay_less_lo and pay_less_hi from its own seed (game, house, month, port, cargo), so it is
        fixed for the visit, never redrawn, and never touches the game's dice. The player is not shown it
        until her ruling."""
        c = R["customs"]
        if choice == "nothing":
            return 0.0
        if choice == "correct":
            return 1.0
        if choice == "more":
            return max(1.0, min(float(c["max_declare"]), float(c.get("pay_more_share", 1.1))))
        lo, hi = sorted((float(c.get("pay_less_lo", 0.7)), float(c.get("pay_less_hi", 0.95))))
        roll = random.Random("payless:{}:{}:{}:{}:{}".format(self.s.get("game_id", ""), p.get("id", p.get("name", "")),
                                                             self.s["turn"], cu.get("port", ""), good)).random()
        return max(0.0, min(1.0, lo + (hi - lo) * roll))

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
        # The four pay buttons (19 Nov 2026): one choice for the whole hold instead of a slider per line.
        # Pay Less draws a hidden share of each line's worth; Pay Correct and Pay More are fully safe
        # (she neither buys nor searches). With no choice, the old per-line values are used.
        choice = a.get("choice") if a.get("choice") in self.PAY_DESK else None
        declared, shares = {}, {}
        for ln in open_lines:
            if choice:
                share = self.pay_share(p, cu, ln["good"], choice)
                shares[ln["good"]] = share
                v = int(math.ceil(ln["value"] * share - 1e-9)) if share > 1 else int(math.floor(ln["value"] * share + 1e-9))
            else:
                try:
                    v = int(round(float(raw.get(ln["good"], ln["value"]))))
                except (TypeError, ValueError):
                    raise GameError(tx("e.whole_number"))
            declared[ln["good"]] = max(0, min(int(math.floor(ln["value"] * top)), v))
        safe = choice in ("correct", "more")
        total_declared = sum(declared.values())
        bribe_mult, bribe = 1.0, None
        if a.get("bribe") and not choice:
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
        desk_hid = {}
        for ln in sorted(open_lines, key=lambda x: -x["appetite"]):
            g, q, value, d = ln["good"], ln["qty"], ln["value"], declared[ln["good"]]
            buy, audit = (0.0, 0.0) if safe else self.customs_odds(cx, ln, d, bribe_mult)
            roll = self.rng.random()
            res = {"good": g, "qty": q, "value": value, "declared": d, "buy": buy, "audit": audit,
                   "roll": round(roll, 5), "outcome": "tax", "units": 0, "paid": 0, "tax": 0, "fine": 0, "back": False}
            if choice:
                res["share"] = round(shares[g], 4)
            if roll < buy:
                per = d / float(q)
                # The crew slips a share below decks before she counts (rules.hide.desk): kept aboard, untaxed.
                hid = self._crew_hide(p, {g: q}, "desk", "voyage").get(g, 0) if (per <= 0 or box >= per) else 0
                room = q - hid
                units = room if per <= 0 else min(room, int(box // per))
                if units > 0:
                    if hid:
                        res["hid"] = hid
                        desk_hid[g] = hid
                    paid = int(round(per * units))
                    box -= paid
                    p["cash"] += paid
                    p["cargo"][g] = p["cargo"].get(g, 0) - units
                    res.update(outcome="buyout" if units == room else "partial", units=units, paid=paid,
                               cost=round(float((p.get("basis") or {}).get(g, ln["unit"])), 4))
                    self._book(p, "pa_sold", paid, arrival=True)
                    self._book(p, "cost", -res["cost"] * units, arrival=True)
                    paid_in += paid
                    res["tax"] = int(math.ceil(rate * per * (q - units - hid) - 1e-9))
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
        if desk_hid:
            p["log"].append(tx("l.hid_desk", goods=self._goods_text(desk_hid)))
        rep_change, generous = 0.0, False
        value_total = sum(ln["value"] for ln in open_lines)
        if self.standing_on():
            # Reputation swings (19 Nov 2026): a caught lie costs standing first, then the fine is set by
            # the band the house has fallen into; an honest declaration earns standing, more for paying more.
            st = R["standing"]
            if caught:
                hidden_all = sum(max(0, ln["value"] - declared[ln["good"]]) for ln in open_lines)
                share = min(1.0, hidden_all / float(value_total)) if value_total else 1.0
                vary = max(0.0, float(st.get("caught_vary", 0.0)))
                hit = (float(st["caught_base"]) + float(st["caught_lie"]) * share) \
                    * self._band_rng(p, "caught").uniform(1 - vary, 1 + vary)
                rep_change = self._standing(p, port, -hit, "caught", travel=True, roll=False)
                p["honest_run"] = 0
                fine_total = self._caught_fine(p, port, out)
            elif value_total:
                ratio = total_declared / float(value_total)
                if ratio >= 1 - 1e-9:
                    generous = ratio >= float(st.get("pay_more_at", 1.1)) - 1e-9
                    run = p["honest_run"] = int(p.get("honest_run", 0) or 0) + 1
                    gain = float(st["pay_more" if generous else "pay_correct"]) \
                        + min(float(st.get("honest_run_max", 0)), float(st.get("honest_run", 0)) * (run - 1))
                    rep_change = self._standing(p, port, gain, "pay_more" if generous else "honest")
                else:
                    p["honest_run"] = 0
        else:
            if caught:
                rep_change = -c["caught_rep"]
            elif value_total and total_declared > value_total:
                over = total_declared / float(value_total) - 1
                rep_change = c["over_rep"] * min(1.0, over / max(0.01, top - 1))
                generous = True
            if rep_change:
                self._gain_rep(p, port, rep_change)
        # The jail: a big fine may be swapped for time; it is charged when the plea is answered.
        plea = bool(fine_total) and jail.offer_plea(self, p, fine_total, "desk", port, "pa_fine", arrival=True)
        owed = self._collect(p, tax_total + (0 if plea else fine_total))
        self._book(p, "pa_tax", -tax_total, arrival=True)
        self._book(p, "pa_fine", -(0 if plea else fine_total), arrival=True)
        cu["box"] = box
        cu["status"] = "verdict"
        cu["result"] = {"lines": out, "declared": total_declared, "value": value_total, "tax": tax_total,
                        "fine": fine_total, "paid": paid_in, "owed": owed, "caught": caught, "bribe": bribe,
                        "rep": round(rep_change, 2), "choice": choice}
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
                        "lines": out, "choice": choice,
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
        if generous and rep_change > 0:
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
                    self._push(port, g, max(floor, before / (1 + k)))
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
        out["rules"]["pay_more_share"] = max(1.0, min(float(c["max_declare"]), float(c.get("pay_more_share", 1.1))))
        if cu["status"] == "verdict":
            for r in out["result"]["lines"]:
                r["back_price"] = self.buyback_cost(r) if r["units"] and not r["back"] else 0
        name = PORTS[cu["port"]]["name"]
        out["home_free"] = bool(cu.get("home_free"))
        out["spot"] = cu.get("spot")             # "home" / "shares" when a free house was stopped anyway
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

    # Slipping out at night (owner's decisions, 19 Nov 2026; doc "SeaTrader Slipping Out"). The harbour
    # watch spots big fleets more often and watches houses the port distrusts; the fine has a floor set by
    # net worth; standing falls by the band's roll and word travels; the Mayor jails repeat offenders more.
    def slip_odds(self, p, port=None):
        """Chance the harbour watch catches this house slipping out of port."""
        d, port = R["dues"], port or p["port"]
        ships = len(p.get("ships") or [])
        fleet = min(float(d.get("slip_ship_max", 0.6)),
                    float(d.get("slip_base", 0.25)) + float(d.get("slip_per_ship", 0.03)) * ships)
        if self.standing_on():
            fleet += float(d.get("slip_" + self.BANDS[self.band_here(p, port)], 0.0) or 0.0)
        lo, hi = sorted((float(d.get("slip_min", 0.1)), float(d.get("slip_max", 0.7))))
        return max(lo, min(hi, fleet))

    def _slip_floor(self, p, port):
        d = R["dues"]
        band = self.BANDS[self.band_here(p, port)]
        return sorted((float(d.get("slip_floor_{}_lo".format(band), 0) or 0),
                       float(d.get("slip_floor_{}_hi".format(band), 0) or 0)))

    def slip_quote(self, p):
        """What the Set sail card says about slipping out: the odds, the least and most the fine can be if
        caught now (the floor is set by the band after the fall, so the real fine may be higher), and the
        standing at stake before the band's roll."""
        d = R["dues"]
        bill = self.dues(p)["total"]
        lo, hi = self._slip_floor(p, p["port"])
        worth = max(0.0, float(self.worth(p)))
        least = int(math.ceil(max(bill * float(d["slip_mult"]), worth * lo)))
        most = int(math.ceil(max(bill * float(d["slip_mult"]), worth * hi)))
        return {"caught": round(self.slip_odds(p), 4), "fine_min": least, "fine_max": most,
                "rep": float(d["slip_rep"]), "travel": bool(d.get("slip_travel", True))}

    def _slip_fine(self, p, port, bill):
        """The fine for a caught house, set by the band it is in after the fall: the larger of slip_mult x the
        bill, or net worth x a roll between the band's slip floors (its own dice, not the game's)."""
        d = R["dues"]
        by_bill = bill * float(d["slip_mult"])
        lo, hi = self._slip_floor(p, port)
        by_worth = max(0.0, float(self.worth(p))) * self._band_rng(p, "slip_floor").uniform(lo, hi)
        fine = int(math.ceil(max(by_bill, by_worth) - 1e-9))
        self._ev("finance", "slip_fine", "{}: caught slipping out of {} ({}): fine {} ({}x the bill {}, net worth floor {})".format(
            p["name"], PORTS[port]["name"], self.BANDS[self.band_here(p, port)], money(fine), d["slip_mult"],
            money(by_bill), money(by_worth)), p, port=port, bill=bill, fine=fine)
        return fine

    def _slip_prior(self, p, port):
        """Earlier catches slipping out of this port that the Mayor still remembers."""
        months = int(jail.rules().get("slip_repeat_months", 24))
        now = int(self.s.get("turn", 0))
        seen = (p.get("slip_caught_at") or {}).get(port) or []
        return sum(1 for t in seen if now - int(t) < months)

    def _depart(self, p, news):
        """Leaving port: pay the Mayor, or try to slip out at night without paying."""
        p.pop("lot", None)                      # a private lot is offered for the one visit only
        if not p.get("slip"):
            return self._pay_dues(p)
        d, port = R["dues"], p["port"]
        bill = self.dues(p)["total"]
        if bill <= 0:
            return self._pay_dues(p)
        odds = self.slip_odds(p)
        if self._chance(odds, "slip_caught", "{}: slipping out of {} without paying {} in dues".format(
                p["name"], PORTS[port]["name"], money(bill)), p, bill=bill):
            before = float(p["rep"][port])
            if self.standing_on():
                self._standing(p, port, -float(d["slip_rep"]), "slip_caught", travel=bool(d.get("slip_travel", True)))
            else:
                self._gain_rep(p, port, -float(d["slip_rep"]))
            lost = before - float(p["rep"][port])
            fine = self._slip_fine(p, port, bill)
            prior = self._slip_prior(p, port)
            seen = p.setdefault("slip_caught_at", {}).setdefault(port, [])
            seen.append(int(self.s.get("turn", 0)))
            del seen[:-12]
            p["log"].append(tx("l.slip_caught", port=PORTS[port]["name"]))
            p["log"].append(tx("l.slip_fine", port=PORTS[port]["name"], fine=money(fine), rep=int(round(lost))))
            news.append(tx("n.slip_caught", name=p["name"], firm=p["firm"], port=PORTS[port]["name"]))
            self._ev("finance", "slip_caught", "{} was caught slipping out of {} ({} odds): fined {}, standing -{:.1f}".format(
                p["name"], PORTS[port]["name"], pct(odds), money(fine), lost), p, port=port, bill=bill, fine=fine,
                odds=round(odds, 4), rep=round(lost, 2), prior=prior)
            if jail.on_slip_caught(self, p, news, port, prior=prior):
                # Locked up: the fleet stays in port. A big fine may be swapped for time (the plea).
                if not jail.offer_plea(self, p, fine, "slip", port, "dues"):
                    self._pay_dues(p, total=fine)
                p["tab"] = self._new_tab()          # this visit's bill is settled
                return "held"
            return self._pay_dues(p, total=fine)
        p["log"].append(tx("l.slip_away", port=PORTS[port]["name"], total=money(bill)))
        self._ev("finance", "slip_away", "{} slipped out of {} at night without paying {} in dues ({} odds)".format(
            p["name"], PORTS[port]["name"], money(bill), pct(odds)), p, port=port, bill=bill, odds=round(odds, 4))

    def _pay_dues(self, p, mult=1.0, total=None):
        """Charge the mayor's bill as the house leaves port. Silver first; any shortfall goes on the debt.
        total: charge this instead of the bill (a caught slip-out's fine)."""
        bill = self.dues(p)
        total = int(math.ceil(bill["total"] * mult)) if total is None else int(math.ceil(total))
        if total <= 0:
            return
        paid = int(min(total, max(0.0, p["cash"])))
        owed = total - paid
        p["cash"] -= paid
        self._book(p, "dues", -total)
        if owed:
            p["debt"] += owed
            p["log"].append(tx("l.dues_short", port=PORTS[p["port"]]["name"], paid=money(paid), owed=money(owed)))
            if self.standing_on():
                self._standing(p, p["port"], -float(R["standing"].get("dues_short", 0)), "dues_short")
        else:
            p["log"].append(tx("l.dues", port=PORTS[p["port"]]["name"], total=money(total)))
        self._ev("finance", "dues", "{}: paid the mayor of {} {} in harbour dues ({}){}".format(
            p["name"], PORTS[p["port"]]["name"], money(total),
            ", ".join("{} {}".format(ln["key"], ln["amount"]) for ln in bill["lines"]),
            "; {} short, added to the debt".format(money(owed)) if owed else ""),
            p, port=p["port"], total=total, paid=paid, owed=owed, lines=bill["lines"])

    def _gain_rep(self, p, port, amount, why=""):
        before = float(p["rep"][port])
        p["rep"][port] = max(0.0, min(100.0, p["rep"][port] + amount))
        if self.standing_on():
            b0, b1 = self.band_of(before), self.band_of(p["rep"][port])
            if b0 != b1:
                self._band_crossed(p, port, b0, b1, why)
        # Standing bought from the Mayor never exceeds the standing itself. A loss lowers the standing and
        # leaves the bought share alone, so standing and earned standing drop by the same amount.
        gr = p.get("gift_rep")
        if isinstance(gr, dict) and gr.get(port, 0) > p["rep"][port]:
            gr[port] = p["rep"][port]

    # ------------------------------------------------- standing swings --
    # Reputation swings (owner's decisions, 19 Nov 2026; rules.standing). Standing falls in five bands of
    # 20 points. Things the house does move it through _standing, which multiplies each loss or gain by a
    # fresh roll from the band the house is in there. The rolls use their own dice (_band_rng), never the
    # game's, so turning the rule on or off leaves every other roll where it was.
    BANDS = ("hostile", "cool", "neutral", "warm", "favoured")

    @staticmethod
    def standing_on():
        return bool((R.get("standing") or {}).get("enabled"))

    @staticmethod
    def standing_popup_on():
        """The band-change card (web/player.js syncBands). Muted 20 Nov 2026 (rules.standing.popup,
        off by default) until it is redone on the big persona screen; the bars and log lines still run."""
        return bool((R.get("standing") or {}).get("popup"))

    @staticmethod
    def band_of(rep):
        """0 Hostile (0-19) .. 4 Favoured (80-100). web/player.js standingTier is the same sum."""
        return min(4, max(0, int(round(float(rep or 0))) // 20))

    def band_here(self, p, port):
        return self.band_of(p["rep"].get(port, 50.0)) if port in PORTS else 2

    def _band_rng(self, p, what):
        s = self.s
        n = s["band_rolls"] = int(s.get("band_rolls", 0)) + 1
        return random.Random("band:{}:{}:{}:{}:{}".format(s.get("game_id", ""), p.get("id", p.get("name", "")),
                                                           s.get("turn", 0), what, n))

    def band_roll(self, p, port, side, what=""):
        """A fresh multiplier from the band the house is in at port: side "pen" for losses, "rew" for gains."""
        st = R["standing"]
        b = self.BANDS[self.band_here(p, port)]
        lo, hi = sorted((float(st.get("{}_{}_lo".format(b, side), 1.0)), float(st.get("{}_{}_hi".format(b, side), 1.0))))
        return self._band_rng(p, what or side).uniform(lo, hi)

    def _standing(self, p, port, amount, why, travel=False, roll=True):
        """Standing moved by something the house did. roll: times the band's roll (loss or gain); travel:
        a loss is also felt, at rules.standing.region_share, in every other port of the same region.
        Returns the change made at port."""
        if not amount or port not in PORTS:
            return 0.0
        if roll:
            amount *= self.band_roll(p, port, "pen" if amount < 0 else "rew", why)
        before = float(p["rep"][port])
        self._gain_rep(p, port, amount, why)
        done = float(p["rep"][port]) - before
        self._ev("players", "standing", "{}: standing in {} {:+.1f} ({}), now {:.1f}".format(
            p["name"], PORTS[port]["name"], done, why, p["rep"][port]), p, port=port, change=round(done, 2), why=why)
        share = float(R["standing"].get("region_share", 0.0) or 0.0)
        if travel and amount < 0 and share > 0:
            region = PORTS[port]["region"]
            for k in PORTS:
                if k != port and PORTS[k]["region"] == region:
                    self._gain_rep(p, k, amount * share, why + "_word")
        return done

    def _band_crossed(self, p, port, b0, b1, why):
        """Standing in a port has crossed into another band: a line in the log (the Mayor herself says a
        fall into Hostile or a rise into Favoured when the house is in her port), and a popup for the
        player screen (p["bands"]; drift moves only get the log line)."""
        name = PORTS[port]["name"]
        here = port == p.get("port") and not p.get("voy")
        word = tx("stat.standing_" + self.BANDS[b1])
        if why == "drift":
            p.setdefault("log", []).append(tx("l.band_drift", port=name, tier=word))
        elif here and b1 == 0 and b0 > b1:
            p.setdefault("log", []).append(tx("l.band_hostile", port=name))
        elif here and b1 == 4 and b0 < b1:
            p.setdefault("log", []).append(tx("l.band_favoured", port=name))
        else:
            p.setdefault("log", []).append(tx("l.band_down" if b1 < b0 else "l.band_up", port=name, tier=word))
        if why != "drift":
            s = self.s
            s["band_seq"] = int(s.get("band_seq", 0)) + 1
            bands = [e for e in (p.get("bands") or []) if int(e.get("turn", 0)) >= int(s.get("turn", 0)) - 1]
            bands.append({"id": s["band_seq"], "port": port, "from": b0, "to": b1, "rep": int(round(p["rep"][port])),
                          "why": why, "turn": int(s.get("turn", 0))})
            p["bands"] = bands[-8:]
        self._ev("players", "band", "{}: standing in {} moved from {} to {} ({})".format(
            p["name"], name, self.BANDS[b0], self.BANDS[b1], why or "-"), p, port=port, band=[b0, b1], why=why)

    def _drift_standing(self, p):
        """Month end: every port's standing moves rules.standing.drift points back toward 50."""
        step = float(R["standing"].get("drift", 0.0) or 0.0)
        if step <= 0:
            return
        for port in PORTS:
            r = float(p["rep"].get(port, 50.0))
            if abs(r - 50.0) < 1e-9:
                continue
            self._gain_rep(p, port, max(-step, min(step, 50.0 - r)), "drift")

    def band_effects(self, p, port):
        """What the band the house is in at port does to it (rules.standing, decisions 9 and 10)."""
        st = R.get("standing") or {}
        out = {"band": self.band_here(p, port), "audit": 1.0, "margin": 0.0, "yard": 0.0, "match": 0.0,
               "tax_cut": 0.0, "avoid": 0.0}
        if not self.standing_on() or port not in PORTS:
            return out
        b = out["band"]
        if b == 0:
            out.update(audit=float(st.get("hostile_audit", 1)), margin=float(st.get("hostile_margin", 0)),
                       yard=float(st.get("hostile_yard", 0)), match=float(st.get("hostile_match", 0)))
        elif b == 1:
            out.update(audit=float(st.get("cool_audit", 1)), margin=float(st.get("cool_margin", 0)),
                       yard=float(st.get("cool_yard", 0)), match=float(st.get("cool_match", 0)))
        elif b == 3:
            out["tax_cut"] = float(st.get("warm_tax_cut", 0))
        elif b == 4:
            out.update(tax_cut=float(st.get("favoured_tax_cut", 0)), match=-float(st.get("favoured_match", 0)),
                       avoid=float(st.get("favoured_avoid", 0)))
        return out

    def yard_mult(self, p, port=None):
        return 1.0 + self.band_effects(p, port or p["port"])["yard"]

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

    def _trade_say(self, p, prefix, fallback=None):
        """The comprador's line for a trade (trade_text.py): the next of the bank prefix.N for this house,
        else the fallback's bank, else the plain line, so a busy trader seldom hears the same receipt."""
        for bank in (prefix, fallback or prefix):
            if self._bank(bank):
                return self._draw(p, bank)
        return fallback or prefix

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
        self._gain_rep(p, port, gain, "gift")
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
            self._check_contracts(p)
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
        if kind == "storm_ack":
            return storm.act_ack(self, p, a)            # the storm screen's "Make port" (any phase; a fight may follow)
        if kind == "legend":
            return legend.act(self, p, a)               # a Legend's choice or its reckoning closed (no game time)
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
        if kind == "plea":
            return jail.act_plea(self, p, a)
        if kind == "counter":
            jail.check_act(self, p, kind)
            if self._customs_pending(p):
                raise GameError(tx("e.customs_first"))
            return counter.act(self, p, a)      # Under the Counter: her tip, paid for (counter.py)
        if kind in ("jail_serve", "jail_free"):
            return jail.act_jail(self, p, kind)     # the jail screen's taps: serve the month, walk free
        jail.check_act(self, p, kind)            # nothing from a cell; answer a plea first
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
            self._contracts_month(q)            # the home Mayor's first offers
        self._ev("turn", "game_started", "The game has started: {} player{}, {} years".format(
            n, "" if n == 1 else "s", s["years"]), players=[q["name"] for q in s["players"].values()], years=s["years"])
        s["news"].insert(0, "{}: {}".format(date_label(0), tx("n.start_one" if n == 1 else "n.start_many", n=n)))
        self._stamp_news()
        return tx("m.begin")

    @staticmethod
    def _qty(a, key="qty", cap=10_000_000):
        """A positive whole number from the action. Cargo stays under 10 million; money
        (bank, lender) passes cap=MONEY_CAP so a rich house can move its whole fortune."""
        try:
            q = int(a.get(key, 0))
        except (TypeError, ValueError):
            raise GameError(tx("e.whole_number"))
        if q <= 0 or q > cap:
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

    def _trade_rep(self, p, value, g, moved, profit=None, mid=None):
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
        if self.standing_on():
            # Good business only (rules.standing, decision 5): a sale at a profit, a cargo sold where it is
            # short or bought where it is in glut. At most trade_cap a visit, before the band's roll.
            st, port = R["standing"], p["port"]
            usual = GOODS[g]["base"] * PORTS[port]["mods"].get(g, 1.0)
            mid = float(self.s["prices"][port][g] if mid is None else mid)
            good = (moved < 0 and ((profit is not None and profit > 0) or mid >= float(st["short_at"]) * usual)) \
                or (moved > 0 and mid <= float(st["glut_at"]) * usual)
            if not good:
                return
            tab = p.setdefault("tab", {})
            room = max(0.0, float(st["trade_cap"]) - float(tab.get("rep_trade", 0.0)))
            pts = min(room, min(m["rep_trade_cap"], value / float(m["rep_per_value"])))
            if pts <= 0:
                return
            tab["rep_trade"] = float(tab.get("rep_trade", 0.0)) + pts
            self._standing(p, port, pts, "trade")
            return
        self._gain_rep(p, p["port"], min(m["rep_trade_cap"], value / float(m["rep_per_value"])))

    # A private lot (rules.standing, decision 10): a house Favoured in a port is now and then offered a lot
    # below market by one of its dealers on arrival, sized and priced by the band's gain roll. It stands
    # for that visit only and never moves the market.
    def _offer_lot(self, p, port):
        p.pop("lot", None)
        st = R.get("standing") or {}
        if not self.standing_on() or port not in PORTS or self.band_here(p, port) != 4:
            return
        if self._band_rng(p, "lot").random() >= float(st.get("lot_chance", 0.0)):
            return
        risky = set(self.banned(port)) | set(contraband())
        pool = sorted(g for g in GOODS if g not in risky and g in self.s["prices"][port])
        if not pool:
            return
        rng = self._band_rng(p, "lot_what")
        g = rng.choice(pool)
        roll = self.band_roll(p, port, "rew", "lot")
        qty = max(5, int(GOODS[g]["depth"] * float(st.get("lot_depth", 0.15)) * roll))
        off = min(float(st.get("lot_discount_max", 0.5)), float(st.get("lot_discount", 0.15)) * roll)
        price = float(self.s["prices"][port][g])
        unit = round(price * (1 - off), 2)
        p["lot"] = {"port": port, "good": g, "qty": qty, "unit": unit, "price": round(price, 2),
                    "off": round(off, 4), "turn": self.s["turn"]}
        p["log"].append(tx("l.band_lot", port=PORTS[port]["name"], qty=qty, good=GOODS[g]["name"].lower(),
                           off=int(round(off * 100))))
        self._ev("market", "private_lot", "{}: Favoured in {}, offered {} {} at {} ({} below market)".format(
            p["name"], PORTS[port]["name"], qty, GOODS[g]["name"], money(unit), pct(off)), p, lot=dict(p["lot"]))

    def lot_view(self, p):
        lot = p.get("lot")
        return dict(lot) if lot and lot.get("port") == p["port"] and lot.get("qty", 0) > 0 else None

    def _act_buy_lot(self, p, a):
        lot = self.lot_view(p)
        if not lot:
            raise GameError(tx("e.no_lot"))
        g, unit = lot["good"], float(lot["unit"])
        try:
            want = int(a.get("qty") or lot["qty"])
        except (TypeError, ValueError):
            raise GameError(tx("e.whole_number"))
        room = self.capacity(p) - self.used(p)
        q = max(0, min(want, lot["qty"], room, int(p["cash"] // max(0.01, unit))))
        if q <= 0:
            raise GameError(tx("e.no_room", free=room) if room <= 0
                            else tx("e.cost", cost=money(int(math.ceil(unit))), cash=money(p["cash"])))
        cost = int(math.ceil(q * unit))
        p["cash"] -= cost
        held = p["cargo"].get(g, 0) + stored(p, g)
        basis = p.setdefault("basis", {})
        basis[g] = (basis.get(g, 0.0) * held + cost) / float(held + q)
        rot.add(p, g, q)
        p["cargo"][g] = p["cargo"].get(g, 0) + q
        p["lot"]["qty"] -= q
        if p["lot"]["qty"] <= 0:
            p.pop("lot", None)
        self._detail = {"good": g, "qty": q, "total": cost, "unit": unit, "lot": True}
        return tx("m.bought_lot", qty=q, good=GOODS[g]["name"], cost=money(cost))

    def _dumped(self, p, g, q, gain, mid):
        """Selling a lot far below the posted price (a lot so big it sinks the price, or dealers out of silver) spoils the market (rules.standing): standing lost,
        once per cargo per visit."""
        if not self.standing_on() or q <= 0:
            return
        st, port = R["standing"], p["port"]
        mid = float(mid)
        tab = p.setdefault("tab", {})
        done = tab.setdefault("dumped", [])
        if g in done or gain / float(q) >= float(st.get("dump_below", 0.6)) * mid:
            return
        done.append(g)
        self._standing(p, port, -float(st.get("dump", 0)), "dump")

    def _push(self, port, g, price):
        """Set a port's price after a trade and remember how far the trade moved it (as a log ratio),
        so most of that move fades next month (rules.market.own_fade) and the rest the month after."""
        before = max(1e-9, float(self.s["prices"][port][g]))
        price = max(1e-9, float(price))
        self.s["prices"][port][g] = price
        row = self.s.setdefault("pushes", {}).setdefault(port, {}).setdefault(g, [0.0, 0.0])
        row[0] += math.log(price / before)

    def _fade_pushes(self):
        """Month end: take back own_fade of each trade's fresh price move, and all that was left of last
        month's. What remains is what the usual pull back (reversion) then works on."""
        fade = float(R["market"].get("own_fade", 0.7))
        s = self.s
        keep = {}
        for port, goods in (s.get("pushes") or {}).items():
            for g, (fresh, carry) in goods.items():
                if port not in PORTS or g not in GOODS:
                    continue
                back = fade * fresh + carry
                if back:
                    s["prices"][port][g] = max(1.0, s["prices"][port][g] * math.exp(-back))
                left = (1 - fade) * fresh
                if abs(left) > 1e-6:
                    keep.setdefault(port, {})[g] = [0.0, left]
        s["pushes"] = keep

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
        rot.add(p, g, q)                          # new units come aboard fresh (rot.py)
        p["cargo"][g] = p["cargo"].get(g, 0) + q
        self._push(p["port"], g, end)
        self._trade_rep(p, cost, g, q, mid=self._detail["price"][0])
        return tx(self._trade_say(p, "m.bought"), qty=q, good=GOODS[g]["name"], cost=money(cost))

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
        self._purse_spend(p["port"], g, gain)
        unit = p.setdefault("basis", {}).get(g, gain / float(q))      # unknown cost counts as no profit
        self._tally_sale(p, g, gain, unit * q)
        self._book(p, "sales", gain)
        self._book(p, "cost", -unit * q)
        self._note_best_sale(p, g, q, gain, unit)
        p["cargo"][g] -= q
        if not p["cargo"][g]:
            del p["cargo"][g]
        self._push(p["port"], g, end)
        self._eat_boom(p, g, q)
        mid0 = self._detail["price"][0]
        self._trade_rep(p, gain, g, -q, profit=gain - unit * q, mid=mid0)
        self._dumped(p, g, q, gain, mid0)
        self._delivered(p, g, q)
        loss = gain < trade_text.LOSS_BELOW * unit * q
        return tx(self._trade_say(p, "m.sold_loss" if loss else "m.sold", "m.sold"), qty=q, good=GOODS[g]["name"], gain=money(gain))

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
        self._purse_spend(p["port"], g, gain)
        unit = p.setdefault("basis", {}).get(g, gain / float(q))
        self._tally_sale(p, g, gain, unit * q)
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
        self._push(p["port"], g, end)
        self._eat_boom(p, g, q)
        mid0 = self._detail["price"][0]
        self._trade_rep(p, gain, g, -q, profit=gain - unit * q, mid=mid0)
        self._dumped(p, g, q, gain, mid0)
        if q - from_wh > 0:
            self._delivered(p, g, q - from_wh)        # only what came off the ships counts as delivered
        return tx(self._trade_say(p, "m.sold_store"), qty=q, good=GOODS[g]["name"], gain=money(gain))

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
        """Open a warehouse in this port (op "open"), enlarge it (op "expand") or sell it back to the
        port for half of what it cost (op "sell", empty warehouses only). Home's is free."""
        port, f = p["port"], R["fleet"]
        name = PORTS[port]["name"]
        if port == home_of(p):
            raise GameError(tx("e.depot_home"))
        if not port_has(p, port, "warehouse"):
            raise GameError(tx("e.no_warehouse_port", port=name))
        deps = depots_of(p)
        if a.get("op") == "sell":
            d = deps.get(port)
            if d is None:
                raise GameError(tx("e.depot_not_open", port=name))
            if sum((d.get("goods") or {}).values()) > 0:
                raise GameError(tx("e.depot_not_empty", port=name))
            gain = depot_refund(d.get("level", 0))
            del deps[port]
            p["cash"] += gain
            self._book(p, "depot", gain)
            return tx("m.depot_sold", port=name, gain=money(gain))
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

    # ------------------------------------------- port shares and the great house (late game) --
    # Shares: s["shares"][port] = {pid: count}, one pool per port shared by every house. A house's
    # own record of what it paid (p["share_paid"][port]) is what counts in its net worth, and what it
    # gets back if it sells. The Patron of a port is the biggest holder; on a tie the Patron keeps it.
    # The great house: p["estate"] is the stage reached (0 none, 1 Townhouse, 2 Mansion, 3 Palace),
    # p["estate_paid"] the silver spent on it.
    HOUSE_STAGES = 3

    def share_price(self, port, p=None):
        """A share's price here; for a house (p), scaled by how rich it is (wealth_mult)."""
        e = R["estates"]
        base = float(PORTS[port].get("tax_rate", 0.0) or 0.0) * 100.0 * float(e["share_price_per_pct"])
        price = max(e["share_price_min"], min(e["share_price_max"], round(base / 1000.0) * 1000))
        if p is not None:
            price *= self.wealth_mult(p)
        return int(round(price / 1000.0) * 1000)

    def wealth_mult(self, p):
        """Prices that grow with the house (Game 3 review, 19 Nov 2026): the square root of net worth over
        rules.estates.wealth_ref, at least 1 and at most wealth_max. Shares, the great house and the Mayor's
        fees are multiplied by it, so they stay a real choice for a rich house."""
        e = R.get("estates") or {}
        if not e.get("wealth_scale", True):
            return 1.0
        ref = max(1.0, float(e.get("wealth_ref", 1000000)))
        top = max(1.0, float(e.get("wealth_max", 10.0)))
        return round(max(1.0, min(top, math.sqrt(max(0.0, self.worth(p)) / ref))), 3)

    def house_cost(self, p, stage):
        e = R["estates"]
        return int(round(float(e["house_cost_{}".format(stage)]) * self.wealth_mult(p) / 1000.0) * 1000)

    # Captain's share allowance (19 Nov 2026, Anthony's playtest: buying out a port was too easy).
    # A house no longer buys shares with silver. It earns them: one free share for each rank climbed
    # above Clerk (shares_per_rank), and later from special awards (award_shares). It holds at most
    # shares_per_house in all, and places each one in any port it is in: all in one port, or spread
    # around. p["share_earned"] is the count earned (capped); the shares not yet placed are
    # earned - held. Taking one back from a port frees it to place again. rules.estates.shares_buy
    # turns the old silver sale back on (still within the per-house limit).
    def share_cap(self):
        return max(0, int(R["estates"].get("shares_per_house", 10)))

    def _rank_shares(self, idx):
        """Shares earned for reaching rank number idx: shares_per_rank for each rank above Clerk."""
        ids = [r["id"] for r in CFG["ranks"]]
        frm = ids.index("clerk") if "clerk" in ids else 0
        return max(0, int(idx) - frm) * max(0, int(R["estates"].get("shares_per_rank", 1)))

    def shares_earned(self, p):
        return max(0, min(self.share_cap(), int(p.get("share_earned", 0) or 0)))

    def shares_total(self, p):
        return sum(self.shares_held(p, port) for port in PORTS)

    def shares_free(self, p):
        """Earned shares not yet placed in a port."""
        return max(0, self.shares_earned(p) - self.shares_total(p))

    def award_shares(self, p, n=1, why="award", **info):
        """Give a house n free shares to place (a promotion now; special awards later). Kept within
        shares_per_house. Returns how many were given."""
        if not R["estates"].get("shares_enabled", True):
            return 0
        have = self.shares_earned(p)
        n = max(0, min(int(n), self.share_cap() - have))
        if n <= 0:
            return 0
        p["share_earned"] = have + n
        p["log"].append(tx("l.share_earned", n=n, s="" if n == 1 else "s", free=self.shares_free(p),
                           earned=p["share_earned"], cap=self.share_cap()))
        self._ev("finance", "shares_earned", "{} earned {} port share(s) ({}): {} of {} earned".format(
            p["name"], n, why, p["share_earned"], self.share_cap()), p, n=n, why=why,
                 earned=p["share_earned"], **info)
        return n

    def _fit_shares(self, p):
        """Older saves: set the earned count from the rank, and hand back (at what was paid) any
        shares beyond it, from the port where the house holds the most first."""
        if "share_earned" not in p:
            ranks = CFG["ranks"]
            p["share_earned"] = min(self.share_cap(), self._rank_shares(ranks.index(self.commissioned_rank(p))))
        over = self.shares_total(p) - self.shares_earned(p)
        if over <= 0 or R["estates"].get("shares_buy", False):
            return
        paid = p.setdefault("share_paid", {})
        back_total, ports, count = 0, [], over
        while over > 0:
            port = max((k for k in PORTS if self.shares_held(p, k)), key=lambda k: self.shares_held(p, k))
            held = self._share_book(port)
            mine = int(held[p["id"]])
            back = int(round(float(paid.get(port, 0)) / mine))
            held[p["id"]] = mine - 1
            paid[port] = float(paid.get(port, 0)) - back
            if held[p["id"]] <= 0:
                held.pop(p["id"], None)
                paid.pop(port, None)
            p["cash"] += back
            back_total += back
            if port not in ports:
                ports.append(port)
            over -= 1
            self.patron_of(port)
        p["log"].append(tx("l.shares_returned", n=count, s="" if count == 1 else "s", cash=money(back_total),
                           ports=", ".join(PORTS[k]["name"] for k in ports), cap=self.shares_earned(p)))
        self._ev("finance", "shares_returned", "{}: shares above the {} earned handed back for {}".format(
            p["name"], self.shares_earned(p), money(back_total)), p, cash=back_total, ports=ports)

    def _share_book(self, port):
        book = self.s.setdefault("shares", {})
        held = book.get(port)
        if not isinstance(held, dict):
            held = book[port] = {}
        for k in [k for k, v in held.items() if int(v) <= 0 or k not in self.s["players"]]:
            del held[k]                         # kept in place: callers hold on to this dict
        return held

    def shares_held(self, p, port):
        return int(self._share_book(port).get(p["id"], 0))

    def share_cut(self, p, port):
        e = R["estates"]
        if not e.get("shares_enabled", True):
            return 0.0
        return min(1.0, self.shares_held(p, port) * float(e["share_cut"]))

    def patron_of(self, port):
        """The id of the port's Patron (its biggest shareholder), or None."""
        held = self._share_book(port)
        pats = self.s.setdefault("patrons", {})
        cur = pats.get(port)
        if not held:
            pats.pop(port, None)
            return None
        top = max(held.values())
        if cur in held and held[cur] == top:
            return cur
        new = next((k for k in self.s["order"] if held.get(k) == top), max(held, key=held.get))
        pats[port] = new
        return new

    def _act_shares(self, p, a):
        """Buy (op "buy") or sell back (op "sell") shares in the port the house is in."""
        e, port = R["estates"], p["port"]
        name = PORTS[port]["name"]
        if not e.get("shares_enabled", True):
            raise GameError(tx("e.shares_off"))
        held = self._share_book(port)
        mine = int(held.get(p["id"], 0))
        try:
            n = max(1, int(a.get("n", 1)))
        except (TypeError, ValueError):
            n = 1
        was_patron = self.patron_of(port)
        paid = p.setdefault("share_paid", {})
        if a.get("op") == "sell":
            if not e.get("share_sell_back", True):
                raise GameError(tx("e.shares_no_sell"))
            n = min(n, mine)
            if n <= 0:
                raise GameError(tx("e.shares_none", port=name))
            back = int(round(float(paid.get(port, 0)) * n / mine))
            held[p["id"]] = mine - n
            paid[port] = float(paid.get(port, 0)) - back
            if held[p["id"]] <= 0:
                held.pop(p["id"], None)
                paid.pop(port, None)
            p["cash"] += back
            msg = (tx("m.shares_sold", n=n, s="" if n == 1 else "s", port=name, gain=money(back)) if back else
                   tx("m.shares_taken_back", n=n, s="" if n == 1 else "s", port=name, free=self.shares_free(p)))
            ev = "sold"
        else:
            left = int(e["shares_per_port"]) - sum(held.values())
            if left <= 0:
                raise GameError(tx("e.shares_gone", port=name))
            free = self.shares_free(p)
            buying = bool(e.get("shares_buy", False))
            room = self.share_cap() - self.shares_total(p)
            if room <= 0:
                raise GameError(tx("e.shares_cap", cap=self.share_cap()))
            if free <= 0 and not buying:
                raise GameError(tx("e.shares_unearned", earned=self.shares_earned(p), cap=self.share_cap()))
            n = min(n, left, room if buying else free)
            # Earned shares go first and cost nothing; the rest (shares_buy only) at the port's price.
            gift = min(n, free)
            price = self.share_price(port, p)
            cost = price * (n - gift)
            if cost > p["cash"]:
                raise GameError(tx("e.cost", cost=money(cost), cash=money(p["cash"])))
            p["cash"] -= cost
            held[p["id"]] = mine + n
            if cost:
                paid[port] = float(paid.get(port, 0)) + cost
            if cost:
                msg = tx("m.shares_bought", n=n, s="" if n == 1 else "s", port=name, cost=money(cost),
                         held=held[p["id"]], cut=pct(self.share_cut(p, port)))
            else:
                msg = tx("m.shares_placed", n=n, s="" if n == 1 else "s", port=name, held=held[p["id"]],
                         cut=pct(self.share_cut(p, port)), free=self.shares_free(p))
            ev = "placed" if not cost else "bought"
        self._ev("finance", "shares_" + ev, "{} {} {} share(s) in {} ({} held)".format(
            p["name"], ev, n, name, held.get(p["id"], 0)), p, port=port, n=n, held=held.get(p["id"], 0))
        now = self.patron_of(port)
        if now != was_patron and now:
            who = self.s["players"][now]
            self.s["news"].insert(0, "{}: {}".format(date_label(self.s["turn"]),
                                                      tx("n.patron", firm=who["firm"], port=name)))
            self._stamp_news()
            self._ev("news", "patron", "{} is now Patron of {}".format(who["firm"], name), who, port=port)
            if now == p["id"]:
                msg += " " + tx("m.patron_you", port=name)
        return msg

    def shares_view(self, p):
        e, port = R["estates"], p["port"]
        if not e.get("shares_enabled", True):
            return None
        held = self._share_book(port)
        pat = self.patron_of(port)
        mine = {k: int(v) for k, v in self._mine_shares(p).items()}
        return {"port": port, "total": int(e["shares_per_port"]), "left": int(e["shares_per_port"]) - sum(held.values()),
                "here": int(held.get(p["id"], 0)), "price": self.share_price(port, p), "cut": float(e["share_cut"]),
                "wealth_mult": self.wealth_mult(p),
                "my_cut": round(self.share_cut(p, port), 4), "base_rate": round(self.tax_rate(port), 4),
                "my_rate": round(self.tax_rate_for(p, port), 4), "home": port == home_of(p),
                "sell_back": bool(e.get("share_sell_back", True)),
                "back": int(round(float((p.get("share_paid") or {}).get(port, 0)) / max(1, held.get(p["id"], 0)))),
                "patron": self.s["players"][pat]["firm"] if pat else None, "patron_me": pat == p["id"],
                "holders": [{"firm": self.s["players"][k]["firm"], "n": v, "me": k == p["id"]}
                            for k, v in sorted(held.items(), key=lambda kv: -kv[1])],
                "mine": mine, "patron_of": [k for k in PORTS if self.s.get("patrons", {}).get(k) == p["id"]],
                "value": int(sum(float(v) for v in (p.get("share_paid") or {}).values())),
                "cap": self.share_cap(), "earned": self.shares_earned(p), "free": self.shares_free(p),
                "placed": self.shares_total(p), "buy": bool(e.get("shares_buy", False))}

    def _mine_shares(self, p):
        return {port: n for port in PORTS for n in [self.shares_held(p, port)] if n}

    def house_stage(self, p):
        return max(0, min(self.HOUSE_STAGES, int(p.get("estate", 0) or 0)))

    def house_rob_cut(self, p):
        st = self.house_stage(p)
        return float(R["estates"].get("house_rob_{}".format(st), 0.0)) if st else 0.0

    def _estate_costs(self, p):
        """What was paid for each stage built, [stage 1, stage 2, ...]. Saves from before the sell-back
        (19 Nov 2026) only kept the total: it is split across the stages by their listed prices."""
        st = self.house_stage(p)
        costs = p.get("estate_costs")
        if isinstance(costs, list) and len(costs) == st:
            return [float(c) for c in costs]
        paid = float(p.get("estate_paid", 0) or 0)
        base = [float(R["estates"].get("house_cost_{}".format(i), 0) or 0) for i in range(1, st + 1)]
        tot = sum(base)
        costs = [paid * b / tot if tot else paid / st for b in base] if st else []
        p["estate_costs"] = costs
        return costs

    def _estate_reps(self, p):
        """Home standing each stage actually added (it stops at 100). Older saves: the listed gains."""
        st = self.house_stage(p)
        reps = p.get("estate_rep")
        if isinstance(reps, list) and len(reps) == st:
            return [float(r) for r in reps]
        reps = [float(R["estates"].get("house_rep_{}".format(i), 0) or 0) for i in range(1, st + 1)]
        p["estate_rep"] = reps
        return reps

    def house_sale_price(self, p):
        """What the top stage of the great house sells back for: rules.estates.house_sell_back of what
        was paid for it (half, by default). 0 with no house."""
        costs = self._estate_costs(p)
        if not costs:
            return 0
        share = max(0.0, min(1.0, float(R["estates"].get("house_sell_back", 0.5))))
        return int(round(costs[-1] * share))

    def _sell_estate(self, p):
        """Sell the top stage of the great house back (Anthony, 19 Nov 2026): the house steps down one
        stage (Palace to Mansion, and so on), gets house_sell_back of what that stage cost, and loses the
        home standing the stage gave and its cut in robbery ashore. December's upkeep falls with it."""
        e = R["estates"]
        if not e.get("house_sell", True):
            raise GameError(tx("e.estate_no_sell"))
        st = self.house_stage(p)
        if st <= 0:
            raise GameError(tx("e.estate_none"))
        costs, reps = self._estate_costs(p), self._estate_reps(p)
        back = self.house_sale_price(p)
        title = tx("estate.stage.{}".format(st))
        paid = costs.pop()
        lost = reps.pop()
        p["estate"] = st - 1
        p["estate_costs"], p["estate_rep"] = costs, reps
        p["estate_paid"] = float(sum(costs)) if costs else 0.0
        p["cash"] += back
        home = home_of(p)
        before = float(p["rep"].get(home, 50.0))
        p["rep"][home] = max(0.0, before - lost)
        gone = before - p["rep"][home]
        gr = p.setdefault("gift_rep", {})
        gr[home] = max(0.0, float(gr.get(home, 0.0)) - gone)
        if not gr[home]:
            gr.pop(home, None)
        now = tx("estate.stage.{}".format(st - 1)) if st > 1 else ""
        self._ev("finance", "estate_sold", "{} sold the {} at {} back for {} (paid {})".format(
            p["name"], title, PORTS[home]["name"], money(back), money(paid)),
                 p, stage=st, left=st - 1, cash=back, paid=int(round(paid)), rep=-round(gone, 2))
        p["log"].append(tx("l.estate_sold", stage=title, home=PORTS[home]["name"], cash=money(back)))
        msg = tx("m.estate_sold", stage=title, home=PORTS[home]["name"], cash=money(back), rep=int(round(gone)))
        return msg + " " + (tx("m.estate_left", stage=now) if now else tx("m.estate_left_none"))

    def _act_estate(self, p, a):
        """Build the next stage of the great house (or, with op "sell", sell the top one back).
        Home port only."""
        e = R["estates"]
        if not e.get("house_enabled", True):
            raise GameError(tx("e.estate_off"))
        self._home_only(p, tx("estate.what"))
        if a.get("op") == "sell":
            return self._sell_estate(p)
        st = self.house_stage(p)
        if st >= self.HOUSE_STAGES:
            raise GameError(tx("e.estate_done"))
        nxt = st + 1
        cost = self.house_cost(p, nxt)
        if cost > p["cash"]:
            raise GameError(tx("e.cost", cost=money(cost), cash=money(p["cash"])))
        costs, reps = self._estate_costs(p), self._estate_reps(p)
        p["cash"] -= cost
        p["estate"], p["estate_paid"] = nxt, float(p.get("estate_paid", 0) or 0) + cost
        home = home_of(p)
        gain = float(e["house_rep_{}".format(nxt)])
        before = float(p["rep"].get(home, 50.0))
        p["rep"][home] = min(100.0, before + gain)
        got = p["rep"][home] - before
        gr = p.setdefault("gift_rep", {})       # bought standing: never more borrowing (as with gifts)
        gr[home] = float(gr.get(home, 0.0)) + got
        p["estate_costs"], p["estate_rep"] = costs + [float(cost)], reps + [round(got, 4)]
        title = tx("estate.stage.{}".format(nxt))
        self._ev("finance", "estate", "{} built the {} at {} for {}".format(p["name"], title, PORTS[home]["name"], money(cost)),
                 p, stage=nxt, cost=cost, rep=round(got, 2))
        p["log"].append(tx("l.estate", stage=title, home=PORTS[home]["name"]))
        return tx("m.estate", stage=title, cost=money(cost), rep=int(round(got)), home=PORTS[home]["name"])

    def estate_view(self, p):
        e = R["estates"]
        if not e.get("house_enabled", True):
            return None
        st = self.house_stage(p)
        nxt = st + 1 if st < self.HOUSE_STAGES else None
        return {"stage": st, "title": tx("estate.stage.{}".format(st)) if st else "",
                "paid": int(p.get("estate_paid", 0) or 0), "rob_cut": self.house_rob_cut(p),
                "sell": bool(e.get("house_sell", True)) and st > 0,
                "sell_price": self.house_sale_price(p) if st else 0,
                "sell_rep": round(self._estate_reps(p)[-1], 1) if st else 0,
                "sell_share": max(0.0, min(1.0, float(e.get("house_sell_back", 0.5)))),
                "upkeep": int(round(float(p.get("estate_paid", 0) or 0) * float(e.get("house_upkeep", 0) or 0))),
                "upkeep_after": int(round(sum(self._estate_costs(p)[:-1]) * float(e.get("house_upkeep", 0) or 0))) if st else 0,
                "wealth_mult": self.wealth_mult(p),
                "stages": [{"stage": i, "title": tx("estate.stage.{}".format(i)), "cost": self.house_cost(p, i),
                            "rep": float(e["house_rep_{}".format(i)]), "rob": float(e["house_rob_{}".format(i)])}
                           for i in range(1, self.HOUSE_STAGES + 1)],
                "next": nxt}

    # --------------------------------------------- the Mayor's commissions (late game) --
    # p["offers"] = {"year": offer|None, "short": offer|None}; p["contracts"] = [taken, ...] with at most
    # one of each slot. An offer or contract: {"id", "slot", "kind" (delivery/supply/standing), "port",
    # "good", "qty", "got", "target", "due" (the month it must be done by), "fee", "rep", "until"}.
    # Offers come at the end of each month (and at the start), from the game's dice, so a replay of the
    # month makes the same ones. Deliveries count cargo sold off the ships in that port after taking it.
    def _contract_rules(self):
        c = R.get("contracts") or {}
        return c if c.get("enabled", True) else None

    def _new_offer(self, p, slot):
        c, turn = R["contracts"], self.s["turn"]
        # Her own dice, drawn from the month's seed: the same offers on a replay, and the month's other
        # dice (storms, pirates, prices) unchanged by them.
        rng = random.Random("{}:{}:{}:{}".format(self.s.get("seed"), p["id"], turn, slot))
        home = home_of(p)
        year = slot == "year"
        # "due" is the last month the work can be done in: a December for a yearly goal.
        due = (turn // 12) * 12 + 11 if year else turn + rng.randint(int(c["short_min"]), max(int(c["short_min"]), int(c["short_max"])))
        if year and due - turn < 3:
            due += 12                                   # late in the year: the goal runs to the next one's end
        hold = max(1, self.capacity(p))
        legal = [g for g in GOODS if not GOODS[g].get("contraband")] or list(GOODS)
        others = [k for k in PORTS if k != home]
        if not others:
            return None
        kinds = ["delivery", "supply", "standing"]
        kind = rng.choice(kinds)
        offer = {"id": int(self.s.setdefault("contract_seq", 0)) + 1, "slot": slot, "kind": kind,
                 "turn": turn, "until": turn + int(c["offer_months"]), "got": 0}
        self.s["contract_seq"] = offer["id"]
        if kind == "supply":
            short = [(k, g) for k in others for g in legal
                     if self.s["prices"][k].get(g, 0) >= float(c["shortage_at"]) * normal_price(g)]
            if short:
                port, good = rng.choice(sorted(short))
                qty = max(int(c["min_qty"]), int(round(hold * float(c["hold_share_short"]) * 0.7 / 10.0)) * 10)
                if not year:
                    due = turn + int(c["supply_months"]) - 1
                fee = float(c["fee_share_year" if year else "fee_share"]) * float(c["supply_mult"]) * qty * normal_price(good)
                offer.update(port=port, good=good, qty=qty, due=due, fee=int(round(fee, -2)))
            else:
                kind = offer["kind"] = "delivery"
        if kind == "delivery":
            port, good = rng.choice(others), rng.choice(legal)
            share = float(c["hold_share_year" if year else "hold_share_short"])
            qty = max(int(c["min_qty"]), int(round(hold * share / 10.0)) * 10)
            fee = float(c["fee_share_year" if year else "fee_share"]) * qty * normal_price(good)
            offer.update(port=port, good=good, qty=qty, due=due, fee=int(round(fee, -2)))
        elif kind == "standing":
            room = [k for k in others if p["rep"].get(k, 50.0) < 85]
            if not room:
                return None
            port = rng.choice(room)
            pts = int(c["standing_year" if year else "standing_short"])
            target = int(min(100, round(p["rep"].get(port, 50.0)) + pts))
            fee = float(c["standing_fee"]) * max(50000.0, self.worth(p)) * pts * (1.5 if year else 1.0)
            offer.update(port=port, target=target, due=due, fee=int(round(fee, -2)))
        offer["rep"] = float(c["rep_year" if year else "rep_short"])
        if c.get("fee_wealth", True) and kind != "standing":    # standing goals already pay by net worth
            offer["fee"] = int(round(float(offer.get("fee", 0)) * self.wealth_mult(p), -2))
        offer["fee"] = max(100, int(offer.get("fee", 0)))
        return offer

    def _contracts_month(self, p):
        """Month end: missed contracts lapse, met ones pay, and the Mayor makes her offers."""
        c = self._contract_rules()
        if c is None:
            return
        turn = self.s["turn"]
        self._check_contracts(p)
        keep = []
        for k in p.get("contracts") or []:
            if turn > int(k["due"]):
                p["log"].append(tx("l.contract_missed", what=self._contract_text(k)))
                self._ev("players", "contract_missed", "{} missed the Mayor's {} ({})".format(
                    p["name"], k["slot"], self._contract_text(k)), p, contract=k)
                p.setdefault("contract_tally", {}).setdefault("missed", 0)
                p["contract_tally"]["missed"] += 1
                if self.standing_on():
                    self._standing(p, home_of(p), -float(R["standing"].get("contract_missed", 0)), "contract_missed")
            else:
                keep.append(k)
        p["contracts"] = keep
        offers = p.setdefault("offers", {})
        taken = {k["slot"] for k in keep}
        for slot in ("year", "short"):
            o = offers.get(slot)
            if o and (turn >= int(o.get("until", 0)) or turn >= int(o.get("due", 0))):
                o = offers[slot] = None
            done_year = slot == "year" and int(p.get("year_goal", -1)) == turn // 12
            if slot not in taken and not o and not done_year:
                offers[slot] = o = self._new_offer(p, slot)
                if o:
                    self._ev("players", "contract_offered", "The Mayor of {} offered {} a {} ({}), fee {}".format(
                        PORTS[home_of(p)]["name"], p["name"], slot, self._contract_text(o), money(o["fee"])), p, contract=o)
        # Game 4 review: her offers were made in silence on a card under Services, and never seen. At home she
        # now says so in the Captain's Log, once for each offer.
        if p["port"] == home_of(p):
            new = [o for o in offers.values() if o and not o.get("told")]
            for o in new:
                o["told"] = True
            if new:
                p["log"].append(tx("l.contract_offer", n=len(new), s="" if len(new) == 1 else "s",
                                   home=PORTS[home_of(p)]["name"]))

    def _contract_text(self, k):
        port = PORTS[k["port"]]["name"] if k.get("port") in PORTS else ""
        if k["kind"] == "standing":
            return tx("contract.standing", port=port, target=k["target"])
        return tx("contract." + k["kind"], qty="{:,}".format(k["qty"]), good=GOODS[k["good"]]["name"] if k.get("good") in GOODS else "",
                  port=port)

    def _delivered(self, p, good, qty):
        for k in p.get("contracts") or []:
            if k["kind"] in ("delivery", "supply") and k["port"] == p["port"] and k["good"] == good:
                k["got"] = min(int(k["qty"]), int(k.get("got", 0)) + int(qty))

    def _check_contracts(self, p):
        """Pay out every contract the house has met (wherever it is)."""
        left = []
        for k in p.get("contracts") or []:
            met = (int(k.get("got", 0)) >= int(k["qty"])) if k["kind"] in ("delivery", "supply") \
                else float(p["rep"].get(k["port"], 0.0)) >= float(k["target"])
            if not met:
                left.append(k)
                continue
            home = home_of(p)
            p["cash"] += int(k["fee"])
            self._book(p, "contracts", int(k["fee"]))
            self._gain_rep(p, home, float(k.get("rep", 0.0)))
            p["log"].append(tx("l.contract_done", what=self._contract_text(k), fee=money(k["fee"]),
                               rep=int(round(float(k.get("rep", 0.0)))), home=PORTS[home]["name"]))
            p.setdefault("contract_tally", {}).setdefault("done", 0)
            p["contract_tally"]["done"] += 1
            p["contract_tally"]["silver"] = int(p["contract_tally"].get("silver", 0)) + int(k["fee"])
            self._ev("finance", "contract_done", "{} completed the Mayor's {} ({}) for {}".format(
                p["name"], k["slot"], self._contract_text(k), money(k["fee"])), p, contract=k)
        if p.get("contracts") is not None:
            p["contracts"] = left

    def _act_contract(self, p, a):
        """Take (op "accept") or turn down (op "decline") the home Mayor's offer for a slot."""
        if self._contract_rules() is None:
            raise GameError(tx("e.contracts_off"))
        self._home_only(p, tx("contract.what"))
        slot = a.get("slot")
        offers = p.setdefault("offers", {})
        o = offers.get(slot) if slot in ("year", "short") else None
        if not o:
            raise GameError(tx("e.contract_none"))
        offers[slot] = None
        if a.get("op") == "decline":
            self._ev("players", "contract_declined", "{} turned down the Mayor's {} ({})".format(
                p["name"], slot, self._contract_text(o)), p, contract=o)
            return tx("m.contract_declined")
        if any(k["slot"] == slot for k in p.get("contracts") or []):
            raise GameError(tx("e.contract_busy"))
        o["taken"] = self.s["turn"]
        p.setdefault("contracts", []).append(o)
        if slot == "year":
            p["year_goal"] = self.s["turn"] // 12
        self._ev("players", "contract_taken", "{} took the Mayor's {} ({}), due {}".format(
            p["name"], slot, self._contract_text(o), date_label(o["due"])), p, contract=o)
        return tx("m.contract_taken", what=self._contract_text(o), due=date_label(o["due"]), fee=money(o["fee"]))

    def contracts_view(self, p):
        if self._contract_rules() is None:
            return None
        def one(k):
            return dict(k, text=self._contract_text(k), due_date=date_label(int(k["due"])),
                        months=max(0, int(k["due"]) - self.s["turn"] + 1),
                        now=int(round(p["rep"].get(k["port"], 0))) if k["kind"] == "standing" else int(k.get("got", 0)))
        offers = p.get("offers") or {}
        return {"active": [one(k) for k in p.get("contracts") or []],
                "offers": {slot: one(o) for slot, o in offers.items() if o},
                "home": p["port"] == home_of(p), "tally": p.get("contract_tally") or {}}

    def _home_only(self, p, what):
        if p["port"] != home_of(p):
            raise GameError(tx("e.home_only", what=what, home=PORTS[home_of(p)]["name"]))

    def _act_bank(self, p, a):
        if not port_has(p, p["port"], "bank"):
            raise GameError(tx("e.no_bank_here", port=PORTS[p["port"]]["name"], home=PORTS[home_of(p)]["name"]))
        q = self._qty(a, "amount", MONEY_CAP)
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
        q = self._qty(a, "amount", MONEY_CAP)
        if a.get("op") == "borrow":
            room = int(self.loan_limit(p) - p["debt"])
            if room <= 0:
                raise GameError(tx("e.no_more_loans"))
            q = min(q, room)
            p["debt"] += q
            p["cash"] += q
            p["borrowed_turn"] = self.s["turn"]
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
        owed0 = float(p["debt"])
        p["debt"] = max(0.0, p["debt"] - q)
        p["cash"] -= q
        if p["debt"] < 1:
            p["debt"] = 0.0
            # Debt cleared (rules.standing): the home port thinks better of a house that pays in full. Not for
            # a loan taken out this same month (no borrowing and paying back for standing).
            st = R.get("standing") or {}
            if self.standing_on() and owed0 >= float(st.get("debt_cleared_min", 0)) \
                    and int(p.get("borrowed_turn", -1)) < self.s["turn"]:
                self._standing(p, home_of(p), float(st.get("debt_cleared", 0)), "debt_cleared")
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
        rot.add(p, g, q)                          # stored cargo comes out fresh: warehouses do not age it
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
                            else tx("e.flagship_have") if role == FLAG
                            else tx("e.class_limit." + role, n=limit))
        need = role_unlock(role)
        if role != "trader" and self.class_count(p, "trader") < need:
            raise GameError(tx("e.class_locked." + role, n=need, have=self.class_count(p, "trader")))
        if role == FLAG and any(role_of(sh["type"]) == FLAG for sh in p["ships"]):
            raise GameError(tx("e.flagship_have"))
        price = int(round(SHIPS[kind]["price"] * self.yard_mult(p)))   # a Hostile or Cool yard charges more
        if price > p["cash"]:
            raise GameError(tx("e.ship_cost", ship=SHIPS[kind]["name"], price=money(price)))
        name = None
        if role == FLAG:
            # Her house names her (any name not already afloat); none given: one from the name list.
            name = " ".join(str(a.get("name") or "").split())[:28] or None
            if name and any(sh["name"].lower() == name.lower() for q in self.s["players"].values() for sh in q["ships"]):
                raise GameError(tx("e.ship_name_taken", name=name))
        p["cash"] -= price
        self._tally(p, "yard", price)
        sh = self._new_ship(kind, name=name)
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
        if self.capacity(p) - ship_hold(sh) < self.used(p):
            raise GameError(tx("e.unload_first"))
        value = int(self.ship_value(sh))
        p["ships"].remove(sh)
        p["cash"] += value
        self._detail = {"ship": sh["type"], "name": sh["name"], "value": value}
        return tx("m.ship_sold", name=sh["name"], value=money(value))

    # ---- laying ships up at home (Game 4 review, 20 Nov 2026) ------------------------------------------
    # A ship laid up stays in the home harbour at rules.fleet.laid_up_wage of her wage. She doesn't sail,
    # carry, fight or count in the fleet's hold, but she still counts against her class's limit and in
    # net worth. Laid up and called back at home only, any month.
    def _act_lay_up(self, p, a):
        self._home_only(p, tx("w.lay_up"))
        sh = self._ship(p, a)
        if len(p["ships"]) <= 1:
            raise GameError(tx("e.last_ship_lay"))
        if R["fleet"].get("keep_trader", True) and role_of(sh["type"]) == "trader" \
                and sum(1 for x in p["ships"] if role_of(x["type"]) == "trader") <= 1:
            raise GameError(tx("e.last_trader_lay"))
        if self.capacity(p) - ship_hold(sh) < self.used(p):
            raise GameError(tx("e.unload_first"))
        p["ships"].remove(sh)
        sh["laid"] = self.s["turn"]
        p.setdefault("laid_up", []).append(sh)
        self._detail = {"ship": sh["type"], "name": sh["name"], "note": "laid up at home"}
        return tx("m.laid_up", name=sh["name"], home=PORTS[home_of(p)]["name"])

    def _act_recall(self, p, a):
        self._home_only(p, tx("w.lay_up"))
        laid = p.get("laid_up") or []
        try:
            i = int(a.get("index"))
            if i < 0:
                raise IndexError
            sh = laid[i]
        except (TypeError, ValueError, IndexError):
            raise GameError(tx("e.no_such_ship"))
        laid.remove(sh)
        sh.pop("laid", None)
        p["ships"].append(sh)
        self._detail = {"ship": sh["type"], "name": sh["name"], "note": "called back to the fleet"}
        return tx("m.recalled", name=sh["name"])

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
        hold = max(0, spec["hold"] - guns * gun_hold())
        return {"kind": kind, "guns": guns, "value": value, "hold": hold, "name": p["ships"][0]["name"],
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
        new.update({k: old[k] for k in ("clean_name", "nsfw_name") if old.get(k)})   # she keeps both names
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
        self._weapon_room(p, sh, guns=1)
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
        self._weapon_room(p, sh, cannons=1)
        if price > p["cash"]:
            raise GameError(tx("e.cannon_cost", price=money(price)))
        p["cash"] -= price
        self._tally(p, "yard", price)
        sh["cannons"] = sh.get("cannons", 0) + 1
        self._detail = {"name": sh["name"], "price": price}
        return tx("m.cannon_mounted", name=sh["name"])

    def _weapon_room(self, p, sh, guns=0, cannons=0):
        """A gun or cannon takes hold space: refuse it while the cargo aboard needs that space."""
        lost = ship_hold(sh) - ship_hold(sh, guns, cannons)
        free = self.capacity(p) - self.used(p)
        if lost > free:
            raise GameError(tx("e.weapon_hold", name=sh["name"], n=lost, free=max(0, free)))

    def fill_plan(self, p, index="all"):
        """Cannons a Fill would mount (19 Nov 2026): every free pair of mounts on one ship (index), or on
        every ship that takes cannons ("all": escorts first, then merchantmen), as far as silver goes."""
        price, cs = cannon_price(), cannon_slots()
        order = range(len(p["ships"])) if index == "all" else [index]
        if index == "all":
            rank = {"escort": 0, "trader": 1, "cargo": 2}
            order = sorted(order, key=lambda i: (rank.get(role_of(p["ships"][i]["type"]), 3), i))
        cash, plan, free = p["cash"], [], self.capacity(p) - self.used(p)
        for i in order:
            sh = p["ships"][i]
            if not SHIPS[sh["type"]].get("cannons"):
                continue
            room = self.mounts_free(sh) // cs
            n = min(room, int(cash // price)) if price > 0 else room
            while n > 0 and ship_hold(sh) - ship_hold(sh, cannons=n) > free:    # cargo aboard needs the space
                n -= 1
            if n > 0:
                plan.append((i, n))
                cash -= n * price
                free -= ship_hold(sh) - ship_hold(sh, cannons=n)
        return plan, sum(n for _i, n in plan) * price

    def _act_fill_cannons(self, p, a):
        """Fill free mounts with cannons on one ship (index) or the whole fleet (index "all") in one go."""
        idx = a.get("index")
        if idx != "all":
            sh = self._ship(p, a)
            idx = p["ships"].index(sh)
            if not SHIPS[sh["type"]].get("cannons"):
                raise GameError(tx("e.no_cannons", name=sh["name"], ship=SHIPS[sh["type"]]["name"]))
        plan, cost = self.fill_plan(p, idx)
        if not plan:
            if p["cash"] < cannon_price():
                raise GameError(tx("e.cannon_cost", price=money(cannon_price())))
            raise GameError(tx("e.no_cannon_fill"))
        for i, n in plan:
            p["ships"][i]["cannons"] = p["ships"][i].get("cannons", 0) + n
        p["cash"] -= cost
        self._tally(p, "yard", cost)
        n = sum(n for _i, n in plan)
        self._detail = {"cannons": n, "price": cost, "ships": [p["ships"][i]["name"] for i, _n in plan]}
        return tx("m.cannons_filled", n=n, cost=money(cost), ships=len(plan))

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
            need = self.repair_need(p, sh)
            rate = self.repair_rate(p, sh)
            points = int(min(need, (p["cash"] - spent) // rate))
            if points > 0:
                spent += int(math.ceil(points * rate))
                sh["hull"] += points
                fixed += points
            if sh.get("crippled") and sh["hull"] >= SHIPS[sh["type"]]["hull"]:
                sh.pop("crippled", None)
        if not fixed:
            if any(sh["hull"] < SHIPS[sh["type"]]["hull"] for sh in ships) and not any(self.repair_need(p, sh) for sh in ships):
                raise GameError(tx("e.repair_yard", pct=int(round(100 * float(storm.rules()["patch_max"])))))             # only a patch is possible here; she needs a shipyard
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
        jail.before_resolve(self, players)         # unanswered pleas are paid; a jailed House stays put
        self._drift_tax_rates()          # the new month's rates, quoted to every ship that arrives
        origins = {p["id"]: [p["port"], bool(p["ready"] and p["dest"])] for p in players}
        s["sea"] = {"cause": cause, "label": label, "actual": actual, "news": news, "origins": origins,
                    "order": [p["id"] for p in players], "present": None if present is None else sorted(present)}
        for p in players:
            # The Mayor may hold a house caught slipping out (jail): it stays at anchor.
            if p["ready"] and p["dest"] and self._depart(p, news) != "held":
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
            was_in = jail.jailed(p)               # inside at the start of the month: only the jail's own spoilage hits
            inside = jail.month(self, p, news)    # the crew drinks, the hold spoils; release when served
            rot.month(self, p, news, skip=was_in or bool(inside))   # perishables age a month; old ones rot (rot.py)
            bank0, debt0 = p["bank"], p["debt"]
            if p["bank"] > 0:
                p["bank"] *= 1 + b["bank_rate"]
            if p["debt"] > 0:
                # The debt cap (19 Nov 2026): interest stops adding once the debt reaches debt_cap_mult x the
                # collectors' line, so a house that falls behind in a long game can't owe trillions.
                p["debt"] = self._debt_after_interest(p)
                # Collectors: a grace period after debt first passes the line, then a call every few months.
                # "debt_over" counts the months in a row spent over the line (old saves start at 0).
                if p["debt"] > self.collectors_line(p):
                    p["debt_over"] = int(p.get("debt_over", 0)) + 1
                    grace = max(0, int(b.get("debt_grace_months", 0)))
                    every = max(1, int(b.get("debt_call_every", 1)))
                    if p["debt_over"] > grace and (p["debt_over"] - grace - 1) % every == 0:
                        if self.standing_on():
                            st = R["standing"]
                            for k in PORTS:
                                self._standing(p, k, -float(st["collect_home" if k == home_of(p) else "collect_away"]),
                                               "collectors")
                        else:
                            self._gain_rep(p, home_of(p), -b["debt_rep_penalty"])
                        p["log"].append(tx("l.collectors", home=PORTS[home_of(p)]["name"]))
                        jail.on_collectors(self, p, news)     # past the debt cap: maybe debtors' prison
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
            if self.standing_on():
                self._drift_standing(p)
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
            if p["port"] == home_of(p):
                mug_odds *= 1.0 - self.house_rob_cut(p)        # the great house keeps the streets quieter
            if not inside and p["cash"] > b["mug_threshold"] and self._chance(mug_odds, "robbery", "{}: robbed ashore (carrying over {}, standing {:.0f})".format(
                    p["name"], money(b["mug_threshold"]), mug_st), p):
                lost = int(p["cash"] * rng.uniform(b["mug_min"], b["mug_max"]))
                p["cash"] -= lost
                self._book(p, "robbed", -lost)
                p["log"].append(tx("l.robbed", lost=money(lost)))
                self._ev("finance", "robbed", "{} was robbed of {}".format(p["name"], money(lost)), p, lost=lost)
            self._rob_warehouses(p, news, b, rng)
            self._pay_running_costs(p)
            self._bankruptcy_month(p, news)

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
            self._contracts_month(p)
        for n in news:
            self._ev("news", "news", "News: " + n, turn=s["turn"] - 1)
        s["news"] = ["{}: {}".format(label, n) for n in news] + s["news"]
        s["news"] = s["news"][:40]
        self._stamp_news()
        if s["turn"] >= s["years"] * 12 and not s.get("free_play"):
            self._finish()
        jail.after_finish(self, players)          # a House still inside is marked as sailed
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
        s["purse"] = {}                                  # the dealers' purses fill again for the new month
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
            if not ev.get("stack_booms", False):
                s["prices"][port][good] = self._clamp(port, good, s["prices"][port][good])
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
        self._fade_pushes()
        runs = self._runs_month()
        for port in PORTS:
            for g, spec in GOODS.items():
                base = spec["base"] * PORTS[port]["mods"].get(g, 1.0)
                price = s["prices"][port][g]
                price += reversion_of(g) * (self._target(port, g) - price)
                price *= math.exp(rng.gauss(0, vol_of(g) * m["vol_mult"]))
                drift = runs.get((port, g))
                if drift:
                    price *= math.exp(drift)              # a run on a wild cargo: up or down again this month
                w = self._windfall(port, g)
                if w:                                       # a crash or boom runs past the usual limits
                    price = max(1.0, price)
                    # A boom from a hot tip holds: the month's swing can lift it but never take it below
                    # the level that was foretold (rules.registrar.hot_hold). Selling into it uses it up
                    # (_eat_boom), so what it holds to shrinks with every big sale.
                    if w.get("foretold") and w.get("kind") == "boom" and hot_hold:
                        price = max(price, base * float(w.get("mult", 1.0)))
                    if not ev.get("stack_booms", False):
                        price = self._clamp(port, g, price)  # never past the boom's own size (Game 3 review)
                    s["prices"][port][g] = price
                else:
                    floor, ceiling = price_limits(g)
                    s["prices"][port][g] = max(floor * base, min(ceiling * base, price))
        moves = sorted(((s["prices"][port][g] / before[port][g] - 1, port, g) for port in PORTS for g in GOODS
                        if before[port].get(g)), key=lambda t: -abs(t[0]))[:6]
        self._ev("market", "prices", "Markets moved. Biggest changes: " + "; ".join(
            "{} in {} {:+.0%} ({:,.0f} -> {:,.0f})".format(GOODS[g]["name"], PORTS[port]["name"], ch, before[port][g],
                                                           s["prices"][port][g]) for ch, port, g in moves),
            movers=[{"port": port, "good": g, "change": round(ch, 4), "from": round(before[port][g], 2),
                     "to": round(s["prices"][port][g], 2)} for ch, port, g in moves])

    def _runs_month(self):
        """Runs on the wild cargoes (Game 4 review, 20 Nov 2026): {(port, good): this month's log-drift}.
        A port with no run going starts one runs_chance of the time: up or down (more often back toward
        the usual price when it is already far out), runs_min..runs_max months, each month moving the
        price runs_drift_min..max. Its own dice, so the month's other dice are unchanged. Kept secret:
        logged for the Admin journal only, never news or a marker on screen."""
        m, s = R["market"], self.s
        wild = [g for g in (m.get("wild_goods") or ()) if g in GOODS]
        book = s.setdefault("runs", {})
        out = {}
        if not wild:
            book.clear()
            return out
        lo_n, hi_n = sorted((max(1, int(m.get("runs_min", 2))), max(1, int(m.get("runs_max", 4)))))
        lo_d, hi_d = sorted((float(m.get("runs_drift_min", 0.15)), float(m.get("runs_drift_max", 0.35))))
        for port in PORTS:
            row = book.setdefault(port, {})
            for g in list(row):
                if g not in wild:
                    row.pop(g)
            for g in wild:
                own = random.Random("runs:{}:{}:{}:{}".format(s.get("game_id", ""), s["turn"], port, g))
                run = row.get(g)
                if run and int(run.get("left", 0)) > 0:
                    out[(port, g)] = float(run["drift"])
                    run["left"] = int(run["left"]) - 1
                    if run["left"] <= 0:
                        row.pop(g, None)
                    continue
                row.pop(g, None)
                if own.random() >= float(m.get("runs_chance", 0.15)):
                    continue
                usual = GOODS[g]["base"] * PORTS[port]["mods"].get(g, 1.0)
                where = s["prices"][port][g] / max(0.01, usual)
                up_odds = 0.3 if where > 2.0 else 0.7 if where < 0.5 else 0.5
                sign = 1.0 if own.random() < up_odds else -1.0
                months = own.randint(lo_n, hi_n)
                drift = round(sign * own.uniform(lo_d, hi_d), 4)
                out[(port, g)] = drift
                if months > 1:
                    row[g] = {"drift": drift, "left": months - 1, "start": s["turn"]}
                self._ev("market", "run", "A run on {} in {}: {} about {:.0%} a month for {} month(s) (secret)".format(
                    GOODS[g]["name"], PORTS[port]["name"], "up" if sign > 0 else "down", abs(math.exp(drift) - 1),
                    months), port=port, good=g, drift=drift, months=months)
        return out

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

                storm_p = w["storm_chance"][level] * min(risk, 1.4) * MULT["storms"]
                if self._chance(storm_p, "storm", "{}: caught in a {}".format(who, "typhoon" if level == 3 else "storm"), p):
                  if storm.on():
                    storm.hit(self, p, v, level, risk, news)
                    dest = v["dest"]
                  else:
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
                deter = self.flag_deter(p)
                if p["ships"] and self._chance(pi["chance"] * risk * MULT["pirates"] * allure * deter, "pirates",
                                               "{}: pirate attack{}{}".format(who, " (their appetite x{:.2f})".format(allure)
                                                                              if allure != 1.0 else "",
                                                                              " (the flagship deters x{:.2f})".format(deter)
                                                                              if deter != 1.0 else ""), p):
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
                    elif self._warned_off(p, origin):
                        log.append(tx("l.band_warned", port=PORTS[origin]["name"]))
                    else:
                        self._battle_open(p, n, "pirates", muster)
            elif v["stage"] == 2:
                v["stage"] = 3
                risk = v["risk"]
                pull = self.lord_pull(p) if R["battle"].get("match") else 1.0
                if p["ships"] and p["protect"] <= 0 and self._chance(ly["chance"] * risk * MULT["pirates"] * self.flag_deter(p) * pull, "pirate_lord",
                                                                      "{}: found by {}'s fleet (no protection){}".format(
                                                                          who, TOKENS["pirate"], " (a rich house x{:.2f})".format(pull)
                                                                          if pull != 1.0 else ""), p):
                    if self._warned_off(p, origin):
                        log.append(tx("l.band_warned", port=PORTS[origin]["name"]))
                    else:
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
                self._offer_lot(p, dest)
                self._ev("voyage", "arrived", "{} anchored in {}: {} ship{}, hull {}, hold {}/{}, silver {}".format(
                    who, PORTS[dest]["name"], len(p["ships"]), "" if len(p["ships"]) == 1 else "s",
                    "/".join(str(sh["hull"]) for sh in p["ships"]), self.used(p), self.capacity(p), money(p["cash"])),
                    p, port=dest, cargo=dict(p["cargo"]), cash=int(p["cash"]))
                risky = self.at_risk(dest)
                jail_seized = False
                held = sum(p["cargo"].get(g, 0) for g in risky)
                if held:
                    banned = dest in self.s["crackdown"]
                    chance = (cb["seize_banned"] - cb["seize_rep_relief"] * p["rep"][dest]) if banned else cb["seize_chance"]
                    if self._chance(chance * MULT["seizure"], "seizure", "{}: customs search in {} ({} units of contraband, {}, standing {})".format(
                            who, PORTS[dest]["name"], held, "banned here" if banned else "no ban", int(round(p["rep"][dest]))), p):
                        # The crew gets a share under the ballast first (rules.hide.customs): never found.
                        hid = self._crew_hide(p, {g: p["cargo"].get(g, 0) for g in risky}, "customs", "voyage")
                        taken = {g: p["cargo"][g] - hid.get(g, 0) for g in risky
                                 if p["cargo"].get(g, 0) - hid.get(g, 0) > 0}
                        found = sum(taken.values())
                        if found:
                            fine = int(min(p["cash"], found * cb["fine_per_unit"]))
                            self._book(p, "seized", -self._cost_of(p, taken))
                            self._book(p, "fines", -fine)
                            for g, q in taken.items():
                                p["cargo"][g] -= q
                                if p["cargo"][g] <= 0:
                                    del p["cargo"][g]
                            what = names_of(list(taken))
                            if jail.offer_plea(self, p, fine, "contraband", dest, "fines"):
                                self._book(p, "fines", fine)       # charged when the plea is answered
                            else:
                                p["cash"] -= fine
                            if self.standing_on():
                                self._standing(p, dest, -float(R["standing"]["seized"]), "seized", travel=True)
                            else:
                                self._gain_rep(p, dest, -cb["rep_penalty"])
                            jail_seized = True
                            log.append(tx("l.seized", qty=found, fine=money(fine), contraband=what.lower(), Contraband=what))
                            news.append(tx("n.caught", name=p["name"], firm=p["firm"], port=PORTS[dest]["name"],
                                           contraband=what.lower(), Contraband=what))
                            self._ev("voyage", "seized", "{}: customs in {} seized {} units of {} and fined {}; standing -{}".format(
                                who, PORTS[dest]["name"], found, what, money(fine), cb["rep_penalty"]), p, qty=found, fine=fine,
                                port=dest, goods=taken, hid=hid)
                        if hid:
                            log.append(tx("l.hid_customs", goods=self._goods_text(hid)))
                # The jail: contraband may cost the captain a month too; rock-bottom standing or a Hostile
                # port may mean arrest on the wharf. A jailed captain's declaration is filed honestly.
                if not (jail_seized and jail.on_seized(self, p, news, dest)):
                    jail.on_arrival(self, p, news, dest)
                self._open_customs(p)
                if jail.jailed(p):
                    self._settle_customs(p)
                legend.on_arrival(self, p, news, dest)      # a Legend may break in here (legend.py); it costs no time
                return

    # ------------------------------------------------------- sea battles --
    # A fight is a small state on the house (p["battle"]) played one step at a time. A captain at a
    # screen chooses each round (fight, run, retreat; or pays the pirates' price before the first
    # shot); a house with nobody at the helm plays every round on its standing orders, exactly as
    # battles were always settled. A fight played on screen rolls its own dice from its own seed,
    # so it comes out the same whatever else is going on around it.
    SEA_CHOICES = ("fight", "run", "retreat", "pay", "pay_cargo", "pay_wu", "spare", "auto", "skip")
    PAY_CHOICES = ("pay", "pay_cargo", "pay_wu")

    def _battle_live(self, p):
        """Is this fight being played by its captain (rather than on standing orders)?"""
        b = p.get("battle")
        return bool(b) and b.get("seed") is not None and not b.get("auto")

    # The enemy's voice (the right-hand seat): Admiral Li Yue speaks for her own war junks, Madam Shek
    # Yu-lan for the ordinary pirate junks. She speaks at the key moments only, after the bosun, from her
    # own pool of lines (battle.foe.<cast key>.<pool>.<n>). Each pool has the mood her picture shows.
    FOE_MOOD = {"sighting": "speaking", "price": "speaking", "lowball": "sly", "reprice": "angry", "paid": "happy",
                "lost_junk": "angry", "sank_ours": "happy", "hit_us": "happy", "noguns": "happy", "got_away": "angry",
                "broke_off": "angry", "retreat": "happy", "defeated": "angry", "victory": "happy", "plunder": "happy",
                "spite": "sly"}

    def _foe_start(self, b):
        """Called when a step of a fight starts: who speaks for this enemy."""
        self._foe_who = "" if b.get("fleet") == "band" else "pirate" if b.get("kind") == "lord" else "agent"
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

    def worth_share(self, p):
        """0 to 1: how rich the house looks to the pirates (half way at rules.battle.worth_ref)."""
        ref = max(1.0, float(R["battle"].get("worth_ref", 5000000)))
        w = max(0.0, self.worth(p))
        return w / (w + ref)

    def _allure(self, p):
        """How keen the pirates are on this fleet: an empty hold and no name draws fewer of them, and a
        rich house draws more (Game 3 review)."""
        bt = R["battle"]
        return max(0.0, bt["allure_base"] + bt["allure_cargo"] * self.temptation(p) + bt["allure_fame"] * self.fame_share(p)
                   + float(bt.get("allure_worth", 0.0)) * self.worth_share(p))

    def lord_pull(self, p):
        """How much more often the pirate queen finds a rich house: 1 + lord_worth x worth share."""
        return 1.0 + float(R["battle"].get("lord_worth", 0.0)) * self.worth_share(p)

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
        tempt, fame, rich = self.temptation(p), self.fame_share(p), self.worth_share(p)
        standing = (float(p["rep"].get(dest, 50.0)) - 50.0) / 50.0 if dest in PORTS else 0.0
        lo, hi = sorted((float(bt["match_rounds_min"]), float(bt["match_rounds_max"])))
        # A rich house meets fleets that last longer under its guns (match_worth_rounds, Game 3 review).
        rounds = max(1.0, rng.uniform(lo, hi) + float(bt.get("match_worth_rounds", 0.0)) * rich)
        noise = rng.gauss(0, float(bt["match_spread"]))
        m = (bt["match_base"] + bt["match_cargo"] * tempt + bt["match_fame"] * fame
             + float(bt.get("match_worth", 0.0)) * rich
             - bt["match_standing"] * standing + noise + (bt["match_lord"] if lord else 0.0)
             # The port sailed from (rules.standing): Hostile locals sell word of the sailing, Favoured
             # friends ashore send warning of who lies in wait.
             + self.band_effects(p, (p.get("voy") or {}).get("origin"))["match"])
        m = max(float(bt["match_min"]), min(float(bt["match_max"]), m)) * MULT.get("pirates", 1.0) ** 0.35
        their_hull = fire * rounds                                  # sum of the junks' hit points
        per_shot = src["hit"] * (src["dmg_min"] + src["dmg_max"]) / 2.0
        their_fire = hull * m / rounds                              # our hull they would take off each round
        size = rng.uniform(float(bt["match_hp_min"]), float(bt["match_hp_max"])) * (1.5 if lord else 1.0)
        top = int(bt["match_lord_ships_max"] if lord else bt["match_ships_max"])
        fleet = self._fleet_type(p, kind)
        if fleet == "raiders":
            their_fire *= float(bt.get("raider_guns", 0.6))         # fast and lightly gunned: they want the hold
        elif fleet == "band":
            weak = float(bt.get("band_strength", 0.45))
            their_hull *= weak
            their_fire *= weak
            top = max(1, min(top, int(bt.get("band_ships_max", 4))))
        # How many (19 Nov 2026): their hull split into junks of this size, then swung up or down by
        # match_size_swing so no two fights look alike. The aim sits low enough under the cap that a swing
        # upward still fits; past that the same hull goes into fewer, tougher junks rather than more of them.
        lo_n, swing = int(bt["match_ships_min"]), max(0.0, float(bt.get("match_size_swing", 0.3)))
        aim = min(their_hull / max(1.0, size), top / (1.0 + swing))
        n = max(min(lo_n, top), min(top, int(round(aim * rng.uniform(1.0 - swing, 1.0 + swing)))))
        weights = [float(bt.get("match_flag", 2.0))] + [rng.uniform(0.7, 1.3) for _ in range(n - 1)]
        total = sum(weights)
        hp = [max(1, int(round(their_hull * w / total))) for w in weights]
        guns_all = max(n, int(round(their_fire / max(0.1, per_shot))))
        raw = [guns_all * w / total for w in weights]
        guns = [max(1, int(r)) for r in raw]
        for i in sorted(range(n), key=lambda i: -(raw[i] - int(raw[i])))[:max(0, guns_all - sum(guns))]:
            guns[i] += 1
        return {"n": n, "hp": hp, "guns": guns, "match": round(m, 3), "rounds": round(rounds, 2), "fleet": fleet,
                "temptation": round(tempt, 3), "fame": round(fame, 3), "standing": round(standing, 3),
                "worth": round(rich, 3),
                "worth_n": their_hull / max(1.0, float(pi["hp"]))}

    def _fleet_type(self, p, kind):
        """Which of the three kinds of enemy this is (Game 4 review, 20 Nov 2026): Admiral Li Yue's heavy war
        fleet ("war"), or for ordinary pirates raiders or, rules.battle.band_share of the time, a small
        lucky band. Its own dice, so the rest of the fight comes out as before. None with the rule off."""
        bt = R["battle"]
        if not bt.get("fleet_types", True):
            return None
        if kind == "lord":
            return "war"
        own = random.Random("fleet_type:{}:{}:{}".format(self.s.get("game_id", ""), self.s["turn"], p.get("id", "")))
        return "band" if own.random() < float(bt.get("band_share", 0.3)) else "raiders"

    # ---- where the enemy's fire lands (the fleet's formation) ----------------------------------
    # Escorts sail in the van and take the fire; merchantmen sail in the line; cargo ships in the rear,
    # screened by the escorts (and half as well by merchantmen) in front of them. With focus, each enemy
    # junk lays its whole broadside on the weakest ship of the front rank, so the van is ground down
    # one ship at a time and the rear grows more exposed as it goes.
    def _formation_weight(self, sh, ships):
        bt, r = R["battle"], role_of(sh["type"])
        if r == "escort":
            return float(bt["van_weight"])
        if r in ("trader", FLAG):
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
        # A ship crippled in this fight has struck out of the line; they finish her only when nothing else is left.
        out = set(b.get("crippled") or ())
        alive = [sh for sh in alive if sh["name"] not in out] or alive
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
        fleet = (muster or {}).get("fleet")
        label = tx("w.raider_junks" if fleet == "raiders" else "w.band_junks" if fleet == "band"
                   else "w.pirate_junks" if kind == "pirates" else "w.war_junks")
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
             "cargo0": dict(p["cargo"]), "net": 0.0, "booty": 0, "paid": 0, "price": 0, "dest": dest, "beat": None,
             "fleet": fleet}
        for sh in b["ships0"]:
            sh["role"] = role_of(sh["type"])
        if muster:
            b.update({"hp": list(muster["hp"]), "hpmax": list(muster["hp"]), "eg": list(muster["guns"]),
                      "enemy_hull": sum(muster["hp"]), "enemy_guns": sum(muster["guns"]),
                      "focus": float(bt.get("focus", 0.0)), "formation": True, "worth_n": muster["worth_n"],
                      "match": {k: muster[k] for k in ("match", "rounds", "temptation", "fame", "standing", "worth") if k in muster}})
        else:
            b.update({"hpmax": list(b["hp"]), "eg": [1] * n, "worth_n": n,
                      "formation": any(role_of(sh["type"]) != "trader" for sh in p["ships"])})
        if live:
            b["seed"] = rng.getrandbits(48)
            own = random.Random("{}:open".format(b["seed"]))
            b["dump"] = round(own.uniform(bt["retreat_min"], bt["retreat_max"]), 4)
            if kind == "pirates" and bt["parley"]:
                value = sum(q * GOODS[g]["base"] for g, q in p["cargo"].items() if g in GOODS)
                # A fair price (Game 4 review): parley_cargo..parley_cargo_max of the hold, drawn for this fight.
                lo, hi = sorted((float(bt["parley_cargo"]), float(bt.get("parley_cargo_max", bt["parley_cargo"]))))
                b["share"] = round(random.Random("{}:share".format(b["seed"])).uniform(lo, hi), 4)
                b["price"] = int(max(1, b["worth_n"] * bt["parley_per_junk"] + b["share"] * value))
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
        self._spite_roll(p, b)
        if b.get("spite"):
            log.append(tx("l.spite", goods=GOODS[b["spite"]["aim"]]["name"]))
        self._limit_roll(p, b)
        p["battle"] = b
        self._say_from, self._said = (b["seed"] or 0) % 9973, 0
        self._foe_start(b)
        who = p["name"]
        mt = b.get("match")
        if fleet:
            self._ev("battle", "fleet_type", "{}: the enemy is {}".format(p["name"], {"raiders": "raiders (fast, few guns, after the hold)",
                     "band": "a small band (weak; can be spared)", "war": "the heavy war fleet"}[fleet]), p, fleet=fleet)
        self._ev("battle", "battle", "{} attacked by {} {}: orders {}{}, {} guns, {} cannons ({} shots a round), hull {}; "
                 "enemy hits {} per gun per round for {}-{}{}{}".format(
                                            who, n, label, orders, " (no guns, so running)" if orders != p["orders"] else "",
                                            self.guns(p), self.cannons(p), self.firepower(p), "/".join(str(sh["hull"]) for sh in p["ships"]), pct(hit), dmg[0], dmg[1],
                                            ("; matched x{} (cargo {}, fame {}, standing {:+}), {} enemy hull, {} enemy guns, "
                                             "about {} rounds of our fire".format(mt["match"], mt["temptation"], mt["fame"],
                                                                                  mt["standing"], sum(b["hp"]), sum(b["eg"]),
                                                                                  mt["rounds"]) if mt else ""),
                                            ("; fought on screen" if live else "") + ("; they ask {} to let the fleet pass".format(
                                                money(b["price"])) if b["price"] else "")),
                 p, enemy=label, count=n, orders=orders, guns=self.guns(p), hit=hit, dmg=list(dmg), fleet=fleet,
                 **({"match": mt, "enemy_hp": list(b["hp"]), "enemy_guns": list(b["eg"])} if mt else {}),
                 **({"live": True} if live else {}), **({"parley": b["price"]} if live or b["price"] else {}))
        where = PORTS[dest]["name"] if dest in PORTS else ""
        say = {"raiders": "sighting_raiders", "band": "sighting_band", "war": "sighting_war"}.get(fleet, "sighting")
        if "battle.say.{}.0".format(say) not in TEXT:
            say = "sighting"
        frames = [self._frame("sighting", "sighting", say, foe="sighting", n=n, enemy=label, port=where)]
        if b["stage"] == "parley":
            talk = "tribute" if kind == "lord" else "lowball" if b.get("lowball") else "parley"
            fr = self._frame("sighting", talk, talk, foe="lowball" if talk == "lowball" else "price", price=money(b["price"]))
            if talk == "lowball":
                fr["mood"] = "sly"
            frames.append(fr)
        if b.get("spite"):
            fr = self._frame("sighting", "spite", "spite", foe="spite", goods=GOODS[b["spite"]["aim"]]["name"])
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
        b["price"] = int(max(1, b["worth_n"] * bt["parley_per_junk"] + b.get("share", bt["parley_cargo"]) * value * think))
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
            choice = "pay" if lord and b["stage"] == "parley" and p["cash"] + p["bank"] >= b["price"] else b["orders"]
        if choice == "fight" and self.firepower(p) == 0:
            choice = "run"                      # every gun dismounted: standing orders to fight become a run for it
        if b["stage"] == "parley":
            if choice in self.PAY_CHOICES:
                price = b["price"]
                plan, silver = self._pay_toll(p, choice)
                b["paid"] = price
                b["paid_how"] = {k: plan[k] for k in ("cash", "bank", "cargo", "cargo_value", "wu", "fee")}
                b["paid_how"]["way"] = choice
                how = ""
                if plan["bank"]:
                    how += ", {} by bank note".format(money(plan["bank"]))
                if choice == "pay_cargo" and plan["cargo"]:
                    how += ", the rest in cargo: " + ", ".join("{} {}".format(q, GOODS[g]["name"]) for g, q in plan["cargo"].items())
                if choice == "pay_wu":
                    how += ", the rest ({}) on Madam Wu's books with a {} fee".format(money(plan["short"]), money(plan["fee"]))
                if lord:
                    self._book(p, "protection", -silver)
                    p["protect"] = R["liyuen"]["protect_months"]
                    log.append(tx("l.tribute_paid", cost=money(price), months=p["protect"]))
                    self._ev("battle", "paid", "{} paid {} {} {} in tribute at sea{}; protected for {} months".format(
                        who, n, b["label"], money(price), how, p["protect"]), p, price=price, tribute=True, how=b["paid_how"])
                    frames.append(self._frame("got_away", "tribute_paid", "paid", foe="paid", price=money(price)))
                else:
                    self._book(p, "parley", -silver)
                    log.append(tx("l.parley_paid", n=n, enemy=b["label"], cost=money(price)))
                    self._ev("battle", "paid", "{} paid {} {} {} to pass{}".format(who, n, b["label"], money(price), how), p,
                             price=price, how=b["paid_how"])
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
                who, "could not pay" if p["cash"] + p["bank"] < b["price"] else "refused to pay", money(b["price"])), p, price=b["price"])
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
            self._check_sunk(p, tx("l.how_sunk"), b)
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
                            * (float(bt.get("match_booty", 1.0)) if b.get("match") else 1.0)
                            * {"war": float(bt.get("lord_booty", 1.0)), "band": float(bt.get("band_booty", 1.0))}.get(b.get("fleet"), 1.0))
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
        elif choice == "spare":
            return self._spare_band(p, b, frames, rnd)
        elif self._chance(pi["run_base"] + (pi["run_fast"] if b["fast"] else 0) + pi["run_round"] * rnd + self._raider_run(b), "escape",
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
        self._check_sunk(p, tx("l.how_sunk"), b)
        b["round"] = rnd
        self._hit_frames(p, b, frames, taken_round, names)
        for nm in b.pop("crippled_now", None) or ():
            frames.append(self._frame("we_are_hit", "crippled", "crippled", name=nm))
        if not p["ships"]:
            frames.append(self._frame("defeat", "defeat", "defeat", foe="victory"))
            return self._battle_close(p, b, "wrecked", frames)
        limit = self._round_limit(b)
        if rnd == limit - 1 and bt.get("limit_hint", True):
            # The round before the last: Powder says the enemy is tiring, with no number (20 Nov 2026).
            frames.append(self._frame("sighting", "limit_near", "limit_near", left=len(pirates)))
        if rnd >= limit:
            if b["runs"] == 0:
                log.append(tx("l.long_fight", n=n - len(pirates)))
                self._ev("battle", "broke_off", "{}: enemy broke off after {} rounds; {} of {} sunk".format(
                    who, limit, n - len(pirates), n), p, sunk=n - len(pirates))
                frames.append(self._frame("got_away", "broke_off", "broke_off", foe="broke_off", sunk=n - len(pirates), n=n))
                return self._battle_close(p, b, "broke_off", frames)
            # Every round spent running and failing lets them close: the cargo they carry off is in
            # proportion (all of it when the fleet only ever ran, as before).
            share = b["runs"] / float(rnd)
            lost = {g: int(q * rng.uniform(pi["plunder_min"], pi["plunder_max"]) * share) for g, q in p["cargo"].items()}
            # Before they come over the rail the crew stows a share of it away (rules.hide.pirates).
            hid = self._crew_hide(p, {g: q for g, q in lost.items() if q > 0}, "pirates", "battle")
            lost = {g: q - hid.get(g, 0) for g, q in lost.items()}
            if hid:
                b["hid"] = hid
            self._book(p, "plundered", -self._cost_of(p, lost))
            for g, q in lost.items():
                p["cargo"][g] -= q
            p["cargo"] = {g: q for g, q in p["cargo"].items() if q > 0}
            log.append(tx("l.plundered", qty=sum(lost.values())))
            if hid:
                log.append(tx("l.hid_pirates", goods=self._goods_text(hid)))
            self._ev("battle", "plundered", "{} could not get away in {} rounds and was plundered of {} units: {}".format(
                who, limit, sum(lost.values()),
                ", ".join("{} {}".format(q, GOODS[g]["name"]) for g, q in lost.items() if q) or "nothing"),
                p, lost={g: q for g, q in lost.items() if q})
            frames.append(self._frame("boarding", "plundered", "plundered", foe="plunder", qty=sum(lost.values())))
            return self._battle_close(p, b, "plundered", frames)
        b["beat"] = {"id": b["step"] + 1, "frames": frames}

    def _raider_run(self, b):
        """Raiders are easy to outrun (rules.battle.raider_run): an extra chance each time the fleet runs."""
        return float(R["battle"].get("raider_run", 0.0)) if b.get("fleet") == "raiders" else 0.0

    def can_spare(self, b):
        """A small band can be spared once the first broadside has been traded (Game 4 review)."""
        return bool(b) and b.get("fleet") == "band" and b.get("stage") == "fight" and int(b.get("round", 0)) >= 1 \
            and bool(b.get("hp"))

    def _spare_band(self, p, b, frames, rnd):
        """Let the little band go: they strike their colours and, grateful, tell what they know of a
        price somewhere (the dearest cargo against its usual price, in a port other than the one ahead)."""
        tip = self._band_tip(p, b)
        b["round"] = rnd - 1
        p["log"].append(tx("l.spared", n=len(b["hp"])))
        if tip:
            p["log"].append(tx("l.band_tip", goods=GOODS[tip["good"]]["name"], where=PORTS[tip["port"]]["name"],
                               price=money(tip["price"])))
        b["spared_tip"] = tip
        self._ev("battle", "spared", "{} spared {} of {} {} after {} round(s){}".format(
            p["name"], len(b["hp"]), b["n"], b["label"], rnd - 1,
            "; they told of {} at {} in {}".format(GOODS[tip["good"]]["name"], money(tip["price"]), PORTS[tip["port"]]["name"])
            if tip else ""), p, tip=tip, left=len(b["hp"]))
        frames.append(self._frame("got_away", "spared", "spared",
                                  goods=GOODS[tip["good"]]["name"] if tip else "", where=PORTS[tip["port"]]["name"] if tip else "",
                                  price=money(tip["price"]) if tip else ""))
        return self._battle_close(p, b, "spared", frames)

    def _band_tip(self, p, b):
        """{good, port, price} or None: the cargo selling dearest against its usual price, anywhere but the
        port ahead and the port left. Recorded as a price the house knows, as the Registrar's tips are."""
        dest, origin = b.get("dest"), (p.get("voy") or {}).get("origin")
        best = None
        for port in sorted(PORTS):
            if port in (dest, origin):
                continue
            for g in sorted(GOODS):
                usual = GOODS[g]["base"] * PORTS[port]["mods"].get(g, 1.0)
                ratio = self.s["prices"][port][g] / max(0.01, usual)
                if best is None or ratio > best[0]:
                    best = (ratio, port, g)
        if best is None:
            return None
        _, port, g = best
        price = int(round(self.s["prices"][port][g]))
        p.setdefault("tips", {}).setdefault(port, {})[g] = {"turn": self.s["turn"], "price": price}
        return {"good": g, "port": port, "price": price}

    PRIZE_TIERS = ("scraps", "modest", "rich", "haul")

    def _battle_prize_manifest(self, p, b):
        """Reproduce this encounter's cargo without touching combat dice or the player's hold."""
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
        return tier, haul, own

    def _battle_reward(self, p, b):
        pi = R["pirates"]
        count = b.get("worth_n", b["n"])
        growth = 1 + self.s["turn"] / float(pi["booty_growth"])
        matched = float(R["battle"].get("match_booty", 1.0)) if b.get("match") else 1.0
        manifest = self._battle_prize_manifest(p, b)
        free = max(0, self.capacity(p) - self.used(p))
        worth, left = 0, 0
        if manifest:
            _, haul, _ = manifest
            for g in sorted(haul, key=lambda k: -GOODS[k]["base"]):
                q = min(haul[g], free)
                worth += q * GOODS[g]["base"]
                free -= q
                left += haul[g] - q
        return {"silver_min": int(count * pi["booty_min"] * growth * matched),
                "silver_max": int(count * pi["booty_max"] * growth * matched),
                "cargo_worth": int(worth), "tier": manifest[0]["key"] if manifest else "none",
                "cargo_left": left}

    def _battle_prize(self, p, b, frames):
        manifest = self._battle_prize_manifest(p, b)
        if manifest is None:
            return
        tier, haul, own = manifest
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
            rot.add(p, g, q)
            p["cargo"][g] = p["cargo"].get(g, 0) + q
        worth = int(sum(q * GOODS[g]["base"] for g, q in took.items()))
        what = self._goods_text(took)
        mark = tx("battle.prize.mark.{}".format(own.randrange(self._count("battle.prize.mark."))))
        b["prize"] = {"tier": tier["key"], "goods": took, "left": left, "worth": worth}
        if took:
            p["log"].append(tx("l.prize", goods=what, mark=mark))
        if left:
            p["log"].append(tx("l.prize_left", qty=left))
        self._ev("battle", "prize", "{} took {} from the {} {} ({} tier, about {} at usual prices){}".format(
            p["name"], what or "nothing", b["n"], b["label"], tier["key"], money(worth),
            "; no room for {} more units".format(left) if left else ""), p,
            tier=tier["key"], goods=took, left=left, worth=worth)
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

    # ---- spiteful crews (rules.battle.spite) -------------------------------------------------------
    # Some enemy crews would rather sink a rich cargo than let it sail on. Rolled once at the sighting
    # (rules.battle.spite_chance, spite_chance_lord for Li Yue's war junks), on dice of its own, so a
    # fight with an ordinary crew rolls exactly as before. A spiteful crew aims for the hold more often
    # (spite_hold times the usual cargo_hit share), and a hold hit goes for the dearest good aboard
    # (spite_aim of the time, otherwise any good, as usual). Powder and the enemy say so at the sighting.
    def _spite_roll(self, p, b):
        bt = R["battle"]
        aboard = [g for g, q in p["cargo"].items() if q > 0 and g in GOODS]
        if not bt.get("spite", True) or not aboard:
            return
        seed = "{}:{}:{}:{}:{}:spite".format(self.s.get("game_id", ""), self.s.get("turn", 0), p.get("id", ""),
                                             b["kind"], b.get("seed") or 0)
        own = random.Random(seed)
        chance = float(bt.get("spite_chance_lord" if b["kind"] == "lord" else "spite_chance", 0.0))
        if b.get("fleet") == "raiders":
            chance = 1.0                              # raiders come for the cargo, and aim for the dearest
        roll = own.random()
        if roll >= chance:
            return
        aim = max(aboard, key=lambda g: (GOODS[g]["base"], g))
        b["spite"] = {"seed": seed, "aim": aim, "n": 0}
        self._ev("battle", "spite", "{}: a spiteful crew ({:.0%} chance): their gunners will aim for the {}".format(
            p["name"], chance, GOODS[aim]["name"]), p, chance=round(chance, 4), aim=aim)

    def _limit_roll(self, p, b):
        """This fight's round limit (rules.battle.limit_min to limit_max), rolled once at the sighting on dice
        of its own, so no other roll changes. The captain never sees it unless the difficulty shows it."""
        bt = R["battle"]
        lo, hi = sorted((int(bt.get("limit_min", 6)), int(bt.get("limit_max", 6))))
        seed = "{}:{}:{}:{}:{}:limit".format(self.s.get("game_id", ""), self.s.get("turn", 0), p.get("id", ""),
                                             b["kind"], b.get("seed") or 0)
        b["limit"] = random.Random(seed).randint(max(2, lo), max(2, hi))
        self._ev("battle", "limit", "{}: this fight will last at most {} rounds".format(p["name"], b["limit"]),
                 p, limit=b["limit"])

    @staticmethod
    def _round_limit(b):
        """The fight's round limit; a fight saved before the limit was rolled keeps the old fixed one."""
        return int(b.get("limit") or R["pirates"]["rounds"])

    @staticmethod
    def _hold_chance(b):
        bt = R["battle"]
        c = float(bt.get("cargo_hit", 0.0))
        if b.get("spite"):
            c *= float(bt.get("spite_hold", 1.0))
        return min(1.0, c)

    def _spite_pick(self, p, b, g, aboard):
        """The good a hold hit lands on: g (already rolled as usual), or for a spiteful crew, mostly the
        dearest good aboard. Returns (good, aimed)."""
        sp = b.get("spite")
        if not sp:
            return g, False
        sp["n"] = sp.get("n", 0) + 1
        if random.Random("{}:aim:{}".format(sp["seed"], sp["n"])).random() >= float(R["battle"].get("spite_aim", 0.0)):
            return g, False
        dear = max(aboard, key=lambda x: (GOODS[x]["base"] if x in GOODS else 0, x))
        return dear, True

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
            if aboard and rng.random() < self._hold_chance(b):
                g, aimed = self._spite_pick(p, b, rng.choice(aboard), aboard)
                lo, hi = sorted((float(bt.get("cargo_hit_min", 0.1)), float(bt.get("cargo_hit_max", 0.3))))
                q = min(p["cargo"][g], max(1, int(round(p["cargo"][g] * rng.uniform(lo, hi)))))
                self._book(p, "overboard", -self._cost_of(p, {g: q}))
                p["cargo"][g] -= q
                if p["cargo"][g] <= 0:
                    del p["cargo"][g]
                shot = b.setdefault("shot", {})
                shot[g] = shot.get(g, 0) + q
                out.append({"name": target["name"], "damage": 0, "guns": 0, "hull": target["hull"], "cargo": {g: q},
                            **({"aimed": True} if aimed else {})})
                continue
            points = rng.randint(*b["dmg"])
            target["hull"] -= points
            self._flag_floor(p, target)
            out.append({"name": target["name"], "damage": points, "guns": 0, "hull": target["hull"]})
        return out

    def _flag_floor(self, p, target):
        """The flagship always sinks last: while any other ship of the fleet is afloat, a shot that
        would sink her leaves her at 1 hull point."""
        if target["hull"] <= 0 and role_of(target["type"]) == FLAG and \
                any(sh is not target and sh["hull"] > 0 for sh in p["ships"]):
            target["hull"] = 1

    def flag_deter(self, p):
        """How much less often pirates find a fleet with its flagship along (1.0 = no change)."""
        if any(role_of(sh["type"]) == FLAG for sh in p["ships"]):
            return max(0.0, 1.0 - float(R["fleet"].get("flagship_deter", 0.0)))
        return 1.0

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
                    if aboard and rng.random() < self._hold_chance(b):
                        # One kind of goods (gold as likely as rice; a spiteful crew aims for the dearest),
                        # as much of it as the shot's share of her hull is of her hold (the cargo-ship rule).
                        g, aimed = self._spite_pick(p, b, rng.choice(aboard), aboard)
                        spec = SHIPS[target["type"]]
                        fill = self.used(p) / float(max(1, self.capacity(p)))
                        share = rng.randint(*b["dmg"]) / float(max(1, spec["hull"])) * spec["hold"] * fill \
                            * float(bt.get("cargo_spill", 1.0))
                        q = min(p["cargo"][g], max(1, int(round(share))))
                        self._spill(p, b, {g: q})
                        out.append({"name": target["name"], "damage": 0, "guns": 0, "hull": target["hull"],
                                    "cargo": {g: q}, "role": role, **({"aimed": True} if aimed else {})})
                        continue
                points = rng.randint(*b["dmg"])
                target["hull"] -= points
                self._flag_floor(p, target)
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
                        wts = [x[1] * (GOODS[x[0]]["base"] if b.get("spite") and x[0] in GOODS else 1) for x in pool]
                        g = rng.choices([x[0] for x in pool], weights=wts)[0] if len(pool) > 1 else pool[0][0]
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
            aimed = not gold and any(h.get("aimed") for h in taken_round)
            pool = ("cargo_gold" if gold else "cargo_aimed" if aimed else "cargo_hit") if say and (gold or aimed or not spoke) else None
            frames.append(self._frame("we_are_hit", "cargo_gold" if gold else "cargo_aimed" if aimed else
                                      "rear_hit" if rear else "cargo_hit",
                                      pool, foe=foe_if(pool),
                                      goods=self._goods_text(spilled), qty=sum(spilled.values())))
        afloat = {sh["name"] for sh in p["ships"]}
        for sh in b["ships0"]:
            if sh["name"] in names and sh["name"] not in afloat:
                r = sh.get("role") or role_of(sh["type"])
                frames.append(self._frame("ship_lost", "escort_lost" if r == "escort" else "cargo_sunk" if r == "cargo"
                                          else "ship_lost", "ship_lost", foe="sank_ours",
                                          ship=SHIPS[sh["type"]]["name"] if sh["type"] in SHIPS else sh["type"], name=sh["name"]))

    def _warned_off(self, p, origin):
        """Favoured in the port sailed from: friends ashore warn of the fleet lying in wait, and now and
        then the house slips past it (rules.standing.favoured_avoid). Its own dice, not the game's."""
        chance = self.band_effects(p, origin)["avoid"] if origin in PORTS else 0.0
        if chance <= 0:
            return False
        hit = self._band_rng(p, "avoid").random() < chance
        self._ev("dice", "band_avoid", "{}: Favoured in {}, friends' warning ({}): {}".format(
            p["name"], PORTS[origin]["name"], pct(chance), "slipped past" if hit else "no luck"), p, odds=chance, hit=hit)
        return hit

    def _battle_close(self, p, b, outcome, frames):
        """The fight is over: the damage line for the log, and the reckoning for the screen."""
        bt = R["battle"]
        dest = (p.get("voy") or {}).get("dest")
        if self.standing_on() and dest in PORTS:
            # The port ahead hears how it went (rules.standing): pirates beaten off its waters, or a house
            # beaten or running from them.
            st = R["standing"]
            if outcome == "won":
                self._standing(p, dest, float(st.get("pirates_beaten", 0)), "pirates_beaten")
            elif outcome in ("retreated", "plundered", "wrecked"):
                self._standing(p, dest, -float(st.get("beaten", 0)), "beaten")
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
                "hid": [{"good": g, "qty": q} for g, q in sorted((b.get("hid") or {}).items(), key=lambda kv: -kv[1])],
                "net": int(round(b.get("net", 0.0))), "where": PORTS[dest]["name"] if dest in PORTS else "",
                "match": b.get("match"), "enemy_hull": b.get("enemy_hull"), "enemy_guns": b.get("enemy_guns"),
                "fleet": b.get("fleet"), "tip": b.get("spared_tip"), "crippled": list(b.get("crippled") or ()),
                "beat": {"id": b["step"] + 1, "frames": frames}})
        p.pop("battle", None)

    def toll_plan(self, p, price):
        """How the house can pay a price to pass (19 Nov 2026). Silver aboard goes first, then the bank
        (a note on the account: no fee, so banked silver can still buy a way past). Whatever is still
        short can go in cargo (the pirates' pick, the dearest units first, counted at their normal price)
        or on Madam Wu's books (the shortfall plus rules.battle.wu_fee, as debt, within the loan limit)."""
        price = int(price)
        cash = min(int(p["cash"]), price)
        bank = min(int(p["bank"]), price - cash)
        short = price - cash - bank
        take, left = {}, short
        for g in sorted(p["cargo"], key=lambda k: -normal_price(k)):
            if left <= 0:
                break
            unit = normal_price(g)
            if unit <= 0:
                continue
            q = min(p["cargo"][g], int(math.ceil(left / unit)))
            if q > 0:
                take[g] = q
                left -= q * unit
        fee = int(math.ceil(short * float(R["battle"].get("wu_fee", 0.10))))
        return {"price": price, "cash": cash, "bank": bank, "short": short, "cargo": take,
                "cargo_value": int(round(sum(q * normal_price(g) for g, q in take.items()))),
                "wu": short + fee, "fee": fee,
                "can_pay": short <= 0,
                "can_cargo": short > 0 and left <= 0,
                "can_wu": short > 0 and p["debt"] + short + fee <= self.loan_limit(p)}

    def _pay_toll(self, p, choice):
        """Pay the price to pass the way the captain chose. Returns the plan that was used."""
        b = p["battle"]
        plan = self.toll_plan(p, b["price"])
        p["cash"] -= plan["cash"]
        p["bank"] -= plan["bank"]
        if choice == "pay_cargo":
            for g, q in plan["cargo"].items():
                p["cargo"][g] -= q
                if not p["cargo"][g]:
                    del p["cargo"][g]
        elif choice == "pay_wu":
            p["debt"] += plan["wu"]
            self._book(p, "interest", -plan["fee"])
        silver = plan["cash"] + plan["bank"] + (plan["short"] if choice == "pay_wu" else 0)
        return plan, silver

    def _act_sea(self, p, a):
        """A captain's choice in a fight: pay, fight, run, retreat; auto (this round on standing
        orders: the round timer ran out) or skip (the rest of the fight on standing orders)."""
        b = p.get("battle")
        if b is None:
            raise GameError(tx("e.no_battle"))
        choice = str(a.get("choice"))
        if choice not in self.SEA_CHOICES:
            raise GameError(tx("e.unknown_action"))
        if choice in self.PAY_CHOICES:
            if b["stage"] != "parley":
                raise GameError(tx("e.no_parley"))
            plan = self.toll_plan(p, b["price"])
            if not plan[{"pay": "can_pay", "pay_cargo": "can_cargo", "pay_wu": "can_wu"}[choice]]:
                raise GameError(tx("e.parley_cost", cost=money(b["price"]), cash=money(p["cash"] + p["bank"])))
        if choice == "fight" and self.firepower(p) == 0:
            raise GameError(tx("e.no_guns"))
        if choice == "spare" and not self.can_spare(b):
            raise GameError(tx("e.no_spare"))
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
                                        + (["pay"] if v["can_pay"] else [])
                                        + (["pay_cargo"] if (v.get("toll") or {}).get("can_cargo") else []))
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
        run = max(0.0, min(1.0, pi["run_base"] + (pi["run_fast"] if b["fast"] else 0) + pi["run_round"] * rnd
                           + self._raider_run(b)))
        avg = (b["dmg"][0] + b["dmg"][1]) / 2.0
        eg = (b.get("eg") or [1] * left)[:left]
        per_round = sum(eg) * b["hit"] * avg                    # hull the enemy takes off the fleet each round
        to_sink = (sum(b["hp"]) / (guns * pi["gun_hit"])) if guns and pi["gun_hit"] > 0 else 99.0
        rounds_left = max(1, self._round_limit(b) - b["round"])
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
        out = {"kind": b["kind"], "enemy": b["label"], "n": b["n"], "left": left, "round": rnd if view != "tell" else 0,
               "rounds": self._round_limit(b) if view == "exact" else 0,       # this fight's limit shows on Calm waters only (20 Nov 2026)
               "stage": b["stage"], "orders": b["orders"], "guns": guns, "can_fight": guns > 0, "step": b["step"],
               "gun_count": self.guns(p), "cannons": self.cannons(p),
               "where": PORTS[dest]["name"] if dest in PORTS else "", "view": view, "moods": moods, "mood": overall,
               "tell": tx("battle.tell.{}.{}".format(overall, (b["seed"] + b["step"]) % tells)) if tells else "",
               "price": b["price"] if b["stage"] == "parley" else 0,
               "can_pay": b["stage"] == "parley" and self.toll_plan(p, b["price"])["can_pay"],
               "toll": (lambda pl: {k: pl[k] for k in ("cash", "bank", "short", "cargo", "cargo_value", "wu", "fee",
                                                       "can_pay", "can_cargo", "can_wu")})(self.toll_plan(p, b["price"]))
                       if b["stage"] == "parley" else None,
               "bargain": ({"share": round(b["price"] / float(max(1, b["lowball"]["value"])), 4),
                            "full": b["lowball"]["full"]}
                           if b.get("lowball") and not b["lowball"].get("seen") and b["stage"] == "parley" else None),
               "repriced": bool(b.get("lowball") and b["lowball"].get("seen") and b["stage"] == "parley"),
               "dump": gone, "dump_qty": sum(gone.values()), "beat": b["beat"], "hull": hull,
               "auto": bool(b.get("auto")),
               "enemy_ships": [{"hp": max(0, h), "max": (b.get("hpmax") or [])[i] if i < len(b.get("hpmax") or []) else h,
                                "guns": eg[i] if i < len(eg) else 1} for i, h in enumerate(b["hp"])],
               "enemy_guns": sum(eg), "matched": bool(b.get("match")),
               "fleet": b.get("fleet"), "can_spare": self.can_spare(b),
               "reward": self._battle_reward(p, b)}
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
        view = MULT.get("battle_view") or MULT.get("customs_view", "bar")     # the round count follows the odds shown
        for p in (self.s["players"][i] for i in self.s["order"]):
            b = p.get("battle")
            if b is None:
                continue
            dest = b.get("dest")
            out.append({"id": p["id"], "name": p["name"], "firm": p["firm"], "color": p["color"], "kind": b["kind"],
                        "enemy": b["label"], "n": b["n"], "left": len(b["hp"]),
                        "round": b["round"] + 1 if view != "tell" else 0,
                        "rounds": self._round_limit(b) if view == "exact" else 0, "stage": b["stage"],
                        "where": PORTS[dest]["name"] if dest in PORTS else ""})
        return out

    def _check_sunk(self, p, how, b=None):
        if b is not None:
            self._cripple(p, b)
        for sh in [sh for sh in p["ships"] if sh["hull"] <= 0]:
            # What she would have fetched in good repair, less the wreck's own value (which is nothing).
            self._book(p, "ships_lost", -SHIPS[sh["type"]]["price"] * R["fleet"]["ship_resale"]
                       - (sh["guns"] * R["fleet"]["gun_price"] + sh.get("cannons", 0) * cannon_price())
                       * R["fleet"]["gun_resale"])
            p["ships"].remove(sh)
            p["log"].append(tx("l.ship_lost", ship=SHIPS[sh["type"]]["name"], name=sh["name"], how=how))
            self._ev("voyage", "ship_lost", "{} lost the {} {} ({} guns, {} cannons): {}".format(
                p["name"], SHIPS[sh["type"]]["name"].lower(), sh["name"], sh["guns"], sh.get("cannons", 0), how), p,
                ship=sh["type"], name=sh["name"], guns=sh["guns"], cannons=sh.get("cannons", 0))
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

    def _cripple(self, p, b):
        """Escorts that would sink in a fight limp home crippled rules.fleet.cripple_chance of the time
        (Game 4 review, 20 Nov 2026): hull 1, every gun and cannon gone, out of the line for the rest of
        the fight. Mended at a shipyard for cripple_repair of a new one. Her own dice."""
        f = R["fleet"]
        chance = float(f.get("cripple_chance", 0.0))
        if chance <= 0:
            return
        for sh in p["ships"]:
            if sh["hull"] > 0 or role_of(sh["type"]) != "escort" or sh["name"] in (b.get("crippled") or ()):
                continue
            own = random.Random("cripple:{}:{}:{}:{}:{}".format(self.s.get("game_id", ""), self.s["turn"], p.get("id", ""),
                                                               sh["name"], b.get("step", 0)))
            if own.random() >= chance:
                continue
            lost = (sh.get("guns", 0) * f["gun_price"] + sh.get("cannons", 0) * cannon_price()) * f["gun_resale"]
            if lost:
                self._book(p, "ships_lost", -lost)
            sh["hull"], sh["guns"], sh["cannons"], sh["crippled"] = 1, 0, 0, True
            b.setdefault("crippled", []).append(sh["name"])
            b.setdefault("crippled_now", []).append(sh["name"])
            p["log"].append(tx("l.crippled", ship=SHIPS[sh["type"]]["name"], name=sh["name"]))
            self._ev("voyage", "ship_crippled", "{}: the {} {} limped out of the fight crippled (hull 1, guns gone)".format(
                p["name"], SHIPS[sh["type"]]["name"].lower(), sh["name"]), p, ship=sh["type"], name=sh["name"])

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
                              "host": q["id"] == host, "jailed": jail.jailed(q)})
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
                           "hold": ship_hold(sh),
                           "value": int(self.ship_value(sh)),
                           "repair": int(math.ceil(self.repair_need(p, sh) * self.repair_rate(p, sh))),
                           "needs_yard": self.repair_ceiling(p, sh) < SHIPS[sh["type"]]["hull"]
                           and sh["hull"] >= self.repair_ceiling(p, sh),
                           "wage": int(round(self.ship_wage(sh) * self.upkeep_rank_mult(p))),
                           "crippled": bool(sh.get("crippled"))}
                          for sh in p["ships"]],
                "laid_up": [{"type": sh["type"], "name": sh["name"], "hull": sh["hull"], "guns": sh["guns"],
                             "cannons": sh.get("cannons", 0), "role": role_of(sh["type"]), "hold": ship_hold(sh),
                             "wage": int(round(self.ship_wage(sh) * self.upkeep_rank_mult(p)
                                               * float(R["fleet"].get("laid_up_wage", 0.25)))),
                             "full_wage": int(round(self.ship_wage(sh) * self.upkeep_rank_mult(p)))}
                            for sh in p.get("laid_up") or ()],
                "idle": p.get("idle") or None,
                "fleet_ledger": self.fleet_ledger(p),
                "classes": self.fleet_classes(p), "fame": round(float(p.get("fame", 0) or 0), 2),
                "trade_down": self.trade_down_offer(p),
                "rep": {k: int(round(v)) for k, v in p["rep"].items()},
                "protect": p["protect"], "protect_cost": self.protection_cost(p),
                "loan_room": max(0, int(self.loan_limit(p) - p["debt"])),
                "collectors": self.collectors(p),
                "bankrupt": self.bankruptcy(p), "debt_cap": int(self.debt_cap(p) or 0),
                "ready": p["ready"], "dest": p["dest"], "orders": p["orders"],
                "log": p["log"], "known": p["known"],
                "tips": p.get("tips") or {},                 # the Registrar's prices: {port: {good: {turn, price}}}
                # The Registrar's hot tips still to come or still running (shown under Port > Arrival and the Price Book).
                "hot_tips": [t for t in (p.get("hot_tips") or []) if int(t.get("ends", -1)) >= s["turn"]],
                "prices": {g: round(v, 2) for g, v in s["prices"][port].items()},
                "basis": {g: round(v, 2) for g, v in (p.get("basis") or {}).items()},   # average paid per unit
                "rot": rot.view(p),   # perishables aboard: months aged and the grace period (rot.py)
                "spread": round(sp, 4),
                "purse": self.purse_view(port),             # the dealers' purse here: {good: [left, size]}
                "dues": self.dues(p), "slip": bool(p.get("slip")), "slip_quote": self.slip_quote(p),
                "customs": self.customs_view(p), "bond": self.sealed(p),
                "battle": self.battle_view(p), "fights": p.get("fights") or [],
                "books": self.books_view(p),
                "gift": self.gift_view(p),
                "market": self.market_view(p),
                "shares": self.shares_view(p), "estate": self.estate_view(p),
                "commissions": self.contracts_view(p),
                # Reputation swings (rules.standing): what the band here does, recent band moves for the
                # popup, and a private lot if one is on offer.
                "band": dict(self.band_effects(p, port), yard_mult=round(self.yard_mult(p), 4),
                             on=self.standing_on()),
                "bands": [dict(e) for e in (p.get("bands") or [])] if (self.standing_on() and self.standing_popup_on()) else [],
                "lot": self.lot_view(p),
                "jail": jail.view(self, p),
                "storm": storm.view(self, p),
                "legend": legend.view(self, p), "legends": legend.book(self, p),   # the Legend on screen; those met
                "counter": counter.view(self, p),    # Under the Counter: the tax lady's paid tips
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
                       "spread_swing": R["market"]["spread_swing"],
                       "hot_min": float((R.get("registrar") or {}).get("hot_min", 3.0)),
                       "avg_amber": float(R["market"].get("avg_amber", 1.5)),
                       "avg_red": float(R["market"].get("avg_red", 2.5)),
                       "purse_over": float(R["market"].get("purse_over", 0.35)) if R["market"].get("purse_enabled", True) else None},
            "gun_price": f["gun_price"], "max_fleet": f["max_fleet"],
            "fleet_rules": {r: {"max": role_limit(r), "unlock": role_unlock(r)} for r in ROLES},
            "keep_trader": bool(f.get("keep_trader", True)),
            "laid_up_wage": float(f.get("laid_up_wage", 0.25)), "idle_note_min": int(f.get("idle_note_min", 1000)),
            "idle_note_share": float(f.get("idle_note_share", 0.25)),
            "gun_resale": f["gun_resale"], "cannon_price": cannon_price(), "cannon_power": cannon_power(),
            "gun_hold": gun_hold(), "cannon_hold": cannon_hold(),
            "cannon_slots": cannon_slots(),
            "loan_rate": loan_rate(), "bank_rate": R["bank"]["bank_rate"], "home": HOME,
            "mug": {k: R["bank"].get(k, 0) for k in ("mug_threshold", "mug_chance", "mug_rep", "mug_min", "mug_max")},
            "impact": R["market"]["impact"], "lengths": R["game"]["lengths"],
            "start_year": R["game"]["start_year"], "renew_at": R["liyuen"]["renew_at"],
            "ban_price_mult": R["events"]["ban_price_mult"],
            "dues_rules": {k: R["dues"][k] for k in ("slip_base", "slip_mult", "slip_rep")},
            "forecast_accuracy": R["weather"]["forecast_accuracy"],
            "brand": b, "graphics": CFG["graphics"], "colors": CFG["theme"]["player_colors"],
            "ranks": CFG["ranks"], "promotion_styles": _config.promotion_styles(),
            "rating": CFG["content"]["rating"],
            "difficulty": MULT.get("name", ""), "yards": [p["name"] for p in PORTS.values() if p["shipyard"]],
            "tokens": TOKENS, "text": TEXT, "lang": CFG["language"]["active"]}


configure()
