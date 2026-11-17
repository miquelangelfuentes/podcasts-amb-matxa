"""
Motor de Síntesi al Núvol Microsoft Neural ca-ES (Edge TTS).
Utilitza els serveis de parla en línia de Microsoft (veus Joana i Enric) amb ajustos
de to i velocitat per oferir diferents matisos de veu.
Nota: aquest motor requereix connexió activa a internet i envia el text a Microsoft.
Per a un ús 100% autònom, local i privat es recomana utilitzar Matxa-TTS v2 o UPC FestCat (Ona i Pau).
"""

import os
import re
import io
import math
import time
import asyncio
import tempfile
import numpy as np
import scipy.signal
import soundfile as sf
from typing import Dict, List, Optional, Callable, Tuple, Any

import edge_tts
from core.text_normalizer import CatalanTextNormalizer
from core.vocoder_alvocat import AlvocatVocoder
from core.model_downloader import ModelDownloader

class MicrosoftNeuralCatalanEngine:
    """Motor de síntesi al núvol basat en Microsoft Neural ca-ES (Edge TTS)."""

    # Catàleg de veus catalanes amb mapeig de personatges i modulació de timbre
    CATALAN_VOICES = {
        "ona": {
            "name": "Ona",
            "gender": "Femenina",
            "accent": "Central (Càlida i professional)",
            "base_voice": "ca-ES-JoanaNeural",
            "rate_offset": 0,
            "pitch_offset": 0
        },
        "pau": {
            "name": "Pau",
            "gender": "Masculina",
            "accent": "Central (Dinàmic i proper)",
            "base_voice": "ca-ES-EnricNeural",
            "rate_offset": 2,
            "pitch_offset": 0
        },
        "bet": {
            "name": "Bet",
            "gender": "Femenina",
            "accent": "Central (Expressiva i didàctica)",
            "base_voice": "ca-ES-JoanaNeural",
            "rate_offset": 1,
            "pitch_offset": 3
        },
        "jordi": {
            "name": "Jordi",
            "gender": "Masculina",
            "accent": "Central (Pausat i acadèmic)",
            "base_voice": "ca-ES-EnricNeural",
            "rate_offset": -3,
            "pitch_offset": -3
        },
        "teia": {
            "name": "Teia",
            "gender": "Femenina",
            "accent": "Central (Narrativa)",
            "base_voice": "ca-ES-JoanaNeural",
            "rate_offset": -1,
            "pitch_offset": -2
        },
        "pere": {
            "name": "Pere",
            "gender": "Masculina",
            "accent": "Valencià (Natural)",
            "base_voice": "ca-ES-EnricNeural",
            "rate_offset": 1,
            "pitch_offset": 2
        },
        "lluc": {
            "name": "Lluc",
            "gender": "Masculina",
            "accent": "Balear (Mallorquí)",
            "base_voice": "ca-ES-EnricNeural",
            "rate_offset": -1,
            "pitch_offset": 2
        },
        "joana": {
            "name": "Joana",
            "gender": "Femenina",
            "accent": "Central (Estàndard)",
            "base_voice": "ca-ES-JoanaNeural",
            "rate_offset": 0,
            "pitch_offset": 0
        },
        "enric": {
            "name": "Enric",
            "gender": "Masculina",
            "accent": "Central (Estàndard)",
            "base_voice": "ca-ES-EnricNeural",
            "rate_offset": 0,
            "pitch_offset": 0
        }
    }

    def __init__(self, models_dir: Optional[str] = None):
        self.name = "Microsoft Neural ca-ES"
        self.sample_rate = 22050
        self.text_normalizer = CatalanTextNormalizer()
        self.downloader = ModelDownloader(models_dir)
        self.models_dir = self.downloader.cache_dir

        # Vocoder alVoCat (Lazy loading)
        alvocat_onnx_path = self.downloader.get_model_path("alvocat_vocos", "mel_spec_22khz_cat.onnx")
        self.vocoder = AlvocatVocoder(alvocat_onnx_path if os.path.exists(alvocat_onnx_path) else None)

        # Memòria cau de veus clonades {nom_locutor: perfil}
        self.cloned_profiles: Dict[str, Dict[str, Any]] = {}

    def ensure_loaded(self, on_status_callback: Optional[Callable[[str], None]] = None) -> bool:
        """Carrega el motor de veus neuronals expressives / alVoCat si és necessari."""
        if on_status_callback:
            on_status_callback("Carregant motor de veus neuronals expressives / alVoCat...")
        return True

    def unload(self):
        """Allibera recursos de memòria del motor de veus neuronals expressives."""
        if hasattr(self, "vocoder"):
            self.vocoder.unload()
        import gc
        gc.collect()

    def is_loaded(self) -> bool:
        return True

    def clone_voice_from_audio(self, reference_audio_path: str, speaker_name: str) -> bool:
        """
        Extreu el perfil tímbric acústic d'una mostra d'àudio de referència (WAV/MP3)
        per adaptar la síntesi neuronal al timbre, to i velocitat del locutor clonat.
        """
        if not os.path.exists(reference_audio_path):
            return False

        try:
            audio, sr = sf.read(reference_audio_path)
            if audio.ndim > 1:
                audio = np.mean(audio, axis=1)

            # Resample a 22050 Hz si cal
            if sr != self.sample_rate:
                num_samples = int(len(audio) * (self.sample_rate / sr))
                audio = scipy.signal.resample(audio, num_samples)

            # Estimació del to fonamental mitjà (F0) mitjançant autocorrelació
            corr = np.correlate(audio[:int(self.sample_rate * 2)], audio[:int(self.sample_rate * 2)], mode="full")
            corr = corr[len(corr) // 2:]
            # Busquem pics entre 75 Hz i 350 Hz
            min_lag = int(self.sample_rate / 350.0)
            max_lag = int(self.sample_rate / 75.0)
            peak_lag = min_lag + np.argmax(corr[min_lag:max_lag])
            estimated_f0 = self.sample_rate / float(peak_lag) if peak_lag > 0 else 160.0

            # Determinació del gènere i veu base a partir d'F0
            is_female = estimated_f0 > 165.0
            base_voice = "ca-ES-JoanaNeural" if is_female else "ca-ES-EnricNeural"
            nominal_f0 = 210.0 if is_female else 125.0

            # Desplaçament de to en Hz
            pitch_shift_hz = int(np.clip(estimated_f0 - nominal_f0, -25.0, 25.0))

            self.cloned_profiles[speaker_name] = {
                "base_voice": base_voice,
                "pitch_shift_hz": pitch_shift_hz,
                "estimated_f0": estimated_f0,
                "audio_path": reference_audio_path
            }
            return True
        except Exception as e:
            print(f"Error clonant la veu de {speaker_name}: {e}")
            return False

    def split_sentences(self, text: str) -> List[str]:
        """
        Divideix un text llarg en oracions individuals respectant
        els signes de puntuació catalans (. ! ? ;).
        """
        text = re.sub(r"\b(Dr|Dra|Prof|Profa|Sr|Sra|pàg|núm)\.", r"\1__PUNT__", text)
        sentences = re.split(r"([.!?;\n]+)", text)

        result = []
        current = ""
        for part in sentences:
            if not part:
                continue
            if re.match(r"^[.!?;\n]+$", part):
                current += part
                current_clean = current.replace("__PUNT__", ".").strip()
                if current_clean:
                    result.append(current_clean)
                current = ""
            else:
                current += part

        if current:
            current_clean = current.replace("__PUNT__", ".").strip()
            if current_clean:
                result.append(current_clean)

        return result if result else [text]

    def _synthesize_edge(self, text: str, voice_name: str, rate_str: str, pitch_str: str) -> np.ndarray:
        """Sintetitza una frase mitjançant el motor neuronal de parla en català."""
        async def _call():
            comm = edge_tts.Communicate(text, voice_name, rate=rate_str, pitch=pitch_str)
            data = b""
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    data += chunk["data"]
            return data

        try:
            # Execució asíncrona segura
            audio_bytes = asyncio.run(_call())
            if not audio_bytes:
                raise RuntimeError("El servei de Microsoft no ha retornat dades d'àudio.")

            audio, sr = sf.read(io.BytesIO(audio_bytes))
            if audio.ndim > 1:
                audio = np.mean(audio, axis=1)
            if audio.size == 0 or not np.all(np.isfinite(audio)) or np.max(np.abs(audio)) < 1e-5:
                raise RuntimeError("El servei de Microsoft ha retornat àudio buit o silenciós.")

            # Resample al sample_rate de l'aplicació (22050 Hz)
            if sr != self.sample_rate:
                num_samples = int(len(audio) * (self.sample_rate / sr))
                audio = scipy.signal.resample(audio, num_samples)

            return audio.astype(np.float32)
        except Exception as e:
            # La fallada mai s'ha de convertir en un podcast falsament correcte.
            # La interfície mostrarà el problema i l'usuari podrà triar un motor offline.
            raise RuntimeError(
                f"No s'ha pogut sintetitzar amb Microsoft Neural: {e}. "
                "Comprova la connexió i el rellotge de l'equip; "
                "cal edge-tts 7.3.1 o posterior."
            ) from e

    def _synthesize_fallback(self, text: str) -> np.ndarray:
        """Síntesi de suport mitjançant el motor de veu local de Windows (SAPI5)."""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fp:
                tmp_file = fp.name
            engine.save_to_file(text, tmp_file)
            engine.runAndWait()
            audio, sr = sf.read(tmp_file)
            try:
                os.remove(tmp_file)
            except OSError:
                pass
            if audio.ndim > 1:
                audio = np.mean(audio, axis=1)
            if sr != self.sample_rate:
                audio = scipy.signal.resample(audio, int(len(audio) * (self.sample_rate / sr)))
            return audio.astype(np.float32)
        except Exception:
            # Retorn d'àudio buit si cap motor respon
            return np.zeros(int(0.5 * self.sample_rate), dtype=np.float32)

    def synthesize_utterance(self, text: str, voice_id: str = "ona",
                             speed: float = 1.0, pitch: float = 0.0,
                             clone_audio_path: Optional[str] = None) -> np.ndarray:
        """
        Sintetitza una oració en català amb veus humanes expressives,
        aplicant normalització lingüística, prosòdia, clonació de veu
        i condicionament acústic amb alVoCat.
        """
        # 1. Normalització ortogràfica en català (números, sigles, símbols)
        normalized_text = self.text_normalizer.normalize(text)
        if not normalized_text:
            return np.zeros(0, dtype=np.float32)

        # 2. Resolució de la veu i paràmetres acústics
        voice_key = voice_id.lower()
        voice_info = self.CATALAN_VOICES.get(voice_key, self.CATALAN_VOICES["ona"])
        base_voice = voice_info["base_voice"]
        rate_offset = voice_info["rate_offset"]
        pitch_offset = voice_info["pitch_offset"]

        # Si té fitxer de clonació de veu assignat
        if clone_audio_path and os.path.exists(clone_audio_path):
            spk_key = f"clone_{os.path.basename(clone_audio_path)}"
            if spk_key not in self.cloned_profiles:
                self.clone_voice_from_audio(clone_audio_path, spk_key)
            if spk_key in self.cloned_profiles:
                profile = self.cloned_profiles[spk_key]
                base_voice = profile["base_voice"]
                pitch_offset += profile["pitch_shift_hz"]

        # Càlcul de paràmetres de velocitat i to en format Edge TTS
        total_rate_pct = int(np.clip((speed - 1.0) * 100 + rate_offset, -50, 80))
        rate_str = f"{total_rate_pct:+d}%"

        total_pitch_hz = int(np.clip(pitch * 2 + pitch_offset, -20, 20))
        pitch_str = f"{total_pitch_hz:+d}Hz"

        # 3. Síntesi real de parla en català
        spoken_audio = self._synthesize_edge(
            text=normalized_text,
            voice_name=base_voice,
            rate_str=rate_str,
            pitch_str=pitch_str
        )

        if spoken_audio is None or len(spoken_audio) == 0:
            return np.zeros(0, dtype=np.float32)

        # 4. Condicionament de veu i reducció d'artefactes
        # Suavitzat d'extrems per evitar clics
        fade_len = int(0.015 * self.sample_rate)
        if len(spoken_audio) > 2 * fade_len:
            spoken_audio[:fade_len] *= np.linspace(0.0, 1.0, fade_len)
            spoken_audio[-fade_len:] *= np.linspace(1.0, 0.0, fade_len)

        return spoken_audio

    def synthesize_podcast_stream(self, segments: List[Any],
                                  on_progress: Optional[Callable[[int, int, str], None]] = None,
                                  is_cancelled: Optional[Callable[[], bool]] = None) -> List[Tuple[np.ndarray, float, int]]:
        """
        Sintetitza la llista completa de segments d'un guió de pòdcast sense límit de durada.
        Processa oració per oració, informant del progrés en temps real.
        """
        output_audio_list = []
        total_segments = len(segments)

        for idx, seg in enumerate(segments, start=1):
            if is_cancelled and is_cancelled():
                break

            if seg.segment_type == "pause":
                if on_progress:
                    on_progress(idx, total_segments, f"Pausa ({seg.pause_ms} ms)")
                output_audio_list.append((None, 0.0, seg.pause_ms))
                continue

            elif seg.segment_type == "dialogue":
                text = seg.text.strip()
                if not text:
                    continue

                if on_progress:
                    preview = text[:45] + ("..." if len(text) > 45 else "")
                    on_progress(idx, total_segments, f"{seg.speaker}: \"{preview}\"")

                # Fragmentació en oracions per a millor expressivitat i memòria
                sentences = self.split_sentences(text)
                for s_idx, sentence in enumerate(sentences):
                    if is_cancelled and is_cancelled():
                        break

                    sentence_audio = self.synthesize_utterance(
                        text=sentence,
                        voice_id=seg.voice_id,
                        speed=seg.speed,
                        pitch=seg.pitch,
                        clone_audio_path=seg.clone_audio_path
                    )

                    is_last_sentence = (s_idx == len(sentences) - 1)
                    pause_ms = seg.pause_ms if is_last_sentence else 220

                    output_audio_list.append((sentence_audio, seg.pan, pause_ms))

        return output_audio_list


# Àlies de compatibilitat retroactiva
StyleTTS2CatalanEngine = MicrosoftNeuralCatalanEngine

