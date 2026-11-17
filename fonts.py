"""SeaTrader web fonts.

The lettering is chosen under Admin > Look & Style. The "Web fonts to download" setting names
Google Fonts families; this module fetches them once into web/fonts/ so every screen (player,
harbor board, admin) is served them by the game itself. After that no device needs the
internet or any installed fonts, which keeps the LAN and Raspberry Pi set-up working offline.

Runs in the background at start-up and after each Save & apply, and only downloads when the
list has changed or files are missing. Without internet the screens fall back to the next
font in each list, and the next start tries again. Standard library only.
"""

import hashlib
import os
import re
import shutil
import threading
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "web", "fonts")
CSS_FILE = os.path.join(FONT_DIR, "fonts.css")
SPEC_FILE = os.path.join(FONT_DIR, "families.txt")

API = "https://fonts.googleapis.com/css2?{}&display=swap"
# A desktop browser's name, so Google answers with WOFF2 files.
AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
SUBSETS = ("latin", "latin-ext")          # enough for English and European languages
FAMILY_RE = re.compile(r"^[A-Za-z0-9 ]{1,60}(:[a-z,]{1,20}@[0-9.,;]{1,80})?$")
BLOCK_RE = re.compile(r"(?:/\*\s*([\w-]+)\s*\*/\s*)?(@font-face\s*\{[^}]*\})", re.S)
URL_RE = re.compile(r"url\((https://fonts\.gstatic\.com/[^)\s]+)\)")
TIMEOUT = 20

_lock = threading.Lock()
_pending = None


def families(spec):
    """The family list from the setting: one per line or separated by |."""
    out = []
    for part in re.split(r"[|\n]", spec or ""):
        part = part.strip()
        if part and FAMILY_RE.match(part) and part not in out:
            out.append(part)
    return out


def _spec_key(fams):
    return "\n".join(fams)


def up_to_date(spec):
    fams = families(spec)
    if not fams:
        return True
    try:
        with open(SPEC_FILE, encoding="utf-8") as f:
            if f.read() != _spec_key(fams):
                return False
        with open(CSS_FILE, encoding="utf-8") as f:
            css = f.read()
    except OSError:
        return False
    return all(os.path.isfile(os.path.join(FONT_DIR, n)) for n in re.findall(r'url\("/fonts/([\w.-]+)"\)', css))


def local_css():
    """The @font-face rules for the downloaded fonts, or "" before they are downloaded."""
    try:
        with open(CSS_FILE, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "font"


def download(spec):
    """Fetches the families now. Returns a one-line report."""
    fams = families(spec)
    if not fams:
        return "Web fonts: none listed."
    query = "&".join("family=" + urllib.parse.quote(f.replace(" ", "+"), safe="+:,@;.") for f in fams)
    css = _get(API.format(query)).decode("utf-8")

    tmp = FONT_DIR + ".new"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    names, rules = {}, []
    for subset, block in BLOCK_RE.findall(css):
        if subset and subset not in SUBSETS:
            continue
        fam = re.search(r"font-family:\s*'([^']+)'", block)
        for src in URL_RE.findall(block):
            if src not in names:
                digest = hashlib.sha1(src.encode()).hexdigest()[:8]
                names[src] = "{}-{}-{}.woff2".format(_slug(fam.group(1) if fam else "font"), subset or "all", digest)
                with open(os.path.join(tmp, names[src]), "wb") as out:
                    out.write(_get(src))
            block = block.replace("url({})".format(src), 'url("/fonts/{}")'.format(names[src]))
        rules.append(("/* {} */\n".format(subset) if subset else "") + block)
    if not rules:
        shutil.rmtree(tmp, ignore_errors=True)
        raise ValueError("Google Fonts sent no usable fonts for: " + ", ".join(fams))

    with open(os.path.join(tmp, "fonts.css"), "w", encoding="utf-8") as f:
        f.write("/* Downloaded by fonts.py from Google Fonts (SIL Open Font Licence). */\n" + "\n".join(rules) + "\n")
    with open(os.path.join(tmp, "families.txt"), "w", encoding="utf-8") as f:
        f.write(_spec_key(fams))
    old = FONT_DIR + ".old"
    shutil.rmtree(old, ignore_errors=True)
    if os.path.isdir(FONT_DIR):
        os.replace(FONT_DIR, old)
    os.replace(tmp, FONT_DIR)
    shutil.rmtree(old, ignore_errors=True)
    return "Web fonts ready: {} ({} files).".format(", ".join(f.split(":")[0] for f in fams), len(names))


on_log = None        # set by the server: on_log(level, message) writes to the server log


def _log(level, msg):
    if on_log is not None:
        try:
            on_log(level, msg)
        except Exception:
            pass


def ensure(spec, on_done=None):
    """Downloads in the background if needed. on_done() is called after a successful download."""
    global _pending
    if up_to_date(spec):
        return False
    with _lock:
        if _pending == spec:
            return False
        _pending = spec

    def work():
        global _pending
        try:
            msg = download(spec)
            print(msg)
            _log("INFO", msg)
            if on_done:
                on_done()
        except Exception as e:                     # no internet, blocked, bad name: keep fallbacks
            msg = ("Web fonts not downloaded ({}). Screens use the fallback fonts; "
                   "the next start will try again.".format(e))
            print(msg)
            _log("WARN", msg)
        finally:
            with _lock:
                _pending = None

    threading.Thread(target=work, name="fonts", daemon=True).start()
    return True


if __name__ == "__main__":                         # python fonts.py  -> download now
    import config
    print(download(config.load()["theme"]["web_fonts"]))
