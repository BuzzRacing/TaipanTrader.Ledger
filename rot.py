"""Perishable cargo rots (rot.py, 20 Nov 2026).

Cargo on the perishable list (rules.jail.perishables: rice, tea, spices by default; shared with the jail)
that stays aboard too long rots. Decisions, all 20 Nov 2026:
  * Each perishable good aboard has ONE average age in months, p["age"][good]. New units come aboard at
    age 0 and blend the average down (add(), the way p["basis"] blends the price paid). Selling leaves the
    average alone; the entry is dropped when the good is gone from the hold.
  * Every month's end the age goes up by one. Once it is past the grace period (rules.rot.grace_months,
    3) a random share of that good, rules.rot.min..max (5-15%), rots and is written off at cost.
  * Only the hold ages. Warehouses and depots are safe storage.
  * While a captain is in jail the jail's own spoilage is the only hit (jail.month). The age still
    advances, and the month the captain walks out is skipped too, so there is never a double hit.
  * The player screen gets each perishable's age and the grace period (view()) so a loss is never a surprise.
Own dice (seeded from game, month and house), so ordinary games' dice are left as they were.
"""
import random

import jail

DEFAULTS = {
    "enabled": True,
    "grace_months": 3,       # safe for this many month-ends aboard; it rots from the next one
    "min": 0.05, "max": 0.15,    # then this share of the good rots each month
}


def E():
    import engine
    return engine


def rules():
    out = dict(DEFAULTS)
    got = E().R.get("rot")
    if isinstance(got, dict):
        out.update({k: v for k, v in got.items() if k in DEFAULTS})
    return out


def on():
    return bool(rules()["enabled"])


def perishables():
    """The shared list (Admin > Perishable cargo), real cargoes only, in a steady order."""
    goods = E().GOODS
    seen = []
    for x in jail.rules().get("perishables") or ():
        if x in goods and x not in seen:
            seen.append(x)
    return seen


def _ages(p):
    a = p.get("age")
    if not isinstance(a, dict):
        a = p["age"] = {}
    return a


def age_of(p, good):
    a = p.get("age")
    return float(a.get(good, 0.0)) if isinstance(a, dict) else 0.0


def add(p, good, qty):
    """qty fresh units are about to come aboard: blend the average age down. Call BEFORE the hold count
    changes. Goods that are not perishable, or a switched-off rule, change nothing."""
    qty = int(qty)
    if qty <= 0 or not on() or good not in perishables():
        return
    a = _ages(p)
    have = max(0, int(p["cargo"].get(good, 0)))
    a[good] = float(a.get(good, 0.0)) * have / float(have + qty) if have > 0 else 0.0


def month(g, p, news=None, skip=False):
    """Month end for one House. The age always advances; the rot is skipped while skip is True (jailed).
    Returns {good: units rotted}."""
    per = perishables()
    a = _ages(p)
    for k in list(a):
        if k not in per or int(p["cargo"].get(k, 0)) <= 0:
            del a[k]                      # gone from the hold (or no longer perishable): the clock stops
    if not on():
        return {}
    for k in per:
        if int(p["cargo"].get(k, 0)) > 0:
            a[k] = float(a.get(k, 0.0)) + 1.0
    if skip:
        return {}
    r = rules()
    grace = max(0, int(r["grace_months"]))
    lo, hi = float(r["min"]), float(r["max"])
    own = random.Random("{}:{}:{}:rot".format(g.s.get("game_id", ""), g.s.get("turn", 0), p.get("id", "")))
    lost = {}
    for k in per:
        q = int(p["cargo"].get(k, 0))
        if q <= 0 or a.get(k, 0.0) <= grace:
            continue
        lose = q * own.uniform(min(lo, hi), max(lo, hi))
        lose = int(lose) + (1 if own.random() < lose - int(lose) else 0)
        lose = min(q, lose)
        if lose > 0:
            lost[k] = lose
    if lost:
        e = E()
        g._book(p, "rot", -g._cost_of(p, lost))
        for k, q in lost.items():
            p["cargo"][k] -= q
            if p["cargo"][k] <= 0:
                del p["cargo"][k]
                a.pop(k, None)
        p["log"].append(e.tx("l.rot", goods=g._goods_text(lost)))
        g._ev("rot", "rot", "{}: {} rotted in the hold (aged {})".format(
            p["name"], g._goods_text(lost),
            ", ".join("{} {:.1f} months".format(k, float(a.get(k, grace + 1))) for k in sorted(lost))), p, lost=lost)
    return lost


def view(p):
    """What the player screen shows: the grace period and the age (months) of each perishable aboard."""
    if not on():
        return {"on": False}
    a = p.get("age") if isinstance(p.get("age"), dict) else {}
    out = {}
    for k in perishables():
        if int(p["cargo"].get(k, 0)) > 0:
            out[k] = round(float(a.get(k, 0.0)), 1)
    return {"on": True, "grace": int(rules()["grace_months"]), "age": out}
