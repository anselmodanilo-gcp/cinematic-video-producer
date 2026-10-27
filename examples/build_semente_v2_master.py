#!/usr/bin/env python3
"""
"A SEMENTE" — Aurora Cloud (v2 · Edição 15 Anos · 2011–2026 · $1.16B ARR → $2B)
Master Pipeline (2:24 · 144.0s · 18 Scenes of 8s · 1920x1080 @ 24fps):
  1. Reuses the 13 matching Pixar 3D scenes & character reference sheets from v1 (`03_a_semente_pixar_2min/clips_v3`)
  2. Generates 5 brand-new Pixar 3D 8s 1080p clips via Vertex AI Veo 3.1 (`veo-3.1-generate-001`):
     - Scene 02: Operating remotely from California & Texas (2011–2019), watering the sapling from afar via a thread of light
     - Scene 04: 2018 LATAM GCP sales structure launched with a lean team of 2 in an immense plaza
     - Scene 10: Pillars 1 & 2 — 33 FTEs + 52 extended driving the $191M ARR (+48% YoY) GCP engine
     - Scene 11: Pillar 3 — Partner ecosystem driving $351M ARR (+27% YoY)
     - Scene 17: Act V — The new luminous sprout of AI (Gemini Enterprise, AIS, AWT) blooming toward $2B
  3. Synthesizes 18 scenes of single-voice narration via Cloud TTS Chirp 3 HD (`Charon` in EN-US & PT-BR)
     with zero-overflow WSOLA protection and exact 1.1s dramatic silence at 1:50.90–1:52.00
  4. Masters the 144.0s Lyria 3 orchestral soundtrack with AGC leveling and strict <60% voice ceiling
  5. Renders fluid Zero-Rewind 1080p24 MP4 masters (EN-US, PT-BR, 720p backup) + .srt subtitles
"""

import base64
import concurrent.futures
import json
import math
import os
import shutil
import subprocess
import time
import urllib.request
import wave
from pathlib import Path

import numpy as np
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import maximum_filter1d, uniform_filter1d
from scipy.signal import butter, sosfiltfilt

# ==============================================================================
# 1. PATHS, CREDENTIALS & CONSTANTS
# ==============================================================================
ROOT_DIR = Path("./output_project")
V1_DIR = ROOT_DIR / "03_a_semente_pixar_2min"
V1_CLIPS_DIR = V1_DIR / "clips_v3"
V1_AUDIO_DIR = V1_CLIPS_DIR / "audio_v4"

BASE_DIR = ROOT_DIR / "07_a_semente_pixar_v2_2m24s"
CLIPS_DIR = BASE_DIR / "clips_v2"
AUDIO_DIR = CLIPS_DIR / "audio_v2"
CLIPS_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

SA_KEY_PATH = ""
ADC_PATH = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")

TTS_PROJECT = os.environ.get("GCP_PROJECT_ID", "your-gcp-project-id")
IMAGE_PROJECT = os.environ.get("GCP_PROJECT_ID", "your-gcp-project-id")
IMAGE_LOCATION = "global"
IMAGE_MODEL = "gemini-2.5-flash-image"

VEO_PROJECT = os.environ.get("GCP_PROJECT_ID", "your-gcp-project-id")
VEO_LOCATION = "us-central1"
VEO_MODEL = "veo-3.1-generate-001"
FIXED_SEED = 20112026

SR = 48000
FPS = 24
WIDTH = 1920
HEIGHT = 1080
NUM_SCENES = 18
SCENE_DUR = 8.0
TOTAL_DUR = NUM_SCENES * SCENE_DUR  # 144.0s (2m24s, 3,456 frames)

FONT_SANS_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_SANS_REG = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_FUTURA = "/System/Library/Fonts/Supplemental/Futura.ttc"

C_BLUE = (66, 133, 244)
C_RED = (234, 67, 53)
C_YELLOW = (251, 188, 4)
C_GREEN = (52, 168, 83)
C_WHITE = (255, 255, 255)

NEGATIVE_PROMPT_PIXAR = (
    "text, words, letters, numbers, captions, subtitles, watermark, logo, "
    "photorealistic, live action, realistic human skin, uncanny valley, "
    "distorted faces, extra fingers, deformed hands, melting geometry, "
    "anime, 2D cartoon, cel shading, flat illustration, horror, dark mood, "
    "shaky camera, zoom out, reverse motion, spoken dialogue, voice over, "
    "narration, singing"
)

# Exact start frame trim for each scene so the first frame already has active motion
START_TRIM_FRAMES = {
    1: 2, 2: 2, 3: 1, 4: 2, 5: 2, 6: 2, 7: 1, 8: 2, 9: 1,
    10: 2, 11: 2, 12: 1, 13: 2, 14: 1, 15: 1, 16: 1, 17: 2, 18: 2,
}


