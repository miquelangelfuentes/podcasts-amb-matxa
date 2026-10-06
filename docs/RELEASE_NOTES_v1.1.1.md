# Pòdcasts amb Matxa v1.1.1 🎙️🍵

> **Versió 1.1.1 — Actualització de refinament acústic, control de velocitat i auto-ducking**  
> Data de publicació: 6 d'octubre de 2026  
> Repositori oficial: [github.com/miquelangelfuentes/podcasts-amb-estil-i-matxa](https://github.com/miquelangelfuentes/podcasts-amb-estil-i-matxa)

---

### ✨ Novetats destacades de la versió 1.1.1

- **Atenuació vocal automàtica (Auto-ducking intel·ligent)**:
  - Sistema automàtic basat en mesurament d'energia vocal RMS (-12 dB) que rebaixa la música de fons de manera transparent mentre parla qualsevol veu i la restaura suaument a les pauses.
  - Inclou un interruptor visual dedicat «📉 Auto-ducking» a la interfície d'usuari (activat per defecte).
- **Selector ràpid de velocitat per veu (0.8x a 1.2x)**:
  - Cada locutor disposa ara d'un selector de píndola (`PillSelector`) a la seva targeta per ajustar la cadència de parla (`0.8x`, `0.9x`, `1.0x (Normal)`, `1.1x` i `1.2x`).
  - S'aplica directament als models locals Matxa-TTS v2 (`length_scale`), UPC FestCat Piper i a les veus neuronals del núvol.
- **Aturada instantània de reproducció i gestió d'àudio**:
  - El botó «■ Atura» atura immediatament qualsevol pista d'àudio de fons en reproducció i allibera la memòria del mesclador.
  - El volum es pot regular en temps real sense haver de reiniciar la pista.
- **Identificació de versió**:
  - Número de versió `v1.1.1` visible tant a la barra de títol de la finestra com al distintiu de la capçalera principal.
  - Paquet oficial per a Windows: `PodcastsAmbMatxa-v1.1.1-Windows.zip`.

---

### 📥 Descàrrega directa per a Windows

👉 **[Descarregar PodcastsAmbMatxa v1.1.1 per a Windows (.zip)](https://github.com/miquelangelfuentes/podcasts-amb-estil-i-matxa/releases/download/v1.1.1/PodcastsAmbMatxa-v1.1.1-Windows.zip)** (~402 MB)

---

### 🛠️ Resum tècnic de canvis

- `ui/version_check_modal.py`: actualitzat `APP_VERSION = "1.1.1"`.
- `ui/main_window.py`: integrat `PillSelector` de velocitat per a cada locutor, parada nàtiva del reproductor amb Pygame i gestió de volum dinàmic.
- `core/audio_processor.py`: algorisme d'auto-ducking amb interpolació suau d'atac i caiguda (*cross-fade*).
- `test_features.py`: 10 de 10 proves superades amb èxit validant la nova versió 1.1.1.
