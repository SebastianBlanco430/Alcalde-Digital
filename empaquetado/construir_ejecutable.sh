#!/usr/bin/env bash
# Construye en macOS el instalador de UN SOLO ARCHIVO de Alcalde Digital: AlcaldeDigital-macOS-<arch>.dmg (+ .sha256).
# Uso: empaquetado/construir_ejecutable.sh [onefile]   (con "onefile" ademas deja el binario suelto, para pruebas)
# Reproducible: venv nuevo en $TMPDIR del build, versiones fijadas, no toca el venv del proyecto. Requiere Python 3.14 (python.org).
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"; export ALCALDE_RAIZ="$(cd "$AQUI/.." && pwd)"
PYTHON="${PYTHON:-python3.14}"; PYINSTALLER_VERSION="${PYINSTALLER_VERSION:-6.22.3}"
SALIDA="${SALIDA:-$ALCALDE_RAIZ/dist-ejecutable}"; BUILD="$(mktemp -d)"; ARCH="$(uname -m)"
trap 'rm -rf "$BUILD"' EXIT
[ -n "$SALIDA" ] || { echo "SALIDA vacio" >&2; exit 1; }
mkdir -p "$SALIDA"
"$PYTHON" -m venv "$BUILD/venv"
"$BUILD/venv/bin/pip" install -q --upgrade pip
"$BUILD/venv/bin/pip" install -q -r "$ALCALDE_RAIZ/requirements.txt" "pyinstaller==$PYINSTALLER_VERSION"
cd "$BUILD"
ALCALDE_MODO=onedir "$BUILD/venv/bin/pyinstaller" --noconfirm --distpath "$BUILD/dist" --workpath "$BUILD/work" "$AQUI/alcalde.spec"
APP="$BUILD/dist/AlcaldeDigital.app"
# Firma ad-hoc (sin cuenta de pago): NO sustituye a la notarizacion; solo hace valido el sello de codigo en Apple Silicon.
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"
DMG="$SALIDA/AlcaldeDigital-macOS-$ARCH.dmg"; rm -f "$DMG"
ESCENA="$BUILD/dmg"; mkdir -p "$ESCENA"; cp -R "$APP" "$ESCENA/"; ln -s /Applications "$ESCENA/Applications"
hdiutil create -quiet -volname "Alcalde Digital" -srcfolder "$ESCENA" -format UDZO -ov "$DMG"
if [ "${1:-}" = "onefile" ]; then
  ALCALDE_MODO=onefile "$BUILD/venv/bin/pyinstaller" --noconfirm --distpath "$SALIDA/onefile" --workpath "$BUILD/work1" "$AQUI/alcalde.spec"
fi
( cd "$SALIDA" && shasum -a 256 "$(basename "$DMG")" | tee "$(basename "$DMG").sha256" )
ls -lh "$DMG" | awk '{print $5, $9}'
