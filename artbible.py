"""Example images for the Art Bible page, rendered on the local AI farm.

Each Art Bible entry (north star, light, material, people tiers I-II and the
asset specs) has one example image. Images live in web/assets/artbible/ with a
manifest.json beside them that records the prompt, negative, model, seed,
size, sampler and date, so every example can be reproduced or replaced.

The examples use the Art Bible's family-friendly style and negative prompt,
so they are safe to show in either content mode.
"""
import json
import os
import re
import secrets
import threading
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from imagegen import ImageGenError

ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(ROOT, "config", "imagegen.json")
OUT_DIR = os.path.join(ROOT, "web", "assets", "artbible")
MANIFEST = os.path.join(OUT_DIR, "manifest.json")
MAX_IMAGE_BYTES = 24 * 1024 * 1024
LOCK = threading.Lock()

# The ComfyUI on this machine that renders SDXL art (the portrait workflow uses its own address).
DEFAULT_BASE = "http://127.0.0.1:8188"
DEFAULT_CHECKPOINT = "juggernautXL_ragnarokBy.safetensors"
FARM_SUBFOLDER = "SeaTrader/artbible"

STYLE = ("romanticized cinematic historical realism set in the China Seas in 1860, family-friendly maritime "
         "adventure with confident fully dressed adult characters, humid salt haze, natural skin, believable "
         "anatomy, weathered maritime materials, lacquer black, oxblood silk, antique brass, imperial jade, ivory "
         "and storm blue, premium tabletop-game key art, richly textured, dramatic but plausible lighting")
NEGATIVE = ("minor, teen, child, youthful face, school uniform, age ambiguity, modern clothing, zipper, latex, "
            "stiletto heel, modern ship, electric light, generic fantasy armor, steampunk machinery, cosplay "
            "plastic, Halloween costume, racial caricature, generic Orientalism, faux Asian lettering, random "
            "dragon motif, plastic skin, airbrushed anatomy, doll face, extra fingers, malformed hands, duplicate "
            "limbs, explicit sexual act, sexual violence, coercion, non-consensual scenario, text, logo, caption, "
            "border, signature, watermark, nudity, exposed breasts, exposed genitals, erotic pose, fetishwear, "
            "bondage, kink imagery")

# SDXL-native render sizes for each master aspect ratio.
SIZES = {"16:9": (1344, 768), "3:1": (1536, 512), "18:7": (1536, 592), "3:2": (1216, 832),
         "1:1": (1024, 1024), "3:4": (864, 1152)}

