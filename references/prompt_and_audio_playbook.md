# Playbook de Prompts (Veo 3.1, Imagen 3, Lyria 3 / Lyria 2 e Chirp 3 HD)

## 1. Anatomia Obrigatória de Prompt para o Veo 3.1 (`veo-3.1-generate-001`)

Todo prompt de cena de 8 segundos deve ser estruturado nos 8 blocos abaixo:

```text
SUBJECT: [Descrição precisa do sujeito, escala e geometria/personagem]
ACTION: [O que acontece nos 8 segundos com progressão clara de 0s a 8s]
CAMERA: [Movimento contínuo — dolly forward, crane up, orbital — nunca zoom out]
LENS: [35mm/50mm/24mm anamorphic 2x ou Pixar cinematic lens, f/2.0, shallow DOF]
LIGHTING: [Luz volumétrica, god rays, direção e evolução cromática]
COLOR: [Paleta explícita — ex: #0D0D0F graphite + Google 4-color accents #4285F4, #EA4335, #FBBC04, #34A853]
AUDIO: [Apenas ambiente e efeitos sonoros diegéticos — nunca voz/narração]
STYLE: [Referência de acabamento — ex: Denis Villeneuve / Fincher ou Pixar Animation Studios RenderMan]
```

### Negative Prompt Padrão (Live-Action / Arquitetural Abstrato)
```text
text, words, letters, numbers, captions, subtitles, watermark, logo, UI elements, distorted faces, extra fingers, deformed hands, warped architecture, cartoon, anime, illustration, oversaturated colors, shaky handheld camera, jump cuts, split screen, zoom out, reverse motion, spoken dialogue, voice over, narration, singing
```

### Negative Prompt Padrão (Animação Estilo Pixar 3D)
```text
text, words, letters, numbers, captions, subtitles, watermark, logo, photorealistic, live action, realistic human skin, uncanny valley, distorted faces, extra fingers, deformed hands, melting geometry, anime, 2D cartoon, cel shading, flat illustration, horror, dark mood, desaturated grade, shaky camera, zoom out, reverse motion, spoken dialogue, voice over, narration, singing
```

---

## 2. Prompts e Endpoints Aprovados para Trilha Sonora no Vertex AI Lyria 3 (`lyria-3-pro-preview` / `lyria-3-clip-preview`) e Lyria 2 (`lyria-002`)

> **Importante:**
> - **Lyria 3 (`lyria-3-pro-preview` para composições completas de ~2 min e `lyria-3-clip-preview` para movimentos de ~30s):** usa o método `:generateContent` no endpoint `global` (`https://aiplatform.googleapis.com/v1beta1/projects/{PROJECT}/locations/global/publishers/google/models/lyria-3-pro-preview:generateContent`) com `"generationConfig": {"responseModalities": ["AUDIO", "TEXT"]}` e retorna o áudio em `candidates[0].content.parts[*].inlineData`.
> - Nunca cite nomes de compositores (`Wagner`, `Hans Zimmer`, `Michael Giacchino`, `Thomas Newman`, `Gustavo Santaolalla`, `John Powell`) ou marcas/títulos protegidos (`Pixar`, `Ride of the Valkyries`) diretamente no prompt, pois o filtro de recitação retorna `HTTP 400`. Descreva a estrutura musical exata:

### Prompt Contínuo de 2 Minutos para `lyria-3-pro-preview` (4 Capítulos Emocionais num Único Take)
```text
Instrumental cinematic orchestral film score, 2 minutes duration, evolving through four emotional chapters: starting with an intimate delicate solo acoustic grand piano and warm nylon-string acoustic guitar with solo cello (0:00 to 0:30), building into warm lush legato string orchestra with gentle marimba and French horns (0:30 to 1:00), expanding into a sweeping heroic symphony orchestra with soaring violin melodies and rich brass (1:00 to 1:35), followed by a glorious triumphant orchestral fanfare celebration that resolves into a peaceful, glowing acoustic grand piano chord at the end. Natural concert hall acoustics, studio master quality, D major, no vocals.
```

