"""SeaTrader server.

Uses only the Python standard library, so there is nothing to install.
Run:  python server.py [--port 8765] [--new] [--admin-password WORD]

  /            player screen (phones, tablets, laptops)
  /board       harbor board for a big shared screen
  /admin       command center: every setting, the look, the wording, the live game
  /stats       the player's statistics: this voyage and career, charts and heat maps (see stats.py)
  /voice/...   lines read aloud by the cast (Inworld voices; see voice.py)
  /api/voice/floor  whose turn it is to speak, so screens never talk over each other (voicefloor.py)
  journal/     everything that happens, written down (see journal.py); read it on
               the Admin page under Captain's Report
  /events      live state stream (Server-Sent Events)
  /api/...     join, actions and the admin interface

The Admin page is open on the computer running the server. From any other
device it asks for the admin password (set one on the Admin page, or with
--admin-password).
"""
import argparse
import json
import os
import platform
import re
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import artbible
import captains
import cast
import config
import engine
import finale
import fonts
import imagegen
import journal
import media
import stats
import strings
import voice
import voicefloor
from engine import Game, GameError, static_data

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, "web")
SAVES = os.path.join(ROOT, "saves")
ARTBIBLE_FILE = os.path.join(ROOT, "config", "artbible_examples.json")
ARTBIBLE_LOCK = threading.Lock()
ARTBIBLE_SLOT_RE = re.compile(r"^[a-z][a-z0-9_]{0,47}$")


def artbible_examples():
    """Generated Art Bible examples: slot -> newest-first list of {url, prompt, seed, ...}."""
    try:
        with open(ARTBIBLE_FILE, encoding="utf-8") as f:
            book = json.load(f)
    except (OSError, ValueError):
        return {}
    out = {}
    for k, v in book.items():
        if not isinstance(v, list) or not ARTBIBLE_SLOT_RE.match(str(k)):
            continue
        # Skip examples whose image was deleted (e.g. from the media library).
        live = [x for x in v if isinstance(x, dict) and media._exists(x.get("url"))]
        if live:
            out[k] = live
    return out


def prune_artbible(urls):
    """Drop Art Bible examples that point at these URLs (or at files that no longer exist)."""
    urls = set(urls or ())
    with ARTBIBLE_LOCK:
        try:
            with open(ARTBIBLE_FILE, encoding="utf-8") as f:
                book = json.load(f)
        except (OSError, ValueError):
            return 0
        if not isinstance(book, dict):
            return 0
        removed, fresh = 0, {}
        for k, v in book.items():
            if not isinstance(v, list):
                fresh[k] = v
                continue
            keep = [x for x in v if isinstance(x, dict) and x.get("url") not in urls and media._exists(x.get("url"))]
            removed += len(v) - len(keep)
            if keep:
                fresh[k] = keep
        if removed:
            tmp = ARTBIBLE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(fresh, f, indent=1, ensure_ascii=False)
            os.replace(tmp, ARTBIBLE_FILE)
        return removed
SAVE_FILE = os.path.join(SAVES, "current.json")
MAX_UPLOAD = 8 * 1024 * 1024
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".js": "application/javascript; charset=utf-8", ".svg": "image/svg+xml",
         ".png": "image/png", ".ico": "image/x-icon", ".json": "application/json",
         ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif",
         ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf",
         ".mp4": "video/mp4", ".m4v": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime"}
STARTED = time.time()
SESSIONS = set()      # admin sign-ins from other devices (cookie values)

SAVE_FILE = os.path.join(SAVES, "current.json")
MAX_UPLOAD = 8 * 1024 * 1024
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".js": "application/javascript; charset=utf-8", ".svg": "image/svg+xml",
         ".png": "image/png", ".ico": "image/x-icon", ".json": "application/json",
         ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif",
         ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf",
         ".mp4": "video/mp4", ".m4v": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime"}
STARTED = time.time()
SESSIONS = set()      # admin sign-ins from other devices (cookie values)


def apply_settings():
    """Read the saved settings and hand them to the engine."""
    cfg = config.load()
    lang = config.load_lang(cfg["language"]["active"])
    engine.configure(cfg, strings.resolve(cfg, lang))
    journal.configure(cfg)
    voice.PLAN.configure(cfg, engine.TEXT)
    fonts.ensure(cfg["theme"].get("web_fonts", ""), on_done=_fonts_ready)
    return cfg


def _fonts_ready():
    """Fonts finished downloading: nudge open screens to reload their styles."""
    hub = globals().get("HUB")
    if hub is not None:
        with hub.cond:
            hub.cfg_version += 1
            hub.changed(save=False)


def _media_changed():
    """The media library changed: nudge open screens to reload it."""
    hub = globals().get("HUB")
    if hub is not None:
        with hub.cond:
            hub.cfg_version += 1
            hub.changed(save=False)


def family_screen(cfg, data):
    """The settings and reference data for one screen that chose Family-friendly in Options while the
    table is not: NSFW pictures out, cargo by their family names, family wording."""
    fcfg = dict(cfg, content=dict(cfg.get("content") or {}, rating="family"))
    data = dict(data)
    data["goods"] = {k: dict(g, name=g.get("family_name") or g.get("name"))
                     for k, g in (data.get("goods") or {}).items()}
    try:
        data["text"] = strings.resolve(fcfg, config.load_lang(cfg["language"]["active"]))
    except Exception:
        data["text"] = dict(data.get("text") or {}, **(strings.FAMILY if cfg["language"]["active"] == "en" else {}))
    contra = [g["name"] for g in data["goods"].values() if g.get("contraband")]
    if contra:
        joined = " & ".join(contra)
        data["tokens"] = dict(data.get("tokens") or {}, Contraband=joined, contraband=joined.lower())
    data["rating"] = "family"
    data["screen_family"] = True
    return fcfg, data


def ship_swaps():
    """(NSFW name, clean name) for every ship at sea that has both, longest first (Ships > NSFW ship names)."""
    hub = globals().get("HUB")
    game = getattr(hub, "game", None)
    out = []
    for p in ((getattr(game, "s", None) or {}).get("players") or {}).values():
        for sh in p.get("ships") or []:
            if sh.get("nsfw_name") and sh.get("clean_name") and sh["nsfw_name"] != sh["clean_name"]:
                out.append((sh["nsfw_name"], sh["clean_name"]))
    return sorted(out, key=lambda ab: -len(ab[0]))


def family_view(view):
    """A game state for a Family-friendly screen: the cargo's family names in every line of text
    (log, news, the desk, the battle). Words only; ids and numbers are left alone."""
    swaps = [(g["name"], g["family_name"]) for g in engine.CFG["goods"].values()
             if g.get("family_name") and g.get("name") and g["family_name"] != g["name"]] + ship_swaps()
    if not swaps:
        return view
    pats = [(re.compile(r"(?<!\w){}(?!\w)".format(re.escape(a))), b) for a, b in swaps] + \
           [(re.compile(r"(?<!\w){}(?!\w)".format(re.escape(a.lower()))), b.lower()) for a, b in swaps]

    def fix(v):
        if isinstance(v, str):
            if " " not in v:                       # one word: only an exact name (ids are lower case)
                return next((b for a, b in swaps if v == a), v)
            for pat, b in pats:
                v = pat.sub(b, v)
            return v
        if isinstance(v, list):
            return [fix(x) for x in v]
        if isinstance(v, dict):
            return {k: fix(x) for k, x in v.items()}
        return v
    return fix(view)


def screen_cfg():
    """The settings as screens may see them: NSFW artwork swapped out while family-friendly."""
    cfg = engine.CFG
    if not media.family(cfg):
        return cfg
    out = dict(cfg)
    out["graphics"] = media.safe_graphics(cfg.get("graphics"), cfg)
    return out


def settings_now():
    """The settings and language file in force, for the journal."""
    cfg = engine.CFG
    return cfg, config.load_lang(cfg["language"]["active"])


def git_commit():
    """The code version, read straight from the .git folder (no git needed)."""
    try:
        with open(os.path.join(ROOT, ".git", "HEAD"), encoding="utf-8") as f:
            head = f.read().strip()
        if head.startswith("ref: "):
            with open(os.path.join(ROOT, ".git", *head[5:].split("/")), encoding="utf-8") as f:
                head = f.read().strip()
        return head[:10]
    except OSError:
        return ""


def backfill_market(game):
    """The Market tab's price book and best sales for games saved before they were kept (stats.py)."""
    try:
        if stats.backfill_market(game):
            journal.log("INFO", "server", "Market price book filled in from the journal ({} months)".format(
                len(game.s.get("price_hist", []))))
    except Exception as e:                  # never let a history fill-in stop the game
        journal.log("WARNING", "server", "Could not fill in the market price book: {!r}".format(e))


