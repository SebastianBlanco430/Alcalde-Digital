# Trabajo desde el NPC del puesto (ALCALDE_TRABAJO_EN_NPC, prompt-puestos.md P3). Puro: sin ursina, con tests.
#
# Antes cada tienda con `trabajo_id` tenía al lado un puesto de trabajo aparte con un cartel «TRABAJO» de poste
# (frontend/trabajo_mundo.py). Con la bandera encendida no hay cartel ni puesto aparte: al hablar con el dependiente,
# el panel de la tienda ofrece «Trabajar aquí» (tecla T o el botón), que abre el menú de turnos de siempre
# (economia.al_trabajar(jugador, trabajo_id) -> trabajo_mundo.pedir_turno: en línea o sin fuerzas dice el motivo).
# Los puestos de trabajo puros (taller, entregas) ya abrían el menú al usar a su NPC: solo pierden el cartel.
# El trabajo, su pago y sus turnos no cambian: es el mismo `trabajo_id` del catálogo.
# ALCALDE_TRABAJO_EN_NPC=0: como antes (puesto aparte con cartel).

import os

TRABAJO_EN_NPC = True
VARIABLE = "ALCALDE_TRABAJO_EN_NPC"
TECLA_TRABAJAR = "t"
TEXTO_BOTON = "Trabajar aquí (T)"

_ENCENDIDO = ("1", "true", "si", "sí", "on")
_APAGADO = ("0", "false", "no", "off")


def trabajo_en_npc_activo():
    """¿Se trabaja hablando con el NPC (sin cartel)? ALCALDE_TRABAJO_EN_NPC=1/0 manda sobre la constante."""
    valor = os.environ.get(VARIABLE, "").strip().lower()
    if valor in _ENCENDIDO:
        return True
    if valor in _APAGADO:
        return False
    return bool(TRABAJO_EN_NPC)


def tiene_trabajo(comercio):
    return comercio.tipo == "puesto_trabajo" or bool(comercio.trabajo_id)


def ofrece_trabajo_en_tienda(comercio, en_npc=None):
    """¿El panel de la tienda de este comercio ofrece «Trabajar aquí»? Solo tiendas con trabajo y la bandera encendida."""
    en_npc = trabajo_en_npc_activo() if en_npc is None else en_npc
    return bool(en_npc and comercio.tipo == "tienda" and comercio.trabajo_id)


def texto_aviso(comercio, nombre, en_npc=None):
    """Aviso de la E junto al dependiente."""
    if comercio.tipo == "puesto_trabajo":
        return f"E: Trabajar en {comercio.nombre}"
    if ofrece_trabajo_en_tienda(comercio, en_npc):
        return f"E: Hablar con {nombre} · comprar o trabajar"
    return f"E: Hablar con {nombre} / comprar"


def plan_puestos(validos, en_npc=None):
    """Para cada (comercio, trabajo) con trabajo: (comercio, trabajo, registrar, puede_cartel). `registrar` = se añade un
    PuestoTrabajo propio como Interacción; `puede_cartel` = ese puesto puede correrse a un lado con el cartel «TRABAJO».
    Con la bandera, ninguno: el trabajo se pide al NPC (ComercioMundo) y el PuestoTrabajo solo guarda el Puesto para
    economia.al_trabajar(jugador, trabajo_id)."""
    en_npc = trabajo_en_npc_activo() if en_npc is None else en_npc
    return [(c, t, not en_npc, not en_npc) for c, t in validos]
