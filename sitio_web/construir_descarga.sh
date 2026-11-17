#!/usr/bin/env bash
# Construye las dos descargas en sitio_web/descargas/:
#   AlcaldeDigital-Windows.zip      (Instalar.bat + juego)
#   AlcaldeDigital-macOS-Linux.zip  (Instalar.command / instalar.sh + juego)
# Sin venv, pruebas, scripts, .blend ni la propia web. Escribe las huellas SHA-256 en descargas/SHA256.txt y en index.html
# (ids sha-win y sha-mac).
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
SITIO="$RAIZ/sitio_web"
INST="$SITIO/instaladores"
mkdir -p "$SITIO/descargas"

armar() {  # nombre-del-zip  carpeta-instalador
  local ZIP="$1" ESPECIFICO="$2" TMP DEST
  TMP="$(mktemp -d)"; DEST="$TMP/AlcaldeDigital"; mkdir -p "$DEST"
  cd "$RAIZ"
  for ruta in main.py assets backend frontend; do cp -R "$ruta" "$DEST/"; done
  find "$DEST" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
  find "$DEST" \( -name ".DS_Store" -o -name "*.pyc" -o -name ".gitkeep" \) -delete
  cp "$INST/comun/lanzar.py" "$INST/comun/requirements-juego.txt" "$DEST/"
  cp "$INST/$ESPECIFICO"/* "$DEST/"
  chmod +x "$DEST"/*.sh "$DEST"/*.command 2>/dev/null || true
  rm -f "$SITIO/descargas/$ZIP"
  (cd "$TMP" && zip -qr -X "$SITIO/descargas/$ZIP" AlcaldeDigital)
  rm -rf "$TMP"
  ls -lh "$SITIO/descargas/$ZIP" | awk '{print $5, $9}'
}

armar AlcaldeDigital-Windows.zip windows
armar AlcaldeDigital-macOS-Linux.zip unix

H_WIN="$(shasum -a 256 "$SITIO/descargas/AlcaldeDigital-Windows.zip" | cut -d' ' -f1)"
H_MAC="$(shasum -a 256 "$SITIO/descargas/AlcaldeDigital-macOS-Linux.zip" | cut -d' ' -f1)"
printf '%s  AlcaldeDigital-Windows.zip\n%s  AlcaldeDigital-macOS-Linux.zip\n' "$H_WIN" "$H_MAC" > "$SITIO/descargas/SHA256.txt"
sed -i.bak -E "s|(id=\"sha-win\">)[^<]*|\1$H_WIN|; s|(id=\"sha-mac\">)[^<]*|\1$H_MAC|" "$SITIO/index.html" && rm -f "$SITIO/index.html.bak"
rm -f "$SITIO/descargas/AlcaldeDigital-beta.zip"
echo "SHA-256 Windows: $H_WIN"
echo "SHA-256 macOS/Linux: $H_MAC"
