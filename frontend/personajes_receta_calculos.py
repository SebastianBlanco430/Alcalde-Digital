# Cálculos puros (NO importa ursina ni panda3d) de los personajes con nombre hechos con la fábrica de NPC a partir de su
# receta (backend/datos/personajes_fiscalia.json, cargador backend/datos/personajes_loader.py): el plan de npc_calculos
# (cuerpo, colores, escala), los rasgos de la cara (rostro_calculos.descriptor_peaton) y los cuerpos de respaldo si el
# suyo no carga. El mismo plan sale en el mundo y en la Fiscalía: el personaje es idéntico dentro y fuera.
#
# Elenco v2 (sesión F): con ALCALDE_ELENCO_V2 (y la maestra) activa, `elegir_v2` da el plan de la malla propia del
# personaje (v2/<id>.glb: sin recolor, sin camisa pintada, cara con `rasgos_v2`); si el .glb falta o no se puede leer,
# None y un aviso por stderr UNA vez, y se usa la receta de hoy (`plan`, con los valores de `receta.hoy`: idéntico a
# antes). El NPC de etapa con capucha usa v2/etapa_capucha.glb (`plan_etapa_capucha`): solo su piel se recolorea.

import os
import zlib
from pathlib import Path

from backend.datos import personajes_loader as pl
from backend.logica import modelos_v2 as mv2
from frontend import npc_calculos as nc
from frontend import npc_nuevos_calculos as nn

CARPETA_PERSONAJES = Path(__file__).resolve().parents[1] / "assets" / "modelos" / "personajes"
ETAPA_CAPUCHA = mv2.CARPETA_V2 + "/etapa_capucha.glb"

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


def colores_hoy(receta):
    """Valores de la receta de siempre (los de antes de la tabla de diseños v2)."""
    if receta.hoy is not None:
        return receta.hoy
    return {"piel": receta.piel, "pelo": receta.pelo, "camiseta": receta.camiseta, "pantalon": receta.pantalon,
            "zapatos": receta.zapatos, "corbata": receta.corbata, "escala": receta.escala}


def aspecto(receta):
    """Aspecto para plan_npc / descriptor_peaton (receta de siempre): piel y pelo en 0..255."""
    h = colores_hoy(receta)
    return {"piel": tuple(h["piel"]), "pelo": tuple(h["pelo"]), "pantalon": tuple(h["pantalon"])}


def aspecto_v2(receta):
    """Aspecto con los colores de la tabla de diseños (los de la malla v2)."""
    return {"piel": tuple(receta.piel), "pelo": tuple(receta.pelo), "pantalon": tuple(receta.pantalon)}


def plan(receta, cuerpo=None):
    """Plan de npc_calculos (modelo nuevo) con los colores, la escala y la corbata de la receta de siempre. `cuerpo`: otro
    cuerpo (respaldo) con los mismos colores."""
    cuerpo = cuerpo or receta.cuerpo
    s = semilla(receta)
    h = colores_hoy(receta)
    p = nn.plan_nuevo(s, s, aspecto(receta), clave_modelo(cuerpo))
    p["colores"] = {"piel": _u(h["piel"]), "pelo": _u(h["pelo"]), "camiseta": _u(h["camiseta"]),
                    "pantalon": _u(h["pantalon"]), "zapatos": _u(h["zapatos"])}
    p["escala"] = h["escala"]
    p["mochila"] = None
    p["corbata"] = _u(h["corbata"]) if h["corbata"] is not None and cuerpo in pl.CUERPOS_HOMBRE else None
    p["personaje"] = receta.id
    return p


def planes_respaldo(receta):
    """Planes de la receta de siempre, en el orden en que se prueban: su cuerpo y luego los otros de su género."""
    return [plan(receta)] + [plan(receta, c) for c in respaldos(receta)]


def rasgos(receta):
    """Rasgos de la cara (formato de peatones_calculos.rasgos_peaton + canas y auriculares)."""
    aur = None
    if receta.auriculares:
        aur = {"color": _u(receta.auriculares["color"]), "almohadilla": _u(receta.auriculares["almohadilla"]),
               "al_cuello": bool(receta.auriculares.get("al_cuello"))}
    return {"peinado": receta.peinado or "corto", "iris": tuple(receta.iris), "cejas": CEJAS,
            "inclinacion": INCLINACION, "gorra": None, "gafas": receta.gafas, "bigote": receta.bigote,
            "barba": receta.barba, "arrugas": receta.arrugas, "canas": receta.canas, "auriculares": aur}


