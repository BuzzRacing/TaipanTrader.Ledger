"""Recipe prompts for pictures that used to need a .bat file (24 Nov 2026). Ported from Atomic Ledger.

Admin > Media Library > Recipes counts what is filed and paints only what is short. Two groups of batches that were
Queue_TaxLady_*_Pairs.bat and Queue_Weather_Pictures.bat / Queue_Weather_Topless.bat are now recipes. Their prompts come
from the very same code the .bat files run (tools/queue_persona_pairs.py, tools/queue_weather_pictures.py and
tools/queue_weather_topless.py), so a recipe paints exactly what the .bat would have painted. This module only
reshapes those prompts for the Recipes panel. (The wide 16:9 tax RESULT pictures are tax_results.py's, as before.)

Each picture the Recipes panel can paint here has a "virtual role", a key such as tax_entry_hungry or
weather_nude_calm. It is a recipe's own name for one exact picture: the real role it is filed under, the tags that
tell it apart from the officer's or the crier's other pictures, and its prompts:

    {persona: {virtual role: {"nsfw": prompt, "clean": prompt or "", "aspect": "3:4",
                              "role": the real role, "need": [tags a filed picture must carry to count],
                              "not": [tags it must not carry], "tags": [tags the new picture gets],
                              "variants": {"nsfw": [...], "clean": [...]} (optional: one prompt per pose),
                              "label": what the recipe's role list shows}}}

web/media-admin.js reads that (scene_prompts) to count, preview and queue. media.admin_view hands it over, with
virtual_roles ({key: label}) and notes (anything skipped, for example an officer with no portrait prompt yet).

    tax_entry_sly, _hungry, _curious, _bored   the Port Authority officer's desk tells (3:4, role sly / idle)
    weather_nude_<kind>, weather_topless_<kind>, weather_clean_<kind>
                                               Tommy Marsh's weather pictures for calm, fair, squalls and typhoon
                                               (3:4, role weather); one prompt per pose, four nude, five topless, five clean
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(ROOT, "tools")

ENTRY_MOODS = ("sly", "hungry", "curious", "bored")
ENTRY_LABELS = {"sly": "Desk face, sly (Pay Nothing)",
                "hungry": "Desk face, hungry (a big lie)",
                "curious": "Desk face, curious (a middling lie)",
                "bored": "Desk face, bored (an honest or small lie)"}
WEATHERS = ("calm", "fair", "squalls", "typhoon")
LOOKS = ("nude", "topless", "clean")

TAX_ENTRY_ROLES = ["tax_entry_" + m for m in ENTRY_MOODS]
WEATHER_NUDE_ROLES = ["weather_nude_" + k for k in WEATHERS]
WEATHER_TOPLESS_ROLES = ["weather_topless_" + k for k in WEATHERS]
WEATHER_CLEAN_ROLES = ["weather_clean_" + k for k in WEATHERS]
WEATHER_ROLES = WEATHER_NUDE_ROLES + WEATHER_TOPLESS_ROLES + WEATHER_CLEAN_ROLES


def _tools():
    """The .bat generators, imported the way their own scripts import each other. queue_weather_pictures reads the
    command line when it is imported, so it is shown an empty one (the server's own is not its business)."""
    if TOOLS not in sys.path:
        sys.path.append(TOOLS)
    saved = sys.argv
    sys.argv = [saved[0] if saved else "recipe_scenes"]
    try:
        import queue_persona_pairs as pairs
        import queue_weather_pictures as weather
        import queue_weather_topless as topless
    finally:
        sys.argv = saved
    return pairs, weather, topless


def officers(cfg):
    """The cast keys of the Port Authority officers on the live game: each port's own officer, in port order."""
    chars = cfg.get("characters") or {}
    out = []
    for p in (cfg.get("ports") or {}).values():
        k = str((p or {}).get("officer") or "")
        if k and k in chars and k not in out:
            out.append(k)
    return out


def tax_entry_prompts(cfg, notes):
    """{officer: {virtual role: entry}} for every officer's four desk tells (what Queue_TaxLady_*_Pairs.bat made)."""
    pairs, _w, _t = _tools()
    pp = pairs.pp
    chars = cfg.get("characters") or {}
    out = {}
    for cid in officers(cfg):
        base = str((chars.get(cid) or {}).get("portrait_prompt") or "").strip()
        if len(base) < 20:
            notes.append("{} has no portrait prompt yet, so no desk faces for her (Admin > Voices > Cast & Voices).".format(cid))
            continue
        found = {}
        for mood in ENTRY_MOODS:
            expr = pairs.MOODS[mood]
            if pp and cid in pp.LOOKS:           # her own nude and clean looks from persona_prompts_v2
                nsfw, clean = pp.build(cid, "nude", expr, saved=base), pp.build(cid, "clean", expr, saved=base)
            else:
                nsfw, clean = pairs.nsfw_prompt(base, expr), pairs.clean_prompt(base, expr)
            found["tax_entry_" + mood] = {
                "nsfw": nsfw[:6000], "clean": clean[:6000], "aspect": "3:4",
                "role": mood if mood in pairs.PERSONA_ROLES else "idle",
                "need": [mood], "not": [], "tags": [mood], "label": ENTRY_LABELS[mood]}
        out[cid] = found
    return out


def weather_prompts(cfg, notes):
    """{crier: {virtual role: entry}} for Tommy Marsh's weather set: what the two weather .bat files made."""
    _p, w, t = _tools()
    if w.WHO not in (cfg.get("characters") or {}):
        notes.append("There is no news crier in the cast, so no weather pictures.")
        return {}

    def one(kind, pose, wear, tail):
        sky, _poses = w.SCENES[kind]
        return ", ".join((w.HEAD, sky, pose, wear)) + tail

    found = {}
    for kind in w.KINDS:
        sky, poses = w.SCENES[kind]
        poses = list(poses)
        five = poses + [t.POSE5[kind]]
        nude = [one(kind, p, w.NUDE_WEAR[kind], w.NUDE_TAIL) for p in poses]
        topless = [one(kind, p, t.TOPLESS_WEAR[kind], t.TOPLESS_TAIL) for p in five]
        clean = [one(kind, p, w.CLEAN_WEAR[kind], w.CLEAN_TAIL) for p in five]
        name = {"calm": "calm", "fair": "fair", "squalls": "squalls", "typhoon": "typhoon"}[kind]
        base = {"aspect": "3:4", "role": "weather"}
        found["weather_nude_" + kind] = dict(base, nsfw=nude[0], clean="", need=["weather-" + kind], **{
            "not": ["topless"], "tags": ["weather", "weather-" + kind], "variants": {"nsfw": nude, "clean": []},
            "label": "Weather {}, nude".format(name)})
        found["weather_topless_" + kind] = dict(base, nsfw=topless[0], clean="", need=["weather-" + kind, "topless"], **{
            "not": [], "tags": ["weather", "weather-" + kind, "topless"], "variants": {"nsfw": topless, "clean": []},
            "label": "Weather {}, topless".format(name)})
        found["weather_clean_" + kind] = dict(base, nsfw="", clean=clean[0], need=["weather-" + kind], **{
            "not": [], "tags": ["weather", "weather-" + kind], "variants": {"nsfw": [], "clean": clean},
            "label": "Weather {}, clean".format(name)})
    return {w.WHO: found}


def all_prompts(cfg):
    """(scene prompts, virtual role labels, notes) for Admin > Media Library."""
    notes, prompts = [], {}
    for part in (tax_entry_prompts(cfg, notes), weather_prompts(cfg, notes)):
        for subject, entries in part.items():
            prompts.setdefault(subject, {}).update(entries)
    labels = {}
    for entries in prompts.values():
        for key, e in entries.items():
            labels[key] = e["label"]
    return prompts, labels, list(dict.fromkeys(notes))
