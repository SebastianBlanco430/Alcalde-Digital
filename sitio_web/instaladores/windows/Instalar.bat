@echo off
chcp 65001 >nul
title Instalador de Alcalde Digital
cd /d "%~dp0"
echo.
echo  ===============================================
echo   Instalador de Alcalde Digital
echo  ===============================================
echo   Descarga e instala todo lo que el juego necesita
echo   (incluido Python, en una carpeta privada del juego).
echo   Necesita internet. Tarda unos minutos.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1"
echo.
pause
