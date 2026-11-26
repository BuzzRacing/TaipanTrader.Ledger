"""Media library checks: filing, NSFW gating, rotation data, scan, remove. Runs in a scratch copy of the folders.
Run:  python tests/media_test.py"""
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
with open(os.path.join(media.UPLOAD_DIR, "portrait-bosun-abcdef12.png"), "wb") as f:
    f.write(PNG)
cfg = config.defaults()
cfg["characters"]["bosun"]["portrait"] = "/uploads/portrait-bosun-abcdef12.png"
cfg["characters"]["bosun"]["portrait_prompt"] = "Legacy portrait with nude glamour"
try:
    lib = media.load(cfg)
    first = lib["items"][0]
    assert first["kind"] == "persona" and first["subject"] == "bosun" and first["primary"], first
    assert first["nsfw"], "a portrait painted with the adult style starts NSFW"
    assert (first["width"], first["height"]) == (2, 3)
    safe = media.add_bytes(PNG, ".png", "persona", "bosun", ["speaking"], ["calm"], False, "upload")
    clip = media.add_bytes(b"\x00" * 64, ".mp4", "persona", "bosun", ["speaking"], (), False, "upload")
    assert clip["type"] == "video" and safe["url"].startswith("/media/persona/bosun/")
    cfg["content"]["rating"] = "historical"
    assert {i["id"] for i in media.public(cfg)["items"]["persona"]["bosun"]} == {safe["id"], clip["id"]}
    cfg["content"]["rating"] = "family"
    pub = media.public(cfg)["items"]["persona"]["bosun"]
    assert {i["id"] for i in pub} == {safe["id"], clip["id"]}, pub
    assert media.is_blocked(first["url"], cfg)
    assert media.safe_cast({"bosun": {"portrait": first["url"]}}, cfg)["bosun"]["portrait"] == safe["url"]
    media.update([safe["id"]], {"reviewed": True})
    assert media.identity_reference(safe["id"], "bosun", cfg) == media.path_for(safe["url"])
    for item_id, subject in [(safe["id"], "crier"), (first["id"], "bosun"), (clip["id"], "bosun")]:
        try:
            media.identity_reference(item_id, subject, cfg)
        except media.MediaError:
            pass
        else:
            raise AssertionError("Invalid identity reference was accepted")
    # Scan: a dropped file in an nsfw folder is tagged NSFW, roles come from the folder name.
    d = os.path.join(media.MEDIA_DIR, "persona", "crier", "speaking", "nsfw")
    os.makedirs(d)
    with open(os.path.join(d, "x.png"), "wb") as f:
        f.write(PNG)
    added, _missing = media.scan(cfg)
    it = [i for i in media.load(cfg)["items"] if i["subject"] == "crier"][0]
    assert added == 1 and it["nsfw"] and it["roles"] == ["speaking"], it
    # Editing, one primary per subject, remove to trash.
    # Personas have no primary: any of their pictures may be shown (the persona rule and the roles ticked on each),
    # so marking one changes nothing. Every other kind has exactly one primary per subject, the last one marked.
    media.update([safe["id"]], {"primary": True})
    assert not any(i["primary"] and i["id"] == safe["id"] for i in media.load(cfg)["items"])
    one = media.add_bytes(PNG, ".png", "cargo", "rice", [], [], False, "upload")
    two = media.add_bytes(PNG + b"\x00", ".png", "cargo", "rice", [], [], False, "upload")
    media.update([one["id"]], {"primary": True})
    media.update([two["id"]], {"primary": True})
    prim = [i for i in media.load(cfg)["items"] if i["kind"] == "cargo" and i["subject"] == "rice" and i["primary"]]
    assert [i["id"] for i in prim] == [two["id"]], prim
    media.update([safe["id"]], {}, add_tags=["Night Sky!"])
    assert "night sky" in [i for i in media.load(cfg)["items"] if i["id"] == safe["id"]][0]["tags"]
    media.remove([clip["id"]])
    assert not any(i["id"] == clip["id"] for i in media.load(cfg)["items"])
    assert os.listdir(media.TRASH_DIR)
    assert media.nsfw_from_prompt("nude glamour") and not media.nsfw_from_prompt("a harbour at dusk")
    print("OK: media library checks passed")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
