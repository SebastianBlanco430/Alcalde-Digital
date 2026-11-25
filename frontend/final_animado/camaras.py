# Tomas de cámara del final animado (PURO: no importa ursina; se prueba con pytest sobre el mundo real).
#
#   toma(plano_id, anclas, mundo) -> Toma        puntos clave ya en coordenadas del mundo
#   camara_en(toma, t) -> (posicion, mira, fov)  t = 0..1 del plano (la curva suave va dentro)
#
# Cada plano se escribe RELATIVO a su ancla (frontend/final_animado/lugares.py), en su marco local (derecha, alto, frente):
# si un ancla se corre, la toma se corre con ella. Así se lee el guion (sesiones-24nov/final/guion.md):
#   - `pos`: puntos clave de la cámara. Su `alto` se mide desde el SUELO real de ese punto (el terreno tiene pendiente: la
#     plaza está a y≈14,4 y el Morro a 8,5), salvo en las tomas con `sobre="ancla"` (aéreas y azotea), donde se mide
#     desde la altura del ancla.
#   - `mira`: puntos a los que mira, relativos al ancla del plano (o a otra: ("prefeitura", d, a, f)); su `alto`, como el
#     de `pos`: desde el suelo de ese punto (o desde el ancla en las tomas `sobre="ancla"`).
#   - Entre puntos clave: Catmull-Rom con el progreso suavizado (sin tirones en los puntos intermedios).
#
# Seguridad: la cámara nunca queda a menos de ALTO_MINIMO del suelo ni dentro de una casa o un edificio. Al construir la
# toma se muestrea el recorrido (MUESTRAS puntos) y se guarda un «piso» por muestra: suelo + ALTO_MINIMO y, si el punto
# cae dentro de la huella de una caja más alta que la cámara, su techo + MARGEN_TECHO (respaldo por si un ancla se corre;
# `toma.rescates` cuenta cuántas muestras lo necesitaron: los tests exigen 0 en el mundo real).

import math
from dataclasses import dataclass

from frontend.final_animado import _calculos as calc
from frontend.final_animado import lugares

ALTO_MINIMO = 1.2               # m sobre el suelo real del punto donde está la cámara
MARGEN_CAJA = 0.3               # m alrededor de cada caja que cuentan como «dentro»
MARGEN_TECHO = 0.6              # m sobre el techo si un punto cayera dentro de una caja (respaldo)
MUESTRAS = 48
FOV = 60.0                      # horizontal (camera.fov de Ursina), como el juego (65) un poco más cerrado

# --- Las tomas, plano por plano (guion.md). Cierres m6/b7/n6: la misma. -------------------------------------------------

_CIERRE = {"ancla": "azotea", "sobre": "ancla",
           "pos": [(0.0, 2.6, -5.0), (0.0, 3.5, -6.5), (0.0, 4.5, -8.0)],
           "mira": [(0.0, -2.2, 24.0), (0.0, -3.0, 28.0)], "fov": (58.0, 62.0)}