# id: (aspect ratio, first seed, subject)
EXAMPLES = {
    "ns-world": ("16:9", 186001, "crowded Qing-era treaty port in 1860, junks, clippers and an early coastal paddle "
                 "steamer at anchor, warehouses and godowns on the waterfront, monsoon clouds"),
    "ns-fantasy": ("3:4", 186002, "an unmistakably adult (age 35) merchant-captain standing on a lantern-lit "
                   "quarterdeck at night, open collar, rolled sleeves, commanding eye contact, silk sash and "
                   "leather belt, hands on a brass spyglass, fully dressed"),
    "ns-promise": ("16:9", 186003, "lacquered table piled with silver coins, an open ledger, customs seals and a "
                   "porcelain cup, cannon smoke drifting past a porthole with a rival ship on the stormy horizon"),
    "lt-golden": ("16:9", 186004, "a teak trading clipper entering harbor, golden hour through humid salt haze, "
                  "warm rim light on sails and rigging"),
    "lt-lantern": ("16:9", 186005, "a waterfront wharf at night, warm lantern pools against cool blue sea shadow, "
                   "cargo crates and coiled rope"),
    "lt-monsoon": ("16:9", 186006, "a rain-soaked harbor quay under monsoon overcast, wet specular highlights on "
                   "stone, tarpaulins and junk sails"),
    "lt-storm": ("16:9", 186007, "storm breaking over the South China Sea, a single shaft of sunlight striking a "
                 "barque under reefed sails, dark storm blue sea"),
    "mat-still": ("1:1", 186008, "still life of salt-stained teak, tarred rope, a hammered patinated brass compass, "
                  "worn black-brown leather satchel, heavy oxblood silk, ivory linen and a celadon porcelain bowl"),
    "tier1": ("3:4", 186009, "an unmistakably adult (age 32) woman harbor agent in a lantern-lit market at dusk, "
              "damp hair, fitted waist, open-collared linen shirt and dark waistcoat, close confident eye contact, "
              "restrained sensuality through gaze, tailoring and posture, hands visible holding a ledger, "
              "fully dressed"),
    "tier2": ("3:4", 186010, "an unmistakably adult (age 34) trading-house proprietor in a candlelit counting room, "
              "oxblood silk gown with corsetry and a deep neckline, commanding pose, one hand resting on a brass "
              "strongbox, adult glamour, fully dressed"),
    "as-masthead": ("3:1", 186011, "panoramic China Seas harbor at dusk with a clipper in the right third, dark "
                    "quiet negative space on the left and center for a title"),
    "as-bg": ("16:9", 186012, "low-contrast misty harbor at dawn, soft detail only at the edges, quiet empty center, "
              "no people"),
    "as-port": ("18:7", 186013, "Victoria Harbour Hong Kong in 1860, Victoria Peak and colonial waterfront "
                "buildings, junks and clippers, horizon in the upper third, environment only, no close foreground "
                "people"),
    "as-ship": ("3:2", 186014, "a full tea clipper in bow three-quarter view under full sail, the whole vessel "
                "silhouette in frame, brisk weather, spray at the bow"),
    "as-cargo": ("1:1", 186015, "a single cluster of blue-and-white Chinese export porcelain vases and bowls in a "
                 "straw-packed crate, three-quarter view, plain dark ground, clear silhouette"),
    "as-char": ("3:4", 186016, "an unmistakably adult (age 40) merchant-captain negotiating on a wharf in Shanghai, "
                "knees-up framing, hands visible over a cargo manifest, period frock coat and waistcoat, "
                "fully dressed"),
}
SAMPLER = {"steps": 30, "cfg": 4.5, "sampler_name": "dpmpp_2m_sde", "scheduler": "karras"}


def _settings():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        cfg = {}
    base = str(cfg.get("artbible_base_url") or DEFAULT_BASE).strip().rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ImageGenError("The Art Bible image farm address is not valid.")
    return {"base": base,
            "checkpoint": str(cfg.get("artbible_checkpoint") or DEFAULT_CHECKPOINT),
            "timeout": int(cfg.get("timeout_seconds") or 300),
            "poll": max(1, int(cfg.get("poll_seconds") or 2))}


def _json(url, method="GET", body=None, timeout=30):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read(400).decode("utf-8", "replace")
        raise ImageGenError("The image farm refused the job: HTTP {} {}".format(exc.code, detail)) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ImageGenError("The image farm (ComfyUI) cannot be reached. Is START Image Gen running?") from exc
    except ValueError as exc:
        raise ImageGenError("The image farm returned an unreadable response.") from exc


