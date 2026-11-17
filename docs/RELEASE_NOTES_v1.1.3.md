## Pòdcasts amb Matxa v1.1.3

### Correccions de les veus neuronals
- **Mostres Joana i Enric:** es torna a trobar i reproduir l'àudio WAV preenregistrat. Les mostres d'aquestes veus no requereixen connexió.
- **Veus neuronals ca-ES (Online):** s'actualitza la dependència a `edge-tts >= 7.3.1` per incorporar el protocol de Microsoft de l'octubre de 2026.
- **Errors de síntesi visibles:** ja no es generen pòdcasts silenciosos com si fossin correctes quan falla el servei. L'aplicació mostra l'error per poder corregir-lo o escollir un motor local.
- **Mostres silencioses:** es rebutgen les respostes d'àudio sense veu i s'evita guardar-les a la memòria cau.
- **Gestió d'errors:** es corregeix el pas d'excepcions entre el fil de generació i la interfície.

### Qualitat i compatibilitat
- Proves de regressió per als WAV de Joana i Enric, la detecció de mostres silencioses i els errors del servei Edge TTS.
- Es manté el funcionament de Matxa-TTS v2 i UPC FestCat (Ona i Pau) sense canvis funcionals.
- Les mostres preenregistrades funcionen sense xarxa; la síntesi de veus Microsoft Neural continua requerint connexió a Internet.

### Instal·lació (Windows)
1. Descarregueu `PodcastsAmbMatxa-v1.1.3-Windows.zip` a la secció *Assets* d'aquesta release.
2. Descomprimiu el ZIP complet i executeu `PodcastsAmbMatxa.exe`.
3. Els models locals opcionals es poden descarregar des del botó **Models** de l'aplicació.

**Nota:** l'executable encara no té signatura digital SignPath. La síntesi neuronal al núvol depèn de la disponibilitat del servei Microsoft i no disposa de garantia de servei.
