# Cálculos puros (NO importa ursina ni panda3d) de la POSTURA de los NPC con modelo .glb: cómo cambia el cuerpo
# según el estado emocional. Es el gancho para la conducta (otro módulo decide el estado; aquí solo está el cuerpo).
#
# Estados: 'sociable' (erguido, mentón arriba, brazos sueltos), 'neutro' (la animación de siempre), 'aislado'
# (encorvado, cabeza gacha, brazos pegados), 'celular' (cabeza gacha y los dos antebrazos al frente, «pegado al
# celular») y 'enojado' (torso echado adelante, codos flexionados y abiertos, braceo corto).
#
# Una postura NO es un clip aparte: modifica las poses de frontend/animacion_humana_calculos.py (reposo y marcha) y
# con ellas se hornean variantes de los clips (frontend/npc_postura.py), así el NPC camina encorvado sin que los
# pies patinen (las piernas no se tocan). Marco del cuerpo: x adelante, y izquierda, z arriba; ángulos en grados.
# También: las poses de los clips que los .glb nuevos no traen (Idle con respiración, Hablar, Saludar).

import math

from frontend import animacion_humana_calculos as ac

NEUTRO = "neutro"
ESTADOS = ("sociable", NEUTRO, "aislado", "celular", "enojado")
TIEMPO_CAMBIO = 0.45             # s que tarda el cuerpo en pasar de una postura a otra

REPOSO_BRAZO = (4.0, 6.0, 14.0, 3.0)     # brazo colgando: (adelante, abducción) del brazo y del antebrazo

# Por estado: giros que se SUMAN a cada zona (giro, inclinación adelante, caída lateral); `braceo` = cuánto del
# balanceo de los brazos queda (1 = el de siempre); `abduccion` = grados que se abren (+) o pegan (-) los brazos;
# `codo` = flexión extra del antebrazo; `brazos` = brazos FIJOS (adelante, abducción) x2, sin balanceo;
# `baja` = metros que baja la pelvis.
POSTURAS = {
    "sociable": {"rot": {"lumbar": (0, -1.0, 0), "pecho": (0, -3.5, 0), "cuello": (0, -3.0, 0), "cabeza": (0, -6.0, 0)},
                 "braceo": 1.2, "abduccion": 3.0, "codo": 0.0, "brazos": None, "baja": 0.0},
    "aislado": {"rot": {"lumbar": (0, 7.0, 0), "pecho": (0, 17.0, 0), "cuello": (0, 24.0, 0), "cabeza": (0, 34.0, 0)},
                "braceo": 0.3, "abduccion": -3.0, "codo": 4.0, "brazos": None, "baja": 0.012},
    "celular": {"rot": {"lumbar": (0, 4.0, 0), "pecho": (0, 10.0, 0), "cuello": (0, 22.0, 0), "cabeza": (0, 36.0, 0)},
                "braceo": 0.0, "abduccion": 0.0, "codo": 0.0, "brazos": (40.0, 6.0, 134.0, -19.0), "baja": 0.006},
    "enojado": {"rot": {"lumbar": (0, 3.0, 0), "pecho": (0, 8.0, 0), "cuello": (0, 4.0, 0), "cabeza": (0, 9.0, 0)},
                "braceo": 0.6, "abduccion": 13.0, "codo": 34.0, "brazos": None, "baja": 0.0},
}
ESTADOS_CON_CLIPS = tuple(e for e in ESTADOS if e in POSTURAS)     # los que hornean clips propios


# Estado válido más cercano a lo pedido: cualquier cosa desconocida (None, números, otro texto) cuenta como neutro.
def estado_valido(estado):
    if isinstance(estado, str) and estado.strip().lower() in ESTADOS:
        return estado.strip().lower()
    return NEUTRO


# Nombre del clip horneado de `clip` para un estado (el neutro usa el clip de siempre).
def nombre_clip(clip, estado):
    return clip if estado == NEUTRO or estado not in POSTURAS else f"{clip}_{estado}"


# Reparto del peso de un clip entre la postura que se va y la que entra: `k` (0..1) es el avance del cambio.
# Devuelve (peso de la saliente, peso de la entrante); suman `peso`.
def repartir(peso, k):
    k = ac._suave(k)
    return peso * (1.0 - k), peso * k


