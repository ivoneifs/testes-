# Vídeo de apresentação (static/video/neuroscore-apresentacao.mp4)

1. Narração: `roteiro.json` (7 falas), gerada com OpenAI TTS (`gpt-4o-mini-tts`, voz `nova`), uma fala por cena.
2. Tempos: `timing.json` = duração de cada fala + 0,7 s (`start`, `dur`, `audio_at`).
3. Quadros: `python render.py <pasta>` (Pillow, 1280×720, 24 fps; fontes Space Grotesk/Inter em `<pasta>/fonts`).
   Rodar dentro da imagem do app (já tem Pillow): `docker run --rm -v <pasta>:/w --entrypoint python <imagem> /w/render.py /w`.
4. Áudio: narração com `adelay` em `audio_at` + acorde sintetizado bem baixo (sem música de terceiros) → `trilha.m4a`.
5. `ffmpeg -framerate 24 -i frames/%05d.jpg -i trilha.m4a -c:v libx264 -crf 23 -pix_fmt yuv420p -movflags +faststart`.
