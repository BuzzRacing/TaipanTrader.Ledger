"""Render Taipan artwork to a review folder without publishing it to the game."""
import argparse
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cast
import imagegen
import persona_prompts_v2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cast", action="store_true", help="Render the missing male cast portraits.")
    parser.add_argument("--persona", action="append", choices=sorted(persona_prompts_v2.LOOKS),
                        help="Render a specific persona. Repeat for additional portraits.")
    parser.add_argument("--replacements", action="store_true", help="Fill public roles left empty by the prompt audit.")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    def render(name, prompt, width, height, seed, reference=None):
        path = args.output / (name + ".png")
        if path.exists():
            return path
        start = time.monotonic()
        print(f"Rendering {name} ({width}x{height})", flush=True)
        data, _ = imagegen.generate_image(prompt, "taipan/pilot-" + name, width, height,
                                         seed=seed, reference_path=reference)
        actual = struct.unpack(">II", data[16:24])
        if actual != (width, height):
            raise RuntimeError(f"{name} returned {actual}, expected {(width, height)}")
        path.write_bytes(data)
        print(f"{name}: {actual[0]}x{actual[1]}, {time.monotonic() - start:.1f}s", flush=True)
        return path

    if args.cast or args.persona or args.replacements:
        cast_order = sorted(cast.MEN)
        for key in cast_order if args.cast else args.persona or []:
            seed = 186100 + cast_order.index(key) if key in cast.MEN else 186199
            render(key, persona_prompts_v2.build(key), 1024, 1360, seed)
        if args.replacements:
            library = json.loads((ROOT / "config" / "media.json").read_text(encoding="utf-8"))
            items = library["items"]

            def slot(item):
                return item["kind"], item["subject"], tuple(item["roles"])

            covered = {slot(it) for it in items if it["enabled"] and not it["nsfw"]}
            for i, item in enumerate(items):
                kind, subject, roles = slot(item)
                if not item["nsfw"] or slot(item) in covered or kind == "reference" or not item["prompt"]:
                    continue
                name = f"{kind}-{subject}-{'-'.join(roles) or 'main'}"
                width, height = imagegen.ASPECTS["16:9" if kind == "port" else "3:4"]
                render(name, item["prompt"], width, height, 187000 + i)
                covered.add(slot(item))
        return

    prompt = persona_prompts_v2.build("shipwright")
    anchor = render("shipwright-2k", prompt, 1536, 2048, 186060)
    render("shipwright-speaking-2k", prompt + ", speaking mid-sentence with a warm, animated expression",
           1536, 2048, 186061, anchor)
    render("hong-kong-2k", "A wide cinematic historical illustration of Victoria Harbour, Hong Kong, 1860. "
           "A three-masted tea clipper lies beyond two batten-sailed wooden junks. In the foreground, "
           "fully dressed women and men work with tea chests beside a weathered teak wharf. "
           "Victoria Peak rises behind the layered waterfront in warm monsoon haze. No readable lettering.",
           2048, 1152, 186062)


if __name__ == "__main__":
    main()