def _sumar(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _brazo(lado, pecho, valores):
    sup, abd_s, inf, abd_i = valores
    return {"sup": ac.unitario(ac.mat_por_vec(pecho, ac.dir_brazo(lado, sup, abd_s))),
            "inf": ac.unitario(ac.mat_por_vec(pecho, ac.dir_brazo(lado, inf, abd_i)))}


# Dirección `quieto` más el balanceo (lo que `original` se aparta de `colgando`) multiplicado por `braceo`.
def _con_braceo(quieto, original, colgando, braceo):
    return ac.unitario(tuple(quieto[i] + (original[i] - colgando[i]) * braceo for i in range(3)))


# Copia de una pose (ac.pose_marcha, pose_reposo...) con la postura del estado: suma los giros del tronco y la
# cabeza, baja la pelvis y rehace los brazos. Las piernas NO cambian (los pies siguen plantados). Total: un estado
# desconocido o neutro devuelve la pose tal cual.
def aplicar_a_pose(pose, estado):
    datos = POSTURAS.get(estado)
    if datos is None:
        return pose
    nueva = dict(pose)
    rots = dict(pose["rot"])
    for zona, extra in datos["rot"].items():
        rots[zona] = _sumar(rots[zona], extra)
    nueva["rot"] = rots
    d = pose["desp_pelvis"]
    nueva["desp_pelvis"] = (d[0], d[1], d[2] - datos["baja"])
    pecho, pecho_original = ac.mat_euler(*rots["pecho"]), ac.mat_euler(*pose["rot"]["pecho"])
    for lado, clave in ((1, "i"), (-1, "d")):
        if datos["brazos"] is not None:
            nueva["brazo_" + clave] = _brazo(lado, pecho, datos["brazos"])
            continue
        sup, abd_s, inf, abd_i = REPOSO_BRAZO
        quieto = _brazo(lado, pecho, (sup, abd_s + datos["abduccion"], inf + datos["codo"], abd_i + datos["abduccion"]))
        original, colgando = pose["brazo_" + clave], _brazo(lado, pecho_original, REPOSO_BRAZO)
        nueva["brazo_" + clave] = {h: _con_braceo(quieto[h], original[h], colgando[h], datos["braceo"])
                                   for h in ("sup", "inf")}
    return nueva


# -- Poses de los clips que los .glb nuevos no traen (vienen sin animaciones) --

def _de_pie(m, rots, brazos, baja=0.005):
    xc, alt = m.cadera_i[0], m.altura_tobillo
    yc = abs(m.cadera_i[1]) + ac.SEPARACION[0]
    return ac._armar_pose(m, (0.0, 0.0, -baja), rots, (xc, yc, alt, 0.0, 0.0), (xc, -yc, alt, 0.0, 0.0), brazos)


# Reposo de pie con respiración: el pecho sube y baja y los brazos se abren apenas. `fase` 0..1 es un ciclo.
def pose_reposo(fase, m=None):
    m = m or ac.Medidas()
    s = math.sin(2 * math.pi * fase)
    sup, abd_s, inf, abd_i = REPOSO_BRAZO
    rots = {"pelvis": (0.0, 0.0, 0.0), "lumbar": (0, 0.5 - 0.4 * s, 0), "pecho": (0, 1.5 - 1.2 * s, 0),
            "cuello": (0, 0.5, 0), "cabeza": (0, -0.5 + 0.5 * s, 0)}
    brazo = (sup, abd_s + 0.8 * s, inf, abd_i + 0.5 * s)
    return _de_pie(m, rots, {"i": brazo, "d": brazo}, baja=0.005 - 0.003 * s)


# Hablar: de pie, el antebrazo derecho arriba marcando el compás.
def pose_hablar(fase, m=None):
    m = m or ac.Medidas()
    s, s2 = math.sin(2 * math.pi * fase), math.sin(4 * math.pi * fase)
    rots = {"pelvis": (0.0, 0.0, 0.0), "lumbar": (0, 0.5, 0), "pecho": (1.5 * s, 2.0, 0), "cuello": (0, 0.5, 0),
            "cabeza": (2.5 * s, -1.0 + 1.5 * s2, 0)}
    return _de_pie(m, rots, {"i": REPOSO_BRAZO, "d": (22.0 + 4.0 * s, 8.0, 88.0 + 12.0 * s2, 2.0)})


# Saludar: el brazo derecho en alto y el antebrazo de lado a lado.
def pose_saludar(fase, m=None):
    m = m or ac.Medidas()
    s = math.sin(2 * math.pi * fase)
    rots = {"pelvis": (0.0, 0.0, 0.0), "lumbar": (0, 0.0, 0), "pecho": (0, -1.0, -2.0), "cuello": (0, 0.0, 0),
            "cabeza": (0, -3.0, 0)}
    return _de_pie(m, rots, {"i": REPOSO_BRAZO, "d": (10.0, 100.0, 12.0, 150.0 + 22.0 * s)})
