"""Storms and damage (20 Nov 2026, planned with Anthony one decision at a time; project doc
"SeaTrader Storms and Damage").

A storm that catches the fleet at sea gets a severity score and lands in a band:

  Rough   scuffed: a little hull, nothing else; a banner and a log line, no detour.
  Heavy   hull, cargo and guns lost; the fleet is sent to the MIDDLE-ranked of the nearest ports that have
          a shipyard, so it can mend and regather.
  Savage  much more of each; the fleet is sent to the WORST-ranked of the nearest ports for the cargo left
          in the hold, and a bad port is one with no shipyard.

Heavy and Savage storms put the storm screen (web/storm.js) in front of the Captain: Roxana, battered, in
front of a broken ship, with the damage ledger. Tap "Make port" to go on.

Severity = sea x dice x distance x hold load x hull already lost x guns carried x difficulty, all from
rules.storm (Admin > Weather & Seas) with DEFAULTS as the fallback. A port with no shipyard can mend a ship
only up to rules.storm.patch_max of her full hull (engine.repair_ceiling).

Ranking the ports (after the losses): each candidate scores w_price x (what the hold left fetches there,
against the best port) + w_yard (a shipyard) + w_standing x standing - ban_penalty for each banned cargo
aboard. Candidates are the `candidates` ports nearest the track, leaving out where she sailed from and where
she was going.

All the dice in here are the storm's own (seeded from the game, month and house), so a month with no storm
rolls exactly as before.

State on the house:
  p["storm"] = the report until the Captain taps "Make port" (storm_ack); see report() for its fields.
"""
import math
import random

DEFAULTS = {
    "enabled": True,
    "base": [0, 20, 32, 62], "dice_min": 0.6, "dice_max": 1.4,
    "risk_w": 0.5, "load_w": 0.25, "hull_w": 0.5, "arms_w": 0.15,
    "big_hull": 300, "big_mult": 0.85, "heavy_at": 45, "savage_at": 75, "cap": 130,
    "rough_hull_min": 0.05, "rough_hull_max": 0.15,
    "heavy_hull_min": 0.20, "heavy_hull_max": 0.40, "heavy_cargo_min": 0.10, "heavy_cargo_max": 0.25,
    "heavy_guns": 0.33,
    # Game 5 review (20 Nov 2026): Savage softened from 45-75% hull, 25-55% cargo and two thirds of the guns.
    "savage_hull_min": 0.25, "savage_hull_max": 0.45, "savage_cargo_min": 0.15, "savage_cargo_max": 0.35,
    "savage_guns": 0.33,
    "divert_heavy": 1.0, "divert_savage": 1.0, "candidates": 4,
    "w_price": 0.5, "w_yard": 0.35, "w_standing": 0.15, "ban_penalty": 0.25,
    "patch_max": 0.5,
    # Limp home (Game 5 review): a storm never sinks a ship. One that would founder is left at 1 hull.
    "limp_home": True,
}

# How many wording variants each line has in storm_text.py (the server picks one, the screen shows it).
LINES = {"open.rough": 4, "open.heavy": 4, "open.savage": 4, "cargo": 4, "guns": 4, "hull": 3,
         "land.bad": 4, "land.mid": 3, "land.same": 3, "close": 4}
# Powder says the first three gun lines; Roxana says the fourth.
GUNS_BY_POWDER = 3


def E():
    import engine
    return engine


def rules():
    out = dict(DEFAULTS)
    got = E().R.get("storm")
    if isinstance(got, dict):
        out.update({k: v for k, v in got.items() if k in DEFAULTS})
    return out


def on():
    return bool(rules()["enabled"])


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _lerp(lo, hi, u):
    return float(lo) + (float(hi) - float(lo)) * u


def _dice(g, p):
    """The storm's own dice: seeded from the game, the month and the house."""
    return random.Random("storm:{}:{}:{}".format(g.s.get("game_id", ""), g.s["turn"], p.get("name", "")))