def rasgos_v2(receta):
    """Rasgos de la cara con la malla v2: los de la receta con las claves de `rostro_v2` (el pelo, los audífonos y la
    barba completa van en la malla: peinado y auriculares None). 'ajuste' no es un rasgo: va en el plan."""
    r = rasgos(receta)
    r["peinado"] = None
    r["auriculares"] = None
    for clave, valor in (receta.rostro_v2 or {}).items():
        if clave != "ajuste":
            r[clave] = valor
    return r


# -- Elenco v2: malla propia por personaje -------------------------------------------------------------------------------

_cache_glb = {}          # ruta -> (mtime, tamaño, datos | None, motivo)


def datos_glb(archivo, carpeta=None):
    """(datos de nn.datos_v2, motivo) del .glb `archivo` (relativo a la carpeta de personajes). (None, motivo) si falta o
    no se puede leer. Se relee solo si el archivo cambia."""
    ruta = Path(carpeta or CARPETA_PERSONAJES) / archivo
    try:
        st = os.stat(ruta)
    except OSError:
        return None, f"falta {archivo}"
    clave = str(ruta)
    previo = _cache_glb.get(clave)
    if previo is not None and previo[:2] == (st.st_mtime_ns, st.st_size):
        return previo[2], previo[3]
    try:
        datos, motivo = nn.datos_v2(nn.leer_gltf(ruta)), ""
    except Exception as error:         # noqa: BLE001  un .glb roto: se usa la receta de hoy
        datos, motivo = None, f"{archivo} no se puede leer ({error})"
    _cache_glb[clave] = (st.st_mtime_ns, st.st_size, datos, motivo)
    return datos, motivo


def plan_v2(receta, carpeta=None):
    """Plan de la malla v2 del personaje (o None si no tiene o no se puede leer). Sin recolor ni camisa pintada."""
    if not receta.glb_v2:
        return None
    datos, _ = datos_glb(receta.glb_v2, carpeta)
    if datos is None:
        return None
    s = semilla(receta)
    colores = {"piel": _u(receta.piel), "pelo": _u(receta.pelo), "camiseta": _u(receta.camiseta),
               "pantalon": _u(receta.pantalon), "zapatos": _u(receta.zapatos)}
    p = nn.plan_v2(receta.glb_v2, datos, Path(carpeta or CARPETA_PERSONAJES) / receta.glb_v2, nc.fase_animacion(s, s),
                   colores, receta.escala, recolor=())
    p["rol"] = "v2_" + receta.id
    p["personaje"] = receta.id
    ajuste = (receta.rostro_v2 or {}).get("ajuste")
    if ajuste:
        p["ajuste_rostro"] = tuple(ajuste)
    return p


def elegir_v2(receta, carpeta=None):
    """Plan v2 si el elenco v2 está activo y su .glb se puede leer; si no, None (y si la bandera está activa, aviso por
    stderr UNA vez: ese personaje usa su receta de hoy)."""
    if not mv2.elenco_activo() or not receta.glb_v2:
        return None
    p = plan_v2(receta, carpeta)
    if p is None:
        _, motivo = datos_glb(receta.glb_v2, carpeta)
        mv2.avisar_una_vez(f"elenco:{receta.id}", f"{receta.nombre} ({receta.id}): {motivo}; se usa su receta de hoy.")
    return p


# -- NPC de etapa con capucha (Raponero, Jíbaro, Extorsionador) ------------------------------------------------------

def plan_etapa_capucha(indice, semilla_npc, aspecto_npc, carpeta=None):
    """Plan de v2/etapa_capucha.glb para el NPC de etapa `indice` (solo la piel se recolorea, con la suya), o None si el
    elenco v2 no está activo o el .glb falta (aviso UNA vez: se usan la fábrica de siempre y la capucha por código)."""
    if not mv2.elenco_activo():
        return None
    datos, motivo = datos_glb(ETAPA_CAPUCHA, carpeta)
    if datos is None:
        mv2.avisar_una_vez("elenco:etapa_capucha", f"NPC de etapa con capucha: {motivo}; se usa la capucha por código.")
        return None
    base = nn.plan_nuevo(indice, semilla_npc, aspecto_npc, ("npc_hombre_02.glb", "npc_hombre_02"))
    colores = dict(base["colores"], piel=tuple(c / 255 for c in aspecto_npc["piel"]))
    p = nn.plan_v2(ETAPA_CAPUCHA, datos, Path(carpeta or CARPETA_PERSONAJES) / ETAPA_CAPUCHA, base["fase"], colores,
                   base["escala"], recolor=("piel",))
    p["rol"] = "v2_etapa_capucha"
    return p


def rasgos_etapa_capucha(rasgos_npc):
    """La capucha va en la malla: fuera los elipsoides de la capucha, el peinado y la gorra (lo demás de la cara, igual)."""
    r = {k: v for k, v in rasgos_npc.items() if k != "capucha"}
    r["peinado"] = None
    r["gorra"] = None
    return r


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
