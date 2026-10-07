"""
Mòdul d'Anàlisi de Guió de Pòdcast (Podcast Script Parser).
Interpreta fitxers .txt amb format estructurat de metadades,
locutors, pauses, paràmetres de panoràmica estèreo i diàlegs.
Garanteix la separació estricta entre metadades de capçalera i diàleg pronunciat.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

@dataclass
class SpeakerConfig:
    name: str
    voice_id: str = "elia"           # elia, grau, ona, pau, olga, quim, gina, lluc, etc.
    pan: float = 0.0                # -1.0 (esquerra) a +1.0 (dreta)
    speed: float = 1.0              # 0.5 a 2.0
    pitch: float = 0.0              # -5 a +5
    clone_audio_path: Optional[str] = None # Ruta a arxiu d'àudio de referència per a clonació
    description: str = ""

@dataclass
class PodcastSegment:
    segment_type: str               # 'dialogue', 'pause', 'cue'
    speaker: str = ""
    text: str = ""
    pause_ms: int = 400
    pan: float = 0.0
    speed: float = 1.0
    pitch: float = 0.0
    clone_audio_path: Optional[str] = None
    voice_id: str = "elia"
    raw_line: str = ""

@dataclass
class PodcastScript:
    title: str = "Pòdcast Educatiu"
    description: str = ""
    format_info: str = "Stereo 160kbps"
    default_pause_ms: int = 350
    turn_pause_ms: int = 700
    metadata: Dict[str, str] = field(default_factory=dict)
    speakers: Dict[str, SpeakerConfig] = field(default_factory=dict)
    segments: List[PodcastSegment] = field(default_factory=list)

class ScriptParser:
    """Analitzador sintàctic robust per a guions de pòdcast en fitxers .txt."""

    DEFAULT_VOICE_MAP = {
        0: "elia",    # Veu femenina central (didàctica)
        1: "grau",    # Veu masculina central (dinàmic)
        2: "ona",     # Veu femenina central institucional
        3: "pau",     # Veu masculina central narrativa
        4: "gina",    # Veu femenina valenciana
        5: "lluc",    # Veu masculina valenciana
        6: "olga",    # Veu femenina balear
        7: "quim",    # Veu masculina balear
        8: "jordi",   # Veu masculina rossellonesa / serena
        9: "emma"     # Veu femenina nord-occidental
    }

    def __init__(self):
        pass

    def parse_time_ms(self, time_str: str) -> int:
        """Converteix cadenes com '500ms', '1.5s', '800' en mil·lisegons."""
        time_str = time_str.strip().lower()
        if time_str.endswith("ms"):
            try:
                return int(float(time_str[:-2]))
            except ValueError:
                return 400
        elif time_str.endswith("s"):
            try:
                return int(float(time_str[:-1]) * 1000)
            except ValueError:
                return 400
        else:
            try:
                return int(float(time_str))
            except ValueError:
                return 400

    def parse_pan(self, pan_str: str) -> float:
        """Converteix '-25%', '+0.2', 'L30', 'R20', 'centre' en float entre -1.0 i +1.0."""
        pan_str = pan_str.strip().lower().replace("%", "")
        if pan_str in ("c", "center", "centre", "0", "+0", "-0"):
            return 0.0
        try:
            val = float(pan_str)
            if abs(val) > 1.0: # Si venia en percentatge (p. ex. -25 o +25)
                val = val / 100.0
            return max(-1.0, min(1.0, val))
        except ValueError:
            if pan_str.startswith("l"):
                try:
                    return -abs(float(pan_str[1:]) / 100.0)
                except ValueError:
                    return -0.25
            elif pan_str.startswith("r"):
                try:
                    return abs(float(pan_str[1:]) / 100.0)
                except ValueError:
                    return 0.25
            return 0.0

    def parse(self, text_content: str) -> PodcastScript:
        """
        Analitza el contingut complet del fitxer .txt i retorna un PodcastScript.
        Garanteix que cap etiqueta o metadada de capçalera (com ara [FORMAT: ...])
        no es converteixi mai en un segment de locució.
        """
        lines = text_content.splitlines()
        script = PodcastScript()

        # Estats de processament: 'HEADER', 'SPEAKERS_DESC', 'SPEAKERS_CONFIG', 'DIALOGUE'
        mode = "HEADER"

        assigned_voice_idx = 0
        default_voices = ["elia", "grau", "ona", "pau", "gina", "lluc", "olga", "quim"]
        default_pans = [-0.25, 0.25, 0.0, -0.35, 0.35]

        dialogue_pattern = re.compile(r"^([A-ZÀ-Úa-zà-ú0-9_\-\.\s]+?)\s*:\s*(.*)$")
        bracket_tag_pattern = re.compile(r"^\[([A-Z_]+)(?:\s*:\s*([^\]]+))?\]", re.IGNORECASE)

        last_speaker = None

        for line_num, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue

            # Separadors estàndard que marquen l'inici del guió / diàleg
            if line.startswith("---") or line.startswith("===") or line.startswith("***"):
                mode = "DIALOGUE"
                continue

            tag_match = bracket_tag_pattern.match(line)
            if tag_match:
                tag_name = tag_match.group(1).upper()
                tag_val = tag_match.group(2).strip() if tag_match.group(2) else ""

                # Canvis de bloc de configuració
                if tag_name in ("LOCUTORS", "SPEAKERS", "VEUS", "REPARTIMENT"):
                    mode = "SPEAKERS_DESC"
                    continue
                elif tag_name in ("CONFIGURACIO_LOCUTORS", "CONFIGURACIO_VEUS", "CONFIGURACIO", "SPEAKERS_CONFIG"):
                    mode = "SPEAKERS_CONFIG"
                    continue
                elif tag_name in ("GUIO", "SCRIPT", "DIALEG", "CONTINGUT", "PODCAST"):
                    mode = "DIALOGUE"
                    continue

                # Gestió d'etiquetes de pausa [PAUSA: 500ms]
                if tag_name in ("PAUSA", "PAUSE"):
                    pause_ms = self.parse_time_ms(tag_val) if tag_val else script.default_pause_ms
                    # Només s'afegeix com a segment de silenci si ja som a la part de diàleg
                    if mode == "DIALOGUE":
                        script.segments.append(PodcastSegment(
                            segment_type="pause",
                            pause_ms=pause_ms,
                            raw_line=raw_line
                        ))
                    continue

                # Gestió d'indicacions sonores o musicals [MUSICA: ...] o [EFECTE: ...]
                if tag_name in ("MUSICA", "MUSIC", "EFECTE", "EFFECT", "FX", "SO", "SOUND", "CUE"):
                    if mode == "DIALOGUE":
                        # Inserim una breu pausa de respiració de 500 ms pel cue sonor
                        script.segments.append(PodcastSegment(
                            segment_type="pause",
                            pause_ms=500,
                            raw_line=raw_line
                        ))
                    continue

                # Si és qualsevol altra etiqueta [CLAU: VALOR] a la capçalera (TITOL, DESCRIPCIO, FORMAT, AUTOR...)
                if mode != "DIALOGUE":
                    script.metadata[tag_name] = tag_val
                    if tag_name in ("TITOL", "TITLE"):
                        script.title = tag_val
                    elif tag_name in ("DESCRIPCIO", "DESCRIPTION"):
                        script.description = tag_val
                    elif tag_name in ("FORMAT",):
                        script.format_info = tag_val
                    elif tag_name in ("PAUSA_DEFECTE", "DEFAULT_PAUSE"):
                        script.default_pause_ms = self.parse_time_ms(tag_val)
                    elif tag_name in ("PAUSA_INTERLOCUTOR", "PAUSA_INTERLOCUCIO", "PAUSA_CANVI_VEU", "TURN_PAUSE"):
                        script.turn_pause_ms = self.parse_time_ms(tag_val)
                    continue
                else:
                    # Dins de la secció de diàleg, una etiqueta entre claudàtors desconeguda [NOTA], [RIURES]
                    # és una acotació de direcció i MAI s'ha de pronunciar com a text en veu alta
                    continue

            # Secció [LOCUTORS]: - Nom: Descripció
            if mode == "SPEAKERS_DESC":
                if line.startswith("-") or line.startswith("*"):
                    item = line.lstrip("-* ").strip()
                    parts = item.split(":", 1)
                    name = parts[0].strip()
                    desc = parts[1].strip() if len(parts) > 1 else ""
                    if name and name not in script.speakers:
                        voice_id = default_voices[assigned_voice_idx % len(default_voices)]
                        pan = default_pans[assigned_voice_idx % len(default_pans)]
                        assigned_voice_idx += 1
                        script.speakers[name] = SpeakerConfig(
                            name=name,
                            voice_id=voice_id,
                            pan=pan,
                            description=desc
                        )
                continue

            # Secció [CONFIGURACIO_LOCUTORS]: Nom: veu=... pan=... velocitat=...
            elif mode == "SPEAKERS_CONFIG":
                cfg_match = dialogue_pattern.match(line)
                if cfg_match:
                    name = cfg_match.group(1).strip()
                    props_str = cfg_match.group(2).strip()
                    if name not in script.speakers:
                        script.speakers[name] = SpeakerConfig(name=name)

                    spk = script.speakers[name]
                    for token in props_str.split():
                        if "=" in token:
                            p_key, p_val = token.split("=", 1)
                            p_key = p_key.lower().strip()
                            p_val = p_val.strip()
                            if p_key in ("veu", "voice", "voice_id"):
                                spk.voice_id = p_val
                            elif p_key in ("pan", "panoramica", "panning"):
                                spk.pan = self.parse_pan(p_val)
                            elif p_key in ("velocitat", "speed", "rate"):
                                try:
                                    spk.speed = float(p_val)
                                except ValueError:
                                    pass
                            elif p_key in ("pitch", "to"):
                                try:
                                    spk.pitch = float(p_val)
                                except ValueError:
                                    pass
                            elif p_key in ("clon", "clone", "audio_ref", "ref_audio"):
                                spk.clone_audio_path = p_val
                continue

            # Comprovació de línia de diàleg: Locutor: Text a sintetitzar
            dialogue_match = dialogue_pattern.match(line)
            if dialogue_match and not line.startswith("["):
                possible_speaker = dialogue_match.group(1).strip()
                utterance = dialogue_match.group(2).strip()

                is_known_spk = possible_speaker in script.speakers
                is_valid_spk_format = (
                    len(possible_speaker.split()) <= 3
                    and possible_speaker[0].isupper()
                    and not any(char in possible_speaker for char in "[]{}()<>;=\"'")
                )

                if is_known_spk or is_valid_spk_format:
                    mode = "DIALOGUE"
                    speaker_name = possible_speaker

                    if speaker_name not in script.speakers:
                        voice_id = default_voices[assigned_voice_idx % len(default_voices)]
                        pan = default_pans[assigned_voice_idx % len(default_pans)]
                        assigned_voice_idx += 1
                        script.speakers[speaker_name] = SpeakerConfig(
                            name=speaker_name,
                            voice_id=voice_id,
                            pan=pan
                        )

                    spk = script.speakers[speaker_name]

                    # Pausa automàtica conversacional en canvi d'interlocutor
                    if last_speaker and last_speaker != speaker_name:
                        script.segments.append(PodcastSegment(
                            segment_type="pause",
                            pause_ms=script.turn_pause_ms,
                            raw_line="[AUTO_TURN_PAUSE]"
                        ))

                    inline_pause_regex = re.compile(r'(\[(?:PAUSA|PAUSE)\s*:\s*[^\]]+\]|<break\s+[^>]*/>)', re.IGNORECASE)
                    parts = inline_pause_regex.split(utterance)

                    for part in parts:
                        if not part:
                            continue
                        bracket_match = re.match(r'^\[(?:PAUSA|PAUSE)\s*:\s*([^\]]+)\]$', part.strip(), re.IGNORECASE)
                        if bracket_match:
                            dur_ms = self.parse_time_ms(bracket_match.group(1))
                            script.segments.append(PodcastSegment(
                                segment_type="pause",
                                pause_ms=dur_ms,
                                raw_line=part
                            ))
                            continue

                        break_match = re.match(r'^<break\s+time=["\']([0-9.]+)(ms|s)["\']\s*/?>$', part.strip(), re.IGNORECASE)
                        if break_match:
                            val = float(break_match.group(1))
                            unit = break_match.group(2).lower()
                            dur_ms = int(val if unit == "ms" else val * 1000)
                            script.segments.append(PodcastSegment(
                                segment_type="pause",
                                pause_ms=dur_ms,
                                raw_line=part
                            ))
                            continue

                        clean_utterance = part.strip()
                        if clean_utterance:
                            script.segments.append(PodcastSegment(
                                segment_type="dialogue",
                                speaker=speaker_name,
                                text=clean_utterance,
                                pause_ms=script.default_pause_ms,
                                pan=spk.pan,
                                speed=spk.speed,
                                pitch=spk.pitch,
                                clone_audio_path=spk.clone_audio_path,
                                voice_id=spk.voice_id,
                                raw_line=raw_line
                            ))

                    last_speaker = speaker_name
                    continue

            # Si estem en mode DIALOGUE i la línia no té prefix "Locutor:", és continuació de la frase
            if mode == "DIALOGUE" and last_speaker:
                spk = script.speakers.get(last_speaker)
                inline_pause_regex = re.compile(r'(\[(?:PAUSA|PAUSE)\s*:\s*[^\]]+\]|<break\s+[^>]*/>)', re.IGNORECASE)
                parts = inline_pause_regex.split(line)

                for part in parts:
                    if not part:
                        continue
                    bracket_match = re.match(r'^\[(?:PAUSA|PAUSE)\s*:\s*([^\]]+)\]$', part.strip(), re.IGNORECASE)
                    if bracket_match:
                        dur_ms = self.parse_time_ms(bracket_match.group(1))
                        script.segments.append(PodcastSegment(
                            segment_type="pause",
                            pause_ms=dur_ms,
                            raw_line=part
                        ))
                        continue

                    break_match = re.match(r'^<break\s+time=["\']([0-9.]+)(ms|s)["\']\s*/?>$', part.strip(), re.IGNORECASE)
                    if break_match:
                        val = float(break_match.group(1))
                        unit = break_match.group(2).lower()
                        dur_ms = int(val if unit == "ms" else val * 1000)
                        script.segments.append(PodcastSegment(
                            segment_type="pause",
                            pause_ms=dur_ms,
                            raw_line=part
                        ))
                        continue

                    clean_part = part.strip()
                    if clean_part:
                        if script.segments and script.segments[-1].segment_type == "dialogue" and script.segments[-1].speaker == last_speaker:
                            script.segments[-1].text += " " + clean_part
                        else:
                            script.segments.append(PodcastSegment(
                                segment_type="dialogue",
                                speaker=last_speaker,
                                text=clean_part,
                                pause_ms=script.default_pause_ms,
                                pan=spk.pan if spk else 0.0,
                                speed=spk.speed if spk else 1.0,
                                pitch=spk.pitch if spk else 0.0,
                                clone_audio_path=spk.clone_audio_path if spk else None,
                                voice_id=spk.voice_id if spk else "elia",
                                raw_line=raw_line
                            ))
                continue

            # Si encara som a HEADER i no és res del que coneixem, es descarta completament
            # per no generar cap so residual de metadades!

        return script
