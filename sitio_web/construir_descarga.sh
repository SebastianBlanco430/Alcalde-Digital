#!/usr/bin/env bash
# Prepara la descarga de macOS (UN archivo: .dmg) en sitio_web/descargas/ y escribe su huella SHA-256.
# Uso: sitio_web/construir_descarga.sh [ruta-al-.dmg]
#   Sin argumento construye el .dmg con empaquetado/construir_ejecutable.sh (hace falta Python 3.14 y toca internet).
#   Con argumento usa ese .dmg ya construido (p. ej. dist-ejecutable/AlcaldeDigital-macOS-arm64.dmg).
# Escribe: descargas/AlcaldeDigital-macOS.dmg, descargas/SHA256.txt y la huella en index.html (id="sha-mac").
# Windows (instalador .exe) y Linux (.AppImage) NO se construyen aqui: los produce el workflow de GitHub Actions y se descargan de la
# Release. Sus huellas (ids sha-win y sha-linux) se pasan como variables: SHA_WIN=<hex> SHA_LINUX=<hex> sitio_web/construir_descarga.sh
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
SITIO="$RAIZ/sitio_web"
DESTINO="$SITIO/descargas"
mkdir -p "$DESTINO"
for v in SHA_WIN SHA_LINUX; do
  if [ -n "${!v:-}" ] && ! [[ "${!v}" =~ ^[0-9a-f]{64}$ ]]; then echo "$v no es un SHA-256 valido (64 hex en minuscula)" >&2; exit 1; fi
done

if [ $# -ge 1 ]; then
  DMG="$1"
else
  SALIDA="$RAIZ/dist-ejecutable" "$RAIZ/empaquetado/construir_ejecutable.sh"
  DMG="$RAIZ/dist-ejecutable/AlcaldeDigital-macOS-$(uname -m).dmg"
fi
[ -f "$DMG" ] || { echo "No existe el .dmg: $DMG" >&2; exit 1; }

cp "$DMG" "$DESTINO/AlcaldeDigital-macOS.dmg"
H_MAC="$(shasum -a 256 "$DESTINO/AlcaldeDigital-macOS.dmg" | cut -d' ' -f1)"
{ printf '%s  AlcaldeDigital-macOS.dmg\n' "$H_MAC"
  [ -n "${SHA_WIN:-}" ] && printf '%s  AlcaldeDigital-Setup-Windows.exe\n' "$SHA_WIN"
  [ -n "${SHA_LINUX:-}" ] && printf '%s  AlcaldeDigital-Linux-x64.AppImage\n' "$SHA_LINUX"
} > "$DESTINO/SHA256.txt"

poner() {  # id valor
  sed -i.bak -E "s|(id=\"$1\">)[^<]*|\1$2|" "$SITIO/index.html" && rm -f "$SITIO/index.html.bak"
}
poner sha-mac "$H_MAC"
[ -n "${SHA_WIN:-}" ] && poner sha-win "$SHA_WIN"
[ -n "${SHA_LINUX:-}" ] && poner sha-linux "$SHA_LINUX"
ls -lh "$DESTINO/AlcaldeDigital-macOS.dmg" | awk '{print $5, $9}'
echo "SHA-256 macOS: $H_MAC"
