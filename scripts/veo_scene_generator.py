#!/usr/bin/env python3
"""
Complete Veo 3.1 + Omni Production Pipeline for:
"A JORNADA DO BILHÃO" — Aurora Cloud · v2 (2:24 · 1920x1080 · 24fps · 18 scenes of 8s)

Incorporates the three adjustments requested by Sponsor:
1. Scenes 06 & 07 (16s block): 2019 localization across the 4 countries (Brazil, Mexico, Colombia, Chile) named and igniting individually.
2. Act III (Scenes 10–13, 32s block): The 4 Pillars that built the $1B milestone.
3. Act IV (Scenes 14–16, 24s compressed): One Google + $1,101.1M (107% of target).
4. Act V (Scenes 17–18, 16s block): Vision of the next horizon ($2B), with the spark from Scene 01 reappearing on the horizon.
"""
import base64
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import wave
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg

BASE_DIR = "./output_project"
V1_CLIPS_DIR = os.path.join(BASE_DIR, "clips")
CLIPS_DIR = os.path.join(BASE_DIR, "clips_jornada_v2")
MD_PATH = os.path.join(BASE_DIR, "roteiro-1b-latam-smb-v2.md")
STATE_PATH = os.path.join(CLIPS_DIR, "generation_state.json")

OUTPUT_MP4 = os.path.join(BASE_DIR, "a_jornada_do_bilhao_v2_latam_smb.mp4")
OUTPUT_720P_MP4 = os.path.join(BASE_DIR, "a_jornada_do_bilhao_v2_latam_smb_720p_backup.mp4")

PROJECT = os.environ.get("GCP_PROJECT_ID", "your-gcp-project-id")
LOCATION = "us-central1"
MODEL = "veo-3.1-generate-001"

WIDTH = 1920
HEIGHT = 1080
FPS = 24
NUM_SCENES = 18
TOTAL_SECONDS = NUM_SCENES * 8       # 144 seconds (2:24)
TOTAL_FRAMES = TOTAL_SECONDS * FPS  # 3456 frames
SCENE_FRAMES = 8 * FPS              # 192 frames per scene

FONT_REGULAR = "/Library/Fonts/GoogleSansDisplay-Regular.ttf"
FONT_MEDIUM = "/Library/Fonts/GoogleSansDisplay-Medium.ttf"
FONT_BOLD = "/Library/Fonts/GoogleSansDisplay-Bold.ttf"

NEGATIVE_PROMPT = (
    "text, words, letters, numbers, captions, subtitles, watermark, logo, "
    "UI elements, distorted faces, extra fingers, deformed hands, warped "
    "architecture, cartoon, anime, illustration, oversaturated colors, "
    "shaky handheld camera, jump cuts, split screen, zoom out, reverse motion"
)

ACT_SEEDS = {
    1: 2016, 2: 2016, 3: 2016, 4: 2016,             # Ato I — A origem
    5: 2019, 6: 2019, 7: 2019, 8: 2019, 9: 2019,    # Ato II — A localização (4 países)
    10: 2024, 11: 2024, 12: 2024, 13: 2024,         # Ato III — Os 4 pilares
    14: 2026, 15: 2026, 16: 2026,                   # Ato IV — O marco ($1,101.1M)
    17: 2028, 18: 2028,                             # Ato V — O próximo horizonte ($2B)
}

# ---------------------------------------------------------------------------
# STEP 1: REUSE PRESERVED V1 CLIPS & GENERATE 8 NEW VEO 3.1 CLIPS
# ---------------------------------------------------------------------------

def get_token():
    return subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()

def parse_scenes_from_md():
    with open(MD_PATH, "r", encoding="utf-8") as f:
        text = f.read()
    pattern = re.compile(
        r"## CENA (\d+)\s*·[^\n]+\n(.*?)```\n(SUBJECT:.*?)```",
        re.DOTALL
    )
    scenes = {}
    for m in pattern.finditer(text):
        num = int(m.group(1))
        meta = m.group(2)
        prompt = m.group(3).strip()
        scenes[num] = {
            "num": num,
            "meta": meta.strip(),
            "prompt": prompt,
            "seed": ACT_SEEDS.get(num, 2026),
        }
    return scenes

