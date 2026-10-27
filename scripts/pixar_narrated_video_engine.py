#!/usr/bin/env python3
"""
upgrade_semente_v4_master.py — Complete V4 Studio Upgrade for "A Semente — Aurora Cloud" (2:00, 15 Scenes)

Fixes & Upgrades:
1. ZERO SCENE STUTTER ("sem travada"):
   - Eliminates the frame-reset rewind bug in assemble_v3_omni.py where outgoing dissolves played frames
     0..tdur-1 of Scene s+1 and then reset to frame 0 when Scene s+1 started.
   - Trims initial low-motion keyframe frames on Veo 3.1 I2V clips (Scenes 4, 5, 6, 13, 15).
   - Uses strictly monotonic frame progression across every single cut and cross-dissolve.
2. COMPLETE SCRIPT NARRATION (EN-US & PT-BR) via Cloud TTS Chirp 3 HD (Charon):
   - Incorporates all missing factual milestones from the official script:
     * 2016-2017: Segment creation across 33 countries, first South America GCP region in São Paulo (Sept 19, 2017),
       2018 Chile hub, and $121M first full year.
     * 2019-2020: Localization across the 4 core countries (Brazil, Mexico, Colombia, Chile) — local resources,
       local currency, FOPs, and the Territory Lead (TL) Program — scaling GCP from $7M to $27M and
       Google Workspace from $114M to $181M.
     * 2023-2024: The 4 Strategic Pillars (Local Presence/FOPs in 5 countries, Scaled Motion with TL & SST,
       Partner Ecosystem led by TD SYNNEX, and Full-Stack Portfolio of Google Workspace + GCP + AI),
       expanding from 78 to 89 FTEs across 5 hubs and all 8 One Google cross-functional areas to reach $702M.
     * FY26 Q4: Crossing $1B to reach $1,101.1M (107% of target), with exact 1.0s dramatic silence at 1:35.0-1:36.0.
     * Next Horizon: Planting the next seed toward $2B ("Onward to two billion" / "Rumo aos dois bilhões").
3. NEW PROFESSIONAL LYRIA 3 (lyria-3-pro-preview & lyria-3-clip-preview) SOUNDTRACK & STUDIO MIX:
   - Uses Google Lyria 3 Pro (`lyria-3-pro-preview`) continuous 2-minute symphony score (`lyria3_pro_full.wav`)
     combined with Lyria 3 Clip (`lyria-3-clip-preview`) triumphant orchestral fanfare (`lyria3_clip_04.wav`)
     after the 1.0-second dramatic silence at 1:35.0-1:36.0, resolving into the warm acoustic piano finale.
   - Studio lookahead sidechain ducking (150ms attack, 650ms hold across word gaps, 950ms cosine release)
     so the music breathes naturally without pumping between syllables.
"""

import base64
import concurrent.futures
import json
import math
import os
import subprocess
import urllib.error
import urllib.request
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter1d, maximum_filter1d, uniform_filter1d
from scipy.signal import butter, sosfiltfilt

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import google.oauth2.service_account as sa

BASE_DIR = Path("./output_project")
CLIPS_DIR = BASE_DIR / "clips_v3"
AUDIO_DIR = CLIPS_DIR / "audio_v4"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

WIDTH, HEIGHT = 1920, 1080
FPS = 24
SCENE_DUR = 8.0
NUM_SCENES = 15
TOTAL_DUR = NUM_SCENES * SCENE_DUR  # 120.0s
TOTAL_FRAMES = int(TOTAL_DUR * FPS)  # 2880 frames
SR = 48000

SA_KEY_PATH = ""
ADC_PATH = ""
TTS_PROJECT = os.environ.get("GCP_PROJECT_ID", "your-gcp-project-id")
LYRIA_PROJECT = os.environ.get("GCP_PROJECT_ID", "your-gcp-project-id")
LYRIA_LOCATION = "global"
LYRIA_PRO_MODEL = "lyria-3-pro-preview"
LYRIA_CLIP_MODEL = "lyria-3-clip-preview"

# Google Brand Colors
C_BLUE = (66, 133, 244)
C_RED = (234, 67, 53)
C_YELLOW = (251, 188, 5)
C_GREEN = (52, 168, 83)
C_WHITE = (255, 255, 255)

FONT_SANS_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_SANS_REG = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_FUTURA = "/System/Library/Fonts/Supplemental/Futura.ttc"

# Start-frame trim table to remove initial static keyframe frames on Veo 3.1 I2V clips
START_TRIM_FRAMES = {
    1: 1,
    2: 1,
    3: 1,
    4: 4,  # start_diffs=[0.58, 0.34, 0.24, 0.26] -> trim 4 slow frames
    5: 3,  # start_diffs=[0.29, 0.31, 0.45] -> trim 3 slow frames
    6: 4,  # start_diffs=[1.0, 1.0, 1.0, 0.98] -> trim 4 slow frames
    7: 1,
    8: 1,
    9: 1,
    10: 1,
    11: 1,
    12: 1,
    13: 2,  # start_diffs=[1.31, 1.16] -> trim 2 slow frames
    14: 1,
    15: 4,  # start_diffs=[1.01, 0.99, 0.94, 1.0] -> trim 4 slow frames
}


