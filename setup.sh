#!/usr/bin/env bash
# Equivalente en macOS/Linux de setup.bat: crea el venv e instala las dependencias.

echo "===================================================="
echo "Configurando entorno para Alcalde Digital"
echo "===================================================="

cd "$(dirname "$0")" || exit 1

# Ursina 8.3.0 exige Python 3.12+ y panda3d solo publica ruedas hasta 3.14:
# se busca un interprete 3.12 a 3.14 en vez de fiarse de lo que sea "python3".
VERSION_OK='import sys; sys.exit(0 if (3, 12) <= sys.version_info[:2] < (3, 15) else 1)'

PY=""
for candidato in python3.14 python3.13 python3.12 python3; do
    if command -v "$candidato" >/dev/null 2>&1 && "$candidato" -c "$VERSION_OK" 2>/dev/null; then
        PY="$candidato"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "[ERROR] No se encontro Python 3.12, 3.13 ni 3.14."
    echo "Ursina 8.3.0 exige Python 3.12 o superior y panda3d aun no publica"
    echo "ruedas para Python 3.15, asi que esa version tampoco sirve."
    echo "Instala Python 3.12 a 3.14 desde https://www.python.org/downloads/"
    echo "o con Homebrew: brew install python@3.13"
    exit 1
fi

echo "Usando el interprete: $PY ($("$PY" --version))"

if [ ! -d "venv" ]; then
    echo "Creando el entorno virtual venv..."
    if ! "$PY" -m venv venv; then
        echo "[ERROR] No se pudo crear el entorno virtual."
        exit 1
    fi
else
    echo "El entorno virtual ya existe. Verificando su version de Python..."
    if [ ! -x "./venv/bin/python" ]; then
        echo "[ERROR] La carpeta venv existe pero esta danada (o es de Windows): falta venv/bin/python."
        echo "Borra la carpeta venv a mano (rm -rf venv) y vuelve a correr setup.sh."
        exit 1
    fi
    if ! ./venv/bin/python -c "$VERSION_OK"; then
        echo "[ERROR] El venv existente usa una version de Python no compatible:"
        ./venv/bin/python --version
        echo "Hace falta Python 3.12 a 3.14."
        echo "Borra la carpeta venv a mano (rm -rf venv) y vuelve a correr setup.sh."
        exit 1
    fi
fi

echo "Actualizando pip dentro del entorno virtual..."
if ! ./venv/bin/python -m pip install --upgrade pip; then
    echo "[ERROR] No se pudo actualizar pip. Revisa tu conexion a internet."
    exit 1
fi

echo "Instalando dependencias de requirements.txt dentro del entorno virtual..."
if ! ./venv/bin/python -m pip install -r requirements.txt; then
    echo "[ERROR] No se pudieron instalar las dependencias de requirements.txt. Revisa tu conexion a internet."
    exit 1
fi

echo "===================================================="
echo "Entorno listo correctamente."
echo "Para correr el juego:"
echo "    ./venv/bin/python main.py"
echo "Para correr los tests:"
echo "    ./venv/bin/python -m pytest"
echo "===================================================="
