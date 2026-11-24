# Poses y gestos de los actores del final animado (PURO: no importa ursina ni panda3d).
#
# Cada POSE es una postura de cuerpo entero de un fotograma, con el mismo formato que las posturas de los NPC
# (frontend/npc_postura_calculos.py): giros por zona (giro, inclinación adelante, caída lateral) y los dos brazos como
# (adelante, abducción) del brazo y del antebrazo, en grados (marco del cuerpo: x adelante, y izquierda, z arriba).
# actores.py las hornea UNA vez por esqueleto con el horneado de frontend/animacion_humana.py y las mezcla en el
# Actor con su peso (Panda normaliza la mezcla), así sirven igual para los 4 modelos de rol y para los NPC.
#
# Cada ACCIÓN dice qué hace el cuerpo: un clip del .glb («Saludar», «Hablar»), una pose fija o dos poses que se
# alternan (a / b) con su frecuencia, y lo que se mueve el cuerpo entero (saltito, bote).
#
#   pose_de(nombre, medidas) -> pose (dict de animacion_humana_calculos)
#   objetivo(accion, segundos, fase, k) -> Objetivo(clip, pesos {pose: 0..1}, dy, mezcla_b)

import math
from dataclasses import dataclass

from frontend import animacion_humana_calculos as ac
from frontend import npc_postura_calculos as pc

REPOSO = pc.REPOSO_BRAZO                           # brazo colgando
_ROTS0 = {"pelvis": (0.0, 0.0, 0.0), "lumbar": (0.0, 0.5, 0.0), "pecho": (0.0, 1.5, 0.0), "cuello": (0.0, 0.5, 0.0),
          "cabeza": (0.0, 0.0, 0.0)}


def _r(**zonas):
    rots = dict(_ROTS0)
    rots.update(zonas)
    return rots


def _b(i, d=None):
    return {"i": tuple(i), "d": tuple(d if d is not None else i)}


