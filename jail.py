"""Jail (19 Nov 2026, planned with Anthony one decision at a time; project doc "SeaTrader Jail").

A Captain can be locked up for 1 or 3 months. While inside, the House's fleet is held at anchor in that
port and the House sits the months out (the Captain taps "Serve the month" on the jail
screen, so each month inside gets its own beat instead of flashing past on the 3-second turn watcher;
an absent Captain holds nobody up, and a forced month end serves it anyway).
The port still eats into it: the crew drinks a share of the silver aboard each month and perishable
cargo spoils. There is no early way out. On release, standing in that port is lifted to a floor so the
Captain is not arrested again straight away.

Ways in:
  - Arrested outright: standing at or below rules.jail.arrest_standing on arrival; a chance in a Hostile
    port; a chance when contraband is seized; a chance when caught slipping out at night; a chance when
    the collectors call past the debt cap (debtors' prison); always on bankruptcy (3 months, at home).
  - The plea deal: a big fine (a Port Authority audit, a contraband fine, the slip-out bill) can be paid
    in full, or swapped for 1 month and a share of it, or 3 months and a smaller share.

All the rules live here; engine.py calls these hooks. Numbers come from rules.jail (Admin > Rules >
Jail) with DEFAULTS as the fallback, and every chance and the crew's drinking are multiplied by the
difficulty level's "jail" setting (easy 0.5, normal 1, hard 1.5).

State on the house:
  p["jail"] = {"port", "months", "left", "charge", "since", "fresh", "served", "fine", "paid"}   (None when free)
  p["plea"] = {"id", "port", "charge", "amount", "book", "arrival", "opts": [{months, share, pay}], "turn"}
  p["jail_freed"] = {"port", "months", "charge", "drunk", "spoiled", "turn", "fine", "paid", "floor"}   (the release
                    card, until "Walk free")

Pacing (owner's decision, 19 Nov 2026, "Tap to serve each month"): the arrest card ("Into the cell"),
each month ("Serve the month") and the release card ("Walk free") wait for a tap.

The story (owner's decision, 20 Nov 2026: "like the Sea Battle: large-screen story telling, the costs and data
only at the end"): web/jail.js plays the arrest as screens, the one who caught the Captain (ACCUSERS) first,
then the warden and the irons, then the held sentence; each month is a quiet story screen; the release is the
door opening and then the costs overlay (months served, silver drunk, cargo spoiled, the fine and what was
paid, standing eased). Nothing here changes the rules; "fine" and "paid" are only remembered for that overlay.
"""
import math

DEFAULTS = {
    "enabled": True,
    "arrest_months": 1,              # an outright arrest
    "max_months": 6,                 # sentences stack up to this
    "arrest_standing": 1,            # arrested on arrival at or below this standing
    "hostile_below": 20,             # a Hostile port...
    "hostile_chance": 0.05,          # ...arrests on arrival this often
    "contraband_chance": 0.25,       # contraband seized: also locked up
    "contraband_low_rep": 20,        # below this standing...
    "contraband_low_mult": 1.5,      # ...that chance is multiplied by this
    "slip_chance": 0.20,             # caught slipping out: the Mayor also locks you up, the first time...
    "slip_repeat": 0.15,             # ...plus this for each earlier catch in that port...
    "slip_repeat_months": 24,        # ...within this many months...
    "slip_jail_max": 0.65,           # ...never more than this
    "collectors_chance": 0.20,       # the collectors call past the debt cap: debtors' prison
    "bankrupt_months": 3,            # bankruptcy: always, served at home before the fresh start
    "plea": True,                    # big fines may be swapped for time
    "big_share": 0.05,               # a fine is "big" above this share of net worth...
    "big_min": 1000,                 # ...and at least this much (or more than silver + bank)
    "plea1_min": 0.40, "plea1_max": 0.60,   # 1 month: still pay this share
    "plea3_min": 0.10, "plea3_max": 0.25,   # 3 months: still pay this share
    "drink_min": 0.03, "drink_max": 0.10,   # each month inside the crew drinks this share of the silver aboard
    "spoil_min": 0.05, "spoil_max": 0.15,   # ...and perishable cargo loses this share
    "perishables": ["rice", "tea", "spices"],
    "release_floor": 10,             # standing in the jail port on release, at least
}
DIFFICULTY = {"easy": 0.5, "normal": 1.0, "hard": 1.5}
CHARGES = ("standing", "hostile", "contraband", "slip", "debt", "bankrupt", "desk", "plea_contraband", "plea_slip")
# Who catches the Captain (the jail story's first screen, 20 Nov 2026): the cast key whose picture fills it.
# The Port Authority officer of the port stands in for "customs" at a desk audit; server.py puts the one who
# really spoke (the cast key on the voiced log line) in its place.
ACCUSERS = {"standing": "mayor", "hostile": "mayor", "slip": "mayor", "plea_slip": "mayor",
            "contraband": "customs", "plea_contraband": "customs", "desk": "customs",
            "debt": "lender", "bankrupt": "lender"}


