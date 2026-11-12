# Lógica pura (sin Ursina) de la skin del jugador en el parkour: interruptor de reversión, rol a mostrar y la
# velocidad/estado en el aire que el modelo necesita para elegir clip. Lo usa frontend/parkour_vista.py.

import math
import os

ROL_SIN_PARTIDA = "ciudadano"     # prueba de desarrollo (ALCALDE_PARKOUR=... sin partida): no hay jugador activo
ENTORNO_SKIN = "ALCALDE_PARKOUR_SKIN"


# ALCALDE_PARKOUR_SKIN=0 (o no/false/off) devuelve el muñeco de cubos de siempre.
def skin_activa(entorno=None):
    entorno = os.environ if entorno is None else entorno
    return str(entorno.get(ENTORNO_SKIN, "1")).strip().lower() not in ("0", "no", "false", "off")


# (nombre, rol) de la skin a mostrar para `jugador` (cualquier objeto con .nombre y .rol, o None).
def datos_de_skin(jugador):
    rol = getattr(jugador, "rol", None) or ROL_SIN_PARTIDA
    nombre = getattr(jugador, "nombre", None) or "Jugador"
    return str(nombre), str(rol)


# Velocidad horizontal real (m/s) entre dos posiciones; `arrastre` = (dx, dz) que movió la plataforma móvil bajo
# los pies en ese paso (no es marcha del jugador, así que se descuenta).
def velocidad_horizontal(x0, z0, x1, z1, dt, arrastre=(0.0, 0.0)):
    if dt <= 1e-6:
        return 0.0
    return math.hypot(x1 - x0 - arrastre[0], z1 - z0 - arrastre[1]) / dt
