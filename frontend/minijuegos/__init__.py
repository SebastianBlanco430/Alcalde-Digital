# Marco de minijuegos de las misiones de verificar (ver backend/logica/minijuegos.py y nota 53 de la bóveda).
# Este paquete NO importa ursina al cargarse: los módulos *_calculos.py son Python puro (se prueban con pytest) y las vistas
# (rastrear.py, comparar.py, ...) se importan de forma PEREZOSA al crear el minijuego, así un fallo en una vista nunca impide
# arrancar el juego (la escena cae al minijuego de siempre).
#
# INTERFAZ COMÚN de un minijuego (frontend/minijuegos/base.py::Minijuego):
#     empezar(contexto) -> None      # contexto: dict con "caso" (preparado), "mision", "al_terminar", "azar"
#     input(tecla) / update()        # los reenvía la escena
#     al terminar llama contexto["al_terminar"](ResultadoMinijuego)  (UNA sola vez)
#     el resultado es de backend.logica.minijuegos.ResultadoMinijuego (aciertos, total, completado, bien)

import importlib

from backend.logica import minijuegos as mj

# id -> (módulo de la vista, nombre de la clase). Registro de datos: añadir un minijuego = una línea aquí + su caso en
# backend/datos/minijuegos_casos.py + su fila en backend/datos/minijuegos_asignacion.py.
REGISTRO = {
    mj.RASTREAR: ("frontend.minijuegos.rastrear", "MinijuegoRastrear"),
    mj.COMPARAR: ("frontend.minijuegos.comparar", "MinijuegoComparar"),
    mj.CRONOLOGIA: ("frontend.minijuegos.cronologia", "MinijuegoCronologia"),
    mj.CHAT: ("frontend.minijuegos.chat", "MinijuegoChat"),
    mj.SENALES: ("frontend.minijuegos.senales", "MinijuegoSenales"),
    mj.CONTRARRELOJ: ("frontend.minijuegos.contrarreloj", "MinijuegoContrarreloj"),
}


def clase_de(minijuego_id):
    """Clase de la vista del minijuego (import perezoso). KeyError si el id no está registrado."""
    modulo, nombre = REGISTRO[minijuego_id]
    return getattr(importlib.import_module(modulo), nombre)


def ids_registrados():
    return tuple(REGISTRO)