def _download(base, filename, subfolder):
    query = urlencode({"filename": filename, "subfolder": subfolder, "type": "output"})
    try:
        with urlopen(base + "/view?" + query, timeout=60) as res:
            data = res.read(MAX_IMAGE_BYTES + 1)
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise ImageGenError("The image could not be downloaded from the farm.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ImageGenError("The image farm (ComfyUI) cannot be reached. Is START Image Gen running?") from exc
    if not data or len(data) > MAX_IMAGE_BYTES or not data.startswith(b"\x89PNG"):
        raise ImageGenError("The farm returned an empty or unreadable image.")
    return data


def _check_id(example_id):
    example_id = str(example_id or "")
    if not re.match(r"^[a-z0-9-]{1,24}$", example_id) or example_id not in EXAMPLES:
        raise ImageGenError("That Art Bible example is not known.")
    return example_id


def load_manifest():
    try:
        with open(MANIFEST, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(example_id, data, seed, settings, source):
    ratio, _, subject = EXAMPLES[example_id]
    width, height = SIZES[ratio]
    os.makedirs(OUT_DIR, exist_ok=True)
    with LOCK:
        manifest = load_manifest()
        old = (manifest.get(example_id) or {}).get("file")
        version = int((manifest.get(example_id) or {}).get("version") or 0) + 1
        fname = "historical_{}_v{:02d}.png".format(example_id, version)
        tmp = os.path.join(OUT_DIR, fname + ".tmp")
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, os.path.join(OUT_DIR, fname))
        manifest[example_id] = {
            "file": fname, "version": version, "source": source, "mode": "historical-family-safe",
            "prompt": subject + ", " + STYLE, "negative": NEGATIVE, "model": settings["checkpoint"],
            "workflow": "SDXL txt2img (artbible.py)", "seed": seed, "width": width, "height": height,
            "aspect": ratio, "sampler": SAMPLER["sampler_name"], "scheduler": SAMPLER["scheduler"],
            "steps": SAMPLER["steps"], "cfg": SAMPLER["cfg"], "bytes": len(data),
            "date": datetime.now().isoformat(timespec="seconds")}
        tmp = MANIFEST + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=1, ensure_ascii=False)
        os.replace(tmp, MANIFEST)
        if old and old != fname:      # keep the folder tidy; the manifest holds the recipe
            try:
                os.remove(os.path.join(OUT_DIR, os.path.basename(old)))
            except OSError:
                pass
        return manifest[example_id]


def import_from_farm(example_id):
    """Pull the first render of this example that is already sitting in the farm's output folder."""
    example_id = _check_id(example_id)
    settings = _settings()
    data = _download(settings["base"], "historical_{}_00001_.png".format(example_id), FARM_SUBFOLDER)
    if data is None:
        raise ImageGenError("No render of this example is waiting on the farm yet.")
    return _save(example_id, data, EXAMPLES[example_id][1], settings, "imported")


def generate(example_id):
    """Render a fresh take on this example with a new seed and keep it."""
    example_id = _check_id(example_id)
    settings = _settings()
    ratio, _, subject = EXAMPLES[example_id]
    width, height = SIZES[ratio]
    seed = secrets.randbits(40)
    workflow = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": settings["checkpoint"]}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": subject + ", " + STYLE}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": NEGATIVE}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": dict(SAMPLER, model=["1", 0], positive=["2", 0],
                                                        negative=["3", 0], latent_image=["4", 0],
                                                        seed=seed, denoise=1.0)},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0],
                                                     "filename_prefix": FARM_SUBFOLDER + "/regen_" + example_id}},
    }
    result = _json(settings["base"] + "/prompt", "POST", {"prompt": workflow})
    if result.get("node_errors"):
        raise ImageGenError("The image farm rejected the workflow (is {} installed?).".format(settings["checkpoint"]))
    prompt_id = str(result.get("prompt_id") or "")
    if not prompt_id:
        raise ImageGenError("The image farm did not accept the job.")
    deadline = time.monotonic() + settings["timeout"]
    image = None
    while time.monotonic() < deadline and not image:
        history = _json(settings["base"] + "/history/" + prompt_id).get(prompt_id) or {}
        if (history.get("status") or {}).get("status_str") == "error":
            raise ImageGenError("The image farm could not render that example.")
        for output in (history.get("outputs") or {}).values():
            if output.get("images"):
                image = output["images"][0]
                break
        if not image:
            time.sleep(settings["poll"])
    if not image:
        raise ImageGenError("The example took too long to render.")
    data = _download(settings["base"], image["filename"], image.get("subfolder", ""))
    if data is None:
        raise ImageGenError("The example rendered, but the file could not be found on the farm.")
    return _save(example_id, data, seed, settings, "generated")
