"""Checks the Dialogue Banks catalogue (banks.py): banks are found from the numbered lines, each belongs to the
right persona or story and surface, the audit flags the right things, Language & Text overrides show, and the
catalogue never changes the wording.
Run from the game folder: python tests/banks_test.py"""
import copy
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import banks         # noqa: E402
import cast          # noqa: E402
import config        # noqa: E402
import manual_text   # noqa: E402
import strings       # noqa: E402

CFG = config.DEFAULTS


def by_id(view):
    return {b["id"]: b for b in view["banks"]}


def test_numbered_banks_are_contiguous():
    view = banks.view(CFG)
    assert view["ok"] and len(view["banks"]) > 300
    for b in view["banks"]:
        if b["numbered"]:
            assert [x["n"] for x in b["lines"]] == list(range(b["size"])), b["id"]
        else:
            assert b["size"] == 1 and b["kind"] == "spoken", b["id"]


def test_every_bank_has_an_owner_and_surface():
    view = banks.view(CFG)
    owners = {o["id"] for o in view["owners"]}
    for b in view["banks"]:
        assert b["owner"] in owners and b["owner_name"], b["id"]
        assert b["surface"] in dict(banks.SURFACES), b["id"]
    assert view["summary"]["lines"] == sum(o["lines"] for o in view["owners"])
    assert view["summary"]["banks"] == sum(o["banks"] for o in view["owners"])


def test_surfaces_and_speakers():
    b = by_id(banks.view(CFG))
    assert b["m.borrowed.easy"]["owner"] == "lender" and b["m.borrowed.easy"]["surface"] == "game"
    assert b["gm.month_open"]["owner"] == "gamemaster" and b["gm.month_open"]["surface"] == "table"
    for key, who in manual_text.SPEAKER.items():
        if key.endswith(".open.0"):
            bank = b[key.rsplit(".", 1)[0]]
            assert bank["owner"] == who and bank["surface"] == "manual" and bank["kind"] == "spoken", key
    assert b["man.money.how"]["kind"] == "written"
    speech = [x for x in b.values() if x["id"].startswith("dash.whisper.") and x["id"].endswith(".speech")]
    assert speech and all(x["owner"] == banks.DASH_ANY and x["surface"] == "dashboard" for x in speech)


def test_officers_and_wardens_group_together():
    view = banks.view(CFG)
    ids = {o["id"] for o in view["owners"]}
    assert "officers" in ids and "wardens" in ids
    assert all(b["owner"] == "officers" for b in view["banks"] if "officer_" in b["id"] and b["id"].startswith("l.customs_welcome."))


def test_audit_flags():
    spicy = {"a.0": "Hello {name}", "a.1": "Hello {name}", "a.2": "Pay {amount}", "a.3": "x" * 300, "a.4": ""}
    clean = {"a.0": "Hi {name}", "a.2": "Pay now", "a.3": "y", "a.4": ""}
    seen = set()
    rows = {k: banks._line(k, i, spicy, clean, True, seen) for i, k in enumerate(spicy)}
    assert rows["a.0"]["flags"] == []
    assert rows["a.1"]["flags"] == ["no_clean", "dup"]
    assert rows["a.2"]["flags"] == ["fields"]
    assert "long" in rows["a.3"]["flags"]
    assert "empty" in rows["a.4"]["flags"]
    assert not banks._line("a.0", 0, {"a.0": "Same"}, {"a.0": "Same"}, True, set())["flags"]
    assert banks._line("a.0", 0, {"a.0": "Same"}, {"a.0": "Same"}, True, set())["same"]


def test_language_overrides_show():
    key = "m.borrowed.easy.0"
    lang = {"strings": {key: "Edited spicy"}, "family": {key: "Edited clean"}}
    line = by_id(banks.view(CFG, lang))["m.borrowed.easy"]["lines"][0]
    assert line["spicy"] == "Edited spicy" and line["clean"] == "Edited clean" and line["twin"]


