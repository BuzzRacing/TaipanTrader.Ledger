"""SeaTrader game engine.

Pure game rules with no networking or file access. All state lives in one
JSON-serialisable dict (Game.s) so saving and loading is trivial.

One turn is one month. Every player does port business at the same time, then
picks a destination (or stays). When everyone has set sail the world advances:
voyages resolve, interest accrues, markets move and the weather changes.
"""
import math
import random
import secrets

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
START_YEAR = 1860
HOME = "hongkong"

# base = typical price per unit; vol = monthly volatility;
# depth = units that move the local price by roughly 25%.
GOODS = {
    "opium":     {"name": "Opium",         "base": 4200, "vol": 0.16, "depth": 60, "contraband": True},
    "silk":      {"name": "Silk",          "base": 520,  "vol": 0.10, "depth": 160},
    "porcelain": {"name": "Porcelain",     "base": 230,  "vol": 0.08, "depth": 250},
    "arms":      {"name": "Arms",          "base": 160,  "vol": 0.10, "depth": 250},
    "spices":    {"name": "Spices",        "base": 95,   "vol": 0.09, "depth": 450},
    "tea":       {"name": "Tea",           "base": 70,   "vol": 0.08, "depth": 500},
    "rice":      {"name": "Rice",          "base": 14,   "vol": 0.07, "depth": 1200},
    "general":   {"name": "General Cargo", "base": 9,    "vol": 0.07, "depth": 1200},
}

REGIONS = {
    "north":  "Yellow Sea & Japan",
    "china":  "South China Sea",
    "south":  "Straits & Java Sea",
    "bengal": "Bay of Bengal",
}

# lon/lat are used by the chart; x/y are derived from them in _project().
# mods = local price multipliers (below 1 = produced here, above 1 = in demand).
PORTS = {
    "hongkong":  {"name": "Hong Kong", "lon": 114.2, "lat": 22.3, "region": "china", "shipyard": True,
                  "mods": {"arms": 0.8, "tea": 0.9, "general": 0.85}},
    "shanghai":  {"name": "Shanghai",  "lon": 121.5, "lat": 31.2, "region": "north", "shipyard": True,
                  "mods": {"silk": 0.6, "tea": 0.6, "opium": 1.35, "arms": 1.3, "spices": 1.3}},
    "nagasaki":  {"name": "Nagasaki",  "lon": 129.9, "lat": 32.75, "region": "north", "shipyard": False,
                  "mods": {"porcelain": 0.6, "silk": 0.85, "arms": 1.5, "spices": 1.4, "rice": 1.3, "opium": 1.2}},
    "manila":    {"name": "Manila",    "lon": 121.0, "lat": 14.6, "region": "china", "shipyard": False,
                  "mods": {"general": 0.75, "rice": 0.9, "spices": 0.9, "silk": 1.3, "porcelain": 1.3, "tea": 1.2}},
    "saigon":    {"name": "Saigon",    "lon": 106.7, "lat": 10.8, "region": "china", "shipyard": False,
                  "mods": {"rice": 0.55, "spices": 0.85, "arms": 1.3, "porcelain": 1.25, "general": 1.2}},
    "bangkok":   {"name": "Bangkok",   "lon": 100.5, "lat": 13.75, "region": "south", "shipyard": False,
                  "mods": {"rice": 0.6, "spices": 0.8, "silk": 1.25, "arms": 1.2, "tea": 1.2}},
    "singapore": {"name": "Singapore", "lon": 103.8, "lat": 1.35, "region": "south", "shipyard": True,
                  "mods": {"arms": 0.85, "general": 0.8, "opium": 0.85, "tea": 1.4, "silk": 1.35, "porcelain": 1.3}},
    "batavia":   {"name": "Batavia",   "lon": 106.8, "lat": -6.2, "region": "south", "shipyard": False,
                  "mods": {"spices": 0.5, "rice": 1.2, "tea": 1.3, "silk": 1.4, "arms": 1.25,
                           "porcelain": 1.35, "general": 1.3}},
    "calcutta":  {"name": "Calcutta",  "lon": 88.4,  "lat": 22.6, "region": "bengal", "shipyard": True,
                  "mods": {"opium": 0.55, "tea": 0.8, "general": 0.9, "rice": 0.9, "silk": 1.3,
                           "spices": 1.3, "porcelain": 1.5}},
}


