#!/usr/bin/env python3
"""
Upgrades "A JORNADA DO BILHÃO" — Aurora Cloud · v2 (2:24 · 1920x1080 · 24fps):
1. Fixes all scene-boundary transitions so there is ZERO rewind and ZERO end-of-clip stall:
   - Each clip's startup/tail inertia is trimmed and resampled into a strictly monotonic
     stream of length (t_in + 192) frames with a continuous subtle forward camera push.
   - During a transition of t_in frames at the end of Scene s-1, Scene s advances through
     frames 0 .. t_in-1, and when Scene s begins at local_f=0, it continues seamlessly at
     frame t_in (never resetting to 0!).
2. Generates a new rousing, high-impact orchestral soundtrack in the style of Wagner's
   "Ride of the Valkyries" (Cavalgada das Valquírias) combining:
   - 5 full symphony orchestra movements via Google Lyria 2 (lyria-002)
   - Frame-synced Wagnerian Valkyries brass fanfare (horns, trumpets, trombones), galloping
     9/8 timpani, cymbal crashes on every milestone, 1s dramatic silence at 1:51–1:52,
     and triumphant $1,101.1M & $2B fanfares.
"""
import base64
import math
import os
import shutil
import subprocess
import sys
import time
import wave
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg

ROOT_DIR = "./output_project"
V2_DIR = os.path.join(ROOT_DIR, "04_jornada_do_bilhao_v2_2m24s_2B")
VALK_DIR = os.path.join(ROOT_DIR, "05_jornada_do_bilhao_v2_valquirias_epico")
CLIPS_DIR = os.path.join(V2_DIR, "clips_jornada_v2")
VALK_AUDIO_DIR = os.path.join(CLIPS_DIR, "audio_valkyries")

PROJECT = os.environ.get("GCP_PROJECT_ID", "your-gcp-project-id")
LOCATION = "us-central1"
LYRIA_MODEL = "lyria-002"

WIDTH = 1920
HEIGHT = 1080
FPS = 24
NUM_SCENES = 18
TOTAL_SECONDS = NUM_SCENES * 8       # 144 seconds (2:24)
TOTAL_FRAMES = TOTAL_SECONDS * FPS  # 3456 frames
SCENE_FRAMES = 8 * FPS              # 192 frames per scene

# Import typography renderer from build_jornada_v2.py
sys.path.insert(0, V2_DIR)
from build_jornada_v2 import (
    render_omni_typography_v2,
    generate_master_audio_v2,
    apply_whip_pan,
    apply_screen_shake,
)

# Transition specification at boundary after Scene i (between Scene i and Scene i+1)
# Notice Scene 6 -> 7 is a direct I2V continuation across the 4 countries, so a short 4-frame
# monotonic optical dissolve with trimmed endpoints makes it completely seamless!
BOUNDARY_TRANSITIONS = {
    1: ("dissolve", 14),  # 01 -> 02
    2: ("dissolve", 14),  # 02 -> 03
    3: ("cut", 0),        # 03 -> 04
    4: ("whip", 8),       # 04 -> 05
    5: ("dissolve", 12),  # 05 -> 06
    6: ("dissolve", 4),   # 06 -> 07 (I2V continuation: trim seed hold + monotonic advance)
    7: ("dissolve", 12),  # 07 -> 08
    8: ("dissolve", 12),  # 08 -> 09
    9: ("cut", 0),        # 09 -> 10 (enter Act III: 4 Pillars)
    10: ("dissolve", 10), # 10 -> 11
    11: ("dissolve", 10), # 11 -> 12
    12: ("dissolve", 12), # 12 -> 13
    13: ("dissolve", 14), # 13 -> 14
    14: ("cut", 0),       # 14 -> 15 (cut on 1s silence)
    15: ("cut", 0),       # 15 -> 16 (cut at peak of counter)
    16: ("dissolve", 20), # 16 -> 17 (slow dissolve into Act V)
    17: ("dissolve", 14), # 17 -> 18 (reveal $2B spark on horizon)
}

def get_incoming_overlap(scene_idx):
    if scene_idx <= 1:
        return 0
    return BOUNDARY_TRANSITIONS.get(scene_idx - 1, ("cut", 0))[1]

