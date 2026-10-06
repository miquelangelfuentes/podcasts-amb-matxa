"""
Script de prova per verificar:
1. Sincronització de locutors i panning amb el text del guió (amb Presentador).
2. Opcions de 1 veu (monòleg), 2 veus (diàleg sense presentador) i 3 veus (amb presentador).
3. Catàleg de veus amb descripcions i conversió bidireccional de labels.
4. Generador i reproductor de mostres de veu (VoicePreviewManager).
5. Tema verd matxa pastel i accessibilitat.
6. Guió complet de mostra de 5 minuts.
"""

import sys
import os
import re

# Afegir arrel del projecte
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from ui.theme import MatchaTheme
from core.script_parser import ScriptParser
from core.voice_preview import VoicePreviewManager
from core.matxa_tts_engine import MatxaTTSCatalanEngine
from core.tts_engine import StyleTTS2CatalanEngine

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def test_voice_descriptions():
    print("--- 1. Provant descripcions de veus ---")
    from ui.main_window import MainWindow
    matxa_descs = MainWindow.MATXA_VOICE_DESCRIPTIONS
    neural_descs = MainWindow.NEURAL_VOICE_DESCRIPTIONS

    assert len(matxa_descs) == 16, f"Esperades 16 veus a Matxa-TTS, obtingudes {len(matxa_descs)}"
    assert "elia" in matxa_descs
    assert "Central" in matxa_descs["elia"]
    assert "quim" in matxa_descs
    assert "Balear" in matxa_descs["quim"]
    assert "lluc" in matxa_descs
    assert "Valencià" in matxa_descs["lluc"]
    assert "emma" in matxa_descs
    assert "Nord-occidental" in matxa_descs["emma"]
    assert "jordi" in matxa_descs
    assert "Septentrional" in matxa_descs["jordi"]

    print("[OK] Totes les 16 veus de Matxa-TTS tenen descripció dialectal correcta.")

    assert len(neural_descs) >= 8, f"Esperades almenys 8 veus neuronals expressives, obtingudes {len(neural_descs)}"
    assert "lluc" in neural_descs and "balear" in neural_descs["lluc"].lower()
    assert "pere" in neural_descs and "valencià" in neural_descs["pere"].lower()
    print("[OK] Totes les veus neuronals expressives tenen descripció correcta (incloent-hi Central, Balear i Valencià).")

    upc_descs = MainWindow.UPC_VOICE_DESCRIPTIONS
    assert "ona" in upc_descs and "pau" in upc_descs
    assert "FestCat" in upc_descs["ona"] and "FestCat" in upc_descs["pau"]
    print("[OK] Totes les veus de UPC FestCat (Ona i Pau) tenen descripció correcta.")


def test_script_synchronization():
    print("\n--- 2. Provant sincronització de veus amb Veu presentadora i etiquetes inclusives ---")
    script_text = """[TITOL: Podcast de Prova]
[VEUS]
- Veu presentadora: Conducció institucional
- Veu 1: Investigadora

[CONFIGURACIO_VEUS]
Veu presentadora: veu=jordi pan=0% velocitat=0.96 pitch=-1
Veu 1: veu=elia pan=-25% velocitat=1.0 pitch=0

---

Veu presentadora: Benvinguts al curs.
Veu 1: Gràcies a tothom.
"""
    spk_name = "Veu presentadora"
    new_voice = "pau"
    new_pan_str = "+25%"

    cfg_header_pattern = re.compile(r"^\[(?:CONFIGURACIO_VEUS|CONFIGURACIO_LOCUTORS|CONFIGURACIO|SPEAKERS_CONFIG)\]", re.MULTILINE | re.IGNORECASE)
    spk_line_pattern = re.compile(rf"^(\s*{re.escape(spk_name)}\s*:\s*)([^\r\n]*)", re.MULTILINE)

    match_spk = spk_line_pattern.search(script_text)
    assert match_spk is not None, "La línia de la veu hauria d'existir al guió"

    prefix = match_spk.group(1)
    rest = match_spk.group(2)
    rest = re.sub(r'\b(?:veu|voice)=([^\s]+)', f'veu={new_voice}', rest, flags=re.IGNORECASE)
    rest = re.sub(r'\b(?:pan|panning)=([^\s]+)', f'pan={new_pan_str}', rest, flags=re.IGNORECASE)
    new_line = f"{prefix}{rest.strip()}"
    updated = script_text[:match_spk.start()] + new_line + script_text[match_spk.end():]

    assert "Veu presentadora: veu=pau pan=+25% velocitat=0.96 pitch=-1" in updated
    assert "Veu 1: veu=elia pan=-25%" in updated

    parser = ScriptParser()
    parsed = parser.parse(updated)
    assert parsed.speakers["Veu presentadora"].voice_id == "pau"
    assert parsed.speakers["Veu presentadora"].pan == 0.25
    assert parsed.segments[0].speaker == "Veu presentadora"
    assert parsed.segments[0].voice_id == "pau"
    assert parsed.segments[0].pan == 0.25
    print("[OK] Sincronització de veus i panning amb etiquetes inclusives [VEUS] i [CONFIGURACIO_VEUS] verificada amb èxit!")


