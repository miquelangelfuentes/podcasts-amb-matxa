# Registre de canvis (Changelog)

Tots els canvis rellevants, correccions (*fixes*) i novetats del projecte **Pòdcasts amb Matxa** es documenten en aquest arxiu seguint el format estàndard de [Keep a Changelog](https://keepachangelog.com/ca/1.0.0/) i la numeració de versions [Semantic Versioning](https://semver.org/).

---

## [1.1.1] - 2026-10-06

### ✨ Novetats
* **Auto-ducking intel·ligent per a la música o ambient de fons:**
  * S'incorpora un detector d'energia RMS de veu (-12 dB) amb atac suau (120 ms) i caiguda progressiva (650 ms) que atenua automàticament la música quan els locutors parlen i la recupera suaument durant les pauses i silencis.
  * Interruptor directe «📉 Auto-ducking» a la targeta de música de fons, activat per defecte.
* **Control visual de velocitat de veu per a cada locutor:**
  * Cada targeta de locutor a la interfície d'usuari incorpora ara un selector ràpid de píndola (`PillSelector`) amb 5 velocitats: `0.8x`, `0.9x`, `1.0x (Normal)`, `1.1x` i `1.2x`.
  * Regulació en temps real sincronitzada automàticament amb els paràmetres de síntesi dels motors Matxa-TTS v2 (`length_scale`), UPC FestCat Piper i Veus neuronals al núvol.

### 🐛 Correccions
* **Aturada instantània de la reproducció de música de fons:**
  * S'ha corregit un problema pel qual el botó «■ Atura» de la previsualització de música no silenciava la pista quan Pygame estava en execució contínua. Ara purga immediatament la memòria d'àudio tant a Pygame com al subsistema de Windows (`winsound.SND_PURGE`).
* **Regulació dinàmica de volum en viu:**
  * Modificar el lliscador de volum mentre sona la prova de música actualitza el nivell sonor en temps real mitjançant `pygame.mixer.music.set_volume()` sense interrompre ni reiniciar la cançó des del principi.

---

## [1.1.0] - 2026-09-25

### ✨ Novetats
* **Reanomenament oficial de l'aplicació a «Pòdcasts amb Matxa»:**
  * L'aplicació passa a dir-se oficialment **Pòdcasts amb Matxa** a tot arreu: títol de finestra, interfície, documentació, guions didàctics, plantilles i binaris.
  * Nou nom d'arxiu executable: `PodcastsAmbMatxa.exe` i distribució principal `PodcastsAmbMatxa-v1.1.0-Windows.zip` (mantenint àlies de compatibilitat per als accessos directes existents).
* **Retirada de referències a StyleTTS i supressió de la clonació de veu:**
  * S'ha suprimit la funcionalitat de clonació de veu de la interfície i el fitxer `voice_clone_modal.py`.
  * S'han retirat totes les mencions a StyleTTS de desplegables, diàlegs i documentació, classificant transparentment les veus alternatives al núvol com a **`Veus neuronals ca-ES (Online)`**.
* **Integració de les veus neurals UPC FestCat — Ona i Pau (100% offline):**
  * S'ha afegit el motor autònom basat en `piper-tts` i els models ONNX procedents de les gravacions del corpus FestCat de la **Universitat Politècnica de Catalunya (UPC)**:
    * **Ona** (`ca_ES-upc_ona-medium.onnx`, 63,2 MB): veu femenina central d'extraordinària calidesa, naturalitat i fidelitat acústica a 22.050 Hz.
    * **Pau** (`ca_ES-upc_pau-x_low.onnx`, 26,8 MB): veu masculina central autònoma de la UPC.
  * Ambdues veus funcionen de forma 100% local, autònoma i sense dependència de connexió a internet.
* **Comprovador d'actualitzacions integrat («🔄 Comprova versió»):**
  * S'ha afegit un botó d'accés directe a la barra superior que obre el diàleg `VersionCheckModal`.
  * Consulta l'API oficial de GitHub (`miquelangelfuentes/podcasts-amb-estil-i-matxa`) per contrastar la versió local amb l'últim commit o release disponible.
  * Mostra el resum dels darrers canvis introduïts al projecte.
  * Permet descarregar l'actualització i reiniciar automàticament l'aplicació amb el botó **«Actualitza l'aplicació»**.
* **Integració de suport oficial per a Linux:**
  * S'ha creat l'script llançador autònom `run_app.sh` que crea l'entorn virtual `.venv`, instal·la dependències i inicia l'aplicació en un sol pas.
  * S'ha afegit el script de compilació `build_linux.py` per generar paquets binaris autònoms en arxiu comprimit (`PodcastsAmbMatxa-v1.1.0-Linux-x86_64.tar.gz`).
  * S'ha integrat un flux de treball automatitzat de CI/CD amb GitHub Actions (`.github/workflows/build-linux.yml`) que compila la versió per a Linux sobre servidors Ubuntu a cada release.
  * Lectura nativa de memòria RAM des de `/proc/meminfo` al mòdul de comprovació de maquinari (`SystemChecker`).
* **Visualitzador de novetats millorat i identificació de versió:**
  * S'ha substituït l'etiqueta d'una sola línia del modal de versions per un component `CTkTextbox` amb ajust automàtic de paraules (`wrap="word"`), evitant que cap missatge de commit o actualització surti retallat.
  * S'ha incorporat el distintiu visual `v1.1.0` a la capçalera de l'aplicació i s'ha actualitzat el títol de la finestra amb la versió instal·lada.
  * Nomenclatura oficial del paquet comprimit per a Windows amb el número de versió corresponent: `PodcastsAmbMatxa-v1.1.0-Windows.zip`.
* **Previsualitzacions d'àudio integrades per a les veus UPC Ona i Pau:**
  * S'han generat i empaquetat mostres d'àudio WAV (`preview_upc_ona.wav` i `preview_upc_pau.wav`) a `assets/previews/` per permetre l'escolta instantània (0 ms) de les veus de la UPC.
* **Gestor de descàrrega de models actualitzat:**
  * S'han incorporat `upc_ona` i `upc_pau` a `ModelDownloader` i a la finestra de gestió de models (`ComponentsManagerModal`), permetent comprovar el seu estat d'instal·lació, mida a disc (60,3 MB i 26,8 MB) i descarregar-les o suprimir-les fàcilment.

### 🐛 Correccions i transparència tècnica
* **Clarificació i transparència dels motors de veu:**
  * S'ha anomenat i identificat obertament el motor **`Veus neuronals ca-ES (Online)`** com a servei al núvol, evitant qualsevol confusió sobre la necessitat de connexió a internet i privadesa.
  * S'ha retirat el checkpoint de recerca de 2,05 GB de StyleTTS 2 que no era apte per a CPU autònom. Els motors 100% autònoms i offline són **Matxa-TTS v2 (16 veus)** i **UPC FestCat Ona i Pau (63 MB i 27 MB)**.
* **Correcció d'estil lingüístic:**
  * S'ha revisat i aplicat la norma gramatical catalana de mantenir minúscula després dels dos punts (`:`) a tots els textos informatius i etiquetes de la interfície.
* **Motor predeterminat per defecte:**
  * S'ha establert **Matxa-TTS v2 multiaccent (100% offline)** com a selecció predeterminada en obrir l'aplicació.
* **Empaquetat PyInstaller per a Windows:**
  * S'ha configurat la compilació de l'executable perquè inclogui automàticament la llibreria `piper-tts`, el seu binari `espeakbridge.pyd` i les taules de dades fonètiques d'`espeak-ng` per al català i totes les seves variants territorials (`ca`, `ca-ba`, `ca-nw`, `ca-va`).
* **Verificació de qualitat:**
  * Ampliació de la suite de proves unitàries i d'integració a 10 bateries de tests (`test_features.py`), totes validades amb èxit (10/10).

---

## [1.0.1] - 2026-09-24

### ✨ Novetats
* **Pista de música o so de fons avançada:**
  * Suport per a fitxers MP3, WAV, OGG i FLAC d'acompanyament sonora.
  * Bucle automàtic continu (*loop*) amb transició suau (*cross-fade* de 20 ms) per evitar salts sobtats.
  * Control de volum dinàmic regulable de l'1% al 100% (calibrat per defecte al 15% per garantir la màxima claredat vocal).
  * Botó de prova d'escolta ràpida de la sintonia (`▶ Prova` / `■ Atura`).
  * Mescla professional amb esvaïment d'entrada (*fade-in* d'1 s) i sortida (*fade-out* de 2 s), combinada amb un limitador suau de pic per evitar saturació.