def _project(lon, lat):
    """Chart projection shared with the browser (1000 x 600 chart)."""
    return (lon - 85.0) / 50.0 * 1000.0, (35.0 - lat) / 45.0 * 600.0


for _p in PORTS.values():
    _p["x"], _p["y"] = [round(v, 1) for v in _project(_p["lon"], _p["lat"])]

# hold = cargo units; hull = damage it can take; slots = guns it can mount.
SHIPS = {
    "junk":      {"name": "Junk",          "hold": 60,  "hull": 100, "slots": 4,  "price": 3000,  "fast": False},
    "lorcha":    {"name": "Lorcha",        "hold": 120, "hull": 140, "slots": 8,  "price": 9000,  "fast": False},
    "barque":    {"name": "Barque",        "hold": 250, "hull": 200, "slots": 12, "price": 22000, "fast": False},
    "clipper":   {"name": "Clipper",       "hold": 180, "hull": 160, "slots": 10, "price": 35000, "fast": True},
    "indiaman":  {"name": "East Indiaman", "hold": 500, "hull": 320, "slots": 24, "price": 80000, "fast": False},
}
MAX_FLEET = 5
GUN_PRICE = 600
WAREHOUSE_CAP = 10000
BANK_RATE = 0.005      # per month
LOAN_RATE = 0.06       # per month, compounding
PROTECTION_MONTHS = 8
WEATHER = ["Calm", "Fair", "Squalls", "Typhoon"]
SHIP_NAMES = ["Morning Cloud", "Jade Heron", "Lucky Star", "Sea Witch", "Golden Carp", "Lady Hughes",
              "Red Rover", "Water Dragon", "Flying Cloud", "Pearl of Canton", "Falcon", "Nemesis",
              "Lotus Wind", "Black Joke", "Sylph", "Cowasjee", "Ariel", "Taeping", "Fiery Cross",
              "Mandarin", "Eastern Queen", "Kestrel", "Tiger Tail", "Silver Moon", "Antelope"]


class GameError(Exception):
    """A rule was broken; the message is shown to the player."""


def money(n):
    return "${:,}".format(int(round(n)))