# ------------------------------------------------------------ severity --
def fleet_hull(p):
    """Average share of full hull across the fleet (1.0 = every ship sound)."""
    S = E().SHIPS
    ships = [sh for sh in p["ships"] if sh["type"] in S]
    if not ships:
        return 1.0
    return _clamp(sum(max(0, sh["hull"]) / float(S[sh["type"]]["hull"] or 1) for sh in ships) / len(ships), 0.0, 1.0)


def arms_share(p):
    """Share of the fleet's gun mounts that are armed (a cannon takes cannon_slots of them)."""
    e = E()
    slots = sum(e.SHIPS[sh["type"]]["slots"] for sh in p["ships"])
    if slots <= 0:
        return 0.0
    used = sum(sh.get("guns", 0) + e.cannon_slots() * sh.get("cannons", 0) for sh in p["ships"])
    return _clamp(used / float(slots), 0.0, 1.0)


def severity(g, p, level, risk, own):
    """(score, parts): the storm's severity and what went into it."""
    e, r = E(), rules()
    base = float(r["base"][int(_clamp(level, 0, 3))])
    dice = own.uniform(float(r["dice_min"]), float(r["dice_max"]))
    risk_f = 1.0 + float(r["risk_w"]) * (float(risk) - 1.0)
    cap = g.capacity(p)
    load = _clamp(g.used(p) / float(cap), 0.0, 1.0) if cap else 0.0
    load_f = 1.0 + float(r["load_w"]) * load
    hull_lost = 1.0 - fleet_hull(p)
    hull_f = 1.0 + float(r["hull_w"]) * hull_lost
    arms = arms_share(p)
    arms_f = 1.0 + float(r["arms_w"]) * arms
    diff = float(e.MULT.get("storms", 1.0) or 1.0)
    score = _clamp(base * dice * risk_f * load_f * hull_f * arms_f * diff, 0.0, float(r["cap"]))
    parts = {"sea": level, "base": base, "dice": round(dice, 3), "risk": round(risk_f, 3), "load": round(load, 3),
             "hull_lost": round(hull_lost, 3), "arms": round(arms, 3), "difficulty": diff}
    return score, parts


def band_of(score):
    r = rules()
    if score >= float(r["savage_at"]):
        return "savage"
    if score >= float(r["heavy_at"]):
        return "heavy"
    return "rough"


def _position(score, band):
    """0..1: how far into its band the storm is (so the severity inputs matter inside a band too)."""
    r = rules()
    lo = {"rough": 0.0, "heavy": float(r["heavy_at"]), "savage": float(r["savage_at"])}[band]
    hi = {"rough": float(r["heavy_at"]), "heavy": float(r["savage_at"]), "savage": float(r["cap"])}[band]
    return _clamp((score - lo) / (hi - lo), 0.0, 1.0) if hi > lo else 0.5


# ------------------------------------------------------------ the ports --
def _seg_dist(a, b, c):
    """Distance from point c to the segment a-b (chart units)."""
    ax, ay, bx, by, cx, cy = a[0], a[1], b[0], b[1], c[0], c[1]
    dx, dy = bx - ax, by - ay
    n = dx * dx + dy * dy
    t = 0.0 if n == 0 else _clamp(((cx - ax) * dx + (cy - ay) * dy) / n, 0.0, 1.0)
    return math.hypot(cx - (ax + t * dx), cy - (ay + t * dy))


def candidates(origin, dest):
    """The ports nearest the line origin -> dest, never the two ends."""
    e, r = E(), rules()
    P = e.PORTS
    a, b = (P[origin]["x"], P[origin]["y"]), (P[dest]["x"], P[dest]["y"])
    rest = [k for k in P if k not in (origin, dest)]
    rest.sort(key=lambda k: (_seg_dist(a, b, (P[k]["x"], P[k]["y"])), k))
    return rest[:max(1, int(r["candidates"]))]


def hold_values(g, p, goods):
    """What the cargo left would fetch from the dealers in every port: {port: silver}."""
    e = E()
    return {k: sum(g.dealer_value(p, k, gd, q) for gd, q in goods.items() if q > 0) for k in e.PORTS}