TOMAS = {
    # -- Malo --
    "m1_reelegido": {"ancla": "prefeitura", "pos": [(0.4, 2.2, 7.0), (0.0, 3.5, 11.0)],
                     "mira": [(0.0, 2.3, 0.0), (0.0, 2.6, 0.0)], "fov": (54.0, 60.0)},
    "m2_calles_arden": {"ancla": "plaza", "sobre": "ancla",
                        "pos": [(-20.0, 26.0, 20.0), (-11.0, 21.0, 11.0), (-2.3, 17.0, 2.3)],
                        "mira": [(14.0, 0.0, -14.0), (20.0, 0.0, -20.0)], "fov": (62.0, 62.0)},
    # Delante de la puerta de la Prefeitura (a ~10 m del ancla), nunca dentro: frente 7 deja a la gente a 8-12 m.
    "m3_protesta": {"ancla": "protesta", "pos": [(-5.0, 2.0, 7.0), (0.0, 2.3, 7.2), (5.0, 3.0, 7.0)],
                    "mira": [(-1.8, 1.3, -3.0), (1.8, 1.3, -3.0)], "fov": (60.0, 60.0)},
    "m5_plaza_vacia": {"ancla": "protesta",
                       "pos": [(1.8, 1.2, -3.6), (1.2, 2.4, -5.0), (0.0, 4.5, -7.0)],
                       "mira": [(0.0, 0.1, -1.8), (0.0, 1.8, 2.0), ("prefeitura", 1.5, 6.0, -1.1)],
                       "fov": (54.0, 58.0)},
    "m6_cierre": _CIERRE,
    # -- Bueno --
    "b1_gana": {"ancla": "urna", "pos": [(0.4, 1.5, 2.5), (-0.3, 2.3, 5.0), (-0.6, 3.2, 8.0)],
                "mira": [(0.0, 1.0, 0.0), (-0.8, 1.3, -0.5)], "fov": (50.0, 60.0)},
    # La puerta no está en el centro de la fachada: el centro del edificio queda a derecha ≈ 2,3 del ancla.
    "b2_sede_oscura": {"ancla": "prefeitura", "pos": [(1.0, 3.2, 15.0), (1.5, 4.2, 10.5)],
                       "mira": [(2.0, 4.4, -1.0), (1.8, 4.2, -1.0)], "fov": (64.0, 66.0)},
    "b3_calles_limpias": {"ancla": "calle", "pos": [(0.0, 1.7, 9.0), (0.0, 1.7, 3.0)],
                          "mira": [(0.0, 1.3, -3.0), (0.0, 1.3, -3.5)], "fov": (60.0, 58.0)},
    "b4_musica": {"ancla": "calle", "pos": [(0.0, 1.3, -7.0), (0.0, 3.0, -7.6)],
                  "mira": [(0.0, 2.6, -12.0), (0.0, 1.9, -13.0)], "fov": (62.0, 62.0)},
    "b6_podio": {"ancla": "podio", "pos": [(0.0, 4.5, 13.0), (0.0, 3.4, 8.0), (0.0, 2.6, 4.0)],
                 "mira": [(0.0, 1.6, -2.0), (0.0, 1.9, 0.0)], "fov": (62.0, 50.0)},
    "b7_cierre": _CIERRE,
    # -- Neutro --
    "n1_conteo": {"ancla": "urna", "arco": {"angulos": (-20.0, 20.0), "radios": (2.5, 6.0), "altos": (1.5, 2.2)},
                  "mira": [(0.0, 0.9, 0.0), (0.0, 1.0, 0.0)], "fov": (52.0, 58.0)},
    "n2_plaza_a_medias": {"ancla": "podio", "pos": [(-6.0, 5.0, 14.0), (6.0, 5.0, 14.0)],
                          "mira": [(-3.0, 1.2, 4.0), (3.0, 1.2, 4.0)], "fov": (60.0, 60.0)},
    "n3_calle": {"ancla": "calle", "pos": [(0.0, 1.7, 8.0), (0.0, 1.7, 4.5)],
                 "mira": [(0.0, 1.3, -3.0), (0.0, 1.3, -3.0)], "fov": (60.0, 60.0)},
    # Los dos candidatos tienen que verse: más cerca y más bajo que la fachada entera (las ventanas, arriba del cuadro).
    "n5_candidatos": {"ancla": "prefeitura", "pos": [(0.0, 2.0, 10.0), (0.0, 2.0, 7.0)],
                      "mira": [(0.0, 2.3, 0.0), (0.0, 2.2, 0.0)], "fov": (60.0, 58.0)},
    "n6_cierre": _CIERRE,
}

# Planos de rol: la misma toma en los tres finales (cambia la actuación, no la cámara).
_ROLES = {
    # La ventana del ciudadano: fachada a frente −1,2 (el ancla está 1,2 m delante de la puerta), derecha 2,2.
    # Alta (2,8 -> 3,2 m) y sin pasar de frente 6: los vecinos que cruzan delante de la ventana (frente 2-3) quedan
    # por debajo de la línea de mirada (a su altura pasa a ~2,3 m).
    "ciudadano": {"ancla": "morro", "pos": [(1.2, 2.8, 7.8), (1.8, 3.2, 6.0)],
                  "mira": [(2.2, 1.5, -1.2), (2.2, 1.5, -1.2)], "fov": (54.0, 48.0)},
    "periodista": {"ancla": "radio", "arco": {"angulos": (-10.0, 15.0), "radios": (6.2, 5.6), "altos": (1.9, 1.8)},
                   "mira": [(0.0, 1.4, 0.0), (0.8, 1.6, 0.0)], "fov": (60.0, 56.0)},
    "influencer": {"ancla": "directo", "pos": [(0.0, 1.7, 3.0), (0.0, 1.9, 5.0)],
                   "mira": [(0.0, 1.5, 0.0), (0.0, 1.7, 0.0)], "fov": (52.0, 60.0)},
    # De tres cuartos: de frente, el pie del micrófono le cruzaba la cara.
    "candidato": {"ancla": "tarima", "pos": [(2.3, 1.8, 4.8), (2.0, 1.8, 4.0)],
                  "mira": [(0.2, 1.5, 0.0), (0.2, 1.6, 0.0)], "fov": (56.0, 54.0)},
}
for _prefijo in ("m4", "b5", "n4"):
    for _rol, _definicion in _ROLES.items():
        TOMAS[f"{_prefijo}_{_rol}"] = _definicion

