"""Brand casting (23 Nov 2026): Admin > Brand picks which cast member plays the moneylender and the pirate
queen. Whoever is cast brings her own name, title, portrait, pictures and voice to the role.
Run:  python tests/casting_test.py"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cast     # noqa: E402
import config   # noqa: E402
import media    # noqa: E402
import voice    # noqa: E402

# 1. Out of the box each role is played by its own character and nothing changes.
cfg, errors = config.validate({})
assert not errors, errors
assert cfg["brand"]["lender_cast"] == "lender" and cfg["brand"]["pirate_cast"] == "pirate"
assert cast.played_by(cfg, "lender") == "lender" and cast.display_name(cfg, "lender") == "Madam Wu Lian"
assert cast.public_cast(cfg)["lender"]["title"] == cfg["characters"]["lender"]["title"]

# A name typed for the moneylender before casting existed is kept while the role is still hers.
old, errors = config.validate({"brand": {"lender": "Madam Silver"}})
assert not errors and old["brand"]["lender"] == "Madam Silver" and cast.display_name(old, "lender") == "Madam Silver"

# 2. Cast the shipwright as the moneylender: the role takes her name, card and voice.
cfg, errors = config.validate({"brand": {"lender_cast": "shipwright"}})
assert not errors, errors
tang = cfg["characters"]["shipwright"]
assert cfg["brand"]["lender"] == tang["name"] == "Tang Wai-lin"          # {lender} in the wording follows
assert cast.played_by(cfg, "lender") == "shipwright"
assert cast.display_name(cfg, "lender") == "Tang Wai-lin" == cast.display_name(cfg, "shipwright")
pub = cast.public_cast(cfg)
assert pub["lender"] == pub["shipwright"], pub["lender"]
assert pub["pirate"]["name"] == "Admiral Li Yue"                          # the other role is untouched
assert cfg["characters"]["lender"]["name"] == "Madam Wu Lian"             # her card in Cast & Voices is kept

# The voice: a moneylender line is spoken with the shipwright's voice, still filed under the role.
plan = voice.Planner.__new__(voice.Planner)
plan.cfg = cfg
seen = []
real_params, real_register = voice._params, voice.register
voice._params = lambda text, ch, vcfg: seen.append(ch["voice_id"]) or "p"
voice.register = lambda params, cid, key: "x"
try:
    clip = plan._clip("The silver is yours.", "lender")
finally:
    voice._params, voice.register = real_params, real_register
assert clip and clip["c"] == "lender" and seen and set(seen) == {tang["voice_id"]}, (clip, seen)

# 3. Hand the role back: her own name returns.
back = dict(cfg, brand=dict(cfg["brand"], lender_cast="lender"))
back, errors = config.validate(back)
assert not errors and back["brand"]["lender"] == "Madam Wu Lian", back["brand"]

# 4. A straight swap of the two roles.
swap, errors = config.validate({"brand": {"lender_cast": "pirate", "pirate_cast": "lender"}})
assert not errors
assert (swap["brand"]["lender"], swap["brand"]["pirate"]) == ("Admiral Li Yue", "Madam Wu Lian"), swap["brand"]
assert cast.display_name(swap, "lender") == "Admiral Li Yue" and cast.display_name(swap, "pirate") == "Madam Wu Lian"

# 5. Someone who is not in the cast falls back to the role's own character.
bad, errors = config.validate({"brand": {"lender_cast": "nobody"}})
assert not errors and bad["brand"]["lender_cast"] == "lender"

# 6. Pictures: the role shows the cast member's library pictures, not the old ones.
tmp = tempfile.mkdtemp()
media.WEB = os.path.join(tmp, "web")
media.MEDIA_DIR = os.path.join(media.WEB, "media")
media.TRASH_DIR = os.path.join(media.MEDIA_DIR, "_trash")
media.UPLOAD_DIR = os.path.join(media.WEB, "uploads")
media.LIB_FILE = os.path.join(tmp, "config", "media.json")
os.makedirs(media.UPLOAD_DIR)
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000020000000308020000000000000000")
try:
    plain = config.defaults()
    media.load(plain)
    wu = media.add_bytes(PNG, ".png", "persona", "lender", ["portrait"], (), False, "upload")
    tw = media.add_bytes(PNG, ".png", "persona", "shipwright", ["portrait"], (), False, "upload")
    ids = lambda c, who: [i["id"] for i in media.public(c)["items"]["persona"].get(who, [])]
    assert ids(plain, "lender") == [wu["id"]]
    assert ids(cfg, "lender") == [tw["id"]] == ids(cfg, "shipwright")
    assert ids(plain, "lender") == [wu["id"]], "the two castings do not share a cached answer"
    li = dict(cfg, brand=dict(cfg["brand"], lender_cast="pirate"))     # she has no pictures in this library
    assert ids(li, "lender") == [], "never the old moneylender's face under another woman's name"
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# 7. The Brand page offers both roles as dropdowns of the cast.
brand = next(s for s in config.SECTIONS if s["id"] == "brand")
fields = {f["path"]: f for g in brand["groups"] for f in g["fields"]}
for role in cast.ROLES:
    f = fields["brand.{}_cast".format(role)]
    assert f["type"] == "select" and f["options_from"] == "characters" and f["role"] == role
assert fields["brand.bank"]["pick"] == "bank" and fields["brand.winner"]["pick"] == "winner"
print("casting ok")