def build_compressed_scene_14(dst_path):
    """
    Builds Scene 14 (1:44–1:52, One Google + Glowing Continent compressed)
    by combining the first 4.0s (96 frames) of V1's scene_11.mp4 (human moments)
    and the last 4.0s (96 frames) of V1's scene_12.mp4 (glowing orbital continent)
    with a 16-frame cross-dissolve and mixed stereo audio.
    """
    s11_path = os.path.join(V1_CLIPS_DIR, "scene_11.mp4")
    s12_path = os.path.join(V1_CLIPS_DIR, "scene_12.mp4")
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    def read_clip_frames(p):
        reader = imageio_ffmpeg.read_frames(p, pix_fmt="rgb24")
        meta = next(reader)
        w, h = meta["size"]
        out = []
        for rf in reader:
            arr = np.frombuffer(rf, dtype=np.uint8).reshape((h, w, 3))
            if w != WIDTH or h != HEIGHT:
                arr = np.array(Image.fromarray(arr).resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS))
            out.append(arr)
            if len(out) >= SCENE_FRAMES:
                break
        while len(out) < SCENE_FRAMES:
            out.append(out[-1].copy())
        return out

    f11 = read_clip_frames(s11_path)
    f12 = read_clip_frames(s12_path)

    tmp_vid = os.path.join(CLIPS_DIR, "_tmp_s14_vid.mp4")
    writer = imageio_ffmpeg.write_frames(
        tmp_vid,
        size=(WIDTH, HEIGHT),
        fps=FPS,
        codec="libx264",
        pix_fmt_in="rgb24",
        pix_fmt_out="yuv420p",
        quality=8,
        macro_block_size=8,
        ffmpeg_log_level="error",
    )
    writer.send(None)
    for i in range(SCENE_FRAMES):
        if i < 88:
            frame = f11[i]
        elif i < 104:
            alpha = (i - 88 + 1) / 17.0
            frame = np.clip(
                f11[i].astype(np.float32) * (1.0 - alpha) + f12[i].astype(np.float32) * alpha,
                0, 255
            ).astype(np.uint8)
        else:
            frame = f12[i]
        writer.send(frame.tobytes())
    writer.close()

    # Mix first 4s of s11 audio + last 4s of s12 audio
    sr = 48000
    def extract_wav(p, w_out):
        subprocess.run(
            [ffmpeg_exe, "-y", "-i", p, "-vn", "-ac", "2", "-ar", str(sr), "-f", "wav", w_out],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
        )
        with wave.open(w_out, "rb") as wf:
            raw = wf.readframes(wf.getnframes())
            arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            l = arr[0::2]
            r = arr[1::2]
        os.remove(w_out)
        return l, r

    l11, r11 = extract_wav(s11_path, os.path.join(CLIPS_DIR, "_tmp11.wav"))
    l12, r12 = extract_wav(s12_path, os.path.join(CLIPS_DIR, "_tmp12.wav"))
    n_samp = 8 * sr
    half = 4 * sr
    out_l = np.zeros(n_samp, dtype=np.float32)
    out_r = np.zeros(n_samp, dtype=np.float32)
    out_l[:half] = l11[:half]
    out_r[:half] = r11[:half]
    out_l[half:] = l12[half:n_samp]
    out_r[half:] = r12[half:n_samp]

    tmp_wav = os.path.join(CLIPS_DIR, "_tmp_s14.wav")
    interleaved = np.empty(n_samp * 2, dtype=np.int16)
    interleaved[0::2] = np.clip(out_l * 32767.0, -32768, 32767).astype(np.int16)
    interleaved[1::2] = np.clip(out_r * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(tmp_wav, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(interleaved.tobytes())

    subprocess.run(
        [ffmpeg_exe, "-y", "-i", tmp_vid, "-i", tmp_wav, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", dst_path],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
    )
    os.remove(tmp_vid)
    os.remove(tmp_wav)
    print(f"Built compressed Scene 14 -> {dst_path}", flush=True)

def prepare_preserved_v1_clips():
    """
    Copies preserved V1 clips to clips_jornada_v2 so only the 8 new scenes
    (06, 07, 10, 11, 12, 13, 17, 18) need Veo 3.1 generation.
    """
    os.makedirs(CLIPS_DIR, exist_ok=True)
    v1_mapping = {
        1: 1,
        2: 2,
        3: 3,
        4: 4,
        5: 5,
        8: 8,
        9: 9,
        15: 13,  # V1 Scene 13 (O contador $702M -> $1,101.1M) -> V2 Scene 15
        16: 14,  # V1 Scene 14 (O bilhão shockwave & particles) -> V2 Scene 16
    }
    for v2_num, v1_num in v1_mapping.items():
        dst = os.path.join(CLIPS_DIR, f"scene_{v2_num:02d}.mp4")
        src = os.path.join(V1_CLIPS_DIR, f"scene_{v1_num:02d}.mp4")
        if not os.path.exists(dst) or os.path.getsize(dst) < 100_000:
            shutil.copy2(src, dst)
            print(f"Reused V1 scene_{v1_num:02d}.mp4 -> V2 scene_{v2_num:02d}.mp4", flush=True)

    s14_dst = os.path.join(CLIPS_DIR, "scene_14.mp4")
    if not os.path.exists(s14_dst) or os.path.getsize(s14_dst) < 100_000:
        build_compressed_scene_14(s14_dst)

def extract_last_frame(video_path, png_path):
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe, "-y",
        "-sseof", "-0.1",
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        png_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return png_path

def start_prediction(scene_num, prompt, seed, image_path=None):
    token = get_token()
    url = f"https://{LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/{LOCATION}/publishers/google/models/{MODEL}:predictLongRunning"
    headers = {
        "Authorization": f"Bearer {token}",
        "x-goog-user-project": PROJECT,
        "Content-Type": "application/json",
    }
    instance = {"prompt": prompt}
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as img_f:
            b64_img = base64.b64encode(img_f.read()).decode("utf-8")
        instance["image"] = {
            "bytesBase64Encoded": b64_img,
            "mimeType": "image/png"
        }

    payload = {
        "instances": [instance],
        "parameters": {
            "aspectRatio": "16:9",
            "sampleCount": 1,
            "durationSeconds": 8,
            "resolution": "1080p",
            "generateAudio": True,
            "personGeneration": "allow_adult",
            "seed": seed,
            "negativePrompt": NEGATIVE_PROMPT,
        }
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Scene {scene_num:02d} HTTP {resp.status_code}: {resp.text[:400]}")
    return resp.json()["name"]

def check_operation(op_name):
    token = get_token()
    url = f"https://{LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/{LOCATION}/publishers/google/models/{MODEL}:fetchPredictOperation"
    headers = {
        "Authorization": f"Bearer {token}",
        "x-goog-user-project": PROJECT,
        "Content-Type": "application/json",
    }
    resp = requests.post(url, headers=headers, json={"operationName": op_name}, timeout=60)
    if resp.status_code != 200:
        print(f"Warning polling {op_name}: HTTP {resp.status_code}", flush=True)
        return None
    return resp.json()

def generate_all_v2_clips():
    prepare_preserved_v1_clips()
    scenes = parse_scenes_from_md()
    print(f"Parsed {len(scenes)} scenes from {MD_PATH}", flush=True)
    if len(scenes) != NUM_SCENES:
        raise RuntimeError(f"Expected {NUM_SCENES} scenes, got {len(scenes)}: {sorted(scenes.keys())}")

    state = {}
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, "r") as f:
            state = json.load(f)

    def save_state():
        with open(STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)

    for num in range(1, NUM_SCENES + 1):
        clip_file = os.path.join(CLIPS_DIR, f"scene_{num:02d}.mp4")
        if os.path.exists(clip_file) and os.path.getsize(clip_file) > 100_000:
            state[str(num)] = {"status": "done", "file": clip_file}
    save_state()

    MAX_CONCURRENT = 3

    while True:
        done_count = sum(1 for k, v in state.items() if v.get("status") == "done")
        running_scenes = [int(k) for k, v in state.items() if v.get("status") == "running"]
        print(f"[{time.strftime('%H:%M:%S')}] Clips Progress: {done_count}/{NUM_SCENES} done, {len(running_scenes)} running {running_scenes}", flush=True)

        if done_count == NUM_SCENES:
            print("All 18 scenes for 'A Jornada do Bilhão v2' are ready!", flush=True)
            break

        for num in list(running_scenes):
            info = state[str(num)]
            op_name = info["op_name"]
            try:
                res = check_operation(op_name)
            except Exception as e:
                print(f"Warning checking Scene {num:02d}: {e}", flush=True)
                continue
            if not res:
                continue
            if res.get("done"):
                if "error" in res:
                    err_msg = json.dumps(res["error"])
                    print(f"Scene {num:02d} failed with error: {err_msg} — will retry", flush=True)
                    prev_retries = info.get("retries", 0) + 1
                    state[str(num)] = {
                        "status": "retry_no_img" if info.get("used_image") else "retry",
                        "retries": prev_retries,
                        "last_error": err_msg,
                    }
                    save_state()
                    time.sleep(8)
                elif "response" in res and res["response"].get("videos"):
                    videos = res["response"]["videos"]
                    raw = base64.b64decode(videos[0]["bytesBase64Encoded"])
                    clip_file = os.path.join(CLIPS_DIR, f"scene_{num:02d}.mp4")
                    with open(clip_file, "wb") as out:
                        out.write(raw)
                    print(f"Scene {num:02d} COMPLETED -> {clip_file} ({len(raw)} bytes)", flush=True)
                    state[str(num)] = {"status": "done", "file": clip_file, "op_name": op_name}
                    save_state()
                else:
                    print(f"Scene {num:02d} done with unexpected payload: {res}", flush=True)
                    state[str(num)] = {"status": "retry", "last_error": str(res)}
                    save_state()

        running_scenes = [int(k) for k, v in state.items() if v.get("status") == "running"]

        for num in range(1, NUM_SCENES + 1):
            if len(running_scenes) >= MAX_CONCURRENT:
                break
            st_info = state.get(str(num), {})
            st = st_info.get("status")
            if st in ("done", "running"):
                continue

            # Scene 07 uses Image-to-video from Scene 06's last frame for direct flight continuity across the 4 countries
            img_path = None
            if num == 7 and st != "retry_no_img":
                s6_status = state.get("6", {}).get("status")
                if s6_status != "done":
                    continue
                s6_clip = os.path.join(CLIPS_DIR, "scene_06.mp4")
                s6_last_png = os.path.join(CLIPS_DIR, "scene_06_last.png")
                if not os.path.exists(s6_last_png):
                    extract_last_frame(s6_clip, s6_last_png)
                img_path = s6_last_png

            try:
                retries = st_info.get("retries", 0)
                seed_to_use = scenes[num]["seed"] + retries
                print(f"Launching Scene {num:02d} (seed={seed_to_use}, image={bool(img_path)})...", flush=True)
                op_name = start_prediction(
                    num,
                    scenes[num]["prompt"],
                    seed_to_use,
                    image_path=img_path
                )
                state[str(num)] = {
                    "status": "running",
                    "op_name": op_name,
                    "started_at": time.time(),
                    "used_image": bool(img_path),
                    "retries": retries,
                }
                save_state()
                running_scenes.append(num)
                time.sleep(3)
            except Exception as e:
                print(f"Could not start Scene {num:02d}: {e}", flush=True)
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    break
                time.sleep(5)

        time.sleep(12)

# ---------------------------------------------------------------------------
# STEP 2: OMNI TYPOGRAPHY & VISUAL OVERLAY ENGINE (18 SCENES · 2:24)
# ---------------------------------------------------------------------------

_FONT_CACHE = {}

def get_font(path, size):
    key = (path, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(path, size)
    return _FONT_CACHE[key]

def measure_tracked_text(draw, text, font, tracking_px):
    if not text:
        return 0, 0
    total_w = 0
    max_h = 0
    for i, ch in enumerate(text):
        bbox = draw.textbbox((0, 0), ch, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        total_w += w
        if i < len(text) - 1:
            total_w += tracking_px
        if h > max_h:
            max_h = h
    return total_w, max_h

def draw_tracked_text(overlay, text, x, y, font, tracking_px, alpha, align="center", color=(255, 255, 255)):
    if alpha <= 0.001 or not text:
        return
    alpha_int = int(max(0, min(255, round(alpha * 255))))
    draw = ImageDraw.Draw(overlay)
    total_w, max_h = measure_tracked_text(draw, text, font, tracking_px)

    if align == "center":
        start_x = x - total_w / 2.0
    elif align == "left":
        start_x = x
    elif align == "right":
        start_x = x - total_w
    else:
        start_x = x

    draw_y = y - max_h / 2.0
    shadow_alpha = int(alpha_int * 0.72)
    cur_x = start_x
    for ch in text:
        bbox = draw.textbbox((0, 0), ch, font=font)
        cw = bbox[2] - bbox[0]
        draw.text((cur_x + 2, draw_y + 3), ch, font=font, fill=(13, 13, 15, shadow_alpha))
        draw.text((cur_x, draw_y), ch, font=font, fill=(color[0], color[1], color[2], alpha_int))
        cur_x += cw + tracking_px

def fade_envelope(local_f, start_f, end_f, fade_in_f=12, fade_out_f=12):
    if local_f < start_f or local_f > end_f:
        return 0.0
    a_in = 1.0 if fade_in_f <= 0 else min(1.0, (local_f - start_f) / float(fade_in_f))
    a_out = 1.0 if fade_out_f <= 0 else min(1.0, (end_f - local_f) / float(fade_out_f))
    return max(0.0, min(a_in, a_out))

def ease_out_cubic(t):
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3

def ease_in_out_cubic(t):
    t = max(0.0, min(1.0, t))
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2

def ease_aggressive(t):
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 4

def render_omni_typography_v2(frame_rgb, global_frame):
    """
    Renders exact scene typography onto frame_rgb according to roteiro-1b-latam-smb-v2.md (18 scenes).
    """
    scene_idx = (global_frame // SCENE_FRAMES) + 1
    local_f = global_frame % SCENE_FRAMES

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

    # ATO I — A ORIGEM (01–04)
    if scene_idx == 1:
        alpha = fade_envelope(local_f, 24, 132, fade_in_f=24, fade_out_f=12)
        font = get_font(FONT_MEDIUM, 52)
        draw_tracked_text(overlay, "H2 2016", WIDTH // 2, HEIGHT // 2, font, tracking_px=4.0, alpha=alpha, align="center")

    elif scene_idx == 2:
        alpha = fade_envelope(local_f, 16, 176, fade_in_f=12, fade_out_f=12)
        font = get_font(FONT_REGULAR, 44)
        draw_tracked_text(overlay, "Where a segment was born.", 160, int(HEIGHT * 0.80), font, tracking_px=2.5, alpha=alpha, align="left")

    elif scene_idx == 3:
        alpha = fade_envelope(local_f, 14, 178, fade_in_f=12, fade_out_f=12)
        font = get_font(FONT_REGULAR, 44)
        draw_tracked_text(overlay, "33 countries. One segment.", WIDTH // 2, int(HEIGHT * 0.82), font, tracking_px=3.0, alpha=alpha, align="center")

    elif scene_idx == 4:
        alpha = fade_envelope(local_f, 12, 178, fade_in_f=12, fade_out_f=12)
        font = get_font(FONT_REGULAR, 40)
        draw_tracked_text(
            overlay,
            "Sep 19, 2017 — South America's first Google Cloud region",
            WIDTH // 2, int(HEIGHT * 0.82), font, tracking_px=2.2, alpha=alpha, align="center"
        )

    # ATO II — A LOCALIZAÇÃO (05–09)
    elif scene_idx == 5:
        alpha = fade_envelope(local_f, 12, 180, fade_in_f=12, fade_out_f=12)
        prog = ease_out_cubic((local_f - 16) / 130.0)
        val = int(round(121 * prog))
        font_year = get_font(FONT_REGULAR, 40)
        font_num = get_font(FONT_BOLD, 92)
        draw_tracked_text(overlay, "2017", WIDTH // 2, HEIGHT // 2 - 68, font_year, tracking_px=5.0, alpha=alpha * 0.85, align="center")
        draw_tracked_text(overlay, f"${val}M", WIDTH // 2, HEIGHT // 2 + 16, font_num, tracking_px=4.0, alpha=alpha, align="center")

    elif scene_idx == 6:
        # CENA 06 (0:40–0:48): 2019 Localization Part 1 — Brazil & Mexico igniting individually
        alpha_top = fade_envelope(local_f, 8, 184, fade_in_f=12, fade_out_f=10)
        font_top = get_font(FONT_REGULAR, 36)
        draw_tracked_text(
            overlay,
            "2019 — Local resources. Local currency. FOP & TL Program.",
            WIDTH // 2, int(HEIGHT * 0.16), font_top, tracking_px=2.5, alpha=alpha_top * 0.9, align="center", color=(66, 133, 244)
        )
        font_country = get_font(FONT_BOLD, 76)
        font_sub = get_font(FONT_REGULAR, 34)
        if local_f < 96:
            a_c = fade_envelope(local_f, 12, 92, fade_in_f=10, fade_out_f=8)
            draw_tracked_text(overlay, "BRAZIL", WIDTH // 2, int(HEIGHT * 0.76), font_country, tracking_px=5.0, alpha=a_c, align="center")
            draw_tracked_text(overlay, "Local Currency  ·  Local FOP  ·  Dedicated Teams", WIDTH // 2, int(HEIGHT * 0.85), font_sub, tracking_px=2.5, alpha=a_c * 0.85, align="center")
        else:
            a_c = fade_envelope(local_f, 96, 184, fade_in_f=10, fade_out_f=10)
            draw_tracked_text(overlay, "BRAZIL   ·   MEXICO", WIDTH // 2, int(HEIGHT * 0.76), font_country, tracking_px=5.0, alpha=a_c, align="center")
            draw_tracked_text(overlay, "GCP $7M → $27M   ·   GWS $114M → $181M", WIDTH // 2, int(HEIGHT * 0.85), font_sub, tracking_px=2.8, alpha=a_c * 0.9, align="center", color=(251, 188, 4))

    elif scene_idx == 7:
        # CENA 07 (0:48–0:56): Localization Part 2 — Colombia & Chile completing the 4 localized countries
        alpha_top = fade_envelope(local_f, 6, 184, fade_in_f=10, fade_out_f=12)
        font_top = get_font(FONT_REGULAR, 36)
        draw_tracked_text(
            overlay,
            "Localized resources across 4 core countries",
            WIDTH // 2, int(HEIGHT * 0.16), font_top, tracking_px=2.5, alpha=alpha_top * 0.9, align="center", color=(52, 168, 83)
        )
        font_country = get_font(FONT_BOLD, 64)
        font_sub = get_font(FONT_REGULAR, 34)
        if local_f < 96:
            a_c = fade_envelope(local_f, 8, 92, fade_in_f=10, fade_out_f=8)
            draw_tracked_text(overlay, "BRAZIL  ·  MEXICO  ·  COLOMBIA", WIDTH // 2, int(HEIGHT * 0.76), font_country, tracking_px=4.0, alpha=a_c, align="center")
            draw_tracked_text(overlay, "Expanding local presence across the Andes", WIDTH // 2, int(HEIGHT * 0.85), font_sub, tracking_px=2.5, alpha=a_c * 0.85, align="center")
        else:
            a_c = fade_envelope(local_f, 96, 184, fade_in_f=10, fade_out_f=12)
            draw_tracked_text(overlay, "BRAZIL  ·  MEXICO  ·  COLOMBIA  ·  CHILE", WIDTH // 2, int(HEIGHT * 0.76), font_country, tracking_px=4.0, alpha=a_c, align="center")
            draw_tracked_text(overlay, "4 Localized Markets Powering Aurora Cloud", WIDTH // 2, int(HEIGHT * 0.85), font_sub, tracking_px=2.8, alpha=a_c * 0.9, align="center", color=(66, 133, 244))

    elif scene_idx == 8:
        alpha = fade_envelope(local_f, 12, 180, fade_in_f=12, fade_out_f=12)
        font = get_font(FONT_REGULAR, 40)
        draw_tracked_text(
            overlay,
            "2023–2024 — SST  ·  TD SYNNEX  ·  Regional FOPs  ·  5 Hubs",
            WIDTH // 2, int(HEIGHT * 0.82), font, tracking_px=2.5, alpha=alpha, align="center"
        )

    elif scene_idx == 9:
        alpha = fade_envelope(local_f, 10, 182, fade_in_f=12, fade_out_f=12)
        prog = ease_in_out_cubic((local_f - 14) / 140.0)
        val = int(round(121 + (702 - 121) * prog))
        font_year = get_font(FONT_REGULAR, 40)
        font_num = get_font(FONT_BOLD, 92)
        draw_tracked_text(overlay, "2024", WIDTH // 2, HEIGHT // 2 - 68, font_year, tracking_px=5.0, alpha=alpha * 0.85, align="center")
        draw_tracked_text(overlay, f"${val}M", WIDTH // 2, HEIGHT // 2 + 16, font_num, tracking_px=4.0, alpha=alpha, align="center")

    # ATO III — O QUE NOS TROUXE AQUI: OS 4 PILARES (10–13)
    elif scene_idx == 10:
        alpha = fade_envelope(local_f, 10, 182, fade_in_f=12, fade_out_f=12)
        font_tag = get_font(FONT_BOLD, 32)
        font_title = get_font(FONT_BOLD, 72)
        font_sub = get_font(FONT_REGULAR, 36)
        draw_tracked_text(overlay, "PILLAR 01  ·  WHAT BROUGHT US HERE", WIDTH // 2, HEIGHT // 2 - 90, font_tag, tracking_px=4.5, alpha=alpha, align="center", color=(66, 133, 244))
        draw_tracked_text(overlay, "Local Presence & Local Currency", WIDTH // 2, HEIGHT // 2 - 10, font_title, tracking_px=3.5, alpha=alpha, align="center")
        draw_tracked_text(overlay, "Dedicated teams, FOPs & local billing in Brazil, Mexico, Colombia & Chile", WIDTH // 2, int(HEIGHT * 0.82), font_sub, tracking_px=2.2, alpha=alpha * 0.9, align="center")

    elif scene_idx == 11:
        alpha = fade_envelope(local_f, 10, 182, fade_in_f=12, fade_out_f=12)
        font_tag = get_font(FONT_BOLD, 32)
        font_title = get_font(FONT_BOLD, 72)
        font_sub = get_font(FONT_REGULAR, 36)
        draw_tracked_text(overlay, "PILLAR 02  ·  WHAT BROUGHT US HERE", WIDTH // 2, HEIGHT // 2 - 90, font_tag, tracking_px=4.5, alpha=alpha, align="center", color=(52, 168, 83))
        draw_tracked_text(overlay, "Scaled Motion & High-Velocity Engine", WIDTH // 2, HEIGHT // 2 - 10, font_title, tracking_px=3.5, alpha=alpha, align="center")
        draw_tracked_text(overlay, "TL Program  ·  SST  ·  Digital acquisition across 33 countries", WIDTH // 2, int(HEIGHT * 0.82), font_sub, tracking_px=2.2, alpha=alpha * 0.9, align="center")

    elif scene_idx == 12:
        alpha = fade_envelope(local_f, 10, 182, fade_in_f=12, fade_out_f=12)
        font_tag = get_font(FONT_BOLD, 32)
        font_title = get_font(FONT_BOLD, 72)
        font_sub = get_font(FONT_REGULAR, 36)
        draw_tracked_text(overlay, "PILLAR 03  ·  WHAT BROUGHT US HERE", WIDTH // 2, HEIGHT // 2 - 90, font_tag, tracking_px=4.5, alpha=alpha, align="center", color=(251, 188, 4))
        draw_tracked_text(overlay, "Partner Ecosystem & Distribution", WIDTH // 2, HEIGHT // 2 - 10, font_title, tracking_px=3.5, alpha=alpha, align="center")
        draw_tracked_text(overlay, "TD SYNNEX & regional partners multiplying reach at scale", WIDTH // 2, int(HEIGHT * 0.82), font_sub, tracking_px=2.2, alpha=alpha * 0.9, align="center")

    elif scene_idx == 13:
        alpha = fade_envelope(local_f, 10, 182, fade_in_f=12, fade_out_f=12)
        font_tag = get_font(FONT_BOLD, 32)
        font_title = get_font(FONT_BOLD, 68)
        font_sub = get_font(FONT_REGULAR, 36)
        draw_tracked_text(overlay, "PILLAR 04  ·  WHAT BROUGHT US HERE", WIDTH // 2, HEIGHT // 2 - 90, font_tag, tracking_px=4.5, alpha=alpha, align="center", color=(234, 67, 53))
        draw_tracked_text(overlay, "Full-Stack Cloud & One Google Team", WIDTH // 2, HEIGHT // 2 - 10, font_title, tracking_px=3.5, alpha=alpha, align="center")
        draw_tracked_text(overlay, "Google Workspace + GCP + AI   ·   78–89 FTEs across 5 hubs", WIDTH // 2, int(HEIGHT * 0.82), font_sub, tracking_px=2.2, alpha=alpha * 0.9, align="center")

    # ATO IV — O MARCO (14–16 · Comprimido)
    elif scene_idx == 14:
        # First 4.5s (0..108f): "Hundreds of people. One decade." + 8 functions; Last 3.5s (108..192f): no text, let the glowing continent breathe before the 1s silence
        if local_f < 112:
            alpha = fade_envelope(local_f, 8, 108, fade_in_f=10, fade_out_f=12)
            font_main = get_font(FONT_MEDIUM, 56)
            font_sub = get_font(FONT_REGULAR, 30)
            draw_tracked_text(overlay, "Hundreds of people. One decade. One Google.", WIDTH // 2, HEIGHT // 2, font_main, tracking_px=3.5, alpha=alpha, align="center")
            draw_tracked_text(
                overlay,
                "Sales  ·  Marketing  ·  Engineering  ·  gTech  ·  Partners  ·  Finance  ·  Legal  ·  People Ops",
                WIDTH // 2, int(HEIGHT * 0.84), font_sub, tracking_px=2.0, alpha=alpha * 0.85, align="center"
            )

    elif scene_idx == 15:
        # CENA 15 (1:52–2:00): Giant counter $702M -> $1,101.1M
        alpha = fade_envelope(local_f, 4, 191, fade_in_f=8, fade_out_f=0)
        prog = ease_aggressive((local_f - 4) / 180.0)
        val = 702.0 + (1101.1 - 702.0) * prog
        txt = f"${val:,.1f}M" if val >= 1000.0 else f"${val:.1f}M"
        font_giant = get_font(FONT_BOLD, 168)
        draw_tracked_text(overlay, txt, WIDTH // 2, HEIGHT // 2, font_giant, tracking_px=5.0, alpha=alpha, align="center")

    elif scene_idx == 16:
        # CENA 16 (2:00–2:08): THE BILLION ($1,101.1M + 107% of target)
        alpha_main = fade_envelope(local_f, 0, 178, fade_in_f=0, fade_out_f=18)
        alpha_sub = fade_envelope(local_f, 12, 178, fade_in_f=12, fade_out_f=18)
        font_hero = get_font(FONT_BOLD, 210)
        font_sub = get_font(FONT_MEDIUM, 54)
        draw_tracked_text(overlay, "$1,101.1M", WIDTH // 2, HEIGHT // 2 - 24, font_hero, tracking_px=6.0, alpha=alpha_main, align="center")
        draw_tracked_text(overlay, "107% of target  ·  FY26 Q4", WIDTH // 2, HEIGHT // 2 + 115, font_sub, tracking_px=4.0, alpha=alpha_sub, align="center", color=(52, 168, 83))

    # ATO V — O PRÓXIMO HORIZONTE: A VISÃO 2B (17–18)
    elif scene_idx == 17:
        # CENA 17 (2:08–2:16):
        if local_f < 88:
            alpha = fade_envelope(local_f, 8, 84, fade_in_f=12, fade_out_f=12)
            font_y = get_font(FONT_REGULAR, 44)
            font_m = get_font(FONT_MEDIUM, 60)
            draw_tracked_text(overlay, "2016  →  2026", WIDTH // 2, HEIGHT // 2 - 52, font_y, tracking_px=4.5, alpha=alpha * 0.85, align="center", color=(66, 133, 244))
            draw_tracked_text(overlay, "One billion dollars. Ten years. One team.", WIDTH // 2, HEIGHT // 2 + 24, font_m, tracking_px=3.5, alpha=alpha, align="center")
        else:
            alpha = fade_envelope(local_f, 88, 184, fade_in_f=12, fade_out_f=12)
            font_m = get_font(FONT_MEDIUM, 64)
            draw_tracked_text(overlay, "The first billion took a decade to build.", WIDTH // 2, HEIGHT // 2, font_m, tracking_px=3.5, alpha=alpha, align="center")

    elif scene_idx == 18:
        # CENA 18 (2:16–2:24): The spark from Scene 01 reappears on the horizon -> $2B vision!
        if local_f < 124:
            a1 = fade_envelope(local_f, 8, 120, fade_in_f=12, fade_out_f=12)
            a2 = fade_envelope(local_f, 24, 120, fade_in_f=14, fade_out_f=12)
            font_top = get_font(FONT_REGULAR, 46)
            font_2b = get_font(FONT_BOLD, 186)
            font_sub = get_font(FONT_MEDIUM, 38)
            draw_tracked_text(overlay, "The next horizon is already in motion.", WIDTH // 2, HEIGHT // 2 - 125, font_top, tracking_px=3.5, alpha=a1, align="center")
            draw_tracked_text(overlay, "$2B", WIDTH // 2, HEIGHT // 2 + 10, font_2b, tracking_px=6.0, alpha=a2, align="center", color=(66, 133, 244))
            draw_tracked_text(overlay, "THE NEXT HORIZON", WIDTH // 2, HEIGHT // 2 + 130, font_sub, tracking_px=5.5, alpha=a2 * 0.9, align="center", color=(255, 255, 255))
        else:
            # Final card (2:21–2:24): Thank you, Aurora Cloud. / Onward to $2B. (cuts sharply to black at 2:24)
            alpha = fade_envelope(local_f, 124, 191, fade_in_f=12, fade_out_f=0)
            font_ty = get_font(FONT_BOLD, 80)
            font_on = get_font(FONT_MEDIUM, 44)
            draw_tracked_text(overlay, "Thank you, Aurora Cloud.", WIDTH // 2, HEIGHT // 2 - 28, font_ty, tracking_px=4.0, alpha=alpha, align="center")
            draw_tracked_text(overlay, "Onward to $2B.", WIDTH // 2, HEIGHT // 2 + 56, font_on, tracking_px=4.5, alpha=alpha * 0.95, align="center", color=(66, 133, 244))

    base_img = Image.fromarray(frame_rgb).convert("RGBA")
    composited = Image.alpha_composite(base_img, overlay).convert("RGB")
    return np.array(composited, dtype=np.uint8)

# ---------------------------------------------------------------------------
# STEP 3: PROCEDURAL 2:24 SOUNDTRACK + VEO 3 NATIVE AUDIO MASTERING
# ---------------------------------------------------------------------------

def generate_master_audio_v2(out_wav_path):
    """
    Generates the 144.0s (2:24, 48kHz stereo) master audio track combining:
    - Procedural cinematic score across all 5 Acts (18 scenes)
    - Native Veo 3 audio from all 18 clips
    - 1-second total silence at 1:51.0–1:52.0 (end of Scene 14 before the counter climax)
    """
    sr = 48000
    n_samples = TOTAL_SECONDS * sr
    score_L = np.zeros(n_samples, dtype=np.float32)
    score_R = np.zeros(n_samples, dtype=np.float32)

    def add_piano_note(start_s, freq, dur_s, amp=0.22):
        idx0 = int(start_s * sr)
        idx1 = min(n_samples, int((start_s + dur_s) * sr))
        if idx0 >= n_samples or idx1 <= idx0:
            return
        lt = np.arange(idx1 - idx0, dtype=np.float32) / sr
        env = np.exp(-lt / (dur_s * 0.38)) * (1.0 - np.exp(-lt / 0.012))
        sig = (
            1.00 * np.sin(2 * np.pi * freq * lt)
            + 0.42 * np.sin(2 * np.pi * freq * 2.0 * lt) * np.exp(-lt * 1.4)
            + 0.18 * np.sin(2 * np.pi * freq * 3.0 * lt) * np.exp(-lt * 2.2)
            + 0.08 * np.sin(2 * np.pi * freq * 4.0 * lt) * np.exp(-lt * 3.5)
        ) * env * amp
        score_L[idx0:idx1] += sig * 0.95
        score_R[idx0:idx1] += sig * 1.05

    def add_pad_chord(start_s, end_s, freqs, amp=0.10, fade_in=1.5, fade_out=1.5):
        idx0 = int(start_s * sr)
        idx1 = min(n_samples, int(end_s * sr))
        if idx0 >= n_samples or idx1 <= idx0:
            return
        dur = (idx1 - idx0) / sr
        lt = np.arange(idx1 - idx0, dtype=np.float32) / sr
        env = np.ones_like(lt)
        if fade_in > 0:
            env *= np.minimum(1.0, lt / fade_in)
        if fade_out > 0:
            env *= np.minimum(1.0, (dur - lt) / fade_out)
        sig_L = np.zeros_like(lt)
        sig_R = np.zeros_like(lt)
        for i, f in enumerate(freqs):
            detune = 1.0 + 0.0015 * ((i % 2) * 2 - 1)
            w1 = np.sin(2 * np.pi * f * lt) + 0.35 * np.sin(2 * np.pi * f * 2.0 * lt)
            w2 = np.sin(2 * np.pi * (f * detune) * lt + 0.4) + 0.35 * np.sin(2 * np.pi * (f * detune) * 2.0 * lt)
            sig_L += w1
            sig_R += w2
        norm = max(1, len(freqs))
        score_L[idx0:idx1] += (sig_L / norm) * env * amp
        score_R[idx0:idx1] += (sig_R / norm) * env * amp

    def add_kick(time_s, amp=0.30):
        idx0 = int(time_s * sr)
        idx1 = min(n_samples, idx0 + int(0.28 * sr))
        if idx0 >= n_samples or idx1 <= idx0:
            return
        lt = np.arange(idx1 - idx0, dtype=np.float32) / sr
        f_sweep = 48.0 + 95.0 * np.exp(-lt * 28.0)
        phase = 2 * np.pi * np.cumsum(f_sweep) / sr
        sig = np.sin(phase) * np.exp(-lt * 11.0) * amp
        score_L[idx0:idx1] += sig
        score_R[idx0:idx1] += sig

    def add_impact(time_s, amp=0.45, dur_s=2.5):
        idx0 = int(time_s * sr)
        idx1 = min(n_samples, idx0 + int(dur_s * sr))
        if idx0 >= n_samples or idx1 <= idx0:
            return
        lt = np.arange(idx1 - idx0, dtype=np.float32) / sr
        f_sweep = 36.0 + 80.0 * np.exp(-lt * 14.0)
        phase = 2 * np.pi * np.cumsum(f_sweep) / sr
        sub = np.sin(phase) * np.exp(-lt * 2.2)
        shimmer = (
            np.sin(2 * np.pi * 523.25 * lt)
            + np.sin(2 * np.pi * 659.25 * lt)
            + np.sin(2 * np.pi * 783.99 * lt)
        ) * 0.15 * np.exp(-lt * 1.5)
        sig = (sub + shimmer) * amp
        score_L[idx0:idx1] += sig
        score_R[idx0:idx1] += sig

    C1, C2, G2, Ab2, Bb2 = 32.70, 65.41, 98.00, 103.83, 116.54
    C3, D3, Eb3, F3, G3, Ab3, Bb3 = 130.81, 146.83, 155.56, 174.61, 196.00, 207.65, 233.08
    C4, D4, Eb4, E4, F4, G4, Ab4, Bb4, C5 = 261.63, 293.66, 311.13, 329.63, 349.23, 392.00, 415.30, 466.16, 523.25
    arp_notes = [C4, Eb4, G4, Bb4, C5, Bb4, G4, Eb4]

    # ATO I (0:00–0:32)
    add_piano_note(3.0, C2, 5.2, amp=0.26)
    add_piano_note(3.0, C3, 5.2, amp=0.18)
    for pt in [8.0, 10.0, 12.0, 14.0]:
        add_piano_note(pt, C3, 2.4, amp=0.20)
        add_piano_note(pt + 1.0, G3, 1.8, amp=0.11)
    add_pad_chord(16.0, 24.5, [C1, C2, G2], amp=0.16, fade_in=2.0, fade_out=1.0)
    for pt in [16.0, 18.0, 20.0, 22.0]:
        add_piano_note(pt, C3, 2.2, amp=0.18)
    add_piano_note(18.5, C5, 3.0, amp=0.15)
    add_pad_chord(24.0, 32.5, [C2, G2, C3, Eb3, G3, Bb3], amp=0.20, fade_in=2.0, fade_out=1.0)
    for pt in [24.0, 26.0, 28.0, 30.0]:
        add_piano_note(pt, C3, 2.0, amp=0.16)
        add_piano_note(pt + 0.5, Eb4, 1.5, amp=0.12)

    # ATO II — A LOCALIZAÇÃO (0:32–1:12)
    # Scene 05 (32–40s)
    add_pad_chord(32.0, 40.5, [Ab2, Eb3, Ab3, C4, Eb4], amp=0.22, fade_in=1.0, fade_out=1.0)
    for beat_t in np.arange(32.0, 40.0, 0.5):
        add_kick(beat_t, amp=0.18)
    # Scene 06 (40–48s): Brazil (40.5s) & Mexico (44.0s) ignitions
    add_pad_chord(40.0, 48.5, [Bb2, F3, Bb3, D4, F4], amp=0.25, fade_in=1.0, fade_out=1.0)
    for country_t in [40.6, 44.2]:
        add_impact(country_t, amp=0.28, dur_s=1.6)
    for i, step_t in enumerate(np.arange(40.0, 48.0, 0.25)):
        add_piano_note(step_t, arp_notes[i % len(arp_notes)], 0.45, amp=0.11)
        if i % 2 == 0:
            add_kick(step_t, amp=0.22)
    # Scene 07 (48–56s): Main melody + Colombia (48.6s) & Chile (52.2s) ignitions
    add_pad_chord(48.0, 56.5, [C2, G2, C3, Eb3, G3, C4, Eb4, G4], amp=0.28, fade_in=0.8, fade_out=1.0)
    melody_07 = [(48.0, C4), (49.5, Eb4), (50.5, G4), (52.0, Ab4), (53.5, G4), (54.5, Bb4)]
    for mt, mf in melody_07:
        add_piano_note(mt, mf, 1.8, amp=0.22)
        add_piano_note(mt, mf * 2, 1.5, amp=0.10)
    for country_t in [48.6, 52.2]:
        add_impact(country_t, amp=0.28, dur_s=1.6)
    for beat_t in np.arange(48.0, 56.0, 0.5):
        add_kick(beat_t, amp=0.24)
    # Scene 08 (56–64s): Regional network & 5 hubs
    add_pad_chord(56.0, 64.5, [Ab2, Eb3, Ab3, C4, Eb4, Ab4, C5], amp=0.30, fade_in=0.8, fade_out=1.0)
    for i, step_t in enumerate(np.arange(56.0, 64.0, 0.25)):
        add_piano_note(step_t, arp_notes[i % len(arp_notes)], 0.4, amp=0.12)
        if i % 2 == 0:
            add_kick(step_t, amp=0.25)
    # Scene 09 (64–72s): Ascent $121M -> $702M
    add_pad_chord(64.0, 72.2, [Bb2, F3, Bb3, D4, F4, Bb4], amp=0.32, fade_in=0.8, fade_out=0.5)
    for imp_t in [65.2, 67.0, 68.5, 69.8, 70.9]:
        add_impact(imp_t, amp=0.32, dur_s=1.2)
    for beat_t in np.arange(64.0, 72.0, 0.5):
        add_kick(beat_t, amp=0.26)

    # ATO III — OS 4 PILARES (1:12–1:44 · 72s–104s)
    pillar_chords = [
        (72.0, 80.2, [C2, G2, C3, Eb3, G3, C4, G4]),       # Pillar 1 (72–80s)
        (80.0, 88.2, [Ab2, Eb3, Ab3, C4, Eb4, Ab4]),       # Pillar 2 (80–88s)
        (88.0, 96.2, [Bb2, F3, Bb3, D4, F4, Bb4]),         # Pillar 3 (88–96s)
        (96.0, 104.2, [C2, G2, C3, E4, G4, C5]),           # Pillar 4 (96–104s)
    ]
    for p_idx, (st_s, en_s, ch_freqs) in enumerate(pillar_chords):
        add_impact(st_s + 0.2, amp=0.34, dur_s=1.8)
        add_pad_chord(st_s, en_s, ch_freqs, amp=0.30 + 0.02 * p_idx, fade_in=0.6, fade_out=0.6)
        for i, step_t in enumerate(np.arange(st_s, en_s - 0.2, 0.25)):
            add_piano_note(step_t, arp_notes[(i + p_idx) % len(arp_notes)], 0.38, amp=0.13)
            if i % 2 == 0:
                add_kick(step_t, amp=0.26 + 0.015 * p_idx)

    # ATO IV — O MARCO (1:44–2:08 · 104s–128s)
    # Scene 14 (104–112s): Emotional breath (104–108s) + Swelling orbital drone (108–111s) + 1s TOTAL SILENCE (111–112s)!
    add_pad_chord(104.0, 108.5, [C3, G3, C4, E4], amp=0.15, fade_in=0.8, fade_out=0.8)
    for pt, pf in [(104.4, C4), (106.0, E4), (107.5, G4)]:
        add_piano_note(pt, pf, 2.0, amp=0.17)
    add_pad_chord(108.0, 111.0, [C2, G2, C3, G3, C4, E4, G4, C5], amp=0.38, fade_in=2.5, fade_out=0.05)

    # Scene 15 (112–120s / 1:52–2:00): CLIMAX COUNTER ($702M -> $1,101.1M)
    add_pad_chord(112.0, 120.0, [C2, G2, C3, E4, G4, Bb4, C5], amp=0.38, fade_in=0.2, fade_out=0.1)
    for beat_t in np.arange(112.0, 120.0, 0.25):
        add_kick(beat_t, amp=0.32)
    r_idx0, r_idx1 = int(112.0 * sr), int(120.0 * sr)
    rt = np.arange(r_idx1 - r_idx0, dtype=np.float32) / sr
    r_freq = 130.81 * (2.0 ** (rt / 2.6))
    r_phase = 2 * np.pi * np.cumsum(r_freq) / sr
    riser = np.sin(r_phase) * (rt / 8.0) * 0.22
    score_L[r_idx0:r_idx1] += riser
    score_R[r_idx0:r_idx1] += riser

    # Scene 16 (120–128s / 2:00–2:08): THE BILLION ($1,101.1M · 107%)
    add_impact(120.0, amp=0.58, dur_s=3.8)
    add_pad_chord(120.0, 128.5, [C1, C2, G2, C3, E4, G4, C5, E4 * 2], amp=0.40, fade_in=0.05, fade_out=1.8)
    add_piano_note(120.0, C5, 4.5, amp=0.28)

    # ATO V — O PRÓXIMO HORIZONTE: A VISÃO 2B (2:08–2:24 · 128s–144s)
    # Scene 17 (128–136s): Ethereal transition as particles align toward the horizon
    add_pad_chord(128.0, 136.5, [C2, G2, C3, E4, G4], amp=0.18, fade_in=1.2, fade_out=1.2)
    for pt, pf in [(128.8, G4), (131.2, E4), (133.6, C4)]:
        add_piano_note(pt, pf, 2.6, amp=0.18)

    # Scene 18 (136–144s / 2:16–2:24): The spark from Scene 01 reappears on the horizon -> $2B vision!
    add_piano_note(136.5, C2, 4.5, amp=0.25)
    add_piano_note(136.5, C3, 4.5, amp=0.20)
    add_impact(137.8, amp=0.35, dur_s=2.4)  # Heartbeat pulse 1 ($2B reveal)
    add_impact(139.8, amp=0.42, dur_s=3.0)  # Heartbeat pulse 2 (Horizon portal opens)
    add_pad_chord(137.5, 143.9, [C2, G2, C3, E4, G4, C5, G4 * 2], amp=0.34, fade_in=1.2, fade_out=0.15)
    add_piano_note(141.0, C5, 2.9, amp=0.26)

    # Mix native Veo 3 audio from all 18 clips
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    veo_L = np.zeros(n_samples, dtype=np.float32)
    veo_R = np.zeros(n_samples, dtype=np.float32)

    for s_idx in range(1, NUM_SCENES + 1):
        clip_path = os.path.join(CLIPS_DIR, f"scene_{s_idx:02d}.mp4")
        tmp_wav = os.path.join(CLIPS_DIR, f"_tmp_audio_{s_idx:02d}.wav")
        cmd = [
            ffmpeg_exe, "-y",
            "-i", clip_path,
            "-vn", "-ac", "2", "-ar", str(sr), "-f", "wav",
            tmp_wav
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode == 0 and os.path.exists(tmp_wav):
            with wave.open(tmp_wav, "rb") as wf:
                raw_bytes = wf.readframes(wf.getnframes())
                audio_i16 = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                if wf.getnchannels() == 2:
                    a_l = audio_i16[0::2]
                    a_r = audio_i16[1::2]
                else:
                    a_l = audio_i16
                    a_r = audio_i16
                start_sample = (s_idx - 1) * 8 * sr
                length = min(8 * sr, len(a_l), n_samples - start_sample)
                if length > 0:
                    fade_len = int(0.15 * sr)
                    env = np.ones(length, dtype=np.float32)
                    env[:fade_len] = np.linspace(0.0, 1.0, fade_len)
                    env[-fade_len:] = np.linspace(1.0, 0.0, fade_len)
                    veo_L[start_sample : start_sample + length] += a_l[:length] * env
                    veo_R[start_sample : start_sample + length] += a_r[:length] * env
            os.remove(tmp_wav)

    mix_L = score_L * 0.85 + veo_L * 0.48
    mix_R = score_R * 0.85 + veo_R * 0.48

    # Enforce 1-second total silence at 1:51.0–1:52.0 (111.0s–112.0s, end of Scene 14)
    sil_0 = int(111.0 * sr)
    sil_1 = int(112.0 * sr)
    fade_sil = int(0.04 * sr)
    mix_L[sil_0 - fade_sil : sil_0] *= np.linspace(1.0, 0.0, fade_sil)
    mix_R[sil_0 - fade_sil : sil_0] *= np.linspace(1.0, 0.0, fade_sil)
    mix_L[sil_0:sil_1] = 0.0
    mix_R[sil_0:sil_1] = 0.0

    mix_L = np.tanh(mix_L * 1.15) * 0.92
    mix_R = np.tanh(mix_R * 1.15) * 0.92

    interleaved = np.empty(n_samples * 2, dtype=np.int16)
    interleaved[0::2] = np.clip(mix_L * 32767.0, -32768, 32767).astype(np.int16)
    interleaved[1::2] = np.clip(mix_R * 32767.0, -32768, 32767).astype(np.int16)

    with wave.open(out_wav_path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(interleaved.tobytes())
    print(f"Master 2:24 audio written to {out_wav_path}", flush=True)

# ---------------------------------------------------------------------------
# STEP 4: VIDEO COMPOSITING, TRANSITIONS & FINAL EXPORT
# ---------------------------------------------------------------------------

def load_scene_frames(scene_idx):
    clip_path = os.path.join(CLIPS_DIR, f"scene_{scene_idx:02d}.mp4")
    reader = imageio_ffmpeg.read_frames(clip_path, pix_fmt="rgb24")
    meta = next(reader)
    w, h = meta["size"]
    frames = []
    for raw_frame in reader:
        arr = np.frombuffer(raw_frame, dtype=np.uint8).reshape((h, w, 3))
        if w != WIDTH or h != HEIGHT:
            arr = np.array(Image.fromarray(arr).resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS))
        frames.append(arr)
        if len(frames) >= SCENE_FRAMES:
            break
    while len(frames) < SCENE_FRAMES:
        frames.append(frames[-1].copy())
    return frames

BOUNDARY_TRANSITIONS = {
    1: ("dissolve", 16),  # 01 -> 02
    2: ("dissolve", 16),  # 02 -> 03
    3: ("cut", 0),        # 03 -> 04
    4: ("whip", 8),       # 04 -> 05
    5: ("dissolve", 12),  # 05 -> 06
    6: ("dissolve", 8),   # 06 -> 07 (continuous localization flight)
    7: ("dissolve", 12),  # 07 -> 08
    8: ("dissolve", 12),  # 08 -> 09
    9: ("cut", 0),        # 09 -> 10 (enter Act III: 4 Pillars)
    10: ("dissolve", 10), # 10 -> 11
    11: ("dissolve", 10), # 11 -> 12
    12: ("dissolve", 12), # 12 -> 13
    13: ("dissolve", 16), # 13 -> 14
    14: ("cut", 0),       # 14 -> 15 (cut on 1s silence)
    15: ("cut", 0),       # 15 -> 16 (cut at peak of counter)
    16: ("dissolve", 24), # 16 -> 17 (slow dissolve into Act V)
    17: ("dissolve", 16), # 17 -> 18 (reveal $2B spark on horizon)
}

def apply_whip_pan(frame_a, frame_b, alpha):
    shift = int(WIDTH * alpha)
    combined = np.zeros_like(frame_a)
    if shift < WIDTH:
        combined[:, : WIDTH - shift] = frame_a[:, shift:]
    if shift > 0:
        combined[:, WIDTH - shift :] = frame_b[:, :shift]
    img = Image.fromarray(combined).filter(ImageFilter.BoxBlur(radius=6))
    return np.array(img, dtype=np.uint8)

def apply_screen_shake(frame_rgb, shake_idx):
    offsets = [(18, -14), (-15, 12), (12, 9), (-9, -7), (6, 4), (-3, -2)]
    dx, dy = offsets[shake_idx % len(offsets)]
    out = np.zeros_like(frame_rgb)
    x_src0 = max(0, -dx)
    x_src1 = min(WIDTH, WIDTH - dx)
    y_src0 = max(0, -dy)
    y_src1 = min(HEIGHT, HEIGHT - dy)
    out[y_src0 + dy : y_src1 + dy, x_src0 + dx : x_src1 + dx] = frame_rgb[y_src0:y_src1, x_src0:x_src1]
    return out

def assemble_master_video():
    tmp_wav = os.path.join(CLIPS_DIR, "_master_audio_v2.wav")
    tmp_video_only = os.path.join(CLIPS_DIR, "_master_video_only_v2.mp4")

    print("1/3 Generating 2:24 master soundtrack + Veo 3 native audio mix...", flush=True)
    generate_master_audio_v2(tmp_wav)

    print("2/3 Loading and compositing 18 scenes (3456 frames @ 1920x1080 24fps)...", flush=True)
    writer = imageio_ffmpeg.write_frames(
        tmp_video_only,
        size=(WIDTH, HEIGHT),
        fps=FPS,
        codec="libx264",
        pix_fmt_in="rgb24",
        pix_fmt_out="yuv420p",
        quality=8,
        macro_block_size=8,
        ffmpeg_log_level="error",
    )
    writer.send(None)

    scene_cache = {}
    def get_scene(idx):
        if idx not in scene_cache:
            print(f"  Loading clip scene_{idx:02d}.mp4...", flush=True)
            scene_cache[idx] = load_scene_frames(idx)
            for k in list(scene_cache.keys()):
                if k < idx - 1:
                    del scene_cache[k]
        return scene_cache[idx]

    for g_frame in range(TOTAL_FRAMES):
        s_idx = (g_frame // SCENE_FRAMES) + 1
        local_f = g_frame % SCENE_FRAMES

        curr_frames = get_scene(s_idx)
        base_frame = curr_frames[local_f]

        if s_idx < NUM_SCENES:
            t_type, t_len = BOUNDARY_TRANSITIONS.get(s_idx, ("cut", 0))
            if t_len > 0 and local_f >= SCENE_FRAMES - t_len:
                next_frames = get_scene(s_idx + 1)
                progress = (local_f - (SCENE_FRAMES - t_len) + 1) / float(t_len + 1)
                next_f = next_frames[min(SCENE_FRAMES - 1, local_f - (SCENE_FRAMES - t_len))]
                if t_type == "dissolve":
                    base_frame = np.clip(
                        base_frame.astype(np.float32) * (1.0 - progress) + next_f.astype(np.float32) * progress,
                        0, 255
                    ).astype(np.uint8)
                elif t_type == "whip":
                    base_frame = apply_whip_pan(base_frame, next_f, progress)

        composed = render_omni_typography_v2(base_frame, g_frame)

        # Apply 6-frame impact screen-shake at start of Scene 16 ($1,101.1M lock at 2:00.0)
        if s_idx == 16 and local_f < 6:
            composed = apply_screen_shake(composed, local_f)

        # Scene 18 cuts sharply to black on the very final frames (2:24.0)
        if s_idx == 18 and local_f >= SCENE_FRAMES - 2:
            composed = np.zeros_like(composed)

        writer.send(composed.tobytes())

        if (g_frame + 1) % 480 == 0:
            print(f"  Rendered {g_frame + 1}/{TOTAL_FRAMES} frames ({(g_frame + 1) // FPS}s / {TOTAL_SECONDS}s)...", flush=True)

    writer.close()

    print("3/3 Muxing final 1080p master video + 720p backup...", flush=True)
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    mux_cmd = [
        ffmpeg_exe, "-y",
        "-i", tmp_video_only,
        "-i", tmp_wav,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "320k",
        "-movflags", "+faststart",
        OUTPUT_MP4
    ]
    subprocess.run(mux_cmd, check=True)

    backup_cmd = [
        ffmpeg_exe, "-y",
        "-i", OUTPUT_MP4,
        "-vf", "scale=1280:720",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "copy",
        "-movflags", "+faststart",
        OUTPUT_720P_MP4
    ]
    subprocess.run(backup_cmd, check=True)

    os.remove(tmp_video_only)
    os.remove(tmp_wav)
    print(f"DONE! Master 1080p video saved at: {OUTPUT_MP4} ({os.path.getsize(OUTPUT_MP4)} bytes)", flush=True)
    print(f"DONE! Backup 720p video saved at: {OUTPUT_720P_MP4} ({os.path.getsize(OUTPUT_720P_MP4)} bytes)", flush=True)

def main():
    generate_all_v2_clips()
    assemble_master_video()

if __name__ == "__main__":
    main()
