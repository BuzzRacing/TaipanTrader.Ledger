"""Legends: the Legend and Folklore Library (20 Nov 2026, planned with Anthony one decision at a time; project
doc "SeaTrader Legends Library").

A LEGEND is a big story that breaks into the game. It takes over the Captain's screen when it triggers
(web/legend.js, on the Sea Battle's story stage), is told by one of three storytellers with the Legend's own
characters answering, asks the Captain to choose, and ends in a reckoning card. It costs NO game time: it opens
on a landfall and is played inside that same month, so the Captain comes back to the month they left.

  - Rare and big: about rules.legend.per_game of them start in a game (four to six), spaced out.
  - Chapters: each Legend has 2 to 4. A chapter ends by scheduling the next one some months on; what the
    Captain chose is remembered as flags, and the next chapter opens on them.
  - Stakes scaled to wealth: every effect is sized from the house's STAKE, a share of its net worth
    (rules.legend.stake_share, never under stake_min), so a Legend matters at $50k and at $50M.
  - Admin > Legends: on/off (a game with no Legends at all), how many, how soon, the gap between chapters,
    the stake, who tells them, and each Legend on or off (rules.legend.tale_<key>).

The Legends themselves are data in legend_tales.py; their people are in legend_cast.py; wording in
legend_text.py. All the dice here are the Legends' own (seeded from the game, month and house), so a month with
no Legend rolls exactly as before.

State on the house:
  p["legends"] = {"runs": {tale: {"ch": next chapter, "due": turn, "flags": [...], "teller": cid,
                                  "answers": [{ch, chapter, node, choice, right, port}, ...]}},
                  "done": [tale, ...], "started": n, "last": turn a Legend last began}
  p["legend"]  = the chapter on screen until it is closed: see _open() for its fields.
Actions:  {"type": "legend", "choice": key}   answer the story's question
          {"type": "legend", "done": True}    close the reckoning (schedules the next chapter)
          {"type": "legend", "share_done": id}  close the story of a share just earned (honour.py)

A LEGEND'S SHARE (21 Nov 2026): each chapter marks its right answers (legend_tales.py, "right"). Every answer
is kept on the run; when a chapter closes with enough chapters answered rightly, honour.py pays a port share.
"""
import random

import honour
import legend_cast
import legend_tales

DEFAULTS = {
    "enabled": True,
    "per_game": 5,            # about this many Legends begin in a game
    "first_month": 6,         # none before this month
    "max_running": 2,         # Legends in progress at once
    "gap_min": 6, "gap_max": 14,   # months between chapters, in a 10-year game (scaled to the game's length)
    "stake_share": 0.06, "stake_min": 2000,
    "swing": 0.25,            # each silver or cargo effect varies by this much either way
    "teller": "tale",         # "tale" (each Legend's own), "random", or one storyteller's cast key
    "tale_palace": True,      # each Legend on or off: tale_<key> (a Legend with no switch is on)
    "share": True,            # a Legend's share (honour.py, 21 Nov 2026): share_right right answers in one
    "share_right": 2,         # Legend earn the house a port share, once a game; never shown or hinted
    "eager": False,           # testing: a Legend begins at the first landfall that fits
}
TELLER_MODES = ("tale", "random") + tuple(legend_cast.STORYTELLERS)


def E():
    import engine
    return engine


def rules():
    out = dict(DEFAULTS)
    got = E().R.get("legend")
    if isinstance(got, dict):
        out.update({k: v for k, v in got.items() if k in DEFAULTS})
    return out


def on():
    return bool(rules()["enabled"])


def _dice(g, p, tag):
    """The Legends' own dice: seeded from the game, the month, the house and what is being rolled."""
    return random.Random("legend:{}:{}:{}:{}".format(g.s.get("game_id", ""), g.s["turn"], p.get("name", ""), tag))


def _state(p):
    st = p.get("legends")
    if not isinstance(st, dict):
        st = p["legends"] = {}
    st.setdefault("runs", {})
    st.setdefault("done", [])
    st.setdefault("started", 0)
    st.setdefault("last", -9999)
    return st


def _months(g):
    return max(12, int(g.s.get("years", 10)) * 12)


