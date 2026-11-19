"""Emit a focused, preflighted Pi patch: pipe stdout to SSH python3 stdin."""
import base64
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET = "web/assets/branding/crimson-ledger-command-center-v01.webp"
EDITS = {
    "config.py": [
        ('        "masthead_bg": "/uploads/historical-masthead.webp",',
         '        "masthead_bg": "/uploads/historical-masthead.webp",\n        "admin_masthead_bg": "/assets/branding/crimson-ledger-command-center-v01.webp",'),
        ('    ["masthead_bg", "Title banner background", "Behind the title on the join and lobby screens."],',
         next(line for line in (ROOT / "config.py").read_text(encoding="utf-8").splitlines() if line.startswith('    ["masthead_bg",')) + '\n' +
         next(line for line in (ROOT / "config.py").read_text(encoding="utf-8").splitlines() if line.startswith('    ["admin_masthead_bg",'))),
    ],
    "media.py": [
        ('BRAND_SLOTS = [["logo", "Logo"], ["favicon", "Browser tab icon"], ["masthead_bg", "Title banner background"],',
         'BRAND_SLOTS = [["logo", "Logo"], ["favicon", "Browser tab icon"], ["masthead_bg", "Title banner background"],\n               ["admin_masthead_bg", "Command Center banner"],'),
    ],
    "web/admin.js": [
        ('function brandMark() {', 'function brandMark() {\n  const banner = CFG?.graphics?.admin_masthead_bg || "";\n  $(".masthead").style.backgroundImage = banner ? `url(${JSON.stringify(banner)})` : "none";'),
    ],
    "web/admin.css": [
        ('/assets/sea-trader-header-sirens.webp?v=1', '/assets/branding/crimson-ledger-command-center-v01.webp'),
    ],
    "web/graphics-admin.js": [
        ('masthead_bg: "16:5", page_bg:', 'masthead_bg: "16:5", admin_masthead_bg: "3:1", page_bg:'),
        ('    if (s.kind === "port") return',
         next(line for line in (ROOT / "web/graphics-admin.js").read_text(encoding="utf-8").splitlines() if 's.subject === "admin_masthead_bg"' in line) + '\n    if (s.kind === "port") return'),
    ],
    "web/admin.html": [
        ('/admin.css?v=20261118brand1', '/admin.css?v=20261118chartroom1'),
        ('/graphics-admin.js?v=20261118text1', '/graphics-admin.js?v=20261118chartroom1'),
        ('/admin.js?v=20261118brand1', '/admin.js?v=20261118chartroom1'),
    ],
}
asset = (ROOT / ASSET).read_bytes()
payload = json.dumps({"edits": EDITS, "asset": ASSET, "data": base64.b64encode(asset).decode(),
                      "sha256": hashlib.sha256(asset).hexdigest()})
print("import base64, hashlib, json, pathlib, shutil, tempfile")
print("payload = json.loads(" + repr(payload) + ")")
print('''root = pathlib.Path("/home/madlively/SeaTrader")
pending = {}
for name, edits in payload["edits"].items():
    text = (root / name).read_text(encoding="utf-8")
    for old, new in edits:
        if new in text:
            continue
        if text.count(old) != 1:
            raise RuntimeError("Preflight refused unexpected content in " + name)
        text = text.replace(old, new, 1)
    if name.endswith(".py"):
        compile(text, name, "exec")
    pending[name] = text
data = base64.b64decode(payload["data"])
assert hashlib.sha256(data).hexdigest() == payload["sha256"]
backup = pathlib.Path(tempfile.mkdtemp(prefix="crimson-command-center-"))
for name, text in pending.items():
    dest = root / name
    saved = backup / name
    saved.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(dest, saved)
    dest.write_text(text, encoding="utf-8")
dest = root / payload["asset"]
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_bytes(data)
assert hashlib.sha256(dest.read_bytes()).hexdigest() == payload["sha256"]
for name, text in pending.items():
    assert (root / name).read_text(encoding="utf-8") == text
print("Verified focused banner patch. Backup:", backup)
print("Asset SHA256:", payload["sha256"])
''')