# nombre -> (giros por zona, brazos, metros que baja la pelvis)
POSES = {
    "aplauso_a": (_r(cabeza=(0, -4, 0)), _b((32, 14, 86, -6)), 0.005),
    "aplauso_b": (_r(cabeza=(0, -4, 0)), _b((34, 6, 90, -42)), 0.005),
    "arriba_a": (_r(pecho=(0, -6, 0), cabeza=(0, -12, 0)), _b((165, 22, 172, 26)), 0.0),
    "arriba_b": (_r(pecho=(0, -6, 0), cabeza=(0, -12, 0)), _b((148, 40, 158, 52)), 0.0),
    "pancarta_arriba": (_r(pecho=(0, -3, 0), cabeza=(0, -8, 0)), _b((158, 12, 176, 6)), 0.0),
    "pancarta_abajo": (_r(), _b((60, 12, 96, -6)), 0.005),
    "puno_arriba": (_r(pecho=(0, -3, -3), cabeza=(0, -8, 0)), _b(REPOSO, (172, 14, 178, 8)), 0.0),
    "puno_medio": (_r(), _b(REPOSO, (112, 24, 152, 18)), 0.0),
    "brazos_cruzados": (_r(cabeza=(0, -3, 0)), _b((18, 6, 92, -72), (22, 8, 96, -66)), 0.005),
    "manos_atras": (_r(pecho=(0, -2, 0)), _b((-22, 10, -28, -58)), 0.005),
    "cintura": (_r(), _b((-4, 42, -22, -62)), 0.005),
    "cabeza_baja": (_r(lumbar=(0, 4, 0), pecho=(0, 10, 0), cuello=(0, 20, 0), cabeza=(0, 26, 0)), _b((2, 3, 10, 1)), 0.01),
    "gracias": (_r(cabeza=(0, 6, 0)), _b((22, 8, 100, -62), (26, 8, 104, -58)), 0.005),
    "reverencia": (_r(lumbar=(0, 10, 0), pecho=(0, 18, 0), cuello=(0, 10, 0), cabeza=(0, 14, 0)),
                   _b((22, 8, 100, -62), (26, 8, 104, -58)), 0.01),
    "teclear_a": (_r(pecho=(0, 10, 0), cuello=(0, 8, 0), cabeza=(0, 16, 0)), _b((28, 12, 78, -14), (28, 12, 72, -10)), 0.01),
    "teclear_b": (_r(pecho=(0, 10, 0), cuello=(0, 8, 0), cabeza=(0, 16, 0)), _b((28, 12, 72, -10), (28, 12, 80, -16)), 0.01),
    "contar_a": (_r(lumbar=(0, 12, 0), pecho=(0, 22, 0), cuello=(0, 10, 0), cabeza=(0, 20, 0)),
                 _b((48, 10, 70, -12), (52, 12, 74, -22)), 0.02),
    "contar_b": (_r(lumbar=(0, 12, 0), pecho=(0, 22, 0), cuello=(0, 10, 0), cabeza=(0, 20, 0)),
                 _b((48, 10, 70, -12), (58, 14, 84, -6)), 0.02),
    "reloj": (_r(cuello=(8, 12, 0), cabeza=(10, 22, 0)), _b((24, 16, 98, -50), REPOSO), 0.005),
    "apoyado": (_r(lumbar=(0, 6, 0), pecho=(0, 14, 0), cabeza=(0, -4, 0)), _b((42, 18, 92, -30)), 0.01),
    "encogerse": (_r(cabeza=(0, 0, 10)), _b((6, 32, 72, 46)), 0.0),
    "mas_menos_a": (_r(cabeza=(0, 0, 4)), _b(REPOSO, (30, 16, 92, 2)), 0.0),
    "mas_menos_b": (_r(cabeza=(0, 0, -4)), _b(REPOSO, (30, 16, 92, 28)), 0.0),
    "nuca_a": (_r(cabeza=(0, 10, 6)), _b(REPOSO, (128, 62, 205, -30)), 0.0),
    "nuca_b": (_r(cabeza=(0, 12, 4)), _b(REPOSO, (126, 58, 215, -36)), 0.0),
    "dar_mano": (_r(), _b(REPOSO, (40, 10, 70, 4)), 0.0),
    "leer": (_r(cuello=(0, 8, 0), cabeza=(0, 10, 0)), _b((-20, 10, -26, -56)), 0.0),
    "nota": (_r(cabeza=(0, -6, 0)), _b((106, 30, 150, 20)), 0.0),
    "guitarra_a": (_r(cabeza=(0, 10, 0)), _b((30, 30, 100, -38), (20, 12, 72, -36)), 0.0),
    "guitarra_b": (_r(cabeza=(0, 12, 0)), _b((30, 30, 100, -38), (24, 12, 58, -26)), 0.0),
    "tambor_a": (_r(cabeza=(0, 8, 0)), _b((26, 16, 80, -16), (26, 16, 56, -16)), 0.0),
    "tambor_b": (_r(cabeza=(0, 8, 0)), _b((26, 16, 56, -16), (26, 16, 80, -16)), 0.0),
    "maracas_a": (_r(), _b((44, 24, 124, 4), (44, 24, 104, 10)), 0.0),
    "maracas_b": (_r(), _b((44, 24, 104, 10), (44, 24, 124, 4)), 0.0),
    "barrer_a": (_r(lumbar=(10, 8, 0), pecho=(18, 12, 0), cabeza=(-12, 10, 0)), _b((26, 8, 36, -30), (16, 14, 30, -20)), 0.02),
    "barrer_b": (_r(lumbar=(-6, 8, 0), pecho=(-12, 12, 0), cabeza=(8, 10, 0)), _b((30, 4, 44, -34), (22, 12, 40, -26)), 0.02),
    "bailar_a": (_r(pelvis=(8, 0, -4), pecho=(-10, 0, 4)), _b((70, 40, 130, 30), (40, 30, 90, 10)), 0.03),
    "bailar_b": (_r(pelvis=(-8, 0, 4), pecho=(10, 0, -4)), _b((40, 30, 90, 10), (70, 40, 130, 30)), 0.03),
    "respirar_a": (_r(), _b(REPOSO), 0.005),
    "respirar_b": (_r(pecho=(0, -7, 0), cuello=(0, -2, 0), cabeza=(0, -8, 0)), _b((2, 12, 8, 8)), 0.0),
    "banda_a": (_r(cabeza=(0, 10, 0)), _b(REPOSO, (30, 6, 118, -64)), 0.0),
    "banda_b": (_r(cabeza=(0, 12, 0)), _b(REPOSO, (36, 4, 130, -72)), 0.0),
    "brazo_arriba": (_r(cabeza=(0, -8, 0)), _b(REPOSO, (170, 18, 176, 14)), 0.0),
    "mirar_izq": (_r(lumbar=(0, 6, 0), pecho=(10, 14, 0), cuello=(18, 2, 0), cabeza=(28, -2, 0)), _b((42, 18, 92, -30)), 0.01),
    "mirar_der": (_r(lumbar=(0, 6, 0), pecho=(-10, 14, 0), cuello=(-18, 2, 0), cabeza=(-28, -2, 0)), _b((42, 18, 92, -30)), 0.01),
    "asentir_a": (_r(cabeza=(0, -4, 0)), _b(REPOSO), 0.0),
    "asentir_b": (_r(cuello=(0, 6, 0), cabeza=(0, 16, 0)), _b(REPOSO), 0.0),
    "negar_a": (_r(cuello=(12, 3, 0), cabeza=(26, 4, 0)), _b((-20, 10, -26, -56)), 0.0),
    "negar_b": (_r(cuello=(-12, 3, 0), cabeza=(-26, 4, 0)), _b((-20, 10, -26, -56)), 0.0),
    "frotar_a": (_r(cabeza=(0, 8, 0)), _b((26, 8, 84, -38)), 0.0),
    "frotar_b": (_r(cabeza=(0, 8, 0)), _b((24, 8, 78, -44), (28, 8, 90, -32)), 0.0),
    "abrir_a": (_r(pecho=(0, 8, 0)), _b((76, 22, 90, 18)), 0.01),
    "abrir_b": (_r(pecho=(0, 10, 0)), _b((82, 52, 88, 74)), 0.01),
}