# Si el guion trae un id que aquí no está: la cámara de prueba del contrato (~8 m del ancla, 2,5 m de alto).
TOMA_GENERICA = {"pos": [(0.0, 2.5, 8.0), (0.0, 2.8, 7.0)], "mira": [(0.0, 1.4, 0.0), (0.0, 1.5, 0.0)], "fov": (60.0, 60.0)}
ANCLA_DE_PREFIJO = {"b": "plaza", "n": "plaza", "m": "plaza"}


@dataclass(frozen=True)
class Toma:
    plano_id: str
    ancla: str
    posiciones: tuple           # ((x, y, z), ...) puntos clave en el mundo
    miras: tuple
    fovs: tuple                 # (fov al empezar, fov al terminar)
    pisos: tuple                # y mínima de la cámara en cada muestra (MUESTRAS + 1, t = k / MUESTRAS)
    rescates: int               # muestras donde el piso tuvo que subir por encima de una caja (0 en el mundo real)
    curva: str = "suave"


# -- Geometría ----------------------------------------------------------------------------------------------------------

def _catmull(puntos, u):
    """Punto en la Catmull-Rom uniforme por `puntos` (>= 1) con u en 0..1 (extremos duplicados)."""
    n = len(puntos)
    if n == 1:
        return tuple(puntos[0])
    u = min(1.0, max(0.0, u))
    s = u * (n - 1)
    i = min(int(s), n - 2)
    f = s - i
    p0, p1, p2, p3 = puntos[max(0, i - 1)], puntos[i], puntos[i + 1], puntos[min(n - 1, i + 2)]
    f2, f3 = f * f, f * f * f
    return tuple(0.5 * (2 * b + (-a + c) * f + (2 * a - 5 * b + 4 * c - d) * f2 + (-a + 3 * b - 3 * c + d) * f3)
                 for a, b, c, d in zip(p0, p1, p2, p3))


def cajas_de(mundo):
    """Cajas sólidas del mundo para la cámara: (x0, x1, z0, z1, y_min, y_max) de las casas decorativas y los edificios."""
    cajas = []
    for o in mundo.obstaculos():
        if getattr(o, "tipo", None) == "casa" and o.es_caja:
            alturas = [mundo.altura(o.cx + sx * o.ancho / 2, o.cz + sz * o.fondo / 2) for sx in (-1, 0, 1) for sz in (-1, 0, 1)]
            alto = float(getattr(o, "alto_total", 4.0))
            cajas.append((o.cx - o.ancho / 2, o.cx + o.ancho / 2, o.cz - o.fondo / 2, o.cz + o.fondo / 2,
                          min(alturas) - 1.0, max(alturas) + alto))
    for e in mundo.edificios():
        cajas.append((e.cx - e.ancho / 2, e.cx + e.ancho / 2, e.cz - e.fondo / 2, e.cz + e.fondo / 2,
                      float(e.y) - 1.0, float(e.y) + float(e.alto)))
    return cajas


def dentro_de_caja(punto, cajas, margen=MARGEN_CAJA):
    """La primera caja que contiene `punto` (x, y, z) con `margen`, o None."""
    x, y, z = punto
    for caja in cajas:
        x0, x1, z0, z1, y0, y1 = caja
        if x0 - margen <= x <= x1 + margen and z0 - margen <= z <= z1 + margen and y0 <= y <= y1 + margen:
            return caja
    return None


def _cajas_cerca(cajas, puntos, radio):
    xs, zs = [p[0] for p in puntos], [p[2] for p in puntos]
    x0, x1, z0, z1 = min(xs) - radio, max(xs) + radio, min(zs) - radio, max(zs) + radio
    return [c for c in cajas if c[1] >= x0 and c[0] <= x1 and c[3] >= z0 and c[2] <= z1]


# -- Construcción -------------------------------------------------------------------------------------------------------

# Las tomas que valen ahora: con ALCALDE_FINALES_PULIDOS, las corregidas de final_pulido_calculos encima de TOMAS.
def _tomas():
    from frontend.final_animado import final_pulido_calculos as pulido
    return pulido.tomas(TOMAS) if pulido.activo() else TOMAS


