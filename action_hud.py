# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "flask",
#     "mss",
#     "numpy",
#     "pillow",
# ]
# ///

import argparse
import ctypes
import json
import logging
import os
import socket
import sys
import ssl
import urllib.request
import threading
import time
from collections import deque
from pathlib import Path

import mss
import numpy as np
from flask import Flask, Response, stream_with_context
from PIL import Image

# ---------------- CONFIG ---------------- #

ATTACK_MOVE_KEY = "a"
ATTACK_MOVE_WINDOW = 1.5
Q_SAME_WEAPON_REPEAT_GUARD = 1.5

MAX_HISTORY = 8
ACTION_TTL = 10.0

# Real capture starts only after this has been replaced by saved calibration.
Q_REGION = {"top": 0, "left": 0, "width": 32, "height": 32}

# A 36px HUD slot looks crisp with 2x assets and avoids decoding huge PNGs in OBS.
HUD_ICON_SIZE = 72
HUD_ICON_PADDING = 4
ENTRY_SIZE_PX = 42

# Input polling via GetAsyncKeyState is much cheaper than global hook libraries.
INPUT_POLL_HZ = 125

# Kill detection reads League's local Live Client Data API (only available while in a game).
LIVE_CLIENT_URL = "https://127.0.0.1:2999/liveclientdata"
KILL_POLL_SECONDS = 0.5

HOST = "127.0.0.1"
PORT = 5002
VERSION = "0.2.0-beta.2"

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
OPTIMIZED_DIR = STATIC_DIR / "hud_small"

SOURCE_ICONS = {
    "q_calibrum": STATIC_DIR / "q_calibrum.png",
    "q_severum": STATIC_DIR / "q_severum.png",
    "q_gravitum": STATIC_DIR / "q_gravitum.png",
    "q_infernum": STATIC_DIR / "q_infernum.png",
    "q_crescendum": STATIC_DIR / "q_crescendum.png",
    "w": STATIC_DIR / "w_hd.png",
    "r": STATIC_DIR / "r_hd.png",
    "aa": STATIC_DIR / "aa_hd.png",
}

logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")
logging.getLogger("werkzeug").setLevel(logging.ERROR)
log = logging.getLogger("aphelios_hud")

app = Flask(__name__, static_url_path="/static", static_folder=str(STATIC_DIR))

# ---------------- STATE ---------------- #

history = deque(maxlen=MAX_HISTORY)
state_lock = threading.Lock()
state_changed = threading.Condition(state_lock)
state_version = 0
action_counter = 0
kill_count = 0

templates = []
ctypes.windll.user32.SetProcessDPIAware()
screen_capture = None
monitor_q = dict(Q_REGION)

user32 = ctypes.WinDLL("user32", use_last_error=True)
GetAsyncKeyState = user32.GetAsyncKeyState
GetAsyncKeyState.argtypes = [ctypes.c_int]
GetAsyncKeyState.restype = ctypes.c_short

VK_LBUTTON = 0x01
VK_A = ord(ATTACK_MOVE_KEY.upper())
VK_Q = 0x51
VK_W = 0x57
VK_R = 0x52

ICON_URLS = {
    "q_calibrum": "/static/hud_small/q_calibrum.png",
    "q_severum": "/static/hud_small/q_severum.png",
    "q_gravitum": "/static/hud_small/q_gravitum.png",
    "q_infernum": "/static/hud_small/q_infernum.png",
    "q_crescendum": "/static/hud_small/q_crescendum.png",
    "w": "/static/hud_small/w.png",
    "r": "/static/hud_small/r.png",
    "aa": "/static/hud_small/aa.png",
}

WEAPON_TEMPLATES = [
    ("Calibrum", SOURCE_ICONS["q_calibrum"], ICON_URLS["q_calibrum"]),
    ("Severum", SOURCE_ICONS["q_severum"], ICON_URLS["q_severum"]),
    ("Gravitum", SOURCE_ICONS["q_gravitum"], ICON_URLS["q_gravitum"]),
    ("Infernum", SOURCE_ICONS["q_infernum"], ICON_URLS["q_infernum"]),
    ("Crescendum", SOURCE_ICONS["q_crescendum"], ICON_URLS["q_crescendum"]),
]


# ---------------- ASSETS ---------------- #

def _resample_filter():
    return getattr(Image, "Resampling", Image).LANCZOS