def E():
    import engine
    return engine


def rules():
    out = dict(DEFAULTS)
    got = E().R.get("jail")
    if isinstance(got, dict):
        out.update({k: v for k, v in got.items() if k in DEFAULTS})
    return out


def on():
    return bool(rules()["enabled"])


def mult():
    m = E().MULT
    v = m.get("jail")
    if v is None:                      # a saved preset from before jail: read the level from its seizure odds
        sz = float(m.get("seizure", 1.0) or 1.0)
        v = DIFFICULTY["easy"] if sz < 0.95 else DIFFICULTY["hard"] if sz > 1.05 else DIFFICULTY["normal"]
    try:
        return max(0.0, float(v))
    except (TypeError, ValueError):
        return 1.0


def jailed(p):
    j = p.get("jail")
    return isinstance(j, dict) and int(j.get("left", 0)) > 0


def pending(p):
    return isinstance(p.get("plea"), dict)


def _port_name(port):
    P = E().PORTS
    return P[port]["name"] if port in P else str(port)


def warden_of(port):
    return "warden_" + str(port)


# ------------------------------------------------------------ going in --
def lock_up(g, p, months, charge, news=None, port=None, fresh=True):
    """Put the Captain in jail (or add to a sentence already running). fresh: set during the month's
    resolution, so this month's end does not count as a month served."""
    e, r = E(), rules()
    port = port or p["port"]
    months = max(1, int(months))
    j = p.get("jail") if jailed(p) else None
    if j:
        add = max(0, min(int(r["max_months"]) - int(j["left"]), months))
        j["left"] += add
        j["months"] += add
        j.setdefault("charges", []).append(charge)
    else:
        j = p["jail"] = {"port": port, "months": months, "left": months, "charge": charge, "charges": [charge],
                         "since": g.s["turn"], "served": 0, "fresh": bool(fresh), "drunk": 0, "spoiled": {}}
    p["ready"], p["dest"], p["slip"] = False, None, False      # the Captain taps "Serve the month"
    p.pop("jail_freed", None)
    p["jail_count"] = int(p.get("jail_count", 0)) + 1
    name = _port_name(j["port"])
    s = "" if months == 1 else "s"
    p["log"].append(e.tx("l.jail_" + charge, port=name, months=months, s=s))
    line = e.tx("n.jail", name=p["name"], firm=p["firm"], port=name, months=months, s=s,
                why=e.tx("jail.why." + charge))
    if news is not None:
        news.append(line)
    else:
        g._news_later(p, line)
    g._ev("jail", "jail_arrest", "{} was jailed in {} for {} month{} ({}){}".format(
        p["name"], name, months, s, charge, "" if fresh else ", starting with this month"), p,
        port=j["port"], months=months, charge=charge, left=j["left"])
    return j


def _chance(g, p, odds, kind, label, **data):
    return g._chance(max(0.0, min(1.0, odds * mult())), kind, label, p, **data)


def on_arrival(g, p, news, port):
    """Landed: arrested on sight at rock-bottom standing, or by chance in a Hostile port.
    Returns True when the Captain was locked up."""
    if not on() or jailed(p):
        return False
    r = rules()
    st = float(p["rep"].get(port, 50.0))
    if st <= float(r["arrest_standing"]):
        g._ev("jail", "jail_standing", "{}: standing {:.0f} in {} is at or below {}: arrested on arrival".format(
            p["name"], st, _port_name(port), r["arrest_standing"]), p, port=port, standing=round(st, 2))
        lock_up(g, p, r["arrest_months"], "standing", news, port)
        return True
    if st < float(r["hostile_below"]) and _chance(
            g, p, float(r["hostile_chance"]), "jail_hostile",
            "{}: arrested on arrival in a Hostile port ({}, standing {:.0f})".format(p["name"], _port_name(port), st),
            port=port, standing=round(st, 2)):
        lock_up(g, p, r["arrest_months"], "hostile", news, port)
        return True
    return False


