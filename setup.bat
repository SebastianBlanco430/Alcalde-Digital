@echo off
echo ====================================================
echo Configurando entorno para Alcalde Digital
echo ====================================================

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no esta instalado o no se encuentra en el PATH.
    echo Por favor instala Python desde https://www.python.org/downloads/
    pause
    exit /b
)

if not exist "venv" (
    echo Creando el entorno virtual (venv)...
    python -m venv venv
) else (
    echo El entorno virtual ya existe.
)

echo Instalando/Actualizando Pygame dentro del entorno virtual...
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install pygame-ce

echo ====================================================
echo Entorno listo correctamente. 
echo ====================================================
pause