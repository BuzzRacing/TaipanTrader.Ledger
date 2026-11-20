"""Sound catalog checks: event IDs, categories, clip files, source records, scenes, server file types, silent videos.
Run:  python tests/audio_test.py"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
AUDIO_DIR = os.path.join(WEB, "media", "audio")
CATEGORIES = {"system", "music", "atmosphere", "dialogue"}
SYNTH = {"click", "chime", "knock", "bell", "wash"}      # the built-in placeholder sounds in web/audio.js
EXTENSIONS = (".mp3", ".m4a", ".ogg", ".opus", ".wav")

problems = []
notes = []


def bad(msg):
    problems.append(msg)


def load_unique(path):
    """Read JSON, failing on a repeated key (a repeated event ID would silently replace the first)."""
    def hook(pairs):
        seen = set()
        for k, _ in pairs:
            if k in seen:
                bad("duplicate key in catalog: %r" % k)
            seen.add(k)
        return dict(pairs)
    with open(path, encoding="utf-8") as f:
        return json.load(f, object_pairs_hook=hook)


def has_source(rec):
    s = rec.get("source", rec)
    return bool(s.get("pack")) and bool(s.get("license"))


cat = load_unique(os.path.join(WEB, "audio", "catalog.json"))
tracks, events, scenes = cat.get("tracks", {}), cat.get("events", {}), cat.get("scenes", {})
if cat.get("version") != 1:
    bad("catalog version should be 1")

# Events: stable IDs, a valid player category, a sound to play, sane numbers, a source record.
for eid, ev in events.items():
    if not re.fullmatch(r"[a-z0-9]+(\.[a-z0-9_]+)+", eid):
        bad("event ID %r should look like trade.buy.success" % eid)
    if ev.get("category") not in CATEGORIES:
        bad("%s: category %r is not one of %s" % (eid, ev.get("category"), sorted(CATEGORIES)))
    files = ev.get("files") or []
    if not files and ev.get("synth") not in SYNTH:
        bad("%s: needs files, or a built-in sound from %s" % (eid, sorted(SYNTH)))
    if files and ev.get("synth"):
        bad("%s: has both files and a built-in sound" % eid)
    for key, lo, hi in (("gain_db", -40, 12), ("cooldown_ms", 0, 60000), ("max", 1, 12), ("priority", 1, 3)):
        v = ev.get(key, lo if key != "max" and key != "priority" else 1)
        if not isinstance(v, (int, float)) or not lo <= v <= hi:
            bad("%s: %s=%r outside %s..%s" % (eid, key, v, lo, hi))
    if not has_source(ev):
        bad("%s: needs a source record (pack and license)" % eid)
    for f in files:
        if not f.lower().endswith(EXTENSIONS):
            bad("%s: %s is not a web audio file" % (eid, f))

# Tracks: each needs its source record, and scenes may only use known tracks.
for f, rec in tracks.items():
    if not f.lower().endswith(EXTENSIONS):
        bad("track %s is not a web audio file" % f)
    for k in ("pack", "original", "license", "title"):
        if not rec.get(k):
            bad("track %s: missing %s" % (f, k))
for sid, sc in scenes.items():
    for part in ("music", "atmosphere"):
        v = sc.get(part, "inherit")
        if v is None or v == "inherit":
            continue
        if not isinstance(v, list):
            bad("scene %s.%s should be a list, null or \"inherit\"" % (sid, part))
            continue
        for f in v:
            if f not in tracks and not any(f in (e.get("files") or []) for e in events.values()):
                bad("scene %s.%s uses %s, which has no record under tracks" % (sid, part, f))

# Clip files: checked only on a machine that has the (git-ignored) audio folder.
if os.path.isdir(AUDIO_DIR):
    used = set(tracks) | {f for e in events.values() for f in (e.get("files") or [])}
    for f in sorted(used):
        p = os.path.join(AUDIO_DIR, *f.split("/"))
        if not os.path.isfile(p) or os.path.getsize(p) < 1000:
            bad("clip missing or empty: web/media/audio/%s" % f)
else:
    notes.append("web/media/audio not on this machine: clip files not checked")

# The Python server must know the audio file types, or the browser gets the wrong Content-Type.
server = os.path.join(ROOT, "server.py")
if os.path.isfile(server):
    src = open(server, encoding="utf-8").read()
    for ext in EXTENSIONS:
        if '"%s"' % ext not in src:
            bad("server.py TYPES has no %s entry" % ext)

# Every video on the game screens stays muted: all sound goes through the mixer.
video_tag = re.compile(r"<video\b[^>]*>", re.S)
for name in sorted(os.listdir(WEB)):
    if not name.endswith((".js", ".html")):
        continue
    if "admin" in name or name == "art-bible.js":
        continue     # admin tools preview library clips themselves, like the Cast and Voices audition
    text = open(os.path.join(WEB, name), encoding="utf-8", errors="replace").read()
    for m in video_tag.finditer(text):
        if not re.search(r"\bmuted\b", m.group(0)):
            bad("%s: a <video> without the muted attribute: %s" % (name, m.group(0)[:70].replace("\n", " ")))
    for m in re.finditer(r"createElement\(\s*[\"']video[\"']\s*\)", text):
        tail = text[m.end():m.end() + 400]
        if not re.search(r"\.muted\s*=\s*true|setAttribute\(\s*[\"']muted", tail):
            bad("%s: a created video element is not muted" % name)

for n in notes:
    print("note:", n)
if problems:
    print("FAILED audio checks:")
    for p in problems:
        print("  -", p)
    sys.exit(1)
print("OK: audio catalog checks passed (%d events, %d tracks, %d scenes)" % (len(events), len(tracks), len(scenes)))
