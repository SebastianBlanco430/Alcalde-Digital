@echo off
echo ====================================================
echo Configurando entorno para Alcalde Digital
echo ====================================================

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado o no se encuentra en el PATH.
    echo Por favor instala Python 3.12 o superior desde https://www.python.org/downloads/
    pause
    exit /b 1
)

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"
if errorlevel 1 (
    echo [ERROR] La version de Python es demasiado vieja. Version detectada:
    python --version
    echo Ursina exige Python 3.12 o superior.
    echo Descarga una version reciente desde https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist "venv" (
    echo Creando el entorno virtual venv...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
) else (
    echo El entorno virtual ya existe. Verificando su version de Python...
    if not exist ".\venv\Scripts\python.exe" (
        echo [ERROR] La carpeta venv existe pero esta danada: falta venv\Scripts\python.exe.
        echo Borra la carpeta venv a mano y vuelve a correr setup.bat.
        pause
        exit /b 1
    )
    .\venv\Scripts\python.exe -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"
    if errorlevel 1 (
        echo [ERROR] El venv fue creado con una version vieja de Python:
        .\venv\Scripts\python.exe --version
        echo Ursina exige Python 3.12 o superior.
        echo Borra la carpeta venv a mano y vuelve a correr setup.bat.
        pause
        exit /b 1
    )
)

echo Actualizando pip dentro del entorno virtual...
.\venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] No se pudo actualizar pip. Revisa tu conexion a internet.
    pause
    exit /b 1
)

echo Instalando Ursina y pytest dentro del entorno virtual...
.\venv\Scripts\python.exe -m pip install ursina pytest
if errorlevel 1 (
    echo [ERROR] No se pudieron instalar ursina y pytest. Revisa tu conexion a internet.
    pause
    exit /b 1
)

echo ====================================================
echo Entorno listo correctamente.
echo Para correr el juego:
echo     .\venv\Scripts\python.exe main.py
echo Para correr los tests:
echo     .\venv\Scripts\python.exe -m pytest
echo ====================================================
pause
exit /b 0
