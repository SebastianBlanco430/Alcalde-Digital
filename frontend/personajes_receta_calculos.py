# Cálculos puros (NO importa ursina ni panda3d) de los personajes con nombre hechos con la fábrica de NPC a partir de su
# receta (backend/datos/personajes_fiscalia.json, cargador backend/datos/personajes_loader.py): el plan de npc_calculos
# (cuerpo, colores, escala), los rasgos de la cara (rostro_calculos.descriptor_peaton) y los cuerpos de respaldo si el
# suyo no carga. El mismo plan sale en el mundo y en la Fiscalía: el personaje es idéntico dentro y fuera.

import zlib

from backend.datos import personajes_loader as pl
from frontend import npc_nuevos_calculos as nn

CEJAS = (0.026, 0.0068, 0.006)
INCLINACION = 6.0


def semilla(receta):
    """Semilla estable del personaje (fase de la animación, parpadeo, desfase de la cara)."""
    return zlib.crc32(receta.id.encode("utf-8")) % 997 + 3


def _u(rgb):
    return tuple(c / 255 for c in rgb)


def clave_modelo(cuerpo):
    """(archivo, clave/rol) que entiende npc_calculos.plan_npc para el cuerpo."""
    return cuerpo, cuerpo[:-4]


def aspecto(receta):
    """Aspecto para plan_npc / descriptor_peaton: piel y pelo en 0..255."""
    return {"piel": tuple(receta.piel), "pelo": tuple(receta.pelo), "pantalon": tuple(receta.pantalon)}


def plan(receta, cuerpo=None):
    """Plan de npc_calculos (modelo nuevo) con los colores, la escala y la corbata de la receta. `cuerpo`: otro cuerpo
    (respaldo) con los mismos colores."""
    cuerpo = cuerpo or receta.cuerpo
    s = semilla(receta)
    p = nn.plan_nuevo(s, s, aspecto(receta), clave_modelo(cuerpo))
    p["colores"] = {"piel": _u(receta.piel), "pelo": _u(receta.pelo), "camiseta": _u(receta.camiseta),
                    "pantalon": _u(receta.pantalon), "zapatos": _u(receta.zapatos)}
    p["escala"] = receta.escala
    p["mochila"] = None
    p["corbata"] = _u(receta.corbata) if receta.corbata is not None and cuerpo in pl.CUERPOS_HOMBRE else None
    p["personaje"] = receta.id
    return p


def rasgos(receta):
    """Rasgos de la cara (formato de peatones_calculos.rasgos_peaton + canas y auriculares)."""
    aur = None
    if receta.auriculares:
        aur = {"color": _u(receta.auriculares["color"]), "almohadilla": _u(receta.auriculares["almohadilla"]),
               "al_cuello": bool(receta.auriculares.get("al_cuello"))}
    return {"peinado": receta.peinado or "corto", "iris": tuple(receta.iris), "cejas": CEJAS,
            "inclinacion": INCLINACION, "gorra": None, "gafas": receta.gafas, "bigote": receta.bigote,
            "barba": receta.barba, "arrugas": receta.arrugas, "canas": receta.canas, "auriculares": aur}


def respaldos(receta):
    """Cuerpos que se prueban si el de la receta no carga: los otros de su género (nunca un protagonista)."""
    mismos = pl.CUERPOS_MUJER if receta.mujer else pl.CUERPOS_HOMBRE
    return [c for c in mismos if c != receta.cuerpo]


# -- Camisa en el escote (retoques-personajes, S1) --
# Antes: pechera y corbata como piezas rígidas colgadas de DEF-spine.003, 5 mm delante de un perfil del pecho medido de
# pie. El escote de la malla (12 triángulos de piel en V) sigue también a los huesos del cuello y los hombros: sentado la
# malla atravesaba las piezas (bordes dentados, pechera partida) y la pechera, más estrecha que la V, dejaba piel a los
# lados. Ahora la camisa ES el escote: esos triángulos, con filas de vértice propias, se pintan de blanco en la misma
# malla (npc_modelo.poner_camisa) y se deforman igual que el pecho. La corbata queda pendiente (sin piezas rígidas).
# Los tres cuerpos de hombre comparten topología: mismos índices de triángulo (comprobado sobre los .glb; en hombre_01 el
# escote está pintado de camiseta y también pasa a camisa).
CAMISA = (0.95, 0.95, 0.92)
TRIANGULOS_CUERPO_HOMBRE = 2152
ESCOTE_TRIANGULOS = (369, 370, 534, 535, 540, 541, 1445, 1446, 1610, 1611, 1616, 1617)
ESCOTE_Z = (1.55, 1.645)       # z del centro de un triángulo del escote (debajo empieza el saco; encima, el cuello)
ESCOTE_X = 0.11                # |x| máximo del centro
ESCOTE_Y = -0.03               # y máximo del centro (delante del cuerpo: y negativa)


def triangulos_escote(posiciones, triangulos):
    """Índices de los triángulos del escote en V (ejes del glb crudo): delante del pecho, entre el cuello y el saco.
    Con los .glb de hombre da ESCOTE_TRIANGULOS."""
    salida = []
    for k, tri in enumerate(triangulos):
        cx = sum(posiciones[r][0] for r in tri) / 3
        cy = sum(posiciones[r][1] for r in tri) / 3
        cz = sum(posiciones[r][2] for r in tri) / 3
        if ESCOTE_Z[0] < cz < ESCOTE_Z[1] and abs(cx) < ESCOTE_X and cy < ESCOTE_Y:
            salida.append(k)
    return salida


# Cuerpo de emergencia si ningún modelo de NPC carga (mejor un cuerpo visible que una sala vacía); se avisa por stderr.
CUERPO_EMERGENCIA = ("periodista.glb", "periodista")