class Hub:
    """Holds the one running game and wakes every screen when it changes."""

    def __init__(self, game, join_url):
        self.game = game
        self.join_url = join_url
        self.cond = threading.Condition(threading.RLock())
        self.version = 0
        self.cfg_version = 1  # goes up whenever settings change; screens then reload them
        self.conns = {}       # player id -> open stream count
        self.last_seen = {}   # player id -> time the last stream closed
        self.clock = {}       # player id -> (which step of which fight, deadline, seconds given)

    # ------------------------------------------------- the sea battle's clock --
    def _deadline(self, pid, p, now):
        """When this captain's time to choose runs out. A new step of a fight starts a new clock."""
        b = p["battle"]
        key = (self.game.s.get("game_id"), self.game.s["turn"], len(p.get("fights") or []), b["step"])
        cur = self.clock.get(pid)
        if not cur or cur[0] != key:
            bt = engine.R["battle"]
            # The first round gets extra time for the sighting; a second fight in one voyage gets it
            # twice, because the captain is still reading the first one's reckoning.
            secs = bt["round_secs"] + bt["voice_grace"] + (
                bt["first_extra"] * (2 if p.get("fights") else 1) if b["step"] == 0 else 0)
            # The round's pictures play before the captain chooses (the bosun's line, then the enemy's
            # answer). The clock must not run out while they play, or the round goes on standing orders
            # and the captain never gets a turn (fixed 19 Nov 2026). Only a captain at a screen sees them.
            if pid in self.present():
                secs += self._beat_secs(b.get("beat"))
            secs = round(secs, 1)
            cur = self.clock[pid] = (key, now + secs, secs)
        return cur

    @staticmethod
    def _beat_secs(beat):
        """About how long the screen plays a fight's pictures (the same pace as web/battle.js): each
        caption stays while its lines are read aloud, or long enough to read when nobody speaks."""
        total = 0.0
        for f in (beat or {}).get("frames") or []:
            quiet = len(f.get("cap") or "") * 0.042 + 1.5
            # Inworld reads about 13 characters a second (measured on saved clips, 19 Nov 2026); each line
            # also waits a moment for its turn and the gap before it.
            lines = (1 if f.get("say") else 0) + (1 if f.get("foe") else 0)
            spoken = (len(f.get("say") or "") + len(f.get("foe") or "")) / 13.0 + 0.8 * lines
            cap = 9.0 + (7.2 if f.get("say") and f.get("foe") else 0.0)
            total += min(cap, max(quiet, spoken))
        return min(60.0, total)

    def battle_tick(self):
        """Call with the lock held. When a captain's clock runs out the round is played on standing
        orders; if that captain has no screen connected, the rest of the fight is. True if anything moved."""
        g = self.game
        if g.s["phase"] != "sea":
            self.clock.clear()
            return False
        now, here, moved = time.time(), self.present(), False
        for pid in list(g.s["order"]):
            p = g.s["players"].get(pid)
            if g.s["phase"] != "sea":
                break
            if not p or p.get("battle") is None:
                self.clock.pop(pid, None)
                continue
            if now < self._deadline(pid, p, now)[1]:
                continue
            try:
                g.act(pid, {"type": "sea", "choice": "auto" if pid in here else "skip"}, here)
                moved = True
            except GameError:
                self.clock.pop(pid, None)
        return moved

    def sea_watch(self):
        """Keeps the fights moving: runs the round clocks while the month waits at sea."""
        while True:
            time.sleep(0.5)
            try:
                with self.cond:
                    if self.battle_tick():
                        self.save()
                        self.version += 1
                        self.cond.notify_all()
            except Exception:                       # never let the watcher die; write it down instead
                crash("The sea battle clock hit an error")

    def _battle_voice(self, me):
        """Who reads each picture of a fight aloud (the bosun, unless the Admin page gave the attack
        lines to someone else), with a link to the audio. Keyed "now" for the fight in progress and
        by fight id for the ones already over."""
        plan = voice.PLAN
        if not plan.ready() or not plan.cfg["voice"]["read_log"]:
            return None
        cid = cast.speaker_for(plan.cfg, "l.attack")
        if not cid:
            return None
        clips = lambda beat: [plan._clip(f["say"], cid) if f.get("say") else None for f in (beat or {}).get("frames", [])]
        out = {f["id"]: clips(f.get("beat")) for f in me.get("fights") or []}
        if me.get("battle"):
            out["now"] = clips(me["battle"].get("beat"))
        return out

    def _battle_foe_voice(self, me):
        """The enemy's answering line on each picture (Admiral Li Yue or Madam Shek Yu-lan, named on the
        frame as foe_by), keyed the same way as _battle_voice. None when nobody reads the log aloud."""
        plan = voice.PLAN
        if not plan.ready() or not plan.cfg["voice"]["read_log"]:
            return None
        clips = lambda beat: [plan._clip(f["foe"], f.get("foe_by")) if f.get("foe") and f.get("foe_by") else None
                              for f in (beat or {}).get("frames", [])]
        out = {f["id"]: clips(f.get("beat")) for f in me.get("fights") or []}
        if me.get("battle"):
            out["now"] = clips(me["battle"].get("beat"))
        return out

    def present(self):
        now = time.time()
        grace = engine.R["game"]["grace_seconds"]
        here = {pid for pid, n in self.conns.items() if n > 0}
        here |= {pid for pid, t in self.last_seen.items() if now - t < grace}
        return here

    def changed(self, save=True):
        """Call with the lock held after any change to the game."""
        if self.game.maybe_advance(self.present()):
            save = True
        if save:
            self.save()
        self.version += 1
        self.cond.notify_all()

    def cue_start(self):
        state = self.game.s
        if state["phase"] != "lobby":
            raise GameError(engine.tx("e.host_start"))
        if not state["players"]:
            raise GameError("Nobody has joined yet.")
        if not state.get("start_at"):
            state["start_at"] = time.time() + 11
            self.changed()
        return engine.tx("m.intro")

    def save(self):
        os.makedirs(SAVES, exist_ok=True)
        tmp = SAVE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.game.s, f)
        os.replace(tmp, SAVE_FILE)

    def view(self, pid):
        v = self.game.view(pid, self.present())
        v["game_id"] = self.game.s["game_id"]
        v["server_time"] = time.time()
        if v["phase"] == "lobby":
            v["start_at"] = self.game.s.get("start_at")
        if v["phase"] == "ended" or self.game.s.get("free_play"):
            v["ended_at"] = self.game.s.get("ended_at")
            v["voyage_story"] = self.game.voyage_story()
        v["join_url"] = self.join_url
        v["cfg"] = self.cfg_version
        # Who reads each line aloud, with a link to the audio (made only when a screen asks for it).
        me = v.get("me") or {}
        # The Captain's Log as shown: the sea battle folded into one report, the standing moves into
        # one line, and only the top couple of lines read aloud (voice.Planner.captains_log).
        if me.get("log") is not None:
            shown, log_plan = voice.PLAN.captains_log(me.get("log"), port=me.get("port"))
            me["log"] = shown
        else:
            log_plan = voice.PLAN.lines(me.get("log"), "log", port=me.get("port"))
        v["voice"] = {"log": log_plan,
                      "news": voice.PLAN.lines(v.get("news"), "news", 14)}
        if me.get("battle") or me.get("fights"):
            v["voice"]["battle"] = self._battle_voice(me)
            v["voice"]["battle_foe"] = self._battle_foe_voice(me)
        promo = me.get("promotion") or {}
        if promo:
            me["promotion"] = dict(promo, achievements=stats.promotion_record(v["game_id"], pid, promo))
        if promo.get("text"):
            # The Mayor's congratulations on a promotion (strings m.promote.N), read by the Mayor.
            v["voice"]["promotion"] = voice.PLAN.lines([promo["text"]], "log", port=promo.get("port"))
        if me.get("battle"):
            _key, deadline, secs = self._deadline(pid, self.game.s["players"][pid], time.time())
            me["battle"]["secs_left"] = round(max(0.0, deadline - time.time()), 1)
            me["battle"]["secs_total"] = secs
        # Saved Captains' portraits and their Houses' crests (Media Library), on every seat and on mine.
        try:
            faces = captains.faces(self.game.s["players"].values(), self.game.s.get("game_id"), engine.CFG)
        except Exception:
            faces = {}
        for q in v.get("players") or []:
            q.update(faces.get(q["id"], {"portrait": "", "crest": ""}))
        if me.get("id"):
            me.update(faces.get(me["id"], {"portrait": "", "crest": ""}))
        cu = me.get("customs")
        if cu and cu.get("welcome"):
            # The Port Authority officer's greeting, read by the officer of that port. At a captain's home
            # port the Registrar reads her welcome home and then her price tip (her own lines, cast.py).
            said = [cu["welcome"]] + ([cu["tip"]["text"]] if (cu.get("tip") or {}).get("text") else [])
            plans = voice.PLAN.lines(said, "log", port=cu.get("port"))
            if plans and not cu.get("aloud", True):
                plans[0] = None                  # a quiet landing: her greeting is shown, not read (her tip still is)
            v["voice"]["customs"] = plans
        return v

    def reload_settings(self, langs_saved=()):
        """Call with the lock held after settings were saved."""
        old = json.loads(json.dumps(engine.CFG))
        apply_settings()
        journal.settings_changed(old, *settings_now(), langs_saved=langs_saved)
        self.game.reconcile()
        self.cfg_version += 1
        self.changed()

    def replace_game(self, game, reason, kind="checkpoint"):
        journal.close_game("This game was set aside: " + reason)
        self.game = game
        self.conns = {}
        self.last_seen = {}
        self.clock = {}
        journal.open_game(game, reason, *settings_now(), kind=kind)
        backfill_market(game)
        self.sync_houses()
        self.changed()

    def sync_houses(self):
        """The House is its id (Admin > Captains, Options): every seat sailing under a saved House takes
        that House's name now, through the game's own "house" action so the journal and replays have it.
        Also writes the House id on seats that were linked by name only. Call with the lock held."""
        changed = False
        s = self.game.s
        for pid in list(s.get("order") or []):
            p = s["players"].get(pid)
            if not p or not p.get("captain"):
                continue
            try:
                hid = captains.house_for_seat(p, s.get("game_id"))
                h = captains.house(p["captain"], hid) if hid else None
            except Exception:
                crash("Looking up a seat's House failed", pid=pid)
                continue
            if not h:
                continue
            if p.get("hid") != hid:
                p["hid"] = hid
                changed = True
            if h["name"] and h["name"] != p["firm"]:
                try:
                    self.game.act(pid, {"type": "house", "name": h["name"]}, self.present() | {pid})
                    changed = True
                except GameError as e:
                    journal.log("WARN", "players", "{}'s House could not take the name {}: {}".format(
                        p["name"], h["name"], e))
        if changed:
            self.changed()
        return changed

    def ticker(self):
        """Notices when a player drops out so the others are not left waiting."""
        seen = self.present()
        last = time.time()
        while True:
            try:
                with self.cond:
                    t = time.time()
                    start_at = self.game.s.get("start_at")
                    if start_at and start_at <= t:
                        if self.game.s["phase"] == "lobby" and self.game.s["players"]:
                            self.game.admin("start", {})
                        else:
                            self.game.s.pop("start_at", None)
                        self.changed()
                        start_at = None
                    if t < last + 3:
                        until = min(last + 3, start_at) if start_at else last + 3
                        self.cond.wait(max(0, until - time.time()))
                        continue
                    now = self.present()
                    if self.game.s["phase"] in ("port", "sea"):
                        gid = self.game.s.get("game_id")
                        seated = [(self.game.s["players"][pid]["captain"], gid) for pid in now
                                  if self.game.s["players"].get(pid, {}).get("captain")]
                        if seated:
                            captains.tick(seated, min(30.0, t - last))
                    last = t
                    for pid in seen - now:
                        p = self.game.s["players"].get(pid)
                        if p:
                            journal.note("players", "away", "{} is away: no screen connected for {} seconds".format(
                                p["name"], engine.R["game"]["grace_seconds"]), pid=pid, who=p["name"])
                    advanced = self.game.maybe_advance(now)
                    if advanced:
                        self.save()
                    if advanced or now != seen:
                        seen = now
                        self.version += 1
                        self.cond.notify_all()
            except Exception:                       # never let the watcher die; write it down instead
                crash("The turn watcher hit an error")
                time.sleep(3)


