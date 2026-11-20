"""Cargo pictures follow the content rating like the cargo's name does (19 Nov 2026).

While family-friendly is on, a cargo with a family-friendly name (Opium -> Fireworks, Arms -> Ironware)
shows only its "family" pictures; its own pictures are hidden. With NSFW on, the family pictures are hidden.
Runs in a scratch copy of the folders.   Run:  python tests/cargo_family_test.py"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
import media   # noqa: E402

tmp = tempfile.mkdtemp()
media.WEB = os.path.join(tmp, "web")
media.MEDIA_DIR = os.path.join(media.WEB, "media")
media.TRASH_DIR = os.path.join(media.MEDIA_DIR, "_trash")
media.UPLOAD_DIR = os.path.join(media.WEB, "uploads")
media.LIB_FILE = os.path.join(tmp, "config", "media.json")
os.makedirs(media.UPLOAD_DIR)
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000020000000308020000000000000000")
cfg = config.defaults()
cfg["goods"]["opium"]["family_name"] = "Fireworks"
cfg["goods"]["porcelain"].update(name="Marijuana", family_name="Porcelain")
cfg["goods"]["arms"]["family_name"] = "Ironware"
cfg["goods"]["tea"]["family_name"] = ""
try:
    media.load(cfg)
    # Porcelain played as "Marijuana": NSFW pictures of the NSFW cargo, clean pictures of porcelain.
    weed = media.add_bytes(PNG, ".png", "cargo", "porcelain", ["icon"], (), True, "upload")
    vase = media.add_bytes(PNG, ".png", "cargo", "porcelain", ["icon"], (), False, "upload")
    # Opium: its own (clean-tagged) chest plus a Fireworks stand-in with the family role.
    opium = media.add_bytes(PNG, ".png", "cargo", "opium", ["icon"], (), False, "upload")
    fireworks = media.add_bytes(PNG, ".png", "cargo", "opium", ["family"], (), False, "upload")
    tea = media.add_bytes(PNG, ".png", "cargo", "tea", ["icon"], (), False, "upload")
    ids = lambda pub, k: {i["id"] for i in pub["items"].get("cargo", {}).get(k, [])}

    cfg["content"]["rating"] = "historical"
    pub = media.public(cfg)
    assert ids(pub, "porcelain") == {weed["id"]}, "NSFW on: only the NSFW pictures, never the vase"
    assert ids(pub, "opium") == {opium["id"]}, "NSFW on: the family picture stays hidden"
    assert ids(pub, "tea") == {tea["id"]}
    assert not media.is_blocked(weed["url"], cfg)

    cfg["content"]["rating"] = "family"
    pub = media.public(cfg)
    assert ids(pub, "porcelain") == {vase["id"]}, "family: only the clean pictures"
    assert ids(pub, "opium") == {fireworks["id"]}, "family: the family picture wins over the clean chest"
    assert pub["items"]["cargo"]["opium"][0]["r"] == [], "a family picture fits every cargo role"
    assert ids(pub, "tea") == {tea["id"]}
    assert media.is_blocked(weed["url"], cfg) and media.is_blocked(opium["url"], cfg)
    g = media.safe_graphics({"goods": {"porcelain": weed["url"], "opium": opium["url"]}}, cfg)
    assert g["goods"] == {"porcelain": vase["url"], "opium": fireworks["url"]}, g

    # Scan: a picture dropped in web/media/cargo/arms/family/ is a family picture.
    d = os.path.join(media.MEDIA_DIR, "cargo", "arms", "family")
    os.makedirs(d)
    with open(os.path.join(d, "ironware.png"), "wb") as f:
        f.write(PNG)
    media.scan(cfg)
    assert len(ids(media.public(cfg), "arms")) == 1
    print("OK: cargo family picture checks passed")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
