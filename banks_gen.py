"""Dialogue Banks generator: drafts new lines for a bank, held in an approval queue until you accept them.

Admin > Language & Text > Dialogue Banks (web/banks-admin.js). Decisions (Anthony, 22 Nov 2026):
  * the writer is a LOCAL LLM by default (the AI farm's OpenAI-compatible router, or any server that speaks the
    OpenAI chat API) or the Anthropic API, picked for each batch;
  * every draft is a spicy + clean pair written in the house voice (house_voice.HOUSE_STYLE) and checked by the
    same rules as a hand-written line (banks._validate); drafts that break them are thrown away;
  * nothing reaches the game until you approve it: approving one draft adds it as a new line (banks.handle
    "add"), live at once. You can edit a draft before approving, or discard it.

Files (config/banks/): generator.json (provider, local address and model, API model), anthropic_key.json (the key
saved from the Admin; ANTHROPIC_API_KEY in the environment applies when none is saved), queue.json (the drafts).

Ops (banks.handle sends these here, before it takes its own lock, because a batch can take minutes):
  gen_run {bank, count, provider, notes}   gen_edit {id, spicy, clean, say, say_clean}   gen_approve {id}
  gen_discard {id}   gen_settings {...}   gen_models {}   (gen_models lists the local server's models)
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request

import config

GEN_FILE = os.path.join(config.CONFIG_DIR, "banks", "generator.json")
KEY_FILE = os.path.join(config.CONFIG_DIR, "banks", "anthropic_key.json")
QUEUE_FILE = os.path.join(config.CONFIG_DIR, "banks", "queue.json")

OPS = ("gen_run", "gen_edit", "gen_approve", "gen_discard", "gen_settings", "gen_models")
DEFAULTS = {"provider": "local",
            "local": {"base_url": "http://192.168.1.214:11435/v1", "model": "", "timeout": 300},
            "api": {"model": "claude-sonnet-5-5"}}
MAX_BATCH = 12
MAX_QUEUE = 200
API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
EXAMPLES = 8

_LOCK = threading.RLock()


class GenError(ValueError):
    """Something the Admin should be told in plain words."""


# ------------------------------------------------------------------------------------------- the files --
def _read(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, type(default)) else default
    except (OSError, ValueError):
        return default


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def settings():
    got = _read(GEN_FILE, {})
    out = json.loads(json.dumps(DEFAULTS))
    if got.get("provider") in ("local", "api"):
        out["provider"] = got["provider"]
    for part in ("local", "api"):
        if isinstance(got.get(part), dict):
            out[part].update({k: v for k, v in got[part].items() if k in out[part]})
    return out


def api_key():
    """(key, where it came from). Empty when none is set."""
    key = str(_read(KEY_FILE, {}).get("key") or "").strip()
    if key:
        return key, "admin"
    key = str(os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    return (key, "env") if key else ("", "")


def _queue():
    q = _read(QUEUE_FILE, {})
    items = q.get("items") if isinstance(q.get("items"), list) else []
    return {"seq": int(q.get("seq") or 0), "items": [x for x in items if isinstance(x, dict)]}


def state():
    """What the Admin page needs: the settings (never the key itself), and the drafts waiting."""
    s = settings()
    key, where = api_key()
    return {"settings": s, "key_set": bool(key), "key_from": where, "queue": _queue()["items"],
            "limits": {"batch": MAX_BATCH}}


# --------------------------------------------------------------------------------------------- prompts --
def _persona(cfg, who, owner_name):
    ch = (cfg.get("characters") or {}).get(who) or {}
    if not ch:
        return "{}: a character in the game. Write in the same sly, funny house voice as the examples.".format(owner_name or who or "The speaker")
    bits = ["{} ({})".format(ch.get("name", owner_name), ch.get("title", "")).replace(" ()", "")]
    for label, field in (("Age", "age"), ("From", "origin"), ("Manner", "delivery"), ("Catchphrase", "catchphrase"),
                         ("Bio", "bio"), ("Quirk", "quirk"), ("Vice", "vice")):
        if ch.get(field):
            bits.append("{}: {}".format(label, str(ch[field]).strip()))
    return "\n".join(bits)


def build_prompt(cfg, bank, count, notes=""):
    """(system, user) for one batch. `bank` is a banks.view() bank dict."""
    import house_voice
    live = [x for x in bank["lines"] if not x["retired"]]
    names = bank["fields"]
    examples = []
    for x in live[:EXAMPLES]:
        row = {"spicy": x["spicy"], "clean": x["clean"] if x["twin"] else x["spicy"]}
        examples.append(json.dumps(row, ensure_ascii=False))
    system = (
        "You write dialogue for Crimson Ledger, an adult-humoured 1860 China Seas trading game. You write new lines "
        "for one character's bank of lines.\n\nTHE HOUSE STYLE (every line follows it):\n" + house_voice.HOUSE_STYLE +
        "\nEvery line comes as a pair: \"spicy\" is the house-voice wording; \"clean\" is the family-friendly twin, "
        "with the same facts and the same {names} but the innuendo removed (the wit stays).\n")
    allowed = ", ".join("{" + n + "}" for n in names) if names else "none"
    amountish = [n for n in names if n in _amounts()]
    user = (
        "CHARACTER\n{persona}\n\nBANK: {bank} (in the game this is: {where}). The game picks one line from the bank "
        "each time, so every new line must be a fresh joke, not a rewording of an existing one.\n\n"
        "EXISTING LINES (do not repeat these):\n{examples}\n\n"
        "WRITE {count} NEW LINES.\n"
        "Rules:\n- Each line is one or two short sentences.\n"
        "- Use only these {{names}}, written exactly like that, or none: {allowed}. If a line uses one, use it in the "
        "spicy AND the clean version.\n- No digits and no money amounts typed out; the game fills amounts in through the names.\n"
        "- Innuendo, never explicit. Everyone is an adult.\n"
        "{amountrule}{notes}"
        "\nReply with ONLY a JSON array, no other text: "
        "[{{\"spicy\": \"...\", \"clean\": \"...\", \"say\": \"\", \"say_clean\": \"\"}}]\n").format(
            persona=_persona(cfg, bank["who"], bank["owner_name"]), bank=bank["id"],
            where=bank.get("moment") or bank["id"], examples="\n".join(examples) or "(none yet)", count=count,
            allowed=allowed,
            amountrule=("- These names carry an amount: {}. When a line uses one, also give \"say\" and \"say_clean\": "
                        "the same line as SPOKEN, with those names left out so the voice never reads a number.\n".format(
                            ", ".join("{" + n + "}" for n in amountish)) if amountish else ""),
            notes=("- Extra direction from the writer: {}\n".format(notes.strip()[:400]) if notes and notes.strip() else ""))
    return system, user


def _amounts():
    import banks
    return banks.AMOUNTS


# ------------------------------------------------------------------------------------------ the writers --
def _post_json(url, body, headers=None, timeout=300):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers=dict({"Content-Type": "application/json"}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        raise GenError("The writer answered with an error ({}). {}".format(e.code, detail).strip())
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise GenError("Could not reach the writer: {}".format(getattr(e, "reason", e)))


def _get_json(url, timeout=6):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise GenError("Could not reach the local LLM at {}: {}".format(url, getattr(e, "reason", e)))


def call_local(s, system, user):
    base = str(s["local"]["base_url"]).rstrip("/")
    model = str(s["local"].get("model") or "").strip()
    if not model:
        raise GenError("Choose the local model first (Generator settings).")
    out = _post_json(base + "/chat/completions",
                     {"model": model, "temperature": 0.95, "max_tokens": 2000, "stream": False,
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
                     timeout=int(s["local"].get("timeout") or 300))
    try:
        return out["choices"][0]["message"]["content"], model
    except (KeyError, IndexError, TypeError):
        raise GenError("The local LLM sent back something unexpected.")


def call_api(s, system, user):
    key, _where = api_key()
    if not key:
        raise GenError("No Anthropic API key is saved. Add one in Generator settings (or set ANTHROPIC_API_KEY).")
    model = str(s["api"].get("model") or DEFAULTS["api"]["model"])
    out = _post_json(API_URL, {"model": model, "max_tokens": 2000, "temperature": 1.0, "system": system,
                               "messages": [{"role": "user", "content": user}]},
                     headers={"x-api-key": key, "anthropic-version": API_VERSION}, timeout=120)
    try:
        return "".join(b.get("text", "") for b in out["content"] if b.get("type") == "text"), model
    except (KeyError, TypeError):
        raise GenError("The Anthropic API sent back something unexpected.")


def parse(text):
    """The list of {spicy, clean, ...} dicts in a writer's reply; tolerant of code fences and chatter."""
    text = re.sub(r"```(?:json)?", "", str(text or ""))
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        rows = json.loads(text[start:end + 1])
    except ValueError:
        return []
    return [r for r in rows if isinstance(r, dict) and isinstance(r.get("spicy"), str)] if isinstance(rows, list) else []


