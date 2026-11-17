"""Generate SeaTrader images (cast portraits, Art Bible examples) through the local AI farm."""
import json
import os
import secrets
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(ROOT, "config", "imagegen.json")
MAX_IMAGE_BYTES = 16 * 1024 * 1024


class ImageGenError(Exception):
    pass


def _settings():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError) as exc:
        raise ImageGenError("Image generation is not configured correctly.") from exc
    base = str(cfg.get("base_url") or "").strip().rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ImageGenError("The image farm address is not valid.")
    workflow = os.path.abspath(os.path.join(ROOT, str(cfg.get("workflow") or "")))
    if not workflow.startswith(ROOT + os.sep) or not os.path.isfile(workflow):
        raise ImageGenError("The portrait workflow file is missing.")
    return cfg, base, workflow


def _json(url, method="GET", body=None, timeout=30):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read(400).decode("utf-8", "replace")
        raise ImageGenError("The image farm refused the portrait: HTTP {} {}".format(exc.code, detail)) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ImageGenError("The image farm on .213 cannot be reached.") from exc
    except ValueError as exc:
        raise ImageGenError("The image farm returned an unreadable response.") from exc


# Pixel sizes per aspect ratio: about one megapixel, every side a multiple of 16.
ASPECTS = {
    "16:5": (1600, 512),
    "1:1": (1024, 1024),
    "3:1": (1776, 592),
    "16:9": (1360, 768),
    "5:3": (1280, 768),
    "18:7": (1664, 640),
    "3:2": (1248, 832),
    "3:4": (1024, 1360),
}


def generate_portrait(prompt, character):
    cfg, _base, _workflow = _settings()
    data, _seed = generate_image(prompt, "seatrader/portrait-{}".format(character),
                                 int(cfg.get("width") or 1024), int(cfg.get("height") or 1360))
    return data


def generate_image(prompt, prefix, width, height, negative=None):
    """Render one image on the farm. Returns (png_bytes, seed)."""
    prompt = str(prompt or "").strip()
    if len(prompt) < 20:
        raise ImageGenError("Write a prompt before generating.")
    if len(prompt) > 6000:
        raise ImageGenError("The prompt is longer than 6,000 characters.")
    cfg, base, workflow_path = _settings()
    with open(workflow_path, encoding="utf-8") as f:
        workflow = json.load(f)
    seed = secrets.randbits(48)
    neg = str(cfg.get("negative_prompt") or "") if negative is None else str(negative)[:4000]
    workflow["4"]["inputs"]["prompt"] = prompt
    workflow["4"]["inputs"]["negative_prompt"] = neg
    workflow["5"]["inputs"]["width"] = int(width)
    workflow["5"]["inputs"]["height"] = int(height)
    workflow["7"]["inputs"]["seed"] = seed
    workflow["7"]["inputs"]["steps"] = int(cfg.get("steps") or 25)
    workflow["9"]["inputs"]["filename_prefix"] = prefix

    result = _json(base + "/prompt", "POST", {"prompt": workflow}, 30)
    if result.get("node_errors"):
        raise ImageGenError("The image farm rejected part of the workflow.")
    prompt_id = str(result.get("prompt_id") or "")
    if not prompt_id:
        raise ImageGenError("The image farm did not accept the job.")

    deadline = time.monotonic() + int(cfg.get("timeout_seconds") or 300)
    poll = max(1, int(cfg.get("poll_seconds") or 2))
    image = None
    while time.monotonic() < deadline:
        history = _json(base + "/history/" + prompt_id, timeout=30).get(prompt_id) or {}
        status = history.get("status") or {}
        if status.get("status_str") == "error":
            raise ImageGenError("The image farm could not render that image.")
        for output in (history.get("outputs") or {}).values():
            images = output.get("images") or []
            if images:
                image = images[0]
                break
        if image:
            break
        time.sleep(poll)
    if not image:
        raise ImageGenError("The image took longer than five minutes to render.")

    query = urlencode({"filename": image["filename"], "subfolder": image.get("subfolder", ""),
                       "type": image.get("type", "output")})
    try:
        with urlopen(base + "/view?" + query, timeout=60) as res:
            data = res.read(MAX_IMAGE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ImageGenError("The image rendered, but could not be downloaded from the image farm.") from exc
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ImageGenError("The generated image file is empty or too large.")
    return data, seed
