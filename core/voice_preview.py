"""
Gestor de Mostres de Veu (Voice Preview Manager).
Sintetitza i emmagatzema en memòria cau fragments breus d'àudio per a cada veu
catalana (Matxa-TTS, UPC FestCat Ona i Pau i veus neuronals) per permetre l'escolta prèvia a la interfície.
"""

import os
import re
import sys
import time
import tempfile
import threading
import soundfile as sf
import numpy as np

try:
    if sys.platform == "win32":
        import winsound
        HAS_WINSOUND = True
    else:
        HAS_WINSOUND = False
except ImportError:
    HAS_WINSOUND = False

try:
    import pygame
    HAS_PYGAME = True
except ImportError:
    HAS_PYGAME = False


class VoicePreviewManager:
    """Gestiona la generació, emmagatzematge en cau i reproducció de mostres de veu."""

    # Frases de mostra personalitzades per a cada veu (concises, naturals i ràpides de generar)
    VOICE_SAMPLE_PHRASES = {
        # Matxa-TTS Central
        "elia": "Hola, soc l'Èlia. Aquesta és la meva veu en català central.",
        "grau": "Hola, soc en Grau. Aquesta és la meva veu en català central.",
        "ona": "Hola, soc l'Ona. Aquesta és la meva veu en català central.",
        "pau": "Hola, soc en Pau. Aquesta és la meva veu en català central.",
        # Matxa-TTS Balear
        "olga": "Hola, soc s'Olga. Aquesta és sa meva veu en català balear.",
        "quim": "Hola, soc en Quim. Aquesta és sa meva veu en català balear.",
        "bm": "Hola, soc en Bernat. Aquesta és sa meva veu en català balear.",
        # Matxa-TTS Valencià
        "gina": "Hola, soc Gina. Aquesta és la meua veu en català valencià.",
        "lluc": "Hola, soc Lluc. Aquesta és la meua veu en català valencià.",
        "arnau": "Hola, soc Arnau. Aquesta és la meua veu en català valencià.",
        "berta": "Hola, soc Berta. Aquesta és la meua veu en català valencià.",
        # Matxa-TTS Nord-occidental
        "emma": "Hola, soc l'Emma. Aquesta és la meva veu en català nord-occidental.",
        "pere": "Hola, soc en Pere. Aquesta és la meva veu en català nord-occidental.",
        "estel": "Hola, soc l'Estel. Aquesta és la meva veu en català nord-occidental.",
        # Matxa-TTS Septentrional
        "laura": "Hola, soc la Laura. Aquesta és la meva veu en català septentrional.",
        "jordi": "Hola, soc en Jordi. Aquesta és la meva veu en català septentrional de Perpinyà.",
        # Veus neuronals online
        "bet": "Hola, soc la Bet. Aquesta és la meva veu en català per als vostres pòdcasts.",
        "teia": "Hola, soc la Teia. Aquesta és la meva veu narrativa en català.",
        "joana": "Hola, soc la Joana. Aquesta és la meva veu estàndard en català.",
        "enric": "Hola, soc l'Enric. Aquesta és la meva veu masculina en català.",
        # UPC FestCat
        "upc_ona": "Hola, soc l'Ona. Aquesta és la meva veu neuronal de la UPC en català.",
        "upc_pau": "Hola, soc en Pau. Aquesta és la meva veu neuronal de la UPC en català."
    }

    GENERIC_SAMPLE = "Hola, aquesta és una mostra de la meva veu en català per al pòdcast."
    CACHE_VERSION = "v7_neural_preview_fix"

    def __init__(self, cache_dir: str = None):
        if cache_dir:
            self.cache_dir = cache_dir
        else:
            self.cache_dir = os.path.join(tempfile.gettempdir(), "podcasts_matxa_voice_previews")
        os.makedirs(self.cache_dir, exist_ok=True)

        self._check_cache_version()

        self._current_sound = None
        self._is_playing = False

        if HAS_PYGAME and not pygame.mixer.get_init():
            try:
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=1024)
            except Exception as e:
                print(f"Avís: no s'ha pogut inicialitzar pygame.mixer a VoicePreviewManager: {e}")

    def _check_cache_version(self):
        """Invalida i neteja mostres de veu obsoletes o amb artefactes de versions anteriors."""
        v_file = os.path.join(self.cache_dir, "cache_version.txt")
        current_v = ""
        if os.path.exists(v_file):
            try:
                with open(v_file, "r", encoding="utf-8") as f:
                    current_v = f.read().strip()
            except Exception:
                pass

        if current_v != self.CACHE_VERSION:
            self.clear_cache()
            try:
                with open(v_file, "w", encoding="utf-8") as f:
                    f.write(self.CACHE_VERSION)
            except Exception:
                pass

    def clear_cache(self):
        """Elimina els fitxers WAV temporals de mostra de veu."""
        try:
            for item in os.listdir(self.cache_dir):
                if item.startswith("preview_") and item.endswith(".wav"):
                    try:
                        os.remove(os.path.join(self.cache_dir, item))
                    except Exception:
                        pass
        except Exception:
            pass

    def get_sample_phrase(self, voice_id: str, engine_name: str = "") -> str:
        """Retorna la frase de mostra per a un identificador de veu."""
        v_key = voice_id.lower().strip()
        if "upc" in engine_name.lower():
            if v_key in ("pau", "upc_pau"):
                return "Hola, soc en Pau. Aquesta és la meva veu neuronal de la UPC en català."
            if v_key in ("ona", "upc_ona"):
                return "Hola, soc l'Ona. Aquesta és la meva veu neuronal de la UPC en català."
        return self.VOICE_SAMPLE_PHRASES.get(v_key, self.GENERIC_SAMPLE)

    def get_cached_path(self, engine_name: str, voice_id: str) -> str:
        """Retorna la mostra preenregistrada abans d'intentar sintetitzar-la."""
        safe_engine = re.sub(r'[^a-zA-Z0-9_]', '_', engine_name).lower()
        safe_voice = re.sub(r'[^a-zA-Z0-9_]', '_', voice_id).lower()
        filename = f"preview_{safe_engine}_{safe_voice}.wav"
        filenames = [filename, f"preview_{safe_voice}.wav"]

        # El motor abans s'anomenava StyleTTS 2. Conservem les mostres
        # existents, també per a Joana i Enric, que funcionen sense xarxa.
        if any(alias in safe_engine for alias in ("microsoft", "neural", "styletts")):
            filenames.append(f"preview_styletts_2_{safe_voice}.wav")

        if "upc" in safe_engine or "upc" in safe_voice:
            filenames.extend([
                f"preview_upc_{safe_voice}.wav",
                f"preview_upc_ona_festcat_{safe_voice}.wav",
                f"preview_upc_festcat_{safe_voice}.wav",
            ])

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        roots = [os.path.join(base_dir, "assets", "previews")]
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            roots.insert(0, os.path.join(bundle_dir, "assets", "previews"))
        if getattr(sys, "frozen", False) and getattr(sys, "executable", None):
            exe_dir = os.path.dirname(sys.executable)
            roots.extend([
                os.path.join(exe_dir, "_internal", "assets", "previews"),
                os.path.join(exe_dir, "assets", "previews"),
            ])

        for root in roots:
            for name in filenames:
                candidate = os.path.join(root, name)
                if os.path.isfile(candidate) and os.path.getsize(candidate) > 1000:
                    return candidate

        # Nom canònic utilitzat per a mostres sintetitzades i desa-les al cau.
        return os.path.join(self.cache_dir, filename)

    def is_cached(self, engine_name: str, voice_id: str) -> bool:
        """Comprova si la mostra ja està disponible (al paquet o en memòria cau)."""
        path = self.get_cached_path(engine_name, voice_id)
        return os.path.exists(path) and os.path.getsize(path) > 1000

    def play_preview(self, engine, voice_id: str,
                     on_start: callable = None,
                     on_complete: callable = None,
                     on_error: callable = None):
        """
        Sintetitza (si cal) i reprodueix la mostra de veu en un fil secundari
        sense bloquejar la interfície gràfica d'usuari.
        """
        def _worker():
            try:
                engine_name = getattr(engine, "name", "matxa")
                cache_path = self.get_cached_path(engine_name, voice_id)

                if not self.is_cached(engine_name, voice_id):
                    # Assegurem que s'escriu al directori de cau d'usuari
                    safe_engine = re.sub(r'[^a-zA-Z0-9_]', '_', engine_name).lower()
                    safe_voice = re.sub(r'[^a-zA-Z0-9_]', '_', voice_id).lower()
                    filename = f"preview_{safe_engine}_{safe_voice}.wav"
                    cache_path = os.path.join(self.cache_dir, filename)

                    phrase = self.get_sample_phrase(voice_id, engine_name=engine_name)
                    # Assegurar que el motor està llest
                    if hasattr(engine, "ensure_loaded"):
                        try:
                            engine.ensure_loaded(voice_id=voice_id)
                        except TypeError:
                            engine.ensure_loaded()

                    sample_rate = getattr(engine, "sample_rate", 22050)

                    # Sintetitzar frase directa en una sola passada ràpida
                    audio_data = engine.synthesize_utterance(phrase, voice_id=voice_id)

                    if audio_data is None or len(audio_data) == 0:
                        raise RuntimeError("La síntesi de mostra ha retornat un àudio buit.")
                    audio_data = np.asarray(audio_data, dtype=np.float32)
                    if not np.all(np.isfinite(audio_data)) or np.max(np.abs(audio_data)) < 1e-5:
                        raise RuntimeError(
                            "La síntesi ha retornat una mostra silenciosa o invàlida. "
                            "Comprova el motor de veu i torna-ho a provar."
                        )

                    # Desarem en 16-bit PCM WAV per a compatibilitat total
                    max_amp = np.max(np.abs(audio_data))
                    if max_amp > 0:
                        audio_data = (audio_data / max_amp) * 0.90
                    sf.write(cache_path, audio_data, sample_rate, subtype="PCM_16")

                # Càlcul de durada del fitxer d'àudio
                duration = 2.0
                try:
                    info = sf.info(cache_path)
                    duration = max(0.5, float(info.duration))
                except Exception:
                    pass

                # Notificar inici
                if on_start:
                    try:
                        on_start()
                    except Exception as err:
                        print(f"Avís al callback on_start: {err}")

                # Reproduir àudio
                if HAS_WINSOUND:
                    self.stop()
                    # SND_FILENAME | SND_ASYNC (reproducció nativa Windows en segon pla)
                    winsound.PlaySound(cache_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                    time.sleep(duration + 0.15)
                    if on_complete:
                        try:
                            on_complete()
                        except Exception as err:
                            print(f"Avís al callback on_complete: {err}")
                elif HAS_PYGAME:
                    self.stop()
                    sound = pygame.mixer.Sound(cache_path)
                    channel = sound.play()
                    self._current_sound = sound

                    if channel:
                        while channel.get_busy():
                            time.sleep(0.05)

                    if on_complete:
                        try:
                            on_complete()
                        except Exception as err:
                            print(f"Avís al callback on_complete: {err}")
                else:
                    time.sleep(duration)
                    if on_complete:
                        try:
                            on_complete()
                        except Exception as err:
                            print(f"Avís al callback on_complete: {err}")

            except Exception as e:
                print(f"Error reproduint mostra per a la veu '{voice_id}': {e}")
                if on_error:
                    try:
                        on_error(str(e))
                    except Exception:
                        pass
                elif on_complete:
                    try:
                        on_complete()
                    except Exception:
                        pass

        threading.Thread(target=_worker, daemon=True).start()

    def stop(self):
        """Atura qualsevol mostra de veu en reproducció."""
        if HAS_WINSOUND:
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
        if HAS_PYGAME and self._current_sound:
            try:
                self._current_sound.stop()
            except Exception:
                pass
            self._current_sound = None
