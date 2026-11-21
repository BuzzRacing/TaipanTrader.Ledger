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


def generate_image(prompt, prefix, width, height, negative=None, seed=None):
    """Render one image on the farm. Returns (png_bytes, seed). Pass seed to re-render a known picture
    (Media Library "Regen"); leave it out for a fresh random one."""
    prompt = str(prompt or "").strip()
    if len(prompt) < 20:
        raise ImageGenError("Write a prompt before generating.")
    if len(prompt) > 6000:
        raise ImageGenError("The prompt is longer than 6,000 characters.")
    cfg, base, workflow_path = _settings()
    with open(workflow_path, encoding="utf-8") as f:
        workflow = json.load(f)
    seed = int(seed) if isinstance(seed, int) and 0 <= seed < 2 ** 63 else secrets.randbits(48)
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


# ------------------------------------------------------------------ video --
# Anthony, 20 Nov 2026: 10-second looping clips made from a library picture on the farm, with Wan 2.2
# image-to-video in ComfyUI. The workflow file (config/imagegen.json "video" > "workflow") is a ComfyUI
# API-format graph whose inputs may hold placeholders, each a whole string value: "{{IMAGE}}", "{{PROMPT}}",
# "{{NEGATIVE}}", "{{SEED}}", "{{WIDTH}}", "{{HEIGHT}}", "{{FRAMES}}", "{{LAST_FRAME}}", "{{FRAMES_B}}",
# "{{FPS}}", "{{STEPS}}", "{{SPLIT}}", "{{CFG}}", "{{SHIFT}}", "{{PREFIX}}", "{{HIGH_MODEL}}", "{{LOW_MODEL}}",
# "{{TEXT_ENCODER}}", "{{VAE}}", "{{UPSCALE}}", "{{SHARPEN}}". So any Wan workflow (GrumpyRobot's, say) can be dropped in by putting the
# placeholders where those values go. Everything happens on the farm; the Pi only uploads a picture and
# downloads an MP4 (no ffmpeg needed there).
VIDEO_DEFAULTS = {
    "workflow": "imagegen/wan22_i2v_loop.json",
    "model": "Wan 2.2 I2V 14B",
    "high_noise": "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
    "low_noise": "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
    "text_encoder": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
    "vae": "wan_2.1_vae.safetensors",
    "short_side": 480,   # 21 Nov 2026: back to 480 (half the render time of 640) so the PC is free sooner; 640 looked better but took twice as long
    # Wan renders at 16 fps; played back at 16 it looks slightly slow-motion. "fps" is what Wan is asked to
    # render at (keeps each pass at 81 frames), "playback_fps" is how fast the finished clip plays (20 = 25% quicker).
    "fps": 16,
    "playback_fps": 20,
    # 20 Nov 2026 (longer): three Wan passes (picture -> motion -> more motion -> back to the picture), each
    # "pass_frames" long (81 is what Wan 2.2 is trained on). 81 + 79 + 79 = 239 frames = 12 s at 20 fps.
    "pass_frames": 81,
    # 20 Nov 2026 (sharper): the clip is rendered small for speed, then enlarged with Lanczos and lightly
    # sharpened on the farm (core ComfyUI nodes). with a 480 render 1.5 gives 720 x 960 (a 640 render at 1.25 gave 800 x 1060); sharpen 0 switches it off.
    "upscale": 1.5,
    "sharpen": 0.4,
    "steps": 20,
    "split": 10,
    "cfg": 3.5,
    "shift": 8.0,
    "timeout_seconds": 3600,
    "negative_prompt": "blurry, low quality, flicker, jitter, morphing face, melting hands, extra fingers, extra limbs, "
                       "deformed keys, text, watermark, subtitles, extra people, a man, men, static frame",
}
MAX_VIDEO_BYTES = 300 * 1024 * 1024
VIDEO_OUT_EXT = (".mp4", ".webm", ".mov", ".m4v")