* **Pre-escalfament en segon pla (*pre-warming*):**
  * Càrrega asíncrona dels models neuronals en memòria en arrencar l'aplicació per a una resposta immediata en la primera petició de síntesi.
* **Mostres d'àudio preempaquetades (0 ms):**
  * S'han emmagatzemat arxius WAV d'escolta prèvia a `assets/previews/` per a totes les veus catalanes de Matxa-TTS, evitant càrregues innecessàries dels models pesats per provar les veus.
* **Documentació divulgativa per a docents:**
  * Creació del document `docs/FITXA_DIVULGACIO_DOCENTS.md` amb context pedagògic, aplicacions a l'aula (DUA, diversitat, varietats dialectals) i directrius ètiques per alimentar altres models de llenguatge (LLM) a xarxes socials.

---

## [1.0.0] - 2026-09-23

### 🚀 Llançament inicial
* **Estructura adaptable de locutors:**
  * Suport per a formats d'**1 veu (monòleg)**, **2 veus (diàleg)** i **3 veus (amb presentador)**.
  * Espacialització estèreo automàtica (*panning*: esquerra, centre i dreta).
* **Motor Matxa-TTS v2 multiaccent (BSC-LT):**
  * 16 veus catalanes autèntiques que cobreixen totes les grans variants territorials:
    * **Central:** Èlia, Grau, Ona, Pau.
    * **Balear:** Olga, Quim, Bernat.
    * **Valencià:** Gina, Lluc, Arnau, Berta.
    * **Nord-occidental:** Emma, Pere, Estel.
    * **Septentrional / Rossellonès:** Laura, Jordi.
* **Normalització lingüística alVoCat (Projecte AINA):**
  * Expansió automàtica de números, dates, hores, símbols, sigles i abreviatures en català.
* **Masterització d'estudi:**
  * Normalització de sonoritat d'emissió segons l'estàndard internacional **EBU R128 (-16 LUFS)**.
  * Exportació directa a fitxer **MP3 estèreo a 160 kbps CBR**.
* **Interfície d'usuari accessible:**
  * Dissenyada amb CustomTkinter seguint la paleta verda te matxa pastel (`#2E5E41`).
  * Suport per a escalat d'alta resolució DPI a Windows (100%, 125%, 150%, 175%, 200%).
  * Reproductor d'àudio integrat ancorat a la part inferior amb control de temps, volum i descàrrega.
* **Gestor de models i diagnòstic de l'equip:**
  * Diàleg visual per verificar l'espai en disc, memòria RAM, processador i GPU, i gestionar la descàrrega de components des d'Hugging Face.
* **Executable independent per a Windows:**
  * Distribució autònoma portable (`PodcastsAmbEstilIMatxa.exe`) sense necessitat d'instal·lar Python.
