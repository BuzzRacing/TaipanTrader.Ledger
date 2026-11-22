"""The Captain's Manual's server side (/Manual, 21 Nov 2026).

/api/manual      the book's layout, but only for a captain with a seat in the game (Anthony, 21 Nov 2026).
/api/manual/say  the spoken clip for one persona line, made only when the player asks to hear it, so a line is
                 paid for once and never before it is wanted (the clip is cached by voice.py).

Wording is not sent here: the page reads every "man.*" line from /api/info like the rest of the game, so
Admin > Language & Text edits it and a Family-friendly screen gets the family wording.
"""
import engine
import manual_text
import strings
import voice


def seat(game, token):
    """The seat (player id) a token holds in the game now being played, or None."""
    return game.pid_for_token(token) if token else None


def view(game, token):
    """The layout for a seated captain; a short refusal for anyone else."""
    pid = seat(game, token)
    if not pid:
        return {"ok": False, "seat": True, "error": engine.tx("man.e_seat")}
    me = game.s["players"].get(pid) or {}
    return {"ok": True, "seated": True, "name": me.get("name", ""), "firm": me.get("firm", ""),
            "chapters": manual_text.chapters()}


def say(game, token, key, family=False):
    """{"ok": True, "item": {c, u}} for a persona line, or {"ok": False} when there is nothing to play."""
    if not seat(game, token):
        return {"ok": False, "seat": True, "error": engine.tx("man.e_seat")}
    cid = manual_text.SPEAKER.get(key)
    if not cid or not voice.PLAN.ready():
        return {"ok": False}
    if family:
        text = strings.FAMILY.get(key) or strings.EN.get(key)
    else:
        text = engine.TEXT.get(key) or strings.EN.get(key)
    item = voice.PLAN._clip(text, cid) if text else None
    if not item:
        return {"ok": False}
    if family:
        item.pop("f", None)          # a family screen already has the family wording; one clip is enough
    return {"ok": True, "item": item}