HUB = None


def captain_career(c):
    """A Captain's record: stats.py career over their linked games, plus wins/losses, time at the
    screen and a line per House."""
    links = captains.links(c)
    cur = journal.current()
    running = HUB.game.s["phase"] != "ended" if HUB else False
    try:
        data = stats.career(c["name"], running_gid=cur if running else None,
                            running_pid=links.get(cur), links=links) or {}
    except Exception:
        crash("Working out a Captain's record failed", captain=c.get("cid"))
        data = {}
    by_gid = {g["gid"]: g for g in c.get("games", []) if g.get("gid")}
    games = data.get("games") or []
    tot = {"games": len(games), "wins": 0, "losses": 0, "unfinished": 0, "playing": 0, "seconds": 0,
           "months": 0, "best": None}
    houses = {}
    for g in games:
        link = by_gid.get(g["id"], {})
        g["house"], g["hid"] = link.get("house") or g.get("firm"), link.get("hid", "")
        g["seconds"] = int(link.get("seconds") or 0)
        if g.get("running"):
            g["outcome"] = "playing"
        elif not g.get("ended"):
            g["outcome"] = "unfinished"
        elif g.get("place") == 1:
            g["outcome"] = "win"
        else:
            g["outcome"] = "loss"
        tot[{"playing": "playing", "unfinished": "unfinished", "win": "wins", "loss": "losses"}[g["outcome"]]] += 1
        tot["seconds"] += g["seconds"]
        tot["months"] += g.get("months") or 0
        tot["best"] = g["worth"] if tot["best"] is None else max(tot["best"], g["worth"])
        h = houses.setdefault(g["hid"] or g["house"], {"hid": g["hid"], "house": g["house"], "games": 0, "wins": 0,
                                                        "losses": 0, "best": None, "seconds": 0})
        h["games"] += 1
        h["wins"] += g["outcome"] == "win"
        h["losses"] += g["outcome"] == "loss"
        h["seconds"] += g["seconds"]
        h["best"] = g["worth"] if h["best"] is None else max(h["best"], g["worth"])
    tot["seconds"] = max(tot["seconds"], sum(int(x.get("seconds") or 0) for x in c.get("games", [])))
    data["summary"] = tot
    data["houses"] = list(houses.values())
    return data


def crash(what, **data):
    """Write an unexpected error to the server log and the game journal."""
    tb = traceback.format_exc()
    last = tb.strip().splitlines()[-1] if tb.strip() else ""
    msg = "{}: {}".format(what, last)
    print(msg)
    try:
        journal.log("ERROR", "crash", msg, traceback=tb, **data)
        journal.note("error", "crash", msg, traceback=tb, **data)
    except Exception:
        pass
    return msg


LOOPBACK = ("127.0.0.1", "::1", "::ffff:127.0.0.1")
TRUSTED_FILE = os.path.join(ROOT, "config", "trusted_admin.txt")
TRUSTED_DEFAULT = ("192.168.1.213",)   # BIGBOX, the dev PC
_trusted_cache = {"mtime": None, "addrs": frozenset(TRUSTED_DEFAULT)}


