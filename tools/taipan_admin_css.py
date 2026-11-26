"""Builds web/taipan-admin.css: the Admin pages recoloured from Crimson Ledger's lacquer and brass to Taipan
Trader's indigo, jade and porcelain blue, with Taipan's fonts.

The Admin stylesheets stay exactly as Crimson Ledger ships them, so merges from Crimson Ledger stay clean. This
reads them, and for every rule that names a colour writes the same rule again with the colour moved into Taipan's
palette. web/admin.html loads the result last. Run it again after a merge from Crimson Ledger:
    python tools/taipan_admin_css.py
"""
import colorsys
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
SOURCES = ["admin.css", "media-admin.css", "captains.css", "voice-library.css", "voice-clips.css",
           "banks-admin.css", "certificate-studio.css"]
OUT = os.path.join(WEB, "taipan-admin.css")

HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
RGBA = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)")
COLOR_WORD = re.compile(r"#[0-9a-fA-F]{3,6}\b|rgba?\(")

ROOT_VARS = """:root {
  --bg: #0d1a22; --panel: #142a37; --panel-2: #1b3545; --line: #2d5163; --ink: #e6efe8; --muted: #9db3ad;
  --brass: #d9a441; --red: #c0533a; --green: #5fbf9b; --field: #0f2029;
  --title: "IM Fell English SC", "Palatino Linotype", Palatino, Georgia, serif;
  --serif: "IM Fell English SC", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif;
  --sans: "Libre Caslon Text", "Palatino Linotype", Palatino, Georgia, serif;
  --special: "IM Fell English SC", "Palatino Linotype", Palatino, Georgia, serif;
}
"""


def shift(r, g, b):
    """One colour into Taipan's palette. Browns and lacquer become indigo and sea blue, tans become jade grey,
    parchment becomes porcelain white. Brass and gold stay (sail ochre); reds stay (warnings)."""
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    deg = h * 360
    if s < 0.06 or (deg < 12 or deg > 340) and s > 0.45:          # greys, blacks, whites and true reds
        return r, g, b
    if 12 <= deg <= 55:
        if l < 0.38:                                                # lacquer, teak, dark leather
            h, s = 203 / 360, min(0.55, s * 0.9 + 0.08)
        elif l < 0.62 and s < 0.5:                                  # tans and muted browns
            h, s = 165 / 360, s * 0.55
        elif l >= 0.8:                                              # parchment and cream
            h, s = 110 / 360, s * 0.35
        else:                                                       # brass and gold: keep, as sail ochre
            return r, g, b
    rr, gg, bb = colorsys.hls_to_rgb(h, l, s)
    return round(rr * 255), round(gg * 255), round(bb * 255)


def recolour(value):
    def hx(m):
        v = m.group(1)
        if len(v) == 3:
            v = "".join(c * 2 for c in v)
        r, g, b = (int(v[i:i + 2], 16) for i in (0, 2, 4))
        return "#{:02x}{:02x}{:02x}".format(*shift(r, g, b))

    def rgba(m):
        r, g, b = shift(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return "rgba({},{},{},{})".format(r, g, b, m.group(4)) if m.group(4) else "rgb({},{},{})".format(r, g, b)

    return RGBA.sub(rgba, HEX.sub(hx, value))


def blocks(css):
    """(prelude, body) pairs at this level, nesting kept in the body."""
    out, depth, mark, start, prelude = [], 0, 0, 0, ""
    for i, c in enumerate(css):
        if c == "{":
            if depth == 0:
                prelude, start = css[mark:i].strip(), i + 1
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                out.append((prelude, css[start:i]))
                mark = i + 1
        elif c == ";" and depth == 0:
            mark = i + 1
    return out


def rules(css):
    lines = []
    for pre, body in blocks(css):
        if pre.startswith("@media") or pre.startswith("@supports"):
            inner = rules(body)
            if inner:
                lines.append(pre + " {\n" + "\n".join("  " + x for x in inner) + "\n}")
        elif pre.startswith("@") or pre.startswith(":root"):
            continue
        else:
            decls = [d.strip() for d in body.split(";") if ":" in d and COLOR_WORD.search(d)]
            new = []
            for d in decls:
                prop, val = d.split(":", 1)
                if prop.strip().startswith("--"):
                    continue
                v2 = recolour(val.strip())
                if v2 != val.strip():
                    new.append("{}: {}".format(prop.strip(), v2))
            if new:
                lines.append("{} {{ {}; }}".format(pre, "; ".join(new)))
    return lines


def main():
    parts = ["/* Taipan Trader Admin: indigo, jade and porcelain blue over Crimson Ledger's admin stylesheets.\n"
             "   Made by tools/taipan_admin_css.py; edit that, not this file. */", ROOT_VARS]
    for name in SOURCES:
        path = os.path.join(WEB, name)
        if not os.path.isfile(path):
            continue
        css = re.sub(r"/\*.*?\*/", "", open(path, encoding="utf-8").read(), flags=re.S)
        got = rules(css)
        if got:
            parts.append("/* from {} */".format(name))
            parts.extend(got)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(parts) + "\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
