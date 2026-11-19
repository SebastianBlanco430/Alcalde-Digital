# Sitio web de Alcalde Digital

Página estática (HTML, CSS y un JS pequeño). Sin dependencias, sin cookies, sin rastreadores y sin peticiones externas:
la tipografía es la del propio juego (Atkinson Hyperlegible, licencia OFL, `fonts/OFL.txt`).

## Qué hay
- `index.html`, `estilos.css`, `app.js`: la página.
- `legal.html`: aviso de uso, privacidad, créditos y clasificación (borrador de `docs/SITIO_WEB_TEXTOS_LEGALES.md`).
- `img/`: capturas reales del juego en JPG (las originales en PNG están en `img/raw/`, no hace falta subirlas).
- `descargas/AlcaldeDigital-macOS.dmg` y `descargas/SHA256.txt`: la descarga de macOS (UN archivo, firmado ad-hoc, no notarizado).
  Windows (instalador `.exe`, hecho con Inno Setup, `empaquetado/instalador_windows.iss`) y Linux (`.AppImage`) los construye el workflow `.github/workflows/construir-ejecutables.yml` y se bajan de la
  última Release de GitHub (SebastianBlanco430/Alcalde-Digital). Mientras no haya Release publicada, los botones lo dicen.
- `construir_descarga.sh [ruta.dmg]`: construye (o copia) el .dmg, lo deja como `descargas/AlcaldeDigital-macOS.dmg` y escribe la huella
  SHA-256 en `SHA256.txt` y en `index.html` (`id="sha-mac"`). Con `SHA_WIN=<hex> SHA_LINUX=<hex>` también escribe `sha-win` y `sha-linux`.
  Ejecútalo SIEMPRE con el juego terminado, justo antes de publicar. El .dmg lo arma `empaquetado/construir_ejecutable.sh` (PyInstaller).
- `procesar_imagenes.sh`: convierte `img/raw/*.png` a los JPG que usa la página.

## Probarla en local
Abre `index.html` en el navegador, o `python3 -m http.server 8000` dentro de esta carpeta y entra a http://localhost:8000.

## Publicarla
Sube la carpeta (sin `img/raw/`) a cualquier alojamiento estático (GitHub Pages, Netlify, Cloudflare Pages). Antes de publicar:
1. Revisa `legal.html` con alguien que sepa de derecho: tiene puntos marcados como PENDIENTE (licencia del juego, autoría y
   licencia de los modelos 3D, sonidos y texturas; edad mínima; contacto del autor).
2. No publiques el .dmg ni la Release mientras no esté aclarada la licencia de los modelos y sonidos que llevan.
3. Confirma con tu alojamiento que no guarda registros de visitas si quieres mantener la frase «no usa cookies ni rastreadores».
4. Probado: solo el .dmg en macOS con chip Apple (arranque). No probados: el workflow de GitHub Actions, el .exe de Windows, el
   AppImage de Linux, macOS Intel y la descarga real desde Safari. Quita las marcas «(sin probar)» de `index.html` cuando funcionen.
5. Sin cuenta de pago de Apple/Microsoft el jugador verá avisos de seguridad (macOS «no se puede verificar», Windows SmartScreen):
   la página explica los pasos. Cuando haya Release, cambia en `index.html` los `href` de `dl-win` y `dl-lin` a
   `https://github.com/SebastianBlanco430/Alcalde-Digital/releases/latest/download/AlcaldeDigital-Setup-Windows.exe` (y `...Linux-x64.AppImage`)
   y quita «disponible al publicar la versión».

## Textos legales y el instalador
`empaquetado/AVISO_INSTALADOR.txt` se muestra dentro del instalador de Windows (`InfoBeforeFile`): mantenlo alineado con `legal.html`
y `docs/SITIO_WEB_TEXTOS_LEGALES.md` (v1.1, 2026-11-18). Todos son borradores pendientes de revisión legal humana; no son asesoría legal.
Pendiente de probar en Windows real: que el desinstalador conserve `~/.alcalde_digital` y que el asistente muestre el aviso.

## Obsoleto (borrar si el dueño quiere)
`instaladores/` (scripts antiguos con uv/Python, ya no se usan ni los referencia nada). Los paquetes comprimidos antiguos de `descargas/` ya se eliminaron: el dueño quiere instaladores, no descargas comprimidas.