def get_tts_token() -> str:
    creds = service_account.Credentials.from_service_account_file(
        SA_KEY_PATH,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    creds.refresh(Request())
    return creds.token


def get_adc_token() -> str:
    with open(ADC_PATH, "r") as f:
        info = json.load(f)
    creds = Credentials.from_authorized_user_info(
        info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    creds.refresh(Request())
    return creds.token


# ==============================================================================
# 2. COMPLETE 18-SCENE V2 METADATA (2011 -> 2026 -> $2B)
# ==============================================================================
SCENES_META = {
    1: {
        "act": 1,
        "time": "0:00–0:08",
        "vo_offset": 0.40,
        "vo_en": "In two thousand eleven, there was a seed. Fifteen years ago, in an empty plaza, the first roots of Aurora Cloud were planted.",
        "vo_ptbr": "Em dois mil e onze, havia uma semente. Quinze anos atrás, numa praça vazia, nascia a história de Aurora Cloud.",
        "badge": "2011 · THE FIRST SEED",
        "badge_pt": "2011 · A PRIMEIRA SEMENTE",
        "headline": "2011 · 15 Years Ago",
        "headline_pt": "2011 · Há 15 Anos",
        "sub": "Where the Aurora Cloud Structure Was Born · 33 Countries to Reach",
        "sub_pt": "Onde Nasceu a Estrutura Aurora Cloud · 33 Países pela Frente",
        "accent": C_BLUE,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    2: {
        "act": 1,
        "time": "0:08–0:16",
        "vo_offset": 0.30,
        "vo_en": "Until February twenty twenty, most of our team operated remotely from California and Texas — tending our region from afar by a thread of light.",
        "vo_ptbr": "Até fevereiro de dois mil e vinte, a maioria do time operava remotamente da Califórnia e do Texas — regando a região de longe por um fio de luz.",
        "badge": "2011–FEB 2020 · NURTURED FROM AFAR",
        "badge_pt": "2011–FEV 2020 · REGANDO DE LONGE",
        "headline": "California & Texas → LATAM",
        "headline_pt": "Califórnia e Texas → LATAM",
        "sub": "Until Feb 2020 Most of the Team Operated Remotely from the US (CA & TX)",
        "sub_pt": "Até Fev/2020 a Maioria do Time Operava Remotamente dos EUA (CA e TX)",
        "accent": C_YELLOW,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    3: {
        "act": 1,
        "time": "0:16–0:24",
        "vo_offset": 0.30,
        "vo_en": "In twenty sixteen, Cloud took shape — and in twenty seventeen, South America's first region reached one hundred and twenty-one million.",
        "vo_ptbr": "Em dois mil e dezesseis, o Cloud ganhou forma — e em dois mil e dezessete, a primeira região chegou a cento e vinte e um milhões.",
        "badge": "2016–2017 · CLOUD INCEPTION & 1ST REGION",
        "badge_pt": "2016–2017 · SEGMENTO CLOUD E 1ª REGIÃO",
        "headline": "$121M · São Paulo Region",
        "headline_pt": "US$ 121M · Região São Paulo",
        "sub": "Sep 19, 2017 — South America's 1st Google Cloud Region · 33 Countries",
        "sub_pt": "19 Set 2017 — 1ª Região Google Cloud na América do Sul · 33 Países",
        "accent": C_BLUE,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    4: {
        "act": 1,
        "time": "0:24–0:32",
        "vo_offset": 0.35,
        "vo_en": "In twenty eighteen, the LATAM GCP sales structure launched with a lean team of just two people standing in an immense plaza.",
        "vo_ptbr": "Em dois mil e dezoito, a estrutura de vendas de GCP na América Latina nasceu com um time enxuto de apenas duas pessoas numa praça imensa.",
        "badge": "2018 · LEAN GCP TEAM OF TWO",
        "badge_pt": "2018 · TIME ENXUTO DE DOIS NO GCP",
        "headline": "2 Pioneers in 2018",
        "headline_pt": "2 Pioneiros em 2018",
        "sub": "LATAM GCP Sales Structure Launched with 2 · Today: 33 FTEs + 52 Extended",
        "sub_pt": "Vendas GCP LATAM Nasceu com 2 Pessoas · Hoje: 33 FTEs + 52 Estendidos",
        "accent": C_GREEN,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    5: {
        "act": 2,
        "time": "0:32–0:40",
        "vo_offset": 0.30,
        "vo_en": "In December twenty nineteen, we came home — starting in Brazil with local currency, local payment, and our first hires in São Paulo.",
        "vo_ptbr": "Em dezembro de dois mil e dezenove, voltamos para casa — começando pelo Brasil com moeda local, pagamento local e contratações em São Paulo.",
        "badge": "2019 / DEC 2019 · COMING HOME: BRAZIL",
        "badge_pt": "2019 / DEZ 2019 · A VOLTA PARA CASA: BRASIL",
        "headline": "Brazil · São Paulo",
        "headline_pt": "Brasil · São Paulo",
        "sub": "Local Currency + Local FOP (2019) · First Local Hires in São Paulo (Dec 2019)",
        "sub_pt": "Moeda Local + FOP Local (2019) · Primeiras Contratações em São Paulo (Dez 2019)",
        "accent": C_GREEN,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    6: {
        "act": 2,
        "time": "0:40–0:48",
        "vo_offset": 0.30,
        "vo_en": "Between December twenty nineteen and twenty twenty, Mexico joined — with our first local hires in Mexico City and local form of payment.",
        "vo_ptbr": "Entre dezembro de dois mil e dezenove e dois mil e vinte, veio o México — com as primeiras contratações na Cidade do México e pagamento local.",
        "badge": "DEC 2019 / 2020 · LOCALIZATION: MEXICO",
        "badge_pt": "DEZ 2019 / 2020 · LOCALIZAÇÃO: MÉXICO",
        "headline": "Mexico · Mexico City",
        "headline_pt": "México · Cidade do México",
        "sub": "1st Local Hires (Dec 2019) & Local FOP (2020) · GCP $7M→$27M · GWS $181M",
        "sub_pt": "Primeiras Contratações (Dez 2019) e FOP Local (2020) · GCP $27M · GWS $181M",
        "accent": C_YELLOW,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    7: {
        "act": 2,
        "time": "0:48–0:56",
        "vo_offset": 0.25,
        "vo_en": "In twenty twenty-one, Chile lit up with our first hire in Santiago — reaching sixty-two million in GCP and two-seventy-nine million in Workspace.",
        "vo_ptbr": "Em dois mil e vinte e um, o Chile acendeu em Santiago — com sessenta e dois milhões em GCP e duzentos e setenta e nove milhões em Workspace.",
        "badge": "2021 · LOCALIZATION: CHILE",
        "badge_pt": "2021 · LOCALIZAÇÃO: CHILE",
        "headline": "Chile · $62M GCP & $279M GWS",
        "headline_pt": "Chile · US$ 62M GCP e US$ 279M GWS",
        "sub": "First Local Hire in Santiago (2021) · Intermediate Milestone: $62M GCP / $279M GWS",
        "sub_pt": "Primeira Contratação em Santiago (2021) · Marco Intermediário: US$ 62M GCP / US$ 279M GWS",
        "accent": C_BLUE,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    8: {
        "act": 2,
        "time": "0:56–1:04",
        "vo_offset": 0.30,
        "vo_en": "And in twenty twenty-two, Colombia lit up with our first local hires in Bogotá — completing a four-year localization journey across our core markets.",
        "vo_ptbr": "E em dois mil e vinte e dois, a Colômbia acendeu com as primeiras contratações em Bogotá — completando quatro anos de localização nos nossos mercados.",
        "badge": "2022 · LOCALIZATION: COLOMBIA",
        "badge_pt": "2022 · LOCALIZAÇÃO: COLÔMBIA",
        "headline": "Colombia · Bogotá (2019→2022)",
        "headline_pt": "Colômbia · Bogotá (2019→2022)",
        "sub": "1st Local Hires in Bogotá · 4-Year Sequence: BR (19) → MX (20) → CL (21) → CO (22)",
        "sub_pt": "Primeiras Contratações em Bogotá · Sequência: BR (19) → MX (20) → CL (21) → CO (22)",
        "accent": C_RED,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    9: {
        "act": 2,
        "time": "1:04–1:12",
        "vo_offset": 0.30,
        "vo_en": "By twenty twenty-four, multi-hub maturity and deep technical specialization across five regional hubs propelled the tree to seven hundred and two million dollars.",
        "vo_ptbr": "Em dois mil e vinte e quatro, a maturidade multi-hub e a especialização técnica em cinco hubs levaram a árvore a setecentos e dois milhões de dólares.",
        "badge": "2023–2024 · MULTI-HUB MATURITY",
        "badge_pt": "2023–2024 · MATURIDADE MULTI-HUB",
        "headline": "$702M · 5 Regional Hubs",
        "headline_pt": "US$ 702M · 5 Hubs Regionais",
        "sub": "Multi-Hub Maturity & Technical Specialization Across Latin America",
        "sub_pt": "Maturidade Multi-Hub e Especialização Técnica na América Latina",
        "accent": C_YELLOW,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    10: {
        "act": 3,
        "time": "1:12–1:20",
        "vo_offset": 0.25,
        "vo_en": "From two pioneers, GCP grew to thirty-three F T Es plus fifty-two extended — our fastest engine at one hundred and ninety-one million ARR, up forty-eight percent.",
        "vo_ptbr": "De dois pioneiros, o GCP chegou a trinta e três F T Es mais cinquenta e dois estendidos — cento e noventa e um milhões em ARR, crescendo quarenta e oito por cento.",
        "badge": "ACT III · PILLARS 1 & 2 · THE FASTEST ENGINE",
        "badge_pt": "ATO III · PILARES 1 E 2 · O MOTOR MAIS RÁPIDO",
        "headline": "$191M ARR GCP (+48% YoY)",
        "headline_pt": "US$ 191M ARR GCP (+48% YoY)",
        "sub": "From 2 Pioneers (2018) to 33 FTEs + 52 Extended · Local Presence + Scaled Motion",
        "sub_pt": "De 2 Pioneiros (2018) para 33 FTEs + 52 Estendidos · Presença Local + Scaled Motion",
        "accent": C_BLUE,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    11: {
        "act": 3,
        "time": "1:20–1:28",
        "vo_offset": 0.25,
        "vo_en": "Our third pillar: the partners who believed early — driving three hundred and fifty-one million dollars in ARR, growing twenty-seven percent.",
        "vo_ptbr": "Nosso terceiro pilar: os parceiros que acreditaram antes — gerando trezentos e cinquenta e um milhões em ARR, crescendo vinte e sete por cento.",
        "badge": "PILLAR 3 · PARTNER ECOSYSTEM",
        "badge_pt": "PILAR 3 · ECOSSISTEMA DE PARCEIROS",
        "headline": "$351M ARR via Partners (+27%)",
        "headline_pt": "US$ 351M ARR via Parceiros (+27%)",
        "sub": "Thousands of Partners Across LATAM Who Believed Before There Was Proof",
        "sub_pt": "Milhares de Parceiros pela Região que Acreditaram Antes de Haver Prova",
        "accent": C_GREEN,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    12: {
        "act": 3,
        "time": "1:28–1:36",
        "vo_offset": 0.30,
        "vo_en": "And our fourth pillar: every function united as One Google — adding two hundred and sixty million in net-new ARR in just twelve months.",
        "vo_ptbr": "E o quarto pilar: todas as áreas unidas como One Google — adicionando duzentos e sessenta milhões em novo ARR em apenas doze meses.",
        "badge": "PILLAR 4 · ONE GOOGLE ACCELERATION",
        "badge_pt": "PILAR 4 · ACELERAÇÃO ONE GOOGLE",
        "headline": "+$260M Net-New ARR in 12m",
        "headline_pt": "+US$ 260M Novo ARR em 12 Meses",
        "sub": "Sales · Eng · Marketing · Partners · Finance · gTech · Legal · People Ops",
        "sub_pt": "Vendas · Eng · Marketing · Parceiros · Finanças · gTech · Jurídico · People Ops",
        "accent": C_RED,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    13: {
        "act": 3,
        "time": "1:36–1:44",
        "vo_offset": 0.35,
        "vo_en": "Fifteen years. From twenty eleven to twenty twenty-six. Hundreds of people — most of whom will never know which branch was theirs.",
        "vo_ptbr": "Quinze anos. De dois mil e onze a dois mil e vinte e seis. Centenas de pessoas — muitas sem nunca saber qual galho era o seu.",
        "badge": "2011 – 2026 · FIFTEEN YEARS",
        "badge_pt": "2011 – 2026 · QUINZE ANOS",
        "headline": "15 Years of Legacy",
        "headline_pt": "15 Anos de Legado",
        "sub": "Every Pioneer, Past and Present, Lives in This Canopy",
        "sub_pt": "Cada Construtor, do Passado e do Presente, Vive Nesta Copa",
        "accent": C_YELLOW,
        "trans_type": "dissolve",
        "trans_dur": 16,
    },
    14: {
        "act": 4,
        "time": "1:44–1:52",
        "vo_offset": 1.10,  # Dynamically aligned so speech ends at 6.90s (1:50.90) -> 1.10s pure silence before 1:52.0!
        "vo_en": "Each lantern in this canopy is a customer — one point one million paying customers, growing thirty-two percent. And then...",
        "vo_ptbr": "Cada lanterna nesta copa é um cliente — um milhão e cem mil clientes pagantes, crescendo trinta e dois por cento. E então...",
        "badge": "1.1M+ PAYING CUSTOMERS (+32% YoY)",
        "badge_pt": "1,1 MILHÃO+ DE CLIENTES PAGANTES (+32% YoY)",
        "headline": "1.1 Million Lanterns",
        "headline_pt": "1,1 Milhão de Lanternas",
        "sub": "Each Lantern in the Canopy Is a Paying Customer (+32% YoY Across 33 Countries)",
        "sub_pt": "Cada Lanterna na Copa É um Cliente Pagante (+32% YoY pelos 33 Países)",
        "accent": C_BLUE,
        "trans_type": "cut",  # Dramatic cut after 1.0s silence at 1:51.0-1:52.0!
        "trans_dur": 0,
    },
    15: {
        "act": 4,
        "time": "1:52–2:00",
        "vo_offset": 0.08,
        "vo_en": "One billion. Crossed in March twenty twenty-six at one point zero six billion — and soaring to one point one six billion dollars in ARR.",
        "vo_ptbr": "Um bilhão. Cruzado em março de dois mil e vinte e seis em um vírgula zero seis bilhão — e saltando para um vírgula dezesseis bilhão de dólares em ARR.",
        "badge": "MARCH 2026 ($1.06B CROSSING) → SEPTEMBER 2026 ($1.16B ARR)",
        "badge_pt": "MARÇO 2026 (CRUZAMENTO US$ 1,06B) → SETEMBRO 2026 (US$ 1,16B ARR)",
        "headline": "COUNTER",  # Dynamic animated counter $702M -> $1.06B -> $1.16B ARR
        "headline_pt": "COUNTER",
        "sub": "Crossed $1B in March 2026 ($1.06B) · Reaching $1.16B ARR (+29% YoY, Sep 2026)",
        "sub_pt": "Cruzou US$ 1B em Março/2026 (US$ 1,06B) · Atingindo US$ 1,16B ARR (+29% YoY, Set/2026)",
        "accent": C_YELLOW,
        "trans_type": "dissolve",
        "trans_dur": 12,
    },
    16: {
        "act": 4,
        "time": "2:00–2:08",
        "vo_offset": 0.25,
        "vo_en": "One point one six billion dollars in ARR — growing twenty-nine percent year over year, with two hundred and sixty million added in twelve months!",
        "vo_ptbr": "Um vírgula dezesseis bilhão de dólares em ARR — crescendo vinte e nove por cento ao ano, com mais duzentos e sessenta milhões em doze meses!",
        "badge": "SEPTEMBER 2026 · HISTORIC ARR MILESTONE (+29% YoY)",
        "badge_pt": "SETEMBRO 2026 · MARCO HISTÓRICO DE ARR (+29% YoY)",
        "headline": "$1.16B ARR · +29% YoY",
        "headline_pt": "US$ 1,16B ARR · +29% YoY",
        "sub": "Crossed in March 2026 ($1.06B) · +$260M Net-New ARR · 1.1M+ Paying Customers",
        "sub_pt": "Cruzamento em Março/2026 (US$ 1,06B) · +US$ 260M Novo ARR · 1,1M+ Clientes Pagantes",
        "accent": C_GREEN,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    17: {
        "act": 5,
        "time": "2:08–2:16",
        "vo_offset": 0.25,
        "vo_en": "And at the tip of the highest branch, a new sprout is blooming — powered by Gemini Enterprise, A I S, and A W T.",
        "vo_ptbr": "E no alto do galho mais forte, um novo broto já floresce — impulsionado por Gemini Enterprise, A I S e A W T.",
        "badge": "ACT V · THE NEW SPROUT OF AI",
        "badge_pt": "ATO V · O NOVO BROTO DA INTELIGÊNCIA ARTIFICIAL",
        "headline": "Gemini Enterprise · AIS · AWT",
        "headline_pt": "Gemini Enterprise · AIS · AWT",
        "sub": "A New Luminous Sprout Blooming at the Top of the Canopy → $2B Horizon",
        "sub_pt": "Um Novo Broto Luminoso Florescendo no Topo da Copa → Rumo a US$ 2B",
        "accent": C_BLUE,
        "trans_type": "dissolve",
        "trans_dur": 14,
    },
    18: {
        "act": 5,
        "time": "2:16–2:24",
        "vo_offset": 0.30,
        "vo_en": "The first billion took fifteen years — and all of us. Now, onward to two billion. Thank you, Aurora Cloud.",
        "vo_ptbr": "O primeiro bilhão levou quinze anos — e todos nós. Agora, rumo aos dois bilhões. Obrigado, Aurora Cloud.",
        "badge": "2011 – 2026 · FIFTEEN YEARS TO $1B · ONWARD TO $2B",
        "badge_pt": "2011 – 2026 · QUINZE ANOS ATÉ US$ 1B · RUMO AOS US$ 2B",
        "headline": "15 Years to $1B · Next: $2B",
        "headline_pt": "15 Anos até US$ 1B · Rumo a US$ 2B",
        "sub": "Thank you, Aurora Cloud — Every Pioneer, Partner, and Builder.",
        "sub_pt": "Obrigado, Aurora Cloud — A Cada Pioneiro, Parceiro e Construtor.",
        "accent": C_YELLOW,
        "trans_type": "fade_out",
        "trans_dur": 24,
    },
}


# ==============================================================================
# 3. COPY V1 ASSETS & GENERATE 5 NEW PIXAR V2 SCENES IN VEO 3.1
# ==============================================================================
V1_TO_V2_SCENE_MAP = {
    1: "scene_01.mp4",   # 2011: A Primeira planting the seed in the empty plaza
    3: "scene_04.mp4",   # 2016-2017: Underground glowing blue roots spreading
    5: "scene_05.mp4",   # Dec 2019: Coming home to Brazil, A Primeira touching the sapling
    6: "scene_06.mp4",   # 2020: More local hands arriving in the plaza (Mexico wave)
    7: "scene_07.mp4",   # 2021: Branch flying across the Andes into Santiago, Chile
    8: "scene_08.mp4",   # 2022: Branch reaching Bogota, Colombia & canopy lighting up
    9: "scene_09.mp4",   # 2023-2024: Vertical climb along trunk past 5 hub platforms ($702M)
    12: "scene_10.mp4",  # Pillar 4: 8 One Google craft groups working around the base
    13: "scene_11.mp4",  # 15 Years (2011-2026): Locked-off time-lapse of aged A Primeira
    14: "scene_12.mp4",  # 1.1M customer lanterns glowing in orbital view + silence
    15: "scene_13.mp4",  # March 2026 -> Sep 2026: Golden fruit swelling with white-gold light
    16: "scene_14.mp4",  # $1.16B ARR: Golden fruit bursting into 4-color glowing leaves
    18: "scene_15.mp4",  # Finale: Aged A Primeira in the crowd beneath the canopy -> $2B
}

NEW_VEO_SCENES = {
    2: {
        "use_keyframe": "keyframe_02_remote.png",
        "keyframe_prompt": (
            "Pixar-style 3D feature animation, RenderMan quality render, 16:9 widescreen cinematic frame. "
            "Using the exact young woman character from the reference image (warm brown skin, dark curly hair tied back, "
            "round glasses, vibrant mustard-yellow jacket), show her standing in a quiet northern studio room (California/Texas) "
            "beside a warm glowing relief map table, gently pouring droplets of golden-blue light into a luminous stream that arcs "
            "out through a panoramic window across a vast twilight continent toward a tiny glowing sapling in a distant Latin American plaza. "
            "No text, no words, no numbers, no letters."
        ),
        "prompt": (
            "SUBJECT: A stylized 3D Pixar-style scene: the young woman with warm brown skin, dark curly hair tied back, round glasses, "
            "and mustard-yellow jacket stands with two fellow pioneers beside a glowing relief table in a northern room, tending a continuous "
            "golden-blue thread of light that arcs across a vast twilight landscape from North America down to a tiny glowing sapling in a distant Latin American plaza. "
            "ACTION: She gently pours luminous droplets into the glowing stream; pulses of warm blue-gold light travel along the thread across the continent "
            "to water and nurture the distant sapling from afar. She gazes toward the southern horizon with quiet devotion and longing. "
            "CAMERA: Smooth slow push-in and pan following the glowing thread of light from her hands toward the distant southern horizon. "
            "LENS: 35mm cinema lens, shallow depth of field on the character resolving into deep geographic scale. "
            "LIGHTING: Cool twilight ambient light contrasted with the warm golden-blue bioluminescent arc of light connecting North and South. "
            "COLOR: Cool slate twilight blues, warm amber and electric blue (#4285F4) along the connecting light thread, mustard-yellow jacket (#FBBC04). "
            "AUDIO: Gentle humming light arc, soft water chime travelling across distance, quiet breeze. No spoken dialogue, no voices, no music. "
            "STYLE: High-end stylized 3D feature animation, RenderMan quality, appealing character proportions, subsurface scattering, soft global illumination."
        ),
    },
    4: {
        "use_keyframe": None,
        "prompt": (
            "SUBJECT: An enormous, vast stone plaza stretching to the horizon in stylized 3D Pixar animation. At the exact center, beside a young glowing sapling, "
            "stand ONLY TWO small stylized 3D animated characters — a lean team of two pioneers — looking tiny against the colossal scale of the plaza. "
            "ACTION: Working side by side with quiet determination, the two characters connect a thick glowing electric-blue and gold root conduit into the base of the sapling. "
            "As they lock it in place together, a powerful surge of blue and golden light shoots up the trunk, making the young tree grow taller and brighter. The two pioneers exchange a proud nod. "
            "CAMERA: Starts as a dramatic high wide shot emphasizing just two figures in the enormous empty plaza, then pushes in smoothly to a medium two-shot beside the glowing trunk. "
            "LENS: 35mm lens, cinematic depth of field. "
            "LIGHTING: Early morning cool mist pierced by the intense warm electric blue (#4285F4) and gold (#FBBC04) glow of the sapling's new GCP root. "
            "COLOR: Cool morning greys warming into vibrant electric blue and gold. "
            "AUDIO: Footsteps of two people in a vast plaza, a resonant power-up chime as the conduit connects, leaves rustling. No spoken dialogue, no voices, no music. "
            "STYLE: High-end stylized 3D feature animation, RenderMan quality, appealing character proportions, emotional scale contrast."
        ),
    },
    10: {
        "use_keyframe": None,
        "prompt": (
            "SUBJECT: Inside the glowing lower canopy of the colossal tree: a vibrant stylized 3D Pixar ensemble of dozens of specialized builders and engineers "
            "working across interconnected wooden and luminous glass walkways around a massive pulsing electric-blue and gold core conduit in the tree trunk. "
            "ACTION: The camera glides smoothly forward along the central walkway as teams coordinate high-velocity streams of sap-light shooting upward into the branches; "
            "the blue core surges with intense radiant energy, illuminating the faces of the crew with warm pride. "
            "CAMERA: Smooth dynamic forward tracking shot through the bustling multi-level tree hub. "
            "LENS: 35mm lens, medium depth of field keeping the collaborative action legible. "
            "LIGHTING: Dramatic bioluminescent electric blue (#4285F4) and warm golden sunlight (#FBBC04) filtering through the canopy. "
            "COLOR: Rich emerald greens, electric blue energy streams, warm golden wood and sunlight. "
            "AUDIO: Energetic hum of flowing light conduits, footsteps on wooden walkways, harmonious chimes of acceleration. No spoken dialogue, no voices, no music. "
            "STYLE: High-end stylized 3D feature animation, RenderMan quality, vibrant ensemble staging, volumetric lighting."
        ),
    },
    11: {
        "use_keyframe": None,
        "prompt": (
            "SUBJECT: A breathtaking wide view of the colossal tree's outer branches where dozens of stylized 3D partner artisans on surrounding hills and wooden bridges "
            "weave golden cables of light and hang glowing lanterns onto the expanding branches across a stylized Latin American landscape. "
            "ACTION: As the partner teams attach new lantern clusters along the bridges, a wave of golden-green light cascades across hundreds of branches, "
            "expanding the canopy's reach and sending flocks of luminous light-birds soaring into the golden sky. "
            "CAMERA: Majestic sweeping crane shot rising over the partner bridges toward the glowing canopy. "
            "LENS: 28mm wide lens, deep focus capturing the vast collaborative partner network. "
            "LIGHTING: Warm golden-hour sunlight combined with thousands of glowing partner lanterns in blue, red, yellow, and green. "
            "COLOR: Warm gold, emerald green (#34A853), sapphire blue (#4285F4), and sunset amber. "
            "AUDIO: Shimmering cascade of chimes as lanterns ignite, gentle breeze, soft wingbeats of light-birds. No spoken dialogue, no voices, no music. "
            "STYLE: High-end stylized 3D feature animation, RenderMan quality, epic collaborative scale, magical realism."
        ),
    },
    17: {
        "use_keyframe": None,
        "prompt": (
            "SUBJECT: At the very top of the colossal tree's highest sunlit branch above a sea of golden clouds, a brand-new, extraordinarily luminous crystal-and-gold sprout "
            "is unfolding its first leaves — glowing with an iridescent Gemini sapphire-blue, soft violet, and warm gold bioluminescence. "
            "ACTION: As the camera pushes in gently past the new sprout, its glowing leaves unfurl in graceful slow motion, releasing a delicate stream of starlight particles "
            "that float forward toward a second, even brighter golden horizon shining in the distance. "
            "CAMERA: Smooth, inspiring forward push-in past the blooming Gemini sprout toward the glowing horizon beyond. "
            "LENS: 50mm lens, shallow depth of field with shimmering starlight bokeh. "
            "LIGHTING: Warm sunrise gold combined with iridescent Gemini blue-violet bioluminescence from the new sprout. "
            "COLOR: Iridescent sapphire blue (#4285F4), soft violet, emerald green (#34A853), and radiant sunrise gold (#FBBC04). "
            "AUDIO: Delicate crystalline unfolding chime, warm hopeful harmonic shimmer, gentle high-altitude breeze. No spoken dialogue, no voices, no music. "
            "STYLE: High-end stylized 3D feature animation, RenderMan quality, magical realism, poetic forward-looking framing."
        ),
    },
}


def prepare_base_assets():
    print("=== Step 0: Copying Reference Sheets, Lyria 3 Stems & Matching Pixar Clips ===", flush=True)
    for sheet in ["a_primeira_reference_sheet.png", "a_primeira_aged_reference_sheet.png"]:
        src = V1_CLIPS_DIR / sheet
        dst = CLIPS_DIR / sheet
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)

    for wav_name in ["lyria3_pro_full.wav", "lyria3_clip_01.wav", "lyria3_clip_02.wav", "lyria3_clip_03.wav", "lyria3_clip_04.wav"]:
        src = V1_AUDIO_DIR / wav_name
        dst = AUDIO_DIR / wav_name
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)

    for v2_idx, v1_name in V1_TO_V2_SCENE_MAP.items():
        src = V1_CLIPS_DIR / v1_name
        dst = CLIPS_DIR / f"scene_{v2_idx:02d}.mp4"
        if src.exists() and (not dst.exists() or dst.stat().st_size < 1_000_000):
            shutil.copy2(src, dst)
            print(f"  [Copied] {v1_name} -> scene_{v2_idx:02d}.mp4", flush=True)


def generate_keyframe_02_remote() -> Path:
    out_png = CLIPS_DIR / "keyframe_02_remote.png"
    if out_png.exists() and out_png.stat().st_size > 100_000:
        return out_png

    ref_sheet = CLIPS_DIR / "a_primeira_reference_sheet.png"
    ref_b64 = base64.b64encode(ref_sheet.read_bytes()).decode("utf-8")
    prompt = NEW_VEO_SCENES[2]["keyframe_prompt"]

    url = (
        f"https://aiplatform.googleapis.com/v1beta1/projects/{IMAGE_PROJECT}"
        f"/locations/{IMAGE_LOCATION}/publishers/google/models/{IMAGE_MODEL}:generateContent"
    )
    token = get_adc_token()
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"inlineData": {"mimeType": "image/png", "data": ref_b64}},
                    {"text": prompt},
                ],
            }
        ],
        "generationConfig": {
            "responseModalities": ["IMAGE", "TEXT"],
            "imageConfig": {"aspectRatio": "16:9"},
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "x-goog-user-project": IMAGE_PROJECT,
        },
        method="POST",
    )
    print("  [Keyframe 02] Generating Pixar remote watering keyframe from character sheet...", flush=True)
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    for cand in data.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            if "inlineData" in part and part["inlineData"].get("data"):
                raw = base64.b64decode(part["inlineData"]["data"])
                out_png.write_bytes(raw)
                img = Image.open(out_png).convert("RGB").resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
                img.save(out_png, format="PNG")
                print(f"  [Keyframe 02] Saved {out_png.name} ({out_png.stat().st_size:,} bytes)", flush=True)
                return out_png
    raise RuntimeError("Failed to generate keyframe_02_remote.png")


def generate_one_veo_scene(scene_idx: int, spec: dict) -> Path:
    out_mp4 = CLIPS_DIR / f"scene_{scene_idx:02d}.mp4"
    if out_mp4.exists() and out_mp4.stat().st_size > 2_000_000:
        print(f"  [Veo 3.1] Scene {scene_idx:02d} already exists ({out_mp4.stat().st_size:,} bytes)", flush=True)
        return out_mp4

    predict_url = (
        f"https://{VEO_LOCATION}-aiplatform.googleapis.com/v1/projects/{VEO_PROJECT}"
        f"/locations/{VEO_LOCATION}/publishers/google/models/{VEO_MODEL}:predictLongRunning"
    )
    fetch_url = (
        f"https://{VEO_LOCATION}-aiplatform.googleapis.com/v1/projects/{VEO_PROJECT}"
        f"/locations/{VEO_LOCATION}/publishers/google/models/{VEO_MODEL}:fetchPredictOperation"
    )

    instance = {"prompt": spec["prompt"]}
    kf_name = spec.get("use_keyframe")
    if kf_name:
        kf_path = CLIPS_DIR / kf_name
        if kf_path.exists():
            instance["image"] = {
                "bytesBase64Encoded": base64.b64encode(kf_path.read_bytes()).decode("utf-8"),
                "mimeType": "image/png",
            }

    parameters = {
        "aspectRatio": "16:9",
        "sampleCount": 1,
        "durationSeconds": 8,
        "resolution": "1080p",
        "personGeneration": "allow_all",
        "enhancePrompt": True,
        "generateAudio": True,
        "negativePrompt": NEGATIVE_PROMPT_PIXAR,
        "seed": FIXED_SEED + scene_idx,
    }

    for attempt in range(4):
        try:
            token = get_adc_token()
            req = urllib.request.Request(
                predict_url,
                data=json.dumps({"instances": [instance], "parameters": parameters}).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "x-goog-user-project": VEO_PROJECT,
                },
                method="POST",
            )
            print(f"  [Veo 3.1] Launching Scene {scene_idx:02d} (attempt {attempt+1})...", flush=True)
            with urllib.request.urlopen(req, timeout=90) as resp:
                op_data = json.loads(resp.read().decode("utf-8"))
            op_name = op_data["name"]

            for poll in range(80):
                time.sleep(6)
                token = get_adc_token()
                freq = urllib.request.Request(
                    fetch_url,
                    data=json.dumps({"operationName": op_name}).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        "x-goog-user-project": VEO_PROJECT,
                    },
                    method="POST",
                )
                with urllib.request.urlopen(freq, timeout=60) as fresp:
                    res = json.loads(fresp.read().decode("utf-8"))
                if res.get("done"):
                    if "error" in res:
                        raise RuntimeError(f"Veo error on Scene {scene_idx:02d}: {res['error']}")
                    videos = res.get("response", {}).get("videos", [])
                    if not videos:
                        raise RuntimeError(f"No videos returned for Scene {scene_idx:02d}: {res}")
                    b64_vid = videos[0].get("bytesBase64Encoded")
                    if b64_vid:
                        out_mp4.write_bytes(base64.b64decode(b64_vid))
                        print(f"  [Veo 3.1] Saved Scene {scene_idx:02d} ({out_mp4.stat().st_size:,} bytes)", flush=True)
                        return out_mp4
        except Exception as e:
            print(f"  [Veo 3.1] Scene {scene_idx:02d} attempt {attempt+1} failed: {e}", flush=True)
            time.sleep(5)

    raise RuntimeError(f"Failed to generate Veo Scene {scene_idx:02d}")


def generate_all_new_veo_scenes():
    print("=== Step 1: Generating 5 New Pixar 3D Scenes in Veo 3.1 ===", flush=True)
    try:
        generate_keyframe_02_remote()
    except Exception as e:
        print(f"  [Warning] Keyframe 02 fallback to T2V: {e}", flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futs = {ex.submit(generate_one_veo_scene, s_idx, spec): s_idx for s_idx, spec in NEW_VEO_SCENES.items()}
        for fut in concurrent.futures.as_completed(futs):
            s_idx = futs[fut]
            fut.result()
            print(f"  [Veo 3.1] Scene {s_idx:02d} ready!", flush=True)


# ==============================================================================
# 4. CHIRP 3 HD NARRATION SYNTHESIS (18 SCENES · EN-US & PT-BR)
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

    if dur > target_max_dur:
        tempo = min(1.50, (dur / (target_max_dur - 0.12)))
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
                "/opt/homebrew/bin/ffmpeg", "-y", "-i", str(pre_wav),
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
    print("=== Step 2: Synthesizing & Auditing Complete 18-Scene V2 Narration (EN-US & PT-BR) ===", flush=True)
    timings = {"en": {}, "ptbr": {}}

    for lang in ["en", "ptbr"]:
        for s_idx in range(1, NUM_SCENES + 1):
            meta = SCENES_META[s_idx]
            text = meta["vo_en"] if lang == "en" else meta["vo_ptbr"]
            offset = meta["vo_offset"]
            max_dur = 5.80 if s_idx == 14 else (7.45 - offset)

            out_wav = AUDIO_DIR / f"vo_{lang}_{s_idx:02d}.wav"
            dur = synthesize_chirp3_clip(text, lang, out_wav, target_max_dur=max_dur)

            # For Scene 14 (1:44–1:52), align end_in_scene to exact 6.90s (1:50.90) so 1:50.90..1:52.00 is 1.10s of pure silence!
            if s_idx == 14:
                offset = round(max(0.35, 6.90 - dur), 3)

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
        timings[lang][15]["one_billion_phrase_dur"] = round(dur_1b, 3)
        print(f"  [VO {lang.upper()}] Scene 15 '{phrase}' exact phrase duration: {dur_1b:.3f}s", flush=True)

    timings_path = AUDIO_DIR / "timings_v2.json"
    timings_path.write_text(json.dumps(timings, indent=2, ensure_ascii=False))
    return timings


# ==============================================================================
# 5. STUDIO MASTER AUDIO ENGINE (144.0s Lyria 3 + Lookahead Ducking <60% + Veo SFX)
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
    n_target = int(SCENE_DUR * SR)
    mp4_path = CLIPS_DIR / f"scene_{scene_idx:02d}.mp4"
    tmp_wav = AUDIO_DIR / f"_veo_sfx_{scene_idx:02d}.wav"
    if not tmp_wav.exists():
        subprocess.run(
            [
                "/opt/homebrew/bin/ffmpeg", "-y", "-i", str(mp4_path),
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

    sos_hp = butter(2, 110.0 / (SR / 2.0), btype="highpass", output="sos")
    sos_lp = butter(2, 10000.0 / (SR / 2.0), btype="lowpass", output="sos")
    l = sosfiltfilt(sos_lp, sosfiltfilt(sos_hp, l)).astype(np.float32)
    r = sosfiltfilt(sos_lp, sosfiltfilt(sos_hp, r)).astype(np.float32)

    fade = int(0.15 * SR)
    l[:fade] *= np.linspace(0.0, 1.0, fade, dtype=np.float32)
    r[:fade] *= np.linspace(0.0, 1.0, fade, dtype=np.float32)
    l[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
    r[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
    return l, r


def equal_power_concat(segs_L: list[np.ndarray], segs_R: list[np.ndarray], xfade_sec: float = 4.0) -> tuple[np.ndarray, np.ndarray]:
    xf = int(xfade_sec * SR)
    out_L = segs_L[0].copy()
    out_R = segs_R[0].copy()
    for next_L, next_R in zip(segs_L[1:], segs_R[1:]):
        theta = np.linspace(0.0, np.pi / 2.0, xf, dtype=np.float32)
        fo = np.cos(theta)
        fi = np.sin(theta)
        out_L[-xf:] = out_L[-xf:] * fo + next_L[:xf] * fi
        out_R[-xf:] = out_R[-xf:] * fo + next_R[:xf] * fi
        out_L = np.concatenate([out_L, next_L[xf:]])
        out_R = np.concatenate([out_R, next_R[xf:]])
    return out_L, out_R


def build_lyria3_master_score_144s() -> tuple[np.ndarray, np.ndarray]:
    """
    Builds the 144.0s (2:24) continuous stereo orchestral score from Google Lyria 3:
    - 0:00.0 to 1:51.0 (0.0s .. 111.0s): Continuous progression combining `lyria3_pro_full.wav` (first 92s)
      equal-power crossfaded into `lyria3_clip_03.wav` (24s orchestral build-up) up to 111.0s.
    - 1:51.0 to 1:52.60 (111.0s .. 112.60s): Exact dramatic silence (1.0s silence + "One billion" solo voice!)
    - 1:52.60 to 2:24.0 (112.60s .. 144.0s = 31.4s): Triumphant orchestral fanfare from `lyria3_clip_04.wav`
      equal-power crossfaded into the glowing piano & string resolution from the tail of `lyria3_pro_full.wav`.
    """
    n_total = int(TOTAL_DUR * SR)
    score_L = np.zeros(n_total, dtype=np.float32)
    score_R = np.zeros(n_total, dtype=np.float32)

    full_L, full_R = load_stereo_wav(AUDIO_DIR / "lyria3_pro_full.wav")
    clip3_L, clip3_R = load_stereo_wav(AUDIO_DIR / "lyria3_clip_03.wav")
    clip4_L, clip4_R = load_stereo_wav(AUDIO_DIR / "lyria3_clip_04.wav")

    def norm_rms(l, r, target_rms=0.18):
        cur = float(np.sqrt(np.mean(0.5 * (l**2 + r**2))))
        if cur > 1e-4:
            g = target_rms / cur
            return l * g, r * g
        return l, r

    full_L, full_R = norm_rms(full_L, full_R, 0.18)
    clip3_L, clip3_R = norm_rms(clip3_L, clip3_R, 0.19)
    clip4_L, clip4_R = norm_rms(clip4_L, clip4_R, 0.21)

    # Pre-climax (0.0s .. 111.0s = 111.0s): 91s of full_L + 25s of clip3_L with 5s equal-power crossfade
    pre_L, pre_R = equal_power_concat(
        [full_L[: int(91.0 * SR)], clip3_L[: int(25.0 * SR)]],
        [full_R[: int(91.0 * SR)], clip3_R[: int(25.0 * SR)]],
        xfade_sec=5.0,
    )
    idx_111 = int(111.0 * SR)
    score_L[:idx_111] = pre_L[:idx_111]
    score_R[:idx_111] = pre_R[:idx_111]

    # Smooth 1.2s fade-in at 0:00
    fi = int(1.2 * SR)
    score_L[:fi] *= np.sin(np.linspace(0.0, np.pi / 2.0, fi, dtype=np.float32))
    score_R[:fi] *= np.sin(np.linspace(0.0, np.pi / 2.0, fi, dtype=np.float32))

    # Crisp dramatic orchestral cutoff into 1:51.0 (111.0s)
    fo_cut = int(0.18 * SR)
    score_L[idx_111 - fo_cut : idx_111] *= np.cos(np.linspace(0.0, np.pi / 2.0, fo_cut, dtype=np.float32))
    score_R[idx_111 - fo_cut : idx_111] *= np.cos(np.linspace(0.0, np.pi / 2.0, fo_cut, dtype=np.float32))

    # Post-climax (112.60s .. 144.0s = 31.40s):
    idx_bloom = int(112.60 * SR)
    len_post = n_total - idx_bloom  # 31.40s

    c4_seg_L = clip4_L[int(0.5 * SR) : int(22.5 * SR)]
    c4_seg_R = clip4_R[int(0.5 * SR) : int(22.5 * SR)]
    tail_seg_L = full_L[-int(15.0 * SR) :]
    tail_seg_R = full_R[-int(15.0 * SR) :]

    post_L, post_R = equal_power_concat([c4_seg_L, tail_seg_L], [c4_seg_R, tail_seg_R], xfade_sec=4.5)
    if len(post_L) < len_post:
        post_L = np.pad(post_L, (0, len_post - len(post_L)))
        post_R = np.pad(post_R, (0, len_post - len(post_R)))
    else:
        post_L = post_L[:len_post]
        post_R = post_R[:len_post]

    # Fast 120ms bloom attack at 112.60s when "One billion" finishes
    atk = int(0.12 * SR)
    post_L[:atk] *= np.sin(np.linspace(0.0, np.pi / 2.0, atk, dtype=np.float32))
    post_R[:atk] *= np.sin(np.linspace(0.0, np.pi / 2.0, atk, dtype=np.float32))

    # Smooth 2.8s final fade-out at 141.2s..144.0s
    fo_end = int(2.8 * SR)
    post_L[-fo_end:] *= np.cos(np.linspace(0.0, np.pi / 2.0, fo_end, dtype=np.float32))
    post_R[-fo_end:] *= np.cos(np.linspace(0.0, np.pi / 2.0, fo_end, dtype=np.float32))

    score_L[idx_bloom:] = post_L
    score_R[idx_bloom:] = post_R

    # Dynamic Sliding-Window RMS Normalizer (AGC Leveler)
    win_agc = int(2.5 * SR)
    inst_power = 0.5 * (score_L**2 + score_R**2)
    local_rms = np.sqrt(uniform_filter1d(inst_power, size=win_agc) + 1e-8)
    target_flat_rms = 0.12
    agc_gain = np.where(local_rms > 0.015, target_flat_rms / local_rms, 1.0)
    agc_gain = np.clip(agc_gain, 0.22, 1.45).astype(np.float32)
    agc_gain = uniform_filter1d(uniform_filter1d(agc_gain, size=int(0.45 * SR)), size=int(0.45 * SR))

    score_L *= agc_gain
    score_R *= agc_gain

    # Flat macro envelope preserving 1:51.0-1:52.60 dramatic silence
    t = np.linspace(0.0, TOTAL_DUR, n_total, dtype=np.float32)
    macro_gain = np.interp(
        t,
        [0.0, 1.2, 110.8, 111.0, 112.55, 112.75, 141.0, 144.0],
        [0.0, 1.0, 1.00,  0.00,  0.00,   0.95,   0.90,  0.00],
    ).astype(np.float32)

    score_L *= macro_gain
    score_R *= macro_gain
    return score_L, score_R


def build_master_audio(lang: str, timings: dict) -> Path:
    print(f"=== Step 3 ({lang.upper()}): Mastering 144s Studio Audio Mix (Music strictly < 60% of Voice) ===", flush=True)
    n_total = int(TOTAL_DUR * SR)

    vo_mono = np.zeros(n_total, dtype=np.float32)
    for s_idx in range(1, NUM_SCENES + 1):
        wav_path = AUDIO_DIR / f"vo_{lang}_{s_idx:02d}.wav"
        clip = load_mono_wav(wav_path)
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

    vo_master_path = AUDIO_DIR / f"vo_master_{lang}_v2.wav"
    vo_pcm = np.clip(vo_mono * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(vo_master_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(vo_pcm.tobytes())

    win = int(0.020 * SR)
    vo_rms_curve = np.sqrt(np.maximum(0.0, uniform_filter1d(vo_mono**2, size=win)))
    active = (vo_rms_curve > 0.010).astype(np.float32)
    hold_samples = int(0.75 * SR)
    active_held = maximum_filter1d(active, size=hold_samples)
    active_smooth = uniform_filter1d(uniform_filter1d(active_held, size=int(0.35 * SR)), size=int(0.35 * SR))
    active_smooth = np.clip(active_smooth, 0.0, 1.0)

    score_L, score_R = build_lyria3_master_score_144s()

    veo_L = np.zeros(n_total, dtype=np.float32)
    veo_R = np.zeros(n_total, dtype=np.float32)
    for s_idx in range(1, NUM_SCENES + 1):
        sl, sr_ch = extract_veo_scene_audio(s_idx)
        i0 = int((s_idx - 1) * SCENE_DUR * SR)
        veo_L[i0 : i0 + len(sl)] = sl
        veo_R[i0 : i0 + len(sr_ch)] = sr_ch

    veo_L[int(110.8 * SR) : int(112.6 * SR)] = 0.0
    veo_R[int(110.8 * SR) : int(112.6 * SR)] = 0.0

    d1 = int(0.018 * SR)
    d2 = int(0.029 * SR)
    vo_L = vo_mono * 1.15
    vo_R = vo_mono * 1.15
    vo_L[d1:] += vo_mono[:-d1] * 0.05
    vo_R[d2:] += vo_mono[:-d2] * 0.05

    vo_active_samples = vo_L[active > 0.5]
    vo_ref_rms = float(np.sqrt(np.mean(vo_active_samples**2))) if len(vo_active_samples) > 0 else 0.22
    vo_ref_peak = float(np.max(np.abs(vo_L))) if np.max(np.abs(vo_L)) > 0.01 else 0.85

    acc_L = score_L + veo_L * 0.05
    acc_R = score_R + veo_R * 0.05
    acc_active = acc_L[np.abs(acc_L) > 0.01]
    acc_rms = float(np.sqrt(np.mean(acc_active**2))) if len(acc_active) > 0 else 0.12
    if acc_rms > 1e-4:
        acc_L *= (vo_ref_rms / acc_rms)
        acc_R *= (vo_ref_rms / acc_rms)

    acc_gain_env = 0.48 - 0.22 * active_smooth
    music_L = acc_L * acc_gain_env
    music_R = acc_R * acc_gain_env

    max_allowed_acc_peak = 0.52 * vo_ref_peak
    music_L = max_allowed_acc_peak * np.tanh(music_L / max_allowed_acc_peak)
    music_R = max_allowed_acc_peak * np.tanh(music_R / max_allowed_acc_peak)

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

    mix_L = music_L + vo_L
    mix_R = music_R + vo_R

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

    out_wav = AUDIO_DIR / f"master_mix_{lang}_v2.wav"
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(stereo_interleaved.tobytes())

    sil_slice = mix_L[int(111.10 * SR) : int(111.95 * SR)]
    sil_rms = float(np.sqrt(np.mean(sil_slice**2)))
    print(
        f"  [Master Audio {lang.upper()}] Saved {out_wav.name} | peak={peak:.3f} -> 0.891 | "
        f"1:51.1-1:51.95 silence RMS={sil_rms:.6f}",
        flush=True,
    )
    return out_wav


# ==============================================================================
# 6. FLUID ZERO-REWIND VIDEO ENGINE + PIXAR V2 TYPOGRAPHY OVERLAYS
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
    mp4_path = CLIPS_DIR / f"scene_{scene_idx:02d}.mp4"
    cmd = [
        "/opt/homebrew/bin/ffmpeg", "-v", "error",
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


def cv_blend(img_a: np.ndarray, img_b: np.ndarray, alpha: float) -> np.ndarray:
    return np.clip(
        img_a.astype(np.float32) * (1.0 - alpha) + img_b.astype(np.float32) * alpha,
        0,
        255,
    ).astype(np.uint8)


def sample_scene_monotonic(
    frames: list[np.ndarray],
    pos_f: float,
    start_trim: int,
    usable_end: int,
) -> np.ndarray:
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


def render_typography_overlay(
    frame_rgb: np.ndarray,
    scene_idx: int,
    f_in_scene: int,
    lang: str,
    timings: dict,
) -> np.ndarray:
    meta = SCENES_META[scene_idx]
    t_in_scene = f_in_scene / float(FPS)

    t_enter = 0.35 if scene_idx != 15 else 0.04
    t_exit = 7.35 if scene_idx != 14 else 6.80
    if t_in_scene < t_enter or t_in_scene > t_exit:
        return frame_rgb

    alpha = 1.0
    if t_in_scene < t_enter + 0.45:
        alpha = (t_in_scene - t_enter) / 0.45
    elif t_in_scene > t_exit - 0.50:
        alpha = (t_exit - t_in_scene) / 0.50
    alpha = max(0.0, min(1.0, alpha))
    alpha = 0.5 - 0.5 * math.cos(math.pi * alpha)

    badge = meta["badge"] if lang == "en" else meta["badge_pt"]
    headline = meta["headline"] if lang == "en" else meta.get("headline_pt", meta["headline"])
    sub = meta["sub"] if lang == "en" else meta["sub_pt"]
    accent = meta["accent"]

    # Dynamic counter for Scene 15 ($702M -> $1.06B [Mar 2026] -> $1.16B ARR [Sep 2026])
    if scene_idx == 15 and headline == "COUNTER":
        vo_start = timings[lang][15]["start_in_scene"]
        dur_1b = timings[lang][15]["one_billion_phrase_dur"]
        lock_106 = vo_start + dur_1b  # crosses $1.06B on "One billion"
        lock_116 = 4.80               # locks in $1.16B ARR as narrator says "one point one six billion"
        if t_in_scene <= vo_start:
            val = 0.702
        elif t_in_scene <= lock_106:
            p = (t_in_scene - vo_start) / max(0.15, (lock_106 - vo_start))
            p_ease = 1.0 - (1.0 - p) ** 2.2
            val = 0.702 + (1.060 - 0.702) * p_ease
        elif t_in_scene <= lock_116:
            p = (t_in_scene - lock_106) / max(0.20, (lock_116 - lock_106))
            p_ease = 1.0 - (1.0 - p) ** 2.0
            val = 1.060 + (1.160 - 1.060) * p_ease
        else:
            val = 1.160

        if val < 1.000:
            m_val = int(round(val * 1000))
            headline = f"${m_val}M ARR" if lang == "en" else f"US$ {m_val}M ARR"
        else:
            headline = f"${val:.2f}B ARR" if lang == "en" else f"US$ {val:.2f}B ARR".replace(".", ",")

    base_img = Image.fromarray(frame_rgb).convert("RGBA")
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    is_centered = scene_idx in (15, 16, 18)
    card_alpha = int(178 * alpha)
    text_alpha = int(255 * alpha)
    sub_alpha = int(228 * alpha)

    f_badge = get_font(FONT_SANS_BOLD, 21)
    f_head = get_font(FONT_FUTURA, 62 if scene_idx in (15, 16) else 50)
    f_sub = get_font(FONT_SANS_REG, 25)

    if is_centered:
        card_w = 1220
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
        bar_w = 240
        bx0 = WIDTH // 2 - bar_w // 2
        for idx_c, col in enumerate([C_BLUE, C_RED, C_YELLOW, C_GREEN]):
            draw.rectangle(
                [bx0 + idx_c * 60, cy, bx0 + (idx_c + 1) * 60, cy + 5],
                fill=(col[0], col[1], col[2], text_alpha),
            )

        bb = draw.textbbox((0, 0), badge, font=f_badge)
        bw = bb[2] - bb[0]
        draw.text(
            ((WIDTH - bw) // 2, cy + 18),
            badge,
            font=f_badge,
            fill=(accent[0], accent[1], accent[2], text_alpha),
        )

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

        sb = draw.textbbox((0, 0), sub, font=f_sub)
        sw = sb[2] - sb[0]
        draw.text(
            ((WIDTH - sw) // 2, sub_y),
            sub,
            font=f_sub,
            fill=(230, 236, 245, sub_alpha),
        )
    else:
        cx = 76
        card_h = 190 if headline else 130
        cy = HEIGHT - card_h - 62
        bw_l = draw.textbbox((0, 0), badge, font=f_badge)[2]
        hw_l = draw.textbbox((0, 0), headline, font=f_head)[2] if headline else 0
        sw_l = draw.textbbox((0, 0), sub, font=f_sub)[2]
        card_w = min(WIDTH - 152, max(920, max(bw_l, hw_l, sw_l) + 64))

        draw.rounded_rectangle(
            [cx, cy, cx + card_w, cy + card_h],
            radius=20,
            fill=(10, 14, 24, card_alpha),
            outline=(255, 255, 255, int(45 * alpha)),
            width=1,
        )
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
    if f_in_scene >= 6:
        return frame_rgb
    offsets = [(10, -8), (-8, 7), (6, -5), (-5, 4), (3, -2), (-1, 1)]
    dx, dy = offsets[f_in_scene]
    return np.roll(np.roll(frame_rgb, dy, axis=0), dx, axis=1)


def render_fluid_video(lang: str, timings: dict, master_wav: Path, out_mp4: Path):
    print(f"=== Step 4 ({lang.upper()}): Rendering Fluid Zero-Rewind 144s 1080p24 Video -> {out_mp4.name} ===", flush=True)

    ffmpeg_cmd = [
        "/opt/homebrew/bin/ffmpeg", "-y", "-v", "error",
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
        out_dissolve = tdur if (s_idx < NUM_SCENES and ttype == "dissolve" and tdur > 0) else 0
        usable_end = (frames_per_scene - 1) - out_dissolve

        if s_idx > 1:
            prev_meta = SCENES_META[s_idx - 1]
            prev_dissolve = prev_meta["trans_dur"] if prev_meta["trans_type"] == "dissolve" else 0
        else:
            prev_dissolve = 0

        eff_start_trim = cur_trim + prev_dissolve

        for f in range(frames_per_scene):
            if out_dissolve > 0 and f > usable_end:
                frame_a = cur_frames[f]
                frame_a = render_typography_overlay(frame_a, s_idx, f, lang, timings)

                next_frames = get_scene(s_idx + 1)
                next_trim = START_TRIM_FRAMES.get(s_idx + 1, 1)
                k = f - (usable_end + 1)
                frame_b = next_frames[min(len(next_frames) - 1, next_trim + k)]

                p = float(k + 1) / float(out_dissolve + 1)
                w = 0.5 - 0.5 * math.cos(math.pi * p)
                out_frame = cv_blend(frame_a, frame_b, w)
            else:
                base_rgb = sample_scene_monotonic(cur_frames, float(f), eff_start_trim, usable_end)
                if s_idx == 16 and f < 6:
                    base_rgb = apply_screen_shake(base_rgb, f)
                out_frame = render_typography_overlay(base_rgb, s_idx, f, lang, timings)

                if s_idx == 1 and f < 16:
                    w_in = 0.5 - 0.5 * math.cos(math.pi * (f / 16.0))
                    out_frame = (out_frame.astype(np.float32) * w_in).astype(np.uint8)

                if s_idx == NUM_SCENES and f >= frames_per_scene - 24:
                    rem = (frames_per_scene - 1 - f) / 24.0
                    w_out = 0.5 - 0.5 * math.cos(math.pi * max(0.0, rem))
                    out_frame = (out_frame.astype(np.float32) * w_out).astype(np.uint8)

            proc.stdin.write(out_frame.tobytes())

        print(f"  [{lang.upper()}] Rendered Scene {s_idx:02d}/18 ({s_idx*8}s / 144s)", flush=True)

    proc.stdin.close()
    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"ffmpeg exited with code {ret}")
    print(f"  [{lang.upper()}] Successfully exported {out_mp4} ({out_mp4.stat().st_size:,} bytes)", flush=True)


def fmt_srt_time(sec: float) -> str:
    ms = int(round((sec - int(sec)) * 1000))
    s = int(sec) % 60
    m = (int(sec) // 60) % 60
    h = int(sec) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_srt_files(timings: dict):
    for lang, srt_name in [
        ("en", "a_semente_v2_latam_smb_pixar_en.srt"),
        ("ptbr", "a_semente_v2_latam_smb_pixar_ptbr.srt"),
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


def main():
    prepare_base_assets()
    generate_all_new_veo_scenes()
    timings = synthesize_all_narrations()
    generate_srt_files(timings)

    wav_en = build_master_audio("en", timings)
    wav_pt = build_master_audio("ptbr", timings)

    out_en = BASE_DIR / "a_semente_v2_latam_smb_pixar_en.mp4"
    out_pt = BASE_DIR / "a_semente_v2_latam_smb_pixar_ptbr.mp4"
    out_720p_en = BASE_DIR / "a_semente_v2_latam_smb_pixar_720p_backup.mp4"
    out_720p_pt = BASE_DIR / "a_semente_v2_latam_smb_pixar_ptbr_720p_backup.mp4"

    render_fluid_video("en", timings, wav_en, out_en)
    render_fluid_video("ptbr", timings, wav_pt, out_pt)

    for src_mp4, dst_720p in [(out_en, out_720p_en), (out_pt, out_720p_pt)]:
        subprocess.run(
            [
                "/opt/homebrew/bin/ffmpeg", "-y", "-v", "error",
                "-i", str(src_mp4),
                "-vf", "scale=1280:720",
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-c:a", "copy", "-movflags", "+faststart",
                str(dst_720p),
            ],
            check=True,
        )
    print(f"=== COMPLETE! Exported {out_en.name}, {out_pt.name}, {out_720p_en.name}, {out_720p_pt.name} ===", flush=True)


if __name__ == "__main__":
    main()