def test_view_is_read_only_and_json():
    before = (copy.deepcopy(strings.EN), copy.deepcopy(strings.FAMILY))
    view = banks.view(CFG)
    assert json.loads(json.dumps(view))["ok"]
    assert (strings.EN, strings.FAMILY) == before


# --------------------------------------------------------------------------------------- slice 2: the overlay --
class Overlay:
    """Runs a test against a throw-away overlay file and puts the shipped wording back afterwards."""
    def __enter__(self):
        self.dir = tempfile.TemporaryDirectory()
        self.saved = (banks.OVERLAY_FILE, banks.BACKUP_DIR)
        banks.OVERLAY_FILE = os.path.join(self.dir.name, "overlay.json")
        banks.BACKUP_DIR = os.path.join(self.dir.name, "backups")
        banks.apply(force=True)
        self.before = (copy.deepcopy(strings.EN), copy.deepcopy(strings.FAMILY), copy.deepcopy(cast.SAY))
        return self

    def __exit__(self, *a):
        banks.OVERLAY_FILE, banks.BACKUP_DIR = self.saved
        banks.apply(force=True)
        self.dir.cleanup()


def engine_bank(stem):
    """engine._bank: the numbered lines counted until one is missing, skipping blanks."""
    n = 0
    while "{}.{}".format(stem, n) in strings.EN:
        n += 1
    return [i for i in range(n) if strings.EN["{}.{}".format(stem, i)].strip()]


GOOD = {"spicy": "Borrowed {amount} at {rate}% a month. Spend it well, darling.",
        "clean": "Borrowed {amount} at {rate}% a month. Spend it well, Captain.",
        "say": "Spend it well, darling.", "say_clean": "Spend it well, Captain."}


def test_edit_applies_and_resets():
    key = "m.borrowed.easy.0"
    with Overlay() as o:
        shipped = (strings.EN[key], strings.FAMILY[key])
        r = banks.handle("edit", dict(GOOD, key=key), CFG)
        assert r["ok"], r
        assert strings.EN[key] == GOOD["spicy"] and strings.FAMILY[key] == GOOD["clean"]
        assert cast.SAY[key] == GOOD["say"] and cast.SAY_FAMILY[key] == GOOD["say_clean"]
        line = by_id(banks.view(CFG))["m.borrowed.easy"]["lines"][0]
        assert line["edited"] and line["shipped"]["spicy"] == shipped[0]
        assert banks.handle("reset", {"key": key}, CFG)["ok"]
        assert (strings.EN[key], strings.FAMILY[key]) == shipped
    assert strings.EN[key] == shipped[0]


def test_edit_back_to_shipped_clears_the_entry():
    key = "m.borrowed.easy.0"
    with Overlay():
        banks.handle("edit", dict(GOOD, key=key), CFG)
        shipped = banks._snapshot()
        r = banks.handle("edit", {"key": key, "spicy": shipped["en"][key], "clean": shipped["family"][key]}, CFG)
        assert r["ok"] and key not in banks.load_overlay()["lines"], r


def test_add_takes_the_next_number_and_is_read_by_the_bank_owner():
    with Overlay():
        n = len(engine_bank("m.borrowed.easy"))
        r = banks.handle("add", dict(GOOD, bank="m.borrowed.easy"), CFG)
        assert r["ok"] and r["key"] == "m.borrowed.easy.%d" % n, r
        key = r["key"]
        assert len(engine_bank("m.borrowed.easy")) == n + 1
        assert strings.EN[key] == GOOD["spicy"] and strings.FAMILY[key] == GOOD["clean"]
        assert cast.speaker_for(CFG, key) == "lender"
        assert cast.spoken_template(CFG, strings.EN, key) == GOOD["say"]
        assert by_id(banks.view(CFG))["m.borrowed.easy"]["lines"][-1]["added"]