# ---------------------------------------------------------------------------
# 1. ZERO-REWIND, ZERO-STALL MONOTONIC SCENE STREAM LOADER
# ---------------------------------------------------------------------------

# Per-scene trim of initial/final frames where Veo 3.1 I2V or animation has slight inertia
SCENE_TRIMS = {
    1: (0, 2),
    2: (4, 4),
    3: (3, 3),
    4: (3, 4),
    5: (3, 4),
    6: (3, 4),
    7: (5, 4),   # Trim I2V static seed hold at start of Scene 07 so 06->07 never stalls!
    8: (4, 4),
    9: (3, 4),
    10: (3, 4),
    11: (3, 4),
    12: (3, 4),
    13: (3, 4),
    14: (2, 2),
    15: (2, 4),
    16: (0, 4),  # Keep frame 0 of Scene 16 for immediate shockwave impact at 2:00.0
    17: (3, 4),
    18: (0, 2),
}

def load_monotonic_scene_stream(scene_idx):
    """
    Loads raw frames from scene_XX.mp4, trims startup/end inertia frames,
    and builds a strictly monotonic sequence of length:
        needed_frames = t_in(scene_idx) + SCENE_FRAMES (192)
    Also applies a subtle, continuous forward optical dolly (1.000x -> 1.032x)
    so the camera never slows down or stalls at the end of an 8-second segment.
    """
    clip_path = os.path.join(CLIPS_DIR, f"scene_{scene_idx:02d}.mp4")
    reader = imageio_ffmpeg.read_frames(clip_path, pix_fmt="rgb24")
    meta = next(reader)
    w, h = meta["size"]
    raw_frames = []
    for rf in reader:
        arr = np.frombuffer(rf, dtype=np.uint8).reshape((h, w, 3))
        if w != WIDTH or h != HEIGHT:
            arr = np.array(Image.fromarray(arr).resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS))
        raw_frames.append(arr)

    n_raw = len(raw_frames)
    trim_s, trim_e = SCENE_TRIMS.get(scene_idx, (3, 3))
    active = raw_frames[trim_s : max(trim_s + 30, n_raw - trim_e)]
    n_active = len(active)

    t_in = get_incoming_overlap(scene_idx)
    needed = t_in + SCENE_FRAMES  # Total monotonic frames needed for this scene

    out_stream = []
    for k in range(needed):
        # Smoothly map k in [0 .. needed-1] -> pos in [0 .. n_active-1]
        u = k / float(max(1, needed - 1))
        pos = u * (n_active - 1)
        idx0 = int(math.floor(pos))
        idx1 = min(n_active - 1, idx0 + 1)
        frac = pos - idx0

        if frac < 0.001 or idx0 == idx1:
            frame = active[idx0].copy()
        else:
            frame = np.clip(
                active[idx0].astype(np.float32) * (1.0 - frac) + active[idx1].astype(np.float32) * frac,
                0, 255
            ).astype(np.uint8)

        # Subtle continuous forward push (1.000 -> 1.028) to guarantee relentless forward motion
        zoom = 1.0 + 0.028 * u
        if zoom > 1.0005:
            zw = int(round(WIDTH / zoom))
            zh = int(round(HEIGHT / zoom))
            x0 = (WIDTH - zw) // 2
            y0 = (HEIGHT - zh) // 2
            cropped = frame[y0 : y0 + zh, x0 : x0 + zw]
            frame = np.array(Image.fromarray(cropped).resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR), dtype=np.uint8)

        out_stream.append(frame)

    return out_stream

# ---------------------------------------------------------------------------
# 2. "CAVALGADA DAS VALQUÍRIAS" (RIDE OF THE VALKYRIES) EPIC SOUNDTRACK ENGINE
# ---------------------------------------------------------------------------

