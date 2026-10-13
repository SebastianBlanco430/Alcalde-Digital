@echo off
setlocal
cd /d "%~dp0"
echo ====================================================
echo Configurando entorno para Alcalde Digital
echo ====================================================

rem Ursina 8.3.0 exige Python 3.12 o superior y panda3d solo publica ruedas hasta 3.14.
rem Por eso se busca un interprete 3.12 a 3.14 (lanzador py y luego python) en vez de
rem fiarse de lo que sea que apunte "python" en el PATH.
set "VERSION_OK=import sys; sys.exit(0 if (3, 12) <= sys.version_info[:2] < (3, 15) else 1)"
set "PY="

for %%V in (3.14 3.13 3.12) do (
    if not defined PY (
        py -%%V -c "import sys" >nul 2>&1
        if not errorlevel 1 set "PY=py -%%V"
    )
)

if not defined PY (
    python -c "%VERSION_OK%" >nul 2>&1
    if not errorlevel 1 set "PY=python"
)

if not defined PY goto :sin_python

echo Usando el interprete: %PY%
%PY% --version

if not exist "venv" goto :crear_venv

echo El entorno virtual ya existe. Verificando su version de Python...
if not exist ".\venv\Scripts\python.exe" goto :venv_danado
.\venv\Scripts\python.exe -c "%VERSION_OK%" >nul 2>&1
if errorlevel 1 goto :venv_viejo
goto :instalar

:crear_venv
echo Creando el entorno virtual venv...
%PY% -m venv venv
if errorlevel 1 goto :venv_fallo
goto :instalar

:instalar
echo Actualizando pip dentro del entorno virtual...
.\venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :pip_fallo

echo Instalando dependencias de requirements.txt dentro del entorno virtual...
.\venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :deps_fallo

echo ====================================================
echo Entorno listo correctamente.
echo Para correr el juego:
echo     .\venv\Scripts\python.exe main.py
echo Para correr los tests:
echo     .\venv\Scripts\python.exe -m pytest
echo ====================================================
set "CODIGO=0"
goto :fin

:sin_python
echo [ERROR] No se encontro Python 3.12, 3.13 ni 3.14.
echo Ursina 8.3.0 exige Python 3.12 o superior, y panda3d aun no publica
echo ruedas para Python 3.15, asi que esa version tampoco sirve.
echo Interpretes que ve el lanzador de Windows:
py -0p 2>nul
echo Instala Python 3.13 desde https://www.python.org/downloads/
echo o con: winget install Python.Python.3.13
echo Luego vuelve a correr setup.bat.
set "CODIGO=1"
goto :fin

:venv_danado
echo [ERROR] La carpeta venv existe pero esta danada: falta venv\Scripts\python.exe.
echo Borra la carpeta venv a mano y vuelve a correr setup.bat.
set "CODIGO=1"
goto :fin

:venv_viejo
echo [ERROR] El venv existente usa una version de Python no compatible:
.\venv\Scripts\python.exe --version
echo Hace falta Python 3.12 a 3.14.
echo Borra la carpeta venv a mano y vuelve a correr setup.bat.
set "CODIGO=1"
goto :fin

:venv_fallo
echo [ERROR] No se pudo crear el entorno virtual.
set "CODIGO=1"
goto :fin

:pip_fallo
echo [ERROR] No se pudo actualizar pip. Revisa tu conexion a internet.
set "CODIGO=1"
goto :fin

:deps_fallo
echo [ERROR] No se pudieron instalar las dependencias de requirements.txt.
echo Revisa tu conexion a internet.
set "CODIGO=1"
goto :fin

:fin
pause
exit /b %CODIGO%