def test_remove_blanks_never_renumbers_and_restore_brings_it_back():
    key = "m.borrowed.easy.1"
    with Overlay():
        n = len(engine_bank("m.borrowed.easy"))
        before = strings.EN[key]
        assert banks.handle("retire", {"key": key}, CFG)["ok"]
        assert strings.EN[key] == "" and key in strings.EN
        assert engine_bank("m.borrowed.easy") == [i for i in range(n) if i != 1]
        assert banks.handle("add", dict(GOOD, bank="m.borrowed.easy"), CFG)["key"].endswith(".%d" % n)
        assert banks.handle("restore", {"key": key}, CFG)["ok"]
        assert strings.EN[key] == before


def test_last_line_and_single_lines_cannot_be_removed():
    with Overlay():
        for i in (0, 1):
            assert banks.handle("retire", {"key": "m.borrowed.easy.%d" % i}, CFG)["ok"]
        r = banks.handle("retire", {"key": "m.borrowed.easy.2"}, CFG)
        assert not r["ok"] and "at least one" in r["error"]
        r = banks.handle("retire", {"key": "dash.whisper.ban.speech"}, CFG)
        assert not r["ok"]


def test_validation():
    key = "m.borrowed.easy.0"
    with Overlay():
        def refused(**kw):
            r = banks.handle("edit", dict(dict(GOOD, key=key), **kw), CFG)
            assert not r["ok"], kw
            return r["error"]
        assert "{secret}" in refused(spicy="Hi {secret}", clean="Hi {secret}")
        assert "same {names}" in refused(clean="Spend it well.")
        assert "stray" in refused(spicy="Hi {amount", clean="Hi {amount")
        assert "spoken spicy" in refused(say="")
        assert "figures" in refused(say="Spend {amount} well.")
        assert "empty" in refused(spicy="  ")
        assert "longer" in refused(spicy="x" * 700)
        r = banks.handle("add", dict(GOOD, bank="m.borrowed.easy", clean=""), CFG)
        assert not r["ok"] and "clean" in r["error"]
        assert not banks.handle("add", dict(GOOD, bank="nope.nope"), CFG)["ok"]
        assert not banks.handle("edit", dict(GOOD, key="nope.0"), CFG)["ok"]
        assert banks.load_overlay()["lines"] == {}


def test_every_surface_can_take_new_lines_except_unplayed_banks():
    b = by_id(banks.view(CFG))
    for bid in ("m.borrowed.easy", "man.money.open", "gm.month_open", "gm.all_sealed", "dash.whisper.boom.speech"):
        assert b[bid]["addable"], bid
    assert not b["gm.your_turn"]["addable"] and b["gm.your_turn"]["fixed_note"]


def test_manual_uses_a_line_added_and_skips_a_retired_one():
    with Overlay():
        before = manual_text.bank_keys("money", "open")
        assert len(before) == 3
        r = banks.handle("add", {"bank": "man.money.open", "spicy": "Another word on money, Captain.",
                                 "clean": "Another word on money, Captain."}, CFG)
        assert r["ok"], r
        assert r["key"] in manual_text.bank_keys("money", "open") and manual_text.SPEAKER[r["key"]]
        chapter = [c for c in manual_text.chapters() if c["id"] == "money"][0]
        assert chapter["bank"]["open"] == manual_text.bank_keys("money", "open") and len(chapter["bank"]["open"]) == 4
        banks.handle("retire", {"key": before[0]}, CFG)
        assert before[0] not in manual_text.bank_keys("money", "open")


def test_table_draws_the_whole_bank_without_repeats():
    import random
    with Overlay():
        r = banks.handle("add", {"bank": "gm.month_open", "spicy": "New month, darlings. Mind the tide.",
                                 "clean": "New month, Captains. Mind the tide."}, CFG)
        assert r["ok"], r
        banks._DECKS.clear()
        keys = banks.live_keys("gm.month_open")
        assert len(keys) == 4
        rng = random.Random(1)
        seen = [banks.pick_stable("gm.month_open", ("g", t), rng=rng) for t in range(4)]
        assert sorted(seen) == sorted(keys)                      # all heard before any repeats
        assert banks.pick_stable("gm.month_open", ("g", 2)) == seen[2]      # same turn, same line (polling)
        banks.handle("retire", {"key": seen[0]}, CFG)
        later = {banks.pick_stable("gm.month_open", ("g", t)) for t in range(10, 20)}
        assert seen[0] not in later


