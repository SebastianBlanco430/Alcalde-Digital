# Narradora y Rádio Comunitária con voz

El prólogo, los tres finales animados y la Rádio Comunitária tienen voz. Son **audios pregenerados** (no hay voz en
tiempo real ni red): el juego busca el audio **por el texto** del subtítulo o de la línea de radio y lo reproduce.

| Voz | Dónde suena | Textos |
|---|---|---|
| Narradora | Prólogo (planos y cartelas) y finales animados (bueno, neutro, malo y el plano de cada rol) | `backend/datos/prologo_cinematica.json`, `backend/datos/finales_historia.json` → `animacion` |
| Jandira Lopes (locutora) | Emisión 3D de la Rádio Comunitária (mañana, noche y puente del día 7) | `backend/datos/radio_textos.json` → `manana`, `noche`, `puente` |

## Banderas (plan B)

| Variable | Por defecto | Con `=0` |
|---|---|---|
| `ALCALDE_NARRADOR` | encendida | **Todo como antes**: sin voz, mismas duraciones de planos, cartelas y líneas de radio |
| `ALCALDE_NARRADOR_RADIO` | encendida | Solo la radio queda sin voz (y con sus tiempos de antes); la narradora sigue |
| `ALCALDE_NARRADOR_ATENUAR` | encendida | La música no baja mientras habla la voz |

```powershell
$env:ALCALDE_NARRADOR="0"; .\venv\Scripts\python.exe main.py
```

## Archivos

- `assets/voz/narradora/*.ogg` (66) y `assets/voz/radio/*.ogg` (64): mono, normalizados a −16 LUFS; la radio lleva un
  EQ suave de emisora. En total ≈ 5,5 MB.
- `assets/voz/indice.json`: `{"voces": {texto: {"archivo", "segundos", "voz", "bloque"}}}`. La clave es el texto del
  juego con los espacios normalizados.
- `frontend/narrador_calculos.py` (puro, sin Ursina): banderas, búsqueda en el índice y tiempos.
- `frontend/narrador.py`: el reproductor. `decir(texto, radio=False)`, `callar()`, `hablando()`. Canal propio (un
  `AudioManager` aparte de música y efectos) con el volumen maestro del juego; mudo si el juego está silenciado.
  Mientras habla, la música baja al 35 % con una rampa de 0,3 s y vuelve al terminar. Nunca lanza.

## Cómo cambia los tiempos

- **Planos** del prólogo y de los finales: el plano dura lo de siempre o, si no cabe, lo justo para sus voces
  (`segundos_plano`); cada subtítulo dura lo que dura su voz (`reparto_con_voz`) en lugar de repartirse por el largo del
  texto. La voz arranca cuando aparece su subtítulo.
- **Cartelas** del prólogo: `max(tiempo de lectura, entrada + voz + salida)`.
- **Radio**: cada línea dura `max(tiempo de lectura, voz + 0,6 s)`. Adelantar una línea corta la voz y suena la
  siguiente; saltar la emisión la corta.
- Saltar (mantener Espacio/Escape o el mando), cerrar o un fallo cortan la voz.

## Si se cambia un texto

Una frase editada en el JSON ya no coincide con el índice: **sale muda**, con su subtítulo y su tiempo de lectura de
siempre (no rompe nada). `tests/test_narrador_calculos.py` avisa de qué frases no tienen voz:

```powershell
.\venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_narrador_calculos.py
```

## Cómo regenerar

El generador y los mp3 originales están **fuera del repositorio** (carpeta `voz\` junto al repo). Usa ElevenLabs
(modelo Eleven v3) con dos voces diseñadas para el proyecto: «Alcalde Digital - Narradora» y «Alcalde Digital - Jandira
(radio)».

1. La clave de la API va **solo en la terminal** (nunca en un archivo del repo):
   ```powershell
   $env:ELEVENLABS_API_KEY = "<clave>"
   python generar_voces_elevenlabs.py --prueba                      # 4 frases para escuchar
   python generar_voces_elevenlabs.py                               # solo genera las que falten
   python generar_voces_elevenlabs.py --rehacer "texto exacto"      # repite una frase
   ```
2. Convertir los mp3 a `.ogg` mono a −16 LUFS (la radio, además, con el EQ de emisora), copiarlos a
   `assets/voz/narradora/` y `assets/voz/radio/` y actualizar `assets/voz/indice.json` con el archivo y los segundos de
   cada frase.
3. Correr el test de arriba: tiene que quedar sin frases mudas, sin audios huérfanos y con las duraciones del índice
   iguales a las de los archivos.

El léxico de pronunciación (nombres en portugués) y las etiquetas de actuación están en el propio generador.

## En línea

Cada equipo reproduce su audio en local. No cambia el protocolo ni la huella: los audios y el índice no entran en ella.

## Licencia

Ver `docs/AVISOS_LEGALES_Y_ACTIVOS.md` §11.