def ensure_small_icons():
    OPTIMIZED_DIR.mkdir(parents=True, exist_ok=True)
    for name, src in SOURCE_ICONS.items():
        dst = OPTIMIZED_DIR / f"{name}.png"
        img = Image.open(src).convert("RGBA")
        alpha_box = img.getchannel("A").getbbox()
        if alpha_box:
            img = img.crop(alpha_box)

        max_size = HUD_ICON_SIZE - (HUD_ICON_PADDING * 2)
        scale = max_size / max(img.width, img.height)
        resized_size = (
            max(1, round(img.width * scale)),
            max(1, round(img.height * scale)),
        )
        img = img.resize(resized_size, _resample_filter())
        canvas = Image.new("RGBA", (HUD_ICON_SIZE, HUD_ICON_SIZE), (0, 0, 0, 0))
        x = (HUD_ICON_SIZE - img.width) // 2
        y = (HUD_ICON_SIZE - img.height) // 2
        canvas.alpha_composite(img, (x, y))
        canvas.save(dst, "PNG", optimize=True)


def load_templates():
    global templates
    loaded = []
    size = (Q_REGION["width"], Q_REGION["height"])

    for weapon_name, path, icon_url in WEAPON_TEMPLATES:
        try:
            img = Image.open(path).convert("L").resize(size, _resample_filter())
        except Exception as exc:
            log.warning("Could not load template %s: %s", path, exc)
            continue
        loaded.append((weapon_name, normalize_match_image(np.array(img)), icon_url))

    templates = loaded
    log.warning("Loaded %d Q templates.", len(templates))


# ---------------- INPUT / CLASSIFYING ---------------- #

def is_pressed(vk_code):
    return bool(GetAsyncKeyState(vk_code) & 0x8000)


def normalize_match_image(image):
    data = image.astype(np.float32)
    data -= float(data.mean())
    norm = float(np.linalg.norm(data))
    if norm <= 0.0001:
        return data
    return data / norm


def grab_q_gray():
    shot = np.array(screen_capture.grab(monitor_q))  # BGRA
    blue = shot[:, :, 0].astype(np.float32)
    green = shot[:, :, 1].astype(np.float32)
    red = shot[:, :, 2].astype(np.float32)
    gray = (0.114 * blue) + (0.587 * green) + (0.299 * red)
    return normalize_match_image(gray)


def classify_q_from_screen():
    if not templates:
        return "Q", ICON_URLS["q_calibrum"]

    try:
        frame = grab_q_gray()
    except Exception as exc:
        log.warning("Could not capture Q region: %s", exc)
        return "Q", ICON_URLS["q_calibrum"]

    best_name = "Q"
    best_icon = ICON_URLS["q_calibrum"]
    best_score = -1.0

    for name, tmpl, icon_url in templates:
        score = float(np.sum(frame * tmpl))
        if score > best_score:
            best_name = name
            best_icon = icon_url
            best_score = score

    return best_name, best_icon


def prune_expired_locked(now):
    global state_version
    changed = False
    while history and now - history[-1]["time"] > ACTION_TTL:
        history.pop()
        changed = True
    if changed:
        state_version += 1
        state_changed.notify_all()
    return changed


def kind_for_weapon(weapon_name):
    return f"weapon-{weapon_name.lower()}"


def add_action(label, icon, kind):
    global action_counter, state_version
    now = time.monotonic()
    with state_changed:
        action_counter += 1
        history.appendleft({
            "id": action_counter,
            "label": label,
            "icon": icon,
            "kind": kind,
            "time": now,
        })
        prune_expired_locked(now)
        state_version += 1
        state_changed.notify_all()


class InputCommandGuard:
    def __init__(self):
        self.attack_move_armed_at = None
        self.last_q_press_by_weapon = {}

    def arm_attack_move(self, now):
        self.attack_move_armed_at = now

    def consume_attack_click(self, now):
        armed_at = self.attack_move_armed_at
        self.attack_move_armed_at = None
        return armed_at is not None and 0 <= now - armed_at <= ATTACK_MOVE_WINDOW

    def accept_q(self, weapon_name, now):
        last_press = self.last_q_press_by_weapon.get(weapon_name)
        self.last_q_press_by_weapon[weapon_name] = now
        return last_press is None or now - last_press >= Q_SAME_WEAPON_REPEAT_GUARD


