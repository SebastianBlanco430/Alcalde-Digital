# Matemática PURA (sin ursina ni panda3d) de la pose SENTADA de un personaje con modelo .glb sobre una bicicleta o
# una moto. El .glb no trae clip de sentado: frontend/piloto_glb.py mueve sus huesos con la pose que sale de aquí.
# Reutiliza el marco del cuerpo y las poses de frontend/animacion_humana_calculos.py (x adelante, y izquierda, z
# arriba; origen en el suelo bajo el pivote de la pelvis; unidades del modelo SIN escalar).
#
# `conv(punto_vehiculo)` lo pone el módulo Panda: pasa un punto del vehículo (x derecha, y arriba, z adelante, en
# metros, con el origen en el piloto) al marco del cuerpo del modelo (ya dividido por la escala del Actor).

import math

from frontend import animacion_humana_calculos as ac
from frontend import vehiculo_calculos as vc

BIELA = 0.17                        # m: largo de la biela (el mismo de vehiculo_piezas.BIELA)
TORSO_BICI, TORSO_MOTO = 32.0, 14.0  # ° de inclinación del tronco hacia delante (los de vehiculo_piezas.pose_piloto)
CADERA_SOBRE_SILLIN = 0.10          # m: la cadera queda sobre el asiento (la carne se hunde un poco)
SUELA = 0.03                        # m: del tobillo-hueso a la planta, ya sumado a altura_tobillo (zapato)
PIE_SOBRE_PEDAL = 0.02              # m: la planta apoya sobre la cara superior del pedal/estribo
PROPORCION_PIE = 0.62               # fracción del largo tobillo-dedos que queda DETRÁS del pedal (el antepié lo pisa)
POLO_CODO = (-0.3, 0.7, -1.0)       # hacia dónde se abre el codo (atrás, afuera y abajo); la y se espeja por lado


def torso_para(es_bici):
    return TORSO_BICI if es_bici else TORSO_MOTO


# Rotaciones absolutas de cada zona (giro, inclina, caída) para un torso inclinado `t` grados al frente: la columna
# se reparte la inclinación y la cabeza se queda casi vertical (mira al frente).
def rotaciones_sentado(t):
    return {"pelvis": (0.0, 0.25 * t, 0.0), "lumbar": (0.0, 0.55 * t, 0.0), "pecho": (0.0, t, 0.0),
            "cuello": (0.0, 0.5 * t, 0.0), "cabeza": (0.0, 0.1 * t, 0.0)}


def _suma(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


# Punto del vehículo donde apoya el pie (bici: pedal según la fase; moto: estribo). `lado`: +1 derecho, -1 izquierdo.
def punto_apoyo(puntos, es_bici, fase, lado):
    if es_bici:
        pz, py = vc.posicion_pedal(fase, lado, BIELA)
        return (puntos["eje_pedal_x"] * lado, puntos["pedalier"][1] + py, puntos["pedalier"][2] + pz)
    return tuple(puntos["estribo_d" if lado > 0 else "estribo_i"])


# Pose completa (formato de ac.pose_*, lista para Hornero.locales).
#   m: ac.Medidas del modelo; puntos: ModeloPiezas.puntos; es_bici: bool; fase: fase del pedal (rad);
#   conv: punto del vehículo -> marco del cuerpo; escala: escala del Actor (para pasar metros a unidades del modelo);
#   hombros: {"i": (x,y,z), "d": ...} posiciones de los hombros en el marco del cuerpo (None = brazos colgando);
#   largos: (brazo, antebrazo) en unidades del modelo.
def pose_sentada(m, puntos, es_bici, fase, conv, escala, hombros=None, largos=(0.3, 0.3)):
    t = torso_para(es_bici)
    rots = rotaciones_sentado(t)
    # Cadera: sobre el asiento. El desplazamiento de la pelvis se despeja para que el centro de las caderas caiga
    # exactamente ahí con el torso ya inclinado.
    sillin = puntos["sillin"]
    objetivo = conv((0.0, sillin[1] + CADERA_SOBRE_SILLIN, sillin[2]))
    centro = ((m.cadera_i[0] + m.cadera_d[0]) / 2, (m.cadera_i[1] + m.cadera_d[1]) / 2, (m.cadera_i[2] + m.cadera_d[2]) / 2)
    sin_desp = ac._cadera_mundo(centro, m, ac.mat_euler(*rots["pelvis"]), (0.0, 0.0, 0.0))
    desp = ac.resta(objetivo, sin_desp)
    # Pies: el tobillo queda detrás del pedal/estribo y a la altura del zapato sobre él.
    tobillos = {}
    for lado, clave in ((1, "d"), (-1, "i")):
        p = conv(punto_apoyo(puntos, es_bici, fase, lado))
        x = p[0] - PROPORCION_PIE * m.pie_adelante
        z = p[2] + (m.altura_tobillo + (SUELA + PIE_SOBRE_PEDAL) / escala)
        tobillos[clave] = (x, p[1], z, 0.0, 0.0)
    brazos = {"i": (0.0, 0.0, 0.0, 0.0), "d": (0.0, 0.0, 0.0, 0.0)}      # colgando; se sustituyen abajo
    pose = ac._armar_pose(m, desp, rots, tobillos["i"], tobillos["d"], brazos)
    if hombros is not None:
        for lado, clave in ((1, "i"), (-1, "d")):
            mano = conv(puntos["agarre_i" if lado > 0 else "agarre_d"])
            polo = (POLO_CODO[0], POLO_CODO[1] * lado, POLO_CODO[2])
            _, sup, inf, _error = ac.ik_pierna(hombros[clave], mano, largos[0], largos[1], polo)
            pose["brazo_" + clave] = {"sup": sup, "inf": inf}
    return pose