### Estilo A: Épico "Cavalgada das Valquírias" (Orquestra em Galope 9/8 + Fanfarra de Metais)
- **Movimento 1 (Abertura):** `"Exciting heroic classical symphony orchestra overture in 9/8 compound meter, rapid galloping staccato string tremolos, rising French horns and bold brass fanfare building thrilling momentum and energy, high dynamic range cinematic film score"`
- **Movimento 2 (Galope Pleno):** `"Rousing triumphant full symphony orchestra in rapid 9/8 gallop, bold heroic dotted-rhythm brass fanfare melody with trumpets, French horns and trombones, driving orchestral timpani and snare rhythm, exhilarating forward momentum"`
- **Movimento 3 (Progressão e Pilares):** `"Powerful epic romantic-era orchestral brass fanfare and driving symphonic gallop, soaring horns and trumpets trading heroic arpeggio motifs, thunderous timpani, energetic staccato strings, unstoppable building power"`
- **Movimento 4 (Clímax Fortissimo):** `"Monumental triumphant orchestral climax in 9/8 meter, blazing full brass section fanfare in fortissimo, crashing orchestral cymbals, thunderous timpani rolls, glorious victorious symphony celebrating a historic achievement"`
- **Movimento 5 (Finale Heroico):** `"Grand heroic orchestral finale, uplifting D major brass fanfare with French horns and trumpets, rapid soaring strings and resonant timpani, inspiring and celebratory symphonic conclusion"`

### Estilo B: Tensão Minimalista Crescente → Clímax Sinfônico (Estilo Thriller Tecnológico)
- **Ato I:** `"Minimalist dark ambient electronic cinematic score, deep sub-bass drone at 60 BPM, sparse solitary piano note in D minor, subtle analog warmth, spacious atmospheric tension, no vocals"`
- **Ato II:** `"Driving cinematic electronic orchestral hybrid score at 90 BPM, rhythmic staccato cello ostinato, warm analog arpeggiator pulse, building momentum and optimism, no vocals"`
- **Ato III:** `"Uplifting modern cinematic hybrid score at 108 BPM, interlocking marimba and string ostinatos, warm brass swells, precise rhythmic pulse representing four pillars of growth, no vocals"`
- **Ato IV:** `"Triumphant full symphony orchestra and modern electronic hybrid climax at 120 BPM in D major, soaring French horns and strings, powerful cinematic percussion, glorious milestone celebration, no vocals"`

### Estilo C: Animação Emocional Estilo Pixar (Piano Íntimo → Cordas Quentes → Orquestra Dourada)
- **Ato I:** `"Intimate emotional animated film score, solo felt piano playing a delicate sparse melody, gentle wind ambience, melancholic yet hopeful, warm acoustic recording, no vocals"`
- **Ato II:** `"Warm heartwarming orchestral animated film score, solo cello joining felt piano, gentle pizzicato strings and acoustic guitar, Latin American folk warmth, growing hope, no vocals"`
- **Ato III:** `"Soaring magical orchestral film score, lush symphonic strings, warm French horns, celesta and woodwinds, golden hour emotional swell, triumphant community celebration, no vocals"`

---

## 3. Vozes Aprovadas para Narração Única (Cloud Text-to-Speech)

Para manter **100% de consistência vocal** em todo o vídeo:
- **Inglês (Grave, Cinematográfica, Imponente):** `en-US-Chirp3-HD-Charon` ou `en-US-Chirp3-HD-Orus`
- **Português Brasil (Grave, Executiva, Contida):** `pt-BR-Chirp3-HD-Charon` ou `pt-BR-Chirp3-HD-Orus`
- **Regra:** Nunca alterne a voz entre cenas. Sintetize com a mesma voz, aplique filtro `highpass=f=65,equalizer=f=130:width_type=o:width=1.2:g=3.5` para encorpar os graves e faça *ducking* suave na trilha musical durante as falas.