def trusted_admin():
    """Addresses that open the Admin page without a password. One per line in
    config/trusted_admin.txt (# starts a comment); BIGBOX's address when the file is missing."""
    try:
        mtime = os.path.getmtime(TRUSTED_FILE)
    except OSError:
        return frozenset(TRUSTED_DEFAULT)
    if mtime != _trusted_cache["mtime"]:
        addrs = set()
        try:
            with open(TRUSTED_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.split("#", 1)[0].strip()
                    if line:
                        addrs.add(line)
        except OSError:
            addrs = set(TRUSTED_DEFAULT)
        _trusted_cache.update(mtime=mtime, addrs=frozenset(addrs))
    return _trusted_cache["addrs"]


def device(headers):
    """A short name for the device from its browser's User-Agent."""
    ua = headers.get("User-Agent", "")
    kind = next((name for key, name in (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"),
                                         ("Windows", "Windows PC"), ("Macintosh", "Mac"), ("CrOS", "Chromebook"),
                                         ("Linux", "Linux")) if key in ua), "unknown device")
    browser = next((name for key, name in (("Edg/", "Edge"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"),
                                            ("Safari/", "Safari")) if key in ua), "")
    return kind + (", " + browser if browser else "")


def list_saves():
    if not os.path.isdir(SAVES):
        return []
    out = []
    for f in sorted(os.listdir(SAVES), reverse=True):
        if f.endswith(".json") and f != "current.json":
            out.append({"name": f[:-5], "time": int(os.path.getmtime(os.path.join(SAVES, f)))})
    return out[:60]


def archive_save():
    if os.path.isfile(SAVE_FILE):
        dst = os.path.join(SAVES, time.strftime("game-%Y%m%d-%H%M%S.json"))
        n = 1
        while os.path.exists(dst):
            n += 1
            dst = os.path.join(SAVES, time.strftime("game-%Y%m%d-%H%M%S-{}.json".format(n)))
        os.replace(SAVE_FILE, dst)
        return True
    return False


class Handler(BaseHTTPRequestHandler):
    server_version = "SeaTrader/2.0"

    def log_message(self, fmt, *args):   # keep the console quiet
        pass

    # ----------------------------------------------------------- helpers --
    def _send(self, code, body, ctype="application/json", headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _file(self, name):
        path = os.path.normpath(os.path.join(WEB, name))
        if not path.startswith(WEB + os.sep) or not os.path.isfile(path):
            return self._send(404, "Not found", "text/plain")
        with open(path, "rb") as f:
            data = f.read()
        extra = {"Content-Security-Policy": "script-src 'none'"} if name.startswith("uploads/") else None
        self._send(200, data, TYPES.get(os.path.splitext(path)[1].lower(), "application/octet-stream"), extra)

    def _stream(self, name):
        """Send a picture or video clip, honouring Range requests so videos can seek."""
        path = os.path.normpath(os.path.join(WEB, name))
        if not path.startswith(WEB + os.sep) or not os.path.isfile(path):
            return self._send(404, "Not found", "text/plain")
        size = os.path.getsize(path)
        ctype = TYPES.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
        start, end, code = 0, size - 1, 200
        m = re.match(r"^bytes=(\d*)-(\d*)$", self.headers.get("Range", "").strip())
        if m and size:
            if m.group(1):
                start = int(m.group(1))
                if m.group(2):
                    end = min(int(m.group(2)), size - 1)
            elif m.group(2):
                start = max(0, size - int(m.group(2)))
            if start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", "bytes */{}".format(size))
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            code = 206
        length = end - start + 1 if size else 0
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Security-Policy", "script-src 'none'")
        if code == 206:
            self.send_header("Content-Range", "bytes {}-{}/{}".format(start, end, size))
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(path, "rb") as f:
            f.seek(start)
            left = length
            while left > 0:
                chunk = f.read(min(256 * 1024, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

    def _raw(self, limit):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        if length <= 0 or length > limit:
            return None
        return self.rfile.read(length)

    def _body(self, limit=20000):
        raw = self._raw(limit)
        if raw is None:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except (ValueError, UnicodeDecodeError):
            return {}

    def _forwarded(self):
        """The visitor's address as passed on by a proxy on this same machine (Caddy on the Pi), else ''.
        Only believed when the request really arrived from this machine, so nobody on the network can
        fake it by sending the header straight to the game's port."""
        if self.client_address[0] not in LOOPBACK:
            return ""
        raw = self.headers.get("X-Forwarded-For", "")
        last = raw.split(",")[-1].strip() if raw else ""
        return last[7:] if last.startswith("::ffff:") else last

    def _addr(self):
        """The real address of whoever sent this request, even when it came through the proxy."""
        return self._forwarded() or self.client_address[0]

    def _local(self):
        """True only for this very machine (not a visitor coming through the proxy)."""
        return self.client_address[0] in LOOPBACK and not self._forwarded()

    def _trusted(self):
        """This machine, or a computer listed in config/trusted_admin.txt (BIGBOX by default):
        the Admin page opens for these without a password."""
        return self._local() or self._addr() in trusted_admin()

    def _via(self):
        return {"address": self._addr(), "device": device(self.headers)}

    def _guard(self, method, handler):
        """Run a request; if it fails unexpectedly, write down why instead of dying quietly."""
        try:
            return handler()
        except (BrokenPipeError, ConnectionError):
            pass
        except Exception:
            msg = crash("{} {} failed".format(method, urlparse(self.path).path), address=self._addr())
            try:
                self._send(500, {"ok": False, "error": "The game server hit an error. It has been written to the "
                                 "Captain's Report. ({})".format(msg[-160:])})
            except Exception:
                pass

    def _admin_ok(self):
        if self._trusted():
            return True
        cookie = self.headers.get("Cookie", "")
        m = re.search(r"(?:^|;\s*)st_admin=([A-Za-z0-9_-]+)", cookie)
        return bool(m and m.group(1) in SESSIONS)

    def _deny(self):
        self._send(401, {"ok": False, "auth": True, "has_password": config.has_password(),
                         "error": "Sign in to use the admin page."})

    # ------------------------------------------------------------ routes --
    def do_GET(self):
        return self._guard("GET", self._get)

    def do_HEAD(self):
        return self._guard("HEAD", self._get)

    def do_POST(self):
        return self._guard("POST", self._post)

    def _get(self):
        url = urlparse(self.path)
        path = url.path
        query = parse_qs(url.query)
        if path == "/":
            return self._file("index.html")
        if path == "/board":
            return self._file("board.html")
        if path == "/design/ceremony-preview.html":
            with open(os.path.join(ROOT, "design", "ceremony-preview.html"), "rb") as preview:
                return self._send(200, preview.read(), "text/html; charset=utf-8")
        if path == "/admin":
            return self._file("admin.html")
        if path == "/stats":
            return self._file("stats.html")
        if path == "/api/stats":
            return self._stats_get(query)
        if path == "/api/finale":
            return self._finale_get()
        if path == "/fonts.css":
            return self._send(200, config.fonts_css(engine.CFG, fonts.local_css()), "text/css; charset=utf-8")
        if path == "/theme.css":
            return self._send(200, config.theme_css(screen_cfg()), "text/css; charset=utf-8")
        if path == "/api/captains":
            cfg = engine.CFG
            return self._send(200, {"ok": True, "captains": captains.public_list(cfg),
                                    "typed": bool(engine.R.get("captains", {}).get("typed"))})
        if path == "/api/info":
            with HUB.cond:
                cfg = engine.CFG
                data = static_data()
                said = voice.PLAN.public()
                if query.get("family", [""])[0] == "1" and not media.family(cfg):
                    cfg, data = family_screen(cfg, data)    # this screen chose Family-friendly (Options)
                if media.family(cfg):
                    data = dict(data, graphics=media.safe_graphics(data.get("graphics"), cfg))
                    if said.get("cast"):
                        said = dict(said, cast=media.safe_cast(said["cast"], cfg))
                return self._send(200, {"ok": True, "join_url": HUB.join_url, "cfg": HUB.cfg_version,
                                        "data": data, "voice": said, "media": media.public(cfg)})
        if path.startswith("/voice/") and path.endswith(".mp3"):
            return self._voice_clip(path[len("/voice/"):-4])
        if path == "/events":
            return self._events(query.get("token", [""])[0], query.get("family", [""])[0] == "1")
        if path == "/api/options":
            return self._options_get(query.get("token", [""])[0])
        if path.startswith("/api/admin/"):
            if not self._admin_ok():
                return self._deny()
            return self._admin_get(path[len("/api/admin/"):], query)
        if media.is_blocked(path, engine.CFG) and not self._admin_ok():
            return self._send(404, "Not found", "text/plain")
        if path.startswith("/media/") or os.path.splitext(path)[1].lower() in media.VIDEO_EXT:
            return self._stream(path.lstrip("/"))
        return self._file(path.lstrip("/"))

    def _post(self):
        url = urlparse(self.path)
        path = url.path
        try:
            if path.startswith("/api/admin/"):
                return self._admin_post(path[len("/api/admin/"):], parse_qs(url.query))
            body = self._body()
            if path == "/api/voice/floor":
                once = body.get("clip") if body.get("once") else ""
                return self._send(200, dict(voicefloor.FLOOR.ask(self._addr(), body.get("id"),
                                                                 body.get("op"), once), ok=True))
            if path == "/api/join":
                if body.get("captain"):
                    return self._join_captain(body)
                if not engine.R.get("captains", {}).get("typed"):
                    raise GameError(engine.tx("e.captain_only"))
                with HUB.cond:
                    try:
                        token = HUB.game.join(body.get("name"), body.get("firm"), HUB.present(), via=self._via())
                    except GameError as e:
                        journal.note("rejected", "join", "Someone tried to join as '{}' and was refused: {}".format(
                            str(body.get("name") or "")[:30], e), via=self._via(), error=str(e))
                        raise
                    HUB.changed()
                return self._send(200, {"ok": True, "token": token})
            if path == "/api/options":
                return self._options_post(body)
            if path == "/api/act":
                with HUB.cond:
                    pid = HUB.game.pid_for_token(body.get("token"))
                    if pid is None:
                        journal.log("WARN", "players", "An action came from a device whose seat is not in this game "
                                    "(it was sent back to the join screen)", action=str(body.get("type")), **self._via())
                        return self._send(200, {"ok": False, "error": engine.tx("e.not_in_game"),
                                                "rejoin": True})
                    present = HUB.present() | {pid}
                    if body.get("type") == "new_game":
                        if HUB.game.host_id(present) != pid:
                            raise GameError(engine.tx("e.host_new_game"))
                        who = HUB.game.s["players"][pid]["name"]
                        HUB.save()
                        archive_save()
                        HUB.replace_game(Game(), "new game started by the host, {}".format(who), kind="game_start")
                        msg = engine.tx("m.new_game")
                    elif body.get("type") == "start":
                        if HUB.game.host_id(present) != pid:
                            raise GameError(engine.tx("e.host_start"))
                        msg = HUB.cue_start()
                    else:
                        msg = HUB.game.act(pid, body, present)
                        HUB.changed()
                    said = voice.PLAN.msg(msg, port=HUB.game.s["players"].get(pid, {}).get("port"))
                return self._send(200, {"ok": True, "msg": msg, "voice": said})
            if path == "/api/shutdown":
                if not self._local():
                    return self._send(403, {"ok": False, "error": "Only from the host computer."})
                with HUB.cond:
                    HUB.save()
                journal.log("INFO", "server", "Stop requested from the host computer")
                self._send(200, {"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
        except GameError as e:
            with HUB.cond:
                said = voice.PLAN.msg(str(e))
            return self._send(200, {"ok": False, "error": str(e), "voice": said})
        self._send(404, {"ok": False, "error": "Not found"})

    # ----------------------------------------------------------- options --
    def _options_seat(self, token):
        pid = HUB.game.pid_for_token(token) if token else None
        if pid is None:
            raise GameError(engine.tx("e.not_in_game"))
        return pid, HUB.game.s["players"][pid]

    @staticmethod
    def _pictures(kind, subject):
        """A Captain's portraits or a House's seals in the Media Library, newest first, starred marked."""
        out = []
        if not subject:
            return out
        for it in media.load(engine.CFG)["items"]:
            if it.get("kind") != kind or it.get("subject") != subject or it.get("type", "image") != "image":
                continue
            if not it.get("enabled", True) or not media._exists(it["url"]):
                continue
            out.append({"id": it["id"], "url": it["url"], "primary": bool(it.get("primary")),
                        "nsfw": bool(it.get("nsfw")), "added": it.get("added") or it.get("created") or ""})
        out.sort(key=lambda i: str(i["added"]), reverse=True)      # newest first, the starred one first of all
        out.sort(key=lambda i: not i["primary"])
        return out

    @staticmethod
    def _jobs_for(kind, subject):
        n = 0
        for j in media.JOBS.list():
            if j.get("kind") == kind and j.get("subject") == subject and j.get("state", j.get("status")) in (
                    "queued", "running", "waiting", "pending"):
                n += max(1, int(j.get("count") or 1) - int(j.get("done") or 0))
        return n

    def _options_get(self, token):
        """Everything the Options popup shows that is not already in the game state."""
        with HUB.cond:
            try:
                pid, p = self._options_seat(token)
            except GameError as e:
                return self._send(200, {"ok": False, "error": str(e)})
            cid = p.get("captain") or ""
            hid = captains.house_for_seat(p, HUB.game.s.get("game_id")) if cid else ""
        c = captains.get(cid) if cid else None
        h = captains.house(cid, hid) if (cid and hid) else None
        family = media.family(engine.CFG)
        pics = lambda kind, subj: [i for i in self._pictures(kind, subj) if not (family and i["nsfw"])]
        return self._send(200, {
            "ok": True, "captain": {"cid": cid, "name": c["name"], "title": c.get("title", "")} if c else None,
            "house": {"hid": hid, "name": h["name"], "color": h["color"], "motto": h.get("motto", "")} if h else None,
            "portraits": pics("captain", cid) if c else [], "crests": pics("house", hid) if h else [],
            "painting": {"captain": self._jobs_for("captain", cid) if c else 0,
                         "house": self._jobs_for("house", hid) if h else 0},
            "mode": engine.MULT.get("name", ""), "table_family": family, "admin": self._admin_ok()})

    def _options_post(self, body):
        """Options: choose a portrait or seal, have a new one made, or rename / re-colour the House."""
        op = str(body.get("op") or "")
        with HUB.cond:
            pid, p = self._options_seat(body.get("token"))
            cid = p.get("captain") or ""
            hid = captains.house_for_seat(p, HUB.game.s.get("game_id")) if cid else ""
            who = p["name"]
        try:
            if op == "house":
                name = " ".join(str(body.get("name") or "").split())[:28]
                color = body.get("color")
                if not name:
                    raise GameError(engine.tx("e.house_name"))
                with HUB.cond:
                    for q in HUB.game.s["players"].values():
                        if q["id"] != pid and q["firm"].lower() == name.lower():
                            raise GameError(engine.tx("e.house_taken", firm=name))
                    if cid and hid:
                        before, after = captains.update_house(cid, hid, name, color if color else None)
                        HUB.sync_houses()
                        msg = engine.tx("m.house_renamed", old=before["name"], firm=after["name"]) \
                            if before["name"] != after["name"] else engine.tx("opt.house_saved")
                    else:
                        msg = HUB.game.act(pid, {"type": "house", "name": name}, HUB.present() | {pid})
                    HUB.changed()
                media._public_cache.clear()
                journal.log("INFO", "players", "{} saved their House in Options: {}".format(who, msg), **self._via())
                return self._send(200, {"ok": True, "msg": msg})
            if op in ("pick", "generate"):
                kind = "captain" if body.get("what") == "portrait" else "house"
                subject = cid if kind == "captain" else hid
                if not subject:
                    raise GameError(engine.tx("opt.no_captain"))
                if op == "pick":
                    iid = str(body.get("id") or "")
                    if not any(i["id"] == iid for i in self._pictures(kind, subject)):
                        raise GameError(engine.tx("opt.no_captain"))
                    media.update([iid], {"primary": True, "enabled": True},
                                 add_roles=["portrait" if kind == "captain" else "crest"])
                    media._public_cache.clear()
                    with HUB.cond:
                        HUB.changed()
                    return self._send(200, {"ok": True, "msg": engine.tx("opt.chosen")})
                if self._jobs_for(kind, subject):
                    return self._send(200, {"ok": True, "msg": engine.tx("opt.generating")})
                c = captains.get(cid)
                h = captains.house(cid, hid) if kind == "house" else None
                prompt = captains.prompt_for(c, h) if kind == "house" else captains.prompt_for(c)
                aspect = "3:4" if kind == "captain" else "1:1"
                if aspect not in imagegen.ASPECTS:
                    aspect = next(iter(imagegen.ASPECTS))
                w, hh = imagegen.ASPECTS[aspect]
                media.JOBS.add(kind, subject, ["portrait" if kind == "captain" else "crest"], prompt[:6000],
                               w, hh, 1, "auto", tags=media._tags(""), aspect=aspect, replaces="")
                journal.log("INFO", "players", "{} asked for a new {} in Options".format(
                    who, "portrait" if kind == "captain" else "House seal"), **self._via())
                return self._send(200, {"ok": True, "msg": engine.tx("opt.generating")})
        except captains.CaptainError as e:
            return self._send(200, {"ok": False, "error": str(e)})
        self._send(404, {"ok": False, "error": "Not found"})

    def _join_captain(self, body):
        """Join (or take back a seat) as a saved Captain: PIN checked first, then the House chosen."""
        try:
            c, h = captains.verify(body.get("captain"), body.get("pin"), body.get("house"), self._addr())
        except captains.CaptainError as e:
            journal.note("rejected", "join", "A Captain's PIN was refused: {}".format(e), via=self._via(),
                         error=str(e))
            raise GameError(str(e))
        with HUB.cond:
            try:
                token = HUB.game.join(c["name"], h["name"], HUB.present(), via=self._via(), captain=c["cid"])
            except GameError as e:
                journal.note("rejected", "join", "Captain {} was refused a seat: {}".format(c["name"], e),
                             via=self._via(), error=str(e))
                raise
            pid = HUB.game.pid_for_token(token)
            seat = HUB.game.s["players"].get(pid)
            if seat is not None and not seat.get("hid"):
                seat["hid"] = h["hid"]   # the House this seat sails under (its crest is shown on the screens)
            captains.link_game(c["cid"], HUB.game.s.get("game_id"), pid, h)
            HUB.changed()
        journal.log("INFO", "players", "Captain {} came aboard under the House {}".format(c["name"], h["name"]),
                    **self._via())
        return self._send(200, {"ok": True, "token": token})

    # ------------------------------------------------------------- stats --
    def _finale_get(self):
        """The finale's Ledger of the Voyage (finale.py): every house's story, worked out from the
        journal up to the close. Only once the game has ended (or is in free play after the end)."""
        with HUB.cond:
            g = HUB.game
            gid = g.s.get("game_id")
            over = g.s["phase"] == "ended" or bool(g.s.get("free_play"))
        if not over:
            return self._send(200, {"ok": False})
        try:
            data = finale.book(gid)
        except Exception:
            crash("Working out the finale's ledger failed", game=gid)
            data = None
        return self._send(200, data or {"ok": False})

    def _stats_get(self, query):
        """A player's statistics (stats.py). The seat token says who is asking. Without a
        seat in the game in progress, a name gives that player's past games only, so
        nobody can look at another house's numbers while the game is still being played."""
        one = lambda k, d="": query.get(k, [d])[0]
        with HUB.cond:
            g = HUB.game
            pid = g.pid_for_token(one("token")) if one("token") else None
            me = g.s["players"].get(pid) if pid else None
            running = g.s["phase"] != "ended"
        cur = journal.current()
        name = (me["name"] if me else one("name")).strip()
        scope = one("scope", "voyage")
        try:
            if scope == "players":
                return self._send(200, {"ok": True, "players": stats.players_seen(), "me": name})
            if not name:
                return self._send(200, {"ok": False, "error": engine.tx("st.e_who"), "who": True,
                                        "players": stats.players_seen()})
            if scope == "career":
                cap = captains.get(me["captain"]) if me and me.get("captain") else None
                data = stats.career(name, running_gid=cur if running else None, running_pid=pid,
                                    links=captains.links(cap) if cap else None)
                return self._send(200, {"ok": True, "scope": "career", "name": name, "current": cur,
                                        "seated": bool(me), "career": data})
            gid = one("game") or cur or ""
            if gid == cur and running:
                if not me:
                    return self._send(200, {"ok": False, "error": engine.tx("st.e_seat"), "seat": True})
                target = pid
            else:
                target = stats.find_pid(gid, name)
            data = stats.voyage(gid, target, running=(gid == cur and running)) if target else None
            if data is None:
                return self._send(200, {"ok": False, "error": engine.tx("st.e_none"), "none": True})
            return self._send(200, {"ok": True, "scope": "voyage", "name": name, "current": cur,
                                    "seated": bool(me), "voyage": data})
        except Exception:
            crash("Working out statistics failed", scope=scope, game=one("game"))
            return self._send(200, {"ok": False, "error": engine.tx("st.e_failed")})

    # --------------------------------------------------------- art bible --
    def _artbible_generate(self, body):
        slot = str(body.get("slot") or "").strip().lower()
        if not ARTBIBLE_SLOT_RE.match(slot):
            return self._send(200, {"ok": False, "error": "That example slot is not valid."})
        aspect = str(body.get("aspect") or "")
        if aspect not in imagegen.ASPECTS:
            return self._send(200, {"ok": False, "error": "That aspect ratio is not supported."})
        width, height = imagegen.ASPECTS[aspect]
        prompt = str(body.get("prompt") or "")
        negative = body.get("negative")
        try:
            data, seed = imagegen.generate_image(prompt, "seatrader/artbible-" + slot, width, height,
                                                 None if negative is None else str(negative))
        except imagegen.ImageGenError as e:
            journal.log("ERROR", "admin", "Art Bible example failed for {}: {}".format(slot, e), **self._via())
            return self._send(200, {"ok": False, "error": str(e)})
        os.makedirs(config.UPLOAD_DIR, exist_ok=True)
        fname = "artbible-{}-{}.png".format(slot.replace("_", "-"), secrets.token_hex(4))
        with open(os.path.join(config.UPLOAD_DIR, fname), "wb") as f:
            f.write(data)
        entry = {"url": "/uploads/" + fname, "prompt": prompt.strip(), "seed": seed, "aspect": aspect,
                 "width": width, "height": height, "date": time.strftime("%Y-%m-%d %H:%M")}
        with ARTBIBLE_LOCK:
            book = artbible_examples()
            book[slot] = ([entry] + [x for x in book.get(slot, []) if isinstance(x, dict)])[:8]
            tmp = ARTBIBLE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(book, f, indent=1, ensure_ascii=False)
            os.replace(tmp, ARTBIBLE_FILE)
        journal.log("INFO", "admin", "Generated Art Bible example {} ({:,} bytes, seed {})".format(
            slot, len(data), seed), **self._via())
        media.register_url(entry["url"], "reference", slot, ["reference"], nsfw=media.nsfw_from_prompt(prompt),
                           source="generated", prompt=prompt.strip(), seed=seed)
        return self._send(200, {"ok": True, "slot": slot, "example": entry, "history": book[slot]})

    # ------------------------------------------------------------- admin --
    def _admin_get(self, what, query):
        if what == "all":
            with HUB.cond:
                cfg = engine.CFG
                return self._send(200, {
                    "ok": True, "config": cfg, "defaults": config.DEFAULTS, "sections": config.SECTIONS,
                    "graphic_slots": config.GRAPHIC_SLOTS,
                    "strings": strings.EN, "family": strings.FAMILY, "string_groups": strings.GROUPS,
                    "langs": config.list_langs(),
                    "lang": {code: config.load_lang(code) for code in config.list_langs()},
                    "presets": config.list_dir(config.PRESET_DIR),
                    "backups": list(reversed(config.list_dir(config.BACKUP_DIR))),
                    "local": self._trusted(), "has_password": config.has_password(),
                    "join_url": HUB.join_url, "cast": self._cast_info(),
                    "server": {"python": platform.python_version(), "system": platform.system(),
                               "folder": ROOT, "started": int(STARTED)}})
        if what == "state":
            with HUB.cond:
                v = HUB.game.admin_view(HUB.present())
                v.update({"ok": True, "saves": list_saves(), "cfg": HUB.cfg_version, "join_url": HUB.join_url,
                          "start_at": HUB.game.s.get("start_at"),
                          "uptime": int(time.time() - STARTED)})
                return self._send(200, v)
        if what == "captains":
            pics = {}
            for it in media.load(engine.CFG)["items"]:
                if it["kind"] in ("captain", "house") and it["subject"] and it["type"] == "image":
                    pics.setdefault(it["subject"], []).append(
                        {"id": it["id"], "url": it["url"], "primary": it["primary"], "nsfw": it["nsfw"],
                         "enabled": it["enabled"], "added": it.get("added", ""), "source": it["source"],
                         "prompt": it.get("prompt", "")})
            for v in pics.values():
                v.sort(key=lambda i: i["added"], reverse=True)       # newest first, the chosen one on top
                v.sort(key=lambda i: not i["primary"])
            return self._send(200, {"ok": True, "captains": captains.admin_list(engine.CFG, captain_career),
                                    "pictures": pics,
                                    "prompts": captains.prompts(), "free_pin": captains.free_pin(),
                                    "ports": {k: v.get("name", k) for k, v in engine.CFG.get("ports", {}).items()},
                                    "seated": {q.get("captain"): q["id"] for q in HUB.game.s["players"].values()
                                               if q.get("captain")},
                                    "jobs": media.JOBS.list()})
        if what == "voice/status":
            return self._send(200, dict(self._cast_status(), ok=True))
        if what == "voice/voices":
            try:
                return self._send(200, {"ok": True, "voices": voice.list_voices(force=bool(query.get("force")))})
            except voice.VoiceError as e:
                return self._send(200, {"ok": False, "error": str(e)})
        if what == "artbible/examples":
            return self._send(200, {"ok": True, "examples": artbible_examples(), "aspects": imagegen.ASPECTS})
        if what == "media/library":
            v = media.admin_view(engine.CFG)
            v.update(ok=True, jobs=media.JOBS.list(), aspects=imagegen.ASPECTS)
            return self._send(200, v)
        if what == "media/jobs":
            return self._send(200, {"ok": True, "jobs": media.JOBS.list()})
        if what.startswith("journal/"):
            return self._journal_get(what[len("journal/"):], query)
        if what == "export":
            return self._send(200, json.dumps(engine.CFG, indent=1, ensure_ascii=False), "application/json",
                              {"Content-Disposition": 'attachment; filename="seatrader-settings.json"'})
        self._send(404, {"ok": False, "error": "Not found"})

    def _admin_post(self, what, query):
        # A custom header that other websites cannot send keeps them from poking at this.
        if self.headers.get("X-SeaTrader") != "admin":
            return self._send(403, {"ok": False, "error": "Not allowed."})
        if what == "login":
            body = self._body()
            if not config.has_password():
                return self._send(200, {"ok": False, "error": "No admin password has been set. Open the Admin "
                                        "page on the computer running the game and set one under Backup & Access."})
            if not config.check_password(body.get("password")):
                time.sleep(1)
                journal.log("WARN", "admin", "Admin sign-in failed: wrong password", **self._via())
                return self._send(200, {"ok": False, "error": "Wrong password."})
            token = secrets.token_urlsafe(24)
            SESSIONS.add(token)
            journal.log("INFO", "admin", "Admin signed in from another device", **self._via())
            return self._send(200, {"ok": True}, headers={
                "Set-Cookie": "st_admin={}; Path=/; HttpOnly; SameSite=Strict; Max-Age=2592000".format(token)})
        if not self._admin_ok():
            return self._deny()

        if what == "upload":
            name = os.path.basename(query.get("name", ["image"])[0])
            stem, ext = os.path.splitext(name)
            ext = ext.lower()
            if ext not in config.IMAGE_EXT:
                return self._send(200, {"ok": False, "error": "Use a PNG, JPG, WebP, GIF, SVG or ICO image."})
            data = self._raw(MAX_UPLOAD)
            if data is None:
                return self._send(200, {"ok": False, "error": "The image is empty or larger than 8 MB."})
            stem = re.sub(r"[^A-Za-z0-9_-]", "", stem)[:40] or "image"
            os.makedirs(config.UPLOAD_DIR, exist_ok=True)
            fname = "{}-{}{}".format(stem, secrets.token_hex(3), ext)
            with open(os.path.join(config.UPLOAD_DIR, fname), "wb") as f:
                f.write(data)
            journal.log("INFO", "admin", "Image uploaded: {} ({:,} bytes)".format(fname, len(data)), **self._via())
            return self._send(200, {"ok": True, "url": "/uploads/" + fname})

        if what == "media/upload":
            return self._media_upload(query)
        if what == "captains/upload":
            return self._captain_upload(query)

        body = self._body(4 * 1024 * 1024)
        if what.startswith("captains/"):
            return self._captains_post(what[len("captains/"):], body)
        if what.startswith("media/"):
            return self._media_post(what[len("media/"):], body)
        if what == "imagegen/portrait":
            character = str(body.get("character") or "").strip().lower()
            if not re.match(r"^[a-z][a-z0-9_]{0,23}$", character):
                return self._send(200, {"ok": False, "error": "That character key is not valid."})
            try:
                data = imagegen.generate_portrait(body.get("prompt"), character)
            except imagegen.ImageGenError as e:
                journal.log("ERROR", "admin", "Portrait generation failed for {}: {}".format(character, e),
                            **self._via())
                return self._send(200, {"ok": False, "error": str(e)})
            os.makedirs(config.UPLOAD_DIR, exist_ok=True)
            fname = "portrait-{}-{}.png".format(character, secrets.token_hex(4))
            with open(os.path.join(config.UPLOAD_DIR, fname), "wb") as f:
                f.write(data)
            journal.log("INFO", "admin", "Generated a new portrait for {} ({:,} bytes)".format(
                character, len(data)), **self._via())
            prompt = str(body.get("prompt") or "")
            media.register_url("/uploads/" + fname, "persona", character, ["portrait"],
                               nsfw=media.nsfw_from_prompt(prompt, media.load(engine.CFG)["options"]),
                               source="generated", prompt=prompt)
            return self._send(200, {"ok": True, "url": "/uploads/" + fname,
                                    "msg": "New portrait generated. Save & apply to keep it."})
        if what == "imagegen/artbible":
            example = str(body.get("id") or "")
            mode = "import" if body.get("mode") == "import" else "generate"
            try:
                entry = artbible.import_from_farm(example) if mode == "import" else artbible.generate(example)
            except imagegen.ImageGenError as e:
                if mode == "generate":
                    journal.log("ERROR", "admin", "Art Bible example {} failed: {}".format(example[:24], e),
                                **self._via())
                return self._send(200, {"ok": False, "error": str(e)})
            journal.log("INFO", "admin", "Art Bible example {} {} ({:,} bytes)".format(
                example, "imported" if mode == "import" else "regenerated", entry["bytes"]), **self._via())
            if entry.get("file"):
                media.register_url("/assets/artbible/" + entry["file"], "reference",
                                   re.sub(r"[^a-z0-9_]", "_", example.lower())[:48], ["reference"],
                                   nsfw=media.nsfw_from_prompt(entry.get("prompt") or ""), source="generated",
                                   prompt=entry.get("prompt") or "", seed=entry.get("seed"))
            return self._send(200, {"ok": True, "entry": entry})
        if what == "imagegen/example":
            return self._artbible_generate(body)
        if what.startswith("voice/"):
            return self._voice_admin(what[len("voice/"):], body)
        if what == "journal":
            return self._journal_post(body)
        if what == "save":
            cfg, errors = config.validate(body.get("config"))
            if errors:
                return self._send(200, {"ok": False, "errors": errors[:40], "error": "Some settings need fixing."})
            langs = body.get("langs") if isinstance(body.get("langs"), dict) else {}
            try:
                for code, data in langs.items():
                    if isinstance(data, dict):
                        config.save_lang(code, data)
            except ValueError as e:
                return self._send(200, {"ok": False, "error": str(e)})
            if cfg["language"]["active"] not in config.list_langs():
                cfg["language"]["active"] = "en"
            with HUB.cond:
                config.save(cfg)
                HUB.reload_settings(langs_saved=[c for c, d in langs.items() if isinstance(d, dict)])
            synced = media.sync_from_config(engine.CFG)
            for key, was, now, how in synced["changes"]:
                journal.log("INFO", "admin", "Graphics: {} {} ({} -> {})".format(
                    key, "file changed on disk" if how == "file" else "removed" if how == "removed" else
                    "changed (" + how + ")", was or "none", now or "none"), **self._via())
            if synced["retagged"]:
                journal.log("INFO", "admin", "Media library: re-filed {} picture(s) under the Graphics slot they "
                            "fill".format(synced["retagged"]), **self._via())
            return self._send(200, {"ok": True, "msg": "Saved. Every screen has been updated."})
        if what == "lang_delete":
            code = str(body.get("code") or "")
            path = config.lang_path(code)
            if code == "en" or not path or not os.path.isfile(path):
                return self._send(200, {"ok": False, "error": "That language cannot be removed."})
            with HUB.cond:
                os.remove(path)
                if engine.CFG["language"]["active"] == code:
                    cfg = json.loads(json.dumps(engine.CFG))
                    cfg["language"]["active"] = "en"
                    config.save(cfg)
                HUB.reload_settings()
            return self._send(200, {"ok": True, "msg": "Language removed."})
        if what == "preset":
            op, name = body.get("op"), body.get("name")
            path = config.preset_path(name)
            if not path:
                return self._send(200, {"ok": False, "error": "Give the preset a name (letters, digits, spaces)."})
            if op == "save":
                cfg, errors = config.validate(body.get("config"))
                if errors:
                    return self._send(200, {"ok": False, "errors": errors[:40], "error": "Some settings need fixing."})
                config._write(path, cfg)
                return self._send(200, {"ok": True, "msg": "Preset saved.", "presets": config.list_dir(config.PRESET_DIR)})
            if op == "delete":
                if os.path.isfile(path):
                    os.remove(path)
                return self._send(200, {"ok": True, "msg": "Preset deleted.", "presets": config.list_dir(config.PRESET_DIR)})
            if op == "load":
                data = config.read_named(config.PRESET_DIR, name)
                if data is None:
                    return self._send(200, {"ok": False, "error": "That preset is missing."})
                cfg, errors = config.validate(data)
                return self._send(200, {"ok": not errors, "config": cfg, "errors": errors[:40],
                                        "error": "That preset has problems." if errors else ""})
        if what == "backup":
            data = config.read_named(config.BACKUP_DIR, body.get("name"))
            if data is None:
                return self._send(200, {"ok": False, "error": "That backup is missing."})
            cfg, errors = config.validate(data)
            return self._send(200, {"ok": not errors, "config": cfg, "errors": errors[:40],
                                    "error": "That backup has problems." if errors else ""})
        if what == "password":
            if not self._trusted() and not config.check_password(body.get("current")):
                time.sleep(1)
                return self._send(200, {"ok": False, "error": "Enter the current password to change it from another device."})
            new = str(body.get("password") or "")
            if new and len(new) < 4:
                return self._send(200, {"ok": False, "error": "Use at least 4 characters."})
            config.set_password(new)
            journal.log("INFO", "admin", "Admin password {}".format("set" if new else "removed"), **self._via())
            if not new:
                SESSIONS.clear()
            return self._send(200, {"ok": True, "msg": "Password set." if new else "Password removed. "
                                    "The admin page now works only on the computer running the game."})
        if what == "game":
            op = body.get("op")
            with HUB.cond:
                if op == "new":
                    HUB.save()
                    archive_save()
                    HUB.replace_game(Game(), "new game started from the Admin page", kind="game_start")
                    return self._send(200, {"ok": True, "msg": "New game started. The old one is in the saves folder."})
                if op == "load_save":
                    name = re.sub(r"[^A-Za-z0-9_-]", "", str(body.get("name") or ""))
                    src = os.path.join(SAVES, name + ".json")
                    if not name or name == "current" or not os.path.isfile(src):
                        return self._send(200, {"ok": False, "error": "That save is missing."})
                    try:
                        with open(src, encoding="utf-8") as f:
                            game = Game(state=json.load(f))
                    except (ValueError, KeyError, TypeError, OSError):
                        return self._send(200, {"ok": False, "error": "That save could not be read."})
                    HUB.save()
                    archive_save()
                    HUB.replace_game(game, "restored from the save {}".format(name))
                    return self._send(200, {"ok": True, "msg": "Save restored. Players rejoin on the devices they used."})
                if op == "force":
                    body["present"] = sorted(HUB.present())   # captains at a screen fight their own battles
                if op == "start":
                    msg = HUB.cue_start()
                else:
                    msg = HUB.game.admin(op, body)
                    HUB.changed()
            return self._send(200, {"ok": True, "msg": msg})
        self._send(404, {"ok": False, "error": "Not found"})

    # ------------------------------------------------------- media library --
    def _media_upload(self, query):
        one = lambda k, d="": query.get(k, [d])[0]
        name = os.path.basename(one("name", "file"))
        stem, ext = os.path.splitext(name)
        ext = ext.lower()
        if ext not in media.IMAGE_EXT + media.VIDEO_EXT:
            return self._send(200, {"ok": False, "error": "Use a PNG, JPG, WebP, GIF or SVG picture, or an MP4, WebM or MOV video."})
        limit = media.MAX_VIDEO if ext in media.VIDEO_EXT else media.MAX_IMAGE
        data = self._raw(limit)
        if data is None:
            return self._send(200, {"ok": False, "error": "The file is empty or larger than {} MB.".format(limit // (1024 * 1024))})
        kind = one("kind", "other")
        subject = one("subject").lower()
        roles = [r for r in one("roles").split(",") if r]
        try:
            replaces = one("replaces")
            it = media.add_bytes(data, ext, kind, subject, roles, media._tags(one("tags")), one("nsfw") == "1",
                                 "upload", title=re.sub(r"[_-]+", " ", stem)[:80],
                                 replaces=replaces if media.ITEM_RE.match(replaces) else "")
        except media.MediaError as e:
            return self._send(200, {"ok": False, "error": str(e)})
        journal.log("INFO", "admin", "Media library: uploaded {} as {}/{} ({:,} bytes)".format(
            it["url"], it["kind"], it["subject"] or "-", len(data)), **self._via())
        return self._send(200, {"ok": True, "item": it})

    def _captains_post(self, what, body):
        """Admin > Captains: save, delete, prompt templates, star a picture."""
        try:
            if what == "save":
                c = captains.save_captain(body.get("captain"))
                media._public_cache.clear()
                with HUB.cond:
                    HUB.sync_houses()          # a House renamed here is renamed at the table too
                journal.log("INFO", "admin", "Captain {} saved ({} House{})".format(
                    c["name"], len(c["houses"]), "" if len(c["houses"]) == 1 else "s"), **self._via())
                return self._send(200, {"ok": True, "cid": c["cid"], "msg": "{} saved.".format(c["name"])})
            if what == "delete":
                cid = str(body.get("cid") or "")
                if any(q.get("captain") == cid for q in HUB.game.s["players"].values()) \
                        and HUB.game.s["phase"] != "ended":
                    return self._send(200, {"ok": False, "error": "That Captain is sailing in the game now. "
                                            "Retire them instead, or wait until the game ends."})
                c = captains.delete_captain(cid)
                journal.log("INFO", "admin", "Captain {} deleted (PIN {})".format(c["name"], c["pin"]), **self._via())
                return self._send(200, {"ok": True, "msg": "{} deleted. Their games stay in the Captain's "
                                        "Report.".format(c["name"])})
            if what == "prompts":
                captains.set_prompts(body.get("prompts"))
                return self._send(200, {"ok": True, "msg": "Prompt templates saved."})
            if what == "pick":
                iid = str(body.get("id") or "")
                it = next((i for i in media.load(engine.CFG)["items"] if i["id"] == iid), None)
                if not it or it["kind"] not in ("captain", "house"):
                    return self._send(200, {"ok": False, "error": "Choose a Captain or House picture."})
                role = "portrait" if it["kind"] == "captain" else "crest"
                media.update([iid], {"primary": True, "enabled": True}, add_roles=[role])
                return self._send(200, {"ok": True, "url": it["url"], "msg": "Picture chosen."})
        except captains.CaptainError as e:
            return self._send(200, {"ok": False, "error": str(e)})
        self._send(404, {"ok": False, "error": "Not found"})

    def _captain_upload(self, query):
        """A picture of a Captain or House chosen from disk: filed in the Media Library and starred."""
        kind = query.get("kind", [""])[0]
        subject = query.get("subject", [""])[0]
        if kind not in ("captain", "house") or not (captains.CID_RE.match(subject) or captains.HID_RE.match(subject)):
            return self._send(200, {"ok": False, "error": "Save the Captain first, then add pictures."})
        ext = os.path.splitext(os.path.basename(query.get("name", ["image.png"])[0]))[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            return self._send(200, {"ok": False, "error": "Use a PNG, JPG, WebP or GIF image."})
        data = self._raw(MAX_UPLOAD)
        if data is None:
            return self._send(200, {"ok": False, "error": "The image is empty or larger than 8 MB."})
        it = media.add_bytes(data, ext, kind, subject, ["portrait" if kind == "captain" else "crest"],
                             source="upload", primary=True, reviewed=True)
        journal.log("INFO", "admin", "Captains: uploaded {} for {}/{}".format(it["url"], kind, subject), **self._via())
        return self._send(200, {"ok": True, "url": it["url"], "msg": "Picture added and chosen."})

    def _media_post(self, what, body):
        cfg = engine.CFG
        ids = [str(x) for x in body.get("ids") or [] if isinstance(x, str)][:2000]
        if what == "update":
            changes = body.get("changes") if isinstance(body.get("changes"), dict) else {}
            lst = lambda k: [str(x) for x in body.get(k) or [] if isinstance(x, str)]
            n = media.update(ids, changes, lst("add_tags"), lst("remove_tags"), lst("add_roles"), lst("remove_roles"))
            return self._send(200, {"ok": True, "changed": n, "msg": "Saved."})
        if what == "delete":
            in_use = [u for u, *_ in media._config_refs(cfg)]   # Captain and House pictures may go; the next is shown
            want = set(ids)
            urls = [i["url"] for i in media.load(cfg)["items"] if i.get("id") in want and i.get("url") not in in_use]
            n = media.remove(ids, in_use)
            prune_artbible(urls)
            journal.log("INFO", "admin", "Media library: removed {} item(s)".format(n), **self._via())
            return self._send(200, {"ok": True, "msg": "Removed {} item{} (files moved to web/media/_trash).".format(
                n, "" if n == 1 else "s")})
        if what == "rules":
            media.set_rules(body.get("rules"), body.get("options"))
            return self._send(200, {"ok": True, "msg": "Playback rules saved. Every screen has been updated."})
        if what == "scan":
            added, missing = media.scan(cfg)
            return self._send(200, {"ok": True, "msg": "Scan done: {} new, {} missing file{} dropped.".format(
                added, missing, "" if missing == 1 else "s")})
        if what == "safe":
            rating = "family" if body.get("family") else "historical"
            with HUB.cond:
                new = json.loads(json.dumps(engine.CFG))
                new["content"]["rating"] = rating
                config.save(new)
                HUB.reload_settings()
            journal.log("INFO", "admin", "Content rating set to {} from the Media Library".format(rating), **self._via())
            return self._send(200, {"ok": True, "rating": rating, "msg": "Family-friendly is on: NSFW items are hidden "
                                    "everywhere." if rating == "family" else "Family-friendly is off."})
        if what == "profile":
            it = next((i for i in media.load(cfg)["items"] if ids and i["id"] == ids[0]), None)
            if not it or it["kind"] != "persona" or it["type"] != "image":
                return self._send(200, {"ok": False, "error": "Choose a persona picture first."})
            cid = it["subject"]
            if cid not in cfg.get("characters", {}):
                return self._send(200, {"ok": False, "error": "That persona is not in the cast."})
            with HUB.cond:
                new = json.loads(json.dumps(engine.CFG))
                new["characters"][cid]["portrait"] = it["url"]
                config.save(new)
                HUB.reload_settings()
            media.update([it["id"]], {"primary": True}, add_roles=["portrait"])
            return self._send(200, {"ok": True, "cid": cid, "url": it["url"],
                                    "msg": "Profile picture set for {}.".format(cid)})
        if what == "generate":
            kind = str(body.get("kind") or "")
            subject = str(body.get("subject") or "").lower()
            if kind not in media.KINDS or (subject and not media.ID_RE.match(subject)):
                return self._send(200, {"ok": False, "error": "Choose what the pictures are of first."})
            aspect = str(body.get("aspect") or "3:4")
            if aspect not in imagegen.ASPECTS:
                return self._send(200, {"ok": False, "error": "That shape is not supported."})
            prompt = str(body.get("prompt") or "").strip()
            if len(prompt) < 20:
                return self._send(200, {"ok": False, "error": "Write a prompt (at least 20 characters) first."})
            try:
                count = max(1, min(8, int(body.get("count") or 1)))
            except (TypeError, ValueError):
                count = 1
            nsfw = body.get("nsfw") if body.get("nsfw") in ("auto", "yes", "no") else "auto"
            roles_ok = {r[0] for r in media.KINDS[kind]["roles"]}
            roles = [r for r in body.get("roles") or [] if r in roles_ok]
            w, h = imagegen.ASPECTS[aspect]
            job = media.JOBS.add(kind, subject, roles, prompt[:6000], w, h, count, nsfw,
                                 tags=media._tags(body.get("tags") or ""), aspect=aspect,
                                 replaces=str(body.get("replaces") or ""))
            journal.log("INFO", "admin", "Media library: queued {} picture(s) for {}/{}".format(
                count, kind, subject or "-"), **self._via())
            return self._send(200, {"ok": True, "job": job["id"], "msg": "Queued {} picture{}. Each is filed as it "
                                    "finishes.".format(count, "" if count == 1 else "s")})
        if what == "cancel":
            ok = media.JOBS.cancel(str(body.get("job") or ""))
            return self._send(200, {"ok": ok, "msg": "Cancelled.", "error": "That job has already finished."})
        self._send(404, {"ok": False, "error": "Not found"})

    # ----------------------------------------------------------- journal --
    def _journal_get(self, what, query):
        one = lambda k, d="": query.get(k, [d])[0]

        def num(k, d=None):
            try:
                return int(one(k))
            except ValueError:
                return d
        gid = one("game") or journal.current() or ""
        if what == "games":
            return self._send(200, {"ok": True, "games": journal.games(), "stats": journal.stats(),
                                    "days": journal.server_days()})
        if what == "index":
            idx = journal.index(gid)
            if idx is None:
                return self._send(200, {"ok": False, "error": "That game has no journal."})
            return self._send(200, dict(idx, ok=True, game=gid))
        if what == "events":
            cats = [c for c in one("cat").split(",") if c]
            res = journal.events(gid, after=num("after", 0), turn=num("turn"), cats=cats, pid=one("pid") or None,
                                 q=one("q"), limit=max(1, min(num("limit", 1500), 5000)), tail=bool(one("tail")))
            return self._send(200, dict(res, ok=True, game=gid, current=journal.current()))
        if what == "server":
            res = journal.server_log(one("day") or None, one("level") or None, one("q"))
            return self._send(200, dict(res, ok=True, days=journal.server_days()))
        if what == "download":
            if one("as") == "txt":
                text = journal.report_text(gid)
                if text is None:
                    return self._send(404, "Not found", "text/plain")
                return self._send(200, text, "text/plain; charset=utf-8", {
                    "Content-Disposition": 'attachment; filename="captains-report-{}.txt"'.format(gid)})
            path = journal.events_path(gid)
            if not path or not os.path.isfile(path):
                return self._send(404, "Not found", "text/plain")
            with open(path, "rb") as f:
                data = f.read()
            return self._send(200, data, "application/x-ndjson", {
                "Content-Disposition": 'attachment; filename="journal-{}.jsonl"'.format(gid)})
        self._send(404, {"ok": False, "error": "Not found"})

    def _journal_post(self, body):
        op, gid = body.get("op"), str(body.get("game") or "")
        if op == "keep":
            ok = journal.set_keep(gid, bool(body.get("keep")))
            return self._send(200, {"ok": ok, "msg": "Marked to keep." if body.get("keep") else "No longer marked to keep.",
                                    "error": "" if ok else "That game has no journal."})
        if op == "delete":
            if gid == journal.current():
                return self._send(200, {"ok": False, "error": "That is the game in progress. Start a new game first."})
            ok = journal.delete(gid)
            return self._send(200, {"ok": ok, "msg": "Journal deleted.", "error": "" if ok else "That game has no journal."})
        if op == "prune":
            gone = journal.prune()
            return self._send(200, {"ok": True, "msg": "Removed {} old record{}.".format(len(gone), "" if len(gone) == 1 else "s")
                                    if gone else "Nothing is past its keep-by date."})
        if op == "replay":
            if not journal.events_path(gid):
                return self._send(200, {"ok": False, "error": "That game has no journal."})
            cmd = [sys.executable, os.path.join(ROOT, "replay.py"), gid, "--json"]
            for key, flag in (("turn", "--turn"), ("from", "--from")):
                if body.get(key) not in (None, ""):
                    try:
                        cmd += [flag, str(int(body[key]))]
                    except (TypeError, ValueError):
                        pass
            try:
                out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=180,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                res = json.loads(out.stdout)
            except (OSError, ValueError, subprocess.SubprocessError) as e:
                journal.log("ERROR", "replay", "The replay check could not run: {!r}".format(e), game=gid)
                return self._send(200, {"ok": False, "error": "The replay check could not run: {}".format(e)})
            journal.log("INFO", "replay", "Replay check of {}: {} checked, {} different".format(
                gid, res.get("checked", 0), res.get("different", 0)), game=gid)
            return self._send(200, {"ok": True, "replay": res})
        self._send(404, {"ok": False, "error": "Not found"})

    # ------------------------------------------------------------- voice --
    def _voice_clip(self, cid):
        try:
            audio = voice.get_clip(cid)
        except voice.VoiceError as e:
            return self._send(502, {"ok": False, "error": str(e)})
        if audio is None:
            return self._send(404, {"ok": False, "error": "Not found"})
        # A clip never changes once made, so screens may keep it.
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(len(audio)))
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.end_headers()
        self.wfile.write(audio)

    def _cast_status(self):
        return {"key": voice.key_status(), "cache": voice.cache_info(), "stats": dict(voice.STATS)}

    def _cast_info(self):
        text = engine.TEXT
        return dict(self._cast_status(), models=cast.MODELS, stat_keys=cast.STAT_KEYS, stat_labels=cast.STAT_LABELS,
                    groups=cast.SPOKEN_GROUPS, line_defaults=cast.LINE_DEFAULTS, prefix_defaults=cast.PREFIX_DEFAULTS,
                    say_defaults={k: cast.say_default(text, k) for k in cast.spoken_keys(text) if cast.say_default(text, k)},
                    lines=[[k, text[k]] for k in cast.spoken_keys(text)], defaults=cast.CHARACTERS)

    def _voice_admin(self, what, body):
        if what == "key":
            try:
                voice.set_key(body.get("key"))
            except voice.VoiceError as e:
                return self._send(200, {"ok": False, "error": str(e)})
            with HUB.cond:
                HUB.cfg_version += 1          # screens reload and learn that voices are on or off
                HUB.changed(save=False)
            st = voice.key_status()
            journal.log("INFO", "voice", "Inworld key {} on the Admin page".format("saved" if body.get("key") else "removed"),
                        **self._via())
            return self._send(200, dict(self._cast_status(), ok=True, msg="Inworld key saved." if body.get("key")
                                        else "Key removed." + (" Using INWORLD_API_KEY from this computer."
                                                                if st["source"] == "env" else "")))
        if what == "clear_cache":
            n = voice.clear_cache()
            journal.log("INFO", "voice", "Voice cache cleared: {} clips removed".format(n))
            return self._send(200, dict(self._cast_status(), ok=True, msg="Removed {} saved clips.".format(n)))
        if what == "preview":
            ch = body.get("character") if isinstance(body.get("character"), dict) else {}
            model = body.get("model_id") if body.get("model_id") in [m[0] for m in cast.MODELS] else \
                engine.CFG["voice"]["model_id"]
            try:
                temp = min(2.0, max(0.0, float(body.get("temperature", engine.CFG["voice"]["temperature"]))))
                rate = min(1.5, max(0.5, float(ch.get("speaking_rate", 1.0))))
            except (TypeError, ValueError):
                temp, rate = 1.0, 1.0
            params = {"text": voice.speech_text(body.get("text"))[:600], "voice_id": str(ch.get("voice_id") or "").strip(),
                      "model_id": model, "rate": round(rate, 3), "temperature": round(temp, 3),
                      "delivery": " ".join(str(ch.get("delivery") or "").split())[:200] if voice.steers(model) else ""}
            try:
                audio = voice.render(params)
            except voice.VoiceError as e:
                return self._send(200, {"ok": False, "error": str(e)})
            return self._send(200, audio, "audio/mpeg")
        return self._send(404, {"ok": False, "error": "Not found"})

    def _events(self, token, family=False):
        with HUB.cond:
            pid = HUB.game.pid_for_token(token) if token else None
            if pid:
                HUB.conns[pid] = HUB.conns.get(pid, 0) + 1
                HUB.last_seen.pop(pid, None)
                HUB.version += 1
                HUB.cond.notify_all()
                name = HUB.game.s["players"][pid]["name"]
                journal.note("players", "connect", "{} connected a screen from {} ({}); {} open".format(
                    name, self._addr(), device(self.headers), HUB.conns[pid]), pid=pid, who=name,
                    via=self._via(), screens=HUB.conns[pid])
            elif token:
                journal.log("WARN", "players", "A screen connected with a seat that is not in this game", **self._via())
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            last = -1
            while True:
                with HUB.cond:
                    if HUB.version == last:
                        HUB.cond.wait(15)
                    payload = None
                    if HUB.version != last:
                        last = HUB.version
                        known = HUB.game.pid_for_token(token) if token else None
                        view = HUB.view(known)
                        view["unknown_token"] = bool(token) and known is None
                        if family or media.family(engine.CFG):
                            # this screen (or the whole table) is Family-friendly: clean ship names in
                            # every line, older log lines included; cargo names too for a screen alone
                            view = family_view(view)
                        payload = json.dumps(view)
                if payload is None:
                    self.wfile.write(b": keepalive\n\n")
                else:
                    self.wfile.write(b"data: " + payload.encode("utf-8") + b"\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionError, OSError):
            pass
        finally:
            if pid:
                with HUB.cond:
                    HUB.conns[pid] = max(0, HUB.conns.get(pid, 1) - 1)
                    if HUB.conns[pid] == 0:
                        HUB.last_seen[pid] = time.time()
                    HUB.version += 1
                    HUB.cond.notify_all()
                    p = HUB.game.s["players"].get(pid)
                    if p:
                        journal.note("players", "disconnect", "{} closed a screen at {}; {} open".format(
                            p["name"], self._addr(), HUB.conns[pid]), pid=pid, who=p["name"],
                            address=self._addr(), screens=HUB.conns[pid])


def lan_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    global HUB
    ap = argparse.ArgumentParser(description="Crimson Ledger game server")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--new", action="store_true", help="archive the saved game and start a fresh one")
    ap.add_argument("--archive-only", action="store_true", help="archive the saved game and exit")
    ap.add_argument("--join-url", help="the address shown to players, e.g. http://sea.trade (default: this machine's IP and port)")
    ap.add_argument("--admin-password", help="set the admin password (for the Admin page on other devices) and exit")
    args = ap.parse_args()

    if args.admin_password is not None:
        config.set_password(args.admin_password)
        print("Admin password set." if args.admin_password else "Admin password removed.")
        return
    if args.new or args.archive_only:
        if archive_save():
            print("Previous game archived in the saves folder.")
        if args.archive_only:
            return
    voice.on_log = lambda level, msg, **data: journal.log(level, "voice", msg, **data)
    fonts.on_log = lambda level, msg: journal.log(level, "fonts", msg)
    threading.excepthook = lambda a: (crash("A background task hit an error") if a.exc_type is not SystemExit else None)
    apply_settings()
    media.load(engine.CFG)
    media.sync_from_config(engine.CFG)
    media.on_change(_media_changed)
    media.JOBS.start(imagegen.generate_image, lambda level, msg: journal.log(level, "media", msg))
    join_url = (args.join_url or "").strip().rstrip("/") or "http://{}:{}".format(lan_address(), args.port)
    voicefloor.FLOOR.add_own(lan_address())
    journal.log("INFO", "server", "Server starting on port {} ({}, Python {}, code {})".format(
        args.port, platform.system(), platform.python_version(), git_commit() or "unversioned"),
        port=args.port, folder=ROOT, join_url=join_url, commit=git_commit(), new=bool(args.new))
    game, reason, kind = None, "", "checkpoint"
    if os.path.isfile(SAVE_FILE):
        try:
            with open(SAVE_FILE, encoding="utf-8") as f:
                state = json.load(f)
            adopted = not state.get("game_id")
            game = Game(state=state)
            reason = ("a game saved before records were kept; recording starts here" if adopted
                      else "resumed after a server restart")
            print("Resumed the saved game ({} players).".format(len(game.s["players"])))
        except (ValueError, KeyError, TypeError, OSError) as e:
            print("Could not read the save ({}); starting a new game.".format(e))
            journal.log("ERROR", "server", "Could not read the saved game ({!r}); it was set aside and a new game started".format(e))
            archive_save()
    if game is None:
        game, reason, kind = Game(), "new game", "game_start"
        print("Started a new game.")

    HUB = Hub(game, join_url)
    journal.open_game(game, reason, *settings_now(), kind=kind)
    backfill_market(game)
    stats.HOUSE_NAMES = captains.firm_names         # the records show each House's name now
    stats.NAMES_VERSION = captains.names_version
    with HUB.cond:
        HUB.sync_houses()
    try:
        httpd = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    except OSError as e:
        print("Could not open port {}: {}".format(args.port, e))
        print("Crimson Ledger may already be running.")
        journal.log("ERROR", "server", "Could not open port {}: {}".format(args.port, e))
        sys.exit(1)
    httpd.daemon_threads = True
    threading.Thread(target=HUB.ticker, daemon=True).start()
    threading.Thread(target=HUB.sea_watch, daemon=True).start()
    print("")
    print("  Crimson Ledger is running.")
    print("  This computer:   http://localhost:{}".format(args.port))
    print("  Other devices:   {}".format(join_url))
    print("  Harbor board:    {}/board".format(join_url))
    print("  Admin:           http://localhost:{}/admin".format(args.port))
    print("")
    print("  Leave this window open while you play. Close it to stop the game.")

    def stop(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)   # systemd stop on the Pi: save, then exit
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    with HUB.cond:
        HUB.save()
        journal.note("system", "server_stop", "The server stopped; the game was saved")
    journal.log("INFO", "server", "Server stopped; game saved", uptime=int(time.time() - STARTED))
    print("Game saved. Goodbye.")


if __name__ == "__main__":
    main()
