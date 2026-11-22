"""The Robbery Story (22 Nov 2026, Anthony: "a quick Robbery Story ... one screen for the robbery, the persona and what
was taken, and then back to the game").

A ROBBERY is the month-end street mugging (engine, "robbed ashore": silver from the purse) or the break-in at a
warehouse the house keeps (engine._rob_warehouses: a share of the stock). Both used to be a line in the Captain's
Log. Now, when nothing else has happened, the Captain also gets ONE screen (web/robbery.js): Magpie (cast key
"thieves"), her own line aloud, and what was taken. Then back to the game. No game time, no choices.

ONE STORY A MONTH (Anthony's rule): the Robbery Story is told only when the month has no other story. If there was
a Sea Battle, a jail (arrest, plea or release), a storm, a Legend, a share's honour story or a promotion, the robbery
is only a line in the Captain's Log as before. "I don't want to go from Sea Battle to Jail to Robbery."
The month's other stories are not all known when the robbery rolls (a promotion is decided after it), so a robbery
only NOTES a candidate (note) and settle() decides once the month is done. When a month has both a mugging and a
warehouse break-in, the bigger loss is the one told.

State on the house:
  p["rob_cand"] = [{kind, port, value, ...}, ...]   this month's robberies, until settle() (never saved past it)
  p["robbery"]  = the story on screen until "Back to the game": {id, turn, kind: "street" | "house", port, value,
                  silver, left (street) | goods {good: qty}, qty, pct (house)}
Action: {"type": "robbery_ack"} closes it.
"""

WHO = "thieves"
DEFAULTS = {
    "enabled": True,
}


def E():
    import engine
    return engine


def rules():
    out = dict(DEFAULTS)
    got = E().R.get("robbery")
    if isinstance(got, dict):
        out.update({k: v for k, v in got.items() if k in DEFAULTS})
    return out


def on():
    return bool(rules()["enabled"])


def note(g, p, kind, port, **data):
    """A robbery has just happened this month. kind: "street" or "house". data: value (what it cost, for choosing the
    bigger) plus the fields the screen shows. Nothing is on screen yet: settle() decides."""
    if not on():
        return
    p.setdefault("rob_cand", []).append(dict(data, kind=kind, port=port))


def other_story(g, p):
    """What else has the month's story, or None. The first thing found is named in the event log."""
    e = E()
    if p.get("robbery"):
        return "an earlier robbery still on screen"
    if p.get("fights") or p.get("battle") is not None:
        return "a sea battle"
    if e.jail.jailed(p) or e.jail.pending(p) or p.get("jail_freed"):
        return "the jail"
    if p.get("storm"):
        return "a storm"
    if p.get("legend"):
        return "a Legend"
    if p.get("honour_queue"):
        return "an honour story"
    if p.get("promotions"):
        return "a promotion"
    return None


def settle(g, p):
    """The month is done (after promotions): tell the robbery as a story, or leave it as a line in the log.
    Returns the story or None. Always clears this month's candidates."""
    cands = p.pop("rob_cand", None)
    if not cands or not on():
        return None
    e = E()
    why = other_story(g, p)
    if why:
        g._ev("robbery", "robbery_skipped", "{}: robbed, but {} already has this month's story, so no Robbery Story".format(
            p["name"], why), p, kinds=[c["kind"] for c in cands])
        return None
    best = max(cands, key=lambda c: float(c.get("value") or 0))
    serial = int(p.get("robbery_serial", 0)) + 1
    p["robbery_serial"] = serial
    story = dict(best, id=serial, turn=int(g.s["turn"]))
    p["robbery"] = story
    g._ev("robbery", "robbery_story", "{}: the Robbery Story ({}, {}, worth {})".format(
        p["name"], story["kind"], e.PORTS[story["port"]]["name"] if story["port"] in e.PORTS else story["port"],
        e.money(story.get("value") or 0)), p, what=story["kind"], port=story["port"], value=story.get("value"))
    return story


def act_ack(g, p, a):
    """robbery_ack: the Captain has seen it; back to the game."""
    e = E()
    st = p.pop("robbery", None)
    if st:
        g._ev("robbery", "robbery_ack", "{} closed the Robbery Story ({})".format(p["name"], st.get("kind")), p)
    return e.tx("m.robbery_ack")


def view(g, p):
    st = p.get("robbery")
    return dict(st) if isinstance(st, dict) else None
