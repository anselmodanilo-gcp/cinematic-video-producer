---
name: cinematic-video-producer
description: >-
  Cria, dirige, edita e masteriza vídeos cinematográficos e animações estilo Pixar de alta qualidade (1080p, 24fps) combinando Vertex AI Veo 3.1 (Text-to-Video e Image-to-Video contínuo), Imagen 3 (Character Sheet), Lyria 3 / Lyria 2 (trilha orquestral sinfônica contínua via lyria-3-pro-preview e lyria-3-clip-preview), Cloud TTS Chirp 3 HD (narração contínua em voz única com auditoria zero-overflow) e composição estilo Omni (tipografia vetorial, contadores animados, transições fluidas zero-rewind, color grading e masterização multipista). Use sempre que o usuário pedir para criar, editar, narrar ou produzir vídeos, animações, trailers, aberturas de Town Hall ou filmes corporativos/executivos.
---

# Cinematic Video Producer (`cinematic-video-producer`)

Esta skill transforma o agente em um **Diretor de Cinema, Animador e Engenheiro de Pós-Produção** capaz de produzir filmes completos de 1 a 3+ minutos em `1920x1080 @ 24fps` a partir de um roteiro `.md` ou briefing do usuário, salvando cada projeto em pastas numeradas organizadas e entregando 3 versões finais (Master 1080p, Apresentação 1080p 20Mbps e Backup 720p) + roteiro `.md` documentado.

---

## 1. Arquitetura de Produção ("Veo 3.1 + Lyria 3 + Chirp 3 HD + Omni Compositor")

Nunca gere um vídeo tentando colocar texto, números ou narração dentro do Veo. A arquitetura de produção profissional divide o filme em **4 camadas independentes**:

```text
Camada 1: IMAGEN 3 (Opcional) → Gera Character Reference Sheet para consistência de personagem (ex: estilo Pixar)
Camada 2: VEO 3.1 (Vídeo+SFX) → Gera clipes de 8s (1080p, 16:9) apenas com ambiente e efeitos sonoros (sem voz/texto)
Camada 3: ÁUDIO MULTIPASTAS   → Lyria 3 Pro/Clip (orquestra contínua) + Chirp 3 HD (voz única auditada) + SFX Veo
Camada 4: COMPOSITOR OMNI     → Fluxo Monotônico Zero-Rewind + Tipografia Vetorial + Contadores + Grade + Grão 24fps
```

### Regras de Ouro Aprendidas em Produção

1. **Organização em Pastas Numeradas Separadas:**
   - Sempre separe cada vídeo/projeto em uma pasta própria numerada dentro do diretório raiz do projeto (ex.: `01_jornada_v1/`, `02_jornada_google_narrado/`, `03_a_semente_pixar/`, `04_jornada_v2_2B/`, `05_jornada_v2_valquirias/`).
   - Sempre salve o roteiro `.md` correspondente dentro da mesma pasta do vídeo.

2. **Transições 100% Fluidas Sem Retrocesso ou Travamento (`Zero-Rewind Monotonic Stream`):**
   - **Problema clássico a evitar:** Se durante o *dissolve* de saída da Cena $s$ (últimos $t_{len}$ frames) você misturar os frames `0 .. t_len-1` da Cena $s+1$ e depois, no início da Cena $s+1$ (`local_f = 0`), voltar a ler o frame `0` da Cena $s+1$, o vídeo dará um salto para trás ("rewind" de 0.5s–0.8s) ou parecerá travar!
   - **Solução obrigatória (`build_monotonic_scene_stream`):**
     - Corte os frames de inércia inicial/final de clipes gerados por *Image-to-Video* (`SCENE_TRIMS`, tipicamente 4 a 6 frames no início).
     - Gere para cada cena um stream contínuo de exatamente `t_in(s) + 192` frames com interpolação sub-frame linear e um leve *dolly push-in* contínuo (`1.000x → 1.028x`).
     - Durante o *dissolve* de entrada da Cena $s$, consuma os frames `0 .. t_in(s)-1`.
     - Quando a Cena $s$ assumir em `local_f = 0 .. 191`, leia `stream[t_in(s) + local_f]`. Assim o índice avança estritamente `+1` a cada frame do filme inteiro, sem jamais repetir ou retroceder!

