# Cinematic Video Producer — Skill & Subagent for Antigravity / Gemini CLI

Skill e Subagente especializados em direção, geração, edição e masterização de **vídeos cinematográficos e animações 3D estilo Pixar** (`1920x1080 @ 24fps`) utilizando o ecossistema **Google Cloud Vertex AI**:

- **Vertex AI Veo 3.1 (`veo-3.1-generate-001`)**: Geração de cenas em 1080p nativo com encadeamento contínuo *Text-to-Video* $\rightarrow$ *Image-to-Video* (extraindo o último frame limpo da cena anterior).
- **Vertex AI Imagen 3 (`imagen-3.0-generate-002`)**: Geração de *Character Reference Sheets* para manter a identidade visual de personagens entre cenas.
- **Vertex AI Lyria 3 (`lyria-3-pro-preview` & `lyria-3-clip-preview`)**: Geração de trilhas sonoras sinfônicas contínuas de até 2 minutos em uma única tomada (`lyria-3-pro-preview`) ou movimentos orquestrais dedicados de 30s (`lyria-3-clip-preview`) via endpoint global `:generateContent`.
- **Cloud Text-to-Speech Chirp 3 HD (`Chirp3-HD-Charon` / `Chirp3-HD-Orus`)**: Narração contínua em voz única (EN-US e PT-BR) com **Auditoria Zero-Overflow** (`end_in_scene <= 7.80s` + ajuste automático WSOLA `atempo`).
- **Composição Programática Zero-Rewind (`1920x1080 @ 24fps`)**:
  - Amostragem monotônica contínua de frames (`sample_scene_monotonic` / `build_monotonic_scene_stream`) com corte de frames iniciais congelados (`START_TRIM_FRAMES`), eliminando 100% das travadas ou retrocessos nas transições *cross-dissolve*.
  - *Lookahead Sidechain Ducking* de estúdio (`650ms` hold + `280ms` Gaussian smoothing) para manter a música de fundo fluida entre frases.
  - Tipografia vetorial Google Sans, contadores animados (`easeOutCubic`), *color grading* cinematográfico e legendas sincronizadas (`.srt`).

---

## Estrutura do Repositório

```text
cinematic-video-producer/
├── SKILL.md                                  # Instruções completas da Skill (pipeline em 7 etapas)
├── README.md                                 # Documentação e guia de instalação
├── install.sh                                # Instalador automático para ~/.gemini/config
├── agents/
│   └── video-producer.md                     # Definição do Subagente dedicado (video-producer)
├── references/
│   └── prompt_and_audio_playbook.md          # Playbook de prompts Veo 3.1, Lyria 3 e Chirp 3 HD
├── examples/
│   ├── roteiro-a-semente-latam-smb-v2.md     # Exemplo real: Roteiro Pixar de 18 cenas (2:24) auditado
│   └── build_semente_v2_master.py            # Exemplo real: Motor Pixar v2 bilíngue (PT-BR/EN-US) com auditoria
└── scripts/
    ├── veo_scene_generator.py                # Gerador de cenas Veo 3.1 + encadeamento Image-to-Video
    ├── cinematic_video_engine.py             # Motor Omni para trailers/aberturas com tipografia e SFX
    └── pixar_narrated_video_engine.py        # Motor Pixar completo (Lyria 3 Pro/Clip + Chirp 3 HD + Zero-Rewind)
```

---

## Instalação Rápida

Clone o repositório e execute o script `install.sh`:

```bash
git clone git@github.com:anselmodanilo-gcp/cinematic-video-producer.git
cd cinematic-video-producer
./install.sh
```

Ou instale manualmente copiando os arquivos para o diretório de configuração do Antigravity (`~/.gemini/config`):

```bash
mkdir -p ~/.gemini/config/skills/cinematic-video-producer
cp -R SKILL.md references scripts ~/.gemini/config/skills/cinematic-video-producer/

mkdir -p ~/.gemini/config/agents
cp agents/video-producer.md ~/.gemini/config/agents/video-producer.md
```

---

## Pré-requisitos

1. **Google Cloud SDK (`gcloud`)** autenticado com acesso à API Vertex AI (`aiplatform.googleapis.com`) e Cloud Text-to-Speech (`texttospeech.googleapis.com`).
2. **Python 3.10+** com as bibliotecas:
   ```bash
   pip install numpy pillow scipy requests imageio-ffmpeg
   ```
3. **Fontes (Opcional):** `GoogleSansDisplay-Bold.ttf`, `GoogleSansDisplay-Medium.ttf` ou `HelveticaNeue.ttc` (fallback automático no macOS).
