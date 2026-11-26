"""Taipan Trader's own rules, checked after every merge from Crimson Ledger (Sync_From_Crimson_Ledger.bat):
family-friendly only, no NSFW pictures, a mixed cast. Run from the game folder: python tests/taipan_clean_test.py"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import cast                # noqa: E402
import config              # noqa: E402
import media               # noqa: E402
import persona_prompts_v2  # noqa: E402
import strings             # noqa: E402
import taipan_text         # noqa: E402

ADULT = re.compile(r"\b(naked|nude|nudity|topless|breasts?|cleavage|erotic\w*|kink\w*|lingerie|boudoir|genital\w*)\b", re.I)
problems = []


def check(ok, what):
    if not ok:
        problems.append(what)
        print("FAIL: " + what)


cfg = config.load()
check(cfg["content"]["rating"] == "family", "the saved rating is family-friendly")
check(config.validate(dict(cfg, content={"rating": "historical"}))[0]["content"]["rating"] == "family",
      "the adult rating cannot be switched back on")
check(media.family(cfg) and media.family({"content": {"rating": "historical"}}), "screens are always family-friendly")

with open(os.path.join(ROOT, "config", "media.json"), encoding="utf-8") as f:
    lib = json.load(f)
check(not [i["id"] for i in lib["items"] if i.get("nsfw")], "no NSFW pictures in the Media Library")

import threading  # noqa: E402
jobs = media.Jobs.__new__(media.Jobs)
jobs.lock, jobs.jobs, jobs.wake = threading.Lock(), [], threading.Event()
jobs._save_locked = lambda: None
check(jobs._push({"nsfw": "yes", "count": 1, "status": "waiting"})["status"] == "failed", "NSFW picture jobs are refused")
check(jobs._push({"nsfw": False, "count": 1, "status": "waiting"})["status"] == "waiting", "clean picture jobs still queue")
for cid in persona_prompts_v2.LOOKS:
    p = persona_prompts_v2.build(cid, "nude")
    check(not ADULT.search(p), "{}: the nude tier gives the dressed look".format(cid))
for cid, c in cast.CHARACTERS.items():
    check(not ADULT.search(c.get("portrait_prompt", "")), "{}: default portrait prompt is clean".format(cid))
for cid, c in cfg["characters"].items():
    check(not ADULT.search(c.get("portrait_prompt", "")), "{}: saved portrait prompt is clean".format(cid))

text = strings.resolve(cfg)
for k, v in taipan_text.OVERRIDES.items():
    check(k in strings.EN, "{}: overridden line still exists in Crimson Ledger's wording".format(k))
    check(text.get(k) == v, "{}: Taipan wording wins".format(k))

men = [cid for cid in cast.MEN if cid in cast.CHARACTERS]
women = [cid for cid in cast.CHARACTERS if cid not in cast.MEN]
check(len(men) >= 10 and len(women) >= 10, "the cast is a mix of men and women")
check(cfg["brand"]["title_a"] == "Taipan" and cfg["brand"]["title_b"] == "Trader", "the brand is Taipan Trader")

print("{} problem(s).".format(len(problems)) if problems else "Taipan Trader rules hold.")
sys.exit(1 if problems else 0)