def _scale(g):
    """Chapter gaps are written for a 10-year game and stretch or shrink with the game's length."""
    return max(0.25, min(4.0, _months(g) / 120.0))


def stake(g, p):
    """The house's stake: what one 'full' Legend effect is worth to it."""
    r = rules()
    return max(float(r["stake_min"]), float(r["stake_share"]) * max(0.0, float(g.worth(p))))


def _tales():
    got = E().R.get("legend")
    got = got if isinstance(got, dict) else {}
    return {k: v for k, v in legend_tales.TALES.items() if got.get("tale_" + k, DEFAULTS.get("tale_" + k, True))}


# ------------------------------------------------------------ triggers --
def on_arrival(g, p, news, port):
    """The fleet has just made port (engine, at landfall). A chapter that is due opens; otherwise a new Legend
    may begin. Nothing happens to a jailed Captain, or while a Legend is already open."""
    e = E()
    if not on() or p.get("legend") or e.jail.jailed(p) or e.jail.pending(p):
        return None
    st, turn = _state(p), g.s["turn"]
    tales = _tales()
    for tid in sorted(st["runs"]):
        run = st["runs"][tid]
        tale = tales.get(tid)
        if not tale or run["ch"] >= len(tale["chapters"]):
            continue
        where = tale["chapters"][run["ch"]].get("where")
        if run["due"] <= turn and where in (None, port):
            return _open(g, p, tid, run["ch"], port)
    return _maybe_begin(g, p, port, tales)


def _maybe_begin(g, p, port, tales):
    r, st, turn = rules(), _state(p), g.s["turn"]
    eager = bool(r["eager"])
    fits = [tid for tid in sorted(tales)
            if tid not in st["done"] and tid not in st["runs"]
            and tales[tid].get("start", {}).get("port") in (None, port)]
    if not fits:
        return None
    running = len(st["runs"])
    if running >= int(r["max_running"]):
        return None
    if not eager:
        per_game = int(r["per_game"])
        left = per_game - int(st["started"])
        months_left = _months(g) - turn
        if left <= 0 or turn < int(r["first_month"]) or months_left <= 0:
            return None
        spacing = _months(g) / float(max(1, per_game) * 2)
        if turn - int(st["last"]) < spacing:
            return None
        # A Legend only fits some landfalls (its port), so each fitting landfall is taken readily: the
        # count is held down by per_game, the spacing and max_running, not by long odds.
        chance = min(1.0, max(0.35, 6.0 * left / float(months_left)))
        if _dice(g, p, "begin").random() >= chance:
            return None
    tid = fits[_dice(g, p, "which").randrange(len(fits))]
    st["started"] = int(st["started"]) + 1
    st["last"] = turn
    st["runs"][tid] = {"ch": 0, "due": turn, "flags": [], "teller": _teller(g, p, tales[tid], tid)}
    return _open(g, p, tid, 0, port)


def _teller(g, p, tale, tid):
    e, mode = E(), str(rules()["teller"])
    if mode in legend_cast.STORYTELLERS:
        return mode
    if mode == "random":
        return legend_cast.STORYTELLERS[_dice(g, p, "teller:" + tid).randrange(len(legend_cast.STORYTELLERS))]
    cid = tale.get("teller")
    return cid if cid in legend_cast.STORYTELLERS else legend_cast.STORYTELLERS[0]


# ---------------------------------------------------------- a chapter --
def _open(g, p, tid, ch_i, port):
    """Put a chapter on the Captain's screen."""
    e = E()
    tale = legend_tales.TALES[tid]
    ch = tale["chapters"][ch_i]
    st = _state(p)
    run = st["runs"][tid]
    flags = set(run.get("flags") or ())
    start = next(node for flag, node in ch["start"] if flag is None or flag in flags)
    p["legend_seq"] = int(p.get("legend_seq", 0)) + 1
    L = p["legend"] = {"id": p["legend_seq"], "tale": tid, "ch": ch_i, "turn": g.s["turn"], "port": port,
                       "teller": run.get("teller") or legend_cast.STORYTELLERS[0], "stake": int(round(stake(g, p))),
                       "node": start, "beats": [], "tally": [], "trail": [], "done": False}
    title, chapter = e.tx("legend.{}.title".format(tid)), e.tx("legend.{}.{}.title".format(tid, ch["id"]))
    p["log"].append(e.tx("l.legend", title=title, chapter=chapter))
    g._ev("legend", "chapter", "{}: the Legend '{}' opened chapter {} ({}) in {}, told by {}; stake {}".format(
        p["name"], tale["title"], ch_i + 1, ch["id"], e.PORTS[port]["name"], L["teller"], e.money(L["stake"])), p,
        tale=tid, chapter=ch["id"], port=port, flags=sorted(flags), stake=L["stake"])
    _enter(g, p, L, start, fresh=True)
    return L


