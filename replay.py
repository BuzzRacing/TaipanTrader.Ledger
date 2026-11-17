"""Play a recorded month again and check it comes out the same.

The game journal (journal.py) holds a full snapshot at the start of every
month, the dice seed in force, and every action in order. This tool loads a
snapshot, applies the recorded actions with the recorded dice, and compares
the result with the next snapshot.

  python replay.py                    check every month of the newest game
  python replay.py GAME_ID            check every month of that game
  python replay.py GAME_ID --turn 37  check month 37 only
  python replay.py GAME_ID --from 512 start at the snapshot numbered 512
  python replay.py --list             list the recorded games

"Same" means the rules reproduced the recorded result exactly. After a change
to the rules (engine.py), a difference shows what the change would have done
to that month, which is the point when chasing a bug.

It runs in its own process, so it never touches the game in progress.
"""
import argparse
import copy
import json
import os
import sys

import engine
import journal
import strings
from engine import Game, GameError


def _load_settings(gid, h):
    data = journal._read_json(os.path.join(journal.GAMES, gid, "settings-{}.json".format(h)), None)
    if not data:
        return False
    cfg = data["config"]
    engine.configure(cfg, strings.resolve(cfg, data.get("lang")))
    return True


def _clean(state):
    s = copy.deepcopy(state)
    for p in s.get("players", {}).values():
        p.pop("token", None)
    return s


def _diff(a, b, path="", out=None, limit=12):
    """Where two states differ: a is the journal, b is the replay."""
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a:
                out.append("{}{}: only in the replay".format(path, k))
            elif k not in b:
                out.append("{}{}: only in the journal".format(path, k))
            else:
                _diff(a[k], b[k], "{}{}.".format(path, k), out, limit)
            if len(out) >= limit:
                break
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            _diff(x, y, "{}{}.".format(path, i), out, limit)
            if len(out) >= limit:
                break
    elif a != b:
        text = lambda v: json.dumps(v, ensure_ascii=False)[:90]
        out.append("{}: journal {}, replay {}".format(path.rstrip("."), text(a), text(b)))
    return out


def replay(gid, turn=None, start=None):
    """Returns {"ok", "game", "segments": [...]}; one segment per snapshot-to-snapshot stretch."""
    if not journal.events_path(gid) or not os.path.isfile(journal.events_path(gid)):
        return {"ok": False, "game": gid, "error": "No journal for that game.", "segments": []}
    segments, game, seg, cfg_hash = [], None, None, None

    def close(e, replaced=""):
        nonlocal game, seg
        if game is not None and seg is not None:
            seg["to"] = e["n"] if e else None
            if replaced:
                seg["result"] = "open"
                seg["note"] = "Nothing to compare: the game changed hands here ({}).".format(replaced)
            elif e is None:
                seg["result"] = "open"
                seg["note"] = ("The game ended here; nothing follows." if game.s["phase"] == "ended" else
                               "This stretch has no closing snapshot yet (the month is still being played).")
            else:
                want, got = copy.deepcopy(e["state"]), _clean(game.s)
                if e.get("type") != "turn_begin":      # a restart begins a fresh run of dice, by design
                    want.pop("seed", None)
                    got.pop("seed", None)
                    seg["note"] = "Checked up to a server restart."
                seg["diffs"] = _diff(want, got)
                seg["result"] = "same" if not seg["diffs"] and not seg["errors"] else "different"
            segments.append(seg)
        game, seg = None, None

    for e in journal._iter(gid, full=True):
        if e.get("type") == "journal_open" and not str(e.get("reason", "")).startswith("resumed"):
            close(e, replaced=e.get("reason", ""))
            continue
        if "state" in e:
            close(e)
            wanted = (turn is None or e.get("turn") == turn) and (start is None or e["n"] >= start)
            if start is not None and turn is None and segments:
                wanted = False                     # --from checks one stretch
            if not wanted:
                continue
            if e.get("cfg") != cfg_hash:
                if not _load_settings(gid, e.get("cfg")):
                    segments.append({"from": e["n"], "turn": e.get("turn"), "date": e.get("date"), "result": "skipped",
                                     "note": "The settings file for this stretch is missing.", "errors": [], "diffs": []})
                    continue
                cfg_hash = e.get("cfg")
            state = copy.deepcopy(e["state"])
            game = Game(state=state, seed=state.get("seed"))
            seg = {"from": e["n"], "turn": e.get("turn"), "date": e.get("date"), "kind": e.get("type"),
                   "actions": 0, "errors": [], "diffs": []}
            continue
        if game is None:
            continue
        do = e.get("do")
        if not do:
            continue
        try:
            if do == "join":
                game.join(e.get("name"), e.get("firm"))
            elif do == "act":
                game.act(e["pid"], dict(e["a"]), e.get("present", []))
            elif do == "admin":
                game.admin(e["op"], dict(e.get("a") or {}, op=e["op"]))
            elif do == "resolve":
                if e.get("cause") == "all_ready":
                    # Who was at a screen decides which fights were played by hand (their choices
                    # follow as actions) and which on standing orders.
                    game.resolve("all_ready", e.get("present"))
            elif do == "settings":
                if _load_settings(gid, e.get("cfg")):
                    cfg_hash = e.get("cfg")
                    game.reconcile()
                else:
                    seg["errors"].append("#{}: the settings saved here are missing".format(e["n"]))
            seg["actions"] += 1
        except GameError as x:
            seg["errors"].append("#{} {}: refused in the replay: {}".format(e["n"], e.get("type"), x))
        except Exception as x:                                     # a crash in the rules is a finding too
            seg["errors"].append("#{} {}: crashed in the replay: {!r}".format(e["n"], e.get("type"), x))
    close(None)
    checked = [s for s in segments if s["result"] in ("same", "different")]
    return {"ok": bool(checked) and all(s["result"] == "same" for s in checked), "game": gid,
            "checked": len(checked), "different": sum(1 for s in checked if s["result"] == "different"),
            "segments": segments}


def main():
    ap = argparse.ArgumentParser(description="Play recorded months again and check they come out the same.")
    ap.add_argument("game", nargs="?", help="game id (default: the newest)")
    ap.add_argument("--turn", type=int, help="check this month only (0 is the first)")
    ap.add_argument("--from", dest="start", type=int, help="start at the snapshot with this event number")
    ap.add_argument("--list", action="store_true", help="list recorded games")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    args = ap.parse_args()
    games = journal.games()
    if args.list:
        for m in games:
            print("{}  month {:>3}  {:>6} events  {}".format(m["id"], m.get("turn", 0), m.get("events", 0),
                                                             ", ".join(p["name"] for p in m.get("players", []))))
        return 0
    gid = args.game or (games[0]["id"] if games else None)
    if not gid:
        print("No recorded games yet.")
        return 1
    res = replay(gid, args.turn, args.start)
    if args.json:
        print(json.dumps(res))
        return 0
    if res.get("error"):
        print(res["error"])
        return 1
    for s in res["segments"]:
        print("Month {:>3} ({}), from event #{}: {}".format(s.get("turn"), s.get("date") or "?", s["from"], s["result"].upper()))
        for line in s.get("errors", []) + s.get("diffs", []):
            print("    " + line)
        if s.get("note"):
            print("    " + s["note"])
    print("{}: {} stretch{} checked, {} different.".format(gid, res["checked"], "" if res["checked"] == 1 else "es",
                                                         res["different"]))
    return 0 if res["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
