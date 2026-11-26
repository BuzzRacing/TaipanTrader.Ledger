"""Fully dressed scene prompts for the Media Library’s virtual recipe roles."""
import persona_prompts_v2 as pp

ENTRY_MOODS = {
    "sly": "a wry, appraising smile as the officer considers the declaration",
    "hungry": "keen interest in an unusually valuable cargo, leaning toward the manifest",
    "curious": "one eyebrow raised while comparing the manifest with a tally sheet",
    "bored": "a patient, businesslike expression while holding a customs stamp",
}
WEATHERS = {
    "calm": "still harbor water under a clear sky, holding up a broadsheet",
    "fair": "small whitecaps and steady wind, pointing at the sails offshore",
    "squalls": "rain sweeping across the harbor, holding the broadsheet tight",
    "typhoon": "heavy rain and wind beyond a sheltered wharf office, pointing to a storm chart",
}
TAX_ENTRY_ROLES = ["tax_entry_" + mood for mood in ENTRY_MOODS]
WEATHER_ROLES = ["weather_clean_" + kind for kind in WEATHERS]


def officers(cfg):
    chars = cfg.get("characters") or {}
    return list(dict.fromkeys(p["officer"] for p in (cfg.get("ports") or {}).values()
                              if p.get("officer") in chars))


def all_prompts(cfg):
    chars = cfg.get("characters") or {}
    prompts, notes = {}, []
    for cid in officers(cfg):
        base = (chars[cid].get("portrait_prompt") or "").strip()
        if len(base) < 20:
            notes.append(f"{cid} has no portrait prompt. Add one in Cast & Voices to queue desk faces.")
            continue
        prompts[cid] = {
            "tax_entry_" + mood: {"clean": pp.build(cid, mood=expression, saved=base) if cid in pp.LOOKS
                                  else f"{base}, {expression}, fully dressed in period clothing",
                                  "aspect": "3:4", "role": mood if mood == "sly" else "idle",
                                  "need": [mood], "tags": [mood], "label": f"Desk face, {mood}"}
            for mood, expression in ENTRY_MOODS.items()
        }
    if "crier" in chars:
        saved = chars["crier"].get("portrait_prompt")
        prompts["crier"] = {}
        for kind, scene in WEATHERS.items():
            tag = "weather-" + kind
            poses = [pp.build("crier", mood=f"{scene}, {angle}", saved=saved)
                     for angle in ("front view", "three-quarter view", "seen from the wharf",
                                   "close framing on the reporter", "wide view of the harbor")]
            prompts["crier"]["weather_clean_" + kind] = {
                "clean": poses[0], "aspect": "3:4", "role": "weather",
                "need": [tag], "tags": ["weather", tag], "variants": poses, "label": f"Weather, {kind}",
            }
    labels = {key: entry["label"] for entries in prompts.values() for key, entry in entries.items()}
    return prompts, labels, notes