def _chapter(L):
    return legend_tales.TALES[L["tale"]]["chapters"][L["ch"]]


def _enter(g, p, L, name, fresh=False):
    """Walk from a node to the next place the story waits (a choice) or stops (the end), collecting the lines
    to show and applying each node's effects on the way."""
    ch = _chapter(L)
    L["beats"] = []
    while True:
        node = ch["nodes"][name]
        L["node"] = name
        L["trail"].append(name)
        for i in range(len(node.get("beats") or ())):
            L["beats"].append([name, i])
        for fx in node.get("fx") or ():
            _apply(g, p, L, fx)
        if node.get("choices"):
            return
        if node.get("end"):
            L["done"] = True
            _finish(g, p, L)
            return
        if node.get("goto"):
            name = node["goto"]
            continue
        flags = set(_state(p)["runs"][L["tale"]].get("flags") or ())
        table = node["roll"]
        for flag in sorted(node.get("roll_if") or {}):
            if flag in flags:
                table = node["roll_if"][flag]
                break
        own = _dice(g, p, "roll:{}:{}:{}".format(L["tale"], L["ch"], name))
        pick = own.uniform(0, sum(w for w, _t in table))
        for w, target in table:
            pick -= w
            if pick <= 0:
                break
        g._ev("legend", "roll", "{}: the Legend's dice at {}.{} fell on {}".format(
            p["name"], _chapter(L)["id"], name, target), p, tale=L["tale"], node=name, to=target,
            table=[[w, t] for w, t in table])
        name = target


def _finish(g, p, L):
    """The chapter's story is over: is there another to come?"""
    tale = legend_tales.TALES[L["tale"]]
    L["more"] = L["ch"] + 1 < len(tale["chapters"])


# ------------------------------------------------------------ effects --
def _where(p, L, where):
    e = E()
    port = {"here": L["port"], "home": e.home_of(p)}.get(where, where)
    return port if port in e.PORTS else None


