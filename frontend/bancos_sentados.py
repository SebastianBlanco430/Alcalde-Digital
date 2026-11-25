# GENTE DE LAS PLAZAS (Ursina + Panda3D): en la ciudad viva (frontend/ciudad_viva.py) los bancos ocupados y los corros ya
# no son figuras de bloques: son NPC de Blender (npc_hombre_01..03 y npc_mujer_01..02, con la ropa y el aspecto
# deterministas de los peatones) con clips propios horneados por frontend/animacion_humana.py sobre el mismo esqueleto:
#   - capa «bancos»: SENTADOS (bancos_sentados_calculos.CLIP: respiran y miran alrededor despacio);
#   - capa «corros»: de pie en rueda CHARLANDO (CLIP_CHARLA: gesticulan, asienten, cambian el peso), cada uno desfasado,
#     con la bocina portátil de siempre en el medio.
# Banderas ALCALDE_BANCOS_SENTADOS y ALCALDE_BANCOS_CORROS (frontend/bancos_sentados_calculos.py): =0 deja las figuras de
# bloques de siempre en esa capa.
#
# Es la MISMA piscina que las demás capas (ciudad_viva.Grupo: sitios fijos de la rejilla, reparto cerca de la cámara,
# fundido de escala, cantidad según la actividad de las plazas) con los NPC creados una vez. Sin colisión (decorado).
# Cada NPC queda con ignore=True (como las ranuras de las demás capas): su update no corre, así que nadie le cambia el
# clip; la animación la mueve Panda en C++. Si algo falla al crearlos, crear_grupo()/crear_grupo_corros() devuelven None
# y la capa sigue con las figuras de bloques.

import sys

from frontend import bancos_sentados_calculos as bsc

# NPC sentados a la vez como mucho (cada uno es un Actor: se cuida la RAM)
N_NPC = 6
# primer índice de peatón (aspecto y ropa deterministas de peatones_calculos)
INDICE_NPC = 60
# m del asiento sobre el suelo de la plaza (ciudad_3d._banco: y + 0.46 + 0.05)
ALTO_ASIENTO = 0.51
# m que se sube el NPC para que no se hunda en la tabla
AJUSTE_ALTURA = 0.05
# corros a la vez como mucho (cada uno con PERSONAS_CORRO NPC) y primer índice de peatón de sus NPC
N_CORROS = 2
INDICE_CORRO = 80
# velocidad del clip de charla: cada persona con la suya (no gesticulan todas a la vez)
VELOCIDADES_CHARLA = (0.24, 0.3, 0.27, 0.21, 0.33)
GRIS_BOCINA, AMARILLO_BOCINA = (44, 46, 56), (236, 200, 70)


def _avisar(texto):
    print(f"[bancos_sentados] {texto}", file=sys.stderr)


def poner_clip(npc, clip, velocidad, fotograma=0):
    """Deja al NPC con `clip` en bucle desde `fotograma` (y nada más). False si su modelo no trae el clip."""
    actor = getattr(npc, "actor", None)
    if actor is None or clip not in actor.getAnimNames():
        return False
    for nombre in actor.getAnimNames():
        actor.stop(nombre)
        actor.setControlEffect(nombre, 0.0)
    actor.setControlEffect(clip, 1.0)
    actor.setPlayRate(velocidad, clip)
    actor.loop(clip, fromFrame=fotograma)
    return True


def sentar(npc):
    """Deja al NPC con el clip de sentado en bucle. False si su modelo no trae el clip."""
    return poner_clip(npc, bsc.CLIP, bsc.VELOCIDAD_CLIP)


def _npc_quieto(parent, indice):
    """NPC de peatón sin aro ni nombre, sin mochila y sin animación automática (la pone quien lo crea)."""
    from frontend.npc_modelo import crear_npc
    from frontend.peatones import ROPA, SEMILLA
    from frontend.peatones_calculos import aspecto_peaton, rasgos_peaton
    npc = crear_npc(indice, SEMILLA, aspecto_peaton(indice, SEMILLA), rasgos_peaton(indice, SEMILLA),
                    ROPA[indice % len(ROPA)], parent=parent)
    npc.automatico = False
    for parte in ("aro", "etiqueta"):
        if getattr(npc, parte, None) is not None:
            getattr(npc, parte).enabled = False
    # sentado o charlando no lleva la mochila puesta (atravesaría el respaldo)
    mochila = npc.actor.find("**/mochila") if getattr(npc, "actor", None) is not None else None
    if mochila is not None and not mochila.isEmpty():
        mochila.hide()
    return npc


