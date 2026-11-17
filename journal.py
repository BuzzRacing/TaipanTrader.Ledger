"""SeaTrader records: the game journal and the server log.

Two records are kept under the `journal` folder, next to `saves`:

  journal/games/<game id>/events.jsonl   everything that happened in one game,
                                          one event per line, in order
  journal/games/<game id>/meta.json      a small summary for the list of games
  journal/games/<game id>/settings-*.json  the settings in force (kept so a
                                          month can be played again exactly)
  journal/server/server-YYYY-MM-DD.log   the technical log, one file per day

A game's journal is kept until it is deleted; the oldest are pruned once there
are more than "Game journals to keep" (Admin > Game Setup). Server logs older
than "Days of server log to keep" are deleted. Secrets are never written: no
admin password, no Inworld key, no seat tokens.

The Admin page reads all of this on its Captain's Report page. The files are
plain text, so they can also be opened in any editor.
"""
import collections
import hashlib
import json
import os
import re
import shutil
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(ROOT, "journal")
GAMES = os.path.join(DIR, "games")
SERVER = os.path.join(DIR, "server")
GID_RE = re.compile(r"^g[0-9A-Za-z-]{1,40}$")
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SECRET_KEYS = ("token", "password", "current", "key", "api_key")

SESSION = time.strftime("s%Y%m%d-%H%M%S")     # one per run of the server
KEEP = {"games": 50, "days": 30}

_lock = threading.RLock()
_cur = None                 # the game being recorded: {"gid", "dir", "n", "meta", "cfg", "game"}
_recent = collections.deque(maxlen=600)       # the newest events of the current game, for the live console
_index_cache = {}           # gid -> (file size, index)
_warned = False
_last_prune_day = ""


def configure(cfg):
    """Take the retention settings from the game's settings."""
    j = (cfg or {}).get("journal") or {}
    KEEP["games"] = int(j.get("keep_games", 50))
    KEEP["days"] = int(j.get("server_days", 30))


def _stamp(now=None):
    now = time.time() if now is None else now
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)) + ".{:03d}".format(int(now * 1000) % 1000)


def _fail(e):
    global _warned
    if not _warned:
        _warned = True
        print("Could not write to the journal folder ({}). The game carries on without records.".format(e))


