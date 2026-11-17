#!/usr/bin/env bash
# Instalador de Alcalde Digital para macOS y Linux. No necesita Python instalado: descarga uv (con comprobación SHA-256),
# instala con él un Python 3.13 PRIVADO del juego dentro de esta carpeta y las bibliotecas (Ursina, psutil).
set -euo pipefail
cd "$(dirname "$0")"
UV_VERSION="0.13.9"

echo
echo "==============================================="
echo " Instalador de Alcalde Digital"
echo "==============================================="
echo " Descarga todo lo que el juego necesita (incluido Python)"
echo " dentro de esta carpeta. Necesita internet. Tarda unos minutos."
echo

SO="$(uname -s)"; ARQ="$(uname -m)"
case "$SO-$ARQ" in
  Darwin-arm64)            T="aarch64-apple-darwin" ;;
  Darwin-x86_64)           T="x86_64-apple-darwin" ;;
  Linux-x86_64)            T="x86_64-unknown-linux-gnu" ;;
  Linux-aarch64|Linux-arm64) T="aarch64-unknown-linux-gnu" ;;
  *) echo "Este sistema ($SO $ARQ) no está soportado por el instalador."; exit 1 ;;
esac

for f in main.py lanzar.py requirements-juego.txt assets backend frontend; do
  [ -e "$f" ] || { echo "Falta '$f'. ¿Descomprimiste TODO el .zip?"; exit 1; }
done

HERR="$PWD/herramientas"
mkdir -p "$HERR"
BASE="https://github.com/astral-sh/uv/releases/download/$UV_VERSION"

echo "==> Descargando el instalador de Python (uv)"
curl -fL --retry 3 -o "$HERR/uv.tar.gz" "$BASE/uv-$T.tar.gz"
curl -fL --retry 3 -o "$HERR/uv.tar.gz.sha256" "$BASE/uv-$T.tar.gz.sha256"
ESPERADO="$(awk '{print tolower($1)}' "$HERR/uv.tar.gz.sha256")"
if command -v shasum >/dev/null 2>&1; then REAL="$(shasum -a 256 "$HERR/uv.tar.gz" | awk '{print $1}')"; else REAL="$(sha256sum "$HERR/uv.tar.gz" | awk '{print $1}')"; fi
if [ "$ESPERADO" != "$REAL" ]; then echo "La descarga de uv no coincide con su huella SHA-256. Vuelve a intentarlo."; exit 1; fi
tar -xzf "$HERR/uv.tar.gz" -C "$HERR" --strip-components=1
chmod +x "$HERR/uv"

export UV_PYTHON_INSTALL_DIR="$HERR/python"
export UV_CACHE_DIR="$HERR/cache"
export UV_PYTHON_PREFERENCE="only-managed"

echo "==> Instalando Python 3.13 (privado de este juego)"
"$HERR/uv" python install 3.13
echo "==> Creando el entorno del juego"
"$HERR/uv" venv --python 3.13 --clear "$PWD/entorno"
echo "==> Instalando las bibliotecas del juego (Ursina y compañía)"
"$HERR/uv" pip install --python "$PWD/entorno/bin/python" -r requirements-juego.txt

cat > jugar.sh <<'JUGAR'
#!/usr/bin/env bash
cd "$(dirname "$0")"
exec ./entorno/bin/python lanzar.py
JUGAR
cp jugar.sh Jugar.command
chmod +x jugar.sh Jugar.command

echo
echo "============================================="
echo " Alcalde Digital está instalado."
if [ "$SO" = "Darwin" ]; then
  echo " Para jugar, haz doble clic en «Jugar.command»"
  echo " (o ejecuta ./jugar.sh en la terminal)."
else
  echo " Para jugar, ejecuta ./jugar.sh"
  echo " (si no se abre la ventana, instala los controladores OpenGL de tu distribución)."
fi
echo "============================================="