def test_dashboard_speech_is_a_bank_of_variants():
    import dashboard_brief
    for kind in ("weather", "fleet", "ban", "expiring", "boom", "spread"):
        stem = "dash.whisper.{}.speech".format(kind)
        assert len(banks.live_keys(stem)) >= 3, kind
        for k in banks.live_keys(stem):
            assert strings.FAMILY.get(k), k
            assert not set(banks._fields(strings.EN[k])) & banks.AMOUNTS, k
            assert set(banks._fields(strings.EN[k])) == set(banks._fields(strings.FAMILY[k])), k
    with Overlay():
        r = banks.handle("add", {"bank": "dash.whisper.boom.speech", "spicy": "Hot {good} at {port}, Captain.",
                                 "clean": "Busy {good} at {port}, Captain."}, CFG)
        assert r["ok"], r
        banks._DECKS.clear()
        text = strings.resolve(CFG)
        used = {banks.pick_stable("dash.whisper.boom.speech", ("obs", i), text) for i in range(4)}
        assert r["key"] in used and len(used) == 4


def test_spoken_setting_and_cap():
    with Overlay():
        saved = banks.SPEND_FILE
        banks.SPEND_FILE = os.path.join(os.path.dirname(banks.OVERLAY_FILE), "spend.json")
        banks._SPENT = None
        try:
            b = by_id(banks.view(CFG))
            assert b["m.borrowed.easy"]["spoken"] == "auto" and not b["m.borrowed.easy"]["spoken_set"]
            assert [o["id"] for o in b["man.money.open"]["spoken_options"]] == ["request", "off"]
            assert b["strings_written"]["spoken_options"] == [] if "strings_written" in b else True
            r = banks.handle("spoken", {"bank": "m.borrowed.easy", "spoken": "off", "cap": 2}, CFG)
            assert r["ok"], r
            assert not banks.may_speak("m.borrowed.easy.1") and banks.may_speak("m.borrowed.hard.0")
            b = by_id(banks.view(CFG))["m.borrowed.easy"]
            assert b["spoken"] == "off" and b["spoken_set"] and b["cap"] == 2
            assert banks.handle("spoken", {"bank": "man.money.open", "spoken": "auto"}, CFG)["ok"] is False
            assert banks.handle("spoken", {"bank": "m.borrowed.easy", "spoken": "auto", "cap": 9999}, CFG)["ok"] is False
            assert banks.handle("spoken", {"bank": "nope.nope", "spoken": "off"}, CFG)["ok"] is False
            banks.handle("spoken", {"bank": "m.borrowed.easy", "spoken": "auto", "cap": 2}, CFG)
            assert banks.may_speak("m.borrowed.easy.1")
            assert banks.charge("m.borrowed.easy.0") and banks.charge("m.borrowed.easy.2")
            assert not banks.charge("m.borrowed.easy.1")          # the third new recording is over the cap
            assert banks.charge("m.borrowed.hard.0")              # another bank, no cap
            banks.handle("spoken", {"bank": "m.borrowed.easy", "spoken": "auto", "cap": 0}, CFG)
            assert banks.charge("m.borrowed.easy.1")              # cap lifted
            assert banks.load_overlay()["voice"] == {}            # defaults leave no trace
            banks.handle("edit", dict(GOOD, key="m.borrowed.easy.0"), CFG)
            banks.handle("spoken", {"bank": "m.borrowed.easy", "spoken": "off"}, CFG)
            assert banks.load_overlay()["lines"] and banks.load_overlay()["voice"]    # lines and voice live together
        finally:
            banks.SPEND_FILE, banks._SPENT = saved, None


