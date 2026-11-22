"""The last two shares (owner's decisions, 21 Nov 2026, made one at a time; project doc "SeaTrader Last Two
Shares").

A captain can hold ten port shares. Eight are earned with silver: one for each promotion, Trader to Hong Master
(engine.Game._promote). The last two are HONOURS, things silver cannot buy, one share each:

  flag     LI YUE'S FLAG. Sink Admiral Li Yue's whole war fleet often enough in one game: rules.estates
           flag_wins_5 / _10 / _20 / _50 for a game of that many years (2, 3, 5, 8). Only a fight of kind
           "lord" that ends "won" counts. Tribute paid, running, breaking off and retreating do not.
  legend   A LEGEND'S SHARE. Answer rules.legend.share_right chapters of one Legend rightly (2 of 3). Each
           chapter marks its right answer in legend_tales.py ("right"); the first Legend to get there pays,
           once a game. No dice.

Decided with them:
  - HIDDEN. Neither count is shown to the Captain anywhere, and nothing on a button says which answer is
    right. Both shares arrive as a surprise. (The Admin journal records every step.)
  - NEVER SEIZED. At bankruptcy the moneylender leaves one placed share where it is for each honour the house
    holds (rules.estates.honours_safe; engine.Game._bankrupt asks kept()).
  - ITS OWN QUICK STORY. Earning one puts a two-page story on the Captain's screen (web/legend.js, on the
    Legend's stage): page one is the share, handed over by whoever lost it (Li Yue herself, or the Legend's
    storyteller) with one spoken line; page two is a small result panel, under half the screen, listing what
    earned it (the right choices, or the fleets sunk) beside a key picture from the story.

State on the house:
  p["lord_wins"] = [{"turn", "dest", "n"}, ...]        every war fleet sunk, in order
  p["honours"]   = {"flag": {...}, "legend": {...}}    the honours held (each is one share)
  p["honour_queue"] = [story, ...]                     stories still to be shown; the first is on screen
A Legend's answers are kept on its run: p["legends"]["runs"][tale]["answers"] (legend.py).
Action:  {"type": "legend", "share_done": id}          close the story on screen
Wording: legend_text.py, keys legend.share.* (and l.honour_*, n.honour_flag).
"""
import random

KINDS = ("flag", "legend")
FLAG_YEARS = (5, 10, 20, 50)            # the game lengths with a setting of their own
FLAG_SPEAKER = "pirate"                 # Admiral Li Yue hands over her own flag
SAY_LINES = 4                           # at most this many lines in each speaker's bank


def E():
    import engine
    return engine


def _estates():
    return E().R.get("estates") or {}


def _legend_rules():
    import legend
    return legend.rules()


def held(p):
    got = p.get("honours")
    return got if isinstance(got, dict) else {}


def _dice(g, p, tag):
    """The honours' own dice (which line is said), so no other roll in the game moves."""
    return random.Random("honour:{}:{}:{}:{}".format(g.s.get("game_id", ""), g.s["turn"], p.get("name", ""), tag))


# ------------------------------------------------------------ the counts --
def flag_on():
    e = _estates()
    return bool(e.get("shares_enabled", True)) and bool(e.get("flag_enabled", True))


def flag_need(g):
    """War fleets to sink in this game: the setting for its length, or for the nearest shorter one."""
    e = _estates()
    years = int(g.s.get("years") or E().R["game"].get("default_years", 10))
    fit = [y for y in FLAG_YEARS if y <= years]
    if fit:
        return max(1, int(e.get("flag_wins_{}".format(fit[-1]), 3)))
    return max(1, int(e.get("flag_wins_{}".format(FLAG_YEARS[0]), 2)) - 1)      # a game shorter than five years


def legend_on():
    return bool(_estates().get("shares_enabled", True)) and bool(_legend_rules().get("share", True))


def legend_need():
    return max(1, int(_legend_rules().get("share_right", 2)))


def right_chapters(run):
    """The chapters of a Legend answered rightly: [{ch, chapter, node, choice, port}], one for each chapter in
    which every question the Captain was asked got its right answer."""
    by_ch = {}
    for a in (run or {}).get("answers") or ():
        by_ch.setdefault(int(a["ch"]), []).append(a)
    out = []
    for ch in sorted(by_ch):
        got = by_ch[ch]
        if got and all(a.get("right") for a in got):
            out.append({k: got[-1].get(k) for k in ("ch", "chapter", "node", "choice", "port")})
    return out


# ---------------------------------------------------------------- earning --
def on_lord_win(g, p, b):
    """The pirate queen's whole war fleet is sunk (engine, as the fight closes)."""
    wins = p.setdefault("lord_wins", [])
    wins.append({"turn": int(g.s["turn"]), "dest": b.get("dest"), "n": int(b.get("n", 0) or 0)})
    need = flag_need(g)
    g._ev("battle", "lord_win", "{}: Li Yue's war fleet sunk, {} this game ({} earn her flag){}".format(
        p["name"], len(wins), need, "" if flag_on() else "; the award is switched off"), p,
        wins=len(wins), need=need)
    if not flag_on() or "flag" in held(p) or len(wins) < need:
        return False
    counted = [dict(w) for w in wins[-need:]]
    return _grant(g, p, "flag", {"wins": counted, "need": need, "dest": b.get("dest")}, news=True)