def _apply(g, p, L, fx):
    e, r = E(), rules()
    kind = fx[0]
    own = _dice(g, p, "fx:{}:{}:{}:{}".format(L["tale"], L["ch"], L["node"], len(L["tally"])))
    swing = 1.0 + own.uniform(-float(r["swing"]), float(r["swing"]))
    base = float(L["stake"])
    if kind == "flag":
        run = _state(p)["runs"][L["tale"]]
        if fx[1] not in run["flags"]:
            run["flags"].append(fx[1])
        return
    if kind == "news":
        g.s.setdefault("pending_news", []).append(e.tx(fx[1], name=p["name"], firm=p["firm"]))
        return
    if kind == "silver":
        amount = int(round(base * float(fx[1]) * swing))
        if amount > 0:
            p["cash"] += amount
            g._book(p, "legend", amount)
            L["tally"].append({"kind": "silver", "amount": amount})
        elif amount < 0:
            owe = -amount
            cash = int(min(max(0, p["cash"]), owe))
            p["cash"] -= cash
            bank = int(min(max(0, p.get("bank", 0)), owe - cash))
            p["bank"] = p.get("bank", 0) - bank
            debt = owe - cash - bank
            if debt > 0:
                p["debt"] = p.get("debt", 0) + debt
            g._book(p, "legend", -owe)
            L["tally"].append({"kind": "silver", "amount": -owe, "debt": int(debt)})
        return
    if kind == "cargo":
        good = fx[1]
        if good not in e.GOODS:
            return
        value = base * float(fx[2]) * swing
        price = max(1.0, float(e.GOODS[good]["base"]))
        room = max(0, int(g.capacity(p) - g.used(p)))
        want = int(value / price)
        qty = min(want, room)
        if qty > 0:
            had = int(p["cargo"].get(good, 0))
            basis = p.setdefault("basis", {})
            basis[good] = round(float(basis.get(good, 0.0)) * had / float(had + qty), 2)   # a gift costs nothing
            p["cargo"][good] = had + qty
            L["tally"].append({"kind": "cargo", "good": good, "qty": qty, "value": int(round(qty * price))})
        rest = int(round((want - qty) * price))
        if rest > 0:                                  # what the hold had no room for comes as silver
            p["cash"] += rest
            g._book(p, "legend", rest)
            L["tally"].append({"kind": "silver", "amount": rest})
        return
    if kind == "lose_cargo":
        share = max(0.0, min(1.0, float(fx[1])))
        lost = {}
        for good in sorted(p["cargo"]):
            q = int(p["cargo"][good])
            n = min(q, int(round(q * share * own.uniform(0.85, 1.15))))
            if n > 0:
                lost[good] = n
        if lost:
            g._book(p, "overboard", -g._cost_of(p, lost))
            for good, n in lost.items():
                p["cargo"][good] -= n
                if p["cargo"][good] <= 0:
                    del p["cargo"][good]
        L["tally"].append({"kind": "lose_cargo", "goods": lost})
        return
    if kind == "hull":
        share = max(0.0, min(1.0, float(fx[1])))
        total = 0
        for sh in p["ships"]:
            spec = e.SHIPS.get(sh["type"])
            if not spec:
                continue
            took = min(max(0, int(sh["hull"]) - 1), int(round(float(spec["hull"]) * share)))   # never sunk
            sh["hull"] -= took
            total += took
        L["tally"].append({"kind": "hull", "amount": int(total)})
        return
    if kind == "standing":
        port = _where(p, L, fx[1])
        if not port:
            return
        done = g._standing(p, port, float(fx[2]), "legend", roll=False)
        L["tally"].append({"kind": "standing", "port": port, "change": round(float(done), 1)})
        return
    raise ValueError("legend effect {!r}".format(kind))


# ------------------------------------------------------------- actions --
def act(g, p, a):
    e = E()
    if a.get("share_done") is not None:
        return honour.act_done(g, p, a)               # the story of a share just earned is closed
    L = p.get("legend")
    if not isinstance(L, dict):
        raise e.GameError(e.tx("e.legend_none"))
    ch = _chapter(L)
    if a.get("done"):
        if not L.get("done"):
            raise e.GameError(e.tx("e.legend_first"))
        return _close(g, p, L)
    if L.get("done"):
        raise e.GameError(e.tx("e.legend_choice"))
    node = ch["nodes"][L["node"]]
    pick = next((c for c in node.get("choices") or () if c[0] == a.get("choice")), None)
    if pick is None:
        raise e.GameError(e.tx("e.legend_choice"))
    # Was it the right answer (the chapter's "right" map)? Kept on the run for a Legend's share (honour.py);
    # the Captain is never told.
    right = pick[0] in ((ch.get("right") or {}).get(L["node"]) or ())
    run = _state(p)["runs"].get(L["tale"])
    if isinstance(run, dict):
        run.setdefault("answers", []).append({"ch": L["ch"], "chapter": ch["id"], "node": L["node"],
                                              "choice": pick[0], "right": right, "port": L.get("port")})
    g._ev("legend", "choice", "{}: in the Legend '{}' ({}), chose: {}{}".format(
        p["name"], legend_tales.TALES[L["tale"]]["title"], ch["id"], pick[1], " (the right answer)" if right else ""), p,
        tale=L["tale"], chapter=ch["id"], node=L["node"], choice=pick[0], right=right)
    L["chose"] = (L.get("chose") or []) + [[L["node"], pick[0]]]
    _enter(g, p, L, pick[2])
    return e.tx("m.legend_choice")