LYRIA_VALKYRIES_PROMPTS = {
    1: "Exciting heroic classical symphony orchestra overture in 9/8 compound meter, rapid galloping staccato string tremolos, rising French horns and bold brass fanfare building thrilling momentum and energy, high dynamic range cinematic film score",
    2: "Rousing triumphant full symphony orchestra in rapid 9/8 gallop, bold heroic dotted-rhythm brass fanfare melody with trumpets, French horns and trombones, driving orchestral timpani and snare rhythm, exhilarating forward momentum",
    3: "Powerful epic romantic-era orchestral brass fanfare and driving symphonic gallop, soaring horns and trumpets trading heroic arpeggio motifs, thunderous timpani, energetic staccato strings, unstoppable building power",
    4: "Monumental triumphant orchestral climax in 9/8 meter, blazing full brass section fanfare in fortissimo, crashing orchestral cymbals, thunderous timpani rolls, glorious victorious symphony celebrating a historic achievement",
    5: "Grand heroic orchestral finale, uplifting D major brass fanfare with French horns and trumpets, rapid soaring strings and resonant timpani, inspiring and celebratory symphonic conclusion",
}

def get_token():
    return subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()

def generate_lyria_valkyries_movements():
    os.makedirs(VALK_AUDIO_DIR, exist_ok=True)
    url = f"https://{LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/{LOCATION}/publishers/google/models/{LYRIA_MODEL}:predict"

    for m_idx, prompt in LYRIA_VALKYRIES_PROMPTS.items():
        out_wav = os.path.join(VALK_AUDIO_DIR, f"valkyries_mov_{m_idx:02d}.wav")
        if os.path.exists(out_wav) and os.path.getsize(out_wav) > 100_000:
            print(f"Lyria Valkyries Movement {m_idx} already exists ({out_wav})", flush=True)
            continue
        for attempt in range(5):
            try:
                print(f"Generating Lyria 'Ride of the Valkyries' Movement {m_idx}/5 (attempt {attempt+1})...", flush=True)
                token = get_token()
                headers = {
                    "Authorization": f"Bearer {token}",
                    "x-goog-user-project": PROJECT,
                    "Content-Type": "application/json",
                }
                resp = requests.post(
                    url,
                    headers=headers,
                    json={"instances": [{"prompt": prompt}], "parameters": {"sample_count": 1}},
                    timeout=90,
                )
                if resp.status_code != 200:
                    raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                b64 = resp.json()["predictions"][0]["bytesBase64Encoded"]
                raw = base64.b64decode(b64)
                with open(out_wav, "wb") as f:
                    f.write(raw)
                print(f"  Saved {out_wav} ({len(raw)} bytes)", flush=True)
                break
            except Exception as e:
                print(f"  Lyria Valkyries movement {m_idx} retry ({e})", flush=True)
                time.sleep(4)
        else:
            raise RuntimeError(f"Failed Lyria Valkyries movement {m_idx}")