# ==============================================================================
# 1. CREDENTIAL HELPERS (Non-interactive, zero gcloud CLI hang)
# ==============================================================================
def get_tts_token() -> str:
    creds = sa.Credentials.from_service_account_file(
        SA_KEY_PATH,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    creds.refresh(Request())
    return creds.token


def get_adc_token() -> str:
    with open(ADC_PATH, "r") as f:
        adc = json.load(f)
    creds = Credentials(
        token=None,
        refresh_token=adc["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=adc["client_id"],
        client_secret=adc["client_secret"],
    )
    creds.refresh(Request())
    return creds.token


# ==============================================================================
# 2. COMPLETE V4 NARRATION SCRIPT (EN-US & PT-BR) WITH ALL MISSING POINTS
# ==============================================================================
SCENES_META = {
    1: {
        "act": 1,
        "time": "0:00–0:08",
        "vo_offset": 0.45,
        "vo_en": "Second half of twenty sixteen. Every great transformation begins as something almost invisible: a single seed.",
        "vo_ptbr": "Segundo semestre de dois mil e dezesseis. Toda grande transformação começa quase invisível: uma única semente.",
        "badge": "H2 2016 · THE FIRST SEED",
        "badge_pt": "2º SEM 2016 · A PRIMEIRA SEMENTE",
        "headline": "",
        "headline_pt": "",
        "sub": "LATAM Small & Medium Business",
        "sub_pt": "Pequenas e Médias Empresas da América Latina",
        "accent": C_YELLOW,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    2: {
        "act": 1,
        "time": "0:08–0:16",
        "vo_offset": 0.35,
        "vo_en": "A handful of pioneers in one room, mapping thirty-three countries and millions of small businesses across Latin America.",
        "vo_ptbr": "Um pequeno grupo de pioneiros em uma sala, mapeando trinta e três países e milhões de pequenas empresas pela América Latina.",
        "badge": "2016 · THE PIONEERS",
        "badge_pt": "2016 · OS PIONEIROS",
        "headline": "33 Countries",
        "headline_pt": "33 Países",
        "sub": "One small team · One shared blueprint for Aurora Cloud",
        "sub_pt": "Um pequeno time · Um plano único para SMB na América Latina",
        "accent": C_BLUE,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    3: {
        "act": 1,
        "time": "0:16–0:24",
        "vo_offset": 0.35,
        "vo_en": "They didn't have scale yet — they had conviction. Planting the first roots in Brazil and igniting the continent.",
        "vo_ptbr": "Eles ainda não tinham escala — tinham convicção. Plantando as primeiras raízes no Brasil e iluminando o continente.",
        "badge": "CONVICTION BEFORE SCALE",
        "badge_pt": "CONVICÇÃO ANTES DA ESCALA",
        "headline": "",
        "headline_pt": "",
        "sub": "First spark in São Paulo · Extending across South & Central America",
        "sub_pt": "A primeira faísca em São Paulo · Expandindo pelas Américas",
        "accent": C_YELLOW,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    4: {
        "act": 2,
        "time": "0:24–0:32",
        "vo_offset": 0.30,
        "vo_en": "In September twenty seventeen, South America's first Google Cloud region went live in São Paulo, followed by the Chile hub.",
        "vo_ptbr": "Em setembro de dois mil e dezessete, nasceu em São Paulo a primeira região de Cloud na América do Sul, seguida pelo hub do Chile.",
        "badge": "SEPT 19, 2017 · INFRASTRUCTURE",
        "badge_pt": "19 SET 2017 · INFRAESTRUTURA",
        "headline": "São Paulo & Chile",
        "headline_pt": "São Paulo e Chile",
        "sub": "1st Google Cloud Region in South America (2017) · Chile Hub (2018)",
        "sub_pt": "1ª Região Google Cloud na América do Sul (2017) · Hub Chile (2018)",
        "accent": C_BLUE,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    5: {
        "act": 2,
        "time": "0:32–0:40",
        "vo_offset": 0.35,
        "vo_en": "By the end of its first full year, that tiny sprout was standing tall at one hundred and twenty-one million dollars.",
        "vo_ptbr": "Ao final do primeiro ano completo, aquele pequeno broto já se erguia forte em cento e vinte e um milhões de dólares.",
        "badge": "2017 · FIRST FULL YEAR",
        "badge_pt": "2017 · PRIMEIRO ANO COMPLETO",
        "headline": "$121M",
        "headline_pt": "US$ 121M",
        "sub": "First Full Year Revenue · The Sprout Was Standing",
        "sub_pt": "Receita do 1º Ano Completo · O Broto Estava de Pé",
        "accent": C_GREEN,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    6: {
        "act": 2,
        "time": "0:40–0:48",
        "vo_offset": 0.28,
        "vo_en": "In twenty nineteen, local currency, FOPs, and the TL Program grew GCP from seven to twenty-seven million, and Workspace to one-eighty-one million.",
        "vo_ptbr": "Com moeda local, FOPs e TL, o GCP saltou para vinte e sete milhões e o Workspace chegou a cento e oitenta e um milhões.",
        "badge": "2019–2020 · LOCALIZATION ENGINE",
        "badge_pt": "2019–2020 · MOTOR DE LOCALIZAÇÃO",
        "headline": "GCP $7M→$27M · GWS $181M",
        "headline_pt": "GCP $7M→$27M · GWS $181M",
        "sub": "Local Currency · Local FOPs · Territory Lead (TL) Program · Workspace $114M→$181M",
        "sub_pt": "Moeda Local · FOPs Locais · Programa Territory Lead (TL) · Workspace $114M→$181M",
        "accent": C_YELLOW,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    7: {
        "act": 3,
        "time": "0:48–0:56",
        "vo_offset": 0.35,
        "vo_en": "Four strategic pillars anchored the tree. First: deep local presence across Brazil, Mexico, Colombia, Chile, and Peru.",
        "vo_ptbr": "Quatro pilares firmaram a árvore. Primeiro: presença local no Brasil, México, Colômbia, Chile e Peru.",
        "badge": "PILLAR 1 · LOCAL PRESENCE & FOPs",
        "badge_pt": "PILAR 1 · PRESENÇA LOCAL E FOPs",
        "headline": "BR · MX · CO · CL · PE",
        "headline_pt": "BR · MX · CO · CL · PE",
        "sub": "4 Core Localized Markets (Brazil, Mexico, Colombia, Chile) + Peru Hub",
        "sub_pt": "4 Mercados Core Localizados (Brasil, México, Colômbia, Chile) + Hub Peru",
        "accent": C_BLUE,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    8: {
        "act": 3,
        "time": "0:56–1:04",
        "vo_offset": 0.30,
        "vo_en": "Second and third: high-velocity Scaled Motion with SST, and a massive partner ecosystem led by TD SYNNEX across the region.",
        "vo_ptbr": "Segundo e terceiro: escala veloz com TL e SST, e milhares de parceiros liderados pela TD SYNNEX.",
        "badge": "PILLARS 2 & 3 · SCALE & PARTNERS",
        "badge_pt": "PILARES 2 E 3 · ESCALA E PARCEIROS",
        "headline": "TL + SST · TD SYNNEX",
        "headline_pt": "TL + SST · TD SYNNEX",
        "sub": "High-Velocity Scaled Motion · Thousands of Regional Partners",
        "sub_pt": "Movimento Escalado de Alta Velocidade · Milhares de Parceiros Regionais",
        "accent": C_GREEN,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    9: {
        "act": 3,
        "time": "1:04–1:12",
        "vo_offset": 0.35,
        "vo_en": "By twenty twenty-four, expanding from seventy-eight to eighty-nine specialists across five hubs propelled the business to seven hundred and two million dollars.",
        "vo_ptbr": "Em dois mil e vinte e quatro, oitenta e nove especialistas em cinco hubs levaram o negócio a setecentos e dois milhões de dólares.",
        "badge": "2023–2024 · ACCELERATION",
        "badge_pt": "2023–2024 · ACELERAÇÃO",
        "headline": "$702M",
        "headline_pt": "US$ 702M",
        "sub": "78 → 89 FTEs Across 5 Regional Hubs · Unstoppable Momentum",
        "sub_pt": "78 → 89 FTEs em 5 Hubs Regionais · Crescimento Imparável",
        "accent": C_YELLOW,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    10: {
        "act": 3,
        "time": "1:12–1:20",
        "vo_offset": 0.30,
        "vo_en": "Fourth: our full-stack portfolio — Google Workspace, GCP, and AI — united as One Google across all eight functions.",
        "vo_ptbr": "Quarto pilar: o portfólio completo de Workspace, GCP e IA — unidos como One Google nas oito áreas.",
        "badge": "PILLAR 4 · FULL-STACK & ONE GOOGLE",
        "badge_pt": "PILAR 4 · PORTFÓLIO COMPLETO E ONE GOOGLE",
        "headline": "Workspace + GCP + AI",
        "headline_pt": "Workspace + GCP + IA",
        "sub": "Sales · Eng · Marketing · Partners · Finance · gTech · Legal · People Ops",
        "sub_pt": "Vendas · Eng · Marketing · Parceiros · Finanças · gTech · Jurídico · People Ops",
        "accent": C_RED,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    11: {
        "act": 3,
        "time": "1:20–1:28",
        "vo_offset": 0.35,
        "vo_en": "Ten years. Hundreds of people who watered the same tree — many without ever knowing which branch was theirs.",
        "vo_ptbr": "Dez anos. Centenas de pessoas que regaram a mesma árvore — muitas sem nunca saber qual galho era o seu.",
        "badge": "2016 – 2026 · TEN YEARS",
        "badge_pt": "2016 – 2026 · DEZ ANOS",
        "headline": "10 Years of Legacy",
        "headline_pt": "10 Anos de Legado",
        "sub": "Every builder, past and present, lives in this canopy",
        "sub_pt": "Cada construtor, do passado e do presente, vive nesta copa",
        "accent": C_YELLOW,
        "trans_type": "dissolve",
        "trans_dur": 16,
    },
    12: {
        "act": 3,
        "time": "1:28–1:36",
        "vo_offset": 2.30,  # Dynamically aligned so speech ends at 6.85s (1:34.85) -> 1.15s pure silence before 1:36.0!
        "vo_en": "Today, that luminous canopy covers all of Latin America. And then...",
        "vo_ptbr": "Hoje, essa copa luminosa cobre toda a América Latina. E então...",
        "badge": "LATAM CANOPY · THE THRESHOLD",
        "badge_pt": "COPA LATAM · O LIMIAR HISTÓRICO",
        "headline": "",
        "headline_pt": "",
        "sub": "33 Countries · One Living Ecosystem",
        "sub_pt": "33 Países · Um Ecossistema Vivo",
        "accent": C_BLUE,
        "trans_type": "cut",  # Dramatic cut after 1.0s silence at 1:35.0-1:36.0!
        "trans_dur": 0,
    },
    13: {
        "act": 4,
        "time": "1:36–1:44",
        "vo_offset": 0.08,
        "vo_en": "One billion. Not a forecast, not a dream — a historic fact: one point one billion dollars.",
        "vo_ptbr": "Um bilhão. Não uma previsão, não um sonho — um fato histórico: um vírgula um bilhão de dólares.",
        "badge": "HISTORIC MILESTONE · THE BILLION",
        "badge_pt": "MARCO HISTÓRICO · O BILHÃO",
        "headline": "COUNTER",  # Dynamic animated counter $702M -> $1,101.1M
        "headline_pt": "COUNTER",
        "sub": "Aurora Cloud Revenue · From $121M to $1,101.1M",
        "sub_pt": "Receita Aurora Cloud · De US$ 121M para US$ 1.101,1M",
        "accent": C_YELLOW,
        "trans_type": "dissolve",
        "trans_dur": 12,
    },
    14: {
        "act": 4,
        "time": "1:44–1:52",
        "vo_offset": 0.30,
        "vo_en": "One billion, one hundred and one point one million dollars — reaching one hundred and seven percent of target in Q4!",
        "vo_ptbr": "Um bilhão, cento e um vírgula um milhões de dólares — atingindo cento e sete por cento da meta no quarto trimestre!",
        "badge": "FY26 Q4 · 107% OF TARGET",
        "badge_pt": "FY26 Q4 · 107% DA META",
        "headline": "$1,101.1M · 107%",
        "headline_pt": "US$ 1.101,1M · 107%",
        "sub": "Overachievement Across Every Pillar · One Google LATAM",
        "sub_pt": "Superação em Todos os Pilares · One Google LATAM",
        "accent": C_GREEN,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    15: {
        "act": 4,
        "time": "1:52–2:00",
        "vo_offset": 0.30,
        "vo_en": "The first billion took ten years to grow. Now the next seed is already in motion. Thank you, Aurora Cloud — onward to two billion.",
        "vo_ptbr": "O primeiro bilhão levou dez anos. A nova semente já germina. Obrigado, Aurora Cloud — rumo aos dois bilhões.",
        "badge": "2016 – 2026 · THE NEXT HORIZON",
        "badge_pt": "2016 – 2026 · O PRÓXIMO HORIZONTE",
        "headline": "$1B Achieved · Onward to $2B",
        "headline_pt": "US$ 1B Alcançado · Rumo aos US$ 2B",
        "sub": "Thank you to every pioneer and partner who made this grow.",
        "sub_pt": "Obrigado a cada pioneiro e parceiro que fez essa história crescer.",
        "accent": C_YELLOW,
        "trans_type": "fade_out",
        "trans_dur": 24,
    },
}


# ==============================================================================
# 3. LYRIA 3 (lyria-3-pro-preview & lyria-3-clip-preview) SCORE GENERATION
# ==============================================================================
LYRIA3_FULL_PROMPT = (
    "Instrumental cinematic orchestral film score, 2 minutes duration, evolving through four emotional chapters: "
    "starting with an intimate delicate solo acoustic grand piano and warm nylon-string acoustic guitar with solo cello "
    "(0:00 to 0:30), building into warm lush legato string orchestra with gentle marimba and French horns "
    "(0:30 to 1:00), expanding into a sweeping heroic symphony orchestra with soaring violin melodies and rich brass "
    "(1:00 to 1:35), followed by a glorious triumphant orchestral fanfare celebration that resolves into a peaceful, "
    "glowing acoustic grand piano chord at the end. Natural concert hall acoustics, studio master quality, D major, no vocals."
)

LYRIA_PROMPTS_V4 = {
    1: (
        "Instrumental warm intimate cinematic orchestral film score, delicate acoustic grand piano melody "
        "with warm nylon-string acoustic guitar and expressive solo cello, gentle emotional awakening, "
        "natural concert hall acoustics, studio master quality, 96 BPM, D major, no vocals"
    ),
    2: (
        "Instrumental inspiring cinematic orchestral soundtrack, warm lush legato string section, noble French horns, "
        "gentle marimba and acoustic guitar pulse, uplifting Latin American warmth and steady forward momentum, "
        "emotional growth theme, studio master quality, 100 BPM, D major, no vocals"
    ),
    3: (
        "Instrumental grand sweeping symphony orchestra film score, soaring violin and cello melodies, rich warm brass choir, "
        "cinematic orchestral percussion and harp arpeggios, building emotional anticipation and unity toward a historic milestone, "
        "studio master quality, 108 BPM, D major, no vocals"
    ),
    4: (
        "Instrumental triumphant glorious cinematic orchestral finale, full symphony orchestra fanfare with soaring strings, "
        "noble French horns, warm acoustic grand piano resolution, radiant emotional fulfillment and celebration, "
        "resolving into a warm glowing orchestral chord, studio master quality, 108 BPM, D major, no vocals"
    ),
}


def _extract_audio_bytes_from_response(data: dict) -> tuple[bytes, str]:
    cands = data.get("candidates", [])
    for cand in cands:
        parts = cand.get("content", {}).get("parts", [])
        for part in parts:
            if "inlineData" in part:
                inl = part["inlineData"]
                b64 = inl.get("data", "")
                if b64:
                    return base64.b64decode(b64), inl.get("mimeType", "audio/mpeg")
    raise ValueError(f"Could not find inlineData audio in generateContent response: {list(data.keys())}")


def _save_decoded_audio_as_48k_wav(raw_bytes: bytes, out_wav: Path):
    tmp_in = out_wav.with_suffix(".raw_audio.mp3")
    tmp_in.write_bytes(raw_bytes)
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(tmp_in),
            "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le",
            str(out_wav),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    tmp_in.unlink(missing_ok=True)


def generate_lyria3_full_composition() -> Path:
    out_wav = AUDIO_DIR / "lyria3_pro_full.wav"
    if out_wav.exists() and out_wav.stat().st_size > 2_000_000:
        print(f"  [Lyria 3 Pro] Full composition already exists ({out_wav.name})", flush=True)
        return out_wav

    url = (
        f"https://aiplatform.googleapis.com/v1beta1/projects/{LYRIA_PROJECT}"
        f"/locations/{LYRIA_LOCATION}/publishers/google/models/{LYRIA_PRO_MODEL}:generateContent"
    )
    for attempt in range(3):
        try:
            token = get_adc_token()
            payload = {
                "contents": [{"role": "user", "parts": [{"text": LYRIA3_FULL_PROMPT}]}],
                "generationConfig": {"responseModalities": ["AUDIO", "TEXT"]},
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "x-goog-user-project": LYRIA_PROJECT,
                },
                method="POST",
            )
            print(f"  [Lyria 3 Pro] Generating full composition via {LYRIA_PRO_MODEL} (attempt {attempt+1})...", flush=True)
            with urllib.request.urlopen(req, timeout=210) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            raw_bytes, mime = _extract_audio_bytes_from_response(data)
            _save_decoded_audio_as_48k_wav(raw_bytes, out_wav)
            return out_wav
        except Exception as e:
            print(f"  [Lyria 3 Pro] Full composition attempt {attempt+1} error: {e}", flush=True)
    raise RuntimeError("Failed to generate Lyria 3 Pro full composition")


def generate_one_lyria3_clip(m_idx: int, prompt: str) -> Path:
    out_wav = AUDIO_DIR / f"lyria3_clip_{m_idx:02d}.wav"
    if out_wav.exists() and out_wav.stat().st_size > 1_000_000:
        print(f"  [Lyria 3 Clip] Movement {m_idx} already exists ({out_wav.name})", flush=True)
        return out_wav

    url = (
        f"https://aiplatform.googleapis.com/v1beta1/projects/{LYRIA_PROJECT}"
        f"/locations/{LYRIA_LOCATION}/publishers/google/models/{LYRIA_CLIP_MODEL}:generateContent"
    )
    for attempt in range(4):
        try:
            token = get_adc_token()
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"responseModalities": ["AUDIO", "TEXT"]},
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "x-goog-user-project": LYRIA_PROJECT,
                },
                method="POST",
            )
            print(f"  [Lyria 3 Clip] Generating Movement {m_idx}/4 via {LYRIA_CLIP_MODEL} (attempt {attempt+1})...", flush=True)
            with urllib.request.urlopen(req, timeout=150) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            raw_bytes, mime = _extract_audio_bytes_from_response(data)
            _save_decoded_audio_as_48k_wav(raw_bytes, out_wav)
            return out_wav
        except Exception as e:
            print(f"  [Lyria 3 Clip] Movement {m_idx} attempt {attempt+1} error: {e}", flush=True)

    raise RuntimeError(f"Failed to generate Lyria 3 movement {m_idx}")


def generate_all_lyria_movements():
    print("=== Step 1: Verifying / Generating Soundtrack via Google Lyria 3 ===", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        fut_full = ex.submit(generate_lyria3_full_composition)
        futs = {ex.submit(generate_one_lyria3_clip, idx, p): idx for idx, p in LYRIA_PROMPTS_V4.items()}
        for fut in concurrent.futures.as_completed(futs):
            fut.result()
        fut_full.result()


# ==============================================================================
# 4. CHIRP 3 HD NARRATION SYNTHESIS (EN-US & PT-BR) + EXACT TIMING MEASUREMENT
# ==============================================================================
def trim_wav_silence(samples: np.ndarray, sr: int, thresh: float = 0.008, pad_ms: int = 45) -> np.ndarray:
    win = int(0.010 * sr)
    if len(samples) < win * 2:
        return samples
    env = np.sqrt(np.convolve(samples**2, np.ones(win) / win, mode="same"))
    idx = np.where(env > thresh)[0]
    if len(idx) == 0:
        return samples
    pad = int((pad_ms / 1000.0) * sr)
    start = max(0, int(idx[0]) - pad)
    end = min(len(samples), int(idx[-1]) + pad)
    out = samples[start:end].copy()
    fi = min(int(0.015 * sr), len(out) // 4)
    fo = min(int(0.025 * sr), len(out) // 4)
    if fi > 0:
        out[:fi] *= np.linspace(0.0, 1.0, fi, dtype=np.float32)
    if fo > 0:
        out[-fo:] *= np.linspace(1.0, 0.0, fo, dtype=np.float32)
    return out


def synthesize_chirp3_clip(text: str, lang: str, out_wav: Path, target_max_dur: float = 7.15) -> float:
    """
    Synthesizes speech using Cloud TTS Chirp 3 HD (Charon) at 48kHz mono.
    If the natural duration slightly exceeds target_max_dur, applies pitch-preserving
    WSOLA time-scale modification via ffmpeg `atempo` so no scene ever overflows 8.0s.
    """
    voice_name = "en-US-Chirp3-HD-Charon" if lang == "en" else "pt-BR-Chirp3-HD-Charon"
    lang_code = "en-US" if lang == "en" else "pt-BR"

    token = get_tts_token()
    url = "https://texttospeech.googleapis.com/v1/text:synthesize"
    payload = {
        "input": {"text": text},
        "voice": {"languageCode": lang_code, "name": voice_name},
        "audioConfig": {
            "audioEncoding": "LINEAR16",
            "sampleRateHertz": SR,
            "speakingRate": 1.0,
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "x-goog-user-project": TTS_PROJECT,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    raw_bytes = base64.b64decode(data["audioContent"])

    tmp_path = out_wav.with_suffix(".raw.wav")
    tmp_path.write_bytes(raw_bytes)
    with wave.open(str(tmp_path), "rb") as wf:
        n = wf.getnframes()
        s = np.frombuffer(wf.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    tmp_path.unlink(missing_ok=True)

    trimmed = trim_wav_silence(s, SR)
    dur = len(trimmed) / SR

    # If natural duration exceeds target_max_dur, apply pitch-preserving WSOLA atempo
    if dur > target_max_dur:
        tempo = min(1.26, (dur / (target_max_dur - 0.12)))
        pre_wav = out_wav.with_suffix(".pre.wav")
        pcm_pre = np.clip(trimmed * 32767.0, -32768, 32767).astype(np.int16)
        with wave.open(str(pre_wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SR)
            wf.writeframes(pcm_pre.tobytes())
        post_wav = out_wav.with_suffix(".post.wav")
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(pre_wav),
                "-af", f"atempo={tempo:.4f}",
                "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le",
                str(post_wav),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with wave.open(str(post_wav), "rb") as wf:
            n2 = wf.getnframes()
            trimmed = np.frombuffer(wf.readframes(n2), dtype=np.int16).astype(np.float32) / 32768.0
        pre_wav.unlink(missing_ok=True)
        post_wav.unlink(missing_ok=True)
        trimmed = trim_wav_silence(trimmed, SR)
        dur = len(trimmed) / SR

    peak = float(np.max(np.abs(trimmed)))
    if peak > 0.01:
        trimmed = trimmed * (0.74 / peak)
    pcm = np.clip(trimmed * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())
    return dur


def synthesize_all_narrations() -> dict:
    print("=== Step 2: Synthesizing & Auditing Complete V4 Narration (EN-US & PT-BR) ===", flush=True)
    timings = {"en": {}, "ptbr": {}}

    for lang in ["en", "ptbr"]:
        for s_idx in range(1, NUM_SCENES + 1):
            meta = SCENES_META[s_idx]
            text = meta["vo_en"] if lang == "en" else meta["vo_ptbr"]
            offset = meta["vo_offset"]
            max_dur = 4.65 if s_idx == 12 else (7.45 - offset)

            out_wav = AUDIO_DIR / f"vo_{lang}_{s_idx:02d}.wav"
            dur = synthesize_chirp3_clip(text, lang, out_wav, target_max_dur=max_dur)

            # For Scene 12, align end_in_scene to exact 6.90s (1:34.90) so 1:34.90..1:36.00 is 1.10s of pure silence!
            if s_idx == 12:
                offset = round(max(0.40, 6.90 - dur), 3)

            start_abs = (s_idx - 1) * SCENE_DUR + offset
            end_abs = start_abs + dur
            timings[lang][s_idx] = {
                "start_in_scene": round(offset, 3),
                "dur": round(dur, 3),
                "end_in_scene": round(offset + dur, 3),
                "start_abs": round(start_abs, 3),
                "end_abs": round(end_abs, 3),
                "text": text,
            }
            print(
                f"  [VO {lang.upper()}] Scene {s_idx:02d}: start={start_abs:6.2f}s  end={end_abs:6.2f}s "
                f"(in_scene={offset:.2f}s..{offset+dur:.2f}s, dur={dur:.2f}s)",
                flush=True,
            )

    for lang, phrase in [("en", "One billion."), ("ptbr", "Um bilhão.")]:
        probe_wav = AUDIO_DIR / f"_probe_1b_{lang}.wav"
        dur_1b = synthesize_chirp3_clip(phrase, lang, probe_wav, target_max_dur=3.0)
        probe_wav.unlink(missing_ok=True)
        timings[lang][13]["one_billion_phrase_dur"] = round(dur_1b, 3)
        print(f"  [VO {lang.upper()}] Scene 13 '{phrase}' exact phrase duration: {dur_1b:.3f}s", flush=True)

    timings_path = AUDIO_DIR / "timings_v4.json"
    timings_path.write_text(json.dumps(timings, indent=2, ensure_ascii=False))
    return timings


# ==============================================================================
# 5. STUDIO MASTER AUDIO ENGINE (Lyria 3 Pro + Clip 4 + Lookahead Ducking + Veo SFX)
# ==============================================================================
def load_stereo_wav(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with wave.open(str(path), "rb") as wf:
        ch = wf.getnchannels()
        n = wf.getnframes()
        raw = np.frombuffer(wf.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    if ch == 2:
        s = raw.reshape(-1, 2)
        return s[:, 0].copy(), s[:, 1].copy()
    return raw.copy(), raw.copy()


def load_mono_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wf:
        ch = wf.getnchannels()
        n = wf.getnframes()
        raw = np.frombuffer(wf.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    if ch == 2:
        return raw.reshape(-1, 2).mean(axis=1)
    return raw


def extract_veo_scene_audio(scene_idx: int) -> tuple[np.ndarray, np.ndarray]:
    """Extracts the native Veo 3.1 audio track from scene_XX.mp4, high-passed at 110Hz to remove rumble."""
    n_target = int(SCENE_DUR * SR)
    mp4_path = CLIPS_DIR / f"scene_{scene_idx:02d}.mp4"
    tmp_wav = AUDIO_DIR / f"_veo_sfx_{scene_idx:02d}.wav"
    if not tmp_wav.exists():
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(mp4_path),
                "-vn", "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le",
                str(tmp_wav),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    l, r = load_stereo_wav(tmp_wav)
    if len(l) < n_target:
        l = np.pad(l, (0, n_target - len(l)))
        r = np.pad(r, (0, n_target - len(r)))
    else:
        l = l[:n_target]
        r = r[:n_target]

    # High-pass at 110Hz and low-pass at 10kHz so only clean organic foley/ambience remains
    sos_hp = butter(2, 110.0 / (SR / 2.0), btype="highpass", output="sos")
    sos_lp = butter(2, 10000.0 / (SR / 2.0), btype="lowpass", output="sos")
    l = sosfiltfilt(sos_lp, sosfiltfilt(sos_hp, l)).astype(np.float32)
    r = sosfiltfilt(sos_lp, sosfiltfilt(sos_hp, r)).astype(np.float32)

    # Smooth 150ms fade at scene edges
    fade = int(0.15 * SR)
    l[:fade] *= np.linspace(0.0, 1.0, fade, dtype=np.float32)
    r[:fade] *= np.linspace(0.0, 1.0, fade, dtype=np.float32)
    l[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
    r[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
    return l, r


def build_lyria3_master_score() -> tuple[np.ndarray, np.ndarray]:
    """
    Builds the 120.0s (5,760,000 samples) continuous stereo orchestral score from Google Lyria 3:
    - 0:00.0 to 1:35.0 (0.0s .. 95.0s): Continuous Lyria 3 Pro (`lyria3_pro_full.wav`, 0.0s..95.0s),
      which organically evolves from intimate solo piano & acoustic guitar (0:00-0:30) -> warm strings &
      marimba (0:30-1:00) -> sweeping symphony orchestra crescendo (1:00-1:35).
    - 1:35.0 to 1:36.08 (95.0s .. 96.08s): Exact 1.08s dramatic silence ("And then..." -> [SILENCE] -> "One billion.")
    - 1:36.55 to 2:00.0 (96.55s .. 120.0s): Triumphant orchestral fanfare from Lyria 3 Clip 04 (`lyria3_clip_04.wav`)
      exploding on the exact frame "One billion" finishes, then equal-power cosine crossfaded (4.5s) into the
      peaceful glowing acoustic grand piano resolution at the tail of `lyria3_pro_full.wav` (98.0s .. 117.6s)!
    """
    n_total = int(TOTAL_DUR * SR)
    score_L = np.zeros(n_total, dtype=np.float32)
    score_R = np.zeros(n_total, dtype=np.float32)

    full_L, full_R = load_stereo_wav(AUDIO_DIR / "lyria3_pro_full.wav")
    clip4_L, clip4_R = load_stereo_wav(AUDIO_DIR / "lyria3_clip_04.wav")

    # Normalize RMS across sources so transitions are level-matched
    def norm_rms(l, r, target_rms=0.18):
        cur = float(np.sqrt(np.mean(0.5 * (l**2 + r**2))))
        if cur > 1e-4:
            g = target_rms / cur
            return l * g, r * g
        return l, r

    full_L, full_R = norm_rms(full_L, full_R, 0.18)
    clip4_L, clip4_R = norm_rms(clip4_L, clip4_R, 0.21)

    # Part A: 0.0s to 95.0s from lyria3_pro_full.wav
    idx_95 = int(95.0 * SR)
    score_L[:idx_95] = full_L[:idx_95]
    score_R[:idx_95] = full_R[:idx_95]

    # Smooth 1.2s fade-in at 0:00
    fi = int(1.2 * SR)
    score_L[:fi] *= np.sin(np.linspace(0.0, np.pi / 2.0, fi, dtype=np.float32))
    score_R[:fi] *= np.sin(np.linspace(0.0, np.pi / 2.0, fi, dtype=np.float32))

    # Crisp dramatic orchestral cutoff into 1:35.0 (fade out over 180ms at 94.82s..95.00s)
    fo_cut = int(0.18 * SR)
    score_L[idx_95 - fo_cut : idx_95] *= np.cos(np.linspace(0.0, np.pi / 2.0, fo_cut, dtype=np.float32))
    score_R[idx_95 - fo_cut : idx_95] *= np.cos(np.linspace(0.0, np.pi / 2.0, fo_cut, dtype=np.float32))

    # Part B: 95.0s to 96.60s -> ABSOLUTE DRAMATIC SILENCE (1.0s silence + "One billion" solo voice!)
    # Part C: 96.60s to 120.0s (23.40s total) -> Triumphant Lyria 3 Finale!
    #   - 96.60s to 111.0s (14.4s): Lyria 3 Clip 04 triumphant symphony fanfare
    #   - 106.5s to 120.0s: Equal-power 4.5s crossfade into the natural glowing piano resolution of lyria3_pro_full.wav!
    idx_bloom = int(96.60 * SR)
    len_post = n_total - idx_bloom  # 23.40s = 1,123,200 samples

    # Build post-climax segment of length len_post
    post_L = np.zeros(len_post, dtype=np.float32)
    post_R = np.zeros(len_post, dtype=np.float32)

    # First 15.5s of post-climax from clip4_L/R (skipping first 0.5s so it enters on a strong downbeat)
    c4_start = int(0.5 * SR)
    c4_len = int(15.5 * SR)
    post_L[:c4_len] = clip4_L[c4_start : c4_start + c4_len]
    post_R[:c4_len] = clip4_R[c4_start : c4_start + c4_len]

    # Tail of lyria3_pro_full.wav (last 12.4s, which has the natural glowing piano resolution!)
    xfade_len = int(4.5 * SR)
    tail_start_in_post = c4_len - xfade_len  # starts at 11.0s into post (107.6s abs)
    tail_len = len_post - tail_start_in_post  # 12.40s
    full_tail_L = full_L[-tail_len:].copy()
    full_tail_R = full_R[-tail_len:].copy()

    # Equal-power cosine crossfade over xfade_len (4.5s)
    theta = np.linspace(0.0, np.pi / 2.0, xfade_len, dtype=np.float32)
    fade_out_c4 = np.cos(theta)
    fade_in_tail = np.sin(theta)

    post_L[tail_start_in_post : tail_start_in_post + xfade_len] *= fade_out_c4
    post_R[tail_start_in_post : tail_start_in_post + xfade_len] *= fade_out_c4

    full_tail_L[:xfade_len] *= fade_in_tail
    full_tail_R[:xfade_len] *= fade_in_tail

    post_L[tail_start_in_post:] += full_tail_L
    post_R[tail_start_in_post:] += full_tail_R

    # Fast 120ms bloom attack at 96.60s when "$1,101.1M" locks in
    atk = int(0.12 * SR)
    post_L[:atk] *= np.sin(np.linspace(0.0, np.pi / 2.0, atk, dtype=np.float32))
    post_R[:atk] *= np.sin(np.linspace(0.0, np.pi / 2.0, atk, dtype=np.float32))

    # Smooth 2.5s final fade-out at 117.5s..120.0s
    fo_end = int(2.5 * SR)
    post_L[-fo_end:] *= np.cos(np.linspace(0.0, np.pi / 2.0, fo_end, dtype=np.float32))
    post_R[-fo_end:] *= np.cos(np.linspace(0.0, np.pi / 2.0, fo_end, dtype=np.float32))

    score_L[idx_bloom:] = post_L
    score_R[idx_bloom:] = post_R

    # Dynamic Sliding-Window RMS Normalizer (AGC Leveler)
    # Prevents the soundtrack from getting louder as the orchestra swells in Acts II, III, and IV!
    win_agc = int(2.5 * SR)
    inst_power = 0.5 * (score_L**2 + score_R**2)
    local_rms = np.sqrt(uniform_filter1d(inst_power, size=win_agc) + 1e-8)
    target_flat_rms = 0.12
    # Only normalize active musical regions (above silence floor), clamp max boost so quiet tails stay natural
    agc_gain = np.where(local_rms > 0.015, target_flat_rms / local_rms, 1.0)
    agc_gain = np.clip(agc_gain, 0.22, 1.45).astype(np.float32)
    agc_gain = uniform_filter1d(uniform_filter1d(agc_gain, size=int(0.45 * SR)), size=int(0.45 * SR))

    score_L *= agc_gain
    score_R *= agc_gain

    # Flat macro envelope (NO upward volume creep over time! Keeps uniform level from 0:00 to 2:00,
    # preserving only the 1:35.0-1:36.6 dramatic silence and final fade-out)
    t = np.linspace(0.0, TOTAL_DUR, n_total, dtype=np.float32)
    macro_gain = np.interp(
        t,
        [0.0, 1.2, 94.8, 95.0, 96.55, 96.75, 117.0, 120.0],
        [0.0, 1.0, 1.00, 0.00, 0.00,  0.95,  0.90,  0.00],
    ).astype(np.float32)

    score_L *= macro_gain
    score_R *= macro_gain
    return score_L, score_R


def build_master_audio(lang: str, timings: dict) -> Path:
    """
    Combines:
    1. Normalized flat-loudness Lyria 3 stereo orchestral score (strictly < 60% of voice at all times)
    2. Studio Lookahead Sidechain Ducking (26% of voice during narration, max 48% of voice in gaps)
    3. Chirp 3 HD Narration (dominant, clear, warm studio EQ)
    4. Filtered Veo 3.1 organic scene SFX/ambience
    """
    print(f"=== Step 3 ({lang.upper()}): Mastering Studio Audio Mix (Music strictly < 60% of Voice) ===", flush=True)
    n_total = int(TOTAL_DUR * SR)

    # 1. Place all 15 narration clips onto the master vocal timeline
    vo_mono = np.zeros(n_total, dtype=np.float32)
    for s_idx in range(1, NUM_SCENES + 1):
        wav_path = AUDIO_DIR / f"vo_{lang}_{s_idx:02d}.wav"
        clip = load_mono_wav(wav_path)
        # Level-normalize each individual scene VO clip to uniform RMS (0.20) & peak (0.78)
        c_rms = float(np.sqrt(np.mean(clip[np.abs(clip) > 0.02]**2))) if np.any(np.abs(clip) > 0.02) else 0.18
        if c_rms > 1e-4:
            clip = clip * (0.20 / c_rms)
        c_pk = float(np.max(np.abs(clip)))
        if c_pk > 0.78:
            clip = np.tanh(clip / c_pk * 1.15) * 0.78
        start_abs = timings[lang][s_idx]["start_abs"]
        idx0 = int(round(start_abs * SR))
        idx1 = min(n_total, idx0 + len(clip))
        vo_mono[idx0:idx1] = clip[: idx1 - idx0]

    # Save standalone master VO stem
    vo_master_path = AUDIO_DIR / f"vo_master_{lang}_v4.wav"
    vo_pcm = np.clip(vo_mono * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(vo_master_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(vo_pcm.tobytes())

    # 2. Build Lookahead Sidechain Ducking Envelope from VO activity
    win = int(0.020 * SR)
    vo_rms_curve = np.sqrt(np.maximum(0.0, uniform_filter1d(vo_mono**2, size=win)))
    active = (vo_rms_curve > 0.010).astype(np.float32)
    hold_samples = int(0.75 * SR)
    active_held = maximum_filter1d(active, size=hold_samples)
    active_smooth = uniform_filter1d(uniform_filter1d(active_held, size=int(0.35 * SR)), size=int(0.35 * SR))
    active_smooth = np.clip(active_smooth, 0.0, 1.0)

    # 3. Load flat-normalized Lyria 3 Master Score
    score_L, score_R = build_lyria3_master_score()

    # 4. Assemble Veo 3.1 Organic Scene Ambience/SFX (kept very subtle)
    veo_L = np.zeros(n_total, dtype=np.float32)
    veo_R = np.zeros(n_total, dtype=np.float32)
    for s_idx in range(1, NUM_SCENES + 1):
        sl, sr_ch = extract_veo_scene_audio(s_idx)
        i0 = int((s_idx - 1) * SCENE_DUR * SR)
        veo_L[i0 : i0 + len(sl)] = sl
        veo_R[i0 : i0 + len(sr_ch)] = sr_ch

    veo_L[int(94.8 * SR) : int(96.6 * SR)] = 0.0
    veo_R[int(94.8 * SR) : int(96.6 * SR)] = 0.0

    # 5. Prepare dominant vocal stem (100% reference level)
    d1 = int(0.018 * SR)
    d2 = int(0.029 * SR)
    vo_L = vo_mono * 1.15
    vo_R = vo_mono * 1.15
    vo_L[d1:] += vo_mono[:-d1] * 0.05
    vo_R[d2:] += vo_mono[:-d2] * 0.05

    vo_active_samples = vo_L[active > 0.5]
    vo_ref_rms = float(np.sqrt(np.mean(vo_active_samples**2))) if len(vo_active_samples) > 0 else 0.22
    vo_ref_peak = float(np.max(np.abs(vo_L))) if np.max(np.abs(vo_L)) > 0.01 else 0.85

    # Combine raw accompaniment (score + subtle foley) and normalize its base RMS to match vo_ref_rms
    acc_L = score_L + veo_L * 0.05
    acc_R = score_R + veo_R * 0.05
    acc_active = acc_L[np.abs(acc_L) > 0.01]
    acc_rms = float(np.sqrt(np.mean(acc_active**2))) if len(acc_active) > 0 else 0.12
    if acc_rms > 1e-4:
        acc_L *= (vo_ref_rms / acc_rms)
        acc_R *= (vo_ref_rms / acc_rms)

    # STRICT CEILING BELOW 60% OF VOICE:
    # - In instrumental pauses (active_smooth = 0): accompaniment is at 48% of voice RMS (< 60% ceiling!)
    # - During narration (active_smooth = 1): accompaniment ducks to 26% of voice RMS (~ -11.7 dB under voice!)
    acc_gain_env = 0.48 - 0.22 * active_smooth
    music_L = acc_L * acc_gain_env
    music_R = acc_R * acc_gain_env

    # Hard peak clamp on accompaniment so not even a single brass/percussion transient exceeds 52% of voice peak
    max_allowed_acc_peak = 0.52 * vo_ref_peak
    music_L = max_allowed_acc_peak * np.tanh(music_L / max_allowed_acc_peak)
    music_R = max_allowed_acc_peak * np.tanh(music_R / max_allowed_acc_peak)

    # Measure and log exact Music-to-Voice ratios
    mus_speech_rms = float(np.sqrt(np.mean(music_L[active > 0.5]**2)))
    mus_gap_rms = float(np.sqrt(np.mean(music_L[(active < 0.1) & (np.abs(music_L) > 0.005)]**2)))
    mus_peak = float(max(np.max(np.abs(music_L)), np.max(np.abs(music_R))))
    print(
        f"  [Audio Balance {lang.upper()}] Voice RMS={vo_ref_rms:.3f} (Peak={vo_ref_peak:.3f}) | "
        f"Music during speech={mus_speech_rms/vo_ref_rms*100:.1f}% of voice | "
        f"Music in gaps={mus_gap_rms/vo_ref_rms*100:.1f}% of voice | "
        f"Music Peak={mus_peak/vo_ref_peak*100:.1f}% of voice (< 60% guaranteed!)",
        flush=True,
    )

    # 6. Combine stems and apply gentle soft-knee mastering limiter to -1.0 dBFS (0.891)
    mix_L = music_L + vo_L
    mix_R = music_R + vo_R

    # Soft-knee tanh saturation above 0.75 to prevent any digital clipping
    def soft_limit(x: np.ndarray) -> np.ndarray:
        return np.tanh(x * 1.05) / np.tanh(1.05)

    mix_L = soft_limit(mix_L)
    mix_R = soft_limit(mix_R)

    peak = float(max(np.max(np.abs(mix_L)), np.max(np.abs(mix_R))))
    if peak > 0.01:
        gain = 0.891 / peak
        mix_L *= gain
        mix_R *= gain

    stereo_interleaved = np.empty(n_total * 2, dtype=np.int16)
    stereo_interleaved[0::2] = np.clip(mix_L * 32767.0, -32768, 32767).astype(np.int16)
    stereo_interleaved[1::2] = np.clip(mix_R * 32767.0, -32768, 32767).astype(np.int16)

    out_wav = AUDIO_DIR / f"master_mix_{lang}_v4.wav"
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(stereo_interleaved.tobytes())

    # Verify silence window at 1:35.1 - 1:35.9
    sil_slice = mix_L[int(95.10 * SR) : int(95.95 * SR)]
    sil_rms = float(np.sqrt(np.mean(sil_slice**2)))
    print(
        f"  [Master Audio {lang.upper()}] Saved {out_wav.name} | peak={peak:.3f} -> 0.891 | "
        f"1:35.1-1:35.9 silence RMS={sil_rms:.6f}",
        flush=True,
    )
    return out_wav


# ==============================================================================
# 6. FLUID ZERO-REWIND VIDEO ENGINE + PIXAR TYPOGRAPHY OVERLAYS
# ==============================================================================
_FONT_CACHE = {}


def get_font(path: str, size: int):
    key = (path, size)
    if key not in _FONT_CACHE:
        try:
            _FONT_CACHE[key] = ImageFont.truetype(path, size)
        except Exception:
            _FONT_CACHE[key] = ImageFont.load_default()
    return _FONT_CACHE[key]


def load_scene_frames(scene_idx: int) -> list[np.ndarray]:
    """Loads all 192 RGB frames (1920x1080) of scene_XX.mp4 into memory."""
    mp4_path = CLIPS_DIR / f"scene_{scene_idx:02d}.mp4"
    cmd = [
        "ffmpeg", "-v", "error",
        "-i", str(mp4_path),
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS),
        "pipe:1",
    ]
    raw = subprocess.check_output(cmd)
    frame_bytes = WIDTH * HEIGHT * 3
    n_frames = len(raw) // frame_bytes
    frames = []
    for i in range(n_frames):
        arr = np.frombuffer(raw, dtype=np.uint8, count=frame_bytes, offset=i * frame_bytes)
        frames.append(arr.reshape((HEIGHT, WIDTH, 3)))
    while len(frames) < 192:
        frames.append(frames[-1])
    return frames[:192]


def sample_scene_monotonic(
    frames: list[np.ndarray],
    pos_f: float,
    start_trim: int,
    usable_end: int,
) -> np.ndarray:
    """
    Maps timeline position `pos_f` (0 .. usable_end) monotonically onto clip frames
    `start_trim .. usable_end` using sub-frame linear interpolation.
    Guarantees strictly forward motion with zero static start frames and zero frame jumps.
    """
    if usable_end <= 0:
        return frames[min(start_trim, len(frames) - 1)]
    t_norm = max(0.0, min(1.0, pos_f / float(usable_end)))
    src_f = start_trim + t_norm * float(usable_end - start_trim)
    i0 = int(math.floor(src_f))
    i1 = min(len(frames) - 1, i0 + 1)
    frac = src_f - i0
    if frac < 1e-3 or i0 == i1:
        return frames[i0]
    return cv_blend(frames[i0], frames[i1], frac)


def cv_blend(img_a: np.ndarray, img_b: np.ndarray, alpha: float) -> np.ndarray:
    return np.clip(
        img_a.astype(np.float32) * (1.0 - alpha) + img_b.astype(np.float32) * alpha,
        0,
        255,
    ).astype(np.uint8)


def render_typography_overlay(
    frame_rgb: np.ndarray,
    scene_idx: int,
    f_in_scene: int,
    lang: str,
    timings: dict,
) -> np.ndarray:
    """
    Renders clean, cinema-grade lower-third / milestone typography in sync with the narration.
    """
    meta = SCENES_META[scene_idx]
    t_in_scene = f_in_scene / float(FPS)

    # Calculate smooth fade-in / fade-out envelope for the text card
    t_enter = 0.35 if scene_idx != 13 else 0.04
    t_exit = 7.35 if scene_idx != 12 else 6.80
    if t_in_scene < t_enter or t_in_scene > t_exit:
        return frame_rgb

    alpha = 1.0
    if t_in_scene < t_enter + 0.45:
        alpha = (t_in_scene - t_enter) / 0.45
    elif t_in_scene > t_exit - 0.50:
        alpha = (t_exit - t_in_scene) / 0.50
    alpha = max(0.0, min(1.0, alpha))
    alpha = 0.5 - 0.5 * math.cos(math.pi * alpha)  # cosine ease

    badge = meta["badge"] if lang == "en" else meta["badge_pt"]
    headline = meta["headline"] if lang == "en" else meta.get("headline_pt", meta["headline"])
    sub = meta["sub"] if lang == "en" else meta["sub_pt"]
    accent = meta["accent"]

    # Dynamic counter for Scene 13 ($702M -> $1,101.1M locked to "One billion." / "Um bilhão.")
    if scene_idx == 13 and headline == "COUNTER":
        vo_start = timings[lang][13]["start_in_scene"]
        dur_1b = timings[lang][13]["one_billion_phrase_dur"]
        lock_t = vo_start + dur_1b  # ~0.91s in EN, ~0.72s in PTBR
        if t_in_scene <= vo_start:
            val = 702.0
        elif t_in_scene >= lock_t:
            val = 1101.1
        else:
            p = (t_in_scene - vo_start) / max(0.15, (lock_t - vo_start))
            p_ease = 1.0 - (1.0 - p) ** 2.4
            val = 702.0 + (1101.1 - 702.0) * p_ease

        if val >= 1000.0:
            whole = int(val)
            dec = int(round((val - whole) * 10)) % 10
            if lang == "en":
                headline = f"${whole // 1000},{whole % 1000:03d}.{dec}M"
            else:
                headline = f"US$ {whole // 1000}.{whole % 1000:03d},{dec}M"
        else:
            headline = f"${int(round(val))}M" if lang == "en" else f"US$ {int(round(val))}M"

    base_img = Image.fromarray(frame_rgb).convert("RGBA")
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Translucent dark glass lower-third pill at bottom-left (or centered for Scene 13/15)
    is_centered = scene_idx in (13, 14, 15)
    card_alpha = int(175 * alpha)
    text_alpha = int(255 * alpha)
    sub_alpha = int(225 * alpha)

    f_badge = get_font(FONT_SANS_BOLD, 21)
    f_head = get_font(FONT_FUTURA, 64 if scene_idx in (13, 14) else 52)
    f_sub = get_font(FONT_SANS_REG, 26)

    if is_centered:
        card_w = 1180
        card_h = 215 if headline else 145
        cx = (WIDTH - card_w) // 2
        cy = HEIGHT - card_h - 64
        draw.rounded_rectangle(
            [cx, cy, cx + card_w, cy + card_h],
            radius=24,
            fill=(10, 14, 24, card_alpha),
            outline=(accent[0], accent[1], accent[2], int(190 * alpha)),
            width=2,
        )
        # Top Google 4-color accent bar
        bar_w = 240
        bx0 = WIDTH // 2 - bar_w // 2
        for idx_c, col in enumerate([C_BLUE, C_RED, C_YELLOW, C_GREEN]):
            draw.rectangle(
                [bx0 + idx_c * 60, cy, bx0 + (idx_c + 1) * 60, cy + 5],
                fill=(col[0], col[1], col[2], text_alpha),
            )

        # Badge
        bb = draw.textbbox((0, 0), badge, font=f_badge)
        bw = bb[2] - bb[0]
        draw.text(
            ((WIDTH - bw) // 2, cy + 18),
            badge,
            font=f_badge,
            fill=(accent[0], accent[1], accent[2], text_alpha),
        )

        # Headline
        if headline:
            hb = draw.textbbox((0, 0), headline, font=f_head)
            hw = hb[2] - hb[0]
            draw.text(
                ((WIDTH - hw) // 2, cy + 52),
                headline,
                font=f_head,
                fill=(255, 255, 255, text_alpha),
            )
            sub_y = cy + 148
        else:
            sub_y = cy + 68

        # Subtitle
        sb = draw.textbbox((0, 0), sub, font=f_sub)
        sw = sb[2] - sb[0]
        draw.text(
            ((WIDTH - sw) // 2, sub_y),
            sub,
            font=f_sub,
            fill=(230, 236, 245, sub_alpha),
        )
    else:
        # Left-aligned cinematic lower-third card
        cx = 76
        card_h = 190 if headline else 130
        cy = HEIGHT - card_h - 62
        card_w = 980 if len(sub) > 58 else 860

        draw.rounded_rectangle(
            [cx, cy, cx + card_w, cy + card_h],
            radius=20,
            fill=(10, 14, 24, card_alpha),
            outline=(255, 255, 255, int(45 * alpha)),
            width=1,
        )
        # Left vertical accent bar
        draw.rounded_rectangle(
            [cx, cy + 16, cx + 7, cy + card_h - 16],
            radius=3,
            fill=(accent[0], accent[1], accent[2], text_alpha),
        )

        tx = cx + 30
        draw.text(
            (tx, cy + 18),
            badge,
            font=f_badge,
            fill=(accent[0], accent[1], accent[2], text_alpha),
        )
        if headline:
            draw.text(
                (tx, cy + 48),
                headline,
                font=f_head,
                fill=(255, 255, 255, text_alpha),
            )
            sub_y = cy + 132
        else:
            sub_y = cy + 62

        draw.text(
            (tx, sub_y),
            sub,
            font=f_sub,
            fill=(228, 234, 242, sub_alpha),
        )

    out_rgba = Image.alpha_composite(base_img, overlay)
    return np.array(out_rgba.convert("RGB"), dtype=np.uint8)


def apply_screen_shake(frame_rgb: np.ndarray, f_in_scene: int) -> np.ndarray:
    """Applies a subtle 6-frame cinematic camera impulse on Scene 14 when the golden fruit bursts."""
    if f_in_scene >= 6:
        return frame_rgb
    offsets = [(10, -8), (-8, 7), (6, -5), (-5, 4), (3, -2), (-1, 1)]
    dx, dy = offsets[f_in_scene]
    shifted = np.roll(np.roll(frame_rgb, dy, axis=0), dx, axis=1)
    return shifted


def render_fluid_video(lang: str, timings: dict, master_wav: Path, out_mp4: Path):
    """
    Renders the 120.0s (2,880 frames) 1080p24 master video with:
    - Strictly monotonic Outgoing Tail Dissolves (ZERO frame-reset rewind bug, ZERO frozen start frames)
    - Frame-locked typography and $1,101.1M counter
    """
    print(f"=== Step 4 ({lang.upper()}): Rendering Fluid Zero-Rewind 1080p24 Video -> {out_mp4.name} ===", flush=True)

    ffmpeg_cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{WIDTH}x{HEIGHT}", "-pix_fmt", "rgb24", "-r", str(FPS),
        "-i", "-",
        "-i", str(master_wav),
        "-c:v", "libx264", "-preset", "medium", "-crf", "17",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "320k", "-ar", str(SR),
        "-movflags", "+faststart",
        "-shortest",
        str(out_mp4),
    ]
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    scene_cache = {}

    def get_scene(s_idx: int) -> list[np.ndarray]:
        if s_idx not in scene_cache:
            scene_cache[s_idx] = load_scene_frames(s_idx)
            # Evict older scenes to keep memory footprint low
            for k in list(scene_cache.keys()):
                if k < s_idx - 1:
                    del scene_cache[k]
        return scene_cache[s_idx]

    frames_per_scene = int(SCENE_DUR * FPS)  # 192 frames

    for s_idx in range(1, NUM_SCENES + 1):
        cur_frames = get_scene(s_idx)
        meta = SCENES_META[s_idx]
        ttype = meta["trans_type"]
        tdur = meta["trans_dur"] if s_idx < NUM_SCENES else 24

        cur_trim = START_TRIM_FRAMES.get(s_idx, 1)
        # How many outgoing dissolve frames at the tail of Scene s_idx?
        out_dissolve = tdur if (s_idx < NUM_SCENES and ttype == "dissolve" and tdur > 0) else 0
        usable_end = (frames_per_scene - 1) - out_dissolve

        # If Scene s_idx was preceded by an incoming dissolve of length prev_dissolve,
        # its first `prev_dissolve` frames after `cur_trim` were already consumed during Scene (s_idx-1)'s tail!
        if s_idx > 1:
            prev_meta = SCENES_META[s_idx - 1]
            prev_dissolve = prev_meta["trans_dur"] if prev_meta["trans_type"] == "dissolve" else 0
        else:
            prev_dissolve = 0

        eff_start_trim = cur_trim + prev_dissolve

        for f in range(frames_per_scene):
            if out_dissolve > 0 and f > usable_end:
                # We are inside the outgoing tail dissolve (frames usable_end+1 .. 191)
                # Scene s_idx continues advancing monotonically through its tail frames (usable_end+1 .. 191)
                frame_a = cur_frames[f]
                frame_a = render_typography_overlay(frame_a, s_idx, f, lang, timings)

                # Scene s_idx+1 advances through its genuine opening frames (next_trim .. next_trim + out_dissolve - 1)
                next_frames = get_scene(s_idx + 1)
                next_trim = START_TRIM_FRAMES.get(s_idx + 1, 1)
                k = f - (usable_end + 1)  # 0 .. out_dissolve - 1
                frame_b = next_frames[min(len(next_frames) - 1, next_trim + k)]

                # Smooth cosine cross-dissolve weight
                p = float(k + 1) / float(out_dissolve + 1)
                w = 0.5 - 0.5 * math.cos(math.pi * p)
                out_frame = cv_blend(frame_a, frame_b, w)
            else:
                # Normal main body of Scene s_idx (frames 0 .. usable_end)
                # Maps f in [0 .. usable_end] monotonically to [eff_start_trim .. usable_end]
                base_rgb = sample_scene_monotonic(cur_frames, float(f), eff_start_trim, usable_end)
                if s_idx == 14 and f < 6:
                    base_rgb = apply_screen_shake(base_rgb, f)
                out_frame = render_typography_overlay(base_rgb, s_idx, f, lang, timings)

                # Fade in from black on Scene 1 (first 16 frames)
                if s_idx == 1 and f < 16:
                    w_in = 0.5 - 0.5 * math.cos(math.pi * (f / 16.0))
                    out_frame = (out_frame.astype(np.float32) * w_in).astype(np.uint8)

                # Fade out to black at the end of Scene 15 (last 24 frames)
                if s_idx == NUM_SCENES and f >= frames_per_scene - 24:
                    rem = (frames_per_scene - 1 - f) / 24.0
                    w_out = 0.5 - 0.5 * math.cos(math.pi * max(0.0, rem))
                    out_frame = (out_frame.astype(np.float32) * w_out).astype(np.uint8)

            proc.stdin.write(out_frame.tobytes())

        print(f"  [{lang.upper()}] Rendered Scene {s_idx:02d}/15 ({s_idx*8}s / 120s)", flush=True)

    proc.stdin.close()
    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"ffmpeg exited with code {ret}")
    print(f"  [{lang.upper()}] Successfully exported {out_mp4} ({out_mp4.stat().st_size:,} bytes)", flush=True)


# ==============================================================================
# 7. SUBTITLES (.SRT) & 720P BACKUP EXPORT
# ==============================================================================
def fmt_srt_time(sec: float) -> str:
    ms = int(round((sec - int(sec)) * 1000))
    s = int(sec) % 60
    m = (int(sec) // 60) % 60
    h = int(sec) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_srt_files(timings: dict):
    for lang, srt_name in [
        ("en", "a_semente_latam_smb_pixar_en.srt"),
        ("ptbr", "a_semente_latam_smb_pixar_ptbr.srt"),
    ]:
        lines = []
        for s_idx in range(1, NUM_SCENES + 1):
            info = timings[lang][s_idx]
            t0 = fmt_srt_time(info["start_abs"])
            t1 = fmt_srt_time(info["end_abs"])
            lines.append(f"{s_idx}\n{t0} --> {t1}\n{info['text']}\n")
        srt_path = BASE_DIR / srt_name
        srt_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"  [SRT] Wrote {srt_path.name}", flush=True)


def remux_video_with_audio(mp4_path: Path, wav_path: Path):
    tmp_out = mp4_path.with_suffix(".remux.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-i", str(mp4_path),
            "-i", str(wav_path),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "320k", "-ar", str(SR),
            "-movflags", "+faststart",
            "-shortest",
            str(tmp_out),
        ],
        check=True,
    )
    tmp_out.replace(mp4_path)
    print(f"  [Remux] Updated audio stream in {mp4_path.name}", flush=True)


def main():
    import sys
    remux_only = "--remux-audio" in sys.argv

    generate_all_lyria_movements()
    timings_path = AUDIO_DIR / "timings_v4.json"
    if remux_only and timings_path.exists():
        raw_t = json.loads(timings_path.read_text())
        timings = {
            lang: {int(k): v for k, v in lang_dict.items()}
            for lang, lang_dict in raw_t.items()
        }
        print("  [Timings] Loaded cached timings_v4.json", flush=True)
    else:
        timings = synthesize_all_narrations()
        generate_srt_files(timings)

    wav_en = build_master_audio("en", timings)
    wav_pt = build_master_audio("ptbr", timings)

    out_en = BASE_DIR / "a_semente_latam_smb_pixar_en.mp4"
    out_pt = BASE_DIR / "a_semente_latam_smb_pixar_ptbr.mp4"
    out_720p = BASE_DIR / "a_semente_latam_smb_pixar_720p_backup.mp4"

    if remux_only and out_en.exists() and out_pt.exists():
        remux_video_with_audio(out_en, wav_en)
        remux_video_with_audio(out_pt, wav_pt)
        if out_720p.exists():
            remux_video_with_audio(out_720p, wav_en)
        print(f"=== COMPLETE! Remuxed {out_en.name}, {out_pt.name}, and {out_720p.name} ===", flush=True)
        return
    else:
        render_fluid_video("en", timings, wav_en, out_en)
        render_fluid_video("ptbr", timings, wav_pt, out_pt)

    # Also update the 720p backup from the EN master
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-i", str(out_en),
            "-vf", "scale=1280:720",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "copy", "-movflags", "+faststart",
            str(out_720p),
        ],
        check=True,
    )
    print(f"=== COMPLETE! Updated {out_en.name}, {out_pt.name}, and {out_720p.name} ===", flush=True)


if __name__ == "__main__":
    main()
