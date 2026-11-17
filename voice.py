"""SeaTrader voices: game wording read aloud by the cast, through Inworld TTS.

Standard library only, like the rest of the server.

How a line becomes speech:
  1. The server works out which wording key produced a line of text (Matcher),
     and so which character reads it (cast.speaker_for). Lines with amounts in
     them are read as a short spoken version without the numbers
     (cast.spoken_template), so each sounds the same every time and is paid
     for once. The screen still shows the full line.
  2. It registers the line and hands the screen a URL, /voice/<clip>.mp3.
  3. Nothing is sent to Inworld until a screen asks for that URL. The finished
     MP3 is kept in cache/voice/ for good (nothing is ever pruned), so a line is
     only ever paid for once. cache/voice/index.jsonl records what each clip says.

Only lines the server itself planned can be synthesized from a player screen;
the Admin page can audition any text.

The API key is the Base64 "Basic" credential from the Inworld dashboard (the
same one GrumpyRobot and Sector Says What use). It comes from the Admin page
(saved in config/voice_key.json, which git ignores) or, failing that, from the
INWORLD_API_KEY environment variable.
"""
import base64
import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict

import cast

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(ROOT, "cache", "voice")
INDEX_NAME = "index.jsonl"   # in CACHE_DIR: one line per clip ever paid for
KEY_FILE = os.path.join(ROOT, "config", "voice_key.json")
TTS_URL = "https://api.inworld.ai/tts/v1/voice:stream"
VOICES_URL = "https://api.inworld.ai/voices/v1/voices"
LEGACY_VOICES_URL = "https://api.inworld.ai/tts/v1/voices"
MAX_CHARS = 1900          # Inworld takes up to 2000 characters a request
REGISTRY_SIZE = 6000
CLIP_RE = re.compile(r"^[0-9a-f]{24}$")
DATE_PREFIX = re.compile(r"^[^:]{1,24}:\s+")

STATS = {"synth_calls": 0, "synth_chars": 0, "cache_hits": 0, "errors": 0, "last_error": "", "last_error_at": 0}


on_log = None        # set by the server: on_log(level, message, **details) writes to the server log


def _log(level, msg, **data):
    if on_log is not None:
        try:
            on_log(level, msg, **data)
        except Exception:                 # the log must never break a voice
            pass


class VoiceError(Exception):
    """Inworld refused or could not be reached. The message is safe to show on the Admin page."""


# ------------------------------------------------------------------ key --
def _clean_key(key):
    key = str(key or "").strip()
    if key.lower().startswith("basic "):
        key = key[6:].strip()
    return key


def api_key():
    """(key, where it came from). Empty key when none is set."""
    try:
        with open(KEY_FILE, encoding="utf-8") as f:
            key = _clean_key(json.load(f).get("key"))
        if key:
            return key, "admin"
    except (OSError, ValueError, AttributeError):
        pass
    key = _clean_key(os.environ.get("INWORLD_API_KEY"))
    return (key, "env") if key else ("", "")


def set_key(key):
    """Saves the key from the Admin page. An empty key removes it (the environment variable then applies)."""
    key = _clean_key(key)
    if not key:
        if os.path.isfile(KEY_FILE):
            os.remove(KEY_FILE)
        return
    if not re.match(r"^[A-Za-z0-9+/=_\-:.]{16,400}$", key):
        raise VoiceError("That does not look like an Inworld API key. Copy the Base64 key from the Inworld dashboard.")
    os.makedirs(os.path.dirname(KEY_FILE), exist_ok=True)
    tmp = KEY_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"key": key}, f)
    os.replace(tmp, KEY_FILE)


def key_status():
    key, source = api_key()
    return {"has_key": bool(key), "source": source, "tail": key[-4:] if key else ""}


# ----------------------------------------------------------------- http --
def _urllib(method, url, headers, body, timeout):
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except (urllib.error.URLError, OSError) as e:
        raise VoiceError("Could not reach Inworld ({}). Check this computer's internet connection.".format(
            getattr(e, "reason", e)))


_transport = _urllib      # tests swap this for a fake