def test_voice_planner_obeys_off_and_cap():
    import voice
    cfg = copy.deepcopy(CFG)
    cfg["voice"]["enabled"] = True
    cid = next(c for c in cfg["characters"])
    cfg["characters"][cid]["voice_id"] = "test-voice"
    plan = voice.Planner()
    plan.configure(cfg, strings.resolve(cfg))
    with Overlay():
        assert plan._clip("Spend it well, Captain.", cid, "m.borrowed.easy.0")
        banks.handle("spoken", {"bank": "m.borrowed.easy", "spoken": "off"}, CFG)
        assert plan._clip("Spend it well, Captain.", cid, "m.borrowed.easy.0") is None
        assert plan._clip("Spend it well, Captain.", cid, "m.borrowed.hard.0")     # other banks unaffected
        assert plan._clip("Spend it well, Captain.", cid)                          # no key, never gated


def test_render_stops_new_recordings_at_the_cap_but_replays_cached_free():
    import voice
    d = tempfile.TemporaryDirectory()
    saved = (voice.CACHE_DIR, voice.synthesize, banks.SPEND_FILE)
    paid = []
    voice.CACHE_DIR = d.name
    voice.synthesize = lambda *a, **k: (paid.append(1) or b"mp3")
    banks.SPEND_FILE = os.path.join(d.name, "spend.json")
    banks._SPENT = None
    try:
        with Overlay():
            banks.handle("spoken", {"bank": "m.borrowed.easy", "spoken": "auto", "cap": 1}, CFG)
            ps = [{"text": "line %d" % i, "voice_id": "v", "model_id": "m", "rate": 1.0, "temperature": 1.0, "delivery": ""} for i in range(3)]
            ids = [voice.register(p, "x", "m.borrowed.easy.%d" % i) for i, p in enumerate(ps)]
            assert voice.render(ps[0]) == b"mp3"
            try:
                voice.render(ps[1])
                assert False, "second new recording should be refused"
            except voice.VoiceError:
                pass
            assert voice.render(ps[0]) == b"mp3" and len(paid) == 1       # cached: free, no new charge
    finally:
        voice.CACHE_DIR, voice.synthesize, banks.SPEND_FILE = saved
        banks._SPENT = None
        d.cleanup()


class GenFiles:
    """Throw-away generator files, and a stand-in for the writer's HTTP calls."""
    def __init__(self, reply):
        self.reply = reply

    def __enter__(self):
        import banks_gen
        self.g = banks_gen
        self.dir = tempfile.TemporaryDirectory()
        self.saved = (banks_gen.GEN_FILE, banks_gen.KEY_FILE, banks_gen.QUEUE_FILE, banks_gen._post_json, banks_gen._get_json)
        banks_gen.GEN_FILE = os.path.join(self.dir.name, "generator.json")
        banks_gen.KEY_FILE = os.path.join(self.dir.name, "key.json")
        banks_gen.QUEUE_FILE = os.path.join(self.dir.name, "queue.json")
        self.calls = []

        def post(url, body, headers=None, timeout=300):
            self.calls.append((url, body, headers))
            if "anthropic" in url:
                return {"content": [{"type": "text", "text": self.reply}]}
            return {"choices": [{"message": {"content": self.reply}}]}
        banks_gen._post_json = post
        banks_gen._get_json = lambda url, timeout=6: {"data": [{"id": "model-b"}, {"id": "model-a"}]}
        return self

    def __exit__(self, *a):
        g = self.g
        g.GEN_FILE, g.KEY_FILE, g.QUEUE_FILE, g._post_json, g._get_json = self.saved
        self.dir.cleanup()


REPLY = """Sure! Here you go:
```json
[{"spicy": "Madam Wu counts the interest twice, darling. Once for the money, once for the pleasure.", "clean": "Madam Wu counts the interest twice, Captain. Once for the money, once for the fun."},
 {"spicy": "A fresh loan {bogus}, darling.", "clean": "A fresh loan, Captain."},
 {"spicy": "Same joke again, darling.", "clean": ""},
 {"spicy": "Borrow boldly, sweetheart. Madam Wu likes a customer with appetite.", "clean": "Borrow boldly, Captain. Madam Wu likes a customer with ambition."}]
```"""


