"""Build the NSFW and clean twins of a persona portrait from one cast prompt (ported from Atomic Ledger, 24 Nov 2026).

This is the wording that used to live inside tools/queue_persona_pairs.py, moved here so the queue tool, the
Admin recipes (recipe_scenes.py) and tests all share one copy. The wording is Crimson's own and is unchanged:
  nsfw_prompt(base, mood)   her description + the mood + openly nude, then her style tail
  clean_prompt(base, mood)  her description made decent + the mood + the modest 1860 style
The style tail of a cast prompt starts at ", romanticized".
"""
import re

NUDE = ("completely naked, her clothes fallen away, breasts and body shown openly, only her jewellery and the "
        "props of her trade left on her")
CLEAN_STYLE = ("fully and modestly clothed, high neckline, no nudity, no cleavage, romanticized cinematic historical "
               "realism, China Seas 1860, humid salt haze, natural skin, weathered maritime materials, lacquer black, "
               "oxblood silk, antique brass, imperial jade, waist-up 3:4 portrait, hands visible, original face and "
               "garment design, no text")
# Undressed wording in the profile prompts, made decent for the clean version.
DECENT = [
    (r"worn loose off both shoulders with the obi half undone", "neatly worn and tied"),
    (r"off-shoulder ", ""), (r"slipping from one shoulder", "worn neatly"), (r"draped over one bare shoulder", "draped neatly"),
    (r"half-laced ", ""), (r"loosened ", ""), (r"with a thigh-high slit unbuttoned at the collar", "buttoned to the collar"),
    (r"open over a black lace corset", "buttoned over a black lace blouse"),
    (r"open over a black silk corset, high collar undone", "with the high collar buttoned"),
    (r"with a laced leather corset over it", ""), (r"plunging ", "high-necked "), (r"with a deep neckline", ""),
    (r"\bundone\b", "fastened"), (r"across her skin", "across the room"), (r"bedroom gaze", "gaze"),
    (r"sensual private-release erotic glamour,? ?", ""),
    # The bookkeeper (Accounting Ledger, 20 Nov 2026).
    (r"black silk blouse unbuttoned to the waist and slipping off one shoulder over an oxblood lace corset",
     "black silk blouse buttoned to the collar under an oxblood waistcoat"),
    (r"sheer black stockings and one knee drawn up, ", ""), (r"reclining in", "seated in"),
    (r"a smouldering heavy-lidded gaze", "a knowing gaze"), (r" deliciously", ""),
]


def split(prompt):
    """(her description, the style tail). The style tail starts at ', romanticized'."""
    at = prompt.find(", romanticized")
    return (prompt[:at], prompt[at + 2:]) if at > 0 else (prompt, "")


def nsfw_prompt(base, mood=""):
    desc, tail = split(base)
    return "{}, {}, {}{}".format(desc, mood, NUDE, ", " + tail if tail else "")


def clean_prompt(base, mood=""):
    desc, _tail = split(base)
    for pat, rep in DECENT:
        desc = re.sub(pat, rep, desc)
    desc = re.sub(r"\s+,", ",", re.sub(r"  +", " ", desc))
    return "{}, {}, {}".format(desc, mood, CLEAN_STYLE)


def pair(base, mood=""):
    return {"nsfw": nsfw_prompt(base, mood), "clean": clean_prompt(base, mood)}
