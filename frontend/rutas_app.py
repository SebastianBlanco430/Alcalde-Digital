"""Rutas y arranque en modo congelado (PyInstaller). Sin congelar no hace nada: el juego se comporta como siempre.

Recursos: los módulos ya usan Path(__file__).parent[.parent] / "assets"|"backend"; PyInstaller reproduce esa estructura
dentro de sys._MEIPASS, así que NO hace falta cambiar ninguna ruta de recursos. Guardado: sigue en ~/.alcalde_digital
(o $ALCALDE_AJUSTES_DIR), carpeta de usuario escribible; nunca se escribe dentro del paquete (en onefile es temporal).
"""
import os
import sys
from pathlib import Path


def congelado():
    return bool(getattr(sys, "frozen", False))


def carpeta_recursos():
    """Raíz que contiene assets/ y backend/ (la carpeta del proyecto, o sys._MEIPASS si está congelado)."""
    if congelado():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent


def carpeta_datos_usuario():
    elegido = os.environ.get("ALCALDE_AJUSTES_DIR")
    return Path(elegido) if elegido else Path.home() / ".alcalde_digital"


TOPE_REGISTRO = 2 * 1024 * 1024  # bytes; el registro se reabre vacio en cada arranque (O_TRUNC)


class _RegistroLimitado:
    """Escribe en registro.txt hasta TOPE_REGISTRO bytes y descarta el resto."""

    def __init__(self, fd, tope=TOPE_REGISTRO):
        self._f = os.fdopen(fd, "w", encoding="utf-8", buffering=1)
        self._restante = tope

    def write(self, texto):
        if self._restante <= 0 or not texto:
            return len(texto or "")
        corte = texto[: self._restante]
        self._restante -= len(corte.encode("utf-8"))
        self._f.write(corte)
        return len(texto)

    def flush(self):
        self._f.flush()

    def isatty(self):
        return False


def abrir_registro(ruta):
    """Abre el registro sin seguir enlaces simbolicos, solo para el dueno (0600) y con tamano limitado."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    return _RegistroLimitado(os.open(ruta, flags, 0o600))


def preparar():
    """Llamar la primera línea de main.py. Congelado: si no hay consola (app de doble clic, Windows
    sin consola), stdout/stderr van a registro.txt para poder diagnosticar un fallo."""
    if not congelado():
        return
    # NO hacer os.chdir aquí: ursina/application.py calcula asset_folder con Path(sys.argv[0]).parent (relativo) al importarse.
    desde_app = ".app/Contents/MacOS" in sys.executable and not os.environ.get("ALCALDE_CONSOLA")
    if sys.stdout is None or sys.stderr is None or desde_app:
        try:
            datos = carpeta_datos_usuario()
            datos.mkdir(parents=True, exist_ok=True)
            registro = abrir_registro(datos / "registro.txt")
            sys.stdout = sys.stderr = registro
        except OSError:
            pass