def input_loop():
    global screen_capture
    # MSS state must be created in the same thread that captures the screen.
    screen_capture = mss.mss()
    command_guard = InputCommandGuard()
    previous = {
        VK_A: False,
        VK_Q: False,
        VK_W: False,
        VK_R: False,
        VK_LBUTTON: False,
    }
    interval = 1.0 / INPUT_POLL_HZ

    while True:
        now = time.monotonic()
        current = {vk: is_pressed(vk) for vk in previous}

        if current[VK_A] and not previous[VK_A]:
            command_guard.arm_attack_move(now)

        if current[VK_Q] and not previous[VK_Q]:
            weapon_name, icon = classify_q_from_screen()
            if command_guard.accept_q(weapon_name, now):
                add_action("Q", icon, kind_for_weapon(weapon_name))

        if current[VK_W] and not previous[VK_W]:
            add_action("W", ICON_URLS["w"], "spell-w")

        if current[VK_R] and not previous[VK_R]:
            add_action("R", ICON_URLS["r"], "spell-r")

        if current[VK_LBUTTON] and not previous[VK_LBUTTON]:
            if command_guard.consume_attack_click(now):
                add_action("AA", ICON_URLS["aa"], "auto")

        previous = current
        time.sleep(interval)


# ---------------- KILLS (League Live Client Data) ---------------- #

_live_ctx = ssl.create_default_context()
_live_ctx.check_hostname = False
_live_ctx.verify_mode = ssl.CERT_NONE  # League's local API uses a self-signed cert on 127.0.0.1


def _live_get(path):
    with urllib.request.urlopen(LIVE_CLIENT_URL + path, context=_live_ctx, timeout=1) as resp:
        return json.loads(resp.read().decode("utf-8"))


def kill_loop():
    global kill_count, state_version
    seen = None  # highest EventID already handled; None = not attached to a game
    while True:
        try:
            me = _live_get("/activeplayername")
            events = _live_get("/eventdata").get("Events", [])
        except Exception:
            seen = None
            time.sleep(2)
            continue
        names = {str(me), str(me).split("#")[0]}
        top = max((int(e.get("EventID", 0)) for e in events), default=-1)
        if seen is None or top < seen:
            seen = top  # just attached or new game: don't replay old kills
        else:
            new_kills = sum(
                1 for e in events
                if int(e.get("EventID", 0)) > seen
                and e.get("EventName") == "ChampionKill"
                and e.get("KillerName") in names
            )
            seen = top
            if new_kills:
                with state_changed:
                    kill_count += new_kills
                    state_version += 1
                    state_changed.notify_all()
        time.sleep(KILL_POLL_SECONDS)


# ---------------- WEB UI ---------------- #

HTML = (STATIC_DIR / "moontrail2.html").read_text(encoding="utf-8")


def snapshot_locked():
    return [
        {
            "id": item["id"],
            "label": item["label"],
            "icon": item["icon"],
            "kind": item["kind"],
        }
        for item in history
    ]


@app.route("/hud")
def hud():
    # Nightbringer Action HUD. Add ?demo=1 to loop fake inputs while setting it up in OBS.
    return Response(HTML, mimetype="text/html")