@dataclass(frozen=True)
class Accion:
    clip: str = None             # clip del .glb que suena (Saludar, Hablar); None = Idle + poses
    a: str = None                # pose fija (o la primera de las dos que se alternan)
    b: str = None                # segunda pose (se alterna con a)
    hz: float = 0.0              # alternancias por segundo (0 = fija)
    salto: float = 0.0           # m del saltito (celebrar)
    bote: float = 0.0            # m de bote suave al compás
    por_k: bool = False          # de a a b una sola vez, con el avance del paso (abrir postigos)


ACCIONES = {
    "quieto": Accion(),
    "caminar": Accion(),
    "saludar": Accion(clip="Saludar"),
    "hablar": Accion(clip="Hablar"),
    "aplaudir": Accion(a="aplauso_a", b="aplauso_b", hz=2.4),
    "celebrar": Accion(a="arriba_a", b="arriba_b", hz=1.5, salto=0.2),
    "protestar": Accion(a="pancarta_abajo", b="pancarta_arriba", hz=0.55),
    "pancarta_abajo": Accion(a="pancarta_abajo"),
    "puno": Accion(a="puno_medio", b="puno_arriba", hz=1.1),
    "brazos_cruzados": Accion(a="brazos_cruzados"),
    "manos_atras": Accion(a="manos_atras"),
    "cintura": Accion(a="cintura"),
    "cabeza_baja": Accion(a="cabeza_baja"),
    "gracias": Accion(a="gracias", b="reverencia", hz=0.3),
    "teclear": Accion(a="teclear_a", b="teclear_b", hz=4.0),
    "contar": Accion(a="contar_a", b="contar_b", hz=1.3),
    "reloj": Accion(a="reloj"),
    "apoyado": Accion(a="apoyado"),
    "encogerse": Accion(a="encogerse", b="respirar_a", hz=0.5),
    "mas_o_menos": Accion(a="mas_menos_a", b="mas_menos_b", hz=1.6),
    "nuca": Accion(a="nuca_a", b="nuca_b", hz=2.2),
    "dar_mano": Accion(a="dar_mano"),
    "leer": Accion(a="leer"),
    "levantar_nota": Accion(a="nota"),
    "guitarra": Accion(a="guitarra_a", b="guitarra_b", hz=3.0, bote=0.02),
    "tambor": Accion(a="tambor_a", b="tambor_b", hz=2.4, bote=0.02),
    "maracas": Accion(a="maracas_a", b="maracas_b", hz=3.0, bote=0.02),
    "barrer": Accion(a="barrer_a", b="barrer_b", hz=0.9),
    "bailar": Accion(a="bailar_a", b="bailar_b", hz=1.0, bote=0.05),
    "respirar": Accion(a="respirar_a", b="respirar_b", hz=0.3),
    "acomodar_banda": Accion(a="banda_a", b="banda_b", hz=0.9),
    "brazo_arriba": Accion(a="brazo_arriba"),
    "mirar_lados": Accion(a="mirar_izq", b="mirar_der", hz=0.25),
    "asentir": Accion(a="asentir_a", b="asentir_b", hz=1.3),
    "negar": Accion(a="negar_a", b="negar_b", hz=2.0),
    "frotar": Accion(a="frotar_a", b="frotar_b", hz=3.2),
    "abrir": Accion(a="abrir_a", b="abrir_b", por_k=True),
}