def on_seized(g, p, news, port):
    """Contraband was seized on arrival: a chance of being locked up as well."""
    if not on():
        return False
    r = rules()
    odds = float(r["contraband_chance"])
    if float(p["rep"].get(port, 50.0)) < float(r["contraband_low_rep"]):
        odds *= float(r["contraband_low_mult"])
    if _chance(g, p, odds, "jail_contraband", "{}: locked up for the contraband seized in {}".format(
            p["name"], _port_name(port)), port=port):
        lock_up(g, p, r["arrest_months"], "contraband", news, port)
        return True
    return False


def slip_jail_odds(r, prior):
    """Repeat offenders (owner's decision, 19 Nov 2026): slip_chance the first time, slip_repeat more for each
    earlier catch in that port within slip_repeat_months, at most slip_jail_max (before the difficulty)."""
    odds = float(r["slip_chance"]) + float(r["slip_repeat"]) * max(0, int(prior))
    return max(0.0, min(float(r["slip_jail_max"]), odds))


def on_slip_caught(g, p, news, port, prior=0):
    """Caught slipping out at night: a chance the Mayor locks the Captain up (the fleet stays in port).
    prior: earlier catches in this port that she still remembers."""
    if not on():
        return False
    r = rules()
    if _chance(g, p, slip_jail_odds(r, prior), "jail_slip", "{}: the Mayor of {} locks the captain up for "
               "slipping out ({} earlier catches there)".format(p["name"], _port_name(port), int(prior)), port=port,
               prior=int(prior)):
        lock_up(g, p, r["arrest_months"], "slip", news, port)
        return True
    return False


def on_collectors(g, p, news):
    """The collectors call while the debt is past the debt cap: a chance of debtors' prison."""
    if not on():
        return False
    cap = g.debt_cap(p)
    if not cap or p["debt"] < cap - 0.5:
        return False
    r = rules()
    if _chance(g, p, float(r["collectors_chance"]), "jail_debt", "{}: the collectors have the captain put in "
               "debtors' prison in {} (debt {} at the cap)".format(p["name"], _port_name(p["port"]),
                                                                   E().money(p["debt"]))):
        lock_up(g, p, r["arrest_months"], "debt", news)
        return True
    return False


def on_bankrupt(g, p, news):
    """Bankruptcy: debtors' prison at home before the fresh start."""
    if not on():
        return False
    p.pop("plea", None)
    lock_up(g, p, rules()["bankrupt_months"], "bankrupt", news, E().home_of(p))
    return True


# ------------------------------------------------------------ the plea --
def is_big(g, p, amount):
    r = rules()
    if not on() or not r["plea"] or amount < float(r["big_min"]):
        return False
    worth = max(0.0, float(g.worth(p)))
    return amount > float(r["big_share"]) * worth or amount > max(0.0, p["cash"]) + max(0.0, p["bank"])


def offer_plea(g, p, amount, charge, port, book, arrival=False):
    """A big fine: instead of charging it now, put the three choices in front of the Captain.
    Returns True when a plea was offered (the caller must not charge the fine)."""
    amount = int(math.ceil(amount))
    if pending(p) or not is_big(g, p, amount):
        return False
    r, rng = rules(), g.rng
    s1 = round(rng.uniform(float(r["plea1_min"]), float(r["plea1_max"])), 3)
    s3 = round(rng.uniform(float(r["plea3_min"]), float(r["plea3_max"])), 3)
    p["plea_seq"] = int(p.get("plea_seq", 0)) + 1
    p["plea"] = {"id": p["plea_seq"], "port": port, "charge": charge, "amount": amount, "book": book,
                 "arrival": bool(arrival), "turn": g.s["turn"],
                 "opts": [{"months": 0, "share": 1.0, "pay": amount},
                          {"months": 1, "share": s1, "pay": int(math.ceil(amount * s1))},
                          {"months": 3, "share": s3, "pay": int(math.ceil(amount * s3))}]}
    p["log"].append(E().tx("l.plea_offer", port=_port_name(port), fine=E().money(amount)))
    g._ev("jail", "plea_offer", "{}: a fine of {} in {} ({}) may be swapped for time: 1 month and {}, or 3 months "
          "and {}".format(p["name"], E().money(amount), _port_name(port), charge, E().money(p["plea"]["opts"][1]["pay"]),
                          E().money(p["plea"]["opts"][2]["pay"])), p, plea=dict(p["plea"]))
    return True


def _pay(g, p, amount, book, arrival):
    owed = g._collect(p, amount)
    g._book(p, book, -amount, arrival=arrival)
    return owed


