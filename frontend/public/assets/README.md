# Assets folder

## agent-preview.mp4 / agent-preview.gif

Il componente `AgentPreview` (visibile nella sticky card di `/app/agent`) prova
a caricare in questo ordine:

1. `/assets/agent-preview.mp4`  (consigliato — H.264, muted, loop, 6–10s, <2MB, 800×500 circa)
2. `/assets/agent-preview.gif`  (fallback)
3. Mock CSS animato (fallback automatico se nessun file è presente)

### Come registrare la GUI reale

1. Avvia l'agent con `Mode = optimize` così Edge apre la GUI.
2. Registra ~8 secondi in cui:
   - Selezioni un tab (es. Gaming)
   - Spunti 2-3 tweak (mostrando il badge "GIÀ ATTIVO")
   - La progress bar avanza
3. Esporta in H.264 MP4 muted, poi copia il file qui come `agent-preview.mp4`.
   Suggerimenti per ridurre il peso:
   ```
   ffmpeg -i input.mp4 -vf "scale=800:-2,fps=24" -c:v libx264 -crf 28 -pix_fmt yuv420p -an agent-preview.mp4
   ```