def _norm(t):
    return re.sub(r"[^a-z0-9{}]+", " ", str(t or "").lower()).strip()


# ----------------------------------------------------------------------------------------------- the ops --
def handle(op, body, cfg):
    """Returns {"ok": True, ...} or {"ok": False, "error": ...}."""
    try:
        return {"gen_run": _run, "gen_edit": _edit, "gen_approve": _approve, "gen_discard": _discard,
                "gen_settings": _settings_op, "gen_models": _models}[op](body, cfg)
    except GenError as e:
        return {"ok": False, "error": str(e)}


def _bank(cfg, bid):
    import banks
    for b in banks.view(cfg)["banks"]:
        if b["id"] == bid:
            return b
    raise GenError("That bank does not exist.")


def _run(body, cfg):
    import banks
    s = settings()
    provider = str(body.get("provider") or s["provider"])
    if provider not in ("local", "api"):
        raise GenError("Pick the local LLM or the API.")
    bank = _bank(cfg, str(body.get("bank") or ""))
    if not bank["numbered"] or not bank["addable"]:
        raise GenError(bank.get("fixed_note") or "New lines cannot be added to this bank.")
    try:
        count = max(1, min(MAX_BATCH, int(body.get("count") or 4)))
    except (TypeError, ValueError):
        count = 4
    room = banks.MAX_BANK - bank["size"]
    if room <= 0:
        raise GenError("This bank is full.")
    system, user = build_prompt(cfg, bank, count, str(body.get("notes") or ""))
    text, model = (call_local if provider == "local" else call_api)(s, system, user)
    rows = parse(text)
    if not rows:
        raise GenError("The writer did not send usable lines. Try again, or pick another model.")
    first = bank["lines"][0]["key"]
    seen = {_norm(x["spicy"]) for x in bank["lines"]}
    kept, thrown = [], 0
    with _LOCK:
        q = _queue()
        seen |= {_norm(i["spicy"]) for i in q["items"] if i.get("bank") == bank["id"]}
        for r in rows[:count]:
            cand = {"spicy": r.get("spicy", ""), "clean": r.get("clean", ""),
                    "say": r.get("say") or "", "say_clean": r.get("say_clean") or ""}
            try:
                fields = banks._validate(cfg, first, cand, None)
            except banks.BankError:
                thrown += 1
                continue
            if _norm(fields["spicy"]) in seen:
                thrown += 1
                continue
            seen.add(_norm(fields["spicy"]))
            q["seq"] += 1
            kept.append(dict(fields, id="g{}".format(q["seq"]), bank=bank["id"], provider=provider, model=model,
                             t=int(time.time())))
        q["items"] = (q["items"] + kept)[-MAX_QUEUE:]
        _write(QUEUE_FILE, q)
    if not kept:
        raise GenError("None of the {} drafts passed the checks (names, length, duplicates). Try again.".format(len(rows)))
    return {"ok": True, "added": len(kept), "thrown": thrown + max(0, len(rows) - count), "model": model}


