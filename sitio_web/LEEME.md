# Sitio web de Alcalde Digital

Página estática (HTML, CSS y un JS pequeño). Sin dependencias, sin cookies, sin rastreadores y sin peticiones externas:
la tipografía es la del propio juego (Atkinson Hyperlegible, licencia OFL, `fonts/OFL.txt`).

## Qué hay
- `index.html`, `estilos.css`, `app.js`: la página.
- `legal.html`: aviso de uso, privacidad, créditos y clasificación (borrador de `docs/SITIO_WEB_TEXTOS_LEGALES.md`).
- `img/`: capturas reales del juego en JPG (las originales en PNG están en `img/raw/`, no hace falta subirlas).
- `descargas/AlcaldeDigital-Windows.zip`, `descargas/AlcaldeDigital-macOS-Linux.zip` y `descargas/SHA256.txt`: las descargas.
- `instaladores/`: lo que lleva cada .zip además del juego. El jugador NO necesita tener Python: los instaladores (`windows/Instalar.bat` +
  `instalar.ps1`, `unix/instalar.sh` + `Instalar.command`) descargan `uv` (versión fijada, con comprobación SHA-256), que instala un Python 3.13
  privado del juego y las bibliotecas de `comun/requirements-juego.txt`. `comun/lanzar.py` arranca el juego (y guarda un registro si no hay consola).
- `construir_descarga.sh`: reconstruye los dos .zip desde el código del juego y reescribe las huellas SHA-256 en `index.html`
  (`id="sha-win"` y `id="sha-mac"`) y en `descargas/SHA256.txt`. Ejecútalo SIEMPRE después de cambiar el juego o los instaladores.
- `procesar_imagenes.sh`: convierte `img/raw/*.png` a los JPG que usa la página.
- `LEEME_PRIMERO.txt`: lo que lleva dentro el .zip.

## Probarla en local
Abre `index.html` en el navegador, o `python3 -m http.server 8000` dentro de esta carpeta y entra a http://localhost:8000.

## Publicarla
Sube la carpeta (sin `img/raw/`) a cualquier alojamiento estático (GitHub Pages, Netlify, Cloudflare Pages). Antes de publicar:
1. Revisa `legal.html` con alguien que sepa de derecho: tiene puntos marcados como PENDIENTE (licencia del juego, autoría y
   licencia de los modelos 3D, sonidos y texturas; edad mínima; contacto del autor).
2. No publiques los .zip mientras no esté aclarada la licencia de los modelos y sonidos que llevan.
3. Confirma con tu alojamiento que no guarda registros de visitas si quieres mantener la frase «no usa cookies ni rastreadores».
4. Probado de punta a punta: solo el instalador de macOS (en un entorno limpio). El de Windows (PowerShell) y el de Linux no se han podido probar:
   pruébalos en un Windows y un Linux reales y quita las marcas «(sin probar)» de `index.html` cuando funcionen.
5. Los instaladores descargan `uv` de GitHub (astral-sh/uv, versión 0.13.9) y Python y las bibliotecas de internet: la web lo dice.
