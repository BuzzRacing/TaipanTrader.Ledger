"""Shrink Crimson Ledger's game pictures.

Image gen hands back 1024x1360 PNGs of about 2.4 MB each. PNG is the wrong format for painted art:
the same picture as WebP is about 170 KB and looks the same. This tool:

  1. converts every PNG/JPG bigger than --min-kb in web/media and web/uploads to a WebP of the same name
     (same size in pixels unless it is wider or taller than --max-side),
  2. rewrites every reference to the old file names in config/, saves/, captains/ and journal/
     (the Media Library index config/media.json gets its new byte counts too),
  3. moves the old files out of the game folder into --originals (or deletes them with --delete).

web/assets is left alone: those files are in Git and named in the code.
Safe to run again at any time: it only touches pictures that are still PNG/JPG.

    python tools/shrink_images.py                         # the game in this folder
    python tools/shrink_images.py --dry-run               # just report what it would do
    python tools/shrink_images.py --root D:/work/pi --originals D:/old --lists D:/work/pi

Needs Pillow (pip install pillow). Stop the game server first: it keeps config/media.json in memory.
"""
import argparse
import io
import json
import os
import re
import shutil
import socket
import sys
import time

try:
    from PIL import Image
except ImportError:
    print("Pillow is not installed. Run:  python -m pip install pillow")
    sys.exit(2)

PIC_FOLDERS = ("web/media", "web/uploads")
SOURCE_EXT = (".png", ".jpg", ".jpeg")
REF_FOLDERS = ("config", "saves", "captains", "journal")
REF_EXT = (".json", ".jsonl")
URL_RE = re.compile(r"/(?:media|uploads)/[A-Za-z0-9._/-]+\.(?:png|jpe?g)", re.I)


def to_webp(data_or_path, quality, max_side):
    """WebP bytes for a picture, or None if it cannot be read."""
    src = io.BytesIO(data_or_path) if isinstance(data_or_path, (bytes, bytearray)) else data_or_path
    with Image.open(src) as im:
        im.load()
        if im.mode == "P" or im.mode == "LA" or (im.mode not in ("RGB", "RGBA") and "A" in im.getbands()):
            im = im.convert("RGBA")
        elif im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
        # Image gen leaves a nearly-solid alpha channel (244-255); drop it unless it is real transparency.
        if im.mode == "RGBA" and im.getchannel("A").getextrema()[0] >= 240:
            im = im.convert("RGB")
        if max_side and max(im.size) > max_side:
            scale = max_side / float(max(im.size))
            im = im.resize((max(1, round(im.size[0] * scale)), max(1, round(im.size[1] * scale))), Image.LANCZOS)
        out = io.BytesIO()
        im.save(out, "WEBP", quality=quality, method=4)
        return out.getvalue(), im.size


def server_running(port):
    if not port:
        return False
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def atomic_write(path, text):
    tmp = path + ".shrinktmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(tmp, path)


def rel(root, path):
    return os.path.relpath(path, root).replace(os.sep, "/")


