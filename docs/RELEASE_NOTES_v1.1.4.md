## Pòdcasts amb Matxa v1.1.4

### Actualització automàtica corregida

- El comprovador contrasta la versió instal·lada amb l'última release publicada a GitHub, no amb els darrers commits.
- Descarrega exactament el paquet Windows de la nova versió. Si la release no té el ZIP corresponent, mostra l'error en lloc de tornar a descarregar una versió antiga.
- Valida l'arxiu ZIP i les mostres de Joana i Enric abans de preparar la instal·lació.
- En confirmar el reinici, un procés extern espera que l'aplicació es tanqui. Després actualitza els fitxers, en comprova la integritat i reinicia l'executable nou.
- Manté els models descarregats i les dades locals. Si l'actualització falla, mostra un missatge i deixa un registre al directori temporal.

### Correccions que inclou

Manté les correccions de la v1.1.3: mostres de Joana i Enric, compatibilitat amb Edge TTS 7.3.1 o posterior, detecció de silencis i visualització d'errors de síntesi.

### Instal·lació a Windows

1. Descarrega PodcastsAmbMatxa-v1.1.4-Windows.zip des de la secció Assets d'aquesta release.
2. Descomprimeix-lo en una carpeta pròpia i executa PodcastsAmbMatxa.exe.
3. Per conservar els models descarregats anteriorment, no esborris la carpeta models de la instal·lació anterior.

**Important:** si l'actualitzador de la v1.1.2 o v1.1.3 falla, cal fer una actualització manual una vegada. El codi defectuós de l'actualitzador antic no es pot reparar des del servidor.

**Signatura:** els executables encara no tenen signatura digital SignPath.