def test_voice_structure_templates():
    print("\n--- 3. Provant plantilles d'1, 2 i 3 veus ---")
    parser = ScriptParser()

    # 1 veu
    path_1v = os.path.join(project_root, "examples", "plantilla_1veu.txt")
    assert os.path.exists(path_1v), "La plantilla d'1 veu ha d'existir"
    with open(path_1v, "r", encoding="utf-8") as f:
        c1 = f.read()
    p1 = parser.parse(c1)
    assert len(p1.speakers) == 1, f"Esperat 1 locutor, obtinguts {len(p1.speakers)}"
    assert "Veu presentadora" in p1.speakers, "El locutor d'1 veu ha de ser la Veu presentadora"
    assert p1.speakers["Veu presentadora"].pan == 0.0, "La Veu presentadora d'1 veu ha d'estar al centre (0%)"
    assert "Com funciona el format d'una veu" in c1 or "com funciona" in c1.lower(), "Ha d'explicar com funciona l'app"
    print("[OK] Plantilla 1 veu verificada (explica com funciona l'app en 1 veu).")

    # 2 veus (sense presentador)
    path_2v = os.path.join(project_root, "examples", "plantilla_2veus.txt")
    assert os.path.exists(path_2v), "La plantilla de 2 veus ha d'existir"
    with open(path_2v, "r", encoding="utf-8") as f:
        c2 = f.read()
    p2 = parser.parse(c2)
    assert len(p2.speakers) == 2, f"Esperats 2 locutors, obtinguts {len(p2.speakers)}"
    assert "Veu presentadora" not in p2.speakers, "La plantilla de 2 veus NO ha de tenir presentador"
    assert "Veu 1" in p2.speakers and "Veu 2" in p2.speakers
    assert p2.speakers["Veu 1"].pan == -0.25
    assert p2.speakers["Veu 2"].pan == 0.25
    assert "Com funciona el format de dues veus" in c2 or "com funciona" in c2.lower(), "Ha d'explicar com funciona l'app"
    print("[OK] Plantilla 2 veus verificada (explica com funciona l'app en 2 veus).")

    # 3 veus (amb presentador)
    path_3v = os.path.join(project_root, "examples", "plantilla_3veus.txt")
    assert os.path.exists(path_3v), "La plantilla de 3 veus ha d'existir"
    with open(path_3v, "r", encoding="utf-8") as f:
        c3 = f.read()
    p3 = parser.parse(c3)
    assert len(p3.speakers) == 3, f"Esperats 3 locutors, obtinguts {len(p3.speakers)}"
    assert "Veu presentadora" in p3.speakers, "La plantilla de 3 veus ha d'incloure la Veu presentadora"
    assert p3.speakers["Veu presentadora"].pan == 0.0
    assert p3.speakers["Veu 1"].pan == -0.25
    assert p3.speakers["Veu 2"].pan == 0.25
    assert "Com funciona el format de tres veus" in c3 or "com funciona" in c3.lower(), "Ha d'explicar com funciona l'app"
    print("[OK] Plantilla 3 veus verificada (explica com funciona l'app en 3 veus).")

    # Guió complet de mostra de 5 minuts
    path_5m = os.path.join(project_root, "examples", "guio_exemple_5min.txt")
    assert os.path.exists(path_5m), "El guió de 5 minuts ha d'existir"
    with open(path_5m, "r", encoding="utf-8") as f:
        content_5m = f.read()
    p5m = parser.parse(content_5m)
    assert len(p5m.speakers) == 3
    assert "Veu presentadora" in p5m.speakers
    assert "Veu 1" in p5m.speakers
    assert "Veu 2" in p5m.speakers
    words = sum(len(s.text.split()) for s in p5m.segments if s.segment_type == "dialogue")
    assert words >= 700, f"El guió de 5 minuts ha de tenir almenys 700 paraules, té {words}"
    assert "Pòdcasts amb Matxa" in content_5m
    assert "flow matching" in content_5m
    assert "UPC Ona" in content_5m, "El guió de 5 minuts ha de mencionar UPC Ona"
    assert "alVoCat" in content_5m
    print(f"[OK] Guió de 5 minuts verificat ({words} paraules, inclou UPC Ona i Matxa-TTS v2).")


