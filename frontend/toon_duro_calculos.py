# T5 del bloque T (ALCALDE_TOON_DURO): toon DURO solo en los personajes que NO traen bandas pintadas.
# Python puro (NO importa ursina ni panda3d): bandera, a quién se aplica, uniforms del shader y la referencia en Python de
# lo que hace el shader (frontend/toon_duro.py), para los tests.
#
# Qué es: un corte casi en escalón (smoothstep de semiancho SEMIANCHO_BANDA sobre N·L) entre la LUZ (×1,0) y una SOMBRA
# con MATIZ violeta azulado: el mismo factor que la sombra cel de los edificios (luz_horneada_calculos.FACTOR_SOMBRA_CEL,
# referencia RGB (88, 78, 140), luminancia ~1,0 / 0,72). Sol fijo: el de siempre (toon_calculos.direccion_hacia_sol).
#
# A quién (y a quién NO):
#   - SÍ: los NPC NUEVOS (npc_hombre_01..03, npc_mujer_01..02; npc_nuevos_calculos.ARCHIVOS_NUEVOS). Llegan con color
#     plano y npc_nuevos_modelo les HORNEA 3 bandas fijas en el color de vértice (nn.BANDAS según nn.LUZ, en ejes del
#     glb). El shader DESHACE ese horneado en el vertex shader (misma normal, mismos cortes) y pone la banda dinámica
#     dura encima; así el color de vértice no se toca y, si el shader falla, el NPC vuelve EXACTO a como era.
#     El casco de tinta (color nn.COLOR_CONTORNO) ni se deshornea ni se sombrea.
#   - SÍ: el muñeco PROCEDURAL (frontend/personaje.py; piezas con casco de contorno_calculos): sus piezas pasan del
#     lit_with_shadows de Ursina a un lit-toon propio sin skinning.
#   - NO: los 4 .glb de los protagonistas (mc.MODELOS_POR_ROL: periodista, smoking, brasilena, ciudadano) ni los NPC que
#     son COPIAS de esos .glb (npc_modelo con plan sin "nuevo"): traen bandas PINTADAS en los materiales (PielSombra /
#     PielBrillo) y el casco Contorno/Tinta; conservan su shader de siempre. Se distinguen por el ARCHIVO del modelo.

from frontend import luz_horneada_calculos as lhc
from frontend import modelo_calculos as mc
from frontend import npc_nuevos_calculos as nn
from frontend import toon_calculos as toon

TOON_DURO = True                 # ALCALDE_TOON_DURO=0/false/no/off: todo exactamente como antes

CENTRO_BANDA = toon.CENTRO_BANDA     # algo más de medio cuerpo a la luz (la cámara suele mirar contra el sol)
SEMIANCHO_BANDA = 0.02               # corte casi en escalón (el toon suave de P5 usa 0,06)
FACTOR_LUZ = (lhc.FACTOR_LUZ_CEL,) * 3
FACTOR_SOMBRA = tuple(lhc.FACTOR_SOMBRA_CEL)
TOLERANCIA_TINTA = 0.01              # distancia por canal al color del casco de tinta para tratarlo como tinta

ARCHIVOS_PROTAGONISTAS = frozenset(mc.MODELOS_POR_ROL.values())


def activa():
    """¿Rige T5? ALCALDE_TOON_DURO=1/0 manda sobre la constante TOON_DURO."""
    return lhc._bandera("ALCALDE_TOON_DURO", TOON_DURO)


def es_protagonista(archivo):
    """¿Es uno de los 4 .glb con bandas pintadas (o una copia suya)? Esos NUNCA llevan el toon duro."""
    return archivo in ARCHIVOS_PROTAGONISTAS


def usa_toon_duro(archivo):
    """¿El modelo .glb `archivo` lleva el toon duro? Solo los NPC nuevos (color plano + bandas horneadas por código)."""
    return archivo in nn.ARCHIVOS_NUEVOS and not es_protagonista(archivo)


def _bandas_horneadas():
    (corte_luz, brillo_luz), (corte_medio, brillo_medio), (_, brillo_sombra) = nn.BANDAS
    return (corte_luz, corte_medio), (brillo_luz, brillo_medio, brillo_sombra)


def parametros():
    """Uniforms del shader (nombre -> tupla). Los mismos para el skinning y el procedural."""
    cortes, brillos = _bandas_horneadas()
    return {"toon_duro_direccion": tuple(toon.direccion_hacia_sol()),
            "toon_duro_banda": (CENTRO_BANDA, SEMIANCHO_BANDA),
            "toon_duro_luz": FACTOR_LUZ,
            "toon_duro_sombra": FACTOR_SOMBRA,
            "toon_duro_horneado": tuple(nn.LUZ),
            "toon_duro_cortes": cortes,
            "toon_duro_brillos": brillos,
            "toon_duro_tinta": tuple(nn.COLOR_CONTORNO)}


# --- Referencia en Python de los shaders (frontend/toon_duro.py) ---

def _smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def brillo_horneado(normal_modelo):
    """El brillo que npc_nuevos_modelo horneó en ese vértice (= nn.banda_luz), como lo calcula el vertex shader."""
    cortes, brillos = _bandas_horneadas()
    largo = sum(c * c for c in normal_modelo) ** 0.5
    coseno = (sum(normal_modelo[i] * nn.LUZ[i] for i in range(3)) / largo) if largo > 1e-6 else cortes[1]
    return brillos[0] if coseno >= cortes[0] else (brillos[1] if coseno >= cortes[1] else brillos[2])


def es_tinta(color):
    return max(abs(color[i] - nn.COLOR_CONTORNO[i]) for i in range(3)) <= TOLERANCIA_TINTA


def deshornear(color, normal_modelo):
    """Color de vértice sin la banda horneada (el casco de tinta se deja igual)."""
    if es_tinta(color):
        return tuple(color[:3])
    brillo = brillo_horneado(normal_modelo)
    return tuple(c / brillo for c in color[:3])


def factor_duro(normal_mundo, direccion=None):
    """Factor RGB del fragment shader: FACTOR_LUZ de cara al sol, FACTOR_SOMBRA de espaldas; corte de ±SEMIANCHO."""
    d = toon.direccion_hacia_sol() if direccion is None else direccion
    largo = sum(c * c for c in normal_mundo) ** 0.5
    n = tuple(c / largo for c in normal_mundo) if largo > 1e-5 else (0.0, 1.0, 0.0)
    luz = _smoothstep(CENTRO_BANDA - SEMIANCHO_BANDA, CENTRO_BANDA + SEMIANCHO_BANDA, sum(n[i] * d[i] for i in range(3)))
    return tuple(FACTOR_SOMBRA[i] + (FACTOR_LUZ[i] - FACTOR_SOMBRA[i]) * luz for i in range(3))
