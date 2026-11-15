# Género de los NPC y modelo acorde a su nombre (cálculos puros: NO importa ursina ni panda3d).
#
# Problema que arregla: los modelos de los NPC se eligen por índice sin mirar el nombre, así que había mujeres con
# cuerpo de hombre y al revés (Inés Duarte y Doña Neide con smoking, Marcos Vela con el modelo de mujer). Aquí:
#   - cada modelo tiene un género (GENERO_POR_ARCHIVO);
#   - un NPC con nombre recibe un modelo de SU género (modelo_para_genero), elegido de forma determinista por
#     (índice, semilla): el mismo NPC siempre sale igual, también en el cooperativo (cada cliente usa SEMILLA=2026);
#   - la influencer (brasilena.glb) queda solo como personaje jugable (INFLUENCER_SOLO_JUGABLE): ningún reparto de
#     NPC la usa y las mujeres salen con npc_mujer_01 / npc_mujer_02.
#
# Banderas (los dos apagados = comportamiento de antes):
#   NOMBRES_POR_GENERO / ALCALDE_NOMBRES_GENERO          modelo según el género del nombre.
#   INFLUENCER_SOLO_JUGABLE / ALCALDE_INFLUENCER_SOLO_JUGABLE  la brasileña fuera de los NPC.

import os
import random

from backend.datos.nombres_npc import HOMBRE, MUJER, genero_de_nombre

NOMBRES_POR_GENERO = True
INFLUENCER_SOLO_JUGABLE = True

ARCHIVO_INFLUENCER = "brasilena.glb"

GENERO_POR_ARCHIVO = {
    "periodista.glb": HOMBRE, "smoking.glb": HOMBRE, "ciudadano.glb": HOMBRE, ARCHIVO_INFLUENCER: MUJER,
    "npc_hombre_01.glb": HOMBRE, "npc_hombre_02.glb": HOMBRE, "npc_hombre_03.glb": HOMBRE,
    "npc_mujer_01.glb": MUJER, "npc_mujer_02.glb": MUJER,
}

# Modelos (archivo, clave/rol) con ropa de diario que se dan a un NPC con nombre según su género. Fuera el smoking
# (traje de gala) y el ciudadano (torso al aire), como ya hacía comercios_mundo.MODELOS_DEPENDIENTE.
MODELOS_CON_NOMBRE = {
    HOMBRE: (("periodista.glb", "periodista"), ("npc_hombre_01.glb", "npc_hombre_01"),
             ("npc_hombre_02.glb", "npc_hombre_02"), ("npc_hombre_03.glb", "npc_hombre_03")),
    MUJER: (("npc_mujer_01.glb", "npc_mujer_01"), ("npc_mujer_02.glb", "npc_mujer_02")),
}


def _bandera(nombre, constante):
    valor = os.environ.get(nombre, "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(constante)


def nombres_por_genero_activo():
    return _bandera("ALCALDE_NOMBRES_GENERO", NOMBRES_POR_GENERO)


def influencer_solo_jugable():
    return _bandera("ALCALDE_INFLUENCER_SOLO_JUGABLE", INFLUENCER_SOLO_JUGABLE)


# Género del modelo `archivo` (None si no se conoce).
def genero_de_archivo(archivo):
    return GENERO_POR_ARCHIVO.get(archivo)


# Modelo (archivo, clave) de género `genero` para el NPC `indice`: determinista por (índice, semilla) y con un
# generador propio. None si el género no se conoce.
def modelo_para_genero(indice, semilla, genero):
    opciones = MODELOS_CON_NOMBRE.get(genero)
    if not opciones:
        return None
    return opciones[random.Random(semilla * 9973 + indice * 241 + 3).randrange(len(opciones))]


# Modelo forzado para un NPC que se llama `nombre`: None si las dos banderas están apagadas, si el nombre no deja saber
# el género o si el modelo que ya le toca (`archivo_actual`) es de su género y no es la influencer (no se cambia lo
# que ya casaba). Con solo INFLUENCER_SOLO_JUGABLE también actúa: las dependientas, que antes llevaban la brasileña,
# necesitan otro modelo de mujer.
def modelo_para_nombre(indice, semilla, nombre, archivo_actual=None):
    if not (nombres_por_genero_activo() or influencer_solo_jugable()):
        return None
    genero = genero_de_nombre(nombre)
    if genero is None:
        return None
    if archivo_actual is not None and genero_de_archivo(archivo_actual) == genero:
        if not (archivo_actual == ARCHIVO_INFLUENCER and influencer_solo_jugable()):
            return None
    return modelo_para_genero(indice, semilla, genero)


# Reparto sin la influencer: la sustituye un modelo de mujer ya existente, el que toque por (índice, semilla).
def sin_influencer(modelo, indice, semilla):
    if modelo is None or modelo[0] != ARCHIVO_INFLUENCER or not influencer_solo_jugable():
        return modelo
    return modelo_para_genero(indice, semilla, MUJER)


# Nombre de un NPC anónimo (peatón, multitud) acorde al género de su modelo: «Peatón N» si la bandera está apagada o
# el modelo no se conoce. Determinista por (índice, semilla). Hoy las etiquetas de los peatones están ocultas; el
# nombre queda en `personaje.nombre` para quien lo muestre (diálogos, depuración).
def nombre_para_npc(indice, semilla, archivo):
    genero = genero_de_archivo(archivo)
    if not nombres_por_genero_activo() or genero is None:
        return f"Peatón {indice}"
    from backend.datos.nombres_npc import nombre_npc
    return nombre_npc(indice, semilla, genero)