def mb(n):
    return "{:,.1f} MB".format(n / 1048576.0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    help="the game folder (default: the folder this tool lives in)")
    ap.add_argument("--quality", type=int, default=85, help="WebP quality 1-100 (default 85)")
    ap.add_argument("--max-side", type=int, default=2048, help="shrink anything wider/taller than this (default 2048)")
    ap.add_argument("--min-kb", type=int, default=300, help="leave pictures smaller than this alone (default 300)")
    ap.add_argument("--originals", default="", help="move the old files here (keeps their folders)")
    ap.add_argument("--delete", action="store_true", help="delete the old files instead of moving them")
    ap.add_argument("--lists", default="", help="write shrink_push.txt / shrink_remove.txt here (used for the Pi)")
    ap.add_argument("--check-port", type=int, default=0, help="refuse to run if a game server answers on this port")
    ap.add_argument("--dry-run", action="store_true", help="report only; change nothing")
    a = ap.parse_args()

    root = os.path.abspath(a.root)
    if not os.path.isdir(os.path.join(root, "web")):
        print("No web folder in {}. Is that the game folder?".format(root))
        return 2
    if not a.dry_run and not a.delete and not a.originals:
        print("Say where the old files go (--originals FOLDER) or use --delete.")
        return 2
    if server_running(a.check_port):
        print("A game server is running on port {} on this PC. Stop it first (Stop_SeaTrader.bat).".format(a.check_port))
        return 3

    # 1. Find the pictures worth converting.
    todo = []
    for folder in PIC_FOLDERS:
        base = os.path.join(root, folder)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for fn in sorted(filenames):
                p = os.path.join(dirpath, fn)
                if os.path.splitext(fn)[1].lower() in SOURCE_EXT and os.path.getsize(p) >= a.min_kb * 1024:
                    todo.append(p)
    if not todo:
        print("Nothing to shrink: every picture over {} KB is already WebP.".format(a.min_kb))
        if a.lists:
            for name in ("shrink_push.txt", "shrink_remove.txt"):
                p = os.path.join(a.lists, name)
                if os.path.exists(p):
                    os.remove(p)
        return 0

    print("{} pictures to convert ({}).".format(len(todo), mb(sum(os.path.getsize(p) for p in todo))))
    if a.dry_run:
        sample = todo[0]
        data, _size = to_webp(sample, a.quality, a.max_side)
        print("Example: {}  {} -> {}".format(rel(root, sample), mb(os.path.getsize(sample)), mb(len(data))))
        return 0

    # 2. Convert. The old file stays until every reference has been rewritten.
    url_map, info, done = {}, {}, []
    before = after = 0
    t0 = time.time()
    for n, p in enumerate(todo, 1):
        dst = os.path.splitext(p)[0] + ".webp"
        old_bytes = os.path.getsize(p)
        try:
            if os.path.exists(dst):          # an earlier run converted it but stopped before moving the old one
                with Image.open(dst) as im:
                    size = im.size
                new_bytes = os.path.getsize(dst)
            else:
                data, size = to_webp(p, a.quality, a.max_side)
                if len(data) >= old_bytes * 0.9:
                    print("  kept   {} (WebP would not be smaller)".format(rel(root, p)))
                    continue
                with open(dst + ".shrinktmp", "wb") as f:
                    f.write(data)
                os.replace(dst + ".shrinktmp", dst)
                new_bytes = len(data)
        except Exception as e:
            print("  SKIPPED {}: {}".format(rel(root, p), e))
            continue
        old_url, new_url = "/" + rel(os.path.join(root, "web"), p), "/" + rel(os.path.join(root, "web"), dst)
        url_map[old_url] = new_url
        info[new_url] = (size[0], size[1], new_bytes)
        done.append((p, dst))
        before += old_bytes
        after += new_bytes
        if n % 25 == 0 or n == len(todo):
            print("  {}/{} converted ({:.0f}s)".format(n, len(todo), time.time() - t0))

    # 3. Rewrite every reference to the old names.
    changed = []
    lower_map = {k.lower(): v for k, v in url_map.items()}

    def swap(m):
        return url_map.get(m.group(0)) or lower_map.get(m.group(0).lower()) or m.group(0)

    for folder in REF_FOLDERS:
        base = os.path.join(root, folder)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d != "backups"]
            for fn in filenames:
                if os.path.splitext(fn)[1].lower() not in REF_EXT:
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    with open(p, encoding="utf-8", newline="") as f:
                        text = f.read()
                except (OSError, UnicodeDecodeError):
                    continue
                new = URL_RE.sub(swap, text)
                is_lib = rel(root, p) == "config/media.json"
                if is_lib:
                    lib = json.loads(new)
                    for it in lib.get("items", []):
                        if it.get("url") in info:
                            it["width"], it["height"], it["bytes"] = info[it["url"]]
                    new = json.dumps(lib, indent=1, ensure_ascii=False)
                if new != text:
                    atomic_write(p, new)
                    changed.append(p)
    print("Updated references in {} file{}.".format(len(changed), "" if len(changed) == 1 else "s"))

    # 4. Move (or delete) the old files.
    for p, _dst in done:
        if a.delete:
            os.remove(p)
        else:
            target = os.path.join(a.originals, rel(root, p))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.move(p, target)

    if a.lists:
        os.makedirs(a.lists, exist_ok=True)
        with open(os.path.join(a.lists, "shrink_push.txt"), "w", encoding="utf-8", newline="\n") as f:
            for line in [rel(root, d) for _p, d in done] + [rel(root, p) for p in changed]:
                f.write(line + "\n")
        with open(os.path.join(a.lists, "shrink_remove.txt"), "w", encoding="utf-8", newline="\n") as f:
            for p, _d in done:
                f.write(rel(root, p) + "\n")

    print("Done: {} pictures, {} -> {} (saved {}).".format(len(done), mb(before), mb(after), mb(before - after)))
    if a.originals and not a.delete:
        print("Old files kept in {}".format(a.originals))
    return 0


if __name__ == "__main__":
    sys.exit(main())