def test_voice_preview_manager():
    print("\n--- 4. Provant VoicePreviewManager ---")
    mgr = VoicePreviewManager()
    phrase_elia = mgr.get_sample_phrase("elia")
    assert "Èlia" in phrase_elia
    assert "central" in phrase_elia.lower()

    phrase_quim = mgr.get_sample_phrase("quim")
    assert "Quim" in phrase_quim
    assert "balear" in phrase_quim.lower()

    phrase_lluc = mgr.get_sample_phrase("lluc")
    assert "Lluc" in phrase_lluc
    assert "valencià" in phrase_lluc.lower()

    print("[OK] Frases dialectals personalitzades verificades correctament.")


def test_theme_and_accessibility():
    print("\n--- 5. Provant tema i colors verd matxa pastel ---")
    assert MatchaTheme.BG_MAIN.startswith("#"), "El fons principal ha de ser un color hex vàlid"
    assert MatchaTheme.PRIMARY == "#2E5E41", "Color primari matxa cerimonial profund"
    assert MatchaTheme.FONT_BODY[1] >= 11, f"La mida del text corporal és massa petita: {MatchaTheme.FONT_BODY}"
    assert MatchaTheme.FONT_SMALL[1] >= 10, f"La mida del text petit és massa petita: {MatchaTheme.FONT_SMALL}"
    print(f"[OK] Tema verd matxa pastel verificat (Primary: {MatchaTheme.PRIMARY}, Fons: {MatchaTheme.BG_MAIN}).")


def test_default_model_and_naming():
    print("\n--- 6. Provant model predeterminat i nom oficial ---")
    import inspect
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow)
    assert "self.tts_engine = self.matxa_engine" in src, "El motor per defecte ha d'estar definit correctament"
    assert 'self.title(f"Pòdcasts amb Matxa v{APP_VERSION}")' in src or 'self.title("Pòdcasts amb Matxa")' in src, "El títol ha de ser 'Pòdcasts amb Matxa'"
    assert "Matxa-TTS v2" in src, "El motor Matxa-TTS v2 ha de figurar al desplegable de motors"
    assert "UPC FestCat" in src, "El motor UPC FestCat ha de figurar al desplegable de motors"
    assert "Veus neuronals ca-ES" in src, "El motor de veus neuronals ca-ES ha de figurar al desplegable"
    print("[OK] Motors de síntesi (Matxa-TTS v2, UPC FestCat Ona i Pau, Veus neuronals Online) i nom oficial verificats.")