def act_plea(g, p, a):
    """The Captain's answer: months 0 (pay it all), 1 or 3."""
    e = E()
    pl = p.get("plea")
    if not isinstance(pl, dict):
        raise e.GameError(e.tx("e.plea_none"))
    try:
        months = int(a.get("months"))
    except (TypeError, ValueError):
        raise e.GameError(e.tx("e.plea_choice"))
    opt = next((o for o in pl["opts"] if o["months"] == months), None)
    if opt is None:
        raise e.GameError(e.tx("e.plea_choice"))
    p.pop("plea")
    owed = _pay(g, p, opt["pay"], pl["book"], pl["arrival"])
    g._detail = {"plea": pl, "months": months, "paid": opt["pay"], "owed": owed,
                 "note": "answered the plea: {}".format("paid the fine in full" if not months else
                                                        "{} month(s) in jail and {}".format(months, e.money(opt["pay"])))}
    if not months:
        return e.tx("m.plea_paid", fine=e.money(opt["pay"]))
    j = lock_up(g, p, months, "plea_" + pl["charge"] if "plea_" + pl["charge"] in CHARGES else "desk",
                None, pl["port"], fresh=False)
    j["fine"] = int(j.get("fine", 0)) + int(pl["amount"])       # for the release card's costs
    j["paid"] = int(j.get("paid", 0)) + int(opt["pay"])
    return e.tx("m.plea_jail", months=months, s="" if months == 1 else "s", fine=e.money(opt["pay"]))


def settle_plea(g, p):
    """The month turns with the plea unanswered: the fine is paid in full."""
    pl = p.pop("plea", None)
    if not isinstance(pl, dict):
        return
    owed = _pay(g, p, pl["amount"], pl["book"], pl["arrival"])
    g._ev("jail", "plea_auto", "{} gave no answer to the plea in {}: the fine of {} was paid in full".format(
        p["name"], _port_name(pl["port"]), E().money(pl["amount"])), p, amount=pl["amount"], owed=owed)


# ---------------------------------------------------------- the month --
def before_resolve(g, players):
    """The month is turning: unanswered pleas are paid; a jailed House stays at anchor."""
    for p in players:
        if pending(p):
            settle_plea(g, p)
        if jailed(p):
            p["ready"], p["dest"], p["slip"] = True, None, False


def month(g, p, news):
    """Month end for one House. Returns True while the Captain is inside (no street robbery)."""
    if not jailed(p):
        if p.get("jail") is not None:
            p["jail"] = None
        return False
    e, r, rng, j = E(), rules(), g.rng, p["jail"]
    name = _port_name(j["port"])
    if j.pop("fresh", False):
        return True                      # locked up during this month's voyage: the months start next month
    j["served"] = int(j.get("served", 0)) + 1
    j["left"] = int(j["left"]) - 1
    lines, drunk = [], 0
    if p["cash"] > 0:
        share = min(1.0, rng.uniform(float(r["drink_min"]), float(r["drink_max"])) * mult())
        drunk = int(p["cash"] * share)
        if drunk > 0:
            p["cash"] -= drunk
            j["drunk"] = int(j.get("drunk", 0)) + drunk
            g._book(p, "jail_drink", -drunk)
            lines.append(e.tx("l.jail_drink", lost=e.money(drunk)))
    spoiled = {}
    for gd in [x for x in r["perishables"] if p["cargo"].get(x, 0) > 0]:
        q = int(p["cargo"][gd])
        lose = q * rng.uniform(float(r["spoil_min"]), float(r["spoil_max"]))
        lose = int(lose) + (1 if rng.random() < lose - int(lose) else 0)
        lose = min(q, lose)
        if lose > 0:
            spoiled[gd] = lose
    if spoiled:
        g._book(p, "jail_spoil", -g._cost_of(p, spoiled))
        for gd, q in spoiled.items():
            p["cargo"][gd] -= q
            if p["cargo"][gd] <= 0:
                del p["cargo"][gd]
            j.setdefault("spoiled", {})[gd] = j.get("spoiled", {}).get(gd, 0) + q
        lines.append(e.tx("l.jail_spoil", goods=g._goods_text(spoiled)))
    j["last"] = {"drunk": drunk, "spoiled": spoiled}
    g._ev("jail", "jail_month", "{}: month {} of {} in jail in {}; the crew drank {}{}".format(
        p["name"], j["served"], j["months"], name, e.money(j["last"]["drunk"]),
        "; spoiled: " + g._goods_text(spoiled) if spoiled else ""), p,
        port=j["port"], served=j["served"], left=j["left"], drunk=j["last"]["drunk"], spoiled=spoiled)
    if j["left"] > 0:
        p["log"].append(e.tx("l.jail_month", port=name, served=j["served"], months=j["months"], left=j["left"],
                             s="" if j["left"] == 1 else "s"))
        p["log"].extend(lines)
        return True
    p["log"].extend(lines)
    release(g, p)
    return True