def definicion(plano_id):
    return _tomas().get(plano_id)


def _definicion_y_ancla(plano_id, anclas):
    propia = _tomas().get(plano_id)
    if propia is not None and propia["ancla"] in anclas:
        return propia, anclas[propia["ancla"]]
    nombre = ANCLA_DE_PREFIJO.get(str(plano_id)[:1], "plaza")
    return TOMA_GENERICA, anclas.get(nombre) or next(iter(anclas.values()))


def _punto_mira(definicion_mira, ancla, anclas, mundo, sobre_ancla):
    if isinstance(definicion_mira[0], str):
        ancla, definicion_mira = anclas[definicion_mira[0]], definicion_mira[1:]
    derecha, alto, frente = definicion_mira
    if sobre_ancla:
        return lugares.a_mundo(ancla, derecha, alto, frente)
    return lugares.en_suelo(mundo, ancla, derecha, frente, alto)


def _posiciones(defn, ancla, mundo):
    sobre_ancla = defn.get("sobre") == "ancla"
    locales = list(defn.get("pos", ()))
    arco = defn.get("arco")
    if arco:                                     # giro alrededor del ancla: puntos sobre un arco (derecha = sen, frente = cos)
        a0, a1 = arco["angulos"]
        r0, r1 = arco["radios"]
        h0, h1 = arco["altos"]
        locales = []
        for k in range(5):
            f = k / 4.0
            ang = math.radians(a0 + (a1 - a0) * f)
            radio = r0 + (r1 - r0) * f
            locales.append((radio * math.sin(ang), h0 + (h1 - h0) * f, radio * math.cos(ang)))
    puntos = []
    for derecha, alto, frente in locales:
        if sobre_ancla:
            puntos.append(lugares.a_mundo(ancla, derecha, alto, frente))
        else:
            puntos.append(lugares.en_suelo(mundo, ancla, derecha, frente, alto))
    return puntos


def toma(plano_id, anclas, mundo, cajas=None):
    """La toma del plano `plano_id` en `mundo` con sus `anclas` (lugares.anclas(mundo)). `cajas` (opcional): las de
    cajas_de(mundo), para no recalcularlas en cada toma."""
    defn, ancla = _definicion_y_ancla(plano_id, anclas)
    posiciones = _posiciones(defn, ancla, mundo)
    miras = [_punto_mira(m, ancla, anclas, mundo, defn.get("sobre") == "ancla") for m in defn["mira"]]
    fov0, fov1 = defn.get("fov", (FOV, FOV))
    todas = cajas if cajas is not None else cajas_de(mundo)
    cerca = _cajas_cerca(todas, posiciones, 6.0)
    pisos, rescates = [], 0
    for k in range(MUESTRAS + 1):                # muestras uniformes en el parámetro u de la curva (camara_en igual)
        x, y, z = _catmull(posiciones, k / MUESTRAS)
        piso = float(mundo.altura(x, z)) + ALTO_MINIMO
        caja = dentro_de_caja((x, max(y, piso), z), cerca)
        if caja is not None:
            rescates += 1
            piso = max(piso, caja[5] + MARGEN_TECHO)
        pisos.append(piso)
    return Toma(str(plano_id), ancla.nombre, tuple(tuple(p) for p in posiciones), tuple(tuple(m) for m in miras),
                (float(fov0), float(fov1)), tuple(pisos), rescates, defn.get("curva", "suave"))


def tomas_de(planos, anclas, mundo):
    """{plano.id: Toma} de una lista de planos (las cajas del mundo se calculan una vez)."""
    cajas = cajas_de(mundo)
    return {p.id: toma(p.id, anclas, mundo, cajas) for p in planos}


def camara_en(toma_, t):
    """(posicion, mira, fov) de la toma a t = 0..1 (fuera de rango se recorta)."""
    curva = calc.CURVAS.get(toma_.curva, calc.suave)
    u = curva(t)
    x, y, z = _catmull(toma_.posiciones, u)
    pisos = toma_.pisos
    s = min(1.0, max(0.0, u)) * (len(pisos) - 1)
    i = min(int(s), len(pisos) - 2)
    f = s - i
    piso = pisos[i] + (pisos[i + 1] - pisos[i]) * f
    mira = _catmull(toma_.miras, u)
    fov = toma_.fovs[0] + (toma_.fovs[1] - toma_.fovs[0]) * u
    return (x, max(y, piso), z), mira, fov