def _close(g, p, L):
    """The reckoning is closed: schedule the next chapter, or the Legend is told."""
    e, r = E(), rules()
    st = _state(p)
    tid = L["tale"]
    tale = legend_tales.TALES[tid]
    run = st["runs"].get(tid) or {"flags": []}
    if L["ch"] + 1 < len(tale["chapters"]):
        own = _dice(g, p, "gap:{}:{}".format(tid, L["ch"]))
        lo, hi = sorted((float(r["gap_min"]), float(r["gap_max"])))
        gap = max(1, int(round(own.uniform(lo, hi) * _scale(g))))
        gap = min(gap, max(1, (_months(g) - g.s["turn"]) // max(1, len(tale["chapters"]) - L["ch"] - 1)))
        run["ch"], run["due"] = L["ch"] + 1, g.s["turn"] + gap
        st["runs"][tid] = run
        g._ev("legend", "closed", "{}: chapter {} of '{}' closed; the next is due from month {}".format(
            p["name"], L["ch"] + 1, tale["title"], run["due"]), p, tale=tid, due=run["due"], tally=L["tally"])
    else:
        st["runs"].pop(tid, None)
        if tid not in st["done"]:
            st["done"].append(tid)
        p["log"].append(e.tx("l.legend_end", title=e.tx("legend.{}.title".format(tid))))
        g._ev("legend", "told", "{}: the Legend '{}' is told (flags: {})".format(
            p["name"], tale["title"], ", ".join(run.get("flags") or []) or "none"), p, tale=tid,
            flags=list(run.get("flags") or []), tally=L["tally"])
    p.pop("legend", None)
    honour.on_legend_closed(g, p, L, run)             # enough right answers in this Legend: a port share
    return e.tx("m.legend_done")


# ---------------------------------------------------------------- view --
def speakers(L):
    """[(cast key, wording key)] for every line now on the screen (the server finds each one's voice clip)."""
    ch = _chapter(L)
    tid = L["tale"]
    out = []
    for name, i in L.get("beats") or ():
        lines = (ch["nodes"].get(name) or {}).get("beats") or ()
        if i >= len(lines):
            continue        # a Legend open on screen while its wording was shortened: skip the lines now gone
        who = lines[i][0]
        out.append((L["teller"] if who == legend_tales.T else who, legend_tales._key(tid, ch["id"], name, i)))
    return out


def view(g, p):
    L = p.get("legend")
    if not isinstance(L, dict):
        return None
    e = E()
    tid = L["tale"]
    tale = legend_tales.TALES.get(tid)
    if not tale:
        return None
    ch = _chapter(L)
    port = e.PORTS[L["port"]]["name"] if L["port"] in e.PORTS else ""
    beats = [{"who": who, "side": "left" if who == L["teller"] else "right", "text": e.tx(key, port=port)}
             for who, key in speakers(L)]
    node = ch["nodes"][L["node"]]
    choices = [] if L.get("done") else [
        {"key": c[0], "label": e.tx("legend.{}.{}.{}.c.{}".format(tid, ch["id"], L["node"], c[0]))}
        for c in node.get("choices") or ()]
    out = {"id": L["id"], "tale": tid, "title": e.tx("legend.{}.title".format(tid)),
           "chapter": e.tx("legend.{}.{}.title".format(tid, ch["id"])), "n": L["ch"] + 1, "of": len(tale["chapters"]),
           "chapter_id": ch["id"], "teller": L["teller"], "cast": list(tale.get("cast") or ()), "port": L["port"],
           "scene": ch.get("scene", "port"),
           "node": L["node"], "step": len(L.get("trail") or ()), "beats": beats, "choices": choices,
           "done": bool(L.get("done")), "more": bool(L.get("more")), "tally": list(L.get("tally") or ()),
           "stake": L.get("stake", 0)}
    return out


def book(g, p):
    """The Legends this house has met: [{tale, title, state: 'running' | 'told', chapter, of}] (for a Legends page)."""
    e, st = E(), _state(p) if isinstance(p.get("legends"), dict) else {"runs": {}, "done": []}
    out = []
    for tid in st["done"]:
        if tid in legend_tales.TALES:
            n = len(legend_tales.TALES[tid]["chapters"])
            out.append({"tale": tid, "title": e.tx("legend.{}.title".format(tid)), "state": "told", "chapter": n, "of": n})
    for tid, run in sorted(st["runs"].items()):
        if tid in legend_tales.TALES:
            out.append({"tale": tid, "title": e.tx("legend.{}.title".format(tid)), "state": "running",
                        "chapter": int(run.get("ch", 0)), "of": len(legend_tales.TALES[tid]["chapters"])})
    return out