def test_generator_queue_and_approve():
    with Overlay(), GenFiles(REPLY) as gf:
        g = gf.g
        r = banks.handle("gen_settings", {"provider": "local", "base_url": "http://x:1/v1", "model": "model-a"}, CFG)
        assert r["ok"], r
        assert banks.handle("gen_settings", {"base_url": "ftp://x"}, CFG)["ok"] is False
        assert banks.handle("gen_settings", {"key": "not a key"}, CFG)["ok"] is False
        assert banks.handle("gen_models", {}, CFG)["models"] == ["model-a", "model-b"]
        r = banks.handle("gen_run", {"bank": "m.borrowed.easy", "count": 4, "notes": "more pirates"}, CFG)
        assert r["ok"] and r["added"] == 2 and r["thrown"] == 2, r      # the {bogus} name and the missing clean twin fail
        url, body, _ = gf.calls[0]
        assert url == "http://x:1/v1/chat/completions" and body["model"] == "model-a"
        assert "Madam Wu" in body["messages"][1]["content"] and "more pirates" in body["messages"][1]["content"]
        assert "HOUSE STYLE" in body["messages"][0]["content"]
        q = banks.view(CFG)["generator"]["queue"]
        assert len(q) == 2 and not strings.EN.get("m.borrowed.easy.3")           # nothing live until approved
        before = banks.live_keys("m.borrowed.easy")
        assert banks.handle("gen_edit", {"id": q[0]["id"], "spicy": q[0]["spicy"] + " Truly."}, CFG)["ok"]
        r = banks.handle("gen_approve", {"id": q[0]["id"]}, CFG)
        assert r["ok"] and r["key"] == "m.borrowed.easy.3", r
        assert strings.EN[r["key"]].endswith("Truly.") and len(banks.live_keys("m.borrowed.easy")) == len(before) + 1
        assert len(banks.view(CFG)["generator"]["queue"]) == 1
        assert banks.handle("gen_discard", {"id": q[1]["id"]}, CFG)["ok"]
        assert banks.view(CFG)["generator"]["queue"] == []
        assert banks.handle("gen_approve", {"id": "g999"}, CFG)["ok"] is False
        again = banks.handle("gen_run", {"bank": "m.borrowed.easy", "count": 4}, CFG)
        assert again["ok"] and again["added"] == 2                    # the discarded one may come back; the approved wording is not
        again = banks.handle("gen_run", {"bank": "m.borrowed.easy", "count": 4}, CFG)
        assert not again["ok"]                                        # now both are already waiting in the queue: all duplicates


def test_generator_api_provider_and_failures():
    with Overlay(), GenFiles(REPLY) as gf:
        r = banks.handle("gen_run", {"bank": "m.borrowed.easy", "provider": "api"}, CFG)
        assert not r["ok"] and "API key" in r["error"]
        assert banks.handle("gen_settings", {"key": "sk-ant-" + "a" * 30}, CFG)["ok"]
        st = banks.view(CFG)["generator"]
        assert st["key_set"] and "sk-ant" not in json.dumps(st)                 # the key never goes back to the page
        r = banks.handle("gen_run", {"bank": "m.borrowed.easy", "provider": "api", "count": 2}, CFG)
        assert r["ok"], r
        url, body, headers = gf.calls[-1]
        assert url.startswith("https://api.anthropic.com") and headers["x-api-key"].startswith("sk-ant")
        assert not banks.handle("gen_run", {"bank": "m.borrowed.easy", "provider": "local"}, CFG)["ok"]    # no local model chosen
        gf.reply = "I cannot help with that."
        banks.handle("gen_settings", {"model": "model-a"}, CFG)
        assert not banks.handle("gen_run", {"bank": "m.borrowed.easy", "provider": "local"}, CFG)["ok"]
        assert not banks.handle("gen_run", {"bank": "gm.your_turn"}, CFG)["ok"]      # a bank no screen plays
        assert not banks.handle("gen_run", {"bank": "nope"}, CFG)["ok"]
        os.environ.pop("ANTHROPIC_API_KEY", None)
        assert banks.handle("gen_settings", {"key": ""}, CFG)["ok"] and not banks.view(CFG)["generator"]["key_set"]