def test_components_manager():
    print("\n--- 7. Provant Gestor de Components i Models ---")
    from core.model_downloader import ModelDownloader
    from ui.components_modal import ComponentsManagerModal

    downloader = ModelDownloader()
    statuses = downloader.get_all_components_status()

    assert "alvocat_vocos" in statuses, "alVoCat ha de figurar al catàleg de components"
    assert "matxa_tts" in statuses, "Matxa-TTS ha de figurar al catàleg de components"
    assert "upc_ona" in statuses, "UPC Ona ha de figurar al catàleg de components"
    assert "upc_pau" in statuses, "UPC Pau ha de figurar al catàleg de components"

    # Verificar que els models instal·lats localment es detecten
    alvocat = statuses["alvocat_vocos"]
    assert alvocat["is_installed"], "alVoCat ha d'estar marcat com a instal·lat"
    assert alvocat["installed_size_mb"] >= 50.0, f"Mida inesperada per alVoCat: {alvocat['installed_size_mb']} MB"

    matxa = statuses["matxa_tts"]
    assert matxa["is_installed"], "Matxa-TTS ha d'estar marcat com a instal·lat"
    assert matxa["installed_size_mb"] >= 250.0, f"Mida inesperada per Matxa-TTS: {matxa['installed_size_mb']} MB"

    pau = statuses["upc_pau"]
    assert pau["is_installed"], "UPC Pau ha d'estar marcat com a instal·lat"
    assert pau["installed_size_mb"] >= 25.0, f"Mida inesperada per UPC Pau: {pau['installed_size_mb']} MB"

    print(f"[OK] Estat de components verificat: alVoCat ({alvocat['installed_size_mb']} MB), Matxa-TTS ({matxa['installed_size_mb']} MB), UPC Pau ({pau['installed_size_mb']} MB).")


def test_background_music_mixing():
    print("\n--- 8. Provant mescla de pista de fons (MP3 / àudio) amb bucle i control de volum ---")
    import numpy as np
    import tempfile
    import soundfile as sf
    from core.audio_processor import AudioProcessor

    ap = AudioProcessor(sample_rate=22050)

    # 1. Crear pista de veu simulada (10 segons a 22050 Hz estèreo)
    voice_len = 10 * 22050
    t_voice = np.linspace(0, 10, voice_len, dtype=np.float32)
    voice_stereo = np.vstack([np.sin(2 * np.pi * 440 * t_voice) * 0.5, np.sin(2 * np.pi * 440 * t_voice) * 0.5])

    # 2. Crear pista de música de fons simulada (3 segons a 44100 Hz mono)
    bg_len = 3 * 44100
    t_bg = np.linspace(0, 3, bg_len, dtype=np.float32)
    bg_mono = np.sin(2 * np.pi * 220 * t_bg) * 0.4

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_bg = f.name
    try:
        sf.write(tmp_bg, bg_mono, 44100)

        # Test carregar i resamplejar
        loaded_bg = ap.load_audio_file(tmp_bg, target_sr=22050)
        assert loaded_bg.shape[0] == 2, "La pista carregada ha de ser estèreo (2 canals)"
        assert abs(loaded_bg.shape[1] - 3 * 22050) < 15, "Re-mostreig de 44.1k a 22.05k correcte"

        # Test mescla amb bucle
        mixed_loop = ap.mix_background_track(voice_stereo, tmp_bg, volume=0.15, loop=True)
        assert mixed_loop.shape == voice_stereo.shape, "L'àudio mesclat ha de tenir exactament la mateixa mida que la veu"
        assert np.max(np.abs(mixed_loop)) <= 0.96, "El limitador de pic prevé saturació"

        # Test mescla sense bucle
        mixed_noloop = ap.mix_background_track(voice_stereo, tmp_bg, volume=0.15, loop=False)
        assert mixed_noloop.shape == voice_stereo.shape

        # A la part final (segons 6-9), la pista en bucle conté música mentre que sense bucle ja ha acabat
        energy_loop_end = np.mean(mixed_loop[:, int(6 * 22050):int(9 * 22050)] ** 2)
        energy_noloop_end = np.mean(mixed_noloop[:, int(6 * 22050):int(9 * 22050)] ** 2)
        assert energy_loop_end > energy_noloop_end, "En bucle la música continua sonant al tram final"

        # Test d'Auto-Ducking intel·ligent
        # Creem veu amb parla als primers 2 segons i silenci als 2 següents
        test_voice = np.zeros((2, 4 * 22050), dtype=np.float32)
        test_voice[:, :2 * 22050] = 0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 2, 2 * 22050, dtype=np.float32))
        mixed_ducked = ap.mix_background_track(test_voice, tmp_bg, volume=0.4, ducking=True)
        assert mixed_ducked.shape == test_voice.shape
        talk_bg = np.mean((mixed_ducked[:, int(0.5 * 22050):int(1.5 * 22050)] - test_voice[:, int(0.5 * 22050):int(1.5 * 22050)]) ** 2)
        pause_bg = np.mean((mixed_ducked[:, int(2.5 * 22050):int(3.5 * 22050)] - test_voice[:, int(2.5 * 22050):int(3.5 * 22050)]) ** 2)
        assert pause_bg > talk_bg * 3.0, "La música ha d'estar significativament atenuada mentre es parla"

        print("[OK] Mescla de pista de fons, bucle continu, auto-ducking, re-mostreig i control de volum verificats amb èxit!")
    finally:
        if os.path.exists(tmp_bg):
            try:
                os.remove(tmp_bg)
            except OSError:
                pass


