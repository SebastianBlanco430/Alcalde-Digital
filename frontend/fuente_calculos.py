# Colisión de la fuente de la Praça da Sé (Python puro: NO importa ursina).
#
# La fuente (frontend/props_mundo.fuente) se dejó sin cuerpo el 2026-11-13 porque está en el centro de la plaza, donde se
# cruzan las calles: los peatones decorativos y la multitud del mapa grande van de centro de plaza en centro de plaza.
# Desde 2026-11-15 (petición del usuario) es sólida para el jugador y los vehículos: un círculo del radio del borde de
# piedra que la ciudad 3D entrega a MundoCiudad.agregar_obstaculos con su propio origen («fuente»). Para que la gente que
# pasea no la atraviese, su posición DIBUJADA se aparta al borde (apartar_de_circulos): su recorrido lógico no cambia
# (el mismo azar, las mismas pausas), solo rodean el pilón por fuera en lugar de cruzarlo.
# La plaza mide 9 m de radio y las misiones llegan al entrar en ella, así que ninguna llegada queda tapada.
# ALCALDE_COLISION_FUENTE=0 la deja atravesable como antes (y la gente vuelve a cruzarla).

import math
import os

from backend.logica.mundo_ciudad import Obstaculo

COLISION_FUENTE = True
ORIGEN_FUENTE = "fuente"
RADIO_FUENTE = 2.05          # m (con tam 1): el borde de piedra mide 4,0 de diámetro; la losa de 4,5 es un escalón de 12 cm
MARGEN_RODEO = 0.35          # m: medio cuerpo de un peatón, para que el borde no le atraviese las piernas


def colision_fuente_activa():
    valor = os.environ.get("ALCALDE_COLISION_FUENTE", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(COLISION_FUENTE)


# Círculo de colisión de cada prop de tipo «fuente» (lista de props_mundo.Prop).
def obstaculos_fuente(props):
    return [Obstaculo("fuente", prop.x, prop.z, radio=round(RADIO_FUENTE * prop.tam, 3))
            for prop in props if prop.tipo == "fuente"]


# [(cx, cz, radio)] que la gente dibujada tiene que rodear: las fuentes ya entregadas al mundo, más el margen del cuerpo.
# Vacío sin bandera o si el mundo no sabe de obstáculos extra (mapa 2D, pruebas).
def circulos_fuente(mundo):
    if not colision_fuente_activa():
        return []
    extra = getattr(mundo, "obstaculos_extra", None)
    if not callable(extra):
        return []
    return [(o.cx, o.cz, o.radio + MARGEN_RODEO) for o in extra(ORIGEN_FUENTE) if o.es_circulo]


# (x, z) fuera de todos los círculos: un punto dentro se lleva al borde por el radio que pasa por él (continuo: un tramo
# recto que cruza el círculo se dibuja por el arco del borde). El centro exacto sale hacia +x.
def apartar_de_circulos(x, z, circulos):
    for cx, cz, radio in circulos:
        dx, dz = x - cx, z - cz
        distancia = math.hypot(dx, dz)
        if distancia >= radio:
            continue
        if distancia < 1e-9:
            dx, dz, distancia = 1.0, 0.0, 1.0
        x, z = cx + dx / distancia * radio, cz + dz / distancia * radio
    return x, z


# RODEO DEL JUGADOR (RODEAR_FUENTE): el movimiento de siempre (navegacion.mover_con_colisiones) desliza por los ejes x/z;
# contra un círculo grande, yendo de frente (como al seguir la línea del GPS, que cruza el centro de la plaza), las tres
# pruebas chocan y el jugador se queda clavado. Solo en ese caso y solo contra la fuente, se prueba el mismo paso a lo
# largo de la tangente del borde (hacia el lado al que ya apunta el paso o, de frente exacto, hacia la derecha de quien
# camina): rodea el pilón sin soltar W. Cualquier otro obstáculo sigue igual. ALCALDE_RODEAR_FUENTE=0 lo apaga.
RODEAR_FUENTE = True


def rodear_fuente_activo():
    valor = os.environ.get("ALCALDE_RODEAR_FUENTE", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return colision_fuente_activa()
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(RODEAR_FUENTE) and colision_fuente_activa()


# (x, z) tras rodear la fuente con el paso (dx, dz), o None si no aplica (no hay fuente pegada o el rodeo también choca).
# `mundo`: MundoCiudad (obstaculos_extra, es_transitable, radio_jugador).
def rodear_fuente(mundo, x, z, dx, dz):
    largo = math.hypot(dx, dz)
    extra = getattr(mundo, "obstaculos_extra", None)
    if largo < 1e-9 or not callable(extra) or not rodear_fuente_activo():
        return None
    margen = getattr(mundo, "radio_jugador", 0.3)
    for o in extra(ORIGEN_FUENTE):
        rx, rz = x - o.cx, z - o.cz
        distancia = math.hypot(rx, rz)
        limite = o.radio + margen
        if distancia < 1e-9 or distancia > limite + largo + 0.05:
            continue
        nx, nz = rx / distancia, rz / distancia
        if dx * nx + dz * nz >= 0:              # el paso no va hacia la fuente: no es ella la que frena
            continue
        tx, tz = -nz, nx                        # tangente; se elige el sentido que ya lleva el paso
        lado = dx * tx + dz * tz
        if abs(lado) < 1e-6 * largo:
            lado = -1.0                         # de frente exacto: hacia la derecha de quien camina
        if lado < 0:
            tx, tz = -tx, -tz
        px, pz = x + tx * largo, z + tz * largo
        # se lleva al borde (un pelo fuera) para no clavarse ni alejarse
        qx, qz = px - o.cx, pz - o.cz
        d = math.hypot(qx, qz)
        if d < limite + 1e-3:
            px, pz = o.cx + qx / d * (limite + 1e-3), o.cz + qz / d * (limite + 1e-3)
        if mundo.es_transitable(px, pz):
            return (px, pz)
    return None


# Rumbo (grados, convenio de la cámara: 0 = +z) del paso dibujado de (x0, z0) a (x1, z1); `previo` si apenas se movió.
def rumbo_del_paso(x0, z0, x1, z1, previo):
    dx, dz = x1 - x0, z1 - z0
    if math.hypot(dx, dz) < 1e-4:
        return previo
    return math.degrees(math.atan2(dx, dz))