def _npc(raiz, indice):
    npc = _npc_quieto(raiz, indice)
    if not sentar(npc):
        raise RuntimeError(f"el modelo del NPC {indice} no tiene el clip {bsc.CLIP}")
    npc.escala_banco = npc.scale_x
    npc.enabled = False
    npc.ignore = True
    return npc


def _colocar_inicial(npc, dato):
    x, z = bsc.posicion_en_banco(dato.x, dato.z, dato.giro, dato.u)
    npc.position = (x, dato.y - ALTO_ASIENTO + AJUSTE_ALTURA, z)
    npc.fijar_rumbo(dato.giro)


def _colocar(npc, dato, es):
    npc.scale = max(0.001, es) * getattr(npc, "escala_banco", 1.0)


def crear_grupo(raiz, sitios, radio):
    """Piscina de NPC sentados para los `sitios` de los bancos (ciudad_viva), o None si está apagada o algo falla."""
    if not bsc.activo():
        return None
    creados = []
    try:
        from backend.logica import ciudad_viva_calculos as cv
        from frontend import ciudad_viva
        for k in range(N_NPC):
            creados.append(_npc(raiz, INDICE_NPC + 3 * k))
        # la piscina de siempre, sin ranuras propias: se le dan los NPC como entidades
        grupo = ciudad_viva.Grupo(raiz, "sentados_npc", lambda: None, 0, sitios, radio, _colocar, _colocar_inicial, N_NPC)
        grupo.ranuras = cv.Ranuras(N_NPC)
        grupo.entidades = creados
        return grupo
    except Exception as error:                   # noqa: BLE001
        from frontend.componentes import destruir_arbol
        for npc in creados:
            destruir_arbol(npc)
        _avisar(f"sin NPC sentados, se usan las figuras de siempre ({error})")
        return None


# -- Corros --

def _corro(raiz, k):
    """Un corro (ranura de la piscina): una Entity con PERSONAS_CORRO NPC charlando en rueda y la bocina en el medio."""
    from ursina import Entity
    from ursina.shaders import unlit_shader
    from frontend.props_mundo import Malla, caja, icosfera
    corro = Entity(parent=raiz, name=f"corro_npc_{k}", enabled=False)
    for j, (x, z, rumbo) in enumerate(bsc.puestos_corro(k)):
        indice = INDICE_CORRO + 5 * k + j
        npc = _npc_quieto(corro, indice)
        fotograma = (7 * j + 3 * k) % 24
        if not poner_clip(npc, bsc.CLIP_CHARLA, VELOCIDADES_CHARLA[(j + k) % len(VELOCIDADES_CHARLA)], fotograma):
            raise RuntimeError(f"el modelo del NPC {indice} no tiene el clip {bsc.CLIP_CHARLA}")
        npc.colocar(x, z)
        npc.fijar_rumbo(rumbo)
        npc.ignore = True
    m = Malla()
    m.agregar(caja(), (0, 0.18, 0), (0.34, 0.36, 0.24), 20 * k, GRIS_BOCINA, (0.8, 1.1))
    m.agregar(icosfera(0), (0, 0.2, 0.13), 0.18, 0, AMARILLO_BOCINA, (0.9, 1.1))
    Entity(parent=corro, model=m.mesh(), shader=unlit_shader)
    corro.ignore = True
    return corro


def _colocar_inicial_corro(corro, dato):
    corro.position = (dato.x, dato.y, dato.z)
    corro.rotation_y = dato.giro


def _colocar_corro(corro, dato, es):
    corro.scale = max(0.001, es)


def crear_grupo_corros(raiz, sitios, radio):
    """Piscina de corros de NPC charlando para los `sitios` de las plazas (ciudad_viva), o None si está apagada o falla."""
    if not bsc.corros_activos():
        return None
    creados = []
    try:
        from backend.logica import ciudad_viva_calculos as cv
        from frontend import ciudad_viva
        for k in range(N_CORROS):
            creados.append(_corro(raiz, k))
        grupo = ciudad_viva.Grupo(raiz, "corros_npc", lambda: None, 0, sitios, radio, _colocar_corro,
                                  _colocar_inicial_corro, N_CORROS)
        grupo.ranuras = cv.Ranuras(N_CORROS)
        grupo.entidades = creados
        return grupo
    except Exception as error:                   # noqa: BLE001
        from frontend.componentes import destruir_arbol
        for corro in creados:
            destruir_arbol(corro)
        _avisar(f"sin corros de NPC, se usan las figuras de siempre ({error})")
        return None