def date_label(turn):
    return "{} {}".format(MONTHS[turn % 12], START_YEAR + turn // 12)


def distance(a, b):
    pa, pb = PORTS[a], PORTS[b]
    return math.hypot(pa["x"] - pb["x"], pa["y"] - pb["y"])


class Game:
    def __init__(self, state=None, seed=None):
        self.rng = random.Random(seed)
        self.s = state if state else self._new_state()

    # ------------------------------------------------------------ setup --
    def _new_state(self):
        s = {"phase": "lobby", "turn": 0, "years": 5, "players": {}, "order": [],
             "prices": {}, "shocks": [], "crackdown": {}, "weather": {}, "news": [],
             "next_id": 1}
        self.s = s
        for port in PORTS:
            s["prices"][port] = {}
            for g in GOODS:
                s["prices"][port][g] = self._target(port, g) * self.rng.uniform(0.85, 1.15)
        self._roll_weather()
        s["news"] = ["The trading season opens. Hong Kong harbour is crowded with ships."]
        return s

    def _target(self, port, good):
        t = GOODS[good]["base"] * PORTS[port]["mods"].get(good, 1.0)
        for sh in self.s["shocks"]:
            if sh["port"] == port and sh["good"] == good:
                t *= sh["mult"]
        if good == "opium" and port in self.s["crackdown"]:
            t *= 1.5
        return t

    def _roll_region(self, region, month):
        """Weather level 0-3 for a region in a given month (0 = January)."""
        typhoon, squalls = 0.02, 0.20
        if region in ("north", "china"):
            if 5 <= month <= 9:           # Jun-Oct typhoon season
                typhoon, squalls = 0.18, 0.30
        elif region == "south":
            typhoon, squalls = 0.01, 0.25
            if month >= 10 or month <= 2:  # north-east monsoon
                squalls = 0.40
        elif region == "bengal":
            if month in (3, 4, 9, 10):     # cyclone seasons
                typhoon, squalls = 0.15, 0.30
        r = self.rng.random()
        if r < typhoon:
            return 3
        if r < typhoon + squalls:
            return 2
        return 1 if self.rng.random() < 0.6 else 0

    def _roll_weather(self):
        month = self.s["turn"] % 12
        self.s["weather"] = {r: self._roll_region(r, month) for r in REGIONS}

    # ---------------------------------------------------------- players --
    def join(self, name, firm, present=()):
        """Join the game, or take back your seat by name from a new device or address."""
        s = self.s
        name = " ".join(str(name or "").split())[:20]
        firm = " ".join(str(firm or "").split())[:28]
        if not name:
            raise GameError("Enter your name.")
        if not firm:
            firm = name + " & Co."
        for p in s["players"].values():
            if p["name"].lower() == name.lower():
                if p["id"] in present:
                    raise GameError("{} is playing on another device right now. Close that screen, "
                                    "wait half a minute and try again, or pick another name.".format(p["name"]))
                return p["token"]
        if s["phase"] == "ended":
            raise GameError("This game has ended. Start a new game to play again.")
        if len(s["players"]) >= 8:
            raise GameError("This game is full (8 players).")
        pid = "p{}".format(s["next_id"])
        s["next_id"] += 1
        p = {"id": pid, "name": name, "firm": firm, "token": secrets.token_urlsafe(16),
             "color": (len(s["order"])) % 8, "port": HOME,
             "cash": 3500.0, "bank": 0.0, "debt": 5000.0,
             "cargo": {}, "wh": {},
             "ships": [self._new_ship("junk", guns=2)],
             "rep": {port: 50.0 for port in PORTS},
             "protect": 0, "ready": False, "dest": None, "orders": "fight",
             "log": ["You arrive in Hong Kong with one junk, {} in silver and a {} debt to "
                     "Elder Brother Wu.".format(money(3500), money(5000))],
             "known": {}, "wrecks": 0}
        p["rep"][HOME] = 60.0
        s["players"][pid] = p
        s["order"].append(pid)
        self._note_prices(p)
        return p["token"]

    def _new_ship(self, kind, guns=0, hull=None):
        used = {sh["name"] for p in self.s["players"].values() for sh in p["ships"]}
        free = [n for n in SHIP_NAMES if n not in used] or SHIP_NAMES
        return {"type": kind, "name": self.rng.choice(free),
                "hull": SHIPS[kind]["hull"] if hull is None else hull, "guns": guns}

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
        """Dealer's margin: 7% for a stranger, 1% for a trusted house."""
        return 0.04 - 0.03 * (p["rep"][port] - 50.0) / 50.0

    def quote(self, p, good, qty, side):
        """Total silver for buying or selling qty units where the player is."""
        port = p["port"]
        mid = self.s["prices"][port][good]
        k = 0.25 * qty / GOODS[good]["depth"]
        if side == "buy":
            end = mid * (1 + k)
            return int(math.ceil(qty * (mid + end) / 2 * (1 + self.spread(p, port)))), end
        end = mid / (1 + k)
        return int(math.floor(qty * (mid + end) / 2 * (1 - self.spread(p, port)))), end

    def ship_value(self, sh):
        spec = SHIPS[sh["type"]]
        return 0.5 * spec["price"] * max(sh["hull"], 0) / spec["hull"] + sh["guns"] * GUN_PRICE / 3

    def worth(self, p):
        hk = self.s["prices"][HOME]
        goods = sum(q * hk[g] for g, q in p["cargo"].items())
        goods += sum(q * hk[g] for g, q in p["wh"].items())
        ships = sum(self.ship_value(sh) for sh in p["ships"])
        return p["cash"] + p["bank"] - p["debt"] + 0.9 * goods + ships

    def loan_limit(self, p):
        assets = p["cash"] + p["bank"] + sum(self.ship_value(sh) for sh in p["ships"])
        return 5000 + 100 * p["rep"][HOME] + 0.5 * max(assets, 0)

    def repair_rate(self, p, sh):
        port = PORTS[p["port"]]
        rate = 6 + SHIPS[sh["type"]]["price"] / 4000.0
        if not port["shipyard"]:
            rate *= 1.3
        return rate * (1 - 0.2 * (p["rep"][p["port"]] - 50.0) / 50.0)

    def protection_cost(self, p):
        return int(max(500, 0.06 * self.worth(p)))

    def _gain_rep(self, p, port, amount):
        p["rep"][port] = max(0.0, min(100.0, p["rep"][port] + amount))

    def _note_prices(self, p):
        port = p["port"]
        p["known"][port] = {"turn": self.s["turn"],
                            "prices": {g: int(round(v)) for g, v in self.s["prices"][port].items()}}

    # ---------------------------------------------------------- actions --
    def act(self, pid, a, present=()):
        """Apply one player action. Returns a short confirmation message."""
        s = self.s
        p = s["players"].get(pid)
        if p is None:
            raise GameError("You are not in this game.")
        kind = a.get("type")
        is_host = pid == self.host_id(set(present) | {pid})

        if kind == "settings":
            if not is_host or s["phase"] != "lobby":
                raise GameError("Only the host can change settings, before the game starts.")
            years = int(a.get("years", 5))
            if years not in (1, 2, 3, 5, 10):
                raise GameError("Choose 1, 2, 3, 5 or 10 years.")
            s["years"] = years
            return "Game length set to {} years.".format(years)
        if kind == "start":
            if not is_host or s["phase"] != "lobby":
                raise GameError("Only the host can start the game.")
            s["phase"] = "port"
            s["news"].insert(0, "{}: {} trading house{} open for business.".format(
                date_label(0), len(s["players"]), "s" if len(s["players"]) != 1 else ""))
            return "The game begins."
        if kind == "force":
            if not is_host or s["phase"] != "port":
                raise GameError("Only the host can end the turn.")
            self.resolve()
            return "Turn ended by the host."

        if s["phase"] != "port":
            raise GameError("The game is not in progress.")
        if kind == "unsail":
            p["ready"], p["dest"] = False, None
            return "Orders cancelled. You are back in port."
        if p["ready"]:
            raise GameError("You have already given sailing orders. Cancel them to keep trading.")

        handler = getattr(self, "_act_" + str(kind), None)
        if handler is None:
            raise GameError("Unknown action.")
        return handler(p, a)

    @staticmethod
    def _qty(a, key="qty"):
        try:
            q = int(a.get(key, 0))
        except (TypeError, ValueError):
            raise GameError("Enter a whole number.")
        if q <= 0 or q > 10_000_000:
            raise GameError("Enter a quantity above zero.")
        return q

    @staticmethod
    def _good(a):
        g = a.get("good")
        if g not in GOODS:
            raise GameError("Unknown cargo.")
        return g

    def _act_buy(self, p, a):
        g, q = self._good(a), self._qty(a)
        if self.used(p) + q > self.capacity(p):
            raise GameError("Not enough room in the hold ({} free).".format(self.capacity(p) - self.used(p)))
        cost, end = self.quote(p, g, q, "buy")
        if cost > p["cash"]:
            raise GameError("That costs {} and you have {} on hand.".format(money(cost), money(p["cash"])))
        p["cash"] -= cost
        p["cargo"][g] = p["cargo"].get(g, 0) + q
        self.s["prices"][p["port"]][g] = end
        self._gain_rep(p, p["port"], min(2.0, cost / 5000.0))
        return "Bought {} {} for {}.".format(q, GOODS[g]["name"], money(cost))

    def _act_sell(self, p, a):
        g, q = self._good(a), self._qty(a)
        if p["cargo"].get(g, 0) < q:
            raise GameError("You only have {} {} aboard.".format(p["cargo"].get(g, 0), GOODS[g]["name"]))
        gain, end = self.quote(p, g, q, "sell")
        p["cash"] += gain
        p["cargo"][g] -= q
        if not p["cargo"][g]:
            del p["cargo"][g]
        self.s["prices"][p["port"]][g] = end
        self._gain_rep(p, p["port"], min(2.0, gain / 5000.0))
        return "Sold {} {} for {}.".format(q, GOODS[g]["name"], money(gain))

    def _home_only(self, p, what):
        if p["port"] != HOME:
            raise GameError("{} is only in Hong Kong.".format(what))

    def _act_bank(self, p, a):
        self._home_only(p, "The bank")
        q = self._qty(a, "amount")
        if a.get("op") == "deposit":
            q = min(q, int(p["cash"]))
            if q <= 0:
                raise GameError("You have no silver on hand to deposit.")
            p["cash"] -= q
            p["bank"] += q
            return "Deposited {}.".format(money(q))
        q = min(q, int(p["bank"]))
        if q <= 0:
            raise GameError("Your account is empty.")
        p["bank"] -= q
        p["cash"] += q
        return "Withdrew {}.".format(money(q))

    def _act_loan(self, p, a):
        self._home_only(p, "Elder Brother Wu")
        q = self._qty(a, "amount")
        if a.get("op") == "borrow":
            room = int(self.loan_limit(p) - p["debt"])
            if room <= 0:
                raise GameError("Elder Brother Wu will lend you nothing more.")
            q = min(q, room)
            p["debt"] += q
            p["cash"] += q
            return "Borrowed {} at {:.0f}% a month.".format(money(q), LOAN_RATE * 100)
        q = min(q, int(math.ceil(p["debt"])), int(p["cash"]))
        if q <= 0:
            raise GameError("Nothing to repay, or no silver on hand.")
        p["debt"] = max(0.0, p["debt"] - q)
        p["cash"] -= q
        if p["debt"] < 1:
            p["debt"] = 0.0
        return "Repaid {}.".format(money(q))

    def _act_warehouse(self, p, a):
        self._home_only(p, "Your warehouse")
        g, q = self._good(a), self._qty(a)
        if a.get("op") == "store":
            q = min(q, p["cargo"].get(g, 0), WAREHOUSE_CAP - sum(p["wh"].values()))
            if q <= 0:
                raise GameError("Nothing to store, or the warehouse is full.")
            p["cargo"][g] -= q
            if not p["cargo"][g]:
                del p["cargo"][g]
            p["wh"][g] = p["wh"].get(g, 0) + q
            return "Stored {} {}.".format(q, GOODS[g]["name"])
        q = min(q, p["wh"].get(g, 0), self.capacity(p) - self.used(p))
        if q <= 0:
            raise GameError("Nothing to load, or no room in the hold.")
        p["wh"][g] -= q
        if not p["wh"][g]:
            del p["wh"][g]
        p["cargo"][g] = p["cargo"].get(g, 0) + q
        return "Loaded {} {}.".format(q, GOODS[g]["name"])

    def _act_buy_ship(self, p, a):
        kind = a.get("ship")
        if kind not in SHIPS:
            raise GameError("Unknown ship.")
        if not PORTS[p["port"]]["shipyard"]:
            raise GameError("There is no shipyard in {}.".format(PORTS[p["port"]]["name"]))
        if len(p["ships"]) >= MAX_FLEET:
            raise GameError("Your fleet is at its limit of {} ships.".format(MAX_FLEET))
        price = SHIPS[kind]["price"]
        if price > p["cash"]:
            raise GameError("A {} costs {}.".format(SHIPS[kind]["name"], money(price)))
        p["cash"] -= price
        sh = self._new_ship(kind)
        p["ships"].append(sh)
        self._gain_rep(p, p["port"], 2.0)
        return "The {} '{}' joins your fleet.".format(SHIPS[kind]["name"], sh["name"])

    def _ship(self, p, a):
        try:
            return p["ships"][int(a.get("index"))]
        except (TypeError, ValueError, IndexError):
            raise GameError("No such ship.")

    def _act_sell_ship(self, p, a):
        sh = self._ship(p, a)
        if not PORTS[p["port"]]["shipyard"]:
            raise GameError("There is no shipyard in {}.".format(PORTS[p["port"]]["name"]))
        if len(p["ships"]) <= 1:
            raise GameError("You cannot sell your last ship.")
        if self.capacity(p) - SHIPS[sh["type"]]["hold"] < self.used(p):
            raise GameError("Unload cargo first; the rest of the fleet cannot carry it.")
        value = int(self.ship_value(sh))
        p["ships"].remove(sh)
        p["cash"] += value
        return "Sold the '{}' for {}.".format(sh["name"], money(value))

    def _act_buy_gun(self, p, a):
        sh = self._ship(p, a)
        if sh["guns"] >= SHIPS[sh["type"]]["slots"]:
            raise GameError("The '{}' can mount no more guns.".format(sh["name"]))
        if GUN_PRICE > p["cash"]:
            raise GameError("A gun costs {}.".format(money(GUN_PRICE)))
        p["cash"] -= GUN_PRICE
        sh["guns"] += 1
        return "Mounted a gun on the '{}'.".format(sh["name"])

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
            raise GameError("Nothing to repair, or not enough silver.")
        p["cash"] = max(0.0, p["cash"] - spent)
        return "Repairs done for {}.".format(money(spent))

    def _act_protection(self, p, a):
        self._home_only(p, "Li Yuen's agent")
        if p["protect"] > 2:
            raise GameError("Li Yuen is content for now ({} months left).".format(p["protect"]))
        cost = self.protection_cost(p)
        if cost > p["cash"]:
            raise GameError("Li Yuen asks {} and you cannot pay it.".format(money(cost)))
        p["cash"] -= cost
        p["protect"] = PROTECTION_MONTHS
        return "Paid {} to Li Yuen. His fleets will leave you be for {} months.".format(
            money(cost), PROTECTION_MONTHS)

    def _act_sail(self, p, a):
        dest = a.get("dest")
        if dest is not None and dest not in PORTS:
            raise GameError("Unknown port.")
        if dest == p["port"]:
            dest = None
        orders = a.get("orders", p["orders"])
        if orders not in ("fight", "run"):
            raise GameError("Orders must be fight or run.")
        p["orders"], p["dest"], p["ready"] = orders, dest, True
        if dest:
            return "Orders given: sail for {}.".format(PORTS[dest]["name"])
        return "Orders given: remain at anchor this month."

    # ------------------------------------------------------ turn engine --
    def maybe_advance(self, present):
        """Advance when every connected player has given orders."""
        s = self.s
        if s["phase"] != "port":
            return False
        here = [s["players"][pid] for pid in s["order"] if pid in present]
        if here and all(p["ready"] for p in here):
            self.resolve()
            return True
        return False

    def resolve(self):
        s, rng = self.s, self.rng
        news = []
        label = date_label(s["turn"])
        # The forecast is right four times in five.
        actual = dict(s["weather"])
        for region in actual:
            if rng.random() < 0.2:
                actual[region] = self._roll_region(region, s["turn"] % 12)
        players = [s["players"][pid] for pid in s["order"]]
        rng.shuffle(players)
        for p in players:
            p["log"] = []
            if p["ready"] and p["dest"]:
                self._voyage(p, actual, news)
            else:
                p["log"].append("You remained at anchor in {}.".format(PORTS[p["port"]]["name"]))
            p["ready"], p["dest"] = False, None

        for p in players:
            if p["bank"] > 0:
                p["bank"] *= 1 + BANK_RATE
            if p["debt"] > 0:
                p["debt"] *= 1 + LOAN_RATE
                if p["debt"] > self.loan_limit(p) * 1.5:
                    self._gain_rep(p, HOME, -3)
                    p["log"].append("Elder Brother Wu's collectors are asking about you. "
                                    "Your name suffers in Hong Kong.")
            if p["protect"] > 0:
                p["protect"] -= 1
                if p["protect"] == 0:
                    p["log"].append("Your arrangement with Li Yuen has lapsed.")
            if p["cash"] > 20000 and rng.random() < 0.06:
                lost = int(p["cash"] * rng.uniform(0.15, 0.35))
                p["cash"] -= lost
                p["log"].append("You were beaten and robbed of {} in the street. "
                                "Silver is safer in the bank.".format(money(lost)))

        self._move_markets(news)
        s["turn"] += 1
        self._roll_weather()
        for p in players:
            self._note_prices(p)
        stamp = date_label(s["turn"])
        s["news"] = ["{}: {}".format(label, n) for n in news] + s["news"]
        s["news"] = s["news"][:40]
        if s["turn"] >= s["years"] * 12:
            s["phase"] = "ended"
            ranked = sorted(players, key=self.worth, reverse=True)
            if ranked:
                s["news"].insert(0, "{}: The game is over. {} of {} is Taipan, worth {}.".format(
                    stamp, ranked[0]["name"], ranked[0]["firm"], money(self.worth(ranked[0]))))

    def _move_markets(self, news):
        s, rng = self.s, self.rng
        s["shocks"] = [dict(sh, turns=sh["turns"] - 1) for sh in s["shocks"] if sh["turns"] > 1]
        for port in list(s["crackdown"]):
            s["crackdown"][port] -= 1
            if s["crackdown"][port] <= 0:
                del s["crackdown"][port]
                news.append("The opium ban in {} has been lifted.".format(PORTS[port]["name"]))
        if rng.random() < 0.35:
            port, good = rng.choice(list(PORTS)), rng.choice(list(GOODS))
            mult = rng.choice([0.4, 0.5, 2.0, 2.5, 3.0])
            s["shocks"].append({"port": port, "good": good, "mult": mult, "turns": rng.randint(2, 3)})
            s["prices"][port][good] *= mult ** 0.7
            if mult > 1:
                news.append("{} is scarce in {} and merchants are paying dearly.".format(
                    GOODS[good]["name"], PORTS[port]["name"]))
            else:
                news.append("A glut of {} in {} has sent prices tumbling.".format(
                    GOODS[good]["name"].lower(), PORTS[port]["name"]))
        if rng.random() < 0.15:
            port = rng.choice([k for k in PORTS if k != "calcutta" and k not in s["crackdown"]])
            s["crackdown"][port] = rng.randint(3, 5)
            news.append("The authorities in {} have banned opium. Ships are being searched.".format(
                PORTS[port]["name"]))
        for port in PORTS:
            for g, spec in GOODS.items():
                base = spec["base"] * PORTS[port]["mods"].get(g, 1.0)
                price = s["prices"][port][g]
                price += 0.3 * (self._target(port, g) - price)
                price *= math.exp(rng.gauss(0, spec["vol"]))
                s["prices"][port][g] = max(0.25 * base, min(4.5 * base, price))

    # ---------------------------------------------------------- voyages --
    def _voyage(self, p, actual, news):
        rng, log = self.rng, p["log"]
        origin, dest = p["port"], p["dest"]
        risk = max(0.6, min(1.8, distance(origin, dest) / 350.0))
        level = max(actual[PORTS[origin]["region"]], actual[PORTS[dest]["region"]])
        log.append("You sailed from {} for {} {}.".format(
            PORTS[origin]["name"], PORTS[dest]["name"],
            ["on a calm sea", "in fair weather", "through squalls", "into a typhoon"][level]))

        storm = {0: 0.0, 1: 0.04, 2: 0.20, 3: 0.60}[level] * min(risk, 1.4)
        if rng.random() < storm:
            lo, hi = (20, 60) if level == 3 else (5, 20)
            for sh in p["ships"]:
                hit = rng.randint(lo, hi)
                sh["hull"] -= int(hit * 0.8) if SHIPS[sh["type"]]["fast"] else hit
            log.append("A {} caught the fleet at sea and battered your ships.".format(
                "typhoon" if level == 3 else "storm"))
            self._check_sunk(p, "foundered in the storm")
            if p["ships"] and level == 3 and rng.random() < 0.15:
                dest = rng.choice([k for k in PORTS if k not in (origin, dest)])
                log.append("You were blown far off course and made port in {} instead.".format(
                    PORTS[dest]["name"]))

        if p["ships"] and rng.random() < 0.18 * risk:
            n = int(rng.randint(2, 4 + self.capacity(p) // 40) * risk)
            n = max(1, min(n, 40))
            if p["protect"] > 0 and rng.random() < 0.5:
                log.append("{} pirate junks closed in, but Li Yuen's fleet drove them off.".format(n))
            else:
                self._battle(p, n, "pirate junks", 0.30, (4, 14))

        if p["ships"] and p["protect"] <= 0 and rng.random() < 0.06 * risk:
            n = min(60, 6 + self.capacity(p) // 25)
            log.append("Li Yuen's fleet found you. You have paid him no tribute.")
            self._battle(p, n, "of Li Yuen's war junks", 0.40, (8, 20))

        if not p["ships"]:
            self._shipwreck(p, news)
            return

        p["port"] = dest
        log.append("You dropped anchor in {}.".format(PORTS[dest]["name"]))
        opium = p["cargo"].get("opium", 0)
        if opium:
            banned = dest in self.s["crackdown"]
            chance = (0.55 - 0.003 * p["rep"][dest]) if banned else 0.03
            if rng.random() < chance:
                fine = int(min(p["cash"], opium * 300))
                del p["cargo"]["opium"]
                p["cash"] -= fine
                self._gain_rep(p, dest, -15)
                log.append("Customs officers searched the fleet, seized {} chests of opium "
                           "and fined you {}.".format(opium, money(fine)))
                news.append("{} of {} was caught landing opium in {}.".format(
                    p["name"], p["firm"], PORTS[dest]["name"]))

    def _battle(self, p, n, label, hit, dmg):
        rng, log = self.rng, p["log"]
        orders = p["orders"]
        if orders == "fight" and self.guns(p) == 0:
            orders = "run"
            log.append("{} {} attacked. With no guns aboard, you could only run.".format(n, label))
        else:
            log.append("{} {} attacked. Your orders were to {}.".format(n, label, orders))
        pirates = [2] * n
        fast = all(SHIPS[sh["type"]]["fast"] for sh in p["ships"])
        hull_before = sum(sh["hull"] for sh in p["ships"])
        for rnd in range(1, 7):
            if orders == "fight":
                for _ in range(self.guns(p)):
                    if pirates and rng.random() < 0.4:
                        pirates[-1] -= 1
                        if pirates[-1] <= 0:
                            pirates.pop()
                if not pirates:
                    booty = int(n * rng.randint(150, 500) * (1 + self.s["turn"] / 24.0))
                    p["cash"] += booty
                    log.append("You sank all {} in {} round{} and took {} in booty.".format(
                        n, rnd, "" if rnd == 1 else "s", money(booty)))
                    break
            elif rng.random() < 0.35 + (0.2 if fast else 0) + 0.05 * rnd:
                log.append("You outran them after {} round{} of fire.".format(rnd, "" if rnd == 1 else "s"))
                pirates = []
                break
            for _ in pirates:
                if p["ships"] and rng.random() < hit:
                    rng.choice(p["ships"])["hull"] -= rng.randint(*dmg)
            self._check_sunk(p, "was sunk")
            if not p["ships"]:
                return
        else:
            if orders == "fight":
                log.append("After a long fight you sank {} of them and the rest broke off.".format(
                    n - len(pirates)))
            else:
                lost = {g: int(q * rng.uniform(0.25, 0.5)) for g, q in p["cargo"].items()}
                for g, q in lost.items():
                    p["cargo"][g] -= q
                p["cargo"] = {g: q for g, q in p["cargo"].items() if q > 0}
                log.append("They ran you down, boarded and plundered {} units of cargo.".format(
                    sum(lost.values())))
        taken = hull_before - sum(sh["hull"] for sh in p["ships"])
        if taken > 0 and p["ships"]:
            log.append("Your surviving ships took {} points of damage.".format(taken))

    def _check_sunk(self, p, how):
        for sh in [sh for sh in p["ships"] if sh["hull"] <= 0]:
            p["ships"].remove(sh)
            p["log"].append("The {} '{}' {}.".format(SHIPS[sh["type"]]["name"], sh["name"], how))
        over = self.used(p) - self.capacity(p)
        if over > 0 and p["ships"]:
            # The crew saves the most valuable cargo first.
            for g in sorted(p["cargo"], key=lambda k: GOODS[k]["base"]):
                drop = min(over, p["cargo"][g])
                p["cargo"][g] -= drop
                over -= drop
                if over <= 0:
                    break
            p["cargo"] = {g: q for g, q in p["cargo"].items() if q > 0}
            p["log"].append("Cargo went down with her; the fleet could not carry it all.")

    def _shipwreck(self, p, news):
        lost = int(p["cash"] * 0.5)
        p["cargo"] = {}
        p["cash"] -= lost
        p["debt"] += 1500
        p["port"] = HOME
        p["wrecks"] += 1
        p["ships"] = [self._new_ship("junk", guns=0, hull=60)]
        p["log"].append("Your last ship went down. A passing clipper pulled you from the sea and "
                        "landed you in Hong Kong. Cargo and {} in silver were lost. Elder Brother Wu "
                        "has advanced you a battered junk, adding {} to your debt.".format(
                            money(lost), money(1500)))
        news.append("{} of {} lost the whole fleet at sea and was carried home to Hong Kong.".format(
            p["name"], p["firm"]))

    # ------------------------------------------------------------- view --
    def view(self, pid, present=()):
        """Everything one screen needs. pid=None gives the public harbor board."""
        s = self.s
        present = set(present)
        host = self.host_id(present)
        standings = []
        for q in (s["players"][i] for i in s["order"]):
            standings.append({"id": q["id"], "name": q["name"], "firm": q["firm"], "color": q["color"],
                              "port": q["port"], "ready": q["ready"], "present": q["id"] in present,
                              "worth": int(self.worth(q)), "ships": len(q["ships"]),
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
            out["me"] = {
                "id": p["id"], "name": p["name"], "firm": p["firm"], "color": p["color"],
                "host": p["id"] == host, "port": port,
                "cash": int(p["cash"]), "bank": int(p["bank"]), "debt": int(math.ceil(p["debt"])),
                "worth": int(self.worth(p)),
                "cargo": p["cargo"], "wh": p["wh"], "wh_cap": WAREHOUSE_CAP,
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


def static_data():
    """Reference data the browser needs once."""
    return {"goods": GOODS, "ports": PORTS, "ships": SHIPS, "regions": REGIONS,
            "weather": WEATHER, "gun_price": GUN_PRICE, "max_fleet": MAX_FLEET,
            "loan_rate": LOAN_RATE, "bank_rate": BANK_RATE, "home": HOME}