3. **Narração Expressiva com Tags de Sentimento, Voz Profunda com Reverb, Estabilidade 100% e Guardião de Volume (`<= 50%` da Voz):**
   - Sempre inclua no `negativePrompt` do Veo: `"spoken dialogue, voice over, narration, singing"`.
   - Gere toda a narração com **uma única voz** (preferencialmente Vertex AI `gemini-2.5-pro-preview-tts` com vozes `Iapetus` ou `Charon`, ou `Chirp3-HD`) mantendo o mesmo timbre do início ao fim.
   - **Tags de Sentimento, Direção Vocal e Pronúncia:** Ao sintetizar com `gemini-2.5-pro-preview-tts`, estruture cada fala com tags explícitas (`[Sentimento: ...] [Voz: ...] [Pronúncia: ...]`) instruindo o modelo a expressar a emoção exata de cada cena sem jamais pronunciar o texto das tags em voz alta, e valide via transcrição rápida (`gemini-2.5-flash`).
   - **Voz Profunda + Reverb Espacial Cinematográfico:** Para narrativas contemplativas/épicas, aplique aprofundamento de formante/pitch (`asetrate=24000*0.918,aresample=48000,atempo=1.0893` + `+4.8dB @ 85Hz`) e **Reverb Espacial Estéreo** (*multi-tap early reflections + late hall tail* filtrada em `2.4kHz`).
   - **Estabilidade Absoluta da Voz + Controle/Verificação de Volume da Trilha (`<= 50%` da Voz):**
     - Nivele todos os segmentos de fala para exatamente o mesmo RMS ativo (`TARGET_VOICE_RMS = 0.200`, `TARGET_VOICE_PEAK = 0.860`), mantendo a voz 100% estável do início ao fim.
     - Normalize a trilha sonora por janela deslizante de RMS (para evitar que crescendos orquestrais ou de órgão aumentem demais o volume) e aplique um **verificador/limitador automático (`enforce_and_verify_50pct_volume_guard`)** que garanta e audite cena a cena que **a trilha sonora + efeitos nunca ultrapassem 50% (`-6 dB`) do volume da voz** (tanto em RMS quanto em pico).
   - **Auditoria de Duração por Cena (Zero Desincronia):** Cada clipe de narração (após remoção de silêncio inicial/final) deve caber com folga dentro da janela da cena. Caso uma frase longa passe do limite, aplique ajuste WSOLA preservando o tom (`ffmpeg -af atempo=...`) para que nenhuma fala jamais invada a cena seguinte.
   - **Lookahead Sidechain Ducking sem Bombeamento ("Zero Pumping"):** Use janela de retenção (`maximum_filter1d` de `650ms`) seguida de suavização Gaussiana (`gaussian_filter1d` com `sigma = 280ms`) sobre o envelope de voz antes de atenuar a trilha musical. Isso impede que a música oscile de volume entre sílabas ou pausas curtas de respiração.

