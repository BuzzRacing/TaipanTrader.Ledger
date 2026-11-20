"""Scan a music or effects folder and write a CSV of what is in it: file, folder, format, size, duration and,
when ffmpeg is installed, loudness. Speeds up choosing and levelling sounds.

Run:  python tools/audio_inventory.py "D:\\path\\to\\Total Music Collection" inventory.csv
      add --no-loudness to skip the (slower) loudness pass."""
import csv
import json
import os
import re
import shutil
import subprocess
import sys

EXT = (".mp3", ".m4a", ".ogg", ".opus", ".wav", ".flac", ".aif", ".aiff")


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_name,sample_rate,channels",
                        "-of", "json", path], capture_output=True, text=True)
    try:
        j = json.loads(r.stdout)
        s = (j.get("streams") or [{}])[0]
        return float(j["format"]["duration"]), s.get("codec_name", ""), s.get("sample_rate", ""), s.get("channels", "")
    except (ValueError, KeyError, json.JSONDecodeError):
        return 0.0, "", "", ""


def loudness(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    try:
        j = json.loads(m.group(0))
        return float(j["input_i"]), float(j["input_tp"])
    except (AttributeError, ValueError, KeyError):
        return "", ""


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__)
        return 2
    root, out = args
    have = shutil.which("ffprobe") is not None
    want_loud = have and shutil.which("ffmpeg") is not None and "--no-loudness" not in argv
    if not have:
        print("ffprobe not found: durations and loudness will be blank")
    rows = []
    for dirpath, _dirs, files in os.walk(root):
        for name in sorted(files):
            if not name.lower().endswith(EXT):
                continue
            p = os.path.join(dirpath, name)
            dur, codec, rate, ch = probe(p) if have else (0.0, "", "", "")
            lufs, tp = loudness(p) if want_loud else ("", "")
            rows.append([os.path.relpath(p, root), os.path.splitext(name)[1].lower(), os.path.getsize(p), round(dur, 1), codec, rate, ch, lufs, tp])
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "format", "bytes", "seconds", "codec", "sample_rate", "channels", "lufs", "true_peak_db"])
        w.writerows(rows)
    print("wrote %d files to %s" % (len(rows), out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