def _item(q, iid):
    for i in q["items"]:
        if i.get("id") == iid:
            return i
    raise GenError("That draft is not in the queue any more.")


def _edit(body, cfg):
    with _LOCK:
        q = _queue()
        item = _item(q, str(body.get("id") or ""))
        for f in ("spicy", "clean", "say", "say_clean"):
            if isinstance(body.get(f), str):
                item[f] = body[f]
        _write(QUEUE_FILE, q)
    return {"ok": True}


def _approve(body, cfg):
    import banks
    with _LOCK:
        q = _queue()
        item = _item(q, str(body.get("id") or ""))
        res = banks.handle("add", {"bank": item["bank"], "spicy": item.get("spicy", ""), "clean": item.get("clean", ""),
                                   "say": item.get("say", ""), "say_clean": item.get("say_clean", "")}, cfg)
        if not res.get("ok"):
            return res                      # stays in the queue so it can be fixed
        q["items"] = [i for i in q["items"] if i.get("id") != item["id"]]
        _write(QUEUE_FILE, q)
    return {"ok": True, "changed": True, "key": res.get("key", "")}


def _discard(body, cfg):
    with _LOCK:
        q = _queue()
        ids = [str(x) for x in (body.get("ids") or [body.get("id")]) if x]
        q["items"] = [i for i in q["items"] if i.get("id") not in ids]
        _write(QUEUE_FILE, q)
    return {"ok": True}


def _settings_op(body, cfg):
    s = settings()
    if body.get("provider") in ("local", "api"):
        s["provider"] = body["provider"]
    if isinstance(body.get("base_url"), str):
        url = body["base_url"].strip()
        if url and not re.match(r"^https?://[^\s]+$", url):
            raise GenError("The local address must start with http:// or https://.")
        s["local"]["base_url"] = url or DEFAULTS["local"]["base_url"]
    if isinstance(body.get("model"), str):
        s["local"]["model"] = body["model"].strip()
    if isinstance(body.get("api_model"), str) and body["api_model"].strip():
        s["api"]["model"] = body["api_model"].strip()
    _write(GEN_FILE, s)
    if "key" in body:
        key = str(body.get("key") or "").strip()
        if not key:
            if os.path.isfile(KEY_FILE):
                os.remove(KEY_FILE)
        elif not re.match(r"^[A-Za-z0-9_\-]{20,300}$", key):
            raise GenError("That does not look like an Anthropic API key.")
        else:
            _write(KEY_FILE, {"key": key})
    return {"ok": True}


def _models(body, cfg):
    base = str(body.get("base_url") or settings()["local"]["base_url"]).rstrip("/")
    data = _get_json(base + "/models")
    rows = data.get("data") if isinstance(data, dict) else None
    names = sorted({str(m.get("id")) for m in rows or [] if isinstance(m, dict) and m.get("id")})
    if not names:
        raise GenError("The local LLM did not list any models.")
    return {"ok": True, "models": names}