def on_legend_closed(g, p, L, run):
    """A Legend's chapter has just been closed (legend._close): were enough of its answers right?"""
    if not legend_on() or "legend" in held(p):
        return False
    right = right_chapters(run)
    need = legend_need()
    if len(right) < need:
        return False
    return _grant(g, p, "legend", {"tale": L["tale"], "teller": L.get("teller"), "right": right, "need": need,
                                   "port": L.get("port")})


def _grant(g, p, kind, data, news=False):
    e = E()
    got = g.award_shares(p, 1, kind, log="l.honour_" + kind)
    if got <= 0:                          # shares switched off, or the house already holds every share it may
        g._ev("finance", "honour_missed", "{}: earned the {} honour, but can hold no more shares".format(
            p["name"], kind), p, honour=kind)
        return False
    p.setdefault("honours", {})[kind] = dict(data, turn=int(g.s["turn"]))
    p["honour_seq"] = int(p.get("honour_seq", 0)) + 1
    who = FLAG_SPEAKER if kind == "flag" else (data.get("teller") or "")
    story = dict(data, id=p["honour_seq"], kind=kind, turn=int(g.s["turn"]), who=who, say=_say_key(g, p, kind, who))
    p.setdefault("honour_queue", []).append(story)
    g._ev("finance", "honour", "{} earned a port share: the {} honour".format(p["name"], kind), p,
          honour=kind, **{k: v for k, v in data.items() if k in ("wins", "right", "tale", "need")})
    if news and g.s.get("sea") is not None:
        g.s["sea"]["news"].append(e.tx("n.honour_flag", name=p["name"], firm=p["firm"]))
    return True


def _say_key(g, p, kind, who):
    """One line from the speaker's own bank (legend.share.say.<bank>.N), drawn with the honours' own dice."""
    e = E()
    banks = ["flag"] if kind == "flag" else [who, "any"]
    for bank in banks:
        keys = [k for k in ("legend.share.say.{}.{}".format(bank, i) for i in range(SAY_LINES)) if k in e.TEXT]
        if keys:
            return keys[_dice(g, p, "say:" + kind).randrange(len(keys))]
    return ""


# ------------------------------------------------------------- bankruptcy --
def kept(p):
    """How many of the house's shares the moneylender may not touch: one for each honour it holds."""
    if not _estates().get("honours_safe", True):
        return 0
    return sum(1 for k in KINDS if k in held(p))


# ------------------------------------------------------------------ story --
def pending(p):
    q = p.get("honour_queue")
    return q[0] if isinstance(q, list) and q else None


def act_done(g, p, a):
    e = E()
    story = pending(p)
    if not story or a.get("share_done") != story.get("id"):
        raise e.GameError(e.tx("e.honour_none"))
    p["honour_queue"].pop(0)
    g._ev("finance", "honour_seen", "{} closed the story of the {} honour".format(p["name"], story.get("kind")), p,
          honour=story.get("kind"))
    return e.tx("m.honour_done")


def _port_name(port):
    e = E()
    return e.PORTS[port]["name"] if port in e.PORTS else ""


def view(g, p):
    """The honour story on the Captain's screen, or None. web/legend.js shows it once the battle, the storm, the
    jail and any Legend have had the screen."""
    story = pending(p)
    if not story:
        return None
    e = E()
    import legend_tales
    kind = story["kind"]
    out = {"id": story["id"], "kind": kind, "who": story.get("who") or "", "turn": story["turn"],
           "date": e.date_label(story["turn"]), "need": int(story.get("need", 0) or 0),
           "title": e.tx("legend.share.{}.title".format(kind)),
           "say": e.tx(story["say"]) if story.get("say") else "",
           "earned": g.shares_earned(p), "cap": g.share_cap(), "free": g.shares_free(p), "safe": kept(p) > 0,
           "rows": [], "port": story.get("port") or story.get("dest") or ""}
    if kind == "flag":
        out["sub"] = e.tx("legend.share.flag.sub")
        for w in story.get("wins") or ():
            port = _port_name(w.get("dest"))
            out["rows"].append({"head": e.date_label(int(w["turn"])),
                                "text": e.tx("legend.share.flag.row" if port else "legend.share.flag.row_sea",
                                             n=int(w.get("n", 0)), port=port)})
    else:
        tid = story.get("tale")
        tale = legend_tales.TALES.get(tid) or {}
        chapters = tale.get("chapters") or []
        out.update(tale=tid, sub=e.tx("legend.{}.title".format(tid)) if tale else "", cast=list(tale.get("cast") or ()))
        for r in story.get("right") or ():
            i = int(r.get("ch", 0))
            ch = chapters[i] if 0 <= i < len(chapters) else None
            if not ch:
                continue
            out["rows"].append({
                "head": e.tx("legend.share.legend.row", n=i + 1, chapter=e.tx("legend.{}.{}.title".format(tid, ch["id"]))),
                "text": e.tx("legend.{}.{}.{}.c.{}".format(tid, ch["id"], r.get("node"), r.get("choice")))})
            if "chapter_id" not in out:               # the picture that jogs the memory: the first right chapter's
                out.update(chapter_id=ch["id"], scene=ch.get("scene", "port"), chapter=e.tx(
                    "legend.{}.{}.title".format(tid, ch["id"])), port=r.get("port") or out["port"])
    return out