@dataclass(frozen=True)
class Objetivo:
    clip: str                    # clip lógico del personaje (Idle, Saludar, Hablar)
    pesos: dict                  # pose -> peso 0..1
    dy: float                    # m que sube el cuerpo entero
    mezcla_b: float              # 0..1: cuánto de la pose b (para los props: pancarta arriba, escoba a un lado)


def poses_de(accion):
    """Poses que necesita una acción (para hornear solo esas)."""
    a = ACCIONES.get(accion, ACCIONES["quieto"])
    return tuple(p for p in (a.a, a.b) if p is not None)


def objetivo(accion, segundos, fase=0.0, k=0.0):
    """Lo que hace el cuerpo `segundos` después de empezar el plano con esa acción. `fase` desfasa la alternancia
    (0..1) y `k` es el avance del paso (para las acciones por_k). Total: una acción desconocida = quieto."""
    a = ACCIONES.get(accion, ACCIONES["quieto"])
    if a.clip is not None:
        return Objetivo(a.clip, {}, 0.0, 0.0)
    if a.a is None:
        return Objetivo("Idle", {}, 0.0, 0.0)
    if a.b is None:
        return Objetivo("Idle", {a.a: 1.0}, 0.0, 0.0)
    if a.por_k:
        m = max(0.0, min(1.0, k))
        m = m * m * (3 - 2 * m)
    else:
        m = 0.5 - 0.5 * math.cos(2 * math.pi * (a.hz * segundos + fase))
    dy = 0.0
    if a.salto:
        dy = a.salto * max(0.0, math.sin(2 * math.pi * (a.hz * segundos + fase) - math.pi / 2)) ** 1.5
    elif a.bote:
        dy = a.bote * (0.5 - 0.5 * math.cos(4 * math.pi * (a.hz * segundos + fase)))
    return Objetivo("Idle", {a.a: 1.0 - m, a.b: m}, dy, m)


def pose_de(nombre, m=None):
    """La pose `nombre` armada con las medidas `m` del esqueleto (ac.Medidas)."""
    rots, brazos, baja = POSES[nombre]
    return pc._de_pie(m or ac.Medidas(), rots, brazos, baja=0.005 + baja)
