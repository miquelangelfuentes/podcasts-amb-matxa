"""
Mòdul de Processament i Masterització d'Àudio (Audio Processor).
Gestiona l'encadenament per blocs, cross-fades, espacialització estèreo (panning),
normalització de sonoritat (estàndard EBU R128 per a pòdcasts) i
exportació a MP3 estèreo a 160 kbps mitjançant FFmpeg integrat.
"""

import os
import math
import subprocess
import tempfile
import numpy as np
import scipy.signal
import soundfile as sf
from typing import List, Tuple, Optional, Union
import imageio_ffmpeg

class AudioProcessor:
    """Motor de processament d'àudio i masterització de pòdcast."""

    def __init__(self, sample_rate: int = 22050):
        self.sample_rate = sample_rate
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    def generate_silence(self, duration_ms: int) -> np.ndarray:
        """
        Genera silenci digital pur (zeros absoluts) entre frases.
        """
        num_samples = int((duration_ms / 1000.0) * self.sample_rate)
        if num_samples <= 0:
            return np.zeros(0, dtype=np.float32)
        return np.zeros(num_samples, dtype=np.float32)

    def apply_pan(self, mono_audio: np.ndarray, pan: float = 0.0) -> np.ndarray:
        """
        Aplica llei de panoràmica d'energia constant (Constant Power Panning Law).
        pan: -1.0 (esquerra pura) a +1.0 (dreta pura). 0.0 és centre.
        Retorna array estèreo (2, num_samples).
        """
        if mono_audio.ndim > 1:
            mono_audio = np.mean(mono_audio, axis=0)

        pan = max(-1.0, min(1.0, float(pan)))
        angle = (pan + 1.0) * (np.pi / 4.0) # 0 a pi/2

        gain_left = float(np.cos(angle))
        gain_right = float(np.sin(angle))

        left_ch = mono_audio * gain_left
        right_ch = mono_audio * gain_right

        return np.vstack([left_ch, right_ch])

    def crossfade_segments(self, seg1: np.ndarray, seg2: np.ndarray, fade_ms: int = 15) -> np.ndarray:
        """
        Encadena dos segments estèreo (2, N) aplicant un cross-fade suau
        per eliminar espetecs de fase a les unions.
        """
        fade_samples = int((fade_ms / 1000.0) * self.sample_rate)
        if seg1.shape[1] < fade_samples or seg2.shape[1] < fade_samples or fade_samples <= 0:
            return np.concatenate([seg1, seg2], axis=1)

        fade_out = np.linspace(1.0, 0.0, fade_samples, dtype=np.float32)
        fade_in = np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)

        # Aplicació del crossfade a la zona encavalcada
        overlap = seg1[:, -fade_samples:] * fade_out + seg2[:, :fade_samples] * fade_in

        stitched = np.concatenate([
            seg1[:, :-fade_samples],
            overlap,
            seg2[:, fade_samples:]
        ], axis=1)

        return stitched

    def normalize_loudness(self, stereo_audio: np.ndarray, target_lufs: float = -16.0, max_peak_db: float = -1.0) -> np.ndarray:
        """
        Normalitza la sonoritat aproximant l'estàndard EBU R128 (-16 LUFS per a pòdcasts)
        amb sostre de pic màxim (True Peak) a -1.0 dBTP per evitar distorsió en codificar a MP3.
        """
        if stereo_audio.size == 0:
            return stereo_audio

        # Càlcul de potència RMS ponderada
        rms = np.sqrt(np.mean(stereo_audio ** 2) + 1e-9)
        current_lufs = 20.0 * np.log10(rms + 1e-9) - 0.691

        gain_db = target_lufs - current_lufs
        # Limitem el guany màxim per evitar amplificar sorolls en audios molt fluixos
        gain_db = max(-18.0, min(18.0, gain_db))
        gain_linear = 10.0 ** (gain_db / 20.0)

        normalized = stereo_audio * gain_linear

        # Limitador de pic
        peak_limit = 10.0 ** (max_peak_db / 20.0)
        current_peak = np.max(np.abs(normalized))
        if current_peak > peak_limit:
            normalized = normalized * (peak_limit / current_peak)

        return normalized.astype(np.float32)

    def assemble_podcast(self, audio_segments: List[Tuple[np.ndarray, float, int]]) -> np.ndarray:
        """
        Acobla una seqüència de segments d'àudio (mono_audio, pan, pause_after_ms)
        en un únic senyal estèreo final sense cap soroll romanent inicial.
        """
        combined = np.zeros((2, 0), dtype=np.float32)

        for idx, (mono_chunk, pan, pause_ms) in enumerate(audio_segments):
            if mono_chunk is not None and len(mono_chunk) > 0:
                # 1. Eliminació de qualsevol component continu (DC offset) del model acústic
                mono_chunk = mono_chunk - np.mean(mono_chunk)

                # 2. Finestra d'esvaïment suau (micro fade-in / fade-out de 8ms) per evitar espetecs
                fade_len = int(0.008 * self.sample_rate)
                if len(mono_chunk) > 2 * fade_len:
                    fade_in = 0.5 * (1.0 - np.cos(np.pi * np.linspace(0, 1, fade_len, dtype=np.float32)))
                    fade_out = 0.5 * (1.0 + np.cos(np.pi * np.linspace(0, 1, fade_len, dtype=np.float32)))
                    mono_chunk[:fade_len] *= fade_in
                    mono_chunk[-fade_len:] *= fade_out

                stereo_chunk = self.apply_pan(mono_chunk, pan)

                if combined.shape[1] == 0:
                    # Afegim 60 ms de silenci net al començament absolut del podcast
                    initial_clean_silence = np.zeros((2, int(0.06 * self.sample_rate)), dtype=np.float32)
                    combined = np.concatenate([initial_clean_silence, stereo_chunk], axis=1)
                else:
                    combined = self.crossfade_segments(combined, stereo_chunk, fade_ms=10)

            # Inserció de pauses naturals (silenci pur, sense sorolls de sala artificials)
            if pause_ms > 0:
                silence_mono = self.generate_silence(pause_ms)
                silence_stereo = self.apply_pan(silence_mono, pan=0.0)
                if combined.shape[1] == 0:
                    combined = silence_stereo
                else:
                    combined = np.concatenate([combined, silence_stereo], axis=1)

        # Masterització final de sonoritat (-16 LUFS)
        final_mastered = self.normalize_loudness(combined, target_lufs=-16.0, max_peak_db=-1.0)
        return final_mastered

    def export_mp3(self, stereo_audio: np.ndarray, output_path: str, title: str = "Pòdcast amb Matxa",
                   artist: str = "Pòdcasts amb Matxa · BSC-LT & alVoCat") -> str:
        """
        Exporta l'àudio estèreo a format MP3 a 160 kbps CBR mitjançant FFmpeg.
        (160 kbps és el màxim estàndard ISO MPEG-2 Layer 3 per a la freqüència de 22.05 kHz).
        Inclou metadades ID3 i conversió directa d'alta qualitat.
        """
        output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Creem un fitxer temporal WAV per passar-lo a FFmpeg
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            tmp_wav_path = tmp_wav.name

        try:
            # Transposem a (num_samples, 2) per a soundfile
            sf_audio = stereo_audio.T
            sf.write(tmp_wav_path, sf_audio, self.sample_rate, subtype="FLOAT")

            # Ordre FFmpeg per a MP3 160kbps estèreo constant bit-rate
            cmd = [
                self.ffmpeg_exe,
                "-y",
                "-i", tmp_wav_path,
                "-vn",
                "-ar", str(self.sample_rate if self.sample_rate in (44100, 48000, 22050) else 44100),
                "-ac", "2",
                "-b:a", "160k",
                "-c:a", "libmp3lame",
                "-metadata", f"title={title}",
                "-metadata", f"artist={artist}",
                "-metadata", "album=Pòdcasts Educatius en Català",
                "-metadata", "genre=Podcast / Educació",
                output_path
            ]

            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Error a FFmpeg al codificar MP3: {result.stderr}")

            return output_path
        finally:
            if os.path.exists(tmp_wav_path):
                try:
                    os.remove(tmp_wav_path)
                except OSError:
                    pass

    def load_audio_file(self, file_path: str, target_sr: Optional[int] = None) -> np.ndarray:
        """
        Carrega un fitxer d'àudio (MP3, WAV, OGG, FLAC, M4A...) i el retorna com a array
        numpy estèreo de forma (2, N) i dtype float32 re-mostrejat a target_sr (per defecte self.sample_rate).
        Utilitza soundfile per defecte i recorre a FFmpeg si el format conté etiquetes complexes.
        """
        if target_sr is None:
            target_sr = self.sample_rate

        file_path = os.path.abspath(file_path)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"No s'ha trobat el fitxer d'àudio: {file_path}")

        data = None
        orig_sr = None

        # 1. Intent de lectura directa mitjançant soundfile
        try:
            data, orig_sr = sf.read(file_path, dtype="float32")
        except Exception:
            # 2. Descodificació de seguretat mitjançant FFmpeg integrat
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
                tmp_wav_path = tmp_wav.name
            try:
                cmd = [
                    self.ffmpeg_exe,
                    "-y",
                    "-i", file_path,
                    "-vn",
                    "-ac", "2",
                    "-ar", str(target_sr),
                    "-f", "wav",
                    tmp_wav_path
                ]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if res.returncode == 0 and os.path.exists(tmp_wav_path):
                    data, orig_sr = sf.read(tmp_wav_path, dtype="float32")
            finally:
                if os.path.exists(tmp_wav_path):
                    try:
                        os.remove(tmp_wav_path)
                    except OSError:
                        pass

        if data is None or orig_sr is None:
            raise RuntimeError(f"No s'ha pogut descodificar el fitxer d'àudio: {file_path}")

        # 3. Normalitzem la forma a estèreo de 2 canals: (2, N)
        if data.ndim == 1:
            stereo = np.vstack([data, data])
        elif data.ndim == 2:
            if data.shape[1] == 2:
                stereo = data.T
            elif data.shape[0] == 2:
                stereo = data
            elif data.shape[1] == 1:
                mono = data[:, 0]
                stereo = np.vstack([mono, mono])
            else:
                stereo = data[:, :2].T
        else:
            flat = data.flatten()
            stereo = np.vstack([flat, flat])

        # 4. Re-mostreig d'alta qualitat polifàsic si cal
        if orig_sr != target_sr and stereo.shape[1] > 0:
            gcd = math.gcd(orig_sr, target_sr)
            up = target_sr // gcd
            down = orig_sr // gcd
            stereo = scipy.signal.resample_poly(stereo, up, down, axis=1).astype(np.float32)

        return stereo.astype(np.float32)

    def mix_background_track(
        self,
        voice_audio: np.ndarray,
        bg_audio: Union[str, np.ndarray],
        volume: float = 0.15,
        loop: bool = True,
        fade_in_sec: float = 1.0,
        fade_out_sec: float = 2.0,
        ducking: bool = True,
        duck_threshold_db: float = -42.0,
        duck_reduction_db: float = 12.0,
        duck_attack_ms: float = 120.0,
        duck_release_ms: float = 650.0
    ) -> np.ndarray:
        """
        Mescla una pista de música o ambient de fons sota la locució del pòdcast.
        - voice_audio: Senyal estèreo principal (2, N) a self.sample_rate.
        - bg_audio: Ruta al fitxer d'àudio (MP3/WAV/etc.) o array estèreo (2, L).
        - volume: Factor de volum de fons (0.0 a 1.0, típicament 0.10 - 0.20 quan parla).
        - loop: Si és True i la pista és més curta que el pòdcast, es repeteix en bucle amb cross-fade de 20 ms.
        - fade_in_sec / fade_out_sec: Durada dels esvaïments suaus d'entrada i sortida de la música.
        - ducking: Si és True, aplica auto-ducking intel·ligent: la música sona al volum complet
          durant silencis o pauses i s'atenua dinàmicament (-12 dB) mentre hi ha locució activa.
        """
        if voice_audio is None or voice_audio.size == 0:
            return voice_audio

        if voice_audio.ndim == 1:
            voice_audio = np.vstack([voice_audio, voice_audio])
        elif voice_audio.shape[0] != 2 and voice_audio.shape[1] == 2:
            voice_audio = voice_audio.T

        total_samples = voice_audio.shape[1]
        if total_samples == 0:
            return voice_audio

        volume = max(0.0, min(1.0, float(volume)))
        if volume <= 0.0:
            return voice_audio

        # Carrega o obté la pista de fons
        if isinstance(bg_audio, str):
            try:
                bg_stereo = self.load_audio_file(bg_audio, target_sr=self.sample_rate)
            except Exception as e:
                print(f"Avís: no s'ha pogut carregar la pista de fons ({e}). Es manté només la veu.")
                return voice_audio
        elif isinstance(bg_audio, np.ndarray):
            bg_stereo = np.copy(bg_audio)
            if bg_stereo.ndim == 1:
                bg_stereo = np.vstack([bg_stereo, bg_stereo])
            elif bg_stereo.shape[0] != 2 and bg_stereo.shape[1] == 2:
                bg_stereo = bg_stereo.T
        else:
            return voice_audio

        bg_len = bg_stereo.shape[1]
        if bg_len == 0:
            return voice_audio

        # Ajust de durada: Bucle o tall/silenci
        if bg_len < total_samples:
            if loop:
                cf_samples = min(int(0.020 * self.sample_rate), bg_len // 3)
                if cf_samples > 10:
                    fade_out = np.linspace(1.0, 0.0, cf_samples, dtype=np.float32)
                    fade_in = np.linspace(0.0, 1.0, cf_samples, dtype=np.float32)
                    tiled = bg_stereo
                    while tiled.shape[1] < total_samples:
                        overlap = tiled[:, -cf_samples:] * fade_out + bg_stereo[:, :cf_samples] * fade_in
                        tiled = np.concatenate([
                            tiled[:, :-cf_samples],
                            overlap,
                            bg_stereo[:, cf_samples:]
                        ], axis=1)
                    bg_final = tiled[:, :total_samples]
                else:
                    reps = int(np.ceil(total_samples / bg_len))
                    bg_final = np.tile(bg_stereo, reps)[:, :total_samples]
            else:
                bg_final = np.pad(bg_stereo, ((0, 0), (0, total_samples - bg_len)), mode="constant")
        else:
            bg_final = bg_stereo[:, :total_samples]

        # Aplicació d'Auto-Ducking intel·ligent si està activat
        if ducking:
            # 1. Envolupant d'amplitud mono de la locució
            voice_mono = np.max(np.abs(voice_audio), axis=0)

            # Detecció de presència de veu per blocs de 20 ms (~RMS)
            block_size = max(1, int(0.020 * self.sample_rate))
            num_blocks = (total_samples + block_size - 1) // block_size
            pad_needed = num_blocks * block_size - total_samples
            if pad_needed > 0:
                v_padded = np.pad(voice_mono, (0, pad_needed), mode="constant")
            else:
                v_padded = voice_mono

            # Valor RMS per bloc
            blocks = v_padded.reshape(num_blocks, block_size)
            block_rms = np.sqrt(np.mean(blocks ** 2, axis=1) + 1e-12)

            # Convertim el llindar dB a escala lineal
            thresh_linear = 10.0 ** (duck_threshold_db / 20.0)

            # Factor de reducció (duck ratio)
            duck_ratio = 10.0 ** (-abs(duck_reduction_db) / 20.0)
            target_gains = np.where(block_rms >= thresh_linear, duck_ratio, 1.0).astype(np.float32)

            # Interpola a nivell de mostra
            raw_gain = np.repeat(target_gains, block_size)[:total_samples]

            # 2. Suavitzat asimètric (Atac ràpid per atenuar, Relaxació suau per recuperar)
            attack_samples = max(1, int((duck_attack_ms / 1000.0) * self.sample_rate))
            release_samples = max(1, int((duck_release_ms / 1000.0) * self.sample_rate))
            alpha_attack = math.exp(-1.0 / attack_samples)
            alpha_release = math.exp(-1.0 / release_samples)

            gain_curve = np.empty(total_samples, dtype=np.float32)
            curr = 1.0
            for i in range(total_samples):
                tgt = raw_gain[i]
                if tgt < curr:
                    curr = alpha_attack * curr + (1.0 - alpha_attack) * tgt
                else:
                    curr = alpha_release * curr + (1.0 - alpha_release) * tgt
                gain_curve[i] = curr

            # Multipliquem la pista de música pel volum i la corba de guany
            bg_final = bg_final * (volume * gain_curve)
        else:
            bg_final = bg_final * volume

        # Esvaïment suau d'entrada (fade-in) i sortida (fade-out)
        fade_in_samples = min(int(fade_in_sec * self.sample_rate), total_samples // 2)
        fade_out_samples = min(int(fade_out_sec * self.sample_rate), total_samples // 2)

        if fade_in_samples > 0:
            curve_in = 0.5 * (1.0 - np.cos(np.pi * np.linspace(0, 1, fade_in_samples, dtype=np.float32)))
            bg_final[:, :fade_in_samples] *= curve_in

        if fade_out_samples > 0:
            curve_out = 0.5 * (1.0 + np.cos(np.pi * np.linspace(0, 1, fade_out_samples, dtype=np.float32)))
            bg_final[:, -fade_out_samples:] *= curve_out

        # Suma ponderada de la locució i la música
        mixed = voice_audio + bg_final

        # Limitador suau de pic per evitar saturació digital (True Peak <= -0.5 dBTP)
        peak = float(np.max(np.abs(mixed)))
        limit = 0.95
        if peak > limit:
            mixed = mixed * (limit / peak)

        return mixed.astype(np.float32)
