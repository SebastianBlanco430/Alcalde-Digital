#!/usr/bin/env bash
# Equivalente en macOS/Linux de setup.bat: crea el venv e instala las dependencias.

echo "===================================================="
echo "Configurando entorno para Alcalde Digital"
echo "===================================================="

cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] Python no esta instalado o no se encuentra en el PATH."
    echo "Instala Python 3.12 o superior desde https://www.python.org/downloads/"
    echo "o con Homebrew: brew install python"
    exit 1
fi

VERSION_OK='import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'

if ! python3 -c "$VERSION_OK"; then
    echo "[ERROR] La version de Python es demasiado vieja. Version detectada:"
    python3 --version
    echo "Ursina exige Python 3.12 o superior."
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "Creando el entorno virtual venv..."
    if ! python3 -m venv venv; then
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
        echo "[ERROR] El venv fue creado con una version vieja de Python:"
        ./venv/bin/python --version
        echo "Ursina exige Python 3.12 o superior."
        echo "Borra la carpeta venv a mano (rm -rf venv) y vuelve a correr setup.sh."
        exit 1
    fi
fi

echo "Actualizando pip dentro del entorno virtual..."
if ! ./venv/bin/python -m pip install --upgrade pip; then
    echo "[ERROR] No se pudo actualizar pip. Revisa tu conexion a internet."
    exit 1
fi

echo "Instalando Ursina y pytest dentro del entorno virtual..."
if ! ./venv/bin/python -m pip install ursina pytest; then
    echo "[ERROR] No se pudieron instalar ursina y pytest. Revisa tu conexion a internet."
    exit 1
fi

echo "===================================================="
echo "Entorno listo correctamente."
echo "Para correr el juego:"
echo "    ./venv/bin/python main.py"
echo "Para correr los tests:"
echo "    ./venv/bin/python -m pytest"
echo "===================================================="