@app.route("/events")
def events():
    def stream():
        last_sent = -1
        while True:
            with state_changed:
                now = time.monotonic()
                prune_expired_locked(now)

                if state_version == last_sent:
                    # Sleep until the next expiry or input; do not poll idle SSE clients.
                    until_expiry = ACTION_TTL - (now - history[-1]["time"]) + 0.001 if history else 15.0
                    state_changed.wait(timeout=max(0.001, min(15.0, until_expiry)))
                    continue

                payload = json.dumps({
                    "v": state_version,
                    "items": snapshot_locked(),
                    "kills": kill_count,
                }, separators=(",", ":"))
                last_sent = state_version

            yield f"data: {payload}\n\n"

    return Response(
        stream_with_context(stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/health")
def health():
    return {"ok": True, "app": "Nightbringer Action HUD", "version": VERSION,
            "templates": len(templates), "history": len(history)}


@app.route("/preview")
def preview():
    return Response('<a href="/hud?demo=1">Open Nightbringer Action HUD demo</a>', mimetype="text/html")


def validate_settings(config):
    key = config.get("attack_move_key", "a")
    if not isinstance(key, str) or len(key) != 1 or not key.isascii() or not key.isalnum():
        raise ValueError("attack_move_key must be one letter or number")
    region = config.get("q_region")
    if not isinstance(region, dict) or set(region) != {"top", "left", "width", "height"}:
        raise ValueError("q_region needs top, left, width and height")
    if any(type(v) is not int for v in region.values()):
        raise ValueError("Q region coordinates must be integers")
    if not (1 <= region["width"] <= 512 and 1 <= region["height"] <= 512):
        raise ValueError("Q region width and height must be between 1 and 512 pixels")
    return {"attack_move_key": key, "q_region": region}


def calibrate(settings_path, attack_key="a"):
    from ctypes import wintypes

    print("\nONE-TIME SETUP: open League Practice Tool with Aphelios.")
    print("Use your normal monitor, resolution and League HUD size.")
    print("Select only the Q icon artwork, excluding its border and key label.")
    print("No screenshots are saved. Ctrl+C cancels without changing settings.\n")
    points = []
    for corner in ("TOP-LEFT", "BOTTOM-RIGHT"):
        input("Press Enter, then move the mouse to the " + corner + " corner within 8 seconds.")
        for remaining in range(8, 0, -1):
            print(remaining, flush=True)
            time.sleep(1)
        point = wintypes.POINT()
        if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
            raise RuntimeError("Could not read cursor position")
        points.append((point.x, point.y))
        print("Corner saved. Return to this window.")
    (left, top), (right, bottom) = points
    config = validate_settings({"attack_move_key": attack_key, "q_region": {
        "left": left, "top": top, "width": right-left, "height": bottom-top}})
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = settings_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    temporary.replace(settings_path)
    print("Calibration saved. Check all five weapons in Practice Tool.")
    return config


def main():
    global Q_REGION, monitor_q, VK_A
    parser = argparse.ArgumentParser(description="Nightbringer Action HUD - Aphelios OBS input overlay")
    parser.add_argument("--preview", action="store_true", help="Serve isolated visuals without screen capture or input polling")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--calibrate", action="store_true", help="Repeat the Q-icon setup")
    parser.add_argument("--settings", type=Path, default=Path(os.environ.get("LOCALAPPDATA", Path.home())) / "NightbringerActionHUD" / "settings.json")
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    # Bind before setup or polling: a second copy fails without capturing inputs.
    from werkzeug.serving import ThreadedWSGIServer

    class ExclusiveServer(ThreadedWSGIServer):
        allow_reuse_address = False

        def server_bind(self):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()

    server = ExclusiveServer(HOST, args.port, app)
    if not args.preview:
        config = None
        if args.settings.exists():
            try:
                config = validate_settings(json.loads(args.settings.read_text(encoding="utf-8")))
            except (ValueError, TypeError, AttributeError):
                print("Saved settings are invalid. Recalibrate with --calibrate.")
                if not args.calibrate:
                    raise
        if args.calibrate or config is None:
            config = calibrate(args.settings, config["attack_move_key"] if config else "a")
        Q_REGION = config["q_region"]
        monitor_q = dict(Q_REGION)
        VK_A = ord(config["attack_move_key"].upper())
        load_templates()
        if len(templates) != 5:
            raise RuntimeError("Missing weapon images. Download the complete release again.")
        threading.Thread(target=input_loop, daemon=True).start()
        threading.Thread(target=kill_loop, daemon=True).start()
    print("\nNightbringer Action HUD - keep this window open while streaming.", flush=True)
    print(f"OBS Browser Source: http://{HOST}:{args.port}/hud", flush=True)
    print("Width: 480   Height: 180   Transparent background", flush=True)
    print(f"Demo: http://{HOST}:{args.port}/hud?demo=1", flush=True)
    print("Close this window or press Ctrl+C to stop. Open NightbringerActionHUD.exe each session.", flush=True)
    if args.preview:
        print("PREVIEW ONLY - game inputs and kills are disabled.", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except (Exception, SystemExit) as exc:
        if isinstance(exc, SystemExit) and exc.code in (None, 0):
            raise
        print(f"\nNightbringer Action HUD could not start: {exc}", file=sys.stderr, flush=True)
        if sys.stdin.isatty():
            input("Press Enter to close.")
        raise SystemExit(1)