def _scrub(value):
    """Drop anything secret before it is written."""
    if isinstance(value, dict):
        return {k: ("(hidden)" if k in SECRET_KEYS else _scrub(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub(v) for v in value]
    return value


def _append(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


# ------------------------------------------------------------ server log --
def log(level, cat, msg, **data):
    """One line in today's server log. level: DEBUG, INFO, WARN or ERROR."""
    global _last_prune_day
    now = time.time()
    line = {"t": int(now * 1000), "at": _stamp(now), "level": level, "cat": cat, "msg": msg, "session": SESSION}
    if data:
        line.update(_scrub(data))
    day = time.strftime("%Y-%m-%d", time.localtime(now))
    with _lock:
        try:
            _append(os.path.join(SERVER, "server-{}.log".format(day)), line)
        except OSError as e:
            _fail(e)
        if day != _last_prune_day:
            _last_prune_day = day
            prune()
    return line


def server_days():
    if not os.path.isdir(SERVER):
        return []
    out = []
    for f in sorted(os.listdir(SERVER), reverse=True):
        m = re.match(r"^server-(\d{4}-\d{2}-\d{2})\.log$", f)
        if m:
            out.append({"day": m.group(1), "size": os.path.getsize(os.path.join(SERVER, f))})
    return out


def server_log(day=None, level=None, q=None, limit=1500):
    """The newest lines of one day's server log (today's by default)."""
    day = day if day and DAY_RE.match(day) else time.strftime("%Y-%m-%d")
    path = os.path.join(SERVER, "server-{}.log".format(day))
    order = {"DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3}
    floor = order.get(level or "DEBUG", 0)
    q = (q or "").lower()
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for raw in f:
                try:
                    e = json.loads(raw)
                except ValueError:
                    continue
                if order.get(e.get("level"), 1) < floor:
                    continue
                if q and q not in raw.lower():
                    continue
                out.append(e)
    except OSError:
        pass
    return {"day": day, "total": len(out), "lines": out[-limit:]}


# ---------------------------------------------------------- game journal --
def _game_dir(gid):
    return os.path.join(GAMES, gid) if GID_RE.match(gid or "") else None


def events_path(gid):
    d = _game_dir(gid)
    return os.path.join(d, "events.jsonl") if d else None


def _count_lines(path):
    n = 0
    try:
        with open(path, "rb") as f:
            for _ in f:
                n += 1
    except OSError:
        pass
    return n


def _settings_hash(cfg, lang):
    blob = json.dumps({"config": cfg, "lang": lang}, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()[:12]


def _store_settings(cfg, lang):
    """Keep a copy of the settings in force with the game, once per distinct set."""
    h = _settings_hash(cfg, lang)
    path = os.path.join(_cur["dir"], "settings-{}.json".format(h))
    if not os.path.isfile(path):
        _write_json(path, {"config": cfg, "lang": lang})
    _cur["cfg"] = h
    return h


def _touch_meta(e=None, write=False):
    """Keep the summary up to date. Called with the lock held."""
    m, game = _cur["meta"], _cur["game"]
    s = game.s
    m.update({"events": _cur["n"], "updated": int(time.time()), "turn": s["turn"], "phase": s["phase"],
              "years": s["years"], "players": [{"id": p["id"], "name": p["name"], "firm": p["firm"]}
                                               for p in (s["players"][i] for i in s["order"])]})
    if e is not None:
        if e.get("date"):
            m["date"] = e["date"]
        if e.get("type") == "game_over":
            m["standings"] = e.get("standings", [])
        if e.get("cat") == "error":
            m["errors"] = m.get("errors", 0) + 1
        if e.get("cat") == "rejected":
            m["rejected"] = m.get("rejected", 0) + 1
    if write:
        try:
            _write_json(os.path.join(_cur["dir"], "meta.json"), m)
        except OSError as x:
            _fail(x)


def record(e):
    """Write one event to the current game's journal. This is Game.on_event."""
    with _lock:
        if _cur is None:
            return
        now = time.time()
        _cur["n"] += 1
        line = {"n": 0, "t": 0, "at": ""}
        line.update(_scrub(e) if "state" not in e else e)      # snapshots are already clean, and large
        line.update({"n": _cur["n"], "t": int(now * 1000), "at": _stamp(now)})   # never let an event's own data replace these
        if "state" in line:
            line["cfg"] = _cur["cfg"]
        try:
            _append(os.path.join(_cur["dir"], "events.jsonl"), line)
        except OSError as x:
            _fail(x)
        _recent.append({k: v for k, v in line.items() if k != "state"})
        heavy = "state" in line or line.get("type") in ("seat_new", "game_started", "game_over", "journal_open",
                                                         "journal_close")
        _touch_meta(line, write=heavy)


def note(cat, kind, msg, **data):
    """An event that comes from the server rather than the rules (a device
    connecting, a crash, the server stopping)."""
    with _lock:
        if _cur is None:
            return
        e = {"turn": _cur["game"].s["turn"], "cat": cat, "type": kind, "msg": msg}
        e.update(data)
        record(e)


def open_game(game, reason, cfg, lang, kind="checkpoint"):
    """Start recording a game (new, resumed after a restart, or restored from a save)."""
    global _cur
    with _lock:
        gid = game.s["game_id"]
        d = _game_dir(gid)
        if d is None:                       # a hand-edited save with an odd id: give it a clean one
            gid = game.s["game_id"] = time.strftime("g%Y%m%d-%H%M%S-") + hashlib.sha1(str(gid).encode()).hexdigest()[:4]
            d = _game_dir(gid)
        path = os.path.join(d, "events.jsonl")
        meta = _read_json(os.path.join(d, "meta.json"), None) or {"id": gid, "started": int(time.time()), "keep": False}
        meta.setdefault("sessions", [])
        if SESSION not in meta["sessions"]:
            meta["sessions"].append(SESSION)
        _recent.clear()
        _cur = {"gid": gid, "dir": d, "n": _count_lines(path), "meta": meta, "cfg": "", "game": game}
        try:
            os.makedirs(d, exist_ok=True)
            _store_settings(cfg, lang)
        except OSError as x:
            _fail(x)
        game.on_event = record
        record({"turn": game.s["turn"], "cat": "system", "type": "journal_open",
                "msg": "Recording {}: {}".format(gid, reason), "reason": reason, "session": SESSION})
        game.checkpoint(kind, note=reason)
    log("INFO", "game", "Recording game {} ({})".format(gid, reason), game=gid)
    prune()
    return gid


def close_game(reason):
    """Stop recording the current game (it was replaced, or the server is stopping)."""
    global _cur
    with _lock:
        if _cur is None:
            return
        record({"turn": _cur["game"].s["turn"], "cat": "system", "type": "journal_close", "msg": reason})
        _cur["game"].on_event = None
        _cur = None


def current():
    with _lock:
        return _cur["gid"] if _cur else None


def _flat(d, prefix=""):
    out = {}
    for k, v in d.items():
        path = prefix + str(k)
        if isinstance(v, dict):
            out.update(_flat(v, path + "."))
        else:
            out[path] = v
    return out


def _short(v):
    text = json.dumps(v, ensure_ascii=False)
    return text if len(text) <= 120 else text[:117] + "..."


def diff_settings(old, new):
    """What changed between two sets of settings: [path, old value, new value]."""
    a, b = _flat(old or {}), _flat(new or {})
    out = []
    for path in sorted(set(a) | set(b)):
        if a.get(path) != b.get(path):
            out.append([path, _short(a.get(path)) if path in a else "(none)", _short(b.get(path)) if path in b else "(removed)"])
    return out


def settings_changed(old_cfg, cfg, lang, langs_saved=()):
    """Record a Save & apply: what changed, and the full settings now in force."""
    changes = diff_settings(old_cfg, cfg)
    with _lock:
        if _cur is None:
            return changes
        try:
            h = _store_settings(cfg, lang)
        except OSError as x:
            _fail(x)
            h = ""
        msg = "Settings saved: {} change{}".format(len(changes), "" if len(changes) == 1 else "s")
        if changes:
            msg += ": " + "; ".join("{} {} -> {}".format(p, o, n) for p, o, n in changes[:8])
            if len(changes) > 8:
                msg += "; and {} more".format(len(changes) - 8)
        if langs_saved:
            msg += " (wording edited: {})".format(", ".join(sorted(langs_saved)))
        record({"turn": _cur["game"].s["turn"], "cat": "settings", "type": "settings", "msg": msg, "do": "settings",
                "cfg": h, "changes": changes[:300], "languages": sorted(langs_saved)})
    log("INFO", "settings", msg[:400], changes=len(changes))
    return changes


# --------------------------------------------------------------- reading --
def games():
    """Every recorded game, newest first."""
    out = []
    cur = current()
    if os.path.isdir(GAMES):
        for gid in os.listdir(GAMES):
            d = _game_dir(gid)
            if not d or not os.path.isdir(d):
                continue
            with _lock:
                meta = dict(_cur["meta"]) if _cur and _cur["gid"] == gid else _read_json(os.path.join(d, "meta.json"), None)
            if meta is None:
                meta = {"id": gid, "started": int(os.path.getmtime(d)), "events": _count_lines(os.path.join(d, "events.jsonl"))}
            try:
                meta["size"] = os.path.getsize(os.path.join(d, "events.jsonl"))
            except OSError:
                meta["size"] = 0
            meta["id"] = gid
            meta["current"] = gid == cur
            out.append(meta)
    out.sort(key=lambda m: (m.get("current", False), m.get("updated", m.get("started", 0))), reverse=True)
    return out


def _iter(gid, full=False):
    path = events_path(gid)
    if not path:
        return
    try:
        with open(path, encoding="utf-8") as f:
            for raw in f:
                try:
                    e = json.loads(raw)
                except ValueError:
                    continue                 # a line cut short by a crash or power loss
                if not full:
                    e.pop("state", None)
                yield e
    except OSError:
        return


def index(gid):
    """The months in a game and how much happened in each, for the review page."""
    path = events_path(gid)
    if not path or not os.path.isfile(path):
        return None
    size = os.path.getsize(path)
    hit = _index_cache.get(gid)
    if hit and hit[0] == size:
        return hit[1]
    turns, cats, total = {}, {}, 0
    for e in _iter(gid):
        total += 1
        t = turns.setdefault(e.get("turn", 0), {"turn": e.get("turn", 0), "count": 0, "first": e["n"], "problems": 0})
        t["count"] += 1
        t["last"] = e["n"]
        if e.get("cat") in ("error", "rejected"):
            t["problems"] += 1
        if e.get("type") == "turn_resolve" and e.get("date"):
            t["date"] = e["date"]
        if "firms" in e and e.get("date"):
            t.setdefault("date", e["date"])
            t.setdefault("snapshot", e["n"])
        cats[e.get("cat", "")] = cats.get(e.get("cat", ""), 0) + 1
    out = {"turns": [turns[k] for k in sorted(turns)], "cats": cats, "total": total}
    _index_cache[gid] = (size, out)
    return out


def events(gid, after=0, turn=None, cats=None, pid=None, q=None, limit=1500, tail=False):
    """Events from a game's journal, without the bulky replay state.

    after: only events numbered above this.  tail: the newest `limit` rather
    than the first.  The other arguments narrow the list.
    """
    q = (q or "").lower()
    cats = set(cats or ())

    def want(e):
        if e["n"] <= after:
            return False
        if turn is not None and e.get("turn") != turn:
            return False
        if cats and e.get("cat") not in cats:
            return False
        if pid and e.get("pid") != pid:
            return False
        if q and q not in (e.get("msg", "") + " " + e.get("type", "")).lower():
            return False
        return True

    with _lock:
        live = _cur is not None and _cur["gid"] == gid
        if live and _recent and turn is None and not q:
            first = _recent[0]["n"]
            pool = [e for e in _recent if want(e)]
            if after >= first - 1 or (tail and (first == 1 or len(pool) >= limit)):
                return {"events": pool[-limit:] if tail else pool[:limit],
                        "more": tail and first > 1, "last": _cur["n"]}
    out = collections.deque(maxlen=limit) if tail else []
    more, last = False, 0
    for e in _iter(gid):
        last = e["n"]
        if not want(e):
            continue
        if not tail and len(out) >= limit:
            more = True
            continue
        if tail and len(out) == limit:
            more = True
        out.append(e)
    return {"events": list(out), "more": more, "last": last}


def report_text(gid):
    """The whole journal as a plain captain's report, month by month."""
    meta = next((m for m in games() if m["id"] == gid), None)
    if meta is None:
        return None
    lines = ["CAPTAIN'S REPORT", "Game {}".format(gid),
             "Started {}".format(time.strftime("%Y-%m-%d %H:%M", time.localtime(meta.get("started", 0)))),
             "Players: " + (", ".join("{} ({})".format(p["name"], p["firm"]) for p in meta.get("players", [])) or "none"), ""]
    turn = None
    for e in _iter(gid):
        if e.get("turn") != turn:
            turn = e.get("turn")
            lines += ["", "=== Month {} ===".format(turn)]
        lines.append("{}  #{:<6} {:<9} {}".format(e.get("at", "")[:19], e["n"], e.get("cat", ""), e.get("msg", "")))
        for f in e.get("firms", []):
            lines.append("            {:<14} {:<12} silver {:>12,} bank {:>12,} debt {:>12,} worth {:>13,}  hold {}/{}  ships {}".format(
                f["name"][:14], f["port"][:12], f["cash"], f["bank"], f["debt"], f["worth"], f["used"], f["hold"],
                len(f["ships"])))
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------ housekeeping --
def set_keep(gid, keep):
    d = _game_dir(gid)
    if not d or not os.path.isdir(d):
        return False
    with _lock:
        if _cur and _cur["gid"] == gid:
            _cur["meta"]["keep"] = bool(keep)
            _touch_meta(write=True)
            return True
        meta = _read_json(os.path.join(d, "meta.json"), None) or {"id": gid}
        meta["keep"] = bool(keep)
        _write_json(os.path.join(d, "meta.json"), meta)
    return True


def delete(gid):
    d = _game_dir(gid)
    if not d or not os.path.isdir(d) or gid == current():
        return False
    shutil.rmtree(d, ignore_errors=True)
    _index_cache.pop(gid, None)
    log("INFO", "journal", "Deleted the journal of game {}".format(gid), game=gid)
    return True


def prune():
    """Delete what is past its keep-by date: old server logs and the oldest game journals."""
    removed = []
    with _lock:
        if KEEP["days"] > 0 and os.path.isdir(SERVER):
            cutoff = time.strftime("%Y-%m-%d", time.localtime(time.time() - KEEP["days"] * 86400))
            for d in server_days():
                if d["day"] < cutoff:
                    try:
                        os.remove(os.path.join(SERVER, "server-{}.log".format(d["day"])))
                        removed.append("server log " + d["day"])
                    except OSError:
                        pass
        if KEEP["games"] > 0:
            spare = [m for m in games() if not m.get("current") and not m.get("keep")]
            kept = sum(1 for m in games() if m.get("current") or m.get("keep"))
            for m in spare[max(0, KEEP["games"] - kept):]:
                shutil.rmtree(_game_dir(m["id"]), ignore_errors=True)
                _index_cache.pop(m["id"], None)
                removed.append("game " + m["id"])
    if removed:
        log("INFO", "journal", "Pruned old records: " + ", ".join(removed))
    return removed


def stats():
    """Sizes, for the Admin page."""
    total = 0
    for base, _dirs, files in os.walk(DIR):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(base, f))
            except OSError:
                pass
    return {"folder": DIR, "bytes": total, "session": SESSION, "keep_games": KEEP["games"], "server_days": KEEP["days"],
            "current": current()}