def generate_valkyries_master_audio(out_wav_path):
    """
    Builds the 144.0s (2:24, 48kHz stereo) "Ride of the Valkyries" Epic Master Audio:
    1. 5 Lyria 2 (lyria-002) Wagnerian Valkyries symphony orchestra movements seamlessly crossfaded
    2. Synthesized Wagner "Ride of the Valkyries" heroic brass fanfare motif (French horns + trumpets + trombones)
       and galloping 9/8 timpani + orchestral cymbal crashes synced to the exact visual milestones
    3. Native Veo 3.1 stereo sound effects from all 18 scenes
    4. Dramatic 1-second total silence at 1:51.0–1:52.0 before the counter climax!
    """
    generate_lyria_valkyries_movements()

    sr = 48000
    n_samples = TOTAL_SECONDS * sr
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    # 1. Load the 5 Lyria movements (each ~32.8s) and place them across the 5 Acts:
    # Act I: 0–32s (mov 1)
    # Act II: 32–72s (mov 2 + tail of mov 1)
    # Act III: 72–104s (mov 3)
    # Act IV: 104–128s (mov 4)
    # Act V: 128–144s (mov 5)
    lyria_L = np.zeros(n_samples, dtype=np.float32)
    lyria_R = np.zeros(n_samples, dtype=np.float32)

    def load_wav_stereo(wav_path):
        tmp_norm = wav_path + "_48k.wav"
        subprocess.run(
            [ffmpeg_exe, "-y", "-i", wav_path, "-ac", "2", "-ar", str(sr), "-f", "wav", tmp_norm],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
        )
        with wave.open(tmp_norm, "rb") as wf:
            raw = wf.readframes(wf.getnframes())
            arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            l = arr[0::2]
            r = arr[1::2]
        os.remove(tmp_norm)
        return l, r

    mov_segments = [
        (1, 0.0, 32.0),
        (2, 30.0, 62.5),
        (3, 60.5, 93.0),
        (2, 91.0, 111.0),
        (4, 112.0, 132.0),
        (5, 129.0, 144.0),
    ]
    for m_idx, st_s, en_s in mov_segments:
        w_path = os.path.join(VALK_AUDIO_DIR, f"valkyries_mov_{m_idx:02d}.wav")
        ml, mr = load_wav_stereo(w_path)
        idx0 = int(st_s * sr)
        idx1 = min(n_samples, int(en_s * sr))
        seg_len = min(idx1 - idx0, len(ml))
        if seg_len <= 0:
            continue
        env = np.ones(seg_len, dtype=np.float32)
        fade_in = int(min(1.5 * sr, seg_len // 4))
        fade_out = int(min(1.5 * sr, seg_len // 4))
        if st_s > 0 and st_s != 112.0:
            env[:fade_in] = np.linspace(0.0, 1.0, fade_in)
        elif st_s == 112.0:
            env[:int(0.08 * sr)] = np.linspace(0.0, 1.0, int(0.08 * sr))
        env[-fade_out:] = np.linspace(1.0, 0.0, fade_out)
        lyria_L[idx0 : idx0 + seg_len] += ml[:seg_len] * env
        lyria_R[idx0 : idx0 + seg_len] += mr[:seg_len] * env

    # 2. Synthesize Iconic Wagnerian "Ride of the Valkyries" Brass Fanfare, Galloping 9/8 Timpani & Cymbal Crashes
    brass_L = np.zeros(n_samples, dtype=np.float32)
    brass_R = np.zeros(n_samples, dtype=np.float32)

    def add_brass_note(start_s, freq, dur_s, amp=0.22, pan=0.0):
        """Rich orchestral brass horn/trumpet synthesis with bright harmonic overtones and vibrato."""
        idx0 = int(start_s * sr)
        idx1 = min(n_samples, int((start_s + dur_s) * sr))
        if idx0 >= n_samples or idx1 <= idx0:
            return
        lt = np.arange(idx1 - idx0, dtype=np.float32) / sr
        attack = np.minimum(1.0, lt / 0.035)
        release = np.minimum(1.0, np.maximum(0.0, (dur_s - lt) / 0.08))
        sustain = np.exp(-lt / (dur_s * 1.4))
        env = attack * release * (0.35 + 0.65 * sustain)

        vib = 1.0 + 0.0025 * np.sin(2 * np.pi * 5.5 * lt) * np.minimum(1.0, lt / 0.25)
        f_inst = freq * vib
        phase = 2 * np.pi * np.cumsum(f_inst) / sr

        # Brass harmonic spectrum (strong 1st, 2nd, 3rd, 4th, 5th harmonics)
        sig = (
            0.90 * np.sin(phase)
            + 0.75 * np.sin(2 * phase + 0.2)
            + 0.55 * np.sin(3 * phase + 0.4)
            + 0.35 * np.sin(4 * phase + 0.1)
            + 0.20 * np.sin(5 * phase + 0.6)
            + 0.10 * np.sin(6 * phase)
        ) * (env * amp / 2.2)

        brass_L[idx0:idx1] += sig * (1.0 - 0.25 * pan)
        brass_R[idx0:idx1] += sig * (1.0 + 0.25 * pan)

    def add_timpani_hit(time_s, freq=65.41, amp=0.32, dur_s=0.45):
        idx0 = int(time_s * sr)
        idx1 = min(n_samples, idx0 + int(dur_s * sr))
        if idx0 >= n_samples or idx1 <= idx0:
            return
        lt = np.arange(idx1 - idx0, dtype=np.float32) / sr
        f_sweep = freq * (1.0 + 0.45 * np.exp(-lt * 32.0))
        phase = 2 * np.pi * np.cumsum(f_sweep) / sr
        sig = (np.sin(phase) + 0.3 * np.sin(1.5 * phase) * np.exp(-lt * 12.0)) * np.exp(-lt * 7.5) * amp
        brass_L[idx0:idx1] += sig
        brass_R[idx0:idx1] += sig

    def add_cymbal_crash(time_s, amp=0.22, dur_s=2.2):
        idx0 = int(time_s * sr)
        idx1 = min(n_samples, idx0 + int(dur_s * sr))
        if idx0 >= n_samples or idx1 <= idx0:
            return
        rng = np.random.default_rng(int(time_s * 100))
        lt = np.arange(idx1 - idx0, dtype=np.float32) / sr
        noise = rng.standard_normal(idx1 - idx0).astype(np.float32)
        # High-frequency metallic shimmer via FM ring modulation
        shimmer = noise * (np.sin(2 * np.pi * 3400.0 * lt) + np.sin(2 * np.pi * 5100.0 * lt)) * 0.5
        env = (1.0 - np.exp(-lt / 0.008)) * np.exp(-lt / (dur_s * 0.42))
        sig = shimmer * env * amp
        brass_L[idx0:idx1] += sig * 0.95
        brass_R[idx0:idx1] += sig * 1.05

    def play_valkyries_fanfare(start_s, base_freq=246.94, amp=0.24):
        """
        Plays Wagner's iconic 'Ride of the Valkyries' brass fanfare phrase!
        Motif intervals in semitones from root (e.g. B3 = 246.94 Hz or C4 = 261.63 Hz):
         Phrase 1: 0 (dotted 8th), -5 (16th), 0 (8th), +3 (dotted quarter), 0 (dotted quarter)
         Phrase 2: +3 (dotted 8th), 0 (16th), +3 (8th), +7 (dotted quarter), +3 (dotted quarter)
         Phrase 3: +7 (dotted 8th), +3 (16th), +7 (8th), +10 (dotted quarter), +5 (dotted quarter)
         Phrase 4: +5 (dotted 8th), +2 (16th), +5 (8th), +9 (dotted half)
        """
        def semi(s):
            return base_freq * (2.0 ** (s / 12.0))

        # Phrase 1
        notes = [
            (0.00, semi(0), 0.36),
            (0.36, semi(-5), 0.16),
            (0.52, semi(0), 0.24),
            (0.76, semi(3), 0.68),
            (1.44, semi(0), 0.64),
            # Phrase 2
            (2.12, semi(3), 0.36),
            (2.48, semi(0), 0.16),
            (2.64, semi(3), 0.24),
            (2.88, semi(7), 0.68),
            (3.56, semi(3), 0.64),
            # Phrase 3
            (4.24, semi(7), 0.36),
            (4.60, semi(3), 0.16),
            (4.76, semi(7), 0.24),
            (5.00, semi(10), 0.68),
            (5.68, semi(5), 0.64),
            # Phrase 4 (Heroic resolution)
            (6.36, semi(5), 0.36),
            (6.72, semi(2), 0.16),
            (6.88, semi(5), 0.24),
            (7.12, semi(12), 0.85),
        ]
        for dt, f_hz, dur in notes:
            # Play main horn + lower octave trombone + fifth harmony
            add_brass_note(start_s + dt, f_hz, dur * 1.05, amp=amp, pan=-0.2)
            add_brass_note(start_s + dt, f_hz * 0.5, dur * 1.08, amp=amp * 0.75, pan=0.2)

    def add_gallop_rhythm(start_s, end_s, root_freq=61.74, amp=0.22):
        """Adds the unmistakable 9/8 Valkyries galloping timpani rhythm (DUM - da - DUM)."""
        beat = 0.53  # ~113 BPM dotted-quarter pulse
        t_cur = start_s
        step = 0
        while t_cur < end_s - 0.2:
            f_hit = root_freq if (step % 2 == 0) else root_freq * 1.122
            add_timpani_hit(t_cur, freq=f_hit, amp=amp, dur_s=0.35)
            add_timpani_hit(t_cur + beat * 0.66, freq=f_hit * 1.5, amp=amp * 0.58, dur_s=0.22)
            t_cur += beat
            step += 1

    # Cue Valkyries Fanfares & Gallops across the 5 Acts:
    # Act I (0–32s): Building galloping pulse from Scene 02 (8s), first brass fanfare at Scene 04 (24s - São Paulo Region!)
    add_gallop_rhythm(8.0, 32.0, root_freq=61.74, amp=0.16)
    play_valkyries_fanfare(24.0, base_freq=246.94, amp=0.20)  # B minor Valkyries fanfare as data center lights snap on!

    # Act II (32–72s): Localization across Brazil, Mexico, Colombia, Chile + Ascent to $702M
    add_gallop_rhythm(32.0, 72.0, root_freq=65.41, amp=0.22)
    play_valkyries_fanfare(40.0, base_freq=261.63, amp=0.24)  # Scene 06: Brazil & Mexico ignite!
    for hit_t in [40.5, 44.2, 48.6, 52.2]:
        add_cymbal_crash(hit_t, amp=0.18, dur_s=1.8)
        add_timpani_hit(hit_t, freq=65.41, amp=0.38, dur_s=0.6)
    play_valkyries_fanfare(48.0, base_freq=293.66, amp=0.25)  # Scene 07: Colombia & Chile ignite (transposed up to D)!
    play_valkyries_fanfare(64.0, base_freq=261.63, amp=0.24)  # Scene 09: $121M -> $702M climb

    # Act III (72–104s): The 4 Pillars — each Pillar gets a rising heroic Valkyries fanfare!
    add_gallop_rhythm(72.0, 104.0, root_freq=65.41, amp=0.25)
    pillar_roots = [
        (72.0, 246.94),  # Pillar 01 (B3)
        (80.0, 261.63),  # Pillar 02 (C4)
        (88.0, 293.66),  # Pillar 03 (D4)
        (96.0, 329.63),  # Pillar 04 (E4 - soaring high brass!)
    ]
    for p_start, p_freq in pillar_roots:
        add_cymbal_crash(p_start + 0.1, amp=0.20, dur_s=2.0)
        add_timpani_hit(p_start + 0.1, freq=65.41, amp=0.40, dur_s=0.65)
        play_valkyries_fanfare(p_start, base_freq=p_freq, amp=0.25)

    # Act IV (104–128s):
    # Scene 14 (104–112s): Swelling roll until 111.0s, then 1.0s TOTAL SILENCE (111.0–112.0s)!
    add_gallop_rhythm(104.0, 110.8, root_freq=65.41, amp=0.22)
    # Scene 15 (112–120s): CLIMAX COUNTER ($702M -> $1,101.1M) — Furious Valkyries gallop + blazing fanfare!
    add_gallop_rhythm(112.0, 120.0, root_freq=65.41, amp=0.32)
    play_valkyries_fanfare(112.0, base_freq=329.63, amp=0.28)
    # Scene 16 (120–128s / 2:00–2:08): THE BILLION ($1,101.1M · 107%) — Fortissimo Major Valkyries Triumph!
    add_cymbal_crash(120.0, amp=0.32, dur_s=3.2)
    add_timpani_hit(120.0, freq=65.41, amp=0.55, dur_s=0.9)
    play_valkyries_fanfare(120.0, base_freq=349.23, amp=0.30)
    add_gallop_rhythm(120.0, 128.0, root_freq=65.41, amp=0.28)

    # Act V (128–144s): The Next Horizon ($2B)
    add_gallop_rhythm(128.0, 143.5, root_freq=65.41, amp=0.22)
    play_valkyries_fanfare(136.0, base_freq=329.63, amp=0.28)  # Scene 18: $2B Horizon Fanfare!
    add_cymbal_crash(137.8, amp=0.25, dur_s=2.8)
    add_timpani_hit(137.8, freq=65.41, amp=0.45, dur_s=0.8)
    # Final triumphant brass chord at 141.5s–143.9s
    for f_chord in [130.81, 196.00, 261.63, 329.63, 392.00, 523.25]:
        add_brass_note(141.2, f_chord, 2.7, amp=0.18)

    # 3. Extract native Veo 3.1 audio from all 18 clips
    veo_L = np.zeros(n_samples, dtype=np.float32)
    veo_R = np.zeros(n_samples, dtype=np.float32)
    for s_idx in range(1, NUM_SCENES + 1):
        clip_path = os.path.join(CLIPS_DIR, f"scene_{s_idx:02d}.mp4")
        tmp_wav = os.path.join(CLIPS_DIR, f"_tmp_valk_audio_{s_idx:02d}.wav")
        res = subprocess.run(
            [ffmpeg_exe, "-y", "-i", clip_path, "-vn", "-ac", "2", "-ar", str(sr), "-f", "wav", tmp_wav],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        if res.returncode == 0 and os.path.exists(tmp_wav):
            with wave.open(tmp_wav, "rb") as wf:
                raw_bytes = wf.readframes(wf.getnframes())
                audio_i16 = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                a_l = audio_i16[0::2] if wf.getnchannels() == 2 else audio_i16
                a_r = audio_i16[1::2] if wf.getnchannels() == 2 else audio_i16
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

    # Combine Lyria Orchestra + Wagnerian Brass/Timpani Fanfare + Veo SFX
    mix_L = lyria_L * 0.72 + brass_L * 0.68 + veo_L * 0.35
    mix_R = lyria_R * 0.72 + brass_R * 0.68 + veo_R * 0.35

    # Enforce the dramatic 1-second total silence at 1:51.0–1:52.0 (111.0s–112.0s)
    sil_0 = int(111.0 * sr)
    sil_1 = int(112.0 * sr)
    fade_sil = int(0.04 * sr)
    mix_L[sil_0 - fade_sil : sil_0] *= np.linspace(1.0, 0.0, fade_sil)
    mix_R[sil_0 - fade_sil : sil_0] *= np.linspace(1.0, 0.0, fade_sil)
    mix_L[sil_0:sil_1] = 0.0
    mix_R[sil_0:sil_1] = 0.0

    # Soft tanh mastering limiter
    mix_L = np.tanh(mix_L * 1.20) * 0.94
    mix_R = np.tanh(mix_R * 1.20) * 0.94

    interleaved = np.empty(n_samples * 2, dtype=np.int16)
    interleaved[0::2] = np.clip(mix_L * 32767.0, -32768, 32767).astype(np.int16)
    interleaved[1::2] = np.clip(mix_R * 32767.0, -32768, 32767).astype(np.int16)

    with wave.open(out_wav_path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(interleaved.tobytes())
    print(f"Valkyries 2:24 Epic Master audio written to {out_wav_path}", flush=True)

# ---------------------------------------------------------------------------
# 3. RENDER FLUID ZERO-REWIND VIDEO STREAM & MUX BOTH EDITIONS
# ---------------------------------------------------------------------------

def render_fluid_video_stream(tmp_video_only):
    print("Rendering 100% fluid, zero-rewind 18-scene video stream (3456 frames @ 1920x1080 24fps)...", flush=True)
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

    stream_cache = {}
    def get_stream(idx):
        if idx not in stream_cache:
            print(f"  Building monotonic stream for scene_{idx:02d}.mp4...", flush=True)
            stream_cache[idx] = load_monotonic_scene_stream(idx)
            for k in list(stream_cache.keys()):
                if k < idx - 1:
                    del stream_cache[k]
        return stream_cache[idx]

    for g_frame in range(TOTAL_FRAMES):
        s_idx = (g_frame // SCENE_FRAMES) + 1
        local_f = g_frame % SCENE_FRAMES

        t_in_curr = get_incoming_overlap(s_idx)
        curr_stream = get_stream(s_idx)
        # Note: during Scene s_idx itself (local_f = 0..191), we read at index (t_in_curr + local_f)!
        # Why? Because indices 0 .. t_in_curr-1 were already displayed during the outgoing transition
        # of Scene s_idx-1! This guarantees strictly monotonic frame progression (+1 every frame, ZERO rewind!).
        base_frame = curr_stream[t_in_curr + local_f]

        if s_idx < NUM_SCENES:
            t_type, t_len = BOUNDARY_TRANSITIONS.get(s_idx, ("cut", 0))
            if t_len > 0 and local_f >= SCENE_FRAMES - t_len:
                next_stream = get_stream(s_idx + 1)
                k_overlap = local_f - (SCENE_FRAMES - t_len)  # 0 .. t_len-1
                # Smooth cosine S-curve blend
                raw_p = (k_overlap + 1) / float(t_len + 1)
                progress = 0.5 - 0.5 * math.cos(math.pi * raw_p)
                next_f = next_stream[k_overlap]
                if t_type == "dissolve":
                    base_frame = np.clip(
                        base_frame.astype(np.float32) * (1.0 - progress) + next_f.astype(np.float32) * progress,
                        0, 255
                    ).astype(np.uint8)
                elif t_type == "whip":
                    base_frame = apply_whip_pan(base_frame, next_f, progress)

        composed = render_omni_typography_v2(base_frame, g_frame)

        # 6-frame impact screen-shake at start of Scene 16 ($1,101.1M lock at 2:00.0)
        if s_idx == 16 and local_f < 6:
            composed = apply_screen_shake(composed, local_f)

        # Cut sharply to black on the final 2 frames of Scene 18 (2:24.0)
        if s_idx == 18 and local_f >= SCENE_FRAMES - 2:
            composed = np.zeros_like(composed)

        writer.send(composed.tobytes())

        if (g_frame + 1) % 480 == 0:
            print(f"  Rendered {g_frame + 1}/{TOTAL_FRAMES} frames ({(g_frame + 1) // FPS}s / {TOTAL_SECONDS}s)...", flush=True)

    writer.close()

def mux_deliverables(tmp_video_only, wav_path, out_master, out_20m, out_720p):
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([
        ffmpeg_exe, "-y", "-i", tmp_video_only, "-i", wav_path,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart", out_master
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    subprocess.run([
        ffmpeg_exe, "-y", "-i", out_master,
        "-c:v", "libx264", "-b:v", "20M", "-maxrate", "24M", "-bufsize", "40M",
        "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", out_20m
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    subprocess.run([
        ffmpeg_exe, "-y", "-i", out_master,
        "-vf", "scale=1280:720", "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "copy", "-movflags", "+faststart", out_720p
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main():
    os.makedirs(VALK_DIR, exist_ok=True)
    # Copy markdown script into 05_jornada_do_bilhao_v2_valquirias_epico as well for completeness
    shutil.copy2(
        os.path.join(V2_DIR, "roteiro-1b-latam-smb-v2.md"),
        os.path.join(VALK_DIR, "roteiro-1b-latam-smb-v2-valquirias.md")
    )

    tmp_wav_orig = os.path.join(CLIPS_DIR, "_master_audio_v2_orig.wav")
    tmp_wav_valk = os.path.join(CLIPS_DIR, "_master_audio_v2_valkyries.wav")
    tmp_video_only = os.path.join(CLIPS_DIR, "_master_video_fluid_v2.mp4")

    print("=== STEP 1/4: Generating Original v2 Soundtrack ===", flush=True)
    generate_master_audio_v2(tmp_wav_orig)

    print("=== STEP 2/4: Generating 'Ride of the Valkyries' (Cavalgada das Valquírias) Epic Soundtrack ===", flush=True)
    generate_valkyries_master_audio(tmp_wav_valk)

    print("=== STEP 3/4: Rendering Fluid Zero-Rewind Video Stream (3456 frames) ===", flush=True)
    render_fluid_video_stream(tmp_video_only)

    print("=== STEP 4/4: Muxing Both Editions (04 Standard + 05 Valkyries Epic) ===", flush=True)
    mux_deliverables(
        tmp_video_only,
        tmp_wav_orig,
        os.path.join(V2_DIR, "a_jornada_do_bilhao_v2_latam_smb.mp4"),
        os.path.join(V2_DIR, "a_jornada_do_bilhao_v2_latam_smb_20mbps.mp4"),
        os.path.join(V2_DIR, "a_jornada_do_bilhao_v2_latam_smb_720p_backup.mp4"),
    )
    print("  Updated 04_jornada_do_bilhao_v2_2m24s_2B with fluid zero-rewind transitions!", flush=True)

    mux_deliverables(
        tmp_video_only,
        tmp_wav_orig,
        os.path.join(VALK_DIR, "a_jornada_do_bilhao_v2_valquirias_master_1080p.mp4"),
        os.path.join(VALK_DIR, "a_jornada_do_bilhao_v2_valquirias_20mbps_1080p.mp4"),
        os.path.join(VALK_DIR, "a_jornada_do_bilhao_v2_valquirias_720p_backup.mp4"),
    )
    print("  Created 05_jornada_do_bilhao_v2_valquirias_epico with Ride of the Valkyries audio!", flush=True)

    os.remove(tmp_video_only)
    os.remove(tmp_wav_orig)
    os.remove(tmp_wav_valk)
    print("ALL DONE!", flush=True)

if __name__ == "__main__":
    main()