def _request(method, url, body=None, timeout=30):
    key, _ = api_key()
    if not key:
        raise VoiceError("No Inworld API key. Add it on the Admin page under Cast & Voices, "
                         "or set the INWORLD_API_KEY environment variable.")
    headers = {"Authorization": "Basic " + key, "Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    status, raw = _transport(method, url, headers, data, timeout)
    if status in (401, 403):
        raise VoiceError("Inworld did not accept the API key (HTTP {}).".format(status))
    if status >= 400:
        detail = raw[:300].decode("utf-8", "replace") if raw else ""
        try:
            detail = json.loads(raw).get("message") or detail
        except (ValueError, AttributeError):
            pass
        raise VoiceError("Inworld answered HTTP {}: {}".format(status, " ".join(str(detail).split())[:240]))
    return status, raw


def _note_error(e):
    STATS["errors"] += 1
    STATS["last_error"] = str(e)
    STATS["last_error_at"] = int(time.time())


# ------------------------------------------------------------ synthesis --
def steers(model_id):
    """Whether the model follows a spoken-delivery note. Flash ignores one, so it is not sent."""
    return model_id.startswith("inworld-tts-2") and "flash" not in model_id


def speech_text(text):
    """Game wording tidied for the ear."""
    t = str(text or "")
    t = t.replace(" · ", ", ").replace("…", "...")
    t = re.sub(r"\{\w+\}", "", t)
    t = " ".join(t.split())
    return t[:MAX_CHARS]


def synthesize(text, voice_id, model_id, rate=1.0, temperature=1.0, delivery=""):
    """MP3 bytes for one line. Raises VoiceError."""
    text = speech_text(text)
    if not text:
        raise VoiceError("Nothing to say.")
    if not voice_id:
        raise VoiceError("This character has no voice ID yet.")
    if delivery and steers(model_id):
        text = "[{}] {}".format(" ".join(delivery.split())[:200], text)
    payload = {
        "text": text,
        "voice_id": voice_id,
        "model_id": model_id,
        "audio_config": {"audio_encoding": "MP3", "speaking_rate": float(rate)},
        "temperature": float(temperature),
    }
    _status, raw = _request("POST", TTS_URL, payload, timeout=45)
    audio, problem = bytearray(), ""
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        chunk = (obj.get("result") or {}).get("audioContent") or obj.get("audioContent")
        if chunk:
            try:
                audio += base64.b64decode(chunk)
            except (ValueError, TypeError):
                continue
        elif obj.get("error"):
            problem = (obj["error"] or {}).get("message") or str(obj["error"])
    if not audio:
        raise VoiceError("Inworld sent no audio" + (": " + problem if problem else
                         ". Check the voice ID '{}' and the model.".format(voice_id)))
    STATS["synth_calls"] += 1
    STATS["synth_chars"] += len(text)
    return bytes(audio)


# --------------------------------------------------------------- voices --
_voices = {"at": 0, "list": [], "error": ""}
_voices_lock = threading.Lock()


def _voice_row(v):
    langs = v.get("promptLanguages") or v.get("languages") or []
    lang = v.get("languageCode") or v.get("langCode") or (langs[0] if langs else "")
    return {
        "id": v.get("voiceId") or v.get("name") or "",
        "name": v.get("displayName") or v.get("voiceId") or "",
        "description": " ".join(str(v.get("description") or "").split())[:240],
        "gender": v.get("gender") or "",
        "age": (v.get("ageGroup") or "").replace("_", " "),
        "lang": str(lang).replace("_", "-"),
        "source": v.get("source") or "",
        "tags": [str(t) for t in (v.get("tags") or [])][:8],
    }


def list_voices(force=False):
    """Every voice this Inworld workspace can use: system voices plus your own clones and designs."""
    with _voices_lock:
        if not force and _voices["list"] and time.time() - _voices["at"] < 900:
            return _voices["list"]
        rows, token, pages = [], "", 0
        try:
            while pages < 8:
                q = {"pageSize": "1000"}
                if token:
                    q["pageToken"] = token
                try:
                    _s, raw = _request("GET", VOICES_URL + "?" + urllib.parse.urlencode(q), timeout=20)
                except VoiceError as e:
                    if pages == 0 and "HTTP 404" in str(e):
                        _s, raw = _request("GET", LEGACY_VOICES_URL, timeout=20)
                        rows = [_voice_row(v) for v in (json.loads(raw).get("voices") or [])]
                        break
                    raise
                data = json.loads(raw)
                rows += [_voice_row(v) for v in (data.get("voices") or [])]
                token = data.get("nextPageToken") or ""
                pages += 1
                if not token:
                    break
        except ValueError:
            raise VoiceError("Inworld sent a voice list this version does not understand.")
        seen, out = set(), []
        for r in rows:
            if r["id"] and r["id"] not in seen:
                seen.add(r["id"])
                out.append(r)
        out.sort(key=lambda r: (r["source"] == "SYSTEM", not r["lang"].startswith("en"), r["name"].lower()))
        _voices.update(at=time.time(), list=out, error="")
        return out


# ---------------------------------------------------------- clip cache --
_registry = OrderedDict()   # clip id -> synthesis parameters
_reg_lock = threading.Lock()
_clip_locks = {}


def _params(text, ch, vcfg):
    model = vcfg["model_id"]
    return {"text": speech_text(text), "voice_id": ch.get("voice_id", ""), "model_id": model,
            "rate": round(float(ch.get("speaking_rate", 1.0)), 3),
            "temperature": round(float(vcfg.get("temperature", 1.0)), 3),
            "delivery": ch.get("delivery", "") if steers(model) else ""}


def clip_id(params):
    raw = json.dumps(params, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:24]


def clip_path(cid):
    return os.path.join(CACHE_DIR, cid + ".mp3")


def register(params):
    cid = clip_id(params)
    with _reg_lock:
        _registry[cid] = params
        _registry.move_to_end(cid)
        while len(_registry) > REGISTRY_SIZE:
            _registry.popitem(last=False)
    return cid


_index_lock = threading.Lock()


def _index(cid, params, nbytes):
    """Notes a newly paid-for clip in cache/voice/index.jsonl (what it says, who says it)."""
    row = {"clip": cid, "at": time.strftime("%Y-%m-%d %H:%M:%S"), "bytes": nbytes}
    row.update(params)
    try:
        with _index_lock, open(os.path.join(CACHE_DIR, INDEX_NAME), "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def render(params):
    """MP3 bytes for a set of parameters, from the cache or from Inworld."""
    cid = clip_id(params)
    path = clip_path(cid)
    with _reg_lock:
        lock = _clip_locks.setdefault(cid, threading.Lock())
    with lock:                           # two screens asking at once pay once
        if os.path.isfile(path):
            STATS["cache_hits"] += 1
            _log("DEBUG", "Voice line played from the cache", clip=cid, voice=params.get("voice_id"))
            with open(path, "rb") as f:
                return f.read()
        try:
            audio = synthesize(params["text"], params["voice_id"], params["model_id"], params["rate"],
                               params["temperature"], params["delivery"])
        except VoiceError as e:
            _note_error(e)
            _log("WARN", "Voice line failed: {}".format(e), clip=cid, voice=params.get("voice_id"),
                 chars=len(params.get("text") or ""), text=(params.get("text") or "")[:120])
            raise
        _log("INFO", "Voice line sent to Inworld: {} characters, voice {}".format(
            len(params.get("text") or ""), params.get("voice_id")), clip=cid, voice=params.get("voice_id"),
            model=params.get("model_id"), chars=len(params.get("text") or ""), bytes=len(audio),
            text=(params.get("text") or "")[:120])
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(audio)
        os.replace(tmp, path)
        _index(cid, params, len(audio))
    with _reg_lock:
        _clip_locks.pop(cid, None)
    return audio


def get_clip(cid):
    """MP3 for a clip a screen was given, or None if the server never planned it."""
    if not CLIP_RE.match(cid or ""):
        return None
    path = clip_path(cid)
    if os.path.isfile(path):
        STATS["cache_hits"] += 1
        _log("DEBUG", "Voice line played from the cache", clip=cid)
        with open(path, "rb") as f:
            return f.read()
    with _reg_lock:
        params = _registry.get(cid)
    return render(params) if params else None


def cache_info():
    try:
        files = [f for f in os.listdir(CACHE_DIR) if f.endswith(".mp3")]
        size = sum(os.path.getsize(os.path.join(CACHE_DIR, f)) for f in files)
    except OSError:
        files, size = [], 0
    chars = 0
    try:
        with open(os.path.join(CACHE_DIR, INDEX_NAME), encoding="utf-8") as f:
            for line in f:
                try:
                    chars += len(json.loads(line).get("text") or "")
                except ValueError:
                    continue
    except OSError:
        pass
    return {"clips": len(files), "mb": round(size / 1048576, 1), "chars": chars}


def clear_cache():
    """Moves every saved clip (and the index) to cache/voice_cleared/<time>/. Paid audio is never deleted."""
    n = 0
    dest = os.path.join(os.path.dirname(CACHE_DIR), "voice_cleared", time.strftime("%Y%m%d-%H%M%S"))
    try:
        for f in os.listdir(CACHE_DIR):
            if f.endswith(".mp3") or f == INDEX_NAME:
                os.makedirs(dest, exist_ok=True)
                os.replace(os.path.join(CACHE_DIR, f), os.path.join(dest, f))
                n += f.endswith(".mp3")
    except OSError:
        pass
    return n


# -------------------------------------------------------------- matcher --
class Matcher:
    """Finds the wording key that produced a line of game text, and the names filled into it."""

    def __init__(self, text):
        pats = []
        for key in cast.spoken_keys(text):
            tpl = text[key]
            parts = re.split(r"(\{\w+\})", tpl)
            literal = sum(len(p) for p in parts if not p.startswith("{"))
            names = [p[1:-1] for p in parts if p.startswith("{") and p.endswith("}")]
            rx = "".join("(.+?)" if p.startswith("{") and p.endswith("}") else re.escape(p) for p in parts)
            try:
                pats.append((literal, key, re.compile("^" + rx + "$", re.DOTALL), names))
            except re.error:
                continue
        pats.sort(key=lambda p: -p[0])
        self.pats = [(k, rx, names) for _l, k, rx, names in pats]
        self.memo = OrderedDict()

    def match(self, line):
        """(key, {name: value}) for a line, or (None, {})."""
        line = str(line or "").strip()
        if line in self.memo:
            return self.memo[line]
        found = (None, {})
        for k, rx, names in self.pats:
            m = rx.match(line)
            if m:
                fields = {}
                for name, value in zip(names, m.groups()):
                    fields.setdefault(name, value)
                found = (k, fields)
                break
        self.memo[line] = found
        if len(self.memo) > 4000:
            self.memo.popitem(last=False)
        return found

    def key(self, line):
        return self.match(line)[0]


# ------------------------------------------------------------- planning --
class Planner:
    """Decides who reads each line a screen is about to show."""

    def __init__(self):
        self.cfg = None
        self.text = {}
        self.matcher = None

    def configure(self, cfg, text):
        self.cfg = cfg
        self.text = text
        self.matcher = Matcher(text)

    def spoken(self, key, fields, line):
        """The words the voice says for a line on screen."""
        if not key:
            return line
        tpl = cast.spoken_template(self.cfg, self.text, key)
        if tpl == self.text.get(key):
            return line                      # read exactly as shown
        return re.sub(r"\{(\w+)\}", lambda m: fields.get(m.group(1), ""), tpl)

    def ready(self):
        return bool(self.cfg and self.cfg["voice"]["enabled"] and api_key()[0])

    def _clip(self, text, cid):
        ch = self.cfg["characters"].get(cid)
        if not ch or not ch.get("voice_id") or not speech_text(text):
            return None
        return {"c": cid, "u": "/voice/{}.mp3".format(register(_params(text, ch, self.cfg["voice"])))}

    def _who(self, key, port):
        """Who reads a line: the Port Authority's lines go to the officer of the player's port."""
        cid = cast.speaker_for(self.cfg, key)
        if port and key in cast.OFFICER_KEYS and cid == cast.LINE_DEFAULTS.get(key):
            officer = ((self.cfg.get("ports") or {}).get(port) or {}).get("officer")
            ch = self.cfg["characters"].get(officer) if officer else None
            if ch and ch.get("voice_id"):
                return officer
        return cid

    def line(self, text, kind, port=None):
        """kind: 'log' (captain's log), 'news', 'msg' (an answer to something the player did).
        port: where the player is, so the Port Authority's lines go to that port's officer."""
        v = self.cfg["voice"]
        if kind == "news":
            text = DATE_PREFIX.sub("", str(text))
        key, fields = self.matcher.match(text)
        if kind == "log":
            if not v["read_log"]:
                return None
            cid = self._who(key, port) if key else cast.speaker_for(self.cfg, "l.?")
        elif kind == "news":
            cid = cast.speaker_for(self.cfg, key) if key else v["custom_news"]
        else:
            if not key or (key.startswith("m.") and not v["read_confirmations"]) or \
                    (key.startswith("e.") and not v["read_errors"]):
                return None
            cid = self._who(key, port)
        return self._clip(self.spoken(key, fields, str(text).strip()), cid) if cid else None

    def lines(self, texts, kind, limit=None, port=None):
        if not self.ready():
            return None
        texts = list(texts or [])[:limit] if limit else list(texts or [])
        return [self.line(t, kind, port) for t in texts]

    def msg(self, text, port=None):
        if not self.ready():
            return None
        return self.line(text, "msg", port)

    def public(self):
        """Settings the screens need: who is who, and what they read."""
        if not self.cfg:
            return {"enabled": False}
        v = self.cfg["voice"]
        return {"enabled": bool(v["enabled"] and api_key()[0]), "news_board": v["read_news_board"],
                "news_players": v["read_news_players"], "cast": cast.public_cast(self.cfg)}


PLAN = Planner()