def test_upc_engine():
    print("\n--- 9. Provant motor UPC FestCat Ona i Pau (Piper Neural 100% Offline) ---")
    import numpy as np
    from core.upc_ona_engine import UPCOnaCatalanEngine
    engine = UPCOnaCatalanEngine()
    assert "UPC" in engine.name
    assert engine.sample_rate == 22050
    assert "ona" in engine.UPC_SPEAKERS
    assert "pau" in engine.UPC_SPEAKERS

    # Verificació de càrrega i síntesi Ona
    loaded_ona = engine.ensure_loaded("ona")
    assert loaded_ona is True, "El model UPC Ona s'hauria de carregar correctament"
    assert engine.is_loaded("ona") is True

    wav_ona = engine.synthesize_utterance("Hola, soc l'Ona de la Universitat Politècnica de Catalunya.", voice_id="ona")
    assert len(wav_ona) > 0, "L'àudio generat per Ona no ha d'estar buit"
    assert wav_ona.ndim == 1, "L'àudio ha de ser mono float32"
    assert wav_ona.dtype == np.float32

    # Verificació de càrrega i síntesi Pau
    loaded_pau = engine.ensure_loaded("pau")
    assert loaded_pau is True, "El model UPC Pau s'hauria de carregar correctament"
    assert engine.is_loaded("pau") is True

    wav_pau = engine.synthesize_utterance("Hola, soc en Pau de la Universitat Politècnica de Catalunya.", voice_id="pau")
    assert len(wav_pau) > 0, "L'àudio generat per Pau no ha d'estar buit"
    assert wav_pau.ndim == 1, "L'àudio ha de ser mono float32"
    assert wav_pau.dtype == np.float32

    print(f"[OK] Motor UPC FestCat verificat correctament (Ona: {len(wav_ona)/22050:.2f} s, Pau: {len(wav_pau)/22050:.2f} s).")


def test_version_check():
    print("\n--- 10. Provant comprovador d'actualitzacions i versió GitHub ---")
    from ui.version_check_modal import APP_VERSION, GITHUB_OWNER, GITHUB_REPO
    assert APP_VERSION == "1.1.0"
    assert GITHUB_OWNER == "miquelangelfuentes"
    assert GITHUB_REPO == "podcasts-amb-estil-i-matxa"
    print(f"[OK] Comprovador de versió configurat: v{APP_VERSION} a {GITHUB_OWNER}/{GITHUB_REPO}")


if __name__ == "__main__":
    test_voice_descriptions()
    test_script_synchronization()
    test_voice_structure_templates()
    test_voice_preview_manager()
    test_theme_and_accessibility()
    test_default_model_and_naming()
    test_components_manager()
    test_background_music_mixing()
    test_upc_engine()
    test_version_check()
    print("\n*** TOTES LES PROVES S'HAN SUPERAT AMB ÈXIT! ***")