def video_settings():
    """The "video" section of config/imagegen.json over the defaults."""
    cfg, base, _wf = _settings()
    v = dict(VIDEO_DEFAULTS)
    if isinstance(cfg.get("video"), dict):
        v.update({k: val for k, val in cfg["video"].items() if k in VIDEO_DEFAULTS})
    path = os.path.abspath(os.path.join(ROOT, str(v["workflow"] or "")))
    if not path.startswith(ROOT + os.sep) or not os.path.isfile(path):
        raise ImageGenError("The video workflow file is missing ({}).".format(v["workflow"]))
    return v, base, path


def _even16(n):
    return max(16, int(round(n / 16.0)) * 16)


def video_size(width, height, short_side):
    """The clip's size: the picture's shape with its short side at short_side, both sides multiples of 16."""
    w, h = int(width or 0), int(height or 0)
    if w <= 0 or h <= 0:
        w, h = 3, 4
    if w <= h:
        return _even16(short_side), _even16(short_side * h / w)
    return _even16(short_side * w / h), _even16(short_side)


def segment_frames(seconds, fps):
    """Frames per Wan pass for a two-pass clip: 4n+1 (Wan's rule), about seconds/2 each."""
    n = max(17, int(round(float(seconds) * fps / 2.0)))
    return (n // 4) * 4 + 1


def pass_frame_count(n):
    """Frames per Wan pass: 4n+1 (Wan's rule), at least 17."""
    return (max(17, int(n)) // 4) * 4 + 1


def fill_placeholders(node, values):
    """Replace every whole-string "{{NAME}}" inside a workflow with its value (keeping numbers as numbers)."""
    if isinstance(node, dict):
        return {k: fill_placeholders(v, values) for k, v in node.items()}
    if isinstance(node, list):
        return [fill_placeholders(v, values) for v in node]
    if isinstance(node, str) and node.startswith("{{") and node.endswith("}}"):
        key = node[2:-2].strip().upper()
        if key in values:
            return values[key]
    return node


def _upload_image(base, path):
    """Send a picture to the farm's ComfyUI input folder. Returns the name LoadImage should use."""
    with open(path, "rb") as f:
        data = f.read()
    name = "seatrader-" + secrets.token_hex(6) + os.path.splitext(path)[1].lower()
    boundary = "----seatrader" + secrets.token_hex(12)
    body = b"".join([
        ("--" + boundary + "\r\n").encode(),
        ('Content-Disposition: form-data; name="image"; filename="' + name + '"\r\n').encode(),
        b"Content-Type: application/octet-stream\r\n\r\n", data, b"\r\n",
        ("--" + boundary + "\r\n").encode(),
        b'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n',
        ("--" + boundary + "--\r\n").encode(),
    ])
    req = Request(base + "/upload/image", data=body, method="POST",
                  headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
    try:
        with urlopen(req, timeout=120) as res:
            out = json.loads(res.read().decode("utf-8"))
    except HTTPError as exc:
        raise ImageGenError("The image farm refused the picture: HTTP {}".format(exc.code)) from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise ImageGenError("The picture could not be sent to the image farm on .213.") from exc
    got = str(out.get("name") or name)
    sub = str(out.get("subfolder") or "")
    return sub + "/" + got if sub else got


def _find_video(history):
    for output in (history.get("outputs") or {}).values():
        for key in ("gifs", "videos", "images", "animated"):
            for f in output.get(key) or []:
                if isinstance(f, dict) and str(f.get("filename") or "").lower().endswith(VIDEO_OUT_EXT):
                    return f
    return None


def generate_video(image_path, motion, width, height, seconds, seed, prefix, progress=None):
    """Make one clip from a picture on disk. Returns (video_bytes, info) where info has ext, model,
    seconds, width, height. motion describes movement only; the look comes from the picture."""
    motion = " ".join(str(motion or "").split())
    if len(motion) < 10:
        raise ImageGenError("Describe the movement (at least 10 characters) first.")
    v, base, wf_path = video_settings()
    with open(wf_path, encoding="utf-8") as f:
        workflow = json.load(f)
    fps = max(8, min(30, int(v["fps"])))
    play_fps = max(8, min(30, int(v["playback_fps"])))
    upscale = max(1.0, min(2.0, float(v["upscale"])))
    sharpen = max(0.0, min(1.5, float(v["sharpen"])))
    w, h = video_size(width, height, int(v["short_side"]))
    frames = pass_frame_count(v["pass_frames"])
    seed = int(seed) if isinstance(seed, int) and 0 <= seed < 2 ** 63 else secrets.randbits(48)
    say = progress or (lambda text: None)
    say("sending the picture")
    name = _upload_image(base, image_path)
    values = {"IMAGE": name, "PROMPT": motion, "NEGATIVE": str(v["negative_prompt"]), "SEED": seed,
              "WIDTH": w, "HEIGHT": h, "FRAMES": frames, "LAST_FRAME": frames - 1, "FRAMES_B": frames - 2,
              "FPS": play_fps, "UPSCALE": upscale, "SHARPEN": sharpen, "STEPS": int(v["steps"]), "SPLIT": int(v["split"]), "CFG": float(v["cfg"]),
              "SHIFT": float(v["shift"]), "PREFIX": prefix, "HIGH_MODEL": v["high_noise"],
              "LOW_MODEL": v["low_noise"], "TEXT_ENCODER": v["text_encoder"], "VAE": v["vae"]}
    workflow = fill_placeholders(workflow, values)
    result = _json(base + "/prompt", "POST", {"prompt": workflow}, 60)
    if result.get("node_errors"):
        raise ImageGenError("The image farm rejected part of the video workflow (missing model or node?): {}".format(
            json.dumps(result.get("node_errors"))[:240]))
    prompt_id = str(result.get("prompt_id") or "")
    if not prompt_id:
        raise ImageGenError("The image farm did not accept the video job.")
    started = time.monotonic()
    deadline = started + int(v["timeout_seconds"])
    found = None
    while time.monotonic() < deadline:
        history = _json(base + "/history/" + prompt_id, timeout=30).get(prompt_id) or {}
        status = history.get("status") or {}
        if status.get("status_str") == "error":
            msgs = [m for m in status.get("messages") or [] if isinstance(m, list) and m and m[0] == "execution_error"]
            why = (msgs[0][1].get("exception_message") or "") if msgs and isinstance(msgs[0][1], dict) else ""
            raise ImageGenError("The image farm could not render the clip. {}".format(str(why)[:200]).strip())
        found = _find_video(history)
        if found:
            break
        say("rendering on the farm, {} min".format(int((time.monotonic() - started) // 60)))
        time.sleep(5)
    if not found:
        raise ImageGenError("The clip took longer than {} minutes to render.".format(int(v["timeout_seconds"]) // 60))
    say("downloading")
    query = urlencode({"filename": found["filename"], "subfolder": found.get("subfolder", ""),
                       "type": found.get("type", "output")})
    try:
        with urlopen(base + "/view?" + query, timeout=300) as res:
            data = res.read(MAX_VIDEO_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ImageGenError("The clip rendered, but could not be downloaded from the image farm.") from exc
    if not data or len(data) > MAX_VIDEO_BYTES:
        raise ImageGenError("The clip file is empty or too large.")
    ext = os.path.splitext(found["filename"])[1].lower()
    total = 3 * frames - 4  # pass 1 whole, then passes 2 and 3 without their first and last frame
    return data, {"ext": ext if ext in VIDEO_OUT_EXT else ".mp4", "model": str(v["model"])[:40],
                  "seconds": int(round(total / float(play_fps))),
                  "width": int(round(w * upscale)), "height": int(round(h * upscale))}
