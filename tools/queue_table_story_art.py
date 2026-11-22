"""Fill missing Table compositions using the game's existing AI-farm queue and Media Library."""
import argparse
import json
from pathlib import Path
import urllib.request

STYLE = (", romantic cinematic historical realism, China Seas in 1860, period-correct materials and dress, "
         "natural skin, luxurious salt-dark teak, oxblood silk, antique brass, imperial jade, ivory, "
         "warm lantern light against cool sea light, dramatic painterly depth, no text, no letters, "
         "no watermark, no border, no UI, no modern objects, fully clothed adult glamour")
GM = ("Madame Anahit Sarkissian, an Armenian woman aged 44 from Calcutta, dark hair swept up with gold pins, "
      "burgundy tailcoat over a fitted black corset, white satin gloves, gold waistcoat chain, "
      "witty commanding seductive smile, the croupier-auctioneer mistress of a trading game aboard an 1860 ship")
JOBS = [
    ("persona", "gamemaster", ["wallpaper", "speaking"], "table-host", "3:4",
     GM + ", knees-up portrait at the head of the captain's gaming table, ringing a brass bell once, "
     "a dice-topped gavel beside her, eyes on the viewer, head and both hands fully in frame, generous headroom"),
    ("persona", "gamemaster", ["sly"], "table-sly", "3:4",
     GM + ", knees-up portrait leaning one gloved hand on the teak table, eyebrow raised at the viewer, "
     "one eyebrow promising trouble, poised to unveil a wager, head and hands fully in frame"),
    ("persona", "gamemaster", ["happy"], "table-happy", "3:4",
     GM + ", knees-up portrait with a delighted cutting smile, presenting a fan of sealed House orders, "
     "brass bell at her elbow, an auctioneer crowning a successful captain, head and hands fully in frame"),
    ("persona", "narrator", ["storm"], "table-storm", "3:4",
     "Roxana Cama, commanding Parsi woman aged 41, black Parsi topi, black frock coat over an ivory "
     "angrakha-cut corset and oxblood sash, gripping a wet brass rail and black logbook, brass chronometer, "
     "rain and wind on the quarterdeck, defiant steady gaze, knees-up portrait, head and hands fully in frame"),
    ("persona", "bosun", ["angry", "speaking"], "table-angry", "3:4",
     "Peggy Powder O'Rourke, Irish woman aged 34, red hair blowing loose, tobacco leather waistcoat over "
     "an open-collared linen shirt, oxblood sash, fierce delighted grin beside a smoking brass cannon, "
     "slow match in one hand, powder marks on her sleeves, knees-up portrait, head and hands fully in frame"),
    ("scene", "loading", ["background"], "table-cabin", "16:9",
     "The sumptuous stern cabin of an 1860 China Seas merchant clipper, no people, broad polished dark "
     "teak gaming table in the foreground, rich jade and oxblood silk at its edges, antique brass lanterns, "
     "stern windows revealing cold moonlit sea and rigging, restrained carved cabinetry, quiet dark centre "
     "for a separate game board, cinematic depth, no map or board painted into the picture"),
]


def request(server, path, body=None):
    req = urllib.request.Request(server + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "X-SeaTrader": "admin"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--server", required=True)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    server = args.server.rstrip("/")
    library = request(server, "/api/info")["media"]["items"]
    receipts = []
    for kind, subject, roles, tag, aspect, prompt in JOBS:
        if any(tag in item.get("g", []) for item in library.get(kind, {}).get(subject, [])):
            print(tag + ": gallery already has this composition")
            continue
        job = dict(kind=kind, subject=subject, roles=roles, tags="table-story, " + tag,
                   aspect=aspect, prompt=prompt + STYLE, nsfw="no", count=1)
        result = {"ok": True, "dry": True} if args.dry else request(server, "/api/admin/media/generate", job)
        receipts.append({"tag": tag, "job": job, "result": result})
        print(tag + ": " + json.dumps(result, ensure_ascii=True))
        if not result.get("ok"):
            raise SystemExit("The farm queue rejected " + tag)
    if not args.dry:
        path = Path(__file__).resolve().parents[1] / "design" / "table-concepts-v01" / "farm-queue.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(receipts, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
