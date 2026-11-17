"""Lanzador de Alcalde Digital. Arranca el juego desde cualquier carpeta y, cuando no hay consola (Windows con pythonw),
guarda lo que el juego escribiría en ella en ~/.alcalde_digital/registro.txt para poder diagnosticar un fallo."""
import os
import runpy
import sys
import traceback
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
os.chdir(CARPETA)
sys.path.insert(0, str(CARPETA))

if sys.stdout is None or sys.stderr is None:          # pythonw: sin consola
    datos = Path.home() / ".alcalde_digital"
    datos.mkdir(parents=True, exist_ok=True)
    registro = open(datos / "registro.txt", "w", encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or registro
    sys.stderr = sys.stderr or registro

try:
    runpy.run_path(str(CARPETA / "main.py"), run_name="__main__")
except SystemExit:
    raise
except BaseException:
    traceback.print_exc()
    raise
