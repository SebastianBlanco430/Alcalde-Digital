# Cálculos puros de los personajes con modelo .glb (NO importa ursina ni panda3d): qué archivo
# usa cada rol, a qué escala, y qué clip de animación toca según la velocidad o la pose.
# Los clips del .glb son Idle, Caminar, Correr, Saludar y Hablar (no hay sentado ni teclear).
#
# Velocidades nativas de los clips (m/s con escala 1): caminar 1.4, correr 3.6. El juego camina
# a 4.8 m/s y corre a 8.5 m/s (escena_mundo.py), muy por encima: el rate se limita (2.0 y 2.2) y
# el umbral caminar/correr queda entre ambas velocidades, no en 3.0 como en los clips.

import math

MODELOS_POR_ROL = {"periodista": "periodista.glb", "candidato": "smoking.glb",
                   "influencer": "brasilena.glb", "ciudadano": "ciudadano.glb"}

ALTURA_MODELO = 2.0              # m: alto del .glb sin escalar (pies en y = 0)
ESCALA_MODELO = 0.92             # 1.84 m (reales 1.994 y 2.006 m sin escalar), como el muñeco procedural (1.83 m)

# Escala propia de un rol cuyo modelo mide distinto (la brasileña con el afro llega a 2.14 m sin escalar).
# Los roles que no están aquí usan ESCALA_MODELO.
ESCALA_POR_ROL = {"influencer": 0.86}

IDLE, CAMINAR, CORRER, SALUDAR, HABLAR = "Idle", "Caminar", "Correr", "Saludar", "Hablar"

VEL_NATIVA_CAMINAR = 1.4
VEL_NATIVA_CORRER = 3.6
RATE_MAX_CAMINAR = 2.0
RATE_MAX_CORRER = 2.2
RATE_MIN_CAMINAR = 0.5
RATE_MIN_CORRER = 1.0

UMBRAL_QUIETO = 0.1              # bajo esta velocidad: Idle
UMBRAL_MOVIMIENTO = 0.25         # entre ambos se mantiene el clip anterior (histéresis)
UMBRAL_CORRER = 6.5              # entre caminar (4.8) y correr (8.5) del juego
HISTERESIS_CORRER = 0.3

ALTURA_PELVIS_SENTADO_MAX = 0.8  # pelvis más baja = pose sentada o tecleando
INTENSIDAD_QUIETO = 0.12         # intensidad de pose_caminar bajo la cual se considera reposo
INTENSIDAD_CORRER = 0.6


def altura_efectiva():
    return ALTURA_MODELO * ESCALA_MODELO


# Escala del modelo de un rol: la de ESCALA_POR_ROL o, si no tiene, ESCALA_MODELO.
def escala_para_rol(rol):
    return ESCALA_POR_ROL.get(rol, ESCALA_MODELO)


def _limitar(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


# (clip, rate) para una velocidad real en m/s; `anterior` es el clip que sonaba (o None).
def clip_para_velocidad(velocidad, anterior=None):
    v = velocidad
    if not isinstance(v, (int, float)) or math.isnan(v) or v < 0:
        v = 0.0
    if v < UMBRAL_QUIETO:
        return IDLE, 1.0
    if v < UMBRAL_MOVIMIENTO and anterior in (None, IDLE):
        return IDLE, 1.0
    corre = v >= UMBRAL_CORRER - (HISTERESIS_CORRER if anterior == CORRER else 0.0)
    if corre:
        return CORRER, _limitar(v / (VEL_NATIVA_CORRER * ESCALA_MODELO), RATE_MIN_CORRER, RATE_MAX_CORRER)
    return CAMINAR, _limitar(v / (VEL_NATIVA_CAMINAR * ESCALA_MODELO), RATE_MIN_CAMINAR, RATE_MAX_CAMINAR)


# (clip, rate) para una pose de frontend/poses.py (dict con las 11 articulaciones). Total: las
# claves que falten valen 0. Sentado/tecleando -> Hablar (no hay clip de sentado). La intensidad
# sale de lo que no depende de la fase: el codo (8 + 25·i) y el balanceo del muslo (40·i).
def clip_para_pose(pose):
    def valor(clave, defecto=0.0):
        try:
            v = float(pose.get(clave, defecto))
        except (TypeError, ValueError, AttributeError):
            return defecto
        return defecto if math.isnan(v) else v

    if valor("pelvis_y", 1.0) < ALTURA_PELVIS_SENTADO_MAX:
        return HABLAR, 1.0
    intensidad = max((valor("codo_i") - 8) / 25, max(abs(valor("muslo_i")), abs(valor("muslo_d"))) / 40)
    if intensidad < INTENSIDAD_QUIETO:
        return IDLE, 1.0
    if intensidad < INTENSIDAD_CORRER:
        return CAMINAR, 1.0
    return CORRER, 1.0