4. **Trilha Sonora Profissional com Vertex AI Lyria 3 (`lyria-3-pro-preview` e `lyria-3-clip-preview`) e Lyria 2 (`lyria-002`):**
   - **Lyria 3 Pro (`lyria-3-pro-preview`) — Composição Contínua Multi-Minuto:**
     - Endpoint oficial: `https://aiplatform.googleapis.com/v1beta1/projects/{PROJECT}/locations/global/publishers/google/models/lyria-3-pro-preview:generateContent` com `"generationConfig": {"responseModalities": ["AUDIO", "TEXT"]}`.
     - Gera uma sinfonia contínua completa (~2 minutos em uma única tomada, sem emendas!) evoluindo por múltiplos atos (ex.: piano acústico íntimo `0:00–0:30` → cordas quentes `0:30–1:00` → orquestra completa `1:00–1:35` → fanfarra triunfal e resolução de piano no final).
   - **Lyria 3 Clip (`lyria-3-clip-preview`) — Movimentos Dedicados de 30s:**
     - Endpoint oficial: `https://aiplatform.googleapis.com/v1beta1/projects/{PROJECT}/locations/global/publishers/google/models/lyria-3-clip-preview:generateContent` com `"generationConfig": {"responseModalities": ["AUDIO", "TEXT"]}`.
     - Ideal para explodir em fanfarra orquestral logo após o silêncio dramático de 1,0s do clímax e fazer *crossfade* em potência constante (`sin/cos` de `4.5s`) de volta para a resolução final do `lyria-3-pro-preview`.
   - **Regra Anti-Bloqueio de Filtro (Lyria 3 e Lyria 2):**
     - Nunca cite nomes próprios de compositores (`Wagner`, `Thomas Newman`, `Gustavo Santaolalla`, `John Powell`, `Hans Zimmer`) ou marcas/títulos protegidos (`Pixar`, `Ride of the Valkyries`), pois o filtro retorna `HTTP 400`. Traduza sempre o estilo pedido para descritores musicais técnicos (instrumentação, andamento BPM, compasso, tonalidade e dinâmica).

5. **Continuidade Espacial (Image-to-Video) e Consistência de Personagem:**
   - Para planos-sequência onde a Cena $s+1$ continua a Cena $s$, extraia o último frame limpo da Cena $s$ (ex.: `t = 7.85s`) e passe no campo `"image": {"bytesBase64Encoded": ..., "mimeType": "image/jpeg"}` do Veo 3.1.
   - Para animações com personagem recorrente (ex.: estilo Pixar), gere primeiro uma folha de referência (*Character Reference Sheet*) com o **Imagen 3 (`imagen-3.0-generate-002`)**, recorte o painel frontal/3-quartos e use como imagem âncora com a mesma `seed` nas cenas iniciais, encadeando o último frame nas cenas contínuas.

6. **Silêncio Dramático antes do Clímax:**
   - Antes do grande número ou revelação (ex.: o segundo `1:51–1:52` antes do contador explodir em `$1,101.1M`), zere todas as pistas de áudio (trilha + SFX) por exatamente **1,0 segundo (24 frames)** com rampa anti-clique de 30ms. O contraste torna o impacto do clímax memorável.

---

## 2. Passo a Passo de Execução

1. **Estruturar a Pasta do Projeto e o Roteiro `.md`:**
   - Crie uma pasta numerada dedicada para o vídeo (ex.: `<diretorio_base>/<NN>_<slug_do_video>/`).
   - Salve o roteiro completo em Markdown (`.md`) dentro da pasta com tabela de linha do tempo factual, identidade visual, configuração do Veo 3.1, prompts cena a cena (`SUBJECT`, `ACTION`, `CAMERA`, `LENS`, `LIGHTING`, `COLOR`, `AUDIO`, `STYLE`), camada de tipografia e mapa de pós-produção.

2. **Executar o Motor de Geração e Pós-Produção:**
   - Use como base o script modular [cinematic_video_engine.py](./scripts/cinematic_video_engine.py) e o guia de prompts [prompt_and_audio_playbook.md](./references/prompt_and_audio_playbook.md).
   - Se o usuário permitir reaproveitar clipes de uma versão anterior, copie os clipes compatíveis para `clips/` e gere no Veo 3.1 apenas as cenas novas ou alteradas (economizando tempo e mantendo continuidade).

3. **Gerar as 3 Entregas Finais + Verificação:**
   - Sempre exporte:
     1. `*_master_1080p.mp4` (`CRF 14`, `1920x1080`, `24fps`, áudio `AAC 320kbps 48kHz`)
     2. `*_20mbps_1080p.mp4` (`20 Mbps CBR/VBR`, ideal para Town Hall / auditório)
     3. `*_720p_backup.mp4` (`1280x720`, leve para Google Meet / Slides / WhatsApp)
   - Verifique com `ls -lh` e `ffprobe` se a duração exata (ex.: `120.0s` ou `144.0s`) e as streams de vídeo e áudio estão íntegras.
