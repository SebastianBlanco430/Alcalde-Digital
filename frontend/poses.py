# Poses del personaje articulado (Python puro: NO importa ursina). Una pose es un dict
# {articulación: ángulo en grados} más la altura de la pelvis ('pelvis_y', en metros).
# Personaje.aplicar_pose() la traduce a rotaciones de los pivotes.
#
# Convención de ÁNGULOS (independiente de Ursina): positivo = el segmento se balancea hacia
# ADELANTE desde su pivote (muslo y brazo hacia delante, antebrazo que se dobla hacia
# delante); rodilla: negativo = pantorrilla que se dobla hacia atrás (0 = recta). La vista
# invierte el signo al aplicarlo a rotation_x (en Ursina rotation_x > 0 inclina hacia atrás
# un segmento que cuelga).
#
# Caminar (fase φ en radianes, intensidad i ∈ [0, 1] = velocidad / velocidad_de_carrera):
#   A = 40·i (grados de balanceo del muslo) ;  B = 50·i (doblez de la rodilla)
#   muslo_i = A·sin φ ;  muslo_d = −A·sin φ
#   rodilla_i = −B·max(0, −sin φ) ;  rodilla_d = −B·max(0, sin φ)    (la pierna atrasada se dobla)
#   brazo_i = −A/2·sin φ ; brazo_d = +A/2·sin φ                      (brazos en contrafase)
# Con i = 0 queda una respiración leve (torso ±1.2°) y la pelvis sube y baja con la zancada.
# La fase avanza φ += 2π·(velocidad / largo_paso)·dt: un paso completo (un ciclo) cada vez
# que se recorre `largo_paso`.

import math
import types

DOS_PI = 2 * math.pi
LARGO_PASO = 2.4
ALTURA_PELVIS_PARADO = 0.95
ALTURA_PELVIS_SENTADO = 0.50

_ARTICULACIONES = (
    "pelvis_y", "torso", "cabeza",
    "brazo_i", "brazo_d", "codo_i", "codo_d",
    "muslo_i", "muslo_d", "rodilla_i", "rodilla_d",
)


def articulaciones():
    return _ARTICULACIONES


def _pose(**valores):
    base = {nombre: 0.0 for nombre in _ARTICULACIONES}
    base.update(valores)
    return base


# Solo lectura: se copian con dict() si hay que modificarlas.
POSE_PARADO = types.MappingProxyType(_pose(pelvis_y=ALTURA_PELVIS_PARADO))
POSE_SENTADO = types.MappingProxyType(_pose(
    pelvis_y=ALTURA_PELVIS_SENTADO, muslo_i=90, muslo_d=90, rodilla_i=-90, rodilla_d=-90,
    codo_i=10, codo_d=10))
# Brazos hacia el teclado: base de pose_teclear.
_BASE_TECLEAR = dict(POSE_SENTADO, brazo_i=30, brazo_d=30, codo_i=60, codo_d=60, torso=6, cabeza=-4)


# Pose de caminar/reposo para la fase φ y la intensidad i (se limita a [0, 1]).
def pose_caminar(fase, intensidad):
    i = min(1.0, max(0.0, intensidad))
    s = math.sin(fase)
    balanceo, doblez = 40 * i, 50 * i
    pose = _pose(
        pelvis_y=ALTURA_PELVIS_PARADO - 0.03 * i * (1 - abs(math.cos(fase))),
        torso=1.2 * (1 - i) * s + 4 * i,
        muslo_i=balanceo * s, muslo_d=-balanceo * s,
        rodilla_i=-doblez * max(0.0, -s), rodilla_d=-doblez * max(0.0, s),
        brazo_i=-balanceo / 2 * s, brazo_d=balanceo / 2 * s,
        codo_i=8 + 25 * i, codo_d=8 + 25 * i,
    )
    return pose


# Sentado tecleando: los brazos oscilan unos grados, desfasados (golpes de tecla).
def pose_teclear(fase):
    pose = dict(_BASE_TECLEAR)
    pose["brazo_i"] += 3 * math.sin(fase)
    pose["brazo_d"] += 3 * math.sin(fase + math.pi)
    pose["codo_i"] += 5 * math.sin(2 * fase)
    pose["codo_d"] += 5 * math.sin(2 * fase + math.pi / 2)
    return pose


# Mezcla articulación a articulación: t = 0 -> a, t = 1 -> b (t se limita a [0, 1]).
# ValueError si las poses no tienen las mismas articulaciones.
def interpolar_pose(a, b, t):
    if set(a) != set(b):
        raise ValueError("Las poses deben tener las mismas articulaciones.")
    t = min(1.0, max(0.0, t))
    if t == 0:
        return dict(a)
    if t == 1:
        return dict(b)
    return {nombre: a[nombre] + (b[nombre] - a[nombre]) * t for nombre in a}


# Fase siguiente (en [0, 2π)): φ += 2π·(velocidad/largo_paso)·dt.
def fase_siguiente(fase, velocidad, dt, largo_paso=LARGO_PASO):
    if velocidad == 0 or dt <= 0:
        return fase
    return (fase + DOS_PI * (velocidad / largo_paso) * dt) % DOS_PI