def test_admin_http_route_reaches_the_banks():
    """The page POSTs to /api/admin/banks/<op>; the server must hand that to banks.handle (it once fell through to 404)."""
    import threading
    import types
    import server
    sent = []
    req = object.__new__(server.Handler)
    req.headers = {"X-SeaTrader": "admin"}
    req._admin_ok = lambda: True
    req._via = lambda: {}
    req._send = lambda code, body, *a, **k: sent.append((code, body))
    saved = (getattr(server, "HUB", None), server.journal.log)
    server.HUB = types.SimpleNamespace(cond=threading.RLock(), reload_settings=lambda: None)
    server.journal.log = lambda *a, **k: None
    try:
        with Overlay(), GenFiles("[]"):
            for what, body in (("banks/gen_settings", {"provider": "local", "model": "m"}),
                               ("banks/spoken", {"bank": "m.borrowed.easy", "spoken": "off"}),
                               ("banks/edit", dict(GOOD, key="m.borrowed.easy.0")),
                               ("banks/gen_models", {})):
                req._body = lambda *a, body=body, **k: body
                sent.clear()
                req._admin_post(what, {})
                code, res = sent[-1]
                assert code == 200 and "ok" in res, (what, code, res)
                assert res.get("error") != "Not found", what
    finally:
        server.HUB, server.journal.log = saved


def test_overlay_survives_reload_and_leaves_no_trace_when_removed():
    key = "m.borrowed.easy.0"
    with Overlay() as o:
        banks.handle("edit", dict(GOOD, key=key), CFG)
        banks.handle("add", dict(GOOD, bank="m.borrowed.easy"), CFG)
        banks.apply(force=True)                  # a restart: the file is read again
        assert strings.EN[key] == GOOD["spicy"]
        os.remove(banks.OVERLAY_FILE)
        banks.apply()
        assert (strings.EN, strings.FAMILY, cast.SAY) == o.before
        assert "m.borrowed.easy.3" not in strings.EN and "m.borrowed.easy.3" not in cast.LINE_DEFAULTS


def test_backups_are_kept():
    with Overlay():
        banks.handle("edit", dict(GOOD, key="m.borrowed.easy.0"), CFG)
        banks.handle("edit", dict(GOOD, key="m.borrowed.easy.1"), CFG)
        assert os.path.isdir(banks.BACKUP_DIR) and os.listdir(banks.BACKUP_DIR)


def test_resolve_carries_the_overlay_to_the_game():
    key = "m.borrowed.easy.0"
    with Overlay():
        banks.handle("edit", dict(GOOD, key=key), CFG)
        text = strings.resolve(CFG)
        assert text[key] == GOOD["spicy"]
        fam = copy.deepcopy(CFG)
        fam["content"]["rating"] = "family"
        assert strings.resolve(fam)[key] == GOOD["clean"]


def test_stale_spoken_version_is_refused():
    key = "m.gift.warm.0"
    snap = banks._snapshot()
    stock = snap["say"].get(key)
    if not stock:
        key = next(k for k in snap["say"] if k in snap["en"] and not set(banks._fields(snap["en"][k])) & banks.AMOUNTS)
        stock = snap["say"][key]
    with Overlay():
        body = {"key": key, "spicy": snap["en"][key] + " Truly.", "clean": snap["family"].get(key, ""), "say": stock}
        r = banks.handle("edit", body, CFG)
        assert not r["ok"] and "still the old line" in r["error"], r


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("OK: dialogue bank checks passed")


if __name__ == "__main__":
    main()