def release(g, p):
    e, r = E(), rules()
    j = p.get("jail") or {}
    port = j.get("port", p["port"])
    floor = float(r["release_floor"])
    if port in p["rep"] and p["rep"][port] < floor:
        p["rep"][port] = floor
    p["jail_months"] = int(p.get("jail_months", 0)) + int(j.get("served", 0))
    p["jail_last"] = {"port": port, "months": int(j.get("months", 0)), "drunk": int(j.get("drunk", 0)),
                      "spoiled": dict(j.get("spoiled") or {}), "turn": g.s["turn"]}
    p["jail"] = None
    p["ready"] = False
    p["jail_freed"] = {"port": port, "months": int(j.get("months", 0)), "charge": j.get("charge"),
                       "drunk": int(j.get("drunk", 0)), "spoiled": dict(j.get("spoiled") or {}), "turn": g.s["turn"],
                       "fine": int(j.get("fine", 0)), "paid": int(j.get("paid", 0)), "floor": int(floor)}
    p["log"].append(e.tx("l.jail_release", port=_port_name(port)))
    g._ev("jail", "jail_release", "{} was released from jail in {} after {} month(s); standing there at least {}".format(
        p["name"], _port_name(port), j.get("served", 0), int(floor)), p, port=port,
        months=j.get("served", 0), drunk=j.get("drunk", 0), spoiled=j.get("spoiled") or {})


def after_finish(g, players):
    """The new month opens: a House still inside waits for its Captain to tap "Serve the month"."""
    for p in players:
        if jailed(p):
            p["ready"], p["dest"], p["slip"] = False, None, False


def act_jail(g, p, kind):
    """jail_serve: the Captain lets the month pass (marks the House as sailed; the month turns when
    everyone present is ready). jail_free: the release card is closed and the Captain is back in port."""
    e = E()
    if kind == "jail_free":
        p.pop("jail_freed", None)
        return e.tx("m.jail_free")
    if not jailed(p):
        raise e.GameError(e.tx("e.jail_not"))
    j = p["jail"]
    p["ready"], p["dest"], p["slip"] = True, None, False
    g._ev("jail", "jail_serve", "{} lets the month pass in the {} gaol ({} of {} served, {})".format(
        p["name"], _port_name(j["port"]), j.get("served", 0), j["months"],
        "arrest month" if j.get("fresh") else "a month served"), p, port=j["port"], left=j["left"])
    return e.tx("m.jail_into" if j.get("fresh") else "m.jail_serve")


# ------------------------------------------------------------- actions --
ALLOWED = ("plea", "promotion_ack", "house", "free_play", "jail_serve", "jail_free")


def check_act(g, p, kind):
    """Refuse anything a Captain in a cell (or with a plea to answer) can't do."""
    e = E()
    if kind in ALLOWED:
        return
    if jailed(p):
        raise e.GameError(e.tx("e.jailed", port=_port_name(p["jail"]["port"])))
    if pending(p):
        raise e.GameError(e.tx("e.plea_first"))


# ---------------------------------------------------------------- view --
def view(g, p):
    j = p.get("jail") if jailed(p) else None
    out = {"plea": None, "jail": None, "last": p.get("jail_last"), "freed": p.get("jail_freed"),
           "months_total": int(p.get("jail_months", 0))}
    if pending(p):
        pl = p["plea"]
        out["plea"] = {"id": pl["id"], "port": pl["port"], "charge": pl["charge"], "amount": pl["amount"],
                       "opts": pl["opts"], "warden": warden_of(pl["port"])}
    if j:
        out["jail"] = {"port": j["port"], "months": j["months"], "left": j["left"], "served": j.get("served", 0),
                       "charge": j["charge"], "charges": j.get("charges") or [j["charge"]], "since": j.get("since"),
                       "drunk": int(j.get("drunk", 0)), "spoiled": j.get("spoiled") or {},
                       "last": j.get("last") or {}, "warden": warden_of(j["port"]), "fresh": bool(j.get("fresh")),
                       "ready": bool(p.get("ready")), "by": ACCUSERS.get(j["charge"], "mayor"),
                       "fine": int(j.get("fine", 0)), "paid": int(j.get("paid", 0))}
    if out["freed"]:
        out["freed"] = dict(out["freed"], warden=warden_of(out["freed"]["port"]))
    return out