def rank_ports(g, p, origin, dest, goods):
    """Score every candidate port for this hold, best first: [{port, score, ratio, yard, banned, standing}]."""
    e, r = E(), rules()
    vals = hold_values(g, p, goods)
    best = max(vals.values()) if vals else 0.0
    out = []
    for k in candidates(origin, dest):
        ratio = (vals[k] / best) if best > 0 else 0.5
        yard = bool(e.port_has(p, k, "shipyard"))
        banned = [gd for gd in goods if goods[gd] > 0 and gd in g.banned(k)]
        stand = float(p["rep"].get(k, 50.0))
        score = (float(r["w_price"]) * ratio + float(r["w_yard"]) * (1.0 if yard else 0.0)
                 + float(r["w_standing"]) * stand / 100.0 - float(r["ban_penalty"]) * len(banned))
        out.append({"port": k, "score": round(score, 4), "ratio": round(ratio, 4), "yard": yard,
                    "banned": banned, "standing": round(stand, 1)})
    out.sort(key=lambda x: (-x["score"], x["port"]))
    return out, vals, best


def pick_port(ranked, band):
    """Savage: the worst one with no shipyard (the worst of all if every one has a yard).
    Heavy: the middle one of those that have a shipyard (the middle of all if none does)."""
    if band == "savage":
        pool = [x for x in ranked if not x["yard"]] or ranked
        return pool[-1]
    pool = [x for x in ranked if x["yard"]] or ranked
    return pool[len(pool) // 2]


def nearest_yard(p, port):
    """The closest port with a shipyard to this one (itself if it has one): (port, chart distance)."""
    e = E()
    if e.port_has(p, port, "shipyard"):
        return port, 0.0
    cand = [(e.distance(port, k), k) for k in e.PORTS if k != port and e.port_has(p, k, "shipyard")]
    if not cand:
        return None, 0.0
    d, k = min(cand)
    return k, round(d, 1)


# ------------------------------------------------------------- the hit --
def _pick(own, key, band=None):
    name = key if band is None else "{}.{}".format(key, band)
    return "storm.{}.{}".format(name, own.randrange(LINES[name]))


def hit(g, p, v, level, risk, news):
    """The storm has caught the fleet (the caller rolled the chance). Takes hull, cargo and guns, may send
    the fleet to another port (v["dest"]), and leaves the report for the screen in p["storm"]."""
    e, r = E(), rules()
    SHIPS, PORTS = e.SHIPS, e.PORTS
    own = _dice(g, p)
    who, origin, dest0 = p["name"], v["origin"], v["dest"]
    score, parts = severity(g, p, level, risk, own)
    band = band_of(score)
    t = _position(score, band)

    def u():
        return _clamp(0.5 * t + 0.5 * own.random(), 0.0, 1.0)

    ships0 = [{"name": sh["name"], "type": sh["type"], "max": int(SHIPS[sh["type"]]["hull"]), "hull0": int(sh["hull"]),
               "guns0": int(sh.get("guns", 0)), "cannons0": int(sh.get("cannons", 0))} for sh in p["ships"]]
    held0 = dict(p["cargo"])
    typhoon = level == 3

    # hull
    lo, hi = float(r[band + "_hull_min"]), float(r[band + "_hull_max"])
    hits = []
    for sh in p["ships"]:
        spec = SHIPS[sh["type"]]
        share = _lerp(lo, hi, u())
        mult = float(e.R["weather"]["fast_dmg_mult"]) if spec.get("fast") else 1.0
        if int(spec["hull"]) >= int(r["big_hull"]):
            mult *= float(r["big_mult"])
        took = max(1, int(round(spec["hull"] * share * mult)))
        limped = False
        if r.get("limp_home", True) and sh["hull"] - took < 1:
            took = max(0, int(sh["hull"]) - 1)          # she limps in at 1 hull instead of foundering
            limped = True
        sh["hull"] -= took
        hits.append({"name": sh["name"], "damage": took, "hull": sh["hull"], "limped": limped})

    # guns and cannons (Heavy and Savage)
    guns_lost = cannons_lost = 0
    gun_value = 0.0
    if band != "rough":
        frac = float(r[band + "_guns"])
        f = e.R["fleet"]
        for sh in p["ships"]:
            if sh["hull"] <= 0:
                continue                         # she goes down with all she carries (_check_sunk books it)
            lg = sum(1 for _ in range(int(sh.get("guns", 0))) if own.random() < frac)
            lc = sum(1 for _ in range(int(sh.get("cannons", 0))) if own.random() < frac)
            if lg or lc:
                sh["guns"] = int(sh.get("guns", 0)) - lg
                if "cannons" in sh or lc:
                    sh["cannons"] = int(sh.get("cannons", 0)) - lc
                guns_lost += lg
                cannons_lost += lc
                gun_value += (lg * float(f["gun_price"]) + lc * float(e.cannon_price())) * float(f["gun_resale"])
        if gun_value:
            g._book(p, "ships_lost", -gun_value)

    # cargo overboard (Heavy and Savage)
    lost = {}
    if band != "rough":
        clo, chi = float(r[band + "_cargo_min"]), float(r[band + "_cargo_max"])
        base_share = _lerp(clo, chi, u())
        for gd in sorted(p["cargo"]):
            q = int(p["cargo"][gd])
            share = _clamp(base_share * own.uniform(0.8, 1.2), 0.0, 1.0)
            n = q * share
            n = int(n) + (1 if own.random() < n - int(n) else 0)
            n = min(q, n)
            if n > 0:
                lost[gd] = n
        if lost:
            g._book(p, "overboard", -g._cost_of(p, lost))
            for gd, n in lost.items():
                p["cargo"][gd] -= n
                if p["cargo"][gd] <= 0:
                    del p["cargo"][gd]

    p["log"].append(e.tx("l.typhoon" if typhoon else "l.storm"))
    g._ev("voyage", "storm_damage", "{}: {} damage ({} storm, score {}, {}-{}% of the hull): {}".format(
        who, "typhoon" if typhoon else "storm", band, int(round(score)), int(lo * 100), int(hi * 100),
        ", ".join("{} -{} (hull {})".format(h["name"], h["damage"], h["hull"]) for h in hits)), p, hits=hits,
        band=band, score=round(score, 2), parts=parts, guns=guns_lost, cannons=cannons_lost, cargo=dict(lost))
    if lost:
        p["log"].append(e.tx("l.storm_cargo", goods=g._goods_text(lost)))
    if guns_lost or cannons_lost:
        p["log"].append(e.tx("l.storm_guns", n=guns_lost + cannons_lost))

    before = dict(p["cargo"])
    g._check_sunk(p, e.tx("l.how_foundered"))
    for gd, q in before.items():                  # cargo the survivors' smaller hold could not carry
        gone = q - p["cargo"].get(gd, 0)
        if gone > 0:
            lost[gd] = lost.get(gd, 0) + gone
    alive = {sh["name"] for sh in p["ships"]}

    ships = []
    for s0 in ships0:
        sh = next((x for x in p["ships"] if x["name"] == s0["name"]), None)
        s0 = dict(s0)
        s0["lost"] = sh is None
        s0["hull1"] = 0 if sh is None else max(0, int(sh["hull"]))
        s0["guns1"] = 0 if sh is None else int(sh.get("guns", 0))
        s0["cannons1"] = 0 if sh is None else int(sh.get("cannons", 0))
        ships.append(s0)
    if not p["ships"]:
        return None                               # the whole fleet foundered: the shipwreck has its own story

    # where the fleet lands
    landing = {"port": dest0, "yard": bool(e.port_has(p, dest0, "shipyard")), "diverted": False}
    ranked = []
    chance = float(r["divert_" + band]) if band != "rough" else 0.0
    diverted = band != "rough" and own.random() < chance
    if diverted:
        ranked, vals, best = rank_ports(g, p, origin, dest0, p["cargo"])
        pick = pick_port(ranked, band)
        dest = v["dest"] = pick["port"]
        yard_port, _d = nearest_yard(p, dest)
        best_port = max(vals, key=lambda k: vals[k]) if vals else dest
        landing = {"port": dest, "yard": pick["yard"], "diverted": True, "ratio": int(round(100 * pick["ratio"])),
                   "rank": [x["port"] for x in ranked].index(dest) + 1, "of": len(ranked),
                   "banned": pick["banned"], "yard_port": yard_port, "best_port": best_port,
                   "was": dest0, "worth": int(round(vals.get(dest, 0))), "best_worth": int(round(best))}
        if pick["yard"]:
            p["log"].append(e.tx("l.storm_land", port=PORTS[dest]["name"]))
        elif yard_port:
            p["log"].append(e.tx("l.storm_land_bad", port=PORTS[dest]["name"], yard=PORTS[yard_port]["name"]))
        else:
            p["log"].append(e.tx("l.storm_land_far", port=PORTS[dest]["name"]))
        g._ev("voyage", "offcourse", "{} was blown off course to {} ({} storm; ranked {} of {} for the hold, {})".format(
            who, PORTS[dest]["name"], band, landing["rank"], landing["of"], "a shipyard" if pick["yard"] else "no shipyard"),
            p, dest=dest, band=band, ranked=ranked)
        news.append(e.tx("n.storm_" + band, name=p["name"], firm=p["firm"], port=PORTS[dest]["name"],
                         was=PORTS[dest0]["name"]))

    hull_lost = sum(max(0, s["hull0"] - s["hull1"]) for s in ships)
    hull_full = sum(s["max"] for s in ships)
    cost = g._cost_of(p, lost)
    p["storm_seq"] = int(p.get("storm_seq", 0)) + 1
    lines = {"open": _pick(own, "open", band), "close": _pick(own, "close")}
    if lost:
        lines["cargo"] = _pick(own, "cargo")
    if guns_lost or cannons_lost:
        lines["guns"] = _pick(own, "guns")
    if band != "rough":
        lines["hull"] = _pick(own, "hull")
        if diverted:
            lines["land"] = _pick(own, "land", "mid" if landing["yard"] else "bad")
        else:
            lines["land"] = _pick(own, "land", "same")
    p["storm"] = {"id": p["storm_seq"], "turn": g.s["turn"], "band": band, "card": band != "rough",
                  "typhoon": typhoon, "level": level, "score": int(round(score)), "parts": parts,
                  "origin": origin, "dest0": dest0, "landing": landing,
                  "ships": ships, "hull_lost": int(hull_lost), "hull_full": int(hull_full),
                  "cargo": [{"good": gd, "qty": q, "cost": int(round(g._cost_of(p, {gd: q})))} for gd, q in sorted(lost.items())],
                  "cargo_cost": int(round(cost)), "held0": held0, "patch_pct": int(round(100 * float(r["patch_max"]))),
                  "guns_lost": guns_lost, "cannons_lost": cannons_lost, "arms_value": int(round(gun_value)),
                  "lines": lines}
    g._ev("voyage", "storm_report", "{}: {} storm: hull -{} of {}, {} lost overboard, {} guns and {} cannons gone{}".format(
        who, band, hull_lost, hull_full, ", ".join("{} {}".format(q, gd) for gd, q in sorted(lost.items())) or "no cargo",
        guns_lost, cannons_lost, "; landed in " + PORTS[landing["port"]]["name"] if diverted else ""), p, band=band,
        landing=landing, hull_lost=hull_lost, cargo=dict(lost), guns=guns_lost, cannons=cannons_lost,
        table_report=p["storm"])
    return p["storm"]


# --------------------------------------------------------------- action --
def act_ack(g, p, a):
    """storm_ack: the Captain has seen the storm; the card (or banner) goes away."""
    e = E()
    st = p.pop("storm", None)
    if st:
        g._ev("voyage", "storm_ack", "{} closed the storm report ({} storm)".format(p["name"], st.get("band")), p)
    return e.tx("m.storm_ack")


# ---------------------------------------------------------------- view --
def view(g, p):
    st = p.get("storm")
    return dict(st) if isinstance(st, dict) else None
